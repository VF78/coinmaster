"""Existing canonical INIT with explicit actual-USDC policy; no native constructors."""
import ast
from pathlib import Path
from dataclasses import replace
from decimal import Decimal as D
from types import SimpleNamespace as N
import pytest
from test_e4_c1_manage_only_pure import code, ROOT, run_ast
from test_e4_c1_input_bridge_pure import fresh_init_fixture

POLICY='ACTUAL_AVAILABLE_USDC_AT_FRESH_FLAT_INIT'

def worker_preflight(runtime,profile,amount):
    # Execute the real constructor prefix through qualified preflight and both
    # balance guards, stopping before credential material or node construction.
    from coinmaster.ops.hl_live_profile import actual_initial_capital,initial_capital_limit
    tree=ast.parse((ROOT/'ops/hl_live_worker.py').read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='HyperliquidLiveNode')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
    body=[]
    for statement in method.body:
        if isinstance(statement,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='record' for t in statement.targets):break
        body.append(statement)
    method.name='preflight';method.body=body+[ast.Return(value=ast.Name(id='equity',ctx=ast.Load()))]
    env=dict(Path=Path,__file__=str(ROOT/'ops/hl_live_worker.py'),actual_initial_capital=actual_initial_capital,
        initial_capital_limit=initial_capital_limit,load_live_profile=lambda *args:profile,
        ReadinessInfoBudget=lambda:N(),check_live_credential=lambda *args,**kw:D(amount))
    run_ast([method],env)
    approval=dict(authorization='START_LIVE_E4_C1',start_approved=True,orders_approved=True,profile_sha256='synthetic')
    return env['preflight'](N(),instance=N(mode='live',instance_id='hl-stageg-live'),candidate=N(),state=runtime,
        credential_path=Path('/synthetic-never-read'),fingerprint_path=Path('/synthetic-never-read'),order_approval=approval)

def actual(code,tmp_path,amount):
    s,r,view,now=fresh_init_fixture(code,tmp_path)
    s._active_c1_authorized=True;s.config.live_initial_capital_policy=POLICY
    s.config.live_initial_capital_limit_usdc='82'
    s.config.live_initial_capital_limit_usdc='0' # explicit policy never reads a numeric maximum
    account=s.cache.account_for_venue(s.config.btc_id.venue)
    account.balance_total=lambda currency:N(as_decimal=lambda:D(amount))
    view=replace(view,equity=D(amount),raw_usd=D(0),free_collateral=D(amount))
    return s,r,view,now

@pytest.mark.parametrize('amount',['61.25','81.84','108.33'])
def test_preflight_to_INIT_movement_uses_actual_USDC_once_with_atomic_H_and_restart(code,tmp_path,amount):
    s,r,view,now=actual(code,tmp_path,amount)
    try:
        profile=dict(profile_id='E4_C1_ACTIVE_SELECTED',initial_capital_policy=POLICY,input_readiness=True,profile_sha256='synthetic')
        assert worker_preflight(r,profile,'82')==D(82)
        assert worker_preflight(r,profile,'108.33')==D('108.33')
        # Actual constructor preflight and qualified INIT may see different USDC.
        s.initialize_clean_flat_c1_epoch(view,intent='INITIALIZE_FRESH_C1_EPOCH',now_ns=now,
            history_anchor_ms=0,cashflow_page=dict(rows=[],start_ms=0,end_ms=1,expected_cursor=None,complete=True))
        assert r.c1_initialization()['initial_equity']==amount and s._c1_peak==D(amount)
        original=r.strategy_checkpoint()
        with pytest.raises(ValueError):
            s.initialize_clean_flat_c1_epoch(view,intent='INITIALIZE_FRESH_C1_EPOCH',now_ns=now,history_anchor_ms=0)
        assert r.strategy_checkpoint()==original
        assert not r.record_cashflow_page(dict(rows=[dict(time=2,hash='later',delta=dict(type='deposit',usdc='10'))],
            start_ms=1,end_ms=2,expected_cursor={'end_ms':1},complete=True))
        assert r.cashflow_quarantined() and s._c1_peak==D(amount)
        path=tmp_path/'fresh.sqlite';r.close();r=code.Runtime(path,'fresh-owner',10**20);r.acquire()
        assert r.c1_initialization()['initial_equity']==amount and not r._fresh_c1_epoch_active
        assert r.strategy_checkpoint()==original
    finally:r.close()

@pytest.mark.parametrize('fault',['zero','hold','free','stale','revision','generation','nonflat','inflight','cashflow','policy','inactive','nonvirgin','identity'])
def test_actual_initial_policy_preserves_all_native_and_virgin_barriers(code,tmp_path,fault):
    s,r,view,now=actual(code,tmp_path,'108.33')
    try:
        if fault=='zero':view=replace(view,equity=D(0),free_collateral=D(0))
        elif fault=='hold':view=replace(view,margin_used=D(1))
        elif fault=='free':view=replace(view,free_collateral=D(100))
        elif fault=='stale':now+=10_000_000_000
        elif fault=='revision':r._bump_native_revision();r.db.commit()
        elif fault=='generation':s._fresh_init_generation_validator=lambda:False
        elif fault=='nonflat':s.cache.positions_open=lambda:[N()]
        elif fault=='inflight':s.cache.orders_inflight=lambda:[N()]
        elif fault=='cashflow':r.db.execute("INSERT INTO live_evidence_cursors VALUES ('external_cashflow_quarantine','{}')");r.db.commit()
        elif fault=='policy':s.config.live_initial_capital_policy='unknown'
        elif fault=='inactive':s._active_c1_authorized=False
        elif fault=='nonvirgin':r.record_submission(client_order_id='unknown',intent_id='unknown',episode_id='unknown',action='BTC_ENTRY',instrument_id=str(s.config.btc_id),quantity='1',reduce_only=False)
        elif fault=='identity':view=replace(view,account_mode='unifiedAccount')
        with pytest.raises((ValueError,RuntimeError)):
            s.initialize_clean_flat_c1_epoch(view,intent='INITIALIZE_FRESH_C1_EPOCH',now_ns=now,
                history_anchor_ms=0,cashflow_page=dict(rows=[],start_ms=0,end_ms=1,expected_cursor=None,complete=True))
        assert r.c1_initialization() is None and not r._fresh_c1_epoch_active
    finally:r.close()

def test_legacy_numeric_limit_still_denies_larger_initial_deposit(code,tmp_path):
    s,r,view,now=fresh_init_fixture(code,tmp_path)
    s._active_c1_authorized=True;s.config.live_initial_capital_limit_usdc='81'
    try:
        with pytest.raises(RuntimeError,match='LIVE_INITIAL_CAPITAL_LIMIT_EXCEEDED'):
            worker_preflight(r,dict(profile_id='E4_C1_ACTIVE_SELECTED',initial_capital_usdc='81',input_readiness=True,profile_sha256='synthetic'),'82')
        with pytest.raises(ValueError,match='LIVE_INITIAL_CAPITAL_LIMIT_EXCEEDED'):
            s.initialize_clean_flat_c1_epoch(view,intent='INITIALIZE_FRESH_C1_EPOCH',now_ns=now,
                history_anchor_ms=0,cashflow_page=dict(rows=[],start_ms=0,end_ms=1,expected_cursor=None,complete=True))
        assert r.c1_initialization() is None
    finally:r.close()
