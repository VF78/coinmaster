from datetime import datetime, UTC, timedelta
from decimal import Decimal as D
import pytest
from nautilus_trader.model.enums import OrderSide, TimeInForce, BarAggregation
from coinmaster.domain.wave_overlay import Episode
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from test_native_split_cover import cfg, seed_beta, HOUR
from test_native_h1_b1 import confirmation_types, bar
from test_native_episode_risk import NativeProbe, tick, run_ticks, marks
from test_native_btc_sizing import prepare_day
from test_wave_native_integration import native_engine


def config(**kw):
    return cfg(True).__replace__(research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,
        research_conditional_sol=True,research_confirmation_bars=confirmation_types(),**kw)


def setup(side=1,probe=NativeProbe,qty=100):
    s=probe(config());e=native_engine(s)
    run_ticks(e,[tick(BTC_PERP,1)])
    prepare_day(s,2,side);marks(s,2);seed_beta(s,1)
    ep=s._domain.episode=Episode('conditional',side,10000,1,wave_levels=(.5,.6,.7),h=10000)
    i=s._domain._intent(ep,'BTC_ENTRY',side,None,quantity=qty)
    s._submit_intent(i,100,100,.01,0,ts_now=2)
    run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,5,'99' if side==1 else '101'),tick(SOL_PERP,6)])
    return s,e,ep


def protect(s,e,ep,ts=10,tf=15):
    price='96' if ep.side==1 else '104'
    marks(s,ts,price,'100')
    run_ticks(e,[tick(BTC_PERP,ts,price),tick(SOL_PERP,ts+1)])
    kind=next(k for k in s.config.research_confirmation_bars if k.instrument_id==SOL_PERP.id and (k.spec.aggregation==BarAggregation.MINUTE)==(tf==15))
    s.on_bar(bar(kind,ts-1,100,101,99))
    s.on_bar(bar(kind,ts+2,98 if ep.side==1 else 102))
    assert not s._conditional['active']
    run_ticks(e,[tick(SOL_PERP,ts+3)])
    return s._conditional


def original(s,e,ep,qty,ts=30):
    ep.sol_rights.add(0);ep.sol_right_fraction[0]=1
    i=s._domain._intent(ep,'SOL_ADD',-ep.side,0,quantity=qty,reason='SOL_ADD')
    s._submit_intent(i,100,100,.02,0,ts_now=ts)
    run_ticks(e,[tick(SOL_PERP,ts)])
    return i


@pytest.mark.parametrize('side',[1,-1])
@pytest.mark.parametrize('tf',[15,60])
def test_conditional_actual_btc_arm_closed_sol_or_next_fresh_quote_native_off(side,tf):
    s,e,ep=setup(side)
    try:
        c=protect(s,e,ep,tf=tf)
        assert c['active'] and c['qc']>0
        assert ep.sol_qty==0 and not ep.sol_adds and not ep.sol_add_filled_notional
        held=next(p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)
        assert held==c['qc']
        marks(s,20,str(ep.btc_entry_vwap),'100')
        run_ticks(e,[tick(BTC_PERP,20,str(ep.btc_entry_vwap)),tick(SOL_PERP,21)])
        assert not c['active']
        assert not any(p.instrument_id==SOL_PERP.id for p in e.cache.positions_open())
        assert not ep.sol_rights
    finally:e.end();e.dispose()


def test_protective_inventory_original_adoption_is_not_native_fill_or_cash_replay():
    s,e,ep=setup()
    try:
        c=protect(s,e,ep);before=len(s.fill_audit)
        cash=e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()
        original(s,e,ep,10)
        assert ep.sol_qty==10
        assert ep.sol_ownership_transfer_credit[0]==1000
        assert ep.sol_add_filled_notional=={} and ep.sol_adds==set()
        assert ep.sol_first_fill_at is None and ep.sol_first_owned_at is not None
        assert len(s.fill_audit)==before
        assert e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()==cash
        assert c['original_target']==10
        marks(s,40,str(ep.btc_entry_vwap),'100')
        run_ticks(e,[tick(BTC_PERP,40,str(ep.btc_entry_vwap)),tick(SOL_PERP,41)])
        held=next(p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)
        assert held==10==D(str(ep.sol_qty))
    finally:e.end();e.dispose()


def test_original_first_protect_topup_then_original_full_release_does_not_restore_rights():
    s,e,ep=setup()
    try:
        original(s,e,ep,10,7)
        assert ep.sol_qty==10 and ep.sol_add_filled_notional[0]==1000
        c=protect(s,e,ep,ts=10)
        assert c['active'] and c['qc']>10
        assert ep.sol_qty==10
        oldnotional=dict(ep.sol_add_filled_notional)
        exit=s._domain._intent(ep,'SOL_EXIT',ep.side,None,quantity=10,reason='SOL_Z_FULL_EXIT')
        s._submit_intent(exit,100,100,None,0,ts_now=30)
        run_ticks(e,[tick(SOL_PERP,30)])
        assert c['original_target']==0 and ep.sol_qty==0
        assert ep.sol_add_filled_notional==oldnotional
        assert any(r['event']=='RELEASE_ORIGINAL' for r in s.conditional_audit)
    finally:e.end();e.dispose()


def test_denied_original_admission_has_atomic_zero_credit_and_clock():
    s,e,ep=setup()
    try:
        c=protect(s,e,ep)
        s._tier_allows_increase=lambda *a:False
        i=original(s,e,ep,10)
        assert i.id not in ep.pending
        assert ep.sol_qty==0 and c['original_target']==0
        assert not ep.sol_ownership_transfer_credit and ep.sol_first_owned_at is None
    finally:e.end();e.dispose()


