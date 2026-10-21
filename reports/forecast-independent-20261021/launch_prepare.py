"""One explicit isolated data job; no model/engine launch."""
import json,os,shutil,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
repo=Path.cwd();report=repo/'reports/forecast-independent-20261021';stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');unit='cm113-pred02-data-'+stamp
available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024;free=shutil.disk_usage(repo).free
if available<850*1024**2 or free<1536*1024**2:raise RuntimeError('RESOURCE_PREFLIGHT_FAIL')
job=Path('/var/lib/coinmaster-native-gui/data/runs/jobs')/unit
job.mkdir();source=job/'source';source.mkdir()
files=['runtime/coinmaster/__init__.py','runtime/coinmaster/research/__init__.py','runtime/coinmaster/research/forecast_independent_data.py','reports/forecast-independent-20261021/protocol.json']+[f'reports/btc-split-sol-cover-20261018/data-warmup-{s}-1h.csv' for s in ('BTCUSDT','SOLUSDT')]
for name in files:
 target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(repo/name,target)
for name in ['result','cache','tmp']:(job/name).mkdir()
(source/'runtime/.venv').mkdir();(source/'runtime/var/data/normalized').mkdir(parents=True)
base=Path('runtime/var/research-datasets/forecast-independent-20261021-v1')
for part in ['execution-tail','execution-warmup']:(source/base/part).mkdir(parents=True)
script=job/'launch.sh';script.write_text('#!/bin/sh\nset -eu\nexport PYTHONPATH="'+str(source/'runtime')+'" OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 TMPDIR="'+str(job/'tmp')+'"\ncd "'+str(source)+'"\nexec "'+str(source/'runtime/.venv/bin/python')+'" -m coinmaster.research.forecast_independent_data --repo "'+str(source)+'" --output "'+str(job/'result/prepared-v1')+'" --protocol "'+str(source/'reports/forecast-independent-20261021/protocol.json')+'"\n')
for root,dirs,fs in os.walk(job):
 os.chown(root,994,986);os.chmod(root,0o755)
 for name in fs:os.chown(Path(root)/name,994,986);os.chmod(Path(root)/name,0o644)
binds=[f'{repo}/runtime/.venv:{source}/runtime/.venv',f'{repo}/runtime/var/data/normalized:{source}/runtime/var/data/normalized']+[f'{repo/base/part}:{source/base/part}' for part in ['execution-tail','execution-warmup']]
props=['User=994','Group=986',f'WorkingDirectory={job}','MemoryMax=600M','MemorySwapMax=0','CPUQuota=100%','CPUWeight=10','IOWeight=10','Nice=15','TasksMax=64','PrivateNetwork=yes','ProtectHome=yes','ProtectSystem=strict','NoNewPrivileges=yes','UMask=0077','PrivateTmp=yes','InaccessiblePaths=-/srv/coinmaster -/srv/coinmaster-native-gui -/opt/coinmaster -/var/lib/coinmaster-hl-stageg-testnet',f'ReadWritePaths={job}/result {job}/cache {job}/tmp',f'BindReadOnlyPaths={source} {script} '+' '.join(binds)]
cmd=['systemd-run','--unit='+unit,*['--property='+p for p in props],'/bin/sh',str(script)]
receipt={'unit':unit,'job':str(job),'available_before':available,'disk_free_before':free,'command':cmd,'purpose':'PREPARE_ONLY_LABELS_PARTITIONED_CHECK_PERFORMANCE_SEALED','at':stamp}
(report/'prepare-launch.json').write_text(json.dumps(receipt,indent=2)+'\n')
p=subprocess.run(cmd,capture_output=True,text=True);receipt.update(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr);(report/'prepare-launch.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt));p.check_returncode()
