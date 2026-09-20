import json
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from coinmaster.research.native_baseline import DAY_MS, MINUTE_MS, ExecutionPolicy, assert_report_boundaries, coverage_blockers, iter_minute_bundles, iter_weekly_minute_batches, monthly_returns, run_native_diagnostic, run_sparse_native_diagnostic_legacy, standard_drawdown


def write_streaming_fixture(root, trading_days: int = 2) -> tuple[int, int]:
    """Small, complete four-stream fixture plus the required 730d seed."""
    warmup_start, trading_start = 0, 730 * DAY_MS
    trading_end = trading_start + trading_days * DAY_MS
    normalized = root / "normalized"
    normalized.mkdir(parents=True)
    for symbol, base in (("BTCUSDT", Decimal("100")), ("SOLUSDT", Decimal("30"))):
        daily = [{
            "open_time_ms": timestamp,
            "open": str(base), "high": str(base + 1), "low": str(base - 1), "close": str(base),
            "volume": "1", "turnover": "1", "mark_close": str(base),
        } for timestamp in range(warmup_start, trading_end, DAY_MS)]
        pq.write_table(pa.Table.from_pylist(daily), normalized / f"bybit-{symbol}-daily.parquet")
        for stream in ("execution", "mark"):
            rows = [{
                "open_time_ms": timestamp,
                "open": str(base), "high": str(base + 1), "low": str(base - 1), "close": str(base),
                **({"volume": "1", "turnover": "1"} if stream == "execution" else {}),
            } for timestamp in range(trading_start, trading_end, MINUTE_MS)]
            pq.write_table(pa.Table.from_pylist(rows), normalized / f"bybit-{symbol}-{stream}-1m.parquet")
    streams = [{"stream": stream, "missing_count": 0, "parquet_sha256": "fixture"} for stream in ("execution", "mark")]
    (root / "bybit-1m").mkdir()
    (root / "bybit-1m" / "manifest.json").write_text(json.dumps({"symbols": [{"symbol": symbol, "streams": streams} for symbol in ("BTCUSDT", "SOLUSDT")]}))
    return trading_start, trading_end


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


def test_sparse_legacy_diagnostic_is_unreachable() -> None:
    with pytest.raises(ValueError, match="NONCANONICAL_SPARSE_DIAGNOSTIC_DISABLED"):
        run_sparse_native_diagnostic_legacy(Path("ignored"))


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
    report = {"terminal_total": "12000", "run_interval": {"start": "2024-09-01T00:00:00+00:00", "end_exclusive": "2026-09-01T00:00:00+00:00", "initial_active_seed": "10000"}, "summary": {"monthly_returns": months, "interval_cash_terminal_total": "12000", "drawdown_start": "2024-09-01T00:00:00+00:00", "drawdown_trough": "2026-08-31T23:59:00+00:00"}, "fill_timestamps_ns": [1788220800000000000], "post_boundary_settlement": {"convention": "TERMINAL_FILLS_AT_END_EXCLUSIVE_REPORTED_SEPARATELY_EXCLUDED_FROM_INTERVAL_RETURNS", "fill_count": 1}}
    assert_report_boundaries(report)


def test_standard_drawdown_uses_preceding_peak_not_initial_seed() -> None:
    drawdown = standard_drawdown([
        {"timestamp": "2024-09-01T00:00:00+00:00", "total": "10000"},
        {"timestamp": "2024-09-02T00:00:00+00:00", "total": "20000"},
        {"timestamp": "2024-09-03T00:00:00+00:00", "total": "15000"},
    ], Decimal("10000"))
    assert drawdown == {"amount": "5000", "percent": "0.25", "start": "2024-09-02T00:00:00+00:00", "trough": "2024-09-03T00:00:00+00:00", "basis": "NATIVE_CASH_ACCOUNT_SERIES"}


def test_lazy_four_stream_merge_processes_every_minute_once_in_bounded_weeks(tmp_path) -> None:
    start, end = write_streaming_fixture(tmp_path)
    bundles = list(iter_minute_bundles(tmp_path, start, end, batch_rows=37))
    assert len(bundles) == 2 * 24 * 60
    assert [item.open_time_ms for item in bundles] == list(range(start, end, MINUTE_MS))
    weeks = list(iter_weekly_minute_batches(iter(bundles), max_minutes=100))
    assert [len(week) for week in weeks] == [100] * 28 + [80]


