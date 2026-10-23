from decimal import Decimal as D
import json
import pytest
from coinmaster.domain.wave_overlay import Episode
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
from coinmaster.strategy.system_contract import child_quantity
from test_wave_native_integration import lifecycle_config, native_engine
from test_native_episode_risk import NativeProbe, tick, run_ticks, marks


def persist(s,e,name):
    import os
    from pathlib import Path
    destination=os.environ.get('SC01_ARTIFACT_DIR')
    if not destination:return
    directory=Path(destination);directory.mkdir(parents=True,exist_ok=True)
    payload=s.reporting_state()
    payload['native_orders']=[dict(id=str(o.client_order_id),status=o.status.name,
        quantity=str(o.quantity),filled_quantity=str(o.filled_qty),
        commissions=[str(x) for x in o.commissions()]) for o in e.cache.orders()]
    (directory/(name+'.json')).write_text(json.dumps(payload,sort_keys=True,indent=2))
    e.trader.generate_order_fills_report().to_csv(directory/(name+'-fills.csv'))
    e.trader.generate_account_report(SOL_PERP.id.venue).to_csv(directory/(name+'-account.csv'))


def setup(explicit=True):
    s=NativeProbe(lifecycle_config(research_sol_explicit_child=explicit))
    e=native_engine(s)
    run_ticks(e,[tick(SOL_PERP,1,"1")])
    s._domain.episode=Episode("sc01",1,10000,1,wave_levels=(.01,.02,.03),h=10000)
    s._bind_native_lots()
    return s,e,s._domain.episode


def submit(s,ep,qty,level=0,ns=2):
    i=s._domain._intent(ep,"SOL_ADD",-1,level,requested_notional=float(qty))
    s._submit_intent(i,1,1,None,0,ts_now=ns)
    return i


@pytest.mark.parametrize("requested",["500","1000","2500"])
@pytest.mark.parametrize("depth",["500","1000","2000"])
@pytest.mark.parametrize("explicit",[False,True])
def test_native_request_depth_matrix(requested,depth,explicit):
    s,e,ep=setup(explicit)
    try:
        run_ticks(e,[tick(SOL_PERP,2,"1",size=depth)])
        i=submit(s,ep,D(requested),ns=3)
        run_ticks(e,[tick(SOL_PERP,4,"1",size=depth)])
        orders=e.cache.orders()
        assert len(orders)==1
        order=orders[0]
        allowed=min(D(requested),D(1000)) if explicit else D(requested)
        assert order.quantity.as_decimal()==allowed
        assert order.filled_qty.as_decimal()==min(allowed,D(depth))
        assert order.status.name==("FILLED" if allowed<=D(depth) else "CANCELED")
        print("SC01_MATRIX",requested,depth,explicit,order.status.name,str(order.filled_qty),str(ep.sol_qty))
        persist(s,e,f"matrix-{requested}-{depth}-{explicit}")
        if explicit:
            row=s._sc_attempts[i.id]
            assert D(row['filled_quantity'])==order.filled_qty.as_decimal()
            assert row['native_status']==order.status.name
            assert D(row['unused_right_notional'])==D(requested)-order.filled_qty.as_decimal()
            assert json.loads(json.dumps(s.reporting_state()))['system_contract_audit']
    finally:
        e.end();e.dispose()


@pytest.mark.parametrize("depth",["500","1000","2000"])
def test_two_native_levels_shared_liquidity(depth):
    s,e,ep=setup()
    try:
        run_ticks(e,[tick(SOL_PERP,2,"1",size=depth)])
        submit(s,ep,D(2500),0,3);submit(s,ep,D(2500),1,3)
        run_ticks(e,[tick(SOL_PERP,4,"1",size=depth)])
        orders=e.cache.orders()
        print("SC01_SHARED",depth,[(o.status.name,str(o.filled_qty)) for o in orders])
        persist(s,e,"shared-"+depth)
        assert all(o.filled_qty.as_decimal()==min(D(1000),D(depth)) for o in orders)
        assert len(orders)==2
        assert sum((o.quantity.as_decimal() for o in orders),D(0))==2000
        assert D(str(ep.sol_qty))==sum((o.filled_qty.as_decimal() for o in orders),D(0))
        json.loads(json.dumps(s.reporting_state()))
    finally:
        e.end();e.dispose()


