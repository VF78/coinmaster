"""Pinned Sandbox reconstruction with an open BTC and working partial maker TP.

This fixture uses native commands, matching, account and callbacks. It does
not establish a durable production replay journal or strategy-domain recovery.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal

from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.common import Environment
from nautilus_trader.config import LoggingConfig
from nautilus_trader.live.config import LiveExecEngineConfig, RoutingConfig, TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.currencies import USDC
from nautilus_trader.model.data import BarSpecification, BarType, QuoteTick, TradeTick
from nautilus_trader.model.enums import (
    AggressorSide, AggregationSource, BarAggregation, OrderSide, PriceType, TimeInForce,
)
from nautilus_trader.model.identifiers import (
    ClientId, ClientOrderId, InstrumentId, TradeId, Venue,
)
from nautilus_trader.model.objects import Price, Quantity

from coinmaster.ops.hl_sandbox_money import SandboxLiveExecClientFactory, model_fx_pair_and_quote
from coinmaster.ops.hyperliquid_testnet import BTC_PERP, SOL_PERP, SANDBOX_LEVERAGES
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig
from coinmaster.venues.marks import venue_mark_data_type
from test_hl_stageg_sandbox_lifecycle import HL_BTC, HL_SOL


VENUE = Venue("HYPERLIQUID")
ENTRY_ID = ClientOrderId("CM-REPLAY-ENTRY")
TP_ID = ClientOrderId("CM-REPLAY-TP")


class StableOrderProbe(WaveOverlayStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.step = 0
        self.decisions = []

    def on_start(self):
        self.subscribe_quote_ticks(self.config.btc_id)

    def on_quote_tick(self, tick):
        if self.step == 0:
            order = self.order_factory.market(
                instrument_id=BTC_PERP, order_side=OrderSide.BUY,
                quantity=Quantity.from_str("0.03000"),
                time_in_force=TimeInForce.IOC, client_order_id=ENTRY_ID,
            )
        elif self.step == 1:
            order = self.order_factory.limit(
                instrument_id=BTC_PERP, order_side=OrderSide.SELL,
                quantity=Quantity.from_str("0.03000"),
                price=Price.from_str("60010.0"), time_in_force=TimeInForce.GTC,
                post_only=True, reduce_only=True, client_order_id=TP_ID,
            )
        else:
            if tick.ts_event >= 5:
                working = [
                    order for order in self.cache.orders_open()
                    if order.client_order_id == TP_ID and order.status.name == "PARTIALLY_FILLED"
                ]
                self.decisions.append("HOLD_WORKING_PARTIAL_TP" if len(working) == 1 else "NO_WORKING_PARTIAL_TP")
            return
        self.step += 1
        self.submit_order(order)


def quote(ts, bid, ask):
    return QuoteTick(
        BTC_PERP, Price.from_str(bid), Price.from_str(ask),
        Quantity.from_str("1000.00000"), Quantity.from_str("1000.00000"), ts, ts,
    )


def snapshot(node, strategy):
    account = node.cache.account_for_venue(VENUE)
    return {
        "strategy_step": strategy.step,
        "next_decisions": list(strategy.decisions),
        "orders": sorted((
            str(order.client_order_id), order.status.name, str(order.quantity),
            str(order.filled_qty), str(order.leaves_qty), str(order.venue_order_id),
            tuple(map(str, order.trade_ids)),
        ) for order in node.cache.orders()),
        "positions": sorted((
            str(position.instrument_id), str(position.quantity), position.is_long,
        ) for position in node.cache.positions_open()),
        "cash": (
            str(account.balance_total(USDC).as_decimal()),
            str(account.balance_free(USDC).as_decimal()),
            str(account.balance_locked(USDC).as_decimal()),
        ),
        "fills": [
            (fill["fill_ns"], fill["qty"], fill["px"], fill["commission"], fill["native_liquidity_side"])
            for fill in strategy.fill_audit
        ],
    }


async def native_run(events):
    spec = BarSpecification(1, BarAggregation.DAY, PriceType.LAST)
    btc_bar = BarType(InstrumentId.from_str("BTCUSDT-LINEAR.BYBIT"), spec, AggregationSource.EXTERNAL)
    sol_bar = BarType(InstrumentId.from_str("SOLUSDT-LINEAR.BYBIT"), spec, AggregationSource.EXTERNAL)
    strategy = StableOrderProbe(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP, sol_id=SOL_PERP,
        btc_bar_type=btc_bar, sol_bar_type=sol_bar,
        btc_mark_data_type=venue_mark_data_type(BTC_PERP),
        sol_mark_data_type=venue_mark_data_type(SOL_PERP),
        mark_client_id=ClientId("HYPERLIQUID-MAINNET-DATA"),
        active_seed=Decimal("10000"),
    ))
    config = TradingNodeConfig(
        environment=Environment.LIVE, trader_id="HL-OPEN-REPLAY-PROBE",
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
        boundary = None
        for event in events:
            node.kernel.data_engine.process(event)
            await asyncio.sleep(0.05)
            if event.ts_event == 4:
                boundary = snapshot(node, strategy)
        return boundary, snapshot(node, strategy)
    finally:
        await node.kernel.stop_async()
        node.kernel.dispose()


def test_pinned_native_open_partial_tp_replays_before_next_decision():
    async def scenario():
        events = [
            quote(1, "59999.0", "60000.0"),
            quote(2, "60001.0", "60002.0"),
            quote(3, "60009.0", "60011.0"),
            TradeTick(
                BTC_PERP, Price.from_str("60010.0"), Quantity.from_str("0.00500"),
                AggressorSide.BUYER, TradeId("PARTIAL-TRADE-1"), 4, 4,
            ),
            quote(5, "60009.0", "60011.0"),
        ]
        uninterrupted_boundary, uninterrupted_next = await native_run(events)
        replayed_boundary, replayed_next = await native_run(events)
        assert uninterrupted_boundary == replayed_boundary
        assert uninterrupted_next == replayed_next
        assert uninterrupted_boundary["positions"] == [(str(BTC_PERP), "0.02500", True)]
        assert uninterrupted_boundary["cash"] == ("9999.1949925", "9998.7249925", "0.47")
        assert uninterrupted_boundary["fills"] == [
            ("1", "0.03", "60000", "0.81", "TAKER"),
            ("4", "0.005", "60010", "0.0450075", "MAKER"),
        ]
        tp = [order for order in uninterrupted_boundary["orders"] if order[0] == str(TP_ID)]
        assert len(tp) == 1
        assert tp[0][1:5] == ("PARTIALLY_FILLED", "0.03000", "0.00500", "0.02500")
        assert uninterrupted_boundary["strategy_step"] == 2
        assert uninterrupted_boundary["next_decisions"] == []
        assert uninterrupted_next["next_decisions"] == ["HOLD_WORKING_PARTIAL_TP"]

    asyncio.run(scenario())
