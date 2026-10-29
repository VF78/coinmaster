"""Actual native Order/Position objects and actual strategy callbacks; engines zero."""
import ast
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as N
import pytest
from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
from coinmaster.research.native_fixture import instrument_quote
from nautilus_trader.common.component import TestClock
from nautilus_trader.common.factories import OrderFactory
from nautilus_trader.model.enums import OrderSide,TimeInForce,OrderStatus
from nautilus_trader.model.identifiers import StrategyId,PositionId
from nautilus_trader.model.objects import Money
from nautilus_trader.model.position import Position
from nautilus_trader.test_kit.stubs.events import TestEventStubs
from nautilus_trader.test_kit.stubs.identifiers import TestIdStubs

SOURCE=Path(__file__).parents[1]/"coinmaster/strategy/wave_overlay.py"


def forced(reason="REGIME",held=5000,*,start=True,accept=True):
    cls=next(n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.ClassDef) and n.name=="WaveOverlayStrategy")
    names={"_staging_a_force_scope","_staging_a_forced_child_ready","_staging_a_continue_forced_fill","_staging_a_reconcile_flat_timeout",
        "_submit_forced_close_on_quote","_submit_forced_closes_from_cache","_ordinary_forced_close_active","_begin_forced_close",
        "on_order_filled","on_position_event","on_order_canceled"}
    methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
    module=ast.Module(body=[ast.ImportFrom(module="__future__",names=[ast.alias(name="annotations")],level=0),
        ast.ClassDef(name="Actual",bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[])
    env=dict(Decimal=D,OrderSide=OrderSide,TimeInForce=TimeInForce)
    exec(compile(ast.fix_missing_locations(module),str(SOURCE),"exec"),env)
    profile=load_current_hl_diagnostic(Path(__file__).parent/"fixtures/hl-current-20261029")
    btc,sol=profile.instruments;clock=TestClock()
    factory=OrderFactory(TestIdStubs.trader_id(),StrategyId("A-001"),clock)
    seed=factory.market(sol.id,OrderSide.BUY,sol.make_qty(held))
    seed.apply(TestEventStubs.order_accepted(seed))
    opening=TestEventStubs.order_filled(seed,sol,position_id=PositionId("A-POS"),last_px=sol.make_price(100),commission=Money(0,sol.quote_currency))
    seed.apply(opening);position=Position(sol,opening)
    s=env["Actual"]();orders={};sent=[]
    s.config=N(research_sol_capital_staging_a=True,active_seed=D(10000),btc_id=btc.id,sol_id=sol.id,
        deposit_runtime=None,research_v3_risk=None,research_sol_risk_first=None,research_v0_execution_repairs=True,research_residual_recovery=False)
    s._forced_close_reason=reason;s._forced_close_decision_ns=100;s._forced_close_cancel_ack_ns=None
    s._forced_close_intent=None;s._forced_close_submitted=set();s._forced_close_orders=set();s._staging_a_forced_children={}
    s._pending_by_order={};s._sigma_by_order={};s._decision_index_by_order={};s._seen_trade_ids=set()
    s._v3_orders={};s._deposit_exit_orders=set();s._liquidation_orders=set();s._terminal_order_ids=set()
    s._mandatory_sol_exit=None;s._research_protect_latch=None;s._liquidating=reason=="LIQUIDATION"
    s.terminal_lifecycle=dict(status="CLOSE_SUBMITTED",close_fills=[]);s.liquidation_audit=[];s._order_audit={}
    s._carry_busy=lambda:False;s._conditional_enabled=lambda:False
    s.order_factory=factory;s.clock=clock
    latest={sol.id:instrument_quote(sol,"100","100",100)}
    s.cache=N(positions_open=lambda:[] if position.is_closed else [position],
        position=lambda i:position if i==position.id else None,
        order=lambda i:orders.get(str(i)),orders_open=lambda:[o for o in orders.values() if o.is_open],
        orders_inflight=lambda:[o for o in orders.values() if not o.is_closed and not o.is_open],instrument=lambda i:btc if i==btc.id else sol,
        quote_tick=lambda i:latest.get(i))
    for name in ("_c1_native_fill","_record_native_fill","_record_fill_audit","_carry_native_fill",
        "_terminal_submission","_reconcile_group_flat","_reconcile_liquidation_flat","_reconcile_terminal_flat",
        "_reconcile_deposit_flat","_hedge_refresh","_insurance_position","_record_native_event",
        "_research_capture_btc_episode","_v3_capture_sol_cycle","_next_terminal","_hedge_terminal"):
        setattr(s,name,lambda *a,**kw:None)
    def record(order,*a):
        s._order_audit[str(order.client_order_id)]={};return True
    s._record_submission=record
    def submit(order):
        orders[str(order.client_order_id)]=order
        if accept:order.apply(TestEventStubs.order_accepted(order,ts_event=100))
        else:order.apply(TestEventStubs.order_submitted(order,ts_event=100))
        sent.append(order)
    s.submit_order=submit
    event=lambda ts=100:N(instrument_id=sol.id,position_id=position.id,ts_event=ts,ts_init=ts)
    def fill(order,quantity=None,ts=100):
        return TestEventStubs.order_filled(order,sol,position_id=position.id,
            last_qty=sol.make_qty(quantity) if quantity is not None else order.quantity,
            last_px=sol.make_price(100),commission=Money(0,sol.quote_currency),ts_event=ts)
    if start:s._submit_forced_close_on_quote(latest[sol.id])
    return N(s=s,btc=btc,sol=sol,profile=profile,position=position,orders=orders,sent=sent,event=event,fill=fill,latest=latest)


@pytest.mark.parametrize("ordering",["fill_before_position","position_before_terminal"])
@pytest.mark.parametrize("reason",["REGIME","TRAIL","TERMINAL_BOUNDARY_SETTLEMENT"])
def test_native_filled_children_drain_same_fresh_quote_once_per_confirmed_position_progress(ordering,reason):
    c=forced(reason)
    before=[]
    for index in range(5):
        assert len(c.sent)==index+1
        order=c.sent[-1];before.append(c.position.quantity.as_decimal())
        assert order.is_reduce_only and order.quantity.as_decimal()==D(1000)
        event=c.fill(order)
        if ordering=="fill_before_position":
            order.apply(event);c.s.on_order_filled(event)
            assert len(c.sent)==index+1  # Native terminal alone cannot reuse stale size.
            c.position.apply(event);c.s.on_position_event(c.event())
        else:
            c.position.apply(event);c.s.on_position_event(c.event())
            assert len(c.sent)==index+1  # Position change alone cannot bypass nonterminal child.
            order.apply(event);c.s.on_order_filled(event)
        count=len(c.sent)
        c.s.on_order_filled(event);c.s.on_position_event(c.event())
        assert len(c.sent)==count  # Duplicate callback cannot forward another child.
    assert before==list(map(D,[5000,4000,3000,2000,1000]))
    assert c.position.is_closed and c.position.quantity.as_decimal()==0
    assert len(c.sent)==5 and not c.s._staging_a_forced_children
    assert all(o.status==OrderStatus.FILLED for o in c.sent)
    assert [D(c.s._order_audit[str(o.client_order_id)]["staging_a_full_admitted_qty"]) for o in c.sent]==before


def test_no_native_position_progress_holds_even_if_a_new_quote_arrives():
    c=forced();order=c.sent[-1];event=c.fill(order)
    order.apply(event);c.s.on_order_filled(event)
    c.s.on_position_event(c.event())
    c.latest[c.sol.id]=instrument_quote(c.sol,"101","101",200)
    c.s._submit_forced_close_on_quote(c.latest[c.sol.id])
    assert len(c.sent)==1 and c.position.quantity.as_decimal()==5000
    c.position.apply(event);c.s.on_position_event(c.event())
    assert len(c.sent)==2


def test_zero_cancel_waits_for_a_new_fresh_quote():
    c=forced();order=c.sent[-1]
    cancel=TestEventStubs.order_canceled(order,ts_event=100)
    order.apply(cancel);c.s.on_order_canceled(cancel);c.s.on_position_event(c.event())
    assert len(c.sent)==1
    c.latest[c.sol.id]=instrument_quote(c.sol,"101","101",200)
    c.s._submit_forced_close_on_quote(c.latest[c.sol.id])
    assert len(c.sent)==2
    c.s.on_order_canceled(cancel)
    assert len(c.sent)==2


@pytest.mark.parametrize("position_first",[False,True])
def test_partial_canceled_child_needs_both_terminal_and_actual_native_position_progress(position_first):
    c=forced();order=c.sent[-1];event=c.fill(order,400)
    order.apply(event);c.s.on_order_filled(event)
    if position_first:
        c.position.apply(event);c.s.on_position_event(c.event())
        assert len(c.sent)==1
    cancel=TestEventStubs.order_canceled(order,ts_event=100)
    order.apply(cancel);c.s.on_order_canceled(cancel)
    if not position_first:
        assert len(c.sent)==1
        c.position.apply(event);c.s.on_position_event(c.event())
    assert len(c.sent)==2 and c.position.quantity.as_decimal()==4600


@pytest.mark.parametrize("reason",["LIQUIDATION","RESEARCH_PORTFOLIO_45"])
def test_native_emergency_flatten_is_not_throttled(reason):
    c=forced(reason)
    assert c.sent[0].quantity.as_decimal()==5000
    assert not c.s._staging_a_forced_children


def test_true_native_cut_child_1000_preserves_actual_credit_and_restores_only_1000():
    from coinmaster.domain.wave_overlay import Candidate,Episode,WaveOverlayState
    root=SOURCE.parents[1]
    residual=next(n for n in ast.parse((root/"strategy/residual_recovery.py").read_text()).body if isinstance(n,ast.ClassDef))
    methods=[n for n in residual.body if isinstance(n,ast.FunctionDef) and n.name in {"_c1_fill","_c1_terminal","_c1_allocate"}]
    nextcls=next(n for n in ast.parse((root/"strategy/next_band.py").read_text()).body if isinstance(n,ast.ClassDef) and any(isinstance(m,ast.FunctionDef) and m.name=="_next_terminal" for m in n.body))
    methods.append(next(n for n in nextcls.body if isinstance(n,ast.FunctionDef) and n.name=="_next_terminal"))
    env=dict(D=D)
    definition=ast.ClassDef(name="ActualC1",bases=[],keywords=[],body=methods,decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[definition],type_ignores=[])),"actual_C1_callbacks","exec"),env)
    s=env["ActualC1"]();c=forced(None,4000,start=False)
    s.config=N(research_residual_recovery=True,btc_id=c.btc.id,sol_id=c.sol.id)
    state=WaveOverlayState(Candidate());state.set_execution_lots(btc=D(".00001"),sol=D(".01"))
    ep=state.episode=Episode("C1",1,10000,1,sol_qty=4000)
    s._domain=state;s.cache=c.s.cache;s._next_enabled=False
    s._c1_state=dict(group=ep.id,instrument=c.sol.id,step=D(".01"),state="CUT_RESOLVING",
        cut_lots=200000,cut_filled=0,cut_value=D(0),credit=0,bucket={},revoked=False,
        cut_submitted=True,restore_submitted=False,restore_filled=0)
    s._c1_intents={};s._c1_terminal_ids=set();s._c1_sol_levels={ep.id:{0:400000}}
    s._c1_rights=lambda:{};s._c1_log=lambda *a,**kw:None
    cut=N(id="cut",episode_id=ep.id,action="SOL_EXIT",quantity=2000)
    s._c1_intents[cut.id]="CUT"
    order=c.s.order_factory.market(c.sol.id,OrderSide.SELL,c.sol.make_qty(1000),time_in_force=TimeInForce.IOC,reduce_only=True)
    order.apply(TestEventStubs.order_accepted(order,ts_event=100));event=c.fill(order)
    order.apply(event);c.position.apply(event)
    assert s._c1_fill(cut,float(event.last_qty),float(event.last_px),event.ts_event)
    s._next_terminal(cut,event.ts_event)
    assert order.status==OrderStatus.FILLED and c.position.quantity.as_decimal()==3000
    assert ep.sol_qty==3000 and s._c1_state["credit"]==100000 and s._c1_state["state"]=="HELD"
    s._c1_state.update(restore_committed=100000,restore_submitted=True,state="RESTORE_RESOLVING")
    restore=N(id="restore",episode_id=ep.id,action="SOL_RESTORE",quantity=1000)
    s._c1_intents[restore.id]="RESTORE"
    order2=c.s.order_factory.market(c.sol.id,OrderSide.BUY,c.sol.make_qty(1000),time_in_force=TimeInForce.IOC)
    order2.apply(TestEventStubs.order_accepted(order2,ts_event=100));event2=c.fill(order2)
    order2.apply(event2);c.position.apply(event2)
    assert s._c1_fill(restore,float(event2.last_qty),float(event2.last_px),event2.ts_event)
    s._next_terminal(restore,event2.ts_event)
    assert order2.status==OrderStatus.FILLED and c.position.quantity.as_decimal()==4000
    assert ep.sol_qty==4000 and s._c1_state["credit"]==0 and s._c1_state["restore_filled"]==100000


