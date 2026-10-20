import json,csv
from decimal import Decimal as D
from pathlib import Path
P=Path("reports/winner-6077107-stats");d=json.load(open(P/"risk-statistics.json"))
def num(x,n=4):return format(D(str(x)),",."+str(n)+"f")
def ep(e):
 return [e["id"],e["peak"]["utc"],num(e["peak"]["equity"],2),e["trough"]["utc"],num(e["trough"]["equity"],2),num(e["drawdown_percent"]),num(e["drawdown_amount"],2),num(e["peak_to_trough_days"]),e["recovery"]["utc"] if e["recovery"] else "UNRECOVERED",num(e["peak_to_recovery_or_end_days"])]
def table(headers,rows):return "| "+" | ".join(headers)+" |\n|"+"|".join("---" for _ in headers)+"|\n"+"".join("| "+" | ".join(map(str,r))+" |\n" for r in rows)
out=["# Exact 6,077,107.23887483 winner: native risk and time statistics\n",
"Source is the selected control artifact, not CHOP_PAIR_50_NET_v1 and not the embedded older control_terminal_total 3,386,491.65211338. Seed 10,000 USDT; interval [2024-09-01,2026-09-01), UTC. No new engine, backtest, optimizer or PnL matching engine. Existing artifact status is NOT_FAITHFUL_DIAGNOSTIC with ranking_eligible=false; these are statistics of this exact run, not a venue-fidelity approval.\n",
"## Measurement and verification\n"]
for k,v in d["basis"].items():out.append("**"+k+":** "+v+"\n")
out.append("Checks:\n"+table(["Check","Value"],[[k,str(v)] for k,v in d["checks"].items()]))
out.append("The all-native curve includes "+str(d["checks"]["interval_native_rows"])+" exported interval samples plus the initial seed, consistent with the existing "+str(d["checks"]["interval_native_with_seed"])+"-sample summary. Two post-boundary rows are separate settlement observations. OHLC conditional bound remains separate from observed native close DD.\n")
out.append("## Global drawdown excursions\n")
out.append("An excursion begins when equity falls below the attained global high-water mark and ends at its first recovery to or above that mark. Equal high-water observations reset the recorded peak timestamp to the latest attainment. CSV includes every excursion, including unrecovered terminal excursion. Clock durations use timestamps; zero-duration callback excursions may occur because native phases share timestamps.\n")
out.append("Episodes: "+str(d["drawdown_episodes_count"])+"; unrecovered: "+str(d["unrecovered_episodes"])+". All-native maximum DD "+num(d["all_native_max_DD_percent"],10)+"%. Minimum relative to seed: "+num(d["initial_capital_minimum"]["equity"],8)+" at "+d["initial_capital_minimum"]["utc"]+"; loss below seed "+num(d["initial_capital_loss_percent"],8)+"%.\n")
headers=["ID","Peak UTC","Peak equity","Trough UTC","Trough equity","DD %","DD amount","Peak→trough days","Recovery UTC","Peak→recovery/end days"]
for title,key in [("Largest ten by percentage","top10_percent"),("Largest ten by amount","top10_amount"),("Longest ten by clock duration","longest10_clock")]:
 out.append("### "+title+"\n"+table(headers,[ep(e) for e in d[key]]))
out.append("## Time underwater and threshold stress\n")
out.append("All-native global high-water elapsed duration, reconstructed from the complete exported excursion boundaries without a second trace pass:\n"+table(["Measure","Value"],[[k,v] for k,v in d["all_native_underwater_elapsed"].items()]))

out.append("These duration statistics use one paired post-SOL sample per minute and its sampled global high-water mark; the all-native peak can differ slightly due to callback ordering. Threshold all-native entry counts are reported separately. Each sampled minute contributes one minute; maximum duration is sample-count duration, not a claim of intraminute exposure certainty.\n")
out.append(table(["Measure","Value"],[[k,v] for k,v in d["time_underwater"].items()]))
out.append(table(["DD threshold %","All-native entries","Paired-minute entries","Minutes at/below threshold","Days","% of interval","Longest minutes","Longest days","Longest start UTC","Longest last sample UTC"],[[k,v["all_native_entries"],v["sampled_entries"],v["minutes"],num(D(v["minutes"])/1440),num(D(v["minutes"])/1051200*100),v["max_contiguous_minutes"],num(D(v["max_contiguous_minutes"])/1440),v["longest_start"],v["longest_end"]] for k,v in d["thresholds"].items()]))
out.append("## Worst equity changes\n")
out.append("Returns use native equity, including marked open positions, not cash-only changes. Amount and percentage minima can occur in different windows. Rolling 30 days is 43,200 minutes; calendar months are reported separately.\n")
rows=[]
for h,v in d["rolling_worst"].items():
 for metric,s in v.items():rows.append([h,metric,num(D(s["value"])*100 if metric=="return" else s["value"],8),s["start"]["utc"],num(s["start"]["equity"],2),s["end"]["utc"],num(s["end"]["equity"],2)])
