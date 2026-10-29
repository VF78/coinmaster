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
