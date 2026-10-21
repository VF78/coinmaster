"""Bounded single-process-tree Mac research execution; not a scheduler."""
import argparse,datetime,fcntl,json,os,signal,subprocess,time
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument("--job",type=Path,required=True);p.add_argument("--wall-seconds",type=float,required=True);p.add_argument("command",nargs=argparse.REMAINDER);a=p.parse_args()
 a.job.mkdir(parents=True,exist_ok=False);lock=(a.job.parent/"heavy-process.lock").open("w");fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 env=dict(os.environ)
 env.update({k:"1" for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMBA_NUM_THREADS","VECLIB_MAXIMUM_THREADS")});env["PYTHONDONTWRITEBYTECODE"]="1"
 command=a.command[1:] if a.command and a.command[0]=="--" else a.command
 command=["/usr/bin/time","-l",*command];started=time.monotonic();peak=0;reason=None
 receipt={"at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"command":command,"threads":1,"RSS_limit_bytes":3221225472,"wall_limit_seconds":a.wall_seconds}
 (a.job/"launch.json").write_text(json.dumps(receipt,indent=2)+"\n")
 with (a.job/"stdout.txt").open("w") as out,(a.job/"stderr-time.txt").open("w") as err:
  proc=subprocess.Popen(command,stdout=out,stderr=err,env=env,start_new_session=True,preexec_fn=lambda:os.nice(10))
  receipt["pid"]=proc.pid
  while proc.poll() is None:
   rows=[tuple(map(int,line.split())) for line in subprocess.check_output(["/bin/ps","-axo","pid=,ppid=,rss="],text=True).splitlines() if len(line.split())==3];tree={proc.pid}
   for _ in range(8):tree.update(pid for pid,parent,rss in rows if parent in tree)
   rss=sum(rss*1024 for pid,parent,rss in rows if pid in tree);peak=max(peak,rss)
   if rss>3221225472:reason="INCOMPLETE_RESOURCE_RSS"
   if time.monotonic()-started>a.wall_seconds:reason="INCOMPLETE_RESOURCE_WALL"
   if reason:
    os.killpg(proc.pid,signal.SIGTERM)
    try:proc.wait(timeout=5)
    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL)
    break
   time.sleep(.5)
  rc=proc.wait()
 receipt.update(status=reason or ("PASS" if rc==0 else "TECHNICAL_FAILURE_NO_AUTORETRY"),returncode=rc,wall_seconds=time.monotonic()-started,observed_process_tree_peak_RSS_bytes=peak,native_time_units="Darwin bytes")
 (a.job/"completion.json").write_text(json.dumps(receipt,indent=2)+"\n")
 print(json.dumps({"status":receipt["status"],"returncode":rc,"wall_seconds":receipt["wall_seconds"],"RSS_bytes":peak,"receipt":str(a.job/"completion.json")}))
 if rc or reason:raise SystemExit(rc or 1)
if __name__=="__main__":main()
