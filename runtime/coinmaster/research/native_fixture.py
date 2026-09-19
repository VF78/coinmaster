"""A deterministic two-perpetual native fill fixture for P1 integration checks."""

from __future__ import annotations

from decimal import Decimal
from dataclasses import dataclass
from pathlib import Path

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import SimulationModuleConfig
from nautilus_trader.backtest.models import LeveragedMarginModel
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
from coinmaster.ledger.journal import NativeEventJournal
from coinmaster.venues.bybit_profile import BybitVenueProfile


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
    margin_probe: bool = False
    tier_probe: bool = False
    tier_actions: tuple[tuple[InstrumentId, OrderSide, str], ...] = ()
    tier_marks: tuple["MarkPriceUpdate", ...] = ()
    tier_selected_leverage: tuple[tuple[InstrumentId, Decimal], ...] = ()
    max_mark_age_ns: int = 0


class FixtureStrategy(Strategy):
    """Orders only after a quote; resulting fills are emitted by Nautilus."""

    def __init__(self, config: FixtureConfig) -> None:
        super().__init__(config)
        self._step = 0
        self._instruments: dict[InstrumentId, CryptoPerpetual] = {}
        self.margin_rejections = 0

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
        if self.config.margin_probe:
            actions = (
                (self.config.btc_id, OrderSide.BUY, "1.000"),
                (self.config.sol_id, OrderSide.SELL, "500.0"),
                (self.config.sol_id, OrderSide.SELL, "1100.0"),
            )
        if self.config.tier_probe:
            actions = self.config.tier_actions or ((self.config.btc_id, OrderSide.BUY, "4.000"),)
        if self._step >= len(actions):
            return
        instrument_id, side, quantity = actions[self._step]
        if tick.instrument_id != instrument_id:
            return
        if self.config.margin_probe and self._step == 2 and not self._margin_allows_increase(
            instrument_id,
            Decimal(quantity),
        ):
            self.margin_rejections += 1
            self._step += 1
            return
        if self.config.tier_probe and self._is_risk_increase(instrument_id, side) and not self._tier_allows_increase(
            instrument_id,
            Decimal(quantity),
            tick.ts_event,
        ):
            self.margin_rejections += 1
            self._step += 1
            return
        order: MarketOrder = self.order_factory.market(
            instrument_id=instrument_id,
            order_side=side,
            quantity=self._instruments[instrument_id].make_qty(Decimal(quantity)),
            time_in_force=TimeInForce.IOC,
        )
        self.submit_order(order)
        self._step += 1

    def _is_risk_increase(self, instrument_id: InstrumentId, side: OrderSide) -> bool:
        position = next(
            (item for item in self.cache.positions_open() if item.instrument_id == instrument_id),
            None,
        )
        return position is None or (position.is_long and side == OrderSide.BUY) or (position.is_short and side == OrderSide.SELL)

    def _tier_allows_increase(self, instrument_id: InstrumentId, quantity: Decimal, ts_now: int) -> bool:
        try:
            policy = TierMarginPolicy(
                self.config.tier_marks,
                dict(self.config.tier_selected_leverage),
                self.config.max_mark_age_ns,
            )
            positions = {item.instrument_id: item for item in self.cache.positions_open()}
            required = Decimal("0")
            for current_id in (self.config.btc_id, self.config.sol_id):
                position = positions.get(current_id)
                current = position.quantity.as_decimal() if position is not None else Decimal("0")
                prospective = current + quantity if current_id == instrument_id else current
                if prospective:
                    required += policy.margin_for(current_id, prospective, ts_now)[0]
            account = self.cache.account_for_venue(SIM)
            return account is not None and required <= account.balance_free(USDT).as_decimal()
        except ValueError:
            # Missing/stale marks and unknown tiers block new risk, never reductions.
            return False

    def _margin_allows_increase(self, instrument_id: InstrumentId, quantity: Decimal) -> bool:
        """Fail closed using the pinned native margin model and native free balance."""
        account = self.cache.account_for_venue(SIM)
        if account is None:
            return False
        model = LeveragedMarginModel()
        required = Decimal("0")
        positions = {position.instrument_id: position for position in self.cache.positions_open()}
        for current_id, instrument in self._instruments.items():
            position = positions.get(current_id)
            current_qty = position.quantity.as_decimal() if position is not None else Decimal("0")
            total_qty = current_qty + quantity if current_id == instrument_id else current_qty
            if total_qty == 0:
                continue
            quote_tick = self.cache.quote_tick(current_id)
            if quote_tick is None:
                return False
            mark = (quote_tick.bid_price.as_decimal() + quote_tick.ask_price.as_decimal()) / 2
            required += model.calculate_margin_init(
                instrument,
                instrument.make_qty(total_qty),
                instrument.make_price(mark),
                Decimal("1"),
            ).as_decimal()
        return required <= account.balance_free(USDT).as_decimal()


