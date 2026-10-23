from datetime import UTC,datetime,timedelta
from decimal import Decimal as D
from types import SimpleNamespace
import pytest
from nautilus_trader.model.data import BarType,BarSpecification
from nautilus_trader.model.enums import AggregationSource,BarAggregation,PriceType,OrderSide,TimeInForce
from coinmaster.domain.wave_overlay import Candidate,DailyBar,Episode
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP
from coinmaster.strategy.next_band import DAY,H4,H1,Z_REASON,S_REASON,next_bar_type,next_closed_bar
from test_wave_native_integration import lifecycle_config,native_engine
from test_native_episode_risk import NativeProbe,tick,run_ticks,marks
from test_native_btc_sizing import prepare_day
from test_native_h1_b1 import bar

BTC4=BarType(BTC_PERP.id,BarSpecification(4,BarAggregation.HOUR,PriceType.LAST),AggregationSource.EXTERNAL)
SOL1=BarType(SOL_PERP.id,BarSpecification(1,BarAggregation.HOUR,PriceType.LAST),AggregationSource.EXTERNAL)

def cfg(**kw):return lifecycle_config(research_regime_reentry_band=D('.5'),max_mark_age_ns=100*DAY,research_next_signals=(next_bar_type(BTC_PERP.id,4),next_bar_type(SOL_PERP.id,1)),**kw)

def held(z=False,s=False,cls=NativeProbe,side=1,**kw):
    strategy=cls(cfg(research_zero_retrace=z,research_sol_dominant=s,**kw,candidate=Candidate(btc_tp_fractions_initial_qty=(.2125,.2125,.575))))
    engine=native_engine(strategy);run_ticks(engine,[tick(BTC_PERP,1)])
    prepare_day(strategy,2,side)
    ep=strategy._domain.episode=Episode('next',side,10000,1,wave_levels=(0.,0.,.10),btc_planref_vwap=D(100))
    i=strategy._domain._intent(ep,'BTC_ENTRY',side,None,quantity=100)
    strategy._submit_intent(i,100,100,None,2,ts_now=2);run_ticks(engine,[tick(BTC_PERP,3),tick(BTC_PERP,4)])
    strategy._split_parent=dict(episode_id=ep.id,closed=True,start_ns=2,management_reference_frozen_ns=3,planref_v1_beta=2.)
    strategy.entry_sizing_audit.append(dict(episode_id=ep.id,branch='MARKETABLE_FULL_ENTRY_FALLBACK'))
    return strategy,engine,ep


def test_defaults_and_ep_unique_latch_origin_gap_side_change():
    s=NativeProbe(cfg(research_wait_persist=True));e=native_engine(s)
    try:
        assert not lifecycle_config().research_wait_4h and not lifecycle_config().research_zero_retrace
        prepare_day(s,DAY,1);s._hb_wait_regime=True;s._next_daily()
        for _ in range(5):s._next_daily()
        assert s._next_count==1
        s._last_accepted_session=2*DAY;s._next_daily();assert s._next_count==2
        assert s._next_wait_allowed(1,105,100,20,2*DAY,False)
        s._last_accepted_session=4*DAY;s._next_daily();assert s._next_count==1
        s._last_accepted_session=5*DAY;s._current_signals[-1].side=-1;s._next_daily();assert s._next_count==1
        # Strong branch permits immediately; no unconditional two-day delay.
        assert s._next_wait_allowed(-1,80,100,20,5*DAY,True)
        s._hb_wait_regime=False;s._next_daily();assert s._next_count==0
    finally:e.end();e.dispose()


