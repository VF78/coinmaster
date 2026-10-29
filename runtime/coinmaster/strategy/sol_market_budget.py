"""Default-off SOL scenario budget. Pure Decimal lattice solver, no PnL engine."""
from dataclasses import dataclass
from decimal import Decimal as D, ROUND_CEILING, ROUND_FLOOR

F=D('.0005')
@dataclass(frozen=True)
class BudgetResult:
    status: str
    target_qty: D
    stress: D
    lower_qty: D | None = None
    upper_qty: D | None = None

def stress(x, *, b, held, a, sol_a, beta, side):
    if beta is None:
        market=abs(b)*a+max(sol_a,D('.02'))*x
    else:
        market=a*abs(b+beta*side*x)+max(sol_a-abs(beta)*a,D('.02'))*x
    return market+F*(abs(b)+x+abs(x-held))

def solve_budget(*,b,held_qty,price,step,max_qty,a,sol_a,beta,side,budget,
                 min_qty=D(0),min_notional=D(0)):
    """Largest feasible legal position; otherwise min-risk reachable reduction.

    Position legality includes an unchanged held position and flat; any delta
    must meet native minimum order quantity/notional. Pending reductions are
    never supplied as held inventory or released collateral.
    """
    vals=(b,held_qty,price,step,max_qty,a,sol_a,budget,min_qty,min_notional)
    if (any(not isinstance(v,D) or not v.is_finite() for v in vals)
        or (beta is not None and (not isinstance(beta,D) or not beta.is_finite()))
        or side not in (-1,1) or min(price,step,a,sol_a)<=0
        or min(held_qty,max_qty,min_qty,min_notional)<0):
        raise ValueError('SOL_B_BUDGET_INPUT_INVALID')
    held=held_qty*price;top=(max_qty/step).to_integral_value(rounding=ROUND_FLOOR)*step
    unit=price*step
    args=dict(b=b,held=held,a=a,sol_a=sol_a,beta=beta,side=side)
    value=lambda q:stress(q*price,**args)
    cuts={D(0),top*price}
    if D(0)<held<top*price:cuts.add(held)
    k=beta*side if beta is not None else D(0)
    if k and D(0)<-b/k<top*price:cuts.add(-b/k)
    cuts=sorted(cuts);intervals=[]
    if len(cuts)==1 and value(D(0))<=budget:intervals=[(D(0),D(0))]
    for lo,hi in zip(cuts,cuts[1:]):
        gl,gh=stress(lo,**args),stress(hi,**args)
        if gl<=budget and gh<=budget:intervals.append((lo,hi))
        elif gl<=budget:intervals.append((lo,lo+(budget-gl)*(hi-lo)/(gh-gl)))
        elif gh<=budget:intervals.append((hi-(budget-gh)*(hi-lo)/(gl-gh),hi))
    minimum=max(min_qty,min_notional/price)
    def legal(q):
        if q<0 or q>top or q%step:return False
        delta=abs(q-held_qty)
        return delta==0 or delta>=minimum
    candidates=set()
    def around(x):
        for rounding in (ROUND_FLOOR,ROUND_CEILING):
            candidates.add((x/unit).to_integral_value(rounding=rounding)*step)
    for lo,hi in intervals:around(lo);around(hi)
    # Legal-delta gaps can cut a feasible interval; include their boundaries.
    for q in (held_qty,held_qty-minimum,held_qty+minimum):around(q*price)
    feasible=[q for q in candidates if legal(q) and value(q)<=budget]
    if feasible:
        return BudgetResult('FEASIBLE',max(feasible),value(max(feasible)),min(feasible),max(feasible))
    candidates={D(0),held_qty}
    for x in cuts:around(x)
    for q in (held_qty-minimum,held_qty+minimum):around(q*price)
    reachable=[q for q in candidates if legal(q) and q<=held_qty]
    if not reachable:
        return BudgetResult('UNATTAINABLE',held_qty,value(held_qty))
    q=min(reachable,key=lambda q:(value(q),-q))
    return BudgetResult('UNATTAINABLE',q,value(q))

class ClosedD1Wilder14:
    """Same TR/14 seed and Wilder recursion as existing hedge_band D1 ATR."""
    def __init__(self):
        self.ns=None;self.previous=None;self.tr=[];self.atr=None;self.valid=True
    def append(self,ns,high,low,close):
        high,low,close=map(lambda x:D(str(x)),(high,low,close))
        if self.ns is not None and ns<=self.ns:return
        if (self.ns is not None and ns-self.ns!=86_400_000_000_000
            or not all(v.is_finite() and v>0 for v in (high,low,close)) or not low<=close<=high):
            self.valid=False
        if self.previous is not None:
            tr=max(high-low,abs(high-self.previous),abs(low-self.previous))
            if self.atr is not None:self.atr=(13*self.atr+tr)/14
            else:
                self.tr.append(tr)
                if len(self.tr)==14:self.atr=sum(self.tr)/14
        self.ns=ns;self.previous=close

