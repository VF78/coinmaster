"""Documented HTTP route, concurrency and real cost phases. No native/network."""
import asyncio,hashlib,json,time,threading
from collections import deque
from types import SimpleNamespace as N
from decimal import Decimal as D
import pytest
from coinmaster.ops.hl_info_receipt import (IncompleteInfoReport,collect_per_dex_states,
    bounded_info_requests,parse_perp_dex_directory)
from test_e4_c1_manage_only_pure import nodes,run_ast,code,config

def source():
    env=dict(asyncio=asyncio,time=time,hashlib=hashlib,json=json,deque=deque,IncompleteInfoReport=IncompleteInfoReport)
    run_ast(nodes('ops/hl_live_execution.py',{'ReadinessInfoBudget','finite_generation_reservation',
        'held_sample_reservation','InfoWeightBudget','SingleAttemptInfoTransport','QualifiedInfoBoundary'}),env)
    return N(**env)

@pytest.mark.parametrize('Dcount,Ncount,bound',[(1,0,401),(11,0,441),(11,14,497),(11,15,501),(32,15,585)])
def test_exact_documented_D_dependent_full_vector_and_held(Dcount,Ncount,bound):
    e=source()
    assert e.finite_generation_reservation(Ncount,unified=True,dex_count=Dcount)==bound
    assert e.held_sample_reservation(Dcount)==28+2*Dcount
    assert e.finite_generation_reservation(15)==600
    gateway=e.ReadinessInfoBudget()
    admitted=gateway.protects_held_schedule(0,additional=bound,sample_weight=28+2*Dcount)
    assert admitted is (bound+10*(28+2*Dcount)<=1000)

@pytest.mark.parametrize('Dcount',[None,0,33,True,-1])
def test_unknown_directory_size_denies_before_requests(Dcount):
    with pytest.raises(ValueError,match='COUNT_UNKNOWN'):source().finite_generation_reservation(0,unified=True,dex_count=Dcount)

def test_WS_only_name_is_rejected_by_HTTP_transport_and_weight_whitelist():
    e=source();calls=[]
    async def info(body):calls.append(body);return []
    async def run():
        for gateway in (e.InfoWeightBudget(info,700),e.SingleAttemptInfoTransport(testnet=False,timeout=1)):
            with pytest.raises(IncompleteInfoReport,match='UNSUPPORTED'):
                await gateway({'type':'allDexsClearinghouseState','user':'synthetic'})
    asyncio.run(run())
    assert calls==[]

def test_bounded_eight_real_delay_parallel_sweeps_have_sequential_barriers_and_provenance():
    active=peak=0;calls=[];first_complete=[None]
    names=('',*('dex'+str(i) for i in range(1,11)))
    async def info(body):
        nonlocal active,peak
        assert body['type']=='clearinghouseState' and body['dex'] in names
        active+=1;peak=max(peak,active);calls.append((body['dex'],time.monotonic_ns()))
        try:
            # Actual wall delay based on ROOT measured .29-.49s public Info latency.
            await asyncio.sleep(.32 if body['dex'] in ('','dex1') else .49)
            return {'assetPositions':[]}
        finally:active-=1
    async def run():
        started=time.monotonic_ns()
        first,proof1=await collect_per_dex_states(info,account='synthetic',dex_names=names)
        first_complete[0]=time.monotonic_ns()
        second,proof2=await collect_per_dex_states(info,account='synthetic',dex_names=names)
        completed=time.monotonic_ns()
        assert tuple(name for name,_ in first)==names==tuple(name for name,_ in second)
        assert len(proof1)==len(proof2)==11 and max(p[3] for p in proof1)<=min(p[2] for p in proof2)
        assert completed-started<9_000_000_000 # Actual delayed fixture span, not future venue guarantee.
    asyncio.run(run())
    assert 1<peak<=8 and len(calls)==22 and active==0

def test_parallel_failure_drains_dispatched_batch_charges_all_and_skips_next_batch():
    e=source();gateway=e.ReadinessInfoBudget();token=gateway.reserve(64,time.monotonic())
    calls=[];finished=[]
    async def info(body):
        gateway.note(token,2,time.monotonic());calls.append(body['dex'])
        await asyncio.sleep(.005 if body['dex']=='dex1' else .02)
        finished.append(body['dex'])
        if body['dex']=='dex1':raise ValueError('recorded HTTP failure')
        return {'assetPositions':[]}
    names=('',*('dex'+str(i) for i in range(1,11)))
    with pytest.raises(IncompleteInfoReport,match='PARALLEL_BATCH'):
        asyncio.run(collect_per_dex_states(info,account='synthetic',dex_names=names))
    gateway.settle(token,2*len(calls),now=time.monotonic())
    assert len(calls)==len(finished)==8 and len(gateway.spent)==8
    assert sum(row[1] for row in gateway.spent)==16
    assert 'dex8' not in calls

def test_missing_DEX_response_never_becomes_flat_zero():
    async def info(body):return None if body['dex']=='foreign' else {'assetPositions':[]}
    with pytest.raises(ValueError,match='POSITION_SET_UNKNOWN'):
        asyncio.run(collect_per_dex_states(info,account='synthetic',dex_names=('','foreign')))

def directory_owner(code):
    e=source();owner=e.QualifiedInfoBoundary();s=code.Strategy(config())
    owner._cm_strategy=s;owner._cm_scope=N(account_ref='synthetic');owner._cm_ws_epoch=4
    owner._cm_unified=True;owner._cm_directory_task=None;owner._cm_inputs_budget=e.ReadinessInfoBudget()
    owner._cm_next_money_request=0;owner._cm_require_healthy=lambda:None;owner._cm_fail=lambda reason:setattr(owner,'failed',reason)
    owner._cm_unified_discovery=dict(account='synthetic',ws_epoch=4,
        policy_sha256=code.env['recovery_policy_hash'](s.config,s._candidate),dex_names=('','foreign'),
        started_ns=10,completed_ns=20,directory_observed_ns=time.monotonic_ns()-301_000_000_000)
    owner.failed=None
    return owner,e

