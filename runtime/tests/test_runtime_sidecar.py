from decimal import Decimal

import io
import json
import pytest
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import RedirectResponse

from coinmaster.api.runtime_sidecar import HlStagegControlRelay, HlStagegDepositProtection, HlStagegDepositProtectionRelay, HlStagegProtectionCommandRequest, HlStagegProjection, HlStagegProjectionReader, HlStagegStrategyReader, RuntimeReader, create_runtime_app, hl_stageg_controls
from coinmaster.ops.hyperliquid_testnet_worker import TestnetWorker as HlStagegWorker, create_status_server
from coinmaster.ops.paper import PaperRuntime


def test_runtime_sidecar_reader_has_decimals_cursor_and_unknowns_when_worker_disconnected(tmp_path) -> None:
    database = tmp_path / "paper.sqlite"; runtime = PaperRuntime(database, "paper", 100)
    runtime.acquire(); runtime.snapshot(ts_ns=1, positions=[], orders=[], funding_event_ids=[])
    runtime.record_modelled_funding(event_id="bybit:BTC:2", instrument_id="BTC", settlement_ns=2, rate=Decimal("0.01"), mark=Decimal("100"), signed_quantity=Decimal("1"))
    runtime.record_native_event("fill-1", "fill"); runtime.close()
    reader = RuntimeReader(str(database), "http://127.0.0.1:9")
    body = reader.runtime()
    assert body.version == "runtime-v1" and body.balances.active_usdt == "UNKNOWN"
    assert body.live_order_capability is None
    assert body.balances.modelled_funding_cash == "-1.00"
    assert body.funding[0].state == "MODELLED_LEDGER_UNPOSTED"
    events = reader.events(0)
    assert events.events[0].cursor > 0


def test_runtime_sidecar_exposes_strict_schemas_and_spa_without_shadowing_api(tmp_path, monkeypatch) -> None:
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<main>paper runtime</main>")
    (dist / "assets" / "app.js").write_text("export {}")
    monkeypatch.setenv("COINMASTER_RUNTIME_DIST", str(dist))
    app = create_runtime_app(database=str(tmp_path / "missing.sqlite"), control_database=str(tmp_path / "control.sqlite"), token="operator", worker_url="http://127.0.0.1:9", worker_token="relay")
    spec = app.openapi()
    schemas = spec["components"]["schemas"]
    for name in ("RuntimeState", "RuntimeBalances", "RuntimeStrategy", "RuntimeFeed", "RuntimeEvent", "RuntimeFunding", "RuntimeEventsResponse", "RuntimeCommandResponse", "HlStagegProjection", "HlStagegStrategy", "HlStagegHashes", "HlStagegControls", "HlStagegControlAction"):
        assert schemas[name]["additionalProperties"] is False
    assert schemas["RuntimeBalances"]["properties"]["active_usdt"]["type"] == "string"
    for path in ("/api/v1/configurations/default", "/api/v1/configurations", "/api/v1/preflight", "/api/v1/runs", "/api/v1/research/catalog", "/api/v1/runtime", "/api/v1/runtime/commands/{command}", "/api/v1/instances/hl-stageg-testnet", "/api/v1/instances/hl-stageg-testnet/strategy", "/api/v1/instances/hl-stageg-testnet/controls"):
        assert path in spec["paths"]
    assert "ResearchCatalogEntry" in schemas and "StrategyConfig" in schemas
    paths = [getattr(route, "path", "") for route in app.routes]
    assert "/api/v1/openapi.json" in paths and "/api/v1/runtime" in paths and "/{path:path}" in paths
    # The SPA fallback is registered after API routes and routes an
    # unauthenticated browser to the single operator login.
    spa = next(route for route in app.routes if getattr(route, "path", "") == "/{path:path}")
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("127.0.0.1", 1234), "scheme": "http"})
    assert isinstance(spa.endpoint("", request, None), RedirectResponse)
    response = spa.endpoint("", request, "Bearer operator")
    assert response.path == dist / "index.html"
    assert spa.endpoint("api/v1/not-a-route", request, "Bearer operator").status_code == 404


