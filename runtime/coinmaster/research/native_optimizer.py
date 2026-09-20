"""Bounded, reproducible optimizer over the one native diagnostic lifecycle."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
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
STAGE_A_BTC_AXIS = (2.0, 3.5, 5.0, 6.5, 7.5, 8.5, 9.5, 10.5)
STAGE_A_SOL_PROFILES = ((0.5, 0.75, 1.0), (0.75, 1.125, 1.5), (1.0, 1.5, 2.0), (1.25, 1.875, 2.5), (1.5, 2.25, 3.0), (1.5, 1.5, 1.5), (0.5, 1.5, 3.0))
STAGE_A_BTC_REFINEMENT = (3.0, 3.5, 4.0, 4.5)
STAGE_A_SOL_COORDINATE_DELTAS = ((0, Decimal("0.25")), (1, Decimal("0.375")), (2, Decimal("0.5")))
STAGE_A_BOUNDARY_PROFILES = ((1.75, 2.625, 3.5), (2.0, 3.0, 4.0))
STAGE_A_FURTHER_BOUNDARY_PROFILE = (2.25, 3.375, 4.5)
# This alias was created by an interrupted pre-fix resume that recalculated A3
# from the final winner.  It has no native execution of its own and is removed
# only when it still proves that exact alias provenance.
STAGE_A_SUPERSEDED_NONEXECUTED_REUSE = "a3-btc-4-sol-2.25-3.375-4.5"
STAGE_B_ID = "stage-b-sol-signal-exit-v1"
STAGE_B_CONTROL = Candidate(btc_notional_multiplier=4.0, sol_size_multipliers_h=(2.25, 3.375, 4.5))
STAGE_C_SEALED_WINNER_ID = "c4-joint"
STAGE_C_SEALED_TOTAL = "656406.65217368"
STAGE_C_FINE_EMA_AXIS = (29, 32, 34, 36, 39)
STAGE_C_FINE_TP_AXIS = (
    (0.15, 0.3, 0.4), (0.25, 0.3, 0.4),
    (0.2, 0.25, 0.4), (0.2, 0.35, 0.4),
    (0.2, 0.3, 0.35), (0.2, 0.3, 0.45),
)
STAGE_D_ID = "stage-d-joint-refinement-v1"
STAGE_D_TP_AXIS = ((0.15, 0.30, 0.55), (0.10, 0.30, 0.60), (0.20, 0.25, 0.55), (0.25, 0.25, 0.50), (0.25, 0.30, 0.45), (0.20, 0.35, 0.45))
STAGE_D_EMA_AXIS = (33, 34, 35)
STAGE_D_BTC_AXIS = (3.75, 4.0, 4.25)
STAGE_D_SOL_AXIS = ((2.0, 3.0, 4.0), (2.25, 3.375, 4.5), (2.5, 3.75, 5.0))


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _stage_a_item(variant_id: str, candidate: Candidate, data_root: Path, stem: str, *, artifact_label: str | None = None) -> dict:
    """One fresh, full-period native Engine result, retained even if liquidated."""
    item = {"variant_id": variant_id, "candidate": asdict(candidate), "candidate_hash": hashlib.sha256(json.dumps(asdict(candidate), sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    started = monotonic()
    try:
        report = run_native_diagnostic(data_root, include_funding=True, candidate=candidate, artifact_label=artifact_label or f"{stem}-{variant_id}", stop_on_liquidation=False)
        assert_report_boundaries(report)
        item.update(report)
        item["wall_time_seconds"] = str(monotonic() - started)
    except Exception as error:
        item.update({"status": "FAILED", "error": f"{type(error).__name__}:{error}", "wall_time_seconds": str(monotonic() - started)})
    return item


def _candidate_tuple_key(candidate: Candidate | dict) -> str:
    """Stable complete-candidate identity; never dedupe on a partial axis."""
    value = asdict(candidate) if isinstance(candidate, Candidate) else candidate
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _stage_a_reuse(variant_id: str, candidate: Candidate | dict, source: dict) -> dict:
    """Retain a planned variant without silently recomputing an identical tuple."""
    candidate_value = asdict(candidate) if isinstance(candidate, Candidate) else candidate
    item = dict(source)
    item.update({
        "variant_id": variant_id,
        "candidate": candidate_value,
        "candidate_hash": hashlib.sha256(_candidate_tuple_key(candidate).encode()).hexdigest(),
        "reused": True,
        "reuse_provenance": {
            "variant_id": source["variant_id"],
            "candidate_hash": source.get("candidate_hash"),
        },
    })
    return item


def _stage_a_dedupe_existing(results: list[dict]) -> tuple[list[dict], bool]:
    """Migrate pre-resume checkpoints to explicit complete-tuple reuse rows."""
    reconciled: list[dict] = []
    by_tuple: dict[str, dict] = {}
    changed = False
    fields = ("terminal_active", "terminal_reserve", "terminal_total", "fills", "native_fees", "funding", "fee_attribution")
    for item in results:
        key = _candidate_tuple_key(item["candidate"])
        source = by_tuple.get(key)
        if source is None:
            by_tuple[key] = item
            reconciled.append(item)
            continue
        if any(item.get(field) != source.get(field) for field in fields):
            raise ValueError(f"STAGE_A_DUPLICATE_TUPLE_RESULT_MISMATCH:{item['variant_id']}")
        # A legacy duplicate needs one migration.  An already explicit reuse
        # remains stable even if its original source is itself a reuse row.
        if not item.get("reused"):
            item = _stage_a_reuse(item["variant_id"], item["candidate"], source)
            changed = True
        reconciled.append(item)
    return reconciled, changed


def _stage_a_reconcile_legacy_resume(results: list[dict]) -> tuple[list[dict], bool]:
    """Remove the one known non-executed alias produced before staged scoping."""
    retained: list[dict] = []
    changed = False
    for item in results:
        if item["variant_id"] != STAGE_A_SUPERSEDED_NONEXECUTED_REUSE:
            retained.append(item)
            continue
        provenance = item.get("reuse_provenance", {})
        if not item.get("reused") or provenance.get("variant_id") != "a6-btc-4-sol-2.25-3.375-4.5":
            raise ValueError("STAGE_A_UNEXPECTED_LEGACY_RESUME_VARIANT")
        changed = True
    return retained, changed


def _stage_a_best(results: list[dict]) -> dict | None:
    ranked = [item for item in results if item.get("terminal_total") is not None]
    return max(ranked, key=lambda item: Decimal(item["terminal_total"])) if ranked else None


def _stage_a_csv_row(item: dict, control_total: str) -> dict:
    """Compact, audit-oriented TOP20 row with all requested terminal economics."""
    candidate = item.get("candidate", {})
    summary = item.get("summary", {})
    fee = item.get("fee_attribution", {})
    maker, taker = fee.get("maker", {}), fee.get("taker", {})
    funding = item.get("funding", {})
    total = item.get("terminal_total")
    return {
        "variant_id": item.get("variant_id"),
        "status": item.get("status"),
        "reused": item.get("reused", False),
        "reused_from": item.get("reuse_provenance", {}).get("variant_id"),
        "candidate": json.dumps(candidate, sort_keys=True, separators=(",", ":")),
        "btc_notional_multiplier": candidate.get("btc_notional_multiplier"),
        "sol_size_multipliers_h": json.dumps(candidate.get("sol_size_multipliers_h"), separators=(",", ":")),
        "active": item.get("terminal_active"),
        "reserve": item.get("terminal_reserve"),
        "total": total,
        "roi": summary.get("roi"),
        "max_drawdown_percent": summary.get("max_drawdown_percent"),
        "max_drawdown_amount": summary.get("max_drawdown_amount"),
        "liquidations": item.get("liquidation_count"),
        "maker_notional": maker.get("notional"),
        "maker_fees": maker.get("fees"),
        "taker_notional": taker.get("notional"),
        "taker_fees": taker.get("fees"),
        "total_fees": item.get("native_fees"),
        "funding_signed_amount": funding.get("signed_amount", "UNKNOWN"),
        "funding_event_count": funding.get("count", "UNKNOWN"),
        "fills": item.get("fills"),
        "delta_vs_accepted_7_5": str(Decimal(total) - Decimal(control_total)) if total is not None else None,
    }


def _stage_a_compact_result(item: dict, partial_path: Path) -> dict:
    """Keep the final artifact reviewable; full native reports remain local evidence."""
    summary = item.get("summary", {})
    fee = item.get("fee_attribution", {})
    funding = item.get("funding", {})
    return {
        "variant_id": item.get("variant_id"),
        "status": item.get("status"),
        "candidate": item.get("candidate"),
        "candidate_hash": item.get("candidate_hash"),
        "reused": item.get("reused", False),
        "reuse_provenance": item.get("reuse_provenance"),
        "terminal_active": item.get("terminal_active"),
        "terminal_reserve": item.get("terminal_reserve"),
        "terminal_total": item.get("terminal_total"),
        "roi": summary.get("roi"),
        "max_drawdown_percent": summary.get("max_drawdown_percent"),
        "max_drawdown_amount": summary.get("max_drawdown_amount"),
        "terminal_open_positions": item.get("terminal_open_positions"),
        "liquidation_count": item.get("liquidation_count"),
        "liquidation_value": item.get("liquidation_value"),
        "fills": item.get("fills"),
        "fee_attribution": {"maker": fee.get("maker"), "taker": fee.get("taker"), "native_total": fee.get("native_total"), "reconciled": fee.get("reconciled")},
        "native_fees": item.get("native_fees"),
        "funding": {"signed_amount": funding.get("signed_amount", "UNKNOWN"), "count": funding.get("count", "UNKNOWN")},
        "local_evidence": {"checkpoint": str(partial_path), "execution_artifacts": item.get("execution_artifacts"), "funding_journal": item.get("funding_journal")},
    }


def run_stage_a_sizing(data_root: Path, control_report: Path) -> dict:
    """Resumable, strictly sequential BTC/SOL sizing search; never Stage B."""
    control = json.loads(control_report.read_text())
    if control.get("terminal_open_positions") != 0 or control.get("liquidation_count") != 0:
        raise ValueError("STAGE_A_CONTROL_NOT_FLAT")
    runs, stem = data_root / "runs", "native-stage-a-sizing-v1"
    runs.mkdir(parents=True, exist_ok=True)
    meta = {"optimizer_id": "stage-a-sizing-v1", "control_path": str(control_report), "control_sha256": sha256_file(control_report), "data_hash": control["data_hash"], "policy_hash": control["policy_hash"], "control_total": control["terminal_total"], "btc_axis": list(STAGE_A_BTC_AXIS), "sol_profiles": [list(item) for item in STAGE_A_SOL_PROFILES], "objective": "terminal TOTAL only; liquidation remains eligible at actual TOTAL", "ranking_eligible_for_live": False}
    partial_path = runs / f"{stem}.partial.json"
    partial = json.loads(partial_path.read_text()) if partial_path.exists() else {"provenance": meta, "results": []}
    if partial.get("provenance") != meta:
        raise ValueError("STAGE_A_PARTIAL_PROVENANCE_MISMATCH")
    # A corrected complete cohort is sealed: normal resume is export-only and
    # must not reopen its plan or replace correction-backed evidence.
    correction_path = runs / f"{stem}-evidence-correction-v1.json"
    if len(partial["results"]) >= 42 and correction_path.exists():
        return write_stage_a_compact_checkpoint(data_root, control_report)
    # Once Stage A has its original complete cohort, later interrupted resume
    # rows are immutable incident evidence only.  They must never affect a
    # normal resume's plan, ranking, or artifact references.
    results, removed_legacy_resume = _stage_a_reconcile_legacy_resume(list(partial["results"][:42]))
    results, deduped_existing = _stage_a_dedupe_existing(results)
    if removed_legacy_resume or deduped_existing:
        _atomic_json(partial_path, {"provenance": meta, "results": results})
    completed = {item["variant_id"] for item in results}
    # This index covers the complete Candidate payload, including fields that
    # this pass does not vary. It makes restart/replanning safe without hiding
    # a potentially material future Candidate-field change.
    by_tuple: dict[str, dict] = {}
    for item in results:
        if item.get("candidate"):
            by_tuple.setdefault(_candidate_tuple_key(item["candidate"]), item)
    def append(item: dict) -> None:
        results.append(item)
        completed.add(item["variant_id"])
        by_tuple.setdefault(_candidate_tuple_key(item["candidate"]), item)
        _atomic_json(partial_path, {"provenance": meta, "results": results})
    def append_candidate(variant_id: str, candidate: Candidate) -> None:
        if variant_id in completed:
            return
        source = by_tuple.get(_candidate_tuple_key(candidate))
        append(_stage_a_reuse(variant_id, candidate, source) if source else _stage_a_item(variant_id, candidate, data_root, stem))
    default_sol = (1.0, 1.5, 2.0)
    for btc in STAGE_A_BTC_AXIS:
        key = f"a1-btc-{btc:g}"
        if key in completed:
            continue
        candidate = replace(Candidate(), btc_notional_multiplier=btc, sol_size_multipliers_h=default_sol)
        if btc == 7.5 and control.get("data_hash") == meta["data_hash"] and control.get("policy_hash") == meta["policy_hash"] and control.get("config", {}).get("candidate") == asdict(candidate):
            append({"variant_id": key, "candidate": asdict(candidate), "candidate_hash": hashlib.sha256(json.dumps(asdict(candidate), sort_keys=True, separators=(",", ":")).encode()).hexdigest(), **control, "reused": True, "reuse_provenance": {"path": str(control_report), "sha256": meta["control_sha256"]}})
        else:
            append_candidate(key, candidate)
    a1 = [item for item in results if item["variant_id"].startswith("a1-") and item.get("terminal_total") is not None]
    top_btc = []
    for item in sorted(a1, key=lambda value: Decimal(value["terminal_total"]), reverse=True):
        value = item["candidate"]["btc_notional_multiplier"]
        if value not in top_btc: top_btc.append(value)
        if len(top_btc) == 3: break
    for btc in top_btc:
        for profile in STAGE_A_SOL_PROFILES:
            key = f"a2-btc-{btc:g}-sol-{'-'.join(f'{value:g}' for value in profile)}"
            candidate = replace(Candidate(), btc_notional_multiplier=btc, sol_size_multipliers_h=profile)
            append_candidate(key, candidate)

    initial_winner = _stage_a_best([item for item in results if item["variant_id"].startswith(("a1-", "a2-"))])
    if initial_winner is None:
        raise ValueError("STAGE_A_NO_TERMINAL_TOTAL")
    initial_sol = tuple(initial_winner["candidate"]["sol_size_multipliers_h"])
    for btc in STAGE_A_BTC_REFINEMENT:
        candidate = replace(Candidate(), btc_notional_multiplier=btc, sol_size_multipliers_h=initial_sol)
        append_candidate(f"a3-btc-{btc:g}-sol-{'-'.join(f'{value:g}' for value in initial_sol)}", candidate)

    btc_winner = _stage_a_best([item for item in results if item["variant_id"].startswith(("a1-", "a2-", "a3-"))])
    if btc_winner is None:
        raise ValueError("STAGE_A_BTC_REFINEMENT_NO_TERMINAL_TOTAL")
    btc = btc_winner["candidate"]["btc_notional_multiplier"]
    sol_winner = tuple(Decimal(str(value)) for value in btc_winner["candidate"]["sol_size_multipliers_h"])
    for level, delta in STAGE_A_SOL_COORDINATE_DELTAS:
        for direction in (-1, 1):
            profile = list(sol_winner)
            profile[level] += Decimal(direction) * delta
            if profile[0] <= 0 or profile[0] > profile[1] or profile[1] > profile[2]:
                continue
            values = tuple(float(value) for value in profile)
            direction_id = "minus" if direction < 0 else "plus"
            candidate = replace(Candidate(), btc_notional_multiplier=btc, sol_size_multipliers_h=values)
            append_candidate(f"a4-btc-{btc:g}-sol-l{level + 1}-{direction_id}-{'-'.join(f'{value:g}' for value in values)}", candidate)

    sol_winner = _stage_a_best([item for item in results if item["variant_id"].startswith(("a1-", "a2-", "a3-", "a4-"))])
    if sol_winner is None:
        raise ValueError("STAGE_A_SOL_REFINEMENT_NO_TERMINAL_TOTAL")
    btc = sol_winner["candidate"]["btc_notional_multiplier"]
    before_boundaries_total = Decimal(sol_winner["terminal_total"])
    for profile in STAGE_A_BOUNDARY_PROFILES:
        candidate = replace(Candidate(), btc_notional_multiplier=btc, sol_size_multipliers_h=profile)
        append_candidate(f"a5-btc-{btc:g}-sol-{'-'.join(f'{value:g}' for value in profile)}", candidate)
    profile_234 = next((item for item in results if item["variant_id"] == f"a5-btc-{btc:g}-sol-2-3-4"), None)
    if profile_234 and Decimal(profile_234["terminal_total"]) > before_boundaries_total:
        profile = STAGE_A_FURTHER_BOUNDARY_PROFILE
        candidate = replace(Candidate(), btc_notional_multiplier=btc, sol_size_multipliers_h=profile)
        append_candidate(f"a6-btc-{btc:g}-sol-{'-'.join(f'{value:g}' for value in profile)}", candidate)

    ranked = [item for item in results if item.get("terminal_total") is not None]
    top20 = sorted(ranked, key=lambda value: Decimal(value["terminal_total"]), reverse=True)[:20]
    best = _stage_a_best(results)
    csv_path = runs / f"{stem}-top20.csv"
    fields = tuple(_stage_a_csv_row(top20[0], control["terminal_total"]).keys()) if top20 else ("variant_id",)
    temporary_csv = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with temporary_csv.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(_stage_a_csv_row(item, control["terminal_total"]) for item in top20)
    temporary_csv.replace(csv_path)
    evidence = {"checkpoint": str(partial_path), "checkpoint_sha256": sha256_file(partial_path), "checkpoint_result_count": len(results)}
    summary = {"status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible_for_live": False, "provenance": meta, "result_count": len(results), "local_evidence": evidence, "results": [_stage_a_compact_result(item, partial_path) for item in results], "top20": [_stage_a_compact_result(item, partial_path) for item in top20], "best": _stage_a_compact_result(best, partial_path) if best else None, "delta_vs_accepted_7_5": str(Decimal(best["terminal_total"]) - Decimal(control["terminal_total"])) if best else None, "limitations": ["Stage A only; no Stage B.", "Full per-candidate native reports and journals remain in the local ignored checkpoint; this aggregate is intentionally compact.", "Historical execution and fee applicability remain diagnostic assumptions."]}
    target = runs / f"{stem}.json"; _atomic_json(target, summary)
    return summary | {"artifact": str(target), "csv": str(csv_path), "partial": str(partial_path)}


def write_stage_a_compact_checkpoint(data_root: Path, control_report: Path) -> dict:
    """Write the compact final Stage-A artifact without resuming or mutating evidence.

    The first 42 rows are the completed, ordered Stage-A plan.  Later rows are
    retained only in the ignored local checkpoint as an interrupted-resume
    incident and are deliberately excluded from ranking.
    """
    runs, stem = data_root / "runs", "native-stage-a-sizing-v1"
    partial_path = runs / f"{stem}.partial.json"
    partial = json.loads(partial_path.read_text())
    results = list(partial["results"])
    canonical = results[:42]
    if len(canonical) != 42 or canonical[-1].get("variant_id") != "a6-btc-4-sol-2.25-3.375-4.5":
        raise ValueError("STAGE_A_CANONICAL_CHECKPOINT_SEQUENCE_MISMATCH")
    if any(item.get("terminal_total") is None for item in canonical):
        raise ValueError("STAGE_A_CANONICAL_CHECKPOINT_INCOMPLETE")
    correction_path = runs / f"{stem}-evidence-correction-v1.json"
    correction = json.loads(correction_path.read_text()) if correction_path.exists() else None
    if correction:
        if correction.get("status") != "SEALED_EVIDENCE_CORRECTION" or correction.get("partial_sha256_before") != sha256_file(partial_path):
            raise ValueError("STAGE_A_CORRECTION_PROVENANCE_MISMATCH")
        replacements = correction.get("replacements", {})
        canonical = [replacements.get(item["variant_id"], item) for item in canonical]
    control = json.loads(control_report.read_text())
    top20 = sorted(canonical, key=lambda item: Decimal(item["terminal_total"]), reverse=True)[:20]
    best = top20[0]
    csv_path = runs / f"{stem}-top20.csv"
    fields = tuple(_stage_a_csv_row(top20[0], control["terminal_total"]).keys())
    temporary_csv = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with temporary_csv.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(_stage_a_csv_row(item, control["terminal_total"]) for item in top20)
    temporary_csv.replace(csv_path)
    incident = [{"variant_id": item.get("variant_id"), "reused": item.get("reused", False), "terminal_total": item.get("terminal_total"), "execution_artifacts": item.get("execution_artifacts")} for item in results[42:]]
    evidence = {"checkpoint": str(partial_path), "checkpoint_sha256": sha256_file(partial_path), "canonical_result_count": len(canonical), "excluded_resume_incident_count": len(incident), "correction": {"path": str(correction_path), "sha256": sha256_file(correction_path)} if correction else None}
    summary = {"status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible_for_live": False, "provenance": partial["provenance"], "result_count": len(canonical), "local_evidence": evidence, "results": [_stage_a_compact_result(item, partial_path) for item in canonical], "top20": [_stage_a_compact_result(item, partial_path) for item in top20], "best": _stage_a_compact_result(best, partial_path), "delta_vs_accepted_7_5": str(Decimal(best["terminal_total"]) - Decimal(control["terminal_total"])), "excluded_resume_incident": {"reason": "INTERRUPTED_PRE_FIX_RESUME_NOT_STAGE_A_PLAN", "rows": incident}, "limitations": ["Stage A only; no Stage B.", "Full per-candidate native reports and journals remain in the local ignored checkpoint; this aggregate is intentionally compact.", "Historical execution and fee applicability remain diagnostic assumptions."]}
    target = runs / f"{stem}.json"
    _atomic_json(target, summary)
    return summary | {"artifact": str(target), "csv": str(csv_path), "partial": str(partial_path)}


def correct_stage_a_a3_evidence(data_root: Path) -> dict:
    """Fresh, sequential replacement evidence for the two overwritten A3 rows."""
    runs, stem = data_root / "runs", "native-stage-a-sizing-v1"
    partial_path = runs / f"{stem}.partial.json"
    source = json.loads(partial_path.read_text())
    canonical = source["results"][:42]
    targets = ("a3-btc-3-sol-1.5-2.25-3", "a3-btc-4-sol-1.5-2.25-3")
    by_id = {item["variant_id"]: item for item in canonical}
    if any(target not in by_id for target in targets):
        raise ValueError("STAGE_A_A3_CORRECTION_TARGET_MISSING")
    correction_path = runs / f"{stem}-evidence-correction-v1.json"
    correction = json.loads(correction_path.read_text()) if correction_path.exists() else {
        "status": "SEALED_EVIDENCE_CORRECTION",
        "partial_sha256_before": sha256_file(partial_path),
        "targets": list(targets),
        "superseded_rows": {target: by_id[target] for target in targets},
        "replacements": {},
    }
    if correction.get("partial_sha256_before") != sha256_file(partial_path) or correction.get("targets") != list(targets):
        raise ValueError("STAGE_A_A3_CORRECTION_PROVENANCE_MISMATCH")
    for target in targets:
        if target in correction["replacements"]:
            continue
        candidate = Candidate(**by_id[target]["candidate"])
        replacement = _stage_a_item(target, candidate, data_root, stem, artifact_label=f"{stem}-evidence-correction-v1-{target}")
        correction["replacements"][target] = replacement
        _atomic_json(correction_path, correction)
    merged = [correction["replacements"].get(item["variant_id"], item) for item in canonical]
    a3_winner = _stage_a_best([item for item in merged if item["variant_id"].startswith(("a1-", "a2-", "a3-"))])
    expected = Candidate(btc_notional_multiplier=4.0, sol_size_multipliers_h=(1.5, 2.25, 3.0))
    correction["downstream_plan_valid"] = bool(a3_winner and _candidate_tuple_key(a3_winner["candidate"]) == _candidate_tuple_key(expected))
    correction["a3_winner"] = {"variant_id": a3_winner["variant_id"], "terminal_total": a3_winner["terminal_total"], "candidate": a3_winner["candidate"]} if a3_winner else None
    _atomic_json(correction_path, correction)
    return correction | {"artifact": str(correction_path)}


def _stage_b_variants(stage: str, control: Candidate) -> tuple[tuple[str, Candidate], ...]:
    """Predeclared, one-axis Stage-B variants; never a Cartesian product."""
    if stage == "b1":
        variants = [("b1-uniform-{:+g}".format(shift), replace(control, sol_entry_z=tuple(value + shift for value in control.sol_entry_z))) for shift in (-0.5, -0.25, 0.0, 0.25, 0.5)]
        variants += [(f"b1-level1-{value:g}", replace(control, sol_entry_z=(value, control.sol_entry_z[1], control.sol_entry_z[2]))) for value in (0.75, 1.0, 1.5, 1.75)]
        variants += [("b1-shape-1-2-3", replace(control, sol_entry_z=(1.0, 2.0, 3.0))), ("b1-shape-1.5-3-4.5", replace(control, sol_entry_z=(1.5, 3.0, 4.5)))]
    elif stage == "b2":
        variants = [(f"b2-half-{value:g}", replace(control, sol_exit_half_z=value)) for value in (0.25, 0.375, 0.5, 0.75)]
        variants += [(f"b2-all-{value:g}", replace(control, sol_exit_all_z=value)) for value in (0.0, 0.125, 0.25) if value <= control.sol_exit_half_z]
        variants += [(f"b2-holding-{value}", replace(control, sol_max_holding_days=value)) for value in (7, 14, 21, 28)]
    elif stage == "b3":
        variants = [(f"b3-beta-{value}", replace(control, beta_days=value)) for value in (180, 270, 365)]
        variants += [(f"b3-relative-{value}", replace(control, relative_days=value)) for value in (30, 65, 90)]
        variants += [(f"b3-z-history-{value}", replace(control, z_history_days=value)) for value in (90, 180, 270)]
    else:
        raise ValueError(f"STAGE_B_UNKNOWN_STAGE:{stage}")
    return tuple((variant_id, candidate) for variant_id, candidate in variants if min(candidate.sol_entry_z) > 0 and candidate.sol_entry_z[0] <= candidate.sol_entry_z[1] <= candidate.sol_entry_z[2])


def _stage_b_compact(item: dict, control_total: str, partial_path: Path) -> dict:
    row = _stage_a_compact_result(item, partial_path)
    row["delta_vs_accepted_stage_a"] = str(Decimal(item["terminal_total"]) - Decimal(control_total))
    row["sol_fill_add_level_attribution"] = "UNKNOWN_NATIVE_FILLS_DO_NOT_EXPORT_SOL_ADD_LEVEL"
    return row


def run_stage_b_sol_search(data_root: Path, stage_a_report: Path) -> dict:
    """Single-owner, sealed-stage native Stage-B SOL signal/exit search."""
    runs, stem = data_root / "runs", "native-stage-b-sol-signal-exit-v1"
    runs.mkdir(parents=True, exist_ok=True)
    accepted = json.loads(stage_a_report.read_text())
    if _candidate_tuple_key(accepted.get("best", {}).get("candidate", {})) != _candidate_tuple_key(STAGE_B_CONTROL):
        raise ValueError("STAGE_B_ACCEPTED_STAGE_A_CANDIDATE_MISMATCH")
    partial_a = data_root / "runs" / "native-stage-a-sizing-v1.partial.json"
    if accepted.get("local_evidence", {}).get("checkpoint_sha256") != sha256_file(partial_a):
        raise ValueError("STAGE_B_ACCEPTED_STAGE_A_EVIDENCE_HASH_MISMATCH")
    stage_a_source = next((item for item in json.loads(partial_a.read_text())["results"][:42] if item["variant_id"] == accepted["best"]["variant_id"]), None)
    if not stage_a_source or _candidate_tuple_key(stage_a_source.get("candidate", {})) != _candidate_tuple_key(STAGE_B_CONTROL):
        raise ValueError("STAGE_B_ACCEPTED_STAGE_A_SOURCE_MISMATCH")
    if _candidate_tuple_key(stage_a_source.get("config", {}).get("candidate", {})) != _candidate_tuple_key(STAGE_B_CONTROL) or not stage_a_source.get("data_hash") or not stage_a_source.get("policy_hash"):
        raise ValueError("STAGE_B_ACCEPTED_STAGE_A_POLICY_CONFIG_DATA_MISMATCH")
    for artifact in stage_a_source.get("execution_artifacts", {}).values():
        path = Path(artifact["path"])
        if not path.exists() or sha256_file(path) != artifact["sha256"]:
            raise ValueError("STAGE_B_ACCEPTED_STAGE_A_ARTIFACT_HASH_MISMATCH")
    meta = {"optimizer_id": STAGE_B_ID, "stage_a_report": str(stage_a_report), "stage_a_report_sha256": sha256_file(stage_a_report), "stage_a_checkpoint_sha256": sha256_file(partial_a), "control_candidate": json.loads(_candidate_tuple_key(STAGE_B_CONTROL)), "control_total": accepted["best"]["terminal_total"], "objective": "terminal TOTAL only; liquidation remains eligible at actual TOTAL", "ranking_eligible_for_live": False}
    partial_path, lock_path = runs / f"{stem}.partial.json", runs / f"{stem}.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError("STAGE_B_SINGLE_PROCESS_LOCK_HELD") from error
    try:
        os.write(fd, str(os.getpid()).encode()); os.close(fd)
        partial = json.loads(partial_path.read_text()) if partial_path.exists() else {"provenance": meta, "results": [], "sealed": {}}
        if partial.get("provenance") != meta:
            raise ValueError("STAGE_B_PARTIAL_PROVENANCE_MISMATCH")
        results, sealed = list(partial["results"]), dict(partial.get("sealed", {}))
        by_tuple = {_candidate_tuple_key(item["candidate"]): item for item in results}
        completed = {item["variant_id"] for item in results}
        def persist() -> None:
            _atomic_json(partial_path, {"provenance": meta, "results": results, "sealed": sealed})
        def add(variant_id: str, candidate: Candidate, source: dict | None = None) -> None:
            if variant_id in completed:
                return
            existing = by_tuple.get(_candidate_tuple_key(candidate)) or source
            item = _stage_a_reuse(variant_id, candidate, existing) if existing else _stage_a_item(variant_id, candidate, data_root, stem)
            results.append(item); completed.add(variant_id); by_tuple.setdefault(_candidate_tuple_key(candidate), item); persist()
        def stage(name: str, base: Candidate) -> dict:
            for variant_id, candidate in _stage_b_variants(name, base):
                source = stage_a_source if candidate == STAGE_B_CONTROL else None
                add(variant_id, candidate, source)
            candidates = [item for item in results if item["variant_id"].startswith(f"{name}-") and item.get("terminal_total") is not None]
            if not candidates:
                raise ValueError(f"STAGE_B_EMPTY:{name}")
            winner = max(candidates, key=lambda item: Decimal(item["terminal_total"]))
            if name not in sealed:
                sealed[name] = winner["variant_id"]; persist()
            return next(item for item in candidates if item["variant_id"] == sealed[name])
        b1 = stage("b1", STAGE_B_CONTROL)
        b2 = stage("b2", Candidate(**b1["candidate"]))
        b3 = stage("b3", Candidate(**b2["candidate"]))
        joint = Candidate(**b3["candidate"])
        add("b4-joint", joint)
        if "b4" not in sealed:
            sealed["b4"] = "b4-joint"; persist()
        ranked = [item for item in results if item.get("terminal_total") is not None]
        top20 = sorted(ranked, key=lambda item: Decimal(item["terminal_total"]), reverse=True)[:20]
        best = top20[0]
        csv_path = runs / f"{stem}-top20.csv"
        rows = [_stage_a_csv_row(item, meta["control_total"]) | {"delta_vs_accepted_stage_a": str(Decimal(item["terminal_total"]) - Decimal(meta["control_total"])), "sol_fill_add_level_attribution": "UNKNOWN_NATIVE_FILLS_DO_NOT_EXPORT_SOL_ADD_LEVEL"} for item in top20]
        with csv_path.with_suffix(".csv.tmp").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
        csv_path.with_suffix(".csv.tmp").replace(csv_path)
        summary = {"status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible_for_live": False, "provenance": meta, "sealed": sealed, "local_evidence": {"checkpoint": str(partial_path), "checkpoint_sha256": sha256_file(partial_path)}, "result_count": len(results), "results": [_stage_b_compact(item, meta["control_total"], partial_path) for item in results], "top20": [_stage_b_compact(item, meta["control_total"], partial_path) for item in top20], "best": _stage_b_compact(best, meta["control_total"], partial_path), "delta_vs_accepted_stage_a": str(Decimal(best["terminal_total"]) - Decimal(meta["control_total"])), "limitations": ["Stage B only; no Stage C.", "SOL fill/add level attribution is UNKNOWN because native fills do not export the domain add level."]}
        target = runs / f"{stem}.json"; _atomic_json(target, summary)
        return summary | {"artifact": str(target), "csv": str(csv_path), "partial": str(partial_path)}
    finally:
        if lock_path.exists():
            lock_path.unlink()


def _stage_c_variants(stage: str, control: Candidate) -> tuple[tuple[str, Candidate], ...]:
    if stage == "c1":
        items = [(f"c1-ema-{value}", replace(control, ema_period=value)) for value in (13, 21, 34, 55)]
        items += [(f"c1-trail-{value:g}", replace(control, btc_close_trail_fraction=value)) for value in (0.02, 0.03, 0.04, 0.05)]
    elif stage == "c2":
        items = [(f"c2-quantiles-{'-'.join(f'{x:g}' for x in values)}", replace(control, wave_quantiles=values)) for values in ((0.05, 0.2, 0.5), (0.1, 0.25, 0.45), (0.1, 0.3, 0.6), (0.1, 0.4, 0.75), (0.15, 0.4, 0.7))]
        items += [(f"c2-history-{value}", replace(control, wave_history_days=value)) for value in (365, 545, 730, 900)]
    elif stage == "c3":
        items = [(f"c3-tp-{'-'.join(f'{x:g}' for x in values)}", replace(control, btc_tp_fractions_initial_qty=values)) for values in ((0.1, 0.2, 0.3), (0.15, 0.25, 0.35), (0.2, 0.3, 0.4), (0.25, 0.25, 0.25), (0.1, 0.2, 0.45))]
    else: raise ValueError(f"STAGE_C_UNKNOWN_STAGE:{stage}")
    return tuple((name, candidate) for name, candidate in items if sum(candidate.btc_tp_fractions_initial_qty) <= 1)


def _stage_c_fine_ema_variants(control: Candidate) -> tuple[tuple[str, Candidate], ...]:
    """The exact authorized EMA neighborhood; no Cartesian expansion."""
    return tuple((f"c5-ema-{value}", replace(control, ema_period=value)) for value in STAGE_C_FINE_EMA_AXIS)


def _stage_c_fine_tp_variants(control: Candidate) -> tuple[tuple[str, Candidate], ...]:
    """The exact authorized one-axis TP neighborhood at the sealed EMA winner."""
    return tuple(
        (f"c6-tp-{'-'.join(f'{value:g}' for value in values)}", replace(control, btc_tp_fractions_initial_qty=values))
        for values in STAGE_C_FINE_TP_AXIS
    )


def _stage_c_boundary_ema_variant(winner: dict) -> tuple[str, Candidate] | None:
    """One EMA step beyond an improving, tested boundary and nothing further."""
    ema = int(winner["candidate"]["ema_period"])
    if ema == STAGE_C_FINE_EMA_AXIS[0]:
        value = ema - 3
    elif ema == STAGE_C_FINE_EMA_AXIS[-1]:
        value = ema + 3
    else:
        return None
    return f"c5-boundary-ema-{value}", replace(Candidate(**winner["candidate"]), ema_period=value)


def _stage_c_boundary_tp_variant(winner: dict) -> tuple[str, Candidate] | None:
    """One valid 0.05 TP extension for a winning tested boundary coordinate."""
    values = [Decimal(str(value)) for value in winner["candidate"]["btc_tp_fractions_initial_qty"]]
    axis = tuple(tuple(Decimal(str(value)) for value in item) for item in STAGE_C_FINE_TP_AXIS)
    current = tuple(values)
    for index in range(3):
        coordinate_axis = sorted({item[index] for item in axis})
        if current[index] == coordinate_axis[0]:
            proposed = current[index] - Decimal("0.05")
        elif current[index] == coordinate_axis[-1]:
            proposed = current[index] + Decimal("0.05")
        else:
            continue
        extended = list(values); extended[index] = proposed
        if proposed <= 0 or sum(extended) > 1:
            return None
        tuple_values = tuple(float(value) for value in extended)
        return f"c6-boundary-tp-l{index + 1}-{'-'.join(f'{value:g}' for value in tuple_values)}", replace(Candidate(**winner["candidate"]), btc_tp_fractions_initial_qty=tuple_values)
    return None


def _stage_c_artifact_path(data_root: Path, value: str) -> Path:
    """Resolve report-local evidence without trusting the caller's cwd."""
    path = Path(value)
    if path.is_absolute():
        return path
    runtime = data_root.parents[1] if len(data_root.parents) >= 2 else data_root
    for candidate in (path, runtime / path, data_root / path.name):
        if candidate.exists():
            return candidate
    return runtime / path


