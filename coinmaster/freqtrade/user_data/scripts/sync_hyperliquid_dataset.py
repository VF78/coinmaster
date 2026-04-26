#!/usr/bin/env python3
"""Build and maintain a local Hyperliquid OHLCV dataset for Freqtrade.

The sync combines:

1. public archival 1m Freqtrade feather files where available;
2. fresh Hyperliquid `candleSnapshot` pulls;
3. existing local Freqtrade data files from previous daily syncs.

This lets the VPS accumulate a durable local dataset even when Hyperliquid's
public candleSnapshot endpoint only exposes a rolling history window for lower
timeframes.
"""

from __future__ import annotations

import argparse
import io
import time
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
from freqtrade.data.history import get_datahandler
from freqtrade.enums import CandleType

from download_hyperliquid_ohlcv import fetch_pair_timeframe, parse_timerange, store_ohlcv

DEFAULT_ARCHIVE_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/guibvieira/freqtrade-hyperliquid-data/main/"
    "user_data/data/hyperliquid/futures/{coin}_USDC_USDC-1m-futures.feather"
)
TIMEFRAME_RULES = {
    "1m": "1min",
    "3m": "3min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
}
TIMEFRAME_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1_800,
    "1h": 3_600,
    "2h": 7_200,
    "4h": 14_400,
    "8h": 28_800,
    "12h": 43_200,
    "1d": 86_400,
}


def pair_to_coin(pair: str) -> str:
    return pair.split("/", 1)[0].upper()


def normalize_ohlcv(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in dataframe.columns]
    if missing:
        raise ValueError(f"OHLCV dataframe missing columns: {missing}")
    out = dataframe[required].copy()
    out["date"] = pd.to_datetime(out["date"], utc=True)
    for column in ["open", "high", "low", "close", "volume"]:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    return out.dropna().drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)


def clip_timerange(dataframe: pd.DataFrame, start_ms: int, end_ms: int) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe
    start = pd.to_datetime(start_ms, unit="ms", utc=True)
    end = pd.to_datetime(end_ms, unit="ms", utc=True)
    return dataframe[(dataframe["date"] >= start) & (dataframe["date"] <= end)].reset_index(drop=True)


def resample_ohlcv(dataframe: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    dataframe = normalize_ohlcv(dataframe)
    if dataframe.empty or timeframe == "1m":
        return dataframe
    if timeframe not in TIMEFRAME_RULES:
        raise ValueError(f"Unsupported resample timeframe: {timeframe}")
    indexed = dataframe.set_index("date")
    rule = TIMEFRAME_RULES[timeframe]
    out = indexed.resample(rule, label="left", closed="left").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    out = out.dropna(subset=["open", "high", "low", "close"]).reset_index()
    return normalize_ohlcv(out)


def merge_frames(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    normalized = [normalize_ohlcv(frame) for frame in frames if frame is not None and not frame.empty]
    if not normalized:
        return normalize_ohlcv(pd.DataFrame())
    merged = pd.concat(normalized, ignore_index=True)
    return normalize_ohlcv(merged)


def load_local(datadir: Path, data_format: str, pair: str, timeframe: str) -> pd.DataFrame:
    handler = get_datahandler(datadir, data_format=data_format)
    try:
        return normalize_ohlcv(handler.ohlcv_load(pair, timeframe, CandleType.FUTURES, warn_no_data=False))
    except FileNotFoundError:
        return normalize_ohlcv(pd.DataFrame())


def fetch_archive(session: requests.Session, url: str) -> pd.DataFrame:
    response = session.get(url, timeout=120)
    if response.status_code == 404:
        return normalize_ohlcv(pd.DataFrame())
    response.raise_for_status()
    return normalize_ohlcv(pd.read_feather(io.BytesIO(response.content)))


def summarize(pair: str, timeframe: str, dataframe: pd.DataFrame) -> str:
    if dataframe.empty:
        return f"{pair} {timeframe}: EMPTY"
    seconds = TIMEFRAME_SECONDS["1m" if timeframe == "archive-1m" else timeframe]
    diffs = dataframe["date"].diff().dropna().dt.total_seconds()
    gaps = diffs[diffs > seconds * 1.5]
    first = dataframe["date"].iloc[0].isoformat()
    last = dataframe["date"].iloc[-1].isoformat()
    if gaps.empty:
        gap_text = "no large gaps"
    else:
        gap_text = f"{len(gaps)} large gaps, max {gaps.max() / 3600:.1f}h"
    return f"{pair} {timeframe}: {len(dataframe)} candles ({first} -> {last}); {gap_text}"


def should_fetch_archive(mode: str, local_frames: dict[str, pd.DataFrame]) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    return all(frame.empty for frame in local_frames.values())


def iter_jobs(pairs: Iterable[str], timeframes: Iterable[str]) -> Iterable[tuple[str, str]]:
    for pair in pairs:
        for timeframe in timeframes:
            yield pair, timeframe


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Hyperliquid OHLCV archive + fresh candles into Freqtrade data files.")
    parser.add_argument("--pairs", nargs="+", default=["BTC/USDC:USDC", "ETH/USDC:USDC", "SOL/USDC:USDC"])
    parser.add_argument("--timeframes", nargs="+", default=["5m", "15m", "1h", "4h"])
    parser.add_argument("--timerange", default="20250701-", help="YYYYMMDD- or YYYYMMDD-YYYYMMDD")
    parser.add_argument("--datadir", default="/freqtrade/user_data/data/hyperliquid")
    parser.add_argument("--data-format", default="feather", choices=["feather", "json", "jsongz", "parquet"])
    parser.add_argument("--archives", choices=["auto", "always", "never"], default="auto")
    parser.add_argument("--archive-url-template", default=DEFAULT_ARCHIVE_URL_TEMPLATE)
    parser.add_argument("--fresh-sleep", type=float, default=0.5)
    args = parser.parse_args()

    start_ms, end_ms = parse_timerange(args.timerange)
    datadir = Path(args.datadir)
    datadir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    for pair in args.pairs:
        local_by_tf = {tf: load_local(datadir, args.data_format, pair, tf) for tf in args.timeframes}
        archive_1m = normalize_ohlcv(pd.DataFrame())
        if should_fetch_archive(args.archives, local_by_tf):
            coin = pair_to_coin(pair)
            url = args.archive_url_template.format(coin=coin, pair=pair.replace("/", "_").replace(":", "_"))
            archive_1m = clip_timerange(fetch_archive(session, url), start_ms, end_ms)
            if archive_1m.empty:
                print(f"archive missing/empty for {pair}: {url}")
            else:
                print(summarize(pair, "archive-1m", archive_1m))

        for timeframe in args.timeframes:
            archive_tf = resample_ohlcv(archive_1m, timeframe) if not archive_1m.empty else normalize_ohlcv(pd.DataFrame())
            fresh_tf = fetch_pair_timeframe(session, pair, timeframe, start_ms, end_ms)
            fresh_tf = clip_timerange(fresh_tf, start_ms, end_ms)
            merged = merge_frames([archive_tf, local_by_tf[timeframe], fresh_tf])
            if merged.empty:
                raise RuntimeError(f"No candles available for {pair} {timeframe}")
            store_ohlcv(datadir, args.data_format, pair, timeframe, merged)
            print(summarize(pair, timeframe, merged))
            time.sleep(args.fresh_sleep)


if __name__ == "__main__":
    main()
