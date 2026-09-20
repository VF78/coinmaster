import json
from decimal import Decimal
import pytest

from coinmaster.research.native_baseline import ExecutionPolicy, assert_report_boundaries, coverage_blockers, monthly_returns, run_native_diagnostic


def test_baseline_refuses_partial_or_unhashed_minute_coverage(tmp_path) -> None:
    root = tmp_path / "data" / "bybit-1m"
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({"symbols": [{"symbol": "BTCUSDT", "streams": [{"stream": "execution", "status": "PARTIAL_RESUMABLE"}, {"stream": "mark", "missing_count": 0}]}]}))
    assert coverage_blockers(root.parent) == ["BTCUSDT:execution:PARTIAL", "BTCUSDT:mark:UNHASHED"]


def test_baseline_accepts_complete_hashed_coverage(tmp_path) -> None:
    root = tmp_path / "bybit-1m"
    root.mkdir()
    (root / "manifest.json").write_text(json.dumps({"symbols": [{"symbol": "BTCUSDT", "streams": [{"stream": "execution", "missing_count": 0, "parquet_sha256": "a"}, {"stream": "mark", "missing_count": 0, "parquet_sha256": "b"}]}]}))
    assert coverage_blockers(root.parent) == []


def test_execution_policy_is_versioned_hashed_and_explicit_about_unknown_costs() -> None:
    policy = ExecutionPolicy()
    assert len(policy.hash) == 64
    assert policy.execution_source == "BYBIT_GAP_FREE_1M_EXECUTION_CLOSE"
    assert "0.001" in policy.fees and policy.fee_historical_applicability == "UNKNOWN" and policy.nonmatching_daily_signals


def test_daily_bar_matching_is_rejected_before_any_data_or_engine_is_loaded(tmp_path) -> None:
    with pytest.raises(ValueError, match="LEGACY_DAILY_BAR_MATCHING_DISABLED"):
        run_native_diagnostic(tmp_path, execution_policy=ExecutionPolicy(nonmatching_daily_signals=False))


def test_monthly_returns_carry_forward_empty_months() -> None:
    rows = [{"timestamp": "2024-09-30T00:00:00+00:00", "total": "11000"}, {"timestamp": "2024-11-01T00:00:00+00:00", "total": "12100"}]
    assert monthly_returns(rows) == [{"month": "2024-09", "total": "11000", "return": "0.1"}, {"month": "2024-10", "total": "11000", "return": "0"}, {"month": "2024-11", "total": "12100", "return": "0.1"}]


def test_report_boundaries_require_terminal_reconciliation_and_trading_dd() -> None:
    total = Decimal("12000")
    months = [{"month": "2024-09", "total": "11000", "return": "0.1"}]
    months.extend({"month": f"2024-{month:02d}", "total": "11000", "return": "0"} for month in range(10, 13))
    months.extend({"month": f"2025-{month:02d}", "total": "11000", "return": "0"} for month in range(1, 13))
    months.extend({"month": f"2026-{month:02d}", "total": "11000", "return": "0"} for month in range(1, 8))
    months.append({"month": "2026-08", "total": "12000", "return": str((total / Decimal("11000")) - 1)})
    report = {"terminal_total": "12000", "run_interval": {"start": "2024-09-01T00:00:00+00:00", "end_exclusive": "2026-09-01T00:00:00+00:00", "initial_active_seed": "10000"}, "summary": {"monthly_returns": months, "drawdown_start": "2024-09-01T00:00:00+00:00", "drawdown_trough": "2026-09-01T00:00:00+00:00"}}
    assert_report_boundaries(report)
