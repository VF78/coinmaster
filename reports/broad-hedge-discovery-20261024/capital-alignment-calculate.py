"""POST_RESULT all36 cached scalar paths. No new market/action outcomes."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from datetime import datetime,timezone
import csv,json,hashlib,collections
getcontext().prec=80
O=Path(__file__).resolve().parent;R=O.parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:list(csv.DictReader(Path(p).open()))
def ns(s):return int(datetime.fromisoformat(s).timestamp())*10**9
seed=D(10000);S0=D('6077107.23887483');floors={'70':D('4256975.067212381'),'90':D('5470396.514987347')};early=ns('2025-01-15T00:00:00+00:00');year=ns('2025-09-01T00:00:00+00:00');end=ns('2026-09-01T00:00:00+00:00')
paths={'protocol':O/'CAPITAL_ALIGNMENT_PROTOCOL.md','growth':R/'reports/early-capital-hedge-20261024/growth-envelope-results.json','stageI_cache':O/'discovery-stageI-episodes.csv','stageII_cache':O/'discovery-stageII-episodes.csv','stageI_receipt':O/'discovery-stageI-result.json','stageII_receipt':O/'discovery-stageII-result.json','combined':O/'discovery-combined-configurations.csv','phase_immutable':O/'phase-ledger.json','scale_immutable':O/'scale-admission-results.json','script':Path(__file__)}
inputs={k:{'path':str(p),'sha256':sha(p)} for k,p in paths.items()}
for stage in ['stageI','stageII']:
 receipt=json.loads(paths[stage+'_receipt'].read_text());assert receipt['output_sha256'][f'discovery-{stage}-episodes.csv']==inputs[stage+'_cache']['sha256']
assert not (O/'capital-alignment-ledger.json').exists(),'ONE_PASS_ONLY'
ledger={'status':'STARTED_POST_RESULT_SCALAR_ONLY','start_utc':datetime.now(timezone.utc).isoformat(),'cache_pass_started':1,'cache_pass_completed':0,'independent_verification_budget':1,'input_sha256':inputs,'new_trade_outcomes':0,'new_configurations':0,'native_engine_runs':0};(O/'capital-alignment-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
cycles=json.loads(paths['growth'].read_text())['cycle_checks'];assert len(cycles)==83
for a,b in zip(cycles,cycles[1:]):assert int(a['last_fill_ns'])<ns(b['start_utc'])
cohorts={'year1':[int(c['cycle']) for c in cycles if ns(c['start_utc'])<year],'year2':[int(c['cycle']) for c in cycles if ns(c['start_utc'])>=year],'early':[int(c['cycle']) for c in cycles if ns(c['start_utc'])<early]}
configs=read(paths['combined']);cache=read(paths['stageI_cache'])+read(paths['stageII_cache']);assert len(configs)==36
cacheby=collections.defaultdict(list)
for r in cache:cacheby[r['rule'],r['horizon_h'],r['slip_bp'],r['funding_boundary']].append(r)
basefactor={int(c['cycle']):1+D(c['return']) for c in cycles};baselog={i:f.ln() for i,f in basefactor.items()};baseline=seed
for c in cycles:baseline*=basefactor[int(c['cycle'])]
pathrows=[];cohortrows=[];boundaryrows=[];factorsaved=[]
for config in configs:
 for slip in ['0','2']:
  for fund in ['BEFORE_ALL','AFTER_ALL']:
   z=cacheby[config['rule'],config['horizon_h'],slip,fund];bycycle={int(r['cycle']):r for r in z};assert len(bycycle)==len(z)
   for action in ['H','T']:
    value=seed;peak=seed;maxDD=D(0);state={};lift={};dA={};bad=[];values={};DDpeakCycle=DDtroughCycle=0;peakcycle=0
    for c in cycles:
     i=int(c['cycle']);row=bycycle.get(i);delta=D(row['net_'+action]) if row else D(0);da=delta/D(c['A']);factor=basefactor[i]+da;dA[i]=da
     if factor<=0:bad.append(i);lift[i]=None;values[i]=None
     else:
      lift[i]=factor.ln()-baselog[i] if delta else D(0)
      if not bad:
       value*=factor;values[i]=value
       if value>peak:peak=value;peakcycle=i
       dd=(peak-value)/peak
       if dd>maxDD:maxDD=dd;DDpeakCycle=peakcycle;DDtroughCycle=i
      else:values[i]=None
     factorsaved.append({'rule':config['rule'],'horizon_h':config['horizon_h'],'slip_bp':slip,'funding_boundary':fund,'action':action,'cycle':i,'original_A':c['A'],'original_r':c['return'],'cached_delta':str(delta),'delta_over_original_A':str(da),'factor':str(factor),'scalar_after_cycle':str(values[i]) if values[i] is not None else '', 'loglift_vs_original':str(lift[i]) if lift[i] is not None else '', 'covered_action':bool(row)})
    common={'rule':config['rule'],'horizon_h':config['horizon_h'],'slip_bp':slip,'funding_boundary':fund,'action':action};status='INFEASIBLE_FACTOR' if bad else 'POST_RESULT_SCALAR_ONLY'
    pathrows.append(dict(**common,status=status,infeasible_cycles=','.join(map(str,bad)),covered_cycles=len(bycycle),terminal_scalar_equivalent=str(value) if not bad else '',net_profit_retention_pct_vs_legacyS0=str((value-seed)/(S0-seed)*100) if not bad else '',gap70_USDT=str(floors['70']-value) if not bad else '',gap90_USDT=str(floors['90']-value) if not bad else '',cycle_boundary_DD_pct=str(maxDD*100) if not bad else '',DD_peak_cycle=DDpeakCycle,DD_trough_cycle=DDtroughCycle,action_tag_counts=json.dumps(dict(collections.Counter(r['J2_tag'] for r in z)),sort_keys=True)))
    for name,ids in cohorts.items():
     selected=[i for i in ids if i in bycycle];lifts=[lift[i] for i in ids];das=[dA[i] for i in ids];valid=all(x is not None for x in lifts)
     meanNB=sum((D(bycycle[i]['net_'+action])/D(bycycle[i]['NB_t'])*10000 for i in selected),D(0))/len(selected) if selected else D(0)
     cohortrows.append(dict(**common,cohort=name,cohort_basis='ORIGINAL_R3_FIRST_ACTUAL_FILL_START',cycles=len(ids),covered_action_cycles=len(selected),loglift_vs_original=str(sum(lifts,D(0))) if valid else '',sum_delta_over_original_A=str(sum(das,D(0))),mean_delta_over_original_A_all_cycles=str(sum(das,D(0))/len(ids)),mean_delta_over_original_A_covered=str(sum((dA[i] for i in selected),D(0))/len(selected)) if selected else '0',mean_delta_over_NB_t_bp_covered=str(meanNB),status='VALID' if valid else 'INFEASIBLE_FACTOR'))
    for name,boundary,include_end in [('early_Jan15',early,False),('year1_Sep1',year,False),('benchmark_terminal_post_boundary',end,True)]:
     complete=[int(c['cycle']) for c in cycles if int(c['last_fill_ns'])<boundary or (include_end and int(c['last_fill_ns'])==boundary)];cross=[int(c['cycle']) for c in cycles if ns(c['start_utc'])<boundary<=int(c['last_fill_ns']) and not(include_end and int(c['last_fill_ns'])==boundary)];last=complete[-1] if complete else 0;val=values[last] if last else seed
     boundaryrows.append(dict(**common,boundary=name,boundary_ns=boundary,actual_completed_cycles=len(complete),last_completed_cycle=last,crossing_open_cycle_ids=','.join(map(str,cross)),scalar_equivalent_completed_cycles_only=str(val) if val is not None else '',basis='ACTUAL_FLAT_STRICTLY_BEFORE_BOUNDARY; terminal includes original end boundary fill'))
# Pair geometric loglifts on identical original-cycle cohorts, not NB means.
cohortmap={(r['rule'],r['horizon_h'],r['slip_bp'],r['funding_boundary'],r['action'],r['cohort']):r for r in cohortrows}
for r in cohortrows:
 other=cohortmap[r['rule'],r['horizon_h'],r['slip_bp'],r['funding_boundary'],'T',r['cohort']]
 r['loglift_H_minus_T']=str(D(r['loglift_vs_original'])-D(other['loglift_vs_original'])) if r['action']=='H' and r['loglift_vs_original'] and other['loglift_vs_original'] else ''
summary=[]
for config in configs:
 key=config['rule'],config['horizon_h'];ps=[r for r in pathrows if (r['rule'],r['horizon_h'])==key];Hrows=[r for r in ps if r['action']=='H'];Trows=[r for r in ps if r['action']=='T'];cs=[r for r in cohortrows if (r['rule'],r['horizon_h'])==key and r['action']=='H'];valid=all(r['status']=='POST_RESULT_SCALAR_ONLY' for r in ps);Hpositive=valid and all(D(r['loglift_vs_original'])>0 for r in cs);paired=valid and all(D(r['loglift_H_minus_T'])>0 for r in cs)
 summary.append(dict(rule=key[0],horizon_h=key[1],family=config['family'],covered_cycles=int(config['episodes']),native_NOACTION_cycles=83-int(config['episodes']),discovery_sparse=config['sparse'],known_control=key[0] in ['A0','A1','R1','R2','F0','C2'],all_factors_valid=valid,capital_scale_positive_H_all3x4=Hpositive,paired_loglift_positive_HminusT_all3x4=paired,both_capital_and_paired_positive=Hpositive and paired,worst_H_terminal_equiv=str(min(D(r['terminal_scalar_equivalent']) for r in Hrows)) if valid else '',best_H_terminal_equiv=str(max(D(r['terminal_scalar_equivalent']) for r in Hrows)) if valid else '',worst_T_terminal_equiv=str(min(D(r['terminal_scalar_equivalent']) for r in Trows)) if valid else '',worst_H_loglift_cohort=str(min(D(r['loglift_vs_original']) for r in cs)) if valid else '',worst_paired_loglift_cohort=str(min(D(r['loglift_H_minus_T']) for r in cs)) if valid else '',worst_H_cycleboundary_DD_pct=str(max(D(r['cycle_boundary_DD_pct']) for r in Hrows)) if valid else '',worst_T_cycleboundary_DD_pct=str(max(D(r['cycle_boundary_DD_pct']) for r in Trows)) if valid else '',net_retention_at_worst_H_pct=str((min(D(r['terminal_scalar_equivalent']) for r in Hrows)-seed)/(S0-seed)*100) if valid else '',gap70_at_worst_H=str(floors['70']-min(D(r['terminal_scalar_equivalent']) for r in Hrows)) if valid else '',gap90_at_worst_H=str(floors['90']-min(D(r['terminal_scalar_equivalent']) for r in Hrows)) if valid else ''))
summary.sort(key=lambda r:(D(r['worst_H_terminal_equiv']) if r['worst_H_terminal_equiv'] else D('-Infinity'),D(r['worst_H_loglift_cohort']) if r['worst_H_loglift_cohort'] else D('-Infinity')),reverse=True)
for i,r in enumerate(summary,1):r['rank_worst_terminal']=i
for name,rows in [('paths',pathrows),('cohorts',cohortrows),('boundaries',boundaryrows),('factors',factorsaved),('summary',summary)]:
 with (O/f'capital-alignment-{name}.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
result={'status':'POST_RESULT_CAPITAL_ALIGNMENT_PENDING_VERIFICATION','configurations':36,'coherent_cases':4,'H_T_paths':len(pathrows),'cycle_factors':len(factorsaved),'original_observed_product':str(baseline),'cohort_cycle_counts':{k:len(v) for k,v in cohorts.items()},'cohort_basis':'Original R3 cycle first actual fill start; includes noactioncycles delta0; distinct from discovery action-entry NB cohort','capital_scale_positive':[r['rule']+'/'+r['horizon_h'] for r in summary if r['capital_scale_positive_H_all3x4']],'paired_positive':[r['rule']+'/'+r['horizon_h'] for r in summary if r['paired_loglift_positive_HminusT_all3x4']],'both_positive':[r['rule']+'/'+r['horizon_h'] for r in summary if r['both_capital_and_paired_positive']],'infeasible_path_count':sum(r['status']=='INFEASIBLE_FACTOR' for r in pathrows),'new_trade_outcomes':0,'new_configurations':0,'native_engine_runs':0,'input_sha256':inputs,'output_sha256':{p.name:sha(p) for p in O.glob('capital-alignment-*.csv')}}
(O/'capital-alignment-results.json').write_text(json.dumps(result,indent=2)+'\n');ledger.update(status='COMPLETE_PENDING_INDEPENDENT_VERIFICATION',cache_pass_completed=1,completed_utc=datetime.now(timezone.utc).isoformat(),results_sha256=sha(O/'capital-alignment-results.json'));(O/'capital-alignment-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');print(json.dumps(result,indent=2))
