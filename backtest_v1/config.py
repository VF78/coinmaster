from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestConfig:
    symbol: str = "BTC-PERP"
    start_utc: str = "2024-01-01T00:00:00Z"
    end_utc: str = "yesterday_23_59_utc"  # TODO: resolve dynamically in production data wiring

    initial_equity: float = 10_000.0
    risk_per_trade: float = 0.0125

    # stop = structure + ATR buffer + hard cap 0.70%
    stop_cap_pct: float = 0.007
    atr_period: int = 14
    atr_buffer_mult: float = 0.5

    # partial take profits
    tp1_r: float = 1.0
    tp2_r: float = 2.2
    tp3_r: float = 3.8
    tp1_fraction: float = 0.40
    tp2_fraction: float = 0.35
    tp3_fraction: float = 0.25

    daily_hard_stop_dd: float = 0.20

    # baseline execution costs
    fee_per_side: float = 0.0003
    slippage_per_side: float = 0.0003

    # data
    timeframe: str = "1m"
    csv_path: str = "backtest_v1/data/sample_btc_1m.csv"