def test_hl_stageg_controls_are_authenticated_instance_bound_and_fail_closed(tmp_path) -> None:
    app = create_runtime_app(database=str(tmp_path / "missing.sqlite"), control_database=str(tmp_path / "control.sqlite"), token="operator", worker_url="http://127.0.0.1:9", hl_stageg_status_url="http://127.0.0.1:9")
    path = "/api/v1/instances/hl-stageg-testnet/controls"
    route = next(item for item in app.routes if getattr(item, "path", "") == path)
    auth = next(dependency.call for dependency in route.dependant.dependencies if dependency.call.__name__ == "auth")
    request = Request({"type": "http", "method": "GET", "path": path, "headers": [], "client": ("127.0.0.1", 1234), "scheme": "http"})
    with pytest.raises(HTTPException) as denied:
        auth(request, None, None)
    assert denied.value.status_code == 401
    auth(request, "Bearer operator", None)
    body = route.endpoint().model_dump()
    assert body["instance_id"] == "hl-stageg-testnet" and body["mode"] == "sandbox"
    assert body["projection_state"] == "UNAVAILABLE"
    assert all(body[action]["enabled"] is False for action in ("pause", "resume", "flatten", "promotion"))
    assert body["pause"]["blocker"] == "NATIVE_PROJECTION_UNAVAILABLE"
    assert body["flatten"]["requires_confirmation"] is True
    assert app.openapi()["paths"][path].keys() == {"get"}
    assert "/api/v1/instances/hl-stageg-testnet/controls/{command}" in app.openapi()["paths"]
    assert "/api/v1/instances/hl-stageg-testnet/controls/set-deposit-protection" in app.openapi()["paths"]
    assert "/api/v1/instances/hl-stageg-testnet/controls/reset-deposit-protection" in app.openapi()["paths"]

    ready = hl_stageg_controls(HlStagegProjection.model_validate(_ready_hl_projection()))
    assert ready.pause.enabled is False and ready.pause.blocker == "NATIVE_ENTRY_CONTROL_UNAVAILABLE"
    assert ready.resume.enabled is False and ready.resume.blocker == "NATIVE_ENTRY_CONTROL_UNAVAILABLE"
    transport_missing = _ready_hl_projection()
    transport_missing["entry_control"] = {"state": "RUNNING", "capability": "READY"}
    transport_missing = hl_stageg_controls(HlStagegProjection.model_validate(transport_missing))
    assert transport_missing.pause.enabled is False and transport_missing.pause.blocker == "NATIVE_ENTRY_CONTROL_TRANSPORT_UNAVAILABLE"
    worker_ready = _ready_hl_projection()
    worker_ready["entry_control"] = {"state": "RUNNING", "capability": "READY"}
    ready = hl_stageg_controls(HlStagegProjection.model_validate(worker_ready), control_transport_available=True)
    assert ready.pause.enabled is True and ready.pause.blocker is None
    assert ready.resume.enabled is True and ready.resume.blocker is None
    assert ready.flatten.blocker == "NO_IDEMPOTENT_NATIVE_FLATTEN_RECOVERY"
    assert ready.promotion.blocker == "SEPARATE_NATIVE_LIFECYCLE_GATE_REQUIRED"


def test_isolated_gui_has_no_paper_command_route_without_relay_token(tmp_path) -> None:
    app = create_runtime_app(database=str(tmp_path / "missing.sqlite"), control_database=str(tmp_path / "control.sqlite"), token="operator", worker_token="", worker_url="http://127.0.0.1:9")
    assert "/api/v1/runtime/commands/{command}" not in app.openapi()["paths"]
    assert all(getattr(route, "path", "") != "/api/v1/runtime/commands/{command}" for route in app.routes)


def test_hl_stageg_strategy_is_sealed_source_identity_with_unknown_account_facts() -> None:
    root = Path(__file__).resolve().parents[1]
    body = HlStagegStrategyReader(root).strategy()
    assert body.source_state == "SEALED_SOURCE_CHECKED"
    assert body.instance_id == "hl-stageg-testnet" and body.mode == "sandbox"
    assert body.hashes.candidate_sha256 == "637762130c76396cd7c6e24644e31b28079a1683e4460d57f103dde42c603b6d"
    assert body.candidate["ema_period"] == "34"
    assert body.running_state == "NOT_CONFIRMED"
    assert body.account_margin == "UNKNOWN" and body.account_fee_schedule == "UNKNOWN"
    assert body.promotion_enabled is False
    assert body.promotion_reason == "SEPARATE_NATIVE_LIFECYCLE_GATE_REQUIRED"


