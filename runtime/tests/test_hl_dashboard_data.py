"""Read-only Hyperliquid Dashboard data never manufactures candles or equity history."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from decimal import Decimal
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import pytest

import coinmaster.api.runtime_sidecar as sidecar
import coinmaster.ops.hyperliquid_testnet_worker as worker_module
from coinmaster.api.hl_public_candles import public_candles
from coinmaster.api.runtime_sidecar import create_runtime_app
from coinmaster.ops.hyperliquid_testnet_worker import TestnetWorker as StageGWorker, create_status_server
from coinmaster.ops.paper import PaperRuntime


DAY = 86_400_000_000_000
MINUTE_MS = 60_000


def _candle(opened: int, *, coin: str = "BTC", interval: str = "1m") -> dict:
    return {
        "t": opened, "T": opened + MINUTE_MS - 1, "s": coin, "i": interval,
        "o": "60000", "h": "60002", "l": "59999", "c": "60001",
        "v": "1.25", "n": 4,
    }


def test_official_public_candles_are_bounded_ordered_and_fresh() -> None:
    now_ms = 1000 * MINUTE_MS + 7
    seen = []
    rows = [_candle(998 * MINUTE_MS), _candle(999 * MINUTE_MS)]
    result = public_candles(
        "BTC", "1m", 2, now_ms=now_ms,
        post=lambda body: seen.append(body) or rows,
    )
    assert seen == [{"type": "candleSnapshot", "req": {
        "coin": "BTC", "interval": "1m", "startTime": 998 * MINUTE_MS,
        "endTime": 1000 * MINUTE_MS - 1,
    }}]
    assert result["state"] == "READY" and result["execution_evidence"] is False
    assert result["source"] == "OFFICIAL_INFO_CANDLE_SNAPSHOT"
    assert [row["open_time_ms"] for row in result["candles"]] == [998 * MINUTE_MS, 999 * MINUTE_MS]
    for bad in (
        list(reversed(rows)),
        [{**rows[-1], "s": "SOL"}],
        [{**rows[-1], "i": "5m"}],
        [{**rows[-1], "T": rows[-1]["T"] + 1}],
        [{**rows[-1], "h": "59998"}],
        [{**rows[-1], "c": "NaN"}],
        rows + [rows[-1]],
    ):
        assert public_candles("BTC", "1m", 2, now_ms=now_ms, post=lambda _body, bad=bad: bad)["state"] == "INVALID"
    assert public_candles("BTC", "1m", 5, now_ms=now_ms, post=lambda _body: [_candle(995 * MINUTE_MS)])["state"] == "STALE"
    assert public_candles("BTC", "1m", 2, now_ms=now_ms, post=lambda _body: [])["state"] == "UNAVAILABLE"
    def unavailable(_body):
        raise OSError("public Info offline")
    assert public_candles("BTC", "1m", 2, now_ms=now_ms, post=unavailable)["state"] == "UNAVAILABLE"
    for coin, interval, limit in (("ETH", "1m", 2), ("BTC", "1s", 2), ("BTC", "1m", 501), ("BTC", "1m", True)):
        with pytest.raises(ValueError):
            public_candles(coin, interval, limit, now_ms=now_ms, post=lambda _body: rows)


def test_native_equity_sqlite_is_sparse_durable_epoch_bound_and_honest(tmp_path) -> None:
    path = tmp_path / "native-equity.sqlite"
    runtime = PaperRuntime(path, "hl-stageg-testnet", 10**20)
    runtime.acquire()
    now_ns = 100 * DAY
    try:
        assert runtime.record_native_equity_observation(
            run_epoch="epoch-a", observed_at_ns=now_ns - 30 * DAY, equity_usdc="10000",
        )
        assert runtime.record_native_equity_observation(
            run_epoch="epoch-a", observed_at_ns=now_ns - 7 * DAY, equity_usdc="10100",
        )
        assert runtime.record_native_equity_observation(
            run_epoch="epoch-a", observed_at_ns=now_ns - DAY, equity_usdc="10200",
        )
        assert runtime.record_native_equity_observation(
            run_epoch="epoch-a", observed_at_ns=now_ns, equity_usdc="10300",
        )
        assert not runtime.record_native_equity_observation(
            run_epoch="epoch-a", observed_at_ns=now_ns + 1, equity_usdc="999999",
        )
        current = runtime.native_equity_changes(run_epoch="epoch-a", now_ns=now_ns)
        assert current["state"] == "READY" and current["equity_usdc"] == "10300"
        assert current["windows"]["24h"]["change_usdc"] == "100"
        assert current["windows"]["7d"]["change_usdc"] == "200"
        assert current["windows"]["30d"]["change_usdc"] == "300"
        assert current["windows"]["30d"]["change_percent"] == "3.00"
        assert runtime.native_equity_changes(run_epoch="epoch-b", now_ns=now_ns)["windows"]["24h"]["state"] == "UNAVAILABLE"
        stale = runtime.native_equity_changes(run_epoch="epoch-a", now_ns=now_ns + 601_000_000_000)
        assert stale["state"] == "STALE"
        assert all(item["change_usdc"] is None for item in stale["windows"].values())
    finally:
        runtime.close()
    reopened = PaperRuntime(path, "hl-stageg-testnet", 10**20)
    reopened.acquire()
    try:
        assert reopened.native_equity_changes(run_epoch="epoch-a", now_ns=now_ns)["windows"]["30d"]["state"] == "AVAILABLE"
        assert reopened.native_equity_changes(run_epoch="epoch-b", now_ns=now_ns)["state"] == "UNAVAILABLE"
        assert reopened.record_native_equity_observation(
            run_epoch="epoch-b", observed_at_ns=now_ns + 1, equity_usdc="10400",
        )
        new_epoch = reopened.native_equity_changes(run_epoch="epoch-b", now_ns=now_ns + 1)
        assert new_epoch["state"] == "READY"
        assert all(item["state"] == "UNAVAILABLE" for item in new_epoch["windows"].values())
    finally:
        reopened.close()


def test_worker_heartbeat_samples_only_current_owned_native_equity(monkeypatch, tmp_path) -> None:
    runtime = PaperRuntime(tmp_path / "heartbeat.sqlite", "hl-stageg-testnet", 10**20)
    runtime.acquire()
    worker = StageGWorker.__new__(StageGWorker)
    worker.runtime = runtime
    worker.run_epoch = "heartbeat-epoch"
    worker.starting_cash = Decimal("10000")
    worker.candidate = SimpleNamespace(sha256="candidate")
    worker.native = SimpleNamespace(
        node=SimpleNamespace(cache=object()), strategy=SimpleNamespace(_latest_marks={}),
        _thread=SimpleNamespace(is_alive=lambda: True),
        status=lambda: {"state": "PUBLIC_FEEDS_READY", "orders_enabled": True},
    )
    worker.poll = lambda: None
    worker._current_process_owns_sandbox = lambda _state: True
    money = {"mark_state": "CURRENT", "equity": "10000"}
    monkeypatch.setattr(worker_module, "native_money_projection", lambda _cache, _marks: money)
    try:
        worker.status()
        worker.status()
        assert runtime.db.execute("SELECT COUNT(*) FROM paper_native_equity_observations").fetchone()[0] == 1
        money["mark_state"] = "STALE_OR_MISSING"
        money["equity"] = None
        worker.status()
        worker.native.status = lambda: {"state": "DATA_STALE/PAUSED", "orders_enabled": False}
        money.update(mark_state="CURRENT", equity="9900")
        worker.status()
        assert runtime.db.execute("SELECT COUNT(*) FROM paper_native_equity_observations").fetchone()[0] == 1
    finally:
        runtime.close()


async def _api_get(app, url: str, *, authorized: bool = True):
    target = urlsplit(url)
    headers = [(b"host", b"localhost")]
    if authorized:
        headers.append((b"authorization", b"Bearer operator-secret"))
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "scheme": "http", "method": "GET", "path": target.path, "raw_path": target.path.encode(),
        "query_string": target.query.encode(), "headers": headers, "server": ("localhost", 80),
        "client": ("127.0.0.1", 4321), "root_path": "",
    }
    messages = []
    received = False
    async def receive():
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}
    async def send(message):
        messages.append(message)
    await app(scope, receive, send)
    start = next(item for item in messages if item["type"] == "http.response.start")
    payload = b"".join(item.get("body", b"") for item in messages if item["type"] == "http.response.body")
    return start["status"], json.loads(payload)


def test_authenticated_sidecar_relays_real_worker_equity_and_public_candles(monkeypatch, tmp_path) -> None:
    runtime = PaperRuntime(tmp_path / "worker.sqlite", "hl-stageg-testnet", 10**20)
    runtime.acquire()
    now_ns = time.time_ns()
    runtime.record_native_equity_observation(
        run_epoch="current-epoch", observed_at_ns=now_ns, equity_usdc="10000",
    )
    worker = SimpleNamespace(
        runtime=runtime, instance=SimpleNamespace(instance_id="hl-stageg-testnet"),
        run_epoch="current-epoch", projection=lambda: {"status": "READY"},
    )
    server = create_status_server(worker, port=0, control_token="worker-secret")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        app = create_runtime_app(
            database=str(tmp_path / "missing.sqlite"), control_database=str(tmp_path / "control.sqlite"),
            token="operator-secret", hl_stageg_status_url=base, hl_stageg_control_token="worker-secret",
            session_database=str(tmp_path / "auth.sqlite"),
        )
        route = "/api/v1/instances/hl-stageg-testnet/equity-changes"
        assert asyncio.run(_api_get(app, route, authorized=False))[0] == 401
        status, equity = asyncio.run(_api_get(app, route))
        assert status == 200 and equity["state"] == "READY" and equity["run_epoch"] == "current-epoch"
        assert equity["equity_usdc"] == "10000"
        assert all(item["state"] == "UNAVAILABLE" for item in equity["windows"].values())
        assert urlopen(Request(base + "/equity-changes"), timeout=2).status == 401
    except HTTPError as error:
        assert error.code == 401
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        runtime.close()

    now_ms = 1000 * MINUTE_MS + 7
    # The test supplies exact public Info rows; no network or Bybit fallback.
    monkeypatch.setattr(sidecar.PublicCandleBudget, "request", lambda _self, coin, interval, limit: public_candles(
        coin, interval, limit, now_ms=now_ms,
        post=lambda _body: [_candle(999 * MINUTE_MS)],
    ))
    app = create_runtime_app(
        database=str(tmp_path / "missing.sqlite"), control_database=str(tmp_path / "control.sqlite"),
        token="operator-secret", session_database=str(tmp_path / "auth.sqlite"),
    )
    route = "/api/v1/markets/hyperliquid/candles?coin=BTC&interval=1m&limit=2"
    assert asyncio.run(_api_get(app, route, authorized=False))[0] == 401
    status, candles = asyncio.run(_api_get(app, route))
    assert status == 200 and candles["state"] == "READY"
    assert candles["source"] == "OFFICIAL_INFO_CANDLE_SNAPSHOT" and len(candles["candles"]) == 1
    assert asyncio.run(_api_get(app, "/api/v1/markets/hyperliquid/candles?coin=ETH&interval=1m"))[0] == 422
