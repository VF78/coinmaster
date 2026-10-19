"""Past-only scenario arithmetic on saved native inputs; no fills/PnL/strategy replay."""
from pathlib import Path
import json,csv,math,statistics as st,hashlib,time,resource
import pyarrow.parquet as pq
P=Path("reports/immediate-sol-insurance-113");start=time.monotonic()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
def quant(v,p=.95):
 v=sorted(v);z=(len(v)-1)*p;i=int(z);return v[i]+(v[min(i+1,len(v)-1)]-v[i])*(z-i)
def qs(v):return {"min":min(v),"median":st.median(v),"p95":quant(v),"max":max(v)}
provpath=Path("reports/sol-risk-first-20261018/analysis-control-provenance.json");prov=json.loads(provpath.read_text())["control"];raw=Path(prov["result"]);assert sha(raw)==prov["result_sha256"];r=json.loads(raw.read_text());pins={str(raw):sha(raw),str(provpath):sha(provpath)}
d={}
for s in ("BTC","SOL"):
 p=Path("runtime/var/data/normalized")/f"bybit-{s}USDT-daily.parquet";pins[str(p)]=sha(p);d[s]={int(x["open_time_ms"]+86400000)*1000000:float(x["close"]) for x in pq.read_table(p,columns=["open_time_ms","close"]).to_pylist()}
times=sorted(set(d["BTC"])&set(d["SOL"]));DAY=86400000000000
def estimate(t):
 tt=[x for x in times if x<=t][-91:];assert len(tt)==91 and all(b-a==DAY for a,b in zip(tt,tt[1:]));x=[math.log(d["BTC"][b]/d["BTC"][a]) for a,b in zip(tt,tt[1:])];y=[math.log(d["SOL"][b]/d["SOL"][a]) for a,b in zip(tt,tt[1:])];beta=st.covariance(x,y)/st.variance(x);assert beta>0;al=quant([abs(v) for v in x]);ul=quant([abs(s-beta*b) for b,s in zip(x,y)]);return beta,al,ul,tt[-1]
sizing={x["episode_id"]:x for x in r["btc_sizing_audit"] if x["event"]=="EPISODE_ENTRY_SIZING"};rows=[]
for p in r["split_cover_audit"]["parents"]:
 t=int(p["start_ns"]);b,al,ul,ct=estimate(t);a=math.expm1(al);u=math.expm1(ul);der=u/b-a;loss=[(1-c)*a+c*u/b for c in (0,.25,.5,.75,1)];imin=min(range(5),key=loss.__getitem__);n=float(p["quantity"])*float(p["first_vwap"]);nf=float(p["first_filled"])*float(p["first_vwap"]);sa=sizing[p["episode_id"]];eq=float(sa["requested_notional"])/float(sa["frozen_multiplier"]);cup=max(0,eq-.55*max(10000,eq));fee=[(1-c)*a+c*u/b+.00055+.00110*c/b for c in (0,.25,.5,.75,1)];jf=min(range(5),key=fee.__getitem__)
 rows.append(dict(episode_id=p["episode_id"],start_ns=t,estimate_close_ns=ct,returns=90,side=p["side"],beta=b,a_log=al,u_log=ul,a_simple=a,u_simple=u,delta_loss_per_c_per_NB=der,hedge_helps_before_fees=der<0,grid_min_c=(0,.25,.5,.75,1)[imin],min_loss_per_NB_no_fees=loss[imin],c025_loss_per_NB_no_fees=loss[1],grid_min_c_known_taker_fees=(0,.25,.5,.75,1)[jf],min_loss_per_NB_known_taker_fees=fee[jf],full_parent_NB_P0=n,first_fill_NB=nf,planning_Eq0_inferred=eq,cushion_upper_bound_planning_H_equals_max_seed_E=cup,optimistic_C_per_full_NB=cup/n,full_parent_fails_even_optimistic_no_fees=n*loss[imin]>cup,first_fill_fails_even_optimistic_no_fees=nf*loss[imin]>cup,min_full_parent_scenario_loss_no_fees=n*loss[imin],min_first_fill_scenario_loss_no_fees=nf*loss[imin],min_full_parent_loss_known_taker_fees=n*fee[jf]))