def test_child_lot_and_invalid_inputs():
    assert child_quantity(D('1000.09'),D('.1'))==1000
    assert child_quantity(D('.09'),D('.1'))==0
    for qty,step in [(D('NaN'),D('.1')),(D(1),D(0)),(D(-1),D('.1'))]:
        with pytest.raises(ValueError):child_quantity(qty,step)


def test_original_right_schedule_and_unused_rights():
    from coinmaster.domain.wave_overlay import WaveOverlayState, Candidate, Features
    from test_wave_overlay import bars
    from datetime import timedelta
    source=bars(2);f=Features(0,1,1.,1.,0.,1.,3.)
    state=WaveOverlayState(Candidate())
    ep=state.episode=Episode("rights",1,10000,1.,btc_initial_qty=1,btc_open_qty=1,
        btc_entry_vwap=source[0].btc_close,btc_reference_qty=2500/source[0].btc_close,h=2500,wave_levels=(9,9,9),sol_rights={0,1})
    intents=state.decide(source,[f,f],0,10000)
    assert {i.level for i in intents}=={0,1}
    for i in intents:
        state.on_fill(i.id,1000,1,source[0].close_time)
        state.on_parent_terminal(i.id)
    assert state.decide(source,[f,f],0,10000)==[]
    again=state.decide(source,[f,f],1,10000)
    assert {i.level for i in again}=={0,1}
    assert [i.requested_notional for i in again]==[1500,2750]
    for i in again:state.on_parent_terminal(i.id)
    ep.sol_add_filled_notional={0:2500,1:3750}
    assert state.decide(source,[f,f],1,10000)==[]


@pytest.mark.parametrize("mode",["rejected","canceled","late_fill","denied"])
def test_actual_native_receipts_terminal_and_late_fill(mode):
    from nautilus_trader.model.enums import OrderSide, TimeInForce
    from nautilus_trader.model.objects import Quantity
    class Delayed(NativeProbe):
        def cancel_order(self,order,*a,**kw):
            if mode=="late_fill":return
            return super().cancel_order(order,*a,**kw)
    s=Delayed(lifecycle_config(research_sol_explicit_child=True));e=native_engine(s)
    try:
        run_ticks(e,[tick(SOL_PERP,1,"1")]);ep=s._domain.episode=Episode("receipts",1,10000,1,h=10000)
        i=s._domain._intent(ep,"SOL_ADD",1,0,requested_notional=1000)
        q=s._sc_sol_quantity(i,D(1000),D('.1'),D(1),2)
        # Native GTC permits delayed cancel/fill races without invented events.
        order=s.order_factory.limit(SOL_PERP.id,OrderSide.BUY,
            Quantity.from_str('1.01') if mode=='denied' else SOL_PERP.make_qty(q),
            SOL_PERP.make_price(D(2) if mode=='rejected' else D('.5')),
            time_in_force=TimeInForce.GTC,post_only=mode=='rejected')
        s._sc_bind(i,order);oid=str(order.client_order_id)
        s._pending_by_order[oid]=i;s._sigma_by_order[oid]=None;s._decision_index_by_order[oid]=0
        s.submit_order(order)
        run_ticks(e,[tick(SOL_PERP,3,"1")])
        if mode in ('canceled','late_fill'):
            s.cancel_order(order)
            if mode=="canceled":run_ticks(e,[tick(SOL_PERP,4,"1")])
            run_ticks(e,[tick(SOL_PERP,5,".5")])
        expected={'rejected':'REJECTED','canceled':'CANCELED','late_fill':'FILLED','denied':'DENIED'}[mode]
        persist(s,e,"lifecycle-"+mode)
        assert order.status.name==expected
        assert s._sc_attempts[i.id]['native_status']==expected
        assert ep.sol_qty==(1000 if mode=='late_fill' else 0)
        assert D(s._sc_attempts[i.id]['unused_right_notional'])==(500 if mode=='late_fill' else 1000)
        json.loads(json.dumps(s.reporting_state()))
    finally:e.end();e.dispose()


def test_local_margin_denial_preserves_right_and_original_attempt():
    class Denied(NativeProbe):
        def _tier_allows_increase(self,*args):return False
    s=Denied(lifecycle_config(research_sol_explicit_child=True));e=native_engine(s)
    try:
        run_ticks(e,[tick(SOL_PERP,1,"1")]);ep=s._domain.episode=Episode("margin",1,10000,1,h=10000)
        i=submit(s,ep,D(2500))
        assert not e.cache.orders()
        row=s._sc_attempts[i.id]
        assert row['native_status']=='LOCAL_UNSENT' and row['submitted_quantity']=='0'
        assert row['unused_right_notional']=='2500.0' and not ep.sol_add_filled_notional
    finally:e.end();e.dispose()