def test_original_half_and_timeout_release_original_budget_only():
    s,e,ep=setup()
    try:
        c=protect(s,e,ep);original(s,e,ep,20)
        s._bind_native_lots();ep.sol_half_target_lots=100
        i=s._domain._intent(ep,'SOL_HALF_EXIT',ep.side,None,quantity=10,reason='SOL_Z_HALF_EXIT')
        s._submit_intent(i,100,100,None,0,ts_now=40);run_ticks(e,[tick(SOL_PERP,40)])
        assert ep.sol_qty==10 and ep.sol_half_done
        assert ep.sol_half_filled_lots==0 and ep.sol_half_released_lots==100
        i=s._domain._intent(ep,'SOL_EXIT',ep.side,None,quantity=10,reason='SOL_HARD_TIMEOUT')
        s._preempt_with_mandatory_sol_exit(i,None,0)
        run_ticks(e,[tick(SOL_PERP,50)])
        assert ep.sol_qty==0 and c['original_target']==0
        assert next(p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)==c['qc']
    finally:e.end();e.dispose()


def test_unknown_ack_blocks_off_trim_until_known_terminal_no_orphan():
    s,e,ep=setup()
    try:
        c=protect(s,e,ep)
        i=s._domain._intent(ep,'SOL_ADD',-ep.side,None,quantity=1,reason='CONDITIONAL_NET_ADD')
        s._pending_by_order['UNKNOWN_ACK']=i
        before=len(e.cache.orders())
        marks(s,30,str(ep.btc_entry_vwap),'100')
        run_ticks(e,[tick(BTC_PERP,30,str(ep.btc_entry_vwap)),tick(SOL_PERP,31)])
        assert not c['active'] and len(e.cache.orders())==before
        s._pending_by_order.pop('UNKNOWN_ACK');s._domain.on_parent_terminal(i.id)
        run_ticks(e,[tick(SOL_PERP,32)])
        assert not any(p.instrument_id==SOL_PERP.id for p in e.cache.positions_open())
    finally:e.end();e.dispose()


def test_btc_partial_reduces_qc_and_btc_flat_preserves_original_budget():
    s,e,ep=setup()
    try:
        c=protect(s,e,ep);original(s,e,ep,10)
        before=c['qc']
        s.submit_order(s.order_factory.market(BTC_PERP.id,OrderSide.SELL,BTC_PERP.make_qty(50),time_in_force=TimeInForce.IOC,reduce_only=True))
        run_ticks(e,[tick(BTC_PERP,40,'96'),tick(SOL_PERP,41)])
        assert c['qc']<before
        s.submit_order(s.order_factory.market(BTC_PERP.id,OrderSide.SELL,BTC_PERP.make_qty(50),time_in_force=TimeInForce.IOC,reduce_only=True))
        run_ticks(e,[tick(BTC_PERP,42,'96'),tick(SOL_PERP,43),tick(SOL_PERP,44)])
        assert c["qc"]==0 and c["original_target"]==10 and ep.sol_qty==10
        assert len(e.cache.positions_open())==1 and e.cache.positions_open()[0].quantity.as_decimal()==10
        s._begin_forced_close("REGIME")
        run_ticks(e,[tick(BTC_PERP,45),tick(SOL_PERP,46),tick(SOL_PERP,47)])
        assert not e.cache.positions_open() and not s._pending_by_order
    finally:e.end();e.dispose()


@pytest.mark.parametrize('outcome',['denied','rejected'])
def test_original_needing_increment_rejected_before_fill_cannot_adopt_inventory(outcome):
    from nautilus_trader.model.events import OrderDenied,OrderRejected
    from nautilus_trader.core.uuid import UUID4
    from nautilus_trader.model.identifiers import AccountId
    class Hold(NativeProbe):
        hold=False
        def submit_order(self,order,*a,**kw):
            i=self._pending_by_order.get(str(order.client_order_id))
            if self.hold and i and i.reason=='CONDITIONAL_NET_ADD':
                self.held=order;return
            return super().submit_order(order,*a,**kw)
    s,e,ep=setup(probe=Hold)
    try:
        c=protect(s,e,ep);s.hold=True
        original(s,e,ep,40)
        assert ep.sol_qty==0 and not ep.sol_ownership_transfer_credit
        assert hasattr(s,'held')
        o=s.held
        if outcome=='denied':
            ev=OrderDenied(o.trader_id,o.strategy_id,o.instrument_id,o.client_order_id,'TEST_DENIED',UUID4(),31)
            s.on_order_denied(ev)
        else:
            ev=OrderRejected(o.trader_id,o.strategy_id,o.instrument_id,o.client_order_id,AccountId('P1SIM-001'),'TEST_REJECTED',UUID4(),31,31)
            s.on_order_rejected(ev)
        assert c['original_target']==0 and not c['adds']
        assert ep.sol_qty==0 and not ep.sol_ownership_transfer_credit and ep.sol_first_owned_at is None
    finally:e.end();e.dispose()


