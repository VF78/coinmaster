"""Actual source/SQLite tests, with no native imports or constructors."""
from decimal import Decimal as D
from types import SimpleNamespace as N
import json
import pytest
from coinmaster.domain.deposit_protection import DepositProtection, DAY_NS
from coinmaster.ops.hl_live_profile import require_profile_deposit_parity
from test_e4_c1_manage_only_pure import nodes,run_ast,code,setup


def clock():
    env={}
    run_ast(nodes('ops/hl_live_worker.py',{'ClosedTradeClock'}),env)
    return env['ClosedTradeClock']({})


def test_requested_retained45_means_drawdown55_and_preserves_daily_anchor_latch():
    state=DepositProtection(limit_percent=55)
    state.initialize(D(100),DAY_NS+1)
    state.observe(D(120),2*DAY_NS-1)
    state.observe(D(119),2*DAY_NS+1)
    assert state.high_water==D(120) and state.threshold==D(54)
    assert state.observe(D('54.01'),2*DAY_NS+2)==(False,False)
    assert state.observe(D(54),2*DAY_NS+3)==(True,True)
    before=state.durable()
    profile={'deposit_protection_percent':55,'retained_equity_floor_fraction':'0.45'}
    assert require_profile_deposit_parity(profile,state.projection())
    assert state.durable()==before
    restored=DepositProtection.from_durable(before)
    assert restored.latched and restored.high_water==D(120) and restored.threshold==D(54)


@pytest.mark.parametrize('value',[50,45,None,True,55.0])
def test_profile_durable_limit_mismatch_blocks_without_mutation(value):
    projection={'drawdown_limit_percent':value,'high_water_equity':'120','trigger':{'reason':'retained'}}
    before=json.dumps(projection,sort_keys=True)
    with pytest.raises(RuntimeError,match='LIVE_DEPOSIT_PROFILE_STATE_MISMATCH'):
        require_profile_deposit_parity({'deposit_protection_percent':55,'retained_equity_floor_fraction':'0.45'},projection)
    assert json.dumps(projection,sort_keys=True)==before


def feed_h4(c,instrument='BTC',end=None,available=None):
    end=end or c.H4
    for close in range(end-c.H4+c.MINUTE,end+c.MINUTE,c.MINUTE):
        c.minute(instrument,close,close,(available or end)+1,(D(100),D(110),D(90),D(105)))


def test_closed_trade_h4_requires240_contiguous_and_actual_later_availability():
    c=clock();feed_h4(c)
    assert c.drain(c.H4+1,('BTC','SOL'))==[]
    bars=c.drain(c.H4+2,('BTC','SOL'))
    assert len(bars)==1 and bars[0]['available_ns']==c.H4+1 and bars[0]['OHLC']==(D(100),D(110),D(90),D(105))
    assert c.drain(c.H4+3,('BTC','SOL'))==[]
    with pytest.raises(ValueError,match='CONFLICT'):
        c.minute('BTC',c.MINUTE,c.MINUTE,c.H4+4,(D(101),D(110),D(90),D(105)))


def test_midnight_h4_waits_both_genuine_d1_and_never_replays_prior_quote():
    c=clock();feed_h4(c,end=c.DAY,available=c.DAY+20)
    assert c.drain(c.DAY+30,('BTC','SOL'))==[]
    c.daily('BTC',c.DAY,c.DAY+40)
    assert c.drain(c.DAY+50,('BTC','SOL'))==[]
    c.daily('SOL',c.DAY,c.DAY+60)
    assert c.drain(c.DAY+60,('BTC','SOL'))==[]
    bars=c.drain(c.DAY+61,('BTC','SOL'))
    assert bars[0]['available_ns']==c.DAY+60


def test_clock_checkpoint_json_roundtrip_uses_actual_recovery_codec(code):
    c=clock();feed_h4(c)
    encoded=code.env['_encode'](c.state)
    restored=code.env['_decode'](json.loads(json.dumps(encoded)))
    assert restored==c.state


def test_terminal_cache_only_exempts_unchanged_native_and_all_fill_fingerprints(code,tmp_path):
    s,r,entry,position=setup(code,tmp_path)
    fill={'tid':10,'time':1,'oid':100}
    proof={'client_id':'ENTRY','native_fingerprint':['exact'],'journal_fills':r._journal_order_fills('ENTRY'),
           'status':{'status':'order','order':{'status':'filled'}}}
    receipt=N(start_ms=1,anchor_tid=10,end_ms=2,fills=(fill,))
    r.save_verified_info_checkpoint(receipt,{'cloid':proof},r.native_revision())
    cached,all_fills,anchor,tid=r.info_query_evidence({'ENTRY':['exact']},frozenset({'10'}))
    assert cached=={'cloid':proof['status']} and all_fills==(fill,) and (anchor,tid)==(1,10)
    assert r.info_query_evidence({'ENTRY':['revised']},frozenset({'10'}))[0]=={}
    r.db.execute("UPDATE paper_native_fill_details SET price='101' WHERE trade_id='10'");r.db.commit()
    assert r.info_query_evidence({'ENTRY':['exact']},frozenset({'10'}))[0]=={}
    assert len(r.all_submissions())==1 and r.applied_fill_ids()==frozenset({'10'})
    r.close()