def test_hl_stageg_strategy_requires_fresh_full_hash_match_to_claim_running(monkeypatch) -> None:
    import coinmaster.api.runtime_sidecar as sidecar
    root = Path(__file__).resolve().parents[1]
    local = HlStagegStrategyReader(root).strategy()

    mismatched = HlStagegProjection.model_validate(_ready_hl_projection())
    result = HlStagegStrategyReader(root, SimpleNamespace(runtime=lambda: mismatched)).strategy()
    assert result.running_state == "MISMATCH"

    matching_payload = _ready_hl_projection()
    matching_payload["hashes"] = local.hashes.model_dump()
    matching = HlStagegProjection.model_validate(matching_payload)
    result = HlStagegStrategyReader(root, SimpleNamespace(runtime=lambda: matching)).strategy()
    assert result.running_state == "RUNNING_MATCH"

    stale_payload = json.dumps(_ready_hl_projection(observed_at_ns=1)).encode()
    monkeypatch.setattr(sidecar.urllib.request, "urlopen", lambda *args, **kwargs: io.BytesIO(stale_payload))
    stale = HlStagegProjectionReader("http://127.0.0.1:18183").runtime()
    result = HlStagegStrategyReader(root, SimpleNamespace(runtime=lambda: stale)).strategy()
    assert stale.projection_state == "STALE"
    assert result.running_state == "NOT_CONFIRMED"


def _ready_hl_projection(*, observed_at_ns=None, instance_id="hl-stageg-testnet"):
    import time
    return {
        "version": "hl-stageg-projection-v1", "instance_id": instance_id, "projection_state": "READY",
        "observed_at_ns": time.time_ns() if observed_at_ns is None else observed_at_ns,
        "mode": "sandbox", "environment": "mainnet-public", "live_order_capability": False,
        "run_epoch": "test-epoch", "virtual_capital_resets_on_flat_restart": False, "sandbox_starting_cash_usdc": "10000",
        "recovery_required": False, "recovery_capability": "NO_NATIVE_SANDBOX_REHYDRATION", "native_thread_alive": True,
        "process_state": "PUBLIC_FEEDS_READY", "reconciliation": "SANDBOX_LOCAL_PROCESS_RECONCILIATION_ONLY",
        "hashes": {"candidate_sha256": "candidate", "strategy_sha256": "strategy", "execution_policy_sha256": "policy"},
        "warmup": {"state": "READY", "rows": 1482}, "gates": {"attachable": True}, "account": {}, "entry_control": {"state": "RUNNING", "capability": "UNAVAILABLE"},
        "funding_state": "OBSERVED_MODELLED_UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT",
        "feeds": {"BTC-USD-PERP.HYPERLIQUID": {"state": "READY", "mark": "100", "next_funding_ns": None}},
        "positions": [{"instrument_id": "BTC-USD-PERP.HYPERLIQUID", "signed_quantity": "0.01", "provenance": "SANDBOX"}],
        "orders": [], "events": [{"cursor": 3, "event_id": "sandbox-fill", "kind": "fill", "provenance": "SANDBOX"}], "event_cursor": 3,
        "provenance": "SANDBOX_LOCAL_READ_ONLY_WORKER_PROJECTION", "warnings": [],
    }


