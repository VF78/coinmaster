from datetime import UTC,datetime
from decimal import Decimal as D
import json
import pytest
from nautilus_trader.model.enums import OrderSide,TimeInForce,OmsType,AccountType,BarAggregation,AggregationSource,PriceType
from nautilus_trader.model.data import Bar,BarType,BarSpecification
from nautilus_trader.model.objects import Money
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import LoggingConfig,RiskEngineConfig,CacheConfig,DataEngineConfig
from coinmaster.domain.wave_overlay import Episode
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP,SIM
from test_native_split_cover import cfg,seed_beta,HOUR
from test_native_episode_risk import NativeProbe,tick,run_ticks,marks
from test_native_btc_sizing import prepare_day
from test_native_h1_b1 import confirmation_types,bar

MIN=60_000_000_000


class Scripted(NativeProbe):
    pause=False
    def _entries_enabled(self):
        return not self.pause and super()._entries_enabled()

    def on_quote_tick(self,q):
        super().on_quote_tick(q)
        action=getattr(self,'sol_action',None)
        if action is not None and q.instrument_id==SOL_PERP.id:
            self.sol_action=None;action(q)


def scripted_original(s,e,ep,quantity,ts,size='1000',notional=False,price='100'):
    ep.sol_rights.add(0);ep.sol_right_fraction[0]=1
    def action(q):
        kw={'requested_notional':quantity*100} if notional else {'quantity':quantity}
        i=s._domain._intent(ep,'SOL_ADD',-ep.side,0,reason='SOL_ADD',**kw)
        s._submit_intent(i,float(q.bid_price),float(q.ask_price),.02,0,ts_now=q.ts_event)
    s.sol_action=action;run_ticks(e,[tick(SOL_PERP,ts,price,size=size)])


def config(mode=None):
    return cfg(True).__replace__(research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,
        research_sol_risk_first=mode,research_confirmation_bars=confirmation_types() if mode else ())


def engine(s,bar_execution=False,rate=None):
    e=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR'),
        **({'cache':CacheConfig(bar_capacity=128),'data_engine':DataEngineConfig(time_bars_build_with_no_updates=False)} if s.config.research_sol_risk_first else {}),
        **({'risk_engine':RiskEngineConfig(max_order_submit_rate=rate)} if rate else {})))
    e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,
        starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,
        default_leverage=D(1),bar_execution=bar_execution)
    e.add_instrument(BTC_PERP);e.add_instrument(SOL_PERP);e.add_strategy(s);return e


def setup(mode,side=1,probe=NativeProbe,sol_price="100"):
    s=probe(config(mode));e=engine(s)
    run_ticks(e,[tick(BTC_PERP,1)])
    prepare_day(s,2,side);marks(s,2,"100",sol_price);seed_beta(s,1)
    ep=s._domain.episode=Episode('risk-first',side,10000,1,wave_levels=(.5,.6,.7),h=10000)
    i=s._domain._intent(ep,'BTC_ENTRY',side,None,quantity=100)
    s._submit_intent(i,100,100,.01,0,ts_now=2)
    run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,5,'99' if side==1 else '101'),tick(SOL_PERP,6,sol_price)])
    return s,e,ep


def original(s,e,ep,qty,ts=10,level=0,notional=False):
    ep.sol_rights.add(level);ep.sol_right_fraction[level]=1
    kw={'requested_notional':qty*100} if notional else {'quantity':qty}
    i=s._domain._intent(ep,'SOL_ADD',-ep.side,level,reason='SOL_ADD',**kw)
    s._submit_intent(i,100,100,.02,0,ts_now=ts);run_ticks(e,[tick(SOL_PERP,ts)])
    return i


def qty(e,iid):
    return sum((p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==iid),D(0))


