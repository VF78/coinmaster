from datetime import datetime,UTC,timedelta
from decimal import Decimal as D
from math import exp
import json
import pytest
from nautilus_trader.model.enums import OrderSide,TimeInForce,BarAggregation
from coinmaster.domain.wave_overlay import Episode,DailyBar,Features
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP
from test_native_split_cover import cfg
from test_native_episode_risk import NativeProbe,tick,run_ticks,marks
from test_native_btc_sizing import prepare_day
from test_native_h1_b1 import confirmation_types,bar
from test_native_sol_risk_first import engine


def config(enabled=True):
    return cfg(True).__replace__(research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,
        research_alpha_cushion=enabled,research_confirmation_bars=confirmation_types() if enabled else ())


def history(s):
    rows=[];b=v=100.;end=datetime(1970,1,1,tzinfo=UTC)
    for n in range(91):
        ret=(.01,-.01,.02,-.02,.005,-.005)[n%6];b*=exp(ret);v*=exp(2*ret)
        close=end-timedelta(days=90-n)
        rows.append(DailyBar(close-timedelta(days=1),close,close,b,b,v))
    s._bars=rows


class Observed(NativeProbe):
    def on_quote_tick(self,q):
        if self._alpha_enabled():self._alpha_observe_equity(self._v3_equity(),q.ts_event)
        super().on_quote_tick(q)
        action=getattr(self,'btc_action',None)
        if action is not None and q.instrument_id==BTC_PERP.id:
            self.btc_action=None;action(q)
        action=getattr(self,'sol_action',None)
        if action is not None and q.instrument_id==SOL_PERP.id:
            self.sol_action=None;action(q)


def setup(side=1,probe=Observed,qty=100):
    s=probe(config());e=engine(s)
    run_ticks(e,[tick(BTC_PERP,1),tick(SOL_PERP,1)])
    prepare_day(s,2,side);history(s);marks(s,2)
    ep=s._domain.episode=Episode('alpha-native',side,10000,1,wave_levels=(10,20,30),h=10000)
    i=s._domain._intent(ep,'BTC_ENTRY',side,None,quantity=qty)
    s._submit_intent(i,100,100,.01,0,ts_now=2)
    run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,5,'99' if side==1 else '101'),tick(SOL_PERP,6)])
    return s,e,ep


def advance(s,e,ts,btc='100',sol='100',size='1000'):
    marks(s,ts,btc,sol);run_ticks(e,[tick(BTC_PERP,ts,btc),tick(SOL_PERP,ts,sol,size=size)])


def deficit(s,e,ts=10,size='1000'):
    ep=s._domain.episode
    marks(s,ts,'200' if ep.side==1 else '1','100');s._alpha_observe_equity(s._v3_equity(),ts)
    advance(s,e,ts+1,size=size)


def original(s,e,ep,qty,ts=30,price='100',size='1000'):
    ep.sol_rights.add(0);ep.sol_right_fraction[0]=1
    i=s._domain._intent(ep,'SOL_ADD',-ep.side,0,quantity=qty,reason='SOL_ADD')
    s.sol_action=lambda q:s._submit_intent(i,float(q.bid_price),float(q.ask_price),.02,len(s._bars)-1,ts_now=q.ts_event)
    run_ticks(e,[tick(SOL_PERP,ts,price,size=size)]);return i


def close(s,e,ts=1000):
    ep=s._domain.episode
    i=s._domain._intent(ep,'CLOSE_ALL',0,None,reason='REGIME') if ep else None
    s._begin_forced_close('REGIME',i)
    for t in range(ts,ts+5):advance(s,e,t)
    assert not e.cache.positions_open() and not e.cache.orders_open() and not s._pending_by_order
    assert s._domain.episode is None


