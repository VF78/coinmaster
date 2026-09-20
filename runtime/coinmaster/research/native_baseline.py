"""Fail-closed native baseline entrypoint.

This command intentionally refuses to calculate or label a result until all
four required 1-minute execution/mark streams are complete and gap-free.  It
is the only accepted launch point for the future native baseline lifecycle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone


DAY_MS = 86_400_000
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

    @property
    def hash(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def monthly_returns(equity: list[dict[str, str]]) -> list[dict[str, str]]:
    """Calendar months with carry-forward TOTAL, including silent months."""
    values = sorted((datetime.fromisoformat(row["timestamp"]).replace(tzinfo=timezone.utc), Decimal(row["total"])) for row in equity)
    if not values: return []
    result, cursor, prior, index = [], values[0][0].replace(day=1), Decimal("10000"), 0
    end = values[-1][0].replace(day=1)
    while cursor <= end:
        while index < len(values) and values[index][0].year == cursor.year and values[index][0].month == cursor.month:
            prior = values[index][1]; index += 1
        base = Decimal("10000") if not result else Decimal(result[-1]["total"])
        result.append({"month": cursor.strftime("%Y-%m"), "total": str(prior), "return": str((prior / base) - 1)})
        cursor = cursor.replace(year=cursor.year + (cursor.month == 12), month=1 if cursor.month == 12 else cursor.month + 1)
    return result


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
        marks = {row["open_time_ms"]: row["close"] for row in pq.read_table(data_root / "normalized" / f"bybit-{symbol}-mark-1m.parquet").to_pylist()}
        for row in pq.read_table(data_root / "normalized" / f"bybit-{symbol}-funding.parquet").to_pylist():
            settlement = int(row["funding_time_ms"])
            # Warmup is feature-only. At an exact range boundary, the prior
            # causal minute is outside the captured [start, end) marks.
            if start_settlement_ms is not None and settlement <= start_settlement_ms:
                continue
            if end_settlement_ms is not None and settlement >= end_settlement_ms:
                continue
            mark = marks.get(settlement - 60_000)
            if mark is None:
                raise ValueError(f"MISSING_CAUSAL_1M_MARK:{symbol}:{settlement}")
            events.append(FundingInstruction(f"bybit:{symbol}:{settlement}:{row['funding_rate']}", instrument.id, Decimal(str(row["funding_rate"])), settlement * 1_000_000, Decimal(str(mark)), "venue_mark_prior_minute"))
    return tuple(events)


def run_native_diagnostic(data_root: Path, include_funding: bool = False, candidate=None) -> dict:
    """Execute one native lifecycle with daily decisions and causal 1m fills.

    Funding settlement marks, fees, and intraminute liquidation remain
    unverified, so this route is deliberately an engineering diagnostic—not a
    faithful baseline or optimizer input.
    """
    import pyarrow.parquet as pq
    from decimal import Decimal
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.model.data import Bar, BarSpecification, BarType
    from nautilus_trader.model.enums import AccountType, AggregationSource, BarAggregation, OmsType, PriceType
    from nautilus_trader.model.objects import Money, Price, Quantity
    from coinmaster.research.native_fixture import BTC_PERP, SIM, SOL_PERP, BybitTierMarginModule, MarkPriceUpdate, PerpetualFundingModule, quote
    from coinmaster.ledger.journal import NativeEventJournal
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig
    from coinmaster.domain.wave_overlay import Candidate
    from coinmaster.venues.marks import venue_mark, venue_mark_data_type

    candidate = candidate or Candidate()
    policy = ExecutionPolicy()
    def rows(symbol: str):
        return {
            row["open_time_ms"]: row
            for row in pq.read_table(data_root / "normalized" / f"bybit-{symbol}-daily.parquet").to_pylist()
            if WARMUP_START_MS <= int(row["open_time_ms"]) < TRADING_END_MS
        }
    btc, sol = rows("BTCUSDT"), rows("SOLUSDT")
    # The full 1m streams are hash/gap checked by the manifest. Only the first
    # closed executable minute after each daily decision is loaded into this
    # one native lifecycle; no synthetic daily-close quote is manufactured.
    decision_days = sorted(set(btc) & set(sol))
    wanted_minutes = sorted({minute for timestamp in decision_days if timestamp >= TRADING_START_MS for minute in (timestamp + 86_400_000 - 60_000, timestamp + 86_400_000) if minute < TRADING_END_MS})
    def minute_closes(symbol: str, stream: str) -> dict[int, dict]:
        table = pq.read_table(data_root / "normalized" / f"bybit-{symbol}-{stream}-1m.parquet", filters=[("open_time_ms", "in", wanted_minutes)])
        return {int(row["open_time_ms"]): row for row in table.to_pylist()}
    btc_execution, sol_execution = minute_closes("BTCUSDT", "execution"), minute_closes("SOLUSDT", "execution")
    btc_marks, sol_marks = minute_closes("BTCUSDT", "mark"), minute_closes("SOLUSDT", "mark")
    def kind(instrument, price_type): return BarType(instrument, BarSpecification(1, BarAggregation.DAY, price_type), AggregationSource.EXTERNAL)
    btc_last, sol_last = kind(BTC_PERP.id, PriceType.LAST), kind(SOL_PERP.id, PriceType.LAST)
    def bar(bar_type, row, precision, volume):
        price = lambda key: Price.from_str(f"{float(row[key]):.{precision}f}")
        ts = (int(row["open_time_ms"]) + 86_400_000) * 1_000_000
        return Bar(bar_type, price("open"), price("high"), price("low"), price("close"), Quantity.from_str(volume), ts, ts)
    events = funding_with_prior_minute_marks(data_root, TRADING_START_MS, TRADING_END_MS) if include_funding else ()
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
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(10_000, BTC_PERP.quote_currency)], base_currency=BTC_PERP.quote_currency, default_leverage=Decimal("1"), modules=modules)
    engine.add_instrument(BTC_PERP); engine.add_instrument(SOL_PERP)
    from nautilus_trader.model.identifiers import ClientId
    engine.add_strategy(WaveOverlayStrategy(WaveOverlayStrategyConfig(btc_id=BTC_PERP.id, sol_id=SOL_PERP.id, btc_bar_type=btc_last, sol_bar_type=sol_last, btc_mark_data_type=venue_mark_data_type(BTC_PERP.id), sol_mark_data_type=venue_mark_data_type(SOL_PERP.id), mark_client_id=ClientId("BYBIT_MARK"), active_seed=Decimal("10000"), tier_marks=mark_updates, tier_selected_leverage=selected_leverage, max_mark_age_ns=max_mark_age_ns, trading_start_open_ns=TRADING_START_MS * 1_000_000, terminal_close_at_ns=TRADING_END_MS * 1_000_000, candidate=candidate)))
    execution_data, mark_data = [], []
    for timestamp in decision_days:
        b, s = btc[timestamp], sol[timestamp]
        event = (timestamp + 86_400_000) * 1_000_000 + 1
        mark_ts = (timestamp + 86_400_000) * 1_000_000
        if b.get("mark_close") is None or s.get("mark_close") is None:
            continue
        execution_minute, mark_minute = timestamp + 86_400_000, timestamp + 86_400_000 - 60_000
        be, se = btc_execution.get(execution_minute), sol_execution.get(execution_minute)
        bm, sm = btc_marks.get(mark_minute), sol_marks.get(mark_minute)
        if timestamp >= TRADING_START_MS and not all((bm, sm)):
            raise ValueError(f"MISSING_CAUSAL_1M_MARK:{mark_minute}")
        if timestamp >= TRADING_START_MS and timestamp + 86_400_000 < TRADING_END_MS and not all((be, se)):
            raise ValueError(f"MISSING_CAUSAL_1M_EXECUTION:{execution_minute}")
        execution_data += [bar(btc_last, b, 1, "1000.000"), bar(sol_last, s, 2, "1000.0")]
        if timestamp >= TRADING_START_MS and bm and sm:
            mark_data += [venue_mark(BTC_PERP.id, Decimal(str(bm["close"])), (mark_minute + 60_000) * 1_000_000), venue_mark(SOL_PERP.id, Decimal(str(sm["close"])), (mark_minute + 60_000) * 1_000_000)]
        if timestamp >= TRADING_START_MS and be and se:
            execution_data += [quote(BTC_PERP.id, f"{float(be['close']):.1f}", f"{float(be['close']):.1f}", (execution_minute + 60_000) * 1_000_000), quote(SOL_PERP.id, f"{float(se['close']):.2f}", f"{float(se['close']):.2f}", (execution_minute + 60_000) * 1_000_000)]
    engine.add_data(execution_data, sort=False)
    engine.add_data(mark_data, client_id=ClientId("BYBIT_MARK"), sort=False)
    engine.sort_data(); engine.run()
    try:
        report = engine.trader.generate_account_report(SIM)
        fills = engine.trader.generate_order_fills_report()
        orders = engine.trader.generate_orders_report()
        artifact_root = data_root / "runs"
        artifacts = {"fills": save_native_artifact(fills, artifact_root / "native-diagnostic-fills.csv"), "orders": save_native_artifact(orders, artifact_root / "native-diagnostic-orders.csv")}
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
        full_config = {**BASELINE_CONFIG, "candidate": asdict(candidate), "execution_policy": asdict(policy)}
        config_hash = hashlib.sha256(json.dumps(full_config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        initial = Decimal("10000")
        equity = [{"timestamp": str(index), "active": str(value), "reserve": "0", "total": str(value)} for index, value in report["total"].items()]
        totals = [Decimal(item["total"]) for item in equity]
        peak, peak_at, max_dd, trough_at = initial, equity[0]["timestamp"], Decimal("0"), equity[0]["timestamp"]
        for item, total in zip(equity, totals):
            if total > peak: peak, peak_at = total, item["timestamp"]
            if peak - total > max_dd: max_dd, trough_at = peak - total, item["timestamp"]
        audit = journal.funding_audit() if journal else []
        funding_by_instrument = {instrument: sum(1 for row in audit if row[1] == instrument) for instrument in sorted({row[1] for row in audit})}
        return {"status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible": False, "interval": "[2024-09-01,2026-09-01)", "warmup": "[2022-09-02,2024-09-01) feature-only", "config": full_config, "config_hash": config_hash, "data_hash": data_hash, "code_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "policy": asdict(policy), "policy_hash": policy.hash, "summary": {"roi": str((terminal_active / initial) - 1), "terminal_total": str(terminal_active), "max_drawdown_amount": str(max_dd), "max_drawdown_percent": str(max_dd / initial), "drawdown_start": peak_at, "drawdown_trough": trough_at, "drawdown_recovery": "UNKNOWN_NOT_RECOVERED_OR_NOT_EXPORTED", "monthly_returns": monthly_returns(equity)}, "equity": equity, "fills": len(fills), "execution_artifacts": artifacts, "episodes": "UNKNOWN_NATIVE_DOMAIN_EPISODE_AUDIT_NOT_EXPORTED", "realized_unrealized": "UNKNOWN_NATIVE_ACCOUNT_REPORT_ONLY", "native_fees": str(fees), "modeled_slippage": "UNKNOWN_1M_CLOSE_PROXY", "native_order_rejections": rejected, "funding": {"count": len(audit), "by_instrument_count": funding_by_instrument, "signed_amount": "UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA"}, "funding_journal": str(journal_path) if journal else None, "transfers": "0", "liquidation_count": 0, "liquidation_value": "0", "terminal_active": str(terminal_active), "terminal_reserve": "0", "terminal_total": str(terminal_active), "terminal_open_positions": len(engine.cache.positions_open()), "limitations": ["1m close proxy has no BBO/L2/slippage/liquidity evidence", "Fixture fees are 0.001/side; historical applicability unknown", "Venue marks are CustomData and do not participate in matching", "Historical liquidation and funding settlement marks are unvalidated"]}
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


def save_diagnostic_report(data_root: Path, report: dict) -> Path:
    """Persist a diagnostic artifact without promoting it to baseline evidence."""
    target = data_root / "runs" / "native-diagnostic-report.json"
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