def finish(s,e,ts=100):
    ep=s._domain.episode
    if ep is not None:
        ep.close_reason='REGIME'
        close=s._domain._intent(ep,'CLOSE_ALL',-ep.side,None,reason='REGIME')
    else:close=None
    s._begin_forced_close('REGIME',close)
    for t in range(ts,ts+4):run_ticks(e,[tick(BTC_PERP,t),tick(SOL_PERP,t)])
    assert not e.cache.positions_open() and not e.cache.orders_open() and not s._pending_by_order
    assert all(o.is_closed for o in e.cache.orders())
    fees=sum((D(r['commission']) for r in s.fill_audit),D(0))
    flow=sum((o.filled_qty.as_decimal()*D(str(o.avg_px))*(1 if o.side==OrderSide.SELL else -1) for o in e.cache.orders() if o.filled_qty.as_decimal()),D(0))
    assert e.cache.account_for_venue(SIM).balance_total().as_decimal()==D(10000)+flow-fees
    json.dumps(s._risk_first_report())


@pytest.mark.parametrize('side',[1,-1])
def test_cap50_actual_native_admission_held_trim_price_nochurn_BTCflat_original_late_add(side):
    s,e,ep=setup('cap50',side)
    try:
        original(s,e,ep,100)
        cap=s._conditional['rf']['cap'];assert qty(e,SOL_PERP.id)==cap and cap<D(50)
        consumed=dict(ep.sol_add_filled_notional)
        i=s._domain._intent(ep,'BTC_REDUCE',-side,0,quantity=50)
        s._submit_intent(i,100,100,.01,0,ts_now=20)
        run_ticks(e,[tick(BTC_PERP,20),tick(SOL_PERP,21)])
        lower=s._conditional['rf']['cap'];assert qty(e,SOL_PERP.id)==lower<cap
        assert ep.sol_add_filled_notional==consumed
        before=len([o for o in e.cache.orders() if o.instrument_id==SOL_PERP.id]);marks(s,30,'120','80')
        run_ticks(e,[tick(BTC_PERP,30,'120'),tick(SOL_PERP,31,'80')])
        assert s._conditional['rf']['cap']==lower and len([o for o in e.cache.orders() if o.instrument_id==SOL_PERP.id])==before
        i=s._domain._intent(ep,'BTC_REDUCE',-side,1,quantity=50)
        s._submit_intent(i,100,100,.01,0,ts_now=40)
        run_ticks(e,[tick(BTC_PERP,40),tick(SOL_PERP,41)])
        assert qty(e,BTC_PERP.id)==0 and qty(e,SOL_PERP.id)==lower
        marks(s,45);original(s,e,ep,10,45)
        assert qty(e,SOL_PERP.id)==lower+10
        finish(s,e,60)
    finally:e.end();e.dispose()


def test_dd_cov_native_global_stage_recovery_ceiling_no_resurrection_and_BTCflat_new_auth():
    s,e,ep=setup('dd-cov')
    try:
        original(s,e,ep,90)
        assert ep.sol_qty==90
        for ts,price,stage in ((20,'88',1),(30,'78',2)):
            marks(s,ts,price,'100');run_ticks(e,[tick(BTC_PERP,ts,price),tick(SOL_PERP,ts+1)])
            assert s._rf_stage==stage
        held=qty(e,SOL_PERP.id);oref=s._conditional['rf']['oref'];assert oref==90 and held<90
        marks(s,40,'88','100');run_ticks(e,[tick(BTC_PERP,40,'88'),tick(SOL_PERP,41)])
        assert s._rf_stage==1 and qty(e,SOL_PERP.id)<=held
        before=len(e.cache.orders());run_ticks(e,[tick(BTC_PERP,42,'88'),tick(SOL_PERP,43)])
        assert len(e.cache.orders())==before and qty(e,SOL_PERP.id)<=held
        marks(s,50);run_ticks(e,[tick(BTC_PERP,50),tick(SOL_PERP,51)])
        assert s._rf_stage==0 and qty(e,SOL_PERP.id)<=held
        i=s._domain._intent(ep,'BTC_REDUCE',-1,None,quantity=100)
        s._submit_intent(i,100,100,.01,0,ts_now=60)
        run_ticks(e,[tick(BTC_PERP,60),tick(SOL_PERP,61)])
        previous=qty(e,SOL_PERP.id);original(s,e,ep,5,70)
        assert qty(e,SOL_PERP.id)==previous+5
        peak=s._rf_peak
        finish(s,e,80)
        assert s._rf_peak>=peak>=D(10000)
    finally:e.end();e.dispose()


