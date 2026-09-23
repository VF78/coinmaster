from decimal import Decimal

import json
from types import SimpleNamespace

from coinmaster.api.runtime_sidecar import HlStagegProjectionReader, RuntimeReader, create_runtime_app
from coinmaster.ops.hyperliquid_testnet_worker import TestnetWorker as HlStagegWorker
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
    for name in ("RuntimeState", "RuntimeBalances", "RuntimeStrategy", "RuntimeFeed", "RuntimeEvent", "RuntimeFunding", "RuntimeEventsResponse", "RuntimeCommandResponse", "HlStagegProjection", "HlStagegHashes"):
        assert schemas[name]["additionalProperties"] is False
    assert schemas["RuntimeBalances"]["properties"]["active_usdt"]["type"] == "string"
    for path in ("/api/v1/configurations/default", "/api/v1/configurations", "/api/v1/preflight", "/api/v1/runs", "/api/v1/research/catalog", "/api/v1/runtime", "/api/v1/runtime/commands/{command}", "/api/v1/instances/hl-stageg-testnet"):
        assert path in spec["paths"]
    assert "ResearchCatalogEntry" in schemas and "StrategyConfig" in schemas
    paths = [getattr(route, "path", "") for route in app.routes]
    assert "/api/v1/openapi.json" in paths and "/api/v1/runtime" in paths and "/{path:path}" in paths
    # The SPA fallback is registered after the authenticated API routes and
    # resolves the built root rather than a file supplied by the request.
    spa = next(route for route in app.routes if getattr(route, "path", "") == "/{path:path}")
    response = spa.endpoint("")
    assert response.path == dist / "index.html"


def test_hl_stageg_projection_is_separate_from_paper_and_preserves_unknown_unposted(tmp_path) -> None:
    projection_path = tmp_path / "hl-stageg-projection.json"
    missing = HlStagegProjectionReader(str(projection_path)).runtime()
    assert missing.projection_state == "UNAVAILABLE"
    assert missing.account.native_cash == "UNKNOWN"
    assert missing.funding_state == "UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT"

    projection_path.write_text(json.dumps({
        "version": "hl-stageg-projection-v1", "instance_id": "hl-stageg-testnet", "projection_state": "READY",
        "observed_at_ns": 7, "mode": "sandbox", "environment": "mainnet-public", "live_order_capability": False,
        "process_state": "PUBLIC_FEEDS_READY", "reconciliation": "SANDBOX_LOCAL_PROCESS_RECONCILIATION_ONLY",
        "hashes": {"candidate_sha256": "candidate", "strategy_sha256": "strategy", "execution_policy_sha256": "policy"},
        "warmup": {"state": "READY", "rows": 1482}, "gates": {"attachable": True}, "account": {},
        "funding_state": "OBSERVED_MODELLED_UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT",
        "feeds": {"BTC-USD-PERP.HYPERLIQUID": {"state": "READY", "mark": "100"}},
        "positions": [{"instrument_id": "BTC-USD-PERP.HYPERLIQUID", "signed_quantity": "0.01", "provenance": "SANDBOX"}],
        "orders": [], "events": [{"cursor": 3, "event_id": "sandbox-fill", "kind": "fill", "provenance": "SANDBOX"}], "event_cursor": 3,
        "provenance": "SANDBOX_LOCAL_READ_ONLY_WORKER_PROJECTION", "warnings": [],
    }))
    body = HlStagegProjectionReader(str(projection_path)).runtime()
    assert body.projection_state == "READY"
    assert body.positions[0].provenance == "SANDBOX"
    assert body.account.equity == "UNKNOWN"

    # A paper-shaped or live-capable file is rejected instead of being mapped
    # into this instance's response.
    projection_path.write_text('{"mode":"paper","live_order_capability":true}')
    rejected = HlStagegProjectionReader(str(projection_path)).runtime()
    assert rejected.projection_state == "INVALID"


def test_hl_worker_publishes_bounded_sandbox_projection_without_journal_path(tmp_path) -> None:
    journal = tmp_path / "worker.sqlite"; runtime = PaperRuntime(journal, "hl-stageg-testnet", 100)
    runtime.acquire(); runtime.snapshot(ts_ns=1, positions=[{"instrument_id": "BTC", "signed_quantity": "0.01"}], orders=[], funding_event_ids=[])
    runtime.record_native_event("sandbox-fill", "fill")
    worker = HlStagegWorker.__new__(HlStagegWorker)
    worker.projection_path = tmp_path / "handoff" / "status.json"
    worker.runtime = runtime
    worker.native = SimpleNamespace(gate=SimpleNamespace(
        candidate_hash="candidate", strategy_code_hash="strategy", execution_policy_hash="policy", attachable=True,
        approval_state="SEALED_APPROVAL_MATCH", margin_policy_state="READY", execution_policy_state="READY", capital_state="ASSUMPTION", funding_state="UNPOSTED",
    ))
    worker._publish_projection({
        "state": "PUBLIC_FEEDS_READY", "reconciliation": "SANDBOX_LOCAL_PROCESS_RECONCILIATION_ONLY",
        "warmup": {"state": "READY", "rows": 1482}, "feeds": {}, "warnings": [],
    })
    raw = worker.projection_path.read_text()
    body = HlStagegProjectionReader(str(worker.projection_path)).runtime()
    assert body.projection_state == "READY" and body.positions[0].provenance == "SANDBOX"
    assert str(journal) not in raw and "paper_snapshot" not in raw
    runtime.close()
