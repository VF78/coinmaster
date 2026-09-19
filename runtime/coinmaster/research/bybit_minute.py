"""Resumable read-only Bybit 1-minute kline and mark-price ingestion.

The progress manifest advances only after a content-addressed raw response is
durably recorded.  It is safe to stop and resume, and never fabricates missing
minutes.  Minute closes remain an explicitly coarse intraminute execution and
liquidation assumption.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from time import sleep

import pyarrow as pa
import pyarrow.parquet as pq

from coinmaster.research.bybit_data import milliseconds, request, write_raw


MINUTE_MS = 60_000


def _save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _load_or_create(path: Path, stream: str, start_ms: int, end_ms: int) -> dict:
    if path.exists():
        state = json.loads(path.read_text())
        if state["start_ms"] != start_ms or state["end_ms"] != end_ms or state["stream"] != stream:
            raise ValueError(f"resume state conflicts with requested range: {path}")
        return state
    return {"stream": stream, "start_ms": start_ms, "end_ms": end_ms, "next_end_ms": end_ms - 1, "raw": [], "completed": False}


def fetch_stream(symbol: str, stream: str, start_ms: int, end_ms: int, root: Path, max_pages: int | None = None) -> dict:
    if stream not in {"execution", "mark"}:
        raise ValueError("stream must be execution or mark")
    directory = root / "bybit-1m" / symbol
    progress_path = directory / f"{stream}.progress.json"
    state = _load_or_create(progress_path, stream, start_ms, end_ms)
    if state["completed"]:
        return state
    endpoint = "/v5/market/kline" if stream == "execution" else "/v5/market/mark-price-kline"
    page = len(state["raw"])
    while state["next_end_ms"] >= start_ms:
        if max_pages is not None and page >= max_pages:
            break
        cursor = state["next_end_ms"]
        payload = request(endpoint, {"category": "linear", "symbol": symbol, "interval": "1", "end": cursor, "limit": 1000})
        rows = payload["result"].get("list", [])
        target, digest = write_raw(directory, f"{stream}-{page:06d}.json", payload)
        state["raw"].append({"path": str(target), "sha256": digest, "count": len(rows)})
        if not rows:
            state["completed"] = True
            _save(progress_path, state)
            break
        oldest = min(int(row[0]) for row in rows)
        if oldest >= cursor:
            raise RuntimeError(f"non-progressing Bybit page at {cursor} for {symbol}/{stream}")
        state["next_end_ms"] = oldest - 1
        if oldest <= start_ms:
            state["completed"] = True
        _save(progress_path, state)
        page += 1
        sleep(0.06)
    return state


def normalize(symbol: str, stream: str, root: Path) -> dict:
    progress_path = root / "bybit-1m" / symbol / f"{stream}.progress.json"
    state = json.loads(progress_path.read_text())
    if not state["completed"]:
        raise RuntimeError(f"cannot normalize incomplete stream: {progress_path}")
    rows: dict[int, list[str]] = {}
    seen: set[int] = set()
    duplicates: set[int] = set()
    for raw in state["raw"]:
        payload = json.loads(Path(raw["path"]).read_text())
        for row in payload["result"].get("list", []):
            timestamp = int(row[0])
            if not state["start_ms"] <= timestamp < state["end_ms"]:
                continue
            if timestamp in seen:
                duplicates.add(timestamp)
            seen.add(timestamp)
            rows[timestamp] = row
    expected = range(state["start_ms"], state["end_ms"], MINUTE_MS)
    missing = [timestamp for timestamp in expected if timestamp not in rows]
    table_rows = [{"open_time_ms": timestamp, "open": row[1], "high": row[2], "low": row[3], "close": row[4], **({"volume": row[5], "turnover": row[6]} if stream == "execution" else {})} for timestamp, row in sorted(rows.items())]
    target = root / "normalized" / f"bybit-{symbol}-{stream}-1m.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(table_rows), target, compression="zstd")
    body = target.read_bytes()
    return {"stream": stream, "symbol": symbol, "raw_pages": len(state["raw"]), "received": len(rows), "expected": len(range(state["start_ms"], state["end_ms"], MINUTE_MS)), "missing_count": len(missing), "duplicate_count": len(duplicates), "missing_sample": missing[:100], "parquet": str(target), "parquet_sha256": hashlib.sha256(body).hexdigest(), "assumptions": ["Minute close is available only at its minute end.", "Minute bars do not prove intraminute liquidity, liquidation trigger path, or funding settlement mark."]}


def ingest(start: str, end: str, output: Path, max_pages: int | None = None) -> Path:
    start_ms, end_ms = milliseconds(start), milliseconds(end)
    if start_ms >= end_ms or start_ms % MINUTE_MS or end_ms % MINUTE_MS:
        raise ValueError("range must be chronological and whole-minute UTC timestamps")
    report = {"venue": "bybit", "category": "linear", "start": start, "end_exclusive": end, "captured_at": datetime.now(UTC).isoformat(), "symbols": []}
    for symbol in ("BTCUSDT", "SOLUSDT"):
        item = {"symbol": symbol, "streams": []}
        for stream in ("execution", "mark"):
            fetch_stream(symbol, stream, start_ms, end_ms, output, max_pages)
            progress = json.loads((output / "bybit-1m" / symbol / f"{stream}.progress.json").read_text())
            item["streams"].append(normalize(symbol, stream, output) if progress["completed"] else {"stream": stream, "status": "PARTIAL_RESUMABLE", "next_end_ms": progress["next_end_ms"], "raw_pages": len(progress["raw"])})
        report["symbols"].append(item)
    target = output / "bybit-1m" / "manifest.json"
    _save(target, report)
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2024-09-01T00:00:00+00:00")
    parser.add_argument("--end", default="2026-09-01T00:00:00+00:00")
    parser.add_argument("--output", type=Path, default=Path("var/data"))
    parser.add_argument("--max-pages", type=int)
    args = parser.parse_args()
    print(ingest(args.start, args.end, args.output, args.max_pages))


if __name__ == "__main__":
    main()
