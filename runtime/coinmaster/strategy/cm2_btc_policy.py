"""BTC market policy. Native positions, fills and account remain economic authority."""
from dataclasses import dataclass, field, asdict
from decimal import Decimal as D, ROUND_FLOOR
from math import isfinite
from uuid import uuid4

VERSION = "cm2-btc-market-v1"
DAY = 86_400_000_000_000
HOUR = DAY // 24
ZERO = D(0)
TP_DISTANCES = (D(".0125"), D(".025"), D(".0375"))
TP_WEIGHTS = (D(".30"), D(".40"), D(".30"))
DISCOUNT = D(".005")
MULTIPLIER = D("7.875")


def positive(x):
    return isinstance(x, D) and x.is_finite() and x > 0


@dataclass(frozen=True)
class BtcConfig:
    version: str = VERSION
    emergency_drawdown_fraction: D | None = None

    def __post_init__(self):
        if type(self.version) is not str or self.version != VERSION:
            raise ValueError("EXACT_BTC_MARKET_MODEL_REQUIRED")
        if self.emergency_drawdown_fraction is not None and not (
                isinstance(self.emergency_drawdown_fraction, D)
                and self.emergency_drawdown_fraction.is_finite()
                and 0 < self.emergency_drawdown_fraction < 1):
            raise ValueError("EMERGENCY_CONFIGURATION_UNKNOWN")


@dataclass(frozen=True)
class BtcDay:
    open_ns: int
    close_ns: int
    available_ns: int
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class BtcSignal:
    index: int
    close_ns: int
    side: int
    ema: float
    atr: float | None


def partition_lots(lots):
    if type(lots) is not int or lots < 0:
        raise ValueError("ACTUAL_ENTRY_LOTS_REQUIRED")
    first = int(D(lots) * TP_WEIGHTS[0])
    second = int(D(lots) * TP_WEIGHTS[1])
    return (first, second, lots-first-second)


def equal_split_quantity(equity, executable, step):
    if not all(positive(x) for x in (equity, executable, step)):
        raise ValueError("NATIVE_SIZING_UNKNOWN")
    lots = int((equity * MULTIPLIER / executable / step).to_integral_value(rounding=ROUND_FLOOR))
    lots -= lots % 2
    return D(lots) * step


def breakeven_price(*, side, native_average, native_quantity, remaining_cost, exit_fee_rate):
    # A price threshold only: expected commission is never posted to native cash.
    if (side not in (-1, 1) or not positive(native_average) or not positive(native_quantity)
            or not isinstance(remaining_cost, D) or not remaining_cost.is_finite()
            or not isinstance(exit_fee_rate, D) or not exit_fee_rate.is_finite()
            or not 0 <= exit_fee_rate < 1):
        raise ValueError("NATIVE_REMAINING_COST_UNKNOWN")
    cost = remaining_cost
    value = ((native_average + cost/native_quantity)/(1-exit_fee_rate) if side == 1
        else (native_average - cost/native_quantity)/(1+exit_fee_rate))
    if not positive(value):
        raise ValueError("BREAKEVEN_PRICE_UNAVAILABLE")
    return value


@dataclass
class BtcCycle:
    id: str
    side: int
    decision_index: int
    created_ns: int
    quantity: D
    first_quantity: D
    entry_filled: D = ZERO
    entry_value: D = ZERO
    first_filled: D = ZERO
    first_value: D = ZERO
    first_terminal: bool = False
    growth_stopped: bool = False
    close_reason: str | None = None
    tp_filled_lots: dict = field(default_factory=dict)
    be_armed: bool = False
    remaining_cost: D = ZERO
    funding_total: D | None = None
    seen_trade_ids: set = field(default_factory=set)

    @property
    def first_vwap(self):
        return self.first_value/self.first_filled if self.first_filled else None