def test_hl_stageg_projection_is_fresh_instance_bound_and_preserves_unknown_unposted(monkeypatch) -> None:
    import coinmaster.api.runtime_sidecar as sidecar
    response = json.dumps(_ready_hl_projection()).encode()
    monkeypatch.setattr(sidecar.urllib.request, "urlopen", lambda *args, **kwargs: __import__("io").BytesIO(response))
    body = HlStagegProjectionReader("http://127.0.0.1:18183").runtime()
    assert body.projection_state == "READY"
    assert body.run_epoch == "test-epoch" and body.native_thread_alive is True
    assert body.feeds["BTC-USD-PERP.HYPERLIQUID"].next_funding_ns is None
    assert body.positions[0].provenance == "SANDBOX"
    assert body.account.equity is None and body.account.status == "UNAVAILABLE"

    response = json.dumps(_ready_hl_projection(observed_at_ns=1)).encode()
    stale = HlStagegProjectionReader("http://127.0.0.1:18183").runtime()
    assert stale.projection_state == "STALE" and stale.warnings == ["HL_STAGEG_STATUS_STALE"]

    response = json.dumps(_ready_hl_projection(instance_id="coinmaster-paper")).encode()
    wrong_instance = HlStagegProjectionReader("http://127.0.0.1:18183").runtime()
    assert wrong_instance.projection_state == "INVALID"

    def disconnected(*_args, **_kwargs):
        raise URLError("worker stopped")
    monkeypatch.setattr(sidecar.urllib.request, "urlopen", disconnected)
    dead = HlStagegProjectionReader("http://127.0.0.1:18183").runtime()
    assert dead.projection_state == "UNAVAILABLE"
    assert dead.account.native_cash is None and dead.account.status == "UNAVAILABLE"
    assert dead.funding_state == "UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT"



def test_captured_native_owned_tp_passes_strict_api_projection(monkeypatch, tmp_path) -> None:
    import time
    import coinmaster.api.runtime_sidecar as sidecar

    # Captured from the running token-free /status worker endpoint with a
    # native BTC position and owned reduce-only TP. Refresh observation time.
    payload = json.loads((Path(__file__).parent / "fixtures" / "hl_stageg_owned_tp_status.json").read_text())
    assert payload["positions"][0]["signed_quantity"] == "0.53865"
    assert payload["orders"][0]["reduce_only"] is True
    payload["observed_at_ns"] = time.time_ns()
    response = json.dumps(payload).encode()
    monkeypatch.setattr(sidecar.urllib.request, "urlopen", lambda *args, **kwargs: io.BytesIO(response))
    app = create_runtime_app(database=str(tmp_path / "missing.sqlite"), control_database=str(tmp_path / "control.sqlite"), token="operator")
    route = next(item for item in app.routes if getattr(item, "path", "") == "/api/v1/instances/hl-stageg-testnet")
    projected = route.endpoint()
    assert projected.projection_state == "READY"
    assert projected.positions[0].signed_quantity == "0.53865"
    assert projected.orders[0].reduce_only is True
    assert projected.account.status == "UNAVAILABLE" and projected.account.native_cash is None
    assert projected.recovery_required is True
    zero = HlStagegProjection.model_validate({**payload, "account": {"native_cash": "0"}})
    negative = HlStagegProjection.model_validate({**payload, "account": {"native_cash": "-0.1"}})
    assert zero.account.status == "PARTIAL" and zero.account.native_cash == "0"
    assert negative.account.native_cash == "-0.1"
    with pytest.raises(ValueError):
        HlStagegProjection.model_validate({**payload, "account": {"native_cash": "UNKNOWN"}})
    with pytest.raises(ValueError):
        HlStagegProjection.model_validate({**payload, "orders": [{**payload["orders"][0], "unexpected": 1}]})


