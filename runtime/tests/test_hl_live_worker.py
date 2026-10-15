import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from coinmaster.ops.hl_live_worker import LiveWorker, require_live_order_approval, SEALED_V0_SHA
from coinmaster.ops.stage_g_config import load_testnet_instance_config

ROOT = Path(__file__).resolve().parents[1]


def test_live_paths_and_identities_are_separate():
    live = load_testnet_instance_config(ROOT / "configs/hl-stageg-live.instance.json")
    sandbox = load_testnet_instance_config(ROOT / "configs/hl-stageg-testnet.instance.json")
    assert live.strategy_config == Path("/srv/coinmaster/hl-live/current/configs/hl-live-v3-dp50.candidate.json").resolve()
    assert live.strategy_config != sandbox.strategy_config
    assert live.state_db != sandbox.state_db
    assert live.signal_warmup_manifest != sandbox.signal_warmup_manifest


def test_approval_required_before_credential_or_journal_access(monkeypatch):
    monkeypatch.setattr("coinmaster.ops.hl_live_worker.load_testnet_instance_config", lambda _: SimpleNamespace())
    monkeypatch.setattr("coinmaster.ops.hl_live_worker.PaperRuntime", lambda *a, **k: pytest.fail("journal touched before approval"))
    monkeypatch.setattr("coinmaster.ops.hl_live_worker.check_live_credential", lambda *a, **k: pytest.fail("credential touched before approval"))
    with pytest.raises(RuntimeError, match="LIVE_OWNER_ORDER_APPROVAL_REQUIRED"):
        LiveWorker({"COINMASTER_HL_LIVE_INSTANCE_CONFIG": "unused", "COINMASTER_LIVE_ORDER_APPROVAL": "/nonexistent"})


def test_exact_release_account_strategy_approval(tmp_path):
    fingerprints = tmp_path / "fingerprints.json"
    fingerprints.write_text(json.dumps({"master_address_sha256": "master"}))
    (tmp_path / "live-release.json").write_text(json.dumps({"source_commit": "commit", "strategy_sha256": SEALED_V0_SHA, "candidate_sha256": "candidate", "profile_sha256": "profile"}))
    approval = {"schema": "coinmaster-live-order-approval-v1", "instance_id": "hl-stageg-live",
                "orders_approved": True, "pilot_capital_usdc": "82", "release_commit": "commit", "master_address_sha256": "master",
                "strategy_sha256": SEALED_V0_SHA, "candidate_sha256": "candidate", "profile_sha256": "profile"}
    path = tmp_path / "approval.json"
    for key, wrong in (("orders_approved", False), ("release_commit", "old"), ("master_address_sha256", "foreign"), ("strategy_sha256", "other")):
        path.write_text(json.dumps({**approval, key: wrong}))
        with pytest.raises(RuntimeError, match="LIVE_OWNER_ORDER_APPROVAL_REQUIRED"):
            require_live_order_approval(path, fingerprints, tmp_path)
    path.write_text(json.dumps(approval))
    require_live_order_approval(path, fingerprints, tmp_path)


def test_snapshot_failure_latches_client_and_persists_manual_restart(tmp_path):
    failures = []
    worker = object.__new__(LiveWorker)
    worker.recovery_marker = tmp_path / "manual-recovery-required"
    strategy = SimpleNamespace(recovery_confirmed=True)
    client = SimpleNamespace(_cm_fail=failures.append)
    worker.native = SimpleNamespace(strategy=strategy, node=SimpleNamespace(kernel=SimpleNamespace(exec_engine=SimpleNamespace(_clients={"live": client}))))
    worker._manual_recovery()
    assert not strategy.recovery_confirmed
    assert failures == ["LIVE_WORKER_SNAPSHOT_FAILED"]
    assert worker.recovery_marker.read_text() == "LIVE_WORKER_SNAPSHOT_FAILED\n"


