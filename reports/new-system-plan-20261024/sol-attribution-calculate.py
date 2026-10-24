#!/usr/bin/env python3
"""One observed native-fill/mark arithmetic attribution, never an execution engine."""
import csv,json,hashlib,subprocess,bisect,collections,re
from pathlib import Path
from decimal import Decimal as D,getcontext
from datetime import datetime,timezone
import pyarrow.parquet as pq
getcontext().prec=60
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent
BASE=ROOT/'reports/b-50-90-next-20261023'; RECEIPT=BASE/'owner-E4-receipt.json'
R=json.loads(RECEIPT.read_text()); RAW=Path(R['raw_artifact']); assert hashlib.sha256(RAW.read_bytes()).hexdigest()==R['raw_sha256']
raw=json.loads(RAW.read_text()); assert raw['config_hash']==R['config_sha256']; assert raw['terminal_total']==R['total']
INPUTS=[RECEIPT,RAW,OUT/'sol-attribution-protocol.json']
def read(p):
 with p.open(newline='') as f:return list(csv.DictReader(f))
for k in ['fills','orders','native-fill-audit.csv','native-order-events.csv','split-parent-audit.csv']:
 e=R['exports'][k];p=Path(e['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==e['sha256'];INPUTS.append(p)
fills=read(Path(R['exports']['fills']['path'])); audit=read(Path(R['exports']['native-fill-audit.csv']['path'])); orders=read(Path(R['exports']['orders']['path'])); events=read(Path(R['exports']['native-order-events.csv']['path'])); parents=read(Path(R['exports']['split-parent-audit.csv']['path']))
assert len(fills)==len(audit)==535
order_byid={r['client_order_id']:r for r in orders}; event_byid={r['client_order_id']:r for r in events}
def ns(s):return int(datetime.fromisoformat(s).timestamp())*10**9
def iso(t):return datetime.fromtimestamp(t/1e9,timezone.utc).isoformat()
def key(t,inst,qty,px):return int(t),inst,D(qty),D(px).quantize(D('.1') if inst.startswith('BTC') else D('.001'))
audit_bykey=collections.defaultdict(list)
for a in audit:audit_bykey[key(a['fill_ns'],a['instrument'],a['qty'],a['px'])].append(a)
bytime=collections.defaultdict(list)
for f in fills:
 oid=f['client_order_id'];o=order_byid[oid];e=event_byid[oid]
 assert D(f['filled_qty'])==D(o['filled_qty'])>0
 aa=audit_bykey[key(ns(f['ts_last']),f['instrument_id'],f['filled_qty'],f['avg_px'])]
 # Same-key duplicates must carry the same economic/action fields; no guessed side assignment.
 assert aa and len({(a['action'],a['reason'],a['commission'],a['submit_ns']) for a in aa})==1
 a=aa.pop(0);assert a['action']==e['action'] and a['submit_ns']==e['submit_ns'];assert D(a['commission'])==D(re.findall(r"([0-9.]+) USDT",f['commissions'])[0])
 bytime[int(a['fill_ns'])].append({'asset':'BTC' if f['instrument_id'].startswith('BTC') else 'SOL','q':D(a['qty'])*(1 if f['side']=='BUY' else -1),'px':D(a['px']),'fee':D(a['commission']),'oid':oid,'action':a['action']})
assert not any(audit_bykey.values())
# Pin and inspect beta definition + lifecycle source; no product imports.
rev=R['source_commit']; sources={}
for label,path in [('wave_domain','runtime/coinmaster/domain/wave_overlay.py'),('wave_strategy','runtime/coinmaster/strategy/wave_overlay.py')]:
 b=subprocess.check_output(['git','show',f'{rev}:{path}']);sources[path]=hashlib.sha256(b).hexdigest();assert sources[path]==raw['source_hashes'][label]
 domain=b.decode() if label=='wave_domain' else None
 if label=='wave_domain':assert 'log(bar.btc_close / bars[index - 1].btc_close)' in domain and 'mean_b' in domain and 'on_group_flat' in domain
assert raw['config']['candidate']['beta_days']==270
parent_ts=[int(p['start_ns']) for p in parents];assert parent_ts==sorted(parent_ts)
# Build actual SOL cycles from signed quantities; each file row is one audited actual fill.
cycles=[];q=D(0);cur=None;fill_cycle={};flips=0
for t,fs in sorted(bytime.items()):
 for f in fs:
  if f['asset']!='SOL':continue
  if not q:
   i=bisect.bisect_right(parent_ts,t)-1; p=parents[i] if i>=0 else None
   primary=D(p['planref_v1_beta']) if p and p['planref_v1_beta'] and int(p['management_reference_frozen_ns'])<t else None
   cur={'cycle':len(cycles)+1,'start_ns':t,'end_ns':None,'parent_index':i,'parent_episode_id':p['episode_id'] if p else 'UNKNOWN','beta270':primary,'beta720':None,'side':1 if f['q']>0 else -1,'fill_count':0,'fill_cash':D(0),'fees':D(0),'held':D(0),'factor270':D(0),'factor720':D(0),'exec':D(0),'unknown_primary_held':D(0),'unknown_secondary_held':D(0)};cycles.append(cur)
  old=q;q+=f['q'];assert not old or not q or (old>0)==(q>0),'SIGN_FLIP_REQUIRES_SEPARATE_REVIEW'
  cur['fill_count']+=1;cur['fill_cash']-=f['q']*f['px'];cur['fees']+=f['fee'];fill_cycle[f['oid']]=cur
  if not q:cur['end_ns']=t
assert q==0 and all(c['end_ns'] for c in cycles)
for c in cycles:
 i=c['parent_index']
 if i<0 or (i+1<len(parents) and c['end_ns']>=parent_ts[i+1]):c['beta270']=None;c['parent_episode_id']='UNKNOWN_CROSS_PARENT'
# Independent secondary lag720H1. Read only saved closed H1 prices, not outcomes.
barfile=BASE/'owner-closed-bars.csv';INPUTS.append(barfile);h=3600000000000
closed={s:{} for s in ['BTCUSDT','SOLUSDT']}
with barfile.open() as f:
 for r in csv.DictReader(f):
  if int(r['step_ns'])==h:
   assert r['available_ns']==r['close_ns'];closed[r['symbol']][int(r['close_ns'])]=D(r['close'])
ts=sorted(set(closed['BTCUSDT'])&set(closed['SOLUSDT']))
for c in cycles:
 j=bisect.bisect_left(ts,c['start_ns']);w=ts[max(0,j-721):j]
 if len(w)==721 and all(b-a==h for a,b in zip(w,w[1:])):
  rb=[closed['BTCUSDT'][b]/closed['BTCUSDT'][a]-1 for a,b in zip(w,w[1:])];rs=[closed['SOLUSDT'][b]/closed['SOLUSDT'][a]-1 for a,b in zip(w,w[1:])]
  mb=sum(rb)/720;ms=sum(rs)/720;var=sum((x-mb)**2 for x in rb)
  if var:c['beta720']=sum((x-mb)*(y-ms) for x,y in zip(rb,rs))/var;c['beta720_last_end_ns']=w[-1]
# Stream paired raw mark minute closes. Inventory changes use actual fills only.
markbase=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/data/normalized')
markpaths=[markbase/f'bybit-{s}USDT-mark-1m.parquet' for s in ['BTC','SOL']];INPUTS+=markpaths
for p in markpaths:assert pq.ParquetFile(p).metadata.num_rows==1051200
def rows(p):
 for batch in pq.ParquetFile(p).iter_batches(batch_size=16384,columns=['open_time_ms','close']):
  yield from batch.to_pylist()
Y2=ns('2025-09-01T00:00:00+00:00');agg=collections.defaultdict(lambda:collections.defaultdict(lambda:D(0)));qB=qS=D(0);active=None;prevB=prevS=None;consumed=0;minutes=0;nativeflatminutes=0
# Aggregate keys calendar year and BTC-state. Exact state applies to held interval only.
def put(year,state,field,value):
 for k in [('all','ALL'),(year,'ALL'),('all',state),(year,state)]:agg[k][field]+=value
for br,sr in zip(rows(markpaths[0]),rows(markpaths[1]),strict=True):
 assert br['open_time_ms']==sr['open_time_ms'];t=(int(br['open_time_ms'])+60000)*1000000;pb=D(br['close']);ps=D(sr['close']);year='first_year' if t<=Y2 else 'second_year'
 state='BTC_FLAT' if not qB else ('OPPOSITE' if qB*qS<0 else 'SAME_SIDE')
 if qS:
  assert active is not None and prevB and prevS
  held=qS*(ps-prevS);active['held']+=held;put(year,state,'held',held);put(year,state,'SOL_active_minutes',D(1));put(year,state,'SOL_abs_notional_minute',abs(qS)*prevS)
  for beta_name,field in [('beta270','factor270'),('beta720','factor720')]:
   beta=active[beta_name]
   if beta is None:active['unknown_primary_held' if beta_name=='beta270' else 'unknown_secondary_held']+=held;put(year,state,field+'_unknown_held',held)
   else:
    factor=qS*prevS*beta*(pb/prevB-1);active[field]+=factor;put(year,state,field,factor)
  beta=active['beta270']
  if beta is not None and beta>0:
   for cap,label in [(D(1),'fullfactor100'),(D('.5'),'halffactor50')]:
    allowed=cap*abs(qB)*prevB/beta if qB*qS<0 else D(0)
    excess=max(D(0),1-allowed/(abs(qS)*prevS));put(year,state,label+'_excess_held_PNL',held*excess)
    if excess:put(year,state,label+'_excess_minutes',D(1))
 fs=bytime.get(t,[]);btc_tie=any(f['asset']=='BTC' for f in fs)
 for f in fs:
  consumed+=1
  if f['asset']=='SOL':
   c=fill_cycle[f['oid']];execution=f['q']*(ps-f['px']);c['exec']+=execution
   fstate='TIMESTAMP_TIE_BTC_FILL' if btc_tie else ('BTC_FLAT' if not qB else ('OPPOSITE' if qB*c['side']<0 else 'SAME_SIDE'))
   put(year,fstate,'exec',execution);put(year,fstate,'fees',f['fee']);qS+=f['q'];active=c if qS else None
  else:qB+=f['q']
 prevB,prevS=pb,ps;minutes+=1
assert consumed==len(fills) and qB==qS==0
for c in cycles:
 assert abs(c['held']+c['exec']-c['fill_cash'])<D('1e-45')
 c['fill_net']=c['fill_cash']-c['fees'];c['residual270']=c['held']-c['factor270'] if c['beta270'] is not None else None;c['residual720']=c['held']-c['factor720'] if c['beta720'] is not None else None
 if c['beta270'] is not None:assert abs(c['factor270']+c['residual270']+c['exec']-c['fees']-c['fill_net'])<D('1e-45')
 c['entry_cohort']='first_year' if c['start_ns']<Y2 else 'second_year';c['start_utc']=iso(c['start_ns']);c['end_utc']=iso(c['end_ns'])
summary=[]
for (year,state),v in sorted(agg.items()):
 row={'year_calendar':year,'BTC_state':state,**v};row['residual270']=v['held']-v['factor270'] if not v['factor270_unknown_held'] else 'UNKNOWN';row['residual720']=v['held']-v['factor720'] if not v['factor720_unknown_held'] else 'UNKNOWN';row['observed_mark_and_exec_net']=v['held']+v['exec']-v['fees'];summary.append(row)
cohorts=[]
for year in ['all','first_year','second_year']:
 cs=[c for c in cycles if year=='all' or c['entry_cohort']==year]
 cohorts.append({'entry_cohort':year,'cycles':len(cs),**{k:sum((c[k] for c in cs),D(0)) for k in ['fill_cash','fees','fill_net','held','factor270','factor720','exec']}})
def writecsv(name,records):
 keys=list(dict.fromkeys(k for r in records for k in r))
 with (OUT/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(records)
writecsv('sol-attribution-cycles.csv',cycles);writecsv('sol-attribution-summary.csv',summary);writecsv('sol-attribution-entry-cohorts.csv',cohorts)
verification={'status':'PASS_OBSERVED_CASH_TELESCOPE_NOT_COUNTERFACTUAL','native_fill_rows':len(fills),'SOL_actual_fill_rows':sum(f['asset']=='SOL' for fs in bytime.values() for f in fs),'SOL_cycles':len(cycles),'minute_marks_paired':minutes,'consumed_actual_fill_rows':consumed,'primary_beta_known_cycles':sum(c['beta270'] is not None for c in cycles),'secondary_beta_known_cycles':sum(c['beta720'] is not None for c in cycles),'maximum_cycle_cash_telescope_residual':str(max(abs(c['held']+c['exec']-c['fill_cash']) for c in cycles)),'terminal_inventory':{'BTC':str(qB),'SOL':str(qS)},'sources_sha256':sources,'input_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in INPUTS},'funding':'UNKNOWN_SIGNED_OLD_PERASSET_COMPONENT_NO_ALLOCATION','scope':{'engine_attempts':0,'training':0,'simulator_reruns':0,'product_changes':0,'runtime_writes':0},'limitations':['Factor uses causal frozen parent270D logreturn beta with simple minute returns: descriptive approximation, not orthogonal causal alpha.','Parent linkage unique timestamp interval + native both-flat lifecycle + cycle-before-next-parent checked. No durable order-to-episode field in fill export.','Raw observed minute marks, not native instrument-rounding marks; executionbasis includes rawmark/fill basis. Algebraic cash identity exact within Decimal60 residual.','BTCstate for markinterval uses actual pre-current-fill inventory. Same-timestamp BTC/SOL executionbasis and fees assigned explicit tie UNKNOWN. Intratimestamp mark/callback path not inferred.','Cap excess PNL is proportional observed held mark PNL only, excludes execution/fees/funding; not PNL of a capped hedge or obtainable saved cash.','Calendar buckets use interval ending at year boundary as prior year; execution at boundary would require separate event qualification.','Old signed perasset funding UNKNOWN, residual is not executable alpha, counterfactual BTC compounding/cashdelta/TOTAL unidentifiable.']}
(OUT/'sol-attribution-verification.json').write_text(json.dumps(verification,indent=2,default=str)+'\n')
(OUT/'sol-attribution-result.json').write_text(json.dumps({'cohorts':cohorts,'calendar_and_state':summary,'early_cycles':cycles[:8],'verdict':'DESCRIPTIVE_ATTRIBUTION_ONLY_NO_NEW_STRATEGY_OR_GO'},indent=2,default=str)+'\n')
print(json.dumps({'verification':{k:v for k,v in verification.items() if k not in ['input_sha256','sources_sha256','limitations']},'cohorts':cohorts,'states':[r for r in summary if r['year_calendar']=='all']},default=str,indent=2))
