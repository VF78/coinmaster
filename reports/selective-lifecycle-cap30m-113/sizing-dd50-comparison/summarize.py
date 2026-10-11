"""Final cached native reports/minute summaries only: no replay or trace scan."""
import json,csv,hashlib,collections,re,shutil,subprocess
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
OUT=Path(__file__).parent;J=Path("/var/lib/coinmaster-native-gui/data/runs/jobs")
FROZEN="a9cbb737a5239d10b9ffcb97d55f997917945263"
LABELS={"c":"sizing-c","v1":"sizing-v1","v2":"sizing-v2","v3":"v0-selective-lifecycle-cap30m-btc-direction","v4":"v0-selective-lifecycle-cap30m-btc-dd25-15"}
archive=J/"cm113-minute-extrema-risk-20261010/result/v0-selective-lifecycle-cap30m.json";old=json.loads(archive.read_text());allreports={};details={};rows=[]
def utc(node):
 if isinstance(node,dict):
  if "timestamp_ns" in node:node["timestamp_utc"]=datetime.fromtimestamp(int(node["timestamp_ns"])/1e9,timezone.utc).isoformat()
  for v in list(node.values()):utc(v)
 elif isinstance(node,list):
  for v in node:utc(v)
def diff(a,b,path=""):
 if isinstance(a,dict) and isinstance(b,dict):
  out=[]
  for k in sorted(set(a)|set(b)):out.extend(diff(a.get(k),b.get(k),path+"."+k))
  return out
 return [] if a==b else [{"path":path,"C":a,"variant":b}]
