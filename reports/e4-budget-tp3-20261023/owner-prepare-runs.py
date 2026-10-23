"""Prepare frozen recipes without launching engines or refreshing old controls."""
from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).parent.resolve();ROOT=Path('/Users/vf/Documents/ChatGPT/Coinmaster')
J=ROOT/'runtime/var/research-jobs/e4-budget-tp3-20261023'
OLD=ROOT/'runtime/var/research-jobs/b-50-90-next-20261023'
def read(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(8*1024*1024):h.update(b)
 return h.hexdigest()
identity=read(R/'owner-source-preparation.json');commit=identity['source_commit'];source=Path(identity['source_snapshot'])
old=read(OLD/'E4/preparation.json');done=read(OLD/'E4/completion.json');base=read(Path(done['artifact']));data=Path(old['data_root'])
assert not (R/'owner-run-budget.json').exists()
for rel,pin in old['input_pins'].items():assert sha(source/rel if rel.startswith('runtime/') else data/rel)==pin,rel
pins={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
manifest=J/(source.name+'-sha256.json');write(manifest,pins)
for p in source.rglob('*'):
 if p.is_file():p.chmod(0o444)
jobs=[]
for name,flags in {'SOL':['--research-sol-budget'],'BTC':['--research-btc-early-tp3'],'COMBINED':['--research-sol-budget','--research-btc-early-tp3']}.items():
 job=J/name;job.mkdir();(job/'tmp').mkdir();artifact=job/'result'
 argv=list(old['argv']);argv[argv.index('--artifact-dir')+1]=str(artifact);argv+=flags
 env=dict(old['env']);env.update(PYTHONPATH=str(source/'runtime'),TMPDIR=str(job/'tmp'))
 config=json.loads(json.dumps(base['config']))
 config['budget_tp3_research']=dict(sol_budget=name!='BTC',btc_early_tp3=name!='SOL',sol_policy='DD35_WARN45_CLOSED_D1_WILDER14_ATR1_GROSS_BTC_RESERVE_SOL_DOMINANT_ONCE_ACTUAL_CYCLE_ORIGINAL_FULL_ADD_BUDGET',btc_policy='SEQUENTIAL_TP3_20PCT_ACTUAL_INITIAL_PLANREF1PCT_ORIGINAL_LOTS_PROPORTIONAL_ACTUAL_RIGHTS')
 digest=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 prep=dict(recipe=name,status='PREPARED_NO_ENGINE_AWAIT_ROOT_GO',source_commit=commit,source_snapshot=str(source),source_manifest_sha256=sha(manifest),source_files_read_only=True,data_root=str(data),input_pins=old['input_pins'],argv=argv,timed_argv=argv,cwd=str(source/'runtime'),env=env,stdout_stderr_log=str(job/'native.log'),artifact_dir=str(artifact),expected_config_sha256=digest,full_run_started=False,protocol_sha256=sha(R/'protocol-freeze.json'))
 write(job/'preparation.json',prep);write(job/'expected-config.json',config);jobs.append(prep)
write(R/'owner-run-preparation.json',dict(source_commit=commit,source_snapshot=str(source),source_pins=pins,jobs=jobs,full_native_runs=0,archived_control=done['artifact'],authorization='PREPARE_ONLY_ROOT_GO_REQUIRED'))
write(R/'owner-run-budget.json',dict(schema='E4_BUDGET_TP3_PHYSICAL_ATTEMPTS_V1',source_commit=commit,max_main=4,max_conditional=0,conditional_authorized=0,completed=0,started=0,reserved=0,current_engine=None,attempts=[],go_required=True,stage='PREPARED_NO_ENGINE',repeat_rule='CONDITIONAL_EXACT_NEW_JOURNAL_REPEAT_ONLY_AFTER_VALID_50_90_AND_ROOT_GO'))
print(json.dumps(dict(source=commit,prepared=[p['recipe'] for p in jobs],source_files=len(pins),full_engines=0)))
