"""Prepare immutable native jobs only. No engine launch."""
import hashlib,json,shutil
from pathlib import Path
R=Path(__file__).parent.resolve();ROOT=Path('/Users/vf/Documents/ChatGPT/Coinmaster')
J=ROOT/'runtime/var/research-jobs/e4-sol-residual-20261023'
PREV=ROOT/'runtime/var/research-jobs/b-50-90-next-20261023'
SOURCE=J/'source-5bb4939';COMMIT='5bb4939c2adbcfcabf835b9e2ed97634f6fba4da'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(8*1024*1024):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
old=read(PREV/'XS/preparation.json')
oldresult=read(PREV/'XS/completion.json')
base=read(Path(oldresult['artifact']));DATA=Path(old['data_root'])
for rel in old['input_pins']:
 if rel.startswith('runtime/'):
  dest=SOURCE/rel;dest.parent.mkdir(parents=True,exist_ok=True)
  shutil.copyfile(Path(old['source_snapshot'])/rel,dest)
pins={str(p.relative_to(SOURCE)):sha(p) for p in sorted(SOURCE.rglob('*')) if p.is_file()}
for p in SOURCE.rglob('*'):
 if p.is_file():p.chmod(0o444)
write(J/'source-5bb4939-sha256.json',pins)
for rel,pin in old['input_pins'].items():assert sha(SOURCE/rel if rel.startswith('runtime/') else DATA/rel)==pin,rel
jobs=[]
for name,flags in {'P0':[],'R1':['--research-sol-residual'],'R2':['--research-sol-residual','--research-sol-minute']}.items():
 job=J/name;job.mkdir(exist_ok=True);(job/'tmp').mkdir(exist_ok=True)
 artifact=job/'result';assert not artifact.exists()
 argv=list(old['argv']);argv[argv.index('--artifact-dir')+1]=str(artifact);argv+=flags
 env=dict(old['env']);env.update(PYTHONPATH=str(SOURCE/'runtime'),TMPDIR=str(job/'tmp'))
 config=json.loads(json.dumps(base['config']))
 if flags:config['next_band_research'].update(sol_residual=True,sol_minute='--research-sol-minute' in flags)
 digest=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 if name=='P0':assert digest==base['config_hash']
 prep=dict(recipe=name,status='PREPARED_NO_ENGINE_AWAIT_REVIEW_AND_ROOT_GO',source_commit=COMMIT,source_snapshot=str(SOURCE),source_manifest_sha256=sha(J/'source-5bb4939-sha256.json'),source_files_read_only=True,data_root=str(DATA),input_pins=old['input_pins'],argv=argv,timed_argv=argv,cwd=str(SOURCE/'runtime'),env=env,stdout_stderr_log=str(job/'native.log'),artifact_dir=str(artifact),expected_config_sha256=digest,full_run_started=False)
 write(job/'preparation.json',prep);write(job/'expected-config.json',config);jobs.append(prep)
write(R/'owner-run-preparation.json',dict(source_commit=COMMIT,source_snapshot=str(SOURCE),source_files_readonly=True,source_pins=pins,jobs=jobs,full_native_runs=0,old_XS_artifact=oldresult['artifact'],authorization='PREPARE_ONLY_ROOT_GO_REQUIRED'))
ledger=R/'owner-run-budget.json'
assert not ledger.exists()
write(ledger,dict(schema='E4_SOL_RESIDUAL_PHYSICAL_ATTEMPTS_V1',source_commit=COMMIT,max_main=4,max_conditional=0,conditional_authorized=0,completed=0,started=0,reserved=0,current_engine=None,attempts=[],go_required=True,stage='PREPARED_NO_ENGINE',repeat_rule='AT_MOST_ONE_FRESH_REPEAT_ONLY_AFTER_VALID_50_90_CANDIDATE_AND_SEPARATE_ROOT_GO'))
print(json.dumps(dict(source=COMMIT,source_files=len(pins),prepared=[p['recipe'] for p in jobs],full_engines=0)))