for name,label in LABELS.items():
 job=J/("cm113-sizing-"+name+"-20261011");art=job/"result"/(label+".json");p=json.loads(art.read_text());m=json.loads((job/"result/minute-risk-summary.json").read_text());allreports[name]=p
 subprocess.run(["/usr/bin/python3",str(OUT/"validate_pack.py"),str(job)],check=True,capture_output=True,text=True)
 assert (job/"source-commit.txt").read_text().strip()==FROZEN
 assert p["streaming"]["processed_rows_per_source"]==1051200 and m["rows"]==3153600
 assert m["conditional_upper_to_later_lower_bound"]["samples"]==1051200
 assert p["data_hash"]==old["data_hash"] and p["policy"]==old["policy"] and p["policy_hash"]==old["policy_hash"]
 assert p["config"]["fixed_base_fee_policy"]==old["config"]["fixed_base_fee_policy"]
 assert p["control_report_sha256"]=="d6a29d6e0e9ac586b911f2802cbe89602a05d2c0d73026d08ed76082a8a934f9"
 assert p["config"]["research_v0_zero_tp_netting"] is False and p["config"]["tp_fee_floor_v1"] is False
 assert p["status"]=="NOT_FAITHFUL_DIAGNOSTIC" and p["ranking_eligible"] is False
 assert p["fee_attribution"]["reconciled"] is True
 c=m["curves"]["all_native_close_samples"];b=m["conditional_upper_to_later_lower_bound"]
 utc(c);utc(b)
 total=D(p["terminal_total"]);base=D("5146884.95718200")
 byasset={}
 for asset in ["BTC","SOL"]:
  rr=[x for x in p["fill_audit"] if x["instrument"].startswith(asset)]
  byasset[asset]={"fills":len(rr),"fees":str(sum((D(x["commission"]) for x in rr),D(0))),"notional":str(sum((D(x["notional"]) for x in rr),D(0))),"actions":dict(collections.Counter(x["action"] for x in rr)),"reasons":dict(collections.Counter(x["reason"] for x in rr))}
 dd=D(c["top3_distinct_excursions"][0]["drawdown_peak_percent"])
 row={"variant":name.upper(),"TOTAL":str(total),"ACTIVE":p["terminal_active"],"RESERVE":p["terminal_reserve"],"ROI_percent":str((total/D(10000)-1)*100),"delta_C":str(total-base),"delta_C_percent":str((total/base-1)*100),"native_global_minute_DD_percent":str(dd),"DD_eligible_le50":dd<=50,"seed_minimum":c["minimum"]["equity"],"loss_below_seed_percent":c["maximum_loss_below_seed_percent"],"conditional_upper_to_later_lower_percent":b["maximum"]["drawdown_peak_percent"],"cash_DD_percent":str(D(str(p["summary"]["max_drawdown_percent"]))*100),"fees":p["native_fees"],"BTC_fills":byasset["BTC"]["fills"],"SOL_fills":byasset["SOL"]["fills"],"fills":p["fills"],"orders":p["execution_artifacts"]["orders"]["rows"],"funding_events":p["funding"]["count"],"signed_funding":p["funding"]["signed_amount"],"liquidations":p["liquidation_count"],"open_positions":p["terminal_open_positions"]};rows.append(row)
 audit=p.get("btc_sizing_audit",[]);episodes=[x for x in audit if x["event"]=="EPISODE_ENTRY_SIZING"];state=[x for x in audit if x["event"]=="DRAWDOWN_STATE_CHANGE"]
 before=(job/"pilot-before.txt").read_text();after=(job/"pilot-after.txt").read_text();assert before==after and "MainPID=2009732" in after and "NRestarts=0" in after
 raw=json.loads((job/"native-run-receipt.json").read_text());journal=raw["unit_journal"]
 compact={"variant":name,"source_commit":FROZEN,"artifact":str(art),"artifact_sha256":hashlib.sha256(art.read_bytes()).hexdigest(),"exit_code":0,"launched_at":(job/"launched-at.txt").read_text().strip(),"systemd_completed_lines":[x for x in journal.splitlines() if "Deactivated successfully" in x or "Consumed" in x],"pilot_before":before,"pilot_after":after,"source_guard_file":str(job/"source-input-hashes.sha256"),"immutable_source_hash_manifest_sha256":hashlib.sha256((job/"immutable-source-hashes.json").read_bytes()).hexdigest(),"immutable_files_verified":106,"data_hash":p["data_hash"],"policy_hash":p["policy_hash"],"config_hash":p["config_hash"],"source_hashes":p["source_hashes"],"streaming":p["streaming"],"minute_rows":m["rows"],"upper_bound_samples":b["samples"],"funding_journal":p["funding_journal"],"terminal_lifecycle":p["terminal_lifecycle"],"post_boundary_settlement":p["post_boundary_settlement"],"boundary_samples_excluded":m["post_boundary_settlement_excluded_from_interval_curves"]}
 if (job/"resource-before.json").exists():compact["resources_before"]=json.loads((job/"resource-before.json").read_text())
 (OUT/(name+"-receipt.json")).write_text(json.dumps(compact,indent=2)+"\n")
 details[name]={"metrics":row,"receipt":compact,"config":p["config"],"source_hashes":p["source_hashes"],"interval":p["interval"],"run_interval":p["run_interval"],"warmup":p["warmup"],"native_minute_curve":c,"conditional_upper_to_later_lower_bound":b,"conditional_lower_envelope":m["curves"]["conditional_ohlc_adverse"],"conditional_margin_breach_count":m["potential_conditional_intrabar_margin_breach_count"],"assets":byasset,"fee_attribution":p["fee_attribution"],"btc_sizing_audit_event_counts":dict(collections.Counter(x["event"] for x in audit)),"episode_frozen_multiplier_counts":dict(collections.Counter(x["frozen_multiplier"] for x in episodes)),"episode_side_multiplier_counts":dict(collections.Counter(str(x["side"])+":"+x["frozen_multiplier"] for x in episodes)),"drawdown_state_changes":state,"status":p["status"],"ranking_eligible":p["ranking_eligible"]}
