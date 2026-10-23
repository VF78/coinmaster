from datetime import UTC,datetime,timedelta
from decimal import Decimal as D
from types import SimpleNamespace
import pytest
from coinmaster.domain.wave_overlay import Candidate,DailyBar,Episode
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP
from coinmaster.strategy.next_band import DAY,SB_REASON
from test_native_next_band import cfg,held
from test_native_episode_risk import NativeProbe,marks,run_ticks,tick
from test_wave_native_integration import native_engine

def config(**kw):
    return cfg(research_wait_4h=True,research_btc_split50=True,research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,**kw)

def daily(s):
    base=datetime(1970,1,1,tzinfo=UTC)
    s._bars=[DailyBar(base+timedelta(days=i),base+timedelta(days=i+1),base+timedelta(days=i+1),100,100,100) for i in range(20)]
    s._last_accepted_session=20*DAY
    s._hb_daily_ohlc={int(r.close_time.timestamp()*1e9):(110,90) for r in s._bars}
    s._next_sol_ohlc={int(r.close_time.timestamp()*1e9):(105,95) for r in s._bars}

def test_atr_completed_only_future_poison_and_gap():
    s=NativeProbe(config(research_sol_budget=True));daily(s)
    assert s._next_budget_atrs()==(D(20),D(10))
    s._next_sol_ohlc[21*DAY]=(1e15,1e-8);s._next_budget_atr_cache=None
    assert s._next_budget_atrs()==(D(20),D(10))
    s._next_sol_ohlc.pop(19*DAY);s._next_budget_atr_cache=None
    assert s._next_budget_atrs() is None

def test_exact_e4_only_and_defaults():
    c=cfg()
    assert not c.research_sol_budget and not c.research_btc_early_tp3
    with pytest.raises(ValueError,match='EXACT_E4'):
        NativeProbe(cfg(research_sol_budget=True))

def test_budget_cap_fee_dominance_no_churn_and_unused_right(monkeypatch):
    s,e,ep=held(side=-1)
    try:
        # Native SOL open under unchanged admission; then enable frozen policy
        # through the test state, without replacing native money.
        add=s._domain._intent(ep,'SOL_ADD',1,0,quantity=100)
        s._submit_intent(add,100,100,.01,2,ts_now=5)
        run_ticks(e,[tick(SOL_PERP,6),tick(SOL_PERP,7)])
        used=dict(ep.sol_add_filled_notional)
        state=dict(equity=D(6000),peak=D(10000),drawdown=D('.4'),btc_qty=D(1),sol_qty=D(100),btc_atr=D(10),sol_atr=D(10),btc_reserve=D(11),sol_fee=D('.00055'),sol_mark=D(100),cap=D(40),sol_stress=D(1000),btc_stress=D(10),daily_ns=2)
        monkeypatch.setattr(s,'_next_budget_state',lambda ns:state)
        s._next_budget_signal(10)
        assert s._next_s['remaining']==40 and s._next_budget_cut_used
        state['cap']=D(0);s._next_budget_signal(11)
        assert s._next_s['remaining']==40
        assert ep.sol_add_filled_notional==used
        s._next_s=None
        state['drawdown']=D('.1')
        assert s._next_budget_admit(D(1),D(100),12)
        state['drawdown']=D('.4');state['equity']=D(5500)
        assert not s._next_budget_admit(D(100),D(100),13)
        assert ep.sol_add_filled_notional==used
        s._next_budget_cut_used=False;state['btc_stress']=D(2000);s._next_budget_signal(14)
        assert s._next_s is None
    finally:e.end();e.dispose()

