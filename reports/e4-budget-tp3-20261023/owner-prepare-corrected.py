"""Prepare one exact BTC reporting correction; never launches or recovers a report."""
from pathlib import Path
import hashlib,json
R=Path(__file__).parent.resolve();J=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/e4-budget-tp3-20261023')
SOURCE=J/'source-6061446';COMMIT='6061446164cc32c27b3ea0e13e86c9cc56d955ac'
def read(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(8*1024*1024):h.update(b)
 return h.hexdigest()
old=read(J/'BTC/preparation.json');budget=read(R/'owner-run-budget.json')
assert budget['started']==2 and budget['completed']==2 and budget['current_engine'] is None
assert read(J/'BTC/completion.json')['exit_code']==1
for rel,pin in old['input_pins'].items():assert sha(SOURCE/rel if rel.startswith('runtime/') else Path(old['data_root'])/rel)==pin
pins={str(p.relative_to(SOURCE)):sha(p) for p in sorted(SOURCE.rglob('*')) if p.is_file()}
manifest=J/(SOURCE.name+'-sha256.json');write(manifest,pins)
for p in SOURCE.rglob('*'):
 if p.is_file():p.chmod(0o444)
name='BTC_CORRECTED';job=J/name;job.mkdir();(job/'tmp').mkdir()
prep=json.loads(json.dumps(old));prep.update(recipe=name,status='PREPARED_REPORT_PRECISION_CORRECTION_AWAIT_ROOT_GO',source_commit=COMMIT,source_snapshot=str(SOURCE),source_manifest_sha256=sha(manifest),cwd=str(SOURCE/'runtime'),stdout_stderr_log=str(job/'native.log'),artifact_dir=str(job/'result'),original_engine_source_commit=old['source_commit'],economic_config_unchanged=True)
prep['argv'][prep['argv'].index('--artifact-dir')+1]=prep['artifact_dir'];prep['timed_argv']=list(prep['argv'])
prep['env'].update(PYTHONPATH=str(SOURCE/'runtime'),TMPDIR=str(job/'tmp'))
write(job/'preparation.json',prep);write(job/'expected-config.json',read(J/'BTC/expected-config.json'))
budget.update(correction_source_commit=COMMIT,correction_recipe=name,stage='TWO_PHYSICAL_ATTEMPTS_COMPLETE_CORRECTED_BTC_PREPARED_AWAIT_ROOT_GO',remaining_physical_slots=2)
budget['attempts'][1]['state']='INVALID_REPORT_ASSERT_WITH_INCOMPLETE_EXPORT'
write(R/'owner-run-budget.json',budget)
meta=dict(source_commit=COMMIT,base_engine_source_commit=old['source_commit'],branch='codex/e4-budget-report-precision-20261023',source_snapshot=str(SOURCE),source_manifest_sha256=sha(manifest),files_sha256={str(p.resolve()):sha(p) for p in (R/'owner-prepare-corrected.py',R/'owner-runner.py',R/'owner-collect-native.py',R/'owner-report-precision-source.patch',R/'owner-report-precision-tests.log',job/'preparation.json',job/'expected-config.json')},source_pins=pins,prepared=prep,focused_tests='6 PASSED,17 DESELECTED',report_guard='LOCAL_DECIMAL80_UNCHANGED_1E-24_THRESHOLD_NO_MONETARY_ENGINE_CHANGE',new_historical_engines=0,physical_attempts_already_consumed=2,aborted_recovery='NO_HELPER_EXECUTED_NO_RAW_OR_GZIP_MODIFIED_NO_RECOVERED_REPORT')
write(R/'owner-correction-source-preparation.json',meta);write(R/'owner-correction-tooling-freeze.json',{k:v for k,v in meta.items() if k not in ('source_pins','prepared')})
print(json.dumps(dict(source=COMMIT,manifest=sha(manifest),recipe=name,config=prep['expected_config_sha256'],full_engines=0,consumed=2)))
