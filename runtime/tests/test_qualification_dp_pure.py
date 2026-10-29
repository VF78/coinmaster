"""Engine-free actual-controller/config/metadata regressions; no native fill proof."""
import ast
import json
import sys
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from coinmaster.domain.deposit_protection import DAY_NS, DepositProtection
from coinmaster.ops.paper import PaperRuntime
from coinmaster.research.qualification_policy import metadata_lot_constraints, native_marked_deposit_equity, research_qualification


def runtime(tmp_path, currency="USDT"):
    return PaperRuntime(tmp_path/"dp.sqlite", "qualification", 120_000_000_000, deposit_currency=currency)


def controller(tmp_path):
    source=Path(__file__).parents[1]/"coinmaster/strategy/wave_overlay.py"
    names={"_deposit_equity","_deposit_check","_persist_deposit","_start_deposit_exit","_reconcile_deposit_flat"}
    functions=[n for n in ast.walk(ast.parse(source.read_text())) if isinstance(n,ast.FunctionDef) and n.name in names]
    module=ast.Module(body=[ast.ClassDef(name="ActualController",bases=[],keywords=[],body=functions,decorator_list=[])],type_ignores=[])
    namespace={"Decimal":D};exec(compile(ast.fix_missing_locations(module),"actual_DP_controller_AST","exec"),namespace)
    obj=namespace["ActualController"]();store=runtime(tmp_path);equity=[D("100")];clock=[DAY_NS+1]
    kwargs,_=research_qualification("live_qualification","legacy_bybit",None,store,lambda _s:equity[0],"SIM-001")
    obj.config=NS(deposit_high_water_allowed=None,**kwargs);obj._deposit=DepositProtection(limit_percent=kwargs["deposit_drawdown_limit_percent"],currency=kwargs["deposit_currency"])
    obj.clock=NS(timestamp_ns=lambda:clock[0]);positions=[];orders=[]
    obj.cache=NS(positions_open=lambda:positions,orders_open=lambda:orders,orders_inflight=lambda:[])
    calls=[];obj.log=NS(error=lambda _message:None);obj._deposit_storage_failed=False;obj._deposit_exit_started=False
    obj._split_stop=lambda reason:calls.append(reason);obj._accepted_reductions={};obj._discard_queued_intents=lambda predicate:None
    obj._mandatory_sol_exit=None;obj._forced_close_reason=None;obj._liquidating=False;obj.is_exiting=lambda:False
    obj.market_exit=lambda:calls.append("DTO_NATIVE_EXIT_REQUEST_ONLY")
    obj._domain=NS(episode=None);obj._pending_by_order={};obj._c1_state={"state":"RELEASED"}
    return obj,store,equity,clock,positions,calls


def test_existing_global_controller_healthy_init_utc_close_then_SOL_only_RELEASED_trip(tmp_path):
    obj,store,equity,clock,positions,calls=controller(tmp_path)
    assert obj._deposit_check() and obj._deposit.limit_percent==55 and obj._deposit.high_water==D("100")
    for value in ("101","99","100"):
        equity[0]=D(value);clock[0]+=60_000_000_000;assert obj._deposit_check()
    equity[0]=D("120");clock[0]=2*DAY_NS-60_000_000_000;assert obj._deposit_check()
    equity[0]=D("119");clock[0]=2*DAY_NS;assert obj._deposit_check()
    assert obj._deposit.high_water==D("120") and not obj._deposit.daily_sample_missed and not calls
    # Controller never consults C1 RELEASED or BTC-domain ownership.
    positions.append(NS(instrument_id="SOL"));equity[0]=D("54");clock[0]+=60_000_000_000
    assert not obj._deposit_check() and obj._deposit.latched
    assert calls==["DP","DTO_NATIVE_EXIT_REQUEST_ONLY"] and obj._c1_state=={"state":"RELEASED"}
    assert not obj._deposit_check() and len(calls)==2
    assert not obj._reconcile_deposit_flat()
    positions.clear()  # DTO-only terminal state; never a native cache mutation.
    assert obj._reconcile_deposit_flat() and store.entry_control_state()=="PAUSED"
    saved=store.deposit_protection_state(instance_id=store.owner,account_id="SIM-001")
    assert saved["drawdown_limit_percent"]==55 and saved["latched"] and saved["exit_state"]=="TRIPPED_FLAT"
    assert DepositProtection.from_durable(saved,currency="USDT").projection()["currency"]=="USDT"
    store.close()


def test_unknown_equity_blocks_but_does_not_fake_trigger(tmp_path):
    obj,store,equity,clock,positions,calls=controller(tmp_path);assert obj._deposit_check()
    equity[0]=None;clock[0]+=60_000_000_000
    assert not obj._deposit_check() and not obj._deposit.latched and not calls
    store.close()


