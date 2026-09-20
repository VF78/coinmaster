"""Fail-closed native baseline entrypoint.

This command intentionally refuses to calculate or label a result until all
four required 1-minute execution/mark streams are complete and gap-free.  It
is the only accepted launch point for the future native baseline lifecycle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import resource
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterator
from uuid import uuid4
from datetime import datetime, timedelta, timezone


DAY_MS = 86_400_000
MINUTE_MS = 60_000
WEEK_MINUTES = 7 * 24 * 60
WARMUP_START_MS = 1_662_076_800_000  # 2022-09-02T00:00:00Z
TRADING_START_MS = 1_725_148_800_000  # 2024-09-01T00:00:00Z
TRADING_END_MS = 1_788_220_800_000  # 2026-09-01T00:00:00Z, exclusive

# Immutable §2 v0 envelope. Candidate is only the domain subset; this object
# records the account/execution/tier assumptions that materially affect a run.
BASELINE_CONFIG = {
    "strategy_id": "btc_sol_wave_overlay_v1", "mode": "paper", "live_enabled": False,
    "venue": "bybit", "initial_total_usdt": "10000", "initial_active_fraction": "1.0",
    "signal_timeframe": "1D", "include_zero_waves": True, "sol_direction": "opposite_btc",
    "sol_entry_eligibility": "persistent_after_btc_level", "freeze_sigma_on_first_sol_fill": True,
    "sol_z_stop": None, "btc_close_stop_fraction": None, "portfolio_loss_limit_fraction": None,
    "future_sol_margin_fraction": "0", "insufficient_margin": "reject",
    "reserve_transfer_fraction": "0", "reserve_trigger_multiple": "4", "restart_target": "initial_active_seed",
    "post_liquidation": "restart_from_reserve_else_pause", "account": "SIM_MARGIN_USDT_10000",
    "tier_assumption": "CURRENT_PUBLIC_BYBIT_40X_BTC_20X_SOL_HISTORICAL_APPLICABILITY_UNKNOWN",
}


@dataclass(frozen=True)
class ExecutionPolicy:
    """Versioned matching assumptions; unknown venue facts stay explicit."""
    version: str = "bybit-1m-close-v1"
    execution_source: str = "BYBIT_GAP_FREE_1M_EXECUTION_CLOSE"
    mark_source: str = "BYBIT_GAP_FREE_1M_MARK_CLOSE"
    latency: str = "next_available_1m_close_after_daily_decision"
    fees: str = "NATIVE_FIXTURE_MAKER_TAKER_0.001_PER_SIDE"
    fee_historical_applicability: str = "UNKNOWN"
    spread_slippage_liquidity: str = "UNKNOWN_NO_L2_OR_TRADE_TAPE"
    liquidation: str = "MARK_FIRST_UNVALIDATED_NO_LIQUIDATION_MODEL"
    execution_delay_minutes: int = 1
    symmetric_adverse_spread_bps: str = "0"
    fee_multiplier: str = "1"
    nonmatching_daily_signals: bool = True

    @property
    def hash(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class MinuteBundle:
    """One causally aligned BTC/SOL execution-and-mark minute."""

    open_time_ms: int
    btc_execution: dict
    sol_execution: dict
    btc_mark: dict
    sol_mark: dict


class ParquetMinuteCursor:
    """Bounded-memory, strict cursor over one normalized minute Parquet."""

    def __init__(self, path: Path, start_ms: int, end_ms: int, batch_rows: int = WEEK_MINUTES) -> None:
        import pyarrow.parquet as pq

        if batch_rows <= 0:
            raise ValueError("INVALID_CURSOR_BATCH_ROWS")
        self.path, self.start_ms, self.end_ms, self.batch_rows = path, start_ms, end_ms, batch_rows
        self.expected_rows = (end_ms - start_ms) // MINUTE_MS
        self._file = pq.ParquetFile(path)
        self.source_rows = self._file.metadata.num_rows
        self._batches = self._file.iter_batches(batch_size=batch_rows)
        self._columns: dict[str, list] = {}
        self._index = 0
        self.rows_seen = 0
        self.peak_buffer_rows = 0

    def __iter__(self) -> "ParquetMinuteCursor":
        return self

    def __next__(self) -> dict:
        while True:
            if self._index >= len(self._columns.get("open_time_ms", ())):
                try:
                    batch = next(self._batches)
                except StopIteration:
                    if self.rows_seen != self.expected_rows:
                        raise ValueError(f"MINUTE_BOUNDARY_LOSS:{self.path.name}:{self.rows_seen}:{self.expected_rows}")
                    raise
                self._columns = batch.to_pydict()
                self._index = 0
                self.peak_buffer_rows = max(self.peak_buffer_rows, len(self._columns["open_time_ms"]))
            row = {key: values[self._index] for key, values in self._columns.items()}
            self._index += 1
            actual = int(row["open_time_ms"])
            if actual < self.start_ms:
                continue
            if actual >= self.end_ms:
                if self.rows_seen != self.expected_rows:
                    raise ValueError(f"MINUTE_BOUNDARY_LOSS:{self.path.name}:{self.rows_seen}:{self.expected_rows}")
                raise StopIteration
            expected = self.start_ms + self.rows_seen * MINUTE_MS
            if actual != expected:
                kind = "DUPLICATE" if actual < expected else "GAP_OR_BOUNDARY_LOSS"
                raise ValueError(f"MINUTE_{kind}:{self.path.name}:{actual}:{expected}")
            self.rows_seen += 1
            return row


def iter_minute_bundles(data_root: Path, start_ms: int, end_ms: int, batch_rows: int = WEEK_MINUTES, require_exact_source_rows: bool = False) -> Iterator[MinuteBundle]:
    """Lazily merge all canonical 1m sources and reject any misalignment."""
    if start_ms >= end_ms or start_ms % MINUTE_MS or end_ms % MINUTE_MS:
        raise ValueError("INVALID_MINUTE_STREAM_INTERVAL")
    normalized = data_root / "normalized"
    paths = (
        normalized / "bybit-BTCUSDT-execution-1m.parquet",
        normalized / "bybit-SOLUSDT-execution-1m.parquet",
        normalized / "bybit-BTCUSDT-mark-1m.parquet",
        normalized / "bybit-SOLUSDT-mark-1m.parquet",
    )
    cursors = tuple(ParquetMinuteCursor(path, start_ms, end_ms, batch_rows) for path in paths)
    if require_exact_source_rows and any(cursor.source_rows != cursor.expected_rows for cursor in cursors):
        actual = ",".join(f"{cursor.path.name}:{cursor.source_rows}" for cursor in cursors)
        raise ValueError(f"MINUTE_ROW_COUNT:{actual}:{cursors[0].expected_rows}")
    while True:
        rows = []
        try:
            for cursor in cursors:
                rows.append(next(cursor))
        except StopIteration:
            break
        else:
            timestamps = {int(row["open_time_ms"]) for row in rows}
            if len(timestamps) != 1:
                raise ValueError(f"MINUTE_STREAM_MISALIGNED:{sorted(timestamps)}")
            yield MinuteBundle(next(iter(timestamps)), rows[0], rows[1], rows[2], rows[3])
    # Each cursor validates its own exact count on exhaustion.  A cursor
    # ending before the others is therefore an explicit boundary failure.
    if any(cursor.rows_seen != cursor.expected_rows for cursor in cursors):
        raise ValueError("MINUTE_SOURCE_EARLY_END")


def iter_weekly_minute_batches(bundles: Iterator[MinuteBundle], max_minutes: int = WEEK_MINUTES) -> Iterator[list[MinuteBundle]]:
    """Yield deterministic bounded batches without retaining prior weeks."""
    if max_minutes <= 0 or max_minutes > WEEK_MINUTES:
        raise ValueError("INVALID_WEEKLY_BATCH_SIZE")
    batch: list[MinuteBundle] = []
    for bundle in bundles:
        batch.append(bundle)
        if len(batch) == max_minutes:
            yield batch
            batch = []
    if batch:
        yield batch


def _peak_rss_bytes() -> int:
    # macOS reports bytes while Linux reports KiB.
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if platform.system() == "Darwin" else peak * 1024)


def monthly_returns(equity: list[dict[str, str]], initial: Decimal = Decimal("10000")) -> list[dict[str, str]]:
    """Calendar months with carry-forward TOTAL, including silent months."""
    values = sorted((datetime.fromisoformat(row["timestamp"]).replace(tzinfo=timezone.utc), Decimal(row["total"])) for row in equity)
    if not values: return []
    result, cursor, prior, index = [], values[0][0].replace(day=1), initial, 0
    end = values[-1][0].replace(day=1)
    while cursor <= end:
        while index < len(values) and values[index][0].year == cursor.year and values[index][0].month == cursor.month:
            prior = values[index][1]; index += 1
        base = initial if not result else Decimal(result[-1]["total"])
        result.append({"month": cursor.strftime("%Y-%m"), "total": str(prior), "return": str((prior / base) - 1)})
        cursor = cursor.replace(year=cursor.year + (cursor.month == 12), month=1 if cursor.month == 12 else cursor.month + 1)
    return result


def standard_drawdown(cash_series: list[dict[str, str]], initial: Decimal) -> dict[str, str]:
    """Peak-to-trough drawdown on native cash checkpoints only.

    The account report is a cash series; it must not be silently mixed with
    mark-to-market values.  Percentage is always divided by the preceding
    peak, rather than by the initial deposit.
    """
    if not cash_series:
        raise ValueError("EMPTY_CASH_ACCOUNT_SERIES")
    peak = Decimal(cash_series[0]["total"])
    peak_at = trough_at = cash_series[0]["timestamp"]
    amount = Decimal("0")
    percent = Decimal("0")
    for point in cash_series:
        total = Decimal(point["total"])
        if total > peak:
            peak, peak_at = total, point["timestamp"]
        current_amount = peak - total
        current_percent = current_amount / peak if peak else Decimal("0")
        if current_amount > amount:
            amount, percent, trough_at = current_amount, current_percent, point["timestamp"]
    return {
        "amount": str(amount),
        "percent": str(percent),
        "start": peak_at,
        "trough": trough_at,
        "basis": "NATIVE_CASH_ACCOUNT_SERIES",
    }


def _fill_timestamp_ns(value) -> int:
    """Normalize a native report timestamp without changing its event time."""
    if hasattr(value, "value"):
        return int(value.value)
    if isinstance(value, int):
        return value
    timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return int(timestamp.timestamp() * 1_000_000_000)


def _reporting_checkpoints(start: datetime, end: datetime) -> tuple[int, ...]:
    """True UTC month boundaries; the last one is the post-boundary mark."""
    cursor = start.replace(day=1)
    result: list[int] = []
    while cursor < end:
        cursor = cursor.replace(year=cursor.year + (cursor.month == 12), month=1 if cursor.month == 12 else cursor.month + 1)
        result.append(int(cursor.timestamp() * 1_000_000_000))
    return tuple(result)


def assert_report_boundaries(report: dict) -> None:
    """Reject report shapes that cannot reconcile to their declared interval."""
    summary = report["summary"]
    months = summary["monthly_returns"]
    start = datetime.fromisoformat(report["run_interval"]["start"])
    end = datetime.fromisoformat(report["run_interval"]["end_exclusive"])
    expected_months = max(1, (end.year - start.year) * 12 + end.month - start.month)
    if len(months) != expected_months:
        raise ValueError(f"MONTHLY_ROW_COUNT:{len(months)}")
    interval_terminal = Decimal(summary["interval_cash_terminal_total"])
    if Decimal(months[-1]["total"]) != interval_terminal:
        raise ValueError("MONTHLY_INTERVAL_CASH_MISMATCH")
    compounded = Decimal("1")
    for month in months:
        compounded *= Decimal("1") + Decimal(month["return"])
    ratio = interval_terminal / Decimal(report["run_interval"]["initial_active_seed"])
    if abs(compounded - ratio) > Decimal("1e-24"):
        raise ValueError("MONTHLY_COMPOUNDING_MISMATCH")
    for timestamp in (summary["drawdown_start"], summary["drawdown_trough"]):
        point = datetime.fromisoformat(timestamp)
        if not start <= point < end:
            raise ValueError(f"DRAWDOWN_OUTSIDE_TRADING_INTERVAL:{timestamp}")
    settlement = report["post_boundary_settlement"]
    if settlement["convention"] != "TERMINAL_FILLS_AT_END_EXCLUSIVE_REPORTED_SEPARATELY_EXCLUDED_FROM_INTERVAL_RETURNS":
        raise ValueError("UNKNOWN_TERMINAL_SETTLEMENT_CONVENTION")
    boundary_ns = int(end.timestamp() * 1_000_000_000)
    fills = report["fill_timestamps_ns"]
    if any(timestamp < int(start.timestamp() * 1_000_000_000) or timestamp > boundary_ns for timestamp in fills):
        raise ValueError("FILL_OUTSIDE_DECLARED_OR_SETTLEMENT_BOUNDARY")
    at_boundary = [timestamp for timestamp in fills if timestamp == boundary_ns]
    if len(at_boundary) != settlement["fill_count"]:
        raise ValueError("POST_BOUNDARY_FILL_COUNT_MISMATCH")
    if any(timestamp == boundary_ns for timestamp in fills) != bool(settlement["fill_count"]):
        raise ValueError("POST_BOUNDARY_FILL_CONVENTION_MISMATCH")


def save_native_artifact(frame, path: Path) -> dict[str, str | int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=True)
    body = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(body).hexdigest(), "rows": len(frame)}


def funding_with_prior_minute_marks(
    data_root: Path,
    start_settlement_ms: int | None = None,
    end_settlement_ms: int | None = None,
):
    """Return stable native funding events from actual rows or fail closed.

    The final closed 1m mark before settlement is causal but not yet proven to
    equal the venue's exact settlement mark; callers must retain that label.
    """
    import pyarrow.parquet as pq
    from decimal import Decimal
    from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP, FundingInstruction
    events = []
    for symbol, instrument in (("BTCUSDT", BTC_PERP), ("SOLUSDT", SOL_PERP)):
        funding_rows = pq.read_table(data_root / "normalized" / f"bybit-{symbol}-funding.parquet").to_pylist()
        relevant = []
        for row in funding_rows:
            settlement = int(row["funding_time_ms"])
            # Warmup is feature-only. At an exact range boundary, the prior
            # causal minute is outside the captured [start, end) marks.
            if start_settlement_ms is not None and settlement <= start_settlement_ms:
                continue
            if end_settlement_ms is not None and settlement >= end_settlement_ms:
                continue
            relevant.append((settlement, row))
        mark_path = data_root / "normalized" / f"bybit-{symbol}-mark-1m.parquet"
        # The canonical full-range stream has exactly one row per minute.
        # Scan it lazily and retain only settlement-adjacent marks; compact
        # unit fixtures retain the old partial lookup behavior.
        lazy_complete = start_settlement_ms is not None and end_settlement_ms is not None and pq.ParquetFile(mark_path).metadata.num_rows == (end_settlement_ms - start_settlement_ms) // MINUTE_MS
        if lazy_complete:
            wanted = {settlement - MINUTE_MS: row for settlement, row in relevant}
            marks = {}
            for mark_row in ParquetMinuteCursor(mark_path, start_settlement_ms, end_settlement_ms):
                timestamp = int(mark_row["open_time_ms"])
                if timestamp in wanted:
                    marks[timestamp] = mark_row["close"]
        else:
            marks = {row["open_time_ms"]: row["close"] for row in pq.read_table(mark_path).to_pylist()}
        for settlement, row in relevant:
            mark = marks.get(settlement - MINUTE_MS)
            if mark is None:
                raise ValueError(f"MISSING_CAUSAL_1M_MARK:{symbol}:{settlement}")
            events.append(FundingInstruction(f"bybit:{symbol}:{settlement}:{row['funding_rate']}", instrument.id, Decimal(str(row["funding_rate"])), settlement * 1_000_000, Decimal(str(mark)), "venue_mark_prior_minute"))
    return tuple(events)


def run_sparse_native_diagnostic_legacy(
    data_root: Path,
    include_funding: bool = False,
    candidate=None,
    trading_start_ms: int = TRADING_START_MS,
    trading_end_ms: int = TRADING_END_MS,
    initial_active_seed: Decimal = Decimal("10000"),
    execution_policy: ExecutionPolicy | None = None,
    artifact_label: str = "native-diagnostic",
) -> dict:
    """Rejected historical sparse path retained only as an audit reference.

    It cannot be invoked by the canonical diagnostic API or optimizer because
    it drops almost every minute before running the engine.
    """
    raise ValueError("NONCANONICAL_SPARSE_DIAGNOSTIC_DISABLED")
    import pyarrow.parquet as pq
    from decimal import Decimal
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.model.data import BarSpecification, BarType
    from nautilus_trader.model.enums import AccountType, AggregationSource, BarAggregation, OmsType, PriceType
    from nautilus_trader.model.objects import Money
    from coinmaster.research.native_fixture import BTC_PERP, SIM, SOL_PERP, BybitTierMarginModule, MarkPriceUpdate, PerpetualFundingModule, quote
    from coinmaster.ledger.journal import NativeEventJournal
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig
    from coinmaster.domain.wave_overlay import Candidate
    from coinmaster.venues.marks import venue_mark, venue_mark_data_type
    from coinmaster.venues.signals import daily_signal, daily_signal_data_type

    candidate = candidate or Candidate()
    policy = execution_policy or ExecutionPolicy()
    if trading_end_ms <= trading_start_ms or trading_start_ms - WARMUP_START_MS < 730 * DAY_MS:
        raise ValueError("INVALID_TRADING_INTERVAL_OR_INSUFFICIENT_730D_WARMUP")
    if policy.execution_delay_minutes < 1:
        raise ValueError("INVALID_EXECUTION_DELAY")
    if Decimal(policy.symmetric_adverse_spread_bps) < 0 or Decimal(policy.fee_multiplier) <= 0:
        raise ValueError("INVALID_EXECUTION_STRESS")
    if not policy.nonmatching_daily_signals:
        raise ValueError("LEGACY_DAILY_BAR_MATCHING_DISABLED")
    start_at = datetime.fromtimestamp(trading_start_ms / 1000, tz=timezone.utc)
    end_at = datetime.fromtimestamp(trading_end_ms / 1000, tz=timezone.utc)
    start_iso, end_iso = start_at.isoformat(), end_at.isoformat()
    def rows(symbol: str):
        return {
            row["open_time_ms"]: row
            for row in pq.read_table(data_root / "normalized" / f"bybit-{symbol}-daily.parquet").to_pylist()
            if WARMUP_START_MS <= int(row["open_time_ms"]) < trading_end_ms
        }
    btc, sol = rows("BTCUSDT"), rows("SOLUSDT")
    # The full 1m streams are hash/gap checked by the manifest. Only the first
    # closed executable minute after each daily decision is loaded into this
    # one native lifecycle; no synthetic daily-close quote is manufactured.
    decision_days = sorted(set(btc) & set(sol))
    execution_offset_ms = (policy.execution_delay_minutes - 1) * 60_000
    wanted_minutes = sorted({minute for timestamp in decision_days if timestamp >= trading_start_ms for minute in (timestamp + 86_400_000 - 60_000, timestamp + 86_400_000 + execution_offset_ms) if minute < trading_end_ms})
    def minute_closes(symbol: str, stream: str) -> dict[int, dict]:
        table = pq.read_table(data_root / "normalized" / f"bybit-{symbol}-{stream}-1m.parquet", filters=[("open_time_ms", "in", wanted_minutes)])
        return {int(row["open_time_ms"]): row for row in table.to_pylist()}
    btc_execution, sol_execution = minute_closes("BTCUSDT", "execution"), minute_closes("SOLUSDT", "execution")
    btc_marks, sol_marks = minute_closes("BTCUSDT", "mark"), minute_closes("SOLUSDT", "mark")
    def kind(instrument, price_type): return BarType(instrument, BarSpecification(1, BarAggregation.DAY, price_type), AggregationSource.EXTERNAL)
    btc_last, sol_last = kind(BTC_PERP.id, PriceType.LAST), kind(SOL_PERP.id, PriceType.LAST)
    events = funding_with_prior_minute_marks(data_root, trading_start_ms, trading_end_ms) if include_funding else ()
    # Each new BacktestEngine starts with a new native account. Its durable
    # funding journal must therefore be scoped to this run: sharing a prior
    # journal would correctly deduplicate IDs but incorrectly omit funding
    # from a fresh account.
    journal_path = data_root / "runs" / f"native-diagnostic-funding-{uuid4().hex}.sqlite"
    journal = NativeEventJournal(str(journal_path)) if events else None
    # Current public tiers and their 40x/20x selected leverage are an
    # explicitly non-historical assumption.  They are used only to make the
    # diagnostic fail closed; no historical fee/tier applicability is claimed.
    mark_updates = tuple(
        MarkPriceUpdate(instrument.id, Decimal(str(row["mark_close"])), (timestamp + 86_400_000) * 1_000_000)
        for symbol, instrument, table in (("BTCUSDT", BTC_PERP, btc), ("SOLUSDT", SOL_PERP, sol))
        for timestamp, row in table.items()
        if row.get("mark_close") is not None
    )
    selected_leverage = ((BTC_PERP.id, Decimal("40")), (SOL_PERP.id, Decimal("20")))
    max_mark_age_ns = 86_400_000_000_000  # daily diagnostic mark cadence.
    modules = [BybitTierMarginModule(mark_updates, selected_leverage, max_mark_age_ns)]
    if journal:
        modules.insert(0, PerpetualFundingModule(events, journal))
    fee = Decimal("0.001") * Decimal(policy.fee_multiplier)
    if fee == Decimal("0.001"):
        btc_instrument, sol_instrument = BTC_PERP, SOL_PERP
    else:
        from nautilus_trader.model.currencies import BTC, SOL
        from coinmaster.research.native_fixture import perpetual
        btc_instrument = perpetual("BTCUSDT", BTC, "0.1", "0.001", "0.025", fee, fee)
        sol_instrument = perpetual("SOLUSDT", SOL, "0.01", "0.1", "0.05", fee, fee)
        selected_leverage = ((btc_instrument.id, Decimal("40")), (sol_instrument.id, Decimal("20")))
        mark_updates = tuple(
            MarkPriceUpdate(instrument.id, Decimal(str(row["mark_close"])), (timestamp + 86_400_000) * 1_000_000)
            for symbol, instrument, table in (("BTCUSDT", btc_instrument, btc), ("SOLUSDT", sol_instrument, sol))
            for timestamp, row in table.items() if row.get("mark_close") is not None
        )
        modules = [BybitTierMarginModule(mark_updates, selected_leverage, max_mark_age_ns)]
        if journal:
            modules.insert(0, PerpetualFundingModule(events, journal))
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(initial_active_seed, btc_instrument.quote_currency)], base_currency=btc_instrument.quote_currency, default_leverage=Decimal("1"), modules=modules)
    engine.add_instrument(btc_instrument); engine.add_instrument(sol_instrument)
    from nautilus_trader.model.identifiers import ClientId
    engine.add_strategy(WaveOverlayStrategy(WaveOverlayStrategyConfig(btc_id=btc_instrument.id, sol_id=sol_instrument.id, btc_bar_type=btc_last, sol_bar_type=sol_last, btc_mark_data_type=venue_mark_data_type(btc_instrument.id), sol_mark_data_type=venue_mark_data_type(sol_instrument.id), mark_client_id=ClientId("BYBIT_MARK"), active_seed=initial_active_seed, tier_marks=mark_updates, tier_selected_leverage=selected_leverage, max_mark_age_ns=max_mark_age_ns, trading_start_open_ns=trading_start_ms * 1_000_000, terminal_close_at_ns=trading_end_ms * 1_000_000, candidate=candidate, btc_signal_data_type=daily_signal_data_type(btc_instrument.id), sol_signal_data_type=daily_signal_data_type(sol_instrument.id), signal_client_id=ClientId("BYBIT_SIGNAL"))))
    signal_data, quote_data, mark_data = [], [], []
    for timestamp in decision_days:
        b, s = btc[timestamp], sol[timestamp]
        event = (timestamp + 86_400_000) * 1_000_000 + 1
        mark_ts = (timestamp + 86_400_000) * 1_000_000
        if b.get("mark_close") is None or s.get("mark_close") is None:
            continue
        execution_minute, mark_minute = timestamp + 86_400_000 + execution_offset_ms, timestamp + 86_400_000 - 60_000
        be, se = btc_execution.get(execution_minute), sol_execution.get(execution_minute)
        bm, sm = btc_marks.get(mark_minute), sol_marks.get(mark_minute)
        if timestamp >= trading_start_ms and not all((bm, sm)):
            raise ValueError(f"MISSING_CAUSAL_1M_MARK:{mark_minute}")
        if timestamp >= trading_start_ms and timestamp + 86_400_000 + execution_offset_ms < trading_end_ms and not all((be, se)):
            raise ValueError(f"MISSING_CAUSAL_1M_EXECUTION:{execution_minute}")
        signal_data += [daily_signal(btc_instrument.id, Decimal(str(b["open"])), Decimal(str(b["high"])), Decimal(str(b["low"])), Decimal(str(b["close"])), (timestamp + 86_400_000) * 1_000_000), daily_signal(sol_instrument.id, Decimal(str(s["open"])), Decimal(str(s["high"])), Decimal(str(s["low"])), Decimal(str(s["close"])), (timestamp + 86_400_000) * 1_000_000)]
        if timestamp >= trading_start_ms and bm and sm:
            mark_data += [venue_mark(btc_instrument.id, Decimal(str(bm["close"])), (mark_minute + 60_000) * 1_000_000), venue_mark(sol_instrument.id, Decimal(str(sm["close"])), (mark_minute + 60_000) * 1_000_000)]
        if timestamp >= trading_start_ms and be and se:
            spread = Decimal(policy.symmetric_adverse_spread_bps) / Decimal("10000")
            def stressed_quote(instrument, close, precision):
                mid = Decimal(str(close))
                return quote(instrument.id, f"{float(mid * (1 - spread)):.{precision}f}", f"{float(mid * (1 + spread)):.{precision}f}", (execution_minute + 60_000) * 1_000_000)
            quote_data += [stressed_quote(btc_instrument, be["close"], 1), stressed_quote(sol_instrument, se["close"], 2)]
    engine.add_data(signal_data, client_id=ClientId("BYBIT_SIGNAL"), sort=False)
    engine.add_data(quote_data, sort=False)
    engine.add_data(mark_data, client_id=ClientId("BYBIT_MARK"), sort=False)
    engine.sort_data(); engine.run()
    try:
        report = engine.trader.generate_account_report(SIM)
        fills = engine.trader.generate_order_fills_report()
        orders = engine.trader.generate_orders_report()
        artifact_root = data_root / "runs"
        artifacts = {"fills": save_native_artifact(fills, artifact_root / f"{artifact_label}-fills.csv"), "orders": save_native_artifact(orders, artifact_root / f"{artifact_label}-orders.csv")}
        terminal_active = Decimal(str(report["total"].iloc[-1]))
        fee_column = next((column for column in ("commission", "fees") if column in fills.columns), None)
        if fee_column:
            fees = sum((Decimal(str(value)) for value in fills[fee_column]), Decimal("0"))
        elif "commissions" in fills.columns:
            fees = sum(
                (Decimal(str(commission).split()[0]) for row in fills["commissions"] for commission in row),
                Decimal("0"),
            )
        else:
            fees = Decimal("0")
        rejected = sum("REJECTED" in str(value) for value in orders.get("status", ()))
        data_hash = hashlib.sha256(json.dumps(json.loads((data_root / "bybit-1m" / "manifest.json").read_text()), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        full_config = {**BASELINE_CONFIG, "candidate": asdict(candidate), "execution_policy": asdict(policy), "run_interval": {"start": start_iso, "end_exclusive": end_iso, "initial_active_seed": str(initial_active_seed)}}
        config_hash = hashlib.sha256(json.dumps(full_config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        initial = initial_active_seed
        equity = [{"timestamp": str(index), "active": str(value), "reserve": "0", "total": str(value)} for index, value in report["total"].items()]
        trading_equity = [{"timestamp": start_iso, "active": str(initial), "reserve": "0", "total": str(initial)}] + [
            item for item in equity
            if start_at <= datetime.fromisoformat(item["timestamp"]).astimezone(timezone.utc) < end_at
        ]
        terminal_rows = [item for item in equity if item["timestamp"].startswith(end_iso[:10])]
        if terminal_rows:
            trading_equity.append({**terminal_rows[-1], "timestamp": (end_at - timedelta(microseconds=1)).isoformat()})
        totals = [Decimal(item["total"]) for item in trading_equity]
        peak, peak_at, max_dd, trough_at = initial, trading_equity[0]["timestamp"], Decimal("0"), trading_equity[0]["timestamp"]
        for item, total in zip(trading_equity, totals):
            if total > peak: peak, peak_at = total, item["timestamp"]
            if peak - total > max_dd: max_dd, trough_at = peak - total, item["timestamp"]
        audit = journal.funding_audit() if journal else []
        funding_by_instrument = {instrument: sum(1 for row in audit if row[1] == instrument) for instrument in sorted({row[1] for row in audit})}
        result = {"status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible": False, "interval": f"[{start_iso},{end_iso})", "run_interval": {"start": start_iso, "end_exclusive": end_iso, "initial_active_seed": str(initial), "feature_warmup_start": datetime.fromtimestamp(WARMUP_START_MS / 1000, tz=timezone.utc).isoformat(), "feature_warmup_days": (trading_start_ms - WARMUP_START_MS) // DAY_MS}, "warmup": f"[{datetime.fromtimestamp(WARMUP_START_MS / 1000, tz=timezone.utc).isoformat()},{start_iso}) feature-only", "config": full_config, "config_hash": config_hash, "data_hash": data_hash, "code_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "policy": asdict(policy), "policy_hash": policy.hash, "summary": {"roi": str((terminal_active / initial) - 1), "terminal_total": str(terminal_active), "max_drawdown_amount": str(max_dd), "max_drawdown_percent": str(max_dd / initial), "drawdown_start": peak_at, "drawdown_trough": trough_at, "drawdown_recovery": "UNKNOWN_NOT_RECOVERED_OR_NOT_EXPORTED", "monthly_returns": monthly_returns(trading_equity, initial)}, "equity": trading_equity, "fills": len(fills), "execution_artifacts": artifacts, "episodes": "UNKNOWN_NATIVE_DOMAIN_EPISODE_AUDIT_NOT_EXPORTED", "realized_unrealized": "UNKNOWN_NATIVE_ACCOUNT_REPORT_ONLY", "native_fees": str(fees), "modeled_slippage": policy.spread_slippage_liquidity, "native_order_rejections": rejected, "funding": {"count": len(audit), "by_instrument_count": funding_by_instrument, "signed_amount": "UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA"}, "funding_journal": str(journal_path) if journal else None, "transfers": "0", "liquidation_count": 0, "liquidation_value": "0", "terminal_active": str(terminal_active), "terminal_reserve": "0", "terminal_total": str(terminal_active), "terminal_open_positions": len(engine.cache.positions_open()), "limitations": ["1m close proxy has no BBO/L2/slippage/liquidity evidence", "Fixture fees are 0.001/side; historical applicability unknown", "Venue marks are CustomData and do not participate in matching", "Historical liquidation and funding settlement marks are unvalidated"]}
        assert_report_boundaries(result)
        return result
    finally:
        engine.dispose()
        if journal:
            journal.close()


def _load_daily_seed(data_root: Path, warmup_start_ms: int, trading_start_ms: int, trading_end_ms: int):
    """Load only small daily inputs and make warmup feature-only state."""
    import pyarrow.parquet as pq
    from coinmaster.domain.wave_overlay import DailyBar

    normalized = data_root / "normalized"
    tables = {
        symbol: {int(row["open_time_ms"]): row for row in pq.read_table(normalized / f"bybit-{symbol}-daily.parquet").to_pylist()}
        for symbol in ("BTCUSDT", "SOLUSDT")
    }
    required = range(warmup_start_ms, trading_end_ms, DAY_MS)
    if any(timestamp not in tables["BTCUSDT"] or timestamp not in tables["SOLUSDT"] for timestamp in required):
        raise ValueError("MISSING_DAILY_SIGNAL_OR_WARMUP_ROW")
    seed = tuple(
        DailyBar(
            datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc),
            datetime.fromtimestamp((timestamp + DAY_MS) / 1000, tz=timezone.utc),
            datetime.fromtimestamp((timestamp + DAY_MS) / 1000, tz=timezone.utc),
            float(tables["BTCUSDT"][timestamp]["open"]),
            float(tables["BTCUSDT"][timestamp]["close"]),
            float(tables["SOLUSDT"][timestamp]["close"]),
        )
        for timestamp in range(warmup_start_ms, trading_start_ms, DAY_MS)
    )
    if len(seed) < 730:
        raise ValueError(f"INSUFFICIENT_DAILY_FEATURE_WARMUP:{len(seed)}")
    return seed, tables


def run_native_diagnostic(
    data_root: Path,
    include_funding: bool = False,
    candidate=None,
    trading_start_ms: int = TRADING_START_MS,
    trading_end_ms: int = TRADING_END_MS,
    initial_active_seed: Decimal = Decimal("10000"),
    execution_policy: ExecutionPolicy | None = None,
    artifact_label: str = "native-diagnostic",
    warmup_start_ms: int = WARMUP_START_MS,
    weekly_batch_minutes: int = WEEK_MINUTES,
    cursor_batch_rows: int = WEEK_MINUTES,
    include_daily_signals: bool = True,
    stop_on_liquidation: bool = False,
) -> dict:
    """Run the canonical bounded-memory 1m diagnostic in weekly batches.

    Every source minute is consumed exactly once.  Venue marks, optional
    non-matching daily signals, then executable quotes are added as separate
    homogeneous lists so identical timestamps preserve their causal order.
    """
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.model.data import BarSpecification, BarType
    from nautilus_trader.model.enums import AccountType, AggregationSource, BarAggregation, OmsType, PriceType
    from nautilus_trader.model.objects import Money
    from nautilus_trader.model.identifiers import ClientId
    from coinmaster.domain.wave_overlay import Candidate
    from coinmaster.ledger.journal import NativeEventJournal
    from coinmaster.research.native_fixture import BTC_PERP, SIM, SOL_PERP, BybitTierMarginModule, PerpetualFundingModule, quote
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig
    from coinmaster.venues.marks import venue_mark, venue_mark_data_type
    from coinmaster.venues.signals import daily_signal, daily_signal_data_type

    candidate = candidate or Candidate()
    policy = execution_policy or ExecutionPolicy()
    if trading_end_ms <= trading_start_ms or trading_start_ms - warmup_start_ms < 730 * DAY_MS:
        raise ValueError("INVALID_TRADING_INTERVAL_OR_INSUFFICIENT_730D_WARMUP")
    if policy.execution_delay_minutes < 1:
        raise ValueError("INVALID_EXECUTION_DELAY")
    if not policy.nonmatching_daily_signals:
        raise ValueError("LEGACY_DAILY_BAR_MATCHING_DISABLED")
    if Decimal(policy.symmetric_adverse_spread_bps) < 0 or Decimal(policy.fee_multiplier) <= 0:
        raise ValueError("INVALID_EXECUTION_STRESS")
    blockers = coverage_blockers(data_root)
    if blockers:
        raise ValueError(f"INCOMPLETE_1M_COVERAGE:{','.join(blockers)}")
    expected_rows = (trading_end_ms - trading_start_ms) // MINUTE_MS
    if (trading_start_ms, trading_end_ms) == (TRADING_START_MS, TRADING_END_MS) and expected_rows != 1_051_200:
        raise ValueError("CANONICAL_1M_ROW_COUNT_MISMATCH")
    seed_bars, daily = _load_daily_seed(data_root, warmup_start_ms, trading_start_ms, trading_end_ms)
    start_at = datetime.fromtimestamp(trading_start_ms / 1000, tz=timezone.utc)
    end_at = datetime.fromtimestamp(trading_end_ms / 1000, tz=timezone.utc)
    selected_leverage = ((BTC_PERP.id, Decimal("40")), (SOL_PERP.id, Decimal("20")))
    max_mark_age_ns = 2 * MINUTE_MS * 1_000_000
    funding_events = funding_with_prior_minute_marks(data_root, trading_start_ms, trading_end_ms) if include_funding else ()
    journal_path = data_root / "runs" / f"native-diagnostic-funding-{uuid4().hex}.sqlite"
    journal = NativeEventJournal(str(journal_path)) if funding_events else None
    modules = [BybitTierMarginModule((), selected_leverage, max_mark_age_ns)]
    if journal:
        modules.insert(0, PerpetualFundingModule(funding_events, journal))
    fee = Decimal("0.001") * Decimal(policy.fee_multiplier)
    if fee == Decimal("0.001"):
        btc_instrument, sol_instrument = BTC_PERP, SOL_PERP
    else:
        from nautilus_trader.model.currencies import BTC, SOL
        from coinmaster.research.native_fixture import perpetual
        btc_instrument = perpetual("BTCUSDT", BTC, "0.1", "0.001", "0.025", fee, fee)
        sol_instrument = perpetual("SOLUSDT", SOL, "0.01", "0.1", "0.05", fee, fee)
        selected_leverage = ((btc_instrument.id, Decimal("40")), (sol_instrument.id, Decimal("20")))
        modules = [BybitTierMarginModule((), selected_leverage, max_mark_age_ns)]
        if journal:
            modules.insert(0, PerpetualFundingModule(funding_events, journal))
    def kind(instrument, price_type):
        return BarType(instrument, BarSpecification(1, BarAggregation.DAY, price_type), AggregationSource.EXTERNAL)
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(initial_active_seed, btc_instrument.quote_currency)], base_currency=btc_instrument.quote_currency, default_leverage=Decimal("1"), modules=modules)
    engine.add_instrument(btc_instrument)
    engine.add_instrument(sol_instrument)
    mark_client, signal_client = ClientId("BYBIT_MARK"), ClientId("BYBIT_SIGNAL")
    strategy = WaveOverlayStrategy(WaveOverlayStrategyConfig(
        btc_id=btc_instrument.id, sol_id=sol_instrument.id,
        btc_bar_type=kind(btc_instrument.id, PriceType.LAST), sol_bar_type=kind(sol_instrument.id, PriceType.LAST),
        btc_mark_data_type=venue_mark_data_type(btc_instrument.id), sol_mark_data_type=venue_mark_data_type(sol_instrument.id),
        mark_client_id=mark_client, active_seed=initial_active_seed, tier_selected_leverage=selected_leverage,
        max_mark_age_ns=max_mark_age_ns, trading_start_open_ns=trading_start_ms * 1_000_000,
        terminal_close_at_ns=trading_end_ms * 1_000_000, candidate=candidate, seed_bars=seed_bars,
        btc_signal_data_type=daily_signal_data_type(btc_instrument.id), sol_signal_data_type=daily_signal_data_type(sol_instrument.id), signal_client_id=signal_client,
        reporting_checkpoint_ns=_reporting_checkpoints(start_at, end_at),
        execution_delay_ns=(policy.execution_delay_minutes - 1) * MINUTE_MS * 1_000_000,
    ))
    engine.add_strategy(strategy)
    stats = {"expected_rows_per_source": expected_rows, "processed_rows_per_source": 0, "batch_count": 0, "event_count": 0, "max_batch_minutes": 0, "max_batch_events": 0, "cursor_batch_rows": cursor_batch_rows}
    spread = Decimal(policy.symmetric_adverse_spread_bps) / Decimal("10000")
    early_liquidation_cutoff = False
    def native_quote(instrument, close: str, precision: int, available_ns: int):
        mid = Decimal(str(close))
        return quote(instrument.id, f"{float(mid * (1 - spread)):.{precision}f}", f"{float(mid * (1 + spread)):.{precision}f}", available_ns)
    try:
        for week in iter_weekly_minute_batches(iter_minute_bundles(data_root, trading_start_ms, trading_end_ms, cursor_batch_rows, require_exact_source_rows=(trading_start_ms, trading_end_ms) == (TRADING_START_MS, TRADING_END_MS)), weekly_batch_minutes):
            marks, signals, quotes = [], [], []
            for minute in week:
                available_ns = (minute.open_time_ms + MINUTE_MS) * 1_000_000
                # Same timestamp ordering is marks -> daily signals -> quotes.
                marks.extend((venue_mark(btc_instrument.id, Decimal(str(minute.btc_mark["close"])), available_ns), venue_mark(sol_instrument.id, Decimal(str(minute.sol_mark["close"])), available_ns)))
                if include_daily_signals and (minute.open_time_ms + MINUTE_MS) % DAY_MS == 0:
                    daily_open = minute.open_time_ms + MINUTE_MS - DAY_MS
                    btc_daily, sol_daily = daily["BTCUSDT"][daily_open], daily["SOLUSDT"][daily_open]
                    signals.extend((daily_signal(btc_instrument.id, Decimal(str(btc_daily["open"])), Decimal(str(btc_daily["high"])), Decimal(str(btc_daily["low"])), Decimal(str(btc_daily["close"])), available_ns), daily_signal(sol_instrument.id, Decimal(str(sol_daily["open"])), Decimal(str(sol_daily["high"])), Decimal(str(sol_daily["low"])), Decimal(str(sol_daily["close"])), available_ns)))
                quotes.extend((native_quote(btc_instrument, minute.btc_execution["close"], 1, available_ns), native_quote(sol_instrument, minute.sol_execution["close"], 2, available_ns)))
            engine.add_data(marks, client_id=mark_client, sort=False)
            if signals:
                engine.add_data(signals, client_id=signal_client, sort=False)
            engine.add_data(quotes, sort=False)
            engine.sort_data()
            engine.run(streaming=True)
            engine.clear_data()
            stats["batch_count"] += 1
            stats["event_count"] += len(marks) + len(signals) + len(quotes)
            stats["max_batch_minutes"] = max(stats["max_batch_minutes"], len(week))
            stats["max_batch_events"] = max(stats["max_batch_events"], len(marks) + len(signals) + len(quotes))
            stats["processed_rows_per_source"] += len(week)
            if stop_on_liquidation and strategy.liquidation_audit:
                early_liquidation_cutoff = True
                break
        engine.end()
        account = engine.trader.generate_account_report(SIM)
        fills, orders = engine.trader.generate_order_fills_report(), engine.trader.generate_orders_report()
        artifacts = {"fills": save_native_artifact(fills, data_root / "runs" / f"{artifact_label}-fills.csv"), "orders": save_native_artifact(orders, data_root / "runs" / f"{artifact_label}-orders.csv")}
        terminal_active = Decimal(str(account["total"].iloc[-1]))
        fees = sum((Decimal(str(value).split()[0]) for row in fills.get("commissions", ()) for value in row), Decimal("0"))
        cash_account_series = [{"timestamp": str(index), "active": str(value), "reserve": "0", "total": str(value)} for index, value in account["total"].items()]
        interval_cash_series = [{"timestamp": start_at.isoformat(), "active": str(initial_active_seed), "reserve": "0", "total": str(initial_active_seed)}] + [row for row in cash_account_series if start_at <= datetime.fromisoformat(row["timestamp"]).astimezone(timezone.utc) < end_at]
        interval_cash_terminal = Decimal(interval_cash_series[-1]["total"])
        cash_drawdown = standard_drawdown(interval_cash_series, initial_active_seed)
        fill_timestamps_ns = [_fill_timestamp_ns(value) for value in fills.get("ts_last", ())]
        boundary_ns = trading_end_ms * 1_000_000
        boundary_fill_count = sum(timestamp == boundary_ns for timestamp in fill_timestamps_ns)
        adapter = strategy.reporting_state()
        audit = journal.funding_audit() if journal else []
        manifest = data_root / "bybit-1m" / "manifest.json"
        full_config = {**BASELINE_CONFIG, "candidate": asdict(candidate), "execution_policy": asdict(policy), "run_interval": {"start": start_at.isoformat(), "end_exclusive": end_at.isoformat(), "initial_active_seed": str(initial_active_seed)}}
        stats["peak_rss_bytes"] = _peak_rss_bytes()
        result = {"status": "LIQUIDATED_EARLY_CUTOFF" if early_liquidation_cutoff else "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible": False, "interval": f"[{start_at.isoformat()},{end_at.isoformat()})", "run_interval": full_config["run_interval"], "warmup": f"[{datetime.fromtimestamp(warmup_start_ms / 1000, tz=timezone.utc).isoformat()},{start_at.isoformat()}) feature-only", "config": full_config, "config_hash": hashlib.sha256(json.dumps(full_config, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), "data_hash": hashlib.sha256(json.dumps(json.loads(manifest.read_text()), sort_keys=True, separators=(",", ":")).encode()).hexdigest(), "code_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "policy": asdict(policy), "policy_hash": policy.hash, "streaming": stats, "summary": {"objective": "POST_BOUNDARY_SETTLED_NATIVE_CASH_ACTIVE_PLUS_RESERVE", "roi": str((terminal_active / initial_active_seed) - 1), "terminal_total": str(terminal_active), "interval_cash_terminal_total": str(interval_cash_terminal), "monthly_returns_basis": "NATIVE_CASH_ACCOUNT_INTERVAL_EXCLUDING_POST_BOUNDARY_SETTLEMENT", "max_drawdown_amount": cash_drawdown["amount"], "max_drawdown_percent": cash_drawdown["percent"], "drawdown_start": cash_drawdown["start"], "drawdown_trough": cash_drawdown["trough"], "drawdown_basis": cash_drawdown["basis"], "drawdown_recovery": "UNKNOWN_NOT_RECOVERED_OR_NOT_EXPORTED", "monthly_returns": monthly_returns(interval_cash_series, initial_active_seed)}, "cash_account_series": cash_account_series, "interval_cash_account_series": interval_cash_series, "marked_equity_series": {"status": "PARTIAL_NATIVE_MARKED_CHECKPOINTS_ONLY", "checkpoints": adapter["marked_equity_checkpoints"], "monthly_returns": "UNKNOWN_NOT_RECONCILED_TO_POST_BOUNDARY_SETTLED_CASH_OBJECTIVE"}, "fills": len(fills), "fill_timestamps_ns": fill_timestamps_ns, "execution_artifacts": artifacts, "native_fees": str(fees), "native_order_rejections": sum("REJECTED" in str(value) for value in orders.get("status", ())), "pre_submit_tier_margin_gate_blocks": adapter["pre_submit_tier_margin_gate_blocks"], "funding": {"count": len(audit), "signed_amount": "UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA"}, "funding_journal": str(journal_path) if journal else None, "liquidation_count": len(adapter["liquidations"]), "liquidation_value": str(sum((Decimal(item["close_value"]) for item in adapter["liquidations"]), Decimal("0"))), "liquidation_audit": adapter["liquidations"], "liquidation_lockout": adapter["liquidation_lockout"], "terminal_lifecycle": adapter["terminal_lifecycle"], "post_boundary_settlement": {"convention": "TERMINAL_FILLS_AT_END_EXCLUSIVE_REPORTED_SEPARATELY_EXCLUDED_FROM_INTERVAL_RETURNS", "boundary_timestamp": end_at.isoformat(), "fill_count": boundary_fill_count, "settled_cash_total": str(terminal_active), "interval_cash_total_before_settlement": str(interval_cash_terminal)}, "early_liquidation_cutoff": early_liquidation_cutoff, "terminal_active": str(terminal_active), "terminal_reserve": "0", "terminal_total": str(terminal_active), "terminal_open_positions": len(engine.cache.positions_open()), "limitations": ["1m close proxy has no BBO/L2/slippage/liquidity evidence", "Fixture fees are 0.001/side; historical applicability unknown", "Venue marks are CustomData and do not participate in matching", "Historical liquidation and funding settlement marks are unvalidated"]}
        result.update({
            "episodes": "UNKNOWN_NATIVE_DOMAIN_EPISODE_AUDIT_NOT_EXPORTED",
            "realized_unrealized": "UNKNOWN_NATIVE_ACCOUNT_REPORT_ONLY",
            "modeled_slippage": policy.spread_slippage_liquidity,
            "transfers": "0",
            "funding": {
                "count": len(audit),
                "by_instrument_count": {instrument: sum(1 for row in audit if row[1] == instrument) for instrument in sorted({row[1] for row in audit})},
                "signed_amount": "UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA",
            },
        })
        if not early_liquidation_cutoff:
            assert_report_boundaries(result)
        return result
    finally:
        engine.dispose()
        if journal:
            journal.close()


def coverage_blockers(root: Path) -> list[str]:
    manifest = root / "bybit-1m" / "manifest.json"
    if not manifest.exists():
        return ["MISSING_1M_MANIFEST"]
    data = json.loads(manifest.read_text())
    blockers: list[str] = []
    for symbol in data.get("symbols", []):
        for stream in symbol.get("streams", []):
            prefix = f"{symbol.get('symbol', 'UNKNOWN')}:{stream.get('stream', 'UNKNOWN')}"
            if stream.get("status") == "PARTIAL_RESUMABLE":
                blockers.append(f"{prefix}:PARTIAL")
            elif stream.get("missing_count") != 0:
                blockers.append(f"{prefix}:GAPS")
            elif not stream.get("parquet_sha256"):
                blockers.append(f"{prefix}:UNHASHED")
    return blockers


def save_diagnostic_report(data_root: Path, report: dict, artifact_name: str = "native-diagnostic-report") -> Path:
    """Persist a diagnostic artifact without promoting it to baseline evidence."""
    target = data_root / "runs" / f"{artifact_name}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temporary.replace(target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("var/data"))
    parser.add_argument("--diagnostic-no-funding", action="store_true")
    parser.add_argument("--diagnostic-with-prior-minute-funding", action="store_true")
    args = parser.parse_args()
    if args.diagnostic_no_funding:
        report = run_native_diagnostic(args.data_root)
        report["artifact"] = str(save_diagnostic_report(args.data_root, report))
        print(json.dumps(report, sort_keys=True))
        return
    if args.diagnostic_with_prior_minute_funding:
        report = run_native_diagnostic(args.data_root, include_funding=True)
        report["artifact"] = str(save_diagnostic_report(args.data_root, report))
        print(json.dumps(report, sort_keys=True))
        return
    blockers = coverage_blockers(args.data_root)
    if blockers:
        print(json.dumps({"status": "BLOCKED", "ranking_eligible": False, "blockers": blockers}, sort_keys=True))
        raise SystemExit(2)
    report = run_native_diagnostic(args.data_root, include_funding=True)
    report["artifact"] = str(save_diagnostic_report(args.data_root, report))
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
