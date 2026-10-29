"""Actual live producer/domain/C1/cancel callback; no native engine or transport."""
import ast
from decimal import Decimal as D
from types import SimpleNamespace as N
import pytest
from coinmaster.domain.wave_overlay import Candidate,Episode,WaveOverlayState
from test_e4_c1_manage_only_pure import ROOT,Q as BaseQ,run_ast,nodes


class Q(BaseQ):
    def __float__(self):return float(self.value)


def extract(path,name,newname,bases,methods):
    source=next(n for n in ast.parse((ROOT/path).read_text()).body if isinstance(n,ast.ClassDef) and n.name==name)
    return ast.ClassDef(name=newname,bases=[ast.Name(id=b,ctx=ast.Load()) for b in bases],keywords=[],
        body=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in methods],decorator_list=[])


def fixture():
    env=dict(D=D,Decimal=D,OrderSide=N(BUY="BUY",SELL="SELL"),CUT="C1_RESIDUAL_CUT",RESTORE="C1_RESIDUAL_RESTORE")
    run_ast(nodes("strategy/residual_recovery.py",{"ResidualRecoveryResearch"}),env)
    run_ast([extract("strategy/wave_overlay.py","WaveOverlayStrategy","Base",["ResidualRecoveryResearch"],
        {"_queue_confirmed_btc_targets","_discard_queued_intents","on_order_canceled","_has_confirmed_btc_remainder"})],env)
    run_ast([extract("strategy/live_recovery.py","RecoverableWaveOverlayStrategy","Live",["Base"],
        {"_live_c1_tp_priority","_queue_confirmed_btc_targets"})],env)
    s=env["Live"]()
    class ID(str):venue="SYNTHETIC"
    s.config=N(research_residual_recovery=True,btc_id=ID("BTC"),sol_id=ID("SOL"),
        research_c1_restore_dd=D(".4"),max_mark_age_ns=1000,terminal_close_at_ns=None,
        research_c1_btc_postcut_d1=True,btc_signal_id=None,research_v0_execution_repairs=False,deposit_runtime=None,research_sol_risk_first=None)
    s._active_c1_authorized=True;s._domain=WaveOverlayState(Candidate());s._domain.set_execution_lots(btc=D(1),sol=D(1))
    ep=Episode("episode",1,1000,1,wave_levels=(.01,.02,.03));s._domain.episode=ep
    ep.btc_entry_vwap=100;ep.btc_initial_qty=20;ep.btc_open_qty=20
    ep.btc_tp_target_lots={0:8,1:8,2:4};ep.btc_tp_filled_lots={2:1};ep.btc_risk_retired_lots={}
    s._split_parent=None;s._split_unfinished=lambda:False;s._carry_busy=lambda:False;s._bind_native_lots=lambda:None
    s._forced_close_reason=None;s._liquidating=False;s._mandatory_sol_exit=None
    s._queued_intents=[];s._queued_intent_ready_ns={};s._pending_by_order={};s._deferred_selective_entries={};s._selected_entry_audits={}
    s._sigma_by_order={};s._decision_index_by_order={};s._bars=[];s._v3_orders={};s._forced_close_orders=set()
    s._c1_state=None;s._c1_intents={};s._c1_terminal_ids=set();s._c1_fill_epoch=0;s._c1_sol_levels={};s.c1_audit=[]
    s._c1_last_bars={"BTC_POSTCUT_D1":dict(instrument="BTC",open_ns=10,close_ns=50,available_ns=60)};s._c1_checkpoint=dict(E=D(700),H=D(1000),DD=D(".3"),C=D(200),source=90,receipt=91,epoch=0)
    orders=[];rows=[];sent=[];cancelled=[];terminal=[]
    quote=N(instrument_id="BTC",ts_event=100,bid_price=Q("99"),ask_price=Q("100"))
    pos=N(quantity=Q("20"),instrument_id="BTC")
    s.cache=N(quote_tick=lambda inst:quote,orders_open=lambda:[o for o in orders if not o.is_closed],orders_inflight=lambda:[],
        positions_open=lambda:[pos],order=lambda client:next((o for o in orders if o.client_order_id==client),None),
        account_for_venue=lambda venue:N(last_event=N(ts_event=80)),instrument=lambda inst:N(min_quantity=None,min_notional=None))
    s._recovery_runtime=N(all_submissions=lambda:list(rows))
    s._c1_first_fresh_quote=lambda *a,**k:None
    s._hb_position=lambda inst:pos;s._entries_enabled=lambda:True;s._tier_allows_increase=lambda *a:True
    s._terminal_submission=lambda oid:terminal.append(oid)
    for name in ("_next_terminal","_hedge_terminal","_requeue_accepted_reduction","_reconcile_terminal_flat","_reconcile_group_flat"):
        setattr(s,name,lambda *a,**k:None)
    s._conditional_enabled=lambda:False;s._ordinary_forced_close_active=lambda:False;s._research_protect_latch=None
    def cancel(order):order.is_pending_cancel=True;cancelled.append(order.client_order_id)
    s.cancel_order=cancel
    def submit(intent,*a,**k):
        sent.append(intent);s._pending_by_order["C1"]=intent;s._c1_bind_submission(intent,"C1",k["ts_now"])
    s._submit_intent=submit
    return N(s=s,ep=ep,quote=quote,pos=pos,orders=orders,rows=rows,sent=sent,cancelled=cancelled,terminal=terminal)