def test_directory_refresh20_actual_time_does_not_reage_foreign_snapshot(code):
    owner,e=directory_owner(code);calls=[]
    async def info(body):calls.append(body);return [None,{'name':'foreign'}]
    owner._cm_info=info
    assert not owner._cm_dex_directory_current()
    asyncio.run(owner.qualify_unified_dex_directory())
    proof=owner._cm_unified_discovery
    assert owner._cm_dex_directory_current() and proof['started_ns']==10 and proof['completed_ns']==20
    assert calls==[{'type':'perpDexs'}] and sum(row[1] for row in owner._cm_inputs_budget.spent)==20
    assert proof['directory_sha256']==hashlib.sha256(json.dumps(('','foreign')).encode()).hexdigest()

@pytest.mark.parametrize('raw',[[None,{'name':'new'}],[None,None],None])
def test_directory_change_malformed_quarantines_without_reusing_old_proof(code,raw):
    owner,e=directory_owner(code)
    async def info(body):return raw
    owner._cm_info=info
    with pytest.raises(ValueError):asyncio.run(owner.qualify_unified_dex_directory())
    assert owner._cm_unified_discovery is None and owner.failed=='UNIFIED_DEX_DIRECTORY_UNKNOWN'

def test_gateway_threadsafe_reservation_admission_cannot_double_spend():
    gateway=source().ReadinessInfoBudget();barrier=threading.Barrier(3);results=[]
    def claim():
        barrier.wait()
        try:
            token=gateway.reserve(600,0);results.append(token)
        except IncompleteInfoReport:results.append(None)
    workers=[threading.Thread(target=claim) for _ in range(2)]
    for worker in workers:worker.start()
    barrier.wait()
    for worker in workers:worker.join()
    assert sum(value is not None for value in results)==1 and gateway.remaining(0)==400

@pytest.mark.parametrize('ignore',[False,True])
def test_inherited_entry_guard_keyword_compatibility_keeps_live_guards(code,ignore):
    s=code.Strategy(config());s._active_c1_authorized=True;s._validated_live_money=lambda:None
    s._capital_basis_verified=True;s._recovery_runtime=N(cashflow_quarantined=lambda:False)
    s._live_context_current=lambda:True;s._live_increase_headroom=lambda:True;s._feeds_fresh=lambda now:True
    calls=[]
    code.env['WaveOverlayStrategy']._entries_enabled=lambda self,**kwargs:calls.append(kwargs) or True
    assert s._entries_enabled(ignore_research_protection=ignore)
    assert calls==[{'ignore_research_protection':ignore}]
    s._live_increase_headroom=lambda:False
    assert not s._entries_enabled(ignore_research_protection=ignore) and len(calls)==1

@pytest.mark.parametrize('equity',['72','108'])
@pytest.mark.parametrize('side',[1,-1])
@pytest.mark.parametrize('omit',[(),(0,1)])
def test_actual_selected_sizing_native_lots_minimums_not_half_capital_proxy(equity,side,omit):
    import ast
    from test_e4_c1_manage_only_pure import ROOT,Q
    selected=json.loads((ROOT.parent/'configs/hl-live-v3-dp50.candidate.json').read_text())['candidate']
    assert selected['btc_tp_fractions_initial_qty']==[.2125,.2125,.575] and selected['ema_period']==34
    cls=next(n for n in ast.parse((ROOT/'strategy/wave_overlay.py').read_text()).body if isinstance(n,ast.ClassDef) and n.name=='WaveOverlayStrategy')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_research_btc_entry_multiplier')
    env={};run_ast([method],env)
    owner=N(config=N(research_v3_risk=False,research_h1_b1=False,research_btc_direction_sizing=True,research_btc_drawdown_sizing=False),
        _current_signals=[N(side=side)])
    multiplier=D(str(env['_research_btc_entry_multiplier'](owner)))
    assert multiplier==(D('5.5') if side==1 else D('7.875'))
    # Synthetic metadata/price, not fresh private-account feasibility or venue matching.
    price=D(100000);step=D('.00001');minimum=D(10)
    gross_lots=int(multiplier*D(equity)/price/step)
    fractions=tuple(D(str(v)) for v in selected['btc_tp_fractions_initial_qty'])
    targets={k:int(D(gross_lots)*fraction) for k,fraction in enumerate(fractions[:-1])}
    targets[len(fractions)-1]=gross_lots-sum(targets.values())
    net_lots=sum(value for k,value in targets.items() if k not in omit) if omit else gross_lots
    first_lots=max(1,net_lots//2);cut_lots=net_lots//4
    assert min(first_lots,net_lots-first_lots,cut_lots)>0
    assert all(D(lots)*step*price>=minimum for lots in (first_lots,net_lots-first_lots,cut_lots))
    assert all(D(value)*step*price>=minimum for k,value in targets.items() if k not in omit)
    money_env={'Decimal':D};run_ast(nodes('ops/hl_live_money.py',{'native_lifecycle_feasible'}),money_env)
    instrument=N(size_increment=Q(str(step)),min_quantity=Q(str(step)),min_notional=N(currency='USDC',as_decimal=lambda:minimum))
    assert money_env['native_lifecycle_feasible'](instrument,D(net_lots)*step,price,tp_fractions=fractions,cut_divisor=4)