@pytest.mark.parametrize('side',[1,-1])
def test_native_beta_freeze_daily_stress_no_future_and_global_peak_across_episode(side):
    s,e,ep=setup(side)
    try:
        f=s._alpha_cycle;assert abs(f['beta']-D('2.0'))<D('1e-12') and f['beta_ns']==3
        assert s._alpha_coefficients(6)['stress_ns']==0
        before=f['beta'];last=s._bars[-1];tomorrow=last.close_time+timedelta(days=1)
        s._bars.append(DailyBar(last.close_time,tomorrow,tomorrow,1,1000,1))
        assert s._alpha_coefficients(10)['stress_ns']==0 and f['beta']==before
        oldpeak=s._alpha_peak;deficit(s,e);assert s._alpha_peak>oldpeak
        peak=s._alpha_peak;assert s._alpha_cycle['beta']==before
        close(s,e);assert s._alpha_peak==peak
        assert any(x['event']=='BUDGET' for x in s.alpha_cushion_audit)
        json.dumps(s.alpha_cushion_audit)
    finally:e.end();e.dispose()


@pytest.mark.parametrize('side',[1,-1])
def test_actual_deficit_native_partial_best_effort_lots_and_BTC_flat_retains_permission(side):
    s,e,ep=setup(side)
    try:
        deficit(s,e,size='.3');assert any(x['event']=='BUDGET' and x['status']=='UNHEDGEABLE' for x in s.alpha_cushion_audit)
        assert sum(D(x['qty']) for x in s.fill_audit if x['instrument'].startswith('SOL'))==D('.3')
        advance(s,e,12);held=next(p for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)
        assert held.quantity.as_decimal()==s._alpha_cycle['target'] and held.quantity.as_decimal()>D('.3')
        btc=next(p for p in e.cache.positions_open() if p.instrument_id==BTC_PERP.id)
        s.submit_order(s.order_factory.market(BTC_PERP.id,OrderSide.SELL if side==1 else OrderSide.BUY,BTC_PERP.make_qty(btc.quantity.as_decimal()),time_in_force=TimeInForce.IOC,reduce_only=True))
        advance(s,e,20);advance(s,e,21)
        assert not e.cache.positions_open() and not e.cache.orders_open() and not s._pending_by_order
        assert s._domain.episode is ep and s._alpha_cycle['target']==0
        original(s,e,ep,1,22);assert not e.cache.positions_open()  # Explicit risk-policy BTCflat override.
        close(s,e,30)
    finally:e.end();e.dispose()


def test_generalized_loss_overhedge_same_side_and_min_step_uses_absolute_residual():
    s,e,ep=setup()
    try:
        s._alpha_coefficients(6);s._alpha_cycle.update(beta=D(2),a=D('.1'),u=D('.02'))
        assert s._alpha_L(D(150),D(100),D(3))==D(26)
        assert s._alpha_L(D(-50),D(100),D(3))==D(24)
        assert s._alpha_L(D(50),D(100),D(3))==D(4)
        deficit(s,e);b=[x for x in s.alpha_cushion_audit if x['event']=='BUDGET'][-1]
        step=SOL_PERP.size_increment.as_decimal()
        assert all(D(x['quantity'])%step==0 for x in b['grid'])
        assert not b['actual_transition_budget_satisfied']
    finally:e.end();e.dispose()


def test_existing_Q2_native_margin_reservation_and_risk_cost_are_not_starved():
    s,e,ep=setup()
    try:
        p=s._split_parent;p.update(closed=False,quantity=D(100),filled=D(50),cancelled=D(0))
        assert s._split_cover_margin_reserve(BTC_PERP.id,D(50),10)==100
        cost,q2=s._alpha_cost(D(10),D(0),D(50),D(100),D(100));assert q2==50
        expected=D(150)*100*D(str(BTC_PERP.taker_fee))+D(20)*100*D(str(SOL_PERP.taker_fee))
        assert cost==expected
        p.update(closed=True,filled=D(100))
    finally:e.end();e.dispose()


