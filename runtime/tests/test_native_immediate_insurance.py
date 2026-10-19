from datetime import UTC,datetime,timedelta
from decimal import Decimal as D
from dataclasses import replace
from math import exp,log
import json
import pytest
from nautilus_trader.model.enums import BarAggregation,OrderSide,TimeInForce
from coinmaster.domain.wave_overlay import DailyBar,Episode
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from test_native_split_cover import cfg,HOUR
from test_native_episode_risk import NativeProbe,tick,run_ticks,marks
from test_native_btc_sizing import prepare_day
from test_native_h1_b1 import confirmation_types,bar
from test_native_sol_risk_first import engine

MIN=60_000_000_000


def config(mode='i25'):
    c=cfg(True)
    return c.__replace__(candidate=replace(c.candidate,sol_overlay_enabled=False),
        research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,
        research_immediate_sol=mode,research_immediate_lookback=30,
        research_confirmation_bars=confirmation_types())


def history(s,future=False):
    closes=[];b=100.;v=100.
    end=datetime(1970,1,1,tzinfo=UTC)
    for n in range(31):
        r=(.01,-.01,.005,-.005,.02,-.02)[n%6];b*=exp(r);v*=exp(2*r)
        close=end-timedelta(days=30-n)
        closes.append(DailyBar(close-timedelta(days=1),close,close,b,b,v))
    s._bars=closes
    if future:
        tomorrow=end+timedelta(days=1)
        s._bars.append(DailyBar(end,tomorrow,tomorrow,b,b*100,v/100))


def setup(mode='i25',side=1,probe=NativeProbe,qty=100):
    s=probe(config(mode));e=engine(s)
    run_ticks(e,[tick(BTC_PERP,1),tick(SOL_PERP,1)])
    prepare_day(s,2,side);history(s);marks(s,2)
    ep=s._domain.episode=Episode('immediate',side,10000,1,wave_levels=(.5,.6,.7),h=10000)
    i=s._domain._intent(ep,'BTC_ENTRY',side,None,quantity=qty)
    s._submit_intent(i,100,100,.01,0,ts_now=2)
    run_ticks(e,[tick(BTC_PERP,3),tick(SOL_PERP,3)])
    return s,e,ep


def advance(s,e,ts,btc='100',sol='100',size='1000'):
    marks(s,ts,btc,sol)
    run_ticks(e,[tick(BTC_PERP,ts,btc),tick(SOL_PERP,ts,sol,size=size)])


def sol_confirm(s,e,ts,side,tf=15):
    kind=next(k for k in s.config.research_confirmation_bars if k.instrument_id==SOL_PERP.id and (k.spec.aggregation==BarAggregation.MINUTE)==(tf==15))
    previous=s._insurance_bars.get((SOL_PERP.id,tf))
    if previous is None:
        s.on_bar(bar(kind,ts-2,100,101,99));previous=s._insurance_bars[(SOL_PERP.id,tf)]
    price=D(str(previous[1]))+1 if side==1 else D(str(previous[2]))-1
    s.on_bar(bar(kind,ts,price))


def close(s,e,ep,ts=1000):
    s._begin_forced_close('REGIME')
    for n in range(6):advance(s,e,ts+n)
    assert not e.cache.positions_open() and not s._pending_by_order and not e.cache.orders_open()
    fees=sum((D(r['commission']) for r in s.fill_audit),D(0))
    flow=sum((o.filled_qty.as_decimal()*D(str(o.avg_px))*(1 if o.side==OrderSide.SELL else -1) for o in e.cache.orders() if o.filled_qty.as_decimal()),D(0))
    assert e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()==D(10000)+flow-fees


@pytest.mark.parametrize('mode',['i25','i25-light','i25-recovery','i33'])
@pytest.mark.parametrize('side',[1,-1])
def test_initial_native_partial_btc_fill_insured_without_confirmation_fixed_daily_estimate(mode,side):
    s,e,ep=setup(mode,side)
    try:
        st=s._insurance_cycle;assert st and st['returns']==30 and abs(st['k']-D('.5'))<D('.0000001')
        assert st['estimate_close_ns']==0 and st['first_fill_ns']==3
        held=next(p for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)
        assert held.is_long==(side==-1) and held.quantity.as_decimal()==st['target']>0
        firsttarget=st['target'];frozen=(st['k'],st['sigma'])
        run_ticks(e,[tick(BTC_PERP,4),tick(BTC_PERP,5,'99' if side==1 else '101')])
        advance(s,e,6)
        assert st['target']>firsttarget and (st['k'],st['sigma'])==frozen
        assert ep.sol_qty==0 and not ep.sol_adds
        assert all(x['native_liquidity_side']=='TAKER' for x in s.fill_audit if x['action']=='SOL_ADD')
        json.dumps(s._insurance_report())
        close(s,e,ep)
    finally:e.end();e.dispose()


