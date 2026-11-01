"""CM2 v2 causal joint inventory policy. No native money or fill simulation."""
from __future__ import annotations
from dataclasses import dataclass, replace
from decimal import Decimal
from math import isfinite, log, sqrt
from statistics import mean

D = Decimal
ZERO = D("0")
HOUR_NS = 3_600_000_000_000
MINUTE_NS = HOUR_NS // 60

@dataclass(frozen=True)
class Config:
    trend_hours: int = 72
    load: float = 4.0
    stop_atr: float = 3.0
    core: float = .75
    hedge_trigger: float = .75
    hedge_fraction: float = .45
    buffer: float = .08
    mode: str = "joint"
    version: str = "cm2-v2"
    core_signal: str = "h1_breakout"
    parent_risk_fraction: float | None = None
    downside_scenarios: tuple[tuple[float, float], ...] = ()
    # Explicit future exit/funding debit per incremental SOL dollar.
    hedge_future_cost_rate: float | None = None
    initial_band_atr: float | None = None
    restore_band_atr: float | None = None
    restore_lifetime_ns: int | None = None
    def __post_init__(self):
        for name, lo, hi in (("trend_hours",24,168),("load",1,8),("stop_atr",2,6),
                            ("core",.5,.9),("hedge_trigger",.25,1.5),
                            ("hedge_fraction",.15,.75),("buffer",.03,.20)):
            value = getattr(self, name)
            if not isfinite(value) or not lo <= value <= hi:
                raise ValueError(name)
        if self.trend_hours != int(self.trend_hours):
            raise ValueError("trend_hours must be integer")
        if self.core_signal not in ("h1_breakout", "slow_d1_h4"):
            raise ValueError("core_signal")
        if self.parent_risk_fraction is not None and not 0 < self.parent_risk_fraction <= 1:
            raise ValueError("parent_risk_fraction")
        if self.initial_band_atr is not None and not 0 < self.initial_band_atr:
            raise ValueError("initial_band_atr")
        if self.hedge_future_cost_rate is not None and (not isfinite(self.hedge_future_cost_rate) or self.hedge_future_cost_rate < 0):
            raise ValueError("hedge_future_cost_rate")
        if any(len(row) != 2 or not all(isfinite(v) for v in row) for row in self.downside_scenarios):
            raise ValueError("downside_scenarios")
        if self.version != "cm2-v2":
            raise ValueError("policy_version")
        if self.restore_band_atr is not None and (not isfinite(self.restore_band_atr) or self.restore_band_atr <= 0):
            raise ValueError("restore_band_atr")
        if self.restore_lifetime_ns is not None and (type(self.restore_lifetime_ns) is not int or self.restore_lifetime_ns <= 0):
            raise ValueError("restore_lifetime_ns")
        if self.mode not in ("joint", "btc_only", "btc_trim"):
            raise ValueError("mode")

@dataclass(frozen=True)
class Hour:
    closed_ns: int
    available_ns: int
    btc_open: float
    btc_high: float
    btc_low: float
    btc_close: float
    sol_close: float

@dataclass(frozen=True)
class Features:
    closed_ns: int
    available_ns: int
    valid: bool
    reason: str = ""
    close: float = 0
    channel_high: float = 0
    channel_low: float = 0
    atr: float = 0
    beta: float = 0
    beta_guard: float = 0
    rho: float = 0
    residual_z: float = 0
    btc_return6: float = 0
    common_loss: float = 0
    residual_loss: float = 0
    hedge_valid: bool = False
    hedge_data_known: bool = True
    covariance_ratio: float = 0
    core_direction: int = 0
    downside_scenarios: tuple[tuple[float, float], ...] = ()
    scenario_classes_complete: bool = False
    daily_atr: float = 0
    h4_close: float = 0
    h4_closed_ns: int = 0
    daily_close: float = 0

def _variance(values):
    avg = mean(values)
    return mean([(v-avg)**2 for v in values])

def _quantile(values, fraction=.95):
    ordered = sorted(values)
    return ordered[min(len(ordered)-1, int((len(ordered)-1)*fraction))]

