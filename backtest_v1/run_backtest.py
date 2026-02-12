from __future__ import annotations

import csv
from pathlib import Path

from .config import BacktestConfig
from .data import load_candles
from .engine import run_backtest
from .metrics import build_summary, summary_to_row
from .signals import attach_features, generate_entry_signal


def _write_csv(path: Path, rows: list[dict]):
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    cfg = BacktestConfig()
    loaded = load_candles(cfg)
    candles = attach_features(loaded.candles, atr_period=cfg.atr_period)

    # TODO: bias should be driven by explicit user regime command in live mode.
    signal = generate_entry_signal(
        candles,
        bias="both",
        sweep_lookback=cfg.local_sweep_lookback,
        fvg_min_gap_pct=cfg.fvg_min_gap_pct,
        fvg_retest_window_bars=cfg.fvg_retest_window_bars,
    )
    trades, equity_curve = run_backtest(candles, signal, cfg)

    out_dir = Path("backtest_v1/out")
    out_dir.mkdir(parents=True, exist_ok=True)

    trades_path = out_dir / "trades.csv"
    equity_path = out_dir / "equity_curve.csv"
    summary_path = out_dir / "summary.csv"

    _write_csv(trades_path, trades)
    _write_csv(equity_path, equity_curve)

    bars_per_year = 365 * 24 * 60
    summary = build_summary(trades, equity_curve, bars_per_year=bars_per_year)
    summary_row = summary_to_row(summary)
    _write_csv(summary_path, [summary_row])

    print("Backtest run complete")
    print(f"Data source: {loaded.meta.get('source')}")
    if loaded.meta.get("actual_start"):
        print(
            f"Range used: {loaded.meta.get('actual_start')} -> {loaded.meta.get('actual_end')} "
            f"({loaded.meta.get('count')} candles, {loaded.meta.get('calls')} API calls)"
        )
    print(f"Trades: {len(trades)}")
    print(summary_row)
    print(f"Saved: {trades_path}, {equity_path}, {summary_path}")


if __name__ == "__main__":
    main()