@pytest.mark.parametrize('side',[1,-1])
@pytest.mark.parametrize('tf',[15,60])
def test_adverse_sigma_requires_posttrigger_closed_or_confirmation_next_quote_and_no_price_churn(side,tf):
    s,e,ep=setup(side=side)
    try:
        st=s._insurance_cycle;f0=st['fraction'];before=len(s.fill_audit)
        btc='97' if side==1 else '103'
        advance(s,e,10,btc);assert st['fraction']==f0 and st['arm']
        sol_confirm(s,e,12,-side,tf)
        assert st['fraction']==f0
        advance(s,e,13,btc)
        assert st['fraction']==D('.75') and len(s.fill_audit)>before
        target=st['target'];before=len(s.fill_audit)
        advance(s,e,14,'97.1' if side==1 else '102.9')
        assert st['target']==target and len(s.fill_audit)==before
        close(s,e,ep)
    finally:e.end();e.dispose()


@pytest.mark.parametrize('side',[1,-1])
def test_light_closed_btc_bar_latches_half_base_no_common_restore(side):
    s,e,ep=setup('i25-light',side)
    try:
        st=s._insurance_cycle;px='104' if side==1 else '96'
        advance(s,e,10,px)
        kind=s.config.research_confirmation_bars[0]
        s.on_bar(bar(kind,11,D(px)))
        advance(s,e,12,px)
        assert st['light'] and st['base']==st['fraction']==D('.125')
        sol_confirm(s,e,15,-side)
        advance(s,e,16,'103.9' if side==1 else '96.1')
        assert st['fraction']==D('.125')
        close(s,e,ep)
    finally:e.end();e.dispose()


@pytest.mark.parametrize('side',[1,-1])
def test_native_recovery_once_max_not_sum_release_preserves_required_adverse(side):
    s,e,ep=setup('i25-recovery',side)
    try:
        st=s._insurance_cycle
        advance(s,e,10,'104' if side==1 else '96','105' if side==1 else '95')
        bpnl,_=s._insurance_pnl(BTC_PERP.id,10);spnl,_=s._insurance_pnl(SOL_PERP.id,10)
        assert bpnl>0 and spnl<0
        sol_confirm(s,e,12,-side);advance(s,e,13,'104' if side==1 else '96','105' if side==1 else '95')
        assert st['recovery_used'] and st['recovery_fraction']==D('.5') and st['fraction']==D('.25')
        # Actual adverse re-entry supersedes rather than adds a second full target.
        advance(s,e,20,'99' if side==1 else '101','105' if side==1 else '95')
        sol_confirm(s,e,22,-side);advance(s,e,23,'99' if side==1 else '101','105' if side==1 else '95')
        assert st['fraction']==D('.75') and max(st['fraction'],st['recovery_fraction'])==D('.75')
        sol_confirm(s,e,30,side);advance(s,e,31,'99' if side==1 else '101','105' if side==1 else '95')
        assert st['recovery_fraction']==0 and st['fraction']==D('.75') and st['recovery_used']
        close(s,e,ep)
    finally:e.end();e.dispose()


def test_realized_profit_harvest_floor_newextreme_rearm_and_two_native_episodes():
    s,e,ep=setup()
    try:
        st=s._insurance_cycle
        advance(s,e,10,'98','95');sol_confirm(s,e,12,1)
        advance(s,e,13,'98','95')
        assert st['fraction']==D('.125')
        sol_confirm(s,e,15,-1);advance(s,e,16,'98','95')
        assert st['fraction']==D('.125')
        advance(s,e,20,'97','95');sol_confirm(s,e,22,-1);advance(s,e,23,'97','95')
        assert st['fraction']>D('.125')
        close(s,e,ep,40)
        history(s);marks(s,50)
        ep2=s._domain.episode=Episode('second',-1,10000,1,wave_levels=(.5,.6,.7),h=10000)
        i=s._domain._intent(ep2,'BTC_ENTRY',-1,None,quantity=20)
        s._submit_intent(i,100,100,.01,0,ts_now=50)
        advance(s,e,51)
        assert len(s.insurance_cycles)==2 and s._insurance_cycle['base']==D('.25')
        close(s,e,ep2,60)
        account=e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()
        # All native signed fills+commissions conserve actual account cash.
        report=e.trader.generate_order_fills_report()
        assert len(report)>0 and account>0
        assert sum(D(x['commission']) for x in s.fill_audit)>0
        json.dumps(s._insurance_report())
    finally:e.end();e.dispose()


def test_future_daily_bar_cannot_change_frozen_coefficient_and_invalid_blocks_new_protection():
    s=NativeProbe(config());history(s);first=s._insurance_estimate(2)
    history(s,True);assert s._insurance_estimate(2)==first
    s._bars=s._bars[-2:];assert s._insurance_estimate(2) is None