def test_currency_store_identity_default_live_unchanged_and_mismatch_rejected(tmp_path):
    live=PaperRuntime(tmp_path/"live.sqlite","live",120_000_000_000)
    assert live.deposit_currency=="USDC" and DepositProtection().projection()["currency"]=="USDC"
    with pytest.raises(ValueError,match="CURRENCY_MISMATCH"):
        research_qualification("live_qualification","legacy_bybit",None,live,lambda s:D("100"),"SIM-001")
    state=DepositProtection(limit_percent=55,currency="USDT");state.initialize(D("100"),DAY_NS+1)
    store=runtime(tmp_path);store.save_deposit_protection(instance_id="qualification",account_id="SIM-001",action="INITIALIZE",event_key="init",state=state.durable(),ts_ns=DAY_NS+1)
    store.close();wrong=PaperRuntime(tmp_path/"dp.sqlite","qualification",120_000_000_000)
    with pytest.raises(ValueError,match="IDENTITY_MISMATCH"):wrong.deposit_protection_state(instance_id="qualification",account_id="SIM-001")
    wrong.close();live.close()


def test_qualification_never_silently_disables_DP_and_legacy_is_explicit(tmp_path):
    assert research_qualification("legacy_reference","legacy_bybit",None,None,None,"")==({}, {})
    with pytest.raises(ValueError,match="RUNTIME_READER_REQUIRED"):
        research_qualification("live_qualification","legacy_bybit",None,None,None,"SIM-001")
    store=runtime(tmp_path)
    with pytest.raises(ValueError,match="LEGACY_REFERENCE"):
        research_qualification("legacy_reference","legacy_bybit",None,store,lambda s:D("100"),"SIM-001")
    store.close()


def test_public_HL_precision_metadata_drives_BTC_and_SOL_without_changing_legacy_fixture():
    metadata={"assets":[{"name":"BTC","szDecimals":5},{"name":"SOL","szDecimals":2}]}
    result=metadata_lot_constraints(metadata)
    assert result["BTC"]["step"]=="0.00001" and result["SOL"]["step"]=="0.01"
    metadata["assets"][0]["szDecimals"]=3
    with pytest.raises(ValueError,match="PRECISION_5_REQUIRED"):metadata_lot_constraints(metadata)


def test_reader_delegates_existing_native_equity_only_when_marks_complete_current_currency():
    btc=NS(venue="SIM");sol=object();marks={id(btc):None}
    # Hashable simple identifiers with venue semantics.
    class ID(str):venue="SIM"
    btc=ID("BTC");sol=ID("SOL");calls=[]
    obj=NS(config=NS(btc_id=btc,sol_id=sol,max_mark_age_ns=120,deposit_currency="USDT"),clock=NS(timestamp_ns=lambda:100),
        _latest_marks={btc:NS(ts_event=90),sol:NS(ts_event=90)},cache=NS(account_for_venue=lambda _:NS(balances_total=lambda:{"USDT":object()}),positions_open=lambda:[]),_v3_equity=lambda:(calls.append("EXISTING_NATIVE_HELPER") or D("100")))
    assert native_marked_deposit_equity(obj)==D("100") and len(calls)==1
    obj._latest_marks[sol].ts_event=89;assert native_marked_deposit_equity(obj) is None and len(calls)==1
    obj._latest_marks[sol].ts_event=90;obj.config.deposit_currency="USDC"
    with pytest.raises(ValueError,match="CURRENCY_MISMATCH"):native_marked_deposit_equity(obj)


def test_actual_config_call_forwards_selected_flags_and_profile_DP55_metadata(tmp_path):
    tree=ast.parse((Path(__file__).parents[1]/"coinmaster/research/native_baseline.py").read_text())
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="run_native_diagnostic")
    call=next(n for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="WaveOverlayStrategyConfig")
    for flag in ("research_c1_first_fresh_h4","research_c1_btc_postcut_d1"):
        value=next(k.value for k in call.keywords if k.arg==flag)
        assert eval(compile(ast.Expression(value),"actual_config_flag_AST","eval"),{flag:True}) is True
    assert any(k.arg is None and isinstance(k.value,ast.Name) and k.value.id=="qualification_kwargs" for k in call.keywords)
    assert any(isinstance(n,ast.Assign) and ast.unparse(n.value)=="TimeInForce.IOC" and "market_exit_time_in_force" in ast.unparse(n.targets[0]) for n in ast.walk(fn))
    store=runtime(tmp_path);kwargs,_=research_qualification("live_qualification","legacy_bybit",None,store,lambda s:D("100"),"SIM-001")
    serial={k:v for k,v in kwargs.items() if isinstance(v,(str,int,bool))}
    restored=json.loads(json.dumps(serial));assert restored["deposit_drawdown_limit_percent"]==55 and restored["deposit_check_interval_secs"]==60 and restored["deposit_currency"]=="USDT"
    store.close()