@dataclass(frozen=True)
class FundingInstruction:
    """A venue funding event normalized before the native engine run."""

    event_id: str
    instrument_id: InstrumentId
    rate: Decimal
    ts_event: int
    settlement_mark: Decimal | None = None
    basis: str = "venue_mark"
    synthetic: bool = False

    def __post_init__(self) -> None:
        if self.settlement_mark is None and not self.synthetic:
            raise ValueError("production funding requires a confirmed settlement mark")
        if self.basis not in {"venue_mark", "venue_mark_prior_minute", "synthetic_mid"}:
            raise ValueError(f"unsupported funding basis: {self.basis}")


class PerpetualFundingModule(SimulationModule):
    """Minimal native-account funding module; no second balance or PnL engine."""

    def __init__(self, events: tuple[FundingInstruction, ...], journal: NativeEventJournal) -> None:
        super().__init__(SimulationModuleConfig())
        self._events = events
        self._journal = journal
        self._applied: set[str] = set()

    def process(self, ts_now: int) -> None:
        for event in self._events:
            if event.event_id in self._applied or event.ts_event > ts_now:
                continue
            if self._journal.has_funding(event.event_id):
                self._applied.add(event.event_id)
                continue
            for position in self.exchange.cache.positions_open():
                if position.instrument_id != event.instrument_id:
                    continue
                instrument = self.exchange.instruments[position.instrument_id]
                mark = event.settlement_mark
                if mark is None:  # Explicitly fixture-only; production must provide venue mark.
                    mark = Decimal(str(self.exchange.get_book(position.instrument_id).midpoint()))
                notional = position.quantity.as_decimal() * mark
                # Positive funding: longs pay and shorts receive; negative reverses it.
                sign = Decimal("-1") if position.is_long else Decimal("1")
                self.exchange.adjust_account(Money(sign * notional * event.rate, instrument.quote_currency))
                account_total = self.exchange.get_account().balance_total(USDT).as_decimal()
                self._journal.record_funding(
                    event.event_id,
                    str(event.instrument_id),
                    event.ts_event,
                    event.rate,
                    mark,
                    account_total,
                )
            self._applied.add(event.event_id)

    def pre_process(self, data) -> None:
        pass

    def log_diagnostics(self, logger) -> None:
        logger.info(f"Perpetual funding events applied: {len(self._applied)}")

    def reset(self) -> None:
        self._applied.clear()


class TierMarginPolicy:
    """Explicit-mark, captured-profile margin policy for native account updates."""

    _symbols = {BTC_PERP.id: "BTCUSDT", SOL_PERP.id: "SOLUSDT"}

    def __init__(
        self,
        marks: tuple["MarkPriceUpdate", ...],
        selected_leverage: dict[InstrumentId, Decimal],
        max_mark_age_ns: int,
    ) -> None:
        if max_mark_age_ns < 0:
            raise ValueError("max mark age must be non-negative")
        self._marks = marks
        self._selected_leverage = selected_leverage
        self._max_mark_age_ns = max_mark_age_ns
        self._profile = BybitVenueProfile.from_raw(Path(__file__).resolve().parents[2])

    def margin_for(self, instrument_id: InstrumentId, quantity: Decimal, ts_now: int) -> tuple[Decimal, Decimal, Decimal]:
        symbol = self._symbols.get(instrument_id)
        leverage = self._selected_leverage.get(instrument_id)
        if symbol is None or leverage is None or leverage <= 0:
            raise ValueError("missing explicit selected leverage")
        applicable = [item for item in self._marks if item.instrument_id == instrument_id and item.ts_event <= ts_now]
        if not applicable:
            raise ValueError("missing explicit mark")
        mark_event = applicable[-1]
        if ts_now - mark_event.ts_event > self._max_mark_age_ns:
            raise ValueError("stale explicit mark")
        notional = abs(quantity) * mark_event.price
        tier = self._profile.tier_for(symbol, notional)
        initial_rate = max(tier.im, Decimal("1") / leverage)
        return notional * initial_rate, max(Decimal("0"), notional * tier.mm - tier.deduction), mark_event.price


