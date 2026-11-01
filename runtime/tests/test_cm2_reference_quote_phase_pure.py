"""Synthetic causal callback phase facts only; no historical trade/date inputs."""
from decimal import Decimal as D
from types import SimpleNamespace as N
import pytest
from coinmaster.strategy.cm2_native import CM2Strategy
from coinmaster.strategy.cm2_execution import SafetyState
from test_cm2_reference_policy_pure import hand_parent,split,fill,T0,DAY


def phase_adapter():
    policy=hand_parent(side=-1,notional=10000);split(policy);fill(policy,'entry',100)
    for plan in policy.confirmed_targets('hand'):fill(policy,'tp'+str(plan.level),plan.quantity,kind='TP',level=plan.level)
    policy._parent.close_reason='REGIME'  # owned synthetic state, not the public copied snapshot
    source=T0+DAY+120_000_000_100;clock=[source];calls=[]
    f=N(id='SYNTHETIC',reference=policy,clock=N(timestamp_ns=lambda:clock[0],timer_names=[]),
        config=N(btc_id='BTC',sol_id='SOL',trading_start_open_ns=0,terminal_close_at_ns=10**20,btc_step=D('.01')),
        safety=SafetyState(),_restore_failed=False,_quotes={},_owned={},_queued_tp={},_needs_daily=False,
        _drain={'BTC_ECONOMIC':{'state':{'scoped_zero_ids':['BTC']},'parent_id':'hand','reason':'REGIME'}},
        drain_audit=[],_position=lambda i:None,_orders=lambda i:[],_persist_checkpoint=lambda:None,
        _check_emergency_drawdown=lambda now:None,_capture_btc_source=lambda now:calls.append(('capture',now)),
        _execute_targets=lambda *a:None,_execute_c1=lambda *a:None,_audit=lambda *a:None,entry_sizing_audit=[])
    f._scope_for=lambda i:CM2Strategy._scope_for(f,i)
    f._reconcile_drains=lambda now:CM2Strategy._reconcile_drains(f,now)
    f._execute_entry=lambda tick,now:CM2Strategy._execute_entry(f,tick,now)
    f._execute_drain=lambda *a:calls.append(('drain',clock[0]))
    f._reference_limit=lambda iid,price:N(as_decimal=lambda:price)
    f._send=lambda *a,**k:calls.append(('send',clock[0])) or True
    def admitted_selector(now):
        if not f._needs_daily:return False
        # Supplied already-admitted pure economic intent: this fixture tests
        # callback ownership, not signal selection or economic qualification.
        calls.append(('select',now));f._needs_daily=False;f.reference=hand_parent(side=-1,notional=10000)
        return False
    f._evaluate_daily=admitted_selector
    def quote():return N(instrument_id='BTC',ts_event=clock[0],bid_price=N(as_decimal=lambda:D(100)),ask_price=N(as_decimal=lambda:D(100)))
    return f,clock,calls,quote


def test_close_completing_quote_consumed_next_same_timestamp_quote_can_q0():
    f,clock,calls,quote=phase_adapter();source=clock[0]
    CM2Strategy.on_quote_tick(f,quote())
    assert f.reference.parent is None and f._needs_daily and calls==[('capture',source)]
    CM2Strategy.on_quote_tick(f,quote())
    assert f.reference.parent.q0_ns==source and calls.count(('select',source))==1
    assert calls.count(('capture',source))==2
    # Another callback at identical ns cannot become q1; no new quote dedup or TTL.
    CM2Strategy.on_quote_tick(f,quote());assert f.reference.parent.selected_quantity is None
    clock[0]+=1;CM2Strategy.on_quote_tick(f,quote())
    assert f.reference.parent.q1_ns==source+1 and f.reference.parent.selected_quantity>0
    assert calls[-1]==('capture',source+1)


@pytest.mark.parametrize('terminal_kind',['cancel','closed_fill_receipt'])
def test_nonquote_terminal_reconcile_does_not_skip_next_btc_callback(terminal_kind):
    f,clock,calls,quote=phase_adapter()
    f._owned={'close':{'purpose':'DRAIN','instrument_id':'BTC','parent_id':'hand'}}
    f.cache=N(order=lambda oid:N(is_closed=True))
    f._terminal_event=lambda *a,**k:CM2Strategy._terminal_event(f,*a,**k)
    event=N(client_order_id='close',ts_event=clock[0])
    if terminal_kind=='cancel':CM2Strategy.on_order_canceled(f,event)
    else:CM2Strategy._terminal_event(f,event,only_if_closed=True)
    assert f.reference.parent is None and not calls
    CM2Strategy.on_quote_tick(f,quote())
    assert f.reference.parent.q0_ns==clock[0] and ('select',clock[0]) in calls
    assert calls[-1]==('capture',clock[0])


def test_synchronous_close_side_effect_rearms_daily_without_same_callback_entry():
    f,clock,calls,quote=phase_adapter();f._drain={};f._needs_daily=True
    p=f.reference;p.decide_on_day=lambda **kw:N(action='BTC_CLOSE',reason='REGIME',parent_id='hand')
    f._native_btc_capital=lambda now:{'equity':D(10000)}
    def synchronous_native_close(now,scope,ids,reason):
        f._drain[scope]={'state':{'scoped_zero_ids':ids},'parent_id':'hand','reason':reason}
        f._reconcile_drains(now)  # supplied native flat/terminal cancel ACK facts
    f._begin_drain=synchronous_native_close
    f._evaluate_daily=lambda now:CM2Strategy._evaluate_daily(f,now)
    CM2Strategy.on_quote_tick(f,quote())
    assert f.reference.parent is None and f._needs_daily  # re-arm not overwritten
    assert not any(kind=='send' for kind,_ in calls) and calls[-1]==('capture',clock[0])
