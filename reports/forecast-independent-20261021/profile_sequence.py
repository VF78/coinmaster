"""Sequential focused verification and exactly one bounded profile per family."""
import json,subprocess,time
from pathlib import Path
report=Path('reports/forecast-independent-20261021');intent=report/'profile-sequence-intent.json'
if intent.exists():raise RuntimeError('PROFILE_SEQUENCE_ALREADY_ATTEMPTED_NO_AUTOMATIC_RETRY')
intent.write_text(json.dumps({'stages':['tests-current-source','profile-control','profile-stumpy','profile-minirocket','profile-rdst','profile-cnn'],'view':'240x60','only_bounded_profiles':True},indent=2)+'\n')
results=[]
# Retain an earlier completed test job receipt if present.
for launch in sorted(report.glob('launch-tests-control-60x20-*.json')):
 r=json.loads(launch.read_text());state=subprocess.check_output(['systemctl','show',r['unit'],'-p','SubState','--value'],text=True).strip()
 if state=='exited':subprocess.run(['python3',str(report/'collect_research.py'),str(launch)],check=True,capture_output=True,text=True)
for stage,family in [('tests','control'),*[( 'profile',x) for x in ['control','stumpy','minirocket','rdst','cnn']]]:
 command=['python3',str(report/'launch_research.py'),stage,'--family',family,'--view','240x60']
 launch=subprocess.run(command,capture_output=True,text=True)
 if launch.returncode:
  result={'stage':stage,'family':family,'status':'ADMISSION_OR_LAUNCH_INCOMPLETE','stdout':launch.stdout,'stderr':launch.stderr};results.append(result);(report/'profile-sequence-progress.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(result),flush=True)
  if stage=='tests':raise RuntimeError('FOCUSED_TEST_LAUNCH_FAILED')
  continue
 record=json.loads(launch.stdout);unit=record['unit'];print(json.dumps({'stage':stage,'family':family,'unit':unit,'status':'RUNNING'}),flush=True)
 while subprocess.check_output(['systemctl','show',unit,'-p','SubState','--value'],text=True).strip() in ('start','start-pre','running'):time.sleep(1)
 collect=subprocess.run(['python3',str(report/'collect_research.py'),record['receipt']],capture_output=True,text=True);collect.check_returncode();result=json.loads(collect.stdout);results.append(result);(report/'profile-sequence-progress.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps({'stage':stage,'family':family,'status':result['status'],'profile':result.get('profile'),'failure':result.get('failure')}),flush=True)
 if stage=='tests' and result['status']!='PASS':raise RuntimeError('FOCUSED_TESTS_FAILED_NO_PROFILE_LAUNCH')
(report/'profile-sequence-completion.json').write_text(json.dumps({'all_pass':all(r['status']=='PASS' for r in results),'results':results},indent=2)+'\n')