def native_account_identity(account):
    """Actual account publication identity; timestamp alone is not a revision."""
    event=getattr(account,'last_event',None)
    identity=getattr(event,'id',None) or getattr(event,'event_id',None)
    return (str(identity),event.ts_event) if identity is not None else None

class SolMarketBudgetResearch:
    def _sol_b_init(self):
        self.sol_market_budget_audit=[];self._sol_b_armed=False;self._sol_b_snapshot=None;self._sol_b_last_held=None
        self._sol_b_atr=[ClosedD1Wilder14(),ClosedD1Wilder14()]
        if not self.config.research_sol_market_budget_b:return
        if not self.config.research_residual_recovery or not callable(self.config.research_sol_market_budget_high_water_reader):
            raise ValueError('SOL_B_REQUIRES_COHERENT_NATIVE_HWM')
        for ns,bh,bl,bc,sh,sl,sc in self.config.research_sol_market_budget_daily_seed:
            self._sol_b_daily(ns,bh,bl,bc,sh,sl,sc)

    def _sol_b_daily(self,ns,bh,bl,bc,sh,sl,sc):
        if not self.config.research_sol_market_budget_b:return
        for state,values in zip(self._sol_b_atr,((bh,bl,bc),(sh,sl,sc))):state.append(ns,*values)

    def _sol_b_log(self,event,ns,**kw):
        self.sol_market_budget_audit.append(dict(event=event,timestamp_ns=ns,armed=self._sol_b_armed,**kw))

    def _sol_b_orders(self):
        # Cache OPEN and INFLIGHT overlap; native ID is the only identity.
        return list({str(o.client_order_id):o for o in self.cache.orders_open()+self.cache.orders_inflight()
                     if o.instrument_id==self.config.sol_id and not o.is_closed}.values())

    def _sol_b_observe(self,equity,ns,source,epoch,details,*,high_water=None,source_marks=None,account_identity=None):
        if not self.config.research_sol_market_budget_b:return
        raw=high_water
        if raw is None or source_marks is None or account_identity is None:self._sol_b_snapshot=None;return
        high=D(str(raw));equity=D(str(equity))
        if not high.is_finite() or high<=0 or not equity.is_finite():self._sol_b_snapshot=None;return
        rows={row['instrument_id']:row for row in details}
        positions={p.instrument_id:p for p in self.cache.positions_open()}
        marks={};identity={};pnl={}
        for iid in (self.config.btc_id,self.config.sol_id):
            raw_mark=source_marks.get(iid)
            if raw_mark is None:self._sol_b_snapshot=None;return
            marks[iid]=self.cache.instrument(iid).make_price(raw_mark).as_decimal()
        # Frozen source OHLC comes from the existing coherent native recorder.
        for iid,p in positions.items():
            row=rows.get(str(iid))
            if row is None:self._sol_b_snapshot=None;return
            inst=self.cache.instrument(iid);mark=marks[iid]
            if inst.make_price(D(row['mark_ohlc']['close'])).as_decimal()!=mark:self._sol_b_snapshot=None;return
            identity[iid]=(str(p.id),p.quantity.as_decimal(),p.is_long)
            pnl[iid]=p.unrealized_pnl(inst.make_price(mark)).as_decimal()
        dd=1-equity/high
        if (dd>=D('.40') and -pnl.get(self.config.sol_id,D(0))>max(D(0),equity-D('.50')*high)):
            if not self._sol_b_armed:
                self._sol_b_armed=True;self._sol_b_log('ARMED',ns,E=str(equity),H=str(high),source_ns=source,fill_epoch=epoch)
        if self._sol_b_armed and self.config.sol_id not in positions and not self._sol_b_orders() and dd<D('.40'):
            self._sol_b_armed=False;self._sol_b_log('CLEARED_NATIVE_FLAT',ns)
        self._sol_b_snapshot=dict(E=equity,H=high,source=source,receipt=ns,epoch=epoch,
                                  positions=identity,marks=marks,account_identity=account_identity)

    def _sol_b_current(self,ns):
        c=self._sol_b_snapshot
        if not c or not c['source']<c['receipt']<=ns or ns-c['source']>self.config.max_mark_age_ns or c['epoch']!=self._c1_fill_epoch:return None
        account=self.cache.account_for_venue(self.config.btc_id.venue)
        if account is None or account.last_event.ts_event>c['source'] or native_account_identity(account)!=c['account_identity']:return None
        actual={p.instrument_id:(str(p.id),p.quantity.as_decimal(),p.is_long) for p in self.cache.positions_open()}
        if actual!=c['positions']:return None
        last=self._last_accepted_session
        available=int(self._bars[-1].available_at.timestamp()*1_000_000_000) if self._bars else None
        if last is None or last>ns or available is None or available>ns or any(not x.valid or x.ns!=last or x.atr is None or x.atr<=0 for x in self._sol_b_atr):return None
        return c

    def _sol_b_result(self,c,demand,side):
        inst=self.cache.instrument(self.config.sol_id);price=c['marks'][self.config.sol_id]
        held=c['positions'].get(self.config.sol_id);btc=c['positions'].get(self.config.btc_id)
        qty=held[1] if held else D(0)
        b=btc[1]*c['marks'][self.config.btc_id]*(1 if btc[2] else -1) if btc else D(0)
        beta=self._current_signals[-1].beta if self._current_signals else None
        if beta is not None and not D(str(beta)).is_finite():beta=None
        return solve_budget(b=b,held_qty=qty,price=price,step=inst.size_increment.as_decimal(),max_qty=qty+demand,
            a=2*self._sol_b_atr[0].atr/c['marks'][self.config.btc_id],sol_a=2*self._sol_b_atr[1].atr/price,
            beta=D(str(beta)) if beta is not None else None,side=side,budget=c['E']-D('.48')*c['H'],
            min_qty=inst.min_quantity.as_decimal() if inst.min_quantity is not None else D(0),
            min_notional=inst.min_notional.as_decimal() if inst.min_notional is not None else D(0))

    def _sol_b_increase_qty(self,qty,side,ns):
        if not self.config.research_sol_market_budget_b:return qty
        c=self._sol_b_current(ns)
        # Missing authoritative input fails closed even before activation.
        if c is None:
            self._sol_b_log('UNKNOWN_INCREASE_DENIED',ns,original_quantity=str(qty));return D(0)
        if self._sol_b_orders():
            self._sol_b_log('INFLIGHT_INCREASE_DENIED',ns,original_quantity=str(qty));return D(0)
        held=c['positions'].get(self.config.sol_id)
        if held and (1 if held[2] else -1)!=side:return D(0)
        if not self._sol_b_armed:return qty
        result=self._sol_b_result(c,qty,side);current=held[1] if held else D(0)
        admitted=max(D(0),result.target_qty-current) if result.status=='FEASIBLE' else D(0)
        self._sol_b_log('INCREASE_BUDGET',ns,original_quantity=str(qty),quantity=str(admitted),
                        status=result.status,target=str(result.target_qty),stress=str(result.stress),
                        E=str(c['E']),H=str(c['H']),source_ns=c['source'],receipt_ns=c['receipt'],fill_epoch=c['epoch'])
        return admitted

    def _sol_b_quote(self,tick,ns):
        if not self.config.research_sol_market_budget_b or tick.instrument_id!=self.config.sol_id:return False
        c=self._sol_b_current(ns);orders=self._sol_b_orders()
        if c is not None and tick.ts_event<c['receipt']:c=None
        # Cancel actual outstanding increases when unknown or no longer covered.
        increases=[o for o in orders if not o.is_reduce_only]
        unsafe=c is None
        if c is not None and self._sol_b_armed and increases:
            p=c['positions'].get(self.config.sol_id);held=p[1] if p else D(0)
            sides={1 if o.is_buy else -1 for o in increases}
            demand=sum((o.leaves_qty.as_decimal() for o in increases),D(0))
            side=(1 if p[2] else -1) if p else next(iter(sides))
            r=self._sol_b_result(c,demand,side)
            # Reserve WHOLE leaves, never pending reduction credit.
            unsafe=len(increases)>1 or sides!={side} or r.status!='FEASIBLE' or r.target_qty<held+demand
        if unsafe:
            for o in increases:
                if not o.is_pending_cancel:
                    self._sol_b_log('CANCEL_INCREASE',ns,reason='UNKNOWN' if c is None else 'WHOLE_LEAVES_OUTSIDE_BUDGET')
                    self.cancel_order(o)
            return False
        if not self._sol_b_armed or orders:return False
        if self._forced_close_reason or self._liquidating or self._mandatory_sol_exit is not None or self._has_owned_sol_exit():return False
        if any(i.action in ('SOL_EXIT','SOL_HALF_EXIT') for i,_,_ in self._queued_intents):return False
        p=self._hb_position(self.config.sol_id);ep=self._domain.episode
        if p is None or ep is None:return False
        r=self._sol_b_result(c,D(0),1 if p.is_long else -1)
        qty=p.quantity.as_decimal()-r.target_qty
        key=(r.status,r.target_qty,p.quantity.as_decimal())
        if key!=self._sol_b_last_held:
            self._sol_b_log('HELD_BUDGET',ns,status=r.status,target=str(r.target_qty),stress=str(r.stress),
                            E=str(c['E']),H=str(c['H']),source_ns=c['source'],receipt_ns=c['receipt'],fill_epoch=c['epoch'])
            self._sol_b_last_held=key
        if qty<=0:return False
        # Existing domain/native order owner handles actual fills, terminals,
        # reductions and C1 revocation. Never infer completion from a target.
        if self.config.research_residual_recovery:self._c1_revoke(ns,'SOL_MARKET_BUDGET_REDUCTION')
        if self._c1_own_pending():return True
        intent=self._domain._intent(ep,'SOL_EXIT',-1 if p.is_long else 1,None,
                                  quantity=float(qty),reason='SOL_MARKET_BUDGET_B')
        self._submit_intent(intent,float(tick.bid_price),float(tick.ask_price),ep.fixed_sigma,len(self._bars)-1,ts_now=ns)
        return True
