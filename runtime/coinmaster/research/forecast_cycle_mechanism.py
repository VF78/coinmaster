"""Read-only all-saved-native-state mechanism availability screen. No PnL engine."""
import argparse,bisect,collections,csv,gzip,hashlib,json,time
from pathlib import Path
from decimal import Decimal as D
def run(inputs,report):
 started=time.monotonic();files=list(inputs.glob("*direction.json"))
 if len(files)!=1:raise ValueError("EXACT_NATIVE_RAW_REQUIRED")
 raw=json.loads(files[0].read_text());trace=inputs/"minute-native-risk.csv.gz"
 def digest(path):
  with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
 if digest(files[0])!="4dbfaf0d228f27ebc5e24157b613b0ddd279bffa2d163d042684bdad13bbec1b" or digest(trace)!="f9b59944ac969f5441babdf2103637f7cd179c6d18971c7bf95c0e2c46e38a0b":raise ValueError("SAVED_S0_INPUT_DRIFT")
 parents=sorted(raw["entry_sizing_audit"],key=lambda p:int(p["q0_ns"]));starts=[int(p["q0_ns"]) for p in parents];sides={p["episode_id"]:int(p["side"]) for p in raw["btc_sizing_audit"]}
 btc_trades=[r for r in csv.DictReader((report.parent/"winner-6077107-stats/trades-ledger.csv").open()) if r["asset"]=="BTC"]
 trades={p["episode_id"]:r for p,r in zip(parents,btc_trades)}
 fills=collections.defaultdict(list)
 for f in raw["fill_audit"]:fills[int(f["fill_ns"])].append(f)
 rights=[]
 for p in parents:
  for activation in p.get("sol_right_activations",[]):
   for level in activation["levels"]:rights.append((int(activation["timestamp_ns"]),p["episode_id"],level))
 rows=[];peak=D(10000);first50=None;count=0;states=collections.Counter();active={};previous_close={};prior_pre={};current_parent=None;lasttime=None
 # Every recorded activation gets an explicit missing-state row; it is not a complete right universe.
 for t,pid,level in rights:rows.append(dict(mechanism="H-SOL",parent=pid,time_ns=t,level=level,source="recorded zero-level right activation; not actual add-decision",eligibility="UNKNOWN",action_available="UNKNOWN",before_first50="PENDING",profitable_counterexample="",original_net_ex_funding="",missing="pending/intents/consumed-right trace; next add-decision state; exact native close perassetUPnL absent",counterfactual_ROI="UNKNOWN"))
 with gzip.open(trace,"rt") as f:
  for row in csv.DictReader(f):
   count+=1;t=int(row["close_available_ns"])
   if t>1788220800000000000:raise ValueError("TRACE_OUTSIDE_S0_PERIOD")
   e=D(row["paired_close_equity"]);peak=max(peak,e)
   if first50 is None and e<peak*D(".5"):first50=t
   ps=json.loads(row["native_positions_and_mark_ohlc_json"]);assets={p["instrument_id"].split("USDT")[0]:p for p in ps};states["+".join(sorted(assets)) or "FLAT"]+=1
   idx=bisect.bisect_right(starts,t)-1;pid=parents[idx]["episode_id"] if idx>=0 else None
   if row["phase"]=="pre_quote_paired_close":
    prior_pre=assets
    # Native pre-quote average validates price-profitable filled TP. Zero activations are never TP.
    if "BTC" in assets and pid:
     p=assets["BTC"];side=sides[pid];basis=D(p["avg_px_open"])
     for fill in fills.get(t,[]):
      if fill["action"]=="BTC_REDUCE" and D(fill["qty"])>0 and side*(D(fill["px"])-basis)>0:
       active[pid]={"TP_ns":t,"TP_price":D(fill["px"]),"favorable":False}
   if row["phase"]!="post_quote_paired_close":continue
   if "BTC" not in assets or pid not in active:continue
   p=assets["BTC"];side=sides[pid];basis=D(p["avg_px_open"]);close=D(str(p["mark_ohlc"]["close"]));state=active[pid];prev=previous_close.get(pid)
   if t>state["TP_ns"] and side*(close-state["TP_price"])>0:state["favorable"]=True
   crossed=prev is not None and side*(prev-basis)>0 and side*(close-basis)<=0
   if state["favorable"] and crossed and "SOL" not in assets:
    trade=trades.get(pid,{});net=trade.get("net_ex_funding","UNKNOWN")
    rows.append(dict(mechanism="H-BTC",parent=pid,time_ns=t,level="",source="all saved post-quote close entry-return crossing after profitable nativeTP and later favorableclose",eligibility="PRICE_SCREEN_ONLY",action_available="UNKNOWN",before_first50="PENDING",profitable_counterexample=(D(net)>0 if net!="UNKNOWN" else "UNKNOWN"),original_net_ex_funding=net,missing="ordinary branch / mandatory-exit / pending-intent / right state absent; no continuous tick or predecision callback state",counterfactual_ROI="UNKNOWN"))
   previous_close[pid]=close
 for row in rows:row["before_first50"]=row["time_ns"]<first50 if first50 is not None else "UNKNOWN"
 report.mkdir(parents=True,exist_ok=True)
 with (report/"mechanism-screen.csv").open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ["mechanism","eligibility"]);w.writeheader();w.writerows(rows)
 summary={"status":"ACTION_VALUE_UNIDENTIFIED","native_rows_scanned":count,"native_states":dict(states),"first_native_phase_DD_over50_ns":first50,"BTC_price_screen_rows":sum(r["mechanism"]=="H-BTC" for r in rows),"BTC_price_screen_before50":sum(r["mechanism"]=="H-BTC" and r["before_first50"] is True for r in rows),"BTC_profitable_original_trade_counterexamples":sum(r["mechanism"]=="H-BTC" and r["profitable_counterexample"] is True for r in rows),"recorded_SOL_zero_right_activations":len(rights),"complete_eligible_action_universe":"UNKNOWN; recorded rights/fills are not all predecision opportunities","paired_action_branches":"NOT_AVAILABLE","native_runs_admitted":0,"money_semantics":"Only saved native equity,average and original trade ledger; price-only crossing is an availability screen; no perasset closePnL reconstruction or alternative fill","early_ML_fit":"No fully24h mature X_joint fit rows before2024-09-01: actualminute coverage beginsAug31,15m40bar warmup consumes10h,earliestnewlabel expiry isSep1after10h; no hourlyupsampling. OverlayearlyS0 thus retains early>50DD; BTCfallbackownflat not ruledout.","wall_seconds":time.monotonic()-started}
 (report/"mechanism-screen-summary.json").write_text(json.dumps(summary,indent=2)+"\n");print(json.dumps(summary))
def main():
 p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--report",type=Path,required=True);a=p.parse_args();run(a.inputs,a.report)
if __name__=="__main__":main()
