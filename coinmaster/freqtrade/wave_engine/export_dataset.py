#!/usr/bin/env python3
"""Export Freqtrade OHLCV candles into the Wave Engine stdlib research dataset format.

Research-only helper. It reads local feather data and writes JSON; it does not touch
running bot config, services, orders, or databases.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from freqtrade.data.history import get_datahandler
from freqtrade.enums import CandleType


def _to_utc(value: str | None, fallback: datetime | None = None) -> datetime | None:
    if value is None:
        return fallback
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def _load_frame(datadir: Path, pair: str, timeframe: str, start: datetime, end: datetime | None) -> pd.DataFrame:
    handler = get_datahandler(datadir, data_format="feather")
    frame = handler.ohlcv_load(pair, timeframe, CandleType.FUTURES, warn_no_data=False)
    if frame is None or frame.empty:
        raise RuntimeError(f"no OHLCV data for {pair} {timeframe} in {datadir}")
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], utc=True)
    out = out.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    out = out[out["date"] >= pd.Timestamp(start)]
    if end is not None:
        out = out[out["date"] <= pd.Timestamp(end)]
    if out.empty:
        raise RuntimeError(f"empty OHLCV slice for {pair} {timeframe} after date filtering")
    return out.reset_index(drop=True)


def _rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in frame.itertuples(index=False):
        rows.append(
            {
                "timestamp": pd.Timestamp(row.date).to_pydatetime().astimezone(UTC).isoformat(),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": float(getattr(row, "volume", 0.0) or 0.0),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Wave Engine research dataset from Freqtrade OHLCV data.")
    parser.add_argument("--pair", required=True)
    parser.add_argument("--start", required=True, help="ISO date/time, e.g. 2026-01-01")
    parser.add_argument("--end", help="Optional ISO date/time")
    parser.add_argument("--datadir", default="/freqtrade/user_data/data/hyperliquid")
    parser.add_argument("--timeframes", nargs="+", default=["4h", "1h", "15m", "5m"])
    parser.add_argument("--output", help="Write JSON to this path instead of stdout")
    args = parser.parse_args()

    start = _to_utc(args.start)
    if start is None:
        raise RuntimeError("start is required")
    end = _to_utc(args.end)
    payload = {
        "pair": args.pair,
        "start": start.isoformat(),
        "end": end.isoformat() if end else None,
        "candles": {},
    }
    for timeframe in args.timeframes:
        frame = _load_frame(Path(args.datadir), args.pair, timeframe, start, end)
        payload["candles"][timeframe] = _rows(frame)

    text = json.dumps(payload, ensure_ascii=False)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
