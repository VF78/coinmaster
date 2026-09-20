"""Deterministic subprocess helper; it is test-only and never production-allowed."""
from __future__ import annotations

import argparse
import json
import time


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--mode", choices=("complete", "sleep", "blocked"), required=True)
    args = parser.parse_args()
    print(json.dumps({"progress": 10}), flush=True)
    if args.mode == "complete":
        time.sleep(0.1)
    if args.mode == "sleep":
        time.sleep(30)
    if args.mode == "blocked":
        print(json.dumps({"status": "BLOCKED", "blockers": ["MISSING_TEST_DATA"]}), flush=True)
        raise SystemExit(2)
    print(json.dumps({"progress": 90}), flush=True)
    print(json.dumps({"status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible": False, "terminal_total": "UNKNOWN_TEST_HELPER"}), flush=True)


if __name__ == "__main__":
    main()
