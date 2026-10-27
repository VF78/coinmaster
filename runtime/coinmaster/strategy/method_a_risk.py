"""Method A W30 risk mathematics. No native engine, money mutation or matching.

This module evaluates hypothetical states only. Actual fills/account/marks remain
native authority. Finite partial fills are enumerated directly in integer lots;
there is deliberately no endpoint/convexity shortcut across venue tiers.
"""
from dataclasses import dataclass
from decimal import Decimal as D
from itertools import product
from decimal import localcontext
from functools import wraps
from fractions import Fraction

DAY = 86_400_000_000_000
MINUTE = 60_000_000_000
RESERVE = D('.001')
TAKER = D('.00055')


def _width(value):
    if isinstance(value,D):
        if not value.is_finite():return 1
        parts=value.as_tuple()
        return len(parts.digits)+abs(parts.exponent)+1
    if type(value)is int:return len(str(abs(value)))+1
    if hasattr(value,'__dataclass_fields__'):
        return sum(_width(getattr(value,k)) for k in value.__dataclass_fields__)
    if isinstance(value,(tuple,list)):return sum(map(_width,value))
    return 0


def exact_algebra(function):
    """Preserve finite input coefficients through bounded-depth products/sums.

    W30 statistical coefficients are frozen finite Decimals, then interpreted
    exactly in the stress algebra. Required precision derives from all input
    digit/exponent widths; 256 guard digits cover the frozen captured profile's
    finite rates/deductions and fixed40x/20x terminating leverage divisions.
    This is arithmetic precision, never a search/risk parameter or lot cap.
    Callback margin functions must use that raw finite frozen profile formula;
    native Money rounding is separately checked at zero shock, never tolerated.
    """
    @wraps(function)
    def wrapped(*args,**kwargs):
        with localcontext() as context:
            context.prec=max(context.prec,256+sum(map(_width,args))+sum(map(_width,kwargs.values())))
            return function(*args,**kwargs)
    return wrapped


def finite(*values):
    if any(not isinstance(x, D) or not x.is_finite() for x in values):
        raise ValueError('METHOD_A_NONFINITE_OR_UNKNOWN')


@dataclass(frozen=True)
class Observation:
    end_ns: int
    available_ns: int
    btc: D
    sol: D


@dataclass(frozen=True)
class Funding:
    leg: str
    effective_ns: int
    available_ns: int
    rate: D
    interval_ns: int


@dataclass(frozen=True)
class Features:
    start_ns: int
    end_ns: int
    available_ns: int
    beta: D
    rho: D
    sigma_b: D
    sigma_s: D
    b: D
    residual: D
    fund_b: D
    fund_s: D

    @exact_algebra
    def shocks(self):
        return ((D(0), D(0)),) + tuple((b, self.beta*b+e)
            for b, e in product((-self.b, self.b), (-self.residual, self.residual)))


def lagged_features(observations, funding, decision_ns):
    """31 paired closes / 30 returns ending <= UTC day-start minus one day.

    Funding intervals tile the exact prior30days for each leg; an omitted or
    unknown interval cannot become zero. Publication model is end+60s minimum.
    """
    cutoff = decision_ns//DAY*DAY-DAY
    rows = sorted((r for r in observations if r.end_ns <= cutoff), key=lambda r:r.end_ns)[-31:]
    if len(rows) != 31 or any(r.end_ns % DAY for r in rows):
        raise ValueError('METHOD_A_W30_MISSING')
    for i,r in enumerate(rows):
        finite(r.btc,r.sol)
        if min(r.btc,r.sol)<=0 or r.available_ns<r.end_ns+MINUTE or r.available_ns>decision_ns:
            raise ValueError('METHOD_A_D1_UNAVAILABLE')
        if i and r.end_ns-rows[i-1].end_ns != DAY:
            raise ValueError('METHOD_A_D1_GAP_OR_DUPLICATE')
    returns = tuple((r.btc/p.btc-1,r.sol/p.sol-1) for p,r in zip(rows,rows[1:]))
    mb = sum((x for x,_ in returns),D(0))/30
    ms = sum((y for _,y in returns),D(0))/30
    vb = sum(((x-mb)**2 for x,_ in returns),D(0))/29
    vs = sum(((y-ms)**2 for _,y in returns),D(0))/29
    cov = sum(((x-mb)*(y-ms) for x,y in returns),D(0))/29
    if vb<=0 or vs<=0 or cov<=0:
        raise ValueError('METHOD_A_UNHEDGEABLE_COEFFICIENT')
    beta=cov/vb; sb=vb.sqrt(); ss=vs.sqrt();rho=cov/(sb*ss)
    fb=[]; ready=max(r.available_ns for r in rows)
    for leg in ('BTC','SOL'):
        rates=sorted((r for r in funding if r.leg==leg and rows[0].end_ns<r.effective_ns<=rows[-1].end_ns),key=lambda r:r.effective_ns)
        previous=rows[0].end_ns
        if not rates:raise ValueError('METHOD_A_FUNDING_MISSING')
        for r in rates:
            finite(r.rate)
            if r.interval_ns<=0 or r.effective_ns-previous!=r.interval_ns or r.available_ns<r.effective_ns or r.available_ns>decision_ns:
                raise ValueError('METHOD_A_FUNDING_GAP_OR_UNAVAILABLE')
            previous=r.effective_ns;ready=max(ready,r.available_ns)
        if previous!=rows[-1].end_ns:raise ValueError('METHOD_A_FUNDING_INCOMPLETE')
        # Evaluate every event-aligned24h window. A full history is present;
        # both open/closed interval conventions have the same bound at edges.
        endpoints={rows[0].end_ns+DAY,rows[-1].end_ns}
        endpoints.update(r.effective_ns for r in rates if r.effective_ns>=rows[0].end_ns+DAY)
        fb.append(max(sum((abs(r.rate) for r in rates if end-DAY<r.effective_ns<=end),D(0)) for end in endpoints))
    return Features(rows[0].end_ns,rows[-1].end_ns,ready,beta,rho,sb,ss,
        max(abs(x) for x,_ in returns),max(abs(y-beta*x) for x,y in returns),*fb)


