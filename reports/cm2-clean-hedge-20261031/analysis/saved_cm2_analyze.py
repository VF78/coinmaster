"""CM2 saved-native analysis only. No engines, product imports, money simulation."""
from __future__ import annotations
import argparse,ast,copy,csv,gzip,hashlib,io,json,re,sys
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime,timezone
from decimal import Decimal as D,localcontext,ROUND_HALF_EVEN
from pathlib import Path

MIN=60_000_000_000
THRESHOLD=D(20)
ALGORITHM="CM2_NATIVE_SAVED_28_HALFEVEN_TERMINAL_CLOSE_V1"

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

def load(path): return json.loads(Path(path).read_text())
def dump(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(value,indent=2,sort_keys=True,default=str)+"\n")
    temporary.replace(path)

def number(value):
    try:
        result=D(str(value))
        return result if result.is_finite() else None
    except Exception: return None

def textnum(value): return str(value) if value is not None else None
def epoch(value): return int(datetime.fromisoformat(value.replace("Z","+00:00")).timestamp())*1_000_000_000
def utc(value):
    return "INITIAL_SEED" if int(value)==0 else datetime.fromtimestamp(int(value)/1e9,timezone.utc).isoformat()

def csvwrite(path,rows,fields):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        writer.writeheader();writer.writerows(rows)

def native_tracker(source):
    """Compile ONLY the frozen pure native tracker class, not module imports."""
    tree=ast.parse(Path(source).read_text())
    node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="DrawdownTracker")
    scope={"D":D,"__name__":"cm2_saved_native_drawdown_reference"}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),"exec"),scope)
    Native=scope["DrawdownTracker"]
    class RecordingNative(Native):
        def __init__(self,seed):
            super().__init__(seed);self.all_ge20=[]
        def _retain(self,episode):
            # Native formula/order/tie semantics twice, no alternate DD formula.
            single=Native(self.seed);single._retain(episode)
            item=single.top[0]
            percent=number(item["drawdown_peak_percent"])
            if percent is None or percent>=THRESHOLD:self.all_ge20.append(copy.deepcopy(item))
            super()._retain(episode)
    return Native,RecordingNative

def maxdd(summary):
    episodes=summary.get("top3_distinct_excursions",[])
    return number(episodes[0]["drawdown_peak_percent"]) if episodes else D(0)

def equivalent(got,expected):
    keys=("samples","minimum","maximum_loss_below_seed_amount",
          "maximum_loss_below_seed_percent","top3_distinct_excursions")
    return [key for key in keys if got.get(key)!=expected.get(key)]

class HashReader:
    def __init__(self,path):
        self.file=Path(path).open("rb");self.hash=hashlib.sha256()
    def read(self,n=-1):
        block=self.file.read(n);self.hash.update(block);return block
    def tell(self):return self.file.tell()
    def seekable(self):return False
    def close(self):self.file.close()

@contextmanager
def lines(path):
    raw=HashReader(path)
    wrapped=gzip.GzipFile(fileobj=raw,mode="rb") if str(path).endswith(".gz") else raw
    decoded=io.TextIOWrapper(wrapped,encoding="utf-8")
    try:yield decoded,raw.hash
    finally:
        decoded.close();raw.close()

