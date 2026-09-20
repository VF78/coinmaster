from __future__ import annotations

import json
from decimal import Decimal

from coinmaster.research.native_sequential import (
    CLASSIFICATION,
    TEST_END_MS,
    TEST_START_MS,
    TRAIN_AXIS,
    TRAIN_END_MS,
    TRAIN_START_MS,
    run_sequential_seen_data_validation,
    select_train_winner,
    sequential_plan,
)


def _report(multiplier: float, *, liquidated: bool = False) -> dict:
    total = Decimal(str(multiplier * 100))
    return {
        "status": "NOT_FAITHFUL_DIAGNOSTIC", "config_hash": f"config-{multiplier}", "data_hash": "data", "code_hash": "code", "policy_hash": "policy",
        "terminal_active": str(total), "terminal_reserve": "0", "terminal_total": str(total), "terminal_open_positions": 0,
        "summary": {"roi": "0", "max_drawdown_amount": "0", "max_drawdown_percent": "0", "monthly_returns": []},
        "fills": 0, "native_fees": "0", "funding": {"count": 0}, "liquidation_count": int(liquidated), "liquidation_value": "0",
        "liquidation_audit": [{"lockout": True}] if liquidated else [], "liquidation_lockout": liquidated,
        "post_boundary_settlement": {"boundary_timestamp": "test", "fill_count": 0},
    }


def test_plan_has_exact_half_windows_axis_and_730_day_warmups() -> None:
    plan = sequential_plan()
    assert plan["classification"] == CLASSIFICATION
    assert plan["train"]["start_ms"] == TRAIN_START_MS and plan["train"]["end_ms"] == TRAIN_END_MS
    assert plan["test"]["start_ms"] == TEST_START_MS and plan["test"]["end_ms"] == TEST_END_MS
    assert tuple(plan["train_axis"]) == TRAIN_AXIS
    assert plan["train"]["warmup_days"] == plan["test"]["warmup_days"] == 730


def test_selection_keeps_liquidated_higher_terminal_total() -> None:
    winner = select_train_winner([
        {"axis_index": 0, "terminal_active": "200", "terminal_reserve": "0", "liquidation_count": 0, "error": None},
        {"axis_index": 1, "terminal_active": "300", "terminal_reserve": "0", "liquidation_count": 1, "error": None},
    ])
    assert winner is not None and winner["liquidation_count"] == 1


def test_resumes_train_then_locks_winner_and_runs_distinct_test_v0(tmp_path) -> None:
    (tmp_path / "bybit-1m").mkdir()
    (tmp_path / "bybit-1m" / "manifest.json").write_text(json.dumps({"source": "test"}))
    calls: list[tuple[str, float]] = []

    def runner(_root, *, candidate, artifact_label, **_kwargs):
        value = float(candidate.btc_notional_multiplier)
        calls.append((artifact_label, value))
        return _report(value, liquidated=value == 10.5)

    first = run_sequential_seen_data_validation(tmp_path, runner=runner)
    assert len(calls) == 7  # five train rows, locked 10.5 winner, and v0.
    assert first["selection"]["locked_multiplier"] == 10.5
    assert first["selection"]["winner_equals_v0"] is False
    assert all(item["status"] == "NOT_FAITHFUL_DIAGNOSTIC" for item in first["train_results"])
    assert first["artifacts"]["json"]["sha256"]
    second = run_sequential_seen_data_validation(tmp_path, runner=runner)
    assert len(calls) == 7 and second["artifacts"] == first["artifacts"]


def test_equal_winner_and_v0_records_one_distinct_test_run(tmp_path) -> None:
    (tmp_path / "bybit-1m").mkdir()
    (tmp_path / "bybit-1m" / "manifest.json").write_text("{}")
    calls: list[str] = []

    def runner(_root, *, candidate, artifact_label, **_kwargs):
        calls.append(artifact_label)
        return _report(900 if candidate.btc_notional_multiplier == 9.0 else 1)

    result = run_sequential_seen_data_validation(tmp_path, runner=runner)
    assert result["selection"]["winner_equals_v0"] is True
    assert [row["phase"] for row in result["test_results"]] == ["test_winner_and_v0"]
    assert len(calls) == 6
