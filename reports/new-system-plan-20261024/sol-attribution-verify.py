#!/usr/bin/env python3
"""One independent output/fill accounting verification, no minute replay or engine."""
import csv,json,hashlib,collections
from pathlib import Path
from decimal import Decimal as D,getcontext
from datetime import datetime
getcontext().prec=60
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];BASE=ROOT/'reports/b-50-90-next-20261023'
def read(p):
 with p.open() as f:return list(csv.DictReader(f))
cs=read(OUT/'sol-attribution-cycles.csv');summary=read(OUT/'sol-attribution-summary.csv');r=json.loads((BASE/'owner-E4-receipt.json').read_text());fills=read(Path(r['exports']['fills']['path']))
assert len({x['client_order_id'] for x in fills})==len(fills)==535
sol=[x for x in fills if x['instrument_id'].startswith('SOL')]
actualcash=-sum((D(x['filled_qty'])*(1 if x['side']=='BUY' else -1)*D(x['avg_px']).quantize(D('.001')) for x in sol),D(0))
actualfee=sum((sum((D(s.split()[0]) for s in __import__('ast').literal_eval(x['commissions'])),D(0)) for x in sol),D(0))
assert sum(D(c['fill_cash']) for c in cs)==actualcash
assert sum(D(c['fees']) for c in cs)==actualfee
for c in cs:
 assert D(c['held'])+D(c['exec'])==D(c['fill_cash'])
 assert abs(D(c['factor270'])+D(c['residual270'])+D(c['exec'])-D(c['fees'])-D(c['fill_net']))<D('1e-45')
 assert abs(D(c['factor720'])+D(c['residual720'])+D(c['exec'])-D(c['fees'])-D(c['fill_net']))<D('1e-45')
 assert int(c['beta720_last_end_ns'])<int(c['start_ns'])
a=next(x for x in summary if x['year_calendar']=='all' and x['BTC_state']=='ALL')
assert D(a['observed_mark_and_exec_net'])==actualcash-actualfee
assert sum(D(x['observed_mark_and_exec_net']) for x in summary if x['year_calendar']=='all' and x['BTC_state']!='ALL')==actualcash-actualfee
assert sum(D(x['observed_mark_and_exec_net']) for x in summary if x['year_calendar']!='all' and x['BTC_state']=='ALL')==actualcash-actualfee
bytime=collections.defaultdict(list)
for f in fills:bytime[int(datetime.fromisoformat(f['ts_last']).timestamp())*10**9].append(f)
starts={int(c['start_ns']):c for c in cs};q=D(0);startstates=[]
for t,fs in sorted(bytime.items()):
 if t in starts:
  tie=any(f['instrument_id'].startswith('BTC') for f in fs)
  startstates.append({'cycle':starts[t]['cycle'],'start_ns':t,'pre_timestamp_actual_BTCqty':str(q),'BTC_fill_same_timestamp':tie,'activation_BTCstate':'UNKNOWN_TIMESTAMP_TIE' if tie else ('BTC_FLAT' if not q else 'BTC_HELD')})
 for f in fs:
  if f['instrument_id'].startswith('BTC'):q+=D(f['filled_qty'])*(1 if f['side']=='BUY' else -1)
assert q==0
with (OUT/'sol-attribution-cycle-start-states.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(startstates[0]));w.writeheader();w.writerows(startstates)
v=json.loads((OUT/'sol-attribution-verification.json').read_text());v['independent_file_accounting_verification']='PASS';v['SOL_cycle_start_states']=dict(collections.Counter(x['activation_BTCstate'] for x in startstates));v['observed_SOL_fill_cash']=str(actualcash);v['observed_SOL_native_fees']=str(actualfee);v['observed_SOL_fill_net_ex_funding']=str(actualcash-actualfee)
(OUT/'sol-attribution-verification.json').write_text(json.dumps(v,indent=2)+'\n')
print(json.dumps({k:v[k] for k in ['independent_file_accounting_verification','SOL_cycle_start_states','observed_SOL_fill_net_ex_funding']},indent=2))