@pytest.mark.parametrize('side',[1,-1])
def test_tp3_native_sequential_actual_partial_rights_and_lots(side):
    from test_native_btc_sizing import prepare_day
    s=NativeProbe(config(research_btc_early_tp3=True,candidate=Candidate(btc_tp_fractions_initial_qty=(.2125,.2125,.575))))
    e=native_engine(s)
    run_ticks(e,[tick(BTC_PERP,1)])
    prepare_day(s,2);marks(s,2)
    ep=s._domain.episode=Episode('tp3',side,10000,1,wave_levels=(.02,.04,.10))
    entry=s._domain._intent(ep,'BTC_ENTRY',side,None,quantity=100)
    s._submit_intent(entry,100,100,.01,0,ts_now=2)
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,5,'99' if side==1 else '101')])
        assert s._split_parent['closed'] and ep.btc_initial_qty==100
        target=next(i for i,_,_ in s._queued_intents if i.level==2)
        assert target.reason=='BTC_TP3_EARLY' and target.quantity==20
        assert D(str(target.limit_price))==D(101 if side==1 else 99)
        original=dict(ep.btc_tp_target_lots)
        # Crossed positive target uses existing actual taker IOC catchup;
        # unlike this wheel's resting maker model, IOC honors finite size.
        favorable='101.1' if side==1 else '98.9'
        run_ticks(e,[tick(BTC_PERP,11,favorable,size='5')])
        assert ep.btc_tp_filled_lots[2]==5000 and ep.sol_right_fraction[2]>0
        assert 2 not in ep.btc_filled_tps
        assert not any(x.get('event')=='TP3_TRANCHE' and x.get('early') is False for x in s.next_band_audit)
        for n in range(12,19):run_ticks(e,[tick(BTC_PERP,n,favorable,size='5')])
        assert ep.btc_tp_filled_lots[2]==20000
        remaining=[i for i in s._pending_by_order.values() if i.level==2]
        assert len(remaining)==1 and remaining[0].reason=='BTC_TP3' and remaining[0].quantity==37.5
        assert BTC_PERP.make_price(D(str(remaining[0].limit_price))).as_decimal()==D(110 if side==1 else 90)
        assert ep.btc_tp_target_lots==original
        final='111' if side==1 else '89'
        run_ticks(e,[tick(BTC_PERP,20,final),tick(BTC_PERP,21,'112' if side==1 else '88'),tick(BTC_PERP,22,'113' if side==1 else '87')])
        assert ep.btc_tp_filled_lots[2]==original[2] and 2 in ep.btc_filled_tps
        assert ep.sol_right_fraction[2]==1 and not ep.btc_risk_retired_lots
    finally:e.end();e.dispose()


def test_budget_current_native_equity_stale_unknown_and_native_cut(monkeypatch):
    s,e,ep=held(side=-1)
    try:
        i=s._domain._intent(ep,'SOL_ADD',1,0,quantity=100)
        s._submit_intent(i,100,100,.01,2,ts_now=5)
        run_ticks(e,[tick(SOL_PERP,6),tick(SOL_PERP,7)])
        consumed=dict(ep.sol_add_filled_notional)
        daily(s);ns=20*DAY;marks(s,ns)
        native=s._v3_equity()
        s._next_equity=D(1) # previous receipt cannot be current monetary source
        state=s._next_budget_state(ns)
        assert state['equity']==native and state['equity']!=s._next_equity
        assert s._next_budget_state(ns+1) is None
        s._next_enabled=True
        s._next_s=dict(kind='SB',episode_id=ep.id,side=1,remaining=D(40),triggered=True,canceled=False)
        for n in range(8,18):run_ticks(e,[tick(SOL_PERP,n,size='10')])
        assert ep.sol_qty==40 and s._hb_position(SOL_PERP.id).quantity.as_decimal()==40
        assert ep.sol_add_filled_notional==consumed
        assert not ep.sol_half_done
        assert sum(D(str(x['quantity'])) for x in s.next_band_audit if x['event']=='RISK_FILL' and x['kind']=='SB')==60
    finally:e.end();e.dispose()


def test_global_peak_keeps_flat_history_even_with_unknown_atr(monkeypatch):
    s=NativeProbe(config(research_sol_budget=True));e=native_engine(s)
    try:
        run_ticks(e,[tick(BTC_PERP,1)])
        marks(s,10);monkeypatch.setattr(s,'_v3_equity',lambda:D(20000))
        s._next_budget_cut_used=True;s._next_budget_signal(10)
        assert s._next_peak==20000 and not s._next_budget_cut_used
        marks(s,11);monkeypatch.setattr(s,'_v3_equity',lambda:D(10000))
        s._next_budget_signal(11)
        assert s._next_peak==20000
    finally:e.end();e.dispose()


def test_early_native_resting_cancel_unknown_ack_and_forced_precedence():
    from test_native_btc_sizing import prepare_day
    s=NativeProbe(config(research_btc_early_tp3=True,candidate=Candidate(btc_tp_fractions_initial_qty=(.2125,.2125,.575))))
    e=native_engine(s);run_ticks(e,[tick(BTC_PERP,1)])
    prepare_day(s,2);marks(s,2)
    ep=s._domain.episode=Episode('cancel-early',1,10000,1,wave_levels=(.02,.04,.10))
    entry=s._domain._intent(ep,'BTC_ENTRY',1,None,quantity=100)
    s._submit_intent(entry,100,100,.01,0,ts_now=2)
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,5,'99'),tick(BTC_PERP,6,'100')])
        early=next(o for o in s.cache.orders_open() if s._pending_by_order[str(o.client_order_id)].reason=='BTC_TP3_EARLY')
        assert early.is_post_only and early.price.as_decimal()==101
        intent=s._pending_by_order[str(early.client_order_id)]
        s._pending_by_order['UNKNOWN_ACK']=intent
        before=len(s._queued_intents);s._queue_confirmed_btc_targets(None,0,7)
        assert len(s._queued_intents)==before and not ep.sol_rights
        s._pending_by_order.pop('UNKNOWN_ACK')
        s.cancel_order(early)
        run_ticks(e,[tick(BTC_PERP,7,'100')])
        assert not ep.sol_rights and not ep.btc_tp_filled_lots
        replacement=[i for i,_,_ in s._queued_intents if i.reason=='BTC_TP3_EARLY']+[i for i in s._pending_by_order.values() if i.reason=='BTC_TP3_EARLY']
        assert len(replacement)==1 and replacement[0].quantity==20
        s._begin_forced_close('REGIME')
        run_ticks(e,[tick(BTC_PERP,8,'100'),tick(BTC_PERP,9,'100')])
        assert not s._queued_intents and not ep.sol_rights
        assert not s.cache.orders_open()
    finally:e.end();e.dispose()