def test_minute_cursor_rejects_duplicate_and_boundary_loss(tmp_path) -> None:
    start, end = write_streaming_fixture(tmp_path)
    path = tmp_path / "normalized" / "bybit-BTCUSDT-execution-1m.parquet"
    rows = pq.read_table(path).to_pylist()
    rows[10]["open_time_ms"] = rows[9]["open_time_ms"]
    pq.write_table(pa.Table.from_pylist(rows), path)
    with pytest.raises(ValueError, match="MINUTE_DUPLICATE"):
        list(iter_minute_bundles(tmp_path, start, end, batch_rows=11, require_exact_source_rows=True))
    pq.write_table(pa.Table.from_pylist(rows[:-1]), path)
    with pytest.raises(ValueError, match="MINUTE_ROW_COUNT"):
        list(iter_minute_bundles(tmp_path, start, end, require_exact_source_rows=True))


def test_streamed_native_smoke_matches_one_shot_and_keeps_callbacks_subscribed(tmp_path, monkeypatch) -> None:
    start, end = write_streaming_fixture(tmp_path)
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
    from coinmaster.venues.marks import VenueMark
    from coinmaster.venues.signals import DailySignalBar

    seen: list[tuple[str, int]] = []
    starts = 0
    original_start, original_data, original_quote = WaveOverlayStrategy.on_start, WaveOverlayStrategy.on_data, WaveOverlayStrategy.on_quote_tick

    def capture_start(self):
        nonlocal starts
        starts += 1
        return original_start(self)

    def capture_data(self, data):
        value = getattr(data, "data", data)
        if isinstance(value, (VenueMark, DailySignalBar)):
            seen.append(("mark" if isinstance(value, VenueMark) else "signal", value.ts_event))
        return original_data(self, data)

    def capture_quote(self, tick):
        seen.append(("quote", tick.ts_event))
        return original_quote(self, tick)

    monkeypatch.setattr(WaveOverlayStrategy, "on_start", capture_start)
    monkeypatch.setattr(WaveOverlayStrategy, "on_data", capture_data)
    monkeypatch.setattr(WaveOverlayStrategy, "on_quote_tick", capture_quote)
    common = {"warmup_start_ms": 0, "trading_start_ms": start, "trading_end_ms": end, "cursor_batch_rows": 60, "artifact_label": "streaming-smoke"}
    one_shot = run_native_diagnostic(tmp_path, weekly_batch_minutes=2 * 24 * 60, **common)
    streamed = run_native_diagnostic(tmp_path, weekly_batch_minutes=24 * 60, **{**common, "artifact_label": "streaming-smoke-two-batches"})
    assert starts == 2  # One strategy start per engine, never per clear_data batch.
    assert one_shot["fills"] == streamed["fills"]
    assert one_shot["terminal_total"] == streamed["terminal_total"]
    assert one_shot["terminal_open_positions"] == streamed["terminal_open_positions"]
    assert one_shot["cash_account_series"] == streamed["cash_account_series"]
    assert one_shot["interval_cash_account_series"] == streamed["interval_cash_account_series"]
    assert one_shot["streaming"]["batch_count"] == 1
    assert streamed["streaming"]["batch_count"] == 2
    assert streamed["streaming"]["max_batch_minutes"] == 24 * 60
    assert streamed["streaming"]["processed_rows_per_source"] == 2 * 24 * 60
    assert streamed["streaming"]["max_batch_events"] <= 4 * 24 * 60 + 2
    assert streamed["episodes"] == "UNKNOWN_NATIVE_DOMAIN_EPISODE_AUDIT_NOT_EXPORTED"
    assert streamed["realized_unrealized"] == "UNKNOWN_NATIVE_ACCOUNT_REPORT_ONLY"
    assert streamed["transfers"] == "0" and streamed["liquidation_value"] == "0"
    assert set(streamed["funding"]) == {"count", "by_instrument_count", "signed_amount"}
    for timestamp in ((start + DAY_MS) * 1_000_000, end * 1_000_000):
        ordered = [kind for kind, event_time in seen if event_time == timestamp]
        assert ordered == ["mark", "mark", "signal", "signal", "quote", "quote"] * 2
    delayed = run_native_diagnostic(tmp_path, weekly_batch_minutes=24 * 60, **{**common, "artifact_label": "streaming-smoke-two-minute", "execution_policy": ExecutionPolicy(execution_delay_minutes=2)})
    assert delayed["policy"]["execution_delay_minutes"] == 2
    assert delayed["streaming"]["processed_rows_per_source"] == (end - start) // MINUTE_MS
