from pathlib import Path
from datetime import datetime,timezone
import sys,json,subprocess,hashlib,re,fcntl,time
report=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021/reports/sol-conditional-hedge-btc-band-20261023')
base=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023')
recipe=sys.argv[1]
assert recipe in ('C0','H4_4H_E34_G050')
def save(path,data):
    tmp=path.with_name(path.name+'.owner-tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)
def utc():return datetime.now(timezone.utc).isoformat()
lock=(base/'.native-owner.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
go=json.loads((report/'native-first-two-go.json').read_text());prep=json.loads((base/recipe/'preparation.json').read_text());budgetpath=report/'run-budget.json';b=json.loads(budgetpath.read_text())
assert go['decision']=='GO_C0_THEN_H4_E34_G050_ONLY' and prep['source_commit']==go['source_commit']
assert b['execution_ledger_owner']=='h4_band_owner' and b['current_engine'] is None and b['physical_full_runs_completed']<b['max_full_runs']
assert not any(x.get('recipe')==recipe for x in b['attempts']),recipe
if recipe.startswith('H4'):
    prior=[x for x in b['attempts'] if x.get('recipe')=='C0'];assert len(prior)==1 and prior[0]['state'].startswith('COMPLETED'),prior
assert not Path(prep['artifact_dir']).exists()
source=Path(prep['source_snapshot']);hashes=json.loads((base/'source-25a085f-sha256.json').read_text())
for name,digest in hashes.items():assert hashlib.sha256((source/name).read_bytes()).hexdigest()==digest,name
for name,digest in prep['input_pins'].items():
    path=source/name if name.startswith('runtime/') else Path(prep['data_root'])/name
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
runid=recipe+'_MAC_1';attempt=dict(attempt=runid,recipe=recipe,state='RUNNING',utc=utc(),source=prep['source_commit'],go_sha256=hashlib.sha256((report/'native-first-two-go.json').read_bytes()).hexdigest(),artifact_dir=prep['artifact_dir'],argv=prep['argv'],cwd=prep['cwd'],env=prep['env'],expected_config_sha256=prep['expected_config_sha256'])
b['attempts'].append(attempt);b['current_engine']=runid;b['full_runs_reserved']=1;save(budgetpath,b)
log=Path(prep['stdout_stderr_log']);assert not log.exists()
start=time.monotonic()
with log.open('w') as handle:
    p=subprocess.Popen(prep['timed_argv'],cwd=prep['cwd'],env=prep['env'],stdout=handle,stderr=subprocess.STDOUT)
    attempt['timed_process_pid']=p.pid;save(budgetpath,b)
    print(json.dumps(dict(event='STARTED',recipe=recipe,pid=p.pid,source=prep['source_commit'],artifact_dir=prep['artifact_dir'])),flush=True)
    rc=p.wait()
attempt.update(exit_code=rc,finished_utc=utc(),elapsed_monotonic_seconds=time.monotonic()-start,log=str(log),log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
text=log.read_text(errors='replace')
match=re.search(r'([\d.]+) real\s+([\d.]+) user\s+([\d.]+) sys',text)
resources=dict(wall_seconds=float(match[1]),user_CPU_seconds=float(match[2]),system_CPU_seconds=float(match[3])) if match else {}
m=re.search(r'(\d+)\s+maximum resident set size',text)
if m:resources['max_RSS_bytes']=int(m[1])
attempt['resources']=resources
files=[]
for path in Path(prep['artifact_dir']).glob('*.json'):
    if path.name.endswith('-raw-native.json') or path.name=='minute-risk-summary.json':continue
    d=json.loads(path.read_text())
    if 'terminal_total' in d and 'config_hash' in d:files.append((path,d))
if rc==0 and len(files)==1:
    path,result=files[0];attempt.update(state='COMPLETED_PENDING_LIFECYCLE_REVIEW',artifact=str(path),artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),full_24m_completed=result.get('streaming',{}).get('processed_rows_per_source')==1051200,actual_config_sha256=result['config_hash'],config_matches_preparation=result['config_hash']==prep['expected_config_sha256'],terminal_total=result['terminal_total'],fills=result['fills'],native_fees=result['native_fees'],terminal_open_positions=result['terminal_open_positions'])
else:
    attempt.update(state='FAILED_NEEDS_CLASSIFICATION',full_24m_completed=False,result_candidates=len(files),log_tail=text[-2000:])
# Every attempted candidate consumes a conservative budget slot, including INVALID.
b['physical_full_runs_completed']+=1;b['full_runs_reserved']=0;b['current_engine']=None;save(budgetpath,b)
save(base/recipe/'completion.json',attempt);save(report/('owner-'+recipe+'-execution.json'),attempt)
print(json.dumps(dict(event='FINISHED',recipe=recipe,exit_code=rc,state=attempt['state'],resources=resources,budget_completed=b['physical_full_runs_completed'],terminal_total=attempt.get('terminal_total'),config_match=attempt.get('config_matches_preparation'))),flush=True)