def test_worker_projects_native_account_for_current_owned_tp_but_restart_stays_recovery_required(tmp_path, monkeypatch) -> None:
    import time
    import coinmaster.ops.hyperliquid_testnet_worker as worker_module

    path = tmp_path / "owned-tp-worker.sqlite"
    runtime = PaperRuntime(path, "hl-stageg-testnet", 120_000_000_000, require_native_cash=True)
    runtime.acquire()
    assert runtime.record_submission(
        client_order_id="tp-1", intent_id="intent-1", episode_id="episode-1",
        action="BTC_REDUCE", instrument_id="BTC-USD-PERP.HYPERLIQUID",
        quantity="0.10000", reduce_only=True,
    )
    runtime.acknowledge_submission("tp-1")
    positions = [{"instrument_id": "BTC-USD-PERP.HYPERLIQUID", "signed_quantity": "0.50000"}]
    orders = [{
        "client_order_id": "tp-1", "instrument_id": "BTC-USD-PERP.HYPERLIQUID",
        "reduce_only": True,
    }]
    assert runtime.snapshot(
        ts_ns=time.time_ns(), positions=positions, orders=orders,
        funding_event_ids=[], native_account_total="10000", strategy_restartable=True,
    )
    assert runtime.recovery_state() == "ACTIVE_OWNED_REDUCTIONS"

    money = {
        "native_cash": "10000", "native_free": "9900", "native_locked": "100",
        "realized_pnl_net_fees": "0", "fees": "0", "unrealized_pnl": "5",
        "equity": "10005", "mark_state": "CURRENT",
    }
    monkeypatch.setattr(worker_module, "native_money_projection", lambda cache, marks: money)

    def native_stub():
        return SimpleNamespace(
            _thread=None, _seed_verified=True,
            gate=SimpleNamespace(
                candidate_hash="candidate", strategy_code_hash="strategy",
                execution_policy_hash="policy", attachable=True,
                approval_state="SEALED_APPROVAL_MATCH", margin_policy_state="READY",
                execution_policy_state="READY", capital_state="ASSUMPTION",
                funding_state="UNPOSTED",
            ),
            node=SimpleNamespace(is_running=lambda: True, cache=object()),
            strategy=SimpleNamespace(_latest_marks={}),
            status=lambda: {
                "state": "PUBLIC_FEEDS_READY", "orders_enabled": True,
                "warmup": {"state": "READY", "rows": 1482}, "feeds": {}, "warnings": [],
            },
            sandbox_snapshot=lambda: (positions, orders),
            native_account_total=lambda: Decimal("10000"),
            strategy_restartable=lambda: True,
        )

    worker = HlStagegWorker.__new__(HlStagegWorker)
    worker.runtime, worker.reconciled = runtime, True
    worker.native = native_stub()
    worker.candidate = SimpleNamespace(sha256="candidate")
    worker.run_epoch, worker.starting_cash, worker.control_available = "same-process", Decimal("10000"), False
    projection = worker.projection()
    assert projection["account"] == money
    assert projection["positions"][0]["signed_quantity"] == "0.50000"
    assert projection["orders"][0]["reduce_only"] is True
    assert projection["recovery_required"] is False
    assert worker.status()["recovery_required"] is False

    runtime.close()
    restarted_runtime = PaperRuntime(path, "hl-stageg-testnet", 120_000_000_000, require_native_cash=True)
    restarted_runtime.acquire()
    assert restarted_runtime.recovery_state() == "MANAGE_ONLY_PENDING_INTENT"
    restarted = HlStagegWorker.__new__(HlStagegWorker)
    restarted.runtime, restarted.reconciled = restarted_runtime, False
    restarted.native = native_stub()
    restarted.candidate = SimpleNamespace(sha256="candidate")
    restarted.run_epoch, restarted.starting_cash, restarted.control_available = "new-process", None, False
    restarted_projection = restarted.projection()
    assert restarted_projection["account"] == {}
    assert restarted_projection["positions"][0]["signed_quantity"] == "0.50000"
    assert restarted_projection["recovery_required"] is True
    assert restarted.status()["recovery_required"] is True
    restarted_runtime.close()


