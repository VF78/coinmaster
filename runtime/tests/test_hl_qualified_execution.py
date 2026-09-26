"""Credential-free pinned native clean-flat report and startup handover tests."""
from __future__ import annotations

import asyncio
import time
from decimal import Decimal

import pytest
from nautilus_trader.adapters.hyperliquid.config import HyperliquidExecClientConfig
from nautilus_trader.adapters.hyperliquid.execution import HyperliquidExecutionClient
from nautilus_trader.common import Environment
from nautilus_trader.common.providers import InstrumentProvider
from nautilus_trader.config import LiveExecClientConfig, LoggingConfig
from nautilus_trader.live.config import LiveExecEngineConfig, RoutingConfig, TradingNodeConfig
from nautilus_trader.live.factories import LiveExecClientFactory
from nautilus_trader.live.execution_engine import LiveExecutionEngine
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.currencies import USDC
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.objects import AccountBalance, Money
from nautilus_trader.trading.strategy import Strategy

from coinmaster.ops.hl_qualified_execution import (
    CleanFlatScope, QualifiedHyperliquidExecutionClient,
)

ACCOUNT = "0x" + "a" * 40


class FakeInfo:
    def __init__(self, *, bad=None):
        self.bad = bad
        self.calls = []

    async def __call__(self, body):
        self.calls.append(body)
        if body["type"] == self.bad:
            raise TimeoutError("fake timeout")
        if body["type"] == "frontendOpenOrders":
            return []
        if body["type"] == "clearinghouseState":
            return {"assetPositions": [], "marginSummary": {"accountValue": "10000"}}
        if body["type"] == "userFillsByTime":
            return []
        raise AssertionError(body)


class FakeNativeHttp:
    def __init__(self, error=None, positions=None):
        self.error = error
        self.positions = positions or []
        self.calls = []

    async def _request(self, kind):
        self.calls.append(kind)
        if self.error:
            raise self.error
        return self.positions if kind == "positions" else []

    async def request_order_status_reports(self, **kwargs):
        return await self._request("orders")

    async def request_fill_reports(self, **kwargs):
        return await self._request("fills")

    async def request_position_status_reports(self, **kwargs):
        return await self._request("positions")


class FakeQualifiedClient(QualifiedHyperliquidExecutionClient):
    async def _connect(self):
        now = self._clock.timestamp_ns()
        total = Money(Decimal("10000"), USDC)
        self.generate_account_state([AccountBalance(total, Money(0, USDC), total)], [], True, now)
        for index in range(FakeFactory.emit_count):
            self._handle_msg(f"buffered-{index}")

    def _cache_is_clean_flat(self):
        return not FakeFactory.force_prior_state and super()._cache_is_clean_flat()


class FakeFactory(LiveExecClientFactory):
    info = None
    native = None
    created = None
    emit_count = 1
    force_prior_state = False
    durable_state_empty = True

    @staticmethod
    def create(loop, name, config, msgbus, cache, clock):
        client = FakeQualifiedClient(
            loop=loop, client=FakeFactory.native, msgbus=msgbus, cache=cache,
            clock=clock, instrument_provider=InstrumentProvider(),
            config=HyperliquidExecClientConfig(account_address=ACCOUNT),
            name="HYPERLIQUID", account_address=ACCOUNT,
        )
        client.install_clean_flat_scope(
            CleanFlatScope(ACCOUNT, "", int(time.time() * 1000) - 10_000,
                           frozenset({"BTC", "SOL"}), lambda: FakeFactory.durable_state_empty),
            FakeFactory.info,
        )
        FakeFactory.created = client
        return client


class ReleaseStrategy(Strategy):
    def __init__(self, events):
        super().__init__()
        self.events = events

    def on_start(self):
        self.events.append("on_start")
        FakeFactory.created.release_ws_after_strategy_start()


