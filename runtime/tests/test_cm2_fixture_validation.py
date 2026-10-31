"""Enum/report-only regressions; no native engine/account/order construction."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import pytest
from nautilus_trader.model.enums import OrderStatus
from coinmaster.research.cm2_fixture_validation import canceled_native_order,derive_validation,fixture_progress

def report():
    return {"fixture_id":"cm2-connected-native-v1","engine_constructors":1,
        "execution_model_id":"CM2_FIXTURE_NATIVE_STOCK_LIMIT_PARTIAL_PLUS_QUALIFIED_MARKET_FULLFILL",
        "interval":{"start_ns":1725148800000000000,"end_ns":1725181200000000000},
        "status":"FAIL","checks":{"native_partial_fill":True,"native_partial_terminal_canceled":False,
            "exact_independent_fees":True,"exact_independent_terminal_cash":True,"native_terminal_flat":True},
        "native_partial_orders":[{"client_order_id":"actual-native-id","filled":"5.00","requested":"300.00","status":"8"}],
        "coverage_unknown":["RESTART_REPLAY_NATIVE_NOT_TESTED"]}

def derive(raw):
    data=json.dumps(raw).encode()
    return derive_validation(data,hashlib.sha256(data).hexdigest())

def test_actual_pinned_enum_string_is_numeric_and_identity_classifies():
    assert OrderStatus(8) == OrderStatus.CANCELED
    assert OrderStatus(8).name=="CANCELED" and str(OrderStatus.CANCELED)=="8"
    assert canceled_native_order(SimpleNamespace(status=OrderStatus.CANCELED))
    assert not canceled_native_order(SimpleNamespace(status=OrderStatus.FILLED))

def test_derived_receipt_preserves_original_failure_and_evidence():
    raw=report();before=deepcopy(raw)
    result=derive(raw)
    assert raw==before
    assert result["original_status"]=="FAIL" and result["original_checks"]["native_partial_terminal_canceled"] is False
    assert result["corrected_result"] is True and result["new_native_engine_constructions"]==0
    assert result["engineering_acceptance"] is False
    assert result["status"]=="DERIVED_ENUM_CHECK_CONFIRMED_ENGINEERING_NOT_ACCEPTED"
    assert result["native_enum_evidence"][0]["pinned_status_name"]=="CANCELED"

def test_hash_mismatch_is_rejected():
    with pytest.raises(ValueError,match="HASH_MISMATCH"):
        derive_validation(json.dumps(report()).encode(),"0"*64)

def test_economic_failure_cannot_be_reclassified():
    raw=report();raw["checks"]["exact_independent_terminal_cash"]=False
    with pytest.raises(ValueError,match="OTHER_NATIVE_CHECK_FAILURE"): derive(raw)

@pytest.mark.parametrize("change",[{"status":str(OrderStatus.FILLED.value)},{"filled":"0.00"},{"filled":"300.00"}])
def test_missing_actual_canceled_partial_evidence_is_rejected(change):
    raw=report();raw["native_partial_orders"][0].update(change)
    with pytest.raises(ValueError,match="NO_ACTUAL_NATIVE_CANCELED_PARTIAL"): derive(raw)


def event(minute,instrument,side,qty,price):
    return {"fill_ns":str(1725148800000000000+minute*60_000_000_000),
        "instrument":instrument+"-USD-PERP.HYPERLIQUID","order_side":side,"qty":qty,"px":price}

def test_short_only_harvest_and_staging_intents_are_not_native_progress():
    fills=[event(2,"BTC","BUY","40","1000"),event(121,"SOL","SELL","300","100"),
           event(181,"SOL","BUY","62.22","90"),event(241,"BTC","SELL","40","950"),
           event(301,"BTC","SELL","31.04184","950"),event(361,"BTC","BUY","15.52092","880")]
    audit=[{"reason":"SOL_BEFORE_ORDINARY_BTC_REDUCTION","parent":1} for _ in range(118)]
    p=fixture_progress(fills,audit)
    assert p["actual_short_positive_harvest"] is True
    assert p["actual_long_positive_harvest"] is False
    assert p["confirmed_sol_before_long_harvest"] is False
    assert p["bounded_long_harvest_progress"] is False
    assert p["ordinary_staging_no_endless_loop"] is False

def test_confirmed_native_event_order_and_guard_demonstrate_bounded_progress():
    fills=[event(2,"BTC","BUY","40","1000"),event(121,"SOL","SELL","300","100"),
           event(181,"SOL","BUY","62.23","90"),event(182,"BTC","SELL","20","1070"),
           event(241,"BTC","SELL","20","950"),event(301,"BTC","SELL","44","950"),
           event(361,"BTC","BUY","22","880")]
    audit=[{"reason":"SOL_BEFORE_ORDINARY_BTC_REDUCTION","parent":1} for _ in range(2)]
    p=fixture_progress(fills,audit)
    assert all(p[key] is True for key in ("actual_long_positive_harvest","actual_short_positive_harvest",
        "confirmed_sol_before_long_harvest","bounded_long_harvest_progress","ordinary_staging_no_endless_loop"))
