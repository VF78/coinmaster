#!/usr/bin/env python3
"""Download Hyperliquid candles into Freqtrade's local OHLCV store.

Freqtrade/CCXT currently reports historical OHLCV download as unavailable for
Hyperliquid, while Hyperliquid's public info API exposes candles via
`candleSnapshot`. This utility keeps Stage 1 research native to Freqtrade by
writing through Freqtrade's data handler into user_data/data/hyperliquid/futures.

Example inside the official Freqtrade container:

    python /freqtrade/user_data/scripts/download_hyperliquid_ohlcv.py \
      --pairs BTC/USDC:USDC ETH/USDC:USDC SOL/USDC:USDC \
      --timeframes 15m 1h 4h \
      --timerange 20260101-
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
from freqtrade.data.history import get_datahandler
from freqtrade.enums import CandleType

API_URL = "https://api.hyperliquid.xyz/info"
INTERVAL_MS = {
    "1m": 60_000,
    "3m": 3 * 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 60 * 60_000,
    "2h": 2 * 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "8h": 8 * 60 * 60_000,
    "12h": 12 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
}
# Safety brake for backward pagination. candleSnapshot returns the latest
# available chunk inside [startTime, endTime], so we move endTime backward from
# the first returned candle until the requested start is reached.
MAX_REQUESTS_PER_JOB = 2_000


def parse_yyyymmdd(value: str) -> int:
    dt = datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def parse_timerange(timerange: str) -> tuple[int, int]:
    if "-" not in timerange:
        raise ValueError("timerange must look like YYYYMMDD- or YYYYMMDD-YYYYMMDD")
    start_raw, end_raw = timerange.split("-", 1)
    if not start_raw:
        raise ValueError("timerange start is required")
    start_ms = parse_yyyymmdd(start_raw)
    end_ms = parse_yyyymmdd(end_raw) if end_raw else int(time.time() * 1000)
    if end_ms <= start_ms:
        raise ValueError("timerange end must be after start")
    return start_ms, end_ms


def pair_to_coin(pair: str) -> str:
    # Freqtrade futures pairs look like BTC/USDC:USDC; Hyperliquid wants BTC.
    return pair.split("/", 1)[0].upper()


def request_candles(session: requests.Session, coin: str, timeframe: str, start_ms: int, end_ms: int) -> list[dict]:
    payload = {
        "type": "candleSnapshot",
        "req": {"coin": coin, "interval": timeframe, "startTime": start_ms, "endTime": end_ms},
    }
    for attempt in range(6):
        response = session.post(API_URL, json=payload, timeout=30)
        if response.status_code != 429:
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise RuntimeError(f"Unexpected Hyperliquid response for {coin} {timeframe}: {data!r}")
            return data
        retry_after = response.headers.get("Retry-After")
        delay = float(retry_after) if retry_after else min(2 ** attempt, 30)
        time.sleep(delay)
    response.raise_for_status()
    raise RuntimeError("unreachable")


def fetch_pair_timeframe(session: requests.Session, pair: str, timeframe: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    if timeframe not in INTERVAL_MS:
        raise ValueError(f"Unsupported timeframe for Hyperliquid candleSnapshot: {timeframe}")

    coin = pair_to_coin(pair)
    interval_ms = INTERVAL_MS[timeframe]
    cursor_end_ms = end_ms
    rows: list[dict] = []
    calls = 0

    while cursor_end_ms > start_ms:
        candles = request_candles(session, coin, timeframe, start_ms, cursor_end_ms)
        calls += 1
        if not candles:
            break

        rows.extend(candles)
        first_ts_ms = min(int(candle["t"]) for candle in candles)
        next_end_ms = first_ts_ms - interval_ms
        if next_end_ms >= cursor_end_ms:
            break
        cursor_end_ms = next_end_ms

        if calls >= MAX_REQUESTS_PER_JOB:
            raise RuntimeError(f"Too many Hyperliquid requests for {pair} {timeframe}; aborting")

        # Public endpoint: be polite and avoid rate-limit spikes.
        time.sleep(0.5)

    if not rows:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    raw = pd.DataFrame(rows)
    dataframe = pd.DataFrame(
        {
            "date": pd.to_datetime(raw["t"], unit="ms", utc=True),
            "open": pd.to_numeric(raw["o"], errors="coerce"),
            "high": pd.to_numeric(raw["h"], errors="coerce"),
            "low": pd.to_numeric(raw["l"], errors="coerce"),
            "close": pd.to_numeric(raw["c"], errors="coerce"),
            "volume": pd.to_numeric(raw["v"], errors="coerce"),
        }
    )
    return dataframe.dropna().drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)


def store_ohlcv(datadir: Path, data_format: str, pair: str, timeframe: str, dataframe: pd.DataFrame) -> None:
    handler = get_datahandler(datadir, data_format=data_format)
    handler.ohlcv_store(pair, timeframe, dataframe, CandleType.FUTURES)


def iter_jobs(pairs: Iterable[str], timeframes: Iterable[str]) -> Iterable[tuple[str, str]]:
    for pair in pairs:
        for timeframe in timeframes:
            yield pair, timeframe


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Hyperliquid candles into Freqtrade user_data/data.")
    parser.add_argument("--pairs", nargs="+", required=True, help="Freqtrade pair names, e.g. BTC/USDC:USDC")
    parser.add_argument("--timeframes", nargs="+", required=True, help="Hyperliquid/Freqtrade timeframes, e.g. 15m 1h 4h")
    parser.add_argument("--timerange", required=True, help="YYYYMMDD- or YYYYMMDD-YYYYMMDD")
    parser.add_argument("--datadir", default="/freqtrade/user_data/data/hyperliquid", help="Freqtrade exchange data dir")
    parser.add_argument("--data-format", default="feather", choices=["feather", "json", "jsongz", "parquet"])
    args = parser.parse_args()

    start_ms, end_ms = parse_timerange(args.timerange)
    datadir = Path(args.datadir)
    datadir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    for pair, timeframe in iter_jobs(args.pairs, args.timeframes):
        dataframe = fetch_pair_timeframe(session, pair, timeframe, start_ms, end_ms)
        if dataframe.empty:
            raise RuntimeError(f"No candles returned for {pair} {timeframe} {args.timerange}")
        store_ohlcv(datadir, args.data_format, pair, timeframe, dataframe)
        first = dataframe["date"].iloc[0].isoformat()
        last = dataframe["date"].iloc[-1].isoformat()
        print(f"stored {pair} {timeframe}: {len(dataframe)} candles ({first} -> {last})")


if __name__ == "__main__":
    main()