def claim(c,state="CUT_RESOLVING"):
    c.s._c1_state=dict(group="episode",state=state,instrument=c.s.config.btc_id,side=1,step=D(1),
        held_lots=20,target_lots=15,cut_lots=5,cut_submitted=False,restore_submitted=False,cut_filled=5,
        restore_filled=0,credit=5,cut_value=D(450),bucket={0:2,1:2,2:1},revoked=False,
        claim_ns=95,cut_terminal_ns=11,last_cut_fill_ns=10,confirmation=None)


def rights(c):
    e=c.ep
    return dict(target=dict(e.btc_tp_target_lots),filled=dict(e.btc_tp_filled_lots),retired=dict(e.btc_risk_retired_lots),held=e.btc_open_qty)


def test_existing_queued_tp_surrenders_only_unsent_reservations_and_cut_submits_once():
    c=fixture();s=c.s;s._queue_confirmed_btc_targets(None,0,90)
    original=rights(c);assert len(s._queued_intents)==3
    claim(c)
    for _ in range(3):s._queue_confirmed_btc_targets(None,0,100)
    assert s._queued_intents==[] and c.ep.pending=={} and not c.ep.btc_tps
    assert rights(c)==original
    s._c1_quote(c.quote,decision_ns=100);s._queue_confirmed_btc_targets(None,0,101);s._c1_quote(c.quote,decision_ns=101)
    assert len(c.sent)==1 and c.sent[0].reason=="C1_RESIDUAL_CUT" and c.sent[0].quantity==5
    assert s._queued_intents==[] and rights(c)==original


@pytest.mark.parametrize("phase",["CUT_RESOLVING","HELD"])
def test_actual_cancel_callback_does_not_requeue_then_next_quote_submits(phase):
    c=fixture();s=c.s
    c.ep.wave_levels=(.03,);c.ep.btc_tp_target_lots={0:20};c.ep.btc_tp_filled_lots={0:1}
    # Initialize an existing native owner from the actual domain planner.
    intent=s._domain.plan_confirmed_btc_targets()[0]
    s._pending_by_order["TP"]=intent
    native=N(client_order_id="TP",is_closed=False,is_pending_cancel=False)
    c.orders.append(native);c.rows.append(dict(intent_id=intent.id,state="ACCEPTED"))
    claim(c,phase)
    if phase=="HELD":s._c1_state["confirmation"]=dict(close_ns=98,open_ns=97,close=D(100))
    s._queue_confirmed_btc_targets(None,0,100);s._c1_quote(c.quote,decision_ns=100)
    assert c.cancelled==["TP"] and c.sent==[] and "TP" in s._pending_by_order
    s._queue_confirmed_btc_targets(None,0,101);s._c1_quote(c.quote,decision_ns=101)
    assert c.cancelled==["TP"] and not c.sent
    native.is_closed=True;native.is_pending_cancel=False;c.rows[0]["state"]="TERMINAL"
    s.on_order_canceled(N(client_order_id="TP",ts_event=102))
    assert c.terminal==["TP"] and not s._queued_intents and not s._pending_by_order
    s._queue_confirmed_btc_targets(None,0,103);s._c1_quote(c.quote,decision_ns=103)
    assert len(c.sent)==1 and c.sent[0].reason==("C1_RESIDUAL_CUT" if phase=="CUT_RESOLVING" else "C1_RESIDUAL_RESTORE")


