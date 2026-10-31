"""Synthetic persisted-native watermark proof; no engine or real financial data."""
from decimal import Decimal as D,localcontext,ROUND_HALF_EVEN
from pathlib import Path
import copy,csv,gzip,json
import pytest
from coinmaster.research.cm2_committed_validation import scan_native,native_reference,MIN

SOURCE=Path(__file__).parents[1]/"coinmaster/research/minute_risk.py"

@pytest.fixture(autouse=True)
def decimal_context():
    with localcontext() as ctx:ctx.prec=28;ctx.rounding=ROUND_HALF_EVEN;yield

def fixture(directory,change=None):
    rows=[]
    def add(kind,ns,cash,epoch=0,state=None,identity=None,retention=None,delta=None):
        r={"sequence":len(rows)+1,"kind":kind,"event_ns":str(ns),"receipt_ns":str(ns),
           "cash":str(cash),"equity":str(cash),"positions":[],"native_positions_sha256":"native-hash",
           "epoch":epoch,"state_epoch":epoch if state is None else state,"native_id":identity,"mark_available_ns":str(ns)}
        if retention:r["prior_source_retention"]=retention
        if delta is not None:r["native_cash_delta"]=str(delta)
        rows.append(r);return r
    add("PREQUOTE_DIRECT_NATIVE",MIN,1000)
    add("PRE_FUNDING_COMMITTED_NATIVE_COPY",2*MIN,1000,identity="fund")
    add("POST_FUNDING_ACCOUNT_NATIVE",2*MIN,990,epoch=1,identity="fund",delta=-10)
    retention={"source_ns":str(MIN),"state_epoch":0,"signature":["1000","native-hash"],"first_new_mutation_ns":str(2*MIN)}
    r=add("SETTLED_PRE_NEXT_SOURCE_WATERMARK",MIN,1000,epoch=1,state=0,retention=retention);r["receipt_ns"]=str(2*MIN)
    add("PREQUOTE_DIRECT_NATIVE",2*MIN,990,epoch=1)
    r=add("SETTLED_PRE_NEXT_SOURCE_WATERMARK",2*MIN,990,epoch=1);r["receipt_ns"]=str(3*MIN)
    add("PREQUOTE_DIRECT_NATIVE",3*MIN,990,epoch=1)
    r=add("SETTLED_PRE_NEXT_SOURCE_WATERMARK",3*MIN,990,epoch=1);r["receipt_ns"]=str(4*MIN)
    add("PREQUOTE_DIRECT_NATIVE",4*MIN,990,epoch=1)
    add("PRE_FILL_LAST_COMMITTED_NATIVE_COPY",4*MIN,990,epoch=1,identity="fill")
    add("POST_FILL_COMMITTED_NATIVE",4*MIN,985,epoch=2,identity="fill",delta=-5)
    add("DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED",4*MIN,985,epoch=2)
    Tracker=native_reference(SOURCE);e=Tracker(D(1000));s=Tracker(D(1000));e.add(0,D(1000));s.add(0,D(1000))
    for sequence,ns,value in ((1,MIN,1000),(2,2*MIN,1000),(3,2*MIN,990),(5,2*MIN,990),(7,3*MIN,990),(9,4*MIN,990)):
        e.add(sequence,D(value),sequence_id=sequence,timestamp_ns=ns)
    for ns,value in ((MIN,1000),(2*MIN,990),(3*MIN,990)):s.add(ns,D(value))
    report={"coherent_native_observer":{"native_cash_transitions":{"seed":"1000"},"settled_receipts":3,
        "sequence_count":12,"settled_drawdown":s.summary(),"event_drawdown":e.summary()},
        "minute_risk_observations":{"settled_native_close_receipts":{"receipts":2,
            "unavailable_intervening_native_mutation":1,"pending_source_quote_ns":None}}}
    if change:change(rows,report)
    trace=directory/"native.jsonl.gz";legacy=directory/"legacy.csv.gz";derived=directory/"derived.csv.gz"
    with gzip.open(trace,"wt") as f:
        for r in rows:f.write(json.dumps(r)+"\n")
    with gzip.open(legacy,"wt",newline="") as f:
        w=csv.writer(f);w.writerow(["source_quote_ns","receipt_ns","cash","paired_close_equity"])
        w.writerow([2*MIN,3*MIN,"990","990"]);w.writerow([3*MIN,4*MIN,"990","990"])
    return report,legacy,trace,derived,Tracker