@dataclass(frozen=True)
class State:
    btc: D  # Signed actual native quantity.
    sol: D
    equity: D
    peak: D
    pb: D
    ps: D

    def __post_init__(self):
        finite(self.btc,self.sol,self.equity,self.peak,self.pb,self.ps)
        if min(self.pb,self.ps,self.peak)<=0 or self.peak<self.equity:
            raise ValueError('METHOD_A_UNKNOWN_STATE')

    @property
    def cushion(self):return self.equity-self.peak/D(2)


@dataclass(frozen=True)
class Evaluation:
    gross: D
    loss: D
    margin_pass: bool
    worst_deficit: D


@exact_algebra
def evaluate(state, features, margin_at, *, unpaid=D(0)):
    """margin_at(leg,absqty,scenario_price) is pure frozen-venue IM/MM.

    Scenario equity includes signed mark change and prospective paid cost.
    Current native getters are checked separately at zero shock by the adapter.
    """
    finite(unpaid)
    if unpaid<0:raise ValueError('METHOD_A_NEGATIVE_COST')
    gross=loss=D(0); margin_pass=True
    for b,s in features.shocks():
        pb=state.pb*(1+b);ps=state.ps*(1+s)
        if min(pb,ps)<=0:raise ValueError('METHOD_A_NONPOSITIVE_SCENARIO')
        pnl=state.btc*state.pb*b+state.sol*state.ps*s
        exit_cost=(abs(state.btc)*pb+abs(state.sol)*ps)*(TAKER+RESERVE)
        funding=abs(state.btc)*pb*features.fund_b+abs(state.sol)*ps*features.fund_s
        gross=max(gross,-pnl)
        loss=max(loss,-pnl+exit_cost+funding+unpaid)
        ib,mb=margin_at('BTC',abs(state.btc),pb)
        is_,ms=margin_at('SOL',abs(state.sol),ps)
        finite(ib,mb,is_,ms)
        if min(ib,mb,is_,ms)<0:raise ValueError('METHOD_A_NEGATIVE_MARGIN')
        es=state.equity+pnl-unpaid
        margin_pass &= es>mb+ms and es>=ib+is_
    return Evaluation(gross,loss,margin_pass,loss-state.cushion)


@dataclass(frozen=True)
class Liability:
    """One CID/generation max old/new native leaves; PendingCancel stays live.

    filled outcomes are clipped for reduce-only and can never cross flat.
    Cost is conservative unpaid future fee+execution reserve per executed unit.
    """
    identity: str
    leg: str
    side: int
    lots: int
    lot: D
    reduce_only: bool
    cost_per_unit: D

    def __post_init__(self):
        finite(self.lot,self.cost_per_unit)
        if not self.identity or self.leg not in ('BTC','SOL') or self.side not in (-1,1) or type(self.lots)is not int or self.lots<0 or self.lot<=0 or self.cost_per_unit<0:
            raise ValueError('METHOD_A_UNKNOWN_LIABILITY')


@dataclass(frozen=True)
class Envelope:
    safe: bool
    states: int
    worst_deficit: D
    margin_pass: bool