def test_sol_true_trade_minutes_produce_1h_and4h_and_gap_is_atomic():
    c=clock();feed_h4(c,'SOL')
    bars=c.drain(c.H4+2,('BTC','SOL'))
    assert [(b['hours'],b['close_ns']) for b in bars]==[(1,60*c.MINUTE),(1,120*c.MINUTE),(1,180*c.MINUTE),(1,c.H4),(4,c.H4)]
    before=json.dumps(str(c.state))
    feed_h4(c,'SOL',end=3*c.H4,available=3*c.H4+1)
    pending=c.state['pending_h4'][:];last=dict(c.state['last_closed'])
    with pytest.raises(ValueError,match='COVERAGE_GAP'):c.drain(3*c.H4+3,('BTC','SOL'))
    assert c.state['last_closed']==last and c.state['pending_h4']==pending


def budget_code():
    from collections import deque
    from coinmaster.ops.hl_info_receipt import IncompleteInfoReport
    env={'deque':deque,'IncompleteInfoReport':IncompleteInfoReport}
    run_ast(nodes('ops/hl_live_execution.py',{'ReadinessInfoBudget','finite_generation_reservation','InfoWeightBudget'}),env)
    return N(**env)


def test_finite600_generation_actual_cost_refund_rolling1000_earliest_wake():
    b=budget_code();state=b.ReadinessInfoBudget()
    assert b.finite_generation_reservation(0)==540 and b.finite_generation_reservation(15)==600
    with pytest.raises(ValueError,match='SCOPE'):b.finite_generation_reservation(16)
    reservation=state.reserve(600,0)
    with pytest.raises(ValueError,match='RATE_BUDGET'):state.reserve(540,1)
    assert state.next_affordable==60
    state.settle(reservation,340)
    second=state.reserve(600,2);state.settle(second,340)
    with pytest.raises(ValueError,match='RATE_BUDGET'):state.reserve(540,3)
    assert state.next_affordable==60
    state.reserve(540,60)
    with pytest.raises(ValueError,match='SETTLEMENT'):state.settle(second,0)


def test_cost_overflow_records_actual_spend_and_unknown_request_denies_before_http():
    import asyncio
    b=budget_code();state=b.ReadinessInfoBudget();reservation=state.reserve(540,0)
    with pytest.raises(ValueError,match='COST_OVERFLOW'):state.settle(reservation,601)
    assert reservation[1]==601 and reservation[2]
    calls=[]
    async def transport(body):calls.append(body);return []
    weighted=b.InfoWeightBudget(transport,600)
    with pytest.raises(ValueError,match='UNSUPPORTED'):asyncio.run(weighted({'type':'unknown'}))
    assert calls==[]


def test_saturated_fills_response_has_one_window_no_recursive_http():
    import asyncio
    from coinmaster.ops.hl_info_receipt import collect_info_receipt
    calls=[]
    async def transport(body):
        calls.append(body['type'])
        if body['type']=='frontendOpenOrders':return []
        if body['type']=='clearinghouseState':return {'assetPositions':[],'marginSummary':{'accountValue':'100','totalRawUsd':'100','totalMarginUsed':'0','totalNtlPos':'0'},'withdrawable':'100'}
        if body['type']=='userFillsByTime':return [{}]*2000
        raise AssertionError(body)
    with pytest.raises(ValueError,match='SATURATED'):
        asyncio.run(collect_info_receipt(transport,account='0x'+'1'*40,dex='',anchor_ms=0,anchor_tid=None,end_ms=1,expected_orders={},owned_coins=frozenset({'BTC','SOL'}),allow_fill_subdivision=False))
    assert calls.count('userFillsByTime')==1


def money_code():
    from dataclasses import dataclass
    from coinmaster.ops.hl_info_receipt import IncompleteInfoReport
    env={'dataclass':dataclass,'Decimal':D,'IncompleteInfoReport':IncompleteInfoReport}
    run_ast(nodes('ops/hl_live_money.py',{'CheapPortfolioObservation','materialize_live_c1_input'}),env)
    return N(**env)


