"""Actual split/recoverable/domain/SQLite methods; native boundary is a pure sink."""
import ast,asyncio,hashlib,json,time
from collections import deque
from dataclasses import replace
from datetime import datetime,timezone
from decimal import Decimal as D
from types import SimpleNamespace as N
import pytest
from coinmaster.domain.wave_overlay import Candidate,Episode,Intent,WaveOverlayState
from coinmaster.domain.deposit_protection import DepositProtection
from coinmaster.ops.paper import PaperRuntime
from test_e4_c1_manage_only_pure import code,nodes,run_ast,config,order,Q,ROOT,ACCOUNT,ACCOUNT_ID

class NativeQ(Q):
    def __str__(self):return str(self.value)
    def __float__(self):return float(self.value)

def method(file,cls,name):
    node=next(n for n in ast.parse((ROOT/file).read_text()).body if isinstance(n,ast.ClassDef) and n.name==cls)
    return next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name==name)

def fixture(code,tmp_path):
    env=code.env;env['replace']=replace;env['OrderSide']=N(SELL='SELL',BUY='BUY')
    for name in ('_queue_confirmed_btc_targets','_bind_native_lots','_entries_enabled','_record_submission','on_order_filled'):
        run_ast([method('strategy/wave_overlay.py','WaveOverlayStrategy',name)],env)
        setattr(env['WaveOverlayStrategy'],name,env[name])
    split_env=dict(D=D,deque=deque,HOUR=3_600_000_000_000,DAY=86_400_000_000_000)
    run_ast(nodes('strategy/split_cover.py',{'SplitCoverResearch'}),split_env)
    class Combined(code.Strategy,split_env['SplitCoverResearch']):pass
    cfg=config();cfg.research_btc_split50=True;cfg.research_btc_split_planref_v1=True
    cfg.entries_enabled=True;cfg.deposit_runtime=None;cfg.entries_gate=None
    cfg.research_v0_selective_lifecycle_repairs=True
    s=Combined(cfg)
    selected=json.loads((ROOT.parent/'configs/hl-live-v3-dp50.candidate.json').read_text())['candidate']
    s._candidate=Candidate(**selected);s._domain=WaveOverlayState(s._candidate)
    s._domain.set_execution_lots(btc=D(1),sol=D(1))
    # Focused state fixture, not native ordinary-entry/alpha proof. NativeA uses public callbacks.
    ep=Episode('episode',1,1000,1,wave_levels=(.01,.02,.03))
    s._domain.episode=ep;s._split_cover_init()
    intent=s._domain._intent(ep,'BTC_ENTRY',1,None,requested_notional=2000)
    s._split_prepare(intent,D(20),D(1),1,None,0)
    s._active_c1_authorized=True;s._manage_only_preparation=False;s.recovery_confirmed=True
    s._recovery_health=lambda:True;s._live_input_ws_epoch=lambda:4
    s._order_audit={'ENTRY':{'action':'BTC_ENTRY'}};s._pending_by_order={'ENTRY':intent}
    s._sigma_by_order={};s._decision_index_by_order={};s._queued_intents=[];s._queued_intent_ready_ns={}
    s._seen_trade_ids=set();s._c1_state=None;s._c1_intents={};s._c1_fill_epoch=0;s._forced_close_reason=None;s._liquidating=False;s._carry_busy=lambda:False
    s._deposit_exit_orders=set();s._terminal_order_ids=set();s._liquidation_orders=set();s._v3_orders={}
    s._deposit=DepositProtection(limit_percent=55);s._deposit.initialize(D(1000),1)
    s.clock=N(timestamp_ns=lambda:1000);s._live_money_provider=lambda:None
    s.suspend_live_financial_authority()
    r=code.Runtime(tmp_path/'partial.sqlite','fixture-owner',10**20);r.acquire()
    r.acquire_live_account(ACCOUNT,'HYPERLIQUID',lock_root=tmp_path/'locks')
    s.attach_recovery_runtime(r);cfg.deposit_runtime=r
    entry=order('ENTRY',side='BUY',quantity='20',reduce=False,closed=False)
    entry.side='BUY';entry.quantity=NativeQ('20');entry.filled_qty=NativeQ('0')
    entry.venue_order_id='entry-venue';entry.status=N(name='PARTIALLY_FILLED')
    pos=N(instrument_id=cfg.btc_id,id='position',strategy_id=str(s.id),account_id=ACCOUNT_ID,
        is_long=True,quantity=NativeQ('0'),events=[])
    instrument=N(size_increment=NativeQ('1'),min_quantity=NativeQ('1'),min_notional=N(as_decimal=lambda:D(10)))
    orders=[entry];cancelled=[];sent=[];refresh=[]
    s.cache=N(positions_open=lambda:[pos] if pos.quantity.as_decimal() else [],
        orders=lambda venue=None:list(orders),orders_open=lambda:[o for o in orders if not o.is_closed],
        orders_inflight=lambda:[],instrument=lambda instrument_id:instrument,
        order=lambda client:next((o for o in orders if str(o.client_order_id)==str(client)),None))
    s._request_live_refresh=lambda:refresh.append(True)
    r.record_submission(client_order_id='ENTRY',intent_id=intent.id,episode_id=ep.id,action='BTC_ENTRY',
        instrument_id=str(cfg.btc_id),quantity='20',reduce_only=False,strategy_state=s.on_save()[env['_KEY']],
        order_shape=dict(side='BUY',kind='LIMIT',tif='GTC',post_only=True,price='100'))
    s.establish_owned_effect_chain(account_id=ACCOUNT_ID,ws_epoch=4,policy_sha256=env['recovery_policy_hash'](cfg,s._candidate))
    sink_env=dict(PaperRuntime=PaperRuntime)
    run_ast(nodes('ops/live_recovery.py',{'LiveRecoverySubmissionSink'}),sink_env)
    cfg.submission_sink=sink_env['LiveRecoverySubmissionSink'](r,s,frozenset({str(cfg.btc_id),str(cfg.sol_id)}))
    def native_cancel(self,native_order):
        marker=self._split_parent.get('partial_tp_replan_pending',())
        if marker:
            doc=json.loads(r.strategy_checkpoint()[0])
            encoded=code.env['_decode'](doc['state']['_split_parent'])
            assert encoded['partial_tp_replan_pending']==marker
        assert all(str(e.trade_id) in r.applied_fill_ids() for e in pos.events)
        assert not native_order.is_pending_cancel
        native_order.is_pending_cancel=True;cancelled.append(str(native_order.client_order_id))
    env['WaveOverlayStrategy'].cancel_order=native_cancel
    def native_submit(self,order):sent.append(order)
    env['WaveOverlayStrategy'].submit_order=native_submit
    def dispatch(self,intent,bid,ask,sigma,index,**kwargs):
        assert all(str(e.trade_id) in r.applied_fill_ids() for e in pos.events)
        if intent.action!='BTC_REDUCE':pytest.fail('No opening permitted while financialPENDING')
        client='TP'+str(len(sent)+1)
        native=order(client,quantity=str(intent.quantity));native.side='SELL'
        native.quantity=NativeQ(str(intent.quantity));native.filled_qty=NativeQ('0')
        native.order_type=N(name='LIMIT');native.time_in_force=N(name='GTC')
        native.ts_init=1000;native.is_post_only=True;native.has_price=True
        native.price=NativeQ(str(intent.limit_price));native.venue_order_id=client+'-venue'
        self._pending_by_order[client]=intent
        assert self._record_submission(native,intent.id,intent.episode_id,intent.action)
        orders.append(native);self.submit_order(native)
    env['WaveOverlayStrategy']._submit_intent=dispatch
    return N(s=s,r=r,entry=entry,pos=pos,orders=orders,cancelled=cancelled,sent=sent,
        refresh=refresh,intent=intent,cfg=cfg,env=env)

