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
            "state": "PUBLIC_FEEDS_READY", "native_thread_alive": True, "account_state": "CURRENT",
            "account": {"native_cash": "81.5", "equity": "82.3", "withdrawable": "70", "margin_used": "11.5"},
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
