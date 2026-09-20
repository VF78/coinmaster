import json
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from coinmaster.ledger.journal import NativeEventJournal
from coinmaster.research.native_baseline import DAY_MS, MINUTE_MS, ExecutionPolicy, FixedBaseFeePolicy, _funding_attempt_path, _publish_clean_funding_attempt, _quarantine_funding_attempt, assert_report_boundaries, coverage_blockers, iter_minute_bundles, iter_weekly_minute_batches, monthly_returns, native_fee_attribution, run_native_diagnostic, run_sparse_native_diagnostic_legacy, standard_drawdown


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
    assert "0.00020" in policy.fees and "0.00055" in policy.fees
    assert policy.fee_historical_applicability == "UNKNOWN" and policy.nonmatching_daily_signals


def test_fixed_base_fee_policy_uses_owner_schedule_and_blocks_hyperliquid_history() -> None:
    assert FixedBaseFeePolicy().rates() == (Decimal("0.00020"), Decimal("0.00055"))
    assert FixedBaseFeePolicy(venue="hyperliquid").rates() == (Decimal("0.00015"), Decimal("0.00045"))
    assert len(FixedBaseFeePolicy().hash) == 64


def test_native_fee_attribution_reconciles_native_liquidity_without_inference() -> None:
    result = native_fee_attribution([
        {"native_liquidity_side": "MAKER", "notional": "100", "commission": "0.020"},
        {"native_liquidity_side": "TAKER", "notional": "200", "commission": "0.110"},
        {"native_liquidity_side": "NO_LIQUIDITY_SIDE", "notional": "50", "commission": "0"},
    ], Decimal("0.130"))
    assert result["maker"] == {"count": 1, "notional": "100", "fees": "0.020"}
    assert result["taker"] == {"count": 1, "notional": "200", "fees": "0.110"}
    assert result["unknown"]["count"] == 1 and result["reconciled"] is True


def test_daily_bar_matching_is_rejected_before_any_data_or_engine_is_loaded(tmp_path) -> None:
    with pytest.raises(ValueError, match="LEGACY_DAILY_BAR_MATCHING_DISABLED"):
        run_native_diagnostic(tmp_path, execution_policy=ExecutionPolicy(nonmatching_daily_signals=False))


def test_from_genesis_funding_attempt_never_reuses_canonical_or_interrupted_rows(tmp_path) -> None:
    """Only a genuine same-engine restart may use durable funding IDs."""
    canonical = tmp_path / "same-label-funding.sqlite"

    def record(path, event_id: str) -> NativeEventJournal:
        journal = NativeEventJournal(str(path))
        assert journal.record_funding(event_id, "BTCUSDT-PERP.P1SIM", 1, Decimal("0.01"), Decimal("100"), Decimal("9999"))
        return journal

    # This is stale evidence from a previous from-genesis engine, never input.
    stale = record(canonical, "stale")
    stale.close()
    first_attempt = _funding_attempt_path(canonical)
    first = record(first_attempt, "current-run")
    _publish_clean_funding_attempt(first, first_attempt, canonical)
    current = NativeEventJournal(str(canonical))
    try:
        assert [row[0] for row in current.funding_audit()] == ["current-run"]
    finally:
        current.close()
    assert list(tmp_path.glob("same-label-funding.sqlite.superseded-*"))

    # An interrupted attempt is retained, then a new from-genesis attempt
    # starts with an empty journal and reports its own funding count only.
    interrupted_path = _funding_attempt_path(canonical)
    interrupted = record(interrupted_path, "interrupted")
    interrupted.close()
    _quarantine_funding_attempt(interrupted_path)
    resumed_path = _funding_attempt_path(canonical)
    resumed = record(resumed_path, "resumed-current-run")
    _publish_clean_funding_attempt(resumed, resumed_path, canonical)
    current = NativeEventJournal(str(canonical))
    try:
        assert [row[0] for row in current.funding_audit()] == ["resumed-current-run"]
    finally:
        current.close()
    assert list(tmp_path.glob("*.attempt-*.aborted-*"))


def test_preexisting_canonical_funding_journal_cannot_change_from_genesis_economics(tmp_path, monkeypatch) -> None:
    """The native diagnostic itself, not just its helper, starts from empty IDs."""
    start, end = write_streaming_fixture(tmp_path)
    from coinmaster.research import native_baseline
    from coinmaster.research.native_fixture import BTC_PERP, FundingInstruction

    baseline = run_native_diagnostic(tmp_path, trading_start_ms=start, trading_end_ms=end, warmup_start_ms=0, artifact_label="no-funding")
    canonical = tmp_path / "runs" / "from-genesis-funding.sqlite"
    stale = NativeEventJournal(str(canonical))
    stale.record_funding("prior-engine", str(BTC_PERP.id), start * 1_000_000, Decimal("0.01"), Decimal("100"), Decimal("9999"))
    stale.close()
    monkeypatch.setattr(native_baseline, "funding_with_prior_minute_marks", lambda *_args: (FundingInstruction("prior-engine", BTC_PERP.id, Decimal("0.01"), start * 1_000_000, Decimal("100"), "synthetic_mid", True),))
    clean = run_native_diagnostic(tmp_path, include_funding=True, trading_start_ms=start, trading_end_ms=end, warmup_start_ms=0, artifact_label="from-genesis")
    assert clean["terminal_total"] == baseline["terminal_total"]
    assert clean["funding"]["count"] == 0  # no open position; stale row was not reported.
    published = NativeEventJournal(str(canonical))
    try:
        assert published.funding_audit() == []
    finally:
        published.close()


