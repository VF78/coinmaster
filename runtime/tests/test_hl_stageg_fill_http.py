"""Worker-owned, read-only native fill history over its existing loopback server."""
import json
import threading
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from coinmaster.ops.hyperliquid_testnet_worker import create_status_server
from coinmaster.ops.paper import PaperRuntime


@pytest.fixture
def fill_server(tmp_path):
    runtime = PaperRuntime(tmp_path / "fills.sqlite", "hl-stageg-testnet", 10**20)
    worker = SimpleNamespace(
        runtime=runtime, instance=SimpleNamespace(instance_id="hl-stageg-testnet"),
        run_epoch="epoch-1", projection=lambda: {"status": "READY"},
    )
    server = create_status_server(worker, port=0, control_token="worker-secret")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield runtime, f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        runtime.close()


def fetch(base, path, *, token="worker-secret", instance="hl-stageg-testnet"):
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if instance is not None:
        headers["X-Coinmaster-Instance"] = instance
    request = Request(base + path, headers=headers)
    try:
        with urlopen(request, timeout=2) as response:
            return response.status, json.load(response), response.headers
    except HTTPError as error:
        return error.code, None, error.headers


def fill(trade_id, *, unknown=False):
    return dict(
        trade_id=trade_id, native_event_id=None if unknown else f"event-{trade_id}",
        client_order_id=None, venue_order_id=None, instrument_id="BTC-USD-PERP.HYPERLIQUID",
        order_side=None if unknown else "BUY", quantity="0.01", price="60000",
        commission_amount=None if unknown else "0.2", commission_currency=None if unknown else "USDC",
        liquidity_side=None if unknown else "TAKER", ts_event_ns=None if unknown else 100,
        ts_init_ns=None if unknown else 101,
    )


def test_fill_http_auth_bounds_and_status_remains_available(fill_server):
    runtime, base = fill_server
    assert fetch(base, "/status", token=None, instance=None)[0] == 200
    assert fetch(base, "/fills", token=None)[0] == 401
    assert fetch(base, "/fills", token="wrong")[0] == 401
    assert fetch(base, "/fills", instance="wrong")[0] == 403
    for query in ("cursor=-1", "cursor=abc", "cursor=9223372036854775808", "limit=0", "limit=101", "limit=1&limit=2", "unexpected=1"):
        assert fetch(base, f"/fills?{query}")[0] == 422
    before = runtime.native_revision()
    code, payload, headers = fetch(base, "/fills")
    assert code == 200 and headers["Cache-Control"] == "no-store"
    assert payload["fills"] == [] and payload["next_cursor"] == 0
    assert payload["detail_store_available"] is True
    assert runtime.native_revision() == before


def test_fill_http_pages_nullable_facts_and_counts_id_only_events(fill_server):
    runtime, base = fill_server
    assert runtime.record_native_event("old-id-only", "fill")
    assert runtime.record_native_fill(**fill("trade-1"))
    assert runtime.record_native_fill(**fill("trade-2", unknown=True))
    before = runtime.native_revision()
    code, first, _ = fetch(base, "/fills?cursor=0&limit=1")
    assert code == 200
    assert first["version"] == "hl-stageg-native-fills-v1"
    assert first["instance_id"] == "hl-stageg-testnet" and first["run_epoch"] == "epoch-1"
    assert first["detail_store_available"] is True and first["historical_id_only_count"] == 1
    assert len(first["fills"]) == 1 and first["fills"][0]["trade_id"] == "trade-1"
    cursor = first["next_cursor"]
    code, second, _ = fetch(base, f"/fills?cursor={cursor}&limit=1")
    assert code == 200 and second["fills"][0]["trade_id"] == "trade-2"
    assert second["fills"][0]["commission_amount"] is None
    assert second["fills"][0]["liquidity_side"] is None
    assert second["fills"][0]["ts_event_ns"] is None
    assert second["fills"][0]["episode_id"] is None
    code, empty, _ = fetch(base, f"/fills?cursor={second['next_cursor']}&limit=1")
    assert code == 200 and empty["fills"] == [] and empty["next_cursor"] == second["next_cursor"]
    assert runtime.native_revision() == before


def test_fill_http_old_schema_reports_id_only_count_without_fabrication(fill_server):
    runtime, base = fill_server
    assert runtime.record_native_event("old-id-only", "fill")
    runtime.db.execute("DROP TABLE paper_native_fill_details")
    runtime.db.commit()
    before = runtime.native_revision()
    code, payload, _ = fetch(base, "/fills?cursor=0&limit=5")
    assert code == 200
    assert payload["detail_store_available"] is False
    assert payload["historical_id_only_count"] == 1
    assert payload["fills"] == [] and payload["next_cursor"] == 0
    assert runtime.native_revision() == before
