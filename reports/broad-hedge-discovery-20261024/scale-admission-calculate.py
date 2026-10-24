"""POST_SELECTION_SCALE_ONLY: immutable cache/scalar arithmetic, no new trade labels."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from datetime import datetime,timezone
import csv,json,hashlib,collections
getcontext().prec=80
O=Path(__file__).resolve().parent;R=O.parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return list(csv.DictReader(Path(p).open()))
def dump(name,z):
 with (O/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(z[0]));w.writeheader();w.writerows(z)
paths={'protocol':O/'SCALE_ADMISSION_PROTOCOL.md','growth':R/'reports/early-capital-hedge-20261024/growth-envelope-results.json','stageI_cache':O/'discovery-stageI-episodes.csv','stageII_cache':O/'discovery-stageII-episodes.csv','stageI_receipt':O/'discovery-stageI-result.json','stageII_receipt':O/'discovery-stageII-result.json','discovery_summary':O/'discovery-summary.json','discovery_phase_immutable':O/'phase-ledger.json','script':Path(__file__)}
inputs={k:{'path':str(p),'sha256':sha(p)} for k,p in paths.items()}
for name in ['stageI','stageII']:
 receipt=json.loads(paths[name+'_receipt'].read_text());assert receipt['output_sha256'][f'discovery-{name}-episodes.csv']==inputs[name+'_cache']['sha256']
ledger={'status':'STARTED_POST_SELECTION_SCALE_ONLY','start_utc':datetime.now(timezone.utc).isoformat(),'fixed_selection':['B2/4h','F0/8h'],'scalar_pass_started':1,'scalar_pass_completed':0,'independent_verification_budget':1,'input_sha256':inputs,'new_trade_outcomes':0,'new_configurations':0,'native_engine_runs':0,'source_discovery_changes':0}
assert not (O/'scale-admission-ledger.json').exists(),'ONE_PASS_ONLY'
(O/'scale-admission-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
growth=json.loads(paths['growth'].read_text());cycles=growth['cycle_checks'];assert len(cycles)==83
seed=D(10000);S0=D('6077107.23887483');floors={'70':D('4256975.067212381'),'90':D('5470396.514987347')};orig={int(c['cycle']):c for c in cycles};sets={};deltas={};rows=[]
for rule,h,source in [('B2','4','stageI_cache'),('F0','8','stageII_cache')]:
 z=[r for r in read(paths[source]) if r['rule']==rule and r['horizon_h']==h];sets[rule]={int(r['cycle']) for r in z};assert len(z)==4*len(sets[rule]);assert len(sets[rule])==(38 if rule=='B2' else 65)
 for slip in ['0','2']:
  for fund in ['BEFORE_ALL','AFTER_ALL']:
   branch=[r for r in z if r['slip_bp']==slip and r['funding_boundary']==fund];assert {int(r['cycle']) for r in branch}==sets[rule];deltas[rule,slip,fund]={int(r['cycle']):D(r['net_H']) for r in branch}
   for cohort in ['all','year1','year2','early']:
    zz=branch if cohort=='all' else [r for r in branch if r['early']=='True'] if cohort=='early' else [r for r in branch if r['year']==cohort]
    amounts=[D(r['net_H']) for r in zz];fractions=[D(r['net_H'])/D(orig[int(r['cycle'])]['A']) for r in zz];NB=[D(r['NB_t']) for r in zz]
    rows.append({'rule':rule,'horizon_h':h,'slip_bp':slip,'funding_boundary':fund,'cohort':cohort,'n':len(zz),'covered_cycles':','.join(str(int(r['cycle'])) for r in zz),'endpoint_delta_sum_USDT':str(sum(amounts,D(0))),'endpoint_delta_mean_USDT':str(sum(amounts,D(0))/len(zz)),'sum_delta_over_original_cycle_A':str(sum(fractions,D(0))),'mean_delta_over_original_cycle_A':str(sum(fractions,D(0))/len(zz)),'mean_delta_over_NB_t_bp':str(sum((v/n for v,n in zip(amounts,NB)),D(0))/len(zz)*10000),'latest_hypothetical_action_endpoint_utc':max(r['end_ns'] for r in zz),'scope':'ACTUAL_R3_QTY_FIXED_CACHED_ENDPOINT_CONTRIBUTION_NOT_CANDIDATE_WALLET'})
dump('scale-admission-cached-deltas.csv',rows)
productrows=[]
for rule in ['B2','F0']:
 for slip in ['0','2']:
  for fund in ['BEFORE_ALL','AFTER_ALL']:
   total=seed
   for c in cycles:
    i=int(c['cycle']);mult=1+D(c['return'])+deltas[rule,slip,fund].get(i,D(0))/D(c['A']);assert mult>0;total*=mult
   productrows.append({'rule':rule,'slip_bp':slip,'funding_boundary':fund,'terminal_scalar_equivalent':str(total),'net_profit_retention_pct_vs_legacyS0':str((total-seed)/(S0-seed)*100),'gap70_USDT':str(floors['70']-total),'gap90_USDT':str(floors['90']-total),'required_terminal_multiple70':str(floors['70']/total),'required_terminal_multiple90':str(floors['90']/total),'basis':'seed*product(1+r_i+cached_delta_i/original_A_i); NOT_NATIVE_TOTAL_OR_CANDIDATE_ROI'})
dump('scale-admission-fixed-transfer.csv',productrows)
sets['UNION']=sets['B2']|sets['F0'];logloss=sum((-(1+D(c['return'])).ln() for c in cycles if D(c['return'])<0),D(0));oracles=[]
for name,cover in sets.items():
 total=seed;coveredlosslog=D(0);nloss=0
 for c in cycles:
  r=D(c['return']);covered=int(c['cycle']) in cover
  if covered and r<0:coveredlosslog-=(1+r).ln();nloss+=1;r=D(0)
  total*=1+r
 oracles.append({'coverage_set':name,'covered_cycles':len(cover),'covered_cycle_ids':','.join(map(str,sorted(cover))),'covered_losing_cycles':nloss,'all_losing_cycles':sum(D(c['return'])<0 for c in cycles),'covered_negative_log_return_fraction':str(coveredlosslog/logloss),'negative_log_return_total':str(logloss),'negative_log_return_covered':str(coveredlosslog),'terminal_scalar_equivalent':str(total),'net_profit_retention_pct_vs_legacyS0':str((total-seed)/(S0-seed)*100),'gap70_USDT':str(floors['70']-total),'gap90_USDT':str(floors['90']-total),'required_terminal_multiple70':str(floors['70']/total),'required_terminal_multiple90':str(floors['90']/total),'basis':'POST_SELECTION_ORACLE; zero ONLY covered original future losers; keep ALL winners; union coverage ONLY, no union strategy/cash'})
dump('scale-admission-oracle-coverage.csv',oracles)
observed=seed
for c in cycles:observed*=1+D(c['return'])
assert abs(observed-D('120718.40416503'))<D('0.000001')
result={'status':'POST_SELECTION_SCALE_ONLY_COMPLETE_PENDING_VERIFICATION','fixed_choices':['B2/4h','F0/8h'],'precision':80,'original_cycles':83,'observed_product_equivalent':str(observed),'legacyS0_total':str(S0),'floors':{k:str(v) for k,v in floors.items()},'cached_delta_tables':rows,'fixed_transfer_products':productrows,'oracle_coverage':oracles,'new_configurations':0,'new_trade_outcomes':0,'native_engine_runs':0,'limitations':['POST_SELECTION cached endpoint arithmetic, not extra trading hypotheses/statistical confirmation.','Early entry cohort action endpoints may follow Jan15; not capital on Jan15 or an E4 gap closure.','Fixed-return transfer keeps original r_i/A_i and quantities/admission; within-cycle timing/capacity/lifecycle/actual3TP not modeled.','Oracle knows future loser labels; they never become features.','Coverage union ONLY an oracle covered-cycle set, no union cash/strategy or best action selection.','Bookends are not formal upper bounds for all SOL or changed BTC exits; no candidateTOTAL/nativeDD/70-90 proof.'],'input_sha256':inputs,'output_sha256':{p.name:sha(p) for p in O.glob('scale-admission-*.csv')}}
(O/'scale-admission-results.json').write_text(json.dumps(result,indent=2)+'\n');ledger.update(status='COMPLETE_PENDING_INDEPENDENT_VERIFICATION',scalar_pass_completed=1,completed_utc=datetime.now(timezone.utc).isoformat(),results_sha256=sha(O/'scale-admission-results.json'));(O/'scale-admission-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');print(json.dumps({'products':productrows,'oracle':oracles},indent=2))