class BybitTierMarginModule(SimulationModule):
    """Reprices validated captured BTC/SOL tiers directly on the native MarginAccount."""

    observed: list[tuple[int, Decimal, Decimal, Decimal]] = []

    def __init__(
        self,
        marks: tuple["MarkPriceUpdate", ...],
        selected_leverage: tuple[tuple[InstrumentId, Decimal], ...],
        max_mark_age_ns: int,
    ) -> None:
        super().__init__(SimulationModuleConfig())
        self._policy = TierMarginPolicy(marks, dict(selected_leverage), max_mark_age_ns)
        self.observed = []

    def process(self, ts_now: int) -> None:
        account = self.exchange.get_account()
        open_ids = {position.instrument_id for position in self.exchange.cache.positions_open()}
        for instrument_id in (BTC_PERP.id, SOL_PERP.id):
            if instrument_id not in open_ids:
                account.clear_margin_init(instrument_id)
                account.clear_margin_maint(instrument_id)
        for position in self.exchange.cache.positions_open():
            try:
                initial, maintenance, mark = self._policy.margin_for(
                    position.instrument_id,
                    position.quantity.as_decimal(),
                    ts_now,
                )
            except ValueError:
                # Never leave a stale/default requirement visible as current margin.
                account.clear_margin_init(position.instrument_id)
                account.clear_margin_maint(position.instrument_id)
                continue
            account.update_margin_init(position.instrument_id, Money(initial, USDT))
            account.update_margin_maint(position.instrument_id, Money(maintenance, USDT))
            self.observed.append((ts_now, mark, initial, maintenance))

    def pre_process(self, data) -> None:
        pass

    def log_diagnostics(self, logger) -> None:
        logger.info("Bybit tier margin module active")

    def reset(self) -> None:
        pass


@dataclass(frozen=True)
class MarkPriceUpdate:
    instrument_id: InstrumentId
    price: Decimal
    ts_event: int


def quote(instrument_id: InstrumentId, bid: str, ask: str, ts: int) -> QuoteTick:
    size = "1000.0" if instrument_id == SOL_PERP.id else "1000.000"
    return QuoteTick(
        instrument_id, Price.from_str(bid), Price.from_str(ask),
        Quantity.from_str(size), Quantity.from_str(size), ts, ts,
    )


def build_engine(
    funding_events: tuple[FundingInstruction, ...] = (),
    funding_journal: NativeEventJournal | None = None,
    margin_probe: bool = False,
    tier_probe: bool = False,
    marks: tuple[MarkPriceUpdate, ...] = (),
    tier_selected_leverage: tuple[tuple[InstrumentId, Decimal], ...] = (),
    max_mark_age_ns: int = 0,
    tier_actions: tuple[tuple[InstrumentId, OrderSide, str], ...] = (),
) -> BacktestEngine:
    if funding_events and (funding_journal is None or not funding_journal.durable):
        raise ValueError("funding requires a durable event journal")
    if tier_probe and not tier_selected_leverage:
        raise ValueError("tier margin requires explicit selected leverage")
    tier_module = (
        BybitTierMarginModule(marks, tier_selected_leverage, max_mark_age_ns)
        if tier_probe else None
    )
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(
        venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
        starting_balances=[Money(10_000, USDT)], base_currency=USDT,
        default_leverage=Decimal("1"),
        modules=([PerpetualFundingModule(funding_events, funding_journal)] if funding_events else []) + ([tier_module] if tier_module else []),
    )
    engine.add_instrument(BTC_PERP)
    engine.add_instrument(SOL_PERP)
    engine.add_strategy(FixtureStrategy(FixtureConfig(
        btc_id=BTC_PERP.id,
        sol_id=SOL_PERP.id,
        margin_probe=margin_probe,
        tier_probe=tier_probe,
        tier_actions=tier_actions,
        tier_marks=marks,
        tier_selected_leverage=tier_selected_leverage,
        max_mark_age_ns=max_mark_age_ns,
    )))
    return engine