def test_accepted_btc_second_half_reserved_while_protecting_only_actual_first_fill():
    s=NativeProbe(config());e=native_engine(s)
    try:
        run_ticks(e,[tick(BTC_PERP,1)]);prepare_day(s,2);marks(s,2);seed_beta(s,1)
        ep=s._domain.episode=Episode('partial-entry',1,10000,1,wave_levels=(.5,.6,.7))
        i=s._domain._intent(ep,'BTC_ENTRY',1,None,quantity=100)
        s._submit_intent(i,100,100,.01,0,ts_now=2);run_ticks(e,[tick(BTC_PERP,3)])
        s._pending_by_order['UNKNOWN_BTC_ACK']=i
        c=protect(s,e,ep)
        assert c['active'] and s._split_parent['filled']==50
        assert c['qc']==(D('.5')*D(50)*D(96)/c['beta']/D(100)//D('.1'))*D('.1')
        assert s._split_cover_margin_reserve(BTC_PERP.id,D(50),14)==100
        s._pending_by_order.pop('UNKNOWN_BTC_ACK')
        run_ticks(e,[tick(BTC_PERP,4*HOUR+20,'96'),tick(BTC_PERP,4*HOUR+21,'96')])
        assert s._split_parent['filled']==s._split_parent['quantity']==100
    finally:e.end();e.dispose()


def test_large_conditional_native_partial_trim_has_no_orphan_or_false_flat():
    s,e,ep=setup()
    try:
        marks(s,10,'96','1');run_ticks(e,[tick(BTC_PERP,10,'96'),tick(SOL_PERP,11,'1')])
        kind=s.config.research_confirmation_bars[2]
        s.on_bar(bar(kind,9,1,1.01,.99));s.on_bar(bar(kind,12,.98))
        for ts in range(13,18):run_ticks(e,[tick(SOL_PERP,ts,'1')])
        held=next(p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)
        assert held==s._conditional['qc'] and held==D('3199.9') and held>1000
        s.submit_order(s.order_factory.market(BTC_PERP.id,OrderSide.SELL,BTC_PERP.make_qty(100),time_in_force=TimeInForce.IOC,reduce_only=True))
        run_ticks(e,[tick(BTC_PERP,20,'96'),tick(SOL_PERP,21,'1')])
        assert any(p.instrument_id==SOL_PERP.id for p in e.cache.positions_open())
        for ts in range(22,26):run_ticks(e,[tick(SOL_PERP,ts,'1')])
        assert not e.cache.positions_open() and not s._pending_by_order
        closes=[D(x['qty']) for x in s.fill_audit if x['reason']=='CONDITIONAL_NET_EXIT']
        assert sum(closes)==held and max(closes)<=1000
    finally:e.end();e.dispose()


@pytest.mark.parametrize('tf',[15,60])
def test_connected_native_stream_original_transfer_recovery_fees_journal_and_flat(tmp_path,tf):
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.cache.config import CacheConfig
    from nautilus_trader.data.config import DataEngineConfig
    from nautilus_trader.model.data import BarType,BarSpecification
    from nautilus_trader.model.enums import AccountType,OmsType,AggregationSource,BarAggregation,PriceType
    from nautilus_trader.model.objects import Money
    from nautilus_trader.model.identifiers import ClientId
    from coinmaster.research.native_fixture import SIM
    from coinmaster.venues.marks import venue_mark
    from coinmaster.ops.paper import PaperRuntime
    base=1725148800*1_000_000_000;minute=60_000_000_000
    confirm=30 if tf==15 else 120;activation=confirm+1;arm=16 if tf==15 else 80;end=activation+10
    journal=PaperRuntime(tmp_path/'native.sqlite','conditional-native',10**20);journal.acquire()
    class Sink:
        def __call__(self,**x):
            return journal.record_submission(client_order_id=x['client_order_id'],intent_id=x['intent_id'],episode_id=x['episode_id'],action=x['action'],instrument_id=x['instrument_id'],quantity=x['quantity'],reduce_only=x['reduce_only'])
        def acknowledge(self,x):journal.acknowledge_submission(x)
        def terminal(self,x):journal.terminal_submission(x)
    class Probe(NativeProbe):
        started=False;adopted=False;closed_original=False;closing=False
        def on_quote_tick(self,q):
            m=(q.ts_event-base)//minute
            if not self.started and q.instrument_id==BTC_PERP.id:
                self.started=True;prepare_day(self,q.ts_event);seed_beta(self,base)
                ep=self._domain.episode=Episode('stream',1,10000,1,wave_levels=(.005,.6,.7))
                i=self._domain._intent(ep,'BTC_ENTRY',1,None,requested_notional=10000)
                self._queued_intents.append((i,.01,0));self._queued_intent_ready_ns[i.id]=q.ts_event
            super().on_quote_tick(q)
            ep=self._domain.episode
            if q.instrument_id==SOL_PERP.id and ep and m==activation+1 and not self.adopted:
                self.adopted=True
                assert 0 in ep.sol_rights
                i=self._domain._intent(ep,'SOL_ADD',-1,0,quantity=1,reason='SOL_ADD')
                self._submit_intent(i,float(q.bid_price),float(q.ask_price),.02,0,ts_now=q.ts_event)
            if q.instrument_id==SOL_PERP.id and ep and m==activation+6 and not self.closed_original:
                self.closed_original=True
                i=self._domain._intent(ep,'SOL_EXIT',1,None,quantity=ep.sol_qty,reason='SOL_Z_FULL_EXIT')
                self._submit_intent(i,float(q.bid_price),float(q.ask_price),None,0,ts_now=q.ts_event)
            if m==end and not self.closing:
                self.closing=True;self._begin_forced_close('REGIME')
    s=Probe(config(event_sink=journal.record_native_event,submission_sink=Sink()))
    e=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR'),cache=CacheConfig(bar_capacity=128),data_engine=DataEngineConfig(time_bars_build_with_no_updates=False)))
    e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,bar_execution=False)
    e.add_instrument(BTC_PERP);e.add_instrument(SOL_PERP);e.add_strategy(s)
    bars=[];markdata=[];quotes=[]
    for m in range(1,end+4):
        ts=base+m*minute
        bp=D('101') if m==10 else D('96') if arm<=m<activation+5 else D('99.5') if m>=activation+5 else D('99') if m>=3 else D(100)
        sp=D(100)
        if tf==15 and m>=16:sp=D(99)
        if tf==60 and 61<=m<=75:sp=D(90)
        if tf==60 and m>=76:sp=D(95)
        for inst,px in ((BTC_PERP,bp),(SOL_PERP,sp)):
            kind=BarType(inst.id,BarSpecification(1,BarAggregation.MINUTE,PriceType.LAST),AggregationSource.EXTERNAL)
            bars.append(bar(kind,ts,px));markdata.append(venue_mark(inst.id,px,ts));quotes.append(tick(inst,ts,str(px)))
    try:
        e.add_data(bars,sort=False);e.add_data(markdata,client_id=ClientId('TEST_MARKS'),sort=False);e.add_data(quotes,sort=False);e.sort_data();e.run(streaming=True);e.clear_data()
        active=[x for x in s.conditional_audit if x['event']=='ACTIVATE']
        assert len(active)==1 and active[0]['timeframe_minutes']==tf, s.conditional_audit
        assert active[0]['confirmation_bar_ns']==base+confirm*minute
        assert active[0]['timestamp_ns']==base+activation*minute
        assert any(x['event']=='TRANSFER_TO_ORIGINAL' for x in s.conditional_audit)
        assert any(x['event']=='OFF' for x in s.conditional_audit)
        assert not e.cache.positions_open() and not s._pending_by_order
        assert journal.pending_submissions()==[]
        assert any(x['kind']=='fill' for x in journal.events())
        assert all(D(x['commission'])>0 for x in s.fill_audit)
        from coinmaster.research.native_baseline import save_diagnostic_report
        import json
        output={"native_adapter":s.reporting_state(),"conditional_sol_audit":s.conditional_audit}
        path=save_diagnostic_report(tmp_path,output,artifact_dir=tmp_path)
        assert path.read_text()==json.dumps(output,indent=2,sort_keys=True)+chr(10)
        assert json.loads(path.read_text())["conditional_sol_audit"]==s.conditional_audit
        realized=sum((p.realized_pnl.as_decimal() for p in e.cache.positions_closed()),D(0))
        assert e.cache.account_for_venue(SIM).balance_total().as_decimal()==D(10000)+realized
    finally:e.end();e.dispose();journal.close()


