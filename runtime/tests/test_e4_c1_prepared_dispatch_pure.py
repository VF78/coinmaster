"""Actual intent/SQLite preparation/final DP dispatch; no Nautilus imports."""
import ast,hashlib,json,time,asyncio
from decimal import Decimal as D
from dataclasses import replace
from types import SimpleNamespace as N
import pytest
from coinmaster.domain.deposit_protection import DepositProtection
from coinmaster.domain.wave_overlay import Candidate,Episode,Intent,WaveOverlayState
from test_e4_c1_manage_only_pure import code,nodes,run_ast,config,order,Q,ROOT,ACCOUNT,ACCOUNT_ID

def source_method(cls,name):
    body=next(n for n in ast.parse((ROOT/'strategy/wave_overlay.py').read_text()).body if isinstance(n,ast.ClassDef) and n.name==cls)
    return next(n for n in body.body if isinstance(n,ast.FunctionDef) and n.name==name)

@pytest.fixture
def prepared(code,tmp_path,monkeypatch):
    env=code.env
    boundary=env['WaveOverlayStrategy']
    env['NativeBoundary']=boundary
    # Real Python class compilation preserves super() and the actual DP caller code.
    selected=['_submit_intent','_record_submission','submit_order','_deposit_check','_deposit_equity','_terminal_without_fill']
    cls=ast.ClassDef(name='WaveOverlayStrategy',bases=[ast.Name(id='NativeBoundary',ctx=ast.Load())],
        keywords=[],body=[source_method('WaveOverlayStrategy',n) for n in selected],decorator_list=[])
    env.update(USDC='USDC',OrderSide=N(BUY='BUY',SELL='SELL'),TimeInForce=N(IOC='IOC',GTC='GTC'),replace=replace)
    run_ast([cls],env)
    run_ast(nodes('strategy/live_recovery.py',{'RecoverableWaveOverlayStrategy'}),env)
    s=env['RecoverableWaveOverlayStrategy'](config());cfg=s.config
    cfg.research_residual_recovery=True;cfg.research_c1_btc_cut_divisor=4
    for name in ['research_sol_risk_first','research_h4_ema','research_sol_notional_cap_multiple']:
        setattr(cfg,name,None)
    for name in ['research_sol_btc_open_only','research_sol_remaining_btc_hedge','research_v0_execution_repairs',
        'research_v0_zero_tp_netting','research_v0_selective_lifecycle_repairs','tp_fee_floor_v1']:
        setattr(cfg,name,False)
    s._candidate=Candidate();s._domain=WaveOverlayState(s._candidate)
    ep=Episode('episode',1,100,1,wave_levels=(.01,.02,.03));s._domain.episode=ep
    intent=s._domain._intent(ep,'BTC_ENTRY',1,None,quantity=20)
    s._active_c1_authorized=True;s._manage_only_preparation=False;s.recovery_confirmed=True
    s._input_readiness_preparation=True;s._recovery_health=lambda:True;s._live_input_ws_epoch=lambda:4
    s._live_account_mode='unifiedAccount';cfg.live_equity_basis='basis'
    s._live_context_current=lambda:True;s._live_increase_headroom=lambda:True
    s._live_financial_suspended=False;s._live_financial_deadline_ns=time.monotonic_ns()+9_000_000_000
    s._live_inputs_dirty=False;s._c1_fill_epoch=0
    s._deposit=DepositProtection(limit_percent=55);s._deposit.initialize(D(100),time.time_ns())
    s._deposit_storage_failed=False;cfg.deposit_initialization_allowed=lambda:False
    cfg.deposit_high_water_allowed=lambda:False;cfg.deposit_equity_reader=lambda strategy:strategy._validated_live_deposit_equity()
    s._pending_by_order={};s._order_audit={};s._sigma_by_order={};s._decision_index_by_order={}
    s._selected_entry_audits={};s._rf_sol_child=False;s._carry_physical=False;s._split_child_submit=False
    s._v3_sol_block_episode=None;s._split_parent=None;s._c1_intents={}
    s.clock=N(timestamp_ns=time.time_ns);s._latest_marks={}
    r=code.Runtime(tmp_path/'prep.sqlite','fixture-owner',10**20);r.acquire()
    r.acquire_live_account(ACCOUNT,'HYPERLIQUID',lock_root=tmp_path/'locks');s.attach_recovery_runtime(r);cfg.deposit_runtime=r
    # Exact source money type and actual require_current methods, pure source extraction.
    money_env=dict(dataclass=__import__('dataclasses').dataclass,Decimal=D)
    class IncompleteInfoReport(ValueError):pass
    money_env['IncompleteInfoReport']=IncompleteInfoReport
    run_ast(nodes('ops/hl_live_money.py',{'CheapPortfolioObservation','native_lifecycle_feasible'}),money_env)
    observation=money_env['CheapPortfolioObservation'](D(100),D(100),D(100),D(0),(),0,0,4,
        time.monotonic_ns(),time.monotonic_ns(),time.time_ns(),'event','unifiedAccount','basis')
    s._last_live_input_observation=observation
    import sys
    module=N(CheapPortfolioObservation=money_env['CheapPortfolioObservation'],native_lifecycle_feasible=money_env['native_lifecycle_feasible'])
    monkeypatch.setitem(sys.modules,'coinmaster.ops.hl_live_money',module)
    account=N(id=ACCOUNT_ID,base_currency=None,last_event=N(id='event'),
        balance_total=lambda currency:N(as_decimal=lambda:D(100),__str__=lambda:'100USDC'),
        balance_free=lambda currency:N(as_decimal=lambda:D(100),__str__=lambda:'100USDC'))
    # Stable Money-like values rather than SimpleNamespace identity representations.
    class Cash:
        def as_decimal(self):return D(100)
        def __str__(self):return '100USDC'
    account.balance_total=lambda currency:Cash();account.balance_free=lambda currency:Cash()
    instrument=N(size_increment=Q('1'),min_quantity=Q('1'),min_notional=None,make_qty=lambda value:Q(str(value)))
    s.cache=N(account_for_venue=lambda venue:account,positions_open=lambda:[],orders=lambda venue=None:[],
        instrument=lambda iid:instrument,order=lambda oid:None)
    from dataclasses import make_dataclass
    Mark=make_dataclass('VenueMark',[('price',D)])
    env['_DATACLASSES']['VenueMark']=Mark
    s._latest_marks[cfg.btc_id]=Mark(D(100))
    s._current_owned_money=lambda:(money,{},())
    money=N(equity=D(100));s._live_money_provider=lambda:money
    s._validated_live_money=lambda:money
    s._feeds_fresh=lambda ns:True;s._tier_allows_increase=lambda *args:True
    s._carry_busy=lambda:False;s._next_before_submit=lambda *args:True;s._conditional_enabled=lambda:False
    s._entries_enabled=lambda **kwargs:True;s._split_prepare=lambda i,q,*args:q
    s._split_limit=lambda *args:None;s._risk_first_sol_bind=lambda *args:None
    s._own_accepted_reduction=lambda *args:None;s._c1_bind_submission=lambda *args:None
    s._start_deposit_exit=lambda ns:None
    s._persist_deposit=lambda *args:None
    sent=[];created=[];after_record=[];terminal=[]
    def market(**kwargs):
        native=order('NEW',side='BUY',quantity='20',reduce=False)
        native.side='BUY';native.order_type='MARKET';native.time_in_force='IOC'
        native.quantity=Q('20');native.is_post_only=False;native.has_price=False;native.tags=[]
        native.ts_init=time.time_ns();created.append(native);return native
    s.order_factory=N(market=market)
    sink_env=dict(time=time,PaperRuntime=__import__('coinmaster.ops.paper',fromlist=['PaperRuntime']).PaperRuntime)
    run_ast(nodes('ops/live_recovery.py',{'LiveRecoverySubmissionSink'}),sink_env)
    sink=sink_env['LiveRecoverySubmissionSink'](r,s,frozenset({str(cfg.btc_id)}))
    def durable_sink(**request):
        answer=sink(**request)
        for mutate in after_record:mutate()
        return answer
    r.snapshot(ts_ns=time.time_ns(),positions=[],orders=[],funding_event_ids=[],native_account_total='100',strategy_restartable=True)
    cfg.submission_sink=durable_sink
    s._deny_local_entry=lambda *args:(_ for _ in ()).throw(AssertionError(('LOCAL_DENIED',args)))
    # Instrument native forward boundary, never fake DP / observation validation.
    def forward(self,native):
        assert not self._active_c1_authorized or next(row for row in r.all_submissions() if row['client_order_id']==str(native.client_order_id))['state']=='SUBMITTING'
        sent.append(native)
        if getattr(self,'fail_after_handoff',False):raise RuntimeError('HANDOFF_UNCERTAIN')
    boundary.submit_order=forward
    # Actual recovery/base terminal methods call real domain+atomic journal cleanup.
    s._c1_terminal=lambda *args:None;s._hedge_terminal=lambda *args:None
    s._v3_orders=set();s._accepted_reductions={};s._forced_close_reason=None
    s._research_protect_latch=None;s._has_confirmed_btc_remainder=lambda *args:False
    s._reduction_key=lambda intent:(intent.episode_id,intent.action,intent.level)
    s._reconcile_terminal_flat=lambda:None;s._ordinary_forced_close_active=lambda:False
    original_terminal=r.terminal_submission
    def terminal_record(client,*args,**kwargs):
        terminal.append(client);return original_terminal(client,*args,**kwargs)
    r.terminal_submission=terminal_record
    s.log=N(warning=lambda *a:None)
    s._deposit_exit_orders=set()
    yield N(s=s,r=r,intent=intent,sent=sent,created=created,account=account,after=after_record,
        terminal=terminal,money=money,observation=observation)
    r.close()