def features(hours: tuple[Hour, ...], cfg: Config, now_ns: int) -> Features:
    """Only prefix data available by now is eligible. Never accept future seed."""
    if any(h.available_ns > now_ns or h.available_ns < h.closed_ns for h in hours):
        raise ValueError("feature availability violation")
    needed = max(cfg.trend_hours, 168) + 1
    if len(hours) < needed:
        return Features(now_ns, now_ns, False, "WARMUP")
    hs = hours[-needed:]
    if any(b.closed_ns-a.closed_ns != HOUR_NS for a,b in zip(hs,hs[1:])):
        return Features(hs[-1].closed_ns, now_ns, False, "HOUR_GAP")
    h = hs[-1]
    if now_ns-h.closed_ns > HOUR_NS or any(
        not all(isfinite(v) and v > 0 for v in (x.btc_open,x.btc_high,x.btc_low,x.btc_close))
        for x in hs):
        return Features(h.closed_ns, h.available_ns, False, "STALE_OR_INVALID")
    previous = [x.btc_close for x in hs[-cfg.trend_hours-1:-1]]
    tr = [max(b.btc_high-b.btc_low,abs(b.btc_high-a.btc_close),abs(b.btc_low-a.btc_close))
          for a,b in zip(hs[-25:],hs[-24:])]
    if any(not isfinite(x.sol_close) or x.sol_close <= 0 for x in hs):
        return Features(h.closed_ns,h.available_ns,True,"SOL_DATA_UNKNOWN",h.btc_close,
            max(previous),min(previous),mean(tr),hedge_data_known=False)
    btc = [log(b.btc_close/a.btc_close) for a,b in zip(hs[-169:], hs[-168:])]
    sol = [log(b.sol_close/a.sol_close) for a,b in zip(hs[-169:], hs[-168:])]
    vx, vy = _variance(btc), _variance(sol)
    mx, my = mean(btc), mean(sol)
    cov = mean([(x-mx)*(y-my) for x,y in zip(btc,sol)])
    beta = cov/vx if vx > 1e-12 else 0.
    residual = [y-beta*x for x,y in zip(btc,sol)]
    vr = _variance(residual)
    guard = beta + 2*sqrt(vr/(len(btc)*vx)) if vx > 1e-12 else 0.
    rho = cov/sqrt(vx*vy) if vx*vy > 1e-24 else 0.
    z = sum(residual[-6:])/sqrt(6*vr) if vr > 1e-12 else 0.
    true_ranges = [max(b.btc_high-b.btc_low, abs(b.btc_high-a.btc_close), abs(b.btc_low-a.btc_close))
                   for a,b in zip(hs[-25:],hs[-24:])]
    previous = [x.btc_close for x in hs[-cfg.trend_hours-1:-1]]
    # Both stress coefficients use ONE-HOUR returns, never six-hour returns.
    # Symmetric residual tail protects both BTC directions.
    b = max(2*sqrt(vx), _quantile([abs(x) for x in btc]))
    u = max(2*sqrt(vr), _quantile([abs(x) for x in residual]))
    valid = all(isfinite(v) for v in (beta,guard,rho,z,b,u)) and beta > .05 and guard > .05 and rho >= .30 and vr > 1e-12
    # One fixed six-hour horizon: covariance and downside use the same causal pairs.
    scenarios = tuple((hs[i].btc_close/hs[i-6].btc_close-1,
                       hs[i].sol_close/hs[i-6].sol_close-1) for i in range(6,len(hs)))
    xs,ys = zip(*scenarios)
    mx6,my6 = mean(xs),mean(ys)
    vy6 = _variance(ys)
    cov6 = mean((x-mx6)*(y-my6) for x,y in scenarios)
    # Require observed adverse, adverse basis divergence, and rebound in either direction.
    complete = all(any(d*x < 0 for x,y in scenarios) and
                   any(d*x < 0 and d*y > 0 for x,y in scenarios) and
                   any(d*x > 0 for x,y in scenarios) for d in (1,-1))
    return Features(h.closed_ns,h.available_ns,True,"",h.btc_close,max(previous),min(previous),
                    mean(true_ranges),beta,guard,rho,z,sum(btc[-6:]),b,u,valid,True,
                    cov6/vy6 if vy6 > 1e-12 else 0.,0,scenarios,complete)

@dataclass(frozen=True)
class Snapshot:
    equity: D
    btc_qty: D
    sol_qty: D
    btc_mark: D
    sol_mark: D
    btc_pending: D = ZERO
    sol_pending: D = ZERO
    unknown_orders: bool = False
    data_known: bool = True
    # Native actual remaining BTC basis and costs, supplied by the adapter.
    btc_vwap: D | None = None
    btc_entry_fees: D | None = None
    btc_signed_funding: D | None = None
    exit_fee_rate: D = D(".000432")
    btc_tick: D = D(".1")
    max_btc_notional: D | None = None
    max_sol_notional: D | None = None
    btc_reduction_pending: D = ZERO
    sol_increase_pending: D = ZERO
    ownership_known: bool = True
    btc_price_known: bool = True
    core_data_known: bool | None = None

@dataclass(frozen=True)
class State:
    direction: int = 0
    parent: int = 0
    btc_target: D = ZERO
    sol_target: D = ZERO
    unhedged_btc_target: D = ZERO
    initial_r: float = 0
    stop: float = 0
    extreme: float = 0
    harvested: bool = False
    hedge_active: bool = False
    activate_count: int = 0
    release_count: int = 0
    last_hour: int = 0
    last_add_hour: int = 0
    draining: bool = False
    safety_cap: D | None = None
    valid_count: int = 0
    btc_intent: str = ""
    intent_hour: int = 0
    harvest_target: D | None = None
    harvest_start_qty: D | None = None
    initial_anchor: D | None = None
    intent_deadline_ns: int = 0
    initial_cash_risk: D | None = None
    core_target_valid: bool = True
    release_anchor: float = 0
    release_atr: float = 0
    release_armed_ns: int = 0
    release_direction: int = 0
    restore_target: D | None = None
    restore_anchor: D | None = None
    restore_deadline_ns: int = 0

@dataclass(frozen=True)
class Decision:
    btc_target: D
    sol_target: D
    reason: str
    state: State
    cancel_increases: bool = False

