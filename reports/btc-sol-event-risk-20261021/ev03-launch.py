import sys,subprocess,json,datetime
from pathlib import Path
R=Path(__file__).resolve().parent;p=json.loads((R/"ev03-prepare.json").read_text());job=Path(p["job"]);source=Path(p["source"]);out=Path(p["out"]);testing=sys.argv[1:]==["--selftest"]
name="cm113-event-btc-ev03-20261021T0810Z"+("-synthetic" if testing else "-comparison")
cmd=["systemd-run","--quiet","--wait","--pipe","--collect", "--unit="+name]
props=["User=994","Group=986","WorkingDirectory="+str(source),"Slice=cm113-v3-risk.slice","MemoryMax=400M","MemorySwapMax=0","CPUQuota=100%","TasksMax=64","CPUWeight=10","Nice=15","PrivateNetwork=yes","ProtectHome=yes","ProtectSystem=strict","NoNewPrivileges=yes","UMask=0077","PrivateTmp=yes","InaccessiblePaths=-/srv/coinmaster -/srv/coinmaster-native-gui -/opt/coinmaster -/var/lib/coinmaster-hl-stageg-testnet","ReadWritePaths="+str(out)+" "+str(job/"cache")+" "+str(job/"tmp"),"BindReadOnlyPaths="+p["read_only_env"]+":"+str(job/"env")]
cmd += ["--property="+x for x in props]
cmd += ["/usr/bin/env","-i","PATH=/usr/bin:/bin","PYTHONDONTWRITEBYTECODE=1","OPENBLAS_NUM_THREADS=1","OMP_NUM_THREADS=1","MKL_NUM_THREADS=1","NUMBA_NUM_THREADS=1","NUMBA_CACHE_DIR="+str(job/"cache"),p["python"],str(source/"reports/btc-sol-event-risk-20261021/ev03-btc-comparison.py")]
if testing:cmd.append("--selftest")
receipt=R/("ev03-synthetic-dispatch.json" if testing else "ev03-real-dispatch.json")
with receipt.open("x") as f:json.dump(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),command=cmd,synthetic_only=testing),f,indent=2)
log=R/("ev03-synthetic.log" if testing else "ev03-comparison.log")
with log.open("w") as f:result=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
(R/("ev03-synthetic-exit.json" if testing else "ev03-real-exit.json")).write_text(json.dumps(dict(exit_code=result.returncode,unit=name,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+"\n")
print(json.dumps(dict(exit_code=result.returncode,unit=name,log=str(log))));sys.exit(result.returncode)