def test_live_input_native_pnl_real_mark_no_doublecount_and_shared_loss_parity():
    m=money_code();now=1_000_000_000_000
    observation=m.CheapPortfolioObservation(D(120),D(100),D(90),D(10),(('BTC',D(2)),),7,3,9,100,200,now-10,'native-event')
    calls=[]
    quantity=N(as_decimal=lambda:D(2));increment=N(as_decimal=lambda:D(1))
    pos=N(instrument_id='BTC',id='owned-pos',ts_opened=1,is_long=True,quantity=quantity,account_id='acct',strategy_id='strategy')
    pos.unrealized_pnl=lambda price:(calls.append(price) or N(as_decimal=lambda:D(-30)))
    instrument=N(make_price=lambda p:p,size_increment=increment)
    cache=N(instrument=lambda i:instrument)
    mark=N(price=D(90),ts_event=now-100,ts_init=now-50)
    kwargs=dict(native_positions=(pos,),native_marks={'BTC':mark},native_cache=cache,account_event_id='native-event',strategy_id='strategy',account_id='acct',decision_ns=now,monotonic_ns=201,revision=7,fill_epoch=3,ws_epoch=9,max_mark_age_ns=1000)
    # Instrument names must match the native BTC/SOL perpetual surface.
    pos.instrument_id='BTC-USD-PERP.HYPERLIQUID';kwargs['native_marks']={pos.instrument_id:mark}
    value=m.materialize_live_c1_input(observation,**kwargs)
    assert value.equity==D(120) and value.positions[0].native_pnl==D(-30) and calls==[D(90)]
    env={'D':D};run_ast(nodes('strategy/residual_recovery.py',{'ResidualRecoveryResearch'}),env)
    policy=env['ResidualRecoveryResearch']();policy.config=N(btc_id=pos.instrument_id,sol_id='SOL-USD-PERP.HYPERLIQUID')
    policy.cache=cache;policy._hb_position=lambda i:pos
    research=[{'instrument_id':pos.instrument_id,'mark_ohlc':{'close':'90'}}]
    assert policy._c1_loss_candidates(research)==policy._c1_loss_candidates(value.positions)
    kwargs['revision']=8
    with pytest.raises(ValueError,match='STALE_OR_MOVED'):m.materialize_live_c1_input(observation,**kwargs)
    kwargs['revision']=7;kwargs['monotonic_ns']=9_000_000_101
    with pytest.raises(ValueError,match='STALE_OR_MOVED'):m.materialize_live_c1_input(observation,**kwargs)


def test_actual_full_generation_vector_prepays_native_refresh_and_refunds_unused():
    import asyncio,time
    from collections import deque
    from dataclasses import replace,dataclass
    from coinmaster.ops.hl_info_receipt import IncompleteInfoReport,collect_info_receipt
    calls=[];account=N(last_event=N(id='old',ts_init=0));queries=[]
    async def read_http(body,**kwargs):
        assert sum(item[1] for item in owner._cm_inputs_budget.spent)==540
        calls.append(body['type'])
        if body['type']=='frontendOpenOrders':return []
        if body['type']=='clearinghouseState':
            summary={'accountValue':'100','totalRawUsd':'100','totalMarginUsed':'0','totalNtlPos':'0'}
            return {'assetPositions':[],'marginSummary':summary,'crossMarginSummary':summary,'withdrawable':'100'}
        if body['type']=='userRole':return {'role':'user'}
        if body['type']=='userAbstraction':return 'disabled'
        if body['type']=='userDexAbstraction':return False
        if body['type']=='userFillsByTime':return []
        if body['type']=='activeAssetData':return {'coin':body['coin']}
        raise AssertionError(body)
    async def assets(info,**kwargs):
        return tuple([await info({'type':'activeAssetData','coin':coin}) for coin in sorted(kwargs['coins'])])
    env={'asyncio':asyncio,'time':time,'deque':deque,'IncompleteInfoReport':IncompleteInfoReport,
        'collect_info_receipt':collect_info_receipt,'collect_selected_cross_assets':assets,
        'qualified_mass_status':lambda *args,**kwargs:N(account_id='acct'),'InstrumentId':N(from_str=lambda v:v),
        'read_info_http':read_http,'_native_order_fingerprint':lambda o:[], 'replace':replace}
    run_ast(nodes('ops/hl_live_execution.py',{'ReadinessInfoBudget','finite_generation_reservation','InfoWeightBudget','SingleAttemptInfoTransport','QualifiedInfoBoundary'}),env)
    owner=env['QualifiedInfoBoundary']()
    owner._cm_inputs_enabled=True;owner._cm_last_receipt=None;owner._cm_last_margin_assets=None;owner._cm_last_revision=None
    owner._cm_bootstrapped=False;owner._cm_ws_failure=None;owner._cm_info_usage=deque();owner._cm_ws_phase='BUFFERING'
    owner._cm_inputs_budget=env['ReadinessInfoBudget']();owner._cm_require_healthy=lambda:None
    owner._cm_fail=lambda reason:(_ for _ in ()).throw(AssertionError(reason))
    scope=N(durable_orders=(),account_ref='0x'+'1'*40,dex='',anchor_ms=0,anchor_tid=None,owned_coins=frozenset({'BTC','SOL'}))
    owner._cm_owned_scope=lambda:(scope,7,(),frozenset(),())
    owner._cm_runtime=N(info_query_evidence=lambda *args:({},(),None,None))
    owner._cache=N(account_for_venue=lambda venue:account,instrument=lambda i:object())
    owner._clock=N(timestamp_ns=lambda:10_000_000_000);owner.venue='HL';owner.account_id='acct';owner.id='client'
    def query(account_id):queries.append(account_id);account.last_event=N(id='fresh',ts_init=10_000_000_000)
    owner._cm_strategy=N(query_account=query)
    owner._cm_info=env['SingleAttemptInfoTransport'](testnet=False,timeout=1)
    assert asyncio.run(owner.generate_mass_status()).account_id=='acct'
    assert queries==['acct'] and len(calls)==14
    assert {kind:calls.count(kind) for kind in set(calls)}=={'frontendOpenOrders':2,'clearinghouseState':2,'userRole':2,'userAbstraction':2,'userDexAbstraction':2,'userFillsByTime':2,'activeAssetData':2}
    assert sum(item[1] for item in owner._cm_inputs_budget.spent)==340
    # Sixteen uncached statuses cannot start even the stock account query.
    scope.durable_orders=tuple(range(16));queries.clear();calls.clear()
    owner._cm_fail=lambda reason:setattr(owner,'_cm_ws_failure',reason)
    with pytest.raises(ValueError,match='SCOPE_EXCEEDS'):asyncio.run(owner.generate_mass_status())
    assert queries==[] and calls==[]


