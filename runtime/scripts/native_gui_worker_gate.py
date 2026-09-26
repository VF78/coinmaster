#!/usr/bin/env python3
"""Validate identity, safety, freshness, and strategy hash from raw worker status."""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from typing import Any

MAX_AGE_NS = 15_000_000_000
MAX_FUTURE_SKEW_NS = 5_000_000_000


def worker_fingerprint(payload: Any, *, now_ns: int | None = None) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("worker status must be a JSON object")
    if (payload.get("version") != "hl-stageg-projection-v1"
            or payload.get("instance_id") != "hl-stageg-testnet"
            or payload.get("projection_state") != "READY"
            or payload.get("mode") != "sandbox"
            or payload.get("live_order_capability") is not False
            or payload.get("provenance") != "SANDBOX_LOCAL_READ_ONLY_WORKER_PROJECTION"):
        raise ValueError("raw worker identity or safety state is invalid")
    observed_at_ns = payload.get("observed_at_ns")
    if isinstance(observed_at_ns, bool) or not isinstance(observed_at_ns, int) or observed_at_ns <= 0:
        raise ValueError("raw worker observation timestamp is invalid")
    now_ns = time.time_ns() if now_ns is None else now_ns
    if observed_at_ns > now_ns + MAX_FUTURE_SKEW_NS:
        raise ValueError("raw worker observation timestamp is in the future")
    if now_ns - observed_at_ns > MAX_AGE_NS:
        raise ValueError("raw worker status is stale")
    hashes = payload.get("hashes")
    strategy = hashes.get("strategy_sha256") if isinstance(hashes, dict) else None
    if not isinstance(strategy, str) or not re.fullmatch(r"[0-9a-f]{64}", strategy):
        raise ValueError("raw worker strategy hash is invalid")
    return "READY", strategy


def fetch_worker_fingerprint(url: str) -> tuple[str, str]:
    request = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=3) as response:
        payload = json.loads(response.read())
    return worker_fingerprint(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    try:
        state, strategy = fetch_worker_fingerprint(args.url)
    except (OSError, TimeoutError, ValueError, TypeError) as error:
        raise SystemExit(f"raw worker fingerprint rejected: {error}") from error
    print(state)
    print(strategy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