def atr(s,e,ts=20):
    run_ticks(e,[tick(SOL_PERP,ts)])
    kind=next(k for k in s.config.research_confirmation_bars if k.instrument_id==SOL_PERP.id and k.spec.aggregation==BarAggregation.MINUTE)
    for i in range(15):s.on_bar(bar(kind,ts-14+i,100,101,99))
    assert s._rf_atr==2


@pytest.mark.parametrize('side',[1,-1])
def test_ATR_native_fixed_notional_group_threelegs_firstpartial_limits_deadline_fallback(side):
    s,e,ep=setup('split-atr',side)
    try:
        atr(s,e)
        original(s,e,ep,100,30,notional=True)
        p=s._rf_sol_parents[0];assert p['quantity']==100 and p['pieces']==[D(34),D(33),D(33)]
        run_ticks(e,[tick(SOL_PERP,31)])
        limits=[o for o in e.cache.orders_open() if o.instrument_id==SOL_PERP.id]
        assert sorted(o.quantity.as_decimal() for o in limits)==[D(33),D(33)]
        expected=[D(101),D(102)] if side==1 else [D(98),D(99)]
        assert sorted(o.price.as_decimal() for o in limits)==expected
        # Future completed-bar update cannot rewrite this accepted ATR or Q.
        run_ticks(e,[tick(SOL_PERP,40)])
        kind=next(k for k in s.config.research_confirmation_bars if k.instrument_id==SOL_PERP.id and k.spec.aggregation==BarAggregation.MINUTE)
        s.on_bar(bar(kind,40,100,110,90));assert s._rf_atr>2 and p['atr']==2 and p['quantity']==100
        marks(s,60*MIN+30)
        run_ticks(e,[tick(SOL_PERP,60*MIN+30)])
        assert not any(p['pending']) and p['fallback']
        run_ticks(e,[tick(SOL_PERP,60*MIN+31)])
        assert p['closed'] and p['filled']==100 and p['cancelled']==0
        assert ep.sol_add_filled_notional[0]==10000
        finish(s,e,60*MIN+50)
    finally:e.end();e.dispose()


def test_ATR_invalid_uses_ordinary_native_IOC_and_no_split_parent():
    s,e,ep=setup('split-atr')
    try:
        original(s,e,ep,2)
        assert not s._rf_sol_parents and qty(e,SOL_PERP.id)==2
        assert any(r['event']=='ATR_UNAVAILABLE_NATIVE_IOC' for r in s.risk_first_sol_audit)
        finish(s,e)
    finally:e.end();e.dispose()


@pytest.mark.parametrize('mode',['cap50','dd-cov','split-atr'])
def test_exclusive_default_off_selector(mode):
    with pytest.raises(ValueError,match='EXCLUSIVE'):
        NativeProbe(config(mode).__replace__(research_conditional_sol=True))


def test_nonpositive_cov_no_new_directed_SOL_native_and_no_hard_beta_bounds():
    s,e,ep=setup('dd-cov')
    try:
        s._cover_returns.clear();s._cover_returns.extend([(0.001,-.001),(-.001,.001)]*360)
        s._rf_factor_ns=None;marks(s,20,'68','100')
        run_ticks(e,[tick(BTC_PERP,20,'68'),tick(SOL_PERP,21)])
        assert s._rf_stage==3 and s._rf_factor is None and qty(e,SOL_PERP.id)==0
        finish(s,e,30)
    finally:e.end();e.dispose()