def _sign(q):
    return 1 if q > 0 else -1 if q < 0 else 0

def _cap(q, maximum):
    return min(q, maximum) if maximum is not None else q

def positive_harvest(s: Snapshot) -> bool:
    if s.btc_vwap is None or s.btc_entry_fees is None or s.btc_signed_funding is None:
        return False
    gross = s.btc_qty * (s.btc_mark-s.btc_vwap)
    # Credits do not create permission to harvest an otherwise losing BTC leg.
    net = gross-s.btc_entry_fees-abs(s.btc_qty)*s.btc_mark*s.exit_fee_rate+min(ZERO,s.btc_signed_funding)
    return net > abs(s.btc_qty)*s.btc_tick

def actual_harvest_geometry(*, signed_before_qty, filled_qty, fill_price, native_vwap,
                            allocated_entry_fees, allocated_signed_funding, native_commission,
                            native_tick, known=True):
    """Actual native-basis/cost permission audit, never account/PnL authority."""
    values=(signed_before_qty,filled_qty,fill_price,native_vwap,allocated_entry_fees,
            allocated_signed_funding,native_commission,native_tick)
    if (not known or any(v is None or not v.is_finite() for v in values)
            or filled_qty <= 0 or filled_qty > abs(signed_before_qty)
            or native_vwap <= 0 or fill_price <= 0 or native_tick <= 0):
        return {"status":"UNKNOWN","reason":"ACTUAL_NATIVE_BASIS_COST_OR_PARENT_UNPROVEN"}
    gross=D(_sign(signed_before_qty))*filled_qty*(fill_price-native_vwap)
    net=gross-allocated_entry_fees-native_commission+min(ZERO,allocated_signed_funding)
    buffer=filled_qty*native_tick
    return {"status":"PASS" if gross > 0 and net > buffer else "FAIL",
        "scope":"NATIVE_BASIS_AND_ACTUAL_COST_GEOMETRY_NOT_NATIVE_PNL_AUTHORITY",
        "native_before_qty":str(signed_before_qty),"native_fill_qty":str(filled_qty),
        "native_fill_price":str(fill_price),"native_vwap":str(native_vwap),
        "allocated_native_entry_fees":str(allocated_entry_fees),
        "allocated_signed_native_funding":str(allocated_signed_funding),
        "actual_native_commission":str(native_commission),"gross_geometry":str(gross),
        "net_geometry":str(net),"strict_tick_buffer":str(buffer)}


def btc_child_permission(cfg: Config, f: Features, s: Snapshot, st: State, *, now_ns: int,
                         executable_price: D) -> tuple[bool, str]:
    """Permission for ordinary BTC intent, using current native costs/quote.

    This is an admission check, never an execution/PnL model. Safety reductions
    are deliberately independent of ordinary entry/add/harvest permission.
    """
    intent = st.btc_intent
    if intent not in ("INITIAL_ENTRY", "FAVORABLE_ADD", "POSITIVE_HARVEST", "MATCHED_RESTORE"):
        if abs(st.btc_target) > abs(s.btc_qty) or st.btc_target*s.btc_qty < 0:
            return False, "NO_CURRENT_ORDINARY_INCREASE_RIGHT"
        return True, "SAFETY_OR_NO_ORDINARY_INTENT"
    if (not f.valid or not (s.data_known if s.core_data_known is None else s.core_data_known) or s.unknown_orders
            or not (f.available_ns < now_ns and 0 <= now_ns-f.closed_ns <= HOUR_NS)
            or executable_price <= 0):
        return False, "ORDINARY_FEATURE_OR_NATIVE_STATE_UNKNOWN"
    if intent == "POSITIVE_HARVEST":
        return (positive_harvest(replace(s,btc_mark=executable_price)), "CURRENT_EXECUTABLE_NET_HARVEST")
    if intent == "MATCHED_RESTORE":
        if (not st.core_target_valid or st.harvested or core_direction(cfg,f) == -st.direction
                or _sign(st.btc_target) != st.direction or cfg.parent_risk_fraction is None
                or cfg.restore_band_atr is None or st.restore_anchor is None
                or st.restore_target != st.btc_target or now_ns > st.restore_deadline_ns
                or abs(executable_price-st.restore_anchor) > D(str(cfg.restore_band_atr*f.atr))):
            return False, "MATCHED_CORE_RESTORE_INVALID"
        return (st.stop > 0 and stop_cash_risk(st.btc_target,executable_price,D(str(st.stop)),s.exit_fee_rate)
                <= s.equity*D(str(cfg.parent_risk_fraction))), "MATCHED_CORE_RESTORE_RISK"
    if st.harvested or st.harvest_target is not None or st.intent_hour != f.closed_ns:
        return False, "ADD_RIGHT_EXPIRED_OR_HARVESTED"
    if cfg.parent_risk_fraction is None:
        return False, "PARENT_RISK_BUDGET_UNAPPROVED"
    if st.btc_intent == "INITIAL_ENTRY" and st.initial_anchor is not None:
        if (cfg.initial_band_atr is None or now_ns > st.intent_deadline_ns
                or abs(executable_price-st.initial_anchor) > D(str(cfg.initial_band_atr*f.atr))):
            return False, "INITIAL_COMPLETION_BAND_OR_DEADLINE"
    if intent == "INITIAL_ENTRY":
        if (st.initial_cash_risk is None or st.initial_cash_risk <= 0 or st.initial_anchor is None
                or st.initial_r <= 0 or cfg.initial_band_atr is None):
            return False, "INITIAL_ACCEPTED_BUDGET_UNKNOWN"
        boundary = st.initial_anchor-D(_sign(st.btc_target))*D(str(st.initial_r))
        if _sign(st.btc_target)*(executable_price-boundary) <= 0:
            return False, "INITIAL_BOUNDARY_ALREADY_CROSSED"
        risk = stop_cash_risk(st.btc_target,executable_price,boundary,s.exit_fee_rate)
        if risk > st.initial_cash_risk:
            return False, "INITIAL_ACCEPTED_CASH_RISK_EXCEEDED"
    if (intent == "FAVORABLE_ADD" and st.stop > 0 and
            stop_cash_risk(st.btc_target,executable_price,D(str(st.stop)),s.exit_fee_rate)
            > s.equity*D(str(cfg.parent_risk_fraction))):
        return False, "ADD_PROSPECTIVE_CASH_RISK_EXCEEDED"
    direction = _sign(st.btc_target)
    if not direction or direction != core_direction(cfg,f):
        return False, "CURRENT_AUTHORIZED_BREAKOUT_REQUIRED"
    # Flat initial entry has no basis yet. Every child after an actual fill
    # must remain favorable against the actual native remaining basis.
    if s.btc_qty:
        if s.btc_vwap is None or direction != _sign(s.btc_qty):
            return False, "NATIVE_BASIS_UNKNOWN_OR_FACTOR_MISMATCH"
        favorable=direction*(executable_price-s.btc_vwap)
        # Authentic remaining INITIAL_ENTRY budget may fill at the same basis;
        # a new ADD/restoration needs a strictly favorable price.
        if intent != "INITIAL_ENTRY" and favorable <= 0:
            return False, "CURRENT_EXECUTABLE_NOT_FAVORABLE"
    return True, "CURRENT_AUTHORIZED_BREAKOUT_FAVORABLE"