def dispatch(ctx):
    ctx.s._submit_intent(ctx.intent,100,100,None,0,ts_now=time.time_ns())

def test_actual_intent_sink_sqlite_final_DP_reader_forwards_exactly_once(prepared):
    c=prepared;dispatch(c)
    assert len(c.sent)==1 and c.r.native_revision()==1 and c.r.all_submissions()[0]['state']=='SUBMITTING'
    assert c.s._prepared_order_dispatch is None and c.s._prepared_deposit_dispatch is None
    with pytest.raises(ValueError):c.s.submit_order(c.created[0])
    assert len(c.sent)==1

@pytest.mark.parametrize('movement',['revision','account','fill','ws','high','limit','latch','control','expiry','context','headroom','wire','otherjournal','mode','policy','native','money'])
def test_intervening_movement_denies_before_native_and_terminals_only_proven_unsent(prepared,movement):
    c=prepared;s=c.s
    def mutate():
        if movement=='revision':c.r.db.execute('UPDATE paper_native_revision SET value=value+1');c.r.db.commit()
        elif movement=='account':c.account.last_event.id='other'
        elif movement=='fill':s._c1_fill_epoch+=1
        elif movement=='ws':s._live_input_ws_epoch=lambda:5
        elif movement=='high':s._deposit.high_water=D(101)
        elif movement=='limit':s._deposit.limit_percent=D(54)
        elif movement=='latch':s._deposit.latched=True
        elif movement=='control':c.r.entry_control_command('pause-new-entries','later-pause')
        elif movement=='expiry':s._live_financial_deadline_ns=time.monotonic_ns()-1
        elif movement=='context':s._live_context_current=lambda:False
        elif movement=='headroom':s._live_increase_headroom=lambda:False
        elif movement=='wire':c.created[0].quantity=Q('21')
        elif movement=='otherjournal':c.r.db.execute("UPDATE paper_intents SET episode_id='foreign'");c.r.db.commit()
        elif movement=='mode':s._live_account_mode='disabled'
        elif movement=='policy':s.config.execution_policy_hash='other-policy'
        elif movement=='native':s.cache.positions_open=lambda:[N(instrument_id=s.config.btc_id,id='foreign',is_long=True,quantity=Q('1'),strategy_id=s.id,account_id=ACCOUNT_ID)]
        elif movement=='money':s._live_money_provider=lambda:N(equity=D(100))
    c.after.append(mutate)
    with pytest.raises((ValueError,RuntimeError)):dispatch(c)
    assert c.sent==[] and c.terminal==['NEW']
    assert c.r.all_submissions()[0]['state']=='TERMINAL'

