"""Independent exact Fraction path/money/DD plus float loglift validation."""
from pathlib import Path
from fractions import Fraction as Q
from decimal import Decimal as D,getcontext
from datetime import datetime,timezone
import csv,json,hashlib,collections,math
getcontext().prec=90
O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:list(csv.DictReader(Path(p).open()))
l=json.loads((O/'capital-alignment-ledger.json').read_text());assert l['cache_pass_completed']==1 and not l.get('verification_started')
for x in l['input_sha256'].values():assert sha(x['path'])==x['sha256']
assert sha(O/'capital-alignment-results.json')==l['results_sha256'];l['verification_started']=1;l['verification_start_utc']=datetime.now(timezone.utc).isoformat();(O/'capital-alignment-ledger.json').write_text(json.dumps(l,indent=2)+'\n')
growth=json.load(open(l['input_sha256']['growth']['path']));cycles=growth['cycle_checks'];cache=read(l['input_sha256']['stageI_cache']['path'])+read(l['input_sha256']['stageII_cache']['path']);saved=read(O/'capital-alignment-paths.csv');savedf=read(O/'capital-alignment-factors.csv');savedc=read(O/'capital-alignment-cohorts.csv');savedb=read(O/'capital-alignment-boundaries.csv');summary=read(O/'capital-alignment-summary.csv');checks=collections.Counter();computed={};logs={};deltas={};cacheby=collections.defaultdict(list)
for r in cache:cacheby[r['rule'],r['horizon_h'],r['slip_bp'],r['funding_boundary']].append(r)
def qdec(q):return D(q.numerator)/D(q.denominator)
def check(q,s):assert abs(qdec(q)-D(s))<max(D('1e-64'),abs(D(s))*D('1e-71')),(qdec(q),s)
def iso(s):return datetime.fromisoformat(s)
year=iso('2025-09-01T00:00:00+00:00');early=iso('2025-01-15T00:00:00+00:00');cohorts={'year1':[int(c['cycle']) for c in cycles if iso(c['start_utc'])<year],'year2':[int(c['cycle']) for c in cycles if iso(c['start_utc'])>=year],'early':[int(c['cycle']) for c in cycles if iso(c['start_utc'])<early]}
for path in saved:
 key=tuple(path[k] for k in ['rule','horizon_h','slip_bp','funding_boundary','action']);z=cacheby[key[:4]];by={int(r['cycle']):r for r in z};value=Q(10000);peak=value;DD=Q(0);values={};log={};da={};bad=[]
 for c in cycles:
  i=int(c['cycle']);delta=Q(by[i]['net_'+key[4]]) if i in by else Q(0);da[i]=delta/Q(c['A']);factor=1+Q(c['return'])+da[i]
  if factor<=0:bad.append(i);values[i]=None;log[i]=None
  else:
   if not bad:value*=factor;peak=max(peak,value);DD=max(DD,(peak-value)/peak);values[i]=value
   else:values[i]=None
   # Independent real-valued check, no Decimal ln reuse.
   log[i]=math.log(float(factor))-math.log1p(float(c['return'])) if delta else 0.
  checks['exact_cycle_factors']+=1
 if bad:assert path['status']=='INFEASIBLE_FACTOR'
 else:
  assert path['status']=='POST_RESULT_SCALAR_ONLY';check(value,path['terminal_scalar_equivalent']);check(DD*100,path['cycle_boundary_DD_pct']);check((value-10000)/(Q('6077107.23887483')-10000)*100,path['net_profit_retention_pct_vs_legacyS0'])
  check(Q('4256975.067212381')-value,path['gap70_USDT']);check(Q('5470396.514987347')-value,path['gap90_USDT']);checks['Fraction_terminal_gap_retention_cycleDD_paths']+=1
 computed[key]=values;logs[key]=log;deltas[key]=da
