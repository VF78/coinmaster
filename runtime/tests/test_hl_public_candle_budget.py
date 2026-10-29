"""Pure fake-HTTP/clock tests of the shared public candle IP-budget slice."""
import json
import multiprocessing
from pathlib import Path

from coinmaster.api.hl_public_candle_budget import PublicCandleBudget, CAPACITY, WINDOW_NS, candle_weight


class Clock:
    def __init__(self): self.now = 1_000_000_000
    def __call__(self): return self.now
    def advance(self, seconds): self.now += int(seconds * 1_000_000_000)


def rows(body, count=None):
    request = body["req"]
    duration = {"1m": 60000, "5m": 300000, "15m": 900000, "1h": 3600000, "4h": 14400000, "1d": 86400000}[request["interval"]]
    maximum = (request["endTime"] - request["startTime"]) // duration + 1
    return [{"t": request["startTime"] + index * duration,
             "T": request["startTime"] + (index + 1) * duration - 1,
             "s": request["coin"], "i": request["interval"], "o": "10", "h": "12", "l": "9", "c": "11", "v": "1", "n": 1}
            for index in range(maximum if count is None else count)]


def make(tmp_path, clock, post):
    return PublicCandleBudget(tmp_path, clock=clock, wall_clock=lambda: 2_000_000_000_001, post=post)


def warm(guard, clock):
    assert guard.request("BTC", "1m", 500)["reason"] == "PUBLIC_CANDLE_BUDGET_EXHAUSTED"
    clock.advance(60)


def charges(guard):
    return json.loads(guard.path.read_text())["charges"]


def test_initial_hold_raw_window_reservation_refund_cache_and_restart(tmp_path):
    clock = Clock(); calls = []
    def post(body):
        calls.append(body)
        assert sum(item["weight"] for item in charges(guard)) == 29
        assert (body["req"]["endTime"] - body["req"]["startTime"]) // 60000 + 1 == 500
        return rows(body, 61)
    guard = make(tmp_path, clock, post); warm(guard, clock)
    result = guard.request("BTC", "1m", 500)
    assert result["quote_currency"] == "USDC" and len(result["candles"]) == 61
    assert sum(item["weight"] for item in charges(guard)) == candle_weight(61) == 22
    restarted = make(tmp_path, clock, lambda _body: (_ for _ in ()).throw(AssertionError("cache made HTTP")))
    assert restarted.request("BTC", "1m", 500) == result
    assert len(calls) == 1


def test_capacity_persists_across_instances_and_rolling_window(tmp_path):
    clock = Clock(); calls = []
    def post(body): calls.append(body); return rows(body)
    guard = make(tmp_path, clock, post); warm(guard, clock)
    for limit in range(495, 500):
        assert make(tmp_path, clock, post).request("BTC", "1m", limit)["state"] == "READY"
    assert len(calls) == 5 and sum(item["weight"] for item in charges(guard)) == 145
    assert make(tmp_path, clock, post).request("SOL", "1m", 500)["reason"] == "PUBLIC_CANDLE_BUDGET_EXHAUSTED"
    clock.advance(60)
    assert guard.request("SOL", "1m", 500)["state"] == "READY"
    assert len(calls) == 6


def test_cache_ttl_stale_fallback_and_coalescing_without_network_lock(tmp_path):
    clock = Clock(); calls = []; guard = None
    second = make(tmp_path, clock, lambda _body: (_ for _ in ()).throw(AssertionError("duplicate HTTP")))
    def post(body):
        calls.append(body)
        assert second.request("BTC", "1m", 500)["reason"] == "PUBLIC_CANDLES_REQUEST_IN_FLIGHT"
        # A different process/instance can take the file lock while HTTP is active.
        with second._locked(): pass
        return rows(body)
    guard = make(tmp_path, clock, post); warm(guard, clock)
    assert guard.request("BTC", "1m", 500)["state"] == "READY"
    assert second.request("BTC", "1m", 500)["state"] == "READY"
    clock.advance(6)
    # Fill remaining budget with unique keys, leaving no room for a refresh.
    for limit in range(495, 499):
        make(tmp_path, clock, rows).request("SOL", "1m", limit)
    stale = guard.request("BTC", "1m", 500)
    assert stale["state"] == "STALE" and stale["reason"] == "PUBLIC_CANDLE_BUDGET_EXHAUSTED"
    assert len(calls) == 1 and len(stale["candles"]) == 500


