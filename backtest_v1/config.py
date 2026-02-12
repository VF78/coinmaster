from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestConfig:
    symbol: str = "BTC-PERP"
    coin: str = "BTC"

    # User-requested baseline period; loader will use available exchange history in range.
    start_utc: str = "2024-01-01T00:00:00Z"
    end_utc: str = "yesterday_23_59_utc"

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

    # trade management
    max_bars_in_trade: int = 24 * 60  # 1 day on 1m base candles

    daily_hard_stop_dd: float = 0.20

    # baseline execution costs (blended)
    fee_per_side: float = 0.0003
    slippage_per_side: float = 0.0003

    # data source: hyperliquid|csv|synthetic
    data_source: str = "hyperliquid"
    base_interval: str = "1m"
    csv_path: str = "backtest_v1/data/btc_1m.csv"
    persist_fetched_csv: bool = True

    # Hyperliquid fetch options
    hyperliquid_info_url: str = "https://api.hyperliquid.xyz/info"
    fetch_chunk_bars: int = 4500  # keep below typical candleSnapshot cap

    # strategy tuning knobs (v1 implementation)
    local_sweep_lookback: int = 6
    fvg_min_gap_pct: float = 0.00025
    fvg_retest_window_bars: int = 8
