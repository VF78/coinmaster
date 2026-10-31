"""Synthetic saved-native equity facts only; no engine or product imports."""
from decimal import Decimal as D,localcontext,ROUND_HALF_EVEN
import copy,csv,gzip,json
from pathlib import Path
import tempfile
import pytest
import saved_cm2_analyze as a

ROOT=Path(__file__).parents[3]
SOURCE=ROOT/"runtime/coinmaster/research/minute_risk.py"

@pytest.fixture(autouse=True)
def decimal_contract():
    with localcontext() as ctx:
        ctx.prec=28;ctx.rounding=ROUND_HALF_EVEN
        yield

def test_native_exact_ties_recovery_and_ongoing_ge20():
    Native,Recording=a.native_tracker(SOURCE)
    base=Native(D(100));ours=Recording(D(100))
    base.add(0,D(100));ours.add(0,D(100))
    values=[D(100),D(80),D(80),D(100),D(100),D(70)]
    for i,value in enumerate(values,1):
        base.add(i,value);ours.add(i,value)
    expected=base.summary();got=ours.summary()
    assert got==expected and a.equivalent(got,expected)==[]
    assert len(ours.all_ge20)==2
    first,second=ours.all_ge20
    assert first["peak"]["timestamp_ns"]=="1"
    assert first["trough"]["timestamp_ns"]=="2"
    assert first["recovery"]["timestamp_ns"]=="4"
    assert second["peak"]["timestamp_ns"]=="5" and second["recovery"] is None
    assert D(first["drawdown_peak_percent"])==20 and D(second["drawdown_peak_percent"])==30

def test_actual_terminal_cash_point_increases_dd_without_changing_raw_interval():
    Native,Recording=a.native_tracker(SOURCE)
    curve=Recording(D(100));native=Native(D(100))
    for t,value in ((0,100),(1,110),(2,80)):
        curve.add(t,D(value));native.add(t,D(value))
    interval=copy.deepcopy(curve)
    saved=native.summary()
    assert interval.summary()==saved
    curve.add(3,D(75))  # authoritative native terminal-flat cash test input
    strict=curve.summary()
    assert a.maxdd(strict)==D(35)/D(110)*100
    assert a.maxdd(saved)==D(30)/D(110)*100
    assert saved["minimum"]["equity"]=="80"

def tiny_saved_pair(directory):
    start=a.epoch("2024-08-31T23:57:00+00:00");end=start+3*a.MIN
    def row(sequence,kind,ns,equity,receipt=None):
        return {"sequence":sequence,"kind":kind,"event_ns":str(ns),"receipt_ns":str(receipt or ns),
                "cash":str(equity),"equity":str(equity),"positions":[]}
    rows=[
        row(1,"PREQUOTE_DIRECT_NATIVE",start+a.MIN,110),
        row(2,"SETTLED_PRE_NEXT_SOURCE_WATERMARK",start+a.MIN,110,start+2*a.MIN),
        row(3,"PREQUOTE_DIRECT_NATIVE",start+2*a.MIN,80),
        row(4,"SETTLED_PRE_NEXT_SOURCE_WATERMARK",start+2*a.MIN,80,end),
        row(5,"PREQUOTE_DIRECT_NATIVE",end,80),
        row(6,"POST_FILL_COMMITTED_NATIVE",end,75),
        row(7,"DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED",end,75)]
    trace=directory/"coherent.jsonl.gz";receipts=directory/"settled.csv.gz"
    with gzip.open(trace,"wt") as f:
        for r in rows:f.write(json.dumps(r)+"\n")
    with gzip.open(receipts,"wt",newline="") as f:
        w=csv.writer(f);w.writerow(["source_quote_ns","receipt_ns","cash","paired_close_equity"])
        w.writerow([start+a.MIN,start+2*a.MIN,110,110]);w.writerow([start+2*a.MIN,end,80,80])
    Native,_=a.native_tracker(SOURCE)
    e=Native(D(100));s=Native(D(100));e.add(0,D(100));s.add(0,D(100))
    for sequence,ns,value in ((1,start+a.MIN,110),(3,start+2*a.MIN,80),(5,end,80)):
        e.add(sequence,D(value),sequence_id=sequence,timestamp_ns=ns)
    s.add(start+a.MIN,D(110));s.add(start+2*a.MIN,D(80))
    report={"run_interval":{"start":"2024-08-31T23:57:00+00:00","end_exclusive":"2024-09-01T00:00:00+00:00"},
        "terminal_total":"75","coherent_native_observer":{"native_cash_transitions":{"seed":"100"},
            "settled_receipts":2,"sequence_count":7,"terminal_actual_cash":"75",
            "settled_drawdown":s.summary(),"event_drawdown":e.summary()}}
    return report,receipts,trace

