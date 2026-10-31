"""Strict qualification of persisted committed-native watermarks. No engine/imports."""
from __future__ import annotations
import argparse,ast,copy,csv,gzip,hashlib,json,sqlite3
from collections import Counter
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D,localcontext,ROUND_HALF_EVEN
from pathlib import Path
from urllib.parse import quote

MODEL="CM2_COMMITTED_NATIVE_WM_QUALIFICATION_V1"
START=1725148800000000000
END=1788220800000000000
MIN=60_000_000_000
COUNT=1051199
DD_SHA="fc7e52eb9fad58acb317c4dd7c004aa99b222cd89c53025f463973b353f9e2ad"
OBSERVER_SHA="606a314485bd64cb10cc0558eccbc147e8ec24ae4220f488b619977c7aa12f42"
COVERAGE_SHA="58b9a047ceb6627108e3bac52a957b231f405fe12b8a6bb1684e3582599682df"

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def fail(condition,reason):
    if not condition:raise ValueError(reason)

def functions(source,names,scope):
    tree=ast.parse(Path(source).read_text())
    selected=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
    fail({n.name for n in selected}==set(names),"REFERENCE_DEFINITION_MISSING")
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(source),"exec"),scope)
    return scope

def native_reference(source):
    return functions(source,["DrawdownTracker"],{"D":D})["DrawdownTracker"]

