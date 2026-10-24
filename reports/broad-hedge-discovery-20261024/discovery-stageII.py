"""Exactly B2/F0 x8h/12h conditional refinement; unchanged frozen library."""
from pathlib import Path
import importlib.util,csv,json,hashlib,collections,re,math
from datetime import datetime,timezone
from decimal import Decimal as D
import numpy as np
import pyarrow.parquet as pq
O=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('frozen_stageI',O/'discovery-stageI.py');lib=importlib.util.module_from_spec(spec);spec.loader.exec_module(lib)
sha=lib.sha;read=lib.read;dump=lib.dump;ns=lib.ns;M=lib.M;H=lib.H
metrics=lib.metrics;cohort=lib.cohort;bootstrap=lib.bootstrap;COHORTS=lib.COHORTS

def analyze(rows,registry):
 summaries=[];tables=[];statrows=[];rng=np.random.default_rng(20261024)
 for reg in registry:
  rule=reg['rule']
  for h in [8,12]:
   zz=[r for r in rows if r['rule']==rule and r['horizon_h']==h];mm=[];valid=True;sparse=False
   for slip in [0,2]:
    for boundary in ['BEFORE_ALL','AFTER_ALL']:
     scenario=[r for r in zz if r['slip_bp']==slip and r['funding_boundary']==boundary]
     for name in COHORTS:
      z=cohort(scenario,name)
      if not z:valid=False;sparse=True;continue
      m=metrics(z);m.update(rule=rule,horizon_h=h,slip_bp=slip,funding_boundary=boundary,cohort=name);tables.append(m);mm.append(m);sparse|=m['n']<(3 if name=='early' else 10)
   capital=valid and all(m['mean_H']>0 and m['mean_paired']>0 for m in mm)
   protectionBase=valid and all(m['CVaR_N']>m['CVaR_H'] for m in mm)
   routeR=protectionBase and all(m['mean_paired']>0 for m in mm);routeK=protectionBase and all(m['CVaR_T']>m['CVaR_H'] for m in mm);protection=routeR or routeK
   # Admission as a SOL family additionally excludes no-SOL actions/control lanes.
   trueSOL=rule not in ['A0','C2'] and any(r['SOL_qty_t']>0 for r in zz)
   qualC=capital and not sparse and trueSOL;qualP=protection and not sparse and trueSOL
   pC=pP=1.;ci_status='NOT_TESTED_FAIL_OR_SPARSE'
   if (capital or protection) and not sparse and valid:
    components=[]
    for m in mm:
     scenario=[r for r in zz if r['slip_bp']==m['slip_bp'] and r['funding_boundary']==m['funding_boundary']];z=cohort(scenario,m['cohort']);p,ci,attempts=bootstrap(z,m['cohort'],rng);components.append(p)
     for j,key in enumerate(['mean_H','mean_H_minus_T','CVaR_N_minus_H','CVaR_T_minus_H']):statrows.append(dict(rule=rule,horizon_h=h,slip_bp=m['slip_bp'],funding_boundary=m['funding_boundary'],cohort=m['cohort'],contrast=key,p=float(p[j]),CI_low=float(ci[0,j]),CI_high=float(ci[1,j]),B=8192,draw_attempts=attempts))
    ps=np.array(components);pC=float(ps[:,:2].max());pReturn=float(ps[:,[2,1]].max());pRisk=float(ps[:,[2,3]].max());pP=min(1.,2*min(pReturn,pRisk));ci_status='BOOTSTRAP_APPROXIMATE_STATIONARY_MONTHS'
   main=[m for m in mm if m['cohort']!='early'];base=next((m for m in mm if m['cohort']=='year1' and m['slip_bp']==2 and m['funding_boundary']=='BEFORE_ALL'),None);second=next((m for m in mm if m['cohort']=='year2' and m['slip_bp']==2 and m['funding_boundary']=='BEFORE_ALL'),None);early=next((m for m in mm if m['cohort']=='early' and m['slip_bp']==2 and m['funding_boundary']=='BEFORE_ALL'),None)
   summary=dict(rule=rule,family=reg['family'],horizon_h=h,episodes=len({r['cycle'] for r in zz}),no_action_episodes=83-len({r['cycle'] for r in zz}),year1_n=base['n'] if base else 0,year2_n=second['n'] if second else 0,early_n=early['n'] if early else 0,raw_capital_positive=bool(capital),raw_protection_positive=bool(protection),consistent_route='RETURN_AND_RISK' if routeR and routeK else 'RETURN' if routeR else 'RISK' if routeK else 'NONE',sparse=bool(sparse),true_SOL_eligible=bool(trueSOL),qualified_raw_capital=bool(qualC),qualified_raw_protection=bool(qualP),capital_p=pC if qualC else 1.,protection_p=pP if qualP else 1.,statistics=ci_status,min_main_paired_mean=min((m['mean_paired'] for m in main),default=None),min_main_CVaR_gain=min((m['CVaR_N']-m['CVaR_H'] for m in main),default=None),min_main_CVaR_vs_trim_gain=min((m['CVaR_T']-m['CVaR_H'] for m in main),default=None))
   for name,m in [('year1',base),('year2',second),('early',early)]:
    for key in ['mean_H','mean_T','mean_paired','CVaR_N','CVaR_H','CVaR_T']:summary[name+'_'+key]=m[key] if m else None
   summaries.append(summary)
 # All 128 potential tests retained; untested future horizons/invalids are p=1.
 tests=[(i,l,float(s[l+'_p'])) for i,s in enumerate(summaries) for l in ['capital','protection']]+[(None,None,1.)]*(128-2*len(summaries));order=sorted(range(128),key=lambda j:tests[j][2]);last=0.
 for rank,j in enumerate(order):
  i,l,p=tests[j];last=max(last,min(1.,(128-rank)*p))
  if i is not None:summaries[i][l+'_Holm128']=last
 for s in summaries:s['capital_confirmed']=s['qualified_raw_capital'] and s['capital_Holm128']<=.05;s['protection_confirmed']=s['qualified_raw_protection'] and s['protection_Holm128']<=.05
 return summaries,tables,statrows