def test_after_native_handoff_exception_keeps_uncertain_no_resend(prepared):
    c=prepared;c.s.fail_after_handoff=True
    with pytest.raises(RuntimeError,match='HANDOFF_UNCERTAIN'):dispatch(c)
    assert len(c.sent)==1 and c.terminal==[] and c.r.all_submissions()[0]['state']=='SUBMITTING'
    assert c.s._prepared_deposit_dispatch is None
    with pytest.raises(ValueError):c.s.submit_order(c.created[0])
    assert len(c.sent)==1

def test_certified_equity_not_ambient_reader_authority(prepared):
    c=prepared;dispatch(c)
    proof=dict(order=c.created[0],thread=__import__('threading').get_ident())
    c.s._prepared_deposit_dispatch=(c.created[0],proof)
    with pytest.raises(ValueError,match='CALL_SCOPE'):c.s._validated_live_deposit_equity()

def test_real_final_DP_refusal_terminals_proven_local_and_no_native(prepared):
    c=prepared;s=c.s
    original=s._deposit.observe
    calls=[]
    def observe(equity,now_ns,**kwargs):
        calls.append(equity)
        if len(calls)==2:
            # Simulate actual DP's new boundary refusal during final recheck.
            s._deposit.daily_sample_missed=True
        return original(equity,now_ns,**kwargs)
    s._deposit.observe=observe
    dispatch(c)
    assert calls==[D(100),D(100)] and c.sent==[] and c.terminal==['NEW']
    assert c.r.all_submissions()[0]['state']=='TERMINAL'
    assert s._pending_by_order=={} and s._prepared_deposit_dispatch is None