@exact_algebra
def execution_envelope(state,features,liabilities,margin_at):
    """Exact finite native-lot outcomes, including every independent opening.

    Reducing orders can occur before/after opening fills. Both orders of all
    per-leg opening/reduction totals are included; clipping never gives credit
    for a reducing order which could have arrived before the held inventory.
    All generation liabilities must already be deduplicated by native CID.
    """
    if len({x.identity for x in liabilities})!=len(liabilities):raise ValueError('METHOD_A_DUPLICATE_GENERATION')
    worst=None; safe=True; count=0; mm=True
    for fills in product(*(range(x.lots+1) for x in liabilities)):
        for ordering in (False,True):
            qty={'BTC':state.btc,'SOL':state.sol};cost=sum((x.lot*x.lots*x.cost_per_unit for x in liabilities if not x.reduce_only),D(0))
            for reduce_first in ((True,False) if ordering else (False,True)):
                for order,lots in zip(liabilities,fills):
                    if order.reduce_only!=reduce_first:continue
                    amount=order.lot*lots
                    held=qty[order.leg]
                    if order.reduce_only:
                        amount=min(amount,abs(held)) if held*order.side<0 else D(0)
                    qty[order.leg]+=order.side*amount
                    if order.reduce_only:cost+=amount*order.cost_per_unit
            outcome=State(qty['BTC'],qty['SOL'],state.equity,state.peak,state.pb,state.ps)
            result=evaluate(outcome,features,margin_at,unpaid=cost)
            count+=1;worst=result.worst_deficit if worst is None else max(worst,result.worst_deficit)
            mm &= result.margin_pass
            safe &= result.worst_deficit<=0 and result.margin_pass and state.cushion>0
    return Envelope(safe,count,worst,mm)


@exact_algebra
def hedge_target(state,features,was_on,active_selection):
    if state.cushion<=0:return False,None,D(0)
    # Bands are BTC-only, independent of the actual-held hedge.
    btc_only=State(state.btc,D(0),state.equity,state.peak,state.pb,state.ps)
    # Gross+reserves requires no venue assumptions; margin deliberately unused.
    ev=evaluate(btc_only,features,lambda leg,q,p:(D(0),D(0)))
    u=ev.loss/state.cushion
    on=active_selection and (u>=D('.70') or was_on and u>D('.50'))
    band='HIGH' if on and u>=D('.85') else 'MEDIUM' if on else None
    target=abs(state.btc)*state.pb*features.sigma_b/features.sigma_s/state.ps*(D(1) if band=='HIGH' else D('.5')) if on else D(0)
    return on,band,target


@exact_algebra
def useful_hedge(state,features,target):
    finite(target)
    if target<=0 or not state.btc:return False,D(0),D(0)
    sign=D(1) if state.btc>0 else D(-1)
    unhedged=State(state.btc,D(0),state.equity,state.peak,state.pb,state.ps)
    hedged=State(state.btc,-sign*target,state.equity,state.peak,state.pb,state.ps)
    margin=lambda leg,q,p:(D(0),D(0))
    improvement=evaluate(unhedged,features,margin).gross-evaluate(hedged,features,margin).gross
    # Full incremental SOL entry + worst scenario exit/funding, once only.
    cost=target*state.ps*(TAKER+RESERVE)+max(target*state.ps*(1+s)*(TAKER+RESERVE+features.fund_s) for _,s in features.shocks())
    return improvement>0 and improvement>=2*cost,improvement,cost


def lawful_residual(*,original,filled,retired,now,expiry,off_since,drained,parent_live,known_off):
    finite(original,filled,retired)
    if min(original,filled,retired)<0 or filled+retired>original:raise ValueError('METHOD_A_UNKNOWN_ORIGINAL_RIGHT')
    if not(known_off and drained and parent_live and off_since is not None and now>=off_since+MINUTE and now<expiry):return D(0)
    return original-filled-retired