def test_one_pass_two_native_exports_exact_parity_and_terminal_cash():
    _,Recording=a.native_tracker(SOURCE)
    with tempfile.TemporaryDirectory() as td:
        report,receipts,trace=tiny_saved_pair(Path(td))
        curves=a.stream_curves(report,receipts,trace,Recording)
        assert curves["errors"]==[]
        assert curves["interval_settled"]==report["coherent_native_observer"]["settled_drawdown"]
        assert curves["interval_coherent"]==report["coherent_native_observer"]["event_drawdown"]
        assert a.maxdd(curves["with_final_close_settled"])>a.maxdd(curves["interval_settled"])
        assert curves["input_hashes"]=={"settled_receipts":a.sha(receipts),"coherent_trace":a.sha(trace)}
        assert curves["monthly"]["2024-08"]["marked_settled_equity"]=="80"
        assert curves["native_terminal_flat_cash_point"]["cash"]=="75"

def test_native_export_disagreement_is_rejected():
    _,Recording=a.native_tracker(SOURCE)
    with tempfile.TemporaryDirectory() as td:
        report,receipts,trace=tiny_saved_pair(Path(td))
        content=gzip.open(receipts,"rt").read().replace(",80,80",",80,79")
        with gzip.open(receipts,"wt") as f:f.write(content)
        with pytest.raises(ValueError,match="TWO_NATIVE_SETTLED_EXPORTS_DISAGREE"):
            a.stream_curves(report,receipts,trace,Recording)

def test_failed_or_running_attempt_does_not_open_any_economic_stream():
    with tempfile.TemporaryDirectory() as td:
        case={"case":"FAILED_ANCHOR","run_id":"failed","native_report":"/DO_NOT_OPEN/no.json"}
        summary=a.analyze_case(case,[{"run_id":"failed","status":"FAILED"}],Path(td),"/DO_NOT_OPEN/source.py")
        assert summary["TOTAL"] is None and summary["numeric_goal_status"]=="UNKNOWN"
        assert summary["with_final_close_DD_percent"]=={"settled":None,"coherent":None}
        with (Path(td)/"FAILED_ANCHOR/MONTHLY_24.csv").open() as f:months=list(csv.DictReader(f))
        assert len(months)==24 and all(m["marked_settled_equity"]=="" for m in months)

def test_native_realized_is_not_reduced_by_fees_again_and_funding_stays_signed():
    raw={"fill_audit":[{"instrument":"BTC-USD-PERP.HYPERLIQUID","notional":"1000","commission":"1"}],
        "funding_cash_audit":[["id","BTC-USD-PERP.HYPERLIQUID",1,"100","97","-3"]],
        "native_cash_reconciliation":{"native_position_lifecycle_export":{"unknown":[],"positions":[
            {"instrument_id":"BTC-USD-PERP.HYPERLIQUID","closed":True,"realized_pnl":"9"}]}}}
    values,unknown=a.allocations(raw)
    assert unknown==[] and values["BTC"]["native_realized_includes_fees"]=="9"
    assert values["BTC"]["native_fees"]=="1" and values["BTC"]["signed_native_funding"]=="-3"

def summary(name,total,dd,group="group"):
    return {"case":name,"run_id":name,"physical_status":"COMPLETED","financial_status":"PASS",
        "structural_status":"UNKNOWN","numeric_goal_status":"FAIL","TOTAL":str(total),
        "with_final_close_DD_percent":{"settled":str(dd),"coherent":str(dd)},
        "robustness_status":"NOT_RUN","persistence_status":"NOT_IMPLEMENTED_FRESH_RESEARCH_ONLY",
        "comparison_group_hash":group,"provenance":{"report_sha256":name}}

def test_pareto_only_compares_exact_matched_groups_and_unknown_stays_null():
    with tempfile.TemporaryDirectory() as td:
        packet=a.compare([summary("A",100,40),summary("B",150,30),
            summary("OTHER",1000,1,"other")],Path(td))
        by={r["case"]:r for r in packet["cases"]}
        assert by["A"]["pareto_native_numeric"] is False
        assert by["B"]["pareto_native_numeric"] is True
        assert by["OTHER"]["pareto_native_numeric"] is True

def test_duplicate_report_is_not_independent_fresh_control():
    with tempfile.TemporaryDirectory() as td:
        x=summary("A",100,40);y=summary("B",100,40)
        y["provenance"]["report_sha256"]="A"
        packet=a.compare([x,y],Path(td))
        assert all(r["pareto_native_numeric"] is None for r in packet["cases"])


