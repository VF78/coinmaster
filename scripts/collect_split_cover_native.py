#!/usr/bin/env python3
"""Collect one completed frozen native research job; never launches work."""
import argparse
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("job",type=Path)
    p.add_argument("--receipt",type=Path,required=True)
    a=p.parse_args()
    job=a.job.resolve()
    if job.parent != Path("/var/lib/coinmaster-native-gui/data/runs/jobs") or not job.name.startswith("cm115-split-"):
        raise ValueError("UNEXPECTED_RESEARCH_JOB")
    raw=[]
    for source in (job/"result").glob("*.json"):
        data=json.loads(source.read_text())
        if "summary" in data and "terminal_total" in data:
            raw.append((source,data))
    if len(raw)!=1:
        raise ValueError("EXACTLY_ONE_NATIVE_RESULT_REQUIRED")
    source,result=raw[0]
    expected=json.loads((job/"immutable-source-hashes.json").read_text())
    for name,digest in expected.items():
        if sha(job/"source"/name)!=digest:
            raise ValueError(f"FROZEN_SOURCE_CHANGED:{name}")
    inputs=json.loads((job/"input-hashes.json").read_text())
    for name,digest in inputs.items():
        if sha(ROOT/"runtime/var/data"/name)!=digest:
            raise ValueError(f"CANONICAL_INPUT_CHANGED:{name}")
    pilot=subprocess.check_output(["systemctl","show","coinmaster-hl-stageg-testnet.service",
        "-p","MainPID","-p","NRestarts","-p","ActiveState"],text=True).strip()
    if "MainPID=2009732" not in pilot or "NRestarts=0" not in pilot or "ActiveState=active" not in pilot:
        raise ValueError("PROTECTED_PILOT_IDENTITY_CHANGED")
    (job/"pilot-after.txt").write_text(pilot+"\n")
    parents=result.get("split_cover_audit",{}).get("parents",[])
    violations=[]
    for parent in parents:
        planned,filled,cancelled=(D(str(parent[k])) for k in ("quantity","filled","cancelled"))
        if min(planned,filled,cancelled)<0 or filled>planned or filled+cancelled!=planned:
            violations.append(parent["episode_id"])
    if violations:
        raise ValueError(f"SPLIT_Q_CONSERVATION_VIOLATION:{violations}")
    if result["terminal_open_positions"]!=0:
        raise ValueError("NATIVE_TERMINAL_POSITIONS_NOT_FLAT")
    if not result.get("early_liquidation_cutoff") and result["streaming"]["processed_rows_per_source"]!=1051200:
        raise ValueError("NATIVE_INPUT_ROWS_INCOMPLETE")
    summary=result.get("minute_risk_observations",{})
    if not summary:
        raise ValueError("NATIVE_MINUTE_MARKED_OBSERVER_MISSING")
    receipt={
        "job":str(job),"variant":json.loads((job/"variant.json").read_text()),
        "source_commit":(job/"source-commit.txt").read_text().strip(),
        "artifact":str(source),"artifact_sha256":sha(source),
        "frozen_manifest_sha256":sha(job/"immutable-source-hashes.json"),
        "frozen_files_verified":len(expected),"canonical_input_hashes":inputs,
        "config_hash":result["config_hash"],"data_hash":result["data_hash"],"policy_hash":result["policy_hash"],
        "terminal_total":result["terminal_total"],"native_fees":result["native_fees"],
        "fills":result["fills"],"liquidation_count":result["liquidation_count"],
        "terminal_open_positions":result["terminal_open_positions"],"streaming":result["streaming"],
        "split_parent_count":len(parents),"split_qty_conserved":True,
        "minute_risk_observations":summary,"funding":result["funding"],
        "resources_before":json.loads((job/"resource-before.json").read_text()),
        "disk_free_after":shutil.disk_usage(job).free,"pilot_after":pilot,
        "scope":"RESEARCH_ONLY_NATIVE_ACCOUNTING_DIAGNOSTIC_NO_PRODUCTION_PROMOTION",
    }
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    a.receipt.write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps({"receipt":str(a.receipt),"terminal_total":result["terminal_total"],
        "native_fees":result["native_fees"],"fills":result["fills"],"liquidations":result["liquidation_count"],
        "parents":len(parents),"Q_conserved":True,"rows":result["streaming"]["processed_rows_per_source"]}))


if __name__=="__main__":
    main()