def test_unknown_transport_late_native_fill_after_BTC_flat_is_closed_no_overbuy():
    class Transport(Observed):
        hold=False;waiting=None;release=False
        def submit_order(self,o,*args,**kw):
            if self.hold and o.instrument_id==SOL_PERP.id and not o.is_reduce_only:
                self.hold=False;self.waiting=o;return
            return super().submit_order(o,*args,**kw)
        def on_quote_tick(self,q):
            super().on_quote_tick(q)
            if self.release and q.instrument_id==SOL_PERP.id:self.release=False;super().submit_order(self.waiting)
    s,e,ep=setup(probe=Transport)
    try:
        s.hold=True;deficit(s,e);assert s.waiting is not None
        assert e.cache.order(s.waiting.client_order_id) is None
        count=len(s._pending_by_order);advance(s,e,12);assert len(s._pending_by_order)==count
        btc=next(p for p in e.cache.positions_open() if p.instrument_id==BTC_PERP.id)
        s.submit_order(s.order_factory.market(BTC_PERP.id,OrderSide.SELL,BTC_PERP.make_qty(btc.quantity.as_decimal()),time_in_force=TimeInForce.IOC,reduce_only=True))
        advance(s,e,20);s.release=True;run_ticks(e,[tick(SOL_PERP,21,size='.3')]);advance(s,e,22)
        assert not e.cache.positions_open() and not e.cache.orders_open() and not s._pending_by_order
        assert any(x['event']=='UNKNOWN' for x in s.alpha_cushion_audit)
        close(s,e,30)
    finally:e.end();e.dispose()


def test_risk_retired_unfilled_authorization_separate_from_native_fill_credit():
    s,e,ep=setup()
    try:
        c=s._conditional_state(10);ep.sol_rights.add(0)
        i=s._domain._intent(ep,'SOL_ADD',-1,0,quantity=10,reason='SOL_ADD')
        c['adds']=[dict(intent=i,remaining=D(10),sigma=.02,index=90,price=D(100))];c['original_target']=D(10)
        s._alpha_retire(c,D(0),10)
        assert ep.sol_risk_retired_notional[0]==1000
        assert ep.sol_add_filled_notional=={} and ep.sol_ownership_transfer_credit=={} and ep.sol_first_owned_at is None
        assert i.id not in ep.pending and not c['adds']
        assert s._alpha_cycle['target']==0
    finally:e.end();e.dispose()


def test_release_requires_fresh_opposite_closed15m_after_last_increase_and_hysteresis():
    s,e,ep=setup()
    try:
        f=s._alpha_cycle;f['last_increase_ns']=10
        kind=next(k for k in s.config.research_confirmation_bars if k.instrument_id==SOL_PERP.id and k.spec.aggregation==BarAggregation.MINUTE)
        run_ticks(e,[tick(BTC_PERP,9)]);s._alpha_bar(bar(kind,9,100,101,99))
        run_ticks(e,[tick(BTC_PERP,11)]);s._alpha_bar(bar(kind,11,102,103,100))
        assert not s._alpha_release_ready(11,D(1),D(10))
        assert s._alpha_release_ready(12,D(8),D(10))
        assert not s._alpha_release_ready(12,D('8.01'),D(10))
        f['release_used']=s._alpha_reverse;assert not s._alpha_release_ready(13,D(1),D(10))
    finally:e.end();e.dispose()