def test_e4_closed_bar_buffers_until_quote_uses_accepted_daily_and_preserves_attempt(monkeypatch):
    from coinmaster.domain import wave_overlay
    monkeypatch.setattr(wave_overlay,'completed_wave_levels',lambda *a:(.01,.02,.03))
    s=NativeProbe(cfg(research_wait_4h=True,research_btc_direction_sizing=True,candidate=Candidate(btc_notional_multiplier=7.875)));e=native_engine(s)
    try:
        t=20*DAY;run_ticks(e,[tick(BTC_PERP,t)])
        prepare_day(s,t,-1);base=datetime(1970,1,1,tzinfo=UTC)
        s._bars=[DailyBar(base+timedelta(days=i),base+timedelta(days=i+1),base+timedelta(days=i+1),100,100,100) for i in range(20)]
        s._current_signals=[SimpleNamespace(side=-1,beta=1.,sigma=.01)]*20
        s._hb_daily_ohlc={int(x.close_time.timestamp()*1e9):(110,90) for x in s._bars};s._hb_wait_regime=True;s._next_latch_ns=t
        s._next_closed_bar(bar(BTC4,t+H4,85));assert s._domain.episode is None
        run_ticks(e,[tick(BTC_PERP,t+H4+1,'85'),tick(BTC_PERP,t+H4+2,'85'),tick(BTC_PERP,t+H4+3,'85')])
        assert s._last_accepted_session==t and len(s._bars)==20
        assert s._domain._last_entry_attempt==(19,-1)
        assert any(x['event']=='E4_ENTRY_INTENT' and x['daily_asof_ns']==t for x in s.next_band_audit)
        first=len(s.entry_sizing_audit)
        s._next_closed_bar(bar(BTC4,t+2*H4,84));run_ticks(e,[tick(BTC_PERP,t+2*H4+1,'84')]);assert len(s.entry_sizing_audit)==first
        assert s._hb_wait_regime is False # cleared by actual native fill only
    finally:e.end();e.dispose()


def test_z_native_partial_cancel_retired_budget_no_rights_positive_tp_preserved():
    s,e,ep=held(z=True)
    try:
        # Genuine unmarketable positive TP owns its separate allocation.
        tp=s._domain._intent(ep,'BTC_REDUCE',-1,2,quantity=57.5,limit_price=110,reason='BTC_TP3')
        s._submit_intent(tp,100,100,None,2,ts_now=5);run_ticks(e,[tick(BTC_PERP,6)])
        p0=ep.btc_planref_vwap;original_targets=dict(ep.btc_tp_target_lots)
        s._next_closed_bar(bar(BTC4,H4,103));run_ticks(e,[tick(BTC_PERP,H4+1,'103')])
        assert s._next_z['armed'] and not s._next_z['triggered']
        g=s._next_z['G'];assert g>=p0
        for n in range(2,22):run_ticks(e,[tick(BTC_PERP,H4+n,'100',size='3')])
        retired=sum(ep.btc_risk_retired_lots.values());assert retired==42500
        assert not ep.sol_rights and not ep.btc_tp_filled_lots
        assert ep.btc_planref_vwap==p0 and ep.btc_tp_target_lots==original_targets
        assert s._domain._btc_target_leaves(ep,0)==0 and s._domain._btc_target_leaves(ep,1)==0
        assert s._domain._btc_target_leaves(ep,2)==57.5
        assert len([x for x in s.next_band_audit if x['event']=='Z_TRIGGER'])==1
        assert any(x.is_open and x.is_reduce_only for x in e.cache.orders())
    finally:e.end();e.dispose()


def test_z_unarmed_no_stop_and_ordinary_reduction_cancels_arm():
    s,e,ep=held(z=True)
    try:
        s._next_closed_bar(bar(BTC4,H4,99));run_ticks(e,[tick(BTC_PERP,H4+1,'99')]);assert not s._next_z['armed']
        assert not ep.btc_risk_retired_lots
        s._next_closed_bar(bar(BTC4,2*H4,103));run_ticks(e,[tick(BTC_PERP,2*H4+1,'103')]);assert s._next_z['armed']
        ordinary=s._domain._intent(ep,'BTC_REDUCE',-1,2,quantity=1,reason='BTC_TP3')
        s._submit_intent(ordinary,103,103,None,2,ts_now=2*H4+2)
        run_ticks(e,[tick(BTC_PERP,2*H4+3,'100')]);assert s._next_z['canceled']
        assert not ep.btc_risk_retired_lots and ep.sol_rights=={2}
    finally:e.end();e.dispose()