def _stage_c_validate_ranked_evidence(results: list[dict], data_root: Path) -> None:
    """Fail closed before publishing TOP20: each ranked row must be auditable."""
    for item in results:
        if item.get("terminal_total") is None:
            continue
        artifacts = item.get("execution_artifacts") or {}
        if not artifacts:
            raise ValueError(f"STAGE_C_RANKED_EVIDENCE_MISSING:{item['variant_id']}")
        for artifact in artifacts.values():
            path = _stage_c_artifact_path(data_root, artifact.get("path", ""))
            if not path.is_file() or sha256_file(path) != artifact.get("sha256"):
                raise ValueError(f"STAGE_C_RANKED_ARTIFACT_HASH_MISMATCH:{item['variant_id']}")
        fee = item.get("fee_attribution") or {}
        maker = Decimal(str((fee.get("maker") or {}).get("fees", "NaN")))
        taker = Decimal(str((fee.get("taker") or {}).get("fees", "NaN")))
        unknown = Decimal(str((fee.get("unknown") or {}).get("fees", "0")))
        native = Decimal(str(item.get("native_fees", "NaN")))
        audited = Decimal(str(fee.get("audited_total", fee.get("native_total", "NaN"))))
        if not fee.get("reconciled") or maker + taker + unknown != native or audited != native:
            raise ValueError(f"STAGE_C_RANKED_FEE_MISMATCH:{item['variant_id']}")
        funding = item.get("funding") or {}
        if not funding.get("signed_amount") or funding.get("count") is None:
            raise ValueError(f"STAGE_C_RANKED_FUNDING_UNEXPLICIT:{item['variant_id']}")


