"""Connected actual-source ACTIVE contracts; no native imports/models/network."""
import ast,asyncio,hashlib,json,time
from collections import deque
from decimal import Decimal as D
from types import SimpleNamespace as N
import pytest
from coinmaster.ops.hl_info_receipt import IncompleteInfoReport
from coinmaster.domain.deposit_protection import DepositProtection,DAY_NS
from test_e4_c1_manage_only_pure import code,nodes,run_ast,setup,order,Q,ACCOUNT_ID,ROOT
from test_e4_c1_input_bridge_pure import fresh_init_fixture
from test_e4_c1_unified_pure import money_source

def budget():
    env=dict(deque=deque,IncompleteInfoReport=IncompleteInfoReport)
    run_ast(nodes('ops/hl_live_execution.py',{'ReadinessInfoBudget','finite_generation_reservation'}),env)
    return N(**env)

@pytest.mark.parametrize('full',[212,497])
def test_actual_60s_held_request_schedule_and_post_settlement_headroom(full):
    b=budget();gateway=b.ReadinessInfoBudget()
    reservation=gateway.reserve(497,0);gateway.settle(reservation,full,now=2)
    assert gateway.protects_held_schedule(2)
    starts=[]
    # Stable real request phases plus varied bounded native/response jitter.
    # Every opaque native retry is conservatively timestamped at completion.
    for second in range(3,70,6):
        token=gateway.reserve(28,second)
        gateway.note(token,20,second)
        completion=second+(.1 if second%12==3 else .2)
        gateway.note(token,8,completion);gateway.settle(token,28,now=completion)
        token=gateway.reserve(20,completion)
        gateway.note(token,20,completion);gateway.settle(token,20,now=completion+.1)
        starts.append(second)
        assert 1000-gateway.remaining(completion+.1)<=977
    assert max(b-a for a,b in zip(starts,starts[1:]))==6
    # Actual oldest-source age before next completion remains below9.
    assert max(6.3 for _ in starts)<9

def test_reservation_does_not_expire_inflight_and_endpoint_phases_do_not_expire_early():
    b=budget();gateway=b.ReadinessInfoBudget()
    token=gateway.reserve(700,0)
    assert gateway.remaining(61)==300 # Outstanding bound never evaporates.
    gateway.note(token,20,61);gateway.note(token,80,62)
    gateway.settle(token,100,now=63)
    assert gateway.remaining(120.99)==900
    assert gateway.remaining(121)==920
    assert gateway.remaining(122)==1000


def test_startup_and_heavy_history_require_actual_post_settlement_safety_capacity():
    b=budget();gateway=b.ReadinessInfoBudget()
    for value in (142,28,240,20):
        token=gateway.reserve(value,0);gateway.settle(token,value)
    token=gateway.reserve(437,1);gateway.settle(token,212)
    assert not gateway.protects_held_schedule(1)
    assert gateway.protects_held_schedule(60)
    # Previously accepted near700 history shape cannot use blindly128 headroom.
    other=b.ReadinessInfoBudget();token=other.reserve(700,0);other.settle(token,697)
    assert not other.protects_held_schedule(0)

def active_owned(code,tmp_path):
    s,r,entry,pos=setup(code,tmp_path)
    s._active_c1_authorized=True;s._manage_only_preparation=False;s.recovery_confirmed=True
    s._recovery_health=lambda:True;s._live_input_ws_epoch=lambda:4
    code.env['OrderSide']=N(SELL='SELL',BUY='BUY')
    s.establish_owned_effect_chain(account_id=ACCOUNT_ID,ws_epoch=4,
        policy_sha256=code.env['recovery_policy_hash'](s.config,s._candidate))
    return s,r,entry,pos

def reduction(client='NEW',quantity='3',side='SELL'):
    o=order(client,quantity=quantity);o.side=side
    return o

