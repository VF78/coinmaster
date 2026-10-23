"""Prepare immutable native jobs and exact arguments, never start an engine."""
import hashlib,json,os,shutil
from pathlib import Path
R=Path(__file__).parent.resolve();ROOT=Path('/Users/vf/Documents/ChatGPT/Coinmaster');OLD=R.parent/'sol-conditional-hedge-btc-band-20261023';PREV=ROOT/'runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023';J=ROOT/'runtime/var/research-jobs/b-50-90-next-20261023';SOURCE=J/'source-bd04c9b';COMMIT='bd04c9b3858bcda40060a08eff488849c69af5d8';PYTHON=ROOT/'runtime/.venv/bin/python'
oldprep=json.load((OLD/'owner-run-preparation.json').open())['jobs'][0];baseexec=json.load((OLD/'owner-BTC_REGIME_REENTRY_BAND_05-execution.json').open());oldartifact=next((PREV/'BTC_REGIME_REENTRY_BAND_05/result').glob('v0*.json'));base=json.load(oldartifact.open());DATA=PREV/'inputs/data'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(8*1024*1024):h.update(b)
 return h.hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
for rel in ['runtime/var/venue-manifest.json','runtime/var/raw/venues/bybit-BTCUSDT-risk-limit.json','runtime/var/raw/venues/bybit-SOLUSDT-risk-limit.json']:
 dest=SOURCE/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(PREV/'source-25a085f'/rel,dest)
sourcepins={str(p.relative_to(SOURCE)):sha(p) for p in sorted(SOURCE.rglob('*')) if p.is_file()}
for p in SOURCE.rglob('*'):
 if p.is_file():p.chmod(0o444)
write(J/'source-bd04c9b-sha256.json',sourcepins)
inputpins=oldprep['input_pins']
for rel,pin in inputpins.items():
 actual=SOURCE/rel if rel.startswith('runtime/') else DATA/rel
 assert sha(actual)==pin,(rel,'PIN_MISMATCH')
recipes={'P0':[], 'E4':['--research-wait-4h'], 'EP':['--research-wait-persist'], 'Z':['--research-zero-retrace'], 'S':['--research-sol-dominant']}
jobs=[]
for recipe,flags in recipes.items():
 job=J/recipe;job.mkdir(exist_ok=True);(job/'tmp').mkdir(exist_ok=True);artifact=job/'result';assert not artifact.exists(),artifact
 argv=list(baseexec['argv']);argv[0]=str(PYTHON);idx=argv.index('--artifact-dir');argv[idx+1]=str(artifact);argv.extend(flags)
 env=dict(oldprep['env']);env['PYTHONPATH']=str(SOURCE/'runtime');env['TMPDIR']=str(job/'tmp')
 config=json.loads(json.dumps(base['config']))
 if flags:
  config['next_band_research']=dict(wait_4h='--research-wait-4h' in flags,wait_persist='--research-wait-persist' in flags,zero_retrace='--research-zero-retrace' in flags,sol_dominant='--research-sol-dominant' in flags,bar_contract='PINNED_CLOSED_OHLC_D1_BEFORE_INTRADAY_QUOTE')
 digest=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 if recipe=='P0':assert digest==base['config_hash']
 prep=dict(recipe=recipe,status='PREPARED_NO_ENGINE_AWAIT_INDEPENDENT_REVIEW_AND_ROOT_GO',source_commit=COMMIT,source_snapshot=str(SOURCE),source_manifest_sha256=sha(J/'source-bd04c9b-sha256.json'),source_files_read_only=True,data_root=str(DATA),input_pins=inputpins,argv=argv,timed_argv=['/usr/bin/time','-l',*argv],cwd=str(SOURCE/'runtime'),env=env,stdout_stderr_log=str(job/'native.log'),artifact_dir=str(artifact),artifact_dir_exists=False,expected_config_sha256=digest,full_run_started=False)
 write(job/'preparation.json',prep);write(job/'expected-config.json',config);jobs.append(prep)
write(R/'owner-run-preparation.json',dict(source_commit=COMMIT,source_snapshot=str(SOURCE),source_edit='NONE_READONLY_CANONICAL_GIT_ARCHIVE_EXECUTION_MIRROR',source_sha256=sourcepins,source_manifest_sha256=sha(J/'source-bd04c9b-sha256.json'),input_pins=inputpins,jobs=jobs,combinations='E_STAR_SELECTION_REQUIRED_XZ_XS_XZS_NOT_PRESELECTED',full_native_runs=0,authorization='PREPARE_ONLY_AWAIT_REVIEW_AND_ROOT_GO'))
ledger=R/'owner-run-budget.json'
if not ledger.exists():write(ledger,dict(schema='B_50_90_NEXT_PHYSICAL_ATTEMPTS_V1',source_commit=COMMIT,max_main=8,max_conditional=4,conditional_authorized=0,completed=0,started=0,reserved=0,current_engine=None,attempts=[],execution_ledger_owner='h4_band_owner',go_required=True,stage='PREPARED_NO_ENGINE'))
print(json.dumps(dict(source_snapshot=str(SOURCE),source_files=len(sourcepins),input_pins=len(inputpins),recipes={x['recipe']:x['expected_config_sha256'] for x in jobs},full_runs=0),indent=2))