def test_healthy_original_native_partial_half_full_two_episode_OFF_ON_parity():
    outputs=[]
    for enabled in (False,True):
        s=Observed(config(enabled));e=engine(s,bar_execution=not enabled)
        try:
            run_ticks(e,[tick(BTC_PERP,1),tick(SOL_PERP,1)])
            snapshots=[]
            for cycle in range(2):
                minute=60_000_000_000;t=cycle*1000*minute+2;prepare_day(s,t);history(s);marks(s,t,'100','1')
                ep=s._domain.episode=Episode('healthy-'+str(cycle),1,10000,1,wave_levels=(10,20,30),h=10000)
                i=s._domain._intent(ep,'BTC_ENTRY',1,None,quantity=100)
                s.btc_action=lambda q:s._submit_intent(i,100,100,.01,0,ts_now=q.ts_event)
                run_ticks(e,[tick(BTC_PERP,t+1),tick(BTC_PERP,t+2),tick(BTC_PERP,t+3,'99'),tick(SOL_PERP,t+4,'1')])
                for k,q in enumerate([3505,2505,1505,505]):
                    now=t+(10+k*10)*minute;marks(s,now,'100','1');original(s,e,ep,q,now,price='1');advance(s,e,now+minute,sol='1')
                    snapshots.append((ep.sol_qty,ep.sol_first_fill_at,ep.sol_first_owned_at,ep.fixed_sigma,dict(ep.sol_add_filled_notional)))
                    assert not any(i.action=='SOL_ADD' for i in s._pending_by_order.values())
                for half,z in [(True,.3),(False,0.)]:
                    now=t+(60 if half else 80)*minute;s._domain._decision_index=100+now
                    when=datetime.fromtimestamp(now/1e9,UTC);b=DailyBar(when-timedelta(days=1),when,when,100,100,1)
                    intents=s._domain._sol_exits(ep,Features(100+now,1,1.,1.,0.,1.,0.),b,100+now,z=z);assert len(intents)==1
                    logical=intents[0]
                    s.sol_action=lambda q:s._submit_intent(logical,1,1,None,100+now,ts_now=q.ts_event)
                    for dt in range(3):advance(s,e,now+dt*minute,sol='1')
                assert ep.sol_qty==0
                s.btc_action=lambda q:s._begin_forced_close('REGIME')
                for dt in range(4):advance(s,e,t+(90+dt)*minute,sol='1')
                assert not e.cache.positions_open() and s._domain.episode is None and not s._pending_by_order
            fills=[{k:x[k] for k in ('fill_ns','instrument','px','qty','commission','native_liquidity_side','order_type','post_only')} for x in s.fill_audit]
            orders=[(str(o.quantity),str(o.filled_qty),int(o.order_type),int(o.time_in_force),o.is_post_only,o.is_reduce_only,int(o.status),o.ts_init,o.ts_last) for o in e.cache.orders()]
            cash=e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal();fees=sum(D(x['commission']) for x in s.fill_audit)
            flow=sum(o.filled_qty.as_decimal()*D(str(o.avg_px))*(1 if o.side==OrderSide.SELL else -1) for o in e.cache.orders() if o.filled_qty.as_decimal()>0)
            assert cash==D(10000)+flow-fees
            outputs.append((fills,orders,cash,fees,snapshots))
        finally:e.end();e.dispose()
    first_fill=next(((a,b) for a,b in zip(outputs[0][0],outputs[1][0]) if a!=b),None)
    print(json.dumps(dict(first_fill=first_fill,first_order=next(((a,b) for a,b in zip(outputs[0][1],outputs[1][1]) if a!=b),None)),default=str))
    assert outputs[0]==outputs[1], dict(first_fill=first_fill,fill_counts=[len(x[0]) for x in outputs],cash=[str(x[2]) for x in outputs],first_order=next(((a,b) for a,b in zip(outputs[0][1],outputs[1][1]) if a!=b),None))


def test_real_production_tiny_runner_original_alpha_ON_observer_and_serialization(tmp_path):
    from test_native_baseline import write_streaming_fixture
    from coinmaster.research.native_baseline import run_native_diagnostic,TRADING_START_MS,MINUTE_MS
    from coinmaster.domain.wave_overlay import Candidate
    import pyarrow as pa
    import pyarrow.parquet as pq
    start,end=write_streaming_fixture(tmp_path,trading_days=1);shift=TRADING_START_MS-start
    for path in (tmp_path/'normalized').glob('*.parquet'):
        rows=pq.read_table(path).to_pylist()
        for row in rows:row['open_time_ms']+=shift
        pq.write_table(pa.Table.from_pylist(rows),path)
    result=run_native_diagnostic(tmp_path,candidate=Candidate(btc_notional_multiplier=7.875,max_parent_notional=30_000_000),trading_start_ms=TRADING_START_MS,trading_end_ms=TRADING_START_MS+2*MINUTE_MS,warmup_start_ms=shift,
        research_v0_execution_repairs=True,research_v0_deferred_selective_zero_tp=True,research_v0_selective_lifecycle_repairs=True,research_btc_direction_sizing=True,research_btc_split50=True,research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,
        research_alpha_cushion=True,observe_minute_risk=True,artifact_dir=tmp_path/'production')
    assert result['config']['research_alpha_cushion'] and result['config']['candidate']['sol_overlay_enabled']
    assert isinstance(result['alpha_cushion_audit'],list) and 'alpha_cushion' in result['source_hashes']
    assert result['minute_risk_observations']['curves']['pre_quote_paired_close']['samples']==3
    json.dumps(result)


