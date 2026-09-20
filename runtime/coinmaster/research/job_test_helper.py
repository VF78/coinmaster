"""Test-only typed research child; reachable only through injected allowlists."""
from __future__ import annotations

import argparse
import json
import signal
import time
from pathlib import Path


def emit(kind: str, request: dict, **body) -> None:
    print(json.dumps({"type": kind, "request_hash": request["request_hash"], "config_hash": request["config_hash"], **body}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("complete", "sleep", "ignore-term", "blocked", "wrong-hash"), required=True)
    parser.add_argument("--job-request", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.job_request.read_text())
    emit("progress", request, progress=10)
    if args.mode == "complete":
        time.sleep(0.5)
    if args.mode == "ignore-term":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    if args.mode in {"sleep", "ignore-term"}:
        time.sleep(30)
    if args.mode == "blocked":
        emit("result", request, status="BLOCKED", blockers=["MISSING_TEST_DATA"])
        raise SystemExit(2)
    artifact_dir = Path(request["artifact_dir"]); artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact = artifact_dir / "result.json"
    report = {"status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible": False, "terminal_total": "UNKNOWN_TEST_HELPER"}
    artifact.write_text(json.dumps(report, sort_keys=True) + "\n")
    emitted_request_hash = "wrong" if args.mode == "wrong-hash" else request["request_hash"]
    envelope = {"type": "result", "status": "COMPLETED", "request_hash": emitted_request_hash, "config_hash": request["config_hash"], "artifact": str(artifact), "report": report}
    (artifact_dir / "result-envelope.json").write_text(json.dumps(envelope, sort_keys=True) + "\n")
    emit("progress", request, progress=90)
    print(json.dumps(envelope), flush=True)


if __name__ == "__main__":
    main()