def reconcile_btc_intent(cfg, f, s, st, *, now_ns, executable_price):
    """Revoke unsafe ordinary leaves permanently; late fills reduce to cap."""
    if st.harvest_target is not None and abs(s.btc_qty) <= abs(st.harvest_target) and not s.btc_pending:
        st = replace(st,harvested=True,harvest_target=None,harvest_start_qty=None,
                     btc_intent="HOLD",btc_target=s.btc_qty,unhedged_btc_target=s.btc_qty)
    allowed, reason = btc_child_permission(cfg,f,s,st,now_ns=now_ns,executable_price=executable_price)
    if not allowed:
        # Keep the once-per-parent harvest right only if native inventory
        # actually reduced. A denied/canceled unfilled harvest consumes none.
        partial = (st.harvest_start_qty is not None
                   and abs(s.btc_qty) < abs(st.harvest_start_qty))
        st = replace(st,btc_target=s.btc_qty,unhedged_btc_target=s.btc_qty,
                     btc_intent="RISK_TRIM",intent_hour=0,harvested=st.harvested or partial,
                     harvest_target=None,harvest_start_qty=None)
    return st, allowed, reason


def decide(cfg: Config, f: Features, s: Snapshot, st: State, *, terminal=False, now_ns=None) -> Decision:
    if any(not v.is_finite() for v in (s.equity,s.btc_qty,s.sol_qty,s.btc_mark,s.sol_mark)):
        raise ValueError("non-finite native snapshot")
    now_ns = max(f.available_ns,f.closed_ns)+1 if now_ns is None else now_ns
    d = _sign(s.btc_qty)
    new_hour = f.closed_ns > st.last_hour
    if terminal or st.draining or s.equity <= 0:
        if s.btc_qty == 0 and s.sol_qty == 0 and s.btc_pending == 0 and s.sol_pending == 0 and not s.unknown_orders:
            clean = State(parent=st.parent,last_hour=f.closed_ns,release_anchor=st.release_anchor,
                release_atr=st.release_atr,release_armed_ns=st.release_armed_ns,release_direction=st.release_direction)
            return Decision(ZERO,ZERO,"TERMINAL_FLAT" if terminal else "DRAIN_COMPLETE",clean,True)
        return Decision(ZERO,ZERO,"TERMINAL_DRAIN" if terminal else "PARENT_DRAIN",
                        replace(st,draining=True,btc_target=ZERO,sol_target=ZERO,btc_intent="RISK_TRIM",
                                intent_hour=0,harvest_target=None,harvest_start_qty=None),True)
    # An unexpected BTC flat immediately invalidates SOL, including pending SOL.
    if d == 0 and st.direction != 0:
        return Decision(ZERO,ZERO,"BTC_FLAT_SOL_DRAIN",
                        replace(st,draining=True,btc_target=ZERO,sol_target=ZERO,btc_intent="RISK_TRIM",
                                intent_hour=0,harvest_target=None,harvest_start_qty=None),True)
    if d and st.direction == 0:
        if (st.btc_intent != "INITIAL_ENTRY" or _sign(st.btc_target) != d
                or st.safety_cap is not None):
            # Revoked/unknown first fills cannot manufacture a fresh parent.
            return Decision(ZERO,ZERO,"LATE_OR_UNOWNED_BTC_DRAIN",
                replace(st,draining=True,btc_target=ZERO,sol_target=ZERO,
                        unhedged_btc_target=ZERO,btc_intent="RISK_TRIM",intent_hour=0,
                        harvest_target=None,harvest_start_qty=None),True)
        # Parent exists only once authorized native BTC inventory is present.
        r = st.initial_r or cfg.stop_atr*f.atr
        entry = float(s.btc_vwap or s.btc_mark)
        st = replace(st,direction=d,parent=st.parent+1,initial_r=r,
                     stop=entry-d*r,extreme=entry)
    if d and d != st.direction:
        return Decision(ZERO,ZERO,"UNEXPECTED_FACTOR_FLIP",replace(st,draining=True,btc_target=ZERO,sol_target=ZERO,unhedged_btc_target=ZERO,
                            btc_intent="RISK_TRIM",intent_hour=0,harvest_target=None,harvest_start_qty=None),True)
    mandatory = evaluate_mandatory_risk(s,st,cfg)
    if mandatory is not None and mandatory.state.draining and cfg.core_signal == "slow_d1_h4":
        mandatory = replace(mandatory,state=arm_slow_release(mandatory.state,f,now_ns))
    if mandatory is not None:
        return mandatory
    unknown = (not f.valid or not (s.data_known if s.core_data_known is None else s.core_data_known) or s.unknown_orders
               or not (0 <= now_ns-f.closed_ns <= HOUR_NS)
               )
    if unknown:
        # A single finite target is latched. Repeated callbacks never halve again.
        cap = st.safety_cap if st.safety_cap is not None else abs(s.btc_qty)*D(".5")
        target = D(d)*min(abs(s.btc_qty),cap)
        return Decision(target,ZERO,"UNKNOWN_DRAIN_AND_FIXED_TRIM",
                        replace(st,btc_target=target,unhedged_btc_target=target,btc_intent="RISK_TRIM",
                                intent_hour=0,harvest_target=None,harvest_start_qty=None,
                                harvested=st.harvested or (st.harvest_start_qty is not None
                                    and abs(s.btc_qty) < abs(st.harvest_start_qty)),
                                sol_target=ZERO,safety_cap=cap,
                                valid_count=0,hedge_active=False,last_hour=max(st.last_hour,f.closed_ns)),True)
    st, allowed, permission_reason = reconcile_btc_intent(cfg,f,s,st,now_ns=now_ns,executable_price=s.btc_mark)
    if not allowed and not new_hour:
        sol = _held_sol_cap(cfg,f,s,st.sol_target)
        return Decision(st.btc_target,sol,"ORDINARY_INTENT_REVOKED:"+permission_reason,
                        replace(st,sol_target=sol),True)
    if not new_hour:
        # Fill/mark rechecks cannot create new signal rights.
        target = st.btc_target
        sol = _held_sol_cap(cfg,f,s,st.sol_target)
        return Decision(target,sol,"INVENTORY_RECHECK",replace(st,sol_target=sol))
    st = replace(st,last_hour=f.closed_ns,valid_count=st.valid_count+1)
    if st.safety_cap is not None:
        if st.valid_count < 2 or s.sol_qty != 0 or s.sol_pending != 0:
            return Decision(D(d)*min(abs(s.btc_qty),st.safety_cap),ZERO,"VALIDITY_RECOVERY_WAIT",st,True)
        st = replace(st,safety_cap=None)
    if d == 0:
        if s.sol_qty or s.sol_pending or s.btc_pending:
            return Decision(st.btc_target,ZERO,"FLAT_WAIT_PENDING",st,True)
        direction = core_direction(cfg,f)
        if cfg.core_signal == "slow_d1_h4" and st.release_armed_ns:
            if direction != st.release_direction:
                st = arm_slow_release(st,f,now_ns)
            if (f.h4_closed_ns <= st.release_armed_ns or not st.release_atr
                    or direction*(f.h4_close-st.release_anchor) < .5*st.release_atr):
                direction = 0
        if direction == 0:
            return Decision(ZERO,ZERO,"NO_BREAKOUT",replace(st,btc_target=ZERO,sol_target=ZERO))
        if cfg.parent_risk_fraction is None or cfg.initial_band_atr is None:
            return Decision(ZERO,ZERO,"PARENT_RISK_OR_INITIAL_BAND_UNAPPROVED",st,True)
        notional = risk_sized_notional(cfg,f,s)
        target = D(direction)*notional/s.btc_mark
        return Decision(target,ZERO,"BTC_BREAKOUT_ENTRY",replace(st,btc_target=target,
                        initial_r=cfg.stop_atr*f.atr,last_add_hour=f.closed_ns,unhedged_btc_target=target,
                        btc_intent="INITIAL_ENTRY",intent_hour=f.closed_ns,initial_anchor=s.btc_mark,
                        intent_deadline_ns=f.closed_ns+HOUR_NS,
                        initial_cash_risk=s.equity*D(str(cfg.parent_risk_fraction)),core_target_valid=True,release_armed_ns=0))
    if cfg.core_signal == "slow_d1_h4" and f.core_direction == -d:
        return Decision(ZERO,ZERO,"SLOW_REGIME_EXIT",arm_slow_release(replace(st,draining=True,
            btc_target=ZERO,sol_target=ZERO,btc_intent="RISK_TRIM",core_target_valid=False),f,now_ns),True)
    previous_extreme = st.extreme
    extreme = max(st.extreme,f.close) if d > 0 else min(st.extreme,f.close)
    proposed = extreme-d*cfg.stop_atr*f.atr
    stop = max(st.stop,proposed) if d > 0 else min(st.stop,proposed)
    st = replace(st,extreme=extreme,stop=stop)
    # Newly ratcheted boundary is effective from this decision onward, never
    # retroactively triggered by the already closed bar used to establish it.
    btc = st.btc_target
    reason = "CORE_HOLD"
    if st.harvest_target is not None:
        btc = st.harvest_target
        reason = "POSITIVE_NET_HARVEST"
    elif not st.harvested and not s.btc_pending and d*(float(s.btc_mark)-float(s.btc_vwap or s.btc_mark)) >= 2*st.initial_r and positive_harvest(s):
        btc = s.btc_qty*D(str(cfg.core))
        st = replace(st,btc_intent="POSITIVE_HARVEST",intent_hour=f.closed_ns,
                     harvest_target=btc,harvest_start_qty=s.btc_qty)
        reason = "POSITIVE_NET_HARVEST"
    elif (not st.harvested and not s.btc_pending and s.btc_vwap is not None
          and d*(float(s.btc_mark)-float(s.btc_vwap)) > 0
          and d*(f.close-previous_extreme) > 0
          and ((d > 0 and f.close > f.channel_high) or (d < 0 and f.close < f.channel_low))
          and f.closed_ns > st.last_add_hour):
        # Target, never ADD L*equity on every callback. No adverse averaging.
        desired = D(d)*risk_sized_notional(cfg,f,s)/s.btc_mark
        if abs(desired) > abs(btc):
            btc = desired
            reason = "FAVORABLE_BREAKOUT_TARGET"
            st = replace(st,btc_intent="FAVORABLE_ADD",intent_hour=f.closed_ns)
        st = replace(st,last_add_hour=f.closed_ns)
    adverse = d*f.btc_return6 < 0 and d*f.residual_z < -cfg.hedge_trigger
    released = d*f.btc_return6 >= 0 or d*f.residual_z >= -cfg.hedge_trigger/2
    ac = st.activate_count+1 if adverse else 0
    rc = st.release_count+1 if released else 0
    active = st.hedge_active
    if ac >= 2: active = True
    if rc >= 2: active = False
    was_active = st.hedge_active
    reference = btc
    if cfg.mode == "btc_trim" and reason == "CORE_HOLD" and (active or was_active):
        reference = st.unhedged_btc_target if was_active else s.btc_qty
    st = replace(st,activate_count=ac,release_count=rc,hedge_active=active,btc_target=btc,
                 unhedged_btc_target=reference)
    # Hold is the feasible no-change baseline, not an instruction to churn to flat.
    sol = s.sol_qty if active and cfg.mode == "joint" and f.hedge_valid else ZERO
    if active and cfg.mode != "btc_only":
        reference = st.unhedged_btc_target if cfg.mode == "btc_trim" else s.btc_qty
        soft, hard = hedge_limits(cfg,f,s,reference)
        target = -D(d)*min(soft,hard)
        selected = select_hedge_target(cfg,f,s,target)
        if cfg.mode == "joint":
            sol = selected
        if selected and (selected == s.sol_qty or hedge_change_improves(cfg,f,s,selected)):
            target = selected
            if cfg.mode == "btc_trim" and st.harvest_target is None:
                btc = D(d)*max(ZERO,abs(reference)-D(str(f.beta))*abs(target)*s.sol_mark/s.btc_mark)
                reason = "MATCHED_BTC_TRIM"
                if abs(btc) <= abs(s.btc_qty):
                    st = replace(st,btc_intent="RISK_TRIM",intent_hour=0)
            elif cfg.mode == "joint":
                sol = target
                reason = "SELECTIVE_SOL_HEDGE"
    if cfg.mode == "btc_trim" and not active and was_active:
        # Restore only with a current favorable core permission, never a stale parent.
        reference = st.unhedged_btc_target
        restore = replace(st,btc_target=reference,btc_intent="MATCHED_RESTORE",intent_hour=f.closed_ns,
            restore_target=reference,restore_anchor=s.btc_mark,
            restore_deadline_ns=now_ns+(cfg.restore_lifetime_ns or 0))
        if abs(s.btc_qty) < abs(reference) and cfg.restore_lifetime_ns is not None and btc_child_permission(cfg,f,s,restore,now_ns=now_ns,executable_price=s.btc_mark)[0]:
            btc = reference
            st = restore
            reason = "MATCHED_TRIM_CAUSAL_RESTORE"
    sol = _held_sol_cap(cfg,f,s,sol)
    st = replace(st,btc_target=btc,sol_target=sol)
    return Decision(btc,sol,reason,st,not allowed)

