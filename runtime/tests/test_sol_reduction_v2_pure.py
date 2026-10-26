"""Real Factory/Cache/Order/event METHOD replay; no matcher/positions/cash engine.

held/btc_held are explicit method-unit inventory inputs, NOT imported positions.
Public submit/modify/cancel boundaries apply constructed real event classes.
They are never native fills/financial or transport atomicity evidence.
"""
from types import SimpleNamespace as NS
from decimal import Decimal as D
from pathlib import Path
import ast,copy
import pytest
from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import TestClock
from nautilus_trader.common.factories import OrderFactory
from nautilus_trader.model.enums import OrderSide,TimeInForce,TriggerType
from nautilus_trader.model.identifiers import TraderId,StrategyId,ClientOrderId,TradeId
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.events import OrderCancelRejected
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.test_kit.stubs.events import TestEventStubs
from coinmaster.research.native_fixture import SOL_PERP,BTC_PERP
from coinmaster.strategy.paired_prefix import PairedPrefixResearch,PairedCaps,sol_prices,MINUTE
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy

class H(PairedPrefixResearch):
    def __init__(self):
        self.config=NS(research_sol_standing_protection=True,research_btc_standing_tp=True,research_a0_family="R2_A0_V1",research_paired_prefix="B2_F0",research_a0_original_second=False,research_btc_real_u=True,research_btc_q_mode="LEGACY_Q_CONTROL",research_sol_off=True,sol_id=SOL_PERP.id,btc_id=BTC_PERP.id,research_native_book=NS(detailed=True),deposit_runtime=None,research_v3_risk=None)
        self.cache=Cache();self.cache.add_instrument(SOL_PERP);self.cache.add_instrument(BTC_PERP)
        self.id=StrategyId("REPLAY-001");self.clock=TestClock();self.clock.set_time(1)
        self.order_factory=OrderFactory(TraderId("UNIT-001"),self.id,self.clock)
        self._pair_init();caps=PairedCaps(D(2),D(1),D(".001"),D(".1"),D(2));caps.entry_terminal(D(2))
        self._pair=dict(parent="P",side=1,p0=D(100),atr=D(2),tp_lots={0:5,1:5,2:10},consumed=set(),signature=None,generation=0,protection_since=None,close_sol=False,failed=False,caps=caps,risk="ACTIVE_RISK",debt_since=None,last_btc=D(2),last_sol=D(2),entry_terminal=True)
        self.held=D(2);self.btc_held=D(2);self.commands=[];self.cancels=[];self.submits=[];self.failures=[];self.recorded=[];self.predecisions=[]
        self._pending_by_order={};self._domain=NS(episode=NS(id="P",side=1,btc_open_qty=2));self._md_plans={"P":{}}
        self._forced_close_reason=None;self._forced_close_intent=None;self._forced_close_submitted=set();self._forced_close_orders=set();self._mandatory_sol_exit=None;self._accepted_reductions={};self._v3_reduction=None;self._liquidating=False;self._group_close_reconciliation_pending=False;self._research_protect_latch=None;self.terminal_lifecycle={}
        self._split_stop=lambda reason:None;self._risk_first_sol_stop=lambda reason:False;self._md_enabled=lambda:False;self._discard_queued_intents=lambda fn:None;self._carry_busy=lambda:False
        self._tp_enabled=lambda:False;self._tier_allows_increase=lambda *a:True
        prices,stop=sol_prices(D(100),D(2),-1,SOL_PERP.price_increment.as_decimal())
        accepted=[]
        for level,q in enumerate((D(".5"),D(".5"),D(1))):
            o=self.order_factory.limit(SOL_PERP.id,OrderSide.BUY,SOL_PERP.make_qty(q),SOL_PERP.make_price(prices[level]),reduce_only=True)
            accepted.append(self.register(o,"TP",level))
        o=self.order_factory.stop_market(SOL_PERP.id,OrderSide.BUY,SOL_PERP.make_qty(D(2)),SOL_PERP.make_price(stop),time_in_force=TimeInForce.IOC,reduce_only=True)
        accepted.append(self.register(o,"STOP"))
        for e in accepted:self._pair_accept(e)
        self.quote();self.submits.clear()
    def _pair_qty(self,instrument):return self.held if instrument==self.config.sol_id else self.btc_held
    def _pair_position(self,instrument):
        # Explicit position-getter method input, no cache position import.
        return NS(strategy_id=self.id,is_long=False)if instrument==self.config.sol_id and self.held else None
    def _record_submission(self,*args):self.recorded.append(args);return True
    def _terminal_submission(self,*args):pass
    def _pair_predecision(self,*args):self.predecisions.append(args)
    def _pair_fail(self,reason,ns):
        self.failures.append(reason);self._pair.update(failed=True,close_sol=True,risk="UNKNOWN_RISK")
    def apply(self,o,e):o.apply(e);self.cache.update_order(o);return e
    def register(self,o,kind,level=None):
        oid=str(o.client_order_id);self._pair_orders[oid]=dict(instrument=SOL_PERP.id,kind=kind,level=level,parent="P",initial_oid=oid,initialized_event_id=str(o.init_event.id),accepted=False,pending=None,ack=None,command_sequence=0)
        self.cache.add_order(o);self.apply(o,TestEventStubs.order_submitted(o,ts_event=self.clock.timestamp_ns()))
        return self.apply(o,TestEventStubs.order_accepted(o,ts_event=self.clock.timestamp_ns()))
    def submit_order(self,o):
        self.submits.append(o);self.cache.add_order(o);self.apply(o,TestEventStubs.order_submitted(o,ts_event=self.clock.timestamp_ns()));self._pair_accept(self.apply(o,TestEventStubs.order_accepted(o,ts_event=self.clock.timestamp_ns())))
    def modify_order(self,o,**kwargs):
        self.commands.append((str(o.client_order_id),kwargs));e=self.apply(o,TestEventStubs.order_pending_update(o,ts_event=self.clock.timestamp_ns()));self._pair_sol_native_event(e,"generic")
    def cancel_order(self,o):
        self.cancels.append(str(o.client_order_id));e=self.apply(o,TestEventStubs.order_pending_cancel(o,ts_event=self.clock.timestamp_ns()));self._pair_sol_native_event(e,"generic")
    def ack_all(self):
        for _ in range(20):
            work=[(oid,x["pending"])for oid,x in self._pair_orders.items()if x.get("pending")]
            if not work:return
            for oid,cmd in work:
                o=self.cache.order(ClientOrderId(oid));e=self.apply(o,TestEventStubs.order_updated(o,quantity=SOL_PERP.make_qty(cmd["payload"][0]),ts_event=self.clock.timestamp_ns()));self._pair_sol_native_event(e,"typed");self._pair_sol_native_event(e,"generic")
        raise AssertionError("UNBOUNDED_MODIFY_REPLAY")
    def order(self,kind,level=None):return next(self.cache.order(ClientOrderId(oid))for oid,x in self._pair_orders.items()if x["kind"]==kind and x["level"]==level and not self.cache.order(ClientOrderId(oid)).is_closed)
    def fill(self,o,qty,trade="UNIT-FILL"):
        e=self.apply(o,TestEventStubs.order_filled(o,SOL_PERP,last_qty=SOL_PERP.make_qty(D(qty)),trade_id=TradeId(trade),ts_event=self.clock.timestamp_ns()))
        self.held-=D(qty);self._pair_fill(e);self._pair_sol_native_event(e,"generic");return e
    def canceled(self,o):
        e=self.apply(o,TestEventStubs.order_canceled(o,ts_event=self.clock.timestamp_ns()));self._pair_terminal(str(o.client_order_id),e.ts_event);self._pair_sol_native_event(e,"typed");self._pair_sol_native_event(e,"generic");return e
    def quote(self):
        q=QuoteTick(SOL_PERP.id,SOL_PERP.make_price(D(100)),SOL_PERP.make_price(D(100)),SOL_PERP.make_qty(D(1000)),SOL_PERP.make_qty(D(1000)),self.clock.timestamp_ns(),self.clock.timestamp_ns());self.cache.add_quote_tick(q);return q
    def strict(self):self._pair_sol_boundary("REPLAY_NEXT_INPUT",self.clock.timestamp_ns(),strict=True)
    def cap(self,qty):self._pair_submit(SOL_PERP.id,1,D(qty),"SOL_CAP",self.clock.timestamp_ns());return self.submits[-1]

