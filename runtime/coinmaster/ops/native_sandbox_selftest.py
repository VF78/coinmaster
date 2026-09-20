"""Isolated native ``SandboxExecutionClient`` lifecycle proof.

This intentionally has no data-client factory and no service journal. It
injects native quotes into a short-lived TradingNode, then asserts the native
Sandbox fills and reports a flat BTC/SOL account. It never contacts a venue.
"""
from __future__ import annotations

import asyncio
import os
from decimal import Decimal
from pathlib import Path

from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.adapters.sandbox.factory import SandboxLiveExecClientFactory
from nautilus_trader.common import Environment
from nautilus_trader.config import LoggingConfig, StrategyConfig
from nautilus_trader.live.config import LiveExecEngineConfig, RoutingConfig, TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.currencies import BTC, SOL, USDT
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import CryptoPerpetual
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.trading.strategy import Strategy

from coinmaster.ops.paper import PaperRuntime


BYBIT = Venue("BYBIT")


def _perpetual(symbol: str, base, tick: str, step: str) -> CryptoPerpetual:
    return CryptoPerpetual(
        InstrumentId(Symbol(f"{symbol}-LINEAR"), BYBIT), Symbol(symbol), base, USDT, USDT,
        False, len(tick.partition(".")[2]), len(step.partition(".")[2]),
        Price.from_str(tick), Quantity.from_str(step), 0, 0,
        margin_init=Decimal("0.025"), margin_maint=Decimal("0.005"),
        maker_fee=Decimal("0.001"), taker_fee=Decimal("0.001"),
    )


BTC_PERP = _perpetual("BTCUSDT", BTC, "0.1", "0.001")
SOL_PERP = _perpetual("SOLUSDT", SOL, "0.01", "0.1")


class SelfTestConfig(StrategyConfig, frozen=True):
    btc_id: InstrumentId
    sol_id: InstrumentId


class SandboxLifecycleStrategy(Strategy):
    """All orders/fills/positions are owned by the native sandbox client."""
    def __init__(self, config: SelfTestConfig) -> None:
        super().__init__(config)
        self.step = 0

    def on_start(self) -> None:
        self.subscribe_quote_ticks(self.config.btc_id)
        self.subscribe_quote_ticks(self.config.sol_id)

    def on_quote_tick(self, tick: QuoteTick) -> None:
        actions = (
            (self.config.btc_id, OrderSide.BUY, "1.000", False),
            (self.config.btc_id, OrderSide.SELL, "0.400", True),
            (self.config.sol_id, OrderSide.SELL, "500.0", False),
            (self.config.btc_id, OrderSide.SELL, "0.600", True),
            (self.config.sol_id, OrderSide.BUY, "500.0", True),
        )
        if self.step >= len(actions) or tick.instrument_id != actions[self.step][0]:
            return
        instrument_id, side, quantity, reduce_only = actions[self.step]
        instrument = self.cache.instrument(instrument_id)
        assert instrument is not None
        self.submit_order(self.order_factory.market(
            instrument_id=instrument_id,
            order_side=side,
            quantity=instrument.make_qty(Decimal(quantity)),
            time_in_force=TimeInForce.IOC,
            reduce_only=reduce_only,
        ))
        self.step += 1


class CrashAfterPartialConfig(StrategyConfig, frozen=True):
    btc_id: InstrumentId
    sol_id: InstrumentId
    journal_path: str


class CrashAfterPartialStrategy(Strategy):
    """Persist an open native group then die after a SOL native submit.

    The first two native Sandbox fills open one BTC and reduce it by 0.4.
    On the next SOL quote the strategy saves the still-open BTC position and
    a pre-submit SOL intent, submits that order to the native execution
    engine, and immediately SIGKILLs its process.  The missing callback is
    intentional: this is the precise crash window the journal must contain.
    """
    def __init__(self, config: CrashAfterPartialConfig) -> None:
        super().__init__(config)
        self.step = 0
        self.journal = PaperRuntime(Path(config.journal_path), "paper-crash-harness", int(60e9))
        self.journal.acquire()

    def on_start(self) -> None:
        self.subscribe_quote_ticks(self.config.btc_id)
        self.subscribe_quote_ticks(self.config.sol_id)

    def on_order_filled(self, event) -> None:
        self.journal.record_native_event(str(event.trade_id), "fill")

    def _positions(self) -> list[dict[str, str]]:
        positions = []
        for position in self.cache.positions_open():
            quantity = position.quantity.as_decimal()
            positions.append({
                "instrument_id": str(position.instrument_id),
                "signed_quantity": str(quantity if position.is_long else -quantity),
            })
        return sorted(positions, key=lambda item: item["instrument_id"])

    def on_quote_tick(self, tick: QuoteTick) -> None:
        actions = (
            (self.config.btc_id, OrderSide.BUY, "1.000", False),
            (self.config.btc_id, OrderSide.SELL, "0.400", True),
            (self.config.sol_id, OrderSide.SELL, "500.0", False),
        )
        if self.step >= len(actions) or tick.instrument_id != actions[self.step][0]:
            return
        instrument_id, side, quantity, reduce_only = actions[self.step]
        instrument = self.cache.instrument(instrument_id)
        assert instrument is not None
        order = self.order_factory.market(
            instrument_id=instrument_id,
            order_side=side,
            quantity=instrument.make_qty(Decimal(quantity)),
            time_in_force=TimeInForce.IOC,
            reduce_only=reduce_only,
        )
        self.step += 1
        if instrument_id != self.config.sol_id:
            self.submit_order(order)
            return

        # The preceding native BTC entry + partial reduce must have left a
        # process-local 0.600 BTC position.  Store that evidence before the
        # native SOL submit; no process is allowed to synthesize it on restart.
        positions = self._positions()
        assert positions == [{"instrument_id": str(self.config.btc_id), "signed_quantity": "0.6"}], positions
        client_order_id = str(order.client_order_id)
        self.journal.snapshot(
            ts_ns=tick.ts_event,
            positions=positions,
            orders=[{"client_order_id": client_order_id}],
            funding_event_ids=[],
        )
        assert self.journal.record_submission(
            client_order_id=client_order_id,
            intent_id="sol-add-after-btc-partial",
            episode_id="native-btc-sol-crash-group",
            action="SOL_ADD",
            instrument_id=str(self.config.sol_id),
            quantity=quantity,
            reduce_only=False,
        )
        self.submit_order(order)
        # Do not acknowledge, terminalize, or close the journal.  This is a
        # real process death after native submit and before callback/ACK.
        os.kill(os.getpid(), 9)


