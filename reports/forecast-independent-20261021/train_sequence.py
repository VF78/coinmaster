"""Conditionally authorized TRAIN only, one attempt per stage, no CHECK."""
import json,subprocess,time
from pathlib import Path
report=Path('reports/forecast-independent-20261021');gate=json.loads((report/'profile-sequence-completion.json').read_text())
if not gate['all_pass']:raise RuntimeError('FOCUSED_TESTS_AND_ALL_FIVE_PROFILES_MUST_PASS')
intent=report/'train-sequence-intent.json'
if intent.exists():raise RuntimeError('TRAIN_SEQUENCE_ALREADY_ATTEMPTED_NO_AUTOMATIC_RETRY')
def used(result):
 value=result.get('properties',{}).get('CPUUsageNSec','')
 if value.isdigit():return int(value)/1e9
 return result.get('profile',{}).get('cpu_seconds',result.get('train_result',{}).get('cpu_seconds',0))
profiles={r['profile']['family']:used(r) for r in gate['results'] if 'profile' in r};tests=0
for p in (report/'receipts').glob('cm113-pred02-tests-*.json'):tests+=used(json.loads(p.read_text()))
prior={'control':319.007+tests+profiles['control'],**{k:profiles[k] for k in ['stumpy','minirocket','rdst','cnn']}}
intent.write_text(json.dumps({'purpose':'TRAIN_ONLY_SCREEN_THEN_FIVE_SEALS_NO_CHECK','prior_cpu_seconds':prior,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()},indent=2)+'\n')
results=[]
def execute(stage,family,selection=None):
 cmd=['python3',str(report/'launch_research.py'),stage,'--family',family,'--view','60x20','--execute-authorized-train','--prior-cpu-seconds',str(prior[family])]
 if selection is not None:cmd+=['--selection',str(selection)]
 p=subprocess.run(cmd,capture_output=True,text=True)
 if p.returncode:
  result={'status':'ADMISSION_INCOMPLETE_NO_FIT','stage':stage,'family':family,'stdout':p.stdout,'stderr':p.stderr};return result
 launch=json.loads(p.stdout);unit=launch['unit'];print(json.dumps({'stage':stage,'family':family,'unit':unit,'status':'RUNNING','prior_cpu_seconds':prior[family]}),flush=True)
 while subprocess.check_output(['systemctl','show',unit,'-p','SubState','--value'],text=True).strip() in ('start','start-pre','running'):time.sleep(1)
 p=subprocess.run(['python3',str(report/'collect_research.py'),launch['receipt']],capture_output=True,text=True);p.check_returncode();result=json.loads(p.stdout);result['stage']=stage;result['family']=family;prior[family]+=used(result)
 print(json.dumps({'stage':stage,'family':family,'status':result['status'],'used_cpu_seconds':prior[family],'failure':result.get('failure'),'selected_view':result.get('train_result',{}).get('view'),'method_views':result.get('train_result',{}).get('method_views')}),flush=True);return result
screen=execute('screen','control');results.append(screen);(report/'train-sequence-progress.json').write_text(json.dumps({'results':results,'cpu_seconds':prior},indent=2)+'\n')
if screen['status']!='PASS':raise RuntimeError('RAW_SCREEN_INCOMPLETE_NO_VIEW_SELECTION_NO_RETRY')
selection=Path(screen['job'])/'result/train/result.json';seals={}
for family in ['control','stumpy','minirocket','rdst','cnn']:
 result=execute('fit',family,selection);results.append(result)
 if result['status']=='PASS':
  p=Path(result['job'])/'result/train/seal.json';seals[family]={'path':str(p),'sha256':__import__('hashlib').file_digest(p.open('rb'),'sha256').hexdigest()}
 (report/'train-sequence-progress.json').write_text(json.dumps({'results':results,'cpu_seconds':prior,'seals':seals},indent=2)+'\n')
status={'status':'ALL_FIVE_SEALED_NO_CHECK' if len(seals)==5 else 'INCOMPLETE_SOME_FAMILIES_NO_CHECK','seals':seals,'cpu_seconds':prior,'results':results}
(report/'train-sequence-completion.json').write_text(json.dumps(status,indent=2)+'\n')
if len(seals)==5:(report/'all-method-seals.json').write_text(json.dumps(seals,indent=2)+'\n')
print(json.dumps({'status':status['status'],'sealed_families':list(seals),'CHECK':'NOT_OPENED'}),flush=True)
