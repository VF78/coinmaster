"""Prepare a fresh corrected namespace; original attempt and frozen files untouched."""
import json,hashlib,shutil,tarfile
from pathlib import Path
R=Path(__file__).resolve().parent;J=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/residual-recovery-20261023')
def read(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(8*1024*1024):h.update(b)
 return h.hexdigest()
frozen=['owner-source-preparation.json','owner-run-preparation.json','protocol-freeze.json','root-C1-engine-go.json'];before={p:sha(R/p) for p in frozen}
commit='78cb85aca1cf5c2e4455f5c5ddf02851cfb40076';old=read(J/'C1/preparation.json');source=J/'source-78cb85a';assert not source.exists();shutil.copytree(Path(old['source_snapshot']),source)
with tarfile.open('/private/tmp/coinmaster-c1-serialization-source-delta.tar') as t:
 for m in t.getmembers():
  assert (m.name.startswith('runtime/') or (m.name=='runtime' and m.isdir())) and '..' not in Path(m.name).parts and not m.issym() and not m.islnk()
  p=source/m.name
  if p.exists() and p.is_file():p.chmod(0o644)
 t.extractall(source)
pins={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file() and '__pycache__' not in p.parts};assert len(pins)==92
manifest=J/'source-78cb85a-sha256.json';write(manifest,pins)
for p in source.rglob('*'):
 if p.is_file():p.chmod(0o444)
for rel,pin in old['input_pins'].items():assert sha(source/rel if rel.startswith('runtime/') else Path(old['data_root'])/rel)==pin
job=J/'C1_CORRECTED';job.mkdir();(job/'tmp').mkdir();artifact=job/'result';assert not artifact.exists()
argv=list(old['argv']);argv[argv.index('--artifact-dir')+1]=str(artifact);env=dict(old['env']);env.update(PYTHONPATH=str(source/'runtime'),TMPDIR=str(job/'tmp'))
config=read(J/'C1/expected-config.json');expected=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest();assert expected==old['expected_config_sha256']=='405ab01b74eb459117dcbb340bc56ace4a1e6edc64290cb049d63695cae772b6'
prep={**old,'recipe':'C1_CORRECTED','status':'SERIALIZATION_ONLY_CORRECTION_PREPARED_NO_ENGINE','source_commit':commit,'source_snapshot':str(source),'source_manifest_sha256':sha(manifest),'argv':argv,'timed_argv':['/usr/bin/time','-l',*argv],'cwd':str(source/'runtime'),'env':env,'stdout_stderr_log':str(job/'native.log'),'artifact_dir':str(artifact),'fresh_journal_namespace':str(artifact),'full_run_started':False,'original_protocol_sha256':sha(R/'protocol-freeze.json'),'rule_freeze_sha256':sha(R/'protocol-rule-freeze.json'),'protocol_sha256':sha(R/'protocol-freeze.json'),'correction_patch_sha256':sha(R/'owner-serialization-source.patch'),'expected_config_sha256':expected,'prior_invalid_attempt':str(J/'C1/completion.json')}
write(job/'preparation.json',prep);write(job/'expected-config.json',config)
changed=['runtime/coinmaster/strategy/residual_recovery.py','runtime/tests/test_native_residual_recovery.py']
identity=dict(status='SERIALIZATION_CORRECTION_REVIEWED_PREPARED_NO_ENGINE',source_commit=commit,base_source='78100d4d69a12144a92dbb9a713b7a7f7ce2f54d',branch='codex/residual-recovery-serialization-20261023',checkout='/root/.openclaw/workspace/coinmaster/coinmaster/research-worktrees/residual-recovery-20261023',source_snapshot=str(source),source_manifest_sha256=sha(manifest),source_manifest=str(manifest),source_file_count=92,source_files={p:pins[p] for p in changed},source_files_read_only=all(not(p.stat().st_mode&0o222) for p in source.rglob('*') if p.is_file()),patch_sha256=sha(R/'owner-serialization-source.patch'),source_bundle='/private/tmp/coinmaster-residual-recovery-serialization-20261023.bundle',source_bundle_sha256=sha(Path('/private/tmp/coinmaster-residual-recovery-serialization-20261023.bundle')),tests='owner-serialization-tests.log',tests_sha256=sha(R/'owner-serialization-tests.log'),test_result='18PASS,3.51s;actualnativepayloadunchangedserializerroundtrip;numericstateDecimalpreserved',economic_config_unchanged=True,expected_config_sha256=expected,full_native_attempts_started_by_this_preparation=0,physical_attempts_already_consumed=1,original_frozen_files=before)
write(R/'owner-serialization-source-preparation.json',identity)
write(R/'owner-serialization-run-preparation.json',dict(source_commit=commit,source_snapshot=str(source),source_pins=pins,jobs=[prep],full_native_runs=0,authorization='PREPARE_ONLY_NEW_ROOT_GO_REQUIRED',expected_config_sha256=expected,original_protocol_sha256=sha(R/'protocol-freeze.json')))
write(R/'owner-serialization-correction.json',dict(status='READY_FOR_ROOT_CORRECTED_ATTEMPT_DECISION_NOT_LAUNCHED',before_source=identity['base_source'],after_source=commit,exact_change='Copy only confirmation witness close to exact str at ATTEMPT_SUBMIT log boundary; stored Decimal policy state/global serializer/guards unchanged',diagnosis='owner-serialization-repro.json',historical_c1_payload='UNAVAILABLE_NOT_EXPORTED;no repair/reconstruction',source_preparation='owner-serialization-source-preparation.json',run_preparation='owner-serialization-run-preparation.json',economic_config_sha256_unchanged=expected,first_attempt_invalid_preserved=True,physical_started=1,active=0,next_attempt_requires_new_root_GO=True))
assert before=={p:sha(R/p) for p in frozen}
print(json.dumps(dict(source=commit,manifest=sha(manifest),config=expected,source_files=92,input_pins=13,recipe='C1_CORRECTED',engines_started=0,original_frozen_files_unchanged=True),indent=2))