def test_stop_and_restore_clear_ephemeral_proof_without_persisting_it(prepared):
    c=prepared;s=c.s
    dispatch(c)
    encoded=s.on_save()
    assert b'_prepared_order_dispatch' not in encoded['wave_overlay_live_recovery_v1']
    s._prepared_order_dispatch={'not_persisted':True}
    s._prepared_deposit_dispatch=('stale','stale')
    s.on_load(encoded)
    assert s._prepared_order_dispatch is None and s._prepared_deposit_dispatch is None

@pytest.mark.parametrize('case',['other_order','other_thread','original_deadline'])
def test_one_order_thread_and_original_deadline_bind_after_local_preparation(prepared,case):
    c=prepared;s=c.s
    def before_dispatch(*args):
        proof=s._prepared_order_dispatch
        assert proof is not None
        if case=='other_thread':proof['thread']=-1
        elif case=='original_deadline':proof['deadline']=time.monotonic_ns()-1
        else:
            other=order('OTHER',quantity='20',reduce=False)
            other.side='BUY';other.order_type='MARKET';other.time_in_force='IOC'
            other.quantity=Q('20');other.is_post_only=False;other.has_price=False;other.tags=[]
            other.ts_init=time.time_ns()
            s.submit_order(other)
    s._c1_bind_submission=before_dispatch
    with pytest.raises(ValueError):dispatch(c)
    assert c.sent==[] and c.terminal==['NEW'] and c.r.all_submissions()[0]['state']=='TERMINAL'
    assert s._prepared_order_dispatch is None

def test_default_inactive_submit_uses_unchanged_research_path(prepared):
    c=prepared;s=c.s
    s._active_c1_authorized=False
    s.config.deposit_runtime=None
    s.config.research_residual_recovery=False
    # No prepared proof is requested on the legacy path.
    native=order('LEGACY',reduce=False)
    s.submit_order(native)
    assert c.sent==[native]

def test_exception_after_journal_before_submit_clears_scope_and_terminals_unsent(prepared):
    c=prepared
    def fail_before_native(*args):raise RuntimeError('BEFORE_DISPATCH')
    c.s._c1_bind_submission=fail_before_native
    with pytest.raises(RuntimeError,match='BEFORE_DISPATCH'):dispatch(c)
    assert c.sent==[] and c.terminal==['NEW'] and c.r.all_submissions()[0]['state']=='TERMINAL'
    assert c.s._prepared_order_dispatch is None

def test_missing_native_account_exception_before_handoff_terminals_proven_unsent(prepared):
    c=prepared
    c.after.append(lambda:setattr(c.s.cache,'account_for_venue',lambda venue:None))
    with pytest.raises(AttributeError):dispatch(c)
    assert c.sent==[] and c.terminal==['NEW']
    assert c.r.all_submissions()[0]['state']=='TERMINAL'
    assert c.s._prepared_order_dispatch is None

def test_actual_two_thread_waiter_cannot_terminalize_owner_unknown_handoff(prepared):
    import threading
    c=prepared;s=c.s
    entered=threading.Event();release=threading.Event();errors=[];workers=[]
    original_lock=c.r._lock
    class BarrierLock:
        def __enter__(self):
            if threading.current_thread().name=='late-prepared-dispatch':
                entered.set()
                assert release.wait(5),'OWNER_HANDOFF_BARRIER_TIMEOUT'
            original_lock.acquire()
            return self
        def __exit__(self,*unused):original_lock.release()
    c.r._lock=BarrierLock()
    def waiter():
        try:s.submit_order(c.created[0])
        except BaseException as error:errors.append(error)
    def prepared_before_submit(*unused):
        thread=threading.Thread(target=waiter,name='late-prepared-dispatch')
        workers.append(thread);thread.start()
        assert entered.wait(5),'WAITER_DID_NOT_REACH_LOCK'
    s._c1_bind_submission=prepared_before_submit
    s.fail_after_handoff=True
    try:
        with pytest.raises(RuntimeError,match='HANDOFF_UNCERTAIN'):dispatch(c)
    finally:
        release.set()
        for thread in workers:thread.join(5)
        c.r._lock=original_lock
    assert workers and all(not thread.is_alive() for thread in workers)
    assert len(errors)==1 and isinstance(errors[0],ValueError)
    assert len(c.sent)==1 and c.terminal==[]
    assert c.r.all_submissions()[0]['state']=='SUBMITTING'
    assert s._prepared_order_dispatch is None and s._prepared_deposit_dispatch is None


