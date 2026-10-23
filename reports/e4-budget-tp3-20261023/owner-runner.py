"""One explicit GO + one prepared recipe per invocation. No automatic reruns/grid."""
import argparse,fcntl,hashlib,json,os,re,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).parent.resolve();J=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/e4-budget-tp3-20261023')
def read(p):return json.loads(p.read_text())
def write(p,x):
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n');tmp.replace(p)
def utc():return datetime.now(timezone.utc).isoformat()
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(8*1024*1024):h.update(b)
 return h.hexdigest()
p=argparse.ArgumentParser();p.add_argument('recipe');p.add_argument('--go',type=Path,required=True);a=p.parse_args()
prep=read(J/a.recipe/'preparation.json');go=read(a.go);assert go['source_commit']==prep['source_commit'];assert a.recipe in go['authorized_recipes']
assert sha(R/'protocol-freeze.json')==prep['protocol_sha256']==go['protocol_sha256'],'PROTOCOL_FREEZE_DRIFT'
assert prep['source_manifest_sha256']==go['source_manifest_sha256'],'GO_SOURCE_MANIFEST_MISMATCH'
lock=(J/'native-engine.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
bpath=R/'owner-run-budget.json';b=read(bpath);assert b['current_engine'] is None;assert not any(x['recipe']==a.recipe for x in b['attempts']),'REPEAT_NOT_AUTHORIZED'
assert len(b['attempts'])<b['max_main'],'MAIN_BUDGET_EXHAUSTED'
artifactdir=Path(prep['artifact_dir']);assert not artifactdir.exists(),'RESULT_NAMESPACE_MUST_NOT_EXIST'
source=Path(prep['source_snapshot']);pins=read(J/('source-'+source.name.removeprefix('source-')+'-sha256.json'))
for rel,pin in pins.items():assert sha(source/rel)==pin,(rel,'SOURCE_DRIFT')
for rel,pin in prep['input_pins'].items():assert sha(source/rel if rel.startswith('runtime/') else Path(prep['data_root'])/rel)==pin,(rel,'INPUT_DRIFT')
start=utc();attempt=dict(recipe=a.recipe,started_utc=start,state='STARTING_EXPLICIT_NATIVE_ATTEMPT',source_commit=prep['source_commit'],go=str(a.go),go_sha256=sha(a.go),argv=prep['argv'],timed_argv=prep['timed_argv'],expected_config_sha256=prep['expected_config_sha256'],artifact_dir=str(artifactdir))
b['attempts'].append(attempt);b['started']=len(b['attempts']);b['current_engine']=dict(recipe=a.recipe,state='STARTING',pid=None);b['stage']='RUNNING_EXPLICIT_GO';write(bpath,b)
t0=time.monotonic();log=Path(prep['stdout_stderr_log'])
with log.open('x') as out:
 process=subprocess.Popen(prep['timed_argv'],cwd=prep['cwd'],env=prep['env'],stdout=out,stderr=subprocess.STDOUT)
 attempt['pid']=process.pid;b['current_engine']['pid']=process.pid;attempt['state']='RUNNING';write(bpath,b)
 write(J/a.recipe/'start.json',attempt)
 code=process.wait()
wall=time.monotonic()-t0;txt=log.read_text(errors='replace');rss=re.search(r'^\s*(\d+)\s+maximum resident set size',txt,re.M);times=re.search(r'([\d.]+)\s+real\s+([\d.]+)\s+user\s+([\d.]+)\s+sys',txt)
resources=dict(elapsed_monotonic_seconds=wall,time_real_seconds=float(times[1]) if times else None,user_seconds=float(times[2]) if times else None,system_seconds=float(times[3]) if times else None,maximum_resident_set_size_bytes=int(rss[1]) if rss else None,resource_log=str(log),wrapper_exit_code=code)
artifacts=[x for x in artifactdir.glob('v0*.json') if not x.name.endswith('-raw-native.json')] if artifactdir.exists() else []
completion=dict(recipe=a.recipe,source_commit=prep['source_commit'],finished_utc=utc(),exit_code=code,resources=resources,artifact=str(artifacts[0]) if len(artifacts)==1 else None,log=str(log),log_sha256=sha(log),state='COMPLETED_PENDING_COLLECTION' if len(artifacts)==1 else 'FAILED_NATIVE_ATTEMPT_NO_SINGULAR_RESULT')
if len(artifacts)==1:
 result=read(artifacts[0]);completion.update(native_status=result.get('status'),total=result.get('terminal_total'),config_sha256=result.get('config_hash'),config_exact=result.get('config_hash')==prep['expected_config_sha256'])
write(J/a.recipe/'completion.json',completion);write(R/('owner-'+a.recipe+'-execution.json'),completion)
attempt.update(state=completion['state'],finished_utc=completion['finished_utc'],exit_code=code,completion=str(J/a.recipe/'completion.json'));b['completed']+=1;b['current_engine']=None;b['stage']='COMPLETED_AWAIT_COLLECTION_NEXT_EXPLICIT_GO';write(bpath,b)
print(json.dumps(completion,indent=2))
