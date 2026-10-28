"""Bounded CODE0 research proof; no matching, cash mutation or fill prediction.

Only supplied already-working paths define the benchmark. The caller proves
native ownership, price/fee bounds and the fixed scenario universe separately.
"""
from decimal import Decimal as D
from fractions import Fraction as F
from coinmaster.strategy.method_a_recovery import floor,ceil
from coinmaster.strategy.method_a_risk import (State,Liability,evaluate,
    tier_partition_envelope,exact_algebra,finite)


@exact_algebra
def recovery_limit(*,side,mark,cost_cap,fee,tick,bid,ask):
    """A marketable LIMIT IOC whose worst linear USDT cost is <= cost_cap.

    Buy rounds DOWN its maximum; sell rounds UP its minimum. Better execution
    only lowers cost when 0<=fee<1. This proves a price bound, never a fill.
    """
    finite(mark,cost_cap,fee,tick,bid,ask)
    if side not in (-1,1) or min(mark,tick,bid,ask)<=0 or bid>ask or cost_cap<0 or not 0<=fee<1:
        raise ValueError('CODE0_UNKNOWN_PRICE_FEE')
    raw=(F(mark)+side*F(cost_cap))/(1+side*F(fee))
    lots=(floor if side==1 else ceil)(raw/F(tick))
    price=D(lots)*tick
    if price<=0 or (price<ask if side==1 else price>bid):
        raise ValueError('CODE0_UNMARKETABLE_COST_CAP')
    cost=max(D(0),side*(price-mark)+price*fee)
    if cost>cost_cap:raise ValueError('CODE0_COST_CAP')
    return price,cost


@exact_algebra
def prove_flat_route(state,feature,old,leg,lot,cost,margin,boundaries):
    """All partials <= SAME old-path baseline; full new fill safe under old.

    Reuses existing exact quantity/tier partitioner, not a second PnL model.
    Candidate closes the actual held leg; no pending fill is added to equity.
    Full new BTC fill clips old BTC leaves to zero; full SOL leaves old BTC
    independently executable. Charging remaining old cost is conservative.
    """
    finite(lot,cost)
    actual=evaluate(state,feature,margin)
    if state.cushion<=0 or actual.worst_deficit<=0 or not actual.margin_pass:
        raise ValueError('CODE0_REQUIRES_ACTUAL_BREACH_MARGIN')
    held=state.btc if leg=='BTC' else state.sol
    if leg not in ('BTC','SOL') or not held or lot<=0 or cost<0:
        raise ValueError('CODE0_UNKNOWN_ROUTE')
    n=abs(held)/lot
    if n!=n.to_integral_value():raise ValueError('CODE0_UNKNOWN_LOTS')
    new=Liability('CODE0_NEW','BTC' if leg=='BTC' else 'SOL',-1 if held>0 else 1,int(n),lot,True,cost)
    baseline=tier_partition_envelope(state,feature,old,margin,boundaries)
    route=tier_partition_envelope(state,feature,old+(new,),margin,boundaries)
    # Require actual cash cushion to survive ALL bounded costs, including the
    # conservative sum when reduce-only clipping makes it unattainable.
    max_cost=sum((o.lot*o.lots*o.cost_per_unit for o in old+(new,)),D(0))
    endpoint=State(D(0) if leg=='BTC' else state.btc,D(0) if leg=='SOL' else state.sol,
                   state.equity-abs(held)*cost,state.peak,state.pb,state.ps)
    remaining=tuple(o for o in old if o.leg!=leg)
    full=tier_partition_envelope(endpoint,feature,remaining,margin,boundaries)
    allowed=(baseline.margin_pass and route.margin_pass and state.cushion>max_cost
             and route.worst_deficit<=baseline.worst_deficit and full.safe)
    return allowed,dict(baseline=str(baseline.worst_deficit),route=str(route.worst_deficit),
        full=str(full.worst_deficit),partition_states=route.states,
        full_partition_states=full.states,cost_per_unit=str(cost),quantity=str(abs(held)),
        endpoint_equity_bound=str(endpoint.equity),no_pending_credit=True,
        scope='FIXED_FIVE_SCENARIOS_ONLY_NO_GAP_OR_FILL_GUARANTEE')
