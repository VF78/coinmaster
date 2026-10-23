"""Single physical native attempt per explicit root GO. No automatic next run."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,hashlib,subprocess,time,fcntl
R=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021/reports/system-contract-repair-20261023')
J=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/system-contract-repair-20261023')
def read(p):return json.loads(p.read_text())
def write(p,x):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2)+'\n');t.replace(p)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
p=argparse.ArgumentParser();p.add_argument('recipe');p.add_argument('--go',type=Path,required=True);p.add_argument('--preparation',type=Path,required=True);a=p.parse_args()
g=read(a.go);prep=read(a.preparation);assert a.recipe in g['authorized_recipes'];assert prep['recipe']==a.recipe
assert sha(a.preparation)==g['preparation_sha256'];assert sha(R/'protocol.json')==g['protocol_sha256']
assert prep['source_commit']==g['source_commit'] and prep['source_manifest_sha256']==g['source_manifest_sha256']
s=Path(prep['source_snapshot']);mf=J/(s.name+'-sha256.json');assert sha(mf)==prep['source_manifest_sha256']
for rel,pin in read(mf).items():assert sha(s/rel)==pin,('SOURCE_DRIFT',rel)
for rel,pin in prep['input_pins'].items():assert sha(s/rel if rel.startswith('runtime/') else Path(prep['data_root'])/rel)==pin,('INPUT_DRIFT',rel)
lock=(J.parent/'coinmaster-full-native.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
lp=R/'run-ledger.json';b=read(lp);assert b['active']==0 and b['started']<b['physical_full_attempt_cap'];assert b['started']+1==g['physical_attempt']
assert not any(t['recipe']==a.recipe for t in b['attempts']);art=Path(prep['artifact_dir']);assert not art.exists()
log=Path(prep['stdout_stderr_log']);assert not log.exists()
t={'attempt':g['physical_attempt'],'recipe':a.recipe,'state':'STARTING','started_utc':utc(),'source_commit':prep['source_commit'],'config_sha256':prep['expected_config_sha256'],'go_sha256':sha(a.go),'artifact_dir':str(art),'log':str(log),'argv':prep['argv'],'pid':None}
b['attempts'].append(t);b['started']+=1;b['active']=1;b['status']='RUNNING_EXPLICIT_ROOT_GO';write(lp,b)
t0=time.monotonic();code=None;error=None
try:
 with log.open('x') as out:
  q=subprocess.Popen(prep['argv'],cwd=prep['cwd'],env=prep['env'],stdout=out,stderr=subprocess.STDOUT)
  t['pid']=q.pid;t['state']='RUNNING';write(lp,b);write(J/a.recipe/'start.json',t);code=q.wait()
except Exception as e:error=type(e).__name__+':'+str(e)
files=[x for x in art.glob('v0*.json') if not x.name.endswith('-raw-native.json')] if art.exists() else []
c={'recipe':a.recipe,'finished_utc':utc(),'source_commit':prep['source_commit'],'native_process_exit_code':code,'error':error,'elapsed_monotonic_seconds':time.monotonic()-t0,'artifact':str(files[0]) if len(files)==1 else None,'log_sha256':sha(log) if log.exists() else None,'state':'COMPLETED_PENDING_INDEPENDENT_VALIDATION' if code==0 and len(files)==1 else 'INVALID_OR_FAILED_PHYSICAL_ATTEMPT'}
if len(files)==1:
 r=read(files[0]);c.update(total=r.get('terminal_total'),native_status=r.get('status'),config_sha256=r.get('config_hash'),config_exact=r.get('config_hash')==prep['expected_config_sha256'])
write(J/a.recipe/'completion.json',c);write(R/('execution-'+a.recipe+'.json'),c)
t.update(state=c['state'],finished_utc=c['finished_utc'],exit_code=code,elapsed_monotonic_seconds=c['elapsed_monotonic_seconds']);b['active']=0;b['completed']+=1;b['status']='AWAIT_INDEPENDENT_VALIDATION_NO_AUTOMATIC_NEXT';write(lp,b)
print(json.dumps(c,indent=2))
