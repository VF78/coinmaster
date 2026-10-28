"""One fixed fresh-account validation qualifier; economic functions unchanged."""
import importlib.util
from pathlib import Path
import json,subprocess,uuid,argparse
MANAGER=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021')
P=MANAGER/'reports/e4-c1-fast-pilot-20261028'
spec=importlib.util.spec_from_file_location('frozen_orchestration',P/'mac_BTC_POSTCUT_D1_runner.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
KEY='QUAL_VALIDATION'
EXPECTED='9c7e16e4bee8ab6c91dae5009b083b1509ffe6053d36c5c38af929964a78d1db'
COMMIT='299197a7140ad0ae5c18aecdf596cbdbd7124bf4'
SOURCE=b.JOB/'source-QUAL-HARNESS-299197a7140a'
def command():
 c=json.loads((P/'QUAL-VALIDATION-run-command.json').read_text());assert c['expected_config_sha256']==EXPECTED
 c['argv']=list(c['argv']);i=c['argv'].index('--control-report')+1;c['argv'][i]=str(b.JOB/'qualification-archived-control-v0.json')
 c['cwd']=str(SOURCE/'runtime');c['env']=dict(c['env']);c['env']['PYTHONPATH']=c['cwd'];c['env']['TMPDIR']=str(b.JOB/KEY/'tmp')
 assert '--qualification-stress' not in c['argv'];return c

def verify_source():
 mpath=b.JOB/'source-QUAL-HARNESS-299197a7140a.manifest.json';assert b.sha(mpath)=='5f3f6e6d9c3c0be7c77b31a30147a39d9eb45a6b65119a250d1e05d5f56a1ae3'
 m=json.loads(mpath.read_text());assert m['commit']==COMMIT and len(m['files'])==173
 for rel,digest in m['files'].items():assert b.sha(SOURCE/rel)==digest,rel
 fixture=json.loads((b.JOB/'source-QUAL-HARNESS-299197a7140a.fixture-inputs.json').read_text());assert fixture['source_commit']==COMMIT and len(fixture['input_pins'])==3
 for rel,digest in fixture['input_pins'].items():assert b.sha(SOURCE/rel)==digest,rel
 assert b.sha(P/'qualification-harness-peer-review.json')=='b1783fbfa26ec716e72a5e8745d965a8078af7789c00e0560c21c7156ad041f4'
 assert b.sha(b.JOB/'qualification-archived-control-v0.json')=='d6a29d6e0e9ac586b911f2802cbe89602a05d2c0d73026d08ed76082a8a934f9'
 return m

def preflight():
 assert not (b.JOB/KEY).exists(),'NAMESPACE_NOT_FRESH'
 m=verify_source();c=command();inputs=[]
 for rel,digest in c['input_pins'].items():
  paths=list(dict.fromkeys(x for x in (Path(c['data_root'])/rel,SOURCE/rel,b.PROJECT/rel) if x.is_file()))
  assert paths,rel
  for path in paths:
   assert b.sha(path)==digest,str(path)
   st=path.stat();inputs.append(dict(path=str(path),sha256=digest,size=st.st_size,mtime_ns=st.st_mtime_ns))
 assert b.sha(P/'config-QUAL-VALIDATION.json')==EXPECTED
 assert b.sha(P/'config-QUAL-VALIDATION.json')==EXPECTED
 q=json.loads((P/'config-QUAL-VALIDATION.json').read_text());old=json.loads((b.PACKET/'config-BTC-POSTCUT-D1.json').read_text());q['run_interval']=old['run_interval'];assert q==old
 acceptance=json.loads((P/'evidence/qualification-data-acceptance.json').read_text());assert acceptance['issues']==[] and acceptance['final_collection_receipt_file_hashes']['status']=='PASS'
 for path,digest in {**acceptance['normalized_hashes'],**acceptance['manifest_pins']}.items():
  path=Path(path);assert b.sha(path)==digest,str(path);st=path.stat();inputs.append(dict(path=str(path),sha256=digest,size=st.st_size,mtime_ns=st.st_mtime_ns))
 control=b.JOB/'qualification-archived-control-v0.json';st=control.stat();inputs.append(dict(path=str(control),sha256=b.sha(control),size=st.st_size,mtime_ns=st.st_mtime_ns))
 canonical=json.dumps(json.loads((Path(c['data_root'])/'bybit-1m/manifest.json').read_text()),sort_keys=True,separators=(',',':')).encode();assert b.hashlib.sha256(canonical).hexdigest()==c['data_hash']=='1714540d189ce5dbc45489ea007f2fb16a5dafb9a451c13010ceee208639171b'
 probe="import json,importlib.metadata; import coinmaster; assert importlib.metadata.version('nautilus_trader')=='1.231.0'; print(json.dumps({'source':coinmaster.__file__,'engines':0}))"
 run=subprocess.run([c['argv'][0],'-c',probe],cwd=c['cwd'],env=c['env'],capture_output=True,text=True,timeout=30);assert run.returncode==0,run.stderr[-1000:];assert Path(json.loads(run.stdout.strip().splitlines()[-1])['source']).resolve().is_relative_to(SOURCE.resolve())
 help_run=subprocess.run(c['argv']+['--help'],cwd=c['cwd'],env=c['env'],capture_output=True,text=True,timeout=30)
 assert help_run.returncode==0 and '--qualification-data-hash' in help_run.stdout,help_run.stderr[-1000:]
 b.save(b.JOB/(KEY+'-preflight.json'),dict(status='PREFLIGHT_PASS_NO_ENGINE',utc=b.now(),source_commit=COMMIT,config_sha256=EXPECTED,inputs=inputs,argv=c['argv'],cwd=c['cwd'],engines_created=0,source_files_verified=len(m['files'])))
 print(json.dumps(dict(status='PREFLIGHT_PASS_NO_ENGINE',config_sha256=EXPECTED,engines_created=0)))

def run_once():
 c=command();verify_source();pre=json.loads((b.JOB/(KEY+'-preflight.json')).read_text());assert pre['status']=='PREFLIGHT_PASS_NO_ENGINE' and pre['config_sha256']==EXPECTED
 for f in pre['inputs']:
  st=Path(f['path']).stat();assert (st.st_size,st.st_mtime_ns)==(f['size'],f['mtime_ns'])
 manifest=json.loads((P/'manifest.json').read_text());r=manifest['runs'][KEY]
 assert manifest['budget']['historical_max']==8 and manifest['budget']['qualification_max']==2
 assert manifest['runs']['BTC_POSTCUT_D1']['independent_full_analysis'].startswith('PASS')
 assert manifest['runs']['QUAL_STRESS']['qualification_technical_status']=='PASS'
 assert manifest['runs']['QUAL_STRESS']['qualification_risk_status']=='PASS'
 assert r['root_go'] is True and r['source_commit']==COMMIT and r['config_sha256']==EXPECTED
 attempt=r['attempt_uuid'];assert str(uuid.UUID(attempt))==attempt
 namespace=b.JOB/KEY;assert not namespace.exists(),'DO_NOT_REPEAT_OR_OVERWRITE'
 def claim(rows):
  assert sum(int(x['historical_budget_count'] or 0) for x in rows)==7
  assert not any(x['status'] in ['RUNNING','CLAIMED'] for x in rows)
  row=next(x for x in rows if x['id']==KEY);assert row['category']=='QUALIFICATION' and int(row['historical_budget_count'] or 0)==0
  assert not any(x['attempt_uuid']==attempt for x in rows)
  row.update(status='CLAIMED',historical_budget_count=1,attempt_uuid=attempt,source_commit=COMMIT,config_hash=EXPECTED,data_hash=c['data_hash'],artifact_dir=str(namespace/'result'),notes='ONE fixed57dayfreshaccountqualification; no tuning; all economicfunctionsidentical; no repeat')
 b.registry_update(claim);namespace.mkdir();(namespace/'tmp').mkdir()
 gate=dict(status='CLAIMED_BEFORE_POPEN',attempt_uuid=attempt,source_commit=COMMIT,config_sha256=EXPECTED,started_utc=b.now(),actual_native_child_pid=None,actual_native_child_exit=None,argv=c['argv'],cwd=c['cwd'],historical_attempt=8)
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
