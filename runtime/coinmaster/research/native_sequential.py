"""Bounded seen-data sequential validation over the canonical native engine."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import asdict, replace
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any, Callable

from coinmaster.domain.wave_overlay import Candidate
from coinmaster.research.native_baseline import DAY_MS, ExecutionPolicy, run_native_diagnostic


SEQUENTIAL_ID = "p3-2-sequential-seen-data-reporting-v2"
CLASSIFICATION = "SEQUENTIAL_SEEN_DATA_VALIDATION_NOT_OOS + NOT_FAITHFUL_DIAGNOSTIC"
TRAIN_AXIS = (9.0, 7.5, 8.25, 9.75, 10.5)
TRAIN_START_MS = int(datetime(2024, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)
TRAIN_END_MS = int(datetime(2025, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)
TEST_START_MS = TRAIN_END_MS
TEST_END_MS = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)

NativeRunner = Callable[..., dict[str, Any]]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _candidate(value: float) -> Candidate:
    return replace(Candidate(), btc_notional_multiplier=value)


def _window(window_id: str, start_ms: int, end_ms: int) -> dict[str, Any]:
    return {
        "id": window_id,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "start": datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc).isoformat(),
        "end_exclusive": datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc).isoformat(),
        "warmup_start_ms": start_ms - 730 * DAY_MS,
        "warmup_days": 730,
    }


def sequential_plan() -> dict[str, Any]:
    """The complete predeclared two-window protocol; no adaptive refinements."""
    return {
        "sequential_id": SEQUENTIAL_ID,
        "classification": CLASSIFICATION,
        "train": _window("train", TRAIN_START_MS, TRAIN_END_MS),
        "test": _window("test", TEST_START_MS, TEST_END_MS),
        "train_axis": list(TRAIN_AXIS),
        "selection_rule": "max terminal ACTIVE + RESERVE after all costs; liquidated terminal rows remain eligible",
        "test_rule": "fresh locked winner plus v0; if equal, one distinct winner_and_v0 run",
        "policy": asdict(ExecutionPolicy()),
        "policy_hash": ExecutionPolicy().hash,
    }


def select_train_winner(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select only by settled terminal objective; never filter liquidation rows."""
    candidates = [
        row for row in rows
        if row.get("error") is None and row.get("terminal_active") is not None and row.get("terminal_reserve") is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: (Decimal(row["terminal_active"]) + Decimal(row["terminal_reserve"]), -int(row["axis_index"])))


def _row(
    *, run_id: str, phase: str, axis_index: int, candidate: Candidate, window: dict[str, Any], report: dict[str, Any] | None = None,
    error: Exception | None = None,
) -> dict[str, Any]:
    base = {
        "run_id": run_id,
        "phase": phase,
        "classification": CLASSIFICATION,
        "axis_index": axis_index,
        "candidate": asdict(candidate),
        "candidate_hash": hashlib.sha256(_canonical(asdict(candidate)).encode()).hexdigest(),
        "interval": {key: window[key] for key in ("start", "end_exclusive", "warmup_start_ms", "warmup_days")},
        "fresh_account_engine_journal": True,
    }
    if error is not None:
        return base | {"status": "FAILED", "error": f"{type(error).__name__}:{error}", "terminal_active": None, "terminal_reserve": None, "terminal_total": None, "terminal_flat": False}
    assert report is not None
    return base | {
        "status": report["status"],
        "error": None,
        "config_hash": report["config_hash"],
        "data_hash": report["data_hash"],
        "code_hash": report["code_hash"],
        "policy_hash": report["policy_hash"],
        "terminal_active": report["terminal_active"],
        "terminal_reserve": report["terminal_reserve"],
        "terminal_total": report["terminal_total"],
        "roi": report["summary"]["roi"],
        "cash_drawdown": {
            "amount": report["summary"]["max_drawdown_amount"],
            "percent": report["summary"]["max_drawdown_percent"],
        },
        "monthly_returns": report["summary"]["monthly_returns"],
        "fills": report["fills"],
        "native_fees": report["native_fees"],
        "funding": report["funding"],
        "liquidation_count": report["liquidation_count"],
        "liquidation_value": report["liquidation_value"],
        "liquidation_audit": report["liquidation_audit"],
        "liquidation_lockout": report["liquidation_lockout"],
        "terminal_flat": report["terminal_open_positions"] == 0,
        "terminal_open_positions": report["terminal_open_positions"],
        "post_boundary_settlement": report["post_boundary_settlement"],
        "report": report,
    }