def _quote(instrument_id: InstrumentId, bid: str, ask: str, ts: int) -> QuoteTick:
    size = "1000.000" if instrument_id == BTC_PERP.id else "1000.0"
    return QuoteTick(instrument_id, Price.from_str(bid), Price.from_str(ask), Quantity.from_str(size), Quantity.from_str(size), ts, ts)


async def _run() -> dict[str, int]:
    config = TradingNodeConfig(
        environment=Environment.LIVE,
        trader_id="PAPER-SELFTEST-001",
        logging=LoggingConfig(log_level="ERROR"),
        exec_engine=LiveExecEngineConfig(reconciliation=False),
        exec_clients={"SANDBOX": SandboxExecutionClientConfig(
            venue="BYBIT", starting_balances=["100000 USDT"], base_currency="USDT",
            use_reduce_only=True, routing=RoutingConfig(venues=frozenset({"BYBIT"})),
        )},
    )
    node = TradingNode(config=config, loop=asyncio.get_running_loop())
    node.add_exec_client_factory("SANDBOX", SandboxLiveExecClientFactory)
    node.build()
    node.cache.add_instrument(BTC_PERP)
    node.cache.add_instrument(SOL_PERP)
    node.trader.add_strategy(SandboxLifecycleStrategy(SelfTestConfig(btc_id=BTC_PERP.id, sol_id=SOL_PERP.id)))
    await node.kernel.start_async()
    try:
        for tick in (
            _quote(BTC_PERP.id, "100.0", "100.1", 1),
            _quote(BTC_PERP.id, "100.0", "100.1", 2),
            _quote(SOL_PERP.id, "30.00", "30.01", 3),
            _quote(BTC_PERP.id, "100.0", "100.1", 4),
            _quote(SOL_PERP.id, "30.00", "30.01", 5),
        ):
            node.kernel.data_engine.process(tick)
            # Let the native data/risk/exec queues flush before the next
            # quote triggers the following lifecycle action.
            await asyncio.sleep(0.05)
        fills = node.trader.generate_order_fills_report()
        account = node.trader.generate_account_report(BYBIT)
        if len(fills) != 5 or node.cache.positions_open() or account.empty:
            raise RuntimeError("NATIVE_SANDBOX_LIFECYCLE_FAILED")
        return {"fills": len(fills), "open_positions": len(node.cache.positions_open()), "account_report_present": int(not account.empty)}
    finally:
        await node.kernel.stop_async()
        node.kernel.dispose()


async def _run_crash_after_partial_fill(database: Path) -> None:
    """Run only in a disposable subprocess; this function SIGKILLs itself."""
    config = TradingNodeConfig(
        environment=Environment.LIVE,
        trader_id="PAPER-CRASH-HARNESS-001",
        logging=LoggingConfig(log_level="ERROR"),
        exec_engine=LiveExecEngineConfig(reconciliation=False),
        exec_clients={"SANDBOX": SandboxExecutionClientConfig(
            venue="BYBIT", starting_balances=["100000 USDT"], base_currency="USDT",
            use_reduce_only=True, routing=RoutingConfig(venues=frozenset({"BYBIT"})),
        )},
    )
    node = TradingNode(config=config, loop=asyncio.get_running_loop())
    node.add_exec_client_factory("SANDBOX", SandboxLiveExecClientFactory)
    node.build()
    node.cache.add_instrument(BTC_PERP)
    node.cache.add_instrument(SOL_PERP)
    node.trader.add_strategy(CrashAfterPartialStrategy(CrashAfterPartialConfig(
        btc_id=BTC_PERP.id, sol_id=SOL_PERP.id, journal_path=str(database),
    )))
    await node.kernel.start_async()
    for tick in (
        _quote(BTC_PERP.id, "100.0", "100.1", 1),
        _quote(BTC_PERP.id, "100.0", "100.1", 2),
        _quote(SOL_PERP.id, "30.00", "30.01", 3),
    ):
        node.kernel.data_engine.process(tick)
        await asyncio.sleep(0.05)
    raise RuntimeError("NATIVE_CRASH_HARNESS_DID_NOT_TERMINATE")


def run() -> dict[str, int]:
    return asyncio.run(_run())


def run_crash_after_partial_fill(database: Path) -> None:
    """Public subprocess entry point for recovery-contract integration tests."""
    asyncio.run(_run_crash_after_partial_fill(database))


if __name__ == "__main__":
    print(run())