def month_boundaries(start,end):
    d=datetime.fromtimestamp(start//1_000_000_000,timezone.utc)
    d=d.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    out=[]
    while int(d.timestamp())*1_000_000_000<end:
        following=d.replace(year=d.year+(d.month==12),month=1 if d.month==12 else d.month+1)
        out.append((d.strftime("%Y-%m"),int(following.timestamp())*1_000_000_000))
        d=following
    return out

def episode_rows(tracker,basis,start,last_ns):
    result=[]
    for e in tracker.all_ge20:
        row={"status":"OBSERVED_NATIVE_EQUITY_EXCURSION","unknown_reason":None,"basis":basis,"DD_percent":e["drawdown_peak_percent"],"drawdown_amount":e["drawdown_amount"],
             "ongoing_censored":e["recovery"] is None,"censored_at_native_ns":str(last_ns) if e["recovery"] is None else None}
        for name in ("peak","trough","recovery"):
            p=e[name]
            row.update({name+"_native_ns":p["timestamp_ns"] if p else None,
                name+"_sequence_id":p.get("sequence_id") if p else None,
                name+"_equity":p["equity"] if p else None,
                name+"_utc":utc(p["timestamp_ns"]) if p else None})
        finish=int(e["recovery"]["timestamp_ns"]) if e["recovery"] else last_ns
        row["time_underwater_seconds"]=str(D(max(0,finish-max(start,int(e["peak"]["timestamp_ns"]))))/D(1e9))
        result.append(row)
    return result

def stream_curves(report,settled_path,trace_path,Recording):
    obs=report["coherent_native_observer"]
    seed=number(obs["native_cash_transitions"]["seed"])
    if seed is None or seed<=0:raise ValueError("POSITIVE_ACTUAL_NATIVE_SEED_REQUIRED")
    start=epoch(report["run_interval"]["start"]);end=epoch(report["run_interval"]["end_exclusive"])
    settled=Recording(seed);event=Recording(seed)
    settled.add(0,seed);event.add(0,seed)
    bs=month_boundaries(start,end);month_values={};month_index=0;n=0;sequence=0;boundary=False
    final=None;errors=[];bounds_unknown=[];last_event_ns=start
    stats={"opposite_sign_samples":0,"same_sign_samples":0,"SOL_without_BTC_samples":0,
        "SOL_increase_with_flat_BTC_count":0,"SOL_increase_with_opposite_BTC_count":0,
        "native_SOL_zero_to_nonzero_with_opposite_BTC":0,
        "max_actual_gross_notional":D(0),"max_actual_gross_to_positive_native_equity":D(0)}
    last_sol=D(0);orphan=None;orphans=[];last_state_time=None
    committed_kinds={"POST_FILL_COMMITTED_NATIVE","POST_FUNDING_ACCOUNT_NATIVE",
        "PREQUOTE_DIRECT_NATIVE","DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED"}
    with lines(settled_path) as (receipt_file,receipt_hash),lines(trace_path) as (trace_file,trace_hash):
        receipts=csv.DictReader(receipt_file)
        for line in trace_file:
            row=json.loads(line)
            if int(row["sequence"])!=sequence+1:raise ValueError("COHERENT_SEQUENCE_GAP")
            sequence+=1
            ns=int(row["event_ns"]);kind=row["kind"];value=number(row.get("equity"))
            if kind=="SETTLED_PRE_NEXT_SOURCE_WATERMARK":
                try:r=next(receipts)
                except StopIteration:raise ValueError("SETTLED_CSV_SHORT")
                source=int(r["source_quote_ns"]);received=int(r["receipt_ns"])
                if source!=start+MIN+n*MIN or received!=source+MIN:
                    raise ValueError("SETTLED_SEQUENCE_OR_RECEIPT_DRIFT")
                if source!=ns or received!=int(row["receipt_ns"]) or number(r["paired_close_equity"])!=value or number(r["cash"])!=number(row["cash"]):
                    raise ValueError("TWO_NATIVE_SETTLED_EXPORTS_DISAGREE")
                if value is None:raise ValueError("UNKNOWN_NATIVE_SETTLED_EQUITY")
                settled.add(source,value);n+=1
                while month_index<len(bs)-1 and source>=bs[month_index][1]:month_index+=1
                month_values[bs[month_index][0]]={"source_ns":str(source),"receipt_ns":str(received),
                    "settled_source_cash":r["cash"],"marked_settled_equity":r["paired_close_equity"]}
                continue
            left=(ns==end and not boundary and kind in
                {"PREQUOTE_DIRECT_NATIVE","PRE_FILL_LAST_COMMITTED_NATIVE_COPY","PRE_FUNDING_COMMITTED_NATIVE_COPY"})
            if value is not None and (ns<end or left):
                event.add(sequence,value,sequence_id=sequence,timestamp_ns=ns)
                last_event_ns=ns
                if left:boundary=True
            if kind=="DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED":
                if ns!=end or row.get("positions") or number(row["cash"])!=value:
                    raise ValueError("TERMINAL_NATIVE_FLAT_CASH_NOT_PROVEN")
                final={"sequence":sequence,"ns":ns,"cash":str(value)}
            if kind not in committed_kinds:continue
            # Actual committed/native snapshot facts only, no adapter quote-lag interval.
            positions={}
            for p in row.get("positions",[]):
                symbol=p["instrument_id"].split("-")[0]
                if symbol not in ("BTC","SOL"):raise ValueError("FOREIGN_NATIVE_POSITION")
                q=D(p["quantity"])*(D(1) if p["side"]=="LONG" else D(-1))
                positions[symbol]=(q,D(p["native_price"]))
            b,bp=positions.get("BTC",(D(0),D(0)));s,sp=positions.get("SOL",(D(0),D(0)))
            if b and s:stats["opposite_sign_samples" if b*s<0 else "same_sign_samples"]+=1
            if s and not b:stats["SOL_without_BTC_samples"]+=1
            if kind=="POST_FILL_COMMITTED_NATIVE" and abs(s)>abs(last_sol):
                if not b:stats["SOL_increase_with_flat_BTC_count"]+=1
                elif b*s<0:
                    stats["SOL_increase_with_opposite_BTC_count"]+=1
                    if last_sol==0:stats["native_SOL_zero_to_nonzero_with_opposite_BTC"]+=1
            last_sol=s
            gross=abs(b*bp)+abs(s*sp)
            stats["max_actual_gross_notional"]=max(stats["max_actual_gross_notional"],gross)
            if value is not None and value>0:
                stats["max_actual_gross_to_positive_native_equity"]=max(stats["max_actual_gross_to_positive_native_equity"],gross/value)
            if last_state_time is not None and ns<last_state_time:
                bounds_unknown.append("NONMONOTONE_COMMITTED_EVENT_CLOCK_ORPHAN_BOUNDS_UNKNOWN")
            last_state_time=ns
            if s and not b and orphan is None:orphan={"start_ns":str(ns),"start_sequence":sequence}
            if orphan is not None and (not s or b):
                orphans.append({**orphan,"end_ns":str(ns),"end_sequence":sequence,
                    "native_event_clock_seconds":str(D(ns-int(orphan["start_ns"]))/D(1e9)) if ns>=int(orphan["start_ns"]) else None,
                    "physical_or_parent_exact_duration":"UNKNOWN_NATIVE_M1_EVENT_CLOCK_ONLY"})
                orphan=None
        if next(receipts,None) is not None:raise ValueError("SETTLED_CSV_LONG")
        hashes={"settled_receipts":receipt_hash.hexdigest(),"coherent_trace":trace_hash.hexdigest()}
    if n!=(end-start)//MIN-1 or n!=int(obs["settled_receipts"]):
        raise ValueError("FULL_SETTLED_COVERAGE_FAILED")
    if len(month_values)!=len(bs):raise ValueError("MONTHLY_SETTLED_ENDPOINT_MISSING")
    for label,bound in bs:
        m=month_values[label]
        if int(m["source_ns"])!=bound-MIN or int(m["receipt_ns"])!=bound:
            raise ValueError("UNMATCHED_MONTHLY_NATIVE_ENDPOINT")
    if sequence!=int(obs["sequence_count"]):raise ValueError("COHERENT_SEQUENCE_COUNT_FAILED")
    if final is None or number(final["cash"])!=number(report["terminal_total"]) or number(final["cash"])!=number(obs["terminal_actual_cash"]):
        raise ValueError("ACTUAL_TERMINAL_CASH_MISMATCH")
    if orphan is not None:errors.append("ONGOING_NATIVE_ORPHAN_AT_TERMINAL")
    interval_s=copy.deepcopy(settled);interval_e=copy.deepcopy(event)
    raw_s=interval_s.summary();raw_e=interval_e.summary()
    errors+=["SETTLED:"+x for x in equivalent(raw_s,obs["settled_drawdown"])]
    errors+=["COHERENT:"+x for x in equivalent(raw_e,obs["event_drawdown"])]
    episodes=episode_rows(interval_s,"INTERVAL_SETTLED",start,end-MIN)+episode_rows(interval_e,"INTERVAL_COHERENT",start,last_event_ns)
    # Append ONLY the actual persisted post-terminal-flat cash, not estimated fees.
    settled.add(end,D(final["cash"]))
    event.add(final["sequence"],D(final["cash"]),sequence_id=final["sequence"],timestamp_ns=end)
    strict_s=settled.summary();strict_e=event.summary()
    episodes+=episode_rows(settled,"WITH_FINAL_CLOSE_SETTLED",start,end)+episode_rows(event,"WITH_FINAL_CLOSE_COHERENT",start,end)
    return {"input_hashes":hashes,"interval_settled":raw_s,"interval_coherent":raw_e,
        "with_final_close_settled":strict_s,"with_final_close_coherent":strict_e,
        "all_dd_ge20":episodes,"monthly":month_values,"native_terminal_flat_cash_point":final,
        "structural_native_samples":{k:textnum(v) if isinstance(v,D) else v for k,v in stats.items()},
        "native_clock_orphans":orphans,"structural_bounds_unknown":list(dict.fromkeys(bounds_unknown)),"errors":errors,"seed":str(seed),"start_ns":start,"end_ns":end}

def allocations(report):
    result={asset:{"fills":0,"turnover":D(0),"native_fees":D(0),"signed_native_funding":D(0),"native_realized_includes_fees":D(0)}
            for asset in ("BTC","SOL")}
    unknown=[]
    fills=report.get("fill_audit")
    if not isinstance(fills,list):return None,["NATIVE_FILL_AUDIT_MISSING"]
    for f in fills:
        asset=f["instrument"].split("-")[0]
        if asset not in result:unknown.append("FOREIGN_FILL_ASSET");continue
        result[asset]["fills"]+=1
        for target,field in (("turnover","notional"),("native_fees","commission")):
            value=number(f.get(field))
            if value is None:unknown.append("NATIVE_"+field.upper()+"_MISSING");result[asset][target]=None
            elif result[asset][target] is not None:result[asset][target]+=value
    funding=report.get("funding_cash_audit")
    if not isinstance(funding,list):
        unknown.append("SIGNED_NATIVE_FUNDING_ALLOCATION_MISSING")
        for v in result.values():v["signed_native_funding"]=None
    else:
        for r in funding:
            asset=r[1].split("-")[0]
            if asset in result:result[asset]["signed_native_funding"]+=D(str(r[5]))
    lifecycles=report.get("native_cash_reconciliation",{}).get("native_position_lifecycle_export",{})
    lives=lifecycles.get("positions")
    if not isinstance(lives,list) or lifecycles.get("unknown") or any(not p.get("closed") or number(p.get("realized_pnl")) is None for p in lives):
        unknown.append("COMPLETE_NATIVE_REALIZED_LIFECYCLES_MISSING")
        for v in result.values():v["native_realized_includes_fees"]=None
    else:
        for p in lives:
            asset=p["instrument_id"].split("-")[0]
            if asset in result:result[asset]["native_realized_includes_fees"]+=D(p["realized_pnl"])
    return {a:{k:textnum(v) if isinstance(v,D) else v for k,v in fields.items()} for a,fields in result.items()},unknown

DD_FIELDS=["status","unknown_reason","basis","DD_percent","drawdown_amount","ongoing_censored",
    "censored_at_native_ns","peak_native_ns","peak_sequence_id","peak_equity","peak_utc",
    "trough_native_ns","trough_sequence_id","trough_equity","trough_utc",
    "recovery_native_ns","recovery_sequence_id","recovery_equity","recovery_utc","time_underwater_seconds"]

def empty_case_outputs(target,case_id,reason):
    months=[{"case":case_id,"month":label,"marked_settled_equity":None,"settled_source_cash":None,
        "native_account_monthly_cash_total":None,"native_account_monthly_cash_return":None,
        "marked_settled_equity_return_ratio":None,"unknown_reason":reason}
        for label,_ in month_boundaries(1725148800000000000,1788220800000000000)]
    csvwrite(target/"MONTHLY_24.csv",months,list(months[0]))
    csvwrite(target/"ALL_DD_GE20.csv",[{"status":"UNKNOWN","unknown_reason":reason,"basis":"UNKNOWN","DD_percent":None}],DD_FIELDS)

def derived_input(case,physical_status):
    """Accept financial recovery only from a fully hash-bound strict receipt."""
    receipt_path=case.get("derived_receipt")
    if not receipt_path:return case,None
    if physical_status not in ("FAILED","COMPLETED"):
        raise ValueError("DERIVED_RECOVERY_REQUIRES_TERMINAL_PHYSICAL_RECORD")
    proof=load(receipt_path)
    required={"native_cash","native_fees","signed_native_funding","native_closed_lifecycles",
        "terminal_flat_orders","original_full_feed_currency_DP_gates","full_24months","exact_native_DD",
        "retained_before_mutation","all_surviving_legacy_rows","unchanged_606_boundaries","one_actual_engine"}
    if (proof.get("status")!="FINANCIAL_QUALIFICATION_PASS"
        or proof.get("qualification_model_id")!="CM2_COMMITTED_NATIVE_WM_QUALIFICATION_V1"
        or proof.get("new_native_engine_constructions")!=0
        or not required.issubset(proof.get("checks",{})) or any(v is not True for v in proof["checks"].values())):
        raise ValueError("DERIVED_FINANCIAL_PROOF_NOT_PASS")
    if sha(case["native_report"])!=proof["original_report_sha256"]:
        raise ValueError("DERIVED_ORIGINAL_REPORT_HASH_MISMATCH")
    if not case.get("qualifier_source") or sha(case["qualifier_source"])!=proof["input_hashes"]["qualifier_source"]:
        raise ValueError("DERIVED_REVIEWED_QUALIFIER_SOURCE_REQUIRED")
    for field,path in (("legacy_csv",case["settled_receipts"]),("coherent_trace",case["coherent_trace"])):
        if sha(path)!=proof["input_hashes"][field]:raise ValueError("DERIVED_RAW_STREAM_HASH_MISMATCH")
    if sha(proof["derived_report"])!=proof["derived_report_sha256"] or sha(proof["derived_csv"])!=proof["derived_csv_sha256"]:
        raise ValueError("DERIVED_OUTPUT_HASH_MISMATCH")
    provenance=proof.get("provenance",{})
    for key,field in (("request","request"),("GO","go"),("engine_count","engine_count")):
        witness=provenance.get(key)
        if physical_status=="FAILED" and witness is None:
            raise ValueError("FAILED_PHYSICAL_RECOVERY_METADATA_WITNESS_REQUIRED")
        if witness is not None and (not case.get(field) or sha(case[field])!=witness["sha256"]):
            raise ValueError("DERIVED_METADATA_HASH_MISMATCH")
    prefix=provenance.get("ledger_prefix")
    if prefix is None:raise ValueError("DERIVED_ORIGINAL_LEDGER_PREFIX_REQUIRED")
    ledger=Path(case.get("_ledger_path",prefix["path"])).read_bytes()
    if len(ledger)<prefix["bytes"] or hashlib.sha256(ledger[:prefix["bytes"]]).hexdigest()!=prefix["sha256"]:
        raise ValueError("ORIGINAL_PHYSICAL_LEDGER_PREFIX_CHANGED")
    replacement=dict(case)
    replacement["native_report"]=proof["derived_report"]
    replacement["settled_receipts"]=proof["derived_csv"]
    return replacement,proof

def analyze_case(case,rows,out,dd_source):
    case_id=case["case"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+",case_id):raise ValueError("UNSAFE_CASE_ID")
    target=out/case_id;target.mkdir(parents=True,exist_ok=True)
    run_id=case.get("run_id",case_id)
    matching=[r for r in rows if r.get("run_id")==run_id and r.get("status") in {"STARTED","COMPLETED","FAILED","PARENT_INTERRUPTED_CHILD_STATE_UNKNOWN"}]
    terminal=matching[-1].get("status") if matching else "UNKNOWN"
    base={"case":case_id,"run_id":run_id,"physical_status":terminal,"TOTAL":None,"net_profit":None,"ROI_fraction":None,
        "financial_status":"UNKNOWN","structural_status":"UNKNOWN","numeric_goal_status":"UNKNOWN",
        "robustness_status":"NOT_RUN","persistence_status":"NOT_IMPLEMENTED_FRESH_RESEARCH_ONLY",
        "model_status":"MODEL_LIMITED_M1_BYBIT_USDT_PRICES_CURRENT_HL_USDC_PROXY","unknown_reasons":[],
        "interval_DD_percent":{"settled":None,"coherent":None},"with_final_close_DD_percent":{"settled":None,"coherent":None}}
    recovery=None
    if case.get("derived_receipt"):
        case,recovery=derived_input(case,terminal)
    if (terminal!="COMPLETED" and recovery is None) or case.get("stage")=="engineering" or not case.get("native_report"):
        base["unknown_reasons"].append("NOT_A_COMPLETED_CANONICAL_ANCHOR_INPUT_NO_STREAMS_READ")
        empty_case_outputs(target,case_id,base["unknown_reasons"][0])
        dump(target/"SUMMARY.json",base);return base
    report_path=Path(case["native_report"]);report=load(report_path);report_hash=sha(report_path)
    key=hashlib.sha256((ALGORITHM+sha(__file__)+sha(dd_source)+report_hash+case_id).encode()).hexdigest()
    cache=out/".cache"/(key+".json")
    _,Recording=native_tracker(dd_source)
    if cache.exists():
        curves=load(cache)
        for field in ("settled_receipts","coherent_trace"):
            if sha(case[field])!=curves["input_hashes"][field]:raise ValueError("IMMUTABLE_COMPLETED_STREAM_HASH_CHANGED")
        cache_used=True
    else:
        with localcontext() as ctx:
            ctx.prec=28;ctx.rounding=ROUND_HALF_EVEN
            curves=stream_curves(report,case["settled_receipts"],case["coherent_trace"],Recording)
        dump(cache,curves);cache_used=False
    money=report.get("native_cash_reconciliation",{});obs=report.get("coherent_native_observer",{})
    engine=load(case["engine_count"]) if case.get("engine_count") else {}
    expected_months=[label for label,_ in month_boundaries(curves["start_ns"],curves["end_ns"])]
    actual_cash_months=report.get("summary",{}).get("monthly_returns",[])
    checks={"native_report_financial":report.get("cm2",{}).get("accounting_status")=="PASS",
        "all_native_financial_checks":bool(report.get("cm2",{}).get("financial_checks")) and all(v is True for v in report["cm2"]["financial_checks"].values()),
        "native_cash_bridge":money.get("status")=="EXACT" and number(money.get("unallocated_bridge"))==0,
        "committed_cash_bridge":number(money.get("actual_native_cash_transitions",{}).get("exact_bridge"))==0,
        "native_fees_reconciled":report.get("fee_attribution",{}).get("reconciled") is True,
        "coherent_complete":obs.get("status")=="PASS" and not obs.get("unknown"),
        "curve_exact":not curves["errors"],"one_actual_engine":engine.get("engine_constructions")==1,
        "all_monthly_cash_rows":[r.get("month") for r in actual_cash_months]==expected_months and all(number(r.get("total")) is not None for r in actual_cash_months),
        "canonical_24months":curves["start_ns"]==1725148800000000000 and curves["end_ns"]==1788220800000000000,
        "native_finite_money_fields":all(number(v) is not None for v in (report.get("terminal_total"),report.get("native_fees"),money.get("signed_funding"))),
        "native_terminal_flat":report.get("terminal_open_positions")==0 and report.get("terminal_lifecycle",{}).get("status")=="FLAT"}
    financial=all(checks.values())
    total=number(report.get("terminal_total"));seed=number(curves["seed"])
    rawdd={k:textnum(maxdd(curves["interval_"+k])) for k in ("settled","coherent")}
    strictdd={k:textnum(maxdd(curves["with_final_close_"+k])) for k in ("settled","coherent")}
    stats=curves["structural_native_samples"]
    conflicts=[]
    if stats["same_sign_samples"]:conflicts.append("SAME_SIGN_NATIVE_SAMPLES_REQUIRES_PARENT_DRAIN_CONTEXT")
    if stats["SOL_increase_with_flat_BTC_count"]:conflicts.append("SOL_INCREASE_WITH_FLAT_BTC_PARENT_OR_LATEFILL_CONTEXT_UNKNOWN")
    request=load(case["request"]) if case.get("request") else {}
    effective_policy=report.get("cm2",{}).get("policy",report.get("config",{}).get("cm2",{}))
    mode=effective_policy.get("mode",request.get("policy",{}).get("mode","UNKNOWN"))
    unknown=["JOINT_PARENT_LINEAGE_NOT_EXPORTED","PER_EVENT_BETA_FACTOR_GUARD_NOT_EXPORTED",
        "CONDITIONAL_TAIL_RISK_BENEFIT_NOT_CAUSALLY_PROVEN","SOL_WINNER_PROFIT_IS_NOT_COUNTERFACTUAL_HEDGE_BENEFIT",
        "PHYSICAL_ORPHAN_LATENCY_UNKNOWN_NATIVE_EVENT_CLOCK_IS_NOT_VENUE_LATENCY"]
    if mode in ("btc_only","btc_trim"):unknown.append("MATCHED_CONTROL_HEDGE_CONTRACT_NOT_APPLICABLE")
    alloc,alloc_unknown=allocations(report)
    measurement=report.get("cm2",{}).get("liquidation_measurement",{})
    liq=report.get("liquidation_count")
    risk_known=isinstance(liq,int) and measurement.get("unknown_checks")==0
    numeric=None if not financial or total is None or not risk_known else (
        total>=D(5600000) and all(D(v)<=45 for v in strictdd.values()) and liq==0)
    base.update(TOTAL=str(total) if financial and total is not None else None,
        raw_native_TOTAL=textnum(total),native_seed=str(seed),net_profit=str(total-seed) if financial and total is not None else None,
        ROI_fraction=str(total/seed-1) if financial and total is not None else None,
        financial_status="PASS" if financial else "FAIL",financial_checks=checks,
        structural_status="UNKNOWN",structural_observed_conflicts=conflicts,
        numeric_goal_status="UNKNOWN" if numeric is None else "PASS" if numeric else "FAIL",
        interval_DD_percent=rawdd,with_final_close_DD_percent=strictdd,
        interval_native_drawdown_raw={"settled":obs.get("settled_drawdown"),"coherent":obs.get("event_drawdown")},
        terminal_flat_cash_point=curves["native_terminal_flat_cash_point"],
        drawdown_basis={"interval":"UNCHANGED_NATIVE_EVENT_AND_SETTLED_INTERVAL_POINTS",
            "with_final_close":"SAME_POINTS_PLUS_ACTUAL_NATIVE_POST_TERMINAL_FLAT_CASH_NO_FEE_EXCLUSION"},
        native_fees=report.get("native_fees"),signed_native_funding=money.get("signed_funding"),
        native_allocations=alloc,liquidations=liq,liquidation_measurement_known=risk_known,
        terminal_open_positions=report.get("terminal_open_positions"),terminal_lifecycle=report.get("terminal_lifecycle"),
        structural_native_samples=stats,native_clock_orphan_count=len(curves["native_clock_orphans"]),
        unproven_structural_metrics={"joint_parent_lineage":None,"beta_factor_flip_fraction":None,
            "conditional_adverse_tail_benefit":None,"hedge_marginal_counterfactual_benefit":None,
            "venue_position_time_or_latency":None},
        structural_bounds_unknown=curves["structural_bounds_unknown"],
        mode=mode,
        qualification_model_id=recovery["qualification_model_id"] if recovery else None,
        financial_recovery_status="HASH_BOUND_DERIVED_COMMITTED_PROOF_PASS" if recovery else "NOT_APPLIED",
        original_physical_status_preserved=terminal,
        unknown_reasons=unknown+alloc_unknown+curves["errors"]+curves["structural_bounds_unknown"],
        cache_reused=cache_used,
        provenance={"algorithm":ALGORITHM,"report_sha256":report_hash,"stream_sha256":curves["input_hashes"],
            "native_dd_source_sha256":sha(dd_source),
            "native_observer_source_sha256":sha(Path(dd_source).with_name("paired_observer.py")),
            "analyzer_sha256":sha(__file__),
            "request_sha256":sha(case["request"]) if case.get("request") else None,
            "GO_sha256":sha(case["go"]) if case.get("go") else None,
            "source_hashes":report.get("source_hashes"),"config_hash":report.get("config_hash"),
            "data_hash":report.get("data_hash"),"policy_hash":report.get("policy_hash")})
    if recovery:
        base["provenance"]["original_report_sha256"]=recovery["original_report_sha256"]
        base["provenance"]["derived_receipt_sha256"]=sha(case["derived_receipt"])
        base["provenance"]["qualification_model_id"]=recovery["qualification_model_id"]
    cash_months={r["month"]:r for r in report.get("summary",{}).get("monthly_returns",[])}
    monthly=[];previous=seed
    for label,_ in month_boundaries(curves["start_ns"],curves["end_ns"]):
        point=curves["monthly"][label];equity=D(point["marked_settled_equity"]);cash=cash_months.get(label,{})
        monthly.append({"case":case_id,"month":label,**point,
            "native_account_monthly_cash_total":cash.get("total"),"native_account_monthly_cash_return":cash.get("return"),
            "marked_settled_equity_return_ratio":str(equity/previous-1) if previous>0 else None,
            "marked_return_unknown_reason":"NONPOSITIVE_PRIOR_NATIVE_EQUITY" if previous<=0 else None,
            "boundary_convention":"SOURCE_LAST_MINUTE_BEFORE_UTC_MONTH_BOUNDARY_RECEIPT_AT_BOUNDARY; CASH_EXPORT_SEPARATE; TERMINAL_CLOSE_EXCLUDED_HERE"})
        previous=equity
    base["matched_early_and_calendar_endpoints"]={m["month"]:m for m in monthly
        if m["month"] in ("2024-09","2024-10","2024-12","2025-12","2026-08")}
    pins={"source_hashes":report.get("source_hashes"),"data_hash":report.get("data_hash"),
        "execution_policy_hash":report.get("policy_hash"),"seed":str(seed),
        "run_interval":report.get("run_interval"),"fees":report.get("config",{}).get("fixed_base_fee_policy"),
        "currency":report.get("config",{}).get("accounting_currency")}
    base["comparison_group_hash"]=hashlib.sha256(json.dumps(pins,sort_keys=True).encode()).hexdigest()
    matched={**pins,"effective_economic_policy_except_control_mode":{k:v for k,v in effective_policy.items() if k!="mode"}}
    base["matched_control_group_hash"]=hashlib.sha256(json.dumps(matched,sort_keys=True).encode()).hexdigest()
    adapter_intervals=report.get("cm2",{}).get("orphan_intervals",[])
    base["adapter_orphan_observation_bounds"]={"count":len(adapter_intervals),
        "maximum_quote_observation_upper_bound_seconds":str(max((D(int(r["end_ns"])-int(r["start_ns"]))/D(1e9) for r in adapter_intervals),default=D(0))),
        "basis":"NEXT_QUOTE_OBSERVATION_UPPER_BOUND_NOT_ACTUAL_NATIVE_EXPOSURE_DURATION"}
    csvwrite(target/"MONTHLY_24.csv",monthly,list(monthly[0]) if monthly else ["case","month"])
    eps=curves["all_dd_ge20"]
    csvwrite(target/"ALL_DD_GE20.csv",eps,DD_FIELDS)
    orphans=curves["native_clock_orphans"]
    csvwrite(target/"NATIVE_EVENT_CLOCK_ORPHANS.csv",orphans,list(orphans[0]) if orphans else ["start_ns","end_ns","native_event_clock_seconds"])
    dump(target/"SUMMARY.json",base);return base

def compare(summaries,out):
    rows=[]
    for s in summaries:
        rows.append({"case":s["case"],"run_id":s["run_id"],"physical_status":s["physical_status"],
            "financial_status":s["financial_status"],"structural_status":s["structural_status"],
            "numeric_goal_status":s["numeric_goal_status"],"TOTAL":s["TOTAL"],"comparison_group_hash":s.get("comparison_group_hash"),
            "report_sha256":s.get("provenance",{}).get("report_sha256"),
            "mode":s.get("mode"),"matched_control_group_hash":s.get("matched_control_group_hash"),
            "settled_DD_including_final_close":s["with_final_close_DD_percent"]["settled"],
            "coherent_DD_including_final_close":s["with_final_close_DD_percent"]["coherent"],
            "robustness_status":s["robustness_status"],"persistence_status":s["persistence_status"]})
    usable=[r for r in rows if r["financial_status"]=="PASS" and r["TOTAL"] is not None]
    repeated={r["report_sha256"] for r in usable if sum(x["report_sha256"]==r["report_sha256"] for x in usable)>1}
    for r in rows:
        if r not in usable or r["report_sha256"] in repeated:r["pareto_native_numeric"]=None;continue
        dd=max(D(r["settled_DD_including_final_close"]),D(r["coherent_DD_including_final_close"]))
        r["pareto_native_numeric"]=not any(D(x["TOTAL"])>=D(r["TOTAL"]) and
            max(D(x["settled_DD_including_final_close"]),D(x["coherent_DD_including_final_close"]))<=dd and
            (D(x["TOTAL"])>D(r["TOTAL"]) or max(D(x["settled_DD_including_final_close"]),D(x["coherent_DD_including_final_close"]))<dd)
            for x in usable if x is not r and x["comparison_group_hash"]==r["comparison_group_hash"])
    control_modes={r.get("mode") for r in usable}
    matched_groups={r.get("matched_control_group_hash") for r in usable}
    controls_matched={"joint","btc_only","btc_trim"}.issubset(control_modes) and len(matched_groups)==1 and None not in matched_groups
    packet={"algorithm":ALGORITHM,"cases":rows,"engine_constructions_added":0,
        "matched_controls_status":"MATCHED_EFFECTIVE_PARAMETERS_VERIFIED" if controls_matched else "UNKNOWN_INCOMPLETE_OR_DIFFERENT_CONTROL_PARAMETERS",
        "comparison_scope":"OWN_FRESH_NATIVE_PATHS_ONLY_A00_HISTORICAL_REFERENCE_NOT_RERUN",
        "pareto_scope":"NATIVE_NUMERIC_ONLY_WITHIN_EXACT_MATCHED_PIN_GROUPS_STRUCTURAL_UNKNOWN_NOT_A_WINNER_OR_VALID_IMPL",
        "duplicate_report_fresh_path_status":"UNKNOWN" if repeated else "UNIQUE_PROVIDED_REPORT_HASHES",
        "A00_historical_reference":{"TOTAL":"5635720.91989984","DD_percent":"51.4383711874","rerun":False}}
    dump(out/"COMPARISON.json",packet)
    csvwrite(out/"COMPARISON_PARETO.csv",rows,list(rows[0]) if rows else ["case","TOTAL"])
    return packet

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--manifest",type=Path,required=True);parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args(argv)
    def guard(event,values):
        if event=="import" and str(values[0]).split(".")[0] in ("coinmaster","nautilus_trader"):
            raise RuntimeError("NO_NATIVE_OR_PRODUCT_IMPORT")
        if event.startswith(("socket.","subprocess.")):raise RuntimeError("NO_NETWORK_OR_SUBPROCESS")
    sys.addaudithook(guard)
    manifest=load(args.manifest)
    if manifest.get("schema_version")!=1:raise ValueError("MANIFEST_SCHEMA_VERSION1_REQUIRED")
    if manifest.get("native_dd_source_sha256")!=sha(manifest["native_dd_source"]):
        raise ValueError("FROZEN_NATIVE_DD_SOURCE_HASH_REQUIRED_OR_MISMATCH")
    with Path(manifest["ledger"]).open() as f:rows=[json.loads(line) for line in f if line.strip()]
    cases=list(manifest["cases"]);known={c.get("run_id",c["case"]) for c in cases}
    for run_id in dict.fromkeys(r["run_id"] for r in rows if r.get("status")=="STARTED"):
        if run_id not in known:cases.append({"case":run_id,"run_id":run_id,"stage":"unprovided"})
    args.out.mkdir(parents=True,exist_ok=True);summaries=[]
    with localcontext() as ctx:
        ctx.prec=28;ctx.rounding=ROUND_HALF_EVEN
        for case in cases:
            case["_ledger_path"]=manifest["ledger"]
            try:s=analyze_case(case,rows,args.out,manifest["native_dd_source"])
            except Exception as error:
                run_id=case.get("run_id",case["case"])
                prior=[r for r in rows if r.get("run_id")==run_id and r.get("status") in {"STARTED","COMPLETED","FAILED","PARENT_INTERRUPTED_CHILD_STATE_UNKNOWN"}]
                s={"case":case["case"],"run_id":run_id,"physical_status":prior[-1].get("status") if prior else "UNKNOWN",
                    "analysis_status":"ERROR",
                    "TOTAL":None,"financial_status":"UNKNOWN","structural_status":"UNKNOWN","numeric_goal_status":"UNKNOWN",
                    "robustness_status":"NOT_RUN","persistence_status":"NOT_IMPLEMENTED_FRESH_RESEARCH_ONLY",
                    "with_final_close_DD_percent":{"settled":None,"coherent":None},
                    "error":{"type":type(error).__name__,"message":str(error)}}
                empty_case_outputs(args.out/case["case"],case["case"],"ANALYSIS_ERROR_NO_QUALIFIED_ECONOMIC_VALUES")
                dump(args.out/case["case"]/"SUMMARY.json",s)
            s.setdefault("provenance",{})["ledger_sha256"]=sha(manifest["ledger"])
            dump(args.out/case["case"]/"SUMMARY.json",s);summaries.append(s)
        packet=compare(summaries,args.out)
    print(json.dumps({"cases":len(packet["cases"]),"engine_constructions_added":0,
        "financial_PASS":sum(s["financial_status"]=="PASS" for s in summaries)}))

if __name__=="__main__":main()
