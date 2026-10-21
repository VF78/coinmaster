"""Native Mac research allocation; executes pinned immutable canonical source."""
import argparse,datetime,hashlib,json,os,resource,signal,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('stage',choices=['profile','fit','check']);p.add_argument('--family',choices=['control','stumpy','minirocket','rdst','cnn'],required=True);p.add_argument('--job',type=Path,required=True);p.add_argument('--python',type=Path,required=True);p.add_argument('--prior-cpu-seconds',type=float,required=True);p.add_argument('--seal',type=Path);p.add_argument('--all-method-seals',type=Path);p.add_argument('--baseline',type=Path);p.add_argument('--execute-authorized-check',action='store_true');a=p.parse_args()
if a.stage=='check' and (not a.execute_authorized_check or a.seal is None or a.all_method_seals is None):raise ValueError('SEPARATE_CHECK_GO_AND_ALL_FIVE_SEALS_REQUIRED')
if a.stage=='check' and a.family!='control' and a.baseline is None:raise ValueError('RAW_CONTROL_BASELINE_REQUIRED')
job=a.job.resolve();protocol=job/'reports/forecast-independent-20261021/protocol.json';stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');out=job/('run-'+a.stage+'-'+a.family+'-'+stamp);out.mkdir()
for part in ['cache','tmp','home']:(out/part).mkdir()
limit=300 if a.stage=='profile' else (480*60 if a.family=='cnn' else 60*60)-a.prior_cpu_seconds
if limit<=0:raise ValueError('CPU_BUDGET_ALREADY_EXHAUSTED')
env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(out/'home'),'PYTHONPATH':str(job/'runtime'),'PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMBA_NUM_THREADS':'1','NUMBA_CACHE_DIR':str(job/'numba-cache'),'TMPDIR':str(out/'tmp')}
args=[a.stage,'--family',a.family,'--view','60x20','--dataset',str(job/'prepared-v1'),'--protocol',str(protocol),'--output',str(out/'result'),'--prior-cpu-seconds',str(a.prior_cpu_seconds)]
if a.stage=='fit':args+=['--execute-train','--selection',str(job/'selection.json')]
if a.stage=='check':
 args+=['--execute-check','--seal',str(a.seal.absolute()),'--all-method-seals',str(a.all_method_seals.absolute())]
 if a.baseline is not None:args+=['--baseline',str(a.baseline.absolute())]
cmd=[str(a.python.absolute()),'-m','coinmaster.research.forecast_independent_run',*args]
if a.stage in ('fit','check') and a.family=='cnn':
 auth=job/'reports/forecast-independent-20261021/coordinator-cnn-resource-envelope.json';cmd=[str(a.python.absolute()),str(job/'reports/forecast-independent-20261021/resource_envelope.py'),'--resource-budget',str(auth),'--resource-budget-sha256',hashlib.sha256(auth.read_bytes()).hexdigest(),*args]
cmd=['/usr/bin/time','-l',*cmd]
def allocation():os.nice(10);resource.setrlimit(resource.RLIMIT_CPU,(int(limit),int(limit)))
receipt={'status':'RUNNING','at_utc':stamp,'job':str(job),'output':str(out),'family':a.family,'stage':a.stage,'prior_cpu_seconds':a.prior_cpu_seconds,'allocated_remaining_cpu_seconds':limit,'RSS_process_tree_limit_bytes':3*1024**3,'threads':1,'nice':10,'clean_environment_keys':list(env),'command':cmd,'source_manifest_sha256':hashlib.sha256((job/'transfer-manifest.json').read_bytes()).hexdigest(),'operational_launcher_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(out/'launch.json').write_text(json.dumps(receipt,indent=2)+'\n')
with (out/'stdout.txt').open('w') as stdout,(out/'stderr-time.txt').open('w') as stderr:
 proc=subprocess.Popen(cmd,cwd=job,env=env,stdout=stdout,stderr=stderr,start_new_session=True,preexec_fn=allocation);awake=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(proc.pid)],env=env);receipt['pid']=proc.pid;print(json.dumps({'pid':proc.pid,'output':str(out),'status':'RUNNING'}),flush=True);peak=0;started=time.monotonic()
 while proc.poll() is None:
  lines=subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,rss='],text=True).splitlines();rows=[tuple(map(int,line.split())) for line in lines if len(line.split())==3];tree={proc.pid}
  for _ in range(8):tree.update(pid for pid,parent,rss in rows if parent in tree)
  rss=sum(rss*1024 for pid,parent,rss in rows if pid in tree);peak=max(peak,rss)
  if rss>3*1024**3:receipt['resource_stop']='PROCESS_TREE_RSS_OVER_3GiB';os.killpg(proc.pid,signal.SIGTERM);break
  time.sleep(1)
 code=proc.wait();awake.wait(timeout=10)
receipt.update(status='PASS' if code==0 else 'INCOMPLETE_NO_AUTOMATIC_RETRY',returncode=code,observed_process_tree_peak_RSS_bytes=peak,wall_seconds=time.monotonic()-started,native_maxrss_units='Darwinbytes; frozen runtime maxrss_bytes field incorrectly scalesLinux1024, use external time/psreceipt')
(out/'completion.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)
if code:raise SystemExit(code)
