"""Foreground CM2 batch admission; one native engine per existing runner child.

A root-frozen allocation reserves every listed case globally before dispatch. This
module never reallocates unused/unknown reservations and never resumes a batch.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from coinmaster.research import cm2_runner as runner


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def policy_digest(policy):
    return digest_bytes(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode())


def available_memory():
    """Conservative fresh admission only; never terminate a running child."""
    if sys.platform == "linux":
        rows = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        return int(rows["MemAvailable"].split()[0]) * 1024
    if sys.platform == "darwin":
        import re
        output = subprocess.check_output(["/usr/bin/vm_stat"], text=True,
                                         env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
        page = int(re.search(r"page size of (\d+) bytes", output).group(1))
        values = {}
        for line in output.splitlines()[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                values[key] = int(value.strip().rstrip("."))
        return page * sum(values.get(k, 0) for k in
                          ("Pages free", "Pages inactive", "Pages speculative"))
    raise ValueError("CM2_UNSUPPORTED_RESOURCE_PLATFORM")


def validate_allocation(manifest, host, manifest_sha):
    if manifest.get("schema") != "cm2-static-block-v1" or manifest.get("root_GO") is not True:
        raise ValueError("CM2_ROOT_BLOCK_NOT_FROZEN")
    if not manifest.get("global_reservation_ref") or not manifest.get("block_id"):
        raise ValueError("CM2_GLOBAL_RESERVATION_REQUIRED")
    stage = manifest["stage"]
    if stage not in ("engineering", "anchors", "broad", "local", "qualification"):
        raise ValueError("CM2_STAGE_INVALID")
    if set(manifest["hosts"]) - {"mac", "vps"}:
        raise ValueError("CM2_UNKNOWN_HOST")
    cap = {"engineering": 4, "anchors": 4, "broad": 32, "local": 32, "qualification": 12}[stage]
    if not 1 <= manifest["reserved_attempts"] <= cap:
        raise ValueError("CM2_BLOCK_STAGE_CAP")
    if stage == "broad" and manifest.get("broad_block") not in ("initial", "second"):
        raise ValueError("CM2_BROAD_BLOCK_GATE_REQUIRED")
    for name, allocation in manifest["hosts"].items():
        if allocation["quota"] != len(allocation["cases"]) or allocation["quota"] < 1:
            raise ValueError("CM2_HOST_QUOTA_MISMATCH")
        if not 1 <= allocation["max_workers"] <= (10 if name == "mac" else 2):
            raise ValueError("CM2_WORKER_LIMIT")
    cases = [c for h in manifest["hosts"].values() for c in h["cases"]]
    ids = [c["run_id"] for c in cases]
    policies = [c["policy_sha256"] for c in cases]
    if len(set(ids)) != len(ids) or len(set(policies)) != len(policies):
        raise ValueError("CM2_DUPLICATE_CASE_OR_POLICY")
    if not cases or len(cases) != manifest["reserved_attempts"]:
        raise ValueError("CM2_GLOBAL_ALLOCATION_CAP_MISMATCH")
    own = manifest["hosts"][host]
    if own["quota"] != len(own["cases"]) or own["quota"] < 1:
        raise ValueError("CM2_HOST_QUOTA_MISMATCH")
    if not 1 <= own["max_workers"] <= (10 if host == "mac" else 2):
        raise ValueError("CM2_WORKER_LIMIT")
    if own["min_available_memory_bytes"] <= 0:
        raise ValueError("CM2_FINITE_MEMORY_ADMISSION_REQUIRED")
    budget = json.loads(Path(own["budget_path"]).read_text())
    expected = {"cap": own["quota"]}
    if stage == "broad":
        expected["initial_block"] = own["quota"]
    if (budget["total_physical_cap"] != own["quota"] or
        budget["stages"] != {stage: expected} or
        budget.get("root_allocation_sha256") != manifest_sha or
        budget.get("scope_version") != manifest["block_id"]):
        raise ValueError("CM2_STRICT_BLOCK_BUDGET_REQUIRED")
    requests = []
    for case in own["cases"]:
        raw = Path(case["request_path"]).read_bytes()
        request = json.loads(raw)
        if digest_bytes(raw) != case["request_sha256"]:
            raise ValueError("CM2_REQUEST_PIN_MISMATCH")
        if (request["run_id"] != case["run_id"] or request["stage"] != stage or
            policy_digest(request["policy"]) != case["policy_sha256"] or
            request["attempt_ledger"] != own["attempt_ledger"] or
            request["budget_path"] != own["budget_path"] or
            request["shared_lock_path"] != own["shared_lock_path"]):
            raise ValueError("CM2_REQUEST_ALLOCATION_MISMATCH")
        requests.append((case, request))
    outputs = [str(Path(r["artifact_dir"]).resolve()) for _, r in requests]
    if len(set(outputs)) != len(outputs):
        raise ValueError("CM2_OUTPUT_COLLISION")
    for a in outputs:
        for b in outputs:
            if a != b and Path(a).is_relative_to(b):
                raise ValueError("CM2_OUTPUT_OVERLAP")
    return own, requests


def collect_child(pid, status, usage, record):
    child, entry, output, started, identity, log, ledger, request = record
    code = os.waitstatus_to_exitcode(status)
    child.returncode = code
    log.close()
    collection_code=code;validation_error=None
    if code==0:
        try:runner.postchild_validation(request)
        except Exception as error:
            collection_code=1
            validation_error={'error_type':type(error).__name__,'error':str(error),
                'failure_phase':'POST_CHILD_PERSISTED_QUALIFICATION'}
    terminal = {**entry, "status": "COMPLETED" if collection_code == 0 else "FAILED",
                "exit_code": code, "elapsed_seconds": time.monotonic() - started,
                "true_child_peak_rss_bytes": int(usage.ru_maxrss) * (1 if sys.platform == "darwin" else 1024),
                "rss_basis": "WAIT4_EXACT_NATIVE_CHILD_RUSAGE_MAXRSS"}
    if validation_error is not None:terminal.update(validation_error,collection_exit_code=collection_code)
    with (output / "native-child-terminal.json").open("x") as stream:
        stream.write(json.dumps({**identity, **terminal}, sort_keys=True) + "\n")
    runner.append_ledger(ledger, terminal)
    return collection_code


def dispatch(requests, receipt, own, manifest_sha):
    ledger = Path(own["attempt_ledger"])
    ledger.parent.mkdir(parents=True, exist_ok=True)
    failures = Counter()
    active = {}
    stopped = False
    # Same open description inherited by every child; close only, NEVER LOCK_UN.
    with runner.acquire_shared_lease(own["shared_lock_path"]) as shared:
        if ledger.exists() and ledger.stat().st_size:
            raise ValueError("CM2_BATCH_EXISTS_NO_RESUME_OR_RETRY")
        pending = iter(requests)
        next_case = next(pending, None)
        try:
            while next_case is not None or active:
                while next_case is not None and not stopped and len(active) < own["max_workers"]:
                    if available_memory() < own["min_available_memory_bytes"]:
                        if not active:
                            stopped = True
                        break
                    case, request = next_case
                    output = Path(request["artifact_dir"])
                    if output.exists() and any(output.iterdir()):
                        raise ValueError("CM2_OUTPUT_EXISTS_NO_REPLAY")
                    output.mkdir(parents=True, exist_ok=True)
                    # STARTED is durable BEFORE any worker preparation or Popen.
                    entry = runner.register_attempt(request, receipt)
                    entry.update(request_sha256=case["request_sha256"],
                                 root_allocation_sha256=manifest_sha)
                    (output / "ATTEMPT_STARTED.json").write_text(json.dumps(entry) + "\n")
                    started = time.monotonic()
                    child = None
                    log = None
                    try:
                        command, env, cwd = runner.worker_process_spec(
                            {**request, "_request_path": case["request_path"]},
                            shared.fileno(), case["request_sha256"])
                        log = (output / "worker.log").open("x")
                        child = subprocess.Popen(command, env=env, cwd=cwd, stdout=log,
                                                 stderr=subprocess.STDOUT, pass_fds=(shared.fileno(),))
                        # Track immediately, even if identity serialization fails.
                        record = (child, entry, output, started, {}, log, str(ledger), {**request,"_request_path":case["request_path"]})
                        active[child.pid] = record
                        identity = runner.record_native_child(output, child.pid, request["run_id"], case["request_sha256"])
                        active[child.pid] = (child, entry, output, started, identity, log, str(ledger), {**request,"_request_path":case["request_path"]})
                    except BaseException as error:
                        if child is None:
                            if log is not None:
                                log.close()
                            runner.append_ledger(ledger, {**entry, "status": "FAILED", "error_type": type(error).__name__,
                                "failure_phase": "PRE_WORKER_SPAWN", "elapsed_seconds": time.monotonic()-started})
                            failures[("PRE_WORKER_SPAWN", type(error).__name__)] += 1
                            if failures[("PRE_WORKER_SPAWN", type(error).__name__)] >= 2:
                                stopped = True
                        else:
                            stopped = True
                            raise
                    next_case = next(pending, None)
                if stopped:
                    next_case = None
                if active:
                    for pid in list(active):
                        result_pid, status, usage = os.wait4(pid, os.WNOHANG)
                        if result_pid:
                            code = collect_child(pid, status, usage, active.pop(pid))
                            if code:
                                failures[("CASE_COLLECTION", code)] += 1
                                if failures[("CASE_COLLECTION", code)] >= 2:
                                    stopped = True
                    if active:
                        time.sleep(0.05)
                elif next_case is not None:
                    stopped = True
                    next_case = None
        except BaseException:
            # Do not kill children or unlock their inherited lease on interruption.
            for pid, record in active.items():
                runner.append_ledger(ledger, {**record[1], "status": "PARENT_INTERRUPTED_CHILD_STATE_UNKNOWN", "child_pid": pid})
                record[5].close()
            raise
    return {"status": "STOPPED_NEW_CLAIMS" if stopped else "TERMINAL", "failures": sum(failures.values()),
            "root_allocation_sha256": manifest_sha, "reservations_reusable": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--host", choices=("mac", "vps"), required=True)
    parser.add_argument("--resource-receipt", type=Path, required=True)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    raw = args.manifest.read_bytes()
    digest = digest_bytes(raw)
    if digest != args.manifest_sha256:
        raise ValueError("CM2_ALLOCATION_PIN_MISMATCH")
    manifest = json.loads(raw)
    own, requests = validate_allocation(manifest, args.host, digest)
    receipt = json.loads(args.resource_receipt.read_text())
    if receipt.get("root_allocation_sha256") != digest:
        raise ValueError("CM2_RECEIPT_ALLOCATION_MISMATCH")
    if manifest["stage"] == "broad" and manifest["broad_block"] == "second" and receipt.get("second_broad_block_GO") is not True:
        raise ValueError("CM2_CONDITIONAL_BROAD_HOLD")
    bindings=receipt.get('case_bindings')
    if (len(requests)>1 or bindings is not None) and (type(bindings) is not dict
            or set(bindings)!={request['run_id'] for _,request in requests}):
        raise ValueError('CM2_EXACT_HOST_CASE_RECEIPT_MAP_REQUIRED')
    for _, request in requests:
        runner.preflight(request, receipt)
    if not args.run:
        print("CM2_BATCH_PURE_PREFLIGHT_NO_ENGINE_NO_ATTEMPT")
        return
    # Existing zero-engine public-data/API boundary before any budget claim.
    import uuid
    for case, request in requests:
        probe = Path(own["api_probe_root"]) / str(uuid.uuid4())
        command, env, cwd = runner.worker_process_spec(
            {**request, "artifact_dir": str(probe), "_request_path": case["request_path"]},
            None, case["request_sha256"], api_probe=True)
        result = subprocess.run(command, env=env, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (probe / "api-probe-worker.log").write_text(result.stdout)
        if result.returncode:
            raise ValueError("CM2_API_PREFLIGHT_FAILED_NO_ATTEMPT:" + str(probe))
        proof = json.loads((probe / "api-boundary-proof.json").read_text())
        if (proof["status"], proof["boundary_calls"], proof["native_engine_constructions"]) != ("ACTUAL_API_ENGINE_BOUNDARY_PASS", 1, 0):
            raise ValueError("CM2_API_PREFLIGHT_INVALID")
    result = dispatch(requests, receipt, own, digest)
    print(json.dumps(result, sort_keys=True))
    if result["failures"] or result["status"] != "TERMINAL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