def test_typed_fill_and_applied_checkpoint_commit_or_rollback_together(code,tmp_path):
    s,r,entry,position=setup(code,tmp_path)
    try:
        # Setup already applied10. A duplicate attempt must roll back newly
        # staged typed payload rather than leave an independent fill receipt.
        assert r.db.execute("SELECT COUNT(*) FROM live_evidence_payloads WHERE kind='fill'").fetchone()[0]==0
        assert not r.commit_applied_fills(['10'],s.on_save()[code.env['_KEY']])
        assert r.db.execute("SELECT COUNT(*) FROM live_evidence_payloads WHERE kind='fill'").fetchone()[0]==0
        r.db.execute("INSERT INTO paper_native_fill_details(trade_id,client_order_id,instrument_id,quantity,price,ts_event_ns) VALUES ('11','ENTRY',?,'1','100',2000000)",(str(s.config.btc_id),));r.db.commit()
        checkpoint=s.on_save()[code.env['_KEY']]
        assert r.commit_applied_fills(['11'],checkpoint)
        assert r.has_applied_fill('11') and r.strategy_checkpoint()[0]==checkpoint
        row=r.db.execute("SELECT body FROM live_evidence_payloads WHERE event_id='11' AND kind='fill'").fetchone()
        assert json.loads(row[0])['native']['quantity']=='1'
    finally:r.close()


def test_changed_runtime_classes_have_no_shadowed_duplicate_methods():
    import ast
    from test_e4_c1_manage_only_pure import ROOT
    paths=('ops/hl_live_epoch.py','ops/hl_live_execution.py','ops/hl_live_money.py','ops/hl_live_profile.py','ops/hl_live_worker.py','strategy/live_recovery.py','strategy/residual_recovery.py')
    duplicates=[]
    for path in paths:
        for cls in (n for n in ast.walk(ast.parse((ROOT/path).read_text())) if isinstance(n,ast.ClassDef)):
            seen=set()
            for method in (n for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))):
                # Property setters intentionally share the getter's name.
                setter=any(isinstance(d,ast.Attribute) and d.attr in ('setter','deleter') for d in method.decorator_list)
                if method.name in seen and not setter:duplicates.append((path,cls.name,method.name))
                seen.add(method.name)
    assert duplicates==[]


def test_actual_sole_startup_calls_native_subscribe_and_persisted_backfill(code,monkeypatch):
    from datetime import timezone
    s=code.Strategy(__import__('test_e4_c1_manage_only_pure').config())
    code.env['timezone']=timezone
    starts=[];subscriptions=[];requests=[]
    monkeypatch.setattr(code.env['WaveOverlayStrategy'],'on_start',lambda self:starts.append('native-base'),raising=False)
    s._input_readiness_preparation=True;s._live_minute_bar_types=('btc1m','sol1m')
    s._live_signal_clock_state={'last_h4':{'BTC':14_400_000_000_000,'SOL':28_800_000_000_000}}
    s.clock=N(timestamp_ns=lambda:2*DAY_NS+123)
    s.subscribe_bars=lambda kind:subscriptions.append(kind)
    s.request_bars=lambda kind,**kwargs:requests.append((kind,kwargs))
    s.on_start()
    assert starts==['native-base'] and subscriptions==['btc1m','sol1m'] and len(requests)==2
    assert all(int(kwargs['start'].timestamp()*1e9)==14_400_000_000_000 and int(kwargs['end'].timestamp()*1e9)==2*DAY_NS for _,kwargs in requests)
    assert s._live_history_cutoff_ns==2*DAY_NS and not s.recovery_confirmed


