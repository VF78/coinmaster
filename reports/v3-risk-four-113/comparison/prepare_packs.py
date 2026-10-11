"""Freeze four public immutable packs; this never launches an engine."""
import sys,json,hashlib,shutil,subprocess,os
from pathlib import Path
ROOT=Path('/root/.openclaw/workspace/coinmaster/coinmaster'); OUT=Path(__file__).parent
BASE=Path('/var/lib/coinmaster-native-gui/data/runs/jobs');FROZEN=sys.argv[1]
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==FROZEN
subprocess.run(['git','diff','--exit-code',FROZEN,'--','runtime/coinmaster','runtime/configs','runtime/scripts','runtime/pyproject.toml','runtime/uv.lock'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
old=BASE/'cm113-sizing-v3-20261011'
keys=json.loads((old/'immutable-source-hashes.json').read_text());assert len(keys)==106
hashes={k:hashlib.sha256((ROOT/'runtime'/k).read_bytes()).hexdigest() for k in keys}
canonical={str(Path('runtime')/k):v for k,v in hashes.items()}
for k in ['runtime/var/data/bybit-1m/manifest.json','runtime/var/data/runs/tp-fee-floor-113/v0/v0.json']:canonical[k]=hashlib.sha256((ROOT/k).read_bytes()).hexdigest()
assert canonical['runtime/var/data/bybit-1m/manifest.json']=='a24b4d914dc4ac168be7bd4e4603eccc6356cb2c150a3d95442d22752e89c5db'
assert canonical['runtime/var/data/runs/tp-fee-floor-113/v0/v0.json']=='d6a29d6e0e9ac586b911f2802cbe89602a05d2c0d73026d08ed76082a8a934f9'
for v in ['b25','s10_15','r2','t3']:
 job=BASE/('cm113-v3-'+v+'-20261011');assert not job.exists();job.mkdir()
 for name in keys:
  dst=job/'source'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'runtime'/name,dst)
 for name in ['source/.venv','source/var/data','tmp']:(job/name).mkdir(parents=True,exist_ok=True)
 (job/'immutable-source-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n');(job/'source-commit.txt').write_text(FROZEN+'\n')
 (job/'source-input-hashes.sha256').write_text(''.join(h+'  '+k+'\n' for k,h in canonical.items()))
 launch='#!/bin/sh\nset -eu\njob='+str(job)+'\nexec >>"$job/run.log" 2>&1\nexec /usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$job/source" TMPDIR="$job/tmp" OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 NUMEXPR_MAX_THREADS=1 ARROW_NUM_THREADS=2 "$job/source/.venv/bin/python" -m coinmaster.research.native_baseline --data-root "$job/source/var/data" --research-v0-execution-repairs --research-v0-deferred-selective-zero-tp --research-v0-selective-lifecycle-repairs --observe-minute-risk --research-v3-risk '+v+' --control-report "$job/source/var/data/runs/tp-fee-floor-113/v0/v0.json" --artifact-dir "$job/result"\n'
 (job/'launch.sh').write_text(launch)
 reviewed='#!/bin/sh\nset -eu\njob='+str(job)+'\nrepo='+str(ROOT)+'\ncd "$repo"\ntest -f "'+str(OUT)+'/GO.json"\ngit merge-base --is-ancestor '+FROZEN+' HEAD\nsha256sum -c "$job/source-input-hashes.sha256"\n/usr/bin/python3 "'+str(OUT)+'/validate_pack.py" "$job"\ntest ! -e "$job/result"\nexec systemd-run --unit='+job.name+' --slice=cm113-v3-risk.slice --collect --property=User=994 --property=Group=986 --property=WorkingDirectory="$job" --property=MemoryMax=900M --property=MemorySwapMax=0 --property=TasksMax=64 --property=CPUWeight=10 --property=Nice=10 --property=PrivateNetwork=yes --property=ProtectHome=yes --property=ProtectSystem=strict --property=NoNewPrivileges=yes --property=UMask=0077 --property=ReadWritePaths="$job" --property=BindReadOnlyPaths="$job/source $repo/runtime/.venv:$job/source/.venv $repo/runtime/var/data:$job/source/var/data" /bin/sh "$job/launch.sh"\n'
 (job/'launch-reviewed-only.sh').write_text(reviewed)
 for p in job.rglob('*'):
  os.chown(p,994,986)
  if p.is_file():p.chmod(0o444 if 'source' in p.relative_to(job).parts else 0o640)
 os.chown(job,994,986);job.chmod(0o750)
 (job/'launch-reviewed-only.sh').chmod(0o750);(job/'launch.sh').chmod(0o750)
 subprocess.run(['/usr/bin/python3',str(OUT/'validate_pack.py'),str(job)],check=True)
contract=json.loads((OUT/'setup-contract.json').read_text());contract.update(source_commit=FROZEN,status='FOUR_IMMUTABLE_PACKS_PREPARED_NO_ENGINE_LAUNCHED',immutable_files_per_pack=len(keys),source_hash_manifest=hashes)
(OUT/'setup-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
print('FOUR_PACKS_PREPARED_NO_ENGINE_LAUNCHED')