def core_direction(cfg, f):
    if cfg.core_signal == "slow_d1_h4":
        return f.core_direction
    return 1 if f.close > f.channel_high else -1 if f.close < f.channel_low else 0


def evaluate_mandatory_risk(s, st, cfg=None):
    """Previously known boundary on fresh native mark; no new signal is consumed."""
    d = _sign(s.btc_qty)
    if (d and d == st.direction and st.stop > 0 and s.btc_price_known
            and s.ownership_known and not s.unknown_orders and s.btc_mark > 0
            and d*(s.btc_mark-D(str(st.stop))) <= 0):
        return Decision(ZERO,ZERO,"PROTECTIVE_STOP",replace(st,draining=True,
            btc_target=ZERO,sol_target=ZERO,btc_intent="RISK_TRIM",intent_hour=0,
            harvest_target=None,harvest_start_qty=None,core_target_valid=False),True)
    if (cfg is not None and cfg.parent_risk_fraction is not None and d and st.stop > 0
            and not st.draining and s.ownership_known and not s.unknown_orders
            and s.btc_price_known and s.btc_mark > 0 and s.equity > 0):
        unit = stop_cash_risk(D(1),s.btc_mark,D(str(st.stop)),s.exit_fee_rate)
        safe = s.equity*D(str(cfg.parent_risk_fraction))/unit if unit > 0 else abs(s.btc_qty)
        if abs(s.btc_qty) > safe:
            target=D(d)*safe
            return Decision(target,st.sol_target,"HELD_CASH_RISK_TRIM",replace(st,
                btc_target=target,unhedged_btc_target=target,btc_intent="RISK_TRIM",
                intent_hour=0,harvest_target=None,harvest_start_qty=None),True)
    return None