def retiring():
    h=H();h.fill(h.order("TP",0),".3","UNIT-ORDINARY");h.ack_all()
    cap=h.cap("1.2");h.fill(cap,"1.2","UNIT-CAP");h.ack_all()
    oid=next(oid for oid,x in h._pair_orders.items()if x.get("retiring"))
    return h,oid

def test_cap_full_preserves_positive_oids_reconciles_from_actual_fill():
    h=H();ids=set(h._pair_orders);h._pair["caps"].bmax=D("1.5");h._pair_sol_reduce(1,SOL_PERP.id)
    assert len(h.submits)==1 and not h.cancels and set(h._pair_orders)>=ids
    h._pair_sol_reduce(1,SOL_PERP.id);assert len(h.submits)==1
    h.fill(h.submits[0],".5","UNIT-FULL-CAP");assert h.commands
    with pytest.raises(ValueError,match="EXACT_COVERAGE_UNKNOWN"):h.strict()
    h.ack_all();h.strict();assert not h.failures and not h.cancels
    assert {x for x in ids if h._pair_orders[x]["kind"]in {"TP","STOP"}}<=set(h._pair_orders)
    assert sum(h._pair["tp_lots"].values())==15 and h.order("STOP").quantity.as_decimal()==h.held

def test_partial_ioc_cancel_keeps_protection_and_serializes_residual():
    h=H();h._pair["caps"].bmax=D(1);h._pair_sol_reduce(1,SOL_PERP.id);o=h.submits[-1]
    h.fill(o,".2","UNIT-PARTIAL-CAP");h.ack_all();h.strict();h._pair_sol_reduce(1,SOL_PERP.id);assert len(h.submits)==1
    h.canceled(o);h.strict();h._pair_sol_reduce(1,SOL_PERP.id);assert len(h.submits)==2
    assert h.submits[-1].quantity.as_decimal()==D(".8")and not h.cancels

