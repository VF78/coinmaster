#!/usr/bin/env python3
"""Prepare/launch ONE secretless frozen native research run after review GO.

No venue connector, network, credentials, trader write, restart or deployment.
The caller runs variants sequentially and records native completion separately.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parents[1]
JOBS = Path("/var/lib/coinmaster-native-gui/data/runs/jobs")
SLICE = "cm113-v3-risk.slice"
VARIANTS = {
    "btc025": ["--research-btc-split50", "--research-btc-split-discount", "0.0025"],
    "btc025-planref": ["--research-btc-split50", "--research-btc-split-discount", "0.0025", "--research-btc-split-planref-v1"],
    "btc025-planref-tp-ioc": ["--research-btc-split50", "--research-btc-split-discount", "0.0025", "--research-btc-split-planref-v1", "--research-btc-split-tp-ioc"],
    "conditional-sol-2-1-50": ["--research-btc-split50", "--research-btc-split-discount", "0.0025", "--research-btc-split-planref-v1", "--research-btc-split-tp-ioc", "--research-conditional-sol"],
    "btc050": ["--research-btc-split50", "--research-btc-split-discount", "0.005"],
    "sol50": ["--research-sol-cover", "0.5"],
    "sol75": ["--research-sol-cover", "0.75"],
    "sol100": ["--research-sol-cover", "1"],
    "v3-repeat": [],
}
for _risk_variant in ("cap50","dd-cov","split-atr"):
    VARIANTS["risk-first-"+_risk_variant]=VARIANTS["btc025-planref-tp-ioc"]+["--research-sol-risk-first",_risk_variant]
for _insurance_variant in ("i25","i25-light","i25-recovery","i33"):
    VARIANTS["immediate-"+_insurance_variant]=VARIANTS["btc025-planref-tp-ioc"]+["--research-immediate-sol",_insurance_variant,"--research-immediate-lookback","90"]
PILOT = "coinmaster-hl-stageg-testnet.service"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked(*args):
    return subprocess.check_output(args, text=True).strip()


def resources():
    memory = {line.split(":")[0]: int(line.split()[1])*1024
              for line in Path("/proc/meminfo").read_text().splitlines()}
    return {"MemAvailable": memory["MemAvailable"], "disk_free": shutil.disk_usage(JOBS).free}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("variant", choices=tuple(VARIANTS)+("joint",))
    p.add_argument("--job-name", required=True)
    p.add_argument("--joint-btc", choices=("btc025","btc050","btc025-planref"))
    p.add_argument("--joint-sol", choices=("sol50","sol75","sol100"))
    p.add_argument("--launch", action="store_true")
    a = p.parse_args()
    if not a.job_name.startswith("cm115-split-") or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in a.job_name):
        raise ValueError("INVALID_ISOLATED_JOB_NAME")
    args = list(VARIANTS.get(a.variant, []))
    if a.variant == "joint":
        if not a.joint_btc or not a.joint_sol:
            p.error("joint requires the selected separate BTC and SOL variants")
        args = VARIANTS[a.joint_btc]+VARIANTS[a.joint_sol]
    if checked("systemctl","show",SLICE,"--value","-p","MemoryMax") != str(650*1024**2):
        raise ValueError("SHARED_RESEARCH_650M_FENCE_REQUIRED")
    if checked("systemctl","show",SLICE,"--value","-p","MemorySwapMax") != "0":
        raise ValueError("RESEARCH_SWAP_MUST_BE_ZERO")
    cgroup = Path("/sys/fs/cgroup")/checked("systemctl","show",SLICE,"--value","-p","ControlGroup").lstrip("/")
    if any(path.read_text().strip() for path in cgroup.rglob("cgroup.procs")):
        raise ValueError("ANOTHER_RESEARCH_PROCESS_IS_ACTIVE")
    before = resources()
    if before["MemAvailable"] < 700*1024**2 or before["disk_free"] < 1024**3:
        raise ValueError("RESOURCE_FLOOR_NOT_MET")
    pilot = checked("systemctl","show",PILOT,"-p","MainPID","-p","NRestarts","-p","ActiveState")
    if "MainPID=2009732" not in pilot or "NRestarts=0" not in pilot or "ActiveState=active" not in pilot:
        raise ValueError("PROTECTED_PILOT_IDENTITY_CHANGED")
    job = JOBS/a.job_name
    job.mkdir(mode=0o700)
    source = job/"source"
    source.mkdir()
    files = list((REPO/"runtime/coinmaster").rglob("*.py"))
    # Existing public venue metadata are required by the native margin profile.
    files += [REPO/"runtime/pyproject.toml", REPO/"runtime/uv.lock", REPO/"runtime/var/venue-manifest.json"]
    files += [f for f in (REPO/"runtime/var/raw/venues").rglob("*") if f.is_file()]
    if "--research-sol-cover" in args or "--research-conditional-sol" in args or "--research-sol-risk-first" in args:
        pack = REPO/"reports/btc-split-sol-cover-20261018"
        files += [pack/"data-warmup-BTCUSDT-1h.csv",pack/"data-warmup-SOLUSDT-1h.csv",pack/"data-warmup-manifest.json"]
    hashes = {}
    for path in files:
        relative = path.relative_to(REPO)
        dest = source/relative
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest)
        hashes[str(relative)] = digest(dest)
    for relative in ("runtime/.venv","runtime/var/data"):
        (source/relative).mkdir(parents=True,exist_ok=True)
    (job/"tmp").mkdir()
    (job/"source-commit.txt").write_text(checked("git","-C",str(REPO),"rev-parse","HEAD")+"\n")
    (job/"immutable-source-hashes.json").write_text(json.dumps(hashes,sort_keys=True,indent=2)+"\n")
    input_hashes = {
        name:digest(REPO/"runtime/var/data"/name)
        for name in ("bybit-1m/manifest.json","runs/tp-fee-floor-113/v0/v0.json")
    }
    if "--research-immediate-sol" in args:
        input_hashes.update({"normalized/bybit-"+symbol+"-daily.parquet":digest(REPO/"runtime/var/data/normalized"/("bybit-"+symbol+"-daily.parquet")) for symbol in ("BTCUSDT","SOLUSDT")})
    (job/"input-hashes.json").write_text(json.dumps(input_hashes,sort_keys=True,indent=2)+"\n")
    (job/"source-input-hashes.sha256").write_text(
        "".join(f"{v}  {source/k}\n" for k,v in sorted(hashes.items()))+
        "".join(f"{v}  {source}/runtime/var/data/{k}\n" for k,v in sorted(input_hashes.items())))
    (job/"resource-before.json").write_text(json.dumps(before,indent=2)+"\n")
    (job/"pilot-before.txt").write_text(pilot+"\n")
    (job/"variant.json").write_text(json.dumps({"variant":a.variant,"flags":args,"dp":"OFF",
        "base_control":"V3_DIRECTION_LONG5.5_SHORT7.875","snapshot_time":datetime.now(timezone.utc).isoformat()},indent=2)+"\n")
    env = ["/usr/bin/env","-i","PATH=/usr/local/bin:/usr/bin:/bin","PYTHONDONTWRITEBYTECODE=1",
        f"PYTHONPATH={source}/runtime",f"TMPDIR={job}/tmp","OPENBLAS_NUM_THREADS=1","OMP_NUM_THREADS=1",
        "MKL_NUM_THREADS=1","NUMEXPR_NUM_THREADS=1","NUMEXPR_MAX_THREADS=1","ARROW_NUM_THREADS=2"]
    cmd = env+[str(source/"runtime/.venv/bin/python"),"-m","coinmaster.research.native_baseline",
        "--data-root",str(source/"runtime/var/data"),"--research-v0-execution-repairs",
        "--research-v0-deferred-selective-zero-tp","--research-v0-selective-lifecycle-repairs",
        "--observe-minute-risk","--research-btc-direction-sizing",
        "--control-report",str(source/"runtime/var/data/runs/tp-fee-floor-113/v0/v0.json"),
        "--artifact-dir",str(job/"result")]+args
    lock = JOBS/".split-cover-native.lock"
    lock.touch(exist_ok=True);os.chown(lock,994,986)
    script = "#!/bin/sh\nset -eu\nexec >>"+shlex.quote(str(job/"run.log"))+" 2>&1\n"
    script += "sha256sum -c "+shlex.quote(str(job/"source-input-hashes.sha256"))+" >/dev/null\n"
    script += "exec /usr/bin/flock -n "+shlex.quote(str(lock))+" "+shlex.join(cmd)+"\n"
    (job/"launch.sh").write_text(script)
    for path in [job]+list(job.rglob("*")):
        os.chown(path,994,986)
    properties = [f"User=994","Group=986",f"WorkingDirectory={job}",f"Slice={SLICE}",
        "MemoryMax=650M","MemorySwapMax=0","TasksMax=64","CPUWeight=10","Nice=10",
        "PrivateNetwork=yes","ProtectHome=yes","ProtectSystem=strict","NoNewPrivileges=yes","UMask=0077",
        f"ReadWritePaths={job} {lock}",
        f"BindReadOnlyPaths={source} {REPO}/runtime/.venv:{source}/runtime/.venv {REPO}/runtime/var/data:{source}/runtime/var/data"]
    launch = ["systemd-run",f"--unit={a.job_name}","--collect"]+[f"--property={v}" for v in properties]+["/bin/sh",str(job/"launch.sh")]
    (job/"launch-command.json").write_text(json.dumps(launch,indent=2)+"\n")
    if a.launch:
        subprocess.run(launch,check=True)
    print(json.dumps({"job":str(job),"variant":a.variant,"launched":a.launch,"frozen_files":len(hashes),"launch_command":launch}))


if __name__ == "__main__":
    main()
