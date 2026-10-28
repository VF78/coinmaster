"""One fixed stress qualifier; original frozen economic source unchanged."""
import importlib.util
from pathlib import Path
import json,subprocess,uuid,argparse
MANAGER=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021')
P=MANAGER/'reports/e4-c1-fast-pilot-20261028'
spec=importlib.util.spec_from_file_location('frozen_orchestration',P/'mac_BTC_POSTCUT_D1_runner.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
KEY='QUAL_STRESS'
EXPECTED='5a1aab4a8e0c75711869fd886aa80c08052874f38e3d107f6d2bea925ac62883'
def command():
 c=b.command();c['argv']=list(c['argv']);i=c['argv'].index('--artifact-dir')+1;c['argv'][i]=str(b.JOB/KEY/'result');c['argv'].append('--qualification-stress');c['env']=dict(c['env']);c['env']['TMPDIR']=str(b.JOB/KEY/'tmp');return c

def preflight():
 assert not (b.JOB/KEY).exists(),'NAMESPACE_NOT_FRESH'
 m=b.verify_source();c=command();inputs=[]
 for rel,digest in c['input_pins'].items():
  paths=list(dict.fromkeys(x for x in (Path(c['data_root'])/rel,b.SOURCE/rel,b.PROJECT/rel) if x.is_file()))
  assert paths,rel
  for path in paths:
   assert b.sha(path)==digest,str(path)
   st=path.stat();inputs.append(dict(path=str(path),sha256=digest,size=st.st_size,mtime_ns=st.st_mtime_ns))
 assert b.sha(P/'config-QUAL-STRESS.json')==EXPECTED
 probe="import json; from coinmaster.research.native_baseline import qualification_stress_metadata; print(json.dumps(qualification_stress_metadata()))"
 run=subprocess.run([c['argv'][0],'-c',probe],cwd=c['cwd'],env=c['env'],capture_output=True,text=True,timeout=30)
 assert run.returncode==0,run.stderr[-1000:]
 actual=json.loads(run.stdout.strip().splitlines()[-1]);q=json.loads((P/'config-QUAL-STRESS.json').read_text());assert q.pop('native_qualification_stress')==actual
 assert q==json.loads((b.PACKET/'config-BTC-POSTCUT-D1.json').read_text())
 help_run=subprocess.run(c['argv']+['--help'],cwd=c['cwd'],env=c['env'],capture_output=True,text=True,timeout=30)
 assert help_run.returncode==0 and '--qualification-stress' in help_run.stdout,help_run.stderr[-1000:]
 b.save(b.JOB/(KEY+'-preflight.json'),dict(status='PREFLIGHT_PASS_NO_ENGINE',utc=b.now(),source_commit=b.COMMIT,config_sha256=EXPECTED,inputs=inputs,argv=c['argv'],cwd=c['cwd'],engines_created=0,source_files_verified=len(m['files'])))
 print(json.dumps(dict(status='PREFLIGHT_PASS_NO_ENGINE',config_sha256=EXPECTED,engines_created=0)))

def run_once():
 c=command();b.verify_source();pre=json.loads((b.JOB/(KEY+'-preflight.json')).read_text());assert pre['status']=='PREFLIGHT_PASS_NO_ENGINE' and pre['config_sha256']==EXPECTED
 for f in pre['inputs']:
  st=Path(f['path']).stat();assert (st.st_size,st.st_mtime_ns)==(f['size'],f['mtime_ns'])
 manifest=json.loads((P/'manifest.json').read_text());r=manifest['runs'][KEY]
 assert manifest['budget']['historical_max']==8 and manifest['budget']['qualification_max']==2
 assert manifest['runs']['BTC_POSTCUT_D1']['independent_full_analysis'].startswith('PASS')
 assert r['root_go'] is True and r['source_commit']==b.COMMIT and r['config_sha256']==EXPECTED
 attempt=r['attempt_uuid'];assert str(uuid.UUID(attempt))==attempt
 namespace=b.JOB/KEY;assert not namespace.exists(),'DO_NOT_REPEAT_OR_OVERWRITE'
 def claim(rows):
  assert sum(int(x['historical_budget_count'] or 0) for x in rows)==6
  assert not any(x['status'] in ['RUNNING','CLAIMED'] for x in rows)
  row=next(x for x in rows if x['id']==KEY);assert row['category']=='QUALIFICATION' and int(row['historical_budget_count'] or 0)==0
  assert not any(x['attempt_uuid']==attempt for x in rows)
  row.update(status='CLAIMED',historical_budget_count=1,attempt_uuid=attempt,source_commit=b.COMMIT,config_hash=EXPECTED,data_hash=c['data_hash'],artifact_dir=str(namespace/'result'),notes='ONE fixed stock adverse-tick qualifier; no algorithm changes; no repeat')
 b.registry_update(claim);namespace.mkdir();(namespace/'tmp').mkdir()
 gate=dict(status='CLAIMED_BEFORE_POPEN',attempt_uuid=attempt,source_commit=b.COMMIT,config_sha256=EXPECTED,started_utc=b.now(),actual_native_child_pid=None,actual_native_child_exit=None,argv=c['argv'],cwd=c['cwd'],historical_attempt=7)
 b.save(namespace/'execution.json',gate)
 try:
  with (namespace/'native.log').open('wb') as log:
   child=subprocess.Popen(c['argv'],cwd=c['cwd'],env=c['env'],stdout=log,stderr=subprocess.STDOUT);gate.update(actual_native_child_pid=child.pid,status='RUNNING');b.save(namespace/'execution.json',gate)
   def started(rows):next(x for x in rows if x['attempt_uuid']==attempt).update(status='RUNNING')
   b.registry_update(started);print(json.dumps(dict(status='RUNNING',native_child_pid=child.pid,attempt_uuid=attempt)),flush=True);rc=child.wait()
  gate.update(actual_native_child_exit=rc,finished_utc=b.now(),status='EXPORTED_PENDING_ANALYSIS' if rc==0 else 'FAILED_NATIVE_EXIT')
 except Exception as exc:gate.update(status='FAILED_LAUNCH',finished_utc=b.now(),error_type=type(exc).__name__,error=str(exc))
 b.save(namespace/'execution.json',gate)
 def done(rows):next(x for x in rows if x['attempt_uuid']==attempt).update(status=gate['status'],native_child_exit='' if gate['actual_native_child_exit'] is None else str(gate['actual_native_child_exit']))
 b.registry_update(done);print(json.dumps(gate),flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--preflight',action='store_true');parser.add_argument('--run',action='store_true');args=parser.parse_args();assert args.preflight!=args.run
 preflight() if args.preflight else run_once()