def test_multiple_retiring_late_fills_liability_and_cascade_deadline_dedup():
    h,oid=retiring();owner=h._pair_orders[oid];ret=owner["retiring"];D0=h._pair["retirement_deadline_ns"]
    assert ret["native_right"]==D(".2")and ret["filled_at_cancel"]==D(".3")and not ret["terminal_event_id"]
    h.strict();o=h.cache.order(ClientOrderId(oid));e=h.fill(o,".1","UNIT-LATE1");h._pair_fill(e);h._pair_sol_native_event(e,"typed");h.ack_all();h.strict()
    assert ret["actual_filled"]==D(".1")and h._pair["retirement_deadline_ns"]==D0
    assert len([x for x in h._pair_orders.values()if x.get("retiring")])==2
    h.fill(o,".1","UNIT-LATE2");h.ack_all();h.strict()
    assert ret["actual_filled"]==ret["native_right"]and ret["terminal_event_id"]
    assert sum(h._pair["tp_lots"].values())==3 and h._pair["debt_since"]is not None
    assert h._pair_sol_retire_busy();other=h.order("TP",1);h.canceled(other)
    assert not h._pair_sol_retire_busy()and h._pair["retirement_deadline_ns"]==D0
    assert h._pair is not None and not h.predecisions

def test_pending_modify_resolves_before_retire_and_no_zero_total_modify():
    h=H();o=h.order("TP",0);owner=h._pair_orders[str(o.client_order_id)]
    # Actual new target while previous known native modification is in flight.
    owner["command_sequence"]=1;owner["pending"]=dict(sequence=1,generation=0,payload=(D(".5"),D(99),None),desired=(D(".5"),D(99),None),sent_ns=1)
    h.apply(o,TestEventStubs.order_pending_update(o,ts_event=1));h.held=D("1.5");h._pair["tp_lots"]={0:0,1:5,2:10};h._pair_sol_protect(1)
    assert not owner.get("retiring")and not h.cancels
    e=h.apply(o,TestEventStubs.order_updated(o,quantity=SOL_PERP.make_qty(D(".5")),ts_event=1));h._pair_sol_native_event(e,"typed");h.ack_all();h.strict()
    assert owner["retiring"]["native_right"]==D(".5")and h.cancels==[str(o.client_order_id)]
    assert all(kw["quantity"].as_decimal()>0 for _,kw in h.commands)