@pytest.mark.parametrize('late_fill',[False,True])
def test_ATR_unknown_ACK_priority_full_exit_cancels_or_closes_actual_late_partial(late_fill):
    class Held(NativeProbe):
        hold=True
        def submit_order(self,order,*args,**kw):
            item=self._rf_sol_orders.get(str(order.client_order_id))
            if self.hold and item and item[1]==1:self.held=order;return
            return super().submit_order(order,*args,**kw)
        def cancel_order(self,order,*args,**kw):
            if late_fill and getattr(self,'held',None) is order:return
            return super().cancel_order(order,*args,**kw)
    s,e,ep=setup('split-atr',probe=Held)
    try:
        atr(s,e);original(s,e,ep,100,30);run_ticks(e,[tick(SOL_PERP,31)])
        p=s._rf_sol_parents[0];assert p['pending'][1] and e.cache.order(s.held.client_order_id) is None
        before=len(e.cache.orders())
        i=s._domain._intent(ep,'SOL_EXIT',ep.side,None,quantity=ep.sol_qty,reason='SOL_Z_FULL_EXIT')
        s._submit_intent(i,100,100,None,0,ts_now=40)
        assert p['stopped'] and len(e.cache.orders())==before and qty(e,SOL_PERP.id)==34
        s.hold=False;NativeProbe.submit_order(s,s.held)
        run_ticks(e,[tick(SOL_PERP,50,'102' if late_fill else '100'),tick(SOL_PERP,51,'102' if late_fill else '100')])
        assert p['closed'] and p['filled']+p['cancelled']==p['quantity']==100
        assert p['filled']==(67 if late_fill else 34)
        assert qty(e,SOL_PERP.id)==0 and not any(p['pending']), (s._queued_intents,s._rf_sol_waiting_exits,[(o.order_type.name,str(o.quantity),o.status.name) for o in e.cache.orders() if o.instrument_id==SOL_PERP.id],s.pre_submit_gate_blocks)
        assert not any(v.action.startswith('SOL') for v in s._pending_by_order.values())
        finish(s,e,60)
    finally:e.end();e.dispose()


def test_ATR_native_partial_initial_and_actual_RiskEngine_throttle_denial_remain_bounded():
    s=NativeProbe(config('split-atr'));e=engine(s,rate='2/00:00:01')
    try:
        run_ticks(e,[tick(BTC_PERP,1)]);prepare_day(s,2);marks(s,2);seed_beta(s,1)
        ep=s._domain.episode=Episode('risk-denied',1,10000,1,wave_levels=(.5,.6,.7),h=10000)
        i=s._domain._intent(ep,'BTC_ENTRY',1,None,quantity=100)
        s._submit_intent(i,100,100,.01,0,ts_now=2)
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,5,'99'),tick(SOL_PERP,6)])
        atr(s,e);original(s,e,ep,90,30)
        assert any(o.status.name=='DENIED' for o in e.cache.orders())
        run_ticks(e,[tick(SOL_PERP,2_000_000_030)])
        p=s._rf_sol_parents[0]
        run_ticks(e,[tick(SOL_PERP,4_000_000_030)])
        assert p['filled']<=p['quantity'] and len(e.cache.orders())<12
        marks(s,60*MIN+30);run_ticks(e,[tick(SOL_PERP,60*MIN+30),tick(SOL_PERP,60*MIN+31)])
        assert p['closed'] and p['filled']==p['quantity']==90 and not any(p['pending'])
        finish(s,e,60*MIN+2_000_000_050)
    finally:e.end();e.dispose()


