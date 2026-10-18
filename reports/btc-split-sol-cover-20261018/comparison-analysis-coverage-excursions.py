"""Bounded actual-fill overshoot localization, no PnL and no engine replay."""
import argparse,json,csv,bisect
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,deque
from datetime import datetime,timezone
import pyarrow.parquet as pq
ap=argparse.ArgumentParser();ap.add_argument('--label',required=True);ap.add_argument('--result',required=True);ap.add_argument('--threshold',type=float,required=True);a=ap.parse_args();p=Path('reports/btc-split-sol-cover-20261018');r=json.load(open(a.result));events=defaultdict(list);sides=defaultdict(deque)
for f in csv.DictReader(open(r['execution_artifacts']['fills']['path'])):
 ns=int(datetime.fromisoformat(f['ts_last']).timestamp())*1000000000;sym='BTC' if f['instrument_id'].startswith('BTC') else 'SOL';sides[ns,sym,D(f['filled_qty']),D(f['avg_px']).quantize(D('.000001'))].append(f['side'])
for f in r['fill_audit']:
 ns=int(f['fill_ns']);sym='BTC' if f['instrument'].startswith('BTC') else 'SOL';side=sides[ns,sym,D(f['qty']),D(f['px']).quantize(D('.000001'))].popleft();events[ns].append((sym,D(f['qty'])*(1 if side=='BUY' else -1)))
cover=r['split_cover_audit']['cover'];starts=sorted((int(x['start_ns']),float(x['beta']),x['episode_id']) for x in cover if x.get('event')=='COVER_START');keys=[x[0] for x in starts];qty={'BTC':D(0),'SOL':D(0)};intervals=[];active=None;previous=None;pending_peak_next=None
files=[Path('/var/lib/coinmaster-native-gui/data/normalized')/f'bybit-{s}USDT-mark-1m.parquet' for s in ('BTC','SOL')];readers=[pq.ParquetFile(f).iter_batches(batch_size=10080,columns=['open_time_ms','close']) for f in files]
def utc(ns):return datetime.fromtimestamp(ns/1e9,timezone.utc).isoformat()
def finish():
 global active
 if active:intervals.append(active);active=None
for bb,ss in zip(*readers):
 bt=bb.column(0).to_pylist();st=ss.column(0).to_pylist();assert bt==st
 for tm,b,s in zip(bt,bb.column(1).to_pylist(),ss.column(1).to_pylist()):
  ns=(int(tm)+60000)*1000000
  for sym,q in events.get(ns,[]):qty[sym]+=q
  if qty['BTC']==0 or ns>=1788220800000000000:finish();previous=None;continue
  i=bisect.bisect_right(keys,ns)-1;beta=starts[i][1];ep=starts[i][2];c=float(abs(qty['SOL'])/abs(qty['BTC']))*float(s)/float(b)*beta
  if qty['BTC']*qty['SOL']>0:c=-c
  sample=dict(ns=ns,utc=utc(ns),coverage=c,episode_id=ep,btc_qty=str(qty['BTC']),sol_qty=str(qty['SOL']),btc_mark=b,sol_mark=s,beta=beta)
  if active and active.get('peak_next') is None and ns>active['peak']['ns']:active['peak_next']=sample
  if c>a.threshold+1e-9:
   if active is None:active=dict(start_ns=ns,start_utc=utc(ns),end_exclusive_ns=ns+60000000000,duration_seconds=60,peak=sample,peak_previous=previous,peak_next=None)
   else:
    active['end_exclusive_ns']=ns+60000000000;active['duration_seconds']+=60
    if c>active['peak']['coverage']:active['peak']=sample;active['peak_previous']=previous;active['peak_next']=None
  else:finish()
  previous=sample
finish()
def eventtime(x):return int(x.get('timestamp_ns',x.get('start_ns',x.get('hour_close_ns',0))))
def annotate(x):
 y=dict(x);ts=y['peak']['ns'];ep=y['peak']['episode_id'];near=[dict(z,utc=utc(int(z['fill_ns']))) for z in r['fill_audit'] if abs(int(z['fill_ns'])-ts)<=600000000000];same=[z for z in cover if z.get('episode_id')==ep];y['nearby_native_fills_10min']=near;y['latest_cover_target']=next((z for z in reversed(same) if z.get('event')=='COVER_TARGET' and eventtime(z)<=ts),None);y['latest_cover_anchor']=next((z for z in reversed(same) if z.get('event')=='COVER_ANCHOR' and eventtime(z)<=ts),None);y['nearby_cover_events_10min']=[z for z in same if abs(eventtime(z)-ts)<=600000000000];y['end_exclusive_utc']=utc(y['end_exclusive_ns']);return y
out=dict(label=a.label,threshold=a.threshold,interval_count=len(intervals),total_above_seconds=sum(x['duration_seconds'] for x in intervals),top3_by_peak=[annotate(x) for x in sorted(intervals,key=lambda x:x['peak']['coverage'],reverse=True)[:3]],top3_by_duration=[annotate(x) for x in sorted(intervals,key=lambda x:x['duration_seconds'],reverse=True)[:3]],method='Actualnativefill-eventnetqty matchedtonativeCSVside, canonicalbothmarkclose, frozenCOVER_STARTbeta. Consecutivecompleted1m samples; each60s. Targetsnotcontinuoushardcaps. NoPnLreconstruction/cachepositionuse/noengine.' )
(p/f'comparison-analysis-{a.label}-coverage-excursions.json').write_text(json.dumps(out,indent=2)+'\n');print(a.label,'intervals',len(intervals),'seconds',out['total_above_seconds']);print(json.dumps([dict(start=x['start_utc'],seconds=x['duration_seconds'],peak=x['peak'],previous=x['peak_previous'],next=x['peak_next'],fills=x['nearby_native_fills_10min']) for x in out['top3_by_peak']],indent=2))