def test_unknown_ack_retains_owner_btc_flat_cancel_then_actual_residual_zero():
    s,e,ep=setup()
    try:
        st=s._insurance_cycle
        run_ticks(e,[tick(BTC_PERP,4),tick(BTC_PERP,5,'99')]);advance(s,e,6)
        i=s._domain._intent(ep,'SOL_ADD',-ep.side,None,quantity=1,reason='CONDITIONAL_NET_ADD')
        s._pending_by_order['UNKNOWN_ACK']=i
        before=len(e.cache.orders())
        btc=next(p for p in e.cache.positions_open() if p.instrument_id==BTC_PERP.id)
        s.submit_order(s.order_factory.market(BTC_PERP.id,OrderSide.SELL,BTC_PERP.make_qty(btc.quantity.as_decimal()),time_in_force=TimeInForce.IOC,reduce_only=True))
        run_ticks(e,[tick(BTC_PERP,10)])
        advance(s,e,11)
        assert st['target']==0 and len(e.cache.orders())==before+1
        s._pending_by_order.pop('UNKNOWN_ACK');s._domain.on_parent_terminal(i.id)
        advance(s,e,12)
        assert not any(p.instrument_id==SOL_PERP.id for p in e.cache.positions_open())
        assert not s._pending_by_order and st['closed']
    finally:e.end();e.dispose()


@pytest.mark.parametrize('mode',['i25','i25-light','i25-recovery','i33'])
def test_real_production_two_minute_runner_resolves_original_off_native_bars_and_serializes(tmp_path,mode):
    from test_native_baseline import write_streaming_fixture
    from coinmaster.research.native_baseline import run_native_diagnostic,MINUTE_MS,TRADING_START_MS
    from coinmaster.domain.wave_overlay import Candidate
    import pyarrow as pa
    import pyarrow.parquet as pq
    start,end=write_streaming_fixture(tmp_path,trading_days=1)
    shift=TRADING_START_MS-start
    for path in (tmp_path/'normalized').glob('*.parquet'):
        rows=pq.read_table(path).to_pylist()
        for row in rows:row['open_time_ms']+=shift
        pq.write_table(pa.Table.from_pylist(rows),path)
    result=run_native_diagnostic(tmp_path,candidate=Candidate(btc_notional_multiplier=7.875,max_parent_notional=30_000_000),
        trading_start_ms=TRADING_START_MS,trading_end_ms=TRADING_START_MS+2*MINUTE_MS,warmup_start_ms=shift,
        research_v0_execution_repairs=True,research_v0_deferred_selective_zero_tp=True,research_v0_selective_lifecycle_repairs=True,
        research_btc_direction_sizing=True,research_btc_split50=True,research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,
        research_immediate_sol=mode,research_immediate_lookback=90,observe_minute_risk=True,artifact_dir=tmp_path/'production')
    assert result['config']['research_immediate_sol']==mode
    assert result['config']['research_immediate_lookback']==90
    assert not result['config']['candidate']['sol_overlay_enabled']
    assert not result['config']['research_conditional_sol']
    assert 'immediate_insurance' in result['source_hashes']
    assert isinstance(result['immediate_sol_insurance_audit'],list)
    assert result['minute_risk_observations']['curves']['pre_quote_paired_close']['samples']==3
    json.dumps(result)


def test_actual_native_partial_canceled_then_risk_throttle_denied_defers_without_recursion_and_flat():
    class Denials(NativeProbe):
        def __init__(self,c):super().__init__(c);self.denials=[]
        def on_order_denied(self,event):
            self.denials.append(event);assert len(self.denials)<=2
            super().on_order_denied(event)
    s=Denials(config());e=engine(s,rate='2/00:00:01')
    try:
        run_ticks(e,[tick(BTC_PERP,1),tick(SOL_PERP,1)])
        prepare_day(s,2);history(s);marks(s,2)
        ep=s._domain.episode=Episode('denied-insurance',1,10000,1,wave_levels=(.5,.6,.7),h=10000)
        i=s._domain._intent(ep,'BTC_ENTRY',1,None,quantity=100)
        s._submit_intent(i,100,100,.01,0,ts_now=2)
        run_ticks(e,[tick(BTC_PERP,3),tick(SOL_PERP,3,size='0.1')])
        assert any(o.status.name=='CANCELED' and o.filled_qty.as_decimal()>0 for o in e.cache.orders() if o.instrument_id==SOL_PERP.id)
        run_ticks(e,[tick(SOL_PERP,4)])
        assert s.denials and 'rate' in s.denials[0].reason.lower()
        assert not any(i.action.startswith('SOL') for i in s._pending_by_order.values())
        before=len(e.cache.orders());run_ticks(e,[tick(SOL_PERP,5)])
        assert len(e.cache.orders())==before
        marks(s,MIN+5)
        run_ticks(e,[tick(SOL_PERP,MIN+5)])
        assert next(p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)==s._insurance_cycle['target']
        close(s,e,ep,MIN+2_000_000_000)
    finally:e.end();e.dispose()


