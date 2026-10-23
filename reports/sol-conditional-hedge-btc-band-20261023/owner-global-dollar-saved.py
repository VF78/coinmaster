from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import csv,gzip,json,hashlib
OUT=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021/reports/sol-conditional-hedge-btc-band-20261023')
m=json.loads((OUT/'owner-analysis-manifest.json').read_text());rows=list(csv.DictReader((OUT/'owner-global-risk.csv').open()));by={x['recipe']:x for x in rows}
def iso(n):return datetime.fromtimestamp(int(n)/1e9,timezone.utc).isoformat()
for source in m['inputs']:
    peak=D(10000);peakts=1725148800000000000;maxloss=D(0);losspeak=peak;losspeakts=peakts;trough=peak;troughts=peakts;recovery=None
    for r in csv.DictReader(gzip.open(source['settled_trace'],'rt')):
        eq=D(r['paired_close_equity']);t=int(r['receipt_ns'])
        if eq>peak:peak=eq;peakts=t
        drop=peak-eq
        if drop>maxloss:maxloss=drop;losspeak=peak;losspeakts=peakts;trough=eq;troughts=t;recovery=None
        if recovery is None and t>troughts and eq>=losspeak:recovery=t
    row=by[source['recipe']];row.update(peak_to_trough_amount_at_max_percent_DD=row['peak_to_trough_amount'],maximum_absolute_drawdown_amount=str(maxloss),maximum_absolute_DD_peak_equity=str(losspeak),maximum_absolute_DD_peak_utc=iso(losspeakts),maximum_absolute_DD_trough_equity=str(trough),maximum_absolute_DD_trough_utc=iso(troughts),maximum_absolute_DD_recovery_utc=iso(recovery) if recovery else None,maximum_absolute_DD_percent=str(maxloss/losspeak*100),max_dollar_DD_is_separate_from_max_percent_DD=True)
    print(source['recipe'],str(maxloss),flush=True)
p=OUT/'owner-global-risk.csv'
with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=sorted({k for x in rows for k in x}));w.writeheader();w.writerows(rows)
m['exports'][p.name].update(rows=len(rows),sha256=hashlib.sha256(p.read_bytes()).hexdigest());m['global_dollar_drawdown_method']='Additional bounded read of saved settled native equity receipts only; maximum absolute dollar drawdown independently retained from maximum percent drawdown event. No engine/account reconstruction.'
(OUT/'owner-analysis-manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
