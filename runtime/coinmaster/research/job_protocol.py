"""Small, fail-closed protocol shared by native research job children."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any


LAUNCH_PERMIT_TIMEOUT_SECONDS = 1.5


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report_summary(report: dict[str, Any]) -> dict[str, Any]:
    """Return the only report data permitted in the child stdout envelope."""
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "status": report.get("status"),
        "ranking_eligible": report.get("ranking_eligible"),
        "terminal_total": report.get("terminal_total", summary.get("terminal_total")),
    }


def wait_for_launch_permit(request: dict[str, Any]) -> bool:
    """Do no work until the owner has durably recorded this exact child.

    The permit is created only after the parent persisted PID, process identity
    and owner token. If a parent dies in that narrow interval, this child exits
    by itself without creating a report artifact.
    """
    try:
        permit_path = Path(request["launch_permit"])
        request_hash = request["request_hash"]
        owner_token = request["launch_owner_token"]
    except (KeyError, TypeError):
        return False
    deadline = time.monotonic() + LAUNCH_PERMIT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            permit = json.loads(permit_path.read_text())
        except (OSError, json.JSONDecodeError):
            time.sleep(0.02)
            continue
        if (
            permit.get("request_hash") == request_hash
            and permit.get("pid") == os.getpid()
            and isinstance(permit.get("owner_token"), str)
            and secrets.compare_digest(permit["owner_token"], owner_token)
            and isinstance(permit.get("process_identity"), str)
        ):
            return True
        return False
    return False