@pytest.mark.parametrize("delta",[-1,0,1])
def test_finite_deadline_first_observed_input_no_reset(delta):
    h,oid=retiring();deadline=h._pair["retirement_deadline_ns"];h.clock.set_time(deadline+delta)
    if delta<0:h.strict()
    else:
        with pytest.raises(ValueError,match="ACK_DEADLINE"):h.strict()
    assert h._pair["retirement_deadline_ns"]==deadline and h._pair_sol_retire_busy()

def test_real_final_ack_at_deadline_finishes_but_no_future_ack_borrowing():
    h,oid=retiring();deadline=h._pair["retirement_deadline_ns"];h.clock.set_time(deadline)
    h.canceled(h.cache.order(ClientOrderId(oid)));h.strict()
    assert not h._pair_sol_retire_busy()and h._pair["retirement_deadline_ns"]==deadline

def reject(h,o):
    e=OrderCancelRejected(o.trader_id,o.strategy_id,o.instrument_id,o.client_order_id,o.venue_order_id,o.account_id,"UNIT_NOT_FOUND",UUID4(),h.clock.timestamp_ns(),h.clock.timestamp_ns());h.apply(o,e);h._pair_sol_native_event(e,"generic");return e

def test_redundant_cancel_reject_only_after_actual_terminal_and_reconciled_history():
    h,oid=retiring();o=h.cache.order(ClientOrderId(oid));h.canceled(o);reject(h,o);h.strict()
    assert not h.failures and h._pair_orders[oid]["retiring"]["terminal_event_id"]

def test_live_cancel_reject_is_not_terminal_credit():
    h,oid=retiring();o=h.cache.order(ClientOrderId(oid))
    with pytest.raises(ValueError,match="RETIRING_LIVE"):reject(h,o)
    assert not h._pair_orders[oid]["retiring"]["terminal_event_id"]

@pytest.mark.parametrize("fault",["expiry","unsolicited_update","missing_trade","foreign_side"])
def test_retiring_unknown_events_keep_liability_and_fail(fault):
    h,oid=retiring();o=h.cache.order(ClientOrderId(oid));ret=h._pair_orders[oid]["retiring"]
    with pytest.raises(ValueError):
        if fault=="expiry":
            e=h.apply(o,TestEventStubs.order_expired(o,ts_event=1));h._pair_sol_native_event(e,"generic")
        elif fault=="unsolicited_update":
            e=h.apply(o,TestEventStubs.order_updated(o,quantity=o.quantity,ts_event=1));h._pair_sol_native_event(e,"generic")
        elif fault=="missing_trade":
            e=h.apply(o,TestEventStubs.order_filled(o,SOL_PERP,last_qty=SOL_PERP.make_qty(D(".1")),trade_id=TradeId("UNRECONCILED"),ts_event=1));h._pair_sol_retire_check(1)
        else:h._pair["side"]=-1;h.strict()
    assert ret["actual_filled"]==0 and not ret["terminal_event_id"]

def test_genuine_global_quote_and_cache_paths_have_one_pair_exit_keep_protection():
    h=H();ids=set(h._pair_orders);WaveOverlayStrategy._begin_forced_close(h,"REGIME")
    assert h._pair["global_close_reason"]=="REGIME"and not h.cancels
    h.strict();WaveOverlayStrategy._submit_forced_close_on_quote(h,h.quote());WaveOverlayStrategy._submit_forced_closes_from_cache(h)
    assert len(h.submits)==1 and h._pair_orders[str(h.submits[0].client_order_id)]["kind"]=="SOL_CLOSE"
    assert not h._forced_close_orders and not h._forced_close_submitted and not h.cancels
    h.fill(h.submits[0],".5","UNIT-CLOSE-PARTIAL");h.ack_all();h.strict()
    assert ids<=set(h._pair_orders)and h.paired_prefix_audit[-1]["state"]=="CLOSING_PROTECTED"
    WaveOverlayStrategy._submit_forced_close_on_quote(h,h.quote());assert len(h.submits)==1