def _write_partial(path: Path, provenance: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps({"provenance": provenance, "results": rows}, indent=2, sort_keys=True) + "\n")


def _load_partial(path: Path, provenance: dict[str, Any]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    partial = json.loads(path.read_text())
    if partial.get("provenance") != provenance:
        raise ValueError("SEQUENTIAL_PARTIAL_PROVENANCE_MISMATCH")
    return list(partial.get("results", ()))


def _write_final(path: Path, value: dict[str, Any]) -> None:
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_bytes() != encoded.encode():
        raise ValueError("SEQUENTIAL_IMMUTABLE_ARTIFACT_EXISTS")
    path.write_bytes(encoded.encode())


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = (
        "run_id", "phase", "axis_index", "status", "candidate", "candidate_hash", "interval", "config_hash", "data_hash", "code_hash", "policy_hash",
        "terminal_active", "terminal_reserve", "terminal_total", "roi", "cash_drawdown", "monthly_returns", "fills", "native_fees", "funding",
        "liquidation_count", "liquidation_value", "liquidation_lockout", "terminal_flat", "terminal_open_positions", "post_boundary_settlement", "error",
    )
    stream = io.StringIO()
    with stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: _canonical(row[field]) if isinstance(row.get(field), (dict, list)) else row.get(field) for field in fields} for row in rows)
        encoded = stream.getvalue()
    if path.exists() and path.read_bytes() != encoded.encode():
        raise ValueError("SEQUENTIAL_IMMUTABLE_ARTIFACT_EXISTS")
    path.write_bytes(encoded.encode())


