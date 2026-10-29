from decimal import Decimal as D
from pathlib import Path
import ast
import pytest
from coinmaster.domain.deposit_protection import DepositProtection, DAY_NS, UTC_DAILY_CLOSE, OBSERVED_NATIVE_EQUITY_PEAK as PEAK
from test_qualification_dp_pure import controller


def test_peak_threshold_is_exact_and_daily_legacy_is_unchanged():
    daily=DepositProtection(limit_percent=55);peak=DepositProtection(limit_percent=55,high_water_basis=PEAK)
    for state in (daily,peak):state.initialize(D("100"),DAY_NS+1)
    for value in ("150","100"):
        for state in (daily,peak):assert not state.observe(D(value),DAY_NS+2)[1]
    assert daily.high_water==100 and peak.high_water==150
    assert peak.observe(D("67.5"),DAY_NS+3)==(True,True)
    assert not daily.observe(D("67.5"),DAY_NS+3)[1]
    another=DepositProtection(limit_percent=55,high_water_basis=PEAK);another.initialize(D("100"),DAY_NS+1)
    another.observe(D("250"),DAY_NS+2);assert another.observe(D("100"),DAY_NS+3)[1]


def test_peak_eligibility_unknown_and_monotonicity():
    state=DepositProtection(high_water_basis=PEAK);state.initialize(D("100"),DAY_NS+1)
    assert state.observe(D("200"),DAY_NS+2,allow_high_water=False)==(False,False)
    assert state.high_water==100
    assert state.observe(None,DAY_NS+3)==(False,False)
    for value in ("101","150","120","200"):
        previous=state.high_water;state.observe(D(value),DAY_NS+4)
        assert state.high_water==max(previous,D(value))


def test_durable_basis_reload_rejects_mismatch_without_reset():
    state=DepositProtection(high_water_basis=PEAK);state.initialize(D("100"),DAY_NS+1);state.observe(D("150"),DAY_NS+2)
    row=state.durable();assert DepositProtection.from_durable(row,high_water_basis=PEAK).high_water==150
    with pytest.raises(ValueError,match="BASIS_MISMATCH"):DepositProtection.from_durable(row)
    old=DepositProtection();old.initialize(D("100"),DAY_NS+1);legacy=old.durable();legacy.pop("high_water_basis")
    assert DepositProtection.from_durable(legacy).high_water_basis==UTC_DAILY_CLOSE
    with pytest.raises(ValueError,match="BASIS_MISMATCH"):DepositProtection.from_durable(legacy,high_water_basis=PEAK)
    assert row==state.durable()


def test_actual_strategy_same_ns_peaks_persist_unique_keys_before_permission(tmp_path):
    obj,store,equity,clock,positions,calls=controller(tmp_path);assert obj._deposit_check()
    for value in ("110","120","150"):
        equity[0]=D(value);assert obj._deposit_check()
        saved=store.deposit_protection_state(instance_id=store.owner,account_id="SIM-001")
        assert saved["high_water_equity"]==value and saved["high_water_basis"]==PEAK
    rows=store.db.execute("SELECT event_key, action FROM paper_deposit_audit").fetchall()
    peaks=[key for key,action in rows if action=="HIGH_WATER"]
    assert len(peaks)==len(set(peaks))==3
    assert not obj._deposit_storage_failed and not calls
    equity[0]=None;assert not obj._deposit_check() and not obj._deposit.latched
    store.close()


def test_btc_only_metadata_does_not_change_SOL_or_legacy(tmp_path):
    from coinmaster.research.qualification_policy import research_qualification
    from coinmaster.ops.paper import PaperRuntime
    metadata={"assets":[{"name":"BTC","szDecimals":5},{"name":"SOL","szDecimals":2}]}
    store=PaperRuntime(tmp_path/"mode.sqlite","mode",120_000_000_000,deposit_currency="USDT")
    kwargs,lots=research_qualification("live_qualification","btc_lot_diagnostic",metadata,store,lambda _:D("100"),"P1SIM-001")
    assert kwargs["deposit_high_water_basis"]==PEAK and kwargs["deposit_drawdown_limit_percent"]==55
    assert lots["BTC"]==dict(step="0.00001",min_quantity="0.00001",size_precision=5)
    assert lots["SOL"]==dict(step="0.1",min_quantity=None,size_precision=1)
    assert research_qualification("legacy_reference","legacy_bybit",None,None,None,"")==({},{})
    store.close()


def test_actual_strategy_storage_failure_never_grants_increase(tmp_path):
    obj,store,equity,clock,positions,calls=controller(tmp_path);assert obj._deposit_check()
    def fail(**kwargs):raise RuntimeError("DTO_STORE_FAILURE")
    store.save_deposit_protection=fail;equity[0]=D("150")
    assert not obj._deposit_check() and obj._deposit_storage_failed and not obj._deposit.latched
    assert not calls
    store.close()


