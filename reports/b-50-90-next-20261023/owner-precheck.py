"""Saved B path causal reachability only: no engine, matching or synthetic PnL."""
import csv,gzip,hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
from decimal import Decimal,ROUND_FLOOR,ROUND_CEILING
import numpy as np
import pyarrow.parquet as pq
ROOT=Path('/Users/vf/Documents/ChatGPT/Coinmaster'); J=ROOT/'runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023'; R=ROOT/'research-worktrees/btc-pattern-pilot-m2-20261021/reports'; OUT=R/'b-50-90-next-20261023'; OLD=R/'sol-conditional-hedge-btc-band-20261023'; DATA=J/'inputs/data/normalized'
sys.path.insert(0,str(J/'source-25a085f/runtime'))
from coinmaster.domain.wave_overlay import Candidate,DailyBar,features_for,completed_wave_levels
UTC=timezone.utc;DAY=86400000000000;H4=DAY//6;H1=DAY//24
artifact=next((J/'BTC_REGIME_REENTRY_BAND_05/result').glob('v0*.json')); art=json.load(artifact.open()); cand=Candidate(**art['config']['candidate'])
def dump(name,rows):
 if not rows:return
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with (OUT/name).open('w',newline='') as f:w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)
def utc(ns):return datetime.fromtimestamp(int(ns)/1e9,UTC).isoformat()
def readcsv(p):return list(csv.DictReader(p.open()))
inputs=[]
def table(name):
 p=DATA/name;inputs.append(dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest()));return pq.read_table(p).to_pylist()
daily={sym:table('bybit-'+sym+'-daily.parquet') for sym in ['BTCUSDT','SOLUSDT']}; sols={x['open_time_ms']:x for x in daily['SOLUSDT']}
bars=[];dohlc={}
for b in daily['BTCUSDT']:
 t=b['open_time_ms'];s=sols.get(t)
 if s is None:continue
 close=(t+86400000)*1000000
 bars.append(DailyBar(datetime.fromtimestamp(t/1000,UTC),datetime.fromtimestamp(close/1e9,UTC),datetime.fromtimestamp(close/1e9,UTC),float(b['open']),float(b['close']),float(s['close'])))
 dohlc[close]=b
features=features_for(bars,cand); daily_state={};ema=atr=previous=None;trs=[]
for b,feature in zip(bars,features):
 ns=int(b.close_time.timestamp()*1e9); x=dohlc[ns];c=b.btc_close;ema=c if ema is None else 2/35*c+33/35*ema
 if previous is not None:
  tr=max(float(x['high'])-float(x['low']),abs(float(x['high'])-previous),abs(float(x['low'])-previous))
  if atr is None:
   trs.append(tr)
   if len(trs)==14:atr=sum(trs)/14
  else:atr=(13*atr+tr)/14
 previous=c;daily_state[ns]=dict(side=feature.side,ema=ema,atr=atr,close=c,index=feature.index)
cache={};barrows=[]
for sym in ['BTCUSDT','SOLUSDT']:
 m=table('bybit-'+sym+'-execution-1m.parquet');ts=np.array([x['open_time_ms']*1000000 for x in m]);assert np.all(np.diff(ts)==60000000000)
 for step in [H1,H4]:
  count=step//60000000000;assert ts[0]%step==0 and len(m)%count==0
  for a in range(0,len(m),count):
   part=m[a:a+count];op=int(ts[a]);cl=op+step
   row=dict(symbol=sym,step_ns=step,open_ns=op,close_ns=cl,available_ns=cl,open=part[0]['open'],high=str(max(Decimal(x['high']) for x in part)),low=str(min(Decimal(x['low']) for x in part)),close=part[-1]['close'],source_rows=count)
   cache[(sym,step,cl)]=row;barrows.append(row)