def run_sequential_seen_data_validation(data_root: Path, *, runner: NativeRunner = run_native_diagnostic) -> dict[str, Any]:
    """Run exactly the predeclared train axis and locked-winner test comparison."""
    plan = sequential_plan()
    runtime = Path(__file__).resolve().parents[2]
    manifest = data_root / "bybit-1m" / "manifest.json"
    if not manifest.is_file():
        raise ValueError("SEQUENTIAL_MISSING_BYBIT_1M_MANIFEST")
    provenance = {
        "plan": plan,
        "data_manifest_sha256": sha256_file(manifest),
        "code_hashes": {
            name: sha256_file(runtime / name)
            for name in (
                "coinmaster/domain/wave_overlay.py", "coinmaster/strategy/wave_overlay.py",
                "coinmaster/research/native_baseline.py", "coinmaster/research/native_fixture.py",
                "coinmaster/research/native_sequential.py",
            )
        },
    }
    runs = data_root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    stem = "native-sequential-seen-data-reporting-v2"
    partial_path = runs / f"{stem}.partial.json"
    json_path, csv_path = runs / f"{stem}.json", runs / f"{stem}.csv"
    # A completed immutable report is authoritative over any interrupted
    # partial writer. This branch never constructs an engine or journal.
    if json_path.exists():
        final = json.loads(json_path.read_text())
        if final.get("status") != CLASSIFICATION or final.get("provenance", {}).get("plan") != plan:
            raise ValueError("SEQUENTIAL_FINAL_ARTIFACT_PROTOCOL_MISMATCH")
        final_rows = list(final.get("train_results", ())) + list(final.get("test_results", ()))
        _write_partial(partial_path, final["provenance"], final_rows)
        _write_csv(csv_path, final_rows)
        artifacts = {name: {"path": str(path), "sha256": sha256_file(path)} for name, path in (("json", json_path), ("csv", csv_path), ("partial", partial_path))}
        return final | {"artifacts": artifacts}
    rows = _load_partial(partial_path, provenance)
    completed = {row["run_id"] for row in rows}

    def execute(run_id: str, phase: str, axis_index: int, multiplier: float, window: dict[str, Any]) -> None:
        if run_id in completed:
            return
        candidate = _candidate(multiplier)
        started = monotonic()
        try:
            report = runner(
                data_root, include_funding=True, candidate=candidate,
                trading_start_ms=window["start_ms"], trading_end_ms=window["end_ms"], warmup_start_ms=window["warmup_start_ms"],
                artifact_dir=runs, artifact_label=run_id, stop_on_liquidation=False,
            )
            row = _row(run_id=run_id, phase=phase, axis_index=axis_index, candidate=candidate, window=window, report=report)
            row["wall_time_seconds"] = str(monotonic() - started)
        except Exception as error:
            row = _row(run_id=run_id, phase=phase, axis_index=axis_index, candidate=candidate, window=window, error=error)
        rows.append(row)
        completed.add(run_id)
        _write_partial(partial_path, provenance, rows)

    for index, multiplier in enumerate(TRAIN_AXIS):
        execute(f"{stem}-train-{multiplier:g}", "train", index, multiplier, plan["train"])
    train_rows = [row for row in rows if row["phase"] == "train"]
    winner = select_train_winner(train_rows)
    if winner is not None:
        winner_multiplier = float(winner["candidate"]["btc_notional_multiplier"])
        if winner_multiplier == 9.0:
            execute(f"{stem}-test-winner-and-v0", "test_winner_and_v0", 0, 9.0, plan["test"])
        else:
            execute(f"{stem}-test-winner-{winner_multiplier:g}", "test_winner", 0, winner_multiplier, plan["test"])
            execute(f"{stem}-test-v0", "test_v0", 1, 9.0, plan["test"])
    test_rows = [row for row in rows if row["phase"].startswith("test")]
    summary = {
        "status": CLASSIFICATION,
        "ranking_eligible_for_live": False,
        "provenance": provenance,
        "selection": {
            "objective": plan["selection_rule"],
            "locked_train_winner": winner["run_id"] if winner else None,
            "locked_multiplier": winner["candidate"]["btc_notional_multiplier"] if winner else None,
            "winner_equals_v0": bool(winner and float(winner["candidate"]["btc_notional_multiplier"]) == 9.0),
            "test_rule": plan["test_rule"],
        },
        "train_results": train_rows,
        "test_results": test_rows,
        "limitations": [
            "SEQUENTIAL_SEEN_DATA_VALIDATION_NOT_OOS", "NOT_FAITHFUL_DIAGNOSTIC",
            "No parameter, execution, policy, profile, or data-source promotion is permitted.",
            "Historical fee/tier, BBO/liquidity, settlement-mark, and intraminute-liquidation fidelity remain unvalidated.",
        ],
    }
    _write_final(json_path, summary)
    _write_csv(csv_path, rows)
    artifacts = {name: {"path": str(path), "sha256": sha256_file(path)} for name, path in (("json", json_path), ("csv", csv_path), ("partial", partial_path))}
    return summary | {"artifacts": artifacts}


