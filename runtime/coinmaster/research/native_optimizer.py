"""Bounded, reproducible optimizer over the one native diagnostic lifecycle."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from time import monotonic
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path

from coinmaster.domain.wave_overlay import Candidate
from coinmaster.research.native_baseline import ExecutionPolicy, assert_report_boundaries, run_native_diagnostic
from coinmaster.venues.bybit_profile import BybitVenueProfile


SEED = 0  # Search is ordered/deterministic; retained in artifacts by contract.
BASELINE_ARTIFACT_SHA256 = "a68062578e4ce3080314164a6cbe5fb3b3afd1f10c2f4907b8e57639a9a74f25"
CAUSAL_V1_ID = "causal-v1"
CAUSAL_V1_AXIS = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.5, 6.48, 9.0)
CAUSAL_V1_REFINEMENT2_ID = "causal-v1-refinement2"
CAUSAL_V1_REFINEMENT2_AXIS = (2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9)
CAUSAL_V1_SENSITIVITY_ID = "causal-v1-sensitivity"
CANONICAL_REENTRY_AXIS = (7.5, 8.25, 9.75, 10.5)


def run_canonical_reentry_btc_pass(
    data_root: Path,
    baseline_report: Path,
    *,
    optimizer_id: str = "canonical-reentry-btc-size-v1",
    artifact_stem: str = "native-optimizer-canonical-reentry-btc",
    supersedes_reporting_checkpoint: str | None = None,
) -> dict:
    """Small canonical-only BTC-size pass after the re-entry reconciliation fix."""
    control = json.loads(baseline_report.read_text())
    if control["status"] != "NOT_FAITHFUL_DIAGNOSTIC" or control["terminal_open_positions"] != 0:
        raise ValueError("CANONICAL_REENTRY_CONTROL_NOT_FLAT")
    runtime = Path(__file__).resolve().parents[2]
    meta = {
        "optimizer_id": optimizer_id,
        "control_path": str(baseline_report),
        "control_sha256": sha256_file(baseline_report),
        "control_terminal_total": control["terminal_total"],
        "data_hash": control["data_hash"],
        "config_hash": control["config_hash"],
        "policy_hash": control["policy_hash"],
        "code_hashes": {name: sha256_file(runtime / name) for name in ("coinmaster/domain/wave_overlay.py", "coinmaster/strategy/wave_overlay.py", "coinmaster/research/native_baseline.py", "coinmaster/research/native_fixture.py")},
        "axis": {"btc_notional_multiplier": list(CANONICAL_REENTRY_AXIS)},
        "objective": "terminal ACTIVE + RESERVE; requires native-flat reconciliation",
        "liquidation_early_cutoff": "stop after the first native batch containing an authoritative liquidation audit",
        "ranking_eligible_for_live": False,
    }
    if supersedes_reporting_checkpoint is not None:
        meta["supersedes_reporting_checkpoint"] = supersedes_reporting_checkpoint
    runs = data_root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    partial_path = runs / f"{artifact_stem}.partial.json"
    expected = {"provenance": meta}
    partial = json.loads(partial_path.read_text()) if partial_path.exists() else {**expected, "results": []}
    if {key: partial.get(key) for key in expected} != expected:
        raise ValueError("CANONICAL_REENTRY_PARTIAL_PROVENANCE_MISMATCH")
    results = list(partial["results"])
    completed = {item["variant_id"] for item in results}
    for value in CANONICAL_REENTRY_AXIS:
        variant_id = f"btc_notional_{value:g}"
        if variant_id in completed:
            continue
        candidate = replace(Candidate(), btc_notional_multiplier=value)
        item = {"variant_id": variant_id, "candidate": asdict(candidate), "candidate_hash": hashlib.sha256(json.dumps(asdict(candidate), sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
        started = monotonic()
        try:
            report = run_native_diagnostic(data_root, include_funding=True, candidate=candidate, artifact_label=f"{artifact_stem}-{variant_id}", stop_on_liquidation=True)
            report["wall_time_seconds"] = str(monotonic() - started)
            if not report["early_liquidation_cutoff"]:
                assert_report_boundaries(report)
            item.update(report)
            item["terminal_flat"] = report["terminal_open_positions"] == 0
            item["early_cutoff"] = report["early_liquidation_cutoff"]
            item["eligible_within_assumption_profile"] = not item["early_cutoff"] and item["terminal_flat"] and report["liquidation_count"] == 0 and report["native_order_rejections"] == 0
        except Exception as error:
            item.update({"status": "FAILED", "error": f"{type(error).__name__}:{error}", "terminal_flat": False, "early_cutoff": False, "eligible_within_assumption_profile": False})
        results.append(item)
        partial_path.write_text(json.dumps({**expected, "results": results}, indent=2, sort_keys=True) + "\n")
    eligible = [item for item in results if item["eligible_within_assumption_profile"]]
    best = max(eligible, key=lambda item: Decimal(item["terminal_total"])) if eligible else None
    summary = {
        "status": "NOT_FAITHFUL_DIAGNOSTIC",
        "ranking_eligible_for_live": False,
        "provenance": meta,
        "control": {"variant_id": "v0", "terminal_total": control["terminal_total"], "terminal_flat": True},
        "results": results,
        "best_within_assumption_profile": best["variant_id"] if best else None,
        "best_delta_vs_control": str(Decimal(best["terminal_total"]) - Decimal(control["terminal_total"])) if best else None,
        "limitations": ["No candidate is live-rankable.", "Historical fee/tier, BBO/liquidity, settlement-mark, and intraminute liquidation assumptions remain unvalidated."],
    }
    json_path = runs / f"{artifact_stem}.json"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    csv_path = runs / f"{artifact_stem}.csv"
    fields = ("variant_id", "status", "candidate", "candidate_hash", "terminal_total", "terminal_active", "terminal_reserve", "terminal_flat", "early_cutoff", "fills", "native_fees", "funding", "native_order_rejections", "liquidation_count", "liquidation_value", "transfers", "wall_time_seconds", "error")
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: json.dumps(item[field], sort_keys=True) if field in {"candidate", "funding"} and field in item else item.get(field) for field in fields} for item in results)
    return summary | {"artifacts": {"json": str(json_path), "csv": str(csv_path), "partial": str(partial_path)}}


def run_canonical_reporting_btc_pass(data_root: Path, baseline_report: Path) -> dict:
    """Fresh four-point pass with the post-audit reporting contract only."""
    return run_canonical_reentry_btc_pass(
        data_root,
        baseline_report,
        optimizer_id="canonical-reporting-v2-btc-size",
        artifact_stem="native-optimizer-canonical-reporting-v2",
        supersedes_reporting_checkpoint="dfd6f4c",
    )


def run_canonical_reporting_v2_stress_validation(data_root: Path, control_report: Path) -> dict:
    """Fixed seen-data robustness checks for the reporting-v2 7.5x candidate.

    This is deliberately validation, not an optimizer: the control is reused,
    the four stress policies are predeclared, and no result selects a new
    trading parameter.
    """
    source = json.loads(control_report.read_text())
    control = next(
        (item for item in source.get("results", ()) if item.get("variant_id") == "btc_notional_7.5"),
        source,
    )
    if control["status"] != "NOT_FAITHFUL_DIAGNOSTIC" or control["terminal_open_positions"] != 0:
        raise ValueError("STRESS_CONTROL_NOT_FLAT_DIAGNOSTIC")
    candidate = replace(Candidate(), btc_notional_multiplier=7.5)
    policies = (
        ("fee_1_25x", ExecutionPolicy(fee_multiplier="1.25")),
        ("fee_1_5x", ExecutionPolicy(fee_multiplier="1.5")),
        ("latency_2m_spread_5bps", ExecutionPolicy(execution_delay_minutes=2, symmetric_adverse_spread_bps="5")),
        ("latency_5m_spread_10bps", ExecutionPolicy(execution_delay_minutes=5, symmetric_adverse_spread_bps="10")),
    )
    runtime = Path(__file__).resolve().parents[2]
    meta = {
        "validation_id": "canonical-reporting-v2-stress-validation",
        "status": "VALIDATION_SEEN_NOT_OOS + NOT_FAITHFUL_DIAGNOSTIC",
        "control_reused": {"path": str(control_report), "sha256": sha256_file(control_report), "terminal_total": control["terminal_total"]},
        "candidate": asdict(candidate),
        "candidate_hash": hashlib.sha256(json.dumps(asdict(candidate), sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "fixed_matrix": [{"variant_id": name, "policy": asdict(policy), "policy_hash": policy.hash} for name, policy in policies],
        "objective": "settled ACTIVE + RESERVE after costs; interval cash returns are reported separately",
        "code_hashes": {name: sha256_file(runtime / name) for name in ("coinmaster/domain/wave_overlay.py", "coinmaster/strategy/wave_overlay.py", "coinmaster/research/native_baseline.py", "coinmaster/research/native_fixture.py", "coinmaster/research/native_optimizer.py")},
        "ranking_eligible_for_live": False,
    }
    runs = data_root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    stem = "native-validation-canonical-reporting-v2-stress"
    partial_path = runs / f"{stem}.partial.json"
    expected = {"provenance": meta}
    partial = json.loads(partial_path.read_text()) if partial_path.exists() else {**expected, "results": []}
    if {key: partial.get(key) for key in expected} != expected:
        raise ValueError("STRESS_VALIDATION_PARTIAL_PROVENANCE_MISMATCH")
    results = list(partial["results"])
    completed = {item["variant_id"] for item in results}
    for variant_id, policy in policies:
        if variant_id in completed:
            continue
        item = {"variant_id": variant_id, "policy": asdict(policy), "policy_hash": policy.hash}
        started = monotonic()
        try:
            report = run_native_diagnostic(data_root, include_funding=True, candidate=candidate, execution_policy=policy, artifact_label=f"{stem}-{variant_id}", stop_on_liquidation=True)
            report["wall_time_seconds"] = str(monotonic() - started)
            if not report["early_liquidation_cutoff"]:
                assert_report_boundaries(report)
            item.update(report)
            item["terminal_flat"] = report["terminal_open_positions"] == 0
            item["excluded_for_liquidation"] = report["liquidation_count"] > 0
            item["eligible_within_assumption_profile"] = not report["early_liquidation_cutoff"] and not item["excluded_for_liquidation"] and item["terminal_flat"] and report["native_order_rejections"] == 0
        except Exception as error:
            item.update({"status": "FAILED", "error": f"{type(error).__name__}:{error}", "terminal_flat": False, "excluded_for_liquidation": True, "eligible_within_assumption_profile": False})
        results.append(item)
        partial_path.write_text(json.dumps({**expected, "results": results}, indent=2, sort_keys=True) + "\n")
    summary = {
        "status": "VALIDATION_SEEN_NOT_OOS + NOT_FAITHFUL_DIAGNOSTIC",
        "ranking_eligible_for_live": False,
        "provenance": meta,
        "control_reuse": {"terminal_total": control["terminal_total"], "interval_cash_terminal_total": control["summary"]["interval_cash_terminal_total"], "status": control["status"]},
        "results": results,
        "limitations": ["Fixed stress checks only; no parameter selection is permitted.", "Historical fee/tier, BBO/liquidity, settlement-mark, and intraminute liquidation assumptions remain unvalidated."],
    }
    json_path = runs / f"{stem}.json"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    csv_path = runs / f"{stem}.csv"
    fields = ("variant_id", "status", "policy", "policy_hash", "terminal_total", "terminal_active", "terminal_reserve", "terminal_flat", "early_liquidation_cutoff", "fills", "native_fees", "funding", "native_order_rejections", "pre_submit_tier_margin_gate_blocks", "liquidation_count", "liquidation_value", "excluded_for_liquidation", "wall_time_seconds", "error")
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: json.dumps(item[field], sort_keys=True) if field in {"policy", "funding", "pre_submit_tier_margin_gate_blocks"} and field in item else item.get(field) for field in fields} for item in results)
    return summary | {"artifacts": {"json": str(json_path), "csv": str(csv_path), "partial": str(partial_path)}}


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


def run_corrected_refinement(data_root: Path) -> dict:
    """Resume-safe BTC-size-only refinement under the corrected assumptions."""
    v0 = Candidate()
    variants = (("v0", v0),) + tuple(
        (f"btc_notional_{value:g}", replace(v0, btc_notional_multiplier=value))
        for value in (6.48, 7.29, 7.695, 8.10, 8.505, 8.91)
    )
    runs = data_root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    partial = runs / "native-optimizer-refinement.partial.json"
    previous = json.loads(partial.read_text()) if partial.exists() else {"results": []}
    results = list(previous["results"])
    completed = {item["variant_id"] for item in results}
    for variant_id, candidate in variants:
        if variant_id in completed:
            continue
        try:
            report = run_native_diagnostic(data_root, include_funding=True, candidate=candidate)
            item = {"variant_id": variant_id, "candidate": asdict(candidate), "candidate_hash": hashlib.sha256(json.dumps(asdict(candidate), sort_keys=True).encode()).hexdigest(), **report}
            item["eligible_for_assumption_ranking"] = item["terminal_open_positions"] == 0
        except Exception as error:
            item = {"variant_id": variant_id, "candidate": asdict(candidate), "status": "FAILED", "error": f"{type(error).__name__}:{error}", "eligible_for_assumption_ranking": False}
        results.append(item)
        partial.write_text(json.dumps({"results": results}, indent=2, sort_keys=True) + "\n")
    control = next(item for item in results if item["variant_id"] == "v0")
    ranked = [item for item in results if item["eligible_for_assumption_ranking"]]
    best = max(ranked, key=lambda item: Decimal(item["terminal_total"])) if ranked else None
    summary = {"status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible_for_live": False, "objective": "terminal ACTIVE + RESERVE after modeled costs, funding, and terminal close", "provenance": provenance(data_root), "search_axis": {"btc_notional_multiplier": [6.48, 7.29, 7.695, 8.10, 8.505, 8.91]}, "results": results, "best_assumption_profile_candidate": best["variant_id"] if best else None, "best_delta_vs_corrected_v0": str(Decimal(best["terminal_total"]) - Decimal(control["terminal_total"])) if best else None, "limitations": ["In-sample diagnostic only; not live ranking.", "Historical fee/tier and funding settlement assumptions remain unverified."]}
    target = runs / "native-optimizer-corrected-refinement.json"
    target.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    csv_path = runs / "native-optimizer-corrected-refinement.csv"
    fields = ("variant_id", "status", "eligible_for_assumption_ranking", "terminal_active", "terminal_reserve", "terminal_total", "fills", "native_fees", "funding_events_posted", "native_order_rejections", "terminal_open_positions", "candidate_hash", "error")
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows({field: item.get(field) for field in fields} for item in results)
    return summary | {"artifacts": {"json": str(target), "csv": str(csv_path), "partial": str(partial)}}


def causal_v1_coarse_variants() -> tuple[tuple[str, Candidate], ...]:
    """The only causal-v1 coarse axis: BTC size, with v0=9.0 as control."""
    v0 = Candidate()
    return tuple(
        ("v0" if value == 9.0 else f"btc_notional_{value:g}", replace(v0, btc_notional_multiplier=value))
        for value in CAUSAL_V1_AXIS
    )


def causal_v1_refinement_variants(value: float) -> tuple[tuple[str, Candidate], ...]:
    """One bounded 5–10% local refinement; never extends the coarse range."""
    v0 = Candidate()
    values = tuple(sorted({round(value * factor, 12) for factor in (0.90, 0.95, 1.05, 1.10)}))
    return tuple((f"btc_notional_refine_{item:g}", replace(v0, btc_notional_multiplier=item)) for item in values)


def causal_v1_provenance(data_root: Path) -> dict:
    """Capture the exact, current baseline report without comparing old runs."""
    baseline_path = data_root / "runs" / "native-diagnostic-report.json"
    baseline = json.loads(baseline_path.read_text())
    if baseline["status"] != "NOT_FAITHFUL_DIAGNOSTIC" or baseline["ranking_eligible"]:
        raise ValueError("CAUSAL_V1_REQUIRES_NON_RANKING_NATIVE_BASELINE")
    return {
        "optimizer_id": CAUSAL_V1_ID,
        "seed": SEED,
        "baseline_report_path": str(baseline_path),
        "baseline_report_sha256": sha256_file(baseline_path),
        "baseline_config": baseline["config"],
        "baseline_config_hash": baseline["config_hash"],
        "baseline_data_hash": baseline["data_hash"],
        "baseline_code_hash": baseline["code_hash"],
        "baseline_policy": baseline["policy"],
        "baseline_policy_hash": baseline["policy_hash"],
        "optimizer_code_hash": sha256_file(Path(__file__)),
    }


def causal_v1_item(variant_id: str, candidate: Candidate, data_root: Path, meta: dict) -> dict:
    """One intentionally fresh native lifecycle; failures are first-class rows."""
    item = {
        "variant_id": variant_id,
        "candidate": asdict(candidate),
        "candidate_hash": hashlib.sha256(json.dumps(asdict(candidate), sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "provenance": meta,
    }
    try:
        report = run_native_diagnostic(data_root, include_funding=True, candidate=candidate)
        item.update(report)
        item["terminal_flat"] = report["terminal_open_positions"] == 0
        item["eligible_for_assumption_ranking"] = False
    except Exception as error:  # Every attempt, including failures, stays durable.
        item.update({"status": "FAILED", "error": f"{type(error).__name__}:{error}", "terminal_flat": False, "eligible_for_assumption_ranking": False})
    return item


def causal_v1_csv_rows(results: list[dict]) -> list[dict]:
    """Keep required per-candidate evidence in the human-portable CSV too."""
    rows = []
    for item in results:
        summary = item.get("summary", {})
        funding = item.get("funding", {})
        provenance_row = item["provenance"]
        rows.append({
            "variant_id": item["variant_id"], "status": item["status"], "candidate": json.dumps(item["candidate"], sort_keys=True),
            "candidate_hash": item["candidate_hash"], "roi": summary.get("roi"), "max_drawdown_amount": summary.get("max_drawdown_amount"),
            "max_drawdown_percent": summary.get("max_drawdown_percent"), "monthly_returns": json.dumps(summary.get("monthly_returns"), sort_keys=True),
            "fills": item.get("fills"), "funding_events": funding.get("count"), "native_fees": item.get("native_fees"),
            "native_order_rejections": item.get("native_order_rejections"), "liquidation_count": item.get("liquidation_count"),
            "liquidation_value": item.get("liquidation_value"), "terminal_active": item.get("terminal_active"),
            "terminal_reserve": item.get("terminal_reserve"), "terminal_total": item.get("terminal_total"),
            "terminal_flat": item.get("terminal_flat"), "baseline_report_sha256": provenance_row["baseline_report_sha256"],
            "baseline_config_hash": provenance_row["baseline_config_hash"], "baseline_data_hash": provenance_row["baseline_data_hash"],
            "baseline_code_hash": provenance_row["baseline_code_hash"], "baseline_policy_hash": provenance_row["baseline_policy_hash"],
            "error": item.get("error"),
        })
    return rows


def run_causal_v1_optimizer(data_root: Path) -> dict:
    """Separate causal-v1 pass; it neither consumes nor overwrites legacy runs."""
    meta = causal_v1_provenance(data_root)
    runs = data_root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    partial_path = runs / "native-optimizer-causal-v1.partial.json"
    expected = {"optimizer_id": CAUSAL_V1_ID, "provenance": meta}
    partial = json.loads(partial_path.read_text()) if partial_path.exists() else {**expected, "results": []}
    if {key: partial.get(key) for key in expected} != expected:
        raise ValueError("CAUSAL_V1_PARTIAL_PROVENANCE_MISMATCH")
    results = list(partial["results"])
    completed = {item["variant_id"] for item in results}
    for variant_id, candidate in causal_v1_coarse_variants():
        if variant_id not in completed:
            results.append(causal_v1_item(variant_id, candidate, data_root, meta))
            partial_path.write_text(json.dumps({**expected, "results": results}, indent=2, sort_keys=True) + "\n")
    coarse_ids = [variant_id for variant_id, _ in causal_v1_coarse_variants()]
    coarse = [item for item in results if item["variant_id"] in coarse_ids and item["status"] == "NOT_FAITHFUL_DIAGNOSTIC" and item["terminal_flat"]]
    best_coarse = max(coarse, key=lambda item: Decimal(item["terminal_total"])) if coarse else None
    refinement = []
    boundary = None
    if best_coarse:
        best_index = coarse_ids.index(best_coarse["variant_id"])
        if best_index in (0, len(coarse_ids) - 1):
            boundary = {"variant_id": best_coarse["variant_id"], "position": "lower" if best_index == 0 else "upper", "extended": False}
        else:
            refinement = list(causal_v1_refinement_variants(best_coarse["candidate"]["btc_notional_multiplier"]))
            for variant_id, candidate in refinement:
                if variant_id not in completed:
                    results.append(causal_v1_item(variant_id, candidate, data_root, meta))
                    completed.add(variant_id)
                    partial_path.write_text(json.dumps({**expected, "results": results}, indent=2, sort_keys=True) + "\n")
    valid = [item for item in results if item["status"] == "NOT_FAITHFUL_DIAGNOSTIC" and item["terminal_flat"]]
    best = max(valid, key=lambda item: Decimal(item["terminal_total"])) if valid else None
    control = next(item for item in results if item["variant_id"] == "v0")
    rerun = causal_v1_item(f"{best['variant_id']}__fresh_rerun", Candidate(**best["candidate"]), data_root, meta) if best else None
    rerun_verified = bool(rerun and rerun["status"] == "NOT_FAITHFUL_DIAGNOSTIC" and all(
        rerun[key] == best[key] for key in ("terminal_active", "terminal_reserve", "terminal_total", "fills", "native_fees", "native_order_rejections", "terminal_open_positions")
    ) and rerun["funding"] == best["funding"])
    summary = {
        "optimizer_id": CAUSAL_V1_ID, "status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible_for_live": False,
        "objective": "terminal ACTIVE + RESERVE after native fixture fees, funding, and terminal close",
        "provenance": meta, "search_axis": {"btc_notional_multiplier": list(CAUSAL_V1_AXIS), "v0_control": "9.0"},
        "refinement": {"performed": bool(refinement), "axis": [candidate.btc_notional_multiplier for _, candidate in refinement], "boundary": boundary},
        "results": results, "best_assumption_profile_candidate": best["variant_id"] if best else None,
        "best_delta_vs_v0": str(Decimal(best["terminal_total"]) - Decimal(control["terminal_total"])) if best and control["status"] == "NOT_FAITHFUL_DIAGNOSTIC" else None,
        "fresh_rerun": rerun, "fresh_rerun_verified": rerun_verified,
        "limitations": ["All rows are NOT_FAITHFUL_DIAGNOSTIC and non-ranking for live.", "Historical fee/tier applicability, exact settlement marks, BBO/liquidity, and intraminute liquidation are unvalidated."],
    }
    json_path = runs / "native-optimizer-causal-v1.json"
    csv_path = runs / "native-optimizer-causal-v1.csv"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    rows = causal_v1_csv_rows(results)
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["variant_id"])
        writer.writeheader(); writer.writerows(rows)
    summary["artifacts"] = {"json": str(json_path), "csv": str(csv_path), "partial": str(partial_path)}
    return summary


def causal_v1_refinement2_variants() -> tuple[tuple[str, Candidate], ...]:
    """Explicitly authorized bracket only; no automatic axis extension."""
    v0 = Candidate()
    return tuple((f"btc_notional_bracket_{value:g}", replace(v0, btc_notional_multiplier=value)) for value in CAUSAL_V1_REFINEMENT2_AXIS)


def run_causal_v1_refinement2(data_root: Path) -> dict:
    """Link seven new bracket runs to, but never mutate, causal-v1 evidence."""
    runs = data_root / "runs"
    parent_path = runs / "native-optimizer-causal-v1.json"
    parent = json.loads(parent_path.read_text())
    if parent.get("optimizer_id") != CAUSAL_V1_ID:
        raise ValueError("CAUSAL_V1_REFINEMENT2_PARENT_MISMATCH")
    parent_hash = sha256_file(parent_path)
    parent_provenance = parent["provenance"]
    meta = {
        "optimizer_id": CAUSAL_V1_REFINEMENT2_ID, "seed": SEED,
        "parent_artifact_path": str(parent_path), "parent_artifact_sha256": parent_hash,
        "baseline_report_sha256": parent_provenance["baseline_report_sha256"],
        "baseline_config": parent_provenance["baseline_config"], "baseline_config_hash": parent_provenance["baseline_config_hash"],
        "baseline_data_hash": parent_provenance["baseline_data_hash"], "baseline_code_hash": parent_provenance["baseline_code_hash"],
        "baseline_policy": parent_provenance["baseline_policy"], "baseline_policy_hash": parent_provenance["baseline_policy_hash"],
        "optimizer_code_hash": sha256_file(Path(__file__)),
    }
    partial_path = runs / "native-optimizer-causal-v1-refinement2.partial.json"
    expected = {"optimizer_id": CAUSAL_V1_REFINEMENT2_ID, "provenance": meta}
    partial = json.loads(partial_path.read_text()) if partial_path.exists() else {**expected, "results": []}
    if {key: partial.get(key) for key in expected} != expected:
        raise ValueError("CAUSAL_V1_REFINEMENT2_PARTIAL_PROVENANCE_MISMATCH")
    new_results = list(partial["results"])
    completed = {item["variant_id"] for item in new_results}
    for variant_id, candidate in causal_v1_refinement2_variants():
        if variant_id not in completed:
            new_results.append(causal_v1_item(variant_id, candidate, data_root, meta))
            partial_path.write_text(json.dumps({**expected, "results": new_results}, indent=2, sort_keys=True) + "\n")
    results = list(parent["results"]) + new_results
    valid = [item for item in results if item["status"] == "NOT_FAITHFUL_DIAGNOSTIC" and item["terminal_flat"]]
    best = max(valid, key=lambda item: Decimal(item["terminal_total"])) if valid else None
    rerun = causal_v1_item(f"{best['variant_id']}__fresh_rerun", Candidate(**best["candidate"]), data_root, meta) if best else None
    rerun_verified = bool(rerun and rerun["status"] == "NOT_FAITHFUL_DIAGNOSTIC" and rerun["terminal_flat"] and len(rerun["summary"]["monthly_returns"]) == 24 and all(
        rerun[key] == best[key] for key in ("terminal_active", "terminal_reserve", "terminal_total", "fills", "native_fees", "native_order_rejections", "terminal_open_positions")
    ) and rerun["funding"] == best["funding"])
    summary = {
        "optimizer_id": CAUSAL_V1_REFINEMENT2_ID, "status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible_for_live": False,
        "objective": "terminal ACTIVE + RESERVE after native fixture fees, funding, and terminal close",
        "provenance": meta, "search_axis": {"btc_notional_multiplier": list(CAUSAL_V1_REFINEMENT2_AXIS), "bracket": "[2.2,3.0]", "automatic_extension": False},
        "prior_result_count": len(parent["results"]), "new_result_count": len(new_results), "results": results,
        "best_assumption_profile_candidate": best["variant_id"] if best else None,
        "fresh_rerun": rerun, "fresh_rerun_verified": rerun_verified,
        "limitations": ["All rows are NOT_FAITHFUL_DIAGNOSTIC and non-ranking for live.", "Historical fee/tier applicability, exact settlement marks, BBO/liquidity, and intraminute liquidation are unvalidated."],
    }
    json_path = runs / "native-optimizer-causal-v1-refinement2.json"
    csv_path = runs / "native-optimizer-causal-v1-refinement2.csv"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    rows = causal_v1_csv_rows(results)
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["variant_id"])
        writer.writeheader(); writer.writerows(rows)
    summary["artifacts"] = {"json": str(json_path), "csv": str(csv_path), "partial": str(partial_path)}
    return summary


def causal_v1_sensitivity_variants() -> tuple[tuple[str, Candidate], ...]:
    """One-factor-only bounded sensitivity around the confirmed 2.4 size."""
    control = replace(Candidate(), btc_notional_multiplier=2.4)
    variants: list[tuple[str, Candidate]] = [("control_2.4", control)]
    for shift in (-0.125, -0.0625, 0.0625, 0.125):
        variants.append((f"sol_entry_z_shift_{shift:+g}", replace(control, sol_entry_z=tuple(value + shift for value in control.sol_entry_z))))
    for field, values in (("relative_days", (60, 70)), ("beta_days", (255, 285)), ("z_history_days", (165, 195)), ("wave_history_days", (715, 745)), ("sol_max_holding_days", (9, 19))):
        variants.extend((f"{field}_{value}", replace(control, **{field: value})) for value in values)
    return tuple(variants)


def run_causal_v1_sensitivity(data_root: Path) -> dict:
    """Run exactly the approved independent one-axis variants, linked to refinement2."""
    runs = data_root / "runs"
    parent_path = runs / "native-optimizer-causal-v1-refinement2.json"
    parent = json.loads(parent_path.read_text())
    if parent.get("optimizer_id") != CAUSAL_V1_REFINEMENT2_ID:
        raise ValueError("CAUSAL_V1_SENSITIVITY_PARENT_MISMATCH")
    parent_provenance = parent["provenance"]
    meta = {
        "optimizer_id": CAUSAL_V1_SENSITIVITY_ID, "seed": SEED,
        "parent_artifact_path": str(parent_path), "parent_artifact_sha256": sha256_file(parent_path),
        "baseline_report_sha256": parent_provenance["baseline_report_sha256"],
        "baseline_config": parent_provenance["baseline_config"], "baseline_config_hash": parent_provenance["baseline_config_hash"],
        "baseline_data_hash": parent_provenance["baseline_data_hash"], "baseline_code_hash": parent_provenance["baseline_code_hash"],
        "baseline_policy": parent_provenance["baseline_policy"], "baseline_policy_hash": parent_provenance["baseline_policy_hash"],
        "optimizer_code_hash": sha256_file(Path(__file__)),
    }
    partial_path = runs / "native-optimizer-causal-v1-sensitivity.partial.json"
    expected = {"optimizer_id": CAUSAL_V1_SENSITIVITY_ID, "provenance": meta}
    partial = json.loads(partial_path.read_text()) if partial_path.exists() else {**expected, "results": []}
    if {key: partial.get(key) for key in expected} != expected:
        raise ValueError("CAUSAL_V1_SENSITIVITY_PARTIAL_PROVENANCE_MISMATCH")
    results = list(partial["results"])
    completed = {item["variant_id"] for item in results}
    for variant_id, candidate in causal_v1_sensitivity_variants():
        if variant_id not in completed:
            results.append(causal_v1_item(variant_id, candidate, data_root, meta))
            partial_path.write_text(json.dumps({**expected, "results": results}, indent=2, sort_keys=True) + "\n")
    valid = [item for item in results if item["status"] == "NOT_FAITHFUL_DIAGNOSTIC" and item["terminal_flat"]]
    best = max(valid, key=lambda item: Decimal(item["terminal_total"])) if valid else None
    rerun = causal_v1_item(f"{best['variant_id']}__fresh_rerun", Candidate(**best["candidate"]), data_root, meta) if best and best["variant_id"] != "control_2.4" else None
    rerun_verified = None if rerun is None else bool(rerun["status"] == "NOT_FAITHFUL_DIAGNOSTIC" and rerun["terminal_flat"] and len(rerun["summary"]["monthly_returns"]) == 24 and all(
        rerun[key] == best[key] for key in ("terminal_active", "terminal_reserve", "terminal_total", "fills", "native_fees", "native_order_rejections", "terminal_open_positions")
    ) and rerun["funding"] == best["funding"])
    summary = {
        "optimizer_id": CAUSAL_V1_SENSITIVITY_ID, "status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible_for_live": False,
        "objective": "terminal ACTIVE + RESERVE after native fixture fees, funding, and terminal close",
        "provenance": meta, "control": "control_2.4", "one_axis_only": True,
        "search_space": [{"variant_id": variant_id, "candidate": asdict(candidate)} for variant_id, candidate in causal_v1_sensitivity_variants()],
        "results": results, "best_assumption_profile_candidate": best["variant_id"] if best else None,
        "fresh_rerun": rerun, "fresh_rerun_verified": rerun_verified,
        "limitations": ["All rows are NOT_FAITHFUL_DIAGNOSTIC and non-ranking for live.", "No winning axes are combined or expanded in this pass.", "Historical fee/tier applicability, exact settlement marks, BBO/liquidity, and intraminute liquidation are unvalidated."],
    }
    json_path = runs / "native-optimizer-causal-v1-sensitivity.json"
    csv_path = runs / "native-optimizer-causal-v1-sensitivity.csv"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    rows = causal_v1_csv_rows(results)
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["variant_id"])
        writer.writeheader(); writer.writerows(rows)
    summary["artifacts"] = {"json": str(json_path), "csv": str(csv_path), "partial": str(partial_path)}
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("var/data"))
    parser.add_argument("--corrected-controls", action="store_true")
    parser.add_argument("--corrected-refinement", action="store_true")
    parser.add_argument("--causal-v1", action="store_true")
    parser.add_argument("--causal-v1-refinement2", action="store_true")
    parser.add_argument("--causal-v1-sensitivity", action="store_true")
    args = parser.parse_args()
    report = run_causal_v1_sensitivity(args.data_root) if args.causal_v1_sensitivity else run_causal_v1_refinement2(args.data_root) if args.causal_v1_refinement2 else run_causal_v1_optimizer(args.data_root) if args.causal_v1 else run_corrected_refinement(args.data_root) if args.corrected_refinement else run_corrected_controls(args.data_root) if args.corrected_controls else run_optimizer(args.data_root)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
