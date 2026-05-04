#!/usr/bin/env python3
"""CLI for CoinMaster Wave Engine research-only runs."""

from __future__ import annotations

import argparse
import json
import sys

from engine import run_matrix_research, run_single_research


def main() -> None:
    parser = argparse.ArgumentParser(description="Run research-only CoinMaster Wave Engine prototype.")
    parser.add_argument("--dataset", required=True, help="Path to JSON candles dataset with 4h and entry TF candles.")
    parser.add_argument(
        "--output-root",
        default="/var/lib/coinmaster/freqtrade/research/wave-engine/runs",
        help="Immutable run root. Override in restricted local sandboxes.",
    )
    parser.add_argument("--profile", help="Optional JSON file overriding default Trading Rules 2 profile.")
    parser.add_argument("--run-id", help="Optional explicit run id.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    single = subparsers.add_parser("single", help="Run one resolved candidate.")
    single.add_argument("--profile-json", help="Inline profile JSON.")

    matrix = subparsers.add_parser("matrix", help="Run coarse/deep parameter search with bounded candidate count.")
    matrix.add_argument("--mode", choices=["quick", "deep"], default="quick")
    matrix.add_argument("--sampling", choices=["random", "grid"], default="random")
    matrix.add_argument("--max-candidates", type=int, default=24)
    matrix.add_argument("--seed", type=int, default=73)

    args = parser.parse_args()
    profile: dict[str, object] = {}
    if args.profile:
        profile.update(json.loads(open(args.profile, "r", encoding="utf-8").read()))
    if getattr(args, "profile_json", None):
        profile.update(json.loads(args.profile_json))

    try:
        if args.command == "single":
            result = run_single_research(args.dataset, profile, args.output_root, run_id=args.run_id)
        else:
            result = run_matrix_research(
                args.dataset,
                profile,
                args.output_root,
                mode=args.mode,
                max_candidates=args.max_candidates,
                sampling=args.sampling,
                seed=args.seed,
                run_id=args.run_id,
            )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        raise

    print(json.dumps({"ok": True, **result}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