def test_ATR_actual_first_IOC_partial_and_postonly_rejection_never_resends_full_parent():
    s,e,ep=setup('split-atr',probe=Scripted)
    try:
        atr(s,e);scripted_original(s,e,ep,90,30,size='.5',notional=True)
        run_ticks(e,[tick(SOL_PERP,30+1)])
        p=s._rf_sol_parents[0]
        native=[o for o in e.cache.orders() if o.instrument_id==SOL_PERP.id]
        assert native[0].filled_qty.as_decimal()==D('.5') and native[0].status.name=='CANCELED'
        assert p['filled']==p['pieces'][0]
        # Explicit native post-only rejection: cancel one passive leg and retry
        # the unchanged accepted group at a currently crossed native quote.
        order=next(o for o in e.cache.orders_open() if o.instrument_id==SOL_PERP.id)
        s.pause=True;s.cancel_order(order);run_ticks(e,[tick(SOL_PERP,32)])
        assert order.is_closed
        s.pause=False;run_ticks(e,[tick(SOL_PERP,33,'103')])
        assert any(o.status.name=='REJECTED' for o in e.cache.orders())
        assert p['filled']<=p['quantity']==90
        marks(s,60*MIN+30);run_ticks(e,[tick(SOL_PERP,60*MIN+30),tick(SOL_PERP,60*MIN+31)])
        assert p['filled']==90 and p['closed']
        finish(s,e,60*MIN+50)
    finally:e.end();e.dispose()


def minute_bars(timestamp):
    return [Bar(BarType(i.id,BarSpecification(1,BarAggregation.MINUTE,PriceType.LAST),AggregationSource.EXTERNAL),
        i.make_price(D(100)),i.make_price(D(150)),i.make_price(D(50)),i.make_price(D(100)),i.make_qty(1),timestamp,timestamp)
        for i in (BTC_PERP,SOL_PERP)]


@pytest.mark.parametrize('mode',['cap50','dd-cov','split-atr'])
def test_two_episode_inert_risk_host_vs_selected_control_bars_execution_fills_fees_cash(mode):
    signatures=[]
    for version in (None,mode):
        s=Scripted(config(version));e=engine(s,bar_execution=version is None)
        records=[];previous_peak=s._rf_peak
        try:
            for cycle in range(2):
                base=cycle*24*HOUR
                run_ticks(e,[tick(BTC_PERP,base+1),tick(SOL_PERP,base+2)])
                prepare_day(s,base+3);marks(s,base+3);seed_beta(s,base+1)
                ep=s._domain.episode=Episode('parity-'+str(cycle),1,10000,1,wave_levels=(.01,.02,.03),h=10000)
                i=s._domain._intent(ep,'BTC_ENTRY',1,None,quantity=100)
                s._submit_intent(i,100,100,.01,0,ts_now=base+3)
                run_ticks(e,[tick(BTC_PERP,base+4)])
                if version:
                    e.add_data(minute_bars(base+MIN));e.run(streaming=True);e.clear_data()
                    assert s._split_parent['filled']==50  # New bars never execute the resting BTC child.
                for dt in range(1,6):run_ticks(e,[tick(BTC_PERP,base+MIN+dt,'104'),tick(SOL_PERP,base+MIN+dt)])
                assert s._split_parent['positive_tp_ioc_catchups']
                assert qty(e,BTC_PERP.id)==0
                scripted_original(s,e,ep,2,base+MIN+10)
                records.append((ep.sol_first_fill_at,ep.sol_first_owned_at,ep.fixed_sigma,dict(ep.sol_add_filled_notional)))
                s._bind_native_lots();ep.sol_half_target_lots=10
                def half_action(q):
                    half=s._domain._intent(ep,'SOL_HALF_EXIT',ep.side,None,quantity=1,reason='SOL_Z_HALF_EXIT')
                    s._submit_intent(half,100,100,None,1,ts_now=q.ts_event)
                s.sol_action=half_action;run_ticks(e,[tick(SOL_PERP,base+MIN+11)])
                assert ep.sol_half_done and ep.sol_half_decision_index is not None
                def full_action(q):
                    full=s._domain._intent(ep,'SOL_EXIT',ep.side,None,quantity=1,reason='SOL_Z_FULL_EXIT')
                    s._submit_intent(full,100,100,None,2,ts_now=q.ts_event)
                s.sol_action=full_action;run_ticks(e,[tick(SOL_PERP,base+MIN+12)])
                assert ep.sol_qty==0 and ep.sol_first_owned_at is None
                finish(s,e,base+MIN+20)
                assert s._domain.episode is None
                assert s._rf_peak>=previous_peak
                previous_peak=s._rf_peak
            fills=[{k:v[k] for k in ('instrument','fill_ns','px','qty','commission','native_liquidity_side','order_type','post_only')} for v in s.fill_audit]
            orders=[(str(o.instrument_id),str(o.quantity),str(o.filled_qty),o.order_type.name,o.time_in_force.name,o.is_post_only,o.is_reduce_only,o.status.name,o.ts_init,o.ts_last) for o in e.cache.orders()]
            signatures.append((fills,orders,e.cache.account_for_venue(SIM).balance_total().as_decimal(),records))
        finally:e.end();e.dispose()
    assert signatures[0][0]==signatures[1][0]
    assert signatures[0][2:]==signatures[1][2:]
    assert len(signatures[0][1])==len(signatures[1][1])
    for old,new in zip(signatures[0][1],signatures[1][1]):assert old==new,(old,new)


