"""Aggregate cached reports/audits only. No replay or minute trace scan."""
import csv,json,hashlib,collections,shutil,subprocess
from decimal import Decimal as D
from pathlib import Path
from datetime import datetime,timezone
OUT=Path(__file__).parent;J=Path("/var/lib/coinmaster-native-gui/data/runs/jobs")
RUNS=[("control","cm113-minute-extrema-risk-20261010","result","v0-selective-lifecycle-cap30m"),("A_btc20","cm113-btc20-group-20261010","result-run","v0-selective-lifecycle-cap30m-btcloss20"),("B_solhedge","cm113-solhedge-admission-20261010","result","v0-selective-lifecycle-cap30m-solhedge")]
reports={}; rows=[]; details={}
for name,jobname,dirname,label in RUNS:
 job=J/jobname; art=job/dirname/(label+".json");p=json.loads(art.read_text());m=json.loads((job/dirname/"minute-risk-summary.json").read_text());reports[name]=p
 c=m["curves"]["all_native_close_samples"]; adv=m["curves"]["conditional_ohlc_adverse"]
 perasset={}
 for asset in ["BTC","SOL"]:
  fills=[x for x in p["fill_audit"] if x["instrument"].startswith(asset)]
  perasset[asset]={"fills":len(fills),"fees":str(sum((D(x["commission"]) for x in fills),D(0))),"notional":str(sum((D(x["notional"]) for x in fills),D(0))),"actions":dict(collections.Counter(x["action"] for x in fills)),"reasons":dict(collections.Counter(x["reason"] for x in fills))}
 total=D(p["terminal_total"]);base=D("5146884.95718200")
 row={"variant":name,"TOTAL":str(total),"ACTIVE":p["terminal_active"],"RESERVE":p["terminal_reserve"],"ROI_percent":str((total/D(10000)-1)*100),"delta_control":str(total-base),"delta_control_percent":str((total/base-1)*100),"native_minute_DD_percent":c["top3_distinct_excursions"][0]["drawdown_peak_percent"],"seed_minimum":c["minimum"]["equity"],"seed_loss_percent":c["maximum_loss_below_seed_percent"],"cash_DD_percent":str(D(str(p["summary"]["max_drawdown_percent"]))*100),"conditional_lower_envelope_DD_percent":adv["top3_distinct_excursions"][0]["drawdown_peak_percent"],"fees":p["native_fees"],"BTC_fills":perasset["BTC"]["fills"],"SOL_fills":perasset["SOL"]["fills"],"fills":p["fills"],"orders":p["execution_artifacts"]["orders"]["rows"],"funding_count":p["funding"]["count"],"signed_funding":p["funding"]["signed_amount"],"liquidations":p["liquidation_count"],"terminal_positions":p["terminal_open_positions"]};rows.append(row)
 btc=p.get("btc_episode_loss_audit",[]);hedge=p.get("sol_hedge_admission_audit",[])
 proof=[]
 for x in hedge:
  if "hedge_target_notional" in x:
   prospective=D(x["native_held_sol_notional"])+D(x["admitted_quantity"])*D(x["sol_mark"]);target=D(x["hedge_target_notional"])
   proof.append({"timestamp_ns":x["timestamp_ns"],"prospective":str(prospective),"target":str(target),"admitted_positive":D(x["admitted_quantity"])>0,"inequality_holds":prospective<=target})
 d={"metrics":row,"artifact":str(art),"artifact_sha256":hashlib.sha256(art.read_bytes()).hexdigest(),"config":p["config"],"config_hash":p["config_hash"],"source_hashes":p["source_hashes"],"data_hash":p["data_hash"],"policy_hash":p["policy_hash"],"control_report_sha256":p["control_report_sha256"],"interval":p["interval"],"run_interval":p["run_interval"],"streaming":p["streaming"],"fee_attribution":p["fee_attribution"],"fees_reconciled":p["fee_attribution"]["reconciled"],"assets":perasset,"terminal_lifecycle":p["terminal_lifecycle"],"post_boundary_settlement":p["post_boundary_settlement"],"minute_risk_summary":m,"btc_guard_event_counts":dict(collections.Counter(x.get("event") for x in btc)),"btc_guard_actual_exit_fills":sum(x["reason"]=="RESEARCH_BTC_EPISODE_LOSS_20" for x in p["fill_audit"]),"btc_guard_block_count":"NOT_EXPORTED_SEPARATELY","hedge_audit_rows":len(hedge),"hedge_pending_ownership_blocks":sum(x.get("reason")=="SOL_OPENING_OWNERSHIP_PENDING" for x in hedge),"hedge_clips":sum("admitted_quantity" in x and D(x["admitted_quantity"])<D(x["requested_quantity"]) for x in hedge),"hedge_zero_admissions":sum("admitted_quantity" in x and D(x["admitted_quantity"])==0 for x in hedge),"hedge_native_inequality_proof":proof,"hedge_positive_admission_violations":sum(x["admitted_positive"] and not x["inequality_holds"] for x in proof)}
 for curve in [c,adv]:
  for ex in curve["top3_distinct_excursions"]:
   for key in ["peak","trough","recovery"]:
    if ex.get(key):ex[key]["timestamp_utc"]=datetime.fromtimestamp(int(ex[key]["timestamp_ns"])/1e9,timezone.utc).isoformat()
 if name!="control":
  expected=json.loads((job/"immutable-source-hashes.json").read_text());assert all(hashlib.sha256((job/"source"/f).read_bytes()).hexdigest()==h for f,h in expected.items())
  d["immutable_source_commit"]="6c5e9d31faded0cc1eff609b47562b63cd551d03";d["immutable_files_verified"]=len(expected)
  for f in ["source-commit.txt","source-input-hashes.sha256","immutable-source-hashes.json","pilot-before.txt","pilot-after.txt","unit-journal.txt"]:
   if (job/f).exists():shutil.copyfile(job/f,OUT/(name+"-"+f))
  (job/"native-run-receipt.json").write_text(json.dumps(d,indent=2)+"\n")
  assert p["streaming"]["processed_rows_per_source"]==1051200 and m["rows"]==3153600
 d["status"]=p["status"];d["ranking_eligible"]=p["ranking_eligible"];d["hedge_nonpending_sizing_clips"]=sum("admitted_quantity" in x and D(x["admitted_quantity"])<D(x["requested_quantity"]) and x.get("reason")!="SOL_OPENING_OWNERSHIP_PENDING" for x in hedge)
 details[name]=d