def test_same_fill_money_rights_depth1000_explicit_vs_large_ioc():
    receipts=[]
    for explicit in [False,True]:
        s,e,ep=setup(explicit)
        try:
            submit(s,ep,D(2500));run_ticks(e,[tick(SOL_PERP,4,"1",size='1000')])
            order=e.cache.orders()[0]
            account=e.cache.account_for_venue(SOL_PERP.id.venue)
            receipts.append((order.status.name,order.filled_qty.as_decimal(),ep.sol_qty,
                dict(ep.sol_add_filled_notional),str(account.balance_total(SOL_PERP.quote_currency)),
                str(account.margin_init(SOL_PERP.id)),len(s._pending_by_order)))
        finally:e.end();e.dispose()
    assert receipts[0][0]=='CANCELED' and receipts[1][0]=='FILLED'
    assert receipts[0][1:]==receipts[1][1:]


@pytest.mark.parametrize('explicit',[False,True])
def test_actual_advance_clock_both_levels_one_original_attempt_per_d1(explicit):
    from datetime import timedelta
    from types import SimpleNamespace as NS
    from coinmaster.domain.wave_overlay import Features,DailyBar
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
    from test_native_btc_sizing import prepare_day
    class ClockProbe(WaveOverlayStrategy):
        # Only the unrelated tier policy is fixed; real _advance_current_day,
        # domain batch construction, native callbacks and queued executor run.
        def _tier_allows_increase(self,*args):return True
    s=ClockProbe(lifecycle_config(research_sol_explicit_child=explicit));e=native_engine(s)
    try:
        run_ticks(e,[tick(SOL_PERP,1,'1')]);prepare_day(s)
        ns=int(s._bars[-1].close_time.timestamp()*1_000_000_000)
        s._current_btc=NS(ts_event=ns);s._current_sol=NS(ts_event=ns)
        s._last_accepted_session=s._latest_seen_session=ns
        marks(s,ns,btc='1',sol='1')
        s._current_btc_mark=s._latest_marks[BTC_PERP.id];s._current_sol_mark=s._latest_marks[SOL_PERP.id]
        s._current_signals=[Features(n,1,1.,.03,0.,.01,3.) for n in range(3)]
        ep=s._domain.episode=Episode('clock',1,10000,1.,btc_initial_qty=25,btc_open_qty=25,
            btc_entry_vwap=100.,btc_reference_qty=25.,h=2500.,wave_levels=(9,9,9),sol_rights={0,1})
        s._advance_current_day()
        batch=[i for i,_,_ in s._queued_intents]
        assert {i.level for i in batch}=={0,1} and len(batch)==2
        assert ep.attempted_sol_at=={0:2,1:2}
        run_ticks(e,[tick(SOL_PERP,ns+60_000_000_000,'1'),tick(SOL_PERP,ns+120_000_000_000,'1')])
        original=e.cache.orders()
        assert len(original)==2 and all(o.filled_qty.as_decimal()==1000 for o in original)
        assert all(o.status.name==('FILLED' if explicit else 'CANCELED') for o in original)
        assert not s._queued_intents
        assert ep.attempted_sol_at=={0:2,1:2}
        s._advance_current_day()
        run_ticks(e,[tick(SOL_PERP,ns+180_000_000_000,'1')])
        assert len(e.cache.orders())==2 and not s._queued_intents
        # Same genuine unused rights become eligible only on next D1.
        previous=s._bars[-1];end=previous.close_time+timedelta(days=1);next_ns=int(end.timestamp()*1_000_000_000)
        s._bars.append(DailyBar(previous.close_time,end,end,100.,100.,100.))
        s._current_signals.append(Features(3,1,1.,.03,0.,.01,3.))
        s._current_btc=s._current_sol=NS(ts_event=next_ns)
        s._last_accepted_session=s._latest_seen_session=next_ns
        marks(s,next_ns,btc='1',sol='1');s._current_btc_mark=s._latest_marks[BTC_PERP.id];s._current_sol_mark=s._latest_marks[SOL_PERP.id]
        s._advance_current_day()
        assert {i.level for i,_,_ in s._queued_intents}=={0,1}
        assert ep.attempted_sol_at=={0:3,1:3}
        assert len(e.cache.orders())==2
    finally:e.end();e.dispose()