def test_cli_failed_attempt_emits_nulls_without_native_or_product_import():
    import subprocess,sys
    with tempfile.TemporaryDirectory() as td:
        directory=Path(td);ledger=directory/"trials.jsonl";manifest=directory/"inputs.json";output=directory/"out"
        ledger.write_text(json.dumps({"run_id":"failed","status":"STARTED"})+"\n"+
                          json.dumps({"run_id":"failed","status":"FAILED"})+"\n")
        manifest.write_text(json.dumps({"schema_version":1,"native_dd_source":str(SOURCE),
            "native_dd_source_sha256":a.sha(SOURCE),"ledger":str(ledger),
            "cases":[{"case":"FAILED","run_id":"failed","stage":"anchors"}]}))
        result=subprocess.run([sys.executable,str(Path(a.__file__)),"--manifest",str(manifest),"--out",str(output)],
            text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        assert result.returncode==0,result.stderr
        packet=json.loads(result.stdout)
        assert packet["engine_constructions_added"]==0 and packet["financial_PASS"]==0
        summary=json.loads((output/"FAILED/SUMMARY.json").read_text())
        assert summary["physical_status"]=="FAILED" and summary["TOTAL"] is None
        with (output/"FAILED/MONTHLY_24.csv").open() as f:assert len(list(csv.DictReader(f)))==24


def derived_case(directory):
    paths={key:directory/(key+".txt") for key in ("raw","legacy","trace","derived","csv","qualifier","request","go","engine")}
    for key,path in paths.items():path.write_text(key)
    ledger=directory/"ledger.jsonl";ledger.write_text('{"run_id":"r1","status":"FAILED"}\n')
    required=("native_cash","native_fees","signed_native_funding","native_closed_lifecycles",
        "terminal_flat_orders","original_full_feed_currency_DP_gates","full_24months","exact_native_DD",
        "retained_before_mutation","all_surviving_legacy_rows","unchanged_606_boundaries","one_actual_engine")
    proof={"status":"FINANCIAL_QUALIFICATION_PASS","qualification_model_id":"CM2_COMMITTED_NATIVE_WM_QUALIFICATION_V1",
        "new_native_engine_constructions":0,"checks":dict.fromkeys(required,True),
        "original_report_sha256":a.sha(paths["raw"]),"derived_report":str(paths["derived"]),
        "derived_report_sha256":a.sha(paths["derived"]),"derived_csv":str(paths["csv"]),"derived_csv_sha256":a.sha(paths["csv"]),
        "input_hashes":{"qualifier_source":a.sha(paths["qualifier"]),"legacy_csv":a.sha(paths["legacy"]),"coherent_trace":a.sha(paths["trace"])},
        "provenance":{"request":{"sha256":a.sha(paths["request"])},"GO":{"sha256":a.sha(paths["go"])},
            "engine_count":{"sha256":a.sha(paths["engine"])},"ledger_prefix":{"path":str(ledger),
                "bytes":len(ledger.read_bytes()),"sha256":a.sha(ledger)}}}
    receipt=directory/"QUALIFICATION.json";receipt.write_text(json.dumps(proof))
    case={"native_report":str(paths["raw"]),"settled_receipts":str(paths["legacy"]),
        "coherent_trace":str(paths["trace"]),"derived_receipt":str(receipt),"qualifier_source":str(paths["qualifier"]),
        "request":str(paths["request"]),"go":str(paths["go"]),"engine_count":str(paths["engine"]),"_ledger_path":str(ledger)}
    return case,proof,paths,ledger

def test_derived_financial_acceptance_keeps_physical_fail_and_allows_ledger_append():
    with tempfile.TemporaryDirectory() as td:
        case,proof,paths,ledger=derived_case(Path(td))
        with ledger.open("a") as f:f.write('{"run_id":"other","status":"STARTED"}\n')
        replacement,accepted=a.derived_input(case,"FAILED")
        assert replacement["native_report"]==str(paths["derived"])
        assert replacement["settled_receipts"]==str(paths["csv"])
        assert accepted["original_report_sha256"]==a.sha(paths["raw"])
        assert '"status":"FAILED"' in ledger.read_text()

def test_derived_acceptance_rejects_hash_change_or_modified_physical_history():
    with tempfile.TemporaryDirectory() as td:
        case,proof,paths,ledger=derived_case(Path(td))
        paths["raw"].write_text("changed")
        with pytest.raises(ValueError,match="ORIGINAL_REPORT_HASH"):a.derived_input(case,"FAILED")
    with tempfile.TemporaryDirectory() as td:
        case,proof,paths,ledger=derived_case(Path(td))
        ledger.write_text('{"run_id":"r1","status":"COMPLETED"}\n')
        with pytest.raises(ValueError,match="LEDGER_PREFIX_CHANGED"):a.derived_input(case,"FAILED")
