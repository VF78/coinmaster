"""Pinned native Sandbox proof that a flat cycle survives NETTING reopen in projection."""
from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace

from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.common import Environment
from nautilus_trader.config import LoggingConfig
from nautilus_trader.live.config import LiveExecEngineConfig, RoutingConfig, TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.currencies import USDC
from nautilus_trader.model.data import BarSpecification, BarType, QuoteTick
from nautilus_trader.model.enums import AggregationSource, BarAggregation, OrderSide, PriceType, TimeInForce
from nautilus_trader.model.identifiers import ClientId, ClientOrderId, InstrumentId, Venue
from nautilus_trader.model.objects import Price, Quantity

from coinmaster.ops.hl_sandbox_money import (
    SandboxLiveExecClientFactory,
    model_fx_pair_and_quote,
    native_money_projection,
)
from coinmaster.ops.hyperliquid_testnet import BTC_PERP, SOL_PERP, SANDBOX_LEVERAGES
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig
from coinmaster.venues.marks import venue_mark_data_type
from test_hl_stageg_sandbox_lifecycle import HL_BTC, HL_SOL


VENUE = Venue("HYPERLIQUID")


class MoneyCycleProbe(WaveOverlayStrategy):
    """Submit fixed native IDs; no strategy rule or approval seal is changed."""

    def __init__(self, config):
        super().__init__(config)
        self.step = 0

    def on_start(self):
        self.subscribe_quote_ticks(self.config.btc_id)

    def on_quote_tick(self, tick):
        if self.step == 0:
            order = self.order_factory.market(
                instrument_id=BTC_PERP,
                order_side=OrderSide.BUY,
                quantity=Quantity.from_str("5.01000"),
                time_in_force=TimeInForce.IOC,
                client_order_id=ClientOrderId("CM-MONEY-ENTRY-1"),
            )
        elif self.step == 1:
            order = self.order_factory.limit(
                instrument_id=BTC_PERP,
                order_side=OrderSide.SELL,
                quantity=Quantity.from_str("5.01000"),
                price=Price.from_str("60010.0"),
                time_in_force=TimeInForce.GTC,
                post_only=True,
                reduce_only=True,
                client_order_id=ClientOrderId("CM-MONEY-TP-1"),
            )
        elif self.step == 2:
            if tick.ts_event < 4:
                return
            order = self.order_factory.market(
                instrument_id=BTC_PERP,
                order_side=OrderSide.BUY,
                quantity=Quantity.from_str("0.01000"),
                time_in_force=TimeInForce.IOC,
                client_order_id=ClientOrderId("CM-MONEY-ENTRY-2"),
            )
        else:
            return
        self.step += 1
        self.submit_order(order)


def quote(ts, bid, ask, size="1000.00000"):
    return QuoteTick(
        BTC_PERP, Price.from_str(bid), Price.from_str(ask),
        Quantity.from_str(size), Quantity.from_str("1000.00000"), ts, ts,
    )


def snapshot(node):
    account = node.cache.account_for_venue(VENUE)
    money = native_money_projection(
        node.cache,
        {BTC_PERP: SimpleNamespace(price=Decimal("60000"), ts_event=5)},
        now_ns=5,
    )
    return {
        "money": money,
        "cash": account.balance_total(USDC).as_decimal(),
        "free": account.balance_free(USDC).as_decimal(),
        "locked": account.balance_locked(USDC).as_decimal(),
        "open_positions": len(node.cache.positions_open()),
        "current_cycles": len(node.cache.positions()),
        "archived_cycles": len(node.cache.position_snapshots()),
    }


async def run_native_cycle():
    spec = BarSpecification(1, BarAggregation.DAY, PriceType.LAST)
    btc_bar = BarType(InstrumentId.from_str("BTCUSDT-LINEAR.BYBIT"), spec, AggregationSource.EXTERNAL)
    sol_bar = BarType(InstrumentId.from_str("SOLUSDT-LINEAR.BYBIT"), spec, AggregationSource.EXTERNAL)
    strategy = MoneyCycleProbe(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP, sol_id=SOL_PERP,
        btc_bar_type=btc_bar, sol_bar_type=sol_bar,
        btc_mark_data_type=venue_mark_data_type(BTC_PERP),
        sol_mark_data_type=venue_mark_data_type(SOL_PERP),
        mark_client_id=ClientId("HYPERLIQUID-MAINNET-DATA"),
        active_seed=Decimal("10000"),
    ))
    config = TradingNodeConfig(
        environment=Environment.LIVE,
        trader_id="HL-NATIVE-MONEY-REOPEN",
        logging=LoggingConfig(log_level="ERROR"),
        exec_engine=LiveExecEngineConfig(reconciliation=False),
        exec_clients={"SANDBOX": SandboxExecutionClientConfig(
            venue="HYPERLIQUID", starting_balances=["10000 USDC"],
            base_currency="USDC", leverages=dict(SANDBOX_LEVERAGES),
            use_reduce_only=True,
            routing=RoutingConfig(venues=frozenset({"HYPERLIQUID"})),
        )},
    )
    node = TradingNode(config=config, loop=asyncio.get_running_loop())
    node.add_exec_client_factory("SANDBOX", SandboxLiveExecClientFactory)
    node.build()
    node.cache.add_instrument(HL_BTC)
    node.cache.add_instrument(HL_SOL)
    pair, fx_quote = model_fx_pair_and_quote()
    node.cache.add_instrument(pair)
    node.cache.add_quote_tick(fx_quote)
    node.trader.add_strategy(strategy)
    await node.kernel.start_async()
    try:
        flat = None
        ticks = [
            quote(1, "59999.0", "60000.0"),
            quote(2, "60001.0", "60002.0"),
            quote(3, "60011.0", "60012.0", "0.00500"),
            quote(4, "60011.0", "60012.0", "0.00500"),
            quote(5, "59999.0", "60000.0"),
        ]
        for tick in ticks:
            node.kernel.data_engine.process(tick)
            await asyncio.sleep(0.05)
            if tick.ts_event == 3:
                flat = snapshot(node)
        return flat, snapshot(node)
    finally:
        await node.kernel.stop_async()
        node.kernel.dispose()


def test_native_flat_then_reopen_retains_archived_realized_and_fees():
    flat, reopened = asyncio.run(run_native_cycle())
    assert flat["open_positions"] == 0
    assert flat["archived_cycles"] == 0
    assert flat["cash"] == Decimal("9869.732485")
    assert Decimal(flat["money"]["fees"]) == Decimal("180.367515")
    assert Decimal(flat["money"]["realized_pnl_net_fees"]) == flat["cash"] - Decimal("10000")

    assert reopened["open_positions"] == 1
    assert reopened["current_cycles"] == reopened["archived_cycles"] == 1
    assert reopened["cash"] == Decimal("9869.462431")
    assert Decimal(reopened["money"]["fees"]) == Decimal("180.637569")
    assert Decimal(reopened["money"]["realized_pnl_net_fees"]) == reopened["cash"] - Decimal("10000")
    assert Decimal(reopened["money"]["native_free"]) == reopened["free"]
    assert Decimal(reopened["money"]["native_locked"]) == reopened["locked"]