def test_conditional_cancel_unknown_ack_late_partial_native_fill_then_exact_trim():
    class DelayedCancel(NativeProbe):
        delay=False
        canceled=[]
        def cancel_order(self,order,*a,**kw):
            if self.delay and order.instrument_id==SOL_PERP.id:
                self.canceled.append(order.client_order_id);return
            return super().cancel_order(order,*a,**kw)
    s,e,ep=setup(probe=DelayedCancel)
    try:
        c=protect(s,e,ep)
        held=next(p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)
        i=s._domain._intent(ep,'SOL_ADD',-1,None,quantity=10,reason='CONDITIONAL_NET_ADD')
        o=s.order_factory.limit(SOL_PERP.id,OrderSide.SELL,SOL_PERP.make_qty(10),SOL_PERP.make_price(101),time_in_force=TimeInForce.GTC)
        s._pending_by_order[str(o.client_order_id)]=i;s.submit_order(o);s.delay=True
        marks(s,30,str(ep.btc_entry_vwap),str(100));run_ticks(e,[tick(BTC_PERP,30,str(ep.btc_entry_vwap))])
        assert s.canceled and str(o.client_order_id) in s._pending_by_order
        run_ticks(e,[tick(SOL_PERP,31,price=str(101),size=str(4))])
        assert o.filled_qty.as_decimal()==4 and o.leaves_qty.as_decimal()==6
        assert next(p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)==held+4
        assert not any(x["event"]=="TRIM" and x["timestamp_ns"]>=30 for x in s.conditional_audit)
        s.delay=False;s.cancel_order(o);run_ticks(e,[tick(SOL_PERP,32),tick(SOL_PERP,33)])
        assert not any(p.instrument_id==SOL_PERP.id for p in e.cache.positions_open())
        assert not any(x.action.startswith("SOL") for x in s._pending_by_order.values())
        assert ep.sol_qty==0 and not ep.sol_add_filled_notional and not ep.sol_ownership_transfer_credit
    finally:e.end();e.dispose()


def test_original_signal_during_pending_native_reduce_waits_cancel_ack_before_transfer():
    s,e,ep=setup()
    try:
        c=protect(s,e,ep)
        held=next(p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)
        i=s._domain._intent(ep,'SOL_EXIT',1,None,quantity=float(held),reason='CONDITIONAL_NET_EXIT')
        o=s.order_factory.limit(SOL_PERP.id,OrderSide.BUY,SOL_PERP.make_qty(held),SOL_PERP.make_price(1),time_in_force=TimeInForce.GTC,reduce_only=True)
        s._pending_by_order[str(o.client_order_id)]=i;s.submit_order(o)
        original(s,e,ep,10)
        assert o.is_canceled and o.filled_qty.as_decimal()==0
        run_ticks(e,[tick(SOL_PERP,31)])
        assert ep.sol_qty==10 and ep.sol_ownership_transfer_credit
        assert not ep.sol_add_filled_notional
        assert next(p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)==held
    finally:e.end();e.dispose()


def test_conditional_default_off_does_not_create_owner_or_consume_original_native_fields():
    s=NativeProbe(cfg(True,research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True));e=native_engine(s)
    try:
        run_ticks(e,[tick(BTC_PERP,1)])
        assert not s.config.research_conditional_sol and s._conditional is None and s.conditional_audit==[]
    finally:e.end();e.dispose()


def test_conditional_latched_quantity_has_no_price_only_churn():
    s,e,ep=setup()
    try:
        c=protect(s,e,ep);q=c["qc"];before=len(s.fill_audit)
        marks(s,40,"95","110")
        run_ticks(e,[tick(BTC_PERP,40,"95"),tick(SOL_PERP,41,"110")])
        assert c["active"] and c["qc"]==q and len(s.fill_audit)==before
        original(s,e,ep,10,ts=42)
        assert c["qc"]==q and ep.sol_qty==10 and len(s.fill_audit)==before
        assert len([x for x in s.conditional_audit if x["event"]=="QC_LATCH"])==1
    finally:e.end();e.dispose()


@pytest.mark.parametrize("route",["release","native","mixed"])
def test_original_logical_half_then_natural_later_full_z_exit(route):
    from coinmaster.domain.wave_overlay import DailyBar,Features
    s,e,ep=setup()
    try:
        c=protect(s,e,ep)
        original(s,e,ep,20 if route=="release" else 40)
        if route=="native":
            marks(s,35,str(ep.btc_entry_vwap),"100")
            run_ticks(e,[tick(BTC_PERP,35,str(ep.btc_entry_vwap)),tick(SOL_PERP,36)])
        first=datetime(1970,1,1,tzinfo=UTC)
        b=DailyBar(first,first+timedelta(seconds=1),first+timedelta(seconds=1),100,100,100)
        f=Features(0,1,1.,1.,0.,1.,0.)
        half=s._domain._sol_exits(ep,f,b,0,z=0.)[0]
        assert half.action=="SOL_HALF_EXIT"
        before_fills=len(s.fill_audit)
        s._submit_intent(half,100,100,None,0,ts_now=40)
        run_ticks(e,[tick(SOL_PERP,40),tick(SOL_PERP,41)])
        applied=max(0,len(s._bars)-1)
        assert ep.sol_half_done and ep.sol_half_decision_index==applied
        assert s._domain._sol_exits(ep,f,b,applied,z=0.)==[]
        full=s._domain._sol_exits(ep,f,b,applied+1,z=0.)[0]
        assert full.action=="SOL_EXIT" and full.reason=="SOL_Z_FULL_EXIT"
        if route=="release":
            assert ep.sol_half_released_lots>0 and ep.sol_half_filled_lots==0
            assert len(s.fill_audit)==before_fills
        elif route=="native":
            assert ep.sol_half_filled_lots>0 and ep.sol_half_released_lots==0
        else:
            assert ep.sol_half_filled_lots>0 and ep.sol_half_released_lots>0
        s._submit_intent(full,100,100,None,1,ts_now=42)
        run_ticks(e,[tick(SOL_PERP,42),tick(SOL_PERP,43)])
        assert ep.sol_qty==0 and c["original_target"]==0
    finally:e.end();e.dispose()


