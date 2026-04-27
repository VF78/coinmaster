#!/usr/bin/env python3
"""Diagnostic counts for the Stage 1 Freqtrade CoinMasterStrategy port."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from freqtrade.data.history import get_datahandler
from freqtrade.enums import CandleType

sys.path.insert(0, "/freqtrade/user_data")
from strategies.CoinMasterStrategy import CoinMasterStrategy


def load_pair(datadir: Path, pair: str, timeframe: str) -> pd.DataFrame:
    handler = get_datahandler(datadir, data_format="feather")
    return handler.ohlcv_load(pair, timeframe, CandleType.FUTURES, warn_no_data=False)


def count(series: pd.Series) -> int:
    return int(series.fillna(False).astype(bool).sum())


class LocalDataProvider:
    def __init__(self, datadir: Path, pairs: list[str]) -> None:
        self.datadir = datadir
        self.pairs = pairs

    def current_whitelist(self) -> list[str]:
        return self.pairs

    def get_pair_dataframe(self, pair: str, timeframe: str) -> pd.DataFrame:
        return load_pair(self.datadir, pair, timeframe)


def audit_pair(pair: str, dataframe: pd.DataFrame, datadir: Path, pairs: list[str]) -> dict[str, object]:
    strategy = CoinMasterStrategy({"timeframe": "5m", "stake_currency": "USDC"})
    strategy.dp = LocalDataProvider(datadir, pairs)
    df = strategy.populate_indicators(dataframe.copy(), {"pair": pair})
    df = strategy.populate_entry_trend(df, {"pair": pair})
    df = strategy.populate_exit_trend(df, {"pair": pair})

    fvg_dir = pd.to_numeric(df.get("fvg_dir", pd.Series(0, index=df.index)), errors="coerce").fillna(0)
    long_signal = df["engulf_long"].fillna(False).astype(bool) | (fvg_dir == 1)
    short_signal = df["engulf_short"].fillna(False).astype(bool) | (fvg_dir == -1)
    volume = df["volume"] > 0
    body_guard = df["body_atr"].fillna(0) >= float(strategy.min_impulse_atr.value)
    close_long = df["close_position"].fillna(0.5) >= 0.75
    close_short = df["close_position"].fillna(0.5) <= 0.25
    regime_long = strategy._regime_series(df, "long").fillna(False)
    regime_short = strategy._regime_series(df, "short").fillna(False)

    rows = len(df)
    first = df["date"].iloc[0].isoformat() if rows and "date" in df.columns else "n/a"
    last = df["date"].iloc[-1].isoformat() if rows and "date" in df.columns else "n/a"
    return {
        "pair": pair,
        "rows": rows,
        "first": first,
        "last": last,
        "bullish_body_engulf": count(df["bullish_body_engulf"]),
        "bearish_body_engulf": count(df["bearish_body_engulf"]),
        "sweep_low": count(df["sweep_low"]),
        "sweep_high": count(df["sweep_high"]),
        "engulf_long": count(df["engulf_long"]),
        "engulf_short": count(df["engulf_short"]),
        "fvg_long_retrace": count(fvg_dir == 1),
        "fvg_short_retrace": count(fvg_dir == -1),
        "raw_long_signal": count(long_signal),
        "raw_short_signal": count(short_signal),
        "regime_long": count(regime_long),
        "regime_short": count(regime_short),
        "long_after_regime": count(long_signal & regime_long),
        "short_after_regime": count(short_signal & regime_short),
        "long_after_close_quality": count(long_signal & regime_long & close_long),
        "short_after_close_quality": count(short_signal & regime_short & close_short),
        "enter_long": count(df.get("enter_long", pd.Series(False, index=df.index)) == 1),
        "enter_short": count(df.get("enter_short", pd.Series(False, index=df.index)) == 1),
        "exit_long_opposite": count(df.get("exit_long", pd.Series(False, index=df.index)) == 1),
        "exit_short_opposite": count(df.get("exit_short", pd.Series(False, index=df.index)) == 1),
        "volume_guard": count(volume),
        "body_guard": count(body_guard),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit CoinMasterStrategy signal/guard counts on local Freqtrade data.")
    parser.add_argument("--pairs", nargs="+", default=["BTC/USDC:USDC", "ETH/USDC:USDC", "HYPE/USDC:USDC"])
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--datadir", default="/freqtrade/user_data/data/hyperliquid")
    args = parser.parse_args()

    rows = []
    for pair in args.pairs:
        try:
            datadir = Path(args.datadir)
            dataframe = load_pair(datadir, pair, args.timeframe)
            rows.append(audit_pair(pair, dataframe, datadir, args.pairs))
        except Exception as exc:
            rows.append({"pair": pair, "error": str(exc)})

    out = pd.DataFrame(rows)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