def fill(ctx,trade,quantity,*,terminal=False):
    s,r=ctx.s,ctx.r;qty=D(quantity);event=N(trade_id=trade,client_order_id='ENTRY',last_qty=NativeQ(quantity),last_px=NativeQ('100'),ts_event=100+len(ctx.pos.events))
    s._domain.on_fill(ctx.intent.id,float(qty),100,datetime.now(timezone.utc),None,decision_index=0)
    s._split_native_fill(ctx.intent,event)
    ctx.entry.filled_qty=NativeQ(str(ctx.entry.filled_qty.as_decimal()+qty));ctx.entry.is_closed=terminal
    ctx.pos.quantity=NativeQ(str(ctx.pos.quantity.as_decimal()+qty));ctx.pos.events.append(N(client_order_id='ENTRY',trade_id=trade))
    r.record_native_fill(trade_id=trade,native_event_id='native-'+trade,client_order_id='ENTRY',venue_order_id='entry-venue',
        instrument_id=str(ctx.cfg.btc_id),order_side='BUY',quantity=quantity,price='100',commission_amount='0',
        commission_currency='USDC',liquidity_side='TAKER',ts_event_ns=event.ts_event,ts_init_ns=event.ts_event)
    s._seen_trade_ids.add(trade);s._after_domain_fill(event)
    return event