def stop_cash_risk(quantity, price, stop, fee):
    """One conservative cash-loss definition for accepted, held and restored size."""
    return abs(quantity)*(abs(price-stop)+fee*(price+stop))


def risk_sized_notional(cfg, f, s):
    """Stop distance + adverse execution costs in currency, shared entry/held units."""
    if cfg.parent_risk_fraction is None or s.btc_mark <= 0 or f.atr <= 0:
        return ZERO
    distance = D(str(cfg.stop_atr*f.atr))/s.btc_mark
    loss_per_notional = stop_cash_risk(D(1),s.btc_mark,s.btc_mark*(1+distance),s.exit_fee_rate)/s.btc_mark
    return _cap(min(s.equity*D(str(cfg.load)),
        s.equity*D(str(cfg.parent_risk_fraction))/loss_per_notional),s.max_btc_notional)


def hedge_limits(cfg, f, s, btc_qty):
    """SOL quantities: covariance soft intensity, distinct no-factor-flip hard cap."""
    if not f.hedge_valid or not f.hedge_data_known or f.beta_guard <= 0 or s.sol_mark <= 0:
        return ZERO,ZERO
    b = abs(btc_qty)*s.btc_mark
    soft = D(str(cfg.hedge_fraction))*D(str(max(0,f.covariance_ratio)))*b/s.sol_mark
    hard = b/D(str(f.beta_guard))/s.sol_mark
    if s.max_sol_notional is not None:
        hard = min(hard,s.max_sol_notional/s.sol_mark)
    return min(soft,hard),hard


