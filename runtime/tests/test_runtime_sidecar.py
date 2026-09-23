from decimal import Decimal

import io
import json
import pytest
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError
from fastapi import HTTPException

from coinmaster.api.runtime_sidecar import HlStagegProjection, HlStagegProjectionReader, HlStagegStrategyReader, RuntimeReader, create_runtime_app, hl_stageg_controls
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
    # The SPA fallback is registered after the authenticated API routes and
    # resolves the built root rather than a file supplied by the request.
    spa = next(route for route in app.routes if getattr(route, "path", "") == "/{path:path}")
    response = spa.endpoint("")
    assert response.path == dist / "index.html"


def test_hl_stageg_controls_are_authenticated_instance_bound_and_fail_closed(tmp_path) -> None:
    app = create_runtime_app(database=str(tmp_path / "missing.sqlite"), control_database=str(tmp_path / "control.sqlite"), token="operator", worker_url="http://127.0.0.1:9", hl_stageg_status_url="http://127.0.0.1:9")
    path = "/api/v1/instances/hl-stageg-testnet/controls"
    route = next(item for item in app.routes if getattr(item, "path", "") == path)
    auth = next(dependency.call for dependency in route.dependant.dependencies if dependency.call.__name__ == "auth")
    with pytest.raises(HTTPException) as denied:
        auth(None)
    assert denied.value.status_code == 401
    auth("Bearer operator")
    body = route.endpoint().model_dump()
    assert body["instance_id"] == "hl-stageg-testnet" and body["mode"] == "sandbox"
    assert body["projection_state"] == "UNAVAILABLE"
    assert all(body[action]["enabled"] is False for action in ("pause", "resume", "flatten", "promotion"))
    assert body["pause"]["blocker"] == "NATIVE_PROJECTION_UNAVAILABLE"
    assert body["flatten"]["requires_confirmation"] is True
    assert app.openapi()["paths"][path].keys() == {"get"}
    assert not any(getattr(route, "path", "").startswith("/api/v1/instances/hl-stageg-testnet/") and "POST" in getattr(route, "methods", set()) for route in app.routes)

    ready = hl_stageg_controls(HlStagegProjection.model_validate(_ready_hl_projection()))
    assert ready.pause.blocker == "NO_INSTANCE_BOUND_NATIVE_PAUSE_COMMAND"
    assert ready.resume.blocker == "NO_INSTANCE_BOUND_NATIVE_RESUME_COMMAND"
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
        "process_state": "PUBLIC_FEEDS_READY", "reconciliation": "SANDBOX_LOCAL_PROCESS_RECONCILIATION_ONLY",
        "hashes": {"candidate_sha256": "candidate", "strategy_sha256": "strategy", "execution_policy_sha256": "policy"},
        "warmup": {"state": "READY", "rows": 1482}, "gates": {"attachable": True}, "account": {},
        "funding_state": "OBSERVED_MODELLED_UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT",
        "feeds": {"BTC-USD-PERP.HYPERLIQUID": {"state": "READY", "mark": "100"}},
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
    assert body.positions[0].provenance == "SANDBOX"
    assert body.account.equity == "UNKNOWN"

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
    assert dead.account.native_cash == "UNKNOWN"
    assert dead.funding_state == "UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT"


def test_hl_worker_serves_bounded_projection_on_loopback_with_get_only(tmp_path, monkeypatch) -> None:
    import coinmaster.ops.hyperliquid_testnet_worker as worker_module
    journal = tmp_path / "worker.sqlite"; runtime = PaperRuntime(journal, "hl-stageg-testnet", 100)
    runtime.acquire(); runtime.snapshot(ts_ns=1, positions=[{"instrument_id": "BTC", "signed_quantity": "0.01"}], orders=[], funding_event_ids=[])
    runtime.record_native_event("sandbox-fill", "fill")
    worker = HlStagegWorker.__new__(HlStagegWorker)
    worker.runtime = runtime
    worker.native = SimpleNamespace(gate=SimpleNamespace(
        candidate_hash="candidate", strategy_code_hash="strategy", execution_policy_hash="policy", attachable=True,
        approval_state="SEALED_APPROVAL_MATCH", margin_policy_state="READY", execution_policy_state="READY", capital_state="ASSUMPTION", funding_state="UNPOSTED",
    ), status=lambda: {
        "state": "PUBLIC_FEEDS_READY", "reconciliation": "SANDBOX_LOCAL_PROCESS_RECONCILIATION_ONLY",
        "warmup": {"state": "READY", "rows": 1482}, "feeds": {}, "warnings": [],
    }, node=SimpleNamespace(is_running=lambda: False), strategy=None)
    projection = worker.projection()
    assert projection["instance_id"] == "hl-stageg-testnet" and projection["observed_at_ns"] > 0
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