def test_default_off_selected_order_path_native_parity_two_episodes_with_no_insurance_state():
    signatures=[]
    for explicit in (False,True):
        c=cfg(True).__replace__(research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True)
        if explicit:c=c.__replace__(research_immediate_sol=None)
        s=NativeProbe(c);e=engine(s,bar_execution=True)
        try:
            for cycle in range(2):
                ts=cycle*1000
                run_ticks(e,[tick(BTC_PERP,ts+1),tick(SOL_PERP,ts+1)])
                prepare_day(s,ts+2);marks(s,ts+2)
                ep=s._domain.episode=Episode('off-'+str(cycle),1,10000,1,wave_levels=(.01,.02,.03),h=10000)
                i=s._domain._intent(ep,'BTC_ENTRY',1,None,quantity=10)
                s._submit_intent(i,100,100,.01,0,ts_now=ts+2)
                for n in range(3,8):run_ticks(e,[tick(BTC_PERP,ts+n,'104'),tick(SOL_PERP,ts+n)])
                close(s,e,ep,ts+20)
            assert not s.insurance_audit and not s.insurance_cycles
            signatures.append(([{k:v[k] for k in ('instrument','fill_ns','px','qty','commission','native_liquidity_side','order_type','post_only')} for v in s.fill_audit],
                [(str(o.quantity),o.order_type.name,o.time_in_force.name,o.is_post_only,o.is_reduce_only,o.status.name,o.ts_init,o.ts_last) for o in e.cache.orders()],
                e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()))
        finally:e.end();e.dispose()
    assert signatures[0]==signatures[1]



def test_real_pending_transport_unknown_ack_late_native_fill_after_btc_flat_is_closed():
    class Transport(NativeProbe):
        hold=False
        waiting=None
        release=False
        def submit_order(self,order,*args,**kw):
            if self.hold and order.instrument_id==SOL_PERP.id and not order.is_reduce_only:
                self.hold=False;self.waiting=order;return
            return super().submit_order(order,*args,**kw)
        def on_quote_tick(self,q):
            super().on_quote_tick(q)
            if self.release and q.instrument_id==SOL_PERP.id:
                self.release=False;super().submit_order(self.waiting)
    s,e,ep=setup(probe=Transport)
    try:
        run_ticks(e,[tick(BTC_PERP,4),tick(BTC_PERP,5,'99')]);advance(s,e,6)
        s.hold=True;advance(s,e,10,'97');sol_confirm(s,e,12,-1);advance(s,e,13,'97')
        assert s.waiting is not None and str(s.waiting.client_order_id) in s._pending_by_order
        assert e.cache.order(s.waiting.client_order_id) is None  # Real transport-owned unknown ACK.
        btc=next(p for p in e.cache.positions_open() if p.instrument_id==BTC_PERP.id)
        s.submit_order(s.order_factory.market(BTC_PERP.id,OrderSide.SELL,BTC_PERP.make_qty(btc.quantity.as_decimal()),time_in_force=TimeInForce.IOC,reduce_only=True))
        run_ticks(e,[tick(BTC_PERP,20)]);advance(s,e,21)
        before=len(s.fill_audit);s.release=True;run_ticks(e,[tick(SOL_PERP,22,size='0.3')])
        assert any(x['action']=='SOL_ADD' for x in s.fill_audit[before:])
        advance(s,e,23)
        assert not e.cache.positions_open() and not e.cache.orders_open() and not s._pending_by_order
        assert s._insurance_cycle['target']==0
        close(s,e,ep,30)
    finally:e.end();e.dispose()



def test_daily_estimate_refresh_does_not_refreeze_open_episode_on_next_utc_day():
    s,e,ep=setup()
    try:
        run_ticks(e,[tick(BTC_PERP,4),tick(BTC_PERP,5,'99')]);advance(s,e,6)
        st=s._insurance_cycle;frozen=(st['k'],st['sigma'],st['estimate_close_ns'])
        last=s._bars[-1];t=last.close_time+timedelta(days=1)
        s._bars.append(DailyBar(last.close_time,t,t,last.btc_close,last.btc_close*1.1,last.sol_close*.7))
        assert s._insurance_estimate(24*HOUR+1)[:2]!=frozen[:2]
        advance(s,e,24*HOUR+1)
        assert (st['k'],st['sigma'],st['estimate_close_ns'])==frozen
        close(s,e,ep,24*HOUR+10)
    finally:e.end();e.dispose()
