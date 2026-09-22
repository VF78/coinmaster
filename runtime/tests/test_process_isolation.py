from __future__ import annotations

import os
import sys
import time
from types import SimpleNamespace

from coinmaster.api.app import BASELINE_CONFIG, ControlStore, StrategyConfig, configured_research_data_root
from coinmaster.api.research_jobs import ResearchJobManager
from coinmaster.ops.hyperliquid_testnet import BTC_PERP, FeedBook, HyperliquidTestnetNode
from scripts.process_isolation_doctor import check, check_host_metadata


def test_d4_deployment_ownership_credential_and_path_doctor_is_clean() -> None:
    assert check() == []


def test_research_child_environment_excludes_trader_secrets_and_state_paths() -> None:
    child = ResearchJobManager.isolated_child_environment({
        "PATH": "/bin",
        "HYPERLIQUID_TESTNET_PK": "must-not-reach-research",
        "COINMASTER_HL_TESTNET_MASTER_ACCOUNT_ADDRESS": "0x123",
        "COINMASTER_PAPER_DB": "/var/lib/coinmaster-paper/paper.sqlite",
        "COINMASTER_RUNTIME_CONTROL_DB": "/var/lib/coinmaster-runtime/control.sqlite",
        "COINMASTER_RUNTIME_API_TOKEN": "must-not-reach-research",
    })
    assert child == {"PATH": "/bin", "COINMASTER_RESEARCH_CHILD": "true"}


def test_local_fixture_checks_real_owner_and_mode_contract(tmp_path) -> None:
    trader_env = tmp_path / "trader.env"; trader_env.write_text("HYPERLIQUID_TESTNET_PK=fixture\n")
    runtime_env = tmp_path / "runtime.env"; runtime_env.write_text("COINMASTER_RUNTIME_API_TOKEN=fixture\n")
    trader_state = tmp_path / "trader-state"; trader_state.mkdir()
    research_state = tmp_path / "research-state"; research_state.mkdir()
    trader_env.chmod(0o600); runtime_env.chmod(0o600); trader_state.chmod(0o700); research_state.chmod(0o700)
    assert check_host_metadata(
        trader_env=trader_env, runtime_env=runtime_env,
        trader_state_dir=trader_state, research_state_dir=research_state,
        root_uid=os.getuid(), trader_uid=os.getuid(), research_uid=os.getuid(),
    ) == []
    trader_env.chmod(0o644)
    assert any(item.startswith("UNSAFE_MODE") for item in check_host_metadata(
        trader_env=trader_env, runtime_env=runtime_env,
        trader_state_dir=trader_state, research_state_dir=research_state,
        root_uid=os.getuid(), trader_uid=os.getuid(), research_uid=os.getuid(),
    ))


def test_runtime_research_data_root_is_writable_state_directory_for_job_creation(tmp_path, monkeypatch) -> None:
    state_data = tmp_path / "coinmaster-runtime" / "data"
    monkeypatch.setenv("COINMASTER_RESEARCH_DATA_ROOT", str(state_data))
    assert configured_research_data_root() == state_data
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    command = [sys.executable, "-m", "coinmaster.research.job_test_helper", "--mode", "complete"]
    manager = ResearchJobManager(store, configured_research_data_root(), {"native_baseline": command}, test_options={})
    run = manager.start(config, "native_baseline")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = store.get_run(run.id)
        if result.status not in {"STARTING", "RUNNING", "CANCEL_REQUESTED"}:
            break
        time.sleep(0.02)
    assert result.status == "COMPLETED"
    assert state_data in __import__("pathlib").Path(run.work_dir).parents


def test_actual_popen_child_does_not_inherit_venue_credentials_or_trader_paths(tmp_path, monkeypatch) -> None:
    for key in (
        "HYPERLIQUID_TESTNET_PK", "HYPERLIQUID_PRIVATE_KEY", "BYBIT_API_KEY",
        "BYBIT_API_SECRET", "COINMASTER_HL_TESTNET_MASTER_ACCOUNT_ADDRESS",
        "COINMASTER_PAPER_DB", "COINMASTER_RUNTIME_CONTROL_DB",
    ):
        monkeypatch.setenv(key, "synthetic-sentinel")
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    command = [sys.executable, "-m", "coinmaster.research.job_test_helper", "--mode", "environment"]
    manager = ResearchJobManager(store, tmp_path / "data", {"native_baseline": command}, test_options={})
    run = manager.start(config, "native_baseline")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = store.get_run(run.id)
        if result.status not in {"STARTING", "RUNNING", "CANCEL_REQUESTED"}:
            break
        time.sleep(0.02)
    assert result.status == "COMPLETED"
    assert result.report["sensitive_environment_present"] == []


def test_research_child_and_public_only_trader_observation_stub_run_concurrently(tmp_path) -> None:
    """D4 smoke: a bounded research child does not need a trader node or secret."""
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    command = [sys.executable, "-m", "coinmaster.research.job_test_helper", "--mode", "sleep"]
    manager = ResearchJobManager(store, tmp_path / "data", {"native_baseline": command}, test_options={})
    run = manager.start(config, "native_baseline")
    try:
        class Trader:
            def __init__(self): self.added = []
            def add_strategy(self, strategy): self.added.append(strategy)
        observation = HyperliquidTestnetNode.__new__(HyperliquidTestnetNode)
        observation.node = SimpleNamespace(trader=Trader())
        observation.feed = FeedBook(ids=(BTC_PERP,))
        observation.feed_observer = None
        observation.prime_error = None
        observation.prime()
        assert run.status == "RUNNING"
        assert observation.prime_error is None
        assert len(observation.node.trader.added) == 1
        assert not hasattr(observation, "strategy")
    finally:
        canceled = manager.cancel(run.id)
        assert canceled.status == "CANCELED"
