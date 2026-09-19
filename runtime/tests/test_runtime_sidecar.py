from decimal import Decimal

from coinmaster.api.runtime_sidecar import RuntimeReader, create_runtime_app
from coinmaster.ops.paper import PaperRuntime


def test_runtime_sidecar_reader_has_decimals_cursor_and_unknowns_when_worker_disconnected(tmp_path) -> None:
    database = tmp_path / "paper.sqlite"; runtime = PaperRuntime(database, "paper", 100)
    runtime.acquire(); runtime.snapshot(ts_ns=1, positions=[], orders=[], funding_event_ids=[])
    runtime.record_modelled_funding(event_id="bybit:BTC:2", instrument_id="BTC", settlement_ns=2, rate=Decimal("0.01"), mark=Decimal("100"), signed_quantity=Decimal("1"))
    runtime.record_native_event("fill-1", "fill"); runtime.close()
    reader = RuntimeReader(str(database), "http://127.0.0.1:9")
    body = reader.runtime()
    assert body.version == "runtime-v1" and body.balances.active_usdt == "UNKNOWN"
    assert body.balances.modelled_funding_cash == "-1.00"
    assert body.funding[0].state == "MODELLED_LEDGER_UNPOSTED"
    events = reader.events(0)
    assert events.events[0].cursor > 0


def test_runtime_sidecar_exposes_strict_schemas_and_spa_without_shadowing_api(tmp_path, monkeypatch) -> None:
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<main>paper runtime</main>")
    (dist / "assets" / "app.js").write_text("export {}")
    monkeypatch.setenv("COINMASTER_RUNTIME_DIST", str(dist))
    app = create_runtime_app(database=str(tmp_path / "missing.sqlite"), token="operator", worker_url="http://127.0.0.1:9", worker_token="relay")
    spec = app.openapi()
    schemas = spec["components"]["schemas"]
    for name in ("RuntimeState", "RuntimeBalances", "RuntimeStrategy", "RuntimeFeed", "RuntimeEvent", "RuntimeFunding", "RuntimeEventsResponse", "RuntimeCommandResponse"):
        assert schemas[name]["additionalProperties"] is False
    assert schemas["RuntimeBalances"]["properties"]["active_usdt"]["type"] == "string"
    paths = [getattr(route, "path", "") for route in app.routes]
    assert "/api/v1/runtime" in paths and "/{path:path}" in paths
    # The SPA fallback is registered after the authenticated API routes and
    # resolves the built root rather than a file supplied by the request.
    spa = next(route for route in app.routes if getattr(route, "path", "") == "/{path:path}")
    response = spa.endpoint("")
    assert response.path == dist / "index.html"