def hedge_change_improves(cfg, f, s, target):
    """One causal horizon of dollar downside; costs apply only to future changes."""
    scenarios = cfg.downside_scenarios or f.downside_scenarios
    if not scenarios or (not cfg.downside_scenarios and not f.scenario_classes_complete) or cfg.hedge_future_cost_rate is None:
        return False
    current = s.sol_qty
    if target*current < 0 or not f.hedge_valid:
        return False
    b = s.btc_qty*s.btc_mark
    def loss(q):
        return max(ZERO,max(-(b*D(str(br))+q*s.sol_mark*D(str(sr)))
                             for br,sr in scenarios))
    delta = abs(target-current)*s.sol_mark
    costs = delta*s.exit_fee_rate+max(ZERO,abs(target)-abs(current))*s.sol_mark*D(str(cfg.hedge_future_cost_rate))
    return loss(target)+costs < loss(current)


def select_hedge_target(cfg,f,s,soft):
    """Compare hold, zero, and covariance target on the identical causal sample."""
    scenarios=cfg.downside_scenarios or f.downside_scenarios
    if (not scenarios or (not cfg.downside_scenarios and not f.scenario_classes_complete)
            or cfg.hedge_future_cost_rate is None):
        return s.sol_qty
    b=s.btc_qty*s.btc_mark
    def score(q):
        downside=max(ZERO,max(-(b*D(str(br))+q*s.sol_mark*D(str(sr))) for br,sr in scenarios))
        execution=abs(q-s.sol_qty)*s.sol_mark*s.exit_fee_rate
        future=max(ZERO,abs(q)-abs(s.sol_qty))*s.sol_mark*D(str(cfg.hedge_future_cost_rate))
        return downside+execution+future
    # Current first breaks equal scores in favor of no trade.
    return min((s.sol_qty,ZERO,soft),key=score)