def test_hl_worker_serves_bounded_projection_on_loopback_with_get_only(tmp_path, monkeypatch) -> None:
    import coinmaster.ops.hyperliquid_testnet_worker as worker_module
    journal = tmp_path / "worker.sqlite"; runtime = PaperRuntime(journal, "hl-stageg-testnet", 100)
    runtime.acquire(); runtime.snapshot(ts_ns=1, positions=[{"instrument_id": "BTC", "signed_quantity": "0.01"}], orders=[], funding_event_ids=[])
    runtime.record_native_event("sandbox-fill", "fill")
    worker = HlStagegWorker.__new__(HlStagegWorker)
    worker.runtime = runtime
    worker.run_epoch = "test-epoch"
    worker.starting_cash = Decimal("10000")
    worker.control_available = False
    worker.native = SimpleNamespace(_thread=None, gate=SimpleNamespace(
        candidate_hash="candidate", strategy_code_hash="strategy", execution_policy_hash="policy", attachable=True,
        approval_state="SEALED_APPROVAL_MATCH", margin_policy_state="READY", execution_policy_state="READY", capital_state="ASSUMPTION", funding_state="UNPOSTED",
    ), status=lambda: {
        "state": "PUBLIC_FEEDS_READY",
        "warmup": {"state": "READY", "rows": 1482}, "feeds": {}, "warnings": [],
    }, node=SimpleNamespace(is_running=lambda: False), strategy=None)
    projection = worker.projection()
    assert projection["instance_id"] == "hl-stageg-testnet" and projection["observed_at_ns"] > 0
    assert projection["reconciliation"] == "SANDBOX_LOCAL_PROCESS_RECONCILIATION_ONLY"
    worker.native.node = SimpleNamespace(is_running=lambda: True)
    worker.native.strategy = object()
    worker.native.strategy = SimpleNamespace(_latest_marks={})
    worker.native.node.cache = object()
    worker.native.sandbox_snapshot = lambda: ([{"instrument_id": "BTC", "signed_quantity": "0.01"}], [])
    worker.native.native_account_total = lambda: Decimal("10000")
    monkeypatch.setattr(worker_module, "native_money_projection", lambda cache, marks: {"native_cash": "10000", "native_free": "10000", "native_locked": "0", "realized_pnl_net_fees": "0", "fees": "0", "unrealized_pnl": "0", "equity": "10000", "mark_state": "CURRENT"})
    assert worker.projection()["account"]["equity"] == "10000"
    def missing_native_cash():
        raise ValueError("NATIVE_USDC_TOTAL_MISSING")
    worker.native.native_account_total = missing_native_cash
    monkeypatch.setattr(worker_module, "native_money_projection", lambda cache, marks: missing_native_cash())
    unavailable_account = worker.projection()
    assert unavailable_account["account"] == {}
    assert "NATIVE_SANDBOX_ACCOUNT_UNAVAILABLE" in unavailable_account["warnings"]
    assert json.loads(runtime.db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone()[0])["ts_ns"] == 1
    for index in range(105):
        runtime.record_native_event(f"fill-{index}", "fill")
    class ServerStub:
        def __init__(self, address, handler):
            self.server_address, self.handler = address, handler
    monkeypatch.setattr(worker_module, "ThreadingHTTPServer", ServerStub)
    server = create_status_server(worker, 18183)
    assert server.server_address == ("127.0.0.1", 18183)
    handler = server.handler.__new__(server.handler)
    handler.path = "/status"; handler.wfile = io.BytesIO(); observed = []
    handler.send_response = lambda code: observed.append(("status", code))
    handler.send_header = lambda key, value: observed.append((key, value))
    handler.end_headers = lambda: None
    handler.send_error = lambda code: observed.append(("error", code))
    handler.do_GET()
    payload = json.loads(handler.wfile.getvalue())
    assert payload["instance_id"] == "hl-stageg-testnet" and payload["positions"][0]["provenance"] == "SANDBOX"
    assert payload["event_cursor"] == 106 and len(payload["events"]) == 100
    assert payload["events"][0]["event_id"] == "fill-5"
    handler.do_POST()
    assert ("error", 405) in observed
    runtime.close()


def test_stageg_entry_control_is_durable_idempotent_and_conflict_safe(tmp_path) -> None:
    runtime = PaperRuntime(tmp_path / "worker.sqlite", "hl-stageg-testnet", 100)
    runtime.acquire()
    assert runtime.entry_control_state() == "RUNNING"
    assert runtime.entry_control_command("pause-new-entries", "a" * 16) == "ACCEPTED"
    assert runtime.entry_control_state() == "PAUSED"
    assert runtime.entry_control_command("pause-new-entries", "a" * 16) == "DUPLICATE"
    with pytest.raises(ValueError, match="IDEMPOTENCY_KEY_CONFLICT"):
        runtime.entry_control_command("resume-new-entries", "a" * 16)
    runtime.close()
    resumed = PaperRuntime(tmp_path / "worker.sqlite", "hl-stageg-testnet", 100)
    assert resumed.entry_control_state() == "PAUSED"
    assert resumed.entry_control_command("resume-new-entries", "b" * 16) == "ACCEPTED"
    assert resumed.health(1).paused_new_entries is False
    resumed.close()


