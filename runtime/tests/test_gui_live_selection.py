"""Selected Live is a separate native account and remains read-only without approval."""
import io
import json
import time
from urllib.error import URLError

import pytest
from fastapi import HTTPException
import coinmaster.api.runtime_sidecar as sidecar


def live(**patch):
    return {"instance_id": "hl-stageg-live", "mode": "live", "environment": "mainnet",
            "version": "hl-stageg-live-projection-v1", "provenance": "NATIVE_MAINNET_OWNED_ACCOUNT",
            "live_order_capability": True, "run_epoch": "live-epoch", "observed_at_ns": time.time_ns(),
            "money_currency": "USDC", "equity_basis": sidecar.USDC_EQUITY_BASIS,
            "state": "PUBLIC_FEEDS_READY", "native_thread_alive": True, "account_state": "CURRENT",
            "account": {"currency": "USDC", "money_currency": "USDC", "equity_basis": sidecar.USDC_EQUITY_BASIS,
                        "margin_basis": sidecar.USDC_MARGIN_BASIS, "native_cash": "81.5", "equity": "82.3", "native_free": "70", "native_locked": "11.5"},
            "profile": {"profile_id": "V3+DP50", "initial_capital_usdc": "82", "deposit_protection_percent": 50},
            "entry_control": {"state": "RUNNING", "capability": "READY"}, "recovery_required": False,
            "orders_enabled": True, "feeds": {}, "positions": [], "orders": [], "events": [], **patch}


def respond(monkeypatch, payload):
    monkeypatch.setattr(sidecar.urllib.request, "urlopen", lambda *_args, **_kwargs: io.BytesIO(json.dumps(payload).encode()))


def test_live_projection_preserves_native_money_and_denies_controls(monkeypatch):
    respond(monkeypatch, live())
    result = sidecar.HlLiveProjectionReader("http://127.0.0.1:18185").runtime()
    assert result.projection_state == "READY" and result.instance_id == "hl-stageg-live"
    assert result.account.native_cash == "81.5" and result.account.equity == "82.3"
    assert result.account.native_free == "70" and result.account.native_locked == "11.5"
    assert result.profile["initial_capital_usdc"] == "82" and result.real_order_approval is False
    controls = sidecar.hl_stageg_controls(result, True)
    assert controls.instance_id == result.instance_id and controls.mode == "live"
    assert all(not getattr(controls, key).enabled for key in ("pause", "resume", "flatten", "promotion"))
    assert controls.pause.blocker == "EXACT_LIVE_ORDER_APPROVAL_REQUIRED"
    # Widened common schema must not allow a Live producer through Sandbox routing.
    assert sidecar.HlStagegProjectionReader("http://127.0.0.1:18183").runtime().projection_state == "INVALID"


@pytest.mark.parametrize("patch,expected", [({"instance_id": "hl-stageg-testnet"}, "INVALID"), ({"mode": "sandbox"}, "INVALID"), ({"live_order_capability": False}, "INVALID"), ({"observed_at_ns": 1}, "STALE"), ({"observed_at_ns": None}, "INVALID"), ({"account_state": "UNAVAILABLE", "account": {}}, "READY")])
def test_live_projection_fails_closed_and_never_infers_seed(monkeypatch, patch, expected):
    respond(monkeypatch, live(**patch))
    result = sidecar.HlLiveProjectionReader("http://127.0.0.1:18185").runtime()
    assert result.instance_id == "hl-stageg-live" and result.mode == "live"
    assert result.projection_state == expected
    assert result.account.native_cash is None
    assert result.account.equity is None


def test_live_unreachable_preserves_identity_unknown_cash(monkeypatch):
    def unavailable(*_args, **_kwargs): raise URLError("offline")
    monkeypatch.setattr(sidecar.urllib.request, "urlopen", unavailable)
    result = sidecar.HlLiveProjectionReader("http://127.0.0.1:18185").runtime()
    assert result.projection_state == "UNAVAILABLE" and result.instance_id == "hl-stageg-live"
    assert result.account.native_cash is None and result.sandbox_starting_cash_usdc is None


def test_live_post_has_auth_and_never_contacts_any_worker(tmp_path, monkeypatch):
    app = sidecar.create_runtime_app(database=str(tmp_path / "none.sqlite"), control_database=str(tmp_path / "control.sqlite"), token="operator")
    route = next(item for item in app.routes if getattr(item, "path", "") == "/api/v1/instances/hl-stageg-live/controls/{command}")
    assert any(dependency.call.__name__ == "auth" for dependency in route.dependant.dependencies)
    def no_contact(*_args, **_kwargs): raise AssertionError("Live control contacted a worker")
    monkeypatch.setattr(sidecar.urllib.request, "urlopen", no_contact)
    for command in ("pause-new-entries", "resume-new-entries", "set-deposit-protection", "reset-deposit-protection", "flatten", "activate"):
        with pytest.raises(HTTPException) as denied: route.endpoint(command, "nonce")
        assert denied.value.status_code == 403