def test_sealed_v3_real_node_build_without_connect(tmp_path, monkeypatch):
    """Actual factory/strategy/kernel composition; no run/connect or secret source."""
    import hashlib
    import os
    from dataclasses import replace
    from decimal import Decimal
    from coinmaster.ops.hl_live_worker import HyperliquidLiveNode, LiveSubmissionHooks
    from coinmaster.ops.hl_live_execution import QualifiedHyperliquidExecutionClient
    from coinmaster.ops.paper import PaperRuntime
    from coinmaster.ops.stage_g_config import load_candidate

    monkeypatch.setattr("coinmaster.ops.hl_live_worker.check_live_credential", lambda *a: Decimal("82"))
    monkeypatch.setattr("coinmaster.ops.hl_live_worker._read_json", lambda _: {
        "master_address": "0x" + "1" * 40, "agent_private_key": "0x" + "2" * 64,
    })
    instance = replace(
        load_testnet_instance_config(ROOT / "configs/hl-stageg-live.instance.json"),
        signal_warmup_manifest=Path(os.getenv("COINMASTER_TEST_LIVE_WARMUP", "/var/lib/coinmaster-hl-stageg-testnet/data/current/manifest.json")),
        state_db=tmp_path / "live.sqlite",
    )
    runtime = PaperRuntime(instance.state_db, instance.instance_id, int(120e9), require_native_cash=True)
    runtime.acquire()
    try:
        native = HyperliquidLiveNode(instance=instance, candidate=load_candidate(ROOT / "configs/hl-live-v3-dp50.candidate.json").candidate,
                                    state=runtime, credential_path=tmp_path / "not-read", fingerprint_path=tmp_path / "not-read")
        assert native.node.is_built() and not native.node.is_running()
        clients = tuple(native.node.kernel.exec_engine._clients.values())
        assert len(clients) == 1 and isinstance(clients[0], QualifiedHyperliquidExecutionClient)
        assert native.config.exec_clients["HYPERLIQUID-LIVE"].account_address == "0x" + "1" * 40
        assert native.config.exec_clients["HYPERLIQUID-LIVE"].include_builder_attribution is False
        assert native.strategy.config.margin_policy is None
        assert not native.strategy.recovery_confirmed
        assert not native._entries_enabled()
        assert isinstance(native.strategy.config.submission_sink, LiveSubmissionHooks)
        assert native.strategy.config.deposit_instance_id == "hl-stageg-live"
        assert native.strategy.config.deposit_account_id == str(clients[0].account_id)
        assert not native.node.cache.instruments()
        native.node.dispose()
        native.loop.close()
    finally:
        runtime.close()


def test_expected_stale_money_defers_snapshot_without_manual_latch(tmp_path):
    worker = object.__new__(LiveWorker)
    worker.recovery_marker = tmp_path / "manual-recovery-required"
    refreshes = []
    def stale():
        raise ValueError("LIVE_MONEY_STALE_OR_UNKNOWN")
    strategy = SimpleNamespace(recovery_confirmed=True, _validated_live_money=stale, _request_live_refresh=lambda: None)
    worker.runtime = SimpleNamespace(heartbeat=lambda _: None)
    worker.native = SimpleNamespace(strategy=strategy, loop=SimpleNamespace(call_soon_threadsafe=refreshes.append))
    # Logical idle timeline spans more than two 30s monitor intervals.
    for elapsed_seconds in (15, 30, 45, 60, 75):
        worker.poll()
    assert strategy.recovery_confirmed
    assert len(refreshes) == 5
    assert not worker.recovery_marker.exists()


def test_stale_projection_returns_unavailable_account_without_latch(tmp_path):
    worker = object.__new__(LiveWorker)
    refreshes = []
    def stale():
        raise ValueError("LIVE_MONEY_STALE_OR_UNKNOWN")
    strategy = SimpleNamespace(recovery_confirmed=True, _validated_live_money=stale,
                               _request_live_refresh=lambda: None, deposit_projection=lambda: {"state": "ARMED"})
    worker.native = SimpleNamespace(
        strategy=strategy, loop=SimpleNamespace(call_soon_threadsafe=refreshes.append),
        status=lambda: {"state": "READY", "orders_enabled": True},
        native_snapshot=lambda: ([], []))
    worker.runtime = SimpleNamespace(
        heartbeat=lambda _: None, projection_events=lambda _: ([], 0),
        entry_control_state=lambda: "RUNNING")
    worker.run_epoch, worker.control_available = "test", True
    worker.recovery_marker = tmp_path / "manual-recovery-required"
    view = worker.projection()
    assert view["state"] == "LIVE_MONEY_STALE/PAUSED"
    assert view["orders_enabled"] is False
    assert view["account"] == {} and view["account_state"] == "UNAVAILABLE"
    assert len(refreshes) == 2
    assert not worker.recovery_marker.exists()
