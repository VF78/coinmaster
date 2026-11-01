"""Pure native-order planning. No matcher, balance, fee or funding engine."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_CEILING
D = Decimal
ZERO = D(0)

REDUCE_MIN_NOTIONAL_REASON="CONSERVATIVE_RESEARCH_MIN_NOTIONAL_REDUCE_EXCEPTION_UNKNOWN"

@dataclass(frozen=True)
class ExecutionLimits:
    # Explicit assumed capacity in quote currency; no fake historical volume.
    max_child_notional: D
    max_gross_notional: D | None = None
    child_interval_ns: int = 0
    def __post_init__(self):
        if not self.max_child_notional.is_finite() or self.max_child_notional <= 0 or (self.max_gross_notional is not None and (not self.max_gross_notional.is_finite() or self.max_gross_notional <= 0)):
            raise ValueError("explicit positive capacity assumptions required")
        if self.child_interval_ns < 0:
            raise ValueError("negative child cadence")

@dataclass(frozen=True)
class OrderPlan:
    action: str
    signed_quantity: D = ZERO
    reason: str = ""

@dataclass(frozen=True)
class NativeExposure:
    equity: D
    btc_qty: D
    sol_qty: D
    btc_mark: D
    sol_mark: D
    unknown_orders: bool
    data_known: bool
    price_known: dict
    unknown_order_assets: frozenset = frozenset()


@dataclass
class SafetyState:
    global_latched: bool = False
    reason: str = ""
    emergency_peak_equity: D = ZERO
    emergency_latched: bool = False
    emergency_valuation_known: bool = False
    emergency_trigger_equity: D = ZERO
    emergency_trigger_peak_equity: D = ZERO
    emergency_trigger_ns: int = 0
    emergency_trigger_fraction: D = ZERO


def order_plan(*,actual,target,pending,unknown,price,step,min_qty,max_child,emergency=False,min_notional=ZERO,venue_max_child_notional=None,venue_reference_price=None):
    # min_notional on reductions is an explicit conservative research policy,
    # not proof of the venue's full-close/dust exception.
    if unknown:
        return OrderPlan("CANCEL" if pending else "HOLD",reason="UNKNOWN_ACK_RECONCILE")
    delta = target-actual
    if pending:
        # Existing leaves are counted once; never submit a second copy.
        wrong_side = delta*pending <= 0
        overshoot = abs(pending) > abs(delta)
        return OrderPlan("CANCEL" if wrong_side or overshoot else "WAIT",reason="PENDING_TARGET_RECONCILE")
    if delta == 0:
        return OrderPlan("HOLD",reason="AT_TARGET")
    # Never issue an order through flat; flip requires flat/drain first.
    if actual and actual*delta < 0:
        delta = (D(1) if delta > 0 else D(-1))*min(abs(delta),abs(actual))
    q = abs(delta)
    if not emergency:
        q = min(q,max_child/(venue_reference_price or price))
    if venue_max_child_notional is not None:
        q = min(q,venue_max_child_notional/(venue_reference_price or price))
    q = (q/step).to_integral_value(rounding=ROUND_DOWN)*step
    if q < min_qty or q == 0:
        return OrderPlan("HOLD",reason="VENUE_MINIMUM")
    if q*price < min_notional:
        return OrderPlan("HOLD",reason=REDUCE_MIN_NOTIONAL_REASON if actual*delta < 0 else "VENUE_MIN_NOTIONAL")
    if actual*delta < 0:
        minimum_remainder = max(step,min_qty,min_notional/price)
        minimum_remainder = (minimum_remainder/step).to_integral_value(rounding=ROUND_CEILING)*step
        remainder = abs(actual)-q
        if ZERO < remainder < minimum_remainder:
            # Shrink only: preserve the original target/cap and leave a legal lot.
            safe_q = ((abs(actual)-minimum_remainder)/step).to_integral_value(rounding=ROUND_DOWN)*step
            q = min(q,max(ZERO,safe_q))
            if q == 0 or q < min_qty or q*price < min_notional:
                return OrderPlan("HOLD",reason="VENUE_RESIDUAL_DUST_PREVENTION")
    return OrderPlan("SUBMIT",(D(1) if delta > 0 else D(-1))*q,"EMERGENCY" if emergency else "TARGET_CHILD")