@pytest.mark.parametrize("owner",["pending","journal","other_group","c1","market","other_reason"])
def test_priority_never_erases_owned_or_unrelated_candidates(owner):
    c=fixture();s=c.s;s._queue_confirmed_btc_targets(None,0,90);intent=s._queued_intents[0][0]
    if owner=="pending":s._pending_by_order["UNKNOWN"]=intent
    if owner=="journal":c.rows.append(dict(intent_id=intent.id,state="SUBMITTING"))
    from dataclasses import replace
    changes={"other_group":dict(episode_id="other"),"market":dict(limit_price=None),"other_reason":dict(reason="INDEPENDENT_EXIT")}
    if owner in changes:
        intent=replace(intent,**changes[owner]);s._queued_intents[0]=(intent,None,0)
    if owner=="c1":s._c1_intents[intent.id]="CUT"
    claim(c);s._queue_confirmed_btc_targets(None,0,100)
    assert [i.id for i,_,_ in s._queued_intents]==[intent.id]
    assert intent.id in c.ep.pending


@pytest.mark.parametrize("blocked",["no_confirmation","pre_d1","unknown_money","dd","reclaim","stale_quote","revoked","released","inactive"])
def test_held_denial_keeps_normal_tp_protection(blocked):
    c=fixture();s=c.s;claim(c,"HELD");t=s._c1_state;t["confirmation"]=dict(close_ns=98,open_ns=97,close=D(100))
    if blocked=="no_confirmation":t["confirmation"]=None
    if blocked=="pre_d1":s._c1_last_bars={}
    if blocked=="unknown_money":s._c1_checkpoint=None
    if blocked=="dd":s._c1_checkpoint["DD"]=D(".41")
    if blocked=="reclaim":t["cut_value"]=D(550)
    if blocked=="stale_quote":c.quote.ts_event=-1001
    if blocked=="revoked":t["revoked"]=True
    if blocked=="released":t["state"]="RELEASED"
    if blocked=="inactive":s._active_c1_authorized=False
    s._queue_confirmed_btc_targets(None,0,100)
    assert len(s._queued_intents)==3 and not c.sent


def test_restore_cancel_barrier_admission_denial_resumes_tp_next_quote():
    c=fixture();s=c.s;claim(c,"HELD");t=s._c1_state;t["confirmation"]=dict(close_ns=98,open_ns=97,close=D(100))
    s._active_c1_authorized=False;s._queue_confirmed_btc_targets(None,0,90);s._active_c1_authorized=True
    original=rights(c);s._queue_confirmed_btc_targets(None,0,100)
    assert not s._queued_intents and rights(c)==original
    s._tier_allows_increase=lambda *a:False;s._c1_quote(c.quote,decision_ns=100)
    assert t["confirmation"] is None and t["state"]=="HELD" and not c.sent
    s._queue_confirmed_btc_targets(None,0,101)
    assert len(s._queued_intents)==3 and rights(c)==original


@pytest.mark.parametrize("loss",["money","reclaim","dd","d1"])
def test_restore_eligibility_loss_resumes_tp_without_latched_priority(loss):
    c=fixture();s=c.s;claim(c,"HELD");s._c1_state["confirmation"]=dict(close_ns=98)
    assert s._live_c1_tp_priority(100)
    if loss=="money":s._c1_checkpoint=None
    if loss=="reclaim":s._c1_state["cut_value"]=D(550)
    if loss=="dd":s._c1_checkpoint["DD"]=D(".41")
    if loss=="d1":s._c1_last_bars={}
    s._queue_confirmed_btc_targets(None,0,101)
    assert len(s._queued_intents)==3 and not c.sent


def test_late_ordinary_fill_revokes_claim_without_erasing_native_owner():
    c=fixture();s=c.s
    intent=s._domain.plan_confirmed_btc_targets()[0]
    s._pending_by_order["TP"]=intent
    native=N(client_order_id="TP",is_closed=False,is_pending_cancel=False)
    c.orders.append(native);c.rows.append(dict(intent_id=intent.id,state="ACCEPTED"))
    claim(c);s._c1_quote(c.quote,decision_ns=100)
    assert c.cancelled==["TP"] and not c.sent
    s._c1_native_fill(N(client_order_id="TP",ts_event=101))
    assert s._c1_state["revoked"] and s._c1_state["credit"]==0
    assert s._pending_by_order["TP"] is intent and not native.is_closed
    s._queue_confirmed_btc_targets(None,0,102);s._c1_quote(c.quote,decision_ns=102)
    assert not c.sent and not s._live_c1_tp_priority(102) and s._pending_by_order["TP"] is intent