dump('owner-closed-bars.csv',barrows)
eventdir=OLD/'owner-BTC_REGIME_REENTRY_BAND_05-events';parents=readcsv(eventdir/'split-parent-audit.csv');entry={x['episode_id']:x for x in readcsv(eventdir/'entry-sizing-audit.csv')}; fills=readcsv(eventdir/'native-fill-audit.csv');orders=readcsv(eventdir/'native-orders.csv')
cohort=[];zstates=[]
for n,p in enumerate(parents,1):
 i=int(p['decision_index']);ns=int(p['start_ns']);e=entry[p['episode_id']];wave=completed_wave_levels(bars,features,i,cand,int(p['side']));ref=json.loads(e['reference_target_lots']);zeros=[k for k,v in enumerate(wave or []) if v==0];omitted=json.loads(e['omitted_zero_levels']);q=float(p['filled']);end=int(parents[n]['start_ns']) if n<len(parents) else 1788220800000000000
 actualfills=[x for x in fills if ns<=int(x['fill_ns'])<end and x['action']=='BTC_ENTRY'];fee=sum(Decimal(x['commission']) for x in actualfills);a=Decimal(p['planref_v1_actual_blended_vwap']);p0=Decimal(p['planref_v1_p0']);c=fee/Decimal(p['filled']);s=int(p['side']);be=(a+c)/Decimal('.99945') if s==1 else (a-c)/Decimal('1.00055');g=(max(p0,be) if s==1 else min(p0,be));g=(g/Decimal('.1')).to_integral_value(rounding=ROUND_CEILING if s==1 else ROUND_FLOOR)*Decimal('.1')
 ordinary=min([int(x['fill_ns']) for x in fills if ns<=int(x['fill_ns'])<end and x['action']=='BTC_REDUCE'] or [end]);completion=max([int(x['ts_last']) for x in orders if ns<=int(x['ts_init'])<end and x['instrument_id'].startswith('BTC') and x['is_reduce_only']=='False'] or [ns])
 row=dict(parent=n,episode_id=p['episode_id'],start_ns=ns,start_utc=utc(ns),side=s,branch=e['branch'],actual_wave_levels=json.dumps(wave),omitted_zero_levels=json.dumps(omitted),suppressed_zero_levels=json.dumps(zeros if e['branch']=='MARKETABLE_FULL_ENTRY_FALLBACK' else []),reference_target_lots=e['reference_target_lots'],P0=str(p0),actual_VWAP=str(a),actual_entry_fees=str(fee),actual_entry_qty=q,beta=p['planref_v1_beta'],native_parent_terminal_ns=completion,first_ordinary_reduce_ns=ordinary,G=str(g),eligible_zero_lots=sum(int(ref[str(k)]) for k in zeros if k not in omitted),arm_ns='',trigger_ns='',sol_increase_state='RECONSTRUCTED_NATIVE_ORDER_INTERVALS_NO_CACHE_SNAPSHOT')
 cohort.append(row);zstates.append(dict(row=row,end=end,ordinary=ordinary,completion=completion,g=float(g),armed=False,triggered=False))