def test_live_planned_profile_is_source_checked_and_separate():
    result = sidecar.HlLiveStrategyReader().strategy()
    assert result.instance_id == "hl-stageg-live" and result.mode == "live"
    assert result.promotion_enabled is False
    if result.source_state == "SEALED_CONFIGURATION_CHECKED":
        assert "82 USDC" in result.capital_assumption and "not an observed account balance" in result.capital_assumption
        assert result.candidate["deposit_protection_percent"] == "50"


def approved_projection(monkeypatch):
    hashes = dict(strategy_sha256="strategy", candidate_sha256="candidate", profile_sha256="profile")
    payload = live(profile={**hashes, "profile_id": "V3+DP50"}, release_commit="release", master_address_sha256="account", real_order_approval=True)
    identity = {"source_commit": "release", **hashes}
    approval = {"schema": "coinmaster-live-order-approval-v1", "instance_id": "hl-stageg-live",
                "orders_approved": True, "pilot_capital_usdc": "82", "release_commit": "release",
                "master_address_sha256": "account", **hashes}
    original_read = sidecar.Path.read_text
    original_resolve = sidecar.Path.resolve
    monkeypatch.setattr(sidecar.Path, "resolve", lambda path, *args, **kwargs: path if str(path) == "/srv/coinmaster/hl-live/current" else original_resolve(path, *args, **kwargs))
    def read(path, *args, **kwargs):
        if path.name == "live-release.json": return json.dumps(identity)
        if path.name == "hl-stageg-live.account-fingerprint.json": return json.dumps({"master_address_sha256": "account"})
        if str(path) == "/etc/coinmaster/live-order-approval.json": return json.dumps(approval)
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(sidecar.Path, "read_text", read)
    respond(monkeypatch, payload)
    return sidecar.HlLiveProjectionReader("http://127.0.0.1:18185").runtime()


def test_approved_live_controls_are_capability_gated_not_permanently_denied(monkeypatch):
    projection = approved_projection(monkeypatch)
    assert projection.real_order_approval and projection.warnings == []
    controls = sidecar.hl_stageg_controls(projection, True)
    assert controls.pause.enabled and controls.resume.enabled
    assert not controls.flatten.enabled and not controls.promotion.enabled
    assert not sidecar.hl_stageg_controls(projection, False).pause.enabled


@pytest.mark.parametrize("patch", [
    {"runtime_release_commit": "old-release"}, {"runtime_master_address_sha256": "foreign"},
    {"recovery_required": True}, {"reconciliation": "UNKNOWN"}, {"native_thread_alive": False},
    {"observed_at_ns": 1}, {"profile": {}},
])
def test_approval_rejects_runtime_identity_or_freshness_mismatch(monkeypatch, patch):
    projection = approved_projection(monkeypatch).model_copy(update=patch)
    assert sidecar.live_order_approval_matches(projection) is False


def test_live_control_relays_exact_nonce_instance_and_checks_new_epoch(tmp_path, monkeypatch):
    app = sidecar.create_runtime_app(database=str(tmp_path / "none.sqlite"), control_database=str(tmp_path / "control.sqlite"), token="operator")
    projection = approved_projection(monkeypatch)
    monkeypatch.setattr(sidecar.Path, "is_file", lambda _path: True)
    monkeypatch.setattr(sidecar, "live_order_approval_matches", lambda _projection: True)
    monkeypatch.setattr(sidecar, "hl_stageg_controls", lambda _p, _transport: sidecar.HlStagegControls(instance_id="hl-stageg-live", mode="live", projection_state="READY", pause={"enabled": True}, resume={"enabled": True}, flatten={}, promotion={}))
    monkeypatch.setattr(sidecar.HlLiveProjectionReader, "runtime", lambda _reader: projection)
    calls = []
    def command(relay, command, nonce):
        calls.append((relay.url, relay.instance_id, command, nonce))
        return sidecar.HlStagegControlCommand(instance_id="hl-stageg-live", command=command, idempotency_key=nonce, status="ACCEPTED", entry_control="RUNNING")
    monkeypatch.setattr(sidecar.HlStagegControlRelay, "command", command)
    route = next(item for item in app.routes if getattr(item, "path", "") == "/api/v1/instances/hl-stageg-live/controls/{command}")
    result = route.endpoint("resume-new-entries", "live-nonce")
    assert result.idempotency_key == "live-nonce"
    assert calls == [("http://127.0.0.1:18185", "hl-stageg-live", "resume-new-entries", "live-nonce")]
    snapshots = iter([projection, projection.model_copy(update={"run_epoch": "different"})])
    monkeypatch.setattr(sidecar.HlLiveProjectionReader, "runtime", lambda _reader: next(snapshots))
    with pytest.raises(HTTPException, match="503"):
        route.endpoint("resume-new-entries", "second-nonce")


def test_entry_relay_rejects_nonce_from_other_command(monkeypatch):
    respond(monkeypatch, {"instance_id": "hl-stageg-live", "command": "pause-new-entries",
                         "idempotency_key": "foreign-nonce", "status": "ACCEPTED", "entry_control": "PAUSED"})
    with pytest.raises(HTTPException, match="503"):
        sidecar.HlStagegControlRelay("http://127.0.0.1:18185", "test", "hl-stageg-live").command("pause-new-entries", "correct-nonce")