def test_actual_fill_eligibility_cannot_observe_mixed_cash_then_real_quote_observes(tmp_path):
    from types import SimpleNamespace as NS,MethodType
    obj,store,equity,clock,positions,calls=controller(tmp_path);assert obj._deposit_check()
    source=Path(__file__).parents[1]/"coinmaster/strategy/wave_overlay.py"
    tree=ast.parse(source.read_text());names={"on_order_filled","_entries_enabled","_deposit_health","on_quote_tick"}
    functions=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in names]
    namespace=dict(OrderFilled=object,QuoteTick=object,Decimal=D)
    exec(compile(ast.fix_missing_locations(ast.Module(body=functions,type_ignores=[])),"actual_fill_eligibility_source","exec"),namespace)
    for name in names:setattr(obj,name,MethodType(namespace[name],obj))
    reads=[];obj.config.deposit_equity_reader=lambda _:reads.append("NATIVE_READER") or equity[0]
    obj.config.research_sol_risk_first=None;obj.config.tp_fee_floor_v1=False;obj.config.research_zero_retrace=False
    obj.config.research_v0_execution_repairs=True;obj.config.research_v0_selective_lifecycle_repairs=True
    obj.config.entries_enabled=True;obj.config.entries_gate=None
    obj._research_protect_latch=None;obj.terminal_lifecycle={};obj._seen_trade_ids=set()
    for name in ("_v3_orders","_deposit_exit_orders","_liquidation_orders","_terminal_order_ids","_forced_close_orders"):setattr(obj,name,set())
    intent=NS(action="BTC_REDUCE",reason="BTC_TP")
    obj._pending_by_order={"tp":intent};obj.cache.order=lambda _:NS(is_closed=True)
    for name in ("_c1_native_fill","_record_native_fill","_record_fill_audit","_carry_native_fill","_h1_native_fill","_risk_first_sol_fill","_split_native_fill","_cover_native_fill","_apply_confirmed_domain_fill","_after_domain_fill","_terminal_submission"):
        setattr(obj,name,lambda *a,**k:None)
    # The actual selected advancement method queues work; its eligibility target is exercised here.
    advanced=[];obj._advance_current_day=lambda:advanced.append(obj._entries_enabled())
    before=store.deposit_protection_state(instance_id=store.owner,account_id="SIM-001")
    equity[0]=D("10000") # Deliberately inconsistent fill-window DTO; must never be read here.
    obj.on_order_filled(NS(trade_id="fill",client_order_id="tp",ts_event=clock[0],last_qty=1,last_px=1))
    assert advanced==[True] and not reads and obj._deposit.high_water==100 and not obj._deposit.latched
    assert store.deposit_protection_state(instance_id=store.owner,account_id="SIM-001")==before
    obj.config.research_v0_deferred_selective_zero_tp=False
    obj._risk_first_sol_stop=lambda reason:None
    obj.config.research_residual_recovery=False;obj.config.research_h1_b1=None;obj.config.btc_id="BTC";obj.config.sol_id="SOL"
    obj._v3_reduction=None;obj._forced_close_reason="MANDATORY";obj._latest_seen_session=None
    obj._retry_deferred_daily_decision=lambda:None;obj._submit_forced_close_on_quote=lambda tick:None
    equity[0]=D("150");obj.on_quote_tick(NS(ts_event=clock[0],instrument_id="SOL"))
    assert reads==["NATIVE_READER"] and obj._deposit.high_water==150
    equity[0]=D("67.5");obj.on_quote_tick(NS(ts_event=clock[0]+1,instrument_id="SOL"))
    assert obj._deposit.latched and obj._deposit.trigger["high_water_equity"]=="150"
    store.close()


def test_selected_fill_callback_queue_path_and_DP_observation_sites_are_explicit():
    tree=ast.parse((Path(__file__).parents[1]/"coinmaster/strategy/wave_overlay.py").read_text())
    funcs={n.name:n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)}
    calls=lambda fn:{n.func.attr for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=="self"}
    assert "_advance_current_day" in calls(funcs["on_order_filled"])
    assert "_entries_enabled" in calls(funcs["_advance_current_day"])
    assert not ({"submit_order","_submit_intent","_tier_allows_increase","_deposit_check"}&calls(funcs["_advance_current_day"]))
    assert "_deposit_health" in calls(funcs["_entries_enabled"])
    assert "_deposit_check" not in calls(funcs["_entries_enabled"])
    assert not calls(funcs["_deposit_health"])
    sites={name for name,fn in funcs.items() if "_deposit_check" in calls(fn)}
    assert sites=={"on_quote_tick","_on_deposit_timer","_tier_allows_increase","submit_order"}
