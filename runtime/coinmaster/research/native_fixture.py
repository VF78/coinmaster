"""A deterministic two-perpetual native fill fixture for P1 integration checks."""

from __future__ import annotations

from decimal import Decimal
from dataclasses import dataclass

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import SimulationModuleConfig
from nautilus_trader.backtest.modules import SimulationModule
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig, StrategyConfig
from nautilus_trader.model.currencies import BTC, SOL, USDT
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide, TimeInForce
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import CryptoPerpetual
from nautilus_trader.model.objects import Money, Price, Quantity
from nautilus_trader.model.orders import MarketOrder
from nautilus_trader.trading.strategy import Strategy


SIM = Venue("P1SIM")


def perpetual(symbol: str, base, tick: str, step: str, im: str) -> CryptoPerpetual:
    instrument_id = InstrumentId(Symbol(f"{symbol}-PERP"), SIM)
    return CryptoPerpetual(
        instrument_id, Symbol(symbol), base, USDT, USDT, False,
        len(tick.partition(".")[2]), len(step.partition(".")[2]),
        Price.from_str(tick), Quantity.from_str(step), 0, 0,
        margin_init=Decimal(im), margin_maint=Decimal("0.005"),
        maker_fee=Decimal("0.001"), taker_fee=Decimal("0.001"),
    )


BTC_PERP = perpetual("BTCUSDT", BTC, "0.1", "0.001", "0.025")
SOL_PERP = perpetual("SOLUSDT", SOL, "0.01", "0.1", "0.05")


class FixtureConfig(StrategyConfig, frozen=True):
    btc_id: InstrumentId
    sol_id: InstrumentId


class FixtureStrategy(Strategy):
    """Orders only after a quote; resulting fills are emitted by Nautilus."""

    def __init__(self, config: FixtureConfig) -> None:
        super().__init__(config)
        self._step = 0
        self._instruments: dict[InstrumentId, CryptoPerpetual] = {}

    def on_start(self) -> None:
        for instrument_id in (self.config.btc_id, self.config.sol_id):
            instrument = self.cache.instrument(instrument_id)
            assert instrument is not None
            self._instruments[instrument_id] = instrument
            self.subscribe_quote_ticks(instrument_id)

    def on_quote_tick(self, tick: QuoteTick) -> None:
        # Each order fills against the next quote. This creates BTC entry,
        # partial BTC reduce, SOL add, and final closes from native fill events.
        actions = (
            (self.config.btc_id, OrderSide.BUY, "1.000"),
            (self.config.btc_id, OrderSide.SELL, "0.400"),
            (self.config.sol_id, OrderSide.SELL, "500.0"),
            (self.config.btc_id, OrderSide.SELL, "0.600"),
            (self.config.sol_id, OrderSide.BUY, "500.0"),
        )
        if self._step >= len(actions):
            return
        instrument_id, side, quantity = actions[self._step]
        if tick.instrument_id != instrument_id:
            return
        order: MarketOrder = self.order_factory.market(
            instrument_id=instrument_id,
            order_side=side,
            quantity=self._instruments[instrument_id].make_qty(Decimal(quantity)),
            time_in_force=TimeInForce.IOC,
        )
        self.submit_order(order)
        self._step += 1


@dataclass(frozen=True)
class FundingInstruction:
    """A venue funding event normalized before the native engine run."""

    event_id: str
    instrument_id: InstrumentId
    rate: Decimal
    ts_event: int


class PerpetualFundingModule(SimulationModule):
    """Minimal native-account funding module; no second balance or PnL engine."""

    def __init__(self, events: tuple[FundingInstruction, ...]) -> None:
        super().__init__(SimulationModuleConfig())
        self._events = events
        self._applied: set[str] = set()

    def process(self, ts_now: int) -> None:
        for event in self._events:
            if event.event_id in self._applied or event.ts_event > ts_now:
                continue
            for position in self.exchange.cache.positions_open():
                if position.instrument_id != event.instrument_id:
                    continue
                instrument = self.exchange.instruments[position.instrument_id]
                mark = Decimal(str(self.exchange.get_book(position.instrument_id).midpoint()))
                notional = position.quantity.as_decimal() * mark
                # Positive funding: longs pay and shorts receive; negative reverses it.
                sign = Decimal("-1") if position.is_long else Decimal("1")
                self.exchange.adjust_account(Money(sign * notional * event.rate, instrument.quote_currency))
            self._applied.add(event.event_id)

    def pre_process(self, data) -> None:
        pass

    def log_diagnostics(self, logger) -> None:
        logger.info(f"Perpetual funding events applied: {len(self._applied)}")

    def reset(self) -> None:
        self._applied.clear()


def quote(instrument_id: InstrumentId, bid: str, ask: str, ts: int) -> QuoteTick:
    size = "1000.0" if instrument_id == SOL_PERP.id else "1000.000"
    return QuoteTick(
        instrument_id, Price.from_str(bid), Price.from_str(ask),
        Quantity.from_str(size), Quantity.from_str(size), ts, ts,
    )


def build_engine(funding_events: tuple[FundingInstruction, ...] = ()) -> BacktestEngine:
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(
        venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
        starting_balances=[Money(10_000, USDT)], base_currency=USDT,
        default_leverage=Decimal("1"),
        modules=[PerpetualFundingModule(funding_events)] if funding_events else None,
    )
    engine.add_instrument(BTC_PERP)
    engine.add_instrument(SOL_PERP)
    engine.add_strategy(FixtureStrategy(FixtureConfig(btc_id=BTC_PERP.id, sol_id=SOL_PERP.id)))
    return engine