def test_H3_observer_passes_same_native_equity_without_mid_mark_false_peak(tmp_path):
    from coinmaster.research.minute_risk import NativeMinuteRiskRecorder
    from coinmaster.research.native_baseline import MinuteBundle
    s,e,ep=setup('dd-cov')
    recorder=NativeMinuteRiskRecorder(tmp_path/'mini.csv.gz',D(10000),{BTC_PERP.id:BTC_PERP,SOL_PERP.id:SOL_PERP},{BTC_PERP.id:D(1),SOL_PERP.id:D(1)},10*MIN)
    try:
        original(s,e,ep,90)
        s._risk_first_observer_driven=True
        peak=s._rf_peak
        marks(s,20,'120','100')  # First native mark of a pair must not sample risk.
        s._risk_first_sample(20);assert s._rf_peak==peak
        marks(s,21,'120','120')
        ohlc={k:'120' for k in ('open','high','low','close')}
        b=MinuteBundle(0,{}, {},ohlc,ohlc)
        recorder.bundles[MIN]=b
        recorder.capture(s,MIN,'pre_quote_paired_close')
        expected=recorder.curves['all_native_close_samples'].peak['equity']
        assert s._rf_peak==max(peak,D(expected))
        assert s._rf_peak<peak+D(1000)
        finish(s,e,30)
    finally:recorder.file.close();e.end();e.dispose()



def test_ATR_actual_streamed_1m_to_closed15m_signal_freeze_and_BTC1pp_completion():
    s,e,ep=setup('split-atr',probe=Scripted)
    try:
        kind=BarType(SOL_PERP.id,BarSpecification(1,BarAggregation.MINUTE,PriceType.LAST),AggregationSource.EXTERNAL)
        bars=[Bar(kind,SOL_PERP.make_price(D(100)),SOL_PERP.make_price(D(101)),SOL_PERP.make_price(D(99)),SOL_PERP.make_price(D(100)),SOL_PERP.make_qty(1),m*MIN,m*MIN) for m in range(1,242)]
        e.add_data(bars);e.run(streaming=True);e.clear_data()
        assert s._rf_atr is not None and s._rf_atr>0 and s._rf_atr_ns<=241*MIN,(len(s._rf_tr),s._rf_atr_ns,s._rf_prev_close)
        ts=241*MIN+1;marks(s,ts);scripted_original(s,e,ep,10,ts)
        p=s._rf_sol_parents[0];assert p['atr_ns']<p['signal_ns'] and p['atr']==s._rf_atr
        run_ticks(e,[tick(SOL_PERP,ts+1)])
        assert len([o for o in e.cache.orders_open() if o.instrument_id==SOL_PERP.id])==2
        marks(s,ts+2,'99','100');run_ticks(e,[tick(BTC_PERP,ts+2,'99')])
        assert p['fallback_reason']=='BTC_ADVERSE_1PP' and not any(p['pending'])
        run_ticks(e,[tick(SOL_PERP,ts+3)])
        assert p['closed'] and p['filled']==p['quantity']==10
        assert p['pieces']==[D('3.4'),D('3.3'),D('3.3')]
        finish(s,e,ts+10)
    finally:e.end();e.dispose()


