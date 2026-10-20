"""One bounded S0 T+V native-receipt pass; no execution or PnL reconstruction."""
import ast,csv,datetime,gzip,hashlib,json,resource
from decimal import Decimal as D
from pathlib import Path
R=Path("reports/fast-rnd-20261020")
PLAN=json.loads((R/"s0-drawdown-attribution-plan.json").read_text())
START=1725148800000000000
CUT=int(datetime.datetime.fromisoformat("2026-04-08T00:00:00+00:00").timestamp())*10**9
def utc(t):return datetime.datetime.fromtimestamp(t/10**9,datetime.timezone.utc).isoformat()
def timestamp(value):
    if value.isdigit():return int(value)
    t=datetime.datetime.fromisoformat(value.replace("Z","+00:00"))
    return int(t.timestamp()*10**9)
def endpoint(row):
    w=D(row["paired_close_equity"]);cash=D(row["cash"])
    return dict(source_ns=int(row["source_quote_ns"]),receipt_ns=int(row["receipt_ns"]),
        W=w,cash=cash,total_unrealized=w-cash,positions=json.loads(row["native_positions_and_mark_ohlc_json"]))
def assetfacts(point):
    ps=point["positions"];facts={}
    for p in ps:
        asset="BTC" if p["instrument_id"].startswith("BTC") else "SOL" if p["instrument_id"].startswith("SOL") else None
        assert asset and asset not in facts,"UNSUPPORTED_NATIVE_POSITION"
        a,b=D(p["low_native_pnl"]),D(p["high_native_pnl"])
        facts[asset]={**p,"native_close_unrealized_bounds":[min(a,b),max(a,b)],
            "native_close_unrealized":point["total_unrealized"] if len(ps)==1 else "UNKNOWN_NATIVE_COMPONENT_NOT_EXPORTED"}
    return facts
fees=[];fee_rows=0;ignored_outside=0
with open(PLAN["inputs"]["native_actual_fees"]) as f:
    for row in csv.DictReader(f):
        t=timestamp(row["ts_last"])
        if not START<=t<CUT:
            ignored_outside+=1
            continue  # Never parse an outside-T+V monetary payload.
        asset="BTC" if row["instrument_id"].startswith("BTC") else "SOL" if row["instrument_id"].startswith("SOL") else None
        assert asset
        commission=D(0)
        for value in ast.literal_eval(row["commissions"]):
            parts=value.split();assert len(parts)==2 and parts[1]=="USDT"
            commission+=D(parts[0])
        fees.append((t,asset,commission));fee_rows+=1
seed={"source_ns":START,"receipt_ns":START,"W":D(10000),"cash":D(10000),"total_unrealized":D(0),"positions":[]}
peak=seed;current=None;top=[];closed=0;count=0;previous=None;first=None;last=None;stopped_before_U=False
def retain(ep):
    global top
    ep["drawdown_amount"]=ep["peak"]["W"]-ep["trough"]["W"]
    ep["drawdown_percent"]=ep["drawdown_amount"]/ep["peak"]["W"]*100
    top=sorted(top+[ep],key=lambda e:e["drawdown_percent"],reverse=True)[:5]
with gzip.open(PLAN["inputs"]["native_W"],"rt") as f:
    for row in csv.DictReader(f):
        receipt=int(row["receipt_ns"]);source=int(row["source_quote_ns"])
        if receipt>=CUT or source>=CUT:
            stopped_before_U=True
            break  # Critically before position JSON or monetary value parsing.
        assert START<source<receipt<CUT
        assert previous is None or receipt>previous
        previous=receipt
        point=endpoint(row);count+=1
        if first is None:first=point
        last=point
        if point["W"]>=peak["W"]:
            if current is not None:
                current["recovery_receipt_ns"]=receipt;current["recovered_in_TV"]=True
                retain(current);closed+=1;current=None
            peak=point
        else:
            if current is None:
                current={"peak":peak,"trough":point,"recovered_in_TV":False,"recovery_receipt_ns":None}
            elif point["W"]<current["trough"]["W"]:current["trough"]=point
if current is not None:
    current["observed_through_receipt_ns"]=last["receipt_ns"];retain(current)
assert stopped_before_U and count>0 and len(top)==5
for rank,ep in enumerate(top,1):
    p,t=ep["peak"],ep["trough"]
    costs={a:sum((fee for ns,a2,fee in fees if a2==a and p["source_ns"]<ns<=t["source_ns"]),D(0)) for a in ("BTC","SOL")}
    dc=t["cash"]-p["cash"];du=t["total_unrealized"]-p["total_unrealized"]
    assert dc+du==-ep["drawdown_amount"]
    ep.update(rank=rank,delta_cash=dc,delta_total_unrealized=du,
        native_commissions_by_asset=costs,native_commissions=sum(costs.values(),D(0)),
        peak_assets=assetfacts(p),trough_assets=assetfacts(t),
        positive_open_UPnL_reduction=max(max(p["total_unrealized"],D(0))-max(t["total_unrealized"],D(0)),D(0)),
        negative_open_UPnL_loss_change=max(-t["total_unrealized"],D(0))-max(-p["total_unrealized"],D(0)),
        seed_capital_loss_at_trough=max(D(10000)-t["W"],D(0)))