def test_native_original_over100_percent_risk_trim_keeps_filled_rights_and_clock():
    s,e,ep=setup(qty=1)
    try:
        original(s,e,ep,.9,10)
        print(json.dumps(dict(audit=s.alpha_cushion_audit[-3:],h=ep.h,order_count=len(e.cache.orders()),pending=list(ep.pending)),default=str))
        assert ep.sol_qty==.9, dict(audit=s.alpha_cushion_audit[-5:],h=ep.h,orders=[str(o) for o in e.cache.orders()],pending=list(ep.pending))
        paid=dict(ep.sol_add_filled_notional);clock=ep.sol_first_owned_at
        marks(s,20,'10000','100');s._alpha_observe_equity(s._v3_equity(),20)
        advance(s,e,21);advance(s,e,22)
        held=next(p for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)
        assert held.quantity.as_decimal()<D('.9') and D(str(ep.sol_qty))==held.quantity.as_decimal()
        assert ep.sol_add_filled_notional==paid and ep.sol_first_owned_at==clock
        assert any(x['event']=='RETIRE_HELD_AUTHORITY' for x in s.alpha_cushion_audit)
        close(s,e,30)
    finally:e.end();e.dispose()


def test_native_same_direction_actual_SOL_reduced_before_any_reverse_increase():
    s,e,ep=setup()
    try:
        s.submit_order(s.order_factory.market(SOL_PERP.id,OrderSide.BUY,SOL_PERP.make_qty(D(1)),time_in_force=TimeInForce.IOC))
        run_ticks(e,[tick(SOL_PERP,10)])
        assert next(p for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id).is_long
        advance(s,e,11)
        assert not any(p.instrument_id==SOL_PERP.id for p in e.cache.positions_open())
        assert any(x['event']=='WRONG_SIDE_REDUCE' for x in s.alpha_cushion_audit)
        assert next(p for p in e.cache.positions_open() if p.instrument_id==BTC_PERP.id).is_long
        close(s,e,20)
    finally:e.end();e.dispose()


def test_native_original_timeout_preempts_protective_hold_and_closes_actual_aggregate():
    s,e,ep=setup()
    try:
        original(s,e,ep,10,10);assert ep.sol_qty==10
        deficit(s,e,20);held=next(p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)
        assert held>10
        i=s._domain._intent(ep,'SOL_EXIT',ep.side,None,quantity=ep.sol_qty,reason='SOL_HARD_TIMEOUT')
        s._preempt_with_mandatory_sol_exit(i,ep.fixed_sigma,len(s._bars)-1)
        advance(s,e,30)
        assert not any(p.instrument_id==SOL_PERP.id for p in e.cache.positions_open())
        assert ep.sol_qty==0 and s._conditional['original_target']==0
        assert not any(i.action.startswith('SOL') for i in s._pending_by_order.values())
        close(s,e,40)
    finally:e.end();e.dispose()


def test_actual_native_RiskEngine_throttle_Denied_retains_forced_residual_then_next_quote_flat():
    class Throttle(Observed):
        denials=None
        def on_order_denied(self,event):
            if self.denials is None:self.denials=[]
            self.denials.append(event);assert len(self.denials)==1
            super().on_order_denied(event)
    s=Throttle(config());e=engine(s,rate='2/00:00:01')
    try:
        run_ticks(e,[tick(SOL_PERP,1)])
        s._domain.episode=Episode('alpha-native-denied',1,10000,1)
        marks(s,1)
        s.submit_order(s.order_factory.market(SOL_PERP.id,OrderSide.BUY,SOL_PERP.make_qty(D(1)),time_in_force=TimeInForce.IOC))
        run_ticks(e,[tick(SOL_PERP,2)])
        assert e.cache.positions_open()[0].quantity.as_decimal()==1
        s._begin_forced_close('REGIME')
        run_ticks(e,[tick(SOL_PERP,3,size='.4')])
        assert len(s.denials)==1 and e.cache.order(s.denials[0].client_order_id).status.name=='DENIED'
        assert e.cache.positions_open()[0].quantity.as_decimal()==D('.6')
        run_ticks(e,[tick(SOL_PERP,2_000_000_003)])
        assert len(s.denials)==1 and not e.cache.positions_open() and not e.cache.orders_open()
        assert not s._pending_by_order and s._domain.episode is None
        account=e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()
        fees=sum(o.commissions()[0].as_decimal() for o in e.cache.orders() if o.commissions())
        assert account==D(10000)-fees
    finally:e.end();e.dispose()


