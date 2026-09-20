import json

from coinmaster.research.native_baseline import ExecutionPolicy, coverage_blockers, monthly_returns


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
    assert "0.001" in policy.fees and policy.fee_historical_applicability == "UNKNOWN"


def test_monthly_returns_carry_forward_empty_months() -> None:
    rows = [{"timestamp": "2024-09-30T00:00:00+00:00", "total": "11000"}, {"timestamp": "2024-11-01T00:00:00+00:00", "total": "12100"}]
    assert monthly_returns(rows) == [{"month": "2024-09", "total": "11000", "return": "0.1"}, {"month": "2024-10", "total": "11000", "return": "0"}, {"month": "2024-11", "total": "12100", "return": "0.1"}]
