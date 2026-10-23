"""Compact actual BTC fill calendar comparison only; no engine/trace/PnL model."""
from pathlib import Path
from decimal import Decimal as D
import csv,json,hashlib
R=Path(__file__).parent.resolve()
keys=('action','fill_ns','px','level','native_liquidity_side','reason','instrument','order_type','post_only')
def load(name):
 p=R/('owner-'+name+'-events')/'native-fill-audit.csv'
 return p,[x for x in csv.DictReader(p.open()) if x['instrument'].startswith('BTC')]
basepath,base=load('P0');out={};differences=[]
for name in ('R1','R2','R2C'):
 if not (R/('owner-'+name+'-events')).exists():continue
 p,rows=load(name);calendar=[{k:x[k] for k in keys} for x in rows]
 basecalendar=[{k:x[k] for k in keys} for x in base]
 diffs=[dict(index=i,baseline={k:a[k] for k in keys},candidate={k:b[k] for k in keys}) for i,(a,b) in enumerate(zip(base,rows)) if any(a[k]!=b[k] for k in keys)]
 qtydiff=[i for i,(a,b) in enumerate(zip(base,rows)) if D(a['qty'])!=D(b['qty'])]
 result=dict(native_BTC_fill_count=len(rows),baseline_count=len(base),same_actual_calendar_prices_sides_reasons=calendar==basecalendar,calendar_comparison_fields=list(keys),calendar_differences=diffs,quantity_changed_rows=len(qtydiff),first_quantity_change=dict(index=qtydiff[0],baseline=base[qtydiff[0]],candidate=rows[qtydiff[0]]) if qtydiff else None,baseline_native_BTC_fees=str(sum((D(x['commission']) for x in base),D(0))),candidate_native_BTC_fees=str(sum((D(x['commission']) for x in rows),D(0))),source_csv=str(p),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),qualification='Actual native fill calendar/prices comparison; quantity/fee differences do not imply fixed-state alternative PnL. Original capital changes can resize later BTC without entry calendar changes.')
 out[name]=result
(R/'owner-btc-calendar-comparison.json').write_text(json.dumps(dict(baseline='P0_EXACT_XS',baseline_sha256=hashlib.sha256(basepath.read_bytes()).hexdigest(),recipes=out,no_engine=True,no_full_trace_scan=True),indent=2)+'\n')
print(json.dumps({k:{f:v[f] for f in ('native_BTC_fill_count','same_actual_calendar_prices_sides_reasons','quantity_changed_rows')} for k,v in out.items()}))