def test_same_c1_economic_body_claims_identical_quarter_cut_from_research_or_live_dto():
    from coinmaster.strategy.c1_inputs import C1PositionInput
    env={'D':D};run_ast(nodes('strategy/residual_recovery.py',{'ResidualRecoveryResearch'}),env)
    cls=env['ResidualRecoveryResearch'];instrument='BTC-USD-PERP.HYPERLIQUID'
    pos=N(id='position',ts_opened=1,is_long=True,quantity=N(as_decimal=lambda:D(10)))
    pos.unrealized_pnl=lambda price:N(as_decimal=lambda:D(-500))
    native_instrument=N(make_price=lambda p:p,size_increment=N(as_decimal=lambda:D(1)))
    def policy():
        p=cls();p.config=N(research_residual_recovery=True,research_c1_global_cut_arm=False,btc_id=instrument,sol_id='SOL-USD-PERP.HYPERLIQUID',research_c1_btc_cut_divisor=4)
        p._c1_peak=D(100);p._c1_state=None;p._c1_fill_epoch=3;p._c1_checkpoint=None;p.c1_audit=[];p.c1_denials={};p._pending_by_order={}
        p._domain=N(episode=N(id='group'),_ensure_btc_targets=lambda ep:None)
        p._split_parent={'episode_id':'group','closed':True};p._split_unfinished=lambda:False
        p._c1_conflict=lambda:False;p._c1_rights=lambda:None
        p.cache=N(instrument=lambda i:native_instrument,orders_inflight=lambda:[])
        p._hb_position=lambda i:pos
        return p
    research=policy();live=policy()
    research._c1_observe(D(50),1000,999,3,[{'instrument_id':instrument,'mark_ohlc':{'close':'55'}}])
    dto=C1PositionInput(instrument,'position',1,True,D(10),D(1),D(55),998,D(-500))
    live._c1_observe(D(50),1000,999,3,(dto,))
    assert live._c1_state==research._c1_state
    assert live._c1_checkpoint==research._c1_checkpoint
    assert live._c1_state['cut_lots']==2 and live._c1_state['target_lots']==8


def test_selected_firstfresh_postcut_d1_hwm_rights_clock_checkpoint_roundtrip(code):
    from test_e4_c1_manage_only_pure import config
    s=code.Strategy(config())
    s._c1_state['first_fresh_last_h4_ns']=14_400_000_000_000
    s._c1_state['first_fresh_deferred']={'close_ns':14_400_000_000_000,'available_ns':14_400_000_000_100,'identity':{'fill_epoch':7,'credit':3}}
    s._c1_last_bars={'BTC_POSTCUT_D1':{'open_ns':DAY_NS,'close_ns':2*DAY_NS,'available_ns':2*DAY_NS+100,'instrument':'BTC'}}
    s._live_signal_clock_state={'last_h4':{'BTC':14_400_000_000_000},'last_closed':{('BTC',4):14_400_000_000_000}}
    body=s.on_save();restored=code.Strategy(config());restored.on_load(body)
    assert restored.on_save()==body and restored._c1_peak==D(15000)
    assert restored._c1_state['first_fresh_deferred']==s._c1_state['first_fresh_deferred']
    assert restored._c1_last_bars==s._c1_last_bars and restored._live_signal_clock_state==s._live_signal_clock_state
    assert restored._last_live_input_observation is None and restored._live_c1_input is None
    assert not restored.recovery_confirmed and restored._management_certificate is None