def test_H3_factor_hourly_buffer_and_actual_small_BTC_fill_exception_native():
    s,e,ep=setup('dd-cov')
    try:
        original(s,e,ep,90);marks(s,20,'88','100')
        run_ticks(e,[tick(BTC_PERP,20,'88'),tick(SOL_PERP,21)])
        initial=qty(e,SOL_PERP.id);factors=sum(r['event']=='COV_FACTOR' for r in s.risk_first_sol_audit)
        s._cover_returns.clear();s._cover_returns.extend([(.001,.00155),(-.001,-.00155)]*360)
        run_ticks(e,[tick(SOL_PERP,30)])
        assert sum(r['event']=='COV_FACTOR' for r in s.risk_first_sol_audit)==factors
        ts=HOUR+20;s._cover_last_hour=ts;marks(s,ts,'88','100')
        before=len([o for o in e.cache.orders() if o.instrument_id==SOL_PERP.id])
        run_ticks(e,[tick(BTC_PERP,ts,'88'),tick(SOL_PERP,ts+1)])
        assert sum(r['event']=='COV_FACTOR' for r in s.risk_first_sol_audit)==factors+1
        assert qty(e,SOL_PERP.id)==initial and len([o for o in e.cache.orders() if o.instrument_id==SOL_PERP.id])==before
        i=s._domain._intent(ep,'BTC_REDUCE',-1,0,quantity=5)
        s._submit_intent(i,88,88,.01,0,ts_now=ts+2)
        run_ticks(e,[tick(BTC_PERP,ts+2,'88'),tick(SOL_PERP,ts+3)])
        assert D(0)<initial-qty(e,SOL_PERP.id)<D('.10')*initial
        finish(s,e,ts+10)
    finally:e.end();e.dispose()



def test_cap50_native_1000_partial_trim_reconciles_to_nonzero_floor_without_competing_reduction():
    s,e,ep=setup('cap50',probe=Scripted,sol_price='1')
    try:
        for t in (10,11,12):scripted_original(s,e,ep,1000,t,price='1')
        assert qty(e,SOL_PERP.id)==3000
        consumed=dict(ep.sol_add_filled_notional)
        i=s._domain._intent(ep,'BTC_REDUCE',-1,0,quantity=90)
        s._submit_intent(i,100,100,.01,0,ts_now=20)
        run_ticks(e,[tick(BTC_PERP,20)])
        states=[]
        for ts in (21,22,23):
            run_ticks(e,[tick(SOL_PERP,ts,'1')]);states.append(qty(e,SOL_PERP.id))
        assert states==[D(2000),D(1000),D('333.3')]
        assert s._conditional['rf']['cap']==states[-1]
        assert ep.sol_add_filled_notional==consumed and not s._conditional['exits']
        assert not any(i.action.startswith('SOL') for i,_,_ in s._queued_intents)
        finish(s,e,30)
    finally:e.end();e.dispose()



@pytest.mark.parametrize('mode',['cap50','dd-cov','split-atr'])
def test_real_production_runner_resolves_exclusive_risk_first_and_serializes_native_result(tmp_path,mode):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from test_native_baseline import write_streaming_fixture
    from coinmaster.research.native_baseline import run_native_diagnostic,MINUTE_MS,TRADING_START_MS
    from coinmaster.domain.wave_overlay import Candidate
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
        research_sol_risk_first=mode,observe_minute_risk=True,artifact_dir=tmp_path/'production')
    assert result['config']['research_sol_risk_first']==mode
    assert not result['config']['research_conditional_sol']
    assert result['config']['candidate']['sol_overlay_enabled']
    assert isinstance(result['risk_first_sol_audit'],list)
    assert result['minute_risk_observations']['curves']['pre_quote_paired_close']['samples']==3  # seed plus two completed native samples.
    json.dumps(result);assert 'risk_first_sol' in result['source_hashes']
