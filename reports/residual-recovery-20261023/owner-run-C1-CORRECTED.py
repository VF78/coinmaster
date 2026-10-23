"""Exactly one root-reserved physical native attempt. No retry, repair or repeat."""
import fcntl,hashlib,json,os,re,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parent;J=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/residual-recovery-20261023');job=J/'C1_CORRECTED'
def read(p):return json.loads(p.read_text())
def utc():return datetime.now(timezone.utc).isoformat()
def write(p,x):
 t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,indent=2)+'\n');os.replace(t,p)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(8*1024*1024):h.update(b)
 return h.hexdigest()
lock=(J/'native-engine.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
go=read(R/'root-C1-CORRECTED-engine-go.json');prep=read(job/'preparation.json');ledger=read(R/'root-launch-budget.json')
assert go['decision']=='GO_ONE_C1_CORRECTED_PHYSICAL_ATTEMPT2_ONLY' and go['expected_next_attempt']==2
assert sha(R/'protocol-freeze.json')==go['protocol_sha256']
assert sha(R/'protocol-serialization-amendment.json')==go['correction_amendment_sha256']
assert sha(R/'protocol-rule-freeze.json')==prep['rule_freeze_sha256']
assert prep['original_protocol_sha256']==go['protocol_sha256']
assert prep['source_commit']==go['source_commit'] and prep['expected_config_sha256']==go['expected_config_sha256']
manifest=J/(Path(prep['source_snapshot']).name+'-sha256.json');assert sha(manifest)==prep['source_manifest_sha256']==go['source_manifest_sha256']
source=Path(prep['source_snapshot'])
for rel,pin in read(manifest).items():
 p=source/rel;assert sha(p)==pin and not(p.stat().st_mode&0o222),rel
for rel,pin in prep['input_pins'].items():assert sha(source/rel if rel.startswith('runtime/') else Path(prep['data_root'])/rel)==pin,rel
assert ledger['started']==1 and ledger['active']==0 and ledger['reserved']==1
assert len(ledger['engines'])==2 and ledger['engines'][1]['status']=='RESERVED_NOT_STARTED'
assert ledger['engines'][1]['GO_sha256']==sha(R/'root-C1-CORRECTED-engine-go.json')
artifact=Path(prep['artifact_dir']);log=Path(prep['stdout_stderr_log']);assert not artifact.exists() and not log.exists()
start=dict(candidate='C1_CORRECTED',attempt=2,started_utc=utc(),state='STARTING_EXPLICIT_ROOT_GO',source_commit=prep['source_commit'],go_sha256=sha(R/'root-C1-CORRECTED-engine-go.json'),protocol_sha256=go['protocol_sha256'],source_manifest_sha256=prep['source_manifest_sha256'],argv=prep['argv'],timed_argv=prep['timed_argv'],cwd=prep['cwd'],env=prep['env'],artifact_dir=str(artifact),log=str(log),expected_config_sha256=prep['expected_config_sha256'],pid=None)
ledger.update(started=2,active=1,reserved=0,status='C1_CORRECTED_ATTEMPT2_STARTING_COUNTED_BEFORE_POPEN');ledger['engines'][1].update(status=start['state'],started_utc=start['started_utc'],pid=None)
write(R/'root-launch-budget.json',ledger);write(job/'start.json',start);write(R/'owner-C1-CORRECTED-start.json',start)
t0=time.monotonic();error=None;code=None
try:
 with log.open('x') as out:
  process=subprocess.Popen(prep['timed_argv'],cwd=prep['cwd'],env=prep['env'],stdout=out,stderr=subprocess.STDOUT)
  start.update(state='RUNNING',pid=process.pid);ledger['engines'][1].update(status='RUNNING',pid=process.pid);ledger['status']='C1_CORRECTED_ATTEMPT2_RUNNING'
  write(job/'start.json',start);write(R/'owner-C1-CORRECTED-start.json',start);write(R/'root-launch-budget.json',ledger)
  print(json.dumps(dict(state='RUNNING',attempt=2,pid=process.pid,started_utc=start['started_utc'])),flush=True)
  code=process.wait()
except BaseException as exc:error=repr(exc)
wall=time.monotonic()-t0;txt=log.read_text(errors='replace') if log.exists() else '';rss=re.search(r'^\s*(\d+)\s+maximum resident set size',txt,re.M);times=re.search(r'([\d.]+)\s+real\s+([\d.]+)\s+user\s+([\d.]+)\s+sys',txt)
files=[p for p in artifact.glob('v0*.json') if not p.name.endswith('-raw-native.json')] if artifact.exists() else []
done=dict(candidate='C1_CORRECTED',attempt=2,source_commit=prep['source_commit'],started_utc=start['started_utc'],finished_utc=utc(),exit_code=code,error=error,elapsed_monotonic_seconds=wall,pid=start['pid'],log=str(log),log_sha256=sha(log) if log.exists() else None,artifact=str(files[0]) if len(files)==1 else None,normal_complete=code==0 and len(files)==1,state='COMPLETED_AWAIT_INDEPENDENT_AUDIT' if code==0 and len(files)==1 else 'FAILED_PHYSICAL_ATTEMPT_PRESERVE_ALL_NO_RETRY',resources=dict(time_real_seconds=float(times[1]) if times else None,user_seconds=float(times[2]) if times else None,system_seconds=float(times[3]) if times else None,maximum_resident_set_size_bytes=int(rss[1]) if rss else None))
if done['normal_complete']:
 result=read(files[0]);done.update(artifact_sha256=sha(files[0]),artifact_bytes=files[0].stat().st_size,total=result.get('terminal_total'),config_sha256=result.get('config_hash'),config_exact=result.get('config_hash')==prep['expected_config_sha256'],native_fees=result.get('native_fees'),fills=result.get('fills'),liquidation_count=result.get('liquidation_count'),terminal_open_positions=result.get('terminal_open_positions'),c1_terminal_state=result.get('c1_terminal_state'),c1_events=len(result.get('c1_audit',[])),settled=result.get('minute_risk_observations',{}).get('settled_native_close_receipts'))
write(job/'completion.json',done);write(R/'owner-C1-CORRECTED-execution.json',done)
ledger=read(R/'root-launch-budget.json');assert ledger['started']==2 and ledger['active']==1
ledger.update(active=0,completed=2,reserved=0,status=done['state']);ledger['engines'][1].update(status=done['state'],finished_utc=done['finished_utc'],exit_code=code,completion=str(job/'completion.json'));write(R/'root-launch-budget.json',ledger)
print(json.dumps(done,indent=2),flush=True)
