"""Exact two failing event contracts, synthetic source facts only/no engines."""
from decimal import Decimal as D
from types import SimpleNamespace as N
import json
import pytest
from coinmaster.strategy.cm2_native import CM2Strategy
from coinmaster.strategy.cm2_reference_policy import BtcParent,DAY,HOUR
from coinmaster.strategy.cm2_checkpoint import canonical,decode
from test_cm2_reference_cycle_pure import policy,row,T0
from test_cm2_reference_quote_phase_pure import phase_adapter


def h4_adapter():
    f,clock,calls,quote=phase_adapter();p=policy()
    for i in range(35):p.accept_closed_day(row(i),receipt_ns=T0+(i+1)*DAY,btc_high=101,btc_low=99)
    p._wait_regime=True;p._regime_latch_ns=T0+35*DAY
    clock[0]=T0+35*DAY+4*HOUR
    p.accept_closed_btc_h4(open_ns=clock[0]-4*HOUR,close_ns=clock[0],available_ns=clock[0],receipt_ns=clock[0],close=D(100+2*p.signals[-1].side))
    f.reference=p;f._drain={};f._needs_daily=True
    def evaluate(now):
        if not f._needs_daily:return False
        f._needs_daily=False
        if p.reentry_allowed():
            calls.append(('queue',now));p._parent=BtcParent('new',p.signals[-1].side,p.signals[-1].index,1.25,(.01,.02,.03),10000)
            p._wait_regime=False;p._h4_release_daily_ns=None
        return False
    f._evaluate_daily=evaluate
    return f,clock,calls,quote


@pytest.mark.parametrize('first_asset',['BTC','SOL'])
def test_h4_fact_activates_only_quote_tail_with_pending_daily(first_asset):
    f,clock,calls,quote=h4_adapter();p=f.reference;now=clock[0]
    assert not p.reentry_allowed() and p._h4_reentry_facts
    tick=quote();tick.instrument_id=first_asset
    CM2Strategy.on_quote_tick(f,tick)
    assert ('queue',now) in calls and p.parent.q0_ns is None
    assert not p._h4_reentry_facts and calls[-1]==('capture',now)
    CM2Strategy.on_quote_tick(f,quote())
    assert p.parent.q0_ns==now  # next BTC callback, same ns permitted
    CM2Strategy.on_quote_tick(f,quote());assert p.parent.q1_ns is None
    clock[0]+=1;CM2Strategy.on_quote_tick(f,quote());assert p.parent.q1_ns==now+1


def test_h4_buffer_json_replay_and_c1_fact_phase_are_distinct():
    f,clock,calls,quote=h4_adapter();p=f.reference
    restored=policy();restored.restore_state(decode(json.loads(canonical(p.snapshot_state()))))
    assert not restored.reentry_allowed() and restored.consume_h4_reentry_facts(clock[0])
    assert restored.reentry_allowed() and not restored.consume_h4_reentry_facts(clock[0])
    restored.accept_closed_btc_h4(open_ns=clock[0]-4*HOUR,close_ns=clock[0],available_ns=clock[0],receipt_ns=clock[0],close=D(100))
    assert not restored._h4_reentry_facts  # accepted global watermark, not a new D1 right


def drain_adapter(purpose='TP_GTC',filled='0',quantity='1'):
    now=100;qty=[D(quantity)];calls=[]
    tick=N(instrument_id='BTC',ts_event=now,bid_price=N(as_decimal=lambda:D(100)),ask_price=N(as_decimal=lambda:D(100)))
    f=N(id='TEST',config=N(btc_id='BTC',sol_id='SOL'),clock=N(timestamp_ns=lambda:now,timer_names=[]),
        reference=N(parent=None),_owned={'retired':{'instrument_id':'BTC','purpose':purpose,'parent_id':None}},
        _drain={'GLOBAL':{'state':{'scoped_zero_ids':['BTC'],'first_ns':now,'deadline_ns':now+120_000_000_000,'reconcile_required':False},'reason':'TERMINAL','parent_id':None}},
        _drain_dispatching=set(),_quotes={'BTC':tick},_orders=lambda i:[],drain_audit=[],
        cache=N(order=lambda oid:N(is_closed=True,filled_qty=N(as_decimal=lambda:D(filled)))),
        _persist_checkpoint=lambda:None)
    f._position=lambda i: N(quantity=N(as_decimal=lambda:qty[0]),is_long=True) if i=='BTC' and qty[0]>0 else None
    f._scope_for=lambda i:CM2Strategy._scope_for(f,i)
    f._reconcile_drains=lambda now:CM2Strategy._reconcile_drains(f,now)
    f._execute_drain=lambda *a:CM2Strategy._execute_drain(f,*a)
    def send(i,q,side,purpose,ns,observed,**kw):
        from coinmaster.strategy.cm2_order_contract import bbo_status
        if not bbo_status(observed,ns)[0]:return False
        assert observed is tick and kw['reduce_only'] and side==-1
        calls.append(q);qty[0]=D(0)
        f._execute_drain(observed,ns,'GLOBAL')  # real synchronous reentrant boundary, no duplicate send
        return True
    f._send=send
    return f,qty,calls,N(client_order_id='retired',ts_event=now)