def test_sparse_legacy_diagnostic_is_unreachable() -> None:
    with pytest.raises(ValueError, match="NONCANONICAL_SPARSE_DIAGNOSTIC_DISABLED"):
        run_sparse_native_diagnostic_legacy(Path("ignored"))


def test_monthly_returns_carry_forward_empty_months() -> None:
    rows = [{"timestamp": "2024-09-30T00:00:00+00:00", "total": "11000"}, {"timestamp": "2024-11-01T00:00:00+00:00", "total": "12100"}]
    assert monthly_returns(rows) == [{"month": "2024-09", "total": "11000", "return": "0.1"}, {"month": "2024-10", "total": "11000", "return": "0"}, {"month": "2024-11", "total": "12100", "return": "0.1"}]


def test_monthly_returns_preserves_native_insertion_order_for_equal_timestamps() -> None:
    rows = [
        {"timestamp": "2024-09-01T00:00:00+00:00", "total": "10000"},
        {"timestamp": "2024-10-29T02:24:00+00:00", "total": "12400"},
        {"timestamp": "2024-10-29T02:24:00+00:00", "total": "12350"},
    ]
    months = monthly_returns(rows)
    assert months[-1]["total"] == "12350"
    report = {"run_interval": {"start": "2024-09-01T00:00:00+00:00", "end_exclusive": "2024-11-01T00:00:00+00:00", "initial_active_seed": "10000"}, "summary": {"monthly_returns": months, "interval_cash_terminal_total": "12350", "drawdown_start": "2024-09-01T00:00:00+00:00", "drawdown_trough": "2024-10-29T02:24:00+00:00"}, "liquidation_count": 0, "liquidation_lockout": False, "fill_timestamps_ns": [], "post_boundary_settlement": {"convention": "TERMINAL_FILLS_AT_END_EXCLUSIVE_REPORTED_SEPARATELY_EXCLUDED_FROM_INTERVAL_RETURNS", "fill_count": 0}}
    assert_report_boundaries(report)


def test_report_boundaries_require_terminal_reconciliation_and_trading_dd() -> None:
    total = Decimal("12000")
    months = [{"month": "2024-09", "total": "11000", "return": "0.1"}]
    months.extend({"month": f"2024-{month:02d}", "total": "11000", "return": "0"} for month in range(10, 13))
    months.extend({"month": f"2025-{month:02d}", "total": "11000", "return": "0"} for month in range(1, 13))
    months.extend({"month": f"2026-{month:02d}", "total": "11000", "return": "0"} for month in range(1, 8))
    months.append({"month": "2026-08", "total": "12000", "return": str((total / Decimal("11000")) - 1)})
    report = {"terminal_total": "12000", "run_interval": {"start": "2024-09-01T00:00:00+00:00", "end_exclusive": "2026-09-01T00:00:00+00:00", "initial_active_seed": "10000"}, "summary": {"monthly_returns": months, "interval_cash_terminal_total": "12000", "drawdown_start": "2024-09-01T00:00:00+00:00", "drawdown_trough": "2026-08-31T23:59:00+00:00"}, "fill_timestamps_ns": [1788220800000000000], "post_boundary_settlement": {"convention": "TERMINAL_FILLS_AT_END_EXCLUSIVE_REPORTED_SEPARATELY_EXCLUDED_FROM_INTERVAL_RETURNS", "fill_count": 1}}
    assert_report_boundaries(report)


def test_report_boundaries_accept_authoritative_early_liquidation_lockout_months() -> None:
    report = {"run_interval": {"start": "2024-09-01T00:00:00+00:00", "end_exclusive": "2025-09-01T00:00:00+00:00", "initial_active_seed": "10000"}, "summary": {"monthly_returns": [{"month": "2024-09", "total": "5000", "return": "-0.5"}], "interval_cash_terminal_total": "5000", "drawdown_start": "2024-09-01T00:00:00+00:00", "drawdown_trough": "2024-09-30T00:00:00+00:00"}, "liquidation_count": 1, "liquidation_lockout": True, "fill_timestamps_ns": [], "post_boundary_settlement": {"convention": "TERMINAL_FILLS_AT_END_EXCLUSIVE_REPORTED_SEPARATELY_EXCLUDED_FROM_INTERVAL_RETURNS", "fill_count": 0}}
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
