from pathlib import Path
from decimal import Decimal as D
import hashlib,json,csv
R=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021/reports/system-contract-repair-20261023');read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();checks={}
d=read(R/'data-manifest.json')
for n,pin in d['files'].items():checks['data_pin:'+n]=sha(R/n)==pin['sha256']
o=read(R/'owner-final-artifact-pins.json')
for n,pin in o.items():checks['owner_pin:'+n]=sha(R/n)==pin
b=read(R/'run-ledger.json');checks['budget_final']=b['started']==b['completed']==4 and b['active']==b['reserved']==0 and b['launches_closed'] and b['unused_slots']==2
checks['all_attempts_valid']=all(t['state'].startswith('VALID_COMPLETED') for t in b['attempts'])
x=read(R/'comparison.json');checks['matched_floor']=D(x['matched90_profit_floor'])==10000+D('.9')*(D(x['matched_S0_TOTAL'])-10000)
for q in x['rows']:
 n=q['recipe'];a=read(R/f'data-native-acceptance-{n}.json');e=read(R/f'execution-{n}.json');checks[n+':accepted']=not a['failed_checks'] and a['status']=='VALID_COMPLETED_CHANGED_EXECUTION_MODEL'
 checks[n+':normal_exit']=e['native_process_exit_code']==0 and e['config_exact']
 checks[n+':true_artifact']=sha(Path(e['artifact']))==q['artifact_sha256']
 checks[n+':DD_total']=q['TOTAL']==a['TOTAL'] and q['global_settled_DD_percent']==a['global_settled_DD_percent']
 checks[n+':fees']=D(q['maker_fees'])+D(q['taker_fees'])==D(q['total_fees'])
 checks[n+':full_coverage']=q['receipt_count']==1051199 and a['source_gaps']==0
 checks[n+':flat_zero_liquidations']=q['terminal_flat'] and q['liquidations']==0
 checks[n+':no_goal_pass']=q['matched_goal_pass'] is False
for n in ['H_SOL','H_BTC']:
 a=read(R/f'data-native-causal-{n}.json');checks[n+':all_groundtruth']=a['status']=='PASS' and a['check_assertions']==2407 and not a['failures']
 checks[n+':label_counts']=a['all_parents']==83 and a['valid_completed']==81 and a['censored']==2
checks['no_winner']=read(R/'selection.json')['selected_variant'] is None
checks['combo_futility']=read(R/'owner-combination-prefix-futility.json')['status']=='PASS'
checks['7windows_each']=sum(1 for _ in csv.DictReader((R/'episode-attribution.csv').open()))==28
checks['24months_each']=sum(1 for _ in csv.DictReader((R/'monthly-attribution.csv').open()))==96
checks['comparison4rows']=sum(1 for _ in csv.DictReader((R/'comparison.csv').open()))==4
review=read(R/'reviewer-final-report.json');checks['review_PASS']=review.get('status')=='PASS_FINAL_BOUNDED_NEGATIVE_REPORT'
checks['proof_no_syntheticTOTAL']=all('TOTAL' not in z for z in x['NOT_RUN'])
result={'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'checks_passed':sum(checks.values()),'checks_count':len(checks),'failures':[k for k,v in checks.items() if not v],'physical_engines':4,'economic_goal':'NOT_MET'}
(R/'root-final-qa.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','checks_passed','checks_count','failures']},indent=2));assert result['status']=='PASS'
