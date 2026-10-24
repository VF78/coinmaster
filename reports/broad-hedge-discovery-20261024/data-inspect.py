"""Feature/clock/coverage inspection only. No prices-to-performance labels."""
from pathlib import Path
import csv,json,hashlib,collections
from datetime import datetime,timezone
from decimal import Decimal as Q
import numpy as np
import pyarrow.parquet as pq
R=Path(__file__).resolve().parents[2]; O=Path(__file__).resolve().parent
D=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/inputs/data/normalized')
S=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/market-redesign-20261024/source-ec2a958')
M=60000000000; H=60*M; DAY=24*H
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def iso(ns):return datetime.fromtimestamp(int(ns)/1e9,timezone.utc).isoformat()
inputs={};coverage={};daily={};minute={}
for sym in ['BTCUSDT','SOLUSDT']:
 for kind in ['daily','execution-1m','mark-1m','funding']:
  p=D/f'bybit-{sym}-{kind}.parquet';inputs[str(p)]=sha(p);t=pq.read_table(p);d=t.to_pydict();col='funding_time_ms' if kind=='funding' else 'open_time_ms';z=np.array(d[col],np.int64);delta=np.diff(z)
  coverage[f'{sym}_{kind}']={'path':str(p),'schema':str(t.schema),'rows':len(z),'first_ms':int(z[0]),'last_ms':int(z[-1]),'first_utc':iso(z[0]*1000000),'last_utc':iso(z[-1]*1000000),'gaps_ms':{str(k):int(v) for k,v in zip(*np.unique(delta,return_counts=True))}}
  if kind=='daily':daily[sym]=d;assert np.all(delta==86400000)
  elif kind=='execution-1m':minute[sym]=d;assert np.all(delta==60000)
  elif kind=='mark-1m':assert np.all(delta==60000)
equivalence={}
for sym in daily:
 d=daily[sym];m=minute[sym];lookup={int(t):i for i,t in enumerate(d['open_time_ms'])};counts=collections.Counter();maxdiff={k:Q(0) for k in ['open','high','low','close']};examples=[]
 for start in range(0,len(m['open_time_ms']),1440):
  op=int(m['open_time_ms'][start]);idx=lookup[op];part=slice(start,start+1440);assert len(m['open_time_ms'][part])==1440
  agg={'open':Q(str(m['open'][start])),'high':max(Q(str(v)) for v in m['high'][part]),'low':min(Q(str(v)) for v in m['low'][part]),'close':Q(str(m['close'][start+1439]))}
  for k,v in agg.items():
   diff=abs(v-Q(str(d[k][idx])));maxdiff[k]=max(maxdiff[k],diff);counts[k+'_different']+=int(diff!=0)
   if diff and len(examples)<3:examples.append({'open_ms':op,'field':k,'daily':d[k][idx],'minute_aggregate':str(v)})
 equivalence[sym]={'comparison':'Exact Decimal of source lexical values','paired_days':len(m['open_time_ms'])//1440,'differences':dict(counts),'max_abs_difference':{k:str(v) for k,v in maxdiff.items()},'first_examples':examples}
 # covariance family: 30 simple D1 returns strictly before decision; lag one whole D1.
 z=np.array(d['open_time_ms'],np.int64)*1000000+DAY
 coverage[sym+'_D1cov30']={'first_possible_decision_ns':int(z[31]),'first_possible_decision_utc':iso(z[31]),'rule':'At decision t choose last daily close c<=t-DAY; need 30 returns ending c and their 31 closes. No H1 substitution.'}
led=R/'reports/early-capital-hedge-20261024/screen-ledger.json';inputs[str(led)]=sha(led);x=json.loads(led.read_text());fp=Path(next(p for p in x['input_sha256'] if p.endswith('-fills.csv')));inputs[str(fp)]=sha(fp)
fills=list(csv.DictReader(fp.open()));times=[int(datetime.fromisoformat(f['ts_last']).timestamp()*1e9) for f in fills]
barstart=int(minute['BTCUSDT']['open_time_ms'][0])*1000000;barend=int(minute['BTCUSDT']['open_time_ms'][-1])*1000000+M
clock={'fill_count':len(fills),'fills_modulo_minute_ns':dict(collections.Counter(str(t%M) for t in times)),'fills_without_completed_raw_mark':sum(not(barstart+M<=t<=barend) for t in times),'fills_at_terminal_raw_close':sum(t==barend for t in times),'first_fill_utc':iso(min(times)),'last_fill_utc':iso(max(times))}
for rel in ['runtime/coinmaster/research/native_baseline.py','runtime/coinmaster/research/minute_risk.py','runtime/coinmaster/research/native_fixture.py']:
 p=S/rel;inputs[str(p)]=sha(p)
for rel in ['reports/market-redesign-20261024/full-freeze.json','reports/market-redesign-20261024/native-analysis-attribution-extract.py','reports/early-capital-hedge-20261024/feature-contract-check.py']:
 p=R/rel;inputs[str(p)]=sha(p)
out={'scope':'DATA_CLOCK_FEATURE_ONLY_NO_PERFORMANCE_OUTCOMES','coverage':coverage,'daily_vs_execution_minute_aggregation':equivalence,'native_fill_clock':clock,'input_sha256':inputs,'script_sha256':sha(Path(__file__)),'engine_runs':0,'new_performance_labels':0}
(O/'data-inspection.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'clock':clock,'D1_equivalence':equivalence,'D1coverage':{k:v for k,v in coverage.items() if 'D1cov30' in k}},indent=2))
