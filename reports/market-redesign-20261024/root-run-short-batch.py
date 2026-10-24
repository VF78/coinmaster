"""Root-owned bounded subprocess launcher; no trading/execution model."""
import hashlib
import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "run-ledger.json"
JOBS = Path("/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/market-redesign-20261024")

def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")

def now():
    return datetime.now(timezone.utc).isoformat()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=int, choices=(1, 2), required=True)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    ledger = json.loads(LEDGER.read_text())
    assert not ledger["physical_full_attempts"]
    assert len(ledger["short_native_episode_checks"]) == (args.batch-1)*4
    assert ledger["active_runs"] == 0
    approval = json.loads((HERE / "approval.json").read_text())
    assert approval["protocol_sha256"] == hashlib.sha256((HERE / "PROTOCOL_PROPOSED.md").read_bytes()).hexdigest()
    source = json.loads((HERE / "owner-source-receipt.json").read_text())
    root = Path(source["frozen_mac_source"])
    assert source["source_commit"] == args.source_commit
    if args.batch == 2:
        assert ledger['observer_only_correction']['status'] == 'AUTHORIZED_NARROW_REPORTING_ONLY'
        assert all(row['exit_code'] == 0 for row in ledger['short_native_episode_checks'])
    for name, pin in source["file_sha256"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == pin, name
        assert (root / name).stat().st_mode & 0o222 == 0, name
    assert (HERE / "review-90da864-closure.md").exists()
    commands = json.loads((HERE / "owner-short-commands.json").read_text())
    batch = JOBS / f"short-batch{args.batch}"
    batch.mkdir(exist_ok=True)
    freeze = {"status": "ROOT_GO_SHORT_ONLY", "created_utc": now(), "source": source,
              "commands": commands, "qualification": "Four bounded R2 windows; no economic acceptance; no full prefix",
              "effective_execution": "Real-U suppresses legacy positive TP IOC fallback despite inherited raw flag; actual native TP LIMIT classification",
              "full_launch_go": False}
    write(HERE / f"short-batch{args.batch}-freeze.json", freeze)
    ledger.update(status=f"SHORT_BATCH{args.batch}_RUNNING", implementation_checkpoint=source["product_checkpoint"],
                  product_source_commit=source["source_commit"],
                  independent_review={"artifact": "review-90da864-closure.md", "status": "CLOSED_BOUNDED_FINDINGS", "full_launch_go": False},
                  substantial_correction={"maximum": 1, "used_or_active": 1, "status": "COMPLETE"})
    write(LEDGER, ledger)
    for case in ("31", "48", "65", "81"):
        command = commands[case]
        assert str(batch / case) in command['argv']
        row = {"number": len(ledger["short_native_episode_checks"]) + 1, "batch": args.batch,
               "case": case, "variant": "R2", "status": "LAUNCHING", "started_utc": now(),
               "source_commit": source["source_commit"], "argv": command["argv"],
               "log": str(batch / (case + ".native.log"))}
        ledger["short_native_episode_checks"].append(row)
        ledger["active_runs"] = 1
        write(LEDGER, ledger)
        begin = time.monotonic()
        with Path(row["log"]).open("wb") as log:
            process = subprocess.Popen(command["argv"], cwd=command["cwd"], env=command["env"], stdout=log, stderr=subprocess.STDOUT)
            row.update(pid=process.pid, status="RUNNING")
            write(LEDGER, ledger)
            print(json.dumps({"case": case, "pid": process.pid, "status": "RUNNING"}), flush=True)
            code = process.wait()
        row.update(exit_code=code, elapsed_seconds=time.monotonic() - begin, ended_utc=now(), status="COMPLETED" if code == 0 else "FAILED")
        ledger["active_runs"] = 0
        write(LEDGER, ledger)
        print(json.dumps({"case": case, "status": row["status"], "exit_code": code, "seconds": row["elapsed_seconds"]}), flush=True)
        if code:
            ledger["status"] = "SHORT_GATE_FAILED_NO_FULL_GO"
            write(LEDGER, ledger)
            return code
    ledger["status"] = f"SHORT_BATCH{args.batch}_COMPLETED_AWAIT_ROOT_ACCOUNTING_ACCEPTANCE"
    write(LEDGER, ledger)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
