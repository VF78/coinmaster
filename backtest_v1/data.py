from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


REQUIRED_COLS = ["timestamp", "open", "high", "low", "close", "volume"]


@dataclass
class CandleData:
    candles: list[dict]


def _parse_ts(v: str) -> datetime:
    v = v.replace("Z", "+00:00")
    return datetime.fromisoformat(v).astimezone(timezone.utc)


def _ensure_schema(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        for c in REQUIRED_COLS:
            if c not in row:
                raise ValueError(f"Missing required column: {c}")
        out.append(
            {
                "timestamp": _parse_ts(str(row["timestamp"])),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
        )
    out.sort(key=lambda x: x["timestamp"])
    return out


def generate_synthetic_ohlcv(rows: int = 2000, seed: int = 7) -> CandleData:
    random.seed(seed)
    candles = []
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    close = 42000.0

    for _ in range(rows):
        drift = 0.0001
        noise = random.uniform(-0.0015, 0.0015)
        next_close = close * (1 + drift + noise)
        open_ = close
        spread = max(2.0, close * random.uniform(0.0003, 0.0012))
        high = max(open_, next_close) + spread
        low = min(open_, next_close) - spread
        volume = random.uniform(10, 100)

        candles.append(
            {
                "timestamp": ts,
                "open": open_,
                "high": high,
                "low": low,
                "close": next_close,
                "volume": volume,
            }
        )
        close = next_close
        ts += timedelta(minutes=1)

    return CandleData(candles=candles)


def load_candles(csv_path: str | Path) -> CandleData:
    path = Path(csv_path)
    if path.exists():
        with path.open("r", newline="") as f:
            rows = list(csv.DictReader(f))
        return CandleData(candles=_ensure_schema(rows))

    # TODO: wire Hyperliquid historical candles endpoint here.
    return generate_synthetic_ohlcv()