class BtcPolicy:
    def __init__(self, config, *, step, start_ns, end_ns):
        if not isinstance(config, BtcConfig) or not positive(step) or not 0 < start_ns < end_ns:
            raise ValueError("BTC_MARKET_POLICY_BINDING")
        self.config, self.step, self.start_ns, self.end_ns = config, step, start_ns, end_ns
        self.days, self.signals = [], []
        self.ema = self.atr = None
        self._trs = []
        self.parent = None
        self._wait_regime = False
        self._regime_latch_ns = 0
        self._h4_release_daily_ns = None
        self._last_h4_ns = 0
        self._h4_facts = []
        self._last_attempt = None
        self.hold_reason = None

    def accept_day(self, day, *, receipt_ns):
        if (not isinstance(day, BtcDay) or day.close_ns-day.open_ns != DAY
                or day.close_ns % DAY or not day.close_ns <= day.available_ns <= receipt_ns
                or any(not isfinite(x) or x <= 0 for x in (day.open, day.high, day.low, day.close))
                or day.low > min(day.open, day.close) or day.high < max(day.open, day.close)
                or self.days and day.close_ns != self.days[-1].close_ns+DAY):
            raise ValueError("GENUINE_CONSECUTIVE_CLOSED_BTC_D1_REQUIRED")
        # Same expression/order as the existing EMA34 and Wilder14 seed path.
        alpha = 2 / (34 + 1)
        self.ema = day.close if self.ema is None else alpha*day.close+(1-alpha)*self.ema
        if self.days:
            previous = self.days[-1].close
            tr = max(day.high-day.low, abs(day.high-previous), abs(day.low-previous))
            if self.atr is None:
                self._trs.append(tr)
                if len(self._trs) == 14:
                    self.atr = sum(self._trs)/14
            else:
                self.atr = (13*self.atr+tr)/14
        self.days.append(day)
        signal = BtcSignal(len(self.signals), day.close_ns, 1 if day.close > self.ema else -1,
                           self.ema, self.atr)
        self.signals.append(signal)
        self._h4_release_daily_ns = None
        return signal

    def complete_seed(self):
        if not self.days or self.days[-1].close_ns != (self.start_ns//DAY)*DAY:
            raise ValueError("LATEST_CLOSED_BTC_SEED_REQUIRED")
        # Seeding history is not a new live D1 signal.
        self._last_attempt = self.days[-1].close_ns

    def current(self, now):
        if (not self.days or self.days[-1].close_ns != (now//DAY)*DAY
                or self.days[-1].available_ns > now):
            raise ValueError("CURRENT_CLOSED_BTC_D1_UNKNOWN")
        return self.signals[-1]

    def reentry_allowed(self):
        if not self._wait_regime:
            return True
        if self.atr is None or not isfinite(self.atr) or self.atr <= 0:
            return False
        f = self.signals[-1]
        return (f.side*(self.days[-1].close-self.ema) >= .5*self.atr
            or self._h4_release_daily_ns == self.days[-1].close_ns)

    def accept_h4(self, *, open_ns, close_ns, available_ns, receipt_ns, close):
        if (close_ns-open_ns != 4*HOUR or close_ns%(4*HOUR)
                or not close_ns <= available_ns <= receipt_ns or not positive(close)):
            raise ValueError("CAUSAL_CLOSED_BTC_H4_REQUIRED")
        if close_ns <= self._last_h4_ns:
            return
        self._last_h4_ns = close_ns
        self._h4_facts.append((close_ns, available_ns, close))

    def consume_h4(self, now):
        ready = [x for x in self._h4_facts if x[1] <= now]
        self._h4_facts = [x for x in self._h4_facts if x[1] > now]
        released = False
        for close_ns, _, close in ready:
            if (self._wait_regime and self.parent is None and close_ns > self._regime_latch_ns
                    and self.atr is not None and self.atr > 0
                    and self.signals[-1].side*(float(close)-self.ema)/self.atr >= .5):
                self._h4_release_daily_ns = self.days[-1].close_ns
                released = True
        return released

    def entry_signal(self, now):
        f = self.current(now)
        return (self.parent is None and self.start_ns <= now < self.end_ns
            and self._last_attempt != f.close_ns and self.reentry_allowed())

    def regime_close(self, now):
        f = self.current(now)
        if self.parent is not None and self.parent.side != f.side:
            self.parent.close_reason = "REGIME"
            self.stop_growth("REGIME")
            return True
        return False

    def open_cycle(self, *, side, equity, executable, now, funding_total):
        f = self.current(now)
        if (self.parent is not None or side != f.side or not self.reentry_allowed()
                or not isinstance(funding_total, D) or not funding_total.is_finite()):
            raise ValueError("BTC_ENTRY_PERMISSION_UNKNOWN")
        quantity = equal_split_quantity(equity, executable, self.step)
        if quantity <= 0:
            raise ValueError("BTC_EQUAL_SPLIT_LOT_UNAVAILABLE")
        p = BtcCycle(str(uuid4()), side, f.index, now, quantity, quantity/2,
                     funding_total=funding_total)
        self.parent = p
        self._last_attempt = f.close_ns
        self._wait_regime = False
        return p

    def observe_funding(self, actual_total):
        p = self.parent
        if (p is None or not isinstance(actual_total, D) or not actual_total.is_finite()
                or p.funding_total is None):
            raise ValueError("ACTUAL_NATIVE_FUNDING_UNKNOWN")
        # Sum actual native cash postings only; no return/PnL reconstruction.
        p.remaining_cost -= actual_total-p.funding_total
        p.funding_total = actual_total

    def entry_fill(self, *, trade_id, quantity, price, commission, first_leg):
        p = self.parent
        if p is None or not all(positive(x) for x in (quantity, price)) or quantity % self.step:
            raise ValueError("ACTUAL_ENTRY_FILL_UNKNOWN")
        if trade_id in p.seen_trade_ids:
            return False
        if not isinstance(commission, D) or not commission.is_finite():
            raise ValueError("ACTUAL_ENTRY_COMMISSION_UNKNOWN")
        p.seen_trade_ids.add(trade_id)
        p.entry_filled += quantity
        p.entry_value += quantity*price
        p.remaining_cost += commission
        if first_leg:
            p.first_filled += quantity
            p.first_value += quantity*price
        return True

    def reduction_fill(self, *, trade_id, quantity, before_quantity, level=None):
        p = self.parent
        if (p is None or not positive(quantity) or quantity % self.step
                or not positive(before_quantity) or quantity > before_quantity):
            raise ValueError("ACTUAL_REDUCTION_FILL_UNKNOWN")
        if trade_id in p.seen_trade_ids:
            return False
        p.seen_trade_ids.add(trade_id)
        p.remaining_cost *= (before_quantity-quantity)/before_quantity
        if level is not None:
            if level not in (0, 1, 2):
                raise ValueError("OWNED_FIXED_TP_LEVEL_UNKNOWN")
            p.tp_filled_lots[level] = p.tp_filled_lots.get(level, 0)+int(quantity/self.step)
            if level == 0:
                p.be_armed = True
                p.growth_stopped = True
        return True

    def confirm_flat(self, *, now, native_flat, owners_terminal):
        p = self.parent
        if p is None or not native_flat or not owners_terminal:
            raise ValueError("BTC_NATIVE_FLAT_AND_OWNERS_TERMINAL_REQUIRED")
        if p.close_reason == "REGIME":
            self._wait_regime, self._regime_latch_ns = True, now
            self._h4_release_daily_ns = None
        if p.close_reason != "REGIME":
            self._last_attempt = self.days[-1].close_ns
        self.parent = None
        self.hold_reason = None

    def target_lots(self):
        p = self.parent
        if p is None:
            return (0, 0, 0)
        target = list(partition_lots(int(p.entry_filled/self.step)))
        return tuple(max(0, lots-p.tp_filled_lots.get(i, 0)) for i, lots in enumerate(target))

    def target_price(self, level, native_average):
        p = self.parent
        if p is None or level not in (0, 1, 2) or not positive(native_average):
            raise ValueError("NATIVE_TP_BASIS_UNKNOWN")
        return native_average*(1+D(p.side)*TP_DISTANCES[level])

    def stop_growth(self, reason):
        if self.parent is not None:
            self.parent.growth_stopped = True
            self.hold_reason = reason

    def snapshot(self):
        p = asdict(self.parent) if self.parent else None
        if p is not None:
            p['seen_trade_ids'] = sorted(p['seen_trade_ids'])
        return dict(version=VERSION, days=[asdict(x) for x in self.days],
            signals=[asdict(x) for x in self.signals], parent=p,
            wait_regime=self._wait_regime, regime_latch_ns=self._regime_latch_ns,
            h4_release_daily_ns=self._h4_release_daily_ns, last_h4_ns=self._last_h4_ns,
            h4_facts=self._h4_facts, last_attempt=self._last_attempt, hold_reason=self.hold_reason)

    def restore(self, value):
        if value.get('version') != VERSION:
            raise ValueError("BTC_MARKET_CHECKPOINT_VERSION")
        rebuilt = BtcPolicy(self.config, step=self.step, start_ns=self.start_ns, end_ns=self.end_ns)
        for row in value['days']:
            day = BtcDay(**row)
            rebuilt.accept_day(day, receipt_ns=day.available_ns)
        if [asdict(x) for x in rebuilt.signals] != value['signals']:
            raise ValueError("BTC_FEATURE_CHECKPOINT_MISMATCH")
        p = BtcCycle(**value['parent']) if value['parent'] is not None else None
        if p:
            p.seen_trade_ids = set(p.seen_trade_ids)
            p.tp_filled_lots = {int(k):v for k,v in p.tp_filled_lots.items()}
        self.days, self.signals, self.ema, self.atr, self._trs = rebuilt.days, rebuilt.signals, rebuilt.ema, rebuilt.atr, rebuilt._trs
        self.parent = p
        self._wait_regime, self._regime_latch_ns = value['wait_regime'], value['regime_latch_ns']
        self._h4_release_daily_ns, self._last_h4_ns = value['h4_release_daily_ns'], value['last_h4_ns']
        self._h4_facts = [tuple(x) for x in value['h4_facts']]
        self._last_attempt, self.hold_reason = value['last_attempt'], value['hold_reason']