def test_original_transfer_sigma_preserved_when_later_native_original_adds():
    s,e,ep=setup()
    try:
        c=protect(s,e,ep);original(s,e,ep,10)
        owned=ep.sol_first_owned_at
        assert ep.fixed_sigma==.02 and ep.sol_first_fill_at is None
        ep.sol_rights.add(1);ep.sol_right_fraction[1]=1
        i=s._domain._intent(ep,"SOL_ADD",-1,1,quantity=30,reason="SOL_ADD")
        s._submit_intent(i,100,100,.07,1,ts_now=40)
        run_ticks(e,[tick(SOL_PERP,40),tick(SOL_PERP,41)])
        assert ep.sol_qty==40 and ep.sol_add_filled_notional[1]>0
        assert ep.sol_first_fill_at is not None and ep.sol_first_owned_at==owned
        assert ep.fixed_sigma==.02 and ep.sol_ownership_transfer_credit
    finally:e.end();e.dispose()


def test_real_production_runner_builds_conditional_with_original_overlay_enabled(tmp_path,monkeypatch):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from test_native_baseline import write_streaming_fixture
    from coinmaster.research.native_baseline import run_native_diagnostic,MINUTE_MS,DAY_MS,TRADING_START_MS
    start,end=write_streaming_fixture(tmp_path,trading_days=1)
    shift=TRADING_START_MS-start
    for path in (tmp_path/"normalized").glob("*.parquet"):
        rows=pq.read_table(path).to_pylist()
        for row in rows:row["open_time_ms"]+=shift
        pq.write_table(pa.Table.from_pylist(rows),path)
    from coinmaster.domain.wave_overlay import Candidate
    accepted=[];constructor=WaveOverlayStrategy.__init__
    def checked(self,config):
        constructor(self,config)
        accepted.append(config)
    monkeypatch.setattr(WaveOverlayStrategy,"__init__",checked)
    result=run_native_diagnostic(tmp_path,candidate=Candidate(btc_notional_multiplier=7.875,max_parent_notional=30_000_000),trading_start_ms=TRADING_START_MS,trading_end_ms=TRADING_START_MS+2*MINUTE_MS,
        warmup_start_ms=shift,research_v0_execution_repairs=True,research_v0_deferred_selective_zero_tp=True,
        research_v0_selective_lifecycle_repairs=True,research_btc_direction_sizing=True,
        research_btc_split50=True,research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,
        research_conditional_sol=True,artifact_dir=tmp_path/"production")
    assert len(accepted)==1 and accepted[0].candidate.sol_overlay_enabled
    assert accepted[0].research_conditional_sol and accepted[0].research_h1_b1 is None
    assert len(accepted[0].research_confirmation_bars)==4 and len(accepted[0].research_cover_hour_seed)==721
    assert result["config"]["research_conditional_sol"] and result["conditional_sol_audit"]==[]
    assert result["streaming"]["processed_rows_per_source"]==2 and result["terminal_open_positions"]==0


@pytest.mark.parametrize("reason",["REGIME","TRAIL","CLOSE_ALL"])
def test_tp3_flat_after_protection_off_retains_episode_until_authorized_group_close(reason):
    from coinmaster.domain.wave_overlay import DailyBar,Features
    s,e,ep=setup()
    try:
        c=protect(s,e,ep)
        marks(s,20,str(ep.btc_entry_vwap),"100")
        run_ticks(e,[tick(BTC_PERP,20,str(ep.btc_entry_vwap)),tick(SOL_PERP,21)])
        assert not c["active"] and not any(p.instrument_id==SOL_PERP.id for p in e.cache.positions_open())
        run_ticks(e,[tick(BTC_PERP,30,"171"),tick(SOL_PERP,31),tick(BTC_PERP,32,"171"),tick(SOL_PERP,33)])
        for ts in range(34,40):run_ticks(e,[tick(BTC_PERP,ts,"171"),tick(SOL_PERP,ts)])
        assert not e.cache.positions_open() and not s._pending_by_order, (s.fill_audit,s._queued_intents,s._pending_by_order)
        assert any(x["reason"]=="BTC_TP3" for x in s.fill_audit)
        assert s._domain.episode is ep and not s._group_close_reconciliation_pending
        first=datetime(1970,1,1,tzinfo=UTC)
        daily=DailyBar(first,first+timedelta(days=1),first+timedelta(days=1),100,100,100)
        feature=Features(0,ep.side,1.,1.,None,None,None)
        decisions=s._domain.decide([daily],[feature],0,10000)
        assert not any(x.action=="BTC_ENTRY" for x in decisions)
        assert s._domain.episode is ep
        close=s._domain._intent(ep,"CLOSE_ALL",-ep.side,None,reason=reason)
        s._begin_forced_close(reason,close)
        run_ticks(e,[tick(BTC_PERP,40),tick(SOL_PERP,41)])
        assert s._domain.episode is None and not e.cache.positions_open() and not s._pending_by_order
    finally:e.end();e.dispose()



