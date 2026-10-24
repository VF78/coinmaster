"""Frozen three-scenario Decimal80 arithmetic; no market/strategy simulation."""
import csv, hashlib, json
from decimal import Decimal, getcontext
from pathlib import Path
from datetime import datetime, timezone
getcontext().prec=80
D=Decimal
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
FILES={'protocol':OUT/'GROWTH_ENVELOPE_PROTOCOL.md','cycles':ROOT/'reports/market-redesign-20261024/native-analysis-attribution-R3-cycles.csv','parents':ROOT/'reports/new-system-plan-20261024/btc-participation-parents.csv'}
rows=list(csv.DictReader(FILES['cycles'].open()))
parents=[x for x in csv.DictReader(FILES['parents'].open()) if x['variant']=='R3']
assert len(rows)==len(parents)==83
seed=D(10000); saved=D('120718.40416503'); tol=D('.000001')
A=seed; previous_end=None; checks=[]; data=[]
for i,(c,p) in enumerate(zip(rows,parents),1):
 assert c['variant']==p['variant']=='R3' and int(c['cycle'])==int(p['cycle'])==i
 assert c['start_ns']==p['start_ns'] and c['native_last_fill_ns']==p['last_fill_ns']
 assert int(c['start_ns'])>int(p['decision_ns'])
 assert previous_end is None or previous_end<int(p['decision_ns'])<int(c['start_ns'])
 n=D(c['net_including_funding']); f=D(c['signed_funding'])
 assert n==D(c['price_fill_net_ex_funding'])+f
 assert D(p['actual_fill_net_ex_funding'])==D(c['price_fill_net_ex_funding']) and D(p['signed_BTC_funding'])==f
 assert D(c['price_fill_net_ex_funding'])==D(c['price_PNL_actual_flat_cashflows'])-D(c['native_fees'])
 cash_res=A-D(p['own_settled_equity_at_decision']); assert abs(cash_res)<=tol and A>0
 r=n/A; assert r>-1
 checks.append({'cycle':i,'A':str(A),'own_pre_entry_flatcash':p['own_settled_equity_at_decision'],'money_residual':str(cash_res),'start_utc':c['start_utc'],'last_fill_ns':c['native_last_fill_ns'],'return':str(r)})
 data.append((c,n,A,r))
 A+=n; previous_end=int(c['native_last_fill_ns'])
assert abs(A-saved)<=tol
paths={k:seed for k in ('observed','uniformhalf','oraclelosshalving')}; peaks=paths.copy(); dds={k:D(0) for k in paths}; snapshots={k:[] for k in paths}
cutoffs={'early_starts_before_2025-01-15':'2025-01-15T00:00:00+00:00','first_year_starts_before_2025-09-01':'2025-09-01T00:00:00+00:00'}
cohorts={}
for c,n,a,r in data:
 factors={'observed':1+r,'uniformhalf':1+r/D(2),'oraclelosshalving':1+(r/D(2) if r<0 else r)}
 for k in paths:
  paths[k]*=factors[k]; peaks[k]=max(peaks[k],paths[k]); dds[k]=max(dds[k],1-paths[k]/peaks[k]); snapshots[k].append(paths[k])
for name,t in cutoffs.items():
 ids=[j for j,(c,n,a,r) in enumerate(data) if c['start_utc']<t]
 endids=[j for j,(c,n,a,r) in enumerate(data) if datetime.fromtimestamp(int(c['native_last_fill_ns'])/1e9,timezone.utc).isoformat()<t]
 cohorts[name]={'count':len(ids),'last_cycle_start':data[ids[-1]][0]['start_utc'],'last_cycle_end_ns':data[ids[-1]][0]['native_last_fill_ns'],'values':{k:str(snapshots[k][ids[-1]]) for k in paths},'strict_completed_before_boundary_count':len(endids),'strict_completed_boundary_values':{k:str(snapshots[k][endids[-1]]) for k in paths},'boundary_crossing_cycles':[j+1 for j in ids if j not in endids]}
floors={'70':D('4256975.067212381'),'90':D('5470396.514987347')}; s0net=D('6077107.23887483')-seed
summary={k:{'algebraic_total_equivalent':str(v),'S0_net_retention_pct':str((v-seed)/s0net*100),'cycle_boundary_DD_pct':str(dds[k]*100),'gaps':{level:{'required_multiplier':str(floor/v),'log_growth_gap':str((floor/v).ln()),'absolute_shortfall':str(floor-v)} for level,floor in floors.items()}} for k,v in paths.items()}
result={'status':'ARITHMETIC_SCENARIOS_ONLY','decimal_precision':80,'inputs':{k:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for k,p in FILES.items()},'checks':{'cycle_count':83,'chronology':'nonoverlapping previous flat fill < next decision < next first fill','net_cash':str(A),'saved_native_TOTAL':str(saved),'total_residual':str(A-saved),'max_abs_ownq0_residual':str(max(abs(D(x['money_residual'])) for x in checks)),'report_comparison_tolerance':str(tol),'funding_complete':True,'funding_sum':str(sum((x[1] and D(x[0]['signed_funding']) or D(x[0]['signed_funding']) for x in data),D(0))),'observed_product_minus_saved':str(paths['observed']-saved)},'negative_cycles':sum(r<0 for c,n,a,r in data),'nonnegative_cycles':sum(r>=0 for c,n,a,r in data),'scenarios':summary,'cohorts':cohorts,'cycle_checks':checks}
(OUT/'growth-envelope-results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('checks','negative_cycles','nonnegative_cycles','scenarios','cohorts')},indent=2))
