"""Unintegrated CM2 BTC reference component: pure decisions, never native money/orders.

Reference market math is shared unchanged. SOL public prices enter beta; SOL
trading state has no interface here. Native admission, money and orders remain
the responsibility of the single CM2 native adapter. No legacy Strategy runs.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, asdict
from datetime import timezone, datetime
from decimal import Decimal as D
from math import isfinite
from typing import Literal
from uuid import uuid4

from coinmaster.domain.wave_overlay import Candidate, DailyBar, FeatureState, completed_wave_levels

VERSION = "cm2-btc-reference-pure-v1"
DAY = 86_400_000_000_000
HOUR = DAY // 24
ZERO = D(0)


def _positive(value: D) -> bool:
    return isinstance(value, D) and value.is_finite() and value > 0


def _ns(when) -> int:
    return int(when.timestamp() * 1_000_000_000)


@dataclass(frozen=True)
class ReferenceFlags:
    # Required actual launch provenance; never guessed defaults.
    c1_first_fresh_h4: bool
    c1_btc_postcut_d1: bool

    def __post_init__(self):
        if type(self.c1_first_fresh_h4) is not bool or type(self.c1_btc_postcut_d1) is not bool:
            raise ValueError("C1_FLAGS_REQUIRE_EXPLICIT_BOOLEAN_PROVENANCE")


def selected_btc_candidate() -> Candidate:
    return Candidate(ema_period=34,beta_days=270,relative_days=65,z_history_days=180,
        wave_history_days=730,wave_min_count=8,wave_quantiles=(.1,.3,.6),
        btc_tp_fractions_initial_qty=(.2125,.2125,.575),btc_notional_multiplier=7.875,
        max_parent_notional=30_000_000.,sol_size_multipliers_h=(1.75,2.625,3.5),
        sol_overlay_enabled=False)


def _exact_frozen_candidate(candidate):
    if type(candidate) is not Candidate:return False
    actual,expected=asdict(candidate),asdict(selected_btc_candidate())
    for key,value in expected.items():
        observed=actual[key]
        if type(observed) is not type(value) or observed!=value:return False
        if isinstance(value,tuple) and any(type(a) is not type(e) for a,e in zip(observed,value)):return False
    return True


@dataclass(frozen=True)
class ReferenceConfig:
    version: str
    candidate: Candidate
    flags: ReferenceFlags
    emergency_drawdown_fraction: D | None = None

    def __post_init__(self):
        if (self.version != "cm2-btc-reference-v1" or not _exact_frozen_candidate(self.candidate)
                or self.flags != ReferenceFlags(True,True)):
            raise ValueError("CM2_REFERENCE_CONFIG_OR_FLAGS_NOT_FROZEN")
        if self.emergency_drawdown_fraction is not None and not (isinstance(self.emergency_drawdown_fraction,D)
                and self.emergency_drawdown_fraction.is_finite() and 0 < self.emergency_drawdown_fraction < 1):
            raise ValueError("CM2_EMERGENCY_CONFIGURATION_UNKNOWN")


@dataclass(frozen=True)
class C1Money:
    source_ns: int
    receipt_ns: int
    revision: int
    equity: D
    peak: D
    drawdown: D
    cushion: D
    open_pnl: D
    position_id: str
    position_open_ns: int


@dataclass
class C1Cycle:
    parent_id: str
    claim_ns: int
    side: int
    held_lots: int
    cut_lots: int
    target_lots: int
    position_id: str
    position_open_ns: int
    state: str = "CUT_RESOLVING"
    cut_submitted: bool = False
    restore_submitted: bool = False
    cut_filled: int = 0
    cut_value: D = ZERO
    cut_terminal_ns: int | None = None
    last_cut_fill_ns: int | None = None
    restore_committed: int = 0
    restore_filled: int = 0
    credit: int = 0
    bucket: dict[int,int] = field(default_factory=dict)
    revoked: bool = False
    confirmation: dict | None = None
    deferred_h4: dict | None = None
    last_h4_ns: int = 0


@dataclass(frozen=True)
class C1Plan:
    kind: Literal["CANCEL", "CUT", "RESTORE"]
    quantity: D
    side: int


@dataclass(frozen=True)
class BtcDecision:
    action: Literal["HOLD", "BTC_ENTRY", "BTC_CLOSE"]
    reason: str
    parent_id: str | None = None
    requested_notional: float | None = None


@dataclass(frozen=True)
class EntryPlan:
    action: Literal["HOLD", "CANCEL", "CANCEL_RESTING_LIMIT", "IOC", "DISCOUNT_GTC"]
    quantity: D = ZERO
    # Declarative raw reference only. Existing native adapter must normalize it.
    raw_limit_price: D | None = None


@dataclass(frozen=True)
class TargetPlan:
    level: int
    quantity: D
    raw_limit_price: D
    positive_ioc_candidate: bool
    parent_id: str
    conditional_ioc: bool = False
    decision_index: int = -1
    ready_ns: int = 0


@dataclass
class BtcParent:
    id: str
    side: int
    decision_index: int
    beta: float
    levels: tuple[float, float, float]
    requested_notional: float
    best_f: float = 0.0
    close_reason: str | None = None
    q0_ns: int | None = None
    q0_session_ns: int | None = None
    q1_ns: int | None = None
    q0_wire_price: D | None = None
    passive_selection: bool | None = None
    gross_lots: int = 0
    reference_targets: tuple[int, ...] = ()
    omitted_levels: frozenset[int] = frozenset()
    suppressed_zero_levels: frozenset[int] = frozenset()
    selected_quantity: D | None = None
    split_start_ns: int | None = None
    split_deadline_ns: int | None = None
    first_quantity: D = ZERO
    filled_quantity: D = ZERO
    entry_notional: D = ZERO
    # Keep the original float accumulation for management fallback parity.
    entry_vwap: float | None = None
    entry_quantity_float: float = 0.0
    first_filled: D = ZERO
    first_notional: D = ZERO
    planref: D | None = None
    fallback: bool = False
    split_terminal: bool = False
    stop_reason: str | None = None
    target_lots: tuple[int, ...] = ()
    tp_filled_lots: dict[int, int] = field(default_factory=dict)
    ordinary_attempted_index: dict[int, int] = field(default_factory=dict)
    risk_retired_lots: dict[int,int] = field(default_factory=dict)
    cut_filled_lots: int = 0
    restore_filled_lots: int = 0


class ReferenceBtcPolicy:
    """One BTC economic state; the existing CM2 adapter remains sole order owner."""
    def __init__(self, candidate: Candidate, *, flags: ReferenceFlags, btc_step: D,
                 trading_start_ns: int, terminal_ns: int, max_quote_age_ns: int,
                 initial_btc_equity: D | None = None):
        if not isinstance(candidate,Candidate):
            raise ValueError("EXPLICIT_REFERENCE_CANDIDATE_REQUIRED")
        if (any(type(getattr(candidate,k)) is not int or getattr(candidate,k) <= 0
                for k in ("ema_period","beta_days","relative_days","z_history_days","wave_history_days","wave_min_count"))
                or len(candidate.wave_quantiles) != 3 or any(not isfinite(x) or not 0 <= x <= 1 for x in candidate.wave_quantiles)
                or len(candidate.btc_tp_fractions_initial_qty) != 3
                or any(not isfinite(x) or x < 0 for x in candidate.btc_tp_fractions_initial_qty)
                or not 0 < sum(candidate.btc_tp_fractions_initial_qty) <= 1
                or not isfinite(candidate.max_parent_notional) or candidate.max_parent_notional <= 0
                or not isfinite(candidate.btc_close_trail_fraction) or candidate.btc_close_trail_fraction <= 0):
            raise ValueError("REFERENCE_BTC_PARAMETERS_INVALID")
        if not isinstance(flags, ReferenceFlags):
            raise ValueError("EXPLICIT_REFERENCE_FLAGS_REQUIRED")
        if (not _positive(btc_step) or any(type(x) is not int for x in (trading_start_ns,terminal_ns,max_quote_age_ns))
                or not 0 < trading_start_ns < terminal_ns or max_quote_age_ns <= 0):
            raise ValueError("REFERENCE_CLOCK_OR_LOT_INVALID")
        self.candidate, self.flags, self.btc_step = candidate, flags, btc_step
        self.trading_start_ns, self.terminal_ns = trading_start_ns, terminal_ns
        self.max_quote_age_ns = max_quote_age_ns
        self._features = FeatureState(candidate)
        self._signals = []
        self._parent: BtcParent | None = None
        self._last_entry_attempt: tuple[int, int] | None = None
        self._fills: dict[str, tuple] = {}
        if initial_btc_equity is not None and not _positive(initial_btc_equity):
            raise ValueError("GENUINE_INITIAL_BTC_CAPITAL_REQUIRED")
        self.initial_btc_equity = initial_btc_equity
        self._c1_peak = initial_btc_equity
        self._c1_money: C1Money | None = None
        self.c1: C1Cycle | None = None
        self.c1_audit: list[dict] = []
        self._btc_revision = 0
        self._funding_version = None
        self._ohlc: dict[int,tuple[float,float]] = {}
        self._wait_regime = False
        self._regime_latch_ns = 0
        self._h4_release_daily_ns: int | None = None
        self._trail_block_index = -1
        self._last_h4_ns = 0

    @property
    def parent(self) -> BtcParent | None:
        return deepcopy(self._parent)

    @property
    def signals(self):
        return tuple(self._signals)

    def accept_closed_day(self, row: DailyBar, *, receipt_ns: int,
                          btc_high: float | None = None, btc_low: float | None = None):
        # DailyBar already validates paired values/UTC/availability. Add strict
        # calendar continuity, finite values and receipt cutoff before mutation.
        start, close, available = _ns(row.open_time), _ns(row.close_time), _ns(row.available_at)
        if (row.open_time.tzinfo != timezone.utc or start % DAY or close-start != DAY
                or not close <= available <= receipt_ns
                or not all(isfinite(v) and v > 0 for v in (row.btc_open,row.btc_close,row.sol_close))):
            raise ValueError("DAILY_CAUSAL_PAIR_INVALID")
        if self._features.bars and _ns(self._features.bars[-1].close_time) != start:
            raise ValueError("DAILY_NONCONTIGUOUS_OR_DUPLICATE")
        if (btc_high is None) != (btc_low is None):
            raise ValueError("DAILY_OHLC_PAIR_REQUIRED")
        if btc_high is not None and (not all(isfinite(x) for x in (btc_high,btc_low))
                or not 0 < btc_low <= min(row.btc_open,row.btc_close)
                or btc_high < max(row.btc_open,row.btc_close)):
            raise ValueError("DAILY_OHLC_INVALID")
        feature = self._features.append(row)
        if btc_high is not None:self._ohlc[close]=(btc_high,btc_low)
        self._signals.append(feature)
        return feature

    def _current(self, now_ns):
        if not self._signals:
            raise ValueError("DAILY_STATE_EMPTY")
        row = self._features.bars[-1]
        if type(now_ns) is not int or not _ns(row.available_at) <= now_ns < self.terminal_ns:
            raise ValueError("DAILY_NOT_YET_AVAILABLE_OR_TERMINAL")
        return row, self._signals[-1]

    def decide_on_day(self, *, native_btc_marked_equity: D, decision_ns: int) -> BtcDecision:
        row, f = self._current(decision_ns)
        p = self._parent
        if p is not None:
            if p.entry_vwap is None and not p.close_reason:
                return BtcDecision("HOLD","PENDING_NATIVE_ENTRY_OUTCOME",p.id)
            if p.close_reason:
                return BtcDecision("BTC_CLOSE",p.close_reason,p.id)
            if f.side != p.side:
                p.close_reason = "REGIME"
            elif p.entry_vwap is not None:
                ref = float(p.planref) if p.planref is not None else p.entry_vwap
                favorable = p.side*(row.btc_close/ref-1)
                p.best_f = max(p.best_f,favorable,0.0)
                if p.best_f > self.candidate.btc_close_trail_fraction and favorable <= p.best_f-self.candidate.btc_close_trail_fraction:
                    p.close_reason = "TRAIL"
            if p.close_reason:
                return BtcDecision("BTC_CLOSE",p.close_reason,p.id)
            return BtcDecision("HOLD","BTC_PARENT_RETAINED",p.id)
        if _ns(row.open_time) < self.trading_start_ns:
            return BtcDecision("HOLD","FEATURE_ONLY_WARMUP")
        if _ns(self._features.bars[0].open_time) > self.trading_start_ns-730*DAY:
            return BtcDecision("HOLD","GENUINE_730_DAY_FEATURE_SEED_REQUIRED")
        if f.index <= self._trail_block_index:
            return BtcDecision("HOLD","TRAIL_WAIT_NEXT_D1")
        if self._wait_regime and not self.reentry_allowed():
            return BtcDecision("HOLD","WAIT_REGIME_REENTRY")
        if self._last_entry_attempt == (f.index,f.side):
            return BtcDecision("HOLD","ENTRY_ATTEMPTED_THIS_SESSION")
        if f.beta is None or not 0.2 < f.beta < 4:
            return BtcDecision("HOLD","BETA_INVALID")
        levels = completed_wave_levels(self._features.bars,self._signals,f.index,self.candidate,f.side)
        if levels is None:
            return BtcDecision("HOLD","WAVES_UNAVAILABLE")
        if not _positive(native_btc_marked_equity):
            return BtcDecision("HOLD","BTC_NATIVE_CAPITAL_UNKNOWN")
        amount = min((5.5 if f.side == 1 else 7.875)*float(native_btc_marked_equity),self.candidate.max_parent_notional)
        if not isfinite(amount) or amount <= 0:
            return BtcDecision("HOLD","BTC_NATIVE_CAPITAL_INVALID")
        p = BtcParent(str(uuid4()),f.side,f.index,f.beta,levels,amount)
        self._parent, self._last_entry_attempt = p,(f.index,f.side)
        self._wait_regime=False;self._h4_release_daily_ns=None
        return BtcDecision("BTC_ENTRY","REFERENCE_DAILY_ENTRY",p.id,amount)

    def _owned(self, parent_id):
        p = self._parent
        if p is None or p.id != parent_id:
            raise ValueError("BTC_PARENT_IDENTITY_UNKNOWN")
        return p

    def _partition(self, lots):
        assigned, result = 0, []
        fractions = tuple(D(str(x)) for x in self.candidate.btc_tp_fractions_initial_qty)
        for i, fraction in enumerate(fractions):
            q = lots-assigned if i == len(fractions)-1 and sum(fractions) == 1 else int(D(lots)*fraction)
            result.append(q); assigned += q
        return tuple(result)

    def observe_entry_q0(self, parent_id: str, *, quote_ns: int, executable_price: D,
                         canonical_wire_price: D):
        p = self._owned(parent_id)
        row,_ = self._current(quote_ns)
        if (p.q0_ns is not None or p.close_reason or not _positive(executable_price)
                or not _positive(canonical_wire_price)):
            raise ValueError("ENTRY_Q0_INVALID_OR_REPEATED")
        # Preserve the actual reference float -> str -> Decimal lot path.
        gross = float(D(str(p.requested_notional))/executable_price)
        lots = int(D(str(gross))//self.btc_step)
        if lots <= 0:
            raise ValueError("ENTRY_BELOW_LOT")
        p.q0_ns, p.q0_session_ns = quote_ns,_ns(row.close_time)
        p.q0_wire_price, p.gross_lots = canonical_wire_price,lots
        p.reference_targets = self._partition(lots)

    def select_entry_q1(self, parent_id: str, *, quote_ns: int, bid: D, ask: D) -> D:
        p = self._owned(parent_id)
        row,_ = self._current(quote_ns)
        if (p.q0_ns is None or p.selected_quantity is not None or p.close_reason
                or not p.q0_ns < quote_ns <= p.q0_ns+self.max_quote_age_ns
                or _ns(row.close_time) != p.q0_session_ns
                or not (_positive(bid) and _positive(ask) and bid <= ask)):
            raise ValueError("ENTRY_Q1_STALE_OR_INVALID")
        passive = p.q0_wire_price > bid if p.side == 1 else p.q0_wire_price < ask
        p.passive_selection = passive
        zeros = frozenset(i for i,x in enumerate(p.levels) if D(str(x)) == 0)
        p.omitted_levels = zeros if passive else frozenset()
        p.suppressed_zero_levels = frozenset() if passive else zeros
        selected = sum(q for i,q in enumerate(p.reference_targets) if i not in p.omitted_levels)
        # Parent cap applies again at q1 executable price, before any split.
        executable = ask if p.side == 1 else bid
        p.q1_ns = quote_ns
        p.selected_quantity = min(D(selected)*self.btc_step,
            (D(str(self.candidate.max_parent_notional))/executable//self.btc_step)*self.btc_step)
        return p.selected_quantity

    def begin_split(self, parent_id: str, *, now_ns: int):
        p = self._owned(parent_id)
        self._current(now_ns)
        if p.split_start_ns is not None or p.q1_ns is None or now_ns != p.q1_ns or not _positive(p.selected_quantity):
            raise ValueError("SPLIT_START_INVALID")
        lots = int(p.selected_quantity/self.btc_step)
        p.first_quantity = D(max(1,lots//2))*self.btc_step
        p.split_start_ns = now_ns
        p.split_deadline_ns = min(now_ns+4*HOUR,((now_ns//DAY)+1)*DAY-60_000_000_000)

    def entry_plan(self, parent_id: str, *, now_ns: int, bid: D, ask: D,
                   pending_kind: Literal["NONE", "IOC", "DISCOUNT_GTC", "UNKNOWN"]) -> EntryPlan:
        p = self._owned(parent_id)
        if pending_kind not in ("NONE","IOC","DISCOUNT_GTC","UNKNOWN") or p.split_start_ns is None or not (_positive(bid) and _positive(ask) and bid <= ask):
            raise ValueError("SPLIT_OR_QUOTE_UNKNOWN")
        if pending_kind == "UNKNOWN":
            return EntryPlan("HOLD")
        native_pending = pending_kind != "NONE"
        if now_ns < p.split_start_ns:
            raise ValueError("SPLIT_QUOTE_FROM_PAST")
        if now_ns >= min(((p.split_start_ns//DAY)+1)*DAY,self.terminal_ns):
            p.stop_reason = p.stop_reason or "UTC_OR_TERMINAL_BOUNDARY"
            p.split_terminal = True
        if p.stop_reason or p.close_reason:
            return EntryPlan("CANCEL" if native_pending else "HOLD")
        if p.split_terminal:
            return EntryPlan("HOLD")
        reference = float(p.planref) if p.planref is not None else p.entry_vwap
        px = bid if p.side == 1 else ask
        early = reference is not None and any(x > 0 and
            (px >= D(str(reference))*(1+D(str(x))) if p.side == 1 else
             px <= D(str(reference))*(1-D(str(x)))) for x in p.levels)
        p.fallback = p.fallback or now_ns >= p.split_deadline_ns or early
        if native_pending:
            return EntryPlan("CANCEL_RESTING_LIMIT" if p.fallback and pending_kind == "DISCOUNT_GTC" else "HOLD")
        remaining = p.selected_quantity-p.filled_quantity
        first_remaining = p.first_quantity-p.filled_quantity
        if first_remaining > 0:
            return EntryPlan("IOC",min(remaining,first_remaining))
        if p.fallback:
            return EntryPlan("IOC",remaining)
        first_vwap = p.first_notional/p.first_filled
        return EntryPlan("DISCOUNT_GTC",remaining,
                         first_vwap*(1-D(".0025")*p.side))

    def stop_entry_remainder(self, parent_id: str, *, reason: str):
        p = self._owned(parent_id)
        if not reason:
            raise ValueError("STOP_REASON_REQUIRED")
        p.stop_reason, p.split_terminal = reason,True
        # This revokes unsubmitted permission. Native pending ownership survives
        # in CM2; a subsequent real late fill must still be applied here.

    def apply_fill(self, parent_id: str, *, trade_id: str, kind: Literal["ENTRY", "TP", "CUT", "RESTORE"],
                   quantity: D, price: D, event_ns: int, level: int | None = None) -> bool:
        p = self._owned(parent_id)
        signature = (parent_id,kind,quantity,price,event_ns,level)
        if trade_id in self._fills:
            if self._fills[trade_id] != signature:
                raise ValueError("CONFLICTING_DUPLICATE_FILL")
            return False
        if (not trade_id or not _positive(quantity) or not _positive(price)
                or quantity % self.btc_step or p.split_start_ns is None or event_ns < p.split_start_ns):
            raise ValueError("ACTUAL_FILL_INVALID")
        if kind == "ENTRY":
            if level is not None or p.filled_quantity+quantity > p.selected_quantity:
                raise ValueError("ENTRY_PARENT_OVERFILL_OR_LEVEL")
            before = p.filled_quantity
            first = min(quantity,max(ZERO,p.first_quantity-before))
            prior_float, q = p.entry_quantity_float,float(quantity)
            p.entry_vwap = ((p.entry_vwap or 0)*prior_float+float(price)*q)/(prior_float+q)
            p.entry_quantity_float += q
            p.filled_quantity += quantity; p.entry_notional += quantity*price
            p.first_filled += first; p.first_notional += first*price
            if p.first_filled == p.first_quantity and p.planref is None:
                p.planref = p.first_notional/p.first_filled
            if p.filled_quantity == p.selected_quantity:
                p.split_terminal = True
        elif kind == "TP":
            targets = self._target_lots(p)
            lots = int(quantity/self.btc_step)
            if (type(level) is not int or not 0 <= level < len(targets)
                    or lots > targets[level]-p.tp_filled_lots.get(level,0)-p.risk_retired_lots.get(level,0)
                    or quantity > self._held(p)):
                raise ValueError("TP_UNEARNED_OR_OVERFILL")
            p.tp_filled_lots[level] = p.tp_filled_lots.get(level,0)+lots
        elif kind in ("CUT","RESTORE"):
            self._apply_c1_fill(p,kind,quantity,price,event_ns)
        else:
            raise ValueError("UNKNOWN_FILL_KIND")
        if kind in ("ENTRY","TP") and self.c1 is not None:
            self.revoke_c1(event_ns,"ACTUAL_ORDINARY_BTC_FILL")
        self._btc_revision += 1
        self._fills[trade_id] = signature
        return True

    def _held(self, p):
        return p.filled_quantity-D(sum(p.tp_filled_lots.values())+p.cut_filled_lots-p.restore_filled_lots)*self.btc_step

    def _target_lots(self, p):
        if not p.split_terminal or p.filled_quantity <= 0:
            raise ValueError("TP_REQUIRES_CONFIRMED_ENTRY_AND_TERMINAL_SPLIT")
        if not p.target_lots:
            basis = int(p.selected_quantity/self.btc_step)
            retained = [i for i in range(3) if i not in p.omitted_levels]
            weights = sum(p.reference_targets[i] for i in retained) if p.passive_selection else 0
            if not weights:
                p.target_lots = self._partition(basis)
            else:
                assigned, targets = 0, []
                for i in range(3):
                    q = 0 if i in p.omitted_levels else basis-assigned if i == retained[-1] else int(D(basis)*p.reference_targets[i]/weights)
                    targets.append(q); assigned += q
                p.target_lots = tuple(targets)
        return p.target_lots

    def confirmed_targets(self, parent_id: str) -> tuple[TargetPlan, ...]:
        p = self._owned(parent_id)
        if p.close_reason:
            return ()
        targets = self._target_lots(p)
        ref = float(p.planref) if p.planref is not None else p.entry_vwap
        held_lots = int(self._held(p)/self.btc_step)
        plans = []
        for level,target in enumerate(targets):
            leaves = min(held_lots,target-p.tp_filled_lots.get(level,0)-p.risk_retired_lots.get(level,0))
            if leaves <= 0 or level in p.suppressed_zero_levels:
                continue
            raw = ref*(1+p.side*p.levels[level])
            plans.append(TargetPlan(level,D(leaves)*self.btc_step,D(str(raw)),
                p.levels[level] > 0 and p.filled_quantity == p.selected_quantity and not p.stop_reason,p.id,decision_index=self._signals[-1].index))
        return tuple(plans)

    def confirm_empty_entry_terminal(self, parent_id: str, *, native_pending: bool):
        """Adapter confirms all BTC native entry owners terminal with no fill.

        This is not a cancellation request or ACK. The later integrated adapter
        must retain ownership until this external native fact is established.
        """
        p = self._owned(parent_id)
        if type(native_pending) is not bool or p.filled_quantity != 0 or native_pending:
            raise ValueError("EMPTY_ENTRY_TERMINAL_NOT_CONFIRMED")
        self._parent = None

    @staticmethod
    def _known_levels(levels):
        if type(levels) is not frozenset or any(type(x) is not int or not 0 <= x < 3 for x in levels):
            raise ValueError("NATIVE_TP_LEVEL_OWNERSHIP_UNKNOWN")

    def ordinary_tp_permissions(self, parent_id: str, *, decision_ns: int,
                                native_resting_levels: frozenset[int],
                                native_pending_levels: frozenset[int]) -> tuple[TargetPlan, ...]:
        """One conditional taker permission per level/D1, never a fill.

        A suppressed zero RESTING target still has this ordinary reduction path.
        Native adapter retains queued permission and owns all submissions/retries.
        """
        p = self._owned(parent_id)
        row,f = self._current(decision_ns)
        self._known_levels(native_resting_levels);self._known_levels(native_pending_levels)
        if p.close_reason or f.side != p.side:
            return ()
        targets = self._target_lots(p)
        reference = float(p.planref) if p.planref is not None else p.entry_vwap
        favorable = p.side*(row.btc_close/reference-1)
        plans=[]
        for level,threshold in enumerate(p.levels):
            leaves=min(targets[level]-p.tp_filled_lots.get(level,0)-p.risk_retired_lots.get(level,0),int(self._held(p)/self.btc_step))
            if (level in p.omitted_levels or level in native_resting_levels or level in native_pending_levels
                    or leaves <= 0 or favorable < threshold
                    or p.ordinary_attempted_index.get(level) == f.index):
                continue
            p.ordinary_attempted_index[level]=f.index
            plans.append(TargetPlan(level,D(leaves)*self.btc_step,
                D(str(reference*(1+p.side*threshold))),False,p.id,True,f.index,decision_ns))
        return tuple(plans)

    def executable_tp_quantity(self, permission: TargetPlan, *, quote_ns: int,
                               bid: D, ask: D,
                               native_pending_levels: frozenset[int]) -> D:
        """Quote predicate for the original permission, not a new daily right."""
        p=self._owned(permission.parent_id)
        row,f=self._current(quote_ns)
        self._known_levels(native_pending_levels)
        if (not permission.conditional_ioc or type(permission.level) is not int
                or not 0 <= permission.level < 3 or not _positive(permission.quantity)
                or not (_positive(bid) and _positive(ask) and bid <= ask)):
            raise ValueError("CONDITIONAL_TP_PERMISSION_OR_QUOTE_INVALID")
        if (p.close_reason or f.side != p.side or quote_ns < permission.ready_ns
                or permission.decision_index > f.index
                or p.ordinary_attempted_index.get(permission.level) != permission.decision_index
                or permission.level in native_pending_levels):
            return ZERO
        # Conditional IOC uses the original Decimal reference predicate,
        # independently of the float target -> native GTC wire rounding path.
        reference = float(p.planref) if p.planref is not None else p.entry_vwap
        threshold = D(str(reference))*(1+p.side*D(str(p.levels[permission.level])))
        crossed = _positive(threshold) and (bid >= threshold if p.side == 1 else ask <= threshold)
        if not crossed:
            return ZERO
        leaves=self._target_lots(p)[permission.level]-p.tp_filled_lots.get(permission.level,0)-p.risk_retired_lots.get(permission.level,0)
        return min(permission.quantity,D(max(0,leaves))*self.btc_step,self._held(p))

    @property
    def btc_revision(self):
        return self._btc_revision

    def _atr_reentry(self):
        previous=atr=None;trs=[]
        for row in self._features.bars:
            if previous is not None:
                hl=self._ohlc.get(_ns(row.close_time))
                if hl is None:return None
                high,low=hl
                tr=max(high-low,abs(high-previous),abs(low-previous))
                if atr is None:
                    trs.append(tr)
                    if len(trs)==14:atr=sum(trs)/14
                else:atr=(13*atr+tr)/14
            previous=row.btc_close
        return atr if atr is not None and isfinite(atr) and atr > 0 else None

    def reentry_allowed(self):
        if not self._wait_regime:return True
        atr=self._atr_reentry()
        if atr is None:return False
        f=self._signals[-1];row=self._features.bars[-1]
        return (f.side*(row.btc_close-self._features.ema) >= .5*atr
                or self._h4_release_daily_ns==_ns(row.close_time))

    def confirm_btc_close(self, parent_id: str, *, receipt_ns: int,
                          native_btc_flat: bool, native_btc_owners_terminal: bool):
        p=self._owned(parent_id)
        if (type(native_btc_flat) is not bool or type(native_btc_owners_terminal) is not bool
                or not native_btc_flat or not native_btc_owners_terminal or not p.close_reason):
            raise ValueError("BTC_ECONOMIC_CLOSE_NOT_NATIVE_TERMINAL")
        self._current(receipt_ns) if receipt_ns < self.terminal_ns else None
        if p.close_reason=="REGIME":
            self._wait_regime=True;self._regime_latch_ns=receipt_ns;self._h4_release_daily_ns=None
        elif p.close_reason=="TRAIL":self._trail_block_index=self._signals[-1].index
        self._parent=None;self.c1=None

    def accept_closed_btc_h4(self, *, open_ns: int, close_ns: int, available_ns: int,
                             receipt_ns: int, close: D):
        if (close_ns-open_ns != 4*HOUR or close_ns%(4*HOUR) or
                not close_ns <= available_ns <= receipt_ns or not _positive(close)):
            raise ValueError("CAUSAL_CLOSED_H4_REQUIRED")
        if close_ns <= self._last_h4_ns:return
        self._last_h4_ns=close_ns
        if self._wait_regime and self._parent is None and close_ns > self._regime_latch_ns:
            atr=self._atr_reentry()
            if atr is not None and self._signals[-1].side*(float(close)-self._features.ema)/atr >= .5:
                self._h4_release_daily_ns=_ns(self._features.bars[-1].close_time)
        t=self.c1
        if t is None or close_ns <= t.last_h4_ns:return
        t.last_h4_ns=close_ns;t.deferred_h4=None
        if (t.state!="HELD" or not t.credit or t.last_cut_fill_ns is None
                or t.cut_terminal_ns is None or open_ns <= max(t.last_cut_fill_ns,t.cut_terminal_ns)):
            return
        reclaim=t.side*(close-t.cut_value/(D(t.cut_filled)*self.btc_step))>0
        money=self._money_at(receipt_ns)
        if reclaim and money is not None and money.drawdown <= D('.40'):
            t.confirmation=dict(open_ns=open_ns,close_ns=close_ns,close=close)
        elif reclaim and money is None and t.confirmation is None and not t.revoked and not t.restore_submitted:
            t.deferred_h4=dict(open_ns=open_ns,close_ns=close_ns,close=close,
                available_ns=available_ns,identity=self._c1_identity())
            self._c1_log("CLOSED_4H_DEFERRED_NO_MONEY",receipt_ns)

    def _c1_identity(self):
        t=self.c1
        return repr((self._btc_revision,t.parent_id,t.state,t.cut_filled,t.cut_value,t.restore_filled,
                t.credit,tuple(sorted(t.bucket.items())),t.last_cut_fill_ns,t.cut_terminal_ns,t.revoked))

    def _c1_log(self,event,now,**detail):
        self.c1_audit.append(dict(event=event,timestamp_ns=now,parent=self.c1.parent_id if self.c1 else None,**detail))

    def note_btc_funding(self,version):
        if version!=self._funding_version:
            self._funding_version=version;self._btc_revision+=1

    def observe_committed_btc(self, *, source_ns: int, receipt_ns: int, revision: int,
                              equity: D, open_pnl: D, native_qty: D,
                              position_id: str, position_open_ns: int,
                              btc_competing_owner: bool):
        if (self._c1_peak is None or not _positive(equity) or not open_pnl.is_finite()
                or not native_qty.is_finite() or not source_ns < receipt_ns
                or receipt_ns-source_ns > self.max_quote_age_ns or revision!=self._btc_revision):
            self._c1_money=None;return
        self._c1_peak=max(self._c1_peak,equity)
        m=C1Money(source_ns,receipt_ns,revision,equity,self._c1_peak,1-equity/self._c1_peak,
            max(ZERO,equity-D('.5')*self._c1_peak),open_pnl,position_id,position_open_ns)
        self._c1_money=m
        t=self.c1;p=self._parent
        if t is not None:
            if t.revoked and not t.cut_submitted and not t.restore_submitted and m.drawdown<=D('.35'):
                t.state="RELEASED"
            return
        if (p is None or p.close_reason or not p.split_terminal or p.filled_quantity<=0
                or m.drawdown < D('.40') or -open_pnl <= m.cushion or btc_competing_owner
                or native_qty*p.side<=0):return
        lots=int(abs(native_qty)/self.btc_step);cut=lots//4
        if not cut:return
        self._target_lots(p)
        self.c1=C1Cycle(p.id,receipt_ns,p.side,lots,cut,lots-cut,position_id,position_open_ns)
        self._c1_log("CLAIM",receipt_ns,held_lots=lots,cut_lots=cut,source_ns=source_ns)

    def _money_at(self,now):
        m=self._c1_money
        return m if m is not None and m.source_ns < m.receipt_ns <= now and now-m.source_ns<=self.max_quote_age_ns and m.revision==self._btc_revision else None

    def revoke_c1(self,now,reason):
        t=self.c1
        if t is None or t.state=="RELEASED" or t.revoked:return
        t.revoked=True;t.credit=0;t.state="REVOKED";t.deferred_h4=None
        self._c1_log("TOKEN_REVOKED",now,reason=reason)

    def c1_plan(self, *, now_ns: int, executable_price: D,
                native_held_quantity: D, native_btc_owners_clear: bool) -> C1Plan | None:
        t=self.c1;p=self._parent;m=self._money_at(now_ns)
        if (t is None or p is None or t.revoked or t.state=="RELEASED" or m is None
                or not _positive(executable_price)):return None
        pending=t.deferred_h4
        if pending is not None and now_ns>pending['available_ns'] and m.source_ns>=pending['close_ns']:
            t.deferred_h4=None
            reclaim=t.side*(executable_price-t.cut_value/(D(t.cut_filled)*self.btc_step))>0
            if pending['identity']==self._c1_identity() and m.drawdown<=D('.40') and reclaim:
                t.confirmation={k:pending[k] for k in ('open_ns','close_ns','close')}
                self._c1_log("DEFERRED_4H_FIRST_FRESH_CONFIRMED",now_ns)
            else:self._c1_log("DEFERRED_4H_FIRST_FRESH_DENIED",now_ns)
        if t.state=="CUT_RESOLVING" and not t.cut_submitted and now_ns>t.claim_ns:
            lots=min(t.cut_lots,max(0,int(abs(native_held_quantity)/self.btc_step)-t.target_lots))
            if lots:return C1Plan("CUT" if native_btc_owners_clear else "CANCEL",
                D(lots)*self.btc_step if native_btc_owners_clear else ZERO,-t.side)
        if t.state=="HELD" and not t.restore_submitted and t.confirmation is not None:
            conf=t.confirmation
            if now_ns<=conf['close_ns']:return None
            daily=self._features.bars[-1]
            if (t.last_cut_fill_ns is None or _ns(daily.open_time)<t.last_cut_fill_ns
                    or not _ns(daily.close_time)<=_ns(daily.available_at)<=m.source_ns<=now_ns):return None
            if m.drawdown>D('.40') or t.side*(executable_price-t.cut_value/(D(t.cut_filled)*self.btc_step))<=0:
                t.confirmation=None;return None
            if t.credit:return C1Plan("RESTORE" if native_btc_owners_clear else "CANCEL",
                D(t.credit)*self.btc_step if native_btc_owners_clear else ZERO,t.side)
        return None

    def commit_c1_submission(self,kind: str, *, now_ns: int):
        t=self.c1
        if t is None or t.revoked:raise ValueError("C1_SUBMISSION_WITHOUT_CLAIM")
        if kind=="CUT" and not t.cut_submitted:t.cut_submitted=True
        elif kind=="RESTORE" and not t.restore_submitted and t.credit:
            t.restore_submitted=True;t.restore_committed=t.credit;t.state="RESTORE_RESOLVING"
        else:raise ValueError("C1_DUPLICATE_OR_UNKNOWN_SUBMISSION")
        self._c1_log("ATTEMPT_SUBMIT",now_ns,kind=kind,credit=t.credit)

    def deny_c1_restore(self):
        if self.c1 is not None:self.c1.confirmation=None

    def c1_terminal(self,kind: str, *, now_ns: int):
        t=self.c1
        if t is None:raise ValueError("C1_TERMINAL_UNKNOWN")
        if kind=="CUT":
            t.cut_terminal_ns=max(now_ns,t.cut_terminal_ns or 0);t.cut_submitted=False
            if not t.revoked:t.state="HELD" if t.credit else "RELEASED"
        elif kind=="RESTORE":
            t.restore_submitted=False;t.credit=0
            if not t.revoked:t.state="RELEASED"
        else:raise ValueError("C1_TERMINAL_KIND_UNKNOWN")
        self._c1_log("ATTEMPT_TERMINAL",now_ns,kind=kind)

    def _apply_c1_fill(self,p,kind,quantity,price,now):
        t=self.c1;lots=int(quantity/self.btc_step)
        if t is None or t.parent_id!=p.id:raise ValueError("C1_FILL_LOST_PARENT")
        targets=self._target_lots(p)
        if kind=="CUT":
            available={k:max(0,n-p.tp_filled_lots.get(k,0)-p.risk_retired_lots.get(k,0)) for k,n in enumerate(targets)}
            total=sum(available.values())
            if lots>total or t.cut_filled+lots>t.cut_lots or quantity>self._held(p):raise ValueError("C1_CUT_OVERFILL")
            allocation={k:lots*n//total for k,n in available.items()};left=lots-sum(allocation.values())
            for k in sorted(available):
                take=min(left,available[k]-allocation[k]);allocation[k]+=take;left-=take
            for k,n in allocation.items():
                p.risk_retired_lots[k]=p.risk_retired_lots.get(k,0)+n;t.bucket[k]=t.bucket.get(k,0)+n
            p.cut_filled_lots+=lots;t.cut_filled+=lots;t.cut_value+=quantity*price;t.last_cut_fill_ns=now
            if not t.revoked:t.credit+=lots
        else:
            if lots>t.restore_committed-t.restore_filled:raise ValueError("C1_RESTORE_EXCEEDS_CREDIT")
            left=lots
            for k in sorted(t.bucket):
                take=min(left,t.bucket[k]);t.bucket[k]-=take;p.risk_retired_lots[k]-=take;left-=take
            if left:raise ValueError("C1_RESTORE_BUCKET_UNDERFLOW")
            p.restore_filled_lots+=lots;t.restore_filled+=lots;t.credit=max(0,t.credit-lots)
        self._c1_log("ACTUAL_FILL",now,kind=kind,lots=lots,credit=t.credit)


    def snapshot_state(self):
        parent=asdict(self._parent) if self._parent else None
        if parent is not None:
            for name in ("omitted_levels","suppressed_zero_levels"):parent[name]=sorted(parent[name])
        return dict(version=VERSION,parent=parent,
            days=[[_ns(r.open_time),_ns(r.close_time),_ns(r.available_at),r.btc_open,r.btc_close,r.sol_close] for r in self._features.bars],
            ohlc=dict(self._ohlc),signals=[asdict(f) for f in self._signals],ema=self._features.ema,
            last_entry_attempt=self._last_entry_attempt,fills=dict(self._fills),
            revision=self._btc_revision,funding_version=self._funding_version,c1_peak=self._c1_peak,
            c1=asdict(self.c1) if self.c1 else None,c1_money=asdict(self._c1_money) if self._c1_money else None,
            wait_regime=self._wait_regime,regime_latch_ns=self._regime_latch_ns,
            h4_release_daily_ns=self._h4_release_daily_ns,trail_block_index=self._trail_block_index,last_h4_ns=self._last_h4_ns)

    def restore_state(self, state):
        # Native owner validates source/config/cache/observer/feed continuity
        # before invoking this pure state load. Loading creates no authority.
        if state.get('version')!=VERSION:raise ValueError("REFERENCE_STATE_VERSION")
        rebuilt=FeatureState(self.candidate);signals=[]
        ohlc={int(k):tuple(v) for k,v in state['ohlc'].items()}
        for row in state['days']:
            times=[datetime.fromtimestamp(x/1_000_000_000,timezone.utc) for x in row[:3]]
            bar=DailyBar(*times,*row[3:]);signals.append(rebuilt.append(bar))
        if [asdict(f) for f in signals]!=state['signals'] or rebuilt.ema!=state['ema']:
            raise ValueError("REFERENCE_STATE_FEATURE_IDENTITY")
        parent=state['parent']
        if parent is not None:
            parent=dict(parent)
            for name in ('omitted_levels','suppressed_zero_levels'):parent[name]=frozenset(parent[name])
            for name in ('reference_targets','target_lots','levels'):parent[name]=tuple(parent[name])
            for name in ('tp_filled_lots','ordinary_attempted_index','risk_retired_lots'):
                parent[name]={int(k):v for k,v in parent[name].items()}
            parent=BtcParent(**parent)
        cycle=state['c1']
        if cycle is not None:
            cycle=dict(cycle);cycle['bucket']={int(k):v for k,v in cycle['bucket'].items()};cycle=C1Cycle(**cycle)
        money=C1Money(**state['c1_money']) if state['c1_money'] else None
        if (state['revision']<0 or (parent is None and cycle is not None)
                or (parent is not None and (self._held(parent)<0 or parent.filled_quantity<0
                    or parent.selected_quantity is not None and parent.filled_quantity>parent.selected_quantity))):
            raise ValueError("REFERENCE_STATE_LOT_OR_CYCLE_INVALID")
        self._features=rebuilt;self._signals=signals;self._ohlc=ohlc;self._parent=parent
        last=state['last_entry_attempt'];self._last_entry_attempt=tuple(last) if last is not None else None
        self._fills={k:tuple(v) for k,v in state['fills'].items()}
        self._btc_revision=state['revision'];self._funding_version=state['funding_version']
        self._c1_peak=state['c1_peak'];self.c1=cycle;self._c1_money=money
        self._wait_regime=state['wait_regime'];self._regime_latch_ns=state['regime_latch_ns']
        self._h4_release_daily_ns=state['h4_release_daily_ns'];self._trail_block_index=state['trail_block_index']
        self._last_h4_ns=state['last_h4_ns']

    def retry_native_tp_permission(self,parent_id: str,*,level: int,decision_index: int,
                                   ready_ns: int) -> TargetPlan | None:
        """Retain a real terminal native reduction's still-unfilled entitlement.

        The adapter must supply its retained native owner binding. This is not a
        new D1 signal, a cancel ACK fill, or an increase in the fixed TP budget.
        """
        p=self._owned(parent_id)
        if type(level) is not int or not 0<=level<3:raise ValueError('TP_RETRY_LEVEL_UNKNOWN')
        if p.close_reason or level in p.omitted_levels:return None
        target=self._target_lots(p)[level]-p.tp_filled_lots.get(level,0)-p.risk_retired_lots.get(level,0)
        leaves=min(D(max(0,target))*self.btc_step,self._held(p))
        if leaves<=0:return None
        if type(decision_index) is not int or not 0<=decision_index<=self._signals[-1].index:
            raise ValueError('TP_RETRY_DECISION_CLOCK_UNKNOWN')
        p.ordinary_attempted_index[level]=decision_index
        reference=float(p.planref) if p.planref is not None else p.entry_vwap
        return TargetPlan(level,leaves,D(str(reference*(1+p.side*p.levels[level]))),False,
            p.id,True,decision_index,ready_ns)
