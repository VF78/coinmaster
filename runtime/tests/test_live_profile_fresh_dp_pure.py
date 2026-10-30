"""Actual profile/config/DP persistence callbacks, SQLite fixtures; engine zero."""
import ast
from pathlib import Path
from decimal import Decimal as D
from types import SimpleNamespace as N
import pytest
from nautilus_trader.model.objects import Money
from nautilus_trader.model.currencies import USDC
from coinmaster.domain.deposit_protection import DepositProtection
from coinmaster.ops.hl_live_epoch import LiveEpochRuntime
from coinmaster.ops.hl_live_profile import require_profile_deposit_parity
from test_sol_capital_staging_a_pure import dispatch

ROOT=Path(__file__).parents[1]/'coinmaster'

def actual_strategy(runtime,percent):
    # Evaluate the ACTUAL typed-config keyword in the worker constructor.
    tree=ast.parse((ROOT/'ops/hl_live_worker.py').read_text())
    cfg_call=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='WaveOverlayStrategyConfig')
    value=next(k.value for k in cfg_call.keywords if k.arg=='deposit_drawdown_limit_percent')
    amount=eval(compile(ast.Expression(value),'actual_worker_DP_keyword','eval'),{'self':N(profile={'deposit_protection_percent':percent})})
    native_money=Money(D('81.84'),USDC)
    config=dispatch('10000',enabled=False).s.config.__replace__(deposit_drawdown_limit_percent=amount,
        deposit_runtime=runtime,deposit_instance_id='fresh',deposit_account_id='owned',
        deposit_equity_reader=lambda s:native_money.as_decimal(),deposit_initialization_allowed=lambda:True)
    cls=next(n for n in ast.parse((ROOT/'strategy/wave_overlay.py').read_text()).body if isinstance(n,ast.ClassDef) and n.name=='WaveOverlayStrategy')
    constructor=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
    assignment=next(n for n in constructor.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=='_deposit' for t in n.targets))
    load=next(n for n in constructor.body if isinstance(n,ast.If) and ast.unparse(n.test)=='config.deposit_runtime is not None')
    methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in {'_deposit_check','_deposit_equity','_persist_deposit'}]
    body=ast.ClassDef(name='Actual',bases=[],keywords=[],body=methods,decorator_list=[])
    env=dict(Decimal=D,DepositProtection=DepositProtection)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),body],type_ignores=[])),'actual_DP_callbacks','exec'),env)
    s=env['Actual']();s.config=config;s._deposit_storage_failed=False;s.log=N(error=lambda *a:None)
    s.clock=N(timestamp_ns=lambda:100);s.cache=N(positions_open=lambda:[],orders_open=lambda:[],orders_inflight=lambda:[])
    env.update(self=s,config=config)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[assignment,load],type_ignores=[])),'actual_DP_constructor','exec'),env)
    s.deposit_projection=s._deposit.projection;s._validated_live_money=lambda:None
    return s,native_money

@pytest.mark.parametrize('percent',[55,50])
def test_fresh_a55_and_legacy50_normal_first_native_money_hwm_and_sqlite_persistence(tmp_path,percent):
    r=LiveEpochRuntime(tmp_path/'fresh.sqlite','owner',10**20);r.acquire()
    try:
        assert r.deposit_protection_state(instance_id='fresh',account_id='owned') is None
        s,money=actual_strategy(r,percent)
        assert s.config.deposit_drawdown_limit_percent==percent and s._deposit.limit_percent==percent
        assert s._deposit.high_water is None
        assert s._deposit_check() and not s._deposit_storage_failed
        assert s._deposit.high_water==money.as_decimal()
        stored=r.deposit_protection_state(instance_id='fresh',account_id='owned')
        assert stored['drawdown_limit_percent']==percent and D(stored['high_water_equity'])==money.as_decimal()
        if percent==55:
            assert require_profile_deposit_parity({'deposit_protection_percent':55,'retained_equity_floor_fraction':'0.45'},s.deposit_projection())
        else:assert s.deposit_projection()['drawdown_limit_percent']==50
    finally:r.close()

def test_restart_persisted_50_is_authoritative_and_existing_a55_entry_guard_blocks(tmp_path):
    path=tmp_path/'restart.sqlite';r=LiveEpochRuntime(path,'owner',10**20);r.acquire()
    original,_=actual_strategy(r,50);assert original._deposit_check();r.close()
    r=LiveEpochRuntime(path,'owner',10**20);r.acquire()
    try:
        before=r.deposit_protection_state(instance_id='fresh',account_id='owned')
        s,_=actual_strategy(r,55)
        assert s.config.deposit_drawdown_limit_percent==55 and s._deposit.limit_percent==50
        # Run the ACTUAL existing LiveNode increase guard, not a substitute gate.
        tree=ast.parse((ROOT/'ops/hl_live_worker.py').read_text())
        node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_entries_enabled')
        cls=ast.ClassDef(name='ActualNode',bases=[],keywords=[],body=[node],decorator_list=[])
        checked=[]
        def parity(profile,projection):
            checked.append(projection['drawdown_limit_percent'])
            return require_profile_deposit_parity(profile,projection)
        env=dict(require_profile_deposit_parity=parity)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),'actual_live_entry_guard','exec'),env)
        worker=env['ActualNode']();worker.profile={'deposit_protection_percent':55,'retained_equity_floor_fraction':'0.45'};worker.strategy=s;worker.input_readiness=True
        worker._refresh_warmup_readiness=lambda:None
        assert worker._entries_enabled() is False and checked==[50]
        assert r.deposit_protection_state(instance_id='fresh',account_id='owned')==before
        assert s._deposit.high_water==D(before['high_water_equity']) and not s._deposit_storage_failed
    finally:r.close()
