"""Fail-closed native baseline entrypoint.

This command intentionally refuses to calculate or label a result until all
four required 1-minute execution/mark streams are complete and gap-free.  It
is the only accepted launch point for the future native baseline lifecycle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
from dataclasses import asdict, dataclass, replace
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Iterator
from uuid import uuid4
from datetime import date, datetime, timedelta, timezone

from coinmaster.research.job_protocol import report_summary, sha256_file, wait_for_launch_permit


DAY_MS = 86_400_000
MINUTE_MS = 60_000
WEEK_MINUTES = 7 * 24 * 60
WARMUP_START_MS = 1_662_076_800_000  # 2022-09-02T00:00:00Z
TRADING_START_MS = 1_725_148_800_000  # 2024-09-01T00:00:00Z
TRADING_END_MS = 1_788_220_800_000  # 2026-09-01T00:00:00Z, exclusive
MAX_BOUNDED_DAYS = 7


def validate_bounded_interval(value: dict[str, str]) -> tuple[int, int]:
    if not isinstance(value, dict) or set(value) != {"start", "end_exclusive"}:
        raise ValueError("INVALID_BOUNDED_INTERVAL")
    try:
        start_date, end_date = (date.fromisoformat(value[key]) for key in ("start", "end_exclusive"))
        if start_date.isoformat() != value["start"] or end_date.isoformat() != value["end_exclusive"]:
            raise ValueError
        start_ms = int(datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)
        end_ms = int(datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("INVALID_BOUNDED_INTERVAL") from error
    if not (TRADING_START_MS <= start_ms < end_ms <= TRADING_END_MS and
            end_ms - start_ms <= MAX_BOUNDED_DAYS * DAY_MS and
            start_ms - WARMUP_START_MS >= 730 * DAY_MS):
        raise ValueError("INVALID_BOUNDED_INTERVAL")
    return start_ms, end_ms

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
    version: str = "bybit-native-resting-reductions-v2"
    execution_source: str = "BYBIT_GAP_FREE_1M_EXECUTION_CLOSE"
    mark_source: str = "BYBIT_GAP_FREE_1M_MARK_CLOSE"
    latency: str = "taker_decisions_next_quote;_maker_reductions_rest_on_later_quotes"
    fees: str = "NATIVE_INSTRUMENT_FIXED_BASE_NON_VIP_BYBIT_MAKER_0.00020_TAKER_0.00055"
    fee_historical_applicability: str = "UNKNOWN"
    spread_slippage_liquidity: str = "UNKNOWN_NO_L2_OR_TRADE_TAPE"
    liquidation: str = "MARK_FIRST_NATIVE_TIER_LIQUIDATION_HISTORICAL_APPLICABILITY_UNVALIDATED"
    execution_delay_minutes: int = 1
    symmetric_adverse_spread_bps: str = "0"
    fee_multiplier: str = "1"
    nonmatching_daily_signals: bool = True

    @property
    def hash(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class FixedBaseFeePolicy:
    """Owner-specified non-VIP venue schedule; historical use is diagnostic."""
    version: str = "fixed-base-native-maker-taker-execution-v3"
    venue: str = "bybit"
    bybit_maker: str = "0.00020"
    bybit_taker: str = "0.00055"
    hyperliquid_maker: str = "0.00015"
    hyperliquid_taker: str = "0.00045"

    def rates(self) -> tuple[Decimal, Decimal]:
        if self.venue == "bybit":
            return Decimal(self.bybit_maker), Decimal(self.bybit_taker)
        if self.venue == "hyperliquid":
            return Decimal(self.hyperliquid_maker), Decimal(self.hyperliquid_taker)
        raise ValueError("UNKNOWN_FEE_VENUE")

    @property
    def hash(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def native_fee_attribution(fill_audit: list[dict[str, str]], native_total: Decimal) -> dict[str, object]:
    """Aggregate only native ``OrderFilled.liquidity_side`` facts.

    This intentionally has no order-type fallback: if Nautilus reports an
    unknown liquidity side it remains unknown rather than being relabeled.
    """
    buckets = {"MAKER": {"count": 0, "notional": Decimal("0"), "fees": Decimal("0")}, "TAKER": {"count": 0, "notional": Decimal("0"), "fees": Decimal("0")}, "UNKNOWN": {"count": 0, "notional": Decimal("0"), "fees": Decimal("0")}}
    for row in fill_audit:
        side = row.get("native_liquidity_side", "UNKNOWN")
        key = side if side in buckets else "UNKNOWN"
        buckets[key]["count"] += 1
        buckets[key]["notional"] += Decimal(row["notional"])
        buckets[key]["fees"] += Decimal(row["commission"])
    audited_total = sum((bucket["fees"] for bucket in buckets.values()), Decimal("0"))
    if audited_total != native_total:
        raise ValueError(f"NATIVE_FEE_AUDIT_RECONCILIATION_MISMATCH:{audited_total}:{native_total}")
    return {
        key.lower(): {"count": bucket["count"], "notional": str(bucket["notional"]), "fees": str(bucket["fees"])}
        for key, bucket in buckets.items()
    } | {"native_total": str(native_total), "audited_total": str(audited_total), "reconciled": True}


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
    if callable(getattr(equity, "monthly_returns", None)):
        return equity.monthly_returns(initial)
    # Keep native insertion order for equal timestamps.  A bare tuple sort
    # uses the amount as a tie breaker, which can silently turn a later debit
    # into an earlier credit at the same native report timestamp.
    values = sorted(
        ((datetime.fromisoformat(row["timestamp"]).replace(tzinfo=timezone.utc), Decimal(row["total"])) for row in equity),
        key=lambda item: item[0],
    )
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
    """UTC month boundaries inside the interval, plus its actual end boundary."""
    if start>=end:raise ValueError("INVALID_REPORT_INTERVAL")
    cursor = start.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    result: list[int] = []
    while True:
        cursor = cursor.replace(year=cursor.year + (cursor.month == 12), month=1 if cursor.month == 12 else cursor.month + 1)
        if cursor>=end:break
        result.append(int(cursor.timestamp() * 1_000_000_000))
    result.append(int(end.timestamp() * 1_000_000_000))
    return tuple(result)


def assert_report_boundaries(report: dict) -> None:
    """Reject report shapes that cannot reconcile to their declared interval."""
    summary = report["summary"]
    months = summary["monthly_returns"]
    start = datetime.fromisoformat(report["run_interval"]["start"])
    end = datetime.fromisoformat(report["run_interval"]["end_exclusive"])
    if start.tzinfo is None or end.tzinfo is None or start.utcoffset()!=timedelta(0) or end.utcoffset()!=timedelta(0) or start>=end:
        raise ValueError("INVALID_REPORT_INTERVAL")
    cursor=start.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    expected_labels=[]
    while cursor<end:
        expected_labels.append(cursor.strftime("%Y-%m"))
        cursor=cursor.replace(year=cursor.year+(cursor.month==12),month=1 if cursor.month==12 else cursor.month+1)
    expected_months=len(expected_labels)
    liquidated_early_lockout = bool(report.get("liquidation_count")) and bool(report.get("liquidation_lockout"))
    if (not liquidated_early_lockout and len(months) != expected_months) or not months:
        raise ValueError(f"MONTHLY_ROW_COUNT:{len(months)}")
    labels=[month.get("month") for month in months]
    if labels!=(expected_labels[:len(months)] if liquidated_early_lockout else expected_labels):
        raise ValueError("MONTHLY_INTERVAL_COVERAGE_MISMATCH")
    interval_terminal = Decimal(summary["interval_cash_terminal_total"])
    if Decimal(months[-1]["total"]) != interval_terminal:
        raise ValueError("MONTHLY_INTERVAL_CASH_MISMATCH")
    with localcontext() as context:
        context.prec = 80
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
    at_boundary = sum(timestamp == boundary_ns for timestamp in fills)
    if at_boundary != settlement["fill_count"]:
        raise ValueError("POST_BOUNDARY_FILL_COUNT_MISMATCH")
    if any(timestamp == boundary_ns for timestamp in fills) != bool(settlement["fill_count"]):
        raise ValueError("POST_BOUNDARY_FILL_CONVENTION_MISMATCH")


def _finalize_native_resources(*,audit_archive,risk_recorder,coherent_observer,engine,journal,
                               successful_run,journal_attempt_path,journal_path,primary_error=None):
    """Flush every report stream; retain the original failure and funding quarantine."""
    errors=[]
    for resource in (audit_archive,risk_recorder,coherent_observer):
        if resource is None:continue
        try:
            close=getattr(resource,"close_writers",None) or resource.close
            close()
        except BaseException as error:errors.append(error)
    try:engine.dispose()
    except BaseException as error:errors.append(error)
    if journal is not None:
        if successful_run and primary_error is None and not errors:
            try:_publish_clean_funding_attempt(journal,journal_attempt_path,journal_path)
            except BaseException as error:
                errors.append(error)
                try:journal.close()
                except BaseException as close_error:errors.append(close_error)
                try:_quarantine_funding_attempt(journal_attempt_path)
                except BaseException as quarantine_error:errors.append(quarantine_error)
        else:
            try:journal.close()
            except BaseException as error:errors.append(error)
            try:_quarantine_funding_attempt(journal_attempt_path)
            except BaseException as error:errors.append(error)
    if primary_error is not None:
        for error in errors:primary_error.add_note("Native report cleanup: "+repr(error))
    elif errors:
        raise errors[0]


def save_native_artifact(frame, path: Path) -> dict[str, str | int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary=path.with_suffix(path.suffix+".tmp")
    with temporary.open("w") as stream:
        frame.to_csv(stream,index=True)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
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
        requested_minutes = (end_settlement_ms - start_settlement_ms) // MINUTE_MS if start_settlement_ms is not None and end_settlement_ms is not None else 0
        lazy_complete = requested_minutes > 0 and pq.ParquetFile(mark_path).metadata.num_rows >= requested_minutes
        if lazy_complete:
            wanted = {settlement - MINUTE_MS: row for settlement, row in relevant}
            marks = {}
            for mark_row in ParquetMinuteCursor(mark_path, start_settlement_ms, end_settlement_ms, batch_rows=min(WEEK_MINUTES, requested_minutes)):
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
    from coinmaster.research.native_fixture import BTC_PERP, SIM, SOL_PERP, BybitTierMarginModule, MarkPriceUpdate, PerpetualFundingModule, TierMarginPolicy, quote
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
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(initial_active_seed, btc_instrument.quote_currency)], base_currency=btc_instrument.quote_currency, default_leverage=Decimal("1"), modules=modules, fee_model=MakerTakerFeeModel())
    engine.add_instrument(btc_instrument); engine.add_instrument(sol_instrument)
    from nautilus_trader.model.identifiers import ClientId
    engine.add_strategy(WaveOverlayStrategy(WaveOverlayStrategyConfig(btc_id=btc_instrument.id, sol_id=sol_instrument.id, btc_bar_type=btc_last, sol_bar_type=sol_last, btc_mark_data_type=venue_mark_data_type(btc_instrument.id), sol_mark_data_type=venue_mark_data_type(sol_instrument.id), mark_client_id=ClientId("BYBIT_MARK"), active_seed=initial_active_seed, margin_policy=TierMarginPolicy(mark_updates, dict(selected_leverage), max_mark_age_ns), trading_start_open_ns=trading_start_ms * 1_000_000, terminal_close_at_ns=trading_end_ms * 1_000_000, candidate=candidate, btc_signal_data_type=daily_signal_data_type(btc_instrument.id), sol_signal_data_type=daily_signal_data_type(sol_instrument.id), signal_client_id=ClientId("BYBIT_SIGNAL"))))
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
                return quote(instrument.id, f"{float(mid * (1 - spread)):.{precision}f}", f"{float(mid * (1 + spread)):.{precision}f}", (execution_minute + 60_000) * 1_000_000, size_precision=instrument.size_precision)
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


def _funding_attempt_path(canonical_path: Path) -> Path:
    """Return a same-directory DB that can never be execution input later."""
    return canonical_path.with_name(f".{canonical_path.name}.attempt-{uuid4().hex}")


def _move_sqlite_family(path: Path, marker: str) -> list[Path]:
    """Keep a whole SQLite family as evidence without reusing it on a run."""
    moved: list[Path] = []
    for suffix in ("", "-wal", "-shm"):
        source = Path(f"{path}{suffix}")
        if source.exists():
            destination = source.with_name(f"{source.name}.{marker}-{uuid4().hex}")
            os.replace(source, destination)
            moved.append(destination)
    return moved


def _publish_clean_funding_attempt(journal, attempt_path: Path, canonical_path: Path) -> None:
    """Checkpoint and atomically promote an isolated successful funding DB."""
    journal.checkpoint()
    journal.close()
    if Path(f"{attempt_path}-wal").exists() or Path(f"{attempt_path}-shm").exists():
        raise ValueError("FUNDING_ATTEMPT_CHECKPOINT_LEFT_SQLITE_SIDECAR")
    # A previous canonical artifact is never an input to this run.  Preserve it
    # before the single-file atomic replacement, including stale WAL sidecars.
    _move_sqlite_family(canonical_path, "superseded")
    os.replace(attempt_path, canonical_path)


def _quarantine_funding_attempt(attempt_path: Path) -> None:
    """Retain failed attempt evidence under a noncanonical, never-reused name."""
    _move_sqlite_family(attempt_path, "aborted")


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
    artifact_dir: Path | None = None,
    fixed_base_fee_policy: FixedBaseFeePolicy | None = None,
    tp_fee_floor_v1: bool = False,
    research_v0_execution_repairs: bool = False,
    research_v0_zero_tp_netting: bool = True,
    research_v0_deferred_selective_zero_tp: bool = False,
    research_v0_selective_lifecycle_repairs: bool = False,
    observe_minute_risk: bool = False,
    research_sol_notional_cap_6x: bool = False,
    research_portfolio_protect_45: bool = False,
    research_btc_direction_sizing: bool = False,
    research_btc_drawdown_sizing: bool = False,
    research_v3_risk: str | None = None,
    research_h1_b1: str | None = None,
    research_btc_split50: bool = False,
    research_btc_split_planref_v1: bool = False,
    research_btc_split_tp_ioc: bool = False,
    research_btc_split_discount: str = "0.0025",
    research_sol_btc_open_only: bool = False, research_h4_ema: int | None = None, research_h4_gamma: str = "0.5", research_h4_warmup: Path | None = None, research_regime_reentry_band: str | None = None, research_residual_recovery: bool = False, research_c1_btc_cut_divisor: int = 2, research_c1_restore_dd: str = "0.35", research_c1_first_fresh_h4: bool = False, research_c1_btc_postcut_d1: bool = False, research_wait_4h: bool = False, research_wait_persist: bool = False, research_zero_retrace: bool = False, research_sol_dominant: bool = False,
    research_sol_cover: str | None = None,
    research_conditional_sol: bool = False, research_immediate_sol: str | None = None, research_immediate_lookback: int = 90, research_sol_risk_first: str | None = None, research_alpha_cushion: bool = False, research_chop_pair: bool = False,
    research_btc_episode_loss_20: bool = False,
    research_sol_remaining_btc_hedge: bool = False,
    qualification_mode: str = "legacy_reference",
    qualification_quantity_model: str = "legacy_bybit",
    qualification_instrument_metadata: dict | None = None,
    qualification_deposit_runtime=None,
    qualification_deposit_equity_reader=None,
    qualification_deposit_account_id: str = "",
    current_hl_execution_inputs: Path | None = None,
) -> dict:
    """Run the canonical bounded-memory 1m diagnostic in weekly batches.

    Every source minute is consumed exactly once.  Venue marks, optional
    non-matching daily signals, then executable quotes are added as separate
    homogeneous lists so identical timestamps preserve their causal order.
    """
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.backtest.models import MakerTakerFeeModel
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.cache.config import CacheConfig
    from nautilus_trader.data.config import DataEngineConfig
    from nautilus_trader.model.data import Bar, BarSpecification, BarType
    from nautilus_trader.model.enums import AccountType, AggregationSource, BarAggregation, OmsType, PriceType, TimeInForce
    from nautilus_trader.model.objects import Money
    from nautilus_trader.model.identifiers import ClientId
    from coinmaster.domain.wave_overlay import Candidate
    from coinmaster.ledger.journal import NativeEventJournal
    from coinmaster.research.native_fixture import BTC_PERP, SIM, SOL_PERP, BybitTierMarginModule, PerpetualFundingModule, TierMarginPolicy, quote, instrument_quote
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig
    from coinmaster.venues.marks import venue_mark, venue_mark_data_type
    from coinmaster.venues.signals import daily_signal, daily_signal_data_type

    if sum((research_portfolio_protect_45, research_sol_notional_cap_6x, research_btc_episode_loss_20, research_sol_remaining_btc_hedge, research_btc_direction_sizing, research_btc_drawdown_sizing, research_v3_risk is not None, research_h1_b1 is not None)) > 1:
        raise ValueError("RESEARCH_RISK_VARIANTS_MUTUALLY_EXCLUSIVE")
    if research_chop_pair and (research_alpha_cushion or research_immediate_sol or research_sol_risk_first or research_conditional_sol or research_sol_cover or research_h1_b1 or research_v3_risk or not research_btc_split50 or not research_btc_split_planref_v1 or not research_btc_split_tp_ioc or not research_btc_direction_sizing or not observe_minute_risk):
        raise ValueError("CHOP_PAIR_REQUIRES_EXCLUSIVE_WINNER_NATIVE_OBSERVER")
    if research_alpha_cushion and (research_immediate_sol or research_sol_risk_first or research_conditional_sol or research_sol_cover or research_h1_b1 or not research_btc_split50 or not research_btc_split_planref_v1 or not research_btc_split_tp_ioc or not research_btc_direction_sizing or not observe_minute_risk):
        raise ValueError("ALPHA_CUSHION_REQUIRES_SELECTED_BTC_EXCLUSIVE_SOL_NATIVE_OBSERVER")
    if research_immediate_sol and (research_immediate_sol not in {"i25","i25-light","i25-recovery","i33"} or not 30<=research_immediate_lookback<=180 or research_sol_risk_first or research_conditional_sol or research_sol_cover or research_h1_b1 or not research_btc_split50 or not research_btc_split_planref_v1 or not research_btc_split_tp_ioc or not research_btc_direction_sizing or not observe_minute_risk):
        raise ValueError("IMMEDIATE_REQUIRES_SELECTED_BTC_EXCLUSIVE_SOL_NATIVE_OBSERVER")
    if research_sol_risk_first=='alpha-corridor-v1' and (not observe_minute_risk or not research_btc_direction_sizing or research_v3_risk or research_alpha_cushion or research_chop_pair or research_immediate_sol):
        raise ValueError('CORRIDOR_REQUIRES_EXCLUSIVE_WINNER_AND_FINAL_NATIVE_OBSERVER')
    if research_sol_risk_first and (research_conditional_sol or research_sol_cover or research_h1_b1 or not research_btc_split50 or not research_btc_split_planref_v1 or not research_btc_split_tp_ioc):
        raise ValueError("RISK_FIRST_REQUIRES_SELECTED_BTC_AND_EXCLUSIVE_SOL_POLICY")
    if (research_portfolio_protect_45 or research_btc_episode_loss_20 or research_sol_remaining_btc_hedge or research_btc_drawdown_sizing or research_v3_risk or research_h1_b1) and not observe_minute_risk:
        raise ValueError("PORTFOLIO_PROTECTION_REQUIRES_PRE_ACTION_MINUTE_OBSERVER")
    if research_sol_btc_open_only or research_h4_ema is not None or research_regime_reentry_band is not None:
        if candidate is None or candidate.ema_period != 34 or candidate.beta_days != 270:
            raise ValueError("HEDGE_BAND_REQUIRES_RESOLVED_S0_EMA34_BETA270_CANDIDATE")
        if not all((research_v0_execution_repairs, research_v0_deferred_selective_zero_tp,
                    research_v0_selective_lifecycle_repairs, research_btc_split50,
                    research_btc_split_planref_v1, research_btc_split_tp_ioc,
                    research_btc_direction_sizing, observe_minute_risk)):
            raise ValueError("HEDGE_BAND_REQUIRES_UNCHANGED_SELECTED_S0_EXECUTOR")
    from coinmaster.research.effective_config import effective_research_candidate
    candidate = effective_research_candidate(candidate, selective_lifecycle_repairs=research_v0_selective_lifecycle_repairs)
    if research_h1_b1 == "h1" or research_sol_cover or research_immediate_sol:
        candidate = replace(candidate, sol_overlay_enabled=False)
    if research_c1_btc_postcut_d1 and not research_c1_first_fresh_h4:raise ValueError("BTC_POSTCUT_D1_REQUIRES_FIRST_FRESH_COMBO")
    if research_c1_first_fresh_h4 and (not research_residual_recovery or research_c1_btc_cut_divisor!=4 or research_c1_restore_dd!="0.40"):
        raise ValueError("FIRST_FRESH_REQUIRES_SELECTED_C1_COMBO")
    from coinmaster.research.qualification_policy import research_qualification
    qualification_kwargs, lot_constraints = research_qualification(qualification_mode, qualification_quantity_model,
        qualification_instrument_metadata, qualification_deposit_runtime, qualification_deposit_equity_reader, qualification_deposit_account_id)
    if qualification_kwargs:qualification_kwargs["market_exit_time_in_force"]=TimeInForce.IOC
    current_hl = None
    if current_hl_execution_inputs is not None:
        if qualification_mode != "execution_diagnostic":
            raise ValueError("CURRENT_HL_REQUIRES_EXPLICIT_EXECUTION_DIAGNOSTIC")
        from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
        from coinmaster.venues.effective_fees import CURRENT_HL_FEES
        current_hl=load_current_hl_diagnostic(current_hl_execution_inputs)
        if fixed_base_fee_policy is not None or execution_policy is not None:
            raise ValueError("CURRENT_HL_USES_SINGLE_FROZEN_FEE_AND_EXECUTION_POLICY")
        fixed_base_fee_policy=FixedBaseFeePolicy(venue="hyperliquid",hyperliquid_maker=str(CURRENT_HL_FEES.maker),hyperliquid_taker=str(CURRENT_HL_FEES.taker))
        execution_policy=ExecutionPolicy(version="current-hl-usdc-full-fill-diagnostic-v1",fees="OWNER_EFFECTIVE_HL_MAKER_0.000144_TAKER_0.000432_REFERRAL_ALREADY_APPLIED",spread_slippage_liquidity="ZERO_MARKET_IMPACT_FULL_FILL_DIAGNOSTIC_NOT_OBSERVED_CAPACITY",liquidation="CURRENT_PUBLIC_HL_TIERS_NATIVE_USDC_ON_HISTORICAL_PROXY_MARKS")
    elif qualification_mode == "execution_diagnostic":
        raise ValueError("CURRENT_HL_FROZEN_INPUTS_REQUIRED")
    policy = execution_policy or ExecutionPolicy()
    fee_policy = fixed_base_fee_policy or FixedBaseFeePolicy()
    if fee_policy.venue != "bybit" and current_hl is None:
        raise ValueError("HYPERLIQUID_HISTORICAL_EXECUTION_BLOCKED")
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
    artifacts_root = artifact_dir or data_root / "runs"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    journal_path = artifacts_root / f"{artifact_label}-funding.sqlite"
    journal_attempt_path = _funding_attempt_path(journal_path) if funding_events else None
    # Every diagnostic is a from-genesis account run.  It must not consult a
    # prior canonical journal, whose durable IDs are only valid for genuine
    # process restart of the same account/engine, never for a fresh engine.
    journal = NativeEventJournal(str(journal_attempt_path)) if journal_attempt_path else None
    modules = [BybitTierMarginModule((), selected_leverage, max_mark_age_ns)] if current_hl is None else []
    if journal:
        modules.insert(0, PerpetualFundingModule(funding_events, journal))
    from nautilus_trader.model.currencies import BTC, SOL
    from coinmaster.research.native_fixture import perpetual
    maker, taker = fee_policy.rates()
    multiplier = Decimal(policy.fee_multiplier)
    btc_instrument = perpetual("BTCUSDT", BTC, "0.1", lot_constraints.get("BTC",{}).get("step","0.001"), "0.025", maker * multiplier, taker * multiplier, min_quantity=lot_constraints.get("BTC",{}).get("min_quantity"))
    sol_instrument = perpetual("SOLUSDT", SOL, "0.01", lot_constraints.get("SOL",{}).get("step","0.1"), "0.05", maker * multiplier, taker * multiplier, min_quantity=lot_constraints.get("SOL",{}).get("min_quantity"))
    selected_leverage = ((btc_instrument.id, Decimal("40")), (sol_instrument.id, Decimal("20")))
    modules = [BybitTierMarginModule((), selected_leverage, max_mark_age_ns)] if current_hl is None else []
    if journal:
        modules.insert(0, PerpetualFundingModule(funding_events, journal))
    if current_hl is not None:
        btc_instrument,sol_instrument=current_hl.instruments
        selected_leverage=current_hl.selected_leverage
        SIM=btc_instrument.id.venue
        mapping={BTC_PERP.id:btc_instrument.id,SOL_PERP.id:sol_instrument.id}
        funding_events=tuple(replace(event,instrument_id=mapping[event.instrument_id]) for event in funding_events)
        modules=[BybitTierMarginModule((),selected_leverage,max_mark_age_ns,
            margin_policy=current_hl.margin_policy(max_mark_age_ns),settlement_currency=btc_instrument.settlement_currency)]
        if journal:modules.insert(0,PerpetualFundingModule(funding_events,journal))
        lot_constraints={i.base_currency.code:dict(step=str(i.size_increment),size_precision=i.size_precision,
            min_quantity=None if i.min_quantity is None else str(i.min_quantity)) for i in current_hl.instruments}
    coherent_observer = None
    coherent_observer_report = None
    if research_residual_recovery:
        from coinmaster.research.paired_observer import CommittedNativeObserver
        coherent_observer = CommittedNativeObserver(artifacts_root / "coherent-native-events.jsonl.gz",
            initial_active_seed,(btc_instrument,sol_instrument),journal,trading_end_ms * 1_000_000)
        modules.append(coherent_observer)
    def kind(instrument, price_type):
        return BarType(instrument, BarSpecification(1, BarAggregation.DAY, price_type), AggregationSource.EXTERNAL)
    if research_c1_restore_dd not in ("0.35","0.40") or (research_c1_restore_dd!="0.35" and not research_residual_recovery):raise ValueError("R_REQUIRES_C1_RESTORE_DD_35_OR_40")
    if research_c1_btc_cut_divisor not in (2,4) or (research_c1_btc_cut_divisor!=2 and not research_residual_recovery):raise ValueError("Q_REQUIRES_C1_DIVISOR_2_OR_4")
    if research_residual_recovery and (not observe_minute_risk or not research_wait_4h or research_regime_reentry_band!="0.5" or research_zero_retrace or research_sol_dominant or research_wait_persist or research_sol_risk_first or research_conditional_sol or research_alpha_cushion or research_chop_pair):raise ValueError("C1_REQUIRES_CLEAN_E4_SETTLED_OBSERVER")
    next_enabled = research_wait_4h or research_wait_persist or research_zero_retrace or research_sol_dominant
    from coinmaster.strategy.next_band import next_bar_type, next_closed_bar
    next_bar_types = tuple(next_bar_type(inst.id,hours) for inst,hours in ((btc_instrument,4),(sol_instrument,1),*((((sol_instrument,4),)) if research_residual_recovery else ()))) if next_enabled else ()
    confirmation_bars = tuple(BarType.new_composite(
        instrument.id, BarSpecification(15 if minutes == 15 else 1, BarAggregation.MINUTE if minutes == 15 else BarAggregation.HOUR, PriceType.LAST),
        AggregationSource.INTERNAL, 1, BarAggregation.MINUTE, AggregationSource.EXTERNAL,
    ) for instrument in (btc_instrument, sol_instrument) for minutes in (15, 60)) if research_h4_ema is not None or research_h1_b1 or research_sol_cover or research_conditional_sol or research_sol_risk_first or research_immediate_sol or research_alpha_cushion or research_chop_pair else ()
    h4_bar_type = BarType.new_composite(sol_instrument.id, BarSpecification(4, BarAggregation.HOUR, PriceType.LAST),
        AggregationSource.INTERNAL, 1, BarAggregation.MINUTE, AggregationSource.EXTERNAL) if research_h4_ema is not None else None
    h4_seed = ()
    h4_warmup_hash = None
    if research_h4_ema is not None:
        import csv
        if research_h4_warmup is None:
            raise ValueError("H4_WARMUP_REQUIRED_BLOCKED_DATA")
        h4_warmup_hash = sha256_file(research_h4_warmup)
        with research_h4_warmup.open() as handle:
            h4_seed = tuple((int(r["close_time_ns"]), float(r["close"])) for r in csv.DictReader(handle))
        if len(h4_seed) != 730 or h4_seed[-1][0] != trading_start_ms*1_000_000 or any(b[0]-a[0] != 14_400_000_000_000 for a,b in zip(h4_seed,h4_seed[1:])):
            raise ValueError("H4_EXACT_730_CLOSED_WARMUP_REQUIRED")
    minute_bars = {instrument.id: BarType(instrument.id, BarSpecification(1, BarAggregation.MINUTE, PriceType.LAST), AggregationSource.EXTERNAL)
                   for instrument in (btc_instrument, sol_instrument)}
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR"),
        run_analysis=not (research_alpha_cushion or research_chop_pair or research_sol_risk_first=="alpha-corridor-v1"),
        **({"cache": CacheConfig(bar_capacity=128), "data_engine": DataEngineConfig(time_bars_build_with_no_updates=False)} if research_h4_ema is not None or research_h1_b1 or research_sol_cover or research_conditional_sol or research_sol_risk_first or research_immediate_sol or research_alpha_cushion or research_chop_pair else {})))
    from coinmaster.research.native_full_fill import ZeroImpactFullFillDiagnostic
    fill_kwargs=dict(fill_model=ZeroImpactFullFillDiagnostic(),liquidity_consumption=True,leverages=dict(selected_leverage)) if current_hl is not None else {}
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(initial_active_seed, btc_instrument.quote_currency)], base_currency=btc_instrument.quote_currency, default_leverage=Decimal("1"), modules=modules, fee_model=MakerTakerFeeModel(), **fill_kwargs, bar_execution=not bool(research_h4_ema is not None or research_h1_b1 or research_sol_cover or research_conditional_sol or research_sol_risk_first or research_immediate_sol or research_alpha_cushion or research_chop_pair))
    engine.add_instrument(btc_instrument)
    engine.add_instrument(sol_instrument)
    mark_client, signal_client = ClientId("BYBIT_MARK"), ClientId("BYBIT_SIGNAL")
    risk_recorder = None
    strategy_type = WaveOverlayStrategy
    if observe_minute_risk:
        from coinmaster.research.minute_risk import NativeMinuteRiskRecorder, observed_strategy_type
        risk_recorder = NativeMinuteRiskRecorder(artifacts_root / "minute-native-risk.csv.gz", initial_active_seed, (btc_instrument, sol_instrument), dict(selected_leverage), trading_end_ms * 1_000_000, margin_policy=current_hl.margin_policy(max_mark_age_ns) if current_hl is not None else None)
        strategy_type = observed_strategy_type(WaveOverlayStrategy, risk_recorder)
    cover_hour_seed = ()
    cover_warmup_hashes = {}
    if research_sol_cover or research_conditional_sol or research_sol_risk_first:
        import csv
        warmup_root = Path(__file__).resolve().parents[3] / "reports/btc-split-sol-cover-20261018"
        paired = {}
        for symbol in ("BTCUSDT", "SOLUSDT"):
            source = warmup_root / f"data-warmup-{symbol}-1h.csv"
            cover_warmup_hashes[symbol] = sha256_file(source)
            with source.open() as handle:
                rows = list(csv.DictReader(handle))
            paired[symbol] = {int(r["open_time_ms"])+3_600_000: float(r["close"]) for r in rows
                              if int(r["open_time_ms"])+3_600_000 <= trading_start_ms}
        timestamps = sorted(set(paired["BTCUSDT"]) & set(paired["SOLUSDT"]))[-721:]
        if len(timestamps) != 721 or any(b-a != 3_600_000 for a,b in zip(timestamps,timestamps[1:])) or timestamps[-1] != trading_start_ms:
            raise ValueError("COVER_EXACT_720_HOURLY_RETURNS_REQUIRED")
        cover_hour_seed = tuple((t*1_000_000,paired["BTCUSDT"][t],paired["SOLUSDT"][t]) for t in timestamps)
    strategy = strategy_type(WaveOverlayStrategyConfig(
        btc_id=btc_instrument.id, sol_id=sol_instrument.id,
        btc_bar_type=kind(btc_instrument.id, PriceType.LAST), sol_bar_type=kind(sol_instrument.id, PriceType.LAST),
        btc_mark_data_type=venue_mark_data_type(btc_instrument.id), sol_mark_data_type=venue_mark_data_type(sol_instrument.id),
        mark_client_id=mark_client, active_seed=initial_active_seed,
        deposit_currency=str(btc_instrument.settlement_currency),
        native_hl_admission=current_hl is not None,
        native_hl_selected_leverage=current_hl.selected_leverage if current_hl is not None else (),
        margin_policy=current_hl.margin_policy(max_mark_age_ns) if current_hl is not None else TierMarginPolicy((), dict(selected_leverage), max_mark_age_ns), trading_start_open_ns=trading_start_ms * 1_000_000,
        terminal_close_at_ns=trading_end_ms * 1_000_000, candidate=candidate, seed_bars=seed_bars,
        research_portfolio_protect_45=research_portfolio_protect_45,
        research_btc_direction_sizing=research_btc_direction_sizing,
        research_btc_drawdown_sizing=research_btc_drawdown_sizing,
        research_v3_risk=research_v3_risk,
        research_h1_b1=research_h1_b1,
        research_btc_split50=research_btc_split50,
        research_btc_split_planref_v1=research_btc_split_planref_v1,
        research_btc_split_tp_ioc=research_btc_split_tp_ioc,
        research_btc_split_discount=Decimal(research_btc_split_discount),
        research_sol_btc_open_only=research_sol_btc_open_only,
        research_h4_ema=research_h4_ema, research_h4_gamma=Decimal(research_h4_gamma),
        research_h4_seed=h4_seed, research_h4_bar_type=h4_bar_type,
        research_residual_recovery=research_residual_recovery, research_c1_btc_cut_divisor=research_c1_btc_cut_divisor, research_c1_restore_dd=Decimal(research_c1_restore_dd), research_c1_first_fresh_h4=research_c1_first_fresh_h4, research_c1_btc_postcut_d1=research_c1_btc_postcut_d1, research_wait_4h=research_wait_4h, research_wait_persist=research_wait_persist,
        research_zero_retrace=research_zero_retrace, research_sol_dominant=research_sol_dominant, research_next_signals=next_bar_types,
        research_regime_reentry_band=Decimal(research_regime_reentry_band) if research_regime_reentry_band is not None else None,
        research_band_daily_seed=tuple(((t+DAY_MS)*1_000_000,float(r["high"]),float(r["low"])) for t,r in sorted(daily["BTCUSDT"].items()) if t+DAY_MS<=trading_start_ms) if research_regime_reentry_band is not None else (),
        research_sol_cover=Decimal(research_sol_cover) if research_sol_cover else None,
        research_conditional_sol=research_conditional_sol,
        research_sol_risk_first=research_sol_risk_first,
        research_immediate_sol=research_immediate_sol,
        research_immediate_lookback=research_immediate_lookback,
        research_alpha_cushion=research_alpha_cushion,
        research_chop_pair=research_chop_pair,
        research_carry_daily_seed=tuple(((t+DAY_MS)*1_000_000,float(r["high"]),float(r["low"])) for t,r in sorted(daily["BTCUSDT"].items()) if t+DAY_MS<=trading_start_ms) if research_chop_pair else (),
        research_cover_hour_seed=cover_hour_seed,
        research_confirmation_bars=confirmation_bars,
        research_btc_episode_loss_20=research_btc_episode_loss_20,
        research_sol_remaining_btc_hedge=research_sol_remaining_btc_hedge,
        research_sol_notional_cap_multiple=Decimal("6") if research_sol_notional_cap_6x else None,
        tp_fee_floor_v1=tp_fee_floor_v1, research_v0_execution_repairs=research_v0_execution_repairs, research_v0_zero_tp_netting=research_v0_zero_tp_netting, research_v0_deferred_selective_zero_tp=research_v0_deferred_selective_zero_tp, research_v0_selective_lifecycle_repairs=research_v0_selective_lifecycle_repairs, max_mark_age_ns=max_mark_age_ns,
        btc_signal_data_type=daily_signal_data_type(btc_instrument.id), sol_signal_data_type=daily_signal_data_type(sol_instrument.id), signal_client_id=signal_client,
        reporting_checkpoint_ns=_reporting_checkpoints(start_at, end_at),
        execution_delay_ns=(policy.execution_delay_minutes - 1) * MINUTE_MS * 1_000_000,
        execution_policy_hash=policy.hash,
        execution_policy_version=policy.version,
        **qualification_kwargs,
    ))
    engine.add_strategy(strategy)
    audit_archive = None
    if research_sol_risk_first == "alpha-corridor-v1":
        from coinmaster.research.native_audit import NativeAuditArchive
        audit_archive = NativeAuditArchive(artifacts_root / f"{artifact_label}-native-audit.sqlite", strategy)
    stats = {"expected_rows_per_source": expected_rows, "processed_rows_per_source": 0, "batch_count": 0, "event_count": 0, "max_batch_minutes": 0, "max_batch_events": 0, "cursor_batch_rows": cursor_batch_rows}
    spread = Decimal(policy.symmetric_adverse_spread_bps) / Decimal("10000")
    early_liquidation_cutoff = False
    def native_quote(instrument, close: str, precision: int, available_ns: int):
        mid = Decimal(str(close))
        if current_hl is not None:
            return instrument_quote(instrument,mid*(1-spread),mid*(1+spread),available_ns)
        return quote(instrument.id, f"{float(mid * (1 - spread)):.{precision}f}", f"{float(mid * (1 + spread)):.{precision}f}", available_ns, size_precision=instrument.size_precision)
    next_accumulators = {}
    successful_run = False
    # Research housekeeping only: bound live reports between archival receipts.
    archival_batch_minutes = min(weekly_batch_minutes, 15) if audit_archive is not None else weekly_batch_minutes
    try:
        for week in iter_weekly_minute_batches(iter_minute_bundles(data_root, trading_start_ms, trading_end_ms, cursor_batch_rows, require_exact_source_rows=(trading_start_ms, trading_end_ms) == (TRADING_START_MS, TRADING_END_MS)), archival_batch_minutes):
            if risk_recorder is not None:
                risk_recorder.set_week(week)
            if coherent_observer is not None:
                coherent_observer.set_week(week)
            marks, signals, quotes, source_bars, next_bars = [], [], [], [], []
            for minute in week:
                available_ns = (minute.open_time_ms + MINUTE_MS) * 1_000_000
                if research_h4_ema is not None or research_h1_b1 or research_sol_cover or research_conditional_sol or research_sol_risk_first or research_immediate_sol or research_alpha_cushion or research_chop_pair:
                    for instrument, row in ((btc_instrument, minute.btc_execution), (sol_instrument, minute.sol_execution)):
                        source_bars.append(Bar(minute_bars[instrument.id],
                            instrument.make_price(row["open"]), instrument.make_price(row["high"]),
                            instrument.make_price(row["low"]), instrument.make_price(row["close"]),
                            instrument.make_qty(0), available_ns, available_ns))
                if next_enabled:
                    for instrument,row,hours,kind in ((btc_instrument,minute.btc_execution,4,next_bar_types[0]),(sol_instrument,minute.sol_execution,1,next_bar_types[1]),*((((sol_instrument,minute.sol_execution,4,next_bar_types[2]),)) if research_residual_recovery else ())):
                        duration=hours*60*MINUTE_MS
                        key=(str(instrument.id),hours)
                        acc=next_accumulators.get(key)
                        if acc is None:
                            if minute.open_time_ms % duration:raise ValueError('NEXT_INCOMPLETE_CLOSED_BAR_START')
                            acc=next_accumulators[key]=dict(open=Decimal(row['open']),high=Decimal(row['high']),low=Decimal(row['low']),count=0,last_ms=minute.open_time_ms-MINUTE_MS)
                        if minute.open_time_ms!=acc['last_ms']+MINUTE_MS:raise ValueError('NEXT_CLOSED_BAR_GAP')
                        acc['count']+=1;acc['last_ms']=minute.open_time_ms;acc['high']=max(acc['high'],Decimal(row['high']));acc['low']=min(acc['low'],Decimal(row['low']))
                        if (minute.open_time_ms+MINUTE_MS)%duration==0:
                            if acc['count']!=hours*60:raise ValueError('NEXT_INCOMPLETE_CLOSED_BAR')
                            next_bars.append(next_closed_bar(instrument.id,hours,acc['open'],acc['high'],acc['low'],Decimal(row['close']),available_ns))
                            del next_accumulators[key]
                # Same timestamp ordering is marks -> daily signals -> quotes.
                marks.extend((venue_mark(btc_instrument.id, Decimal(str(minute.btc_mark["close"])), available_ns), venue_mark(sol_instrument.id, Decimal(str(minute.sol_mark["close"])), available_ns)))
                if include_daily_signals and (minute.open_time_ms + MINUTE_MS) % DAY_MS == 0:
                    daily_open = minute.open_time_ms + MINUTE_MS - DAY_MS
                    btc_daily, sol_daily = daily["BTCUSDT"][daily_open], daily["SOLUSDT"][daily_open]
                    signals.extend((daily_signal(btc_instrument.id, Decimal(str(btc_daily["open"])), Decimal(str(btc_daily["high"])), Decimal(str(btc_daily["low"])), Decimal(str(btc_daily["close"])), available_ns), daily_signal(sol_instrument.id, Decimal(str(sol_daily["open"])), Decimal(str(sol_daily["high"])), Decimal(str(sol_daily["low"])), Decimal(str(sol_daily["close"])), available_ns)))
                quotes.extend((native_quote(btc_instrument, minute.btc_execution["close"], 1, available_ns), native_quote(sol_instrument, minute.sol_execution["close"], 2, available_ns)))
            if source_bars:
                engine.add_data(source_bars, sort=False)
            engine.add_data(marks, client_id=mark_client, sort=False)
            if signals:
                engine.add_data(signals, client_id=signal_client, sort=False)
            if next_bars:
                engine.add_data(next_bars, client_id=signal_client, sort=False)
            engine.add_data(quotes, sort=False)
            engine.sort_data()
            engine.run(streaming=True)
            engine.clear_data()
            if audit_archive is not None:
                rss_before_archive = int(Path("/proc/self/statm").read_text().split()[1])*os.sysconf("SC_PAGE_SIZE")
                archival = audit_archive.capture(engine, available_ns)
                archival.update(processed_minutes=stats["processed_rows_per_source"] + len(week), last_available_ns=available_ns,
                    archival_batch_minutes=archival_batch_minutes, rss_before_archive=rss_before_archive, peak_rss_bytes=_peak_rss_bytes(),
                    rss_bytes=int(Path("/proc/self/statm").read_text().split()[1])*os.sysconf("SC_PAGE_SIZE"))
                save_diagnostic_report(data_root, archival, "batch-resource-latest", artifacts_root)
            stats["batch_count"] += 1
            stats["event_count"] += len(marks) + len(signals) + len(quotes)
            stats["max_batch_minutes"] = max(stats["max_batch_minutes"], len(week))
            stats["max_batch_events"] = max(stats["max_batch_events"], len(marks) + len(signals) + len(quotes))
            stats["processed_rows_per_source"] += len(week)
            if research_alpha_cushion:
                # Overwrite one bounded operational snapshot; never retain a
                # per-batch history or alter cache/order ownership.
                snapshot = dict(batch_count=stats["batch_count"], processed_minutes=stats["processed_rows_per_source"],
                    last_available_ns=(week[-1].open_time_ms + MINUTE_MS)*1_000_000,
                    weekly_batch_minutes=weekly_batch_minutes, cursor_batch_rows=cursor_batch_rows,
                    native_orders=len(engine.cache.orders()), native_positions=len(engine.cache.positions()),
                    strategy_order_audit=len(strategy._order_audit), native_fill_events=len(strategy.fill_audit),
                    seen_trade_ids=len(strategy._seen_trade_ids), alpha_audit_rows=len(strategy.alpha_cushion_audit),
                    alpha_audit_dropped=strategy._alpha_audit_dropped, peak_rss_bytes=_peak_rss_bytes(),
                    rss_bytes=int(Path("/proc/self/statm").read_text().split()[1])*os.sysconf("SC_PAGE_SIZE"))
                snapshot_path = artifacts_root / "batch-resource-latest.json"
                temporary = snapshot_path.with_suffix(".tmp")
                temporary.write_text(json.dumps(snapshot,sort_keys=True)+"\n")
                temporary.replace(snapshot_path)

            if stop_on_liquidation and strategy.liquidation_audit:
                early_liquidation_cutoff = True
                break
        engine.end()
        if coherent_observer is not None:
            coherent_observer_report = coherent_observer.finish_after_engine_end(trading_end_ms * 1_000_000)
        # Retain only one native report DataFrame at a time; native history
        # remains authoritative and report-derived monetary formulas are unchanged.
        if audit_archive is not None:
            from coinmaster.research.native_audit import CashRows, FillTimes
            audit_archive.capture(engine, available_ns, final=True)
            audit_archive.freeze()
            terminal_active = engine.cache.account_for_venue(SIM).balance_total().as_decimal()
            cash_account_series = CashRows(audit_archive)
            interval_cash_series = CashRows(audit_archive, start_at, end_at, initial_active_seed)
            interval_cash_terminal = Decimal(interval_cash_series[-1]["total"])
            cash_drawdown = standard_drawdown(interval_cash_series, initial_active_seed)
            artifacts = {kind: audit_archive.export_orders(artifacts_root / f"{artifact_label}-{kind}.csv", filled=kind=="fills")
                         for kind in ("orders", "fills")}
            native_fill_count = artifacts["fills"]["rows"]
            fees = Decimal("0")
            native_order_rejections = 0
            for (body,) in audit_archive.db.execute("SELECT payload FROM native WHERE kind='order'"):
                row = json.loads(body)
                native_order_rejections += "REJECTED" in row["status"]
                fees += sum((Decimal(str(value).split()[0]) for value in row.get("commissions", ())), Decimal("0"))
            fill_timestamps_ns = FillTimes(audit_archive)
            boundary_ns = trading_end_ms * 1_000_000
            boundary_fill_count = sum(timestamp == boundary_ns for timestamp in fill_timestamps_ns)
        else:
            account = engine.trader.generate_account_report(SIM)
            terminal_active = Decimal(str(account["total"].iloc[-1]))
            # Native report insertion order is not a reporting-time guarantee when
            # orders settle across streamed batches. Preserve chronological cash.
            cash_account_series = sorted(
                ({"timestamp": str(index), "active": str(value), "reserve": "0", "total": str(value)} for index, value in account["total"].items()),
                key=lambda row: datetime.fromisoformat(row["timestamp"]).astimezone(timezone.utc),
            )
            del account
            interval_cash_series = [{"timestamp": start_at.isoformat(), "active": str(initial_active_seed), "reserve": "0", "total": str(initial_active_seed)}] + [row for row in cash_account_series if start_at <= datetime.fromisoformat(row["timestamp"]).astimezone(timezone.utc) < end_at]
            interval_cash_terminal = Decimal(interval_cash_series[-1]["total"])
            cash_drawdown = standard_drawdown(interval_cash_series, initial_active_seed)
            fills = engine.trader.generate_order_fills_report()
            artifacts = {"fills": save_native_artifact(fills, artifacts_root / f"{artifact_label}-fills.csv")}
            native_fill_count = len(fills)
            fees = sum((Decimal(str(value).split()[0]) for row in fills.get("commissions", ()) for value in row), Decimal("0"))
            fill_timestamps_ns = [_fill_timestamp_ns(value) for value in fills.get("ts_last", ())]
            boundary_ns = trading_end_ms * 1_000_000
            boundary_fill_count = sum(timestamp == boundary_ns for timestamp in fill_timestamps_ns)
            del fills
            orders = engine.trader.generate_orders_report()
            artifacts["orders"] = save_native_artifact(orders, artifacts_root / f"{artifact_label}-orders.csv")
            native_order_rejections = sum("REJECTED" in str(value) for value in orders.get("status", ()))
            del orders
        adapter = strategy.reporting_state()
        save_diagnostic_report(data_root,{'raw_audit_state':'NATIVE_EXPORTS_COMPLETE_BEFORE_VALIDATION',
            'native_strategy_events':adapter,'native_order_events':strategy._order_audit,'native_risk_first_audit':strategy.risk_first_sol_audit,
            'native_carry_audit':strategy.carry_pair_audit,'native_carry_counts':strategy.carry_pair_counts,
            'native_alpha_audit':strategy.alpha_cushion_audit,'native_alpha_counts':strategy.alpha_cushion_counts,
            'execution_artifacts':artifacts,'native_fees':str(fees),'terminal_active':str(terminal_active)},
            artifact_label+'-raw-native',artifacts_root)
        terminal = adapter["terminal_lifecycle"]
        if terminal["reason"] == "TERMINAL_BOUNDARY_SETTLEMENT" and (
            terminal["status"] != "FLAT" or engine.cache.positions_open() or adapter["terminal_open_orders"]
        ):
            raise ValueError("TERMINAL_RECONCILIATION_INCOMPLETE")
        fee_attribution = native_fee_attribution(adapter["fill_audit"], fees)
        audit = journal.funding_audit() if journal else []
        manifest = data_root / "bybit-1m" / "manifest.json"
        full_config = {**BASELINE_CONFIG, "initial_total_usdt": str(initial_active_seed), "account": (BASELINE_CONFIG["account"] if initial_active_seed==Decimal("10000") else "SIM_MARGIN_USDT_DYNAMIC_SEED") if qualification_mode=="legacy_reference" else "SIM_MARGIN_USDT_DP55_QUALIFICATION", "candidate": asdict(candidate), "execution_policy": asdict(policy), "fixed_base_fee_policy": asdict(fee_policy), "fee_policy_hash": fee_policy.hash, "tp_fee_floor_v1": tp_fee_floor_v1, "deposit_protection": "DISABLED_IDENTICALLY_IN_RESEARCH" if qualification_mode=="legacy_reference" else "GLOBAL_DP55_NATIVE_USDT_M1", "qualification_mode": qualification_mode, "quantity_model": qualification_quantity_model, "lot_constraints": lot_constraints, "run_interval": {"start": start_at.isoformat(), "end_exclusive": end_at.isoformat(), "initial_active_seed": str(initial_active_seed)}}
        if research_v0_execution_repairs:
            full_config["research_v0_execution_repairs"] = True
            if not research_v0_zero_tp_netting:
                full_config["research_v0_zero_tp_netting"] = False
            if research_v0_deferred_selective_zero_tp:
                full_config["research_v0_deferred_selective_zero_tp"] = True
        if research_v0_selective_lifecycle_repairs:
            full_config["research_v0_selective_lifecycle_repairs"] = True
        stats["peak_rss_bytes"] = _peak_rss_bytes()
        authoritative_liquidation = bool(adapter["liquidations"]) and bool(adapter["liquidation_lockout"])
        if research_residual_recovery:
            full_config["residual_recovery_research"]=dict(version="C1",trigger_DD="0.40",open_loss_dominates_remaining_50_cushion=True,cut_fraction="0.50",restore_DD="0.35",restore_closed_hours=4,max_cut_restore_per_group=1)
        if research_c1_restore_dd != "0.35":
            full_config["residual_recovery_research"]["restore_DD"]=research_c1_restore_dd
        if research_c1_btc_cut_divisor != 2:
            full_config["residual_recovery_research"]["btc_cut_divisor"]=research_c1_btc_cut_divisor
        if next_enabled:
            full_config["next_band_research"] = dict(wait_4h=research_wait_4h,wait_persist=research_wait_persist,zero_retrace=research_zero_retrace,sol_dominant=research_sol_dominant,bar_contract="PINNED_CLOSED_OHLC_D1_BEFORE_INTRADAY_QUOTE")
        if research_sol_btc_open_only or research_h4_ema is not None or research_regime_reentry_band is not None:
            full_config["hedge_band_research"] = dict(c0=research_sol_btc_open_only, h4_ema=research_h4_ema,
                h4_gamma=research_h4_gamma, h4_warmup_sha256=h4_warmup_hash, regime_reentry_band=research_regime_reentry_band,
                beta="LATEST_ACCEPTED_DAILY_LOG_RETURN_270_FREEZE_AT_ACTIVATION", ttl_ns=14_400_000_000_000,
                atr="WILDER14_ORIGINAL_DAILY_OHLC_SEED", execution="EXISTING_NATIVE_ONLY")
        if research_h1_b1:
            full_config["research_h1_b1"] = {"variant": research_h1_b1, "direction_sizing": {"long": "5.5", "short": "7.875"},
                "confirmation": "NATIVE_INTERNAL_15M_OR_1H_CLOSE_PREVIOUS_HIGH_LOW", "bar_execution": False, "native_bar_cache_capacity_per_type": 128, "build_empty_bars": False,
                "warmup": "NATURAL_TWO_CLOSED_BARS_NO_DAILY_OHLC_SYNTHESIS", "execution": "CURRENT_NATIVE_QUOTE_ONLY",
                "h1_rules": {"adverse_strict_fraction": "0.025", "stage1_remaining_btc_notional_fraction": "0.5",
                    "beta": "CURRENT_VALID_DAILY_BETA_FREEZE_AT_FIRST_NATIVE_FILL", "stage2": "ONCE_SAME_ACTUAL_STAGE1_QUANTITY_AFTER_POST_FIRST_FILL_TP_AND_NEW_CONFIRMATION",
                    "remaining_btc_stage2_cap": False, "btc_partial_trim": False, "recovery_fraction": "0.01",
                    "recovery_confirmation": "FRESH_REVERSE_SOL_1H", "max_holding_days": 14,
                    "btc_flat_sol_flat": True, "closed_cycle_reentry": False} if research_h1_b1 == "h1" else None}
        if research_v3_risk:
            full_config["research_v3_risk"] = {"variant": research_v3_risk, "direction_sizing": {"long": "5.5", "short": "7.875"}, "sampling": "CAUSAL_PAIRED_PREQUOTE_AFTER_OBSERVATION", "execution": "CURRENT_NATIVE_QUOTE_ONLY", "signed_funding": "SEPARATE_UNKNOWN"}
        if research_portfolio_protect_45:
            full_config["research_portfolio_protect_45"] = {"fraction": "0.45", "resume": "NEXT_NATIVE_FLAT_FRESH_DAILY_DOMAIN_EPISODE", "peak_reset": "PROTECTIVE_ONLY", "sampling": "AFTER_PREQUOTE_CAPTURE_BEFORE_EXECUTION_QUOTES", "execution": "EXISTING_FORCED_EXIT_MAY_MATCH_PREVIOUS_BOOK_ON_CANCEL_ACK"}
        if research_sol_notional_cap_6x:
            full_config["research_sol_notional_cap_multiple"] = "6"
        if research_btc_direction_sizing:
            full_config["research_btc_direction_sizing"] = {"long": "5.5", "short": "7.875", "freeze": "GENUINE_EPISODE_CREATION"}
        if research_btc_drawdown_sizing:
            full_config["research_btc_drawdown_sizing"] = {"normal": "7.875", "reduced": "3.9375", "enter_drawdown": "0.25", "resume_drawdown": "0.15",
                "sampling": "NATIVE_PAIRED_MINUTE_PRE_SIGNAL_PRE_QUOTE", "global_peak_seed": str(initial_active_seed), "peak_reset": False, "freeze": "GENUINE_EPISODE_CREATION", "held_reduction": False}
        if research_btc_episode_loss_20:
            full_config["research_btc_episode_loss_20"] = {"loss_fraction": "0.20", "basis": "FIRST_CONFIRMED_BTC_FILL_NATIVE_PORTFOLIO_EQUITY", "pnl": "NATIVE_REALIZED_INCLUDES_FEES_PLUS_HELD_UNREALIZED", "scope": "GROUP_CLOSE", "global_peak_reset": False}
        if research_sol_remaining_btc_hedge:
            full_config["research_sol_remaining_btc_hedge"] = {
                "target": "MAX_ZERO_ACTUAL_REMAINING_BTC_MARK_NOTIONAL_DIV_VALID_BETA_ENTRY_MINUS_AGGREGATE_HELD_SOL_MARK_NOTIONAL",
                "budget": "UNUSED_EARNED_ORIGINAL_RIGHT_ONLY",
                "pending_policy": "SERIALIZE_ANY_OWNED_SOL_OPENING_ORDER_OR_UNRESOLVED_SOL_ADD_SUBMISSION",
                "held_rebalance": False,
                "beta_entry_open_interval": ["0.2", "4"],
            }
        if current_hl is not None:
            full_config.update(venue="hyperliquid",account="NATIVE_HL_USDC_CURRENT_RULES_DIAGNOSTIC",
                accounting_currency="USDC",initial_total_usdc=str(initial_active_seed),
                tier_assumption="FROZEN_CURRENT_PUBLIC_HL_TIERS_HISTORICAL_APPLICABILITY_UNPROVEN",
                deposit_protection="DISABLED_CLEAN_EXECUTION_DIAGNOSTIC_ONLY",current_hl_profile=current_hl.evidence,
                full_fill_assumption="ZERO_MARKET_IMPACT_FULL_FILL_DIAGNOSTIC",maker_touch_fill=False,
                admission_core="SHARED_USDC_EXPOSURE_COST_CORE",venue_availability="UNOBSERVED_HISTORICALLY;ADDITIONAL_MANDATORY_LIVE_GATE")
            full_config.pop("initial_total_usdt",None)
        result = {"status": "LIQUIDATED_EARLY_CUTOFF" if early_liquidation_cutoff or authoritative_liquidation else "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible": False, "interval": f"[{start_at.isoformat()},{end_at.isoformat()})", "run_interval": full_config["run_interval"], "warmup": f"[{datetime.fromtimestamp(warmup_start_ms / 1000, tz=timezone.utc).isoformat()},{start_at.isoformat()}) feature-only", "config": full_config, "config_hash": hashlib.sha256(json.dumps(full_config, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), "data_hash": hashlib.sha256(json.dumps(json.loads(manifest.read_text()), sort_keys=True, separators=(",", ":")).encode()).hexdigest(), "code_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "policy": asdict(policy), "policy_hash": policy.hash, "streaming": stats, "summary": {"objective": "POST_BOUNDARY_SETTLED_NATIVE_CASH_ACTIVE_PLUS_RESERVE", "roi": str((terminal_active / initial_active_seed) - 1), "terminal_total": str(terminal_active), "interval_cash_terminal_total": str(interval_cash_terminal), "monthly_returns_basis": "NATIVE_CASH_ACCOUNT_INTERVAL_EXCLUDING_POST_BOUNDARY_SETTLEMENT", "max_drawdown_amount": cash_drawdown["amount"], "max_drawdown_percent": cash_drawdown["percent"], "drawdown_start": cash_drawdown["start"], "drawdown_trough": cash_drawdown["trough"], "drawdown_basis": cash_drawdown["basis"], "drawdown_recovery": "UNKNOWN_NOT_RECOVERED_OR_NOT_EXPORTED", "monthly_returns": monthly_returns(interval_cash_series, initial_active_seed)}, "cash_account_series": cash_account_series, "interval_cash_account_series": interval_cash_series, "marked_equity_series": {"status": "PARTIAL_NATIVE_MARKED_CHECKPOINTS_ONLY", "checkpoints": adapter["marked_equity_checkpoints"], "monthly_returns": "UNKNOWN_NOT_RECONCILED_TO_POST_BOUNDARY_SETTLED_CASH_OBJECTIVE"}, "fills": native_fill_count, "fill_timestamps_ns": fill_timestamps_ns, "fill_audit": adapter["fill_audit"], "entry_sizing_audit": adapter["entry_sizing_audit"], "fee_attribution": fee_attribution, "execution_artifacts": artifacts, "native_fees": str(fees), "native_order_rejections": native_order_rejections, "pre_submit_tier_margin_gate_blocks": adapter["pre_submit_tier_margin_gate_blocks"], "funding": {"count": len(audit), "signed_amount": "UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA"}, "funding_journal": str(journal_path) if journal else None, "liquidation_count": len(adapter["liquidations"]), "liquidation_value": str(sum((Decimal(item["close_value"]) for item in adapter["liquidations"]), Decimal("0"))), "liquidation_audit": adapter["liquidations"], "liquidation_lockout": adapter["liquidation_lockout"], "terminal_lifecycle": adapter["terminal_lifecycle"], "post_boundary_settlement": {"convention": "TERMINAL_FILLS_AT_END_EXCLUSIVE_REPORTED_SEPARATELY_EXCLUDED_FROM_INTERVAL_RETURNS", "boundary_timestamp": end_at.isoformat(), "fill_count": boundary_fill_count, "settled_cash_total": str(terminal_active), "interval_cash_total_before_settlement": str(interval_cash_terminal)}, "early_liquidation_cutoff": early_liquidation_cutoff or authoritative_liquidation, "terminal_active": str(terminal_active), "terminal_reserve": "0", "terminal_total": str(terminal_active), "terminal_open_positions": len(engine.cache.positions_open()), "limitations": ["1m close proxy has no BBO/L2/slippage/liquidity evidence", "Owner-specified non-VIP fixed-base fees are diagnostic; historical applicability remains unknown", "Venue marks are CustomData and do not participate in matching", "Historical liquidation and funding settlement marks are unvalidated"]}
        if research_sol_btc_open_only or research_h4_ema is not None or research_regime_reentry_band is not None:
            result["hedge_band_audit"] = strategy.hedge_band_audit
        if research_residual_recovery:
            result["coherent_native_observer"] = coherent_observer_report
            result["funding_cash_audit"] = journal.funding_cash_audit() if journal else []
            result["funding"]["signed_amount"] = str(sum((Decimal(row[5]) for row in result["funding_cash_audit"]),Decimal(0)))
            from coinmaster.research.native_accounting import native_position_lifecycles
            lifecycle_export=native_position_lifecycles(engine.cache)
            native_realized=lifecycle_export["positions"]
            complete=not lifecycle_export["unknown"] and all(row["realized_pnl"] is not None and row["closed"] for row in native_realized) and not engine.cache.positions_open()
            realized_total=sum((Decimal(row["realized_pnl"]) for row in native_realized),Decimal(0)) if complete else None
            bridge=terminal_active-initial_active_seed-realized_total-Decimal(result["funding"]["signed_amount"]) if complete else None
            result["native_cash_reconciliation"]=dict(terminal_cash=str(terminal_active),seed=str(initial_active_seed),
                native_position_lifecycle_export=lifecycle_export,native_position_realized=native_realized,native_realized_total=str(realized_total) if complete else None,
                signed_funding=result["funding"]["signed_amount"],unallocated_bridge=str(bridge) if complete else None,
                status="EXACT" if bridge==0 else "UNKNOWN_UNALLOCATED_NATIVE_BRIDGE",
                fees_policy="NATIVE_POSITION_REALIZED_PNL_ALREADY_INCLUDES_NATIVE_COMMISSIONS_DO_NOT_SUBTRACT_AGAIN",
                bridge_is_funding=False,tolerance=None,actual_native_cash_transitions=(coherent_observer_report or {}).get("native_cash_transitions"))
            result["c1_audit"]=strategy.c1_audit
            result["c1_denial_counts"]=strategy.c1_denials
            result["c1_terminal_state"]=strategy._c1_export_terminal()
        if next_enabled:
            result["next_band_audit"] = strategy.next_band_audit
        result.update({
            "episodes": "UNKNOWN_NATIVE_DOMAIN_EPISODE_AUDIT_NOT_EXPORTED",
            "realized_unrealized": "UNKNOWN_NATIVE_ACCOUNT_REPORT_ONLY",
            "modeled_slippage": policy.spread_slippage_liquidity,
            "transfers": "0",
            "funding": {
                "count": len(audit),
                "by_instrument_count": {instrument: sum(1 for row in audit if row[1] == instrument) for instrument in sorted({row[1] for row in audit})},
                "signed_amount": result["funding"]["signed_amount"] if research_residual_recovery else "UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA",
            },
        })
        if research_v0_execution_repairs:
            coinmaster_root = Path(__import__("coinmaster").__file__).resolve().parent
            result["source_hashes"] = {
                name: hashlib.sha256((coinmaster_root / relative).read_bytes()).hexdigest()
                for name, relative in (
                    ("native_baseline", "research/native_baseline.py"),
                    ("effective_research_config", "research/effective_config.py"),
                    ("qualification_policy", "research/qualification_policy.py"),
                    ("wave_domain", "domain/wave_overlay.py"),
                    ("wave_strategy", "strategy/wave_overlay.py"), ("next_band", "strategy/next_band.py"), *(((("residual_recovery", "strategy/residual_recovery.py"),)) if research_residual_recovery else ()),
                    *(((("hedge_band", "strategy/hedge_band.py"),)) if research_sol_btc_open_only or research_h4_ema is not None or research_regime_reentry_band is not None else ()),
                )
            }
        if research_residual_recovery:
            coinmaster_root=Path(__import__("coinmaster").__file__).resolve().parent
            result.setdefault("source_hashes",{}).update({name:hashlib.sha256((coinmaster_root/relative).read_bytes()).hexdigest() for name,relative in (
                ("native_accounting","research/native_accounting.py"),("paired_observer","research/paired_observer.py"),
                ("funding_fixture","research/native_fixture.py"),("native_journal","ledger/journal.py"))})
        # Preserve native facts before any boundary/metadata packaging assertion.
        if qualification_mode=="live_qualification":
            result["deposit_protection_projection"]=strategy.deposit_projection()
            result["deposit_protection_durable"]=qualification_deposit_runtime.deposit_protection_state(
                instance_id=qualification_deposit_runtime.owner,account_id=qualification_deposit_account_id)
        raw_native={**result,'native_strategy_events':strategy.reporting_state(),'native_order_events':strategy._order_audit,
            'native_risk_first_audit':strategy.risk_first_sol_audit,
            'native_carry_audit':strategy.carry_pair_audit,'native_carry_counts':strategy.carry_pair_counts,
            'native_alpha_audit':strategy.alpha_cushion_audit,'native_alpha_counts':strategy.alpha_cushion_counts,
            'raw_audit_state':'NATIVE_COMPLETE_PACKAGING_NOT_VALIDATED'}
        save_diagnostic_report(data_root,raw_native,artifact_label+'-raw-native',artifacts_root)
        if qualification_mode=="live_qualification":
            if strategy._deposit.latched:
                if (strategy._deposit.exit_state!="TRIPPED_FLAT" or engine.cache.positions_open()
                    or engine.cache.orders_open() or engine.cache.orders_inflight()
                    or result["deposit_protection_durable"]!=strategy._deposit.durable()):
                    raise ValueError("QUALIFICATION_DP_NATIVE_TERMINAL_FLAT_REQUIRED")
                if (stats["processed_rows_per_source"]!=expected_rows or coherent_observer_report is None or coherent_observer_report["status"]!="PASS"
                    or coherent_observer_report["end_exclusive_ns"]!=str(trading_end_ms*1_000_000)):
                    raise ValueError("DP_CALENDAR_REQUIRES_COMPLETE_NATIVE_WATERMARKS")
                from coinmaster.research.qualification_policy import verified_flat_calendar_returns
                result["raw_account_change_months"]=result["summary"]["monthly_returns"]
                result["summary"]["monthly_returns"]=verified_flat_calendar_returns(
                    interval_cash_series,initial_active_seed,start_at,end_at,terminal_active)
                result["summary"]["monthly_returns_basis"]="NATIVE_CASH_MUTATIONS_WITH_VERIFIED_FLAT_TERMINAL_WATERMARK_CARRY_FORWARD"
                result["continued_trading_after_DP_pause"]=False
        if not early_liquidation_cutoff:
            assert_report_boundaries(result)
        if research_btc_split50 or research_sol_cover or research_conditional_sol:
            result["split_cover_audit"] = strategy._split_cover_report()
            result["config"]["research_btc_split50"] = research_btc_split50
            result["config"]["research_btc_split_planref_v1"] = research_btc_split_planref_v1
            result["config"]["research_btc_split_tp_ioc"] = research_btc_split_tp_ioc
            result["config"]["positive_tp_ioc_policy"] = "COMPLETED_PARENT_CROSSED_POSITIVE_TARGET_NATIVE_IOC_ACTUAL_TAKER" if research_btc_split_tp_ioc else "OFF"
            result["config"]["btc_management_reference_policy"] = "FIRST_LEG_COMPLETED_ACTUAL_VWAP_PLANREF_V1" if research_btc_split_planref_v1 else "ACTUAL_AGGREGATE_VWAP"
            result["config"]["research_btc_split_discount"] = research_btc_split_discount
            result["config"]["research_sol_cover"] = research_sol_cover
            result["config"]["research_conditional_sol"] = research_conditional_sol
            if research_conditional_sol:
                result["conditional_sol_audit"] = strategy.conditional_audit
                result["source_hashes"]["conditional_hedge"] = sha256_file(Path(__import__("coinmaster").__file__).resolve().parent/"strategy/conditional_hedge.py")
                result["config"]["conditional_sol_policy"] = {"arm":">0.02_actual_blended_BTC_VWAP","off":"<=0.01_immediate_fresh_BTC_mark","confirmation":"POST_ARM_CLOSED_SOL15m_OR1h_PREVIOUS_BAR_BREAK_NEXT_FRESH_QUOTE","coverage":"0.50_actual_BTC_beta720completed1H_frozen","quantity_cadence":"LATCH_ACTIVATION_AND_ACTUAL_BTC_QUANTITY_CHANGE_ONLY_NO_PRICE_ONLY_REBALANCE","net_target":"MAX_ORIGINAL_AUTHORIZED_REMAINING_AND_CONDITIONAL","ownership_transfer":"SEPARATE_AUTHORIZATION_CREDIT_NO_NATIVE_FILL_OR_PNL"}
            if research_immediate_sol:
                result["config"]["research_immediate_sol"]=research_immediate_sol
                result["config"]["research_immediate_lookback"]=research_immediate_lookback
                result["config"]["immediate_insurance_policy"]={"coefficient":"PURE_SAMPLE_DAILY_VOLRATIO_ROLLING_W_CLOSED_DAYS_FROZEN_FIRST_BTC_FILL","original_SOL":"OFF","target":"ACTUAL_REMAINING_BTC_VOLRATIO_LATCH_ON_FILL_OR_AUTHORIZED_FRACTION","confirm":"CLOSED_SOL_15M_OR_1H_PREVIOUS_BAR_BREAK_THEN_FRESH_QUOTE","funding_components":"UNKNOWN","retry":"KNOWN_ADD_DENIAL_NEXT_MINUTE_NO_RECURSION","BTC":"SELECTED_RULES_UNCHANGED"}
                result["source_hashes"]["immediate_insurance"]=sha256_file(Path(__import__("coinmaster").__file__).resolve().parent/"strategy/immediate_insurance.py")
                result["immediate_sol_insurance_audit"]=strategy.insurance_audit
                result["immediate_sol_insurance_cycles"]=strategy._insurance_report()["cycles"]
                result["immediate_daily_sources"]={symbol:sha256_file(data_root/"normalized"/f"bybit-{symbol}-daily.parquet") for symbol in ("BTCUSDT","SOLUSDT")}
            if research_sol_risk_first:
                result["config"]["research_sol_risk_first"]=research_sol_risk_first
                result["config"]["risk_first_sol_policy"]={"variant":research_sol_risk_first,"old_conditional":"OFF","risk_excess_exit":"NATIVE_MARKET_IOC_NO_SYNTHETIC_PROFIT_FLOOR","cap50":"FROZEN720H_BETA_ACTUAL_BTC_QTY_ONLY_NO_AUTOFILL_BTCFLAT_ORIGINAL_RETAINED","dd_cov":"GLOBAL_NATIVE_HIGHWATER_10_20_30_UP_5_15_25_DOWN_34_67_100_MINVAR720H_FACTOR_HOURLY_BUFFER10","dd_cov_target":"min((1-w)*Oref,Olive)+w*Qc;lowerstage/BTCflat_latched_noincrease_until_fresh_Oauth/BTCincrease/higherstage","split_atr":"FIXED_Q_34_33_33_WILDER_ATR14_CLOSED15M_FIRST_ACTUAL_FILL_0.5_1ATR_60MIN_OR_BTC1PP_CANCEL_ACK_ACTUAL_LEAVES","split_atr_invalid":"ORDINARY_NATIVE_IOC","original_execution_change":"H2_ACCEPTED_GROUP_PERSISTS_KNOWN_CHILD_IOC_PARTIAL_TERMINAL_UNTIL_PRIORITY_EXIT_OR_LAWFUL_TTL_COMPLETION"}
                result["risk_first_sol_audit"]=strategy.risk_first_sol_audit
                result["risk_first_sol_parents"]=strategy._risk_first_report()["SOL_parents"]
                if research_sol_risk_first=="alpha-corridor-v1":
                    result["corridor_status_counts"]=getattr(strategy,"_rf_corridor_counts",{})
                    result["config"]["risk_first_sol_policy"]={"variant":"ALPHA-CORRIDOR-v1","risk_window":90,"E_H":"FINAL_POST_SOL_NATIVE_CHECKPOINT","floor":".55_GLOBAL_H_NO_RESET","objective":"NEAREST_LAWFUL_ALPHA_CONVEX_NATIVE_LOTS","failure":"EXPLICIT_MIN_L_BEST_EFFORT_NO_BTC_CHANGE","funding_L2":"UNKNOWN"}
                result["source_hashes"]["risk_first_sol"]=sha256_file(Path(__import__("coinmaster").__file__).resolve().parent/"strategy/risk_first_sol.py")
            result["config"]["cover_hour_warmup_sha256"] = cover_warmup_hashes
            result["config_hash"] = hashlib.sha256(json.dumps(result["config"],sort_keys=True,separators=(",",":")).encode()).hexdigest()
            result["source_hashes"]["split_cover"] = sha256_file(Path(__import__("coinmaster").__file__).resolve().parent/"strategy/split_cover.py")
        if research_chop_pair:
            result["config"]["research_chop_pair"]=True
            result["carry_pair_audit"]=strategy.carry_pair_audit
            result["carry_pair_counts"]=strategy.carry_pair_counts
            result["carry_pair_policy"]={"name":"CHOP_PAIR_50_NET_v1","recovery_label":"REMAINING_INVENTORY_NOT_WHOLE_EPISODE","funding":"UNCHANGED_NATIVE_POSTINGS_ONLY","daily_atr":"EMA_TR_ALPHA_2_15_CAUSAL_SEED","range":"7_CLOSED_DAILY_TWO_CONSECUTIVE_SAME_BOUNDARY_1H"}
            result["source_hashes"]["carry_pair"]=sha256_file(Path(__import__("coinmaster").__file__).resolve().parent/"strategy/carry_pair.py")
            result["config_hash"]=hashlib.sha256(json.dumps(result["config"],sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if research_alpha_cushion:
            result["config"]["research_alpha_cushion"]=True
            result["research_housekeeping"]={"native_run_analysis":False,"export":"SEQUENTIAL_UNCHANGED_NATIVE_REPORTS","economic_policy_change":False}
            result["config"]["alpha_cushion_policy"]={"window":90,"floor":".55GLOBAL_NATIVE_PEAK","costs":"KNOWN_PINNED_NATIVE_PROXY_TAKER;FUTURE_FUNDING_REAL_L2_UNKNOWN","BTCflat":"SOL_TARGET_ZERO_WITHOUT_EPISODE_RESET","original_alpha":"KEEP_IF_WHOLE_BUDGET_VALID;RISK_RETIRED_AUTHORITY_NO_RESURRECTION"}
            result["alpha_cushion_audit"]=strategy.alpha_cushion_audit
            result["alpha_cushion_audit_counts"]=strategy.alpha_cushion_counts
            result["alpha_cushion_audit_sampling"]={"diagnostic_sample_cap":4096,"diagnostic_sample_rows":strategy._alpha_sampled_rows,"diagnostic_rows_dropped":strategy._alpha_audit_dropped,"all_beta_and_daily_stress_rows_retained":True}
            result["alpha_cushion_native_peak_validation"]={"basis":"EXISTING_MINUTE_RECORDER_NATIVE_EQUITY_STATE_ONLY","initial_seed":str(initial_active_seed),"samples":strategy._alpha_observer_samples,"peak_updates":strategy._alpha_peak_updates,"peak_decreases":strategy._alpha_peak_decreases,"final_peak":str(strategy._alpha_peak),"last_equity_sample":str(strategy._alpha_equity)}
            result["source_hashes"]["alpha_cushion"]=sha256_file(Path(__import__("coinmaster").__file__).resolve().parent/"strategy/alpha_cushion.py")
            result["config_hash"]=hashlib.sha256(json.dumps(result["config"],sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if research_h1_b1:
            result["h1_b1_audit"] = strategy.h1_b1_audit
        if research_v3_risk:
            result["v3_risk_audit"] = strategy.v3_risk_audit
            result["btc_sizing_audit"] = strategy.btc_sizing_audit
        if research_portfolio_protect_45:
            result["research_protection_audit"] = strategy.research_protection_audit
        if research_sol_notional_cap_6x:
            result["sol_cap_admission_audit"] = strategy.sol_cap_admission_audit
        if research_btc_direction_sizing or research_btc_drawdown_sizing:
            result["btc_sizing_audit"] = strategy.btc_sizing_audit
        if research_btc_episode_loss_20:
            result["btc_episode_loss_audit"] = strategy.btc_episode_loss_audit
        if research_sol_remaining_btc_hedge:
            result["sol_hedge_admission_audit"] = strategy.sol_hedge_admission_audit
        if risk_recorder is not None:
            result["minute_risk_observations"] = risk_recorder.close()
            risk_recorder = None
        save_diagnostic_report(data_root,{**raw_native,**result,'raw_audit_state':'NATIVE_COMPLETE_BEFORE_WRAPPER_METADATA'},artifact_label+'-raw-native',artifacts_root)
        if audit_archive is not None:
            from coinmaster.research.native_audit import audit_json_default
            result = json.loads(json.dumps(result, default=audit_json_default))
        successful_run = True
        return result
    finally:
        _finalize_native_resources(audit_archive=audit_archive,risk_recorder=risk_recorder,
            coherent_observer=coherent_observer,engine=engine,journal=journal,
            successful_run=successful_run,journal_attempt_path=journal_attempt_path,journal_path=journal_path,
            primary_error=os.sys.exc_info()[1])


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


def save_diagnostic_report(data_root: Path, report: dict, artifact_name: str = "native-diagnostic-report", artifact_dir: Path | None = None) -> Path:
    """Persist a diagnostic artifact without promoting it to baseline evidence."""
    target = (artifact_dir or data_root / "runs") / f"{artifact_name}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    with temporary.open('w') as stream:
        from coinmaster.research.native_audit import audit_json_default
        stream.write(json.dumps(report, indent=2, sort_keys=True, default=audit_json_default) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(target)
    return target


def _emit(kind: str, **body) -> None:
    print(json.dumps({"type": kind, **body}, sort_keys=True), flush=True)


def _candidate_from_job_config(config: dict):
    """Map every configurable native Candidate field or reject before run."""
    from coinmaster.domain.wave_overlay import Candidate
    if config.get("venue") not in (None, "bybit"):
        raise ValueError("UNMAPPABLE_CONFIG:venue")
    expected = {
        "strategy_id": "btc_sol_wave_overlay_v1", "mode": "paper", "live_enabled": False,
        "initial_total_usdt": "10000", "initial_active_fraction": 1.0, "signal_timeframe": "1D",
        "regime": "close_vs_ema", "include_zero_waves": True, "sol_direction": "opposite_btc",
        "sol_entry_eligibility": "persistent_after_btc_level", "freeze_sigma_on_first_sol_fill": True,
        "sol_z_stop": None, "btc_close_stop_fraction": None, "portfolio_loss_limit_fraction": None,
        "future_sol_margin_fraction": 0.0, "insufficient_margin": "reject", "reserve_transfer_fraction": 0.0,
        "reserve_trigger_multiple": 4.0, "restart_target": "initial_active_seed",
        "post_liquidation": "restart_from_reserve_else_pause", "max_gross_to_active": 50.0,
    }
    for field, value in expected.items():
        if config.get(field) != value:
            raise ValueError(f"UNMAPPABLE_CONFIG:{field}")
    return Candidate(
        ema_period=config["ema_period"], beta_days=config["beta_days"], relative_days=config["relative_days"],
        z_history_days=config["z_history_days"], wave_history_days=config["wave_history_days"], wave_min_count=config["wave_min_count"],
        wave_quantiles=tuple(config["wave_quantiles"]), btc_tp_fractions_initial_qty=tuple(config["btc_tp_fractions_initial_qty"]),
        btc_notional_multiplier=config["btc_notional_multiplier"], max_parent_notional=float(config["max_parent_notional"]),
        sol_size_multipliers_h=tuple(config["sol_size_multipliers_H"]), sol_entry_z=tuple(config["sol_entry_z"]),
        sol_exit_half_z=config["sol_exit_half_z"], sol_exit_all_z=config["sol_exit_all_z"], sol_max_holding_days=config["sol_max_holding_days"],
        btc_close_trail_fraction=config["btc_close_trail_fraction"],
    )


def run_job_request(path: Path) -> int:
    request = json.loads(path.read_text())
    required = {"request_hash", "config_hash", "config", "data_root", "artifact_dir", "launch_permit", "launch_owner_token"}
    if "bounded_interval" in request:
        required |= {"source_manifest_sha256"}
    if not required <= set(request) or ("source_manifest_sha256" in request and "bounded_interval" not in request):
        _emit("result", status="FAILED", evidence=["INVALID_JOB_REQUEST"])
        return 1
    signed_keys = ("config_hash", "config", "data_root", "artifact_dir", "launch_permit", "launch_owner_token")
    if "bounded_interval" in request:
        signed_keys += ("bounded_interval", "source_manifest_sha256")
    canonical = json.dumps({key: request[key] for key in signed_keys}, sort_keys=True, separators=(",", ":"))
    if hashlib.sha256(canonical.encode()).hexdigest() != request["request_hash"]:
        _emit("result", status="FAILED", request_hash=request["request_hash"], config_hash=request["config_hash"], evidence=["REQUEST_HASH_MISMATCH"])
        return 1
    if hashlib.sha256(json.dumps(request["config"], sort_keys=True, separators=(",", ":")).encode()).hexdigest() != request["config_hash"]:
        _emit("result", status="FAILED", request_hash=request["request_hash"], config_hash=request["config_hash"], evidence=["CONFIG_HASH_MISMATCH"])
        return 1
    if not wait_for_launch_permit(request):
        return 1
    try:
        candidate = _candidate_from_job_config(request["config"])
    except (KeyError, TypeError, ValueError) as error:
        _emit("result", status="BLOCKED", request_hash=request["request_hash"], config_hash=request["config_hash"], blockers=[str(error)])
        return 2
    data_root, artifact_dir = Path(request["data_root"]), Path(request["artifact_dir"])
    bounded = request.get("bounded_interval")
    if "bounded_interval" in request:
        from coinmaster.research.optimizer_job import config_blockers, source_blockers
        try:
            start_ms, end_ms = validate_bounded_interval(bounded)
        except ValueError as error:
            _emit("result", status="BLOCKED", request_hash=request["request_hash"], config_hash=request["config_hash"], blockers=[str(error)])
            return 2
        source_errors, source_hash = source_blockers(data_root)
        blockers = [*config_blockers(request["config"]), *source_errors]
        if source_hash != request["source_manifest_sha256"]:
            blockers.append("SOURCE_MANIFEST_CHANGED")
        if request.get("test_options") is not None:
            blockers.append("BOUNDED_TEST_OPTIONS_FORBIDDEN")
    else:
        start_ms = end_ms = None
        blockers = coverage_blockers(data_root)
    if blockers:
        _emit("result", status="BLOCKED", request_hash=request["request_hash"], config_hash=request["config_hash"], blockers=blockers)
        return 2
    _emit("progress", request_hash=request["request_hash"], config_hash=request["config_hash"], progress=1)
    options = request.get("test_options") or {}
    try:
        report = run_native_diagnostic(
            data_root, include_funding=options.get("include_funding", True), candidate=candidate, artifact_dir=artifact_dir, artifact_label="result",
            **({"trading_start_ms": start_ms, "trading_end_ms": end_ms} if bounded is not None else {"warmup_start_ms": options["warmup_start_ms"], "trading_start_ms": options["trading_start_ms"], "trading_end_ms": options["trading_end_ms"], "weekly_batch_minutes": options.get("weekly_batch_minutes", WEEK_MINUTES), "cursor_batch_rows": options.get("cursor_batch_rows", WEEK_MINUTES)} if options else {}),
        )
        if bounded is not None:
            report["source_manifest_sha256"] = request["source_manifest_sha256"]
            report["bounded_interval"] = bounded
        artifact = save_diagnostic_report(data_root, report, "result", artifact_dir)
        envelope = {"type": "result", "status": "COMPLETED", "request_hash": request["request_hash"], "config_hash": request["config_hash"], "artifact": str(artifact), "artifact_sha256": sha256_file(artifact), "summary": report_summary(report)}
        (artifact_dir / "result-envelope.json").write_text(json.dumps(envelope, sort_keys=True) + "\n")
        _emit("progress", request_hash=request["request_hash"], config_hash=request["config_hash"], progress=99)
        _emit("result", **{key: value for key, value in envelope.items() if key != "type"})
        return 0
    except Exception as error:
        _emit("result", status="FAILED", request_hash=request["request_hash"], config_hash=request["config_hash"], evidence=[f"NATIVE_RUNNER:{type(error).__name__}"])
        return 1


def run_research_v0_repairs_cli(data_root: Path, artifact_dir: Path, control_report: Path, *, zero_tp_netting: bool = True, deferred_selective_zero_tp: bool = False, selective_lifecycle_repairs: bool = False, observe_minute_risk: bool = False, research_sol_notional_cap_6x: bool = False, research_portfolio_protect_45: bool = False, research_btc_episode_loss_20: bool = False, research_sol_remaining_btc_hedge: bool = False, research_btc_direction_sizing: bool = False, research_btc_drawdown_sizing: bool = False, research_v3_risk: str | None = None, research_h1_b1: str | None = None, research_btc_split50: bool = False, research_btc_split_planref_v1: bool = False, research_btc_split_tp_ioc: bool = False, research_btc_split_discount: str = "0.0025", research_sol_cover: str | None = None, research_conditional_sol: bool = False, research_immediate_sol: str | None = None, research_immediate_lookback: int = 90, research_sol_risk_first: str | None = None, research_alpha_cushion: bool = False, research_chop_pair: bool = False, research_sol_btc_open_only: bool = False, research_h4_ema: int | None = None, research_h4_gamma: str = "0.5", research_h4_warmup: Path | None = None, research_regime_reentry_band: str | None = None, research_residual_recovery: bool = False, research_c1_btc_cut_divisor: int = 2, research_c1_restore_dd: str = "0.35", research_c1_first_fresh_h4: bool = False, research_c1_btc_postcut_d1: bool = False, research_wait_4h: bool = False, research_wait_persist: bool = False, research_zero_retrace: bool = False, research_sol_dominant: bool = False, research_batch_minutes: int | None = None) -> Path:
    """Run one opt-in variant from the exact archived V0 economic inputs."""
    from coinmaster.domain.wave_overlay import Candidate

    if research_batch_minutes is not None and (not (research_alpha_cushion or research_chop_pair) or not 1 <= research_batch_minutes <= WEEK_MINUTES):
        raise ValueError("BATCH_OVERRIDE_REQUIRES_ALPHA_AND_1_TO_10080_MINUTES")
    if artifact_dir.exists():
        raise ValueError("RESEARCH_ARTIFACT_DIR_MUST_BE_NEW")
    if deferred_selective_zero_tp and zero_tp_netting:
        raise ValueError("DEFERRED_SELECTIVE_REQUIRES_ORIGINAL_ZERO_TP_BASE")
    if selective_lifecycle_repairs and not deferred_selective_zero_tp:
        raise ValueError("SELECTIVE_LIFECYCLE_REQUIRES_DEFERRED_SELECTIVE")
    if sum((research_portfolio_protect_45, research_sol_notional_cap_6x, research_btc_episode_loss_20, research_sol_remaining_btc_hedge, research_btc_direction_sizing, research_btc_drawdown_sizing, research_v3_risk is not None, research_h1_b1 is not None)) > 1:
        raise ValueError("RESEARCH_RISK_VARIANTS_MUTUALLY_EXCLUSIVE")
    if (research_sol_notional_cap_6x or research_portfolio_protect_45 or research_btc_episode_loss_20 or research_sol_remaining_btc_hedge or research_btc_direction_sizing or research_btc_drawdown_sizing or research_v3_risk or research_h1_b1) and not selective_lifecycle_repairs:
        raise ValueError("SOL_CAP_REQUIRES_SELECTIVE_LIFECYCLE_CONTROL")
    control = json.loads(control_report.read_text())
    config = control["config"]
    if (
        control["status"] != "NOT_FAITHFUL_DIAGNOSTIC"
        or Decimal(control["summary"]["terminal_total"]) != Decimal("3386491.65211338")
        or any(config.get(key) != value for key, value in BASELINE_CONFIG.items())
        or config["run_interval"]["start"] != datetime.fromtimestamp(TRADING_START_MS / 1000, tz=timezone.utc).isoformat()
        or config["run_interval"]["end_exclusive"] != datetime.fromtimestamp(TRADING_END_MS / 1000, tz=timezone.utc).isoformat()
        or config["run_interval"]["initial_active_seed"] != "10000"
        or config.get("tp_fee_floor_v1") is not False
        or config["execution_policy"] != control["policy"]
    ):
        raise ValueError("CONTROL_V0_INPUTS_MISMATCH")
    manifest = data_root / "bybit-1m" / "manifest.json"
    actual_data_hash = hashlib.sha256(json.dumps(json.loads(manifest.read_text()), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if actual_data_hash != control["data_hash"]:
        raise ValueError("CONTROL_V0_DATA_HASH_MISMATCH")
    from coinmaster.research.effective_config import effective_research_candidate
    candidate = effective_research_candidate(Candidate(**config["candidate"]), selective_lifecycle_repairs=selective_lifecycle_repairs)
    policy = ExecutionPolicy(**config["execution_policy"])
    fee_policy = FixedBaseFeePolicy(**config["fixed_base_fee_policy"])
    if fee_policy.hash != config["fee_policy_hash"]:
        raise ValueError("CONTROL_V0_FEE_POLICY_HASH_MISMATCH")
    artifact_dir.mkdir(parents=True, exist_ok=False)
    label = "v0-deferred-selective-zero-tp" if deferred_selective_zero_tp else "v0-execution-repairs" if zero_tp_netting else "v0-three-repairs-zero-tp-original"
    if selective_lifecycle_repairs:
        label = "v0-selective-lifecycle-cap30m"
    if research_sol_notional_cap_6x:
        label += "-solcap6"
    if research_btc_split50:
        label += "-btc-split50-d" + research_btc_split_discount
        if research_btc_split_planref_v1:
            label += "-planref-v1"
    if research_btc_split_tp_ioc:
        label += "-tp-ioc"
    if research_sol_cover:
        label += "-sol-cover" + research_sol_cover
    if research_sol_btc_open_only:
        label += "-C0"
    for enabled, name in ((research_residual_recovery,"C1"),(research_wait_4h,"E4"),(research_wait_persist,"EP"),(research_zero_retrace,"Z"),(research_sol_dominant,"S")):
        if enabled:label += "-"+name
    if research_h4_ema is not None:
        label += f"-H4-4H-E{research_h4_ema}-G{research_h4_gamma}"
    if research_regime_reentry_band is not None:
        label += "-B-ATR"+research_regime_reentry_band
    if research_chop_pair:
        label += "-chop-pair-50-net-v1"
    if research_alpha_cushion:
        label += "-alpha-cushion"
    if research_conditional_sol:
        label += "-conditional-sol-2-1-50"
    if research_immediate_sol:
        label += "-immediate-"+research_immediate_sol
    if research_sol_risk_first:
        label += "-sol-risk-first-"+research_sol_risk_first
    if research_h1_b1:
        label += "-" + research_h1_b1
    if research_v3_risk:
        label += "-v3-" + research_v3_risk
    if research_portfolio_protect_45:
        label += "-portfolio45"
    if research_btc_direction_sizing:
        label += "-btc-direction"
    if research_btc_drawdown_sizing:
        label += "-btc-dd25-15"
    if research_btc_episode_loss_20:
        label += "-btcloss20"
    if research_sol_remaining_btc_hedge:
        label += "-solhedge"
    report = run_native_diagnostic(
        data_root, include_funding=True, candidate=candidate,
        execution_policy=policy, fixed_base_fee_policy=fee_policy,
        initial_active_seed=Decimal(config["run_interval"]["initial_active_seed"]),
        artifact_dir=artifact_dir, artifact_label=label,
        research_v0_execution_repairs=True, research_v0_zero_tp_netting=zero_tp_netting,
        research_v0_deferred_selective_zero_tp=deferred_selective_zero_tp,
        research_v0_selective_lifecycle_repairs=selective_lifecycle_repairs,
        observe_minute_risk=observe_minute_risk,
        research_sol_notional_cap_6x=research_sol_notional_cap_6x,
        research_portfolio_protect_45=research_portfolio_protect_45,
        research_btc_direction_sizing=research_btc_direction_sizing,
        research_btc_drawdown_sizing=research_btc_drawdown_sizing,
        research_v3_risk=research_v3_risk,
        research_h1_b1=research_h1_b1,
        research_btc_split50=research_btc_split50,
        research_btc_split_planref_v1=research_btc_split_planref_v1,
        research_btc_split_tp_ioc=research_btc_split_tp_ioc,
        research_btc_split_discount=research_btc_split_discount,
        research_sol_cover=research_sol_cover,
        research_conditional_sol=research_conditional_sol,
        research_sol_risk_first=research_sol_risk_first,
        research_immediate_sol=research_immediate_sol,
        research_immediate_lookback=research_immediate_lookback,
        research_alpha_cushion=research_alpha_cushion,
        research_chop_pair=research_chop_pair,
        research_sol_btc_open_only=research_sol_btc_open_only, research_h4_ema=research_h4_ema,
        research_h4_gamma=research_h4_gamma, research_h4_warmup=research_h4_warmup,
        research_regime_reentry_band=research_regime_reentry_band,
        research_residual_recovery=research_residual_recovery, research_c1_btc_cut_divisor=research_c1_btc_cut_divisor, research_c1_restore_dd=research_c1_restore_dd, research_c1_first_fresh_h4=research_c1_first_fresh_h4, research_c1_btc_postcut_d1=research_c1_btc_postcut_d1, research_wait_4h=research_wait_4h, research_wait_persist=research_wait_persist,
        research_zero_retrace=research_zero_retrace, research_sol_dominant=research_sol_dominant,
        weekly_batch_minutes=research_batch_minutes or WEEK_MINUTES,
        cursor_batch_rows=research_batch_minutes or WEEK_MINUTES,
        research_btc_episode_loss_20=research_btc_episode_loss_20,
        research_sol_remaining_btc_hedge=research_sol_remaining_btc_hedge,
    )
    report["control_report_sha256"] = sha256_file(control_report)
    report["control_terminal_total"] = control["summary"]["terminal_total"]
    return save_diagnostic_report(data_root, report, label, artifact_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--research-btc-split50", action="store_true")
    parser.add_argument("--research-btc-split-planref-v1", action="store_true")
    parser.add_argument("--research-btc-split-tp-ioc", action="store_true")
    parser.add_argument("--research-btc-split-discount", choices=("0.0025","0.005"), default="0.0025")
    parser.add_argument("--research-sol-cover", choices=("0.5","0.75","1"))
    parser.add_argument("--research-conditional-sol", action="store_true")
    parser.add_argument("--research-alpha-cushion", action="store_true")
    parser.add_argument("--research-chop-pair", action="store_true")
    parser.add_argument("--research-batch-minutes", type=int, default=None, help="Isolated ALPHA research cursor and native event batch override; no economic parameter")
    parser.add_argument("--research-immediate-sol", choices=("i25","i25-light","i25-recovery","i33"),default=None)
    parser.add_argument("--research-immediate-lookback",type=int,default=90)
    parser.add_argument("--research-sol-risk-first", choices=("cap50","dd-cov","split-atr","alpha-corridor-v1"),default=None)
    parser.add_argument("--data-root", type=Path, default=Path("var/data"))
    parser.add_argument("--diagnostic-no-funding", action="store_true")
    parser.add_argument("--diagnostic-with-prior-minute-funding", action="store_true")
    parser.add_argument("--job-request", type=Path)
    parser.add_argument("--research-v0-execution-repairs", action="store_true")
    parser.add_argument("--research-v0-original-zero-tp", action="store_true", help="With research repairs, retain original BTC entry and zero-threshold TP levels")
    parser.add_argument("--research-v0-deferred-selective-zero-tp", action="store_true", help="Research-only one-quote deferred BTC entry with causal zero-target selection")
    parser.add_argument("--research-v0-selective-lifecycle-repairs", action="store_true", help="Research-only accepted-target/causal-right/margin repairs with 30m parent cap")
    parser.add_argument("--research-sol-btc-open-only", action="store_true")
    for flag in ("residual-recovery", "c1-first-fresh-h4", "c1-btc-postcut-d1", "wait-4h", "wait-persist", "zero-retrace", "sol-dominant"):
        parser.add_argument("--research-"+flag, action="store_true")
    parser.add_argument("--research-h4-ema", type=int, choices=(13,34,89))
    parser.add_argument("--research-h4-gamma", choices=("0.5","1"), default="0.5")
    parser.add_argument("--research-h4-warmup", type=Path)
    parser.add_argument("--research-regime-reentry-band", choices=("0","0.5"))
    parser.add_argument("--research-h1-b1", choices=("h1", "b1"), default=None)
    parser.add_argument("--research-v3-risk", choices=("b25", "s10_15", "r2", "t3"), default=None, help="One default-OFF research risk variation on V3 directional sizing")
    parser.add_argument("--research-btc-direction-sizing", action="store_true", help="Research-only frozen episode long5.5 short7.875 multiplier")
    parser.add_argument("--research-btc-drawdown-sizing", action="store_true", help="Research-only global paired-minute DD25/15 sizing7.875/3.9375")
    parser.add_argument("--research-btc-episode-loss-20", action="store_true", help="Research-only native BTC episode loss20 group exit")
    parser.add_argument("--research-sol-remaining-btc-hedge", action="store_true", help="Research-only earned SOL admission clipped to remaining native BTC/beta")
    parser.add_argument("--research-portfolio-protect-45", action="store_true", help="Research-only paired-minute 45%% protective epoch drawdown; resume next genuine BTC episode")
    parser.add_argument("--research-sol-notional-cap-6x", action="store_true", help="Research-only aggregate SOL entry notional capped at 6x fresh native marked equity")
    parser.add_argument("--research-c1-restore-dd", choices=("0.35","0.40"), default="0.35")
    parser.add_argument("--research-c1-btc-cut-divisor", type=int, choices=(2,4), default=2)
    parser.add_argument("--observe-minute-risk", action="store_true", help="Research-only non-mutating native close-equity and conditional OHLC risk recorder")
    parser.add_argument("--control-report", type=Path)
    parser.add_argument("--artifact-dir", type=Path)
    args = parser.parse_args()
    if (args.research_sol_btc_open_only or args.research_h4_ema is not None or args.research_regime_reentry_band is not None) and not args.research_v0_execution_repairs:
        parser.error("C0/H4/B require the explicit native research repair pipeline")
    if args.job_request is not None:
        raise SystemExit(run_job_request(args.job_request))
    if (args.research_v0_original_zero_tp or args.research_v0_deferred_selective_zero_tp) and not args.research_v0_execution_repairs:
        parser.error("research V0 zero-TP options require --research-v0-execution-repairs")
    if args.research_v0_original_zero_tp and args.research_v0_deferred_selective_zero_tp:
        parser.error("choose only one research V0 zero-TP option")
    if args.research_v0_selective_lifecycle_repairs and not (args.research_v0_execution_repairs and args.research_v0_deferred_selective_zero_tp):
        parser.error("selective lifecycle repairs require execution repairs and deferred selective zero TP")
    if sum((args.research_sol_notional_cap_6x, args.research_portfolio_protect_45, args.research_btc_episode_loss_20, args.research_sol_remaining_btc_hedge, args.research_btc_direction_sizing, args.research_btc_drawdown_sizing, args.research_v3_risk is not None, args.research_h1_b1 is not None)) > 1:
        parser.error("research risk variants are mutually exclusive")
    if (args.research_sol_notional_cap_6x or args.research_portfolio_protect_45 or args.research_btc_episode_loss_20 or args.research_sol_remaining_btc_hedge or args.research_btc_direction_sizing or args.research_btc_drawdown_sizing or args.research_v3_risk or args.research_h1_b1) and not (args.research_v0_selective_lifecycle_repairs and args.observe_minute_risk):
        parser.error("SOL cap requires selective lifecycle control and minute observer")
    if args.observe_minute_risk and not args.research_v0_execution_repairs:
        parser.error("minute risk observer requires isolated research execution repairs")
    if args.research_v0_execution_repairs:
        if args.control_report is None or args.artifact_dir is None:
            parser.error("research V0 repairs require --control-report and --artifact-dir")
        artifact = run_research_v0_repairs_cli(
            args.data_root, args.artifact_dir, args.control_report,
            zero_tp_netting=not (args.research_v0_original_zero_tp or args.research_v0_deferred_selective_zero_tp),
            deferred_selective_zero_tp=args.research_v0_deferred_selective_zero_tp,
            selective_lifecycle_repairs=args.research_v0_selective_lifecycle_repairs,
            observe_minute_risk=args.observe_minute_risk,
            research_sol_notional_cap_6x=args.research_sol_notional_cap_6x,
            research_portfolio_protect_45=args.research_portfolio_protect_45,
            research_btc_direction_sizing=args.research_btc_direction_sizing,
            research_btc_drawdown_sizing=args.research_btc_drawdown_sizing,
            research_v3_risk=args.research_v3_risk,
            research_h1_b1=args.research_h1_b1,
            research_btc_split50=args.research_btc_split50,
            research_btc_split_planref_v1=args.research_btc_split_planref_v1,
            research_btc_split_tp_ioc=args.research_btc_split_tp_ioc,
            research_btc_split_discount=args.research_btc_split_discount,
            research_sol_cover=args.research_sol_cover,
            research_conditional_sol=args.research_conditional_sol,
            research_alpha_cushion=args.research_alpha_cushion,
            research_chop_pair=args.research_chop_pair,
            research_sol_btc_open_only=args.research_sol_btc_open_only, research_h4_ema=args.research_h4_ema,
            research_h4_gamma=args.research_h4_gamma, research_h4_warmup=args.research_h4_warmup,
            research_regime_reentry_band=args.research_regime_reentry_band,
            research_residual_recovery=args.research_residual_recovery, research_c1_btc_cut_divisor=args.research_c1_btc_cut_divisor, research_c1_restore_dd=args.research_c1_restore_dd, research_c1_first_fresh_h4=args.research_c1_first_fresh_h4, research_c1_btc_postcut_d1=args.research_c1_btc_postcut_d1, research_wait_4h=args.research_wait_4h, research_wait_persist=args.research_wait_persist,
            research_zero_retrace=args.research_zero_retrace, research_sol_dominant=args.research_sol_dominant,
            research_batch_minutes=args.research_batch_minutes,
            research_sol_risk_first=args.research_sol_risk_first,
            research_immediate_sol=args.research_immediate_sol,
            research_immediate_lookback=args.research_immediate_lookback,
            research_btc_episode_loss_20=args.research_btc_episode_loss_20,
            research_sol_remaining_btc_hedge=args.research_sol_remaining_btc_hedge,
        )
        print(json.dumps({"status": "COMPLETED", "artifact": str(artifact), "artifact_sha256": sha256_file(artifact)}, sort_keys=True))
        return
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
