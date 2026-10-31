"""Read-only CM2 fixture report classification. Never constructs an engine."""
from decimal import Decimal
import argparse
import hashlib
import json
from pathlib import Path

def canceled_native_order(order):
    """Compare the actual pinned enum; its str representation is numeric."""
    from nautilus_trader.model.enums import OrderStatus
    return order.status == OrderStatus.CANCELED

def fixture_progress(fills, audit):
    """Check actual persisted fixture event progress, not presence of an intent."""
    D=Decimal
    start=1725148800000000000
    hour=3_600_000_000_000
    minute=60_000_000_000
    btc="BTC-USD-PERP.HYPERLIQUID"
    sol="SOL-USD-PERP.HYPERLIQUID"
    longs=[(i,f) for i,f in enumerate(fills) if f["instrument"]==btc and f["order_side"]=="SELL"
           and start+3*hour <= int(f["fill_ns"]) < start+4*hour and D(f["px"])==D(1070)]
    short_entry=sum((D(f["qty"]) for f in fills if f["instrument"]==btc and f["order_side"]=="SELL"
                     and start+5*hour <= int(f["fill_ns"]) < start+6*hour and D(f["px"])==D(950)),D(0))
    short_partial=sum((D(f["qty"]) for f in fills if f["instrument"]==btc and f["order_side"]=="BUY"
                       and start+6*hour <= int(f["fill_ns"]) < start+7*hour and D(f["px"])==D(880)),D(0))
    staged=[r for r in audit if r["reason"]=="SOL_BEFORE_ORDINARY_BTC_REDUCTION" and r["parent"]==1]
    long_qty=sum((D(f["qty"]) for _,f in longs),D(0))
    confirmed=False
    if longs:
        index,first=longs[0]
        prior_sol=[f for f in fills[:index] if f["instrument"]==sol]
        held_sol=sum(((D(1) if f["order_side"]=="BUY" else D(-1))*D(f["qty"]) for f in prior_sol),D(0))
        reduced=any(f["order_side"]=="BUY" and D(f["px"])==D(90) for f in prior_sol)
        # Fixed fixture parent starts40BTC; evaluate guard at native BTC fill.
        remaining=D(40)-D(first["qty"])
        confirmed=reduced and abs(held_sol)*D(90)<=remaining*D(1070)
    return {"actual_long_positive_harvest":long_qty==D(20),
            "actual_short_positive_harvest":D(0)<short_partial<short_entry,
            "confirmed_sol_before_long_harvest":confirmed,
            "bounded_long_harvest_progress":bool(longs) and int(longs[0][1]["fill_ns"])<=start+3*hour+3*minute,
            "ordinary_staging_no_endless_loop":0<len(staged)<=4,
            "long_harvest_actual_quantity":str(long_qty),"long_staging_callbacks":len(staged)}

def derive_validation(raw_bytes: bytes, expected_sha256: str) -> dict:
    actual=hashlib.sha256(raw_bytes).hexdigest()
    if actual != expected_sha256:
        raise ValueError("UNCHANGED_NATIVE_REPORT_HASH_MISMATCH")
    raw=json.loads(raw_bytes)
    from nautilus_trader import __version__
    from nautilus_trader.model.enums import OrderStatus
    if __version__ != "1.231.0":
        raise ValueError("PINNED_NATIVE_ENUM_VERSION_REQUIRED")
    if raw.get("fixture_id")!="cm2-connected-native-v1" or raw.get("engine_constructors")!=1:
        raise ValueError("UNEXPECTED_NATIVE_FIXTURE_REPORT")
    if raw.get("execution_model_id")!="CM2_FIXTURE_NATIVE_STOCK_LIMIT_PARTIAL_PLUS_QUALIFIED_MARKET_FULLFILL":
        raise ValueError("UNEXPECTED_FIXTURE_EXECUTION_MODEL")
    if raw.get("interval")!={"start_ns":1725148800000000000,"end_ns":1725181200000000000}:
        raise ValueError("UNEXPECTED_FIXTURE_INTERVAL")
    checks=raw.get("checks",{})
    corrected="native_partial_terminal_canceled"
    if raw.get("status")!="FAIL" or checks.get(corrected) is not False:
        raise ValueError("EXPECTED_ORIGINAL_CLASSIFICATION_FAILURE_REQUIRED")
    if not checks or any(value is not True for key,value in checks.items() if key!=corrected):
        raise ValueError("OTHER_NATIVE_CHECK_FAILURE_NOT_REPORT_ONLY")
    evidence=[]
    for order in raw.get("native_partial_orders",[]):
        # These are persisted actual native cache fields from fixture engine end.
        filled=Decimal(order["filled"])
        requested=Decimal(order["requested"])
        status=OrderStatus(int(order["status"]))
        if Decimal(0) < filled < requested and status == OrderStatus.CANCELED:
            evidence.append({"client_order_id":order["client_order_id"],"requested":order["requested"],
                "filled":order["filled"],"persisted_status":order["status"],
                "pinned_status_value":status.value,"pinned_status_name":status.name})
    if not evidence:
        raise ValueError("NO_ACTUAL_NATIVE_CANCELED_PARTIAL_EVIDENCE")
    progress=fixture_progress(raw.get("actual_native_fill_audit",[]),raw.get("native_adapter",{}).get("cm2",{}).get("audit",[]))
    return {"status":"DERIVED_ENUM_CHECK_CONFIRMED_ENGINEERING_NOT_ACCEPTED","source_report_sha256":actual,
        "engineering_acceptance":False,"additional_liveness_checks":progress,
        "liveness_status":"FAIL_OR_UNPROVEN_REQUIRES_REMEDIATED_NATIVE_FIXTURE",
        "original_status":raw["status"],"original_checks":checks,
        "corrected_check":corrected,"corrected_result":True,
        "reason":"PINNED_NATIVE_ENUM_CANCELED_IS_VALUE8_AND_STR8_NOT_NAME_SUBSTRING",
        "native_version":__version__,"native_enum_evidence":evidence,
        "all_other_checks_preserved_true":True,"new_native_engine_constructions":0,
        "original_engine_constructors":raw["engine_constructors"],
        "original_report_modified":False,"original_failure_and_budget_spend_preserved":True,
        "economic_or_fill_change":False,"coverage_unknown":raw.get("coverage_unknown",[]),
        "acceptance_scope":"ENUM_INTERPRETATION_ONLY_ORIGINAL_E01_REMAINS_FAILED_AND_SPENT"}

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--report",type=Path,required=True)
    parser.add_argument("--expected-sha256",required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args(argv)
    result=derive_validation(args.report.read_bytes(),args.expected_sha256)
    result["source_report_path"]=str(args.report.resolve())
    # Exclusive create preserves any previous derived evidence too.
    with args.out.open("x") as stream:
        stream.write(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(result["status"])

if __name__=="__main__": main()