def test_native_pending_original_risk_cancel_latepartial_retires_only_bound_unfilled_no_resurrection():
    class DelayedCancel(Observed):
        delay=False;cancel_requests=None
        def cancel_order(self,o,*a,**kw):
            if self.delay and o.instrument_id==SOL_PERP.id:
                if self.cancel_requests is None:self.cancel_requests=[]
                self.cancel_requests.append(o.client_order_id);return
            return super().cancel_order(o,*a,**kw)
    s,e,ep=setup(probe=DelayedCancel,qty=1)
    try:
        ep.sol_rights.add(0);ep.sol_right_fraction[0]=1
        logical=s._domain._intent(ep,'SOL_ADD',-1,0,quantity=.9,reason='SOL_ADD')
        assert s._alpha_admit(D('.9'),D(100),10)
        assert s._tier_allows_increase(SOL_PERP.id,OrderSide.SELL,D('.9'),10)
        # Native resting order supplies an actual delayed-ACK lifecycle; normal
        # original IOC policy/type is independently covered by exact A/B parity.
        c=s._conditional_state(10);c['adds']=[dict(intent=logical,remaining=D('.9'),sigma=.02,index=90,price=D(100))];c['original_target']=D('.9')
        physical=s._domain._intent(ep,'SOL_ADD',-1,None,quantity=.9,reason='CONDITIONAL_NET_ADD')
        c['original_attempts'][physical.id]=(logical.id,)
        o=s.order_factory.limit(SOL_PERP.id,OrderSide.SELL,SOL_PERP.make_qty(D('.9')),SOL_PERP.make_price(101),time_in_force=TimeInForce.GTC)
        s._pending_by_order[str(o.client_order_id)]=physical;s._sigma_by_order[str(o.client_order_id)]=.02;s._decision_index_by_order[str(o.client_order_id)]=90
        s.submit_order(o);run_ticks(e,[tick(SOL_PERP,10)])
        assert o.is_open and ep.sol_qty==0
        s.delay=True;marks(s,20,'10000','100');s._alpha_observe_equity(s._v3_equity(),20);advance(s,e,21)
        assert s.cancel_requests and not ep.sol_risk_retired_notional
        assert physical.id in c['alpha_risk_cancels'] and str(o.client_order_id) in s._pending_by_order
        run_ticks(e,[tick(SOL_PERP,22,'101',size='.3')])
        assert o.filled_qty.as_decimal()==D('.3') and o.leaves_qty.as_decimal()==D('.6')
        assert ep.sol_qty==.3 and ep.sol_add_filled_notional[0]==pytest.approx(30.3,abs=1e-12)
        assert not ep.sol_risk_retired_notional
        s.delay=False;s.cancel_order(o);advance(s,e,23)
        assert ep.sol_risk_retired_notional[0]==60
        assert ep.sol_qty==.3 and ep.sol_add_filled_notional[0]==pytest.approx(30.3,abs=1e-12)
        assert not c.get('alpha_risk_cancels') and logical.id not in ep.pending
        before=len(s.fill_audit);original(s,e,ep,.6,24)
        assert ep.sol_qty==.3 and ep.sol_add_filled_notional[0]==pytest.approx(30.3,abs=1e-12)
        assert not any(D(x.get('original_native_quantity','0'))>0 for x in s.alpha_cushion_audit if x.get('event')=='NATIVE_FILL' and x['timestamp_ns']>=23)
        assert any(x['event']=='RETIRE_RISK_CANCELED_AUTHORITY' and x['quantity']=='.6' or x['event']=='RETIRE_RISK_CANCELED_AUTHORITY' and D(x['quantity'])==D('.6') for x in s.alpha_cushion_audit)
        close(s,e,30)
    finally:e.end();e.dispose()
