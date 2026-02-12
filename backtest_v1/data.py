from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib import request

from .config import BacktestConfig

REQUIRED_COLS = ["timestamp", "open", "high", "low", "close", "volume"]
INTERVAL_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
}


@dataclass
class CandleData:
    candles: list[dict]
    meta: dict


def _parse_ts(v: str) -> datetime:
    v = v.replace("Z", "+00:00")
    return datetime.fromisoformat(v).astimezone(timezone.utc)


def _resolve_end_utc(v: str) -> datetime:
    if v == "yesterday_23_59_utc":
        now = datetime.now(timezone.utc)
        y = now.date() - timedelta(days=1)
        return datetime(y.year, y.month, y.day, 23, 59, 0, tzinfo=timezone.utc)
    return _parse_ts(v)


def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


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


def _write_csv(path: Path, candles: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REQUIRED_COLS)
        w.writeheader()
        for c in candles:
            w.writerow(
                {
                    "timestamp": c["timestamp"].isoformat().replace("+00:00", "Z"),
                    "open": c["open"],
                    "high": c["high"],
                    "low": c["low"],
                    "close": c["close"],
                    "volume": c["volume"],
                }
            )


def _fetch_hl_chunk(info_url: str, coin: str, interval: str, start_ms: int, end_ms: int) -> list[dict]:
    payload = {
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": interval,
            "startTime": start_ms,
            "endTime": end_ms,
        },
    }
    req = request.Request(
        info_url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=30) as resp:
        raw = json.loads(resp.read().decode())

    out = []
    for x in raw:
        # Hyperliquid shape: t,o,h,l,c,v (strings for numerics)
        ts = datetime.fromtimestamp(int(x["t"]) / 1000, tz=timezone.utc)
        out.append(
            {
                "timestamp": ts,
                "open": float(x["o"]),
                "high": float(x["h"]),
                "low": float(x["l"]),
                "close": float(x["c"]),
                "volume": float(x.get("v", 0.0)),
            }
        )
    out.sort(key=lambda c: c["timestamp"])
    return out


def _discover_earliest_available(
    info_url: str,
    coin: str,
    requested_start: datetime,
    end_utc: datetime,
) -> tuple[datetime | None, int]:
    """
    Coarse backward scan using 1h data to avoid wasting hundreds of empty requests
    when requested start is earlier than exchange availability.
    """
    scan_calls = 0
    step = timedelta(days=30)
    probe_end = end_utc
    earliest: datetime | None = None
    seen_data = False

    while probe_end > requested_start:
        probe_start = max(requested_start, probe_end - step)
        rows = _fetch_hl_chunk(
            info_url,
            coin,
            "1h",
            _to_ms(probe_start),
            _to_ms(probe_end),
        )
        scan_calls += 1

        if rows:
            seen_data = True
            earliest = rows[0]["timestamp"] if earliest is None else min(earliest, rows[0]["timestamp"])
        elif seen_data:
            break

        probe_end = probe_start

    return earliest, scan_calls


def fetch_hyperliquid_candles(
    info_url: str,
    coin: str,
    interval: str,
    start_utc: datetime,
    end_utc: datetime,
    chunk_bars: int,
) -> tuple[list[dict], dict]:
    if interval not in INTERVAL_MS:
        raise ValueError(f"Unsupported interval: {interval}")
    if end_utc <= start_utc:
        return [], {"warning": "empty_range"}

    interval_ms = INTERVAL_MS[interval]

    start_ms = _to_ms(start_utc)
    cursor_end_ms = _to_ms(end_utc)

    all_rows: list[dict] = []
    calls = 0

    # Backward pagination:
    # candleSnapshot tends to return the latest chunk inside [start, end].
    # We repeatedly move end backward by the first returned candle timestamp.
    while cursor_end_ms > start_ms:
        rows = _fetch_hl_chunk(info_url, coin, interval, start_ms, cursor_end_ms)
        calls += 1
        if not rows:
            break

        all_rows.extend(rows)

        first_ts_ms = _to_ms(rows[0]["timestamp"])
        next_end = first_ts_ms - interval_ms
        if next_end >= cursor_end_ms:
            break
        cursor_end_ms = next_end

        # safety brake
        if calls > 2000:
            break

    # de-dup by timestamp and clip to requested range
    dedup = {}
    for r in all_rows:
        if start_utc <= r["timestamp"] <= end_utc:
            dedup[r["timestamp"]] = r
    candles = [dedup[k] for k in sorted(dedup.keys())]

    meta = {
        "calls": calls,
        "requested_start": start_utc.isoformat(),
        "requested_end": end_utc.isoformat(),
        "interval": interval,
        "coin": coin,
        "count": len(candles),
    }

    if candles:
        meta["actual_start"] = candles[0]["timestamp"].isoformat()
        meta["actual_end"] = candles[-1]["timestamp"].isoformat()
    else:
        meta["warning"] = "no_candles_returned"

    return candles, meta


def _load_csv(path: Path) -> list[dict]:
    with path.open("r", newline="") as f:
        rows = list(csv.DictReader(f))
    return _ensure_schema(rows)


def generate_synthetic_ohlcv(rows: int = 3000, seed: int = 7) -> list[dict]:
    import random

    random.seed(seed)
    candles = []
    ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
    close = 42_000.0

    for _ in range(rows):
        drift = 0.00008
        noise = random.uniform(-0.0018, 0.0018)
        next_close = close * (1 + drift + noise)
        open_ = close
        spread = max(2.0, close * random.uniform(0.0003, 0.0013))
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

    return candles


def load_candles(cfg: BacktestConfig) -> CandleData:
    csv_path = Path(cfg.csv_path)

    if cfg.data_source == "csv":
        candles = _load_csv(csv_path)
        return CandleData(candles=candles, meta={"source": "csv", "count": len(candles)})

    if cfg.data_source == "synthetic":
        candles = generate_synthetic_ohlcv()
        return CandleData(candles=candles, meta={"source": "synthetic", "count": len(candles)})

    if cfg.data_source != "hyperliquid":
        raise ValueError("data_source must be one of: hyperliquid|csv|synthetic")

    start_utc = _parse_ts(cfg.start_utc)
    end_utc = _resolve_end_utc(cfg.end_utc)

    candles, meta = fetch_hyperliquid_candles(
        info_url=cfg.hyperliquid_info_url,
        coin=cfg.coin,
        interval=cfg.base_interval,
        start_utc=start_utc,
        end_utc=end_utc,
        chunk_bars=cfg.fetch_chunk_bars,
    )

    if not candles:
        # Fallback to synthetic so the run stays executable.
        syn = generate_synthetic_ohlcv()
        return CandleData(candles=syn, meta={"source": "synthetic_fallback", **meta})

    if cfg.persist_fetched_csv:
        _write_csv(csv_path, candles)

    return CandleData(candles=candles, meta={"source": "hyperliquid", **meta})