def test_full_prepared_forward_with_real_LIVE_health_and_owned_standing_TP(prepared,code,tmp_path):
    from test_e4_c1_input_bridge_pure import fresh_init_fixture
    from test_e4_c1_live_health_pure import worker_source
    c=prepared;s=c.s;r=c.r
    init,template,view,now=fresh_init_fixture(code,tmp_path/'init-template')
    try:
        init.attach_recovery_runtime(r);init.cache.account_for_venue=lambda venue:c.account
        view=replace(view,equity=D(100),free_collateral=D(100),raw_usd=D(100))
        r.entry_control_command('pause-new-entries','actual-init-prepare')
        init.initialize_clean_flat_c1_epoch(view,intent='INITIALIZE_FRESH_C1_EPOCH',now_ns=now,history_anchor_ms=0)
    finally:template.close()
    r.entry_control_command('resume-new-entries','actual-init-resume')
    entry=order('ENTRY',side='BUY',quantity='10',reduce=False,closed=True)
    class Side(str):
        @property
        def name(self):return str(self)
    tp=order('TP',side='SELL',quantity='3');tp.side=Side('SELL')
    tp.is_pending_update=False;tp.has_price=True;tp.price=Q('110');tp.is_post_only=True
    tp.order_type=N(name='LIMIT');tp.time_in_force=N(name='GTC')
    pos=N(id='owned',instrument_id=s.config.btc_id,strategy_id=s.id,account_id=ACCOUNT_ID,
        is_long=True,quantity=Q('10'),events=[])
    standing=Intent('standing','episode','BTC_REDUCE',1,-1,quantity=3,limit_price=110,reason='BTC_TP1')
    s._pending_by_order['TP']=standing
    r.record_submission(client_order_id='ENTRY',intent_id='entry',episode_id='episode',action='BTC_ENTRY',
        instrument_id=str(s.config.btc_id),quantity='10',reduce_only=False)
    r.terminal_submission('ENTRY')
    r.record_submission(client_order_id='TP',intent_id='standing',episode_id='episode',action='BTC_REDUCE',
        instrument_id=str(s.config.btc_id),quantity='3',reduce_only=True,
        order_shape=dict(side='SELL',kind='LIMIT',tif='GTC',post_only=True,price='110'))
    r.db.execute("UPDATE paper_intents SET state='ACKED' WHERE client_order_id='TP'");r.db.commit()
    s.cache.orders=lambda venue=None:[entry,tp];s.cache.positions_open=lambda:[pos]
    s._capital_basis_verified=True;s.deposit_projection=lambda:dict(state='ARMED')
    s.establish_owned_effect_chain(account_id=ACCOUNT_ID,ws_epoch=4,
        policy_sha256=code.env['recovery_policy_hash'](s.config,s._candidate))
    revision=r.native_revision()
    money=replace(view,end_ms=time.time_ns()//1_000_000,native_revision=revision,
        position_sizes=(('BTC',D(10)),))
    s._live_money_provider=lambda:money
    del s.__dict__['_current_owned_money'];del s.__dict__['_validated_live_money']
    s._last_live_input_observation=replace(s._last_live_input_observation,
        position_sizes=(('BTC',D(10)),),native_revision=revision)
    node=object.__new__(worker_source());node.state=r;node.strategy=s;node.active_c1=True
    node.input_readiness=False;node._refresh_warmup_readiness=lambda:None
    node.gate=N(attachable=True);node.node=N(is_running=lambda:True)
    node.feed=N(status=lambda now:dict(BTC=dict(state='READY'),SOL=dict(state='READY')))
    r.bind_live_health(node._live_health_current);s._entries_enabled=node._entries_enabled
    assert node._entries_enabled()
    post_health=[]
    c.after.append(lambda:post_health.append(r.health(time.time_ns()).safe_for_increase))
    dispatch(c)
    assert len(c.sent)==1 and post_health==[False] and r.native_revision()==revision+1
    assert s._prepared_order_dispatch is None and s._prepared_deposit_dispatch is None
    assert next(row for row in r.all_submissions() if row['client_order_id']=='TP')['state']=='ACKED'
    with pytest.raises(ValueError):s.submit_order(c.created[0])
    assert len(c.sent)==1
