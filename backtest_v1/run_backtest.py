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
    candles = load_candles(cfg.csv_path).candles
    candles = attach_features(candles, atr_period=cfg.atr_period)

    # TODO: drive bias by explicit user regime input.
    signal = generate_entry_signal(candles, bias="both")
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
    print(f"Trades: {len(trades)}")
    print(summary_row)
    print(f"Saved: {trades_path}, {equity_path}, {summary_path}")


if __name__ == "__main__":
    main()