def scan(args):
    report,legacy,trace,derived,Tracker=args
    return scan_native(report,legacy,trace,derived,Tracker,start=0,end=4*MIN,expected=3)

def test_genuine_retained_watermark_projects_without_interpolation(tmp_path):
    args=fixture(tmp_path);result=scan(args)
    assert result["wm_rows"]==3 and result["legacy_rows"]==2 and result["legacy_missing"]==1
    assert result["retained_native_rows"]==1 and result["exact_interval_DD_parity"] is True
    with gzip.open(args[3],"rt") as f:rows=list(csv.DictReader(f))
    assert len(rows)==3 and rows[0]["source_quote_ns"]==str(MIN) and rows[0]["cash"]=="1000"
    assert result["native_funding_cash_delta"]=="-10" and result["native_fill_cash_delta"]=="-5"

@pytest.mark.parametrize("change,reason",[
    (lambda rows,r:rows[3].pop("prior_source_retention"),"LEGACY_GAP_HAS_NO_ACTUAL_RETAINED_NATIVE_WM"),
    (lambda rows,r:rows[3]["prior_source_retention"].update(signature=["999","native-hash"]),"RETAINED_NATIVE_SIGNATURE_MISMATCH"),
    (lambda rows,r:rows[3].update(state_epoch=1),"INVALID_RETAINED_NATIVE_EPOCH"),
    (lambda rows,r:rows[3].update(event_ns=str(MIN+1)),"COMMITTED_WM_SEQUENCE_OR_RECEIPT_DRIFT"),
    (lambda rows,r:rows[2].update(native_cash_delta="-9"),"NATIVE_TRANSITION_DELTA_MISMATCH"),
    (lambda rows,r:rows[1].update(sequence=500),"COHERENT_SEQUENCE_GAP"),
])
def test_unproven_gap_or_native_cash_tampering_cannot_qualify(tmp_path,change,reason):
    with pytest.raises(ValueError,match=reason):scan(fixture(tmp_path,change))

def test_every_surviving_legacy_value_must_equal_actual_native_row(tmp_path):
    args=fixture(tmp_path)
    with gzip.open(args[1],"wt",newline="") as f:
        w=csv.writer(f);w.writerow(["source_quote_ns","receipt_ns","cash","paired_close_equity"])
        w.writerow([2*MIN,3*MIN,"990","989"]);w.writerow([3*MIN,4*MIN,"990","990"])
    with pytest.raises(ValueError,match="SURVIVING_LEGACY_NATIVE_ROW_DISAGREES"):scan(args)

def test_exact_native_dd_summary_cannot_be_tolerance_waived(tmp_path):
    def change(rows,report):report["coherent_native_observer"]["settled_drawdown"]["samples"]+=1
    with pytest.raises(ValueError,match="EXACT_NATIVE_SETTLED_DD_SUMMARY_MISMATCH"):scan(fixture(tmp_path,change))


@pytest.mark.parametrize("mark,pnl,reason",[
    (2*MIN,"0","NONCOMMON_NATIVE_MARK_SOURCE"),
    (MIN,"1","EXPORTED_NATIVE_CASH_UPNL_EQUITY_MISMATCH")])
def test_common_native_mark_and_exported_upnl_cannot_be_substituted(tmp_path,mark,pnl,reason):
    def change(rows,report):
        rows[3]["positions"]=[{"native_price":"100","native_upnl":pnl}]
        rows[3]["mark_available_ns"]=str(mark)
    with pytest.raises(ValueError,match=reason):scan(fixture(tmp_path,change))