out.append(table(["Rolling minutes","Metric","Value (% or USDT)","Start UTC","Start E","End UTC","End E"],rows))
for k,rows in d["calendar_worst"].items():out.append("### Worst ten calendar "+k+" returns\n"+table(["Period","Start E","End E","Change","Return %","Within-period minute DD %"],[[x["period"],num(x["start_equity"],2),num(x["end_equity"],2),num(x["change"],2),num(x["return_percent"]),num(x["within_period_DD_percent"])] for x in rows]))
out.append("## All 24 calendar months\n")
out.append("Start/end native equity compounds exactly through all months to the final interval marked value. Monthly within-period DD is measured from the larger of period-start equity and subsequent paired-minute peaks, and differs from global DD. Positive/negative/flat day counts use UTC daily equity changes. End cash plus native marked unrealized equals end equity; no funding or realized per-asset components are invented.\n")
out.append(table(["Month","Start E","End E","Return %","Min E","Max E","Within-month DD %","+days","−days","0days","End cash","End native U"],[[x["period"],num(x["start_equity"],2),num(x["end_equity"],2),num(x["return_percent"]),num(x["min_equity"],2),num(x["max_equity"],2),num(x["within_period_DD_percent"]),x["positive_days"],x["negative_days"],x["flat_days"],num(x["end_cash"],2),num(x["end_native_unrealized"],2)] for x in d["monthly"]]))
b=d["settlement_bridge"];out.append("### Terminal marked-to-settled reconciliation\n")
out.append(table(["Measure","Value"],[["Final interval UTC",b["final_interval_marked"]["utc"]],["Final interval native marked E",b["final_interval_marked"]["equity"]],["Final interval cash",b["final_interval_marked"]["cash"]],["Final interval native U",b["final_interval_marked"]["native_total_unrealized"]],["Actual settled TOTAL",b["settled_total"]],["Marked→settled delta",b["marked_to_settled_delta"]],["August2026 settled variant return %",b["last_month_settled_return_percent"]],["Raw settlement metadata",json.dumps(b["raw_settlement"])]]))
out.append("Native settlement bridge: actual terminal fee "+str(b["terminal_fee_from_native_fill"])+", actual native cash increment before fee "+str(b["native_cash_increment_before_terminal_fee"])+", residual versus final native U "+str(b["native_marked_U_to_cash_increment_residual"])+". Exact arithmetic equality verified: "+str(b["fee_plus_native_U_to_cash_bridge_exact_match"])+". "+b["bridge_qualification"]+"\n")
out.append("The settled variant replaces only the last monthly endpoint with actual settled TOTAL. It is shown separately, so boundary settlement costs are not hidden in a purported interval return. The old artifact marked_equity_series.monthly_returns remains UNKNOWN; these calendar returns are newly derived from durable paired native samples.\n")
out.append("## Native exposure and concentration\n")
out.append("Minutes and percentages refer to the full 730-day interval, including flat time. Asset long/short categories overlap with portfolio BTC-only/SOL-only/both categories; these rows must not all be summed. Net directional notionals use raw dollar directions, without a beta claim.\n")
out.append(table(["State","Minutes","Days","% of interval"],[[k,v,num(D(v)/1440),num(d["exposure_percent"][k])] for k,v in d["exposure_minutes"].items()]))
out.append(table(["Extreme","Value (ratio or USDT)","UTC","Native E","Cash","Native U","Actual positions"],[[k,num(v["value"],8),v["snapshot"]["utc"],v["snapshot"]["equity"],v["snapshot"]["cash"],v["snapshot"]["native_total_unrealized"],"; ".join(p["instrument_id"][:3]+" "+("LONG" if p["side"]=="2" else "SHORT")+" "+p["quantity"]+" basis "+p["avg_px_open"]+" mark "+p["mark_ohlc"]["close"] for p in v["snapshot"]["positions"])] for k,v in d["exposure_extremes"].items()]))
out.append("## Files and limits\n")
out.append("Full excursions: risk-drawdowns.csv. All 730 daily NAV/cash/U/returns/extrema: risk-daily.csv. Monthly: risk-monthly.csv. Weekly: risk-weekly.csv. Small plot source: risk-daily-curve.csv. Exact values, detailed native minimum/maximum position context, top excursion metadata and thresholds: risk-statistics.json. Reproducible bounded-memory pass: risk-analysis.py.\n")
out.append("No assumption of intrabar extrema ordering; no historical venue mark-tick path reconstruction. Signed funding and realized per-asset PnL remain unknown. Calendar sampled extrema and time-underwater measures are explicit, and are not substituted for the verified all-native DD metric.\n")
(P/"risk-statistics.md").write_text("\n".join(out))
print(P/"risk-statistics.md")