@exact_algebra
def tier_partition_envelope(state,features,liabilities,margin_at,tier_boundaries):
    """Conservative finite reduction of every native-lot partial-fill state.

    Proof: per leg write q=h+o-r with same-side openings0<=o<=O,
    reductions0<=r<=R and q>=0 (native reduce-only clipping). Thus q ranges
    [max(0,h-R),h+O]. Entry reserve for all O leaves is fixed. At fixed q,
    the largest possible reduction cost is attained at r=min(R,h+O-q),
    allocated to descending exact per-CID unitcost. This piecewise affine
    frontier is exact, with breaks at cumulative expensive-CID capacities.
    Opening paid-cost plus still-unpaid entryreserve is the constant sum(ci*Oi).
    Actual fills rebuild E/leaves and remove their previous reserve. There is
    no favorable fillprice credit; H is the current native coherent peak.

    Gross shock, exit/funding and conservative cost are affine between q=0,
    q=h+O-cumulative_R_j and every scenario tier cap/MM-zero. Frozen tier IM is affine
    within each tier; max(0,notional*MM-deduction) adds only MM-zero. Therefore
    every inequality is affine on each two-leg rectangle. Integer lattice
    extrema are at adjacent floor/ceil lots at those boundaries or interval
    endpoints. Cartesian evaluation of this finite partition covers all
    corners, including tier discontinuities; no global convexity is assumed.

    tier_boundaries(leg,scenario_price) MUST return ALL cap/MM-zero quantities
    from the exact frozen policy as Fractions, including its finite maximum
    tier cap. Already-rounded cap/price Decimal quotients are not qualified.
    Unknown or out-of-range margin still raises rather than passing.
    """
    if len({x.identity for x in liabilities})!=len(liabilities):raise ValueError('METHOD_A_DUPLICATE_GENERATION')
    leg_data=[]
    for leg,held,price in (('BTC',state.btc,state.pb),('SOL',state.sol,state.ps)):
        orders=[x for x in liabilities if x.leg==leg]
        opening=[x for x in orders if not x.reduce_only]
        signs={x.side for x in opening}
        if held:sign=1 if held>0 else -1
        elif signs:sign=next(iter(signs))
        else:sign=1
        if any(x!=sign for x in signs):raise ValueError('METHOD_A_CROSSING_OPENING_LIABILITY')
        if orders:
            lot=orders[0].lot
            if any(x.lot!=lot for x in orders):raise ValueError('METHOD_A_MIXED_NATIVE_LOT')
        else:
            # Without orders q is fixed; no invented lattice is necessary.
            leg_data.append((leg,sign,(abs(held),),D(0),(),D(0),abs(held)));continue
        ratio=abs(held)/lot
        if ratio!=ratio.to_integral_value():raise ValueError('METHOD_A_NONINTEGER_HELD_LOTS')
        h=abs(held);o=sum((x.lots*x.lot for x in opening),D(0))
        r=sum((x.lots*x.lot for x in orders if x.reduce_only and x.side==-sign),D(0))
        entry=sum((x.lots*x.lot*x.cost_per_unit for x in opening),D(0))
        frontier=tuple(sorted(((x.lots*x.lot,x.cost_per_unit,x.identity) for x in orders if x.reduce_only and x.side==-sign),key=lambda x:(-x[1],x[2])))
        low=max(D(0),h-r);high=h+o
        cuts={low,high};cumulative=D(0)
        for capacity,unitcost,identity in frontier:
            cumulative+=capacity;cuts.add(h+o-cumulative)
        for b,s in features.shocks():
            scenario=price*(1+(b if leg=='BTC' else s))
            if scenario<=0:raise ValueError('METHOD_A_NONPOSITIVE_SCENARIO')
            cuts.update(tier_boundaries(leg,scenario))
        points={low,high}
        for cut in cuts:
            # Callback returns exact Fraction(cap)/Fraction(scenario_price),
            # not an already-rounded Decimal quotient. Integer crossproducts
            # preserve floor/ceil even immediately next to a native lot.
            ratio=Fraction(cut)/Fraction(lot)
            lower=ratio.numerator//ratio.denominator
            upper=-((-ratio.numerator)//ratio.denominator)
            for count in (lower-1,lower,upper,upper+1):
                value=D(count)*lot
                if low<=value<=high:points.add(value)
        leg_data.append((leg,sign,tuple(sorted(points)),entry,frontier,r,h+o))
    worst=None;safe=True;count=0;mm=True
    for qb,qs in product(leg_data[0][2],leg_data[1][2]):
        cost=D(0)
        for data,q in zip(leg_data,(qb,qs)):
            _,_,_,entry,frontier,r,maximum=data
            remaining=min(r,max(D(0),maximum-q));cost+=entry
            for capacity,unitcost,identity in frontier:
                amount=min(remaining,capacity);cost+=amount*unitcost;remaining-=amount
            if remaining:raise ValueError('METHOD_A_REDUCTION_FRONTIER_INCOMPLETE')
        outcome=State(leg_data[0][1]*qb,leg_data[1][1]*qs,state.equity,state.peak,state.pb,state.ps)
        result=evaluate(outcome,features,margin_at,unpaid=cost)
        count+=1;worst=result.worst_deficit if worst is None else max(worst,result.worst_deficit)
        mm &= result.margin_pass
        safe &= result.worst_deficit<=0 and result.margin_pass and state.cushion>0
    return Envelope(safe,count,worst,mm)