def recover_liquidated_train_rows(data_root: Path, *, runner: NativeRunner = run_native_diagnostic) -> dict[str, Any]:
    """Reporting-only recovery for the two rows lost to pre-lockout month checks."""
    runs = data_root / "runs"
    prior_path = runs / "native-sequential-seen-data-reporting-v2.json"
    prior = json.loads(prior_path.read_text())
    plan = sequential_plan()
    if prior.get("status") != CLASSIFICATION or prior.get("provenance", {}).get("plan") != plan:
        raise ValueError("SEQUENTIAL_RECOVERY_SOURCE_MISMATCH")
    targets = [row for row in prior["train_results"] if row.get("error") == "ValueError:MONTHLY_ROW_COUNT:7"]
    if tuple(float(row["candidate"]["btc_notional_multiplier"]) for row in targets) != (9.75, 10.5):
        raise ValueError("SEQUENTIAL_RECOVERY_TARGET_MISMATCH")
    stem = "native-sequential-seen-data-reporting-v2-reporting-recovery1"
    partial_path, json_path, csv_path = runs / f"{stem}.partial.json", runs / f"{stem}.json", runs / f"{stem}.csv"
    provenance = {
        "plan": plan, "recovery": "MONTHLY_ROW_COUNT early liquidation lockout accepted without changing execution",
        "supersedes_json": {"path": str(prior_path), "sha256": sha256_file(prior_path)},
        "data_manifest_sha256": sha256_file(data_root / "bybit-1m" / "manifest.json"),
    }
    if json_path.exists():
        final = json.loads(json_path.read_text())
        if final.get("provenance") != provenance:
            raise ValueError("SEQUENTIAL_RECOVERY_IMMUTABLE_MISMATCH")
        return final | {"artifacts": {name: {"path": str(path), "sha256": sha256_file(path)} for name, path in (("json", json_path), ("csv", csv_path), ("partial", partial_path))}}
    rows = _load_partial(partial_path, provenance)
    completed = {row["run_id"] for row in rows}
    for old in targets:
        multiplier = float(old["candidate"]["btc_notional_multiplier"])
        run_id = f"{stem}-train-{multiplier:g}"
        if run_id in completed:
            continue
        candidate = _candidate(multiplier)
        try:
            report = runner(data_root, include_funding=True, candidate=candidate, trading_start_ms=TRAIN_START_MS, trading_end_ms=TRAIN_END_MS, warmup_start_ms=TRAIN_START_MS - 730 * DAY_MS, artifact_dir=runs, artifact_label=run_id, stop_on_liquidation=False)
            row = _row(run_id=run_id, phase="train_reporting_recovery", axis_index=TRAIN_AXIS.index(multiplier), candidate=candidate, window=plan["train"], report=report)
        except Exception as error:
            row = _row(run_id=run_id, phase="train_reporting_recovery", axis_index=TRAIN_AXIS.index(multiplier), candidate=candidate, window=plan["train"], error=error)
        rows.append(row); completed.add(run_id); _write_partial(partial_path, provenance, rows)
    recovered = {float(row["candidate"]["btc_notional_multiplier"]): row for row in rows}
    train = [recovered.get(float(row["candidate"]["btc_notional_multiplier"]), row) for row in prior["train_results"]]
    winner = select_train_winner(train)
    summary = {
        "status": CLASSIFICATION, "ranking_eligible_for_live": False, "provenance": provenance,
        "selection": {"objective": plan["selection_rule"], "locked_train_winner": winner["run_id"] if winner else None, "locked_multiplier": winner["candidate"]["btc_notional_multiplier"] if winner else None, "prior_locked_multiplier": prior["selection"]["locked_multiplier"], "test_winner_unchanged": bool(winner and winner["candidate"]["btc_notional_multiplier"] == prior["selection"]["locked_multiplier"])},
        "train_results": train, "test_results": prior["test_results"],
        "limitations": ["SEQUENTIAL_SEEN_DATA_VALIDATION_NOT_OOS", "NOT_FAITHFUL_DIAGNOSTIC", "Reporting recovery reran only 9.75 and 10.5 after authoritative liquidation lockout ended cash months early."],
    }
    _write_final(json_path, summary); _write_csv(csv_path, train + prior["test_results"])
    return summary | {"artifacts": {name: {"path": str(path), "sha256": sha256_file(path)} for name, path in (("json", json_path), ("csv", csv_path), ("partial", partial_path))}}
