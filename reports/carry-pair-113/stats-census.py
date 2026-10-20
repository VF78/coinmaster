import csv,json,pathlib,datetime,hashlib,collections
from decimal import Decimal as D
ROOT=pathlib.Path("/root/.openclaw/workspace/coinmaster/coinmaster");OUT=ROOT/"reports/carry-pair-113"
s=json.load(open(ROOT/"reports/chop-pair-113/stats-summary.json"));jp=next(p for p in s["sources"] if p.startswith("/var") and p.endswith(".json"));fp=next(p for p in s["sources"] if p.endswith("-fills.csv"));j=json.load(open(jp));f=list(csv.DictReader(open(fp)));a=j["fill_audit"]
assert len(a)==len(f)==621
# Native fills already have domain actions. Inventory qty and weighted basis only; no realized PnL/matching/portfolio cash.
state={x:dict(q=D(0),basis=D(0),entry_fee_per_q=D(0),side=0,tp=collections.Counter(),first_ms=None,entry_ids=[]) for x in ["BTC","SOL"]};rows=[];sources={jp:s["sources"][jp],fp:s["sources"][fp]}
bykey=collections.defaultdict(list)
for y in f:
 t=int(datetime.datetime.fromisoformat(y["ts_last"]).timestamp()*1000000000);bykey[(y["instrument_id"],t,D(y["filled_qty"]))].append(y)
for i,x in enumerate(a):
 y=bykey[(x["instrument"],int(x["fill_ns"]),D(x["qty"]))].pop(0)
 sym=x["instrument"][:3];q=D(x["qty"]);px=D(x["px"]);fee=D(x["commission"]);ms=int(x["fill_ns"])//1000000;sd=1 if y["side"]=="BUY" else -1;st=state[sym]
 assert x["instrument"]==y["instrument_id"] and q==D(y["filled_qty"]) and abs(px-D(y["avg_px"]))<D("0.0000001"),i
 if sym=="BTC" and x["reason"]=="REGIME":
  sol=state["SOL"];r=dict(event=len(rows)+1,utc=datetime.datetime.fromtimestamp(ms/1000,datetime.timezone.utc).isoformat(),ms=ms,period="calibration" if ms<1756684800000 else "later",BTC_side=st["side"],BTC_qty=str(st["q"]),BTC_basis=str(st["basis"]),BTC_entry_fee_per_q=str(st["entry_fee_per_q"]),BTC_regime_close_px=str(px),BTC_inherited_return=float(st["side"]*(px/st["basis"]-1)),BTC_entry_ms=st["first_ms"],BTC_TP_actions=json.dumps(st["tp"],sort_keys=True),SOL_qty=str(sol["q"]),SOL_side=sol["side"],SOL_basis=str(sol["basis"]),SOL_entry_fee_per_q=str(sol["entry_fee_per_q"]),SOL_first_ms=sol["first_ms"],SOL_TP_actions=json.dumps(sol["tp"],sort_keys=True),SOL_opposite_BTC=sol["q"]>0 and sol["side"]==-st["side"],BTC_native_fill_index=i)
  same=[z for z in a if z["instrument"].startswith("SOL") and z["fill_ns"]==x["fill_ns"] and z["reason"]=="REGIME"]
  r["SOL_regime_close_px"]=same[0]["px"] if same else "";r["SOL_same_timestamp_regime_close"]=bool(same)
  if same and sol["q"]>0:r["SOL_inherited_return"]=float(sol["side"]*(D(same[0]["px"])/sol["basis"]-1))
  rows.append(r)
 if x["action"] in ["BTC_ENTRY","SOL_ADD"]:
  assert st["q"]==0 or st["side"]==sd,(i,sym)
  if st["q"]==0:st.update(first_ms=ms,tp=collections.Counter(),entry_ids=[],entry_fee_per_q=D(0))
  total=st["q"]+q;st["basis"]=(st["basis"]*st["q"]+px*q)/total;st["entry_fee_per_q"]=(st["entry_fee_per_q"]*st["q"]+fee)/total;st["q"]=total;st["side"]=sd;st["entry_ids"].append(i)
 else:
  assert q<=st["q"] and sd==-st["side"],(i,sym,q,st)
  st["q"]-=q;st["tp"][x["reason"]]+=1
  if st["q"]==0:st.update(basis=D(0),entry_fee_per_q=D(0),side=0)
# Link next actual BTC entry; these are the calendar/alpha rights any carry policy delays or skips.
for r in rows:
 n=next((z for z in a[r["BTC_native_fill_index"]+1:] if z["action"]=="BTC_ENTRY"),None)
 r["next_BTC_entry_ms"]=int(n["fill_ns"])//1000000 if n else None;r["next_BTC_entry_delay_min"]=(r["next_BTC_entry_ms"]-r["ms"])/60000 if n else None
 r["next_BTC_entry_px"]=n["px"] if n else None
 r["original_SOL_adds_next_1D"]=sum(z["action"]=="SOL_ADD" and r["ms"]<int(z["fill_ns"])//1000000<=r["ms"]+86400000 for z in a)
fields=list(dict.fromkeys(k for r in rows for k in r))
with open(OUT/"stats-native-census.csv","w") as z:w=csv.DictWriter(z,fieldnames=fields);w.writeheader();w.writerows(rows)
summary={"status":"SAVED_NATIVE_INVENTORY_CENSUS_ONLY","sources":sources,"counts":{},"limitations":["Original native inventory snapshots only, no synthetic fills/cash/equity/PnL","No minute or daily market data read by this script","Actual SOL reference price exists only when native SOL REGIME fill occurred at same timestamp","CHOP flags at opposed signal not yet computed; native BTC-entry flags are not carried forward as a proxy"]}
for period in ["calibration","later","all"]:
 rr=[r for r in rows if period=="all" or r["period"]==period];summary["counts"][period]={"BTC_REGIME_residual":len(rr),"SOL_present":sum(D(r["SOL_qty"])>0 for r in rr),"SOL_opposite":sum(r["SOL_opposite_BTC"] for r in rr),"BTC_inherited_negative":sum(r["BTC_inherited_return"]<0 for r in rr),"original_SOL_adds_next_1D":sum(r["original_SOL_adds_next_1D"] for r in rr),"next_BTC_delays_min":dict(collections.Counter(r["next_BTC_entry_delay_min"] for r in rr))}
(OUT/"stats-native-census.json").write_text(json.dumps(summary,indent=2)+"\n");print(json.dumps(summary["counts"],indent=2))
