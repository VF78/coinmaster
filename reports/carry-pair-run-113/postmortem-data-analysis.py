import csv,gzip,json,glob,datetime,collections,re
from decimal import Decimal as D
from pathlib import Path
P=Path("reports/carry-pair-run-113"); B=Path("/var/lib/coinmaster-native-gui/data/runs/jobs")
A=B/"cm113-chop-pair50-net-20261020a/result"; C=Path(json.load(open(P/"control-reference.json"))["raw_path"]).parent

def utc(ns): return datetime.datetime.fromtimestamp(int(ns)/1e9,datetime.timezone.utc).isoformat()
def snap(r):
 ps=json.loads(r["native_positions_and_mark_ohlc_json"]); e=D(r["paired_close_equity"]); cash=D(r["cash"])
 return {"utc":utc(r["close_available_ns"]),"ns":r["close_available_ns"],"phase":r["phase"],"equity":str(e),"cash":str(cash),"native_total_unrealized":str(e-cash),"positions":ps}
def fills(p):
 rows=list(csv.DictReader(open(next(p.glob("*-fills.csv"))))); sums={}
 for r in rows:
  k=r["instrument_id"][:3];s=sums.setdefault(k,{"rows":0,"fees":D(0),"notional":D(0),"buy_qty":D(0),"sell_qty":D(0),"first":r["ts_last"],"last":r["ts_last"]})
  s["rows"]+=1;s["fees"]+=D(re.search(r"[-0-9.]+",r["commissions"])[0]);s["notional"]+=D(r["filled_qty"])*D(r["avg_px"]);s[r["side"].lower()+"_qty"]+=D(r["filled_qty"]);s["first"]=min(s["first"],r["ts_last"]);s["last"]=max(s["last"],r["ts_last"])
 return rows,sums
ar,af=fills(A);cr,cf=fills(C)
# Small order reports only; inventory is exposure context, no PnL matching/replay.
keys={str(int(datetime.datetime.fromisoformat(r["ts_last"]).timestamp()*1e9)) for r in ar+cr}
keys.update(str(int(datetime.datetime.fromisoformat(t).timestamp()*1e9)) for t in ["2024-09-17T00:00:00+00:00","2024-09-17T00:01:00+00:00","2024-09-17T16:08:00+00:00","2025-04-06T20:37:00+00:00","2025-04-06T20:38:00+00:00"])
results={"method":"One streaming pass per durable native trace; no second PnL/backtest engine. Snapshots at existing report times, drawdown thresholds, exposure transitions. E-cash uses native equity/cash. Per-asset native low/high PnL retained without inventing realized components.","fill_sums":{"candidate":af,"control":cf},"first_difference":None,"traces":{},"same_date":[]}
states={k:{"peak":D(10000),"peak_row":None,"min":None,"maxdd":D(0),"worst":None,"thresholds":{},"snapshots":{},"monthly":{},"exposure_minutes":collections.Counter(),"sol_only_spells":[],"spell":None,"last":None} for k in ["candidate","control"]}
ra=csv.DictReader(gzip.open(A/"minute-native-risk.csv.gz","rt")); rc=csv.DictReader(gzip.open(C/"minute-native-risk.csv.gz","rt"))
for idx,(a,c) in enumerate(zip(ra,rc)):
 if (a["close_available_ns"],a["phase"])!=(c["close_available_ns"],c["phase"]): raise ValueError("TRACE ALIGNMENT")
 if results["first_difference"] is None and any(a[k]!=c[k] for k in ["cash","paired_close_equity","native_positions_and_mark_ohlc_json"]):results["first_difference"]={"candidate":snap(a),"control":snap(c)}
 for label,r in [("candidate",a),("control",c)]:
  st=states[label]; e=D(r["paired_close_equity"])
  if e>st["peak"]:st["peak"]=e;st["peak_row"]=snap(r)
  dd=1-e/st["peak"]
  if st["min"] is None or e<D(st["min"]["equity"]):st["min"]=snap(r)
  if dd>st["maxdd"]:st["maxdd"]=dd;st["worst"]={"peak":st["peak_row"],"trough":snap(r),"dd":str(dd)}
  for level in ["0.1","0.3","0.5","0.8","0.9","0.99"]:
   if dd>=D(level) and level not in st["thresholds"]:st["thresholds"][level]=snap(r)
  ns=r["close_available_ns"]
  if ns in keys:st["snapshots"][ns]=snap(r) # last phase for exact close time
  if r["phase"]!="pre_quote_paired_close":continue
  ss=snap(r);mon=ss["utc"][:7];st["monthly"].setdefault(mon,ss)
  ps=ss["positions"]; btc=[p for p in ps if p["instrument_id"].startswith("BTC")];sol=[p for p in ps if p["instrument_id"].startswith("SOL")];kind="both" if btc and sol else "BTC_only" if btc else "SOL_only" if sol else "flat";st["exposure_minutes"][kind]+=1
  if kind=="SOL_only":
   if st["spell"] is None:st["spell"]={"start":ss,"minutes":0}
   st["spell"]["minutes"]+=1;st["spell"]["end"]=ss
  elif st["spell"] is not None:st["sol_only_spells"].append(st["spell"]);st["spell"]=None
  st["last"]=ss
for label,st in states.items():
 if st["spell"]:st["sol_only_spells"].append(st["spell"])
 st.pop("spell");results["traces"][label]={k:v for k,v in st.items() if k!="snapshots"}
for ns in sorted(keys,key=int):
 if ns in states["candidate"]["snapshots"] and ns in states["control"]["snapshots"]:results["same_date"].append({"candidate":states["candidate"]["snapshots"][ns],"control":states["control"]["snapshots"][ns]})
(P/"postmortem-data.json").write_text(json.dumps(results,indent=2,default=str)+"\n")
with open(P/"postmortem-data.csv","w") as f:
 w=csv.writer(f);w.writerow(["utc","variant","equity","cash","native_total_unrealized","positions_json"])
 for pair in results["same_date"]:
  for label,s in pair.items():w.writerow([s["utc"],label,s["equity"],s["cash"],s["native_total_unrealized"],json.dumps(s["positions"])])
print(json.dumps({"rows":idx+1,"first_difference":results["first_difference"],"fill_sums":results["fill_sums"],"summary":{k:{x:v for x,v in st.items() if x in ["peak","min","worst","thresholds","exposure_minutes"]} for k,st in states.items()}},default=str))