assumptions=[
"Primary W is stored actual native account cash plus native Position.unrealized_pnl at causal source marks. RESERVE=0. No execution/PnL model or S0 rerun.",
"Source quote and actual later receipt timestamps retained; rank five distinct high-water excursions by native relative percentage. No U recovery observed.",
"Cash change is NOT isolated closed-trade PnL: it includes native realized settlement, commissions and funding. Exact identity delta W=delta cash+delta total unrealized holds.",
"Positive-open-UPnL reduction is descriptive, not necessarily economic giveback: realized profit can move from open UPnL to cash. Negative-open-UPnL movement and seed-capital loss are separately named; exact initial-position-loss attribution UNKNOWN.",
"Native BTC/SOL commissions are summed once in (peak source timestamp,trough source timestamp]; already included in W/cash, never subtracted twice.",
"Exact BTC/SOL native realized and two-asset close UPnL are not exported. Low/high native PnL endpoint bounds and positions are descriptive; no interpolation, fill-weighted ledger or invented asset allocation.",
"Signed funding UNKNOWN: journal stores post-account-total, not signed cash delta. Funding is not assumed zero.",
"Filter receipt/source timestamps before parsing monetary values/position JSON; break before first U payload. Fill rows outside T+V are time-filtered before commission parsing."
]
result={"status":"COMPLETE_ONE_BOUNDED_TV_PASS","cutoff_exclusive_ns":CUT,"cutoff_exclusive_utc":utc(CUT),
    "coverage":{"receipt_rows":count,"source_first_ns":first["source_ns"],"source_last_ns":last["source_ns"],
        "receipt_first_ns":first["receipt_ns"],"receipt_last_ns":last["receipt_ns"],
        "strictly_monotone_receipts":True,"stopped_before_U_payload_parse":stopped_before_U,
        "closed_excursions_in_TV":closed,"tail_unrecovered_in_TV":current is not None,
        "native_fee_rows_TV":fee_rows,"fee_rows_outside_TV_skipped_without_monetary_parse":ignored_outside},
    "assumptions":assumptions,"missing_native_artifacts":["perasset native close-unrealized component at receipt","complete native Position realized/lifecycle report","signed funding delta"],
    "resource":{"peak_RSS_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},
    "top5":top}
def default(x):
    if isinstance(x,D):return str(x)
    raise TypeError(type(x).__name__)
jp=R/"s0-drawdown-attribution-result.json";jp.write_text(json.dumps(result,indent=2,default=default)+"\n")
fields=["rank","peak_receipt_utc","trough_receipt_utc","peak_source_utc","trough_source_utc","native_peak_W","native_trough_W","native_DD_percent","native_DD_amount","delta_cash","delta_total_unrealized","BTC_fees","SOL_fees","native_fees","positive_open_UPnL_reduction","negative_open_UPnL_loss_change","seed_capital_loss_at_trough","peak_assets","trough_assets"]
with (R/"s0-drawdown-attribution-result.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for e in top:
        p,t=e["peak"],e["trough"]
        w.writerow(dict(rank=e["rank"],peak_receipt_utc=utc(p["receipt_ns"]),trough_receipt_utc=utc(t["receipt_ns"]),
            peak_source_utc=utc(p["source_ns"]),trough_source_utc=utc(t["source_ns"]),
            native_peak_W=p["W"],native_trough_W=t["W"],native_DD_percent=e["drawdown_percent"],native_DD_amount=e["drawdown_amount"],
            delta_cash=e["delta_cash"],delta_total_unrealized=e["delta_total_unrealized"],
            BTC_fees=e["native_commissions_by_asset"]["BTC"],SOL_fees=e["native_commissions_by_asset"]["SOL"],native_fees=e["native_commissions"],
            positive_open_UPnL_reduction=e["positive_open_UPnL_reduction"],negative_open_UPnL_loss_change=e["negative_open_UPnL_loss_change"],
            seed_capital_loss_at_trough=e["seed_capital_loss_at_trough"],peak_assets=json.dumps(e["peak_assets"],default=default,separators=(",",":")),trough_assets=json.dumps(e["trough_assets"],default=default,separators=(",",":"))))
lines=["S0: five largest native-W drawdowns inside T+V only. Receipt timestamps shown; source quote timestamps retained in CSV/JSON. No U payload parsed.","","|Rank|Peak receipt UTC|Trough receipt UTC|DD %|Native W loss|Δcash|Δtotal UPnL|BTC fees|SOL fees|","|---|---|---|---:|---:|---:|---:|---:|---:|"]
for e in top:
    lines.append(f'|{e["rank"]}|{utc(e["peak"]["receipt_ns"])}|{utc(e["trough"]["receipt_ns"])}|{e["drawdown_percent"]:.6f}|{e["drawdown_amount"]:.8f}|{e["delta_cash"]:.8f}|{e["delta_total_unrealized"]:.8f}|{e["native_commissions_by_asset"]["BTC"]:.8f}|{e["native_commissions_by_asset"]["SOL"]:.8f}|')
lines+=["","Native cash + total UPnL reconcile every listed decline exactly. Commissions already affect cash/W; these cost columns are descriptive and are not deducted again. Endpoint native BTC/SOL quantities, entry prices, marks and native low/high PnL bounds are in CSV/JSON.","","Exact asset-level native realized/close-UPnL allocation and signed funding remain UNKNOWN because the native component artifacts were not saved. Positive open-UPnL reduction alone does not prove economic profit giveback when a position was realized into cash. No alternate PnL ledger is used.","",f'Coverage: {count} strictly monotone receipts, actual receipt <{utc(CUT)}, one streaming pass. Peak RSS {result["resource"]["peak_RSS_bytes"]} bytes.']
(R/"s0-drawdown-attribution-result.md").write_text("\n".join(lines)+"\n")
print(json.dumps({"status":result["status"],"coverage":result["coverage"],"top5":[{k:e[k] for k in ("rank","drawdown_percent","drawdown_amount","delta_cash","delta_total_unrealized","native_commissions_by_asset")} for e in top],"peak_RSS_bytes":result["resource"]["peak_RSS_bytes"]},default=default))