@pytest.mark.parametrize("blocker",["foreign","ENTRY","BTC_open","pending_modify"])
def test_global_does_not_filter_other_blockers_or_create_exit(blocker):
    h=H();WaveOverlayStrategy._begin_forced_close(h,"REGIME")
    if blocker=="pending_modify":
        o=h.order("STOP");h._pair_orders[str(o.client_order_id)]["pending"]={"unit":True};h.apply(o,TestEventStubs.order_pending_update(o,ts_event=1))
    else:
        inst=BTC_PERP if blocker=="BTC_open"else SOL_PERP
        o=h.order_factory.limit(inst.id,OrderSide.SELL,inst.make_qty(D(1)),inst.make_price(D(100)),reduce_only=False)
        h.cache.add_order(o);h.apply(o,TestEventStubs.order_accepted(o,ts_event=1))
        if blocker=="ENTRY":h._pair_orders[str(o.client_order_id)]=dict(parent="P",instrument=SOL_PERP.id,kind="ENTRY",level=None)
    WaveOverlayStrategy._submit_forced_close_on_quote(h,h.quote());WaveOverlayStrategy._submit_forced_closes_from_cache(h)
    assert not h.submits and h._pair_sol_global_wait()

def test_closing_flag_does_not_bypass_unknown_positive_stop():
    h=H();h._pair_sol_global_begin("REGIME",1);h.cancel_order(h.order("STOP"))
    with pytest.raises(ValueError,match="EXACT_COVERAGE_UNKNOWN"):h.strict()

def test_any_stop_fill_forbids_protection_modify_and_fault_is_not_qualified_closing():
    h=H();h.fill(h.order("STOP"),".1","UNIT-STOP-PARTIAL");h._pair_sol_protect(1)
    assert not h.commands and h._pair["stop_filled"]
    h.canceled(h.order("STOP"));assert "PARTIAL_NATIVE_STOP"in h.failures
    h._pair_sol_boundary("FAULT_RECORDED_NOT_PASS",1)
    assert h.paired_prefix_audit[-1]["state"]=="FAULT_UNPROTECTED"

def test_cap_rejected_uses_existing_fault_no_protection_resurrection():
    h=H();o=h.cap(".5");e=h.apply(o,TestEventStubs.order_rejected(o,ts_event=1));h._pair_terminal(str(o.client_order_id),e.ts_event,rejected=True)
    assert "NATIVE_SOL_CAP_REJECTED"in h.failures and h._pair["failed"]and h._pair["close_sol"]
    before=len(h.commands);h._pair_sol_protect(1);assert len(h.commands)==before

@pytest.mark.parametrize("field,value",[("research_sol_standing_protection",False),("research_a0_family",None),("research_btc_standing_tp",False)])
def test_off_or_other_family_has_no_v2_global_delegation(field,value):
    h=H();setattr(h.config,field,value);assert not h._pair_sol_v2()
    h._pair_sol_global_begin("REGIME",1);assert not h._pair_sol_global_active()
    assert h._pair_sol_global_wait()==h.cache.orders_open()

def test_product_and_replay_sources_have_no_engine_constructor_call():
    root=Path(__file__).resolve().parents[1]
    for file in("coinmaster/strategy/paired_prefix.py","coinmaster/strategy/wave_overlay.py","tests/test_sol_reduction_v2_pure.py"):
        t=ast.parse((root/file).read_text());assert not any(isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id=="BacktestEngine"for n in ast.walk(t))