def test_original_1000_after_btc_tp3_flat_late_pending_partial_add_then_native_regime_2000():
    class HoldLate(NativeProbe):
        hold=False
        def submit_order(self,order,*a,**kw):
            i=self._pending_by_order.get(str(order.client_order_id))
            if self.hold and i and i.reason=="CONDITIONAL_NET_ADD":
                self.held=order;return
            return super().submit_order(order,*a,**kw)
    s,e,ep=setup(probe=HoldLate)
    try:
        marks(s,10,"96","1")
        run_ticks(e,[tick(BTC_PERP,10,"96"),tick(SOL_PERP,11,"1")])
        kind=s.config.research_confirmation_bars[2]
        s.on_bar(bar(kind,9,1,1.01,.99));s.on_bar(bar(kind,12,.98))
        for ts in range(13,18):run_ticks(e,[tick(SOL_PERP,ts,"1")])
        c=s._conditional
        run_ticks(e,[tick(BTC_PERP,20,"151"),tick(SOL_PERP,21,"1")])
        assert 0 in ep.sol_rights
        i=s._domain._intent(ep,"SOL_ADD",-1,0,quantity=1000,reason="SOL_ADD")
        s._submit_intent(i,1,1,.02,0,ts_now=22)
        run_ticks(e,[tick(SOL_PERP,22,"1")])
        assert ep.sol_qty==1000
        owned=ep.sol_first_owned_at
        for ts in range(30,40):run_ticks(e,[tick(BTC_PERP,ts,"171"),tick(SOL_PERP,ts,"1")])
        assert not any(p.instrument_id==BTC_PERP.id for p in e.cache.positions_open())
        assert any(x["reason"]=="BTC_TP3" for x in s.fill_audit)
        assert c["qc"]==0 and c["original_target"]==1000 and ep.sol_qty==1000
        assert next(p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)==1000
        assert s._domain.episode is ep and ep.sol_first_owned_at==owned
        assert 1 in ep.sol_rights
        late=s._domain._intent(ep,"SOL_ADD",-1,1,quantity=1000,reason="SOL_ADD")
        s.hold=True;s._submit_intent(late,1,1,.07,1,ts_now=40)
        run_ticks(e,[tick(SOL_PERP,40,"1")])
        assert c["original_target"]==2000 and c["adds"] and ep.sol_qty==1000
        # Native accepted/resting venue receipt models delayed IOC terminal/ACK;
        # same owner/id/quantity, real matching and partial fills, no fill replay.
        held=s.held;s.hold=False
        o=s.order_factory.limit(SOL_PERP.id,OrderSide.SELL,SOL_PERP.make_qty(1000),SOL_PERP.make_price(D("1.01")),
            time_in_force=TimeInForce.GTC,client_order_id=held.client_order_id)
        s.submit_order(o)
        run_ticks(e,[tick(SOL_PERP,41,"1.01",size="400")])
        assert not o.is_closed and o.filled_qty.as_decimal()==800 and o.leaves_qty.as_decimal()==200
        assert ep.sol_qty==1800 and c["adds"] and not c["active"]
        run_ticks(e,[tick(SOL_PERP,42,"1.01")])
        assert o.is_closed and o.filled_qty.as_decimal()==1000 and ep.sol_qty==2000 and not c["adds"]
        assert ep.sol_first_owned_at==owned and ep.fixed_sigma==.02
        assert ep.sol_add_filled_notional[1]==1010 and ep.sol_ownership_transfer_credit[0]==1000
        assert not any(x["reason"]=="CONDITIONAL_BTC_FLAT" for x in s.fill_audit)
        before=len(s.fill_audit);s._begin_forced_close("REGIME")
        for ts in range(43,47):run_ticks(e,[tick(SOL_PERP,ts,"1.01")])
        closes=[D(x["qty"]) for x in s.fill_audit[before:] if x["reason"]=="REGIME"]
        assert closes==[D(1000),D(1000)]
        assert not e.cache.positions_open() and not s._pending_by_order and s._domain.episode is None
    finally:e.end();e.dispose()