def test_stageg_entry_control_relay_fails_closed_on_timeout(monkeypatch) -> None:
    import coinmaster.api.runtime_sidecar as sidecar
    monkeypatch.setattr(sidecar.urllib.request, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError()))
    with pytest.raises(HTTPException) as unavailable:
        HlStagegControlRelay("http://127.0.0.1:18183", "internal-test-token").command("pause-new-entries", "c" * 16)
    assert unavailable.value.status_code == 503


def test_deposit_protection_contract_uses_money_strings_and_strict_integer_percent() -> None:
    protection = HlStagegDepositProtection.model_validate({
        "state": "ARMED", "drawdown_limit_percent": 50, "currency": "USDC",
        "equity": "10000.00", "high_water_equity": "11000.00", "threshold_equity": "5500.00",
        "observed_at_ns": 123, "last_daily_close_utc": "2026-09-26T00:00:00Z", "trigger": None,
    })
    assert protection.equity == "10000.00" and protection.threshold_equity == "5500.00"
    for invalid in (0, 100, 50.5, True, "50"):
        with pytest.raises(ValueError):
            HlStagegProtectionCommandRequest(idempotency_key="test-key", drawdown_limit_percent=invalid)
    assert HlStagegProtectionCommandRequest(idempotency_key="test-key", drawdown_limit_percent=1).drawdown_limit_percent == 1
    assert HlStagegProtectionCommandRequest(idempotency_key="test-key", drawdown_limit_percent=99).drawdown_limit_percent == 99


def test_deposit_protection_relay_requires_worker_applied_readback_and_fails_closed_on_timeout(monkeypatch) -> None:
    import coinmaster.api.runtime_sidecar as sidecar
    body = {"idempotency_key": "dp-test", "drawdown_limit_percent": 40}
    import time
    worker_reply = {
        "instance_id": "hl-stageg-testnet", "command": "set-deposit-protection",
        "idempotency_key": "dp-test", "status": "APPLIED",
        "deposit_protection": {
            "state": "ARMED", "drawdown_limit_percent": 40, "currency": "USDC",
            "equity": "10000", "high_water_equity": "10000", "threshold_equity": "6000",
            "observed_at_ns": time.time_ns(), "last_daily_close_utc": None, "trigger": None,
        },
    }
    captured = {}
    def reply(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return io.BytesIO(json.dumps(worker_reply).encode())
    monkeypatch.setattr(sidecar.urllib.request, "urlopen", reply)
    result = HlStagegDepositProtectionRelay("http://127.0.0.1:18183", "worker-token").command("set-deposit-protection", body)
    assert result.status == "APPLIED" and result.deposit_protection.drawdown_limit_percent == 40
    request = captured["request"]
    assert request.get_header("X-coinmaster-instance") == "hl-stageg-testnet"
    assert request.get_header("Idempotency-key") == body["idempotency_key"]
    assert json.loads(request.data) == body and captured["timeout"] == 3

    stale_reply = {**worker_reply, "deposit_protection": {**worker_reply["deposit_protection"], "observed_at_ns": 1}}
    monkeypatch.setattr(sidecar.urllib.request, "urlopen", lambda *_args, **_kwargs: io.BytesIO(json.dumps(stale_reply).encode()))
    with pytest.raises(HTTPException) as stale:
        HlStagegDepositProtectionRelay("http://127.0.0.1:18183", "worker-token").command("set-deposit-protection", body)
    assert stale.value.status_code == 503

    monkeypatch.setattr(sidecar.urllib.request, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError()))
    with pytest.raises(HTTPException) as unavailable:
        HlStagegDepositProtectionRelay("http://127.0.0.1:18183", "worker-token").command("set-deposit-protection", body)
    assert unavailable.value.status_code == 503