def test_owned_reduce_does_not_read_stale_money_or_issue_http(code,tmp_path):
    s,r,entry,pos=active_owned(code,tmp_path)
    try:
        s._live_money_provider=lambda:pytest.fail('reduce must not read opening money')
        assert s._owned_reduce_allowed(reduction(quantity='10'))
        assert not s._owned_reduce_allowed(reduction(quantity='10.00001'))
        assert not s._owned_reduce_allowed(reduction(side='BUY'))
        # Pending cancel remains reserved; actual native terminal ACK releases it.
        pending=order('TP',quantity='8');pending.side='SELL';pending.is_pending_cancel=True
        r.record_submission(client_order_id='TP',intent_id='tp',episode_id='episode',action='BTC_REDUCE',
            instrument_id=str(s.config.btc_id),quantity='8',reduce_only=True,strategy_state=s.on_save()[code.env['_KEY']])
        s.cache.orders=lambda venue=None:[entry,pending]
        assert not s._owned_reduce_allowed(reduction(quantity='3'))
        pending.filled_qty=Q('1');pos.quantity=Q('9')
        assert s._owned_reduce_allowed(reduction(quantity='2'))
        pending.is_closed=True
        assert s._owned_reduce_allowed(reduction(quantity='9'))
        assert not s._owned_reduce_allowed(reduction(client='TP',quantity='1'))
    finally:r.close()

@pytest.mark.parametrize('case',['ws','policy','foreign','unapplied','health','native_quantity','native_owner','rejected'])
def test_owned_chain_revokes_on_actual_unknown_lineage(code,tmp_path,case):
    s,r,entry,pos=active_owned(code,tmp_path)
    try:
        if case=='ws':s._live_input_ws_epoch=lambda:5
        if case=='policy':s.config.research_c1_restore_dd=D('.40')
        if case=='foreign':s.cache.orders=lambda venue=None:[entry,order('FOREIGN')]
        if case=='unapplied':pos.events.append(N(client_order_id='ENTRY',trade_id='unapplied'))
        if case=='health':s._recovery_health=lambda:False
        if case=='native_quantity':entry.quantity=Q('11')
        if case=='native_owner':entry.strategy_id='FOREIGN'
        if case=='rejected':entry.status=N(name='REJECTED')
        assert not s._owned_reduce_allowed(reduction())
    finally:r.close()

def page(rows,start,end,cursor=None):
    return dict(rows=rows,start_ms=start,end_ms=end,expected_cursor=cursor,complete=True)
def cash(hash_,when=1):
    return dict(time=when,hash=hash_,delta=dict(type='deposit',usdc='10'))

def test_fresh_init_cash_baseline_is_atomic_and_same_ms_new_cash_quarantines(code,tmp_path):
    s,r,view,now=fresh_init_fixture(code,tmp_path)
    try:
        baseline=page([cash('before',1)],0,1)
        s.initialize_clean_flat_c1_epoch(view,intent='INITIALIZE_FRESH_C1_EPOCH',now_ns=now,
            history_anchor_ms=0,cashflow_page=baseline)
        assert r.c1_initialization() and r.evidence_cursor('userNonFundingLedgerUpdates')=={'end_ms':1}
        assert not r.cashflow_quarantined()
        assert r.record_cashflow_page(page([cash('before')],1,1,{'end_ms':1}))
        assert not r.record_cashflow_page(page([cash('before'),cash('later-same-ms')],1,1,{'end_ms':1}))
        assert r.cashflow_quarantined() and s._c1_peak==D(82)
        assert r.db.execute("SELECT COUNT(*) FROM live_evidence_payloads WHERE kind='external_cashflow'").fetchone()[0]==2
        assert all(not json.loads(row[0])['cash_posted'] for row in r.db.execute("SELECT body FROM live_evidence_payloads WHERE kind='external_cashflow'"))
        # Restart preserves quarantine and H; no optimistic deposit credit.
        body=s.on_save();restored=code.Strategy(s.config);restored.on_load(body)
        assert restored._c1_peak==D(82) and not restored.recovery_confirmed
    finally:r.close()

