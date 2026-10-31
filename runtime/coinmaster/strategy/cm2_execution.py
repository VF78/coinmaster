"""Pure native-order planning. No matcher, balance, fee or funding engine."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_CEILING
from coinmaster.strategy.cm2_policy import Decision, Features, Snapshot, D, ZERO

@dataclass(frozen=True)
class ExecutionLimits:
    # Explicit assumed capacity in quote currency; no fake historical volume.
    max_child_notional: D
    max_gross_notional: D | None = None
    child_interval_ns: int = 60_000_000_000
    def __post_init__(self):
        if not self.max_child_notional.is_finite() or self.max_child_notional <= 0 or (self.max_gross_notional is not None and (not self.max_gross_notional.is_finite() or self.max_gross_notional <= 0)):
            raise ValueError("explicit positive capacity assumptions required")
        if self.child_interval_ns < 60_000_000_000:
            raise ValueError("child cadence must be at least one source minute")

@dataclass(frozen=True)
class OrderPlan:
    action: str
    signed_quantity: D = ZERO
    reason: str = ""

def stage_targets(decision: Decision, s: Snapshot, f: Features, *, sol_step=ZERO, sol_min_qty=ZERO, sol_min_notional=ZERO):
    """Ordinary BTC reductions wait for confirmed safe SOL inventory.
    Emergency exits proceed immediately and carry explicitly measured orphan risk.
    """
    btc, sol = decision.btc_target, decision.sol_target
    if decision.cancel_increases:
        return btc, sol, False
    reducing = s.btc_qty*btc >= 0 and abs(btc) < abs(s.btc_qty)
    if f.hedge_valid and s.btc_qty:
        # Both proposed targets and all pending reductions can fill first.
        pending_btc = s.btc_qty+s.btc_pending
        future_btc = min(abs(s.btc_qty),abs(btc))
        if pending_btc*s.btc_qty >= 0:
            future_btc = min(future_btc,abs(pending_btc))
        else:
            future_btc = ZERO
        future_cap = future_btc*s.btc_mark/D(str(f.beta_guard))/s.sol_mark
        sign = -1 if s.btc_qty > 0 else 1
        sol = D(sign)*min(abs(sol),future_cap)
        if sol_step > 0:
            # Quantize the remaining target toward flat BEFORE delta rounding.
            # Rounding a required reduction down can strand held SOL above cap.
            amount=(abs(sol)/sol_step).to_integral_value(rounding=ROUND_DOWN)*sol_step
            held=abs(s.sol_qty)
            if held > amount and s.sol_qty*D(sign) > 0:
                minimum=max(sol_step,sol_min_qty,sol_min_notional/s.sol_mark)
                minimum=(minimum/sol_step).to_integral_value(rounding=ROUND_CEILING)*sol_step
                # Native1.231 min_notional also applies to reduce-only orders.
                # Enlarge a necessary guard trim only toward flat, never risk up.
                if held-amount < minimum:
                    amount=max(ZERO,held-minimum)
                    amount=(amount/sol_step).to_integral_value(rounding=ROUND_DOWN)*sol_step
            sol=D(sign)*amount
        worst_sol = abs(s.sol_qty)+abs(s.sol_pending)
        if reducing and worst_sol > future_cap:
            return s.btc_qty, sol, True
    return btc, sol, False

def order_plan(*,actual,target,pending,unknown,price,step,min_qty,max_child,emergency=False,min_notional=ZERO):
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
        q = min(q,max_child/price)
    q = (q/step).to_integral_value(rounding=ROUND_DOWN)*step
    if q < min_qty or q == 0:
        return OrderPlan("HOLD",reason="VENUE_MINIMUM")
    if q*price < min_notional:
        return OrderPlan("HOLD",reason="VENUE_MIN_NOTIONAL_INCLUDING_REDUCE_ONLY")
    return OrderPlan("SUBMIT",(D(1) if delta > 0 else D(-1))*q,"EMERGENCY" if emergency else "TARGET_CHILD")
