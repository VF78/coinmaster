"""Resumable, public-only Hyperliquid REST evidence capture.

This module is deliberately an importer, not a backtester.  The free REST
surface provides daily candles and historical funding rates, but not a
historical 24-month BBO/L2 or a settlement-mark oracle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from urllib.request import Request, urlopen

import pyarrow as pa
import pyarrow.parquet as pq


INFO_URL = "https://api.hyperliquid.xyz/info"
DAY_MS = 86_400_000
HOUR_MS = 3_600_000
DAILY_START = "2022-09-02T00:00:00+00:00"
DAILY_END = "2026-09-01T00:00:00+00:00"
FUNDING_START = "2024-09-01T00:00:00+00:00"


def milliseconds(value: str) -> int:
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def _save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def request(body: dict) -> object:
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    call = Request(INFO_URL, data=encoded, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(call, timeout=30) as response:  # nosec B310: fixed public HTTPS endpoint
        return json.loads(response.read())


def write_raw(root: Path, name: str, body: dict, response: object) -> dict[str, str]:
    capture = {"request_body": body, "captured_at": datetime.now(UTC).isoformat(), "response": response}
    encoded = json.dumps(capture, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    target = root / "raw" / f"{name}-{digest}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != encoded:
        raise RuntimeError(f"RAW_CONTENT_ADDRESS_COLLISION:{target}")
    if not target.exists():
        target.write_bytes(encoded)
    return {"path": str(target), "sha256": digest, "request_body": json.dumps(body, sort_keys=True, separators=(",", ":"))}


def _load_state(path: Path, stream: str, start_ms: int, end_ms: int) -> dict:
    if path.exists():
        state = json.loads(path.read_text())
        if (state["stream"], state["start_ms"], state["end_ms"]) != (stream, start_ms, end_ms):
            raise ValueError(f"RESUME_RANGE_CONFLICT:{path}")
        return state
    return {"stream": stream, "start_ms": start_ms, "end_ms": end_ms, "next_start_ms": start_ms, "raw": [], "completed": False}


def _capture_meta(root: Path) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    for name, body in (("meta", {"type": "meta"}), ("metaAndAssetCtxs", {"type": "metaAndAssetCtxs"})):
        evidence.append(write_raw(root / "hyperliquid", name, body, request(body)))
    return evidence


def fetch_candles(symbol: str, start_ms: int, end_ms: int, root: Path, max_pages: int | None = None) -> dict:
    """Capture 1d candles in immutable pages; API only exposes latest 5000."""
    directory = root / "hyperliquid" / symbol
    state_path = directory / "candle-1d.progress.json"
    state = _load_state(state_path, "candleSnapshot_1d", start_ms, end_ms)
    page = len(state["raw"])
    while not state["completed"]:
        if max_pages is not None and page >= max_pages:
            break
        body = {"type": "candleSnapshot", "req": {"coin": symbol, "interval": "1d", "startTime": state["next_start_ms"], "endTime": end_ms - 1}}
        response = request(body)
        if not isinstance(response, list):
            raise RuntimeError(f"CANDLE_RESPONSE_NOT_LIST:{symbol}")
        raw = write_raw(directory, f"candle-1d-{page:04d}", body, response)
        state["raw"].append({**raw, "rows": len(response)})
        rows = [row for row in response if start_ms <= int(row["t"]) < end_ms]
        if not rows:
            state["completed"] = True
        else:
            newest = max(int(row["t"]) for row in rows)
            if newest < state["next_start_ms"]:
                raise RuntimeError(f"CANDLE_NON_PROGRESS:{symbol}")
            state["next_start_ms"] = newest + DAY_MS
            state["completed"] = state["next_start_ms"] >= end_ms or len(response) < 5000
        _save(state_path, state)
        page += 1
        sleep(0.05)
    return state


def fetch_funding(symbol: str, start_ms: int, end_ms: int, root: Path, max_pages: int | None = None) -> dict:
    """Page public historical funding with strict local end-exclusive filtering."""
    directory = root / "hyperliquid" / symbol
    state_path = directory / "funding.progress.json"
    state = _load_state(state_path, "fundingHistory", start_ms, end_ms)
    page = len(state["raw"])
    while not state["completed"]:
        if max_pages is not None and page >= max_pages:
            break
        # Documented range results are capped at 500.  A 450-hour window
        # preserves overlap room while startTime stays inclusive.
        page_end = min(end_ms - 1, state["next_start_ms"] + 450 * HOUR_MS - 1)
        body = {"type": "fundingHistory", "coin": symbol, "startTime": state["next_start_ms"], "endTime": page_end}
        response = request(body)
        if not isinstance(response, list):
            raise RuntimeError(f"FUNDING_RESPONSE_NOT_LIST:{symbol}")
        raw = write_raw(directory, f"funding-{page:04d}", body, response)
        state["raw"].append({**raw, "rows": len(response)})
        rows = [row for row in response if start_ms <= int(row["time"]) < end_ms]
        if rows:
            newest = max(int(row["time"]) for row in rows)
            if newest < state["next_start_ms"]:
                raise RuntimeError(f"FUNDING_NON_PROGRESS:{symbol}")
            state["next_start_ms"] = max(state["next_start_ms"] + 1, newest + 1)
        else:
            state["next_start_ms"] = page_end + 1
        state["completed"] = state["next_start_ms"] >= end_ms
        _save(state_path, state)
        page += 1
        sleep(0.05)
    return state


def _captured_rows(state: dict, timestamp_key: str) -> list[dict]:
    rows: list[dict] = []
    for raw in state["raw"]:
        response = json.loads(Path(raw["path"]).read_text())["response"]
        rows.extend(row for row in response if state["start_ms"] <= int(row[timestamp_key]) < state["end_ms"])
    return rows


def normalize_candles(symbol: str, root: Path) -> dict:
    state = json.loads((root / "hyperliquid" / symbol / "candle-1d.progress.json").read_text())
    if not state["completed"]:
        return {"stream": "candleSnapshot_1d", "status": "PARTIAL_RESUMABLE", "next_start_ms": state["next_start_ms"]}
    rows, seen, duplicates = {}, set(), set()
    for row in _captured_rows(state, "t"):
        timestamp = int(row["t"])
        if timestamp in seen: duplicates.add(timestamp)
        seen.add(timestamp); rows[timestamp] = row
    expected = list(range(state["start_ms"], state["end_ms"], DAY_MS))
    missing = [timestamp for timestamp in expected if timestamp not in rows]
    values = [{"open_time_ms": timestamp, "close_time_ms": int(row["T"]), "open": row["o"], "high": row["h"], "low": row["l"], "close": row["c"], "volume": row["v"], "trades": int(row["n"]), "price_classification": "PROXY_PRICES_NONTRADING" if row["v"] == "0" or int(row["n"]) == 0 else "CANDLE_SNAPSHOT"} for timestamp, row in sorted(rows.items())]
    target = root / "normalized" / f"hyperliquid-{symbol}-daily.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(values), target, compression="zstd")
    return {"stream": "candleSnapshot_1d", "status": "COMPLETE", "rows": len(values), "expected": len(expected), "min_time_ms": min(rows) if rows else None, "max_time_ms": max(rows) if rows else None, "missing_count": len(missing), "missing_sample": missing[:100], "duplicate_count": len(duplicates), "off_grid_count": len([timestamp for timestamp in rows if timestamp % DAY_MS]), "parquet": str(target), "parquet_sha256": _sha(target), "proxy_prices_nontrading_count": sum(row["price_classification"] == "PROXY_PRICES_NONTRADING" for row in values)}


def normalize_funding(symbol: str, root: Path) -> dict:
    state = json.loads((root / "hyperliquid" / symbol / "funding.progress.json").read_text())
    if not state["completed"]:
        return {"stream": "fundingHistory", "status": "PARTIAL_RESUMABLE", "next_start_ms": state["next_start_ms"]}
    rows, seen, duplicates, offsets = {}, set(), set(), {}
    for row in _captured_rows(state, "time"):
        timestamp = int(row["time"]); bucket = timestamp // HOUR_MS * HOUR_MS
        if bucket in seen: duplicates.add(bucket)
        seen.add(bucket); rows[bucket] = row
        offset = timestamp - bucket; offsets[str(offset)] = offsets.get(str(offset), 0) + 1
    expected = list(range(state["start_ms"], state["end_ms"], HOUR_MS))
    missing = [timestamp for timestamp in expected if timestamp not in rows]
    values = [{"funding_hour_ms": bucket, "observed_time_ms": int(row["time"]), "funding_rate": row["fundingRate"], "premium": row.get("premium"), "settlement_mark": "UNKNOWN_FREE_REST_HAS_NO_SETTLEMENT_ORACLE"} for bucket, row in sorted(rows.items())]
    target = root / "normalized" / f"hyperliquid-{symbol}-funding.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(values), target, compression="zstd")
    nonzero_offsets = {offset: count for offset, count in offsets.items() if offset != "0"}
    return {"stream": "fundingHistory", "status": "COMPLETE", "rows": len(values), "expected_hourly": len(expected), "min_time_ms": min(rows) if rows else None, "max_time_ms": max(rows) if rows else None, "missing_count": len(missing), "missing_sample": missing[:100], "duplicate_hour_bucket_count": len(duplicates), "off_grid_observed_timestamp_count": sum(nonzero_offsets.values()), "off_grid_observed_timestamp_offset_samples_ms": sorted(nonzero_offsets)[:20], "parquet": str(target), "parquet_sha256": _sha(target), "settlement_oracle": "UNKNOWN_FREE_REST_HAS_NO_SETTLEMENT_ORACLE"}


def ingest(output: Path, daily_start: str = DAILY_START, daily_end: str = DAILY_END, funding_start: str = FUNDING_START, max_pages: int | None = None) -> Path:
    daily_start_ms, daily_end_ms, funding_start_ms = milliseconds(daily_start), milliseconds(daily_end), milliseconds(funding_start)
    if not daily_start_ms < funding_start_ms < daily_end_ms or daily_start_ms % DAY_MS or daily_end_ms % DAY_MS or funding_start_ms % HOUR_MS:
        raise ValueError("INVALID_HYPERLIQUID_INTERVAL")
    meta = _capture_meta(output)
    symbols = []
    for symbol in ("BTC", "SOL"):
        fetch_candles(symbol, daily_start_ms, daily_end_ms, output, max_pages)
        fetch_funding(symbol, funding_start_ms, daily_end_ms, output, max_pages)
        symbols.append({"symbol": symbol, "daily": normalize_candles(symbol, output), "funding": normalize_funding(symbol, output)})
    raw_paths = sorted((output / "hyperliquid").rglob("raw/*.json"))
    manifest = {"schema": "coinmaster-hyperliquid-public-rest-v1", "venue": "hyperliquid", "info_endpoint": INFO_URL, "captured_at": datetime.now(UTC).isoformat(), "daily_interval": {"start": daily_start, "end_exclusive": daily_end}, "funding_interval": {"start": funding_start, "end_exclusive": daily_end}, "meta_evidence": meta, "symbols": symbols, "raw_manifest_sha256": hashlib.sha256("".join(sorted(_sha(path) for path in raw_paths)).encode()).hexdigest(), "historical_profile_applicability": "UNKNOWN_CURRENT_META_ONLY", "faithful_comparable_1m_run_blockers": ["REST_MAX_5000_NO_24M_BBO", "AWS_REQUESTER_PAYS_INVENTORY_REQUIRED"], "limitations": ["Daily candleSnapshot prices with zero volume/trades are PROXY_PRICES_NONTRADING, not execution evidence.", "FundingHistory has no free-REST settlement-mark oracle.", "No Hyperliquid backtest or second simulator is authorized without historical 1m L2/BBO."]}
    target = output / "hyperliquid" / "manifest.json"
    _save(target, manifest)
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("var/data"))
    parser.add_argument("--max-pages", type=int)
    args = parser.parse_args()
    print(ingest(args.output, max_pages=args.max_pages))


if __name__ == "__main__":
    main()