def test_future_runtime_forwards_only_report_validation_and_preserves_raw(tmp_path,monkeypatch):
    from coinmaster.research import cm2_runner as runner
    from coinmaster.research import cm2_committed_validation as q
    raw=tmp_path/"CASE-raw-native.json";raw.write_text("{}")
    (tmp_path/"engine-construction-count.json").write_text('{"engine_constructions":1}')
    observed={}
    def strict(*args,**kwargs):
        observed["args"]=args;observed["kwargs"]=kwargs
        return {"coverage":{"full":True},"checks":{"exact":True},"qualification_model_id":q.MODEL,
            "original_report_sha256":q.sha(raw),"parent_raw_model_ids":{"code_hash":"ORIGINAL"},
            "comparability":"SAME_MONEY_NEW_QUALIFICATION","derived_report_sha256":"derived"}
    monkeypatch.setattr(q,"qualify",strict)
    result={"cm2":{}}
    runner.validate_full_output(result,{"artifact_dir":str(tmp_path),"run_id":"CASE",
        "qualified_coverage_source":str(tmp_path/"qualified.py")})
    assert observed["args"][0]==raw and observed["args"][-1]==1
    assert observed["kwargs"]["expected_report_sha"]==q.sha(raw)
    assert raw.read_text()=="{}" and result["cm2"]["accounting_status"]=="PASS"
    assert result["committed_wm_qualification"]["parent_raw_model_ids"]["code_hash"]=="ORIGINAL"


def finance_fixture(directory):
    import sqlite3
    from coinmaster.research.cm2_committed_validation import END
    db=directory/"funding.sqlite"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE funding_cash(event_id TEXT,instrument_id TEXT,ts_event INTEGER,before_total TEXT,after_total TEXT,signed_delta TEXT)")
        c.execute("INSERT INTO funding_cash VALUES ('fund','BTC',120,'1000','990','-10')")
    transitions={"seed":"1000","terminal_cash":"985","native_fill_cash_delta_total":"-5",
        "native_funding_cash_delta_total":"-10","exact_bridge":"0"}
    raw={"coherent_native_observer":{"status":"PASS","unknown":[],"end_exclusive_ns":str(END),
        "terminal_actual_cash":"985","native_cash_transitions":transitions},
        "terminal_total":"985","fill_audit":[{"trade_id":"fill","commission":"5"}],
        "native_fees":"5","fee_attribution":{"native_total":"5","audited_total":"5","reconciled":True},
        "funding_cash_audit":[["fund","BTC",120,"1000","990","-10"]],"funding":{"signed_amount":"-10"},
        "native_cash_reconciliation":{"signed_funding":"-10","status":"EXACT","unallocated_bridge":"0",
            "native_realized_total":"-5","native_position_lifecycle_export":{"unknown":[],"positions":[{"closed":True,"realized_pnl":"-5"}]}},
        "terminal_open_positions":0,"terminal_lifecycle":{"status":"FLAT"},"native_strategy_events":{"terminal_open_orders":0},
        "streaming":{"processed_rows_per_source":1051200},
        "config":{"accounting_currency":"USDC","deposit_protection":"DISABLED_CLEAN_EXECUTION_DIAGNOSTIC_ONLY"}}
    scan={"terminal_native_cash":"985","native_fill_cash_delta":"-5","native_funding_cash_delta":"-10",
        "fill_ids":["fill"],"funding_ids":["fund"],
        "kind_counts":{"PREQUOTE_DIRECT_NATIVE":2102400,"DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED":1}}
    return raw,scan,db

def test_native_cash_fees_sqlite_and_closed_lifecycle_bridges_are_independent(tmp_path):
    from coinmaster.research.cm2_committed_validation import financial_checks
    raw,scan,db=finance_fixture(tmp_path)
    assert all(financial_checks(raw,scan,db).values())
    raw["native_fees"]="4"
    with pytest.raises(ValueError,match="COMMISSION_BRIDGE_FAILED"):financial_checks(raw,scan,db)

def test_sqlite_or_native_boundary_metadata_drift_cannot_be_waived(tmp_path):
    from coinmaster.research.cm2_committed_validation import financial_checks
    raw,scan,db=finance_fixture(tmp_path)
    raw["funding_cash_audit"][0][5]="-9"
    with pytest.raises(ValueError,match="JOURNAL_EXPORT_MISMATCH"):financial_checks(raw,scan,db)
    raw["funding_cash_audit"][0][5]="-10"
    raw["coherent_native_observer"]["end_exclusive_ns"]="1"
    with pytest.raises(ValueError,match="OBSERVER_END_BOUNDARY"):financial_checks(raw,scan,db)