def send_targets(ctx):
    for item in list(ctx.s._queued_intents):
        ctx.s._queued_intents.remove(item)
        ctx.s._queued_intent_ready_ns.pop(item[0].id,None)
        ctx.s._submit_intent(item[0],99,100,item[1],item[2],ts_now=1000)

def cancel_ack(ctx,native):
    native.is_closed=True;native.is_pending_cancel=False;native.status=N(name='CANCELED')
    intent=ctx.s._pending_by_order.pop(str(native.client_order_id))
    ctx.s._domain.on_parent_cancelled(intent.id)
    ctx.r.terminal_submission(str(native.client_order_id),ctx.s.on_save()[ctx.env['_KEY']])
    ctx.s._queue_confirmed_btc_targets(None,0,1000) # Actual next-quote planner path after real ACK.

def test_actual_split_and_actual_entries_temporary_financial_wait_parks_no_opening(code,tmp_path):
    ctx=fixture(code,tmp_path)
    try:
        fill(ctx,'first','4')
        assert not ctx.s._entries_enabled() and not ctx.s._split_stop_requested()
        # Last terminal ACK already happened before a later financial suspension.
        ctx.entry.is_closed=True;ctx.s._pending_by_order.pop('ENTRY')
        ctx.r.terminal_submission('ENTRY',ctx.s.on_save()[ctx.env['_KEY']])
        tick=N(instrument_id=ctx.cfg.btc_id,bid_price=NativeQ('99'),ask_price=NativeQ('100'),ts_event=1000)
        ctx.s._split_check(tick)
        assert not ctx.s._split_parent['closed'] and ctx.refresh and ctx.sent==[]
        send_targets(ctx)
        assert sum(o.quantity.as_decimal() for o in ctx.sent)==D(4)
        assert all(o.is_reduce_only for o in ctx.sent)
    finally:ctx.r.close()

def test_partial_latefill_cancel_pending_duplicate_then_full_baseline_targets(code,tmp_path):
    ctx=fixture(code,tmp_path)
    try:
        fill(ctx,'first','4');send_targets(ctx)
        assert len(ctx.sent)==1 and ctx.sent[0].quantity.as_decimal()==4
        assert not ctx.s._split_parent.get('partial_protection_reason')
        old=ctx.sent[0]
        second=fill(ctx,'second','2')
        assert ctx.cancelled==[str(old.client_order_id)] and old.is_pending_cancel
        assert ctx.s._queued_intents==[] and ctx.s._split_parent['partial_tp_replan_pending']
        # Source duplicate callback returns before planning/cancel/quantity changes.
        before=ctx.r.native_revision();ctx.s.on_order_filled(second)
        assert ctx.r.native_revision()==before and len(ctx.cancelled)==1
        fill(ctx,'late-during-cancel','3')
        assert len(ctx.cancelled)==1 and ctx.s._queued_intents==[]
        fill(ctx,'final-entry','11',terminal=True)
        assert ctx.s._split_parent['closed'] and ctx.s._domain.episode.btc_initial_qty==20
        assert ctx.s._queued_intents==[] # Never replace before old native cancel ACK.
        cancel_ack(ctx,old)
        planned={i.level:(D(str(i.quantity)),D(str(i.limit_price))) for i,_,_ in ctx.s._queued_intents}
        baseline=WaveOverlayState(ctx.s._candidate);baseline.set_execution_lots(btc=D(1),sol=D(1))
        baseline.episode=Episode('baseline',1,1000,1,btc_initial_qty=20,btc_open_qty=20,btc_entry_vwap=100,
            btc_planref_vwap=100,btc_target_basis_qty=20,wave_levels=(.01,.02,.03))
        expected={i.level:(D(str(i.quantity)),D(str(i.limit_price))) for i in baseline.plan_confirmed_btc_targets()}
        assert planned==expected and [planned[k][0] for k in sorted(planned)]==[D(4),D(4),D(12)]
        send_targets(ctx)
        working=[o for o in ctx.sent if not o.is_closed]
        assert sum(o.quantity.as_decimal() for o in working)==20
        assert len(working)==3 and 'partial_tp_replan_pending' not in ctx.s._split_parent
    finally:ctx.r.close()

