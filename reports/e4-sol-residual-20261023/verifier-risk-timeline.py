"""Native risk-order timeline from completed reports only; no native trace read."""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D
import csv,json,sys,ast
P=Path(__file__).resolve().parent
def ns(s):return int(datetime.fromisoformat(s).timestamp()*1e9)
def iso(n):return datetime.fromtimestamp(int(n)/1e9,timezone.utc).isoformat()
rows=[]
for recipe in sys.argv[1:]:
 receipt=json.loads((P/f'owner-{recipe}-receipt.json').read_text());d=json.loads(Path(receipt['artifact']).read_text());raw=json.loads(Path(receipt['raw_artifact']).read_text());fills=list(csv.DictReader(Path(d['execution_artifacts']['fills']['path']).open()));byid={f['client_order_id']:f for f in fills}
 triggers=[x for x in d['next_band_audit'] if x['event']=='S_TRIGGER']
 for cid,e in raw['native_order_events'].items():
  if e['reason']!='SOL_DOMINANT_ADVERSE_RISK' or cid not in byid:continue
  f=byid[cid];submit=int(e['submit_ns']);prior=[t for t in triggers if int(t['timestamp_ns'])<=submit];t=prior[-1]
  btc_before=sum(((1 if x['side']=='BUY' else -1)*D(x['filled_qty']) for x in fills if x['instrument_id'].startswith('BTC') and ns(x['ts_last'])<=int(t['timestamp_ns'])),D(0))
  candidates=sorted([(i,x) for i,x in enumerate(fills) if x['instrument_id'].startswith('SOL')],key=lambda z:(ns(z[1]['ts_last']),z[0]))
  q=D(0);before=None;flat=None;adds=0;seen=False
  for _,x in candidates:
   if x['client_order_id']==cid:before=q;seen=True
   elif seen and x['is_reduce_only']=='False':adds+=1
   q+=(1 if x['side']=='BUY' else -1)*D(x['filled_qty'])
   if seen and q==0:flat=x['ts_last'];break
  commission=sum((D(v.rsplit(' ',1)[0]) for v in ast.literal_eval(f['commissions'])),D(0))
  rows.append(dict(recipe=recipe,trigger_utc=iso(t['timestamp_ns']),cadence=t.get('cadence','H1'),reported_residual_btc_flat=t.get('residual_btc_flat',False),trigger_native_equity=t['settled_equity'],trigger_global_peak=t['peak'],frozen_held=t['held'],frozen_desired_remaining=t['desired_remaining'],native_BTC_signed_quantity_asof_trigger=btc_before,client_order_id=cid,submit_utc=iso(submit),native_last_fill_utc=f['ts_last'],actual_Q=f['filled_qty'],actual_native_avg_px=f['avg_px'],actual_native_fees=commission,actual_reduce_only=f['is_reduce_only'],SOL_signed_quantity_before_order_report=before,next_SOL_native_flat_utc=flat,later_native_SOL_increase_orders_until_flat=adds,qualification='BTC/SOL quantities reconstructed from native filled-order report side/quantity at ts_last, not domain/cache/ACK proof. Owner/source proofs establish residual gate. Each row actual native filled order, not trigger/proposal.'))
with (P/'verifier-risk-cut-timeline.csv').open('w') as f:
 w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(dict(recipes=sys.argv[1:],actual_native_risk_orders=len(rows),later_SOL_increases_before_flat=sum(r['later_native_SOL_increase_orders_until_flat'] for r in rows))))
