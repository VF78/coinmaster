"""Explicit bounded isolated tests/profiles. Does not authorize full fits or CHECK."""
import argparse,json,os,shutil,subprocess,hashlib
from pathlib import Path
from datetime import datetime,timezone
p=argparse.ArgumentParser();p.add_argument('stage',choices=['tests','profile','screen','fit']);p.add_argument('--family',default='control',choices=['control','stumpy','minirocket','rdst','cnn']);p.add_argument('--view',default='60x20');p.add_argument('--selection',type=Path);p.add_argument('--prior-cpu-seconds',type=float);p.add_argument('--execute-authorized-train',action='store_true');p.add_argument('--focused-resource-tests',action='store_true');p.add_argument('--focused-phase-tests',action='store_true');a=p.parse_args()
if a.focused_phase_tests:a.focused_resource_tests=True
if a.focused_resource_tests and a.stage!='tests':raise ValueError('TEST_ONLY_EXCEPTION_CANNOT_APPLY_TO_MODELS')
if a.stage in ('screen','fit'):
 if not a.execute_authorized_train or a.prior_cpu_seconds is None:raise ValueError('EXPLICIT_CONDITIONAL_TRAIN_GO_AND_BUDGET_REQUIRED')
 gate=json.loads(Path('reports/forecast-independent-20261021/profile-sequence-completion.json').read_text())
 if not gate['all_pass']:raise ValueError('ALL_FIVE_RESOURCE_PROFILES_REQUIRED')
repo=Path.cwd();report=repo/'reports/forecast-independent-20261021';stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');unit=f'cm113-pred02-{a.stage}-{a.family}-{stamp}'
available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024;free=shutil.disk_usage(repo).free
admission_mib=650 if a.focused_resource_tests else 850
limit_mib=400 if a.focused_resource_tests else 600
if available<admission_mib*1024**2 or free<1536*1024**2:raise RuntimeError('RESOURCE_PREFLIGHT_FAIL')
job=Path('/var/lib/coinmaster-native-gui/data/runs/jobs')/unit;job.mkdir();source=job/'source';source.mkdir()
files=['runtime/coinmaster/__init__.py','runtime/coinmaster/research/__init__.py','reports/forecast-independent-20261021/protocol.json']+[str(x.relative_to(repo)) for x in (repo/'runtime/coinmaster/research').glob('forecast_independent_*.py')]+[str(x.relative_to(repo)) for x in (repo/'runtime/tests').glob('test_forecast_independent*.py')]+[f'reports/btc-split-sol-cover-20261018/data-warmup-{s}-1h.csv' for s in ('BTCUSDT','SOLUSDT')]
for name in files:
 target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(repo/name,target)
for name in ['result','cache','tmp','dataset']:(job/name).mkdir()
(source/'runtime/.venv').mkdir();(source/'runtime/var/data/normalized').mkdir(parents=True)
base=Path('runtime/var/research-datasets/forecast-independent-20261021-v1')
for part in ['execution-tail','execution-warmup']:(source/base/part).mkdir(parents=True)
prepare=json.loads((report/'prepare-launch.json').read_text());dataset=Path(prepare['job'])/'result/prepared-v1'
python=str(source/'runtime/.venv/bin/python');protocol=str(source/'reports/forecast-independent-20261021/protocol.json')
cmd=[python,'-m','unittest','discover','-s',str(source/'runtime/tests'),'-p','test_forecast_independent*.py','-v'] if a.stage=='tests' else [python,'-m','coinmaster.research.forecast_independent_run','profile','--family',a.family,'--view',a.view,'--dataset',str(job/'dataset'),'--protocol',protocol,'--output',str(job/'result/profile')]
if a.focused_resource_tests:
 cmd=[python,'-m','unittest','-v',*['test_forecast_independent_models.ModelContractTests.'+name for name in ['test_numeric_transform_and_scaler_precede_torch_import','test_early_best_cannot_bypass_family_minimum','test_projection_pre_and_post_calibration','test_training_only_scaler']],'test_forecast_independent_actual.ActualPreparedContractTests']
if a.focused_phase_tests:
 cmd=[python,'-m','unittest','-v',*['test_forecast_independent_models.ModelContractTests.'+name for name in ['test_opaque_rdst_parent_roundtrip_and_missing_cache_ids','test_injected_features_preserve_exact_existing_torch_head','test_budget_counts_completed_child_cpu','test_numeric_transform_and_scaler_precede_torch_import','test_early_best_cannot_bypass_family_minimum','test_projection_pre_and_post_calibration']]]