dump('owner-btc-parent-precheck.csv',cohort)
waits=readcsv(OLD/'owner-B-skip-delay.csv');print('wait schema',list(waits[0]));
# Saved native settled receipts are monetary authority; mark OHLC lows/highs are not a simultaneous alternative equity.
peak=Decimal('10000');srows=[];zrows=[];seen_s=set();positions_by_hour={};first50=None
trace=J/'BTC_REGIME_REENTRY_BAND_05/result/minute-native-settled-receipts.csv.gz'
with gzip.open(trace,'rt') as f:
 for r in csv.DictReader(f):
  source=int(r['source_quote_ns']);receipt=int(r['receipt_ns']);equity=Decimal(r['paired_close_equity']);peak=max(peak,equity);dd=1-equity/peak
  if first50 is None and dd>=Decimal('.5'):first50=receipt
  positions=json.loads(r['native_positions_and_mark_ohlc_json']);pp={('BTC' if p['instrument_id'].startswith('BTC') else 'SOL'):p for p in positions};btc=pp.get('BTC');sol=pp.get('SOL')
  if source%H1==0 and btc and sol:
   parent=next((p for p in reversed(cohort) if int(p['start_ns'])<=source),None);beta=float(parent['beta']) if parent else None;bs=1 if btc['side']=='2' else -1;ss=1 if sol['side']=='2' else -1;bm=float(btc['mark_ohlc']['close']);sm=float(sol['mark_ohlc']['close']);hour=cache.get(('SOLUSDT',H1,source));adverse=-ss*(float(hour['close'])/float(sol['avg_px_open'])-1) if hour else 0
   if beta and .2<beta<4 and bs==-ss and beta*float(sol['quantity'])*sm>float(btc['quantity'])*bm and dd>=Decimal('.4') and adverse>=.02:
    key=sol['avg_px_open'] # diagnostic state identity; full runtime cycle identity must not use mutable VWAP
    srows.append(dict(source_ns=source,receipt_ns=receipt,utc=utc(receipt),parent=parent['parent'],beta=beta,btc_qty=btc['quantity'],sol_qty=sol['quantity'],sol_VWAP=sol['avg_px_open'],h1_close=hour['close'],adverse=adverse,global_dd=str(dd),frozen_cut_qty=str((Decimal(sol['quantity'])/2//Decimal('.1'))*Decimal('.1'))))
  for z in zstates:
   p=z['row'];ns=int(p['start_ns']);side=int(p['side'])
   if not (ns<=source<min(z['end'],z['ordinary'])) or p['branch']!='MARKETABLE_FULL_ENTRY_FALLBACK' or not p['eligible_zero_lots']:continue
   busy=any(x['instrument_id'].startswith('SOL') and x['is_reduce_only']=='False' and int(x['ts_init'])<=receipt<int(x['ts_last']) for x in orders)
   eligible=btc is not None and sol is None and not busy and receipt>z['completion']
   if not eligible:continue
   h4=cache.get(('BTCUSDT',H4,source))
   if not z['armed'] and h4 and source>z['completion'] and side*(float(h4['close'])-z['g'])>=.1-1e-9:
    z['armed']=True;z['arm_receipt']=receipt;p['arm_ns']=receipt;zrows.append(dict(parent=p['parent'],event='ARM',source_ns=source,receipt_ns=receipt,G=p['G'],close=h4['close']))
   # executable quote stream uses 1m execution close, not native mark close; trigger filled in a second bounded causal vector lookup below.
   if z['armed'] and not z['triggered'] and receipt>z['arm_receipt']:
    pass
# Trigger quotes: pinned execution minute close delivered at open+60s. Require later than delivered arm and before ordinary reduction.
bm=table('bybit-BTCUSDT-execution-1m.parquet')
for z in zstates:
 if not z['armed']:continue
 for x in bm:
  ns=(x['open_time_ms']+60000)*1000000
  if z['arm_receipt']<ns<min(z['end'],z['ordinary']) and int(z['row']['side'])*(float(x['close'])-z['g'])<=0:
   z['row']['trigger_ns']=ns;zrows.append(dict(parent=z['row']['parent'],event='RETURN_QUOTE_REACHABILITY_ONLY',source_ns=ns,receipt_ns=ns,G=z['row']['G'],close=x['close']));break
dump('owner-btc-parent-precheck.csv',cohort);dump('owner-zero-guard-precheck.csv',zrows);dump('owner-sol-risk-precheck.csv',srows)
summary=dict(source='25a085f596292df58e51188dd91e996adbe5724c',kind='SAVED_B_PATH_REACHABILITY_NOT_NATIVE_POLICY_PNL',parents=len(cohort),full_branches=sum(p['branch']=='MARKETABLE_FULL_ENTRY_FALLBACK' for p in cohort),closed_bar_rows=len(barrows),first_dd50_receipt_ns=first50,S_first_trigger_receipt_ns=srows[0]['receipt_ns'] if srows else None,S_before_first_dd50=bool(srows and srows[0]['receipt_ns']<first50),B50=cohort[49],inputs=inputs,UNKNOWN=['Exact historical queued/inflight/unknown_ACK snapshots not exported','saved path reachability does not guarantee future candidate admission/fill','zero return scan requires eligibility revalidation at trigger in runtime'])
(OUT/'owner-precheck.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='inputs'},indent=2))