def test_first_unrelated_native_event_at_deadline_cannot_borrow_future_ack():
    h,oid=retiring();deadline=h._pair["retirement_deadline_ns"];h.clock.set_time(deadline)
    h._tp_native_event=lambda *args:None;h._record_native_event=lambda *args:None
    o=h.order_factory.market(BTC_PERP.id,OrderSide.SELL,BTC_PERP.make_qty(D(1)),reduce_only=True)
    h.cache.add_order(o);event=h.apply(o,TestEventStubs.order_submitted(o,ts_event=deadline))
    with pytest.raises(ValueError,match="ACK_DEADLINE"):WaveOverlayStrategy.on_order_event(h,event)
    assert not h._pair_orders[oid]["retiring"]["terminal_event_id"]

def test_global_full_exit_cancels_only_after_actual_flat_and_retains_pair_until_ack():
    h=H();WaveOverlayStrategy._begin_forced_close(h,"REGIME");WaveOverlayStrategy._submit_forced_close_on_quote(h,h.quote());o=h.submits[-1]
    h.fill(o,"2.0","UNIT-FULL-CLOSE");assert h.held==0 and len(h.cancels)==4 and h._pair is not None
    h.btc_held=D(0);h._pair_release_if_terminal(1);assert h._pair is not None
    for owned in list(h._pair_orders):
        order=h.cache.order(ClientOrderId(owned))
        if order.is_pending_cancel:h.canceled(order)
    assert h._pair is None and not h.cache.orders_open()and not h.cache.orders_inflight()

def test_global_position_foreign_owner_is_not_adopted():
    h=H();h._pair_position=lambda instrument:NS(strategy_id=StrategyId("FOREIGN-001"),is_long=False)
    with pytest.raises(ValueError,match="POSITION_OWNER_UNKNOWN"):WaveOverlayStrategy._begin_forced_close(h,"REGIME")
    assert not h.cancels and not h.submits

def test_explicit_fault_global_close_uses_conservative_owned_drain_not_positive_bypass():
    h=H();h.fill(h.order("STOP"),".1","UNIT-PARTIAL-STOP-FAULT");h.canceled(h.order("STOP"))
    assert h._pair["failed"]
    WaveOverlayStrategy._begin_forced_close(h,"REGIME");assert len(h.cancels)==3
    WaveOverlayStrategy._submit_forced_closes_from_cache(h);assert not h.submits
    for oid,x in list(h._pair_orders.items()):
        order=h.cache.order(ClientOrderId(oid))
        if order.is_pending_cancel:h.canceled(order)
    WaveOverlayStrategy._submit_forced_closes_from_cache(h)
    assert len(h.submits)==1 and h._pair_orders[str(h.submits[0].client_order_id)]["kind"]=="SOL_CLOSE"and not h.commands
    assert h._pair["failed"]and "PARTIAL_NATIVE_STOP"in h.failures


def test_global_fault_never_retries_retiring_cancel_after_native_partial_status():
    h,oid=retiring();h.fill(h.cache.order(ClientOrderId(oid)),".1","UNIT-RETIRE-BEFORE-GLOBAL-FAULT");h.ack_all()
    assert h.cache.order(ClientOrderId(oid)).status.name=="PARTIALLY_FILLED"
    assert h.cancels.count(oid)==1
    h._pair["failed"]=True;WaveOverlayStrategy._begin_forced_close(h,"REGIME")
    assert h.cancels.count(oid)==1 and h._pair_orders[oid]["retiring"]["actual_filled"]==D(".1")


def test_matching_observer_only_checks_and_logs_never_commits_owner_or_rights():
    h,oid=retiring();owners=copy.deepcopy(h._pair_orders);rights=copy.deepcopy(h._pair["tp_lots"]);caps=copy.deepcopy(h._pair["caps"])
    h.strict();assert h._pair_orders==owners and h._pair["tp_lots"]==rights and h._pair["caps"]==caps
    # An actual native terminal already in cache, but not delivered to the
    # owner, receives no observer-created terminal ACK or early release credit.
    o=h.cache.order(ClientOrderId(oid));h.apply(o,TestEventStubs.order_canceled(o,ts_event=1));h.strict()
    assert not h._pair_orders[oid]["retiring"]["terminal_event_id"]and h._pair_sol_retire_busy()