def test_funding_separate_same_rolling_budget_item_weights_no_cashposting(code,tmp_path):
    import asyncio,time
    b=budget_code();env={'time':time,'IncompleteInfoReport':b.IncompleteInfoReport}
    run_ast(nodes('ops/hl_live_execution.py',{'QualifiedInfoBoundary'}),env)
    s,r,entry,position=setup(code,tmp_path)
    owner=env['QualifiedInfoBoundary']();owner._cm_inputs_enabled=True;owner.recovery_healthy=lambda:True
    owner._cm_parity_lock=asyncio.Lock();owner._cm_runtime=r;owner._cm_scope=N(anchor_ms=0,account_ref='synthetic')
    owner._clock=N(timestamp_ns=lambda:2*DAY_NS);owner._cm_inputs_budget=b.ReadinessInfoBudget()
    rows=[{'time':1,'hash':'0x1','delta':{'coin':'BTC','usdc':'-1.5'}}]
    calls=[]
    async def info(body):calls.append(body);return rows
    owner._cm_info=info
    try:
        revision=r.native_revision()
        assert asyncio.run(owner.collect_user_funding_observation(s))
        assert sum(item[1] for item in owner._cm_inputs_budget.spent)==21
        assert r.native_revision()==revision and r.pending_native_funding()==[]
        cursor=r.evidence_cursor('userFunding')
        assert cursor=={'end_ms':DAY_NS//1_000_000} and len(calls)==1
        rows[:]=[{'time':DAY_NS//1_000_000+1}]*500
        with pytest.raises(ValueError,match='COMPLETENESS_UNKNOWN'):asyncio.run(owner.collect_user_funding_observation(s))
        assert r.evidence_cursor('userFunding')==cursor
        assert sum(item[1] for item in owner._cm_inputs_budget.spent)==66
    finally:r.close()


def test_live_firstfresh_uses_real_callback_clock_without_forging_quote_event():
    env={'D':D};run_ast(nodes('strategy/residual_recovery.py',{'ResidualRecoveryResearch'}),env)
    policy=env['ResidualRecoveryResearch']();policy.config=N(research_c1_first_fresh_h4=True)
    policy._domain=N(episode=N(id='group'));policy._c1_deferred_identity=lambda t:{'id':'same'}
    policy._c1_log=lambda *args,**kwargs:None
    pending={'available_ns':200,'close_ns':100,'open_ns':1,'close':D(101),'identity':{'id':'same'}}
    policy._c1_state={'first_fresh_deferred':pending,'instrument':'BTC','group':'group','state':'HELD','revoked':False,'restore_submitted':False,'credit':1,'confirmation':None,'side':1,'cut_value':D(100),'cut_filled':1,'step':D(1)}
    policy._c1_fill_epoch=3;policy.config.research_c1_restore_dd=D('.40')
    tick=N(instrument_id='BTC',ts_event=150,ask_price=N(as_decimal=lambda:D(101)))
    current={'source':250,'DD':D('.1')}
    policy._c1_first_fresh_quote(tick,current)
    assert 'first_fresh_deferred' in policy._c1_state
    policy._c1_first_fresh_quote(tick,current,decision_ns=300)
    assert policy._c1_state['confirmation']['close_ns']==100 and 'first_fresh_deferred' not in policy._c1_state
    assert tick.ts_event==150


def test_actual_worker_dp_reader_observes_native_equity_without_command_permit(code,tmp_path,monkeypatch):
    import ast,time,sys
    from types import ModuleType
    from test_e4_c1_manage_only_pure import ROOT,ACCOUNT_ID
    m=money_code();module=ModuleType('coinmaster.ops.hl_live_money');module.CheapPortfolioObservation=m.CheapPortfolioObservation
    monkeypatch.setitem(sys.modules,module.__name__,module)
    tree=ast.parse((ROOT/'ops/hl_live_worker.py').read_text())
    reader=next(k.value for n in ast.walk(tree) if isinstance(n,ast.Call) for k in n.keywords if k.arg=='deposit_equity_reader')
    actual_reader=eval(compile(ast.Expression(reader),'actual_worker_dp_reader','eval'),{})
    s,r,entry,position=setup(code,tmp_path)
    try:
        s._input_readiness_preparation=True;s._live_inputs_dirty=False;s._live_input_ws_epoch=lambda:3;s._recovery_health=lambda:True
        account=N(id=ACCOUNT_ID,last_event=N(id='native-actual'))
        s.cache.account_for_venue=lambda venue:account
        now=time.monotonic_ns()
        s._last_live_input_observation=m.CheapPortfolioObservation(D('45.01'),D(100),D(40),D(5),(('BTC',D(10)),),r.native_revision(),s._c1_fill_epoch,3,now,now,DAY_NS+1,'native-actual')
        dp=DepositProtection(limit_percent=55);dp.initialize(D(100),DAY_NS+1)
        assert actual_reader(s)==D('45.01')
        assert dp.observe(actual_reader(s),DAY_NS+2)==(False,False)
        from dataclasses import replace
        s._last_live_input_observation=replace(s._last_live_input_observation,equity=D(45))
        assert dp.observe(actual_reader(s),DAY_NS+3)==(True,True)
        assert dp.high_water==D(100) and dp.threshold==D(45) and dp.latched
        assert not s.recovery_confirmed and not s._entries_enabled() and not s._management_dispatch_enabled
        account.last_event.id='changed'
        with pytest.raises(ValueError,match='ACCOUNT_MOVED'):actual_reader(s)
    finally:r.close()


def test_actual_input_worker_constructor_preserves_runtime_decimal_and_paused_dp_setter_route(monkeypatch):
    import sys
    from types import ModuleType
    from pathlib import Path
    from test_e4_c1_manage_only_pure import ROOT
    runtime=N(record_native_fill=lambda **kwargs:None,all_submissions=lambda:[],strategy_checkpoint=lambda:(b'fixture',0))
    flags={'research_btc_split_discount':'0.0025','research_c1_restore_dd':'0.40','research_regime_reentry_band':'0.5'}
    profile={'input_readiness':True,'manage_only_readiness':True,'strategy_flags':flags,'deposit_protection_percent':55,'retained_equity_floor_fraction':'0.45'}
    captured=[]
    class FakeStrategy:
        def __init__(self,config):
            assert config.deposit_runtime is runtime
            assert config.research_btc_split_discount==D('.0025') and type(config.research_btc_split_discount) is D
            self.config=config;self.recovery_confirmed=False
        def enable_manage_only_preparation(self):pass
        def on_load(self,body):pass
        def _validated_live_money(self):return None
        def deposit_projection(self):return {'drawdown_limit_percent':50}
    class FakeNode:
        def __init__(self,**kwargs):self.trader=N(add_strategy=lambda strategy:captured.append(strategy))
        def add_data_client_factory(self,*args):pass
        def add_exec_client_factory(self,*args):pass
        def build(self):captured.append('built')
    warmup=ModuleType('coinmaster.ops.stage_g_warmup')
    warmup.load_stageg_bybit_warmup=lambda path:({'BTCUSDT':[{'open_time_ms':0,'high':'101','low':'99'}]},'READY')
    monkeypatch.setitem(sys.modules,warmup.__name__,warmup)
    native=ModuleType('nautilus_trader');native.__path__=[]
    core=ModuleType('nautilus_trader.core');core.nautilus_pyo3=N()
    monkeypatch.setitem(sys.modules,native.__name__,native);monkeypatch.setitem(sys.modules,core.__name__,core)
    env={'Path':Path,'__file__':str(ROOT/'ops/hl_live_worker.py'),'Decimal':D,'time':__import__('time'),
        'asyncio':N(new_event_loop=lambda:'fixture-loop'),'replace':lambda value,**kw:N(**(vars(value)|kw)),
        'load_live_profile':lambda *args:profile,'check_live_credential':lambda *args:D(100),
        '_read_json':lambda path:{'master_address':'synthetic','agent_private_key':'synthetic-not-key'},
        'cross_venue_stage_g_gate':lambda **kwargs:N(warmup_state='READY',margin_policy_state='READY_PUBLIC_HL_MAINNET_TIERS_LOCAL_SANDBOX_LEVERAGE',candidate_hash='fixture'),
        'load_stageg_warmup_bundle':lambda path:(N(bars=(),rows=730),'READY'),
        'LiveSubmissionHooks':lambda state:N(record_event=lambda *args:None), 'FeedBook':lambda **kwargs:N(),
        'hyperliquid_testnet_node_config':lambda **kwargs:N(exec_clients={'HYPERLIQUID-LIVE':N(instrument_provider=None,routing=None,environment=None)},data_clients={'BYBIT-PUBLIC-SIGNAL':N()}),
        'HyperliquidExecClientConfig':lambda **kwargs:N(**kwargs),'RecoverableWaveOverlayStrategy':FakeStrategy,
        'WaveOverlayStrategyConfig':lambda **kwargs:N(**kwargs),'BTC_PERP':'BTC','SOL_PERP':'SOL','BYBIT_IDS':('BTCUSDT','SOLUSDT'),
        'TESTNET_IDS':('BTC','SOL'),'bybit_daily_bar_type':lambda i:i,'venue_mark_data_type':lambda i:i,'ClientId':str,
        'TimeInForce':N(IOC='IOC'),'BarType':lambda *args:args,'BarSpecification':lambda *args:args,
        'BarAggregation':N(MINUTE='MINUTE'),'PriceType':N(LAST='LAST'),'AggregationSource':N(EXTERNAL='EXTERNAL'),
        'durable_management_scope':lambda state,*args:N(runtime=state),
        'ScopedHyperliquidExecClientFactory':N(bind=lambda scope,state,*args,**kwargs:captured.append(state)),
        'TradingNode':FakeNode,'BybitLiveDataClientFactory':object(),'HyperliquidLiveDataClientFactory':object(),
        'FeedObserver':lambda config:N(),'FeedObserverConfig':lambda **kwargs:N(**kwargs),
        'HyperliquidTestnetNode':N(sandbox_snapshot=None,strategy_restartable=None,start=None,stop=None),
        'require_profile_deposit_parity':require_profile_deposit_parity}
    run_ast(nodes('ops/hl_live_worker.py',{'HyperliquidLiveNode'}),env)
    instance=N(mode='live',instance_id='hl-stageg-live',signal_warmup_manifest=Path('/synthetic'),trader_id='trader',strategy_id='strategy',order_id_tag='tag')
    node=env['HyperliquidLiveNode'](instance=instance,candidate=object(),state=runtime,credential_path=Path('/synthetic'),fingerprint_path=Path('/synthetic'))
    assert node.state is runtime and runtime in captured and 'built' in captured
    node._refresh_warmup_readiness=lambda:None
    assert node.strategy.deposit_projection()['drawdown_limit_percent']==50
    assert node._entries_enabled() is False


def fresh_init_fixture(code,tmp_path):
    from dataclasses import dataclass
    from test_e4_c1_manage_only_pure import config,ACCOUNT,ACCOUNT_ID
    from coinmaster.ops.hl_info_receipt import IncompleteInfoReport
    money={'dataclass':dataclass,'Decimal':D,'IncompleteInfoReport':IncompleteInfoReport}
    run_ast(nodes('ops/hl_live_money.py',{'LivePerpsMoneyView'}),money)
    code.env['LivePerpsMoneyView']=money['LivePerpsMoneyView'];code.env['USDC']='USDC'
    cfg=config();cfg.research_c1_btc_cut_divisor=4;cfg.research_c1_restore_dd=D('.40')
    cfg.research_c1_first_fresh_h4=True;cfg.research_c1_btc_postcut_d1=True;cfg.research_c1_global_cut_arm=False
    s=code.Strategy(cfg);s._input_readiness_preparation=True;s.enable_manage_only_preparation()
    s._domain.episode=None;s._c1_state=None;s._c1_intents={};s._c1_fill_epoch=0;s._seen_trade_ids=set()
    s._fresh_c1_init_intent='INITIALIZE_FRESH_C1_EPOCH';s._fresh_init_generation_validator=lambda:True
    r=code.Runtime(tmp_path/'fresh.sqlite','fresh-owner',10**20);r.acquire();r.acquire_live_account(ACCOUNT,'HYPERLIQUID',lock_root=tmp_path/'fresh-locks')
    s.attach_recovery_runtime(r)
    r.entry_control_command('pause-new-entries','fixture-c1-init')
    cash=N(as_decimal=lambda:D(82));account=N(id=ACCOUNT_ID,base_currency=None,last_event=N(id='fresh-native'),balance_total=lambda currency:cash)
    s.cache=N(account_for_venue=lambda venue:account,positions_open=lambda:[],orders_open=lambda:[],orders_inflight=lambda:[])
    now=DAY_NS+1000
    view=money['LivePerpsMoneyView'](ACCOUNT,'',now//1_000_000,D(82),D(82),D(0),D(82),(N(coin='BTC'),N(coin='SOL')),(),r.native_revision())
    return s,r,view,now


def test_canonical_fresh_epoch_initializes_from_actual_native_once_and_restart_preserves_h(code,tmp_path):
    s,r,view,now=fresh_init_fixture(code,tmp_path)
    try:
        s._live_signal_clock_state={'last_h4':{'BTC':14_400_000_000_000}}
        body=s.initialize_clean_flat_c1_epoch(view,intent='INITIALIZE_FRESH_C1_EPOCH',now_ns=now,history_anchor_ms=0)
        assert r.strategy_checkpoint()[0]==body and r.c1_initialization()['initial_equity']=='82'
        assert s._c1_peak==D(82) and s._next_peak==D(82) and s._c1_state is None and s._c1_fill_epoch==0
        assert r.coherent_snapshot() and r.projection_snapshot()==([],[])
        scope=code.management['durable_management_scope'](r,view.account,'',lambda client:'unused')
        assert scope.anchor_ms==0 and scope.anchor_tid is None and scope.durable_orders==()
        assert not s.recovery_confirmed and not s._entries_enabled() and not s._management_dispatch_enabled
        restored=code.Strategy(s.config);restored.on_load(s.on_save())
        assert restored._c1_peak==D(82) and restored._live_signal_clock_state==s._live_signal_clock_state
        assert restored._management_certificate is None and not restored.recovery_confirmed
        before=r.strategy_checkpoint();marker=r.c1_initialization();s._fresh_c1_init_intent='INITIALIZE_FRESH_C1_EPOCH'
        with pytest.raises(ValueError,match='PRIOR_OR_UNCERTAIN'):s.initialize_clean_flat_c1_epoch(view,intent='INITIALIZE_FRESH_C1_EPOCH',now_ns=now+1,history_anchor_ms=0)
        assert r.strategy_checkpoint()==before and r.c1_initialization()==marker and s._c1_peak==D(82)
    finally:r.close()


@pytest.mark.parametrize('fault',['intent','nonflat','unknown','checkpoint','seen_fill','native_equity','unpaused','raw_fill','legacy_fill'])
def test_fresh_epoch_rejects_missing_intent_nonflat_unknown_or_prior_state(code,tmp_path,fault):
    s,r,view,now=fresh_init_fixture(code,tmp_path)
    try:
        intent='INITIALIZE_FRESH_C1_EPOCH'
        if fault=='intent':intent=None
        elif fault=='nonflat':s.cache.positions_open=lambda:[object()]
        elif fault=='unknown':s._fresh_init_generation_validator=lambda:False
        elif fault=='checkpoint':assert r.persist_strategy_checkpoint(s.on_save()[code.env['_KEY']],r.native_revision())
        elif fault=='seen_fill':s._seen_trade_ids={'prior'}
        elif fault in ('raw_fill','legacy_fill'):
            if fault=='raw_fill':r.db.execute("INSERT INTO paper_native_fill_details(trade_id,instrument_id,quantity,price) VALUES ('old','BTC','1','100')")
            else:r.db.execute("INSERT INTO paper_events VALUES ('old','fill')")
            snapshot={'ts_ns':now,'positions':[],'orders':[],'funding_event_ids':[],'reconciled':True,'native_revision':r.native_revision(),'native_account_total':'82','native_account_currency':'USDC','strategy_restartable':True}
            r.db.execute('INSERT OR REPLACE INTO paper_snapshot VALUES (1,?)',(json.dumps(snapshot),));r.db.commit()
        elif fault=='unpaused':r.entry_control_command('resume-new-entries','fixture-resume')
        elif fault=='native_equity':
            from dataclasses import replace
            view=replace(view,equity=D(83),raw_usd=D(83))
        previous=r.strategy_checkpoint();old_h=s._c1_peak
        with pytest.raises(ValueError):s.initialize_clean_flat_c1_epoch(view,intent=intent,now_ns=now,history_anchor_ms=0)
        assert r.c1_initialization() is None and r.strategy_checkpoint()==previous and s._c1_peak==old_h
    finally:r.close()
