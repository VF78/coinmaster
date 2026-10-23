"""Frozen canonical source copy + ONE explicit C1 recipe; never starts engine."""
from pathlib import Path
import hashlib,json,shutil,tarfile
ROOT=Path('/Users/vf/Documents/ChatGPT/Coinmaster');R=Path(__file__).resolve().parent
J=ROOT/'runtime/var/research-jobs/residual-recovery-20261023';commit='78100d4d69a12144a92dbb9a713b7a7f7ce2f54d'
source=J/('source-'+commit[:7]);oldsource=ROOT/'runtime/var/research-jobs/b-50-90-next-20261023/source-bd04c9b'
def read(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(8*1024*1024):h.update(b)
 return h.hexdigest()
assert not source.exists();J.mkdir(exist_ok=True);shutil.copytree(oldsource,source)
with tarfile.open('/private/tmp/coinmaster-c1-source-delta.tar') as t:
 for member in t.getmembers():
  assert (member.name.startswith('runtime/') or (member.name=='runtime' and member.isdir())) and '..' not in Path(member.name).parts and not member.issym() and not member.islnk()
  target=source/member.name
  if target.exists() and target.is_file():target.chmod(0o644)
 t.extractall(source)
old=read(ROOT/'runtime/var/research-jobs/b-50-90-next-20261023/E4/preparation.json');base=read(Path(read(ROOT/'runtime/var/research-jobs/b-50-90-next-20261023/E4/completion.json')['artifact']))
for rel,pin in old['input_pins'].items():assert sha(source/rel if rel.startswith('runtime/') else Path(old['data_root'])/rel)==pin,rel
pins={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
manifest=J/(source.name+'-sha256.json');write(manifest,pins)
for p in source.rglob('*'):
 if p.is_file():p.chmod(0o444)
job=J/'C1';job.mkdir();(job/'tmp').mkdir();artifact=job/'result';assert not artifact.exists()
argv=list(old['argv']);argv[argv.index('--artifact-dir')+1]=str(artifact);argv+=['--research-residual-recovery']
env=dict(old['env']);env.update(PYTHONPATH=str(source/'runtime'),TMPDIR=str(job/'tmp'))
config=json.loads(json.dumps(base['config']));config['residual_recovery_research']=dict(version='C1',trigger_DD='0.40',open_loss_dominates_remaining_50_cushion=True,cut_fraction='0.50',restore_DD='0.35',restore_closed_hours=4,max_cut_restore_per_group=1)
expected=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest()
prep=dict(recipe='C1',status='PREPARED_NO_ENGINE_AWAIT_ROOT_GO',source_commit=commit,source_snapshot=str(source),source_manifest_sha256=sha(manifest),source_files_read_only=True,data_root=old['data_root'],input_pins=old['input_pins'],argv=argv,timed_argv=['/usr/bin/time','-l',*argv],cwd=str(source/'runtime'),env=env,stdout_stderr_log=str(job/'native.log'),artifact_dir=str(artifact),expected_config_sha256=expected,full_run_started=False,protocol_sha256=sha(R/'protocol-rule-freeze.json'),contract_sha256=sha(R/'owner-contract.md'),expected_settled_receipts=1051199,expected_source_rows_each=1051200,engine='SOLE_NATIVE_NAUTILUS',fresh_journal_namespace=str(artifact),target_windows_UTC=read(R/'protocol-rule-freeze.json')['target_windows_UTC'])
write(job/'preparation.json',prep);write(job/'expected-config.json',config)
changed=['runtime/coinmaster/research/minute_risk.py','runtime/coinmaster/research/native_baseline.py','runtime/coinmaster/strategy/next_band.py','runtime/coinmaster/strategy/residual_recovery.py','runtime/coinmaster/strategy/wave_overlay.py','runtime/tests/test_native_report_precision.py','runtime/tests/test_native_residual_recovery.py']
identity=dict(status='SOURCE_FROZEN_REVIEW_READY_NO_ENGINE',base_commit='bd04c9b3858bcda40060a08eff488849c69af5d8',report_precision_provenance='6061446164cc32c27b3ea0e13e86c9cc56d955ac',source_commit=commit,branch='codex/residual-recovery-20261023',checkout='/root/.openclaw/workspace/coinmaster/coinmaster/research-worktrees/residual-recovery-20261023',source_snapshot=str(source),source_files={p:pins[p] for p in changed},source_manifest=str(manifest),source_manifest_sha256=sha(manifest),source_file_count=len(pins),source_archive_sha256=sha(Path('/private/tmp/coinmaster-c1-source-delta.tar')),source_bundle='/private/tmp/coinmaster-residual-recovery-20261023.bundle',source_bundle_sha256=sha(Path('/private/tmp/coinmaster-residual-recovery-20261023.bundle')),source_patch_sha256=sha(R/'owner-source.patch'),tested_canonical_source=True,source_changes_canonical_VPS_only=True,full_native_engines_started=0,pilot_touched=False,test_result=dict(relevant_suite_pass=206,documented_inherited_E4_clock_deselections=2,final_focused_pass=18,last_flat_guard_delta_pass=3,diff_check='PASS'))
write(R/'owner-source-preparation.json',identity)
write(R/'owner-run-preparation.json',dict(source_commit=commit,source_snapshot=str(source),source_pins=pins,jobs=[prep],full_native_runs=0,archived_control=read(ROOT/'runtime/var/research-jobs/b-50-90-next-20261023/E4/completion.json')['artifact'],authorization='PREPARE_ONLY_ROOT_ENGINE_GO_REQUIRED',protocol_sha256=prep['protocol_sha256']))
print(json.dumps(dict(source=commit,source_files=len(pins),changed_files=identity['source_files'],expected_config_sha256=expected,prepared='C1',engines=0),indent=2))