assert len(rows)==105
out=P/"challenge-cushion.csv"
with out.open("w",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
land=[]
for z in r["minute_risk_observations"]["curves"]["all_native_close_samples"]["top3_distinct_excursions"]:
 e=float(z["trough"]["equity"]);h=max(10000,float(z["peak"]["equity"]));ep=max((p for p in r["split_cover_audit"]["parents"] if int(p["start_ns"])<=int(z["trough"]["timestamp_ns"])),key=lambda p:int(p["start_ns"]));b,al,ul,ct=estimate(int(ep["start_ns"]));tt=[x for x in times if x<=int(z["trough"]["timestamp_ns"])][-91:];xx=[math.log(d["BTC"][v]/d["BTC"][u]) for u,v in zip(tt,tt[1:])];yy=[math.log(d["SOL"][v]/d["SOL"][u]) for u,v in zip(tt,tt[1:])];a=math.expm1(quant([abs(v) for v in xx]));u=math.expm1(quant([abs(s-b*v) for v,s in zip(xx,yy)]));land.append(dict(timestamp_ns=z["trough"]["timestamp_ns"],native_E=e,native_H=h,floor=.55*h,cushion=max(0,e-.55*h),below_floor=e<.55*h,episode_id=ep["episode_id"],beta_frozen_at_episode=b,current_daily_a_simple=a,current_daily_u_simple_frozen_beta=u,hedge_helps_before_fees=u/b<a,quantity_and_current_notional="NOT_AVAILABLE_IN_COMPACT_SELECTED_CONTROL_LANDMARKS; no old-version exposure substituted"))
summary=dict(method="W90 paired completed daily log returns; sample covariance/variance; linear q95 abs returns and abs residual WITHOUT intercept as specified; expm1 shocks; beta frozen at episode, entry a/u recomputed at that same timestamp. No native backtest or PnL engine.",source_pins=pins,n=105,hedge_helps_count=sum(x["hedge_helps_before_fees"] for x in rows),hedge_helps_percent=100*sum(x["hedge_helps_before_fees"] for x in rows)/105,grid_opt_c_counts={str(c):sum(x["grid_min_c"]==c for x in rows) for c in (0,.25,.5,.75,1)},full_parent_impossible_even_best_H_no_fees=sum(x["full_parent_fails_even_optimistic_no_fees"] for x in rows),first_fill_impossible_even_best_H_no_fees=sum(x["first_fill_fails_even_optimistic_no_fees"] for x in rows),full_parent_impossible_even_best_H_known_taker_fees=sum(x["min_full_parent_loss_known_taker_fees"]>x["cushion_upper_bound_planning_H_equals_max_seed_E"] for x in rows),quantiles={k:qs([x[k] for x in rows]) for k in ("beta","a_simple","u_simple","delta_loss_per_c_per_NB","min_loss_per_NB_no_fees","optimistic_C_per_full_NB")},entry_money_examples=[rows[i] for i in (0,1,2)],native_worst_troughs=land,limits=["Scenario not joint95%, probability guarantee, DD guarantee or ROI estimate.","Eq0 inferred from recorded requested_notional/multiplier, NOT actual fill equity. Entry H audit is stale and not used. Capacity uses optimistic H=max(seed,Eq0), so passing is NOT proof of actual feasibility; failing is an optimistic exclusion at that planning snapshot.","Full parent NB=recorded filled quantity*first VWAP, not simultaneously held mark notional; first-fill NB separate. Quantization, passive Q2 pricing and fees are not simulated.","Known fee illustration assumes new SOL open+close both taker .00055 and BTC exit taker .00055; actual remaining costs depend on current holdings, fees already paid, funding and later execution. No slippage/funding assigned zero as known result.","Landmark beta tied to preceding accepted episode; no claim parent remains open at trough; compact original landmark file has different control version, so its q/E excluded.","Four native immediate insurance variants already failed; H-CUSHION has NOT been native tested."],runtime_seconds=time.monotonic()-start,max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
(P/"challenge-cushion.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps(summary,indent=2))
# Compact summary from the already computed entry rows; no additional data pass.
from datetime import datetime,timezone
counts={str(c):0 for c in (0,.25,.5,.75,1)};nonhelpers=[]
for x in rows:
 a=x["a_simple"];u=x["u_simple"];b=x["beta"];cap=x["optimistic_C_per_full_NB"]
 feasible=[c for c in (0,.25,.5,.75,1) if (1-c)*a+c*u/b<=cap]
 counts[str(min(feasible)) if feasible else "NONE"]+=1
 if not x["hedge_helps_before_fees"]:nonhelpers.append(dict(start_utc=datetime.fromtimestamp(x["start_ns"]/1e9,timezone.utc).isoformat(),beta=b,a_simple=a,u_over_beta=u/b,delta_loss_per_c_per_NB=u/b-a,NB_P0=x["full_parent_NB_P0"]))
summary["smallest_c_satisfying_optimistic_planning_capacity_no_fees"]=counts
summary["non_helpful_entries"]=nonhelpers
summary["important_omitted_source"]={"path":"reports/btc-split-sol-cover-20261018/comparison-analysis-worst-dd-native-landmarks.json","reason":"btc025/V3 are different control versions. At selected trough1727970240000000000 btc025 E=2990.60113081 versus selected E=4530.57414701. Its q/E not used."}
(P/"challenge-cushion.json").write_text(json.dumps(summary,indent=2)+"\n")
# Fold collaborator-validated selected native inventory, no observer reread.
invpath=P/"postmortem-early-chop.json"
assert sha(invpath)=="43dfa946902ae484b4ca8623e84a2aad80ed948c30be2650420cc4cb5ebb986b"
summary["validated_inventory_source"]={"path":str(invpath),"sha256":sha(invpath),"key":"native_621fill_inventory_crosscheck","method":"Collaborator exact order.side/621 native fill inventory, strictly before prequote timestamp; selected raw4dbfaf...ec1b and selected tracef9b599...38a0b already pinned in collaborator artifact."}
inv=[(.724,60209.94,810.9,133.166),(29.484,105225.64,0,0),(169.664,92944.7,0,0)]
for z,(q,bp,sq,sp) in zip(summary["native_worst_troughs"],inv):
 n=q*bp;b=z["beta_frozen_at_episode"];a=z["current_daily_a_simple"];u=z["current_daily_u_simple_frozen_beta"]
 loss=min((1-c)*a+c*u/b for c in (0,.25,.5,.75,1))
 z.update(actual_BTC_quantity=q,actual_BTC_mark=bp,actual_NB=n,actual_SOL_quantity=sq,actual_SOL_mark=sp,actual_NS=sq*sp,minimum_scenario_loss_no_costs=n*loss,full_factor_hedge_target_NS=n/b,required_C_per_NB_no_costs=loss,scope="Scenario applied to actual saved BTC exposure; existing SOL shown separately, no synthetic rebalance/fill or PnL. Minimum additional remaining costs not claimed known.")
(P/"challenge-cushion.json").write_text(json.dumps(summary,indent=2)+"\n")

for z in summary["native_worst_troughs"]:z["quantity_and_current_notional"]="VALIDATED_SELECTED_621_NATIVE_FILL_INVENTORY; collaborator artifact pinned below; old-version source not used"
(P/"challenge-cushion.json").write_text(json.dumps(summary,indent=2)+"\n")
