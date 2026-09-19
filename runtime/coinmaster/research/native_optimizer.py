"""Bounded, reproducible optimizer over the one native diagnostic lifecycle."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path

from coinmaster.domain.wave_overlay import Candidate
from coinmaster.research.native_baseline import run_native_diagnostic
from coinmaster.venues.bybit_profile import BybitVenueProfile


SEED = 0  # Search is ordered/deterministic; retained in artifacts by contract.
BASELINE_ARTIFACT_SHA256 = "a68062578e4ce3080314164a6cbe5fb3b3afd1f10c2f4907b8e57639a9a74f25"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_variants() -> tuple[tuple[str, Candidate], ...]:
    """Compact spec-shaped sensitivity; venue and fee assumptions never vary."""
    v0 = Candidate()
    return (
        ("v0", v0),
        ("btc_notional_minus_10pct", replace(v0, btc_notional_multiplier=8.1)),
        ("btc_notional_plus_10pct", replace(v0, btc_notional_multiplier=9.9)),
        ("sol_z_minus_0125", replace(v0, sol_entry_z=(1.125, 2.375, 3.625))),
        ("sol_z_plus_0125", replace(v0, sol_entry_z=(1.375, 2.625, 3.875))),
    )


def provenance(data_root: Path) -> dict:
    runtime = Path(__file__).resolve().parents[2]
    profile = BybitVenueProfile.from_raw(runtime)
    code_files = (
        runtime / "coinmaster/domain/wave_overlay.py",
        runtime / "coinmaster/strategy/wave_overlay.py",
        runtime / "coinmaster/research/native_baseline.py",
        Path(__file__),
    )
    return {
        "seed": SEED,
        "data_manifest_sha256": sha256_file(data_root / "bybit-1m/manifest.json"),
        "profile_hashes": profile.hashes,
        "code_hashes": {str(path.relative_to(runtime)): sha256_file(path) for path in code_files},
        "baseline_artifact_sha256": sha256_file(data_root / "runs/native-diagnostic-report.json"),
        "expected_baseline_artifact_sha256": BASELINE_ARTIFACT_SHA256,
        "assumption_profile": "current_public_bybit_tiers; BTC 40x/SOL 20x; native fixture fee model",
    }


def run_optimizer(data_root: Path) -> dict:
    """Run each candidate with a fresh native Engine and funding journal."""
    meta = provenance(data_root)
    if meta["baseline_artifact_sha256"] != BASELINE_ARTIFACT_SHA256:
        raise ValueError("baseline artifact hash does not match immutable v0 control")
    results: list[dict] = []
    for variant_id, candidate in candidate_variants():
        item = {"variant_id": variant_id, "candidate": asdict(candidate), "candidate_hash": hashlib.sha256(json.dumps(asdict(candidate), sort_keys=True).encode()).hexdigest()}
        try:
            report = run_native_diagnostic(data_root, include_funding=True, candidate=candidate)
            item.update(report)
            item["eligible_for_assumption_ranking"] = report["status"] == "NOT_FAITHFUL_DIAGNOSTIC" and report["terminal_open_positions"] == 0
        except Exception as error:  # Failed/incomplete candidates are retained, never ranked.
            item.update({"status": "FAILED", "error": f"{type(error).__name__}:{error}", "eligible_for_assumption_ranking": False})
        results.append(item)
    valid = [item for item in results if item["eligible_for_assumption_ranking"]]
    best = max(valid, key=lambda item: Decimal(item["terminal_total"])) if valid else None
    v0 = next(item for item in results if item["variant_id"] == "v0")
    summary = {
        "status": "NOT_FAITHFUL_DIAGNOSTIC",
        "ranking_eligible_for_live": False,
        "objective": "terminal ACTIVE + RESERVE after native fees, funding, terminal close",
        "provenance": meta,
        "search_space": [{"variant_id": key, "candidate": asdict(value)} for key, value in candidate_variants()],
        "results": results,
        "best_assumption_profile_candidate": best["variant_id"] if best else None,
        "best_delta_vs_v0": str(Decimal(best["terminal_total"]) - Decimal(v0["terminal_total"])) if best else None,
        "limitations": ["Results are rankable only within the explicit current-profile assumption.", "Historical fee/tier applicability, exact funding settlement marks, and intraminute liquidation remain unverified."],
    }
    runs = data_root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    json_path = runs / "native-optimizer-report.json"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    csv_path = runs / "native-optimizer-results.csv"
    fields = ("variant_id", "status", "eligible_for_assumption_ranking", "terminal_active", "terminal_reserve", "terminal_total", "fills", "native_fees", "funding_events_posted", "native_order_rejections", "terminal_open_positions", "candidate_hash", "error")
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: item.get(field) for field in fields} for item in results)
    summary["artifacts"] = {"json": str(json_path), "csv": str(csv_path)}
    return summary


def run_corrected_controls(data_root: Path) -> dict:
    """Re-evaluate v0 and the prior winner after a correctness correction."""
    controls = candidate_variants()[:2]
    results = []
    for variant_id, candidate in controls:
        report = run_native_diagnostic(data_root, include_funding=True, candidate=candidate)
        results.append({"variant_id": variant_id, "candidate": asdict(candidate), **report})
    summary = {
        "status": "NOT_FAITHFUL_DIAGNOSTIC",
        "supersedes": "native-optimizer-report.json",
        "reason": "P3 correctness correction: staged lifecycle, beta gate, exact z window, gross guard, terminal reentry semantics",
        "results": results,
        "ranking_eligible_for_live": False,
    }
    target = data_root / "runs/native-optimizer-corrected-controls.json"
    target.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary | {"artifact": str(target)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("var/data"))
    parser.add_argument("--corrected-controls", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_corrected_controls(args.data_root) if args.corrected_controls else run_optimizer(args.data_root), sort_keys=True))


if __name__ == "__main__":
    main()