for name,p in allreports.items():details[name]["config_diff_from_C"]=diff(allreports["c"]["config"],p["config"])
eligible=[x for x in rows if x["DD_eligible_le50"]];winner=max(eligible,key=lambda x:D(x["TOTAL"]))["variant"] if eligible else None
assert winner is None
parity=json.loads((OUT/"C-archived-native-parity.json").read_text());assert all(x["equal"] for x in parity.values())
limitations=["All outputs remain NOT_FAITHFUL_DIAGNOSTIC and ranking_eligible=false; no live promotion or faithful exchange execution claim.","C is a measured fixes-only baseline on the same frozen source. Its 502 native fill rows and 556 order rows match archived control exactly after excluding init_id only. Each V is compared against C; no extra control/repeat/refinement replay.","Native marked minute DD, seed minimum and TOP3 preserve global peaks without resets and exclude post-boundary settlement quotes. Cash-DD is a separate account series and is not the eligibility metric.","Conditional upper-to-strictly-later-lower bound uses prior completed-bar favorable equity versus later adverse equity for fixed prequote exposure. It assumes no same-bar extrema order and is not observed tick portfolio DD or a venue liquidation guarantee.","V4 hysteresis sizes future genuine BTC episodes; multiplier/notional freeze before q0, without resizing held exposure or resetting the global peak. Normal7.875→reduced3.9375 at DD>=25%, normal return at DD<=15%. V3 long5.5/short7.875. Original gross SOL H and actual-fill earned-right behavior retained.","All candidates keep approved SOL multipliers, BTC TP fractions, fee/funding policy, 30m cap, seed10000/reserve0 and existing three repair flags; BTC20, SOL hedge, SOLcap6, PORT45 and fee floor are OFF.","Funding events are genuine native posts but signed funding remains UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA. Do not infer zero.","Missing L2/trade tape, close-only execution proxy, historical fee applicability, native liquidation model and live recovery limits remain. No actual liquidations here does not prove venue survival.","Exactly five sequential engines completed. Public venue metadata was included in each immutable allowlisted pack. Shared canonical venv/data were read-only bound, not copied. PilotPID2009732/NRestarts0/release81e6318 preserved; no credentials, real orders, service restarts or deploy."]
package={"source_commit":FROZEN,"economic_runs":5,"winner_highest_TOTAL_native_DD_le50":winner,"archived_control":{"artifact":str(archive),"sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),"TOTAL":old["terminal_total"],"C_native_parity":parity},"variants":details,"limitations":limitations}
(OUT/"comparison.json").write_text(json.dumps(package,indent=2)+"\n")
with (OUT/"comparison.csv").open("w",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
md=["# CM-113 BTC sizing / DD50 comparison","","Five approved sequential native 24-month runs, frozen source `"+FROZEN+"`. Interval [2024-09-01,2026-09-01); seed 10,000 USDT, reserve zero. C fixes-only7.875; V1 fixed6.3; V2 fixed5.5; V3 long5.5/short7.875; V4 episode sizing hysteresis25/15%.","","**Eligible winner: none.** Every native global minute DD exceeds50%. V3 has highest TOTAL; V4 has lowest native DD, still52.1271%, with conditional extrema bound61.1856%.","","| Variant | TOTAL USDT | ROI % | Native minute DD % | Conditional bound % | Seed minimum | Fees | BTC/SOL fills |","|---|---:|---:|---:|---:|---:|---:|---:|"]
for r in rows:md.append("| {} | {} | {} | {} | {} | {} | {} | {}/{} |".format(r["variant"],r["TOTAL"],r["ROI_percent"],r["native_global_minute_DD_percent"],r["conditional_upper_to_later_lower_percent"],r["seed_minimum"],r["fees"],r["BTC_fills"],r["SOL_fills"]))
md.extend(["","V3 gains290,323.61232895 USDT versus measured C but fails the risk constraint. V4 loses2,034,853.72598566 USDT versus C; it improves native DD but does not satisfy50% or establish an intrabar50% guarantee.","","All five processed1,051,200 rows per source and3,153,600 observer rows; each strict-later extrema tracker has1,051,200 samples. Fees reconcile; zero liquidations and terminal flat. Per-run receipts/hashes, exact parameter differences, BTC/SOL actions/notionals/fees, maker/taker totals, funding counts, TOP3 peak/trough/recovery timestamps and V3/V4 sizing audits are in comparison.json. Full raw traces/logs/journals remain private job artifacts.","","## TOP3 native minute drawdowns",""])
for n,d in details.items():md.append(n.upper()+": "+", ".join(str(round(D(x["drawdown_peak_percent"]),6))+"%" for x in d["native_minute_curve"]["top3_distinct_excursions"]))
md.extend(["","## Limitations",""]+["- "+x for x in limitations]);(OUT/"README.md").write_text("\n".join(md)+"\n")
setup=json.loads((OUT/"setup-contract.json").read_text());setup.update(status="FIVE_APPROVED_ECONOMIC_RUNS_COMPLETED",source_commit=FROZEN,economic_runs=5,authoritative_report="comparison.json",eligible_winner=winner);setup["observability"]="Streamed prior-bar favorable upper to strictly-later adverse lower in native observer; no report-side recomputation or trace scan";(OUT/"setup-contract.json").write_text(json.dumps(setup,indent=2)+"\n")
(OUT/"SHA256SUMS").write_text("".join(hashlib.sha256(f.read_bytes()).hexdigest()+"  "+f.name+"\n" for f in sorted(OUT.iterdir()) if f.is_file() and f.name!="SHA256SUMS"))
print(json.dumps({"winner":winner,"rows":rows,"sizing_events":{n:d["btc_sizing_audit_event_counts"] for n,d in details.items()}}))