if a.stage in ('screen','fit'):
 cmd=[python,'-m','coinmaster.research.forecast_independent_run',a.stage,'--family',a.family,'--dataset',str(job/'dataset'),'--protocol',protocol,'--output',str(job/'result/train'),'--execute-train','--prior-cpu-seconds',str(a.prior_cpu_seconds)]
 if a.stage=='fit':
  if a.selection is None:raise ValueError('SELECTION_REQUIRED')
  shutil.copyfile(a.selection,job/'selection.json');cmd+=['--selection',str(job/'selection.json')]
script=job/'launch.sh';script.write_text('#!/bin/sh\nset -eu\nexport PYTHONPATH="'+str(source/'runtime')+':'+str(source/'runtime/tests')+'" OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 NUMBA_CACHE_DIR="'+str(job/'cache/numba')+'" TMPDIR="'+str(job/'tmp')+'" FORECAST_DATASET="'+str(job/'dataset')+'" FORECAST_PROTOCOL="'+protocol+'" FORECAST_SOURCE_ROOT="'+str(source)+'"\ncd "'+str(source)+'"\nexec /usr/bin/time -v -o "'+str(job/'result/time.txt')+'" '+__import__('shlex').join(cmd)+' >"'+str(job/'result/stdout.txt')+'" 2>"'+str(job/'result/stderr.txt')+'"\n')
for root,dirs,fs in os.walk(job):
 os.chown(root,994,986);os.chmod(root,0o755)
 for name in fs:os.chown(Path(root)/name,994,986);os.chmod(Path(root)/name,0o644)
binds=[f'{repo}/runtime/var/research-envs/fast-rnd-20261020:{source}/runtime/.venv',f'{dataset}:{job}/dataset',f'{repo}/runtime/var/data/normalized:{source}/runtime/var/data/normalized']+[f'{repo/base/part}:{source/base/part}' for part in ['execution-tail','execution-warmup']]
remaining_cpu=int((7200 if a.family=='cnn' else 3600)-(a.prior_cpu_seconds or 0))
if remaining_cpu<=0:raise RuntimeError('CPU_BUDGET_EXHAUSTED_BEFORE_LAUNCH')
props=[f'LimitCPU={remaining_cpu}','User=994','Group=986',f'WorkingDirectory={job}',f'MemoryMax={limit_mib}M','MemorySwapMax=0','CPUQuota=100%','CPUWeight=10','IOWeight=10','Nice=15','TasksMax=64','PrivateNetwork=yes','ProtectHome=yes','ProtectSystem=strict','NoNewPrivileges=yes','UMask=0077','PrivateTmp=yes','RemainAfterExit=yes','MemoryAccounting=yes','CPUAccounting=yes','InaccessiblePaths=-/srv/coinmaster -/srv/coinmaster-native-gui -/opt/coinmaster -/var/lib/coinmaster-hl-stageg-testnet',f'ReadWritePaths={job}/result {job}/cache {job}/tmp',f'BindReadOnlyPaths={source} {script} '+(str(job/'selection.json')+' ' if a.stage=='fit' else '')+' '.join(binds)]
command=['systemd-run','--unit='+unit,*['--property='+v for v in props],'/bin/sh',str(script)]
receipt={'unit':unit,'job':str(job),'stage':a.stage,'family':a.family,'view':a.view,'dataset_manifest_sha256':hashlib.file_digest((dataset/'manifest.json').open('rb'),'sha256').hexdigest(),'source_files':{name:hashlib.file_digest((repo/name).open('rb'),'sha256').hexdigest() for name in files},'available_before':available,'disk_free_before':free,'test_only_exception':a.focused_resource_tests,'admission_mib':admission_mib,'memory_limit_mib':limit_mib,'headroom_mib':250,'command':command,'compute_command':cmd,'at':stamp};rp=report/f'launch-{a.stage}-{a.family}-{a.view}-{stamp}.json';rp.write_text(json.dumps(receipt,indent=2)+'\n')
r=subprocess.run(command,capture_output=True,text=True);receipt.update(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr);rp.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'unit':unit,'job':str(job),'receipt':str(rp),'returncode':r.returncode}));r.check_returncode()