def test_authenticated_api_set_and_reset_relay_round_trip_with_worker_status(tmp_path):
    import asyncio
    import threading
    import time
    from http.server import ThreadingHTTPServer

    class Worker:
        instance = SimpleNamespace(instance_id="hl-stageg-testnet")

        def __init__(self):
            self.body = _ready_hl_projection()
            self.body["positions"] = []
            self.body["orders"] = []
            self.body["entry_control"] = {"state": "PAUSED", "capability": "READY"}
            self.body["account"] = {"equity": "10000"}
            self.protection = {
                "state": "ARMED", "drawdown_limit_percent": 50, "currency": "USDC",
                "equity": "10000", "high_water_equity": "10000", "threshold_equity": "5000",
                "observed_at_ns": time.time_ns(), "last_daily_close_utc": None, "trigger": None,
            }

        def projection(self):
            self.body["observed_at_ns"] = time.time_ns()
            return {**self.body, "deposit_protection": dict(self.protection)}

        def deposit_control(self, command, key, *, drawdown_limit_percent=None, confirm=False):
            if not key or self.body["entry_control"]["state"] != "PAUSED" or self.body["positions"] or self.body["orders"]:
                raise ValueError("DEPOSIT_CONTROL_REQUIRES_PAUSED_CONFIRMED_FLAT")
            if command == "set-deposit-protection" and type(drawdown_limit_percent) is int and 1 <= drawdown_limit_percent <= 99:
                self.protection["drawdown_limit_percent"] = drawdown_limit_percent
                threshold = Decimal(self.protection["high_water_equity"]) * Decimal(100 - drawdown_limit_percent) / Decimal(100)
                self.protection["threshold_equity"] = str(threshold)
            elif command == "reset-deposit-protection" and confirm is True:
                self.protection["high_water_equity"] = self.protection["equity"]
                self.protection["state"] = "ARMED"
                self.protection["trigger"] = None
            else:
                raise ValueError("DEPOSIT_CONTROL_INVALID")
            self.protection["observed_at_ns"] = time.time_ns()
            return dict(self.protection)

    worker = Worker()
    server = create_status_server(worker, port=0, control_token="worker-secret")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        app = create_runtime_app(
            database=str(tmp_path / "paper.sqlite"), control_database=str(tmp_path / "control.sqlite"),
            token="operator-secret", hl_stageg_status_url=f"http://127.0.0.1:{server.server_address[1]}",
            hl_stageg_control_token="worker-secret",
        )

        async def call(method, path, body=None, *, authorized=True):
            headers = [(b"host", b"localhost"), (b"content-type", b"application/json")]
            if authorized:
                headers.append((b"authorization", b"Bearer operator-secret"))
            scope = {
                "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                "scheme": "http", "method": method, "path": path, "raw_path": path.encode(),
                "query_string": b"", "headers": headers, "server": ("localhost", 80),
                "client": ("127.0.0.1", 4321), "root_path": "",
            }
            payload = json.dumps(body).encode() if body is not None else b""
            messages = []
            received = False
            async def receive():
                nonlocal received
                if not received:
                    received = True
                    return {"type": "http.request", "body": payload, "more_body": False}
                return {"type": "http.disconnect"}
            async def send(message):
                messages.append(message)
            await app(scope, receive, send)
            start = next(item for item in messages if item["type"] == "http.response.start")
            response_body = b"".join(item.get("body", b"") for item in messages if item["type"] == "http.response.body")
            return start["status"], json.loads(response_body)

        set_key = "set-" + "a" * 32
        path = "/api/v1/instances/hl-stageg-testnet/controls/set-deposit-protection"
        assert asyncio.run(call("POST", path, {"idempotency_key": set_key, "drawdown_limit_percent": 40}, authorized=False))[0] == 401
        status, applied = asyncio.run(call("POST", path, {"idempotency_key": set_key, "drawdown_limit_percent": 40}))
        assert status == 200 and applied["status"] == "APPLIED"
        assert applied["deposit_protection"]["drawdown_limit_percent"] == 40
        status, projection = asyncio.run(call("GET", "/api/v1/instances/hl-stageg-testnet"))
        assert status == 200 and projection["deposit_protection"]["threshold_equity"] == "6000"

        reset_key = "reset-" + "b" * 32
        status, reset = asyncio.run(call(
            "POST", "/api/v1/instances/hl-stageg-testnet/controls/reset-deposit-protection",
            {"idempotency_key": reset_key, "confirm": True},
        ))
        assert status == 200 and reset["status"] == "APPLIED"
        assert reset["deposit_protection"]["high_water_equity"] == reset["deposit_protection"]["equity"]
        assert worker.body["entry_control"]["state"] == "PAUSED"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