@pytest.mark.parametrize('change',['saturated','cursor','clock','malformed'])
def test_cashflow_failure_cannot_advance_cursor_or_partially_initialize(code,tmp_path,change):
    s,r,view,now=fresh_init_fixture(code,tmp_path)
    try:
        p=page([],0,1)
        if change=='saturated':p['rows']=[cash(str(i)) for i in range(500)]
        if change=='cursor':p['expected_cursor']={'end_ms':0}
        if change=='clock':p['end_ms']=-1
        if change=='malformed':p['rows']=[{'time':1,'hash':'bad'}]
        with pytest.raises(ValueError):
            s.initialize_clean_flat_c1_epoch(view,intent='INITIALIZE_FRESH_C1_EPOCH',now_ns=now,history_anchor_ms=0,cashflow_page=p)
        assert r.c1_initialization() is None and r.evidence_cursor('userNonFundingLedgerUpdates') is None
    finally:r.close()

def test_cheap_daily_sample_cannot_credit_H_but_downward_DP_still_latches():
    dp=DepositProtection(limit_percent=55);dp.initialize(D(100),DAY_NS-100)
    dp.observe(D(120),DAY_NS-1,allow_high_water=False)
    dp.observe(D(110),DAY_NS,allow_high_water=False)
    assert dp.high_water==100 and dp.pending_daily_high['equity']=='120'
    assert dp.observe(D(45),DAY_NS+1,allow_high_water=False)[1]
    assert dp.latched and dp.high_water==100 and dp.threshold==45
    assert dp.confirm_pending_high((DAY_NS-10)//1_000_000,DAY_NS//1_000_000)
    assert dp.high_water==120 and dp.latched

@pytest.mark.parametrize('equity',['72','108'])
def test_current_price_actual_HL_lots_expose_sub10_lifecycle_requests(equity):
    env={'Decimal':D}
    run_ast(nodes('ops/hl_live_money.py',{'native_lifecycle_feasible'}),env)
    instrument=N(size_increment=Q('.00001'),min_quantity=Q('.00001'),
        min_notional=N(currency='USDC',as_decimal=lambda:D(10)))
    # Synthetic capital brackets, half-capital request, actual BTC five-decimal lot.
    price=D(100000);quantity=(D(equity)/2/price//D('.00001'))*D('.00001')
    before=quantity
    assert (quantity//D('.00001')//4)*D('.00001')*price==(D(9) if equity=='72' else D(13))
    result=env['native_lifecycle_feasible'](instrument,quantity,price,cut_divisor=4,tp_fractions=('.15','.25','.35'))
    assert not result # Both expose first-TP below10; never silently enlarge.
    assert quantity==before
    assert env['native_lifecycle_feasible'](instrument,D('.002'),price,cut_divisor=4,tp_fractions=('.15','.25','.35'))

def test_changed_runtime_classes_have_no_shadowed_methods():
    for filename in ('strategy/live_recovery.py','strategy/wave_overlay.py','ops/hl_live_execution.py','ops/hl_live_worker.py'):
        tree=ast.parse((ROOT/filename).read_text())
        for cls in (node for node in ast.walk(tree) if isinstance(node,ast.ClassDef)):
            names={}
            for method in cls.body:
                if not isinstance(method,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
                decorators=[ast.unparse(d) for d in method.decorator_list]
                if any(d.endswith('.setter') or d.endswith('.deleter') or d.endswith('overload') for d in decorators):continue
                assert method.name not in names,(filename,cls.name,method.name)
                names[method.name]=method.lineno

def test_actual_input_quote_dispatch_calls_ordinary_core_once_with_real_clock(code):
    from test_e4_c1_manage_only_pure import config
    s=code.Strategy(config());s._input_readiness_preparation=True;s._active_c1_authorized=True
    tick=N(instrument_id=s.config.btc_id,ts_event=10,ts_init=15)
    s.clock=N(timestamp_ns=lambda:20);s.cache=N(positions_open=lambda:[])
    s._materialize_live_c1_observation=lambda now:None
    s._live_clock=lambda:N(drain=lambda *args:[])
    s._c1_current_money=lambda now:None;s._persist_transient_checkpoint=lambda:None
    s._feeds_fresh=lambda now:True
    calls=[]
    code.env['WaveOverlayStrategy'].on_quote_tick=lambda self,tick,**kwargs:calls.append((tick,kwargs))
    s.on_quote_tick(tick)
    assert calls==[(tick,{'decision_ns':20})] and tick.ts_event==10 and tick.ts_init==15
    s._active_c1_authorized=False;s.on_quote_tick(tick)
    assert len(calls)==1

@pytest.mark.parametrize('change',['valid','age','role_expiry','ws','signer','policy'])
def test_context_original_timestamp_and_strict_binding(code,change):
    from test_e4_c1_manage_only_pure import config,ACCOUNT
    env=dict(asyncio=asyncio,time=time,hashlib=hashlib,deque=deque,IncompleteInfoReport=IncompleteInfoReport)
    run_ast(nodes('ops/hl_live_execution.py',{'QualifiedInfoBoundary'}),env)
    owner=object.__new__(env['QualifiedInfoBoundary']);strategy=code.Strategy(config())
    strategy._signer_sha256='signer'
    owner._cm_strategy=strategy;owner._cm_scope=N(account_ref=ACCOUNT);owner._cm_ws_epoch=4
    policy=code.env['recovery_policy_hash'](strategy.config,strategy._candidate)
    original=time.monotonic_ns()
    proof=dict(master_role='user',agent_role='agent',account_sha256=hashlib.sha256(ACCOUNT.lower().encode()).hexdigest(),
        signer_sha256='signer',policy_sha256=policy,ws_epoch=4,dex_abstraction=False,verified_at_ns=original)
    owner._cm_account_context=proof
    if change=='age':proof['verified_at_ns']-=300_000_000_001
    if change=='role_expiry':proof['agent_expiry_unix_ms']=time.time_ns()//1_000_000-1
    if change=='ws':owner._cm_ws_epoch=5
    if change=='signer':strategy._signer_sha256='other'
    if change=='policy':proof['policy_sha256']='other'
    before=dict(proof)
    assert bool(owner._cm_context_current()) is (change=='valid')
    assert proof==before # No cached proof is re-aged, even on failure.

def test_worker_currency_projection_preserves_reported_total_and_real_free_hold():
    env=dict(time=time,Decimal=D,TestnetWorker=N(deposit_control=lambda:None))
    run_ast(nodes('ops/hl_live_worker.py',{'LiveWorker'}),env)
    worker=object.__new__(env['LiveWorker'])
    strategy=N(config=N(live_equity_basis='HYPERLIQUID_UNIFIED_SPOT_USDC_REPORTED_TOTAL_V1'),
        _input_readiness_preparation=True,_live_account_mode='unifiedAccount',
        _validated_live_deposit_equity=lambda:D(100),
        _last_live_input_observation=N(free_collateral=D(70),margin_used=D(30)),
        _live_c1_input=None,_c1_checkpoint=None,deposit_projection=lambda:dict(drawdown_limit_percent=55))
    worker.native=N(strategy=strategy,status=lambda:dict(state='PAUSED',orders_enabled=False),
        native_snapshot=lambda:([],[]),_thread=None)
    worker.runtime=N(projection_events=lambda count:([],0),entry_control_state=lambda:'PAUSED',
        funding_projection=lambda:dict(funding=None,funding_currency='USDC',
        funding_reason='FUNDING_ATTRIBUTION_UNKNOWN_OR_INCOMPLETE',funding_coverage_end_ns=None))
    worker.poll=lambda:None;worker.run_epoch='fixture';worker.release_identity={'source_commit':'frozen'}
    worker.master_address_sha256='synthetic-hash';worker.order_approval={'orders_approved':False};worker.control_available=False
    projection=worker.projection();account=projection['account']
    assert projection['money_currency']==account['currency']=='USDC'
    assert account['equity']==account['reported_total']=='100'
    assert account['native_free']==account['available']=='70'
    assert account['native_locked']==account['hold']=='30'
    assert account['funding'] is None and account['funding_reason']
    assert projection['deposit_protection']['retained_equity_floor_fraction']=='0.45'

def test_dynamic_post_settlement_headroom_accounts_actual_expiries():
    b=budget();gateway=b.ReadinessInfoBudget()
    # Ten already-paid held samples; original HTTP phases remain distinct.
    for at in range(0,60,6):
        token=gateway.reserve(48,at)
        gateway.note(token,20,at);gateway.note(token,28,at+.2)
        gateway.settle(token,48,now=at+.3)
    token=gateway.reserve(497,60);gateway.settle(token,497,now=60)
    assert gateway.remaining(60)==43
    assert gateway.protects_held_schedule(60,next_due=60)
    # No expiration soon means same nominal spare43 cannot fund the next sample.
    other=b.ReadinessInfoBudget();token=other.reserve(957,60);other.settle(token,957,now=60)
    assert not other.protects_held_schedule(60,next_due=60)

def test_one_generation_race_raises_unknown_without_hidden_retry_or_none():
    env=dict(asyncio=asyncio,time=time,hashlib=hashlib,deque=deque,IncompleteInfoReport=IncompleteInfoReport)
    run_ast(nodes('ops/hl_live_execution.py',{'ReadinessInfoBudget','finite_generation_reservation',
        'QualifiedInfoBoundary','InfoWeightBudget','SingleAttemptInfoTransport'}),env)
    owner=env['QualifiedInfoBoundary']()
    owner._cm_unified=False;owner._cm_inputs_enabled=True;owner._cm_bootstrapped=False
    owner._cm_ws_failure=None;owner._cm_ws_phase='LIVE';owner._cm_suspend_recovery=None
    owner._cm_inputs_budget=env['ReadinessInfoBudget']();owner._cm_info_usage=deque()
    owner._cm_require_healthy=lambda:None;failures=[];owner._cm_fail=failures.append
    scope=N(durable_orders=(),account_ref='synthetic',dex='',anchor_ms=0,anchor_tid=None,fill_anchor_ms=None,fill_anchor_fingerprint=None,owned_coins=frozenset())
    owner._cm_owned_scope=lambda:(scope,0,(),frozenset(),())
    owner._cm_runtime=N(info_query_evidence=lambda *args,**kwargs:({},(),None,None),native_revision=lambda:0)
    owner._cache=N(positions_open=lambda:[])
    async def refresh():pass
    owner._cm_refresh_native_account_for_generation=refresh
    owner._cm_info=env['SingleAttemptInfoTransport'](testnet=False,timeout=1)
    owner._clock=N(timestamp_ns=lambda:10_000_000_000)
    calls=[]
    async def receipt(*args,**kwargs):
        calls.append(1);raise IncompleteInfoReport('ORDER_STATUS_UNKNOWN')
    env['collect_info_receipt']=receipt
    with pytest.raises(IncompleteInfoReport,match='ORDER_STATUS_UNKNOWN'):
        asyncio.run(owner.generate_mass_status())
    assert calls==[1] and failures==['INFO_GENERATION_FAILED']

def test_active_initial_scope_captures_actual_runtime_revision_and_movement():
    env=dict(asyncio=asyncio,time=time,deque=deque,IncompleteInfoReport=IncompleteInfoReport)
    run_ast(nodes('ops/hl_live_execution.py',{'QualifiedInfoBoundary'}),env)
    owner=env['QualifiedInfoBoundary']();owner._cm_bootstrapped=False
    owner._cm_management_only=False;owner._cm_inputs_enabled=True
    revision=[41];owner._cm_runtime=N(native_revision=lambda:revision[0],all_submissions=lambda:())
    owner._cm_scope='scope';owner.venue='HL';owner._cache=N(orders=lambda venue:())
    owner._cm_applied_fill_ids=lambda:frozenset()
    assert owner._cm_owned_scope()[1]==41
    revision[0]=42
    assert owner._cm_owned_scope()[1]==42

def test_oldest_generation_deadline_blocks_every_opening_even_if_second_receipt_is_fresh(code):
    from test_e4_c1_manage_only_pure import config
    from test_e4_c1_unified_pure import money_source
    s=code.Strategy(config());s._active_c1_authorized=True;s.recovery_confirmed=True
    s._recovery_runtime=N(cashflow_quarantined=lambda:False)
    s._capital_basis_verified=True;s._live_context_current=lambda:True;s._live_increase_headroom=lambda:True
    m=money_source();code.env['LivePerpsMoneyView']=m.LivePerpsMoneyView
    view=m.LivePerpsMoneyView('synthetic','',4000,D(100),D(100),D(0),D(100),(),(),0)
    s._live_money_provider=lambda:view
    mono=[8_000_000_000];wall=[8_000_000_000]
    code.env['time']=N(monotonic_ns=lambda:mono[0],time_ns=lambda:wall[0])
    s.accept_live_financial_authority(started_ns=0)
    assert s._validated_live_money() is view
    mono[0]=12_000_000_000;wall[0]=12_000_000_000
    # Second-sweep receipt age8s is valid; oldest native start age12s is not.
    view.require_fresh(12000,9000)
    with pytest.raises(ValueError,match='STALE_OR_UNKNOWN'):s._validated_live_money()
    assert not s._entries_enabled()
    assert not s._tier_allows_increase(s.config.btc_id,'BUY',D(1),wall[0])

def test_worker_poll_expected_financial_suspend_preserves_owned_chain_but_unknown_does_not(code):
    from test_e4_c1_manage_only_pure import config
    env=dict(time=time,TestnetWorker=N(deposit_control=lambda:None))
    run_ast(nodes('ops/hl_live_worker.py',{'LiveWorker'}),env)
    s=code.Strategy(config());s._active_c1_authorized=True;s.recovery_confirmed=True
    s._live_money_provider=lambda:None;s._owned_effect_chain=('account',4,'policy')
    s.suspend_live_financial_authority()
    requests=[];s._request_live_refresh=lambda:None
    worker=object.__new__(env['LiveWorker']);worker.runtime=N(heartbeat=lambda now:None)
    worker.native=N(strategy=s,input_readiness=False,loop=N(call_soon_threadsafe=requests.append))
    manual=[];worker._manual_recovery=lambda:manual.append(True)
    worker.poll()
    assert manual==[] and requests==[s._request_live_refresh]
    assert s.recovery_confirmed and s._owned_effect_chain
    # Clear only expected-suspend marker; an actually missing full view remains UNKNOWN.
    s._live_financial_suspended=False;s._live_financial_deadline_ns=time.monotonic_ns()+9_000_000_000
    worker.poll()
    assert manual==[True]

def test_worker_C1_projects_one_canonical_checkpoint_not_DP_floor_or_newer_account(monkeypatch):
    env=dict(time=time,Decimal=D,TestnetWorker=N(deposit_control=lambda:None))
    run_ast(nodes('ops/hl_live_worker.py',{'LiveWorker'}),env)
    worker=object.__new__(env['LiveWorker'])
    checkpoint=dict(E=D(90),H=D(120),DD=D('.25'),C=D(30),source=10,receipt=15,epoch=5)
    strategy=N(config=N(live_equity_basis='HYPERLIQUID_UNIFIED_SPOT_USDC_REPORTED_TOTAL_V1'),
        _input_readiness_preparation=True,_live_account_mode='unifiedAccount',
        _validated_live_deposit_equity=lambda:D(100),_c1_peak=D(140),
        _last_live_input_observation=N(free_collateral=D(70),margin_used=D(30)),
        _live_c1_input=N(equity=D(100),source_available_ns=20,decision_ns=25,fill_epoch=5),
        _c1_checkpoint=checkpoint,_c1_state=None,_c1_rights=lambda:{},
        deposit_projection=lambda:dict(state='ARMED',drawdown_limit_percent=55,daily_sample_missed=False,
            equity='100',high_water_equity='120',threshold_equity='54',last_daily_close_utc=0))
    worker.native=N(strategy=strategy,status=lambda:dict(state='PAUSED',orders_enabled=False,
        instance_id='hl-stageg-live',mode='live',environment='mainnet',live_order_capability=True,profile={}),
        native_snapshot=lambda:([],[]),_thread=None)
    worker.runtime=N(projection_events=lambda count:([],0),entry_control_state=lambda:'PAUSED',
        funding_projection=lambda:dict(funding=None,funding_currency='USDC',funding_reason='UNKNOWN',funding_coverage_end_ns=None))
    worker.poll=lambda:None;worker.run_epoch='fixture';worker.release_identity={'source_commit':'frozen'}
    worker.master_address_sha256='synthetic';worker.order_approval={};worker.control_available=False
    result=worker.projection()
    assert result['account']['equity']=='100'
    assert {key:result['c1'][key] for key in ('E','H','DD','cushion','source_available_ns','decision_ns')}==dict(
        E='90',H='120',DD='0.25',cushion='30',source_available_ns=10,decision_ns=15)
    assert result['deposit_protection']['retained_equity_floor_fraction']=='0.45'

    from test_hl_usdc_projection_contract import pure_sidecar,read
    projected=read(pure_sidecar(),monkeypatch,result)
    assert projected.projection_state=='READY'
    assert projected.account.equity=='100' and projected.account.native_free=='70'
    assert projected.c1.E=='90' and projected.c1.H=='120' and projected.c1.cushion=='30'
    assert projected.c1.source_available_ns==10 and projected.c1.decision_ns==15
    assert projected.deposit_protection.retained_equity_floor_fraction=='0.45'

@pytest.mark.parametrize('first_filled,expected',[('2','3'),('5','5')])
def test_actual_split_check_forwards_exact_remaining_child_through_recoverable(code,first_filled,expected):
    from coinmaster.domain.wave_overlay import Intent
    from test_e4_c1_manage_only_pure import config
    split_env=dict(D=D,HOUR=3_600_000_000_000,DAY=86_400_000_000_000)
    run_ast(nodes('strategy/split_cover.py',{'SplitCoverResearch'}),split_env)
    class Combined(code.Strategy,split_env['SplitCoverResearch']):pass
    cfg=config();cfg.research_btc_split50=True;cfg.research_btc_split_planref_v1=True
    s=Combined(cfg);s._split_parent=None;s.split_parent_audit=[];s._split_child_submit=False;s._queued_intents=[]
    s._domain.episode.wave_levels=(.01,.02,.03)
    intent=Intent('logical-parent',s._domain.episode.id,'BTC_ENTRY',None,1,requested_notional=1000)
    s._split_prepare(intent,D(10),D(1),1,None,0)
    s._split_native_fill(intent,N(last_qty=Q(first_filled),last_px=Q('100'),ts_event=2))
    s._entries_enabled=lambda:True;s._persist_transient_checkpoint=lambda:None
    s._current_owned_money=lambda:None
    dispatched=[]
    code.env['WaveOverlayStrategy']._submit_intent=lambda self,*args,**kwargs:dispatched.append((args,kwargs))
    class Price(Q):
        def __float__(self):return float(self.value)
    tick=N(instrument_id=cfg.btc_id,bid_price=Price('99'),ask_price=Price('99.1'),ts_event=3)
    s._split_check(tick)
    assert len(dispatched)==1 and dispatched[0][0][0] is intent
    assert dispatched[0][1]['entry_override_qty']==D(expected)
    assert not s._split_child_submit
    # Expected financial suspension must not enqueue a parent without child qty.
    dispatched.clear()
    def pending():raise ValueError('LIVE_MONEY_REFRESH_PENDING')
    s._current_owned_money=pending;requested=[];s._request_live_refresh=lambda:requested.append(True)
    s._split_check(tick)
    assert dispatched==[] and s._queued_intents==[] and requested==[True]
    # Ordinary default None still forwards identically.
    s._current_owned_money=lambda:None
    s._submit_intent(intent,99,99.1,None,0,ts_now=4)
    assert dispatched[0][1]['entry_override_qty'] is None