def main():
 ledger=json.loads((O/'phase-ledger.json').read_text());assert ledger['stage_I']['verification_status']=='PASS' and ledger['stage_II']['started']==0 and ledger['stage_II']['completed']==0
 for p,s in ledger['sha256'].items():assert sha(O/p)==s
 first=json.loads((O/'discovery-stageI-result.json').read_text());assert sha(O/'discovery-stageI.py')==first['script_sha256'];assert sha(O/'discovery-stageI-result.json')==ledger['stage_I']['result_sha256'];assert sha(O/'discovery-stageI-verification.json')==ledger['stage_I']['verification_result_sha256']
 build=json.loads((O/'discovery-build.json').read_text())
 for p,s in build['input_sha256'].items():assert sha(p)==s
 stage1=read(O/'discovery-stageI-configurations.csv');cap=sorted([s for s in stage1 if s['qualified_raw_capital']=='True'],key=lambda s:(-float(s['min_main_paired_mean']),-int(s['episodes'])));chosen=[cap[0]['rule']];prot=sorted([s for s in stage1 if s['qualified_raw_protection']=='True' and s['family']!=cap[0]['family']],key=lambda s:(-float(s['min_main_CVaR_gain'])*int(s['episodes']),-min(float(s['year1_mean_H']),float(s['year2_mean_H']))));chosen.append(prot[0]['rule']);assert chosen==['B2','F0']
 ledger['stage_II'].update(started=1,start_utc=datetime.now(timezone.utc).isoformat(),selected_rules=chosen,selection_formula='Prefer one per lane: highest min-main paired mean capital B2/4; highest min-main CVaR_N-H times episodes among different families protection F0/4.',selection_facts={'B2_capital_min_paired_bp':float(cap[0]['min_main_paired_mean']),'F0_protection_score':float(prot[0]['min_main_CVaR_gain'])*int(prot[0]['episodes'])},script_sha256=sha(Path(__file__)),frozen_stageI_library_sha256=sha(O/'discovery-stageI.py'));ledger['status']='STAGE_II_RUNNING';(O/'phase-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
 data=Path(next(p for p in build['input_sha256'] if p.endswith('bybit-BTCUSDT-execution-1m.parquet'))).parent;z=np.load(O/'discovery-baseline.npz');baseline={k:z[k] for k in z.files};mt=baseline['timestamp_ns'];start=int(mt[0]);ix=lambda t:int((t-start)//M);market={};rates={}
 for sym in ['BTC','SOL']:
  for kind in ['execution-1m','mark-1m']:market[sym,kind]=np.array(pq.read_table(data/f'bybit-{sym}USDT-{kind}.parquet',columns=['close']).column('close').to_pylist(),float)
  d=pq.read_table(data/f'bybit-{sym}USDT-funding.parquet').to_pydict();rates[sym]={int(t)*10**6:float(r) for t,r in zip(d['funding_time_ms'],d['funding_rate'])}
 raw=json.loads(Path(next(p for p in build['input_sha256'] if p.endswith('-raw-native.json'))).read_text());csvf=read(next(p for p in build['input_sha256'] if p.endswith('-fills.csv')));sides=collections.defaultdict(list)
 for f in csvf:sides[(ns(f['ts_last']),D(f['filled_qty']),D(f['avg_px']).quantize(D('.1')),D(re.search(r'([0-9.]+) USDT',f['commissions'])[1]))].append(1 if f['side']=='BUY' else -1)
 fills=collections.defaultdict(list);funds=collections.defaultdict(float)
 for j,a in enumerate(raw['fill_audit']):
  t=int(a['fill_ns']);key=t,D(a['qty']),D(a['px']).quantize(D('.1')),D(a['commission']);sg=sides[key].pop();fills[t].append(dict(dq=sg*float(a['qty']),px=float(a['px']),fee=float(a['commission']),index=j))
 for x in raw['funding']['signed_native_cash_deltas']:funds[int(x[2])]+=float(x[5])
 features={(f['cycle'],f['decision_ns']):f for f in read(O/'discovery-features.csv')};selected=[s for s in read(O/'discovery-stageI-selected.csv') if s['rule'] in chosen];cycles={int(c['cycle']):c for c in read(O/'discovery-actual-cycles.csv')};registry=[r for r in read(O/'discovery-registry.csv') if r['rule'] in chosen];rows=[]
 for s in selected:
  f=dict(features[s['cycle'],s['decision_ns']],rule=s['rule']);cy=int(s['cycle'])
  for h in [8,12]:
   for slip in [0,2]:
    for boundary in ['BEFORE_ALL','AFTER_ALL']:
     row,error=lib.action_path(f,h,slip,boundary,baseline,mt,ix,market,rates,fills,funds,cycles[cy]);assert error is None;rows.append(row)
 summaries,tables,stats=analyze(rows,registry);assert len(summaries)==4
 # Recompute Holm on ALL prior64 + current8 + untested56 potential tests.
 combined=[dict(x) for x in stage1]+summaries;tests=[(i,l,float(s[l+'_p'])) for i,s in enumerate(combined) for l in ['capital','protection']]+[(None,None,1.)]*56;assert len(tests)==128;last=0.
 for rank,j in enumerate(sorted(range(128),key=lambda j:tests[j][2])):
  i,l,p=tests[j];last=max(last,min(1.,(128-rank)*p))
  if i is not None:combined[i][l+'_Holm128']=last
 for s in combined:
  for lane in ['capital','protection']:s[lane+'_confirmed']=str(s['qualified_raw_'+lane])=='True' and float(s[lane+'_Holm128'])<=.05
 summaries=combined[-4:];dump('discovery-stageII-episodes.csv',rows);dump('discovery-stageII-cohorts.csv',tables);dump('discovery-stageII-configurations.csv',summaries);dump('discovery-stageII-statistics.csv',stats);dump('discovery-combined-configurations.csv',combined)
 result={'status':'STAGE_II_COMPLETE_PENDING_VERIFICATION','selected_rules':chosen,'new_configurations':4,'all_configurations':36,'rows':len(rows),'raw_capital_positive':[s['rule']+':'+str(s['horizon_h']) for s in summaries if s['raw_capital_positive']],'raw_protection_positive':[s['rule']+':'+str(s['horizon_h']) for s in summaries if s['raw_protection_positive']],'qualified_raw_capital':[s['rule']+':'+str(s['horizon_h']) for s in summaries if s['qualified_raw_capital']],'qualified_raw_protection':[s['rule']+':'+str(s['horizon_h']) for s in summaries if s['qualified_raw_protection']],'confirmed_capital':[s['rule']+':'+str(s['horizon_h']) for s in summaries if s['capital_confirmed']],'confirmed_protection':[s['rule']+':'+str(s['horizon_h']) for s in summaries if s['protection_confirmed']],'physical_engine_runs':0,'no_further_refinement_budget':True,'script_sha256':sha(Path(__file__)),'stageI_library_sha256':sha(O/'discovery-stageI.py'),'output_sha256':{p.name:sha(p) for p in O.glob('discovery-stageII-*.csv')},'combined_summary_sha256':sha(O/'discovery-combined-configurations.csv')}
 (O/'discovery-stageII-result.json').write_text(json.dumps(result,indent=2)+'\n');ledger['stage_II'].update(completed=1,completed_utc=datetime.now(timezone.utc).isoformat(),configurations_evaluated=4,result_sha256=sha(O/'discovery-stageII-result.json'));ledger['status']='STAGE_II_COMPLETE_PENDING_VERIFICATION';(O/'phase-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