def test_original_ioc_two_cycle_unarmed_native_off_on_account_fee_exit_clock_parity(tmp_path):
    from coinmaster.domain.wave_overlay import DailyBar,Features
    from coinmaster.ops.paper import PaperRuntime
    base=1725148800*1_000_000_000;minute=60_000_000_000;day=24*60*minute
    t=lambda d,m=20:base+d*day+m*minute
    plan={t(0):("ADD",3505,0,.02,10),t(1):("ADD",2505,0,.02,11),
          t(2):("ADD",1505,0,.02,12),t(3):("ADD",505,0,.02,13),
          t(4):("HALF",None,None,None,20),t(5):("FULL",None,None,None,21),
          t(6):("ADD",1200,1,.04,30),t(7):("ADD",200,1,.04,31),
          t(8):("HALF",None,None,None,40),t(9):("FULL",None,None,None,41)}
    quiet={t(0)+minute,t(0)+2*minute,t(0)+3*minute,t(1)+minute,t(2)+minute,t(6)+minute,t(6)+2*minute}
    settle={t(4)+minute,t(4)+2*minute,t(5)+minute,t(5)+2*minute}
    snapshots_at=(set(plan)-{t(4),t(5)})|{t(4)+2*minute,t(5)+2*minute}
    snapshots=[];outcomes=[]
    for enabled in (False,True):
        journal=PaperRuntime(tmp_path/("ab-on.sqlite" if enabled else "ab-off.sqlite"),"original-ioc-ab",10**20);journal.acquire()
        class AB(NativeProbe):
            scripted=False
            last_add_count=0
            records=[]
            def on_quote_tick(self,q):
                if self.scripted:marks(self,q.ts_event,"100","1")
                super().on_quote_tick(q)
                if not self.scripted or q.instrument_id!=SOL_PERP.id:return
                ep=self._domain.episode
                if q.ts_event in quiet:
                    assert len([x for x in self.fill_audit if x["instrument"].startswith("SOL") and x["action"]=="SOL_ADD"])==self.last_add_count
                if q.ts_event not in plan:return
                action,qty,level,sigma,index=plan[q.ts_event]
                assert ep is not None
                self._domain._decision_index=index
                if action=="ADD":
                    assert level in ep.sol_rights
                    intent=self._domain._intent(ep,"SOL_ADD",-ep.side,level,quantity=qty,reason="SOL_ADD")
                else:
                    now=datetime.fromtimestamp(q.ts_event/1e9,UTC)
                    b=DailyBar(now-timedelta(days=1),now,now,100,100,1)
                    f=Features(index,ep.side,1.,1.,0.,1.,0.)
                    intents=self._domain._sol_exits(ep,f,b,index,z=.3 if action=="HALF" else 0.)
                    assert len(intents)==1
                    intent=intents[0]
                    assert intent.action==("SOL_HALF_EXIT" if action=="HALF" else "SOL_EXIT")
                self._submit_intent(intent,1,1,sigma,index,ts_now=q.ts_event)
        s=AB(config().__replace__(research_conditional_sol=enabled,event_sink=journal.record_native_event));e=native_engine(s)
        try:
            run_ticks(e,[tick(BTC_PERP,base+1)])
            prepare_day(s,base+2);marks(s,base+2,"100","1");seed_beta(s,base)
            ep=s._domain.episode=Episode("native-ab",1,10000,1,wave_levels=(.5,.6,.7))
            i=s._domain._intent(ep,"BTC_ENTRY",1,None,quantity=100)
            s._submit_intent(i,100,100,.01,0,ts_now=base+2)
            run_ticks(e,[tick(BTC_PERP,base+3),tick(BTC_PERP,base+4),tick(BTC_PERP,base+5,"99"),tick(SOL_PERP,base+6,"1")])
            s.scripted=True
            times=sorted(set(plan)|quiet|settle|{base+10*minute,t(6)-minute})
            for ts in times:
                bp="151" if ts==base+10*minute else "161" if ts==t(6)-minute else "100"
                run_ticks(e,[tick(BTC_PERP,ts,bp),tick(SOL_PERP,ts,"1")])
                if ts in snapshots_at:
                    s.last_add_count=len([x for x in s.fill_audit if x["instrument"].startswith("SOL") and x["action"]=="SOL_ADD"])
                    s.records.append({"time":ts,"qty":ep.sol_qty,"first_native":ep.sol_first_fill_at,
                        "first_owned":ep.sol_first_owned_at,"sigma":ep.fixed_sigma,"native_notional":dict(ep.sol_add_filled_notional),
                        "transfer_credit":dict(ep.sol_ownership_transfer_credit),"half_done":ep.sol_half_done,
                        "half_index":ep.sol_half_decision_index,"original_pending":sum(i.action.startswith("SOL") for i in ep.pending.values())})
                    assert s.records[-1]["original_pending"]==0
                    if enabled:
                        assert s._conditional["original_target"]==D(str(ep.sol_qty))
                        assert not s._conditional["original_attempts"] and not s._conditional["adds"]

            assert ep.sol_qty==0 and ep.sol_first_owned_at is None
            if enabled:assert not s._conditional["active"] and s._conditional["armed_ns"] is None
            snapshots.append(s.records)
            s._begin_forced_close("REGIME")
            for ts in range(t(9)+minute,t(9)+minute+3):run_ticks(e,[tick(BTC_PERP,ts),tick(SOL_PERP,ts,"1")])
            assert not e.cache.positions_open() and not s._pending_by_order and s._domain.episode is None
            fields=("fill_ns","instrument","px","qty","notional","commission","commission_currency","native_liquidity_side","order_type","post_only")
            sfills=[{k:x[k] for k in fields} for x in s.fill_audit if x["instrument"].startswith("SOL")]
            assert all(x["native_liquidity_side"]=="TAKER" and x["post_only"]=="false" for x in sfills)
            assert sum((D(x["commission"]) for x in sfills),D(0))==D(9410)*D(str(SOL_PERP.taker_fee))
            orders=[{"quantity":str(o.quantity),"filled":str(o.filled_qty),"type":int(o.order_type),
                "tif":int(o.time_in_force),"reduce_only":o.is_reduce_only,"closed":o.is_closed,"status":int(o.status),
                "init":o.ts_init,"last":o.ts_last} for o in e.cache.orders() if o.instrument_id==SOL_PERP.id]
            account=e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()
            fees=sum((D(x["commission"]) for x in s.fill_audit),D(0))
            flow=sum((o.filled_qty.as_decimal()*D(str(o.avg_px))*(1 if o.side==OrderSide.SELL else -1) for o in e.cache.orders() if o.filled_qty.as_decimal()>0),D(0))
            realized=flow-fees
            assert account==D(10000)+realized and any(x["kind"]=="fill" for x in journal.events())
            outcomes.append({"native_SOL_fills":sfills,"native_SOL_orders":orders,"account":account,
                "all_native_fees":sum((D(x["commission"]) for x in s.fill_audit),D(0)),"realized":realized})
        finally:e.end();e.dispose();journal.close()
    assert snapshots[0]==snapshots[1]
    assert outcomes[0]==outcomes[1]



