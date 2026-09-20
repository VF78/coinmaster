"""Validation-only scenarios for the current causal-v1 candidate.

These are seen-data diagnostics, not an optimizer or out-of-sample claim.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path

from coinmaster.domain.wave_overlay import Candidate
from coinmaster.research.native_baseline import ExecutionPolicy, TRADING_END_MS, TRADING_START_MS, run_native_diagnostic, save_diagnostic_report


VALIDATION_ID = "causal-v1-validation-v3-nonmatching-signal"
WINDOW_END_MS = 1_756_684_800_000  # 2025-09-01T00:00:00Z


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_candidate() -> Candidate:
    return replace(Candidate(), btc_notional_multiplier=2.4, sol_entry_z=(1.125, 2.375, 3.625))


def stress_policy(delay_minutes: int = 1, spread_bps: str = "0", fee_multiplier: str = "1") -> ExecutionPolicy:
    return ExecutionPolicy(
        version="bybit-1m-close-validation-stress-v1",
        latency=f"first_available_1m_close_after_{delay_minutes}m_decision_latency_ASSUMPTION",
        fees=f"NATIVE_INSTRUMENT_MAKER_TAKER_0.001_PER_SIDE_X{fee_multiplier}_ASSUMPTION",
        spread_slippage_liquidity=f"SYMMETRIC_{spread_bps}BPS_BID_ASK_PROXY_ASSUMPTION_NO_BBO_L2",
        execution_delay_minutes=delay_minutes,
        symmetric_adverse_spread_bps=spread_bps,
        fee_multiplier=fee_multiplier,
        nonmatching_daily_signals=True,
    )


def scenarios() -> tuple[dict, ...]:
    return (
        {"id": "control_full_24m", "start": TRADING_START_MS, "end": TRADING_END_MS, "policy": stress_policy()},
        {"id": "validation_seen_2024_09_2025_09", "start": TRADING_START_MS, "end": WINDOW_END_MS, "policy": stress_policy()},
        {"id": "validation_seen_2025_09_2026_09", "start": WINDOW_END_MS, "end": TRADING_END_MS, "policy": stress_policy()},
        {"id": "fee_stress_1_25x", "start": TRADING_START_MS, "end": TRADING_END_MS, "policy": stress_policy(fee_multiplier="1.25")},
        {"id": "fee_stress_1_50x", "start": TRADING_START_MS, "end": TRADING_END_MS, "policy": stress_policy(fee_multiplier="1.5")},
        {"id": "execution_stress_2m_5bps", "start": TRADING_START_MS, "end": TRADING_END_MS, "policy": stress_policy(delay_minutes=2, spread_bps="5")},
        {"id": "execution_stress_5m_10bps", "start": TRADING_START_MS, "end": TRADING_END_MS, "policy": stress_policy(delay_minutes=5, spread_bps="10")},
    )


def validation_item(scenario: dict, data_root: Path, provenance: dict) -> dict:
    """A fresh engine and journal are constructed inside every diagnostic call."""
    item = {"scenario_id": scenario["id"], "scenario": {"start_ms": scenario["start"], "end_ms": scenario["end"], "policy": asdict(scenario["policy"])}, "provenance": provenance}
    try:
        report = run_native_diagnostic(
            data_root, include_funding=True, candidate=current_candidate(), trading_start_ms=scenario["start"],
            trading_end_ms=scenario["end"], execution_policy=scenario["policy"], artifact_label=f"validation-{scenario['id']}",
        )
        item.update(report)
        item["diagnostic_status"] = report["status"]
        item["status"] = "VALIDATION_SEEN_NOT_OOS"
        item["ranking_eligible"] = False
        item["terminal_flat"] = report["terminal_open_positions"] == 0
    except Exception as error:
        item.update({"status": "FAILED", "error": f"{type(error).__name__}:{error}", "terminal_flat": False, "ranking_eligible": False})
    return item


def validation_csv_rows(results: list[dict]) -> list[dict]:
    rows = []
    for item in results:
        summary, funding = item.get("summary", {}), item.get("funding", {})
        rows.append({
            "scenario_id": item["scenario_id"], "status": item["status"], "diagnostic_status": item.get("diagnostic_status"),
            "scenario": json.dumps(item["scenario"], sort_keys=True), "total": item.get("terminal_total"), "roi": summary.get("roi"),
            "max_drawdown_amount": summary.get("max_drawdown_amount"), "max_drawdown_percent": summary.get("max_drawdown_percent"),
            "monthly_returns": json.dumps(summary.get("monthly_returns"), sort_keys=True), "fills": item.get("fills"),
            "funding_events": funding.get("count"), "native_fees": item.get("native_fees"), "native_order_rejections": item.get("native_order_rejections"),
            "liquidation_count": item.get("liquidation_count"), "liquidation_value": item.get("liquidation_value"), "terminal_flat": item.get("terminal_flat"),
            "config_hash": item.get("config_hash"), "data_hash": item.get("data_hash"), "code_hash": item.get("code_hash"), "policy_hash": item.get("policy_hash"),
            "parent_artifact_sha256": item["provenance"]["parent_artifact_sha256"], "error": item.get("error"),
        })
    return rows


def run_validation(data_root: Path) -> dict:
    runs = data_root / "runs"
    parent_path = runs / "native-optimizer-causal-v1-sensitivity.json"
    parent = json.loads(parent_path.read_text())
    if parent.get("optimizer_id") != "causal-v1-sensitivity":
        raise ValueError("VALIDATION_PARENT_MISMATCH")
    parent_best = next(row for row in parent["results"] if row["variant_id"] == parent["best_assumption_profile_candidate"])
    candidate_config = json.loads(json.dumps(asdict(current_candidate())))
    provenance = {
        "validation_id": VALIDATION_ID, "parent_artifact_path": str(parent_path), "parent_artifact_sha256": sha256_file(parent_path),
        "parent_best_variant": parent["best_assumption_profile_candidate"], "parent_best_total": parent_best["terminal_total"],
        "candidate": candidate_config, "candidate_hash": hashlib.sha256(json.dumps(candidate_config, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }
    partial_path = runs / "native-validation-causal-v1-v3.partial.json"
    expected = {"validation_id": VALIDATION_ID, "provenance": provenance}
    partial = json.loads(partial_path.read_text()) if partial_path.exists() else {**expected, "results": []}
    if {key: partial.get(key) for key in expected} != expected:
        raise ValueError("VALIDATION_PARTIAL_PROVENANCE_MISMATCH")
    results = list(partial["results"])
    # Failed attempts remain in the audit trail but never suppress a corrected,
    # fresh retry of the same explicitly named scenario.
    completed = {row["scenario_id"] for row in results if row["status"] == "VALIDATION_SEEN_NOT_OOS"}
    for scenario in scenarios():
        if scenario["id"] not in completed:
            results.append(validation_item(scenario, data_root, provenance))
            partial_path.write_text(json.dumps({**expected, "results": results}, indent=2, sort_keys=True) + "\n")
    control = next(row for row in reversed(results) if row["scenario_id"] == "control_full_24m" and row["status"] == "VALIDATION_SEEN_NOT_OOS")
    canonical_control = run_native_diagnostic(data_root, include_funding=True, candidate=current_candidate(), execution_policy=stress_policy(), artifact_label="validation-v3-canonical-control")
    canonical_report_path = save_diagnostic_report(data_root, canonical_control)
    control_matches_parent = canonical_control["terminal_total"] == parent_best["terminal_total"] and len(canonical_control["summary"]["monthly_returns"]) == 24 and canonical_control["terminal_open_positions"] == 0
    summary = {
        "validation_id": VALIDATION_ID, "status": "VALIDATION_SEEN_NOT_OOS", "ranking_eligible_for_live": False,
        "provenance": provenance, "control_matches_parent_best": control_matches_parent,
        "control_parent_comparison": {"validation_total": canonical_control["terminal_total"], "parent_total": parent_best["terminal_total"], "reason_if_mismatch": "Canonical daily signals are non-matching CustomData, so 1m quotes—not daily bars—set native fill prices" if not control_matches_parent else None},
        "canonical_control": canonical_control, "canonical_control_report": {"path": str(canonical_report_path), "sha256": sha256_file(canonical_report_path)},
        "supersedes": {"artifacts": ["native-optimizer-causal-v1.json", "native-optimizer-causal-v1-refinement2.json", "native-optimizer-causal-v1-sensitivity.json"], "status": "SUPERSEDED_DAILY_BAR_MATCHING"},
        "scenarios": results, "limitations": ["Seen-data validation only; this is not OOS.", "All scenarios remain NOT_FAITHFUL_DIAGNOSTIC/non-ranking for live.", "Historical fee/tier applicability, exact settlement marks, BBO/liquidity, and intraminute liquidation remain unvalidated."],
    }
    json_path = runs / "native-validation-causal-v1-v3.json"
    csv_path = runs / "native-validation-causal-v1-v3.csv"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    rows = validation_csv_rows(results)
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["scenario_id"])
        writer.writeheader(); writer.writerows(rows)
    summary["artifacts"] = {"json": str(json_path), "csv": str(csv_path), "partial": str(partial_path)}
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("var/data"))
    args = parser.parse_args()
    print(json.dumps(run_validation(args.data_root), sort_keys=True))


if __name__ == "__main__":
    main()