async def run_node(*, info=None, native=None, emit_count=1,
                   force_prior_state=False, durable_state_empty=True):
    FakeFactory.info = info or FakeInfo()
    FakeFactory.native = native or FakeNativeHttp()
    FakeFactory.created = None
    FakeFactory.emit_count = emit_count
    FakeFactory.force_prior_state = force_prior_state
    FakeFactory.durable_state_empty = durable_state_empty
    events = []
    config = TradingNodeConfig(
        environment=Environment.LIVE, trader_id="HL-QUALIFIED-FAKE",
        logging=LoggingConfig(log_level="ERROR"),
        exec_engine=LiveExecEngineConfig(reconciliation=True, reconciliation_startup_delay_secs=0.0),
        exec_clients={"FAKE": LiveExecClientConfig(routing=RoutingConfig(venues=frozenset({"HYPERLIQUID"})))},
    )
    node = TradingNode(config=config, loop=asyncio.get_running_loop())
    node.add_exec_client_factory("FAKE", FakeFactory)
    node.build()
    strategy = ReleaseStrategy(events)
    node.trader.add_strategy(strategy)
    try:
        await node.kernel.start_async()
        client = FakeFactory.created
        snapshot = (client._ws_gate, len(client._ws_buffer))
        return node, events, client, snapshot
    finally:
        if node.is_running():
            await node.kernel.stop_async()
        node.kernel.dispose()


def test_clean_flat_mass_status_reconciles_before_on_start_and_releases_once(monkeypatch):
    events = []
    monkeypatch.setattr(HyperliquidExecutionClient, "_handle_msg", lambda self, msg: events.append(msg))
    original = LiveExecutionEngine._reconcile_execution_mass_status
    def tracked(engine, mass):
        events.append("engine_applied")
        return original(engine, mass)
    monkeypatch.setattr(LiveExecutionEngine, "_reconcile_execution_mass_status", tracked)
    node, starts, client, snapshot = asyncio.run(run_node())
    assert starts == ["on_start"]
    assert events == ["engine_applied", "buffered-0"]
    assert snapshot == ("RELEASED", 0)
    assert client._ws_gate == "FAILED" and not client._ws_buffer  # disconnect invalidates handover
    assert FakeFactory.native.calls == ["orders", "fills", "positions"]
    assert len(FakeFactory.info.calls) == 6


def test_info_timeout_prevents_strategy_start_and_buffer_release(monkeypatch):
    events = []
    monkeypatch.setattr(HyperliquidExecutionClient, "_handle_msg", lambda self, msg: events.append(msg))
    node, starts, client, snapshot = asyncio.run(run_node(info=FakeInfo(bad="userFillsByTime")))
    assert starts == [] and events == []
    assert snapshot == ("BUFFERING", 1)
    assert client._qualified_generation is None
    assert client._ws_gate == "FAILED" and not client._ws_buffer


def test_native_timeout_prevents_strategy_start_and_buffer_release(monkeypatch):
    events = []
    monkeypatch.setattr(HyperliquidExecutionClient, "_handle_msg", lambda self, msg: events.append(msg))
    node, starts, client, snapshot = asyncio.run(run_node(native=FakeNativeHttp(error=TimeoutError("native timeout"))))
    assert starts == [] and events == []
    assert snapshot == ("BUFFERING", 1)
    assert client._qualified_generation is None


def test_malformed_info_or_native_row_never_starts_strategy():
    class MalformedInfo(FakeInfo):
        async def __call__(self, body):
            if body["type"] == "clearinghouseState":
                return None
            return await super().__call__(body)

    for options in ({"info": MalformedInfo()}, {"native": FakeNativeHttp(positions=[None])}):
        node, starts, client, snapshot = asyncio.run(run_node(**options))
        assert starts == []
        assert snapshot == ("BUFFERING", 1)
        assert client._qualified_generation is None


def test_buffer_overflow_and_prior_cache_state_block_start():
    for options, expected in (
        ({"emit_count": 4097}, ("FAILED", 0)),
        ({"force_prior_state": True}, ("BUFFERING", 1)),
        ({"durable_state_empty": False}, ("BUFFERING", 1)),
    ):
        node, starts, client, snapshot = asyncio.run(run_node(**options))
        assert starts == []
        assert snapshot == expected
        assert client._qualified_generation is None


def test_scope_rejects_open_durable_intent_and_direct_reports():
    node, starts, client, snapshot = asyncio.run(run_node())
    with pytest.raises(ValueError, match="OPEN_OR_NONPERP"):
        client.install_clean_flat_scope(
            CleanFlatScope(ACCOUNT, "", 1, frozenset({"BTC"}), lambda: False), FakeInfo(),
        )
    with pytest.raises(RuntimeError, match="DIRECT_FILL_REPORT_UNQUALIFIED"):
        asyncio.run(client.generate_fill_reports(None))