def test_budget_rejected_original_submit_keeps_native_orders_and_consumed_rights():
    from test_native_btc_sizing import prepare_day
    s=NativeProbe(config(research_sol_budget=True));e=native_engine(s)
    try:
        run_ticks(e,[tick(BTC_PERP,1)]);daily(s);ns=20*DAY;marks(s,ns)
        ep=s._domain.episode=Episode('unused-add',-1,10000,1,h=10000)
        ep.sol_rights={0};ep.sol_right_fraction={0:1.0}
        s._next_peak=D(20000)
        before=len(s.cache.orders());consumed=dict(ep.sol_add_filled_notional);rights=set(ep.sol_rights)
        i=s._domain._intent(ep,'SOL_ADD',1,0,quantity=10)
        s._submit_intent(i,100,100,.01,19,ts_now=ns)
        assert len(s.cache.orders())==before and not s._pending_by_order
        assert i.id not in ep.pending
        assert ep.sol_add_filled_notional==consumed and ep.sol_rights==rights
        assert s.next_band_audit[-1]['event']=='SB_ADD_ADMISSION' and not s.next_band_audit[-1]['allowed']
    finally:e.end();e.dispose()

def test_early_ineligible_noop_and_native_denied_before_first_fill():
    from dataclasses import replace
    from nautilus_trader.model.enums import OrderSide,TimeInForce
    from nautilus_trader.model.objects import Quantity
    from test_native_btc_sizing import prepare_day
    s=NativeProbe(config(research_btc_early_tp3=True,candidate=Candidate(btc_tp_fractions_initial_qty=(.2125,.2125,.575))))
    e=native_engine(s);run_ticks(e,[tick(BTC_PERP,1)])
    prepare_day(s,2);marks(s,2)
    ep=s._domain.episode=Episode('denied-early',1,10000,1,wave_levels=(.02,.04,.10))
    entry=s._domain._intent(ep,'BTC_ENTRY',1,None,quantity=100)
    s._submit_intent(entry,100,100,.01,0,ts_now=2)
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,5,'99')])
        item=next(x for x in s._queued_intents if x[0].reason=='BTC_TP3_EARLY');i=item[0]
        frozen=s._next_tp3_freeze;s._next_tp3_freeze=None
        ep.wave_levels=(.02,.04,.005)
        original=replace(i,reason='BTC_TP3',quantity=57.5,limit_price=100.5)
        assert s._next_tp3_target(original,5) is original
        assert not ep.sol_rights and not ep.btc_tp_filled_lots
        ep.wave_levels=(.02,.04,.10);s._next_tp3_freeze=frozen
        s._queued_intents.remove(item)
        # Fault-inject invalid wire precision; native RiskEngine generates
        # OrderDenied. No direct domain fill or fabricated callback.
        bad=s.order_factory.limit(BTC_PERP.id,OrderSide.SELL,Quantity.from_str('0.0001'),BTC_PERP.make_price(D(101)),time_in_force=TimeInForce.GTC,post_only=True,reduce_only=True)
        oid=str(bad.client_order_id);s._pending_by_order[oid]=i;s._sigma_by_order[oid]=None;s._decision_index_by_order[oid]=0
        s.submit_order(bad);run_ticks(e,[tick(BTC_PERP,6,'100')])
        assert s.cache.order(bad.client_order_id).status.name=='DENIED'
        assert not ep.sol_rights and not ep.btc_tp_filled_lots and ep.btc_open_qty==100
        replacements=[x[0] for x in s._queued_intents if x[0].reason=='BTC_TP3_EARLY']+[x for x in s._pending_by_order.values() if x.reason=='BTC_TP3_EARLY']
        assert len(replacements)==1 and replacements[0].quantity==20
    finally:e.end();e.dispose()