def test_malformed_and_exception_keep_full_reservation(tmp_path):
    clock = Clock()
    guard = make(tmp_path, clock, lambda body: [{**rows(body, 1)[0], "c": "NaN"}]); warm(guard, clock)
    assert guard.request("BTC", "1m", 500)["state"] == "INVALID"
    def failed(_body): raise OSError("fake offline")
    assert make(tmp_path, clock, failed).request("SOL", "1m", 500)["state"] == "UNAVAILABLE"
    assert sum(item["weight"] for item in charges(guard)) == 58


def test_failure_corruption_backwards_clock_or_busy_lock_never_posts(tmp_path):
    clock = Clock()
    def forbidden(_body): raise AssertionError("unexpected HTTP")
    guard = make(tmp_path, clock, forbidden); warm(guard, clock)
    with guard._locked():
        assert guard.request("BTC", "1m", 500)["reason"] == "PUBLIC_CANDLE_BUDGET_UNAVAILABLE"
    guard.path.write_text("{corrupt")
    assert guard.request("BTC", "1m", 500)["reason"] == "PUBLIC_CANDLE_BUDGET_UNAVAILABLE"
    guard.path.unlink()
    guard.request("BTC", "1m", 500)  # Missing state restarts the conservative hold.
    clock.advance(-1)
    assert guard.request("BTC", "1m", 500)["reason"] == "PUBLIC_CANDLE_BUDGET_UNAVAILABLE"
    assert make(tmp_path / "missing-parent", clock, forbidden).request("BTC", "1m", 1)["reason"] == "PUBLIC_CANDLE_BUDGET_UNAVAILABLE"


def test_settlement_write_failure_keeps_durable_prepaid_weight(tmp_path, monkeypatch):
    clock = Clock(); guard = make(tmp_path, clock, lambda body: rows(body, 1)); warm(guard, clock)
    original = guard._write; writes = []
    def write(state):
        writes.append(1)
        if len(writes) == 3: raise OSError("fake settlement disk failure")
        original(state)
    monkeypatch.setattr(guard, "_write", write)
    assert guard.request("BTC", "1m", 500)["reason"] == "PUBLIC_CANDLE_BUDGET_UNAVAILABLE"
    assert sum(item["weight"] for item in charges(guard)) == 29


def test_cache_entry_count_bounded(tmp_path):
    clock = Clock(); guard = make(tmp_path, clock, rows); warm(guard, clock)
    for limit in range(1, 16):
        assert guard.request("BTC", "1m", limit)["state"] == "READY"
        clock.advance(60)
    assert len(json.loads(guard.path.read_text())["cache"]) == 12


def _process_request(path, now, limit, counter):
    def post(body):
        with counter.get_lock(): counter.value += 1
        return rows(body)
    PublicCandleBudget(Path(path), clock=lambda: now, wall_clock=lambda: 2_000_000_000_001, post=post).request("BTC", "1m", limit)


def test_concurrent_processes_share_one_budget_file(tmp_path):
    clock = Clock(); guard = make(tmp_path, clock, rows); warm(guard, clock)
    context = multiprocessing.get_context("fork")
    count = context.Value("i", 0)
    processes = [context.Process(target=_process_request, args=(str(tmp_path), clock.now, limit, count)) for limit in range(1, 21)]
    for process in processes: process.start()
    for process in processes:
        process.join(5)
        assert process.exitcode == 0
    assert 0 < count.value <= 7
    assert sum(item["weight"] for item in charges(guard)) <= CAPACITY


def test_delayed_reservation_is_rebound_before_http_or_expired_without_http(tmp_path):
    clock = Clock(); guard = make(tmp_path, clock, rows); warm(guard, clock)
    def delayed_wall(): clock.advance(29); return 2_000_000_000_001
    guard.wall_clock = delayed_wall
    assert guard.request("BTC", "1m", 500)["state"] == "READY"
    assert charges(guard)[0]["at_ns"] == clock.now
    guard.wall_clock = lambda: (clock.advance(31) or 2_000_000_000_001)
    def no_post(_body): raise AssertionError("expired lease posted")
    guard.post = no_post
    assert guard.request("SOL", "1m", 500)["state"] == "INVALID"


def pure_api_module():
    import ast
    import sys
    import types
    path = Path(__file__).parents[1] / "coinmaster/api/runtime_sidecar.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    allowed = {"coinmaster.api.gui_auth", "coinmaster.api.hl_public_candle_budget"}
    tree.body = [node for node in tree.body if
                 isinstance(node, (ast.Import, ast.ImportFrom)) and not
                 (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("coinmaster") and node.module not in allowed)
                 or isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                 or isinstance(node, ast.Assign) and not any(isinstance(t, ast.Name) and t.id == "app" for t in node.targets)]
    module = types.ModuleType("pure_candle_api_route")
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(tree, str(path), "exec"), module.__dict__)
    module.create_control_app = lambda **_kwargs: module.FastAPI()
    return module