def test_original_ioc_terminal_drops_Oshortfall_but_active_Qc_reconciles_protective_only():
    class Hold(NativeProbe):
        hold=False
        def submit_order(self,order,*a,**kw):
            i=self._pending_by_order.get(str(order.client_order_id))
            if self.hold and i and i.reason=="CONDITIONAL_NET_ADD":self.held=order;return
            return super().submit_order(order,*a,**kw)
    s,e,ep=setup(probe=Hold)
    try:
        marks(s,7,"100",".4");run_ticks(e,[tick(BTC_PERP,8,"151"),tick(SOL_PERP,8,".4")])
        assert 0 in ep.sol_rights
        s.hold=True
        i=s._domain._intent(ep,"SOL_ADD",-1,0,quantity=3505,reason="SOL_ADD")
        s._submit_intent(i,.4,.4,.02,0,ts_now=9);run_ticks(e,[tick(SOL_PERP,9,".4")])
        old=s.held;physical=s._pending_by_order[str(old.client_order_id)]
        marks(s,10,"96",".4");run_ticks(e,[tick(BTC_PERP,10,"96"),tick(SOL_PERP,11,".4")])
        kind=s.config.research_confirmation_bars[2]
        s.on_bar(bar(kind,9,.4,.41,.39));s.on_bar(bar(kind,12,.38))
        run_ticks(e,[tick(SOL_PERP,13,".4")])
        c=s._conditional
        assert c["active"] and c["qc"]>3505 and ep.sol_qty==0
        assert c["original_attempts"][physical.id]==(i.id,) and len([x for x in s._pending_by_order.values() if x.action=="SOL_ADD"])==1
        s.hold=False;NativeProbe.submit_order(s,old)
        for ts in range(14,24):run_ticks(e,[tick(SOL_PERP,ts,".4")])
        assert e.cache.order(old.client_order_id).is_closed and e.cache.order(old.client_order_id).filled_qty.as_decimal()==1000
        assert c["original_target"]==1000 and ep.sol_qty==1000 and not c["adds"] and not c["original_attempts"]
        assert ep.sol_add_filled_notional[0]==400 and not ep.sol_ownership_transfer_credit
        assert next(p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)==c["qc"]
        future=[x for x in s.conditional_audit if x["event"]=="NATIVE_FILL" and x["physical_intent"]!=physical.id]
        assert future and all(D(x["original_native_quantity"])==0 for x in future)
        assert sum((D(x["conditional_native_quantity"]) for x in future),D(0))>0
        s._begin_forced_close("REGIME")
        for ts in range(30,42):run_ticks(e,[tick(BTC_PERP,ts,"96"),tick(SOL_PERP,ts,".4")])
        assert not e.cache.positions_open() and not s._pending_by_order
        account=e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()
        assert account==D(10000)+sum((p.realized_pnl.as_decimal() for p in e.cache.positions_closed()),D(0))
    finally:e.end();e.dispose()


@pytest.mark.parametrize("terminal",["denied","rejected","expired","partial_cancel"])
def test_original_attempt_terminal_cannot_release_or_fill_newer_authorization(terminal):
    from types import SimpleNamespace
    from nautilus_trader.model.events import OrderDenied,OrderRejected
    from nautilus_trader.core.uuid import UUID4
    from nautilus_trader.model.identifiers import AccountId
    class Hold(NativeProbe):
        hold=False;old_physical=None;observed=None
        def submit_order(self,order,*a,**kw):
            i=self._pending_by_order.get(str(order.client_order_id))
            if self.hold and i and i.reason=="CONDITIONAL_NET_ADD":self.held=order;return
            return super().submit_order(order,*a,**kw)
        def _conditional_attempt_terminal(self,intent,ts,cause,order_id=None):
            bound=self._conditional is not None and intent is not None and intent.id in self._conditional["original_attempts"]
            super()._conditional_attempt_terminal(intent,ts,cause,order_id)
            if bound and intent.id==self.old_physical:
                self.observed={"remaining":{t["intent"].id:t["remaining"] for t in self._conditional["adds"]},
                    "desired":self._conditional["original_target"],"new_native_notional":self._domain.episode.sol_add_filled_notional.get(1),
                    "new_credit":self._domain.episode.sol_ownership_transfer_credit.get(1)}
    s,e,ep=setup(probe=Hold)
    try:
        marks(s,7,"100","1");run_ticks(e,[tick(BTC_PERP,8,"161"),tick(SOL_PERP,8,"1"),tick(BTC_PERP,9,"161")])
        assert {0,1}<=ep.sol_rights
        s.hold=True
        old_intent=s._domain._intent(ep,"SOL_ADD",-1,0,quantity=3505,reason="SOL_ADD")
        s._submit_intent(old_intent,1,1,.02,0,ts_now=10);run_ticks(e,[tick(SOL_PERP,10,"1")])
        old=s.held;s.old_physical=s._pending_by_order[str(old.client_order_id)].id
        new=s._domain._intent(ep,"SOL_ADD",-1,1,quantity=200,reason="SOL_ADD")
        s._submit_intent(new,1,1,.07,1,ts_now=11)
        run_ticks(e,[tick(SOL_PERP,11,"1"),tick(SOL_PERP,12,"1")])
        assert s._conditional["original_target"]==3705 and ep.sol_qty==0
        assert s._conditional["original_attempts"][s.old_physical]==(old_intent.id,)
        before=e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()
        if terminal=="partial_cancel":
            NativeProbe.submit_order(s,old);run_ticks(e,[tick(SOL_PERP,13,"1")])
        elif terminal=="denied":
            s.on_order_denied(OrderDenied(old.trader_id,old.strategy_id,old.instrument_id,old.client_order_id,"DENIED",UUID4(),13))
        elif terminal=="rejected":
            s.on_order_rejected(OrderRejected(old.trader_id,old.strategy_id,old.instrument_id,old.client_order_id,AccountId("P1SIM-001"),"REJECTED",UUID4(),13,13))
        else:s.on_order_expired(SimpleNamespace(client_order_id=old.client_order_id))
        assert s.observed["remaining"]=={new.id:D(200)}
        assert s.observed["desired"]==D(1200 if terminal=="partial_cancel" else 200)
        assert s.observed["new_native_notional"] is None and s.observed["new_credit"] is None
        if terminal!="partial_cancel":
            assert e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()==before
        run_ticks(e,[tick(SOL_PERP,14,"1"),tick(SOL_PERP,15,"1")])
        newer=s.held;assert newer.client_order_id!=old.client_order_id
        s.hold=False;NativeProbe.submit_order(s,newer)
        run_ticks(e,[tick(SOL_PERP,16,"1"),tick(SOL_PERP,17,"1")])
        assert ep.sol_add_filled_notional[1]==200 and not s._conditional["adds"]
        assert ep.sol_qty==(1200 if terminal=="partial_cancel" else 200)
        assert s._conditional["original_target"]==D(str(ep.sol_qty))
        assert not ep.sol_ownership_transfer_credit
        s._begin_forced_close("REGIME")
        for ts in range(20,25):run_ticks(e,[tick(BTC_PERP,ts),tick(SOL_PERP,ts,"1")])
        assert not e.cache.positions_open() and not s._pending_by_order
        account=e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()
        assert account==D(10000)+sum((p.realized_pnl.as_decimal() for p in e.cache.positions_closed()),D(0))
    finally:e.end();e.dispose()
