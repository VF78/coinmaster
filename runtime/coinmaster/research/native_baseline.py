"""Fail-closed native baseline entrypoint.

This command intentionally refuses to calculate or label a result until all
four required 1-minute execution/mark streams are complete and gap-free.  It
is the only accepted launch point for the future native baseline lifecycle.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def run_native_diagnostic(data_root: Path) -> dict:
    """Execute the one native Strategy on real daily Bybit bars, never rank it.

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
    from coinmaster.research.native_fixture import BTC_PERP, SIM, SOL_PERP, quote
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig

    def rows(symbol: str): return {row["open_time_ms"]: row for row in pq.read_table(data_root / "normalized" / f"bybit-{symbol}-daily.parquet").to_pylist()}
    btc, sol = rows("BTCUSDT"), rows("SOLUSDT")
    def kind(instrument, price_type): return BarType(instrument, BarSpecification(1, BarAggregation.DAY, price_type), AggregationSource.EXTERNAL)
    btc_last, sol_last, btc_mid, sol_mid = kind(BTC_PERP.id, PriceType.LAST), kind(SOL_PERP.id, PriceType.LAST), kind(BTC_PERP.id, PriceType.MID), kind(SOL_PERP.id, PriceType.MID)
    def bar(bar_type, row, precision, volume):
        price = lambda key: Price.from_str(f"{float(row[key]):.{precision}f}")
        ts = (int(row["open_time_ms"]) + 86_400_000) * 1_000_000
        return Bar(bar_type, price("open"), price("high"), price("low"), price("close"), Quantity.from_str(volume), ts, ts)
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(10_000, BTC_PERP.quote_currency)], base_currency=BTC_PERP.quote_currency, default_leverage=Decimal("1"))
    engine.add_instrument(BTC_PERP); engine.add_instrument(SOL_PERP)
    engine.add_strategy(WaveOverlayStrategy(WaveOverlayStrategyConfig(btc_id=BTC_PERP.id, sol_id=SOL_PERP.id, btc_bar_type=btc_last, sol_bar_type=sol_last, btc_mark_bar_type=btc_mid, sol_mark_bar_type=sol_mid, active_seed=Decimal("10000"))))
    data = []
    for timestamp in sorted(set(btc) & set(sol)):
        b, s = btc[timestamp], sol[timestamp]
        event = (timestamp + 86_400_000) * 1_000_000 + 1
        data += [bar(btc_last, b, 1, "1000.000"), bar(sol_last, s, 2, "1000.0"), bar(btc_mid, b, 1, "1000.000"), bar(sol_mid, s, 2, "1000.0"), quote(BTC_PERP.id, f"{float(b['close']) - .05:.1f}", f"{float(b['close']) + .05:.1f}", event), quote(SOL_PERP.id, f"{float(s['close']) - .05:.2f}", f"{float(s['close']) + .05:.2f}", event)]
    engine.add_data(data); engine.run()
    try:
        report = engine.trader.generate_account_report(SIM)
        return {"status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible": False, "fills": len(engine.trader.generate_order_fills_report()), "terminal_native_total": str(report["total"].iloc[-1]), "limitations": ["MID stand-in is not production mark routing", "Funding settlement marks/fees/intraminute liquidation unverified"]}
    finally:
        engine.dispose()


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
    return blockers or ["NATIVE_BASELINE_NOT_IMPLEMENTED"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("var/data"))
    parser.add_argument("--diagnostic-no-funding", action="store_true")
    args = parser.parse_args()
    if args.diagnostic_no_funding:
        print(json.dumps(run_native_diagnostic(args.data_root), sort_keys=True))
        return
    blockers = coverage_blockers(args.data_root)
    print(json.dumps({"status": "BLOCKED", "ranking_eligible": False, "blockers": blockers}, sort_keys=True))
    raise SystemExit(2)


if __name__ == "__main__":
    main()