def test_api_route_uses_existing_gui_state_directory_without_native_imports(tmp_path, monkeypatch):
    module = pure_api_module()
    calls = []
    class FakeBudget:
        def __init__(self, state_dir): calls.append(state_dir)
        def request(self, coin, interval, limit):
            calls.append((coin, interval, limit))
            return PublicCandleBudget._unavailable(coin, interval, "TEST_ONLY")
    module.PublicCandleBudget = FakeBudget
    for key in ("COINMASTER_GUI_USERNAME", "COINMASTER_GUI_PASSWORD_HASH", "COINMASTER_GUI_ORIGIN"):
        monkeypatch.delenv(key, raising=False)
    app = module.create_runtime_app(session_database=str(tmp_path / "auth.sqlite"), token="fixture")
    route = next(route for route in app.routes if getattr(route, "path", None) == "/api/v1/markets/hyperliquid/candles")
    response = route.endpoint("BTC", "1m", 300)
    assert calls == [tmp_path, ("BTC", "1m", 300)]
    assert response.quote_currency == "USDC" and response.state == "UNAVAILABLE"


def test_boot_change_even_with_higher_clock_and_unavailable_boot_id_deny(tmp_path):
    clock = Clock(); calls = []
    guard = make(tmp_path, clock, lambda body: calls.append(body) or rows(body))
    guard.boot_id = lambda: "boot-a"
    warm(guard, clock)
    assert guard.request("BTC", "1m", 500)["state"] == "READY"
    clock.advance(1000)
    guard.boot_id = lambda: "boot-b"
    assert guard.request("SOL", "1m", 500)["reason"] == "PUBLIC_CANDLE_BUDGET_UNAVAILABLE"
    guard.boot_id = lambda: ""
    assert guard.request("SOL", "1m", 500)["reason"] == "PUBLIC_CANDLE_BUDGET_UNAVAILABLE"
    assert len(calls) == 1


def test_backwards_clock_is_latched_after_clock_catches_up(tmp_path):
    clock = Clock(); guard = make(tmp_path, clock, rows); warm(guard, clock)
    guard.request("BTC", "1m", 500)
    clock.advance(-1)
    assert guard.request("SOL", "1m", 500)["reason"] == "PUBLIC_CANDLE_BUDGET_UNAVAILABLE"
    clock.advance(1000)
    assert make(tmp_path, clock, rows).request("SOL", "1m", 500)["reason"] == "PUBLIC_CANDLE_BUDGET_UNAVAILABLE"
    assert json.loads(guard.path.read_text())["fault"] == "CANDLE_BUDGET_CLOCK_REVERSED"


def test_valid_json_bit_flip_fails_checksum_without_http(tmp_path):
    clock = Clock(); calls = []
    guard = make(tmp_path, clock, lambda body: calls.append(body) or rows(body)); warm(guard, clock)
    guard.request("BTC", "1m", 500)
    state = json.loads(guard.path.read_text()); state["charges"][0]["weight"] = 28
    guard.path.write_text(json.dumps(state))
    clock.advance(60)
    assert guard.request("SOL", "1m", 500)["reason"] == "PUBLIC_CANDLE_BUDGET_UNAVAILABLE"
    assert len(calls) == 1


def test_affected_existing_api_route_fixture_without_native_worker_segment(tmp_path, monkeypatch):
    import ast
    import asyncio
    from urllib.parse import urlsplit
    from coinmaster.api.hl_public_candles import public_candles
    module = pure_api_module()
    path = Path(__file__).with_name("test_hl_dashboard_data.py")
    tree = ast.parse(path.read_text(), filename=str(path))
    original = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "test_authenticated_sidecar_relays_real_worker_equity_and_public_candles")
    # Execute only the actual affected public-candle API tail, never its native
    # worker/server setup or the module's native imports.
    start = next(index for index, node in enumerate(original.body) if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "now_ms" for t in node.targets))
    original.body = original.body[start:]
    helpers = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {"_api_get", "_candle"}]
    isolated = ast.Module(body=helpers + [original], type_ignores=[])
    namespace = {"sidecar": module, "create_runtime_app": module.create_runtime_app, "public_candles": public_candles,
                 "asyncio": asyncio, "json": json, "urlsplit": urlsplit, "MINUTE_MS": 60000}
    exec(compile(isolated, str(path), "exec"), namespace)
    for key in ("COINMASTER_GUI_USERNAME", "COINMASTER_GUI_PASSWORD_HASH", "COINMASTER_GUI_ORIGIN"):
        monkeypatch.delenv(key, raising=False)
    namespace[original.name](monkeypatch, tmp_path)