for r in savedf:
 key=tuple(r[k] for k in ['rule','horizon_h','slip_bp','funding_boundary','action']);i=int(r['cycle']);v=computed[key][i]
 if v is None:assert not r['scalar_after_cycle']
 else:check(v,r['scalar_after_cycle'])
 check(deltas[key][i],r['delta_over_original_A']);checks['all_cycle_prefix_money']+=1
for r in savedc:
 key=tuple(r[k] for k in ['rule','horizon_h','slip_bp','funding_boundary','action']);ids=cohorts[r['cohort']];assert int(r['cycles'])==len(ids);z=cacheby[key[:4]];by={int(x['cycle']):x for x in z};selected=[i for i in ids if i in by];assert len(selected)==int(r['covered_action_cycles']);das=sum((deltas[key][i] for i in ids),Q(0));check(das,r['sum_delta_over_original_A']);check(das/len(ids),r['mean_delta_over_original_A_all_cycles']);check(sum((deltas[key][i] for i in selected),Q(0))/len(selected) if selected else Q(0),r['mean_delta_over_original_A_covered'])
 assert abs(sum(logs[key][i] for i in ids)-float(r['loglift_vs_original']))<1e-12
 if key[-1]=='H':
  tk=key[:-1]+('T',);assert abs(sum(logs[key][i]-logs[tk][i] for i in ids)-float(r['loglift_H_minus_T']))<1e-12
 checks['independent_cohort_money_loglifts']+=1
for r in savedb:
 key=tuple(r[k] for k in ['rule','horizon_h','slip_bp','funding_boundary','action']);boundary=int(r['boundary_ns']);terminal=r['boundary']=='benchmark_terminal_post_boundary';ids=[int(c['cycle']) for c in cycles if int(c['last_fill_ns'])<boundary or (terminal and int(c['last_fill_ns'])==boundary)];assert len(ids)==int(r['actual_completed_cycles']);value=computed[key][ids[-1]] if ids else Q(10000)
 if value is not None:check(value,r['scalar_equivalent_completed_cycles_only'])
 checks['strict_completed_boundary_values']+=1
# Independently reconstruct all-case positivity and worst-case rankings.
for s in summary:
 Hkeys=[key for key in computed if key[:2]==(s['rule'],s['horizon_h']) and key[-1]=='H'];totals=[computed[k][83] for k in Hkeys];worst=min(totals);check(worst,s['worst_H_terminal_equiv']);positive=all(sum(logs[k][i] for i in ids)>0 for k in Hkeys for ids in cohorts.values());paired=all(sum(logs[k][i]-logs[k[:-1]+('T',)][i] for i in ids)>0 for k in Hkeys for ids in cohorts.values());assert positive==(s['capital_scale_positive_H_all3x4']=='True') and paired==(s['paired_loglift_positive_HminusT_all3x4']=='True');checks['all_config_scale_and_paired_predicates']+=1
ranking=sorted(summary,key=lambda r:(D(r['worst_H_terminal_equiv']),D(r['worst_H_loglift_cohort'])),reverse=True);assert [r['rank_worst_terminal'] for r in ranking]==list(map(str,range(1,37)))
assert all(sha(x['path'])==x['sha256'] for x in l['input_sha256'].values())
v={'status':'PASS_POST_RESULT_CAPITAL_ALIGNMENT','checks':dict(checks),'method':'Independent exact Fraction all83-cycle products/prefixes/gaps/retentions/cycle-boundaryDD; independent float log comparisons/cohort grouping/ranking','source_cache_discovery_phase_scale_unchanged':True,'new_trade_outcomes':0,'new_configurations':0,'native_engine_runs':0,'verifier_sha256':sha(Path(__file__))};(O/'capital-alignment-verification.json').write_text(json.dumps(v,indent=2)+'\n');l.update(status='PASS_POST_RESULT_CAPITAL_ALIGNMENT',verification_completed=1,verification_sha256=sha(O/'capital-alignment-verification.json'));(O/'capital-alignment-ledger.json').write_text(json.dumps(l,indent=2)+'\n');print(json.dumps(v,indent=2))
