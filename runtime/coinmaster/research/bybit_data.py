"""Read-only, reproducible Bybit linear-market history ingestion.

Raw endpoint pages are immutable JSON files.  Normalized Parquet and its
manifest are derived artefacts under ``var/`` and are intentionally untracked.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import sleep
from urllib.parse import urlencode
from urllib.request import urlopen

import pyarrow as pa
import pyarrow.parquet as pq


BASE_URL = "https://api.bybit.com"
DAY_MS = 86_400_000
FUNDING_MS = 8 * 60 * 60 * 1000


@dataclass(frozen=True)
class GapReport:
    series: str
    symbol: str
    requested_start_ms: int
    requested_end_ms: int
    expected: int
    received: int
    missing: list[int]
    duplicate_timestamps: list[int]
    off_expected_schedule: list[int]


def milliseconds(value: str) -> int:
    return int(datetime.fromisoformat(value).replace(tzinfo=UTC).timestamp() * 1000)


def request(path: str, params: dict[str, str | int]) -> dict:
    url = f"{BASE_URL}{path}?{urlencode(params)}"
    with urlopen(url, timeout=30) as response:  # nosec B310: fixed public HTTPS host
        payload = json.loads(response.read())
    if payload.get("retCode") != 0:
        raise RuntimeError(f"Bybit {path}: {payload.get('retCode')} {payload.get('retMsg')}")
    return payload


def write_raw(root: Path, name: str, payload: dict) -> tuple[Path, str]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    digest = hashlib.sha256(body).hexdigest()
    target = root / "raw" / f"{Path(name).stem}-{digest}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != body:
        raise RuntimeError(f"raw content-addressed file collision: {target}")
    if not target.exists():
        target.write_bytes(body)
    return target, digest


def backwards_pages(path: str, params: dict[str, str | int], start_ms: int, end_ms: int, raw_root: Path, prefix: str, *, end_key: str = "end", limit: int = 1000) -> tuple[list[list[str]], list[dict[str, str]]]:
    """Use Bybit's reverse ordering with an exclusive next end boundary."""
    cursor = end_ms - 1
    rows: list[list[str]] = []
    raw: list[dict[str, str]] = []
    page = 0
    while cursor >= start_ms:
        payload = request(path, {**params, end_key: cursor, "limit": limit})
        values = payload["result"].get("list", [])
        target, digest = write_raw(raw_root, f"{prefix}-{page:04d}.json", payload)
        raw.append({"path": str(target), "sha256": digest})
        if not values:
            break
        rows.extend(values)
        oldest = min(int(item[0] if isinstance(item, list) else item["fundingRateTimestamp"]) for item in values)
        if oldest <= start_ms:
            break
        cursor = oldest - 1
        page += 1
        sleep(0.05)
    return rows, raw


def gaps(series: str, symbol: str, timestamps: list[int], start_ms: int, end_ms: int, interval_ms: int) -> GapReport:
    filtered = [item for item in timestamps if start_ms <= item < end_ms]
    unique = set(filtered)
    expected_times = list(range(start_ms, end_ms, interval_ms))
    expected_set = set(expected_times)
    missing = [item for item in expected_times if item not in unique]
    duplicates = sorted({item for item in filtered if filtered.count(item) > 1})
    return GapReport(series, symbol, start_ms, end_ms, len(expected_times), len(unique), missing, duplicates, sorted(unique - expected_set))


def interval_evidence(timestamps: list[int]) -> dict[str, int]:
    """Observed spacing only; it is not an assertion of the venue's official schedule."""
    ordered = sorted(set(timestamps))
    counts: dict[str, int] = {}
    for before, after in zip(ordered, ordered[1:]):
        key = str(after - before)
        counts[key] = counts.get(key, 0) + 1
    return counts


def ingest_symbol(symbol: str, start_ms: int, end_ms: int, root: Path) -> dict:
    raw_root = root / "bybit" / symbol
    kline, kline_raw = backwards_pages("/v5/market/kline", {"category": "linear", "symbol": symbol, "interval": "D"}, start_ms, end_ms, raw_root, "kline")
    mark, mark_raw = backwards_pages("/v5/market/mark-price-kline", {"category": "linear", "symbol": symbol, "interval": "D"}, start_ms, end_ms, raw_root, "mark")
    funding, funding_raw = backwards_pages("/v5/market/funding/history", {"category": "linear", "symbol": symbol}, start_ms, end_ms, raw_root, "funding", end_key="endTime", limit=200)
    kline_rows = {int(row[0]): row for row in kline if start_ms <= int(row[0]) < end_ms}
    mark_rows = {int(row[0]): row for row in mark if start_ms <= int(row[0]) < end_ms}
    funding_rows = {int(row["fundingRateTimestamp"]): row for row in funding if start_ms <= int(row["fundingRateTimestamp"]) < end_ms}
    data = []
    for timestamp, row in sorted(kline_rows.items()):
        data.append({"open_time_ms": timestamp, "open": row[1], "high": row[2], "low": row[3], "close": row[4], "volume": row[5], "turnover": row[6], "mark_close": mark_rows.get(timestamp, [None, None, None, None, None])[4]})
    normalized = root / "normalized" / f"bybit-{symbol}-daily.parquet"
    normalized.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(data), normalized, compression="zstd")
    funding_path = root / "normalized" / f"bybit-{symbol}-funding.parquet"
    pq.write_table(pa.Table.from_pylist([{"funding_time_ms": timestamp, "funding_rate": row["fundingRate"]} for timestamp, row in sorted(funding_rows.items())]), funding_path, compression="zstd")
    reports = [
        gaps("kline_daily", symbol, [int(row[0]) for row in kline], start_ms, end_ms, DAY_MS),
        gaps("mark_daily", symbol, [int(row[0]) for row in mark], start_ms, end_ms, DAY_MS),
        gaps("funding_8h", symbol, [int(row["fundingRateTimestamp"]) for row in funding], start_ms, end_ms, FUNDING_MS),
    ]
    return {"symbol": symbol, "raw": kline_raw + mark_raw + funding_raw, "normalized": [str(normalized), str(funding_path)], "reports": [asdict(report) for report in reports], "funding_interval_ms_observed": interval_evidence(list(funding_rows))}


def ingest(start: str, end: str, output: Path) -> Path:
    start_ms, end_ms = milliseconds(start), milliseconds(end)
    if start_ms >= end_ms:
        raise ValueError("start must precede end")
    manifest = {"venue": "bybit", "category": "linear", "requested_start": start, "requested_end_exclusive": end, "captured_at": datetime.now(UTC).isoformat(), "historical_tiers": "UNKNOWN_NOT_INFERRED_FROM_CURRENT_PROFILE", "account_fees": "UNKNOWN", "symbols": [ingest_symbol(symbol, start_ms, end_ms, output) for symbol in ("BTCUSDT", "SOLUSDT")]}
    raw_hashes = [item["sha256"] for symbol in manifest["symbols"] for item in symbol["raw"]]
    manifest["raw_manifest_sha256"] = hashlib.sha256("".join(sorted(raw_hashes)).encode()).hexdigest()
    target = output / "bybit" / "manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2022-09-02T00:00:00+00:00")
    parser.add_argument("--end", default="2026-09-01T00:00:00+00:00")
    parser.add_argument("--output", type=Path, default=Path("var/data"))
    args = parser.parse_args()
    print(ingest(args.start, args.end, args.output))


if __name__ == "__main__":
    main()