def ordinary(action,reason,held,*,requested=None):
    from datetime import datetime,UTC
    from coinmaster.domain.wave_overlay import Candidate,Episode,WaveOverlayState
    from test_sol_capital_staging_a_pure import dispatch
    c=forced(None,held,start=False);s=c.s
    cls=next(n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.ClassDef) and n.name=="WaveOverlayStrategy")
    names={"_submit_intent","_apply_confirmed_domain_fill","_own_accepted_reduction",
        "_requeue_accepted_reduction","_reduction_key","_bind_native_lots","_rearm_mandatory_sol_exit"}
    methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
    quote=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=="on_quote_tick")
    mandatory=next(n for n in quote.body if isinstance(n,ast.If) and ast.unparse(n.test)=="self._mandatory_sol_exit is not None")
    queued=next(n for n in quote.body if isinstance(n,ast.For) and "self._queued_intents" in ast.unparse(n.iter))
    for name,node in (("_actual_mandatory_quote",mandatory),("_actual_queued_quote",queued)):
        methods.append(ast.FunctionDef(name=name,args=ast.arguments(posonlyargs=[],args=[ast.arg(arg="self"),ast.arg(arg="tick"),ast.arg(arg="ts_decision")],kwonlyargs=[],kw_defaults=[],defaults=[]),body=[node],decorator_list=[]))
    env=dict(Decimal=D,OrderSide=OrderSide,TimeInForce=TimeInForce,datetime=datetime,UTC=UTC)
    module=ast.Module(body=[ast.ImportFrom(module="__future__",names=[ast.alias(name="annotations")],level=0),
        ast.ClassDef(name="Extra",bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[])
    exec(compile(ast.fix_missing_locations(module),str(SOURCE),"exec"),env)
    for name,value in env["Extra"].__dict__.items():
        if name in names or name.startswith("_actual_"):setattr(type(s),name,value)
    s.config=dispatch("10000").s.config.__replace__(research_v0_execution_repairs=True)
    s._candidate=s.config.candidate
    s._domain=WaveOverlayState(s._candidate)
    ep=s._domain.episode=Episode("ordinary",-1,10000,1,h=2000,btc_initial_qty=20,
        btc_open_qty=20,btc_entry_vwap=100,sol_qty=float(held),fixed_sigma=.1)
    if action=="SOL_HALF_EXIT":ep.sol_half_target_lots=int(D(held)/2/D(".01"))
    s._domain.set_execution_lots(btc=D(".00001"),sol=D(".01"))
    s._accepted_reductions={};s._queued_intents=[];s._queued_intent_ready_ns={}
    s._selected_entry_audits={};s._v3_sol_block_episode=None;s._rf_sol_child=False;s._carry_physical=False
    s._entries_enabled=lambda:True;s._tier_allows_increase=lambda *a:True
    s._next_before_submit=lambda *a:True;s._risk_first_sol_prepare=lambda i,q,*a:q
    s._risk_first_sol_limit=lambda *a:None;s._risk_first_sol_bind=lambda *a:None
    s._split_tp_ioc_eligible=lambda *a:False;s._split_unfinished=lambda:False
    s._c1_bind_submission=lambda *a:None;s._c1_fill=lambda *a:False;s._next_risk_fill=lambda *a:False
    s._confirmed_fill_cycle=lambda *a:0
    for name in ("_insurance_btc_fill","_alpha_btc_fill","_hedge_btc_flat","_h1_native_fill",
        "_risk_first_sol_fill","_split_native_fill","_cover_native_fill","_after_domain_fill","_advance_current_day"):
        setattr(s,name,lambda *a,**kw:None)
    s._bars=[N()];s._split_parent=None;s._mandatory_sol_retry_after_ns=0
    quantity=requested if requested is not None else held/2 if action=="SOL_HALF_EXIT" else held
    side=1 if action in {"SOL_ADD","SOL_RESTORE"} else -1
    i=s._domain._intent(ep,action,side,None,quantity=float(quantity),reason=reason)
    s._submit_intent(i,100,100,None,0,ts_now=100)
    return c,i


@pytest.mark.parametrize("action,reason,held,expected_children",[
    ("SOL_HALF_EXIT","SOL_Z_HALF_EXIT",4000,2),("SOL_EXIT","SOL_Z_FULL_EXIT",4000,4),
])
def test_original_ordinary_reduction_budget_survives_filled_child_and_retries_next_minute(action,reason,held,expected_children):
    c,parent=ordinary(action,reason,held);s=c.s;key=(parent.episode_id,parent.action,parent.level)
    assert s._accepted_reductions[key][1]==D(held/2 if action=="SOL_HALF_EXIT" else held)
    for index in range(expected_children):
        order=c.sent[-1];t=100+index*60_000_000_000
        event=c.fill(order,ts=t);order.apply(event);c.position.apply(event)
        s.on_order_filled(event);s.on_position_event(c.event(t))
        assert order.status==OrderStatus.FILLED
        if index<expected_children-1:
            assert len(s._queued_intents)==1 and s._queued_intent_ready_ns[s._queued_intents[0][0].id]==t+60_000_000_000
            early=instrument_quote(c.sol,"100","100",t+60_000_000_000-1)
            s._actual_queued_quote(early,early.ts_event);assert len(c.sent)==index+1
            due=instrument_quote(c.sol,"100","100",t+60_000_000_000)
            c.latest[c.sol.id]=due;s._actual_queued_quote(due,due.ts_event)
            assert len(c.sent)==index+2
    assert key not in s._accepted_reductions and not s._queued_intents
    assert c.position.quantity.as_decimal()==D(2000 if action=="SOL_HALF_EXIT" else 0)


@pytest.mark.parametrize("position_first",[False,True])
def test_timeout_13000_drains_13_truthful_children_at_original_one_minute_cadence(position_first):
    c,parent=ordinary("SOL_EXIT","SOL_HARD_TIMEOUT",13000);s=c.s
    for index in range(13):
        assert len(c.sent)==index+1
        order=c.sent[-1];assert order.quantity.as_decimal()==1000
        t=100+index*60_000_000_000;event=c.fill(order,ts=t)
        if position_first:c.position.apply(event)
        order.apply(event);s.on_order_filled(event)
        if not position_first:c.position.apply(event)
        s.on_position_event(c.event(t))
        assert order.status==OrderStatus.FILLED
        if index<12:
            assert s._mandatory_sol_exit is not None and s._mandatory_sol_retry_after_ns==t+60_000_000_000
            early=instrument_quote(c.sol,"100","100",t+60_000_000_000-1)
            s._actual_mandatory_quote(early,early.ts_event);assert len(c.sent)==index+1
            due=instrument_quote(c.sol,"100","100",t+60_000_000_000)
            c.latest[c.sol.id]=due;s._actual_mandatory_quote(due,due.ts_event)
    assert c.position.is_closed and c.position.quantity.as_decimal()==0 and len(c.sent)==13
    assert s._mandatory_sol_exit is None
    assert [D(s._order_audit[str(o.client_order_id)]["staging_a_full_admitted_qty"]) for o in c.sent]==list(map(D,range(13000,0,-1000)))


def test_c1_cut_and_restore_native_orders_are_staged_after_their_original_parent_admission():
    cut,parent=ordinary("SOL_EXIT","C1_RESIDUAL_CUT",4000,requested=2000)
    order=cut.sent[0]
    assert parent.quantity==2000 and order.quantity.as_decimal()==1000 and order.is_reduce_only
    audit=cut.s._order_audit[str(order.client_order_id)]
    assert D(audit["staging_a_full_admitted_qty"])==2000
    restore,logical=ordinary("SOL_RESTORE","C1_RESIDUAL_RESTORE",3000,requested=1000)
    assert logical.quantity==1000 and restore.sent[0].quantity.as_decimal()==1000
    assert not restore.sent[0].is_reduce_only


@pytest.mark.parametrize("different",["id","instrument","side"])
def test_closed_order_cannot_release_current_child_against_a_different_native_position(different):
    c=forced();order=c.sent[-1];event=c.fill(order)
    order.apply(event)
    instrument=c.btc if different=="instrument" else c.sol
    side=OrderSide.SELL if different=="side" else OrderSide.BUY
    other=c.s.order_factory.market(instrument.id,side,instrument.make_qty(4000 if different!="instrument" else 1))
    other.apply(TestEventStubs.order_accepted(other))
    fill=TestEventStubs.order_filled(other,instrument,position_id=PositionId("OTHER" if different=="id" else str(c.position.id)),
        last_px=instrument.make_price(100),commission=Money(0,instrument.quote_currency),ts_event=100)
    other.apply(fill);wrong=Position(instrument,fill)
    c.s.cache.position=lambda i:wrong
    c.s.on_order_filled(event);c.s.on_position_event(c.event())
    assert len(c.sent)==1 and c.s._staging_a_forced_children


def test_boundary_superseding_parent_retains_current_native_inflight_child():
    c=forced(accept=False);s=c.s;old=c.sent[-1]
    assert not old.is_closed and not old.is_open
    before=dict(s._staging_a_forced_children[c.sol.id])
    s._risk_first_sol_stop=lambda *a:False;s._split_stop=lambda *a:None
    s._discard_queued_intents=lambda *a:None;s._accepted_reductions={}
    s._v3_reduction=None;s.clock=N(timestamp_ns=lambda:100);s.cancel_order=lambda o:None
    s._begin_forced_close("TERMINAL_BOUNDARY_SETTLEMENT")
    assert s._staging_a_forced_children[c.sol.id]==before
    s._submit_forced_closes_from_cache();s.on_position_event(c.event())
    assert len(c.sent)==1  # No duplicated order while original child lacks terminal ACK.
