"""Conditionally authorized TRAIN only, one attempt per stage, no CHECK."""
import json,subprocess,time
from pathlib import Path
report=Path('reports/forecast-independent-20261021');gate=json.loads((report/'profile-sequence-completion.json').read_text())
if not gate['all_pass']:raise RuntimeError('ALL_FIVE_RESOURCE_PROFILES_REQUIRED')
intent=report/'train-sequence-intent.json'
if intent.exists():raise RuntimeError('TRAIN_SEQUENCE_ALREADY_ATTEMPTED_NO_AUTOMATIC_RETRY')
def used(result):
 value=result.get('properties',{}).get('CPUUsageNSec','')
 if value.isdigit():return int(value)/1e9
 return result.get('profile',{}).get('cpu_seconds',result.get('train_result',{}).get('cpu_seconds',0))
profiles={r['profile']['family']:used(r) for r in gate['results'] if 'profile' in r};tests=0
for p in (report/'receipts').glob('cm113-pred02-tests-*.json'):tests+=used(json.loads(p.read_text()))
prior={'control':319.007+tests+profiles['control'],**{k:profiles[k] for k in ['stumpy','minirocket','cnn']},'rdst':profiles.get('rdst',0)+used(gate['rdst_corrected_attempt'])}
intent.write_text(json.dumps({'purpose':'TRAIN_ONLY_SCREEN_THEN_FIVE_SEALS_NO_CHECK','prior_cpu_seconds':prior,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()},indent=2)+'\n')
# Interrupted engineering profiles still consume the frozen family CPU budget.
interrupted=report/'resource-interruption-rdst-initial.json'
if interrupted.exists():
 proof=json.loads(interrupted.read_text());usage=dict(line.split() for line in proof['cpu.stat'].splitlines()).get('usage_usec')
 if usage is not None:prior['rdst']+=int(usage)/1e6
intent.write_text(json.dumps({'purpose':'TRAIN_ONLY_SCREEN_THEN_FIVE_SEALS_NO_CHECK','prior_cpu_seconds':prior,'interrupted_RDST_CPU_included':True,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()},indent=2)+'\n')
results=[]
def resource_sample(unit):
 base=Path('/sys/fs/cgroup/system.slice')/(unit+'.service')
 if not base.exists():return None
 stat=dict(line.split() for line in (base/'memory.stat').read_text().splitlines());events=dict(line.split() for line in (base/'memory.events').read_text().splitlines());read=sum(int(token.split('=')[1]) for line in (base/'io.stat').read_text().splitlines() for token in line.split()[1:] if token.startswith('rbytes='))
 return {'wall':time.time(),'anon':int(stat.get('anon',0)),'max_events':int(events.get('max',0)),'physical_read_bytes':read,'memory_stat':stat,'memory_events':events}
def execute(stage,family,selection=None):
 cmd=['python3',str(report/'launch_research.py'),stage,'--family',family,'--view','60x20','--execute-authorized-train','--prior-cpu-seconds',str(prior[family])]
 if selection is not None:cmd+=['--selection',str(selection)]
 p=subprocess.run(cmd,capture_output=True,text=True)
 if p.returncode:
  result={'status':'ADMISSION_INCOMPLETE_NO_FIT','stage':stage,'family':family,'stdout':p.stdout,'stderr':p.stderr};return result
 launch=json.loads(p.stdout);unit=launch['unit'];print(json.dumps({'stage':stage,'family':family,'unit':unit,'status':'RUNNING','prior_cpu_seconds':prior[family]}),flush=True)
 samples=[]
 while subprocess.check_output(['systemctl','show',unit,'-p','SubState','--value'],text=True).strip() in ('start','start-pre','running'):
  time.sleep(5)
  try:sample=resource_sample(unit)
  except FileNotFoundError:sample=None
  if sample is None:continue
  samples.append(sample);samples=[v for v in samples if sample['wall']-v['wall']<=40]
  old=next((v for v in samples if sample['wall']-v['wall']>=30),None)
  job=Path(launch['job']);progress_files=[job/'result/stdout.txt',*list((job/'result/train').glob('**/progress.json'))];last_progress=max((p.stat().st_mtime for p in progress_files if p.exists()),default=sample['wall'])
  if old and sample['anon']>=580*1024**2 and sample['wall']-last_progress>=45 and sample['max_events']-old['max_events']>=10000 and sample['physical_read_bytes']-old['physical_read_bytes']>=1024**3:
   proof={'unit':unit,'status':'INTERRUPTED_RESOURCE_THRASH_NOT_PREDICTIVE_FAILURE','reason':'>=580MiB anonymous + >=10000 max events + >=1GiB physical reads in30s + no scientific progress45s','samples':samples,'last_progress_wall':last_progress}
   (report/f'resource-interruption-{unit}.json').write_text(json.dumps(proof,indent=2)+'\n');subprocess.run(['systemctl','stop',unit],check=True);break
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
status={'status':'ALL_FIVE_MODELS_SEALED_NO_CHECK' if len(seals)==5 else 'INCOMPLETE_SOME_FAMILIES_NO_CHECK','seals':seals,'cpu_seconds':prior,'results':results}
(report/'train-sequence-completion.json').write_text(json.dumps(status,indent=2)+'\n')
if len(seals)==5:(report/'all-method-seals.json').write_text(json.dumps(seals,indent=2)+'\n')
print(json.dumps({'status':status['status'],'sealed_families':list(seals),'CHECK':'NOT_OPENED'}),flush=True)
