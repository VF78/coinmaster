"""Actual native filled quantity + canonical venue marks. No PnL reconstruction."""
import argparse,csv,json,bisect,hashlib,resource
from collections import defaultdict,Counter,deque
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path
import pyarrow.parquet as pq
ap=argparse.ArgumentParser();ap.add_argument('--result',required=True);ap.add_argument('--label',required=True);a=ap.parse_args();OUT=Path('reports/btc-split-sol-cover-20261018');r=json.load(open(a.result));events=defaultdict(list);sides=defaultdict(deque)
for f in csv.DictReader(open(r['execution_artifacts']['fills']['path'])):
 ts=int(datetime.fromisoformat(f['ts_last']).timestamp())*1000000000;sym='BTC' if f['instrument_id'].startswith('BTC') else 'SOL';sides[ts,sym,D(f['filled_qty']),D(f['avg_px']).quantize(D('.000001'))].append(f['side'])
for f in r['fill_audit']:
 ts=int(f['fill_ns']);sym='BTC' if f['instrument'].startswith('BTC') else 'SOL';side=sides[ts,sym,D(f['qty']),D(f['px']).quantize(D('.000001'))].popleft();events[ts].append((sym,D(f['qty'])*(1 if side=='BUY' else -1)))
assert all(not v for v in sides.values());cover=r['split_cover_audit']['cover'];starts=sorted((int(x['start_ns']),float(x['beta']),x['episode_id']) for x in cover if x.get('event')=='COVER_START');keys=[x[0] for x in starts]
files=[Path('/var/lib/coinmaster-native-gui/data/normalized')/f'bybit-{s}USDT-mark-1m.parquet' for s in ('BTC','SOL')];readers=[pq.ParquetFile(f).iter_batches(batch_size=10080,columns=['open_time_ms','close']) for f in files];qty={'BTC':D(0),'SOL':D(0)};cnt=Counter();bins=Counter();sumc=0.;minimum=maximum=None;extremes=[];processed=0;matched=0
for bb,ss in zip(*readers):
 bt=bb.column(0).to_pylist();st=ss.column(0).to_pylist();assert bt==st;bp=bb.column(1).to_pylist();sp=ss.column(1).to_pylist()
 for tm,b,s in zip(bt,bp,sp):
  ns=(int(tm)+60000)*1000000;processed+=1
  for sym,q in events.get(ns,[]):qty[sym]+=q;matched+=1
  if ns>=1788220800000000000:continue
  if qty['BTC']==0:
   if qty['SOL']!=0:cnt['orphan_sol_seconds']+=60
   continue
  cnt['btc_held_seconds']+=60
  if qty['SOL']!=0:cnt['btc_with_sol_seconds']+=60
  i=bisect.bisect_right(keys,ns)-1;assert i>=0;beta=starts[i][1];c=float(abs(qty['SOL'])/abs(qty['BTC']))*float(s)/float(b)*beta
  if qty['BTC']*qty['SOL']>0:c=-c
  bins[round(c*10000)/10000]+=60;sumc+=c*60;minimum=c if minimum is None else min(minimum,c);maximum=c if maximum is None else max(maximum,c)
  if c<.5-1e-9:cnt['below050_seconds']+=60
  if c<.45-1e-9:cnt['below045_seconds']+=60
  if .45-1e-9<=c<=.55+1e-9:cnt['within045_055_seconds']+=60
  if c<=1e-9:cnt['zero_coverage_seconds']+=60
  if c>1+1e-9:cnt['above100_seconds']+=60
  if (c<.45 or c>1) and len(extremes)<20:extremes.append(dict(ns=ns,c=c,btc_qty=str(qty['BTC']),sol_qty=str(qty['SOL']),btc_mark=b,sol_mark=s,beta=beta))
assert processed==1051200;assert matched==len(r['fill_audit']);assert qty=={'BTC':D(0),'SOL':D(0)}
total=cnt['btc_held_seconds'];cum=0;quant={}
for c,n in sorted(bins.items()):
 cum+=n
 for q in (.01,.05,.25,.5,.75,.95,.99):
  if str(q) not in quant and cum>=q*total:quant[str(q)]=c
result=dict(label=a.label,basis='ACTUAL_NATIVE_FILL_EVENT_NET_QUANTITY_PLUS_CANONICAL_BYBIT_MARK_CLOSE_AND_FIXED_COVER_START_BETA',formula='abs(SOLqty)*SOLmark*beta/(abs(BTCqty)*BTCmark), negative ifsamedirection',time_seconds={k:cnt[k] for k in ('btc_held_seconds','btc_with_sol_seconds','below050_seconds','below045_seconds','within045_055_seconds','zero_coverage_seconds','above100_seconds','orphan_sol_seconds')},fractions={k:cnt[k]/total for k in ('btc_with_sol_seconds','below050_seconds','below045_seconds','within045_055_seconds','zero_coverage_seconds','above100_seconds')},coverage_mean=sumc/total,coverage_min=minimum,coverage_max=maximum,quantiles_resolution_0001=quant,first_extremes=extremes,verified_native_fill_rows=matched,canonical_rows_per_mark=processed,terminal_net_qty={k:str(v) for k,v in qty.items()},peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,limitations='Onecompleted1mquote sample counted60s; no intraminute orderpath proof. Quantities fromactualnativefills groupedbyeventtimestampafterbothassets, notstalequote-cachepositions. Markclose rawvenue1m recordedmark, no genericPriceconversion andno uPnLreconstruction. ForSOL75/100 actualTOTALnetpositioncoverage, notanindependentlyobservedcore/tacticalsubposition. Fundingnotneeded/notimputed.')
(OUT/f'comparison-analysis-{a.label}-actual-fill-coverage.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
