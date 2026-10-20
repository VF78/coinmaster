import csv,hashlib,json,resource
from collections import Counter
from decimal import Decimal as D
from pathlib import Path
R=Path("reports/fast-rnd-20261020")
p=R/"s0-drawdown-attribution-result.json";d=json.loads(p.read_text())
report=Path("/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-fast-rnd-s0-20261020T170935Z/result/v0-selective-lifecycle-cap30m-btc-split50-d0.0025-planref-v1-tp-ioc-btc-direction.json")
native=json.loads(report.read_text())
events=[]
for row in native["fill_audit"]:
    ts=int(row["fill_ns"])
    if not 1725148800000000000<=ts<d["cutoff_exclusive_ns"]:continue
    assert row["commission_currency"]=="USDT"
    asset="BTC" if row["instrument"].startswith("BTC") else "SOL"
    events.append((ts,asset,D(row["commission"])))
assert len(events)==d["coverage"]["native_fee_rows_TV"]
changed=0
for e in d["top5"]:
    costs={a:sum((fee for t,a2,fee in events if a==a2 and e["peak"]["source_ns"]<t<=e["trough"]["source_ns"]),D(0)) for a in ("BTC","SOL")}
    if any(D(e["native_commissions_by_asset"][a])!=costs[a] for a in costs):changed+=1
    e["native_commissions_by_asset"]={a:str(v) for a,v in costs.items()}
    e["native_commissions"]=str(sum(costs.values(),D(0)))
d["cost_provenance"]={"source":str(report),"field":"fill_audit actual native OrderFilled callback facts: fill_ns/instrument/commission/commission_currency","event_boundary":"(peak.source_ns,trough.source_ns], never receipt_ns; source receipt guards had0unavailable and native fill/account timestamps<=source","T_V_native_events":len(events),"top5_intervals_changed_vs_order_ts_last":changed,"scope":"only existing small native event facts, no W trace reread; outside-TV monetary fields not interpreted"}
d["assumptions"][4]="Native BTC/SOL actual OrderFilled commissions use fill_ns in (peak source timestamp,trough source timestamp]; included in W/cash already. Filled-order CSV ts_last is not relied on for event ordering."
d["assumptions"][-1]="Receipt stream stopped before first U monetary/position payload. Small native event table filtered by fill_ns before interpreting commissions; no U outcome details printed."
d["resource"]["fee_finalizer_peak_RSS_bytes"]=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
p.write_text(json.dumps(d,indent=2)+"\n")
cp=R/"s0-drawdown-attribution-result.csv"
with cp.open() as f:r=csv.DictReader(f);fields=r.fieldnames;rows=list(r)
for row,e in zip(rows,d["top5"]):
    row["BTC_fees"]=e["native_commissions_by_asset"]["BTC"];row["SOL_fees"]=e["native_commissions_by_asset"]["SOL"];row["native_fees"]=e["native_commissions"]
with cp.open("w",newline="") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
mp=R/"s0-drawdown-attribution-result.md";lines=mp.read_text().splitlines()
for i,line in enumerate(lines):
    if any(line.startswith("|"+str(k)+"|") for k in range(1,6)):
        cols=line.split("|");e=d["top5"][int(cols[1])-1]
        cols[8]=f'{D(e["native_commissions_by_asset"]["BTC"]):.8f}';cols[9]=f'{D(e["native_commissions_by_asset"]["SOL"]):.8f}'
        lines[i]="|".join(cols)
lines+=["","Brief endpoint attribution (native monetary facts only):",
"1. At the trough, SOL long native open-PnL lies between -5,619.537 and -5,165.433; BTC short is positive between 475.849 and 530.0042. Aggregate open loss is -5,121.0266. Cash also fell 3,738.47267409. Seed-capital loss is 5,469.42585299; exact initial-trade loss/realized asset allocation remains UNKNOWN.",
"2. Cash falls 407,279.98224643 and total open PnL falls 140,386.09995. Trough exposure is BTC-only, with exact native open loss 113,305.5378; this does not allocate the preceding cash loss by asset.",
"3. Both endpoints are BTC-only: native open PnL changes from +225,132.0842 to -938,216.4704 while cash rises 12,589.11625687. The open-book deterioration drives this decline; quantities differ, so this is not a same-lot causal PnL claim.",
"4. Both endpoints are SOL-only: positive native open PnL declines from 80,370 to 1,294.544, with cash down 190.14478393. This is predominantly positive-open-PnL giveback in the actual book; quantities changed.",
"5. Both endpoints are BTC-only: native open PnL changes from +93,132.17585 to -125,712.895 while cash rises 2,552.47182436. Open-book deterioration exceeds the W decline; no closed-trade allocation is inferred.",
"","Cost timing: actual saved OrderFilled fill_ns, not filled-order ts_last. Fees use (peak.source_quote_ns,trough.source_quote_ns]; cash/position source finality guards had zero unavailable receipts. Native commissions remain descriptive and already included in W."]
mp.write_text("\n".join(lines)+"\n")
print(json.dumps({"native_fee_rows_TV":len(events),"cost_intervals_changed":changed,"trace_rescans":0,"fee_finalizer_peak_RSS_bytes":d["resource"]["fee_finalizer_peak_RSS_bytes"]}))