control=reports["control"]["config"]
for name in ["A_btc20","B_solhedge"]:
 cfg=reports[name]["config"];details[name]["config_differences"]={k:{"control":control.get(k),"variant":cfg.get(k)} for k in sorted(set(control)|set(cfg)) if control.get(k)!=cfg.get(k)}
 for key in ["data_hash","policy_hash","control_report_sha256"]:assert reports[name][key]==reports["control"][key]
 details[name]["common_config_fields_equal"]=all(cfg[k]==v for k,v in control.items() if k in cfg)
 caveats=["All artifacts remain NOT_FAITHFUL_DIAGNOSTIC and ranking_eligible=false; these comparisons do not establish live readiness or faithful exchange execution.","A and B include two shared native lifecycle correctness fixes: ordinary-close pending ACK cleanup and cross-day SOL half completion. No fixes-only control was replayed, so pure candidate effects are not isolated.","A BTC20 measures native BTC episode realized PnL including fees plus held unrealized loss against portfolio equity at first confirmed BTC fill. It closes the group; it is not a global 20% drawdown limit.","B limits future earned SOL admissions to remaining native BTC notional/beta; held SOL is not rebalanced. Pending own SOL openings are conservatively serialized, which can delay/suppress same-cycle rights.","Native minute drawdown uses global marked-equity peaks without resets. Cached conditional OHLC adverse series is a fixed-exposure lower-envelope drawdown, not actual observed portfolio/tick drawdown or an upper-to-later-lower exact bound. That distinct bound is not exported by these cached summaries and was not recomputed by a new trace scan.","Signed funding remains UNKNOWN. Counts are not zero funding. Fixed fees, close proxy, absent L2/tick execution and liquidation applicability limitations remain.","Original control same-timestamp native callback ordering proof is incomplete; original control cross-day SOL half completion receipt is absent. New source includes focused proofs but this comparison does not retroactively attest old control.","Final prequote left-limit sample is retained; final postquote settlement samples are separately exported and excluded from interval DD/TOP3/seed minimum.","Initial A packing failure happened before engine.run, produced no funding journal/fill CSV, and is preserved; only two actual economic engines ran. No promotion/deploy/pilot change."]
package={"frozen_source_commit":"6c5e9d31faded0cc1eff609b47562b63cd551d03","variants":details,"limitations":caveats}
(OUT/"comparison.json").write_text(json.dumps(package,indent=2)+"\n")
with (OUT/"comparison.csv").open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
for name in ["A_btc20","B_solhedge"]:(OUT/(name+"-receipt.json")).write_text(json.dumps(details[name],indent=2)+"\n")
shutil.copyfile(J/"cm113-btc20-group-20261010/failed-preengine-receipt.json",OUT/"A-initial-preengine-failure.json")
md=["# CM-113 BTC episode budget / remaining BTC SOL hedge comparison","","Exactly two isolated sequential native 24-month engines on frozen source 6c5e9d3. Archived minute-observer control is reused. Seed 10,000 USDT; reserve zero; Bybit interval [2024-09-01,2026-09-01).", "", "| Variant | TOTAL USDT | ROI % | Native minute DD % | Seed minimum | Fees | BTC/SOL fills |", "|---|---:|---:|---:|---:|---:|---:|"]
for r in rows:md.append("| {} | {} | {} | {} | {} | {} | {}/{} |".format(*(r[k] for k in ["variant","TOTAL","ROI_percent","native_minute_DD_percent","seed_minimum","fees","BTC_fills","SOL_fills"])))
md.extend(["","Full TOP3 peak/trough/recovery timestamps, conditional envelope, fee/notional attribution, parameter differences, native guard/admission counts and immutable-source receipts are in comparison.json. All candidates processed 1,051,200 rows per source and 3,153,600 risk rows, reconciled fees, zero liquidations and terminal flat. Raw logs and traces remain private job artifacts.",""]+caveats)
(OUT/"README.md").write_text("\n\n".join(md)+"\n")
for f in OUT.iterdir():
 if f.is_file() and f.name!="SHA256SUMS":pass
(OUT/"SHA256SUMS").write_text("".join(hashlib.sha256(f.read_bytes()).hexdigest()+"  "+f.name+"\n" for f in sorted(OUT.iterdir()) if f.is_file() and f.name!="SHA256SUMS"))
print(json.dumps(rows));print("COUNTS",json.dumps({n:{k:details[n][k] for k in ["btc_guard_event_counts","btc_guard_actual_exit_fills","hedge_clips","hedge_pending_ownership_blocks","hedge_positive_admission_violations"]} for n in details}))