def _run_stage_c_fine_neighbors(
    data_root: Path,
    runs: Path,
    stem: str,
    meta: dict,
    partial_path: Path,
    source: dict,
    results: list[dict],
    sealed: dict,
) -> dict:
    """Execute only the authorized c5/c6 one-axis neighbors after sealed c1-c4."""
    expected_sealed = {"c1": "c1-ema-34", "c2": "c2-quantiles-0.1-0.3-0.6", "c3": "c3-tp-0.2-0.3-0.4", "c4": STAGE_C_SEALED_WINNER_ID}
    if {key: sealed.get(key) for key in expected_sealed} != expected_sealed:
        raise ValueError("STAGE_C_SEALED_SELECTION_MISMATCH")
    by_id = {item["variant_id"]: item for item in results}
    c4 = by_id.get(STAGE_C_SEALED_WINNER_ID)
    if not c4 or c4.get("terminal_total") != STAGE_C_SEALED_TOTAL:
        raise ValueError("STAGE_C_SEALED_WINNER_MISMATCH")
    base = Candidate(**c4["candidate"])
    if base.ema_period != 34 or tuple(base.btc_tp_fractions_initial_qty) != (0.2, 0.3, 0.4):
        raise ValueError("STAGE_C_SEALED_CANDIDATE_MISMATCH")
    completed = set(by_id)
    by_tuple = {_candidate_tuple_key(item["candidate"]): item for item in results}

    def persist() -> None:
        _atomic_json(partial_path, {"provenance": meta, "results": results, "sealed": sealed})

    def add(name: str, candidate: Candidate) -> None:
        if name in completed:
            return
        existing = by_tuple.get(_candidate_tuple_key(candidate)) or (source if candidate == Candidate(**source["candidate"]) else None)
        item = _stage_a_reuse(name, candidate, existing) if existing else _stage_a_item(name, candidate, data_root, stem)
        results.append(item); completed.add(name); by_tuple.setdefault(_candidate_tuple_key(candidate), item); persist()

    def select(prefix: str, key: str) -> dict:
        options = [item for item in results if item["variant_id"].startswith(prefix) and item.get("terminal_total") is not None]
        if not options:
            raise ValueError(f"STAGE_C_EMPTY:{key}")
        if key not in sealed:
            sealed[key] = max(options, key=lambda item: Decimal(item["terminal_total"]))["variant_id"]
            persist()
        return next(item for item in options if item["variant_id"] == sealed[key])

    for name, candidate in _stage_c_fine_ema_variants(base):
        add(name, candidate)
    ema_winner = select("c5-ema-", "c5")
    if Decimal(ema_winner["terminal_total"]) > Decimal(c4["terminal_total"]) and ema_winner.get("liquidation_count", 0) == 0:
        extension = _stage_c_boundary_ema_variant(ema_winner)
        if extension:
            add(*extension)
            select("c5-boundary-ema-", "c5_boundary")

    for name, candidate in _stage_c_fine_tp_variants(Candidate(**ema_winner["candidate"])):
        add(name, candidate)
    tp_winner = select("c6-tp-", "c6")
    if Decimal(tp_winner["terminal_total"]) > Decimal(ema_winner["terminal_total"]) and tp_winner.get("liquidation_count", 0) == 0:
        extension = _stage_c_boundary_tp_variant(tp_winner)
        if extension:
            add(*extension)
            select("c6-boundary-tp-", "c6_boundary")

    for item in results:
        item.setdefault("btc_tp_level_attribution", "UNKNOWN_NATIVE_FILLS_DO_NOT_EXPORT_TP_LEVEL_OR_EXIT_REASON")
    ranked = sorted((item for item in results if item.get("terminal_total") is not None), key=lambda item: Decimal(item["terminal_total"]), reverse=True)
    _stage_c_validate_ranked_evidence(ranked, data_root)
    top20, best = ranked[:20], ranked[0]
    rows = [_stage_a_csv_row(item, meta["control_total"]) | {"delta_vs_accepted_stage_b": str(Decimal(item["terminal_total"]) - Decimal(meta["control_total"])), "btc_tp_level_attribution": "UNKNOWN_NATIVE_FILLS_DO_NOT_EXPORT_TP_LEVEL_OR_EXIT_REASON"} for item in top20]
    csv_path, temporary = runs / f"{stem}-top20.csv", runs / f"{stem}-top20.csv.tmp"
    with temporary.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    temporary.replace(csv_path)
    summary = {"status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible_for_live": False, "provenance": meta, "sealed": sealed, "local_evidence": {"checkpoint": str(partial_path), "checkpoint_sha256": sha256_file(partial_path), "ranked_evidence_validated": True}, "result_count": len(results), "results": [_stage_b_compact(item, meta["control_total"], partial_path) | {"btc_tp_level_attribution": item["btc_tp_level_attribution"]} for item in results], "top20": [_stage_b_compact(item, meta["control_total"], partial_path) | {"btc_tp_level_attribution": item["btc_tp_level_attribution"]} for item in top20], "best": _stage_b_compact(best, meta["control_total"], partial_path) | {"btc_tp_level_attribution": best["btc_tp_level_attribution"]}, "delta_vs_accepted_stage_b": str(Decimal(best["terminal_total"]) - Decimal(meta["control_total"])), "limitations": ["Stage C only; no Stage D.", "BTC TP-level and exit-reason attribution UNKNOWN from native fills."]}
    target = runs / f"{stem}.json"; _atomic_json(target, summary)
    return summary | {"artifact": str(target), "csv": str(csv_path), "partial": str(partial_path)}


