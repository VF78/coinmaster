from pathlib import Path
from decimal import Decimal as D, localcontext
import csv,json,hashlib,datetime
import pyarrow.parquet as pq
BASE=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
freeze=BASE/'reports/market-redesign-20261024/full-freeze.json'
manifest=json.loads(freeze.read_text())
def findpin(node):
 if isinstance(node,dict):
  for k,v in node.items():
   if k=='normalized/bybit-SOLUSDT-execution-1m.parquet':return v
   r=findpin(v)
   if r:return r
 if isinstance(node,list):
  for v in node:
   r=findpin(v)
   if r:return r
pin=findpin(manifest);assert pin
source=BASE/'reports/broad-hedge-discovery-20261024/implementation-signal-feed-build.py'
assert sha(source)=='47704f6ca1a998ef464ba7b0237d5e32d2330f92702d3c05d00df426a0b34cf3'
M=60000;H4=240*M;start=1725148800000;end=start+28*60*M
p=Path(pin['path'])
tab=pq.read_table(p,columns=['open_time_ms','open','high','low','close'],filters=[('open_time_ms','>=',start),('open_time_ms','<',end)])
d=tab.to_pydict();times=[int(t) for t in d['open_time_ms']];assert times==list(range(start,end,M)) and len(times)==1680
for i in range(len(times)):
 o,h,l,c=(D(str(d[k][i])) for k in ['open','high','low','close']);assert all(x.is_finite() and x>0 for x in [o,h,l,c]) and l<=min(o,c)<=max(o,c)<=h
warm=OUT/'bybit-sol-h4-qualified.csv'
with warm.open() as f:bars=list(csv.DictReader(f))
assert len(bars)==102 and int(bars[-1]['closed_at_ms'])==start
for i in range(0,len(times),240):
 bars.append({'start_ms':times[i],'closed_at_ms':times[i]+H4,'open':str(d['open'][i]),'high':str(max(D(str(v)) for v in d['high'][i:i+240])),'low':str(min(D(str(v)) for v in d['low'][i:i+240])),'close':str(d['close'][i+239])})
assert len(bars)==109 and [int(b['start_ms']) for b in bars]==list(range(int(bars[0]['start_ms']),end,H4))
TR=[];ATR=None;outrows=[]
with localcontext() as ctx:
 ctx.prec=50
 for k,b in enumerate(bars):
  h=D(b['high']);l=D(b['low']);prev=D(bars[k-1]['close']) if k else None
  tr=h-l if prev is None else max(h-l,abs(h-prev),abs(l-prev));TR.append(tr)
  if k==13:ATR=sum(TR,D(0))/D(14)
  elif k>13:ATR=(13*ATR+tr)/14
  outrows.append({'start_ms':int(b['start_ms']),'closed_at_ms':int(b['closed_at_ms']),'open':b['open'],'high':str(h),'low':str(l),'close':b['close'],'true_range':str(tr),'atr14':str(ATR) if ATR is not None else ''})
csvpath=OUT/'strict-warmup-stitch-atr.csv'
with csvpath.open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(outrows[0]));w.writeheader();w.writerows(outrows)
iso=lambda t:datetime.datetime.fromtimestamp(t/1000,datetime.timezone.utc).isoformat()
def eligible(cut,inclusive):
 r=[r for r in outrows if r['closed_at_ms']<=cut] if inclusive else [r for r in outrows if r['closed_at_ms']<cut]
 b=r[-1];return {'cut_utc':iso(cut),'operator':'<=' if inclusive else '<','last_bar_end_utc':iso(b['closed_at_ms']),'atr14':b['atr14'],'nominal_bar_close_eligible':True}
receipt={'status':'RESEARCH_DATA_ONLY_NOT_ADMITTED_FOR_NATIVE','checks':'PASS_1680_M1_7_H4_AND_109_H4_STITCH','new_public_requests':0,'aggregate_endpoint_attempts':2,'aggregate_downloaded_responses':1,'engines_created':0,'economic_ROI_simulations':0,'old_input_writes':0,'m1_columns':['open_time_ms','open','high','low','close'],'m1_filter':{'gte_ms':start,'lt_ms':end},'m1_rows':1680,'new_h4_rows':7,'combined_h4_rows':109,'duplicates':0,'gaps':0,'ohlc_checks':'PASS','existing_m1_pin_from_full_freeze':pin,'full_freeze_path':str(freeze),'full_freeze_sha256':sha(freeze),'m1_full_hash_recomputed':False,'m1_pin_limitation':'Existing immutable full-freeze SHA reference used; no full-file rescan performed in this step','warmup_h4_sha256':sha(warm),'formula_source_sha256':sha(source),'arithmetic':'Decimal50 firstTR high-low, mean first14TR at k13, then (13*ATR+TR)/14','benchmark_sep1_strict':eligible(start,False),'benchmark_sep1_inclusive':eligible(start,True),'first_post00_decision_sep1_04_strict':eligible(start+H4,False),'missing_sep2_04_strict':eligible(end,False),'missing_sep2_04_inclusive':eligible(end,True),'artifacts':{'code_path':str(Path(__file__).resolve()),'code_sha256':sha(Path(__file__).resolve()),'csv_path':str(csvpath),'csv_sha256':sha(csvpath)},'limitations':['Nominal close/end is not proven historical publication/availability time; publication latency/revisions UNKNOWN','H1 warmup and M1 continuation are trade-price series; no overlapping interval to prove vendor equality across resolutions','Aug15 seed is specified finite warmup, not proof of converged infinite-history ATR','No strategy-signal regeneration, native input modification, native admission, benefit/PnL or OOS claim']}
(OUT/'strict-warmup-stitch-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