def scan_native(report,legacy,trace,derived,Tracker,*,start=START,end=END,expected=COUNT):
    """One pass over both complete native trace and surviving sparse CSV."""
    obs=report["coherent_native_observer"];seed=D(obs["native_cash_transitions"]["seed"])
    event=Tracker(seed);settled=Tracker(seed);event.add(0,seed);settled.add(0,seed)
    n=0;seq=0;legacy_count=0;missing=0;retained_count=0;boundary=False
    epoch=0;pre={};mutations={};mutation_kinds={};gap_kinds=Counter();fill_ids=set();fund_ids=[];fill_delta=D(0);fund_delta=D(0);kinds=Counter()
    months=Counter();terminal=None;first_gap=None
    with gzip.open(legacy,"rt") as lf,gzip.open(trace,"rt") as tf,gzip.open(derived,"wt",newline="") as df:
        old=csv.DictReader(lf);pending=next(old,None)
        writer=csv.writer(df)
        writer.writerow(["source_quote_ns","receipt_ns","state_epoch","cash","paired_close_equity",
            "native_positions_sha256","native_sequence"])
        for line in tf:
            r=json.loads(line);seq+=1
            fail(int(r["sequence"])==seq,"COHERENT_SEQUENCE_GAP")
            ns=int(r["event_ns"]);value=D(r["equity"]) if r.get("equity") is not None else None
            fail(ns<=end,"NATIVE_EVENT_OUTSIDE_TERMINAL_BOUNDARY")
            kind=r["kind"];kinds[kind]+=1
            fail(kind in {"PRE_FILL_LAST_COMMITTED_NATIVE_COPY","POST_FILL_COMMITTED_NATIVE",
                "PRE_FUNDING_COMMITTED_NATIVE_COPY","POST_FUNDING_ACCOUNT_NATIVE",
                "SETTLED_PRE_NEXT_SOURCE_WATERMARK","PREQUOTE_DIRECT_NATIVE","DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED"},
                "UNKNOWN_COMMITTED_NATIVE_KIND")
            new_epoch=int(r["epoch"])
            fail(new_epoch>=epoch and int(r["state_epoch"])<=new_epoch,"INVALID_NATIVE_STATE_EPOCH")
            signature=(r["cash"],r["native_positions_sha256"])
            if kind in ("PRE_FILL_LAST_COMMITTED_NATIVE_COPY","PRE_FUNDING_COMMITTED_NATIVE_COPY"):
                pre[(kind,r["native_id"])]=(ns,new_epoch,signature)
                mutations[(ns,new_epoch)]=signature
                mutation_kinds[(ns,new_epoch)]=kind
            if kind in ("POST_FILL_COMMITTED_NATIVE","POST_FUNDING_ACCOUNT_NATIVE"):
                before_kind="PRE_FILL_LAST_COMMITTED_NATIVE_COPY" if kind=="POST_FILL_COMMITTED_NATIVE" else "PRE_FUNDING_COMMITTED_NATIVE_COPY"
                before=pre.pop((before_kind,r["native_id"]),None)
                fail(before is not None and before[0]==ns and before[1]+1==new_epoch,"NATIVE_TRANSITION_PAIR_MISMATCH")
                delta=D(r["cash"])-D(before[2][0])
                fail(delta==D(r["native_cash_delta"]),"NATIVE_TRANSITION_DELTA_MISMATCH")
                if kind=="POST_FILL_COMMITTED_NATIVE":
                    fail(r["native_id"] not in fill_ids,"DUPLICATE_COMMITTED_NATIVE_FILL")
                    fill_ids.add(r["native_id"]);fill_delta+=delta
                else:fund_ids.append(r["native_id"]);fund_delta+=delta
            epoch=new_epoch
            if kind=="SETTLED_PRE_NEXT_SOURCE_WATERMARK":
                source=start+MIN+n*MIN;receipt=source+MIN
                fail(ns==source and int(r["receipt_ns"])==receipt,"COMMITTED_WM_SEQUENCE_OR_RECEIPT_DRIFT")
                fail(value is not None and value.is_finite() and D(r["cash"]).is_finite(),"UNKNOWN_COMMITTED_NATIVE_MONEY")
                if r["positions"]:
                    fail(int(r["mark_available_ns"])==source,"NONCOMMON_NATIVE_MARK_SOURCE")
                actual=D(r["cash"])
                for p in r["positions"]:
                    fail(D(p["native_price"]).is_finite() and D(p["native_price"])>0,"INVALID_NATIVE_COMMON_PRICE")
                    actual+=D(p["native_upnl"])
                fail(actual==value,"EXPORTED_NATIVE_CASH_UPNL_EQUITY_MISMATCH")
                retention=r.get("prior_source_retention")
                if retention:
                    retained_count+=1
                    first=int(retention["first_new_mutation_ns"]);state=int(retention["state_epoch"])
                    fail(int(retention["source_ns"])==source and state==int(r["state_epoch"]) and state<new_epoch and first>source,
                        "INVALID_RETAINED_NATIVE_EPOCH")
                    fail(tuple(retention["signature"])==signature,"RETAINED_NATIVE_SIGNATURE_MISMATCH")
                    fail(mutations.get((first,state))==signature,"RETAINED_NATIVE_PREMUTATION_WITNESS_MISSING")
                if pending is not None:
                    fail(int(pending["source_quote_ns"])>=source,"LEGACY_EXTRA_DUPLICATE_OR_REORDERED_SOURCE")
                if pending is not None and int(pending["source_quote_ns"])==source:
                    fail(int(pending["receipt_ns"])==receipt and D(pending["cash"])==D(r["cash"])
                         and D(pending["paired_close_equity"])==value,"SURVIVING_LEGACY_NATIVE_ROW_DISAGREES")
                    legacy_count+=1;pending=next(old,None)
                else:
                    missing+=1
                    if first_gap is None:first_gap={"source_ns":str(source),"receipt_ns":str(receipt)}
                    fail(retention is not None and int(retention["first_new_mutation_ns"])==receipt,
                        "LEGACY_GAP_HAS_NO_ACTUAL_RETAINED_NATIVE_WM")
                    gap_kinds[mutation_kinds[(int(retention["first_new_mutation_ns"]),int(retention["state_epoch"]))]]+=1
                writer.writerow([r["event_ns"],r["receipt_ns"],r["state_epoch"],r["cash"],r["equity"],
                    r["native_positions_sha256"],r["sequence"]])
                settled.add(source,value);months[datetime.fromtimestamp(source//1_000_000_000,timezone.utc).strftime("%Y-%m")]+=1
                n+=1;continue
            left=ns==end and not boundary and kind in (
                "PREQUOTE_DIRECT_NATIVE","PRE_FILL_LAST_COMMITTED_NATIVE_COPY","PRE_FUNDING_COMMITTED_NATIVE_COPY")
            if value is not None and (ns<end or left):
                event.add(seq,value,sequence_id=seq,timestamp_ns=ns)
                if left:boundary=True
            if kind=="DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED":
                fail(ns==end and not r["positions"] and value==D(r["cash"]),"TERMINAL_NATIVE_FLAT_NOT_PROVEN")
                terminal=r
        fail(pending is None,"LEGACY_NATIVE_ROWS_OUTSIDE_COMMITTED_TRACE")
    fail(n==expected and n==int(obs["settled_receipts"]),"COMMITTED_NATIVE_WM_COUNT_MISMATCH")
    fail(seq==int(obs["sequence_count"]) and boundary,"NATIVE_SEQUENCE_COUNT_OR_LEFT_BOUNDARY_MISMATCH")
    fail(not pre,"UNPAIRED_NATIVE_CASH_TRANSITION")
    fail(terminal is not None,"TERMINAL_NATIVE_POINT_MISSING")
    got_s=settled.summary();got_e=event.summary()
    fail(got_s==obs["settled_drawdown"],"EXACT_NATIVE_SETTLED_DD_SUMMARY_MISMATCH")
    fail(got_e==obs["event_drawdown"],"EXACT_NATIVE_EVENT_DD_SUMMARY_MISMATCH")
    metadata=report["minute_risk_observations"]["settled_native_close_receipts"]
    fail(legacy_count==int(metadata["receipts"]) and missing==int(metadata["unavailable_intervening_native_mutation"]),
        "LEGACY_SPARSE_EXPORT_METADATA_MISMATCH")
    fail(metadata["pending_source_quote_ns"] is None,"LEGACY_PENDING_RECEIPT_AT_TERMINAL")
    return {"wm_rows":n,"trace_rows":seq,"kind_counts":dict(kinds),"legacy_rows":legacy_count,"legacy_missing":missing,
        "retained_native_rows":retained_count,"legacy_gap_actual_mutation_kinds":dict(gap_kinds),"first_legacy_gap":first_gap,"month_rows":dict(months),
        "terminal_native_cash":terminal["cash"],"terminal_native_sequence":terminal["sequence"],
        "fill_ids":sorted(fill_ids),"funding_ids":fund_ids,"native_fill_cash_delta":str(fill_delta),
        "native_funding_cash_delta":str(fund_delta),"exact_interval_DD_parity":True,"boundary_left_limit_proven":True}

def financial_checks(report,scan,funding_database):
    money=report["native_cash_reconciliation"];obs=report["coherent_native_observer"]
    transitions=obs["native_cash_transitions"];seed=D(transitions["seed"]);total=D(scan["terminal_native_cash"])
    fail(obs["status"]=="PASS" and not obs["unknown"],"NATIVE_OBSERVER_NOT_COMPLETE")
    fail(int(obs["end_exclusive_ns"])==END,"ORIGINAL_OBSERVER_END_BOUNDARY_GATE_FAILED")
    fail(total==D(report["terminal_total"])==D(obs["terminal_actual_cash"])==D(transitions["terminal_cash"]),"NATIVE_TERMINAL_TOTAL_MISMATCH")
    fail(D(scan["native_fill_cash_delta"])==D(transitions["native_fill_cash_delta_total"]),"NATIVE_FILL_TRANSITION_TOTAL_MISMATCH")
    fail(D(scan["native_funding_cash_delta"])==D(transitions["native_funding_cash_delta_total"]),"NATIVE_FUNDING_TRANSITION_TOTAL_MISMATCH")
    fail(total-seed-D(scan["native_fill_cash_delta"])-D(scan["native_funding_cash_delta"])==D(0)
         and D(transitions["exact_bridge"])==0,"EXACT_NATIVE_CASH_TRANSITION_BRIDGE_FAILED")
    fills=report["fill_audit"]
    fail(len(fills)==len({r["trade_id"] for r in fills}) and {r["trade_id"] for r in fills}==set(scan["fill_ids"]),"NATIVE_FILL_IDENTITIES_MISMATCH")
    fees=sum((D(r["commission"]) for r in fills),D(0))
    fail(fees==D(report["native_fees"])==D(report["fee_attribution"]["native_total"])==D(report["fee_attribution"]["audited_total"])
         and report["fee_attribution"]["reconciled"] is True,"EXACT_NATIVE_COMMISSION_BRIDGE_FAILED")
    with sqlite3.connect("file:"+quote(str(Path(funding_database).resolve()))+"?mode=ro",uri=True) as db:
        rows=db.execute("SELECT event_id,instrument_id,ts_event,before_total,after_total,signed_delta FROM funding_cash ORDER BY ts_event,event_id,instrument_id").fetchall()
    fail([list(r) for r in rows]==[list(r) for r in report["funding_cash_audit"]],"PERSISTED_FUNDING_JOURNAL_EXPORT_MISMATCH")
    for r in rows:fail(D(r[4])-D(r[3])==D(r[5]),"PERSISTED_NATIVE_FUNDING_DELTA_MISMATCH")
    funding=sum((D(r[5]) for r in rows),D(0))
    fail(sorted(r[0] for r in rows)==sorted(scan["funding_ids"]),"NATIVE_FUNDING_IDENTITIES_MISMATCH")
    fail(funding==D(scan["native_funding_cash_delta"])==D(money["signed_funding"])==D(report["funding"]["signed_amount"]),
        "EXACT_NATIVE_SIGNED_FUNDING_BRIDGE_FAILED")
    lives=money["native_position_lifecycle_export"]
    fail(not lives["unknown"] and all(r["closed"] and r["realized_pnl"] is not None for r in lives["positions"]),
        "COMPLETE_NATIVE_POSITION_LIFECYCLES_REQUIRED")
    realized=sum((D(r["realized_pnl"]) for r in lives["positions"]),D(0))
    fail(realized==D(money["native_realized_total"]) and total-seed-realized-funding==0
         and money["status"]=="EXACT" and D(money["unallocated_bridge"])==0,"EXACT_NATIVE_REALIZED_CASH_BRIDGE_FAILED")
    fail(report["terminal_open_positions"]==0 and report["terminal_lifecycle"]["status"]=="FLAT"
         and report["native_strategy_events"]["terminal_open_orders"]==0,"NATIVE_TERMINAL_RESIDUE")
    fail(scan["kind_counts"]["PREQUOTE_DIRECT_NATIVE"]==2*1051200
         and scan["kind_counts"]["DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED"]==1,"FULL_NATIVE_QUOTE_WATERMARK_COVERAGE_FAILED")
    fail(report["streaming"]["processed_rows_per_source"]==1051200 and report["config"]["accounting_currency"]=="USDC"
         and report["config"]["deposit_protection"]=="DISABLED_CLEAN_EXECUTION_DIAGNOSTIC_ONLY","ORIGINAL_FULL_ACCOUNTING_GATE_FAILED")
    return {"native_cash":True,"native_fees":True,"signed_native_funding":True,
        "native_closed_lifecycles":True,"terminal_flat_orders":True,"original_full_feed_currency_DP_gates":True}

def qualify(report_path,legacy,trace,out,dd_source,coverage_source,engine_count,*,expected_report_sha=None,provenance=None):
    """Only derives new files. Never rewrites original report, ledger or money."""
    out=Path(out).resolve();raw_path=Path(report_path).resolve();dd_source=Path(dd_source)
    fail(not any(Path(p).resolve().is_relative_to(out) for p in (raw_path,legacy,trace)),
        "DERIVED_DIRECTORY_MUST_NOT_CONTAIN_OR_REPLACE_RAW_INPUTS")
    fail(not any((out/name).exists() for name in ("QUALIFICATION.json","QUALIFICATION_FAILED.json","minute-native-settled-receipts.csv.gz")),
        "DERIVED_QUALIFICATION_EXISTS_NO_REPLAY")
    out.mkdir(parents=True,exist_ok=True)
    report_sha=sha(raw_path)
    if expected_report_sha is not None:fail(report_sha==expected_report_sha,"ORIGINAL_RAW_REPORT_HASH_MISMATCH")
    fail(sha(dd_source)==DD_SHA and sha(dd_source.with_name("paired_observer.py"))==OBSERVER_SHA,"FROZEN_NATIVE_MEASURER_SOURCE_MISMATCH")
    fail(sha(coverage_source)==COVERAGE_SHA,"QUALIFIED_COVERAGE_SOURCE_MISMATCH")
    raw=json.loads(raw_path.read_text());source=dd_source.with_name("native_baseline.py")
    fail(sha(source)==raw["code_hash"],"ORIGINAL_NATIVE_BASELINE_SOURCE_MISMATCH")
    fail(engine_count==1,"ONE_ACTUAL_ENGINE_REQUIRED")
    derived=out/"minute-native-settled-receipts.csv.gz"
    try:
        with localcontext() as ctx:
            ctx.prec=28;ctx.rounding=ROUND_HALF_EVEN
            Tracker=native_reference(dd_source)
            scan=scan_native(raw,legacy,trace,derived,Tracker)
            checks=financial_checks(raw,scan,raw["funding_journal"])
            scope={"Decimal":D,"datetime":datetime,"timezone":timezone,"timedelta":timedelta,"localcontext":localcontext}
            functions(source,["assert_report_boundaries"],scope)["assert_report_boundaries"](raw)
            cvscope={"csv":csv,"gzip":gzip,"Counter":Counter,"datetime":datetime,"timezone":timezone,"sha":sha}
            coverage=functions(coverage_source,["coverage"],cvscope)["coverage"](raw,out)
            fail(coverage["full"],"UNCHANGED_QUALIFIED_COVERAGE_NOT_FULL")
            checks.update(full_24months=True,exact_native_DD=True,retained_before_mutation=True,all_surviving_legacy_rows=True,
                unchanged_606_boundaries=True,one_actual_engine=True)
        public_scan={k:v for k,v in scan.items() if k not in ("fill_ids","funding_ids","terminal_native_cash","native_fill_cash_delta","native_funding_cash_delta")}
        receipt={"status":"FINANCIAL_QUALIFICATION_PASS","qualification_model_id":MODEL,
            "original_report_sha256":report_sha,"original_report_path":str(raw_path),
            "original_physical_status_preserved":True,"new_native_engine_constructions":0,"actual_engine_constructions":engine_count,
            "parent_raw_model_ids":{"policy_hash":raw.get("policy_hash"),"data_hash":raw.get("data_hash"),
                "code_hash":raw.get("code_hash"),"source_hashes":raw.get("source_hashes"),"config_hash":raw.get("config_hash")},
            "checks":checks,"native_watermark_proof":public_scan,"coverage":coverage,
            "input_hashes":{"legacy_csv":sha(legacy),"coherent_trace":sha(trace),"funding_sqlite":sha(raw["funding_journal"]),
                "native_DD_source":sha(dd_source),"native_observer_source":sha(dd_source.with_name("paired_observer.py")),
                "coverage_source":sha(coverage_source),"qualifier_source":sha(__file__)},
            "derived_csv":str(derived),"derived_csv_sha256":sha(derived),
            "comparability":"SAME_PERSISTED_NATIVE_MONEY; NEW_STRICT_COMMITTED_WM_QUALIFICATION; ORIGINAL_SOURCE_IDS_PRESERVED_NOT_RELABELED",
            "legacy_receipt_status":"SPARSE_UNAVAILABLE_AFTER_INTERVENING_MUTATION_NOT_SILENTLY_COMPLETE",
            "provenance":provenance or {}}
        qualified=copy.deepcopy(raw)
        qualified["committed_wm_qualification"]={k:receipt[k] for k in ("qualification_model_id","original_report_sha256","checks","comparability")}
        qualified.setdefault("cm2",{}).update(accounting_status="PASS",financial_checks=checks)
        qualified["actual_feed_coverage"]=coverage
        qualified["derived_financial_status"]="PASS"
        qualified_path=out/"COMMITTED_QUALIFIED_NATIVE_REPORT.json"
        qualified_path.write_text(json.dumps(qualified,sort_keys=True)+"\n")
        receipt["derived_report"]=str(qualified_path);receipt["derived_report_sha256"]=sha(qualified_path)
        (out/"QUALIFICATION.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
        return receipt
    except BaseException as error:
        failure={"status":"NOT_QUALIFIED","qualification_model_id":MODEL,"original_report_sha256":report_sha,
            "error_type":type(error).__name__,"error":str(error),"new_native_engine_constructions":0}
        (out/"QUALIFICATION_FAILED.json").write_text(json.dumps(failure,indent=2)+"\n")
        raise

def provenance_files(request=None,go=None,ledger=None,engine_count_path=None):
    result={}
    for key,path in (("request",request),("GO",go),("engine_count",engine_count_path)):
        if path is not None:result[key]={"path":str(Path(path).resolve()),"sha256":sha(path)}
    if ledger is not None:
        raw=Path(ledger).read_bytes()
        result["ledger_prefix"]={"path":str(Path(ledger).resolve()),"bytes":len(raw),
            "sha256":hashlib.sha256(raw).hexdigest(),"append_only_later_records_allowed":True}
    return result

def main(argv=None):
    p=argparse.ArgumentParser()
    for name in ("report","legacy","trace","out","dd-source","coverage-source","engine-count"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--expected-report-sha256",required=True)
    for name in ("request","go","ledger"):p.add_argument("--"+name,type=Path,required=True)
    args=p.parse_args(argv)
    engine=json.loads(args.engine_count.read_text())["engine_constructions"]
    receipt=qualify(args.report,args.legacy,args.trace,args.out,args.dd_source,args.coverage_source,engine,
        expected_report_sha=args.expected_report_sha256,provenance=provenance_files(args.request,args.go,args.ledger,args.engine_count))
    print(json.dumps({"status":receipt["status"],"qualification_model_id":MODEL,
        "wm_rows":receipt["native_watermark_proof"]["wm_rows"],"legacy_missing":receipt["native_watermark_proof"]["legacy_missing"],
        "new_native_engine_constructions":0}))

if __name__=="__main__":main()