@pytest.mark.parametrize('hard',['PAUSE','DP','FORCED'])
def test_hard_stop_rearms_without_new_terminal_and_DP_does_not_duplicate_TPs(code,tmp_path,hard):
    ctx=fixture(code,tmp_path)
    try:
        fill(ctx,'first','4')
        for item in list(ctx.s._queued_intents):ctx.s._domain.on_parent_cancelled(item[0].id)
        ctx.s._queued_intents=[]
        ctx.entry.is_closed=True;ctx.s._pending_by_order.pop('ENTRY')
        ctx.r.terminal_submission('ENTRY',ctx.s.on_save()[ctx.env['_KEY']])
        if hard=='PAUSE':ctx.r.entry_control_command('pause-new-entries','pause')
        if hard=='DP':ctx.s._deposit.observe(D(400),2)
        if hard=='FORCED':ctx.s._forced_close_reason='EXISTING_MARKET_EXIT'
        tick=N(instrument_id=ctx.cfg.btc_id,bid_price=NativeQ('99'),ask_price=NativeQ('100'),ts_event=1000)
        ctx.s._split_check(tick)
        assert ctx.s._split_parent['closed']
        if hard=='PAUSE':
            assert ctx.s._queued_intents
            send_targets(ctx);assert sum(o.quantity.as_decimal() for o in ctx.sent)==4
        else:assert ctx.s._queued_intents==[] and ctx.sent==[]
        assert ctx.s._c1_peak==D(15000) # Existing high-water never reset by management.
    finally:ctx.r.close()

def test_partial_below_native_minimum_is_unknown_not_sized_up(code,tmp_path):
    ctx=fixture(code,tmp_path)
    try:
        fill(ctx,'tiny','1')
        ctx.s.cache.instrument=lambda instrument_id:N(size_increment=NativeQ('1'),min_quantity=NativeQ('1'),min_notional=N(as_decimal=lambda:D(1000)))
        send_targets(ctx)
        assert ctx.sent==[] and ctx.s._split_parent['partial_protection_reason']
        assert not ctx.s._entries_enabled() and ctx.pos.quantity.as_decimal()==1
    finally:ctx.r.close()

def test_ownership_loss_is_not_temporary_money_wait_and_never_reports_flat(code,tmp_path):
    ctx=fixture(code,tmp_path)
    try:
        fill(ctx,'first','4')
        ctx.s._recovery_health=lambda:False
        assert not ctx.s._entries_enabled() and ctx.s._split_stop_requested()
        tick=N(instrument_id=ctx.cfg.btc_id,bid_price=NativeQ('99'),ask_price=NativeQ('100'),ts_event=1000)
        with pytest.raises(RuntimeError,match='RECOVERY_NOT_CONFIRMED'):ctx.s._split_check(tick)
        assert not ctx.s.recovery_confirmed and ctx.sent==[] and ctx.cancelled==[]
        assert ctx.pos.quantity.as_decimal()==4 # Unknown ownership is not a flat receipt.
    finally:ctx.r.close()

def test_default_research_hooks_keep_old_entry_stop_and_unfinished_target_block():
    env=dict(D=D,deque=deque,HOUR=3_600_000_000_000,DAY=86_400_000_000_000)
    run_ast(nodes('strategy/split_cover.py',{'SplitCoverResearch'}),env)
    for name in ('_entries_enabled','_queue_confirmed_btc_targets'):
        run_ast([method('strategy/wave_overlay.py','WaveOverlayStrategy',name)],env)
        setattr(env['SplitCoverResearch'],name,env[name])
    s=env['SplitCoverResearch']();s.config=N(research_v0_selective_lifecycle_repairs=False,
        deposit_runtime=None,entries_gate=None,entries_enabled=True)
    s._research_protect_latch=None;s._split_parent=dict(closed=False,filled=D(1),quantity=D(10))
    s._forced_close_reason=None;attempts=[]
    s._domain=N(plan_confirmed_btc_targets=lambda:attempts.append(True))
    s._carry_busy=lambda:False
    assert s._split_partial_targets_allowed() is False and s._split_stop_requested() is False
    s._queue_confirmed_btc_targets(None,0,1)
    assert attempts==[]
    s.config.entries_enabled=False
    assert s._split_stop_requested() is True