def _held_sol_cap(cfg, f, s, target):
    if s.btc_qty == 0 or not f.hedge_valid or s.sol_mark <= 0:
        return ZERO
    d = _sign(s.btc_qty)
    if _sign(target) == d:
        return ZERO
    _,cap = hedge_limits(cfg,f,s,s.btc_qty)
    desired = -D(d)*min(abs(target),cap)
    difference=abs(desired-s.sol_qty)*s.sol_mark
    if desired and desired*s.sol_qty > 0 and abs(s.sol_qty) <= cap and difference < D(str(cfg.buffer))*abs(s.btc_qty)*s.btc_mark:
        return s.sol_qty
    return desired

class PairedHourBuilder:
    """UTC minute barrier, contiguous exactly-60 aggregation, no forward fill."""
    def __init__(self):
        self.pending = {}
        self.minutes = []
        self.last_minute = None
    def add(self, symbol: str, closed_ns: int, available_ns: int, o: float, h: float, l: float, c: float):
        if symbol not in ("BTC","SOL") or available_ns < closed_ns:
            raise ValueError("invalid minute")
        if self.last_minute is not None and closed_ns <= self.last_minute:
            return None  # duplicate event is idempotent
        row = self.pending.setdefault(closed_ns,{})
        incoming = (available_ns,o,h,l,c)
        if symbol in row and row[symbol] != incoming:
            raise ValueError("conflicting duplicate")
        row[symbol] = incoming
        if len(row) != 2:
            return None
        if len(self.pending) > 1 or (self.last_minute is not None and closed_ns-self.last_minute != MINUTE_NS):
            raise ValueError("paired minute gap/out-of-order")
        self.pending.pop(closed_ns)
        self.last_minute = closed_ns
        if not self.minutes and (closed_ns-MINUTE_NS) % HOUR_NS:
            raise ValueError("partial initial hour")
        self.minutes.append((closed_ns,row))
        if closed_ns % HOUR_NS:
            return None
        if len(self.minutes) != 60:
            raise ValueError("incomplete hour")
        rows = self.minutes
        self.minutes = []
        return Hour(closed_ns,max(x[1][s][0] for x in rows for s in ("BTC","SOL")),
                    rows[0][1]["BTC"][1],max(x[1]["BTC"][2] for x in rows),
                    min(x[1]["BTC"][3] for x in rows),rows[-1][1]["BTC"][4],rows[-1][1]["SOL"][4])


@dataclass(frozen=True)
class Day:
    closed_ns: int
    available_ns: int
    open: float
    high: float
    low: float
    close: float


def slow_features(base: Features, days: tuple[Day, ...], hours: tuple[Hour, ...], now_ns: int):
    """ONE clean EMA34 D1 regime, ATR14 D1, closed H4 release reference."""
    if any(d.available_ns > now_ns or d.available_ns < d.closed_ns for d in days):
        raise ValueError("D1 availability violation")
    if len(days) < 35 or any(b.closed_ns-a.closed_ns != 24*HOUR_NS for a,b in zip(days,days[1:])):
        return replace(base,valid=False,reason="GENUINE_D1_WARMUP_REQUIRED")
    if days[-1].closed_ns > now_ns or now_ns-days[-1].closed_ns >= 25*HOUR_NS:
        return replace(base,valid=False,reason="D1_STALE")
    ema = mean(d.close for d in days[:34])
    for day in days[34:]:
        ema += (day.close-ema)*2/35
    trs = [max(b.high-b.low,abs(b.high-a.close),abs(b.low-a.close)) for a,b in zip(days,days[1:])]
    atr = mean(trs[:14])
    for tr in trs[14:]:
        atr = (atr*13+tr)/14
    direction = 1 if days[-1].close > ema else -1 if days[-1].close < ema else 0
    closed_h4 = [h for h in hours if h.closed_ns % (4*HOUR_NS) == 0 and h.available_ns <= now_ns]
    h4 = closed_h4[-1] if closed_h4 else None
    return replace(base,atr=atr,core_direction=direction,daily_atr=atr,
                   h4_close=h4.btc_close if h4 else 0,h4_closed_ns=h4.closed_ns if h4 else 0,daily_close=days[-1].close)


def pending_effects(actual, orders):
    """Reachable reductions and gross increases; no offset/RO credit for growth."""
    reduction=ZERO
    growth=ZERO
    for signed,reduce_only in orders:
        if actual*signed < 0:
            reduction += signed
        if not reduce_only:
            # Opposite non-RO may fill through flat; reserve conservatively in gross.
            growth += abs(signed)
    reduction = D(-_sign(actual))*min(abs(actual),abs(reduction))
    return reduction,growth


def arm_slow_release(st,f,now_ns):
    if st.draining and st.release_armed_ns:
        return st
    return replace(st,release_anchor=f.daily_close,release_atr=f.daily_atr,
        release_armed_ns=now_ns,release_direction=f.core_direction,core_target_valid=False,
        restore_target=None,restore_anchor=None,restore_deadline_ns=0)