def run_stage_c_btc_management(data_root: Path, stage_b_report: Path) -> dict:
    """Single-owner sealed Stage-C BTC management search; never Stage D."""
    runs, stem = data_root / "runs", "native-stage-c-btc-management-v1"; runs.mkdir(parents=True, exist_ok=True)
    accepted = json.loads(stage_b_report.read_text()); control = Candidate(**accepted["best"]["candidate"])
    if _candidate_tuple_key(control) != _candidate_tuple_key(STAGE_B_CONTROL): raise ValueError("STAGE_C_ACCEPTED_CONTROL_MISMATCH")
    b_partial = data_root / "runs" / "native-stage-b-sol-signal-exit-v1.partial.json"
    if accepted.get("local_evidence", {}).get("checkpoint_sha256") != sha256_file(b_partial): raise ValueError("STAGE_C_STAGE_B_EVIDENCE_HASH_MISMATCH")
    source = next((item for item in json.loads(b_partial.read_text())["results"] if item["variant_id"] == accepted["best"]["variant_id"]), None)
    if not source or _candidate_tuple_key(source.get("candidate", {})) != _candidate_tuple_key(control) or not source.get("data_hash") or not source.get("policy_hash"): raise ValueError("STAGE_C_STAGE_B_SOURCE_MISMATCH")
    for artifact in source.get("execution_artifacts", {}).values():
        if not Path(artifact["path"]).exists() or sha256_file(Path(artifact["path"])) != artifact["sha256"]: raise ValueError("STAGE_C_STAGE_B_ARTIFACT_HASH_MISMATCH")
    meta = {"optimizer_id":"stage-c-btc-management-v1","stage_b_report_sha256":sha256_file(stage_b_report),"stage_b_checkpoint_sha256":sha256_file(b_partial),"control_candidate":json.loads(_candidate_tuple_key(control)),"control_total":accepted["best"]["terminal_total"],"objective":"terminal TOTAL only","ranking_eligible_for_live":False}
    partial_path, lock_path = runs/f"{stem}.partial.json", runs/f"{stem}.lock"
    try: fd=os.open(lock_path, os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError as error: raise RuntimeError("STAGE_C_SINGLE_PROCESS_LOCK_HELD") from error
    try:
        os.write(fd,str(os.getpid()).encode()); os.close(fd)
        partial=json.loads(partial_path.read_text()) if partial_path.exists() else {"provenance":meta,"results":[],"sealed":{}}
        if partial.get("provenance")!=meta: raise ValueError("STAGE_C_PARTIAL_PROVENANCE_MISMATCH")
        results,sealed=list(partial["results"]),dict(partial["sealed"]); completed={x["variant_id"] for x in results}; by_tuple={_candidate_tuple_key(x["candidate"]):x for x in results}
        # c1-c4 were independently sealed before this fine pass.  Their plan
        # is immutable: resume can add c5/c6 only, never replay prior stages.
        if "c4" in sealed:
            return _run_stage_c_fine_neighbors(data_root, runs, stem, meta, partial_path, source, results, sealed)
        def persist(): _atomic_json(partial_path,{"provenance":meta,"results":results,"sealed":sealed})
        def add(name,candidate):
            if name in completed:return
            existing=by_tuple.get(_candidate_tuple_key(candidate)) or (source if candidate==control else None)
            item=_stage_a_reuse(name,candidate,existing) if existing else _stage_a_item(name,candidate,data_root,stem)
            results.append(item);completed.add(name);by_tuple.setdefault(_candidate_tuple_key(candidate),item);persist()
        def stage(name,base):
            for key,candidate in _stage_c_variants(name,base): add(key,candidate)
            options=[x for x in results if x["variant_id"].startswith(name+"-") and x.get("terminal_total") is not None]
            winner=max(options,key=lambda x:Decimal(x["terminal_total"]))
            if name not in sealed: sealed[name]=winner["variant_id"];persist()
            return next(x for x in options if x["variant_id"]==sealed[name])
        c1=stage("c1",control); c2=stage("c2",Candidate(**c1["candidate"])); c3=stage("c3",Candidate(**c2["candidate"])); add("c4-joint",Candidate(**c3["candidate"])); sealed.setdefault("c4","c4-joint");persist()
        ranked=sorted((x for x in results if x.get("terminal_total") is not None),key=lambda x:Decimal(x["terminal_total"]),reverse=True); top20=ranked[:20]; best=top20[0]
        for item in results: item.setdefault("btc_tp_level_attribution","UNKNOWN_NATIVE_FILLS_DO_NOT_EXPORT_TP_LEVEL_OR_EXIT_REASON")
        rows=[_stage_a_csv_row(x,meta["control_total"])|{"delta_vs_accepted_stage_b":str(Decimal(x["terminal_total"])-Decimal(meta["control_total"])),"btc_tp_level_attribution":"UNKNOWN_NATIVE_FILLS_DO_NOT_EXPORT_TP_LEVEL_OR_EXIT_REASON"} for x in top20]
        csv_path=runs/f"{stem}-top20.csv"; tmp=csv_path.with_suffix(".csv.tmp")
        with tmp.open("w",newline="") as stream: writer=csv.DictWriter(stream,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
        tmp.replace(csv_path)
        summary={"status":"NOT_FAITHFUL_DIAGNOSTIC","ranking_eligible_for_live":False,"provenance":meta,"sealed":sealed,"local_evidence":{"checkpoint":str(partial_path),"checkpoint_sha256":sha256_file(partial_path)},"result_count":len(results),"results":[_stage_b_compact(x,meta["control_total"],partial_path)|{"btc_tp_level_attribution":x["btc_tp_level_attribution"]} for x in results],"top20":[_stage_b_compact(x,meta["control_total"],partial_path)|{"btc_tp_level_attribution":x["btc_tp_level_attribution"]} for x in top20],"best":_stage_b_compact(best,meta["control_total"],partial_path)|{"btc_tp_level_attribution":best["btc_tp_level_attribution"]},"delta_vs_accepted_stage_b":str(Decimal(best["terminal_total"])-Decimal(meta["control_total"])),"limitations":["Stage C only; no Stage D.","BTC TP-level and exit-reason attribution UNKNOWN from native fills."]}
        target=runs/f"{stem}.json";_atomic_json(target,summary);return summary|{"artifact":str(target),"csv":str(csv_path),"partial":str(partial_path)}
    finally:
        if lock_path.exists(): lock_path.unlink()


def _stage_d_variants(stage: str, control: Candidate) -> tuple[tuple[str, Candidate], ...]:
    """The approved Stage-D coordinates, always one axis at a time."""
    if stage == "d1":
        values = STAGE_D_TP_AXIS
        return tuple((f"d1-tp-{'-'.join(f'{value:g}' for value in item)}", replace(control, btc_tp_fractions_initial_qty=item)) for item in values)
    if stage == "d2":
        return tuple((f"d2-ema-{value}", replace(control, ema_period=value)) for value in STAGE_D_EMA_AXIS)
    if stage == "d3":
        return tuple((f"d3-btc-{value:g}", replace(control, btc_notional_multiplier=value)) for value in STAGE_D_BTC_AXIS)
    if stage == "d4":
        return tuple((f"d4-sol-{'-'.join(f'{value:g}' for value in item)}", replace(control, sol_size_multipliers_h=item)) for item in STAGE_D_SOL_AXIS)
    raise ValueError(f"STAGE_D_UNKNOWN_STAGE:{stage}")


def _stage_d_sol_boundary_extension(winner: dict) -> tuple[str, Candidate] | None:
    profile = tuple(float(value) for value in winner["candidate"]["sol_size_multipliers_h"])
    if profile == STAGE_D_SOL_AXIS[0]:
        extended = (1.75, 2.625, 3.5)
    elif profile == STAGE_D_SOL_AXIS[-1]:
        extended = (2.75, 4.125, 5.5)
    else:
        return None
    return f"d5-boundary-sol-{'-'.join(f'{value:g}' for value in extended)}", replace(Candidate(**winner["candidate"]), sol_size_multipliers_h=extended)


def run_stage_d_joint_refinement(data_root: Path, stage_c_report: Path) -> dict:
    """One sequential, sealed Stage-D coordinate/joint pass; never Stage E."""
    runs, stem = data_root / "runs", "native-stage-d-joint-refinement-v1"
    runs.mkdir(parents=True, exist_ok=True)
    accepted = json.loads(stage_c_report.read_text())
    c_partial = data_root / "runs" / "native-stage-c-btc-management-v1.partial.json"
    if accepted.get("local_evidence", {}).get("checkpoint_sha256") != sha256_file(c_partial):
        raise ValueError("STAGE_D_STAGE_C_EVIDENCE_HASH_MISMATCH")
    source = next((item for item in json.loads(c_partial.read_text())["results"] if item["variant_id"] == accepted.get("best", {}).get("variant_id")), None)
    baseline = Candidate(ema_period=34, btc_tp_fractions_initial_qty=(0.2, 0.3, 0.5), btc_notional_multiplier=4.0, sol_size_multipliers_h=(2.25, 3.375, 4.5))
    if not source or _candidate_tuple_key(source.get("candidate", {})) != _candidate_tuple_key(baseline) or source.get("terminal_total") != "714572.72107702":
        raise ValueError("STAGE_D_ACCEPTED_STAGE_C_BASELINE_MISMATCH")
    _stage_c_validate_ranked_evidence([source], data_root)
    meta = {"optimizer_id": STAGE_D_ID, "stage_c_report_sha256": sha256_file(stage_c_report), "stage_c_checkpoint_sha256": sha256_file(c_partial), "control_candidate": json.loads(_candidate_tuple_key(baseline)), "control_total": source["terminal_total"], "seed": SEED, "reserve": "0", "objective": "terminal TOTAL only; liquidation remains eligible at actual TOTAL", "ranking_eligible_for_live": False}
    partial_path, lock_path = runs / f"{stem}.partial.json", runs / f"{stem}.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError("STAGE_D_SINGLE_PROCESS_LOCK_HELD") from error
    try:
        os.write(fd, str(os.getpid()).encode()); os.close(fd)
        partial = json.loads(partial_path.read_text()) if partial_path.exists() else {"provenance": meta, "results": [], "sealed": {}}
        if partial.get("provenance") != meta:
            raise ValueError("STAGE_D_PARTIAL_PROVENANCE_MISMATCH")
        results, sealed = list(partial["results"]), dict(partial.get("sealed", {}))
        completed = {item["variant_id"] for item in results}
        by_tuple = {_candidate_tuple_key(item["candidate"]): item for item in results}

        def persist() -> None:
            _atomic_json(partial_path, {"provenance": meta, "results": results, "sealed": sealed})

        def add(name: str, candidate: Candidate) -> None:
            if name in completed:
                return
            existing = by_tuple.get(_candidate_tuple_key(candidate)) or (source if _candidate_tuple_key(candidate) == _candidate_tuple_key(baseline) else None)
            item = _stage_a_reuse(name, candidate, existing) if existing else _stage_a_item(name, candidate, data_root, stem)
            results.append(item); completed.add(name); by_tuple.setdefault(_candidate_tuple_key(candidate), item); persist()

        def stage(name: str, base: Candidate) -> dict:
            for variant_id, candidate in _stage_d_variants(name, base):
                add(variant_id, candidate)
            options = [item for item in results if item["variant_id"].startswith(f"{name}-") and item.get("terminal_total") is not None]
            if not options:
                raise ValueError(f"STAGE_D_EMPTY:{name}")
            if name not in sealed:
                sealed[name] = max(options, key=lambda item: Decimal(item["terminal_total"]))["variant_id"]
                persist()
            return next(item for item in options if item["variant_id"] == sealed[name])

        add("d0-stage-c-baseline", baseline)
        d1 = stage("d1", baseline)
        d2 = stage("d2", Candidate(**d1["candidate"]))
        d3 = stage("d3", Candidate(**d2["candidate"]))
        d4 = stage("d4", Candidate(**d3["candidate"]))
        best_coordinate = max((d1, d2, d3, d4), key=lambda item: Decimal(item["terminal_total"]))
        if Decimal(best_coordinate["terminal_total"]) > Decimal(source["terminal_total"]):
            add("d5-joint", Candidate(**d4["candidate"]))
            sealed.setdefault("d5", "d5-joint"); persist()
            # Exactly one extension is permitted, and only from the final
            # joint/SOL boundary after a genuine Stage-D improvement.
            extension = _stage_d_sol_boundary_extension(d4)
            if extension and Decimal(d4["terminal_total"]) > Decimal(source["terminal_total"]) and d4.get("liquidation_count", 0) == 0:
                add(*extension)
                sealed.setdefault("d5_boundary", extension[0]); persist()
        for item in results:
            item.setdefault("btc_tp_level_attribution", "UNKNOWN_NATIVE_FILLS_DO_NOT_EXPORT_TP_LEVEL_OR_EXIT_REASON")
            item.setdefault("sol_fill_add_level_attribution", "UNKNOWN_NATIVE_FILLS_DO_NOT_EXPORT_SOL_ADD_LEVEL")
        ranked = sorted((item for item in results if item.get("terminal_total") is not None), key=lambda item: Decimal(item["terminal_total"]), reverse=True)
        _stage_c_validate_ranked_evidence(ranked, data_root)
        top20, best = ranked[:20], ranked[0]
        rows = [_stage_a_csv_row(item, meta["control_total"]) | {"delta_vs_stage_c": str(Decimal(item["terminal_total"]) - Decimal(meta["control_total"])), "btc_tp_level_attribution": item["btc_tp_level_attribution"], "sol_fill_add_level_attribution": item["sol_fill_add_level_attribution"]} for item in top20]
        csv_path, temporary = runs / f"{stem}-top20.csv", runs / f"{stem}-top20.csv.tmp"
        with temporary.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
        temporary.replace(csv_path)
        summary = {"status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible_for_live": False, "provenance": meta, "sealed": sealed, "local_evidence": {"checkpoint": str(partial_path), "checkpoint_sha256": sha256_file(partial_path), "ranked_evidence_validated": True}, "result_count": len(results), "results": [_stage_b_compact(item, meta["control_total"], partial_path) | {"delta_vs_stage_c": str(Decimal(item["terminal_total"]) - Decimal(meta["control_total"])), "btc_tp_level_attribution": item["btc_tp_level_attribution"], "sol_fill_add_level_attribution": item["sol_fill_add_level_attribution"]} for item in results], "top20": [_stage_b_compact(item, meta["control_total"], partial_path) | {"delta_vs_stage_c": str(Decimal(item["terminal_total"]) - Decimal(meta["control_total"])), "btc_tp_level_attribution": item["btc_tp_level_attribution"], "sol_fill_add_level_attribution": item["sol_fill_add_level_attribution"]} for item in top20], "best": _stage_b_compact(best, meta["control_total"], partial_path) | {"delta_vs_stage_c": str(Decimal(best["terminal_total"]) - Decimal(meta["control_total"])), "btc_tp_level_attribution": best["btc_tp_level_attribution"], "sol_fill_add_level_attribution": best["sol_fill_add_level_attribution"]}, "delta_vs_stage_c": str(Decimal(best["terminal_total"]) - Decimal(meta["control_total"])), "limitations": ["Stage D only; no Stage E or hypotheses.", "BTC TP-level and SOL add-level attribution UNKNOWN from native fills."]}
        target = runs / f"{stem}.json"; _atomic_json(target, summary)
        return summary | {"artifact": str(target), "csv": str(csv_path), "partial": str(partial_path)}
    finally:
        if lock_path.exists():
            lock_path.unlink()


HYPOTHESIS_ID = "native-hypothesis-pass-v1"


def run_native_hypothesis_pass(data_root: Path, stage_d_report: Path) -> dict:
    """Sequential independent H1/H3/H4 tests over a reused Stage-D H0."""
    runs, stem = data_root / "runs", "native-hypothesis-pass-v1"
    runs.mkdir(parents=True, exist_ok=True)
    accepted = json.loads(stage_d_report.read_text())
    d_partial = data_root / "runs" / "native-stage-d-joint-refinement-v1.partial.json"
    if accepted.get("local_evidence", {}).get("checkpoint_sha256") != sha256_file(d_partial):
        raise ValueError("HYPOTHESIS_STAGE_D_EVIDENCE_HASH_MISMATCH")
    source = next((item for item in json.loads(d_partial.read_text())["results"] if item["variant_id"] == accepted.get("best", {}).get("variant_id")), None)
    control = Candidate(ema_period=34, btc_tp_fractions_initial_qty=(0.2, 0.25, 0.55), btc_notional_multiplier=4.0, sol_size_multipliers_h=(2.0, 3.0, 4.0))
    source_candidate = source.get("candidate", {}) if source else {}
    legacy_control = {key: asdict(control)[key] for key in source_candidate if key in asdict(control)}
    if not source or _candidate_tuple_key(source_candidate) != _candidate_tuple_key(legacy_control) or source.get("terminal_total") != "740906.55113925":
        raise ValueError("HYPOTHESIS_STAGE_D_CONTROL_MISMATCH")
    _stage_c_validate_ranked_evidence([source], data_root)
    meta = {"optimizer_id": HYPOTHESIS_ID, "stage_d_report_sha256": sha256_file(stage_d_report), "stage_d_checkpoint_sha256": sha256_file(d_partial), "control_candidate": source["candidate"], "control_total": source["terminal_total"], "objective": "terminal TOTAL only", "independent_hypotheses": ["H1", "H2", "H3", "H4"], "h2_definition": "freeze entry beta only; current relative uses it while rolling feature mu/sigma remain unchanged", "ranking_eligible_for_live": False}
    partial_path, lock_path = runs / f"{stem}.partial.json", runs / f"{stem}.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError("HYPOTHESIS_SINGLE_PROCESS_LOCK_HELD") from error
    try:
        os.write(fd, str(os.getpid()).encode()); os.close(fd)
        partial = json.loads(partial_path.read_text()) if partial_path.exists() else {"provenance": meta, "results": []}
        if partial.get("provenance") != meta:
            raise ValueError("HYPOTHESIS_PARTIAL_PROVENANCE_MISMATCH")
        results = list(partial["results"])
        completed = {item["variant_id"] for item in results}

        def persist() -> None:
            _atomic_json(partial_path, {"provenance": meta, "results": results})

        def add(name: str, candidate: Candidate | None, *, reuse: dict | None = None, blocked: str | None = None) -> None:
            if name in completed:
                return
            if blocked:
                item = {"variant_id": name, "status": "BLOCKED", "error": blocked, "candidate": source["candidate"]}
            elif reuse:
                item = _stage_a_reuse(name, source["candidate"], reuse)
            else:
                assert candidate is not None
                item = _stage_a_item(name, candidate, data_root, stem)
            results.append(item); completed.add(name); persist()

        add("H0-control-reuse", None, reuse=source)
        add("H1-timeout-preempts-sol-add", replace(control, sol_timeout_preempts_add=True))
        add("H2-episode-fixed-beta", replace(control, episode_fixed_beta=True))
        # The sealed control already permits a late z signal after a confirmed
        # TP right. H3 executes that explicit, behavior-preserving version.
        add("H3-late-sol-entry-after-tp", replace(control, sol_late_entry_after_tp=True))
        add("H4-btc-only", replace(control, sol_overlay_enabled=False))
        ranked = sorted((item for item in results if item.get("terminal_total") is not None), key=lambda item: Decimal(item["terminal_total"]), reverse=True)
        _stage_c_validate_ranked_evidence(ranked, data_root)
        h0 = next(item for item in results if item["variant_id"] == "H0-control-reuse")
        h4 = next(item for item in results if item["variant_id"] == "H4-btc-only")
        for item in ranked:
            item.setdefault("btc_tp_level_attribution", "UNKNOWN_NATIVE_FILLS_DO_NOT_EXPORT_TP_LEVEL_OR_EXIT_REASON")
            item.setdefault("sol_fill_add_level_attribution", "UNKNOWN_NATIVE_FILLS_DO_NOT_EXPORT_SOL_ADD_LEVEL")
        rows = [_stage_a_csv_row(item, meta["control_total"]) | {"delta_vs_h0": str(Decimal(item["terminal_total"]) - Decimal(h0["terminal_total"])), "sol_incremental_vs_btc_only": str(Decimal(h0["terminal_total"]) - Decimal(h4["terminal_total"])) if item["variant_id"] == "H4-btc-only" else None} for item in ranked]
        csv_path, temporary = runs / f"{stem}-top20.csv", runs / f"{stem}-top20.csv.tmp"
        with temporary.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
        temporary.replace(csv_path)
        compact = lambda item: _stage_b_compact(item, meta["control_total"], partial_path) | {"delta_vs_h0": str(Decimal(item["terminal_total"]) - Decimal(h0["terminal_total"]))}
        summary = {"status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible_for_live": False, "provenance": meta, "local_evidence": {"checkpoint": str(partial_path), "checkpoint_sha256": sha256_file(partial_path), "ranked_evidence_validated": True}, "result_count": len(results), "results": [compact(item) for item in results], "top20": [compact(item) for item in ranked], "h0": compact(h0), "h2": compact(next(item for item in results if item["variant_id"] == "H2-episode-fixed-beta")), "h4_sol_incremental": str(Decimal(h0["terminal_total"]) - Decimal(h4["terminal_total"])), "defaults": {"H1": "off", "H2": "off", "H3": "current control semantics retained", "H4": "off"}, "limitations": ["Independent hypotheses only; no combinations.", "No Stage E."]}
        target = runs / f"{stem}.json"; _atomic_json(target, summary)
        return summary | {"artifact": str(target), "csv": str(csv_path), "partial": str(partial_path)}
    finally:
        if lock_path.exists():
            lock_path.unlink()


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
