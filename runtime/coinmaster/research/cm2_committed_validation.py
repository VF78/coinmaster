"""Strict qualification of persisted committed-native watermarks. No engine/imports."""
from __future__ import annotations
import argparse,ast,copy,csv,gzip,hashlib,json,sqlite3
from collections import Counter
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D,localcontext,ROUND_HALF_EVEN
from pathlib import Path
from urllib.parse import quote

MODEL="CM2_COMMITTED_NATIVE_WM_QUALIFICATION_V2"
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

def checked(predicates,condition,reason):
    value=bool(condition)
    previous=predicates.get(reason,{'evaluations':0,'passed':value})
    predicates[reason]={'evaluations':previous['evaluations']+1,'passed':previous['passed'] and value}
    fail(value,reason)
    return value


def expected_month_rows(start,end):
    # Actual source timestamps occupy [start+MIN,end), excluding seed/terminal.
    left=start+MIN;month=datetime.fromtimestamp(left//1_000_000_000,tz=timezone.utc).replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    result={}
    while int(month.timestamp())*1_000_000_000<end:
        next_month=month.replace(year=month.year+1,month=1) if month.month==12 else month.replace(month=month.month+1)
        a=max(left,int(month.timestamp())*1_000_000_000);z=min(end,int(next_month.timestamp())*1_000_000_000)
        if z>a:result[month.strftime('%Y-%m')]=(z-a)//MIN
        month=next_month
    return result


def interval_coverage(derived,start,end):
    counts=Counter();n=0;first=None;last=None
    with gzip.open(derived,'rt') as stream:
        reader=csv.DictReader(stream)
        fail(reader.fieldnames is not None and {'source_quote_ns','receipt_ns'}.issubset(reader.fieldnames),'UNKNOWN_RECEIPT_CSV_SHAPE')
        for row in reader:
            source=int(row['source_quote_ns']);receipt=int(row['receipt_ns'])
            fail(source==start+MIN+n*MIN and receipt==source+MIN,'SETTLED_RECEIPT_SEQUENCE_OR_BOUND_DRIFT')
            first=source if first is None else first;last=receipt;n+=1
            counts[datetime.fromtimestamp(source//1_000_000_000,tz=timezone.utc).strftime('%Y-%m')]+=1
    expected=expected_month_rows(start,end)
    complete=(dict(counts)==expected and n==(end-start)//MIN-1 and first==start+MIN and last==end)
    fail(complete,'DECLARED_INTERVAL_CSV_COVERAGE')
    return dict(path=str(derived),sha256=sha(derived),rows=n,first_source_ns=first,last_receipt_ns=last,
        source_calendar_months=len(counts),month_rows=dict(counts),month_counts_complete=dict(counts)==expected,
        interval_complete=complete,scope='PREFIX',full=(start==START and end==END and complete))


def report_interval(report,start,end):
    fail(type(start) is int and type(end) is int and 0<start<end and start%MIN==end%MIN==0 and end-start>=2*MIN,
        'EXPLICIT_MINUTE_ALIGNED_REQUEST_INTERVAL_REQUIRED')
    declared=report['run_interval'];config=report['config']['run_interval']
    def ns(value):
        stamp=datetime.fromisoformat(value)
        fail(stamp.tzinfo is not None and stamp.utcoffset()==timedelta(0) and stamp.microsecond==0,'REPORT_INTERVAL_MUST_BE_UTC')
        return int(stamp.timestamp())*1_000_000_000
    actual=(ns(declared['start']),ns(declared['end_exclusive']))
    fail(actual==(start,end) and config==declared,'REQUEST_REPORT_INTERVAL_IDENTITY')
    return (end-start)//MIN


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
    predicates={}
    check=lambda condition,reason:checked(predicates,condition,reason)
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
            check(int(r["sequence"])==seq,"COHERENT_SEQUENCE_GAP")
            ns=int(r["event_ns"]);value=D(r["equity"]) if r.get("equity") is not None else None
            check(ns<=end,"NATIVE_EVENT_OUTSIDE_TERMINAL_BOUNDARY")
            kind=r["kind"];kinds[kind]+=1
            check(kind in {"PRE_FILL_LAST_COMMITTED_NATIVE_COPY","POST_FILL_COMMITTED_NATIVE",
                "PRE_FUNDING_COMMITTED_NATIVE_COPY","POST_FUNDING_ACCOUNT_NATIVE",
                "SETTLED_PRE_NEXT_SOURCE_WATERMARK","PREQUOTE_DIRECT_NATIVE","DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED"},
                "UNKNOWN_COMMITTED_NATIVE_KIND")
            new_epoch=int(r["epoch"])
            check(new_epoch>=epoch and int(r["state_epoch"])<=new_epoch,"INVALID_NATIVE_STATE_EPOCH")
            signature=(r["cash"],r["native_positions_sha256"])
            if kind in ("PRE_FILL_LAST_COMMITTED_NATIVE_COPY","PRE_FUNDING_COMMITTED_NATIVE_COPY"):
                pre[(kind,r["native_id"])]=(ns,new_epoch,signature)
                mutations[(ns,new_epoch)]=signature
                mutation_kinds[(ns,new_epoch)]=kind
            if kind in ("POST_FILL_COMMITTED_NATIVE","POST_FUNDING_ACCOUNT_NATIVE"):
                before_kind="PRE_FILL_LAST_COMMITTED_NATIVE_COPY" if kind=="POST_FILL_COMMITTED_NATIVE" else "PRE_FUNDING_COMMITTED_NATIVE_COPY"
                before=pre.pop((before_kind,r["native_id"]),None)
                check(before is not None and before[0]==ns and before[1]+1==new_epoch,"NATIVE_TRANSITION_PAIR_MISMATCH")
                delta=D(r["cash"])-D(before[2][0])
                check(delta==D(r["native_cash_delta"]),"NATIVE_TRANSITION_DELTA_MISMATCH")
                if kind=="POST_FILL_COMMITTED_NATIVE":
                    check(r["native_id"] not in fill_ids,"DUPLICATE_COMMITTED_NATIVE_FILL")
                    fill_ids.add(r["native_id"]);fill_delta+=delta
                else:fund_ids.append(r["native_id"]);fund_delta+=delta
            epoch=new_epoch
            if kind=="SETTLED_PRE_NEXT_SOURCE_WATERMARK":
                source=start+MIN+n*MIN;receipt=source+MIN
                check(ns==source and int(r["receipt_ns"])==receipt,"COMMITTED_WM_SEQUENCE_OR_RECEIPT_DRIFT")
                check(value is not None and value.is_finite() and D(r["cash"]).is_finite(),"UNKNOWN_COMMITTED_NATIVE_MONEY")
                if r["positions"]:
                    check(int(r["mark_available_ns"])==source,"NONCOMMON_NATIVE_MARK_SOURCE")
                actual=D(r["cash"])
                for p in r["positions"]:
                    check(D(p["native_price"]).is_finite() and D(p["native_price"])>0,"INVALID_NATIVE_COMMON_PRICE")
                    actual+=D(p["native_upnl"])
                check(actual==value,"EXPORTED_NATIVE_CASH_UPNL_EQUITY_MISMATCH")
                retention=r.get("prior_source_retention")
                if retention:
                    retained_count+=1
                    first=int(retention["first_new_mutation_ns"]);state=int(retention["state_epoch"])
                    check(int(retention["source_ns"])==source and state==int(r["state_epoch"]) and state<new_epoch and first>source,
                        "INVALID_RETAINED_NATIVE_EPOCH")
                    check(tuple(retention["signature"])==signature,"RETAINED_NATIVE_SIGNATURE_MISMATCH")
                    check(mutations.get((first,state))==signature,"RETAINED_NATIVE_PREMUTATION_WITNESS_MISSING")
                if pending is not None:
                    check(int(pending["source_quote_ns"])>=source,"LEGACY_EXTRA_DUPLICATE_OR_REORDERED_SOURCE")
                if pending is not None and int(pending["source_quote_ns"])==source:
                    check(int(pending["receipt_ns"])==receipt and D(pending["cash"])==D(r["cash"])
                         and D(pending["paired_close_equity"])==value,"SURVIVING_LEGACY_NATIVE_ROW_DISAGREES")
                    legacy_count+=1;pending=next(old,None)
                else:
                    missing+=1
                    if first_gap is None:first_gap={"source_ns":str(source),"receipt_ns":str(receipt)}
                    check(retention is not None and int(retention["first_new_mutation_ns"])==receipt,
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
                check(ns==end and not r["positions"] and value==D(r["cash"]),"TERMINAL_NATIVE_FLAT_NOT_PROVEN")
                terminal=r
        check(pending is None,"LEGACY_NATIVE_ROWS_OUTSIDE_COMMITTED_TRACE")
    check(n==expected and n==int(obs["settled_receipts"]),"COMMITTED_NATIVE_WM_COUNT_MISMATCH")
    check(seq==int(obs["sequence_count"]) and boundary,"NATIVE_SEQUENCE_COUNT_OR_LEFT_BOUNDARY_MISMATCH")
    check(not pre,"UNPAIRED_NATIVE_CASH_TRANSITION")
    check(terminal is not None,"TERMINAL_NATIVE_POINT_MISSING")
    got_s=settled.summary();got_e=event.summary()
    check(got_s==obs["settled_drawdown"],"EXACT_NATIVE_SETTLED_DD_SUMMARY_MISMATCH")
    check(got_e==obs["event_drawdown"],"EXACT_NATIVE_EVENT_DD_SUMMARY_MISMATCH")
    metadata=report["minute_risk_observations"]["settled_native_close_receipts"]
    check(legacy_count==int(metadata["receipts"]) and missing==int(metadata["unavailable_intervening_native_mutation"]),
        "LEGACY_SPARSE_EXPORT_METADATA_MISMATCH")
    check(metadata["pending_source_quote_ns"] is None,"LEGACY_PENDING_RECEIPT_AT_TERMINAL")
    return {"wm_rows":n,"trace_rows":seq,"kind_counts":dict(kinds),"legacy_rows":legacy_count,"legacy_missing":missing,
        "retained_native_rows":retained_count,"legacy_gap_actual_mutation_kinds":dict(gap_kinds),"first_legacy_gap":first_gap,"month_rows":dict(months),
        "terminal_native_cash":terminal["cash"],"terminal_native_sequence":terminal["sequence"],
        "fill_ids":sorted(fill_ids),"funding_ids":fund_ids,"native_fill_cash_delta":str(fill_delta),
        "native_funding_cash_delta":str(fund_delta),"verified_predicates":predicates,
        "exact_interval_DD_parity":got_s==obs["settled_drawdown"] and got_e==obs["event_drawdown"],
        "boundary_left_limit_proven":seq==int(obs["sequence_count"]) and boundary}

def financial_checks(report,scan,funding_database,*,end=END,minutes=1051200):
    predicates={}
    check=lambda condition,reason:checked(predicates,condition,reason)
    money=report["native_cash_reconciliation"];obs=report["coherent_native_observer"]
    transitions=obs["native_cash_transitions"];seed=D(transitions["seed"]);total=D(scan["terminal_native_cash"])
    check(obs["status"]=="PASS" and not obs["unknown"],"NATIVE_OBSERVER_NOT_COMPLETE")
    check(int(obs["end_exclusive_ns"])==end,"ORIGINAL_OBSERVER_END_BOUNDARY_GATE_FAILED")
    check(total==D(report["terminal_total"])==D(obs["terminal_actual_cash"])==D(transitions["terminal_cash"]),"NATIVE_TERMINAL_TOTAL_MISMATCH")
    check(D(scan["native_fill_cash_delta"])==D(transitions["native_fill_cash_delta_total"]),"NATIVE_FILL_TRANSITION_TOTAL_MISMATCH")
    check(D(scan["native_funding_cash_delta"])==D(transitions["native_funding_cash_delta_total"]),"NATIVE_FUNDING_TRANSITION_TOTAL_MISMATCH")
    check(total-seed-D(scan["native_fill_cash_delta"])-D(scan["native_funding_cash_delta"])==D(0)
         and D(transitions["exact_bridge"])==0,"EXACT_NATIVE_CASH_TRANSITION_BRIDGE_FAILED")
    fills=report["fill_audit"]
    check(len(fills)==len({r["trade_id"] for r in fills}) and {r["trade_id"] for r in fills}==set(scan["fill_ids"]),"NATIVE_FILL_IDENTITIES_MISMATCH")
    check(all(r.get('commission_currency')=='USDC' for r in fills),'REQUIRED_NATIVE_SETTLEMENT_AND_FEE_CURRENCY_KNOWN')
    fees=sum((D(r["commission"]) for r in fills),D(0))
    check(fees==D(report["native_fees"])==D(report["fee_attribution"]["native_total"])==D(report["fee_attribution"]["audited_total"])
         and report["fee_attribution"]["reconciled"] is True,"EXACT_NATIVE_COMMISSION_BRIDGE_FAILED")
    with sqlite3.connect("file:"+quote(str(Path(funding_database).resolve()))+"?mode=ro",uri=True) as db:
        rows=db.execute("SELECT event_id,instrument_id,ts_event,before_total,after_total,signed_delta FROM funding_cash ORDER BY ts_event,event_id,instrument_id").fetchall()
    check([list(r) for r in rows]==[list(r) for r in report["funding_cash_audit"]],"PERSISTED_FUNDING_JOURNAL_EXPORT_MISMATCH")
    for r in rows:check(D(r[4])-D(r[3])==D(r[5]),"PERSISTED_NATIVE_FUNDING_DELTA_MISMATCH")
    funding=sum((D(r[5]) for r in rows),D(0))
    check(sorted(r[0] for r in rows)==sorted(scan["funding_ids"]),"NATIVE_FUNDING_IDENTITIES_MISMATCH")
    check(funding==D(scan["native_funding_cash_delta"])==D(money["signed_funding"])==D(report["funding"]["signed_amount"]),
        "EXACT_NATIVE_SIGNED_FUNDING_BRIDGE_FAILED")
    lives=money["native_position_lifecycle_export"]
    check(not lives["unknown"] and all(r["closed"] and r["realized_pnl"] is not None for r in lives["positions"]),
        "COMPLETE_NATIVE_POSITION_LIFECYCLES_REQUIRED")
    realized=sum((D(r["realized_pnl"]) for r in lives["positions"]),D(0))
    check(realized==D(money["native_realized_total"]) and total-seed-realized-funding==0
         and money["status"]=="EXACT" and D(money["unallocated_bridge"])==0,"EXACT_NATIVE_REALIZED_CASH_BRIDGE_FAILED")
    check(report["terminal_open_positions"]==0 and report["terminal_lifecycle"]["status"]=="FLAT"
         and report["native_strategy_events"]["terminal_open_orders"]==0,"NATIVE_TERMINAL_RESIDUE")
    check(scan["kind_counts"]["PREQUOTE_DIRECT_NATIVE"]==2*minutes
         and scan["kind_counts"]["DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED"]==1,"FULL_NATIVE_QUOTE_WATERMARK_COVERAGE_FAILED")
    check(report["streaming"]["processed_rows_per_source"]==minutes and report["config"]["accounting_currency"]=="USDC"
         and report["config"]["deposit_protection"]=="DISABLED_CLEAN_EXECUTION_DIAGNOSTIC_ONLY","ORIGINAL_FULL_ACCOUNTING_GATE_FAILED")
    groups={
        'native_cash':('NATIVE_TERMINAL_TOTAL_MISMATCH','NATIVE_FILL_TRANSITION_TOTAL_MISMATCH','NATIVE_FUNDING_TRANSITION_TOTAL_MISMATCH','EXACT_NATIVE_CASH_TRANSITION_BRIDGE_FAILED'),
        'native_fees':('NATIVE_FILL_IDENTITIES_MISMATCH','EXACT_NATIVE_COMMISSION_BRIDGE_FAILED','REQUIRED_NATIVE_SETTLEMENT_AND_FEE_CURRENCY_KNOWN'),
        'signed_native_funding':('PERSISTED_FUNDING_JOURNAL_EXPORT_MISMATCH','NATIVE_FUNDING_IDENTITIES_MISMATCH','EXACT_NATIVE_SIGNED_FUNDING_BRIDGE_FAILED'),
        'native_closed_lifecycles':('COMPLETE_NATIVE_POSITION_LIFECYCLES_REQUIRED','EXACT_NATIVE_REALIZED_CASH_BRIDGE_FAILED'),
        'terminal_flat_orders':('NATIVE_TERMINAL_RESIDUE',),
        'original_feed_currency_DP_gates':('FULL_NATIVE_QUOTE_WATERMARK_COVERAGE_FAILED','ORIGINAL_FULL_ACCOUNTING_GATE_FAILED')}
    result={key:all(predicates[name]['passed'] for name in names) for key,names in groups.items()}
    for key,value in result.items():fail(value,'FINANCIAL_CHECK_NOT_PROVEN:'+key)
    result['verified_financial_predicates']=predicates
    return result

def measurer_profile(dd_source,raw,provenance):
    """Explicit admitted request family, never choose whichever hash passes."""
    request_pin=(provenance or {}).get('request')
    fail(type(request_pin) is dict and set(request_pin)=={'path','sha256'},'MEASURER_REQUEST_PIN_REQUIRED')
    request_path=Path(request_pin['path'])
    fail(sha(request_path)==request_pin['sha256'],'MEASURER_REQUEST_HASH_MISMATCH')
    request=json.loads(request_path.read_text());family=request.get('source_family')
    fail(family in ('CM2BTCREF','REFERENCE_BTC_ONLY'),'MEASURER_EXPLICIT_SOURCE_FAMILY_REQUIRED')
    source=Path(dd_source).resolve();observer=source.with_name('paired_observer.py');baseline=source.with_name('native_baseline.py')
    root=Path(request['execution_source_root']).resolve()
    fail(source==root/'runtime/coinmaster/research/minute_risk.py','MEASURER_EXECUTION_SOURCE_ROOT_MISMATCH')
    if family=='CM2BTCREF':
        fail(type(raw.get('cm2')) is dict and raw['cm2']['policy']==request['policy']
            and request['policy']['version']=='cm2-btc-reference-v1','MEASURER_CM2_POLICY_FAMILY_MISMATCH')
        frozen={str(Path(row['path']).resolve()):row['sha256'] for row in request['freeze_files']}
        fail(all(frozen.get(str(p))==sha(p) for p in (source,observer,baseline)),'MEASURER_CM2_FROZEN_SOURCE_MISMATCH')
        return dict(source_family=family,dd_sha256=DD_SHA,observer_sha256=OBSERVER_SHA,
            request_sha256=request_pin['sha256'])
    commit='5b56f7d02e09d4495ac018ec1ce701f6f0dfb737'
    dd_sha='750adf241919554226deebda57310d07e69453150a136f360346214cf5b8c5ac'
    baseline_sha='51a3b736509a7eb38c9af7bf975419a9aef513ec6153f1f9a20433e0fc49df61'
    fail('cm2' not in raw and request['execution_source_commit']==commit
        and request['policy']=={'version':'reference-btc-only-public5b-v1','source_commit':commit,
            'prepared_kwargs_sha256':request['prepared_control_kwargs_sha256']},'MEASURER_REFERENCE_POLICY_FAMILY_MISMATCH')
    manifest_path=Path(request['execution_source_manifest'])
    fail(sha(manifest_path)==request['execution_source_manifest_sha256'],'MEASURER_REFERENCE_MANIFEST_HASH_MISMATCH')
    fail(sha(request['prepared_control_kwargs'])==request['prepared_control_kwargs_sha256'],'MEASURER_REFERENCE_KWARGS_HASH_MISMATCH')
    manifest=json.loads(manifest_path.read_text())
    fail(manifest['commit']==commit and len(manifest['entries'])>=91,'MEASURER_REFERENCE_MANIFEST_INCOMPLETE')
    verified=set()
    for entry in manifest['entries']:
        relative=Path(entry['path']);path=(root/relative).resolve()
        fail(not relative.is_absolute() and path.is_relative_to(root) and str(path) not in verified,'MEASURER_REFERENCE_MANIFEST_PATH')
        content=path.read_bytes();blob=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
        fail(len(content)==entry['bytes'] and blob==entry['git_blob_sha1'],'MEASURER_REFERENCE_MANIFEST_BLOB_MISMATCH')
        verified.add(str(path))
    fail(all(str(p) in verified for p in (source,observer,baseline)),'MEASURER_REFERENCE_REQUIRED_BLOB_MISSING')
    fail(sha(baseline)==baseline_sha==raw['code_hash'],'MEASURER_REFERENCE_PUBLIC_BASELINE_MISMATCH')
    return dict(source_family=family,execution_source_commit=commit,dd_sha256=dd_sha,
        observer_sha256=OBSERVER_SHA,request_sha256=request_pin['sha256'],
        source_manifest_sha256=request['execution_source_manifest_sha256'])


def qualify(report_path,legacy,trace,out,dd_source,coverage_source,engine_count,*,expected_report_sha=None,provenance=None,expected_start_ns=None,expected_end_ns=None):
    """Only derives new files. Never rewrites original report, ledger or money."""
    out=Path(out).resolve();raw_path=Path(report_path).resolve();dd_source=Path(dd_source)
    fail(not any(Path(p).resolve().is_relative_to(out) for p in (raw_path,legacy,trace)),
        "DERIVED_DIRECTORY_MUST_NOT_CONTAIN_OR_REPLACE_RAW_INPUTS")
    fail(not any((out/name).exists() for name in ("QUALIFICATION.json","QUALIFICATION_FAILED.json","minute-native-settled-receipts.csv.gz")),
        "DERIVED_QUALIFICATION_EXISTS_NO_REPLAY")
    out.mkdir(parents=True,exist_ok=True)
    report_sha=sha(raw_path)
    if expected_report_sha is not None:fail(report_sha==expected_report_sha,"ORIGINAL_RAW_REPORT_HASH_MISMATCH")
    raw=json.loads(raw_path.read_text())
    profile=measurer_profile(dd_source,raw,provenance)
    fail(sha(dd_source)==profile['dd_sha256'] and sha(dd_source.with_name("paired_observer.py"))==profile['observer_sha256'],"FROZEN_NATIVE_MEASURER_SOURCE_MISMATCH")
    fail(sha(coverage_source)==COVERAGE_SHA,"QUALIFIED_COVERAGE_SOURCE_MISMATCH")
    source=dd_source.with_name("native_baseline.py")
    fail(sha(source)==raw["code_hash"],"ORIGINAL_NATIVE_BASELINE_SOURCE_MISMATCH")
    fail(engine_count==1,"ONE_ACTUAL_ENGINE_REQUIRED")
    minutes=report_interval(raw,expected_start_ns,expected_end_ns)
    start,end=expected_start_ns,expected_end_ns
    full_scope=(start==START and end==END)
    scope_name='FULL_24M' if full_scope else 'PREFIX'
    raw_status=raw.get('status')
    derived=out/"minute-native-settled-receipts.csv.gz"
    try:
        with localcontext() as ctx:
            ctx.prec=28;ctx.rounding=ROUND_HALF_EVEN
            Tracker=native_reference(dd_source)
            scan=scan_native(raw,legacy,trace,derived,Tracker,start=start,end=end,expected=minutes-1)
            checks=financial_checks(raw,scan,raw["funding_journal"],end=end,minutes=minutes)
            scope={"Decimal":D,"datetime":datetime,"timezone":timezone,"timedelta":timedelta,"localcontext":localcontext}
            boundary_result=functions(source,["assert_report_boundaries"],scope)["assert_report_boundaries"](raw)
            boundary_verified=(boundary_result is None)
            fail(boundary_verified,'UNCHANGED_BOUNDARY_HELPER_NOT_COMPLETED')
            cvscope={"csv":csv,"gzip":gzip,"Counter":Counter,"datetime":datetime,"timezone":timezone,"sha":sha}
            if full_scope:
                coverage=functions(coverage_source,["coverage"],cvscope)["coverage"](raw,out)
                fail(coverage["full"],"UNCHANGED_QUALIFIED_COVERAGE_NOT_FULL")
            else:coverage=interval_coverage(derived,start,end)
            expected_months=expected_month_rows(start,end)
            interval_complete=(coverage['rows']==minutes-1 and coverage['first_source_ns']==start+MIN
                and coverage['last_receipt_ns']==end and coverage['month_rows']==expected_months
                and coverage['source_calendar_months']==len(expected_months) and coverage['month_counts_complete'])
            fail(interval_complete,'DECLARED_INTERVAL_CSV_COVERAGE')
            scan_guards=scan['verified_predicates']
            checks.update(declared_interval_coverage=interval_complete,
                exact_native_DD=scan['exact_interval_DD_parity'],
                retained_before_mutation=all(v['passed'] for k,v in scan_guards.items() if k.startswith(('INVALID_RETAINED','RETAINED_NATIVE','LEGACY_GAP_HAS'))),
                all_surviving_legacy_rows=all(v['passed'] for k,v in scan_guards.items() if k.startswith(('LEGACY_','SURVIVING_LEGACY'))),
                unchanged_606_boundaries=boundary_verified and sha(dd_source)==profile['dd_sha256'] and sha(dd_source.with_name('paired_observer.py'))==profile['observer_sha256'],
                one_actual_engine=(engine_count==1))
            if full_scope:checks['full_24months']=full_scope and bool(coverage['full']) and interval_complete
            for key,value in checks.items():
                if key!='verified_financial_predicates':fail(value,'REQUIRED_QUALIFICATION_CHECK_FALSE:'+key)
        public_scan={k:v for k,v in scan.items() if k not in ("fill_ids","funding_ids","terminal_native_cash","native_fill_cash_delta","native_funding_cash_delta")}
        receipt={"status":"FINANCIAL_QUALIFICATION_PASS","qualification_model_id":MODEL,
            "original_report_sha256":report_sha,"original_report_path":str(raw_path),
            "original_physical_status_preserved":sha(raw_path)==report_sha and json.loads(raw_path.read_text()).get("status")==raw_status,"new_native_engine_constructions":0,"actual_engine_constructions":engine_count,
            "parent_raw_model_ids":{"policy_hash":raw.get("policy_hash"),"data_hash":raw.get("data_hash"),
                "code_hash":raw.get("code_hash"),"source_hashes":raw.get("source_hashes"),"config_hash":raw.get("config_hash")},
            "checks":checks,"native_watermark_proof":public_scan,"coverage":coverage,"measurer_source_profile":profile,
            "scope":scope_name,"request_interval_ns":[start,end],"full_24months":full_scope and bool(coverage["full"]),
            "input_hashes":{"legacy_csv":sha(legacy),"coherent_trace":sha(trace),"funding_sqlite":sha(raw["funding_journal"]),
                "native_DD_source":sha(dd_source),"native_observer_source":sha(dd_source.with_name("paired_observer.py")),
                "coverage_source":sha(coverage_source),"qualifier_source":sha(__file__)},
            "derived_csv":str(derived),"derived_csv_sha256":sha(derived),
            "comparability":"SAME_PERSISTED_NATIVE_MONEY; NEW_STRICT_COMMITTED_WM_QUALIFICATION; ORIGINAL_SOURCE_IDS_PRESERVED_NOT_RELABELED",
            "legacy_receipt_status":"SPARSE_UNAVAILABLE_AFTER_INTERVENING_MUTATION_NOT_SILENTLY_COMPLETE",
            "provenance":provenance or {}}
        qualified=copy.deepcopy(raw)
        qualified["committed_wm_qualification"]={k:receipt[k] for k in ("qualification_model_id","original_report_sha256","checks","comparability")}
        if 'cm2' in qualified:qualified['cm2'].update(accounting_status='PASS',financial_checks=checks)
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
    p.add_argument("--start-ns",type=int,required=True);p.add_argument("--end-ns",type=int,required=True)
    for name in ("request","go","ledger"):p.add_argument("--"+name,type=Path,required=True)
    args=p.parse_args(argv)
    engine=json.loads(args.engine_count.read_text())["engine_constructions"]
    receipt=qualify(args.report,args.legacy,args.trace,args.out,args.dd_source,args.coverage_source,engine,
        expected_report_sha=args.expected_report_sha256,expected_start_ns=args.start_ns,expected_end_ns=args.end_ns,provenance=provenance_files(args.request,args.go,args.ledger,args.engine_count))
    print(json.dumps({"status":receipt["status"],"qualification_model_id":MODEL,
        "wm_rows":receipt["native_watermark_proof"]["wm_rows"],"legacy_missing":receipt["native_watermark_proof"]["legacy_missing"],
        "new_native_engine_constructions":0}))

if __name__=="__main__":main()