@pytest.mark.parametrize('variant',['old','R1','R2'])
def test_s_cancel_add_late_fill_reconciles_frozen_remaining_partial_no_readd(variant):
    class Delayed(NativeProbe):
        def cancel_order(self,order,*a,**kw):
            if not order.is_reduce_only:return
            return super().cancel_order(order,*a,**kw)
    s,e,ep=held(s=True,cls=Delayed,side=-1,research_sol_residual=variant!='old',research_sol_minute=variant=='R2')
    try:
        i=s._domain._intent(ep,'SOL_ADD',1,0,quantity=100)
        s._submit_intent(i,100,100,.01,2,ts_now=5);run_ticks(e,[tick(SOL_PERP,6),tick(SOL_PERP,7)])
        # In-flight original add was already admitted before the S latch.
        add=s._domain._intent(ep,'SOL_ADD',1,1,quantity=20)
        order=s.order_factory.limit(SOL_PERP.id,OrderSide.BUY,SOL_PERP.make_qty(D(20)),SOL_PERP.make_price(D(90)),time_in_force=TimeInForce.GTC)
        oid=str(order.client_order_id);s._pending_by_order[oid]=add;s._sigma_by_order[oid]=.01;s._decision_index_by_order[oid]=2;s.submit_order(order)
        marks(s,H1,'100','97');s._next_observe_settled(D(5000),H1,H1-1)
        age=ep.sol_first_fill_at;sigma=ep.fixed_sigma
        # beta2*100SOL*97 > 100BTC*100; lower BTC position makes dominance true.
        s._split_parent['planref_v1_beta']=2.
        if variant=='R2':
            s._next_observe_settled(D(5000),H1,H1-60_000_000_000)
            run_ticks(e,[tick(BTC_PERP,H1),tick(SOL_PERP,H1,'97')])
        else:
            s._next_closed_bar(bar(SOL1,H1,97));run_ticks(e,[tick(SOL_PERP,H1+1,'97')])
        assert s._next_s['remaining']==50 and ep.sol_qty==100
        # Real late fill after cancellation request; wait until native terminal.
        run_ticks(e,[tick(SOL_PERP,H1+2,'89',size='20')]);assert ep.sol_qty>=50
        for n in range(3,15):run_ticks(e,[tick(SOL_PERP,H1+n,'89',size='10')])
        assert ep.sol_qty==50 and s._hb_position(SOL_PERP.id).quantity.as_decimal()==50
        assert s._next_s['remaining']==50 and not ep.sol_half_done
        assert ep.sol_first_fill_at==age and ep.fixed_sigma==sigma
        future=s._domain._intent(ep,'SOL_ADD',1,2,quantity=5)
        s._submit_intent(future,89,89,.01,2,ts_now=H1+20)
        assert future.id not in ep.pending and ep.sol_qty==50
        assert len([x for x in s.next_band_audit if x['event']=='S_TRIGGER'])==1
        assert not s._hb_wait_regime and s._domain.episode is ep
    finally:e.end();e.dispose()