def test_cancel_ack_advances_existing_terminal_drain_without_quote():
    f,qty,calls,event=drain_adapter()
    CM2Strategy._terminal_event(f,event)
    assert calls==[D(1)] and qty[0]==0 and not f._drain and not f._owned
    assert not f._drain_dispatching and f.drain_audit[0]['event']=='NATIVE_CALLBACK_PROGRESS'
    CM2Strategy._terminal_event(f,event);assert calls==[D(1)]


def test_zero_progress_ro_terminal_stops_while_positive_native_progress_advances():
    f,qty,calls,event=drain_adapter(purpose='DRAIN')
    CM2Strategy._terminal_event(f,event);assert not calls and qty[0]==1 and f._drain
    f,qty,calls,event=drain_adapter(purpose='DRAIN',filled='.5')
    CM2Strategy._terminal_event(f,event);assert calls==[D(1)] and qty[0]==0


def test_reject_no_native_quantity_progress_is_one_attempt_not_loop():
    f,qty,calls,event=drain_adapter();f._owned={}
    f._send=lambda *a,**kw:calls.append(1) or True
    first=dict(f._drain['GLOBAL']['state']);f._execute_drain(f._quotes['BTC'],100,'GLOBAL')
    assert calls==[1] and qty[0]==1 and f._drain['GLOBAL']['state']==first
    assert not f._drain_dispatching


def test_cached_stale_quote_cannot_advance_cancel_receipt():
    f,qty,calls,event=drain_adapter();f._quotes['BTC'].ts_event=-120_000_000_000
    CM2Strategy._terminal_event(f,event)
    assert not calls and qty[0]==1 and f._drain


def test_terminal_engineering_protocol_and_actual_api_boundary(tmp_path,monkeypatch):
    from dataclasses import asdict
    from pathlib import Path
    from coinmaster.research import cm2_reference_fixture as fixture,cm2_runner as runner
    from test_cm2_reference_native_pure import config
    identity=fixture.TERMINAL_FIXTURE_ID;start,end=fixture.fixture_interval(identity)
    protocol=fixture.fixture_protocol(identity)
    assert 'native_callback_progress' in protocol['mandatory'] and 'standing_protection_canceled_at_boundary' in protocol['mandatory']
    request={'fixture_id':identity,'start_ns':start,'end_ns':end,'policy':asdict(config()),
        'current_hl_execution_inputs':str(Path(__file__).parent/'fixtures/hl-current-20261029')}
    monkeypatch.setattr(CM2Strategy,'__init__',lambda *a,**k:(_ for _ in ()).throw(AssertionError('NO_STRATEGY')))
    proof=runner.fixture_api_boundary_probe(request,tmp_path/'probe')
    assert proof['boundary_calls']==1 and proof['native_engine_constructions']==0

@pytest.mark.parametrize('scope',["GLOBAL","BTC_ECONOMIC"])
@pytest.mark.parametrize('quote_ns',[99,100,101])
def test_drain_requires_quote_at_or_after_persisted_decision_epoch(scope,quote_ns):
    f,qty,calls,event=drain_adapter();f._owned={}
    f._drain={scope:f._drain['GLOBAL']}
    f._quotes['BTC'].ts_event=quote_ns
    f._send=lambda *a,**kw:calls.append(1) or False
    f._execute_drain(f._quotes['BTC'],101,scope)
    assert calls==([1] if quote_ns>=100 else [])
    assert qty[0]==1 and f._drain[scope]['state']['first_ns']==100
    assert not f._drain_dispatching