def test_custom_closed_ohlc_never_matches_with_original_bar_execution_true():
    import test_wave_native_integration as f
    from nautilus_trader.model.identifiers import ClientId
    class Resting(NativeProbe):
        def on_quote_tick(self,q):
            if q.ts_event==1:
                self.test_order=self.order_factory.limit(BTC_PERP.id,OrderSide.BUY,BTC_PERP.make_qty(D(1)),BTC_PERP.make_price(D(90)),time_in_force=TimeInForce.GTC)
                self.submit_order(self.test_order)
            super().on_quote_tick(q)
    s=Resting(cfg(research_wait_persist=True,signal_client_id=ClientId('NEXT_TEST')))
    e=f.BacktestEngine(f.BacktestEngineConfig(logging=f.LoggingConfig(log_level="ERROR")))
    e.add_venue(venue=f.SIM,oms_type=f.OmsType.NETTING,account_type=f.AccountType.MARGIN,starting_balances=[f.Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,default_leverage=D(1),bar_execution=True)
    e.add_instrument(BTC_PERP);e.add_instrument(SOL_PERP);e.add_strategy(s)
    try:
        e.add_data([next_closed_bar(BTC_PERP.id,4,D(100),D(200),D(1),D(100),H4)],client_id=s.config.signal_client_id)
        run_ticks(e,[tick(BTC_PERP,1)])
        assert len(s._next_bars)==1 # genuine native custom callback received
        assert not e.cache.positions_open() and e.cache.order(s.test_order.client_order_id).is_open
        run_ticks(e,[tick(BTC_PERP,H4+1,'100')]);assert not e.cache.positions_open()
        run_ticks(e,[tick(BTC_PERP,H4+2,'89')]);assert e.cache.positions_open()[0].quantity.as_decimal()==1
    finally:e.end();e.dispose()


def test_z_cancel_ack_late_risk_fill_before_ordinary_tp_no_fake_sol_rights():
    class Delayed(NativeProbe):
        def cancel_order(self,order,*a,**kw):return
        def _queue_confirmed_btc_targets(self,*a,**kw):pass
    s,e,ep=held(z=True,cls=Delayed)
    try:
        task=s._next_z=s._next_z_state(5)
        assert task is not None
        task.update(armed=True,triggered=True,armed_ns=4)
        risk=s._domain._intent(ep,'BTC_REDUCE',-1,None,quantity=3,reason=Z_REASON)
        s._next_risk_intents[risk.id]=task
        order=s.order_factory.limit(BTC_PERP.id,OrderSide.SELL,BTC_PERP.make_qty(D(3)),BTC_PERP.make_price(D(110)),time_in_force=TimeInForce.GTC,reduce_only=True)
        oid=str(order.client_order_id);s._pending_by_order[oid]=risk;s._sigma_by_order[oid]=None;s._decision_index_by_order[oid]=2;s.submit_order(order)
        ordinary=s._domain._intent(ep,'BTC_REDUCE',-1,2,quantity=1,reason='BTC_TP3')
        s._queued_intents.append((ordinary,None,2));s._queued_intent_ready_ns[ordinary.id]=6
        run_ticks(e,[tick(BTC_PERP,6,'100')]);assert task['canceled'] and ep.btc_open_qty==100
        assert ordinary.id in ep.pending and not ep.sol_rights
        run_ticks(e,[tick(BTC_PERP,7,'111'),tick(BTC_PERP,8,'111')])
        assert ep.btc_open_qty==96 and sum(ep.btc_risk_retired_lots.values())==3000
        assert ep.sol_rights=={2} and ep.btc_tp_filled_lots.get(2)==1000
        assert not s._pending_by_order and not s._queued_intents
    finally:e.end();e.dispose()


@pytest.mark.parametrize('minute',[False,True])
def test_residual_native_flat_single_frozen_target_preserves_rights(minute):
    s,e,ep=held(s=True,side=-1,research_sol_residual=True,research_sol_minute=minute)
    try:
        add=s._domain._intent(ep,'SOL_ADD',1,0,quantity=100)
        s._submit_intent(add,100,100,.01,2,ts_now=5)
        run_ticks(e,[tick(SOL_PERP,6),tick(SOL_PERP,7)])
        for order in s.cache.orders_open():
            if order.instrument_id==BTC_PERP.id:s.cancel_order(order)
        close=s._domain._intent(ep,'BTC_REDUCE',1,2,quantity=100)
        s._submit_intent(close,100,100,None,2,ts_now=8)
        run_ticks(e,[tick(BTC_PERP,9),tick(BTC_PERP,10)])
        assert s._next_residual_btc_flat(ep,s._split_parent)
        rights=set(ep.sol_rights);retired=dict(ep.btc_risk_retired_lots)
        age=ep.sol_first_fill_at;sigma=ep.fixed_sigma
        ns=H1 if not minute else H1//60
        marks(s,ns,'100','97');s._next_observe_settled(D(5000),ns,ns-60_000_000_000)
        if not minute:s._next_closed_bar(bar(SOL1,ns,97))
        run_ticks(e,[tick(BTC_PERP,ns,'100'),tick(SOL_PERP,ns,'97')])
        assert s._next_s['remaining']==50
        for n in range(1,5):run_ticks(e,[tick(SOL_PERP,ns+n,'97')])
        assert ep.sol_qty==50 and s._hb_position(SOL_PERP.id).quantity.as_decimal()==50
        assert len([x for x in s.next_band_audit if x['event']=='S_TRIGGER'])==1
        assert ep.sol_rights==rights and ep.btc_risk_retired_lots==retired
        assert ep.sol_first_fill_at==age and ep.fixed_sigma==sigma and not ep.sol_half_done
        future=s._domain._intent(ep,'SOL_ADD',1,1,quantity=20)
        s._submit_intent(future,97,97,.01,2,ts_now=ns+10)
        assert ep.sol_qty==50 and future.id not in ep.pending
        task=s._next_s
        s._split_parent=None
        entry=s._domain._intent(ep,'BTC_ENTRY',-1,None,quantity=1)
        s._submit_intent(entry,100,100,None,2,ts_now=ns+11)
        run_ticks(e,[tick(BTC_PERP,ns+12),tick(BTC_PERP,ns+13)])
        assert s._hb_position(BTC_PERP.id) is not None
        assert s._next_s is task and task['remaining']==50
        ordinary=s._domain._intent(ep,'SOL_EXIT',-1,None,quantity=50,reason='SOL_HARD_TIMEOUT')
        s._submit_intent(ordinary,97,97,.01,2,ts_now=ns+14)
        assert task['canceled']
        run_ticks(e,[tick(SOL_PERP,ns+15,'97'),tick(SOL_PERP,ns+16,'97')])
        assert s._hb_position(SOL_PERP.id) is None
    finally:e.end();e.dispose()


@pytest.mark.parametrize('blocked',['prior','domain','split','pending','queued','native'])
def test_residual_flat_requires_all_authoritative_evidence(blocked):
    s,e,ep=held(s=True,research_sol_residual=True)
    try:
        for order in s.cache.orders_open():
            if order.instrument_id==BTC_PERP.id:s.cancel_order(order)
        close=s._domain._intent(ep,'BTC_REDUCE',-1,2,quantity=100)
        s._submit_intent(close,100,100,None,2,ts_now=5)
        run_ticks(e,[tick(BTC_PERP,6),tick(BTC_PERP,7)])
        assert s._next_residual_btc_flat(ep,s._split_parent)
        if blocked=='prior':ep.btc_initial_qty=0
        if blocked=='domain':ep.btc_open_qty=.001
        if blocked=='split':s._split_parent['closed']=False
        i=s._domain._intent(ep,'BTC_ENTRY',1,None,quantity=1)
        if blocked=='pending':s._pending_by_order['unknown-ACK']=i
        if blocked=='queued':s._queued_intents.append((i,None,2))
        if blocked=='native':
            s.submit_order(s.order_factory.market(BTC_PERP.id,OrderSide.BUY,BTC_PERP.make_qty(D(1))))
            run_ticks(e,[tick(BTC_PERP,9),tick(BTC_PERP,10)])
            ep.btc_open_qty=0 # cache disagreement must still fail closed
        assert not s._next_residual_btc_flat(ep,s._split_parent)
    finally:e.end();e.dispose()


@pytest.mark.parametrize('bad',['stale_receipt','unknown_source','stale_source','stale_quote','future_mark','stale_mark','not_minute'])
def test_minute_requires_current_causal_paired_quote_receipt_and_marks(bad):
    s,e,ep=held(s=True,side=-1,research_sol_residual=True,research_sol_minute=True)
    try:
        add=s._domain._intent(ep,'SOL_ADD',1,0,quantity=100)
        s._submit_intent(add,100,100,.01,2,ts_now=5)
        run_ticks(e,[tick(SOL_PERP,6),tick(SOL_PERP,7)])
        ns=H1
        marks(s,ns,'100','97');s._next_observe_settled(D(5000),ns,ns-60_000_000_000)
        if bad=='stale_receipt':s._next_equity_ns=ns-60_000_000_000
        if bad=='unknown_source':s._next_equity_source=None
        if bad=='stale_source':s._next_equity_source=ns-120_000_000_000
        if bad=='future_mark':marks(s,ns+1,'100','97')
        if bad=='stale_mark':marks(s,-200*DAY,'100','97')
        if bad=='not_minute':ns+=1
        run_ticks(e,[tick(BTC_PERP,ns-1 if bad=='stale_quote' else ns),tick(SOL_PERP,ns,'97')])
        assert s._next_s is None
    finally:e.end();e.dispose()


def test_new_flags_default_off_and_dependency_validation():
    c=lifecycle_config()
    assert not c.research_sol_residual and not c.research_sol_minute
    with pytest.raises(ValueError,match='RESIDUAL_REQUIRES_S'):NativeProbe(cfg(research_sol_residual=True))
    with pytest.raises(ValueError,match='MINUTE_REQUIRES_RESIDUAL_S'):NativeProbe(cfg(research_sol_dominant=True,research_sol_minute=True))


def test_r2_real_observer_receipt_precedes_paired_quote_and_native_cut_once(tmp_path):
    from coinmaster.research.minute_risk import NativeMinuteRiskRecorder,observed_strategy_type
    from coinmaster.venues.marks import venue_mark
    r=NativeMinuteRiskRecorder(tmp_path/'risk.csv.gz',D(10000),(BTC_PERP,SOL_PERP),
        {BTC_PERP.id:D(40),SOL_PERP.id:D(20)},10*H1)
    s,e,ep=held(s=True,side=-1,cls=observed_strategy_type(NativeProbe,r),
        research_sol_residual=True,research_sol_minute=True)
    try:
        add=s._domain._intent(ep,'SOL_ADD',1,0,quantity=100)
        s._submit_intent(add,100,100,.01,2,ts_now=5)
        run_ticks(e,[tick(SOL_PERP,6),tick(SOL_PERP,7)])
        ts=[H1//60,2*H1//60,3*H1//60]
        r.set_week([SimpleNamespace(open_time_ms=t//1_000_000-60000,
            btc_mark={k:'100' for k in ('open','high','low','close')},
            sol_mark={k:'55' for k in ('open','high','low','close')}) for t in ts])
        for n,t in enumerate(ts):
            e.add_data([venue_mark(BTC_PERP.id,D(100),t),venue_mark(SOL_PERP.id,D(55),t)],
                client_id=s.config.mark_client_id)
            run_ticks(e,[tick(BTC_PERP,t),tick(SOL_PERP,t,'55')])
            if n==0:assert s._next_s is None and r.receipt_count==0
            if n==1:
                assert r.receipt_count==1 and s._next_equity_ns==t
                assert s._next_equity/s._next_peak<D('.6')
                assert s._next_s['remaining']==50
        assert len([x for x in s.next_band_audit if x['event']=='S_TRIGGER'])==1
        assert any(x['event']=='RISK_FILL' and x['kind']=='S' for x in s.next_band_audit)
        assert ep.sol_qty==50
    finally:r.file.close();r.receipt_file.close();e.end();e.dispose()


@pytest.mark.parametrize('minute',[False,True])
def test_real_fractional_split_native_tp_flat_carry_cut_with_domain_dust(tmp_path,minute):
    from coinmaster.research.minute_risk import NativeMinuteRiskRecorder,observed_strategy_type
    from coinmaster.venues.marks import venue_mark
    r=NativeMinuteRiskRecorder(tmp_path/'risk.csv.gz',D(10000),(BTC_PERP,SOL_PERP),
        {BTC_PERP.id:D(40),SOL_PERP.id:D(20)},10*H1)
    cls=observed_strategy_type(NativeProbe,r)
    s=cls(cfg(research_sol_dominant=True,research_sol_residual=True,research_sol_minute=minute,
        research_btc_split50=True,research_btc_split_planref_v1=True,
        research_btc_split_tp_ioc=True,candidate=Candidate(btc_tp_fractions_initial_qty=(.2125,.2125,.575))))
    e=native_engine(s)
    try:
        run_ticks(e,[tick(BTC_PERP,1)])
        prepare_day(s,2,-1)
        ep=s._domain.episode=Episode('fractional-native',-1,10000,1,wave_levels=(0.,0.,.03))
        i=s._domain._intent(ep,'BTC_ENTRY',-1,None,quantity=9.105)
        s._submit_intent(i,100,100,.01,2,ts_now=2)
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,5,'101')])
        p=s._split_parent
        assert p['first_filled']==D('4.552') and p['filled']==D('9.105') and p['closed']
        assert ep.btc_initial_qty==4.552+4.553
        # Original positive TP3 fills natively first, exactly as actual Jan9.
        run_ticks(e,[tick(BTC_PERP,6,'97'),tick(BTC_PERP,7,'97')])
        assert ep.btc_tp_filled_lots.get(2)==5237
        # The original zero TP slots close on the next accepted decision.
        for level in (0,1):
            leaves=ep.btc_tp_target_lots[level]-ep.btc_tp_filled_lots.get(level,0)
            assert leaves==1934
            i=s._domain._intent(ep,'BTC_REDUCE',1,level,quantity=float(D(leaves)*BTC_PERP.size_increment.as_decimal()))
            s._submit_intent(i,100,100,None,2,ts_now=8+level*2)
            run_ticks(e,[tick(BTC_PERP,9+level*2),tick(BTC_PERP,10+level*2)])
        assert ep.btc_open_qty==4.440892098500626e-16
        assert s._hb_position(BTC_PERP.id) is None and not s._next_busy(BTC_PERP.id)
        assert s._next_residual_btc_flat(ep,p)
        # No assignment to parent/domain BTC state: actual native callbacks own it.
        i=s._domain._intent(ep,'SOL_ADD',1,0,quantity=100)
        s._submit_intent(i,100,100,.01,2,ts_now=13)
        run_ticks(e,[tick(SOL_PERP,14),tick(SOL_PERP,15)])
        assert ep.sol_qty==100
        rights=set(ep.sol_rights);retired=dict(ep.btc_risk_retired_lots)
        ts=[H1//60,H1,H1+H1//60]
        r.set_week([SimpleNamespace(open_time_ms=t//1_000_000-60000,
            btc_mark={k:'100' for k in ('open','high','low','close')},
            sol_mark={k:'55' for k in ('open','high','low','close')}) for t in ts])
        # First receipt comes from a real preceding minute; H1 quote then cuts.
        if minute:ts=[H1-H1//60,H1,H1+H1//60];r.set_week([SimpleNamespace(open_time_ms=t//1_000_000-60000,btc_mark={k:'100' for k in ('open','high','low','close')},sol_mark={k:'55' for k in ('open','high','low','close')}) for t in ts])
        for t in ts:
            e.add_data([venue_mark(BTC_PERP.id,D(100),t),venue_mark(SOL_PERP.id,D(55),t)],client_id=s.config.mark_client_id)
            if not minute and t==H1:s._next_closed_bar(bar(SOL1,H1,55))
            run_ticks(e,[tick(BTC_PERP,t),tick(SOL_PERP,t,'55')])
        assert ep.sol_qty==50
        triggers=[x for x in s.next_band_audit if x['event']=='S_TRIGGER']
        assert len(triggers)==1 and triggers[0]['residual_btc_flat']
        assert s._next_s['remaining']==50 and ep.sol_rights==rights and ep.btc_risk_retired_lots==retired
    finally:r.file.close();r.receipt_file.close();e.end();e.dispose()


@pytest.mark.parametrize('qty,allowed',[('0',True),('0.000999999',True),('0.001',False),('0.002',False),('-0.000001',False)])
def test_residual_domain_native_quantum_conflicts(qty,allowed):
    s,e,ep=held(s=True,research_sol_residual=True)
    try:
        for order in s.cache.orders_open():
            if order.instrument_id==BTC_PERP.id:s.cancel_order(order)
        i=s._domain._intent(ep,'BTC_REDUCE',-1,2,quantity=100)
        s._submit_intent(i,100,100,None,2,ts_now=5)
        run_ticks(e,[tick(BTC_PERP,6),tick(BTC_PERP,7)])
        ep.btc_open_qty=float(qty)
        assert s._next_residual_btc_flat(ep,s._split_parent)==allowed
    finally:e.end();e.dispose()
