"""Verified, source-preserving Bybit signal warmup for Stage-G/HL Sandbox."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


DAY_MS = 86_400_000
WARMUP_MS = 730 * DAY_MS
SYMBOLS = ("BTCUSDT", "SOLUSDT")
DAILY_FIELDS = ("open", "high", "low", "close", "volume", "turnover", "mark_close")
EXPECTED_SOURCE_MANIFEST_SHA256 = {
    "base": "a3ece5d12a229a6bbb7d64d079f7b2c78e914eef46867d8df1e95935c9bcac74",
    "tail": "d2e1ff66be91a81a9680a1483ea924836e765fca0a7903ee6f2e532377f836b7",
}
EXPECTED_RAW_MANIFEST_SHA256 = {
    "base": "3bae960f2cecbd87f36e4f7c291c12632c39e44f3fdcd56093a48749d7476280",
    "tail": "7b49087f049d056dbf830d43745794283b8b0284536b8bf060b97e23de314ef4",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_raw_hash(path: Path) -> str:
    raw = json.loads(path.read_text())
    content = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(content).hexdigest()


def _manifest_raw_inputs(manifest_path: Path, raw_root: Path, *, normalize_absolute_paths: bool) -> list[dict[str, str]]:
    manifest = json.loads(manifest_path.read_text())
    hashes: list[str] = []
    result: list[dict[str, str]] = []
    for symbol in manifest["symbols"]:
        for item in symbol["raw"]:
            raw_path = Path(item["path"])
            marker = "/bybit/"
            raw_text = str(raw_path)
            if normalize_absolute_paths:
                if marker not in raw_text:
                    raise ValueError("RAW_SOURCE_PATH_NOT_CANONICALIZABLE")
                relative = Path("bybit") / raw_text.split(marker, 1)[1]
            else:
                parts = raw_path.parts
                if "bybit" not in parts:
                    raise ValueError("RAW_SOURCE_PATH_NOT_CANONICALIZABLE")
                relative = Path(*parts[parts.index("bybit"):])
            source = raw_root / relative
            expected = item["sha256"]
            if _sha256(source) != expected or _canonical_raw_hash(source) != expected:
                raise ValueError(f"RAW_SOURCE_HASH_MISMATCH:{relative}")
            result.append({"path": relative.as_posix(), "sha256": expected})
            hashes.append(expected)
    combined = hashlib.sha256("".join(sorted(hashes)).encode()).hexdigest()
    if combined != manifest["raw_manifest_sha256"]:
        raise ValueError("RAW_SOURCE_MANIFEST_HASH_MISMATCH")
    return result


def _validate_coverage(manifest: dict, *, require_daily_complete: bool) -> None:
    for symbol in SYMBOLS:
        item = next((entry for entry in manifest["symbols"] if entry["symbol"] == symbol), None)
        if item is None:
            raise ValueError(f"WARMUP_SOURCE_SYMBOL_MISSING:{symbol}")
        for report in item["reports"]:
            if report["series"] not in {"kline_daily", "mark_daily"}:
                continue
            if report["missing"] or report["duplicate_timestamps"] or report["off_expected_schedule"]:
                raise ValueError(f"WARMUP_SOURCE_DAILY_COVERAGE_INVALID:{symbol}:{report['series']}")
            if require_daily_complete and report["expected"] != report["received"]:
                raise ValueError(f"WARMUP_SOURCE_DAILY_INCOMPLETE:{symbol}:{report['series']}")


def _validate_daily_rows(rows: list[dict], *, symbol: str) -> None:
    previous: int | None = None
    for row in rows:
        ts = int(row["open_time_ms"])
        if ts % DAY_MS or (previous is not None and ts - previous != DAY_MS):
            raise ValueError(f"WARMUP_DAILY_SESSION_GAP_OR_OFF_GRID:{symbol}:{ts}")
        previous = ts
        values = {name: float(row[name]) for name in DAILY_FIELDS}
        if any(not math.isfinite(value) for value in values.values()):
            raise ValueError(f"WARMUP_NONFINITE_DAILY_VALUE:{symbol}:{ts}")
        if any(values[name] <= 0 for name in ("open", "high", "low", "close", "mark_close")):
            raise ValueError(f"WARMUP_NONPOSITIVE_PRICE:{symbol}:{ts}")
        if values["volume"] < 0 or values["turnover"] < 0:
            raise ValueError(f"WARMUP_NEGATIVE_VOLUME_OR_TURNOVER:{symbol}:{ts}")
        if values["high"] < max(values["open"], values["close"]) or values["low"] > min(values["open"], values["close"]) or values["high"] < values["low"]:
            raise ValueError(f"WARMUP_INVALID_OHLC:{symbol}:{ts}")


def _rebuild_daily_from_raw(manifest: dict, raw_root: Path, symbol: str) -> list[dict]:
    source = next(item for item in manifest["symbols"] if item["symbol"] == symbol)
    start_ms = int(datetime.fromisoformat(manifest["requested_start"].replace("Z", "+00:00")).timestamp() * 1000)
    end_ms = int(datetime.fromisoformat(manifest["requested_end_exclusive"].replace("Z", "+00:00")).timestamp() * 1000)
    klines: dict[int, list] = {}
    marks: dict[int, list] = {}
    for item in source["raw"]:
        relative = item["path"]
        parts = Path(relative).parts
        if "bybit" in parts:
            relative = Path(*parts[parts.index("bybit"):]).as_posix()
        raw_path = raw_root / relative
        if "/kline-" not in f"/{relative}" and "/mark-" not in f"/{relative}":
            continue
        target = klines if "/kline-" in f"/{relative}" else marks
        for row in json.loads(raw_path.read_text())["result"]["list"]:
            timestamp = int(row[0])
            if start_ms <= timestamp < end_ms:
                target[timestamp] = row
    if set(klines) != set(marks):
        raise ValueError(f"RAW_DAILY_KLINE_MARK_MISMATCH:{symbol}")
    return [
        {
            "open_time_ms": timestamp,
            "open": klines[timestamp][1], "high": klines[timestamp][2],
            "low": klines[timestamp][3], "close": klines[timestamp][4],
            "volume": klines[timestamp][5], "turnover": klines[timestamp][6],
            "mark_close": marks[timestamp][4],
        }
        for timestamp in sorted(klines)
    ]


def _daily_rows_equal(left: list[dict], right: list[dict]) -> bool:
    if len(left) != len(right):
        return False
    for first, second in zip(left, right, strict=True):
        if int(first["open_time_ms"]) != int(second["open_time_ms"]):
            return False
        if any(Decimal(str(first[name])) != Decimal(str(second[name])) for name in DAILY_FIELDS):
            return False
    return True


def prepare_stageg_bybit_warmup(*, base_root: Path, tail_root: Path, output_root: Path, now_ms: int | None = None) -> Path:
    """Create a new immutable-by-convention merged signal artifact.

    ``base_root`` and ``tail_root`` each contain ``bybit/manifest.json`` and
    ``normalized`` data. The destination must not already exist. No input or
    canonical artifact is edited.
    """
    if output_root.exists():
        raise FileExistsError("REFUSE_TO_OVERWRITE_STAGEG_WARMUP_ARTIFACT")
    base_manifest_path = base_root / "bybit/manifest.json"
    tail_manifest_path = tail_root / "bybit/manifest.json"
    base_manifest = json.loads(base_manifest_path.read_text())
    tail_manifest = json.loads(tail_manifest_path.read_text())
    if (base_manifest.get("venue"), base_manifest.get("category")) != ("bybit", "linear"):
        raise ValueError("BASE_SIGNAL_SOURCE_NOT_BYBIT_LINEAR")
    if (tail_manifest.get("venue"), tail_manifest.get("category")) != ("bybit", "linear"):
        raise ValueError("TAIL_SIGNAL_SOURCE_NOT_BYBIT_LINEAR")
    if base_manifest["requested_end_exclusive"] != tail_manifest["requested_start"]:
        raise ValueError("WARMUP_SOURCE_BOUNDARY_MISMATCH")
    if tail_manifest["requested_end_exclusive"] != "2026-09-22T00:00:00+00:00":
        raise ValueError("TAIL_END_DATE_NOT_EXPECTED")
    _validate_coverage(base_manifest, require_daily_complete=True)
    _validate_coverage(tail_manifest, require_daily_complete=True)

    paper_manifest_path = base_root / "paper-warmup-manifest.json"
    paper_manifest = json.loads(paper_manifest_path.read_text())
    if paper_manifest.get("schema") != "coinmaster-paper-warmup-v1":
        raise ValueError("BASE_WARMUP_MANIFEST_SCHEMA_MISMATCH")
    if _sha256(base_manifest_path) != paper_manifest.get("source_manifest_sha256"):
        raise ValueError("BASE_SOURCE_MANIFEST_HASH_MISMATCH")

    output_root.mkdir(parents=True)
    sources_root = output_root / "sources"
    (sources_root / "base").mkdir(parents=True)
    (sources_root / "tail").mkdir(parents=True)
    shutil.copy2(base_manifest_path, sources_root / "base/manifest.json")
    shutil.copy2(tail_manifest_path, sources_root / "tail/manifest.json")
    shutil.copy2(paper_manifest_path, sources_root / "base/paper-warmup-manifest.json")
    source_inputs: dict[str, dict] = {}
    for source_name, source_manifest, source_root, source_out, normalize in (
        ("base", base_manifest, base_root, sources_root / "base", False),
        ("tail", tail_manifest, tail_root, sources_root / "tail", True),
    ):
        raw_inputs = _manifest_raw_inputs(
            source_root / "bybit/manifest.json" if source_name == "tail" else base_manifest_path,
            source_root if source_name == "tail" else base_root,
            normalize_absolute_paths=normalize,
        )
        copied: list[dict[str, str]] = []
        for item in raw_inputs:
            src = source_root / item["path"]
            dest = source_out / item["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied.append({"path": dest.relative_to(output_root).as_posix(), "sha256": item["sha256"]})
        source_inputs[source_name] = {
            "manifest_path": (source_out / "manifest.json").relative_to(output_root).as_posix(),
            "manifest_sha256": _sha256(source_out / "manifest.json"),
            "raw_manifest_sha256": source_manifest["raw_manifest_sha256"],
            "raw_files": copied,
        }
        if source_inputs[source_name]["manifest_sha256"] != EXPECTED_SOURCE_MANIFEST_SHA256[source_name]:
            raise ValueError(f"UNEXPECTED_STAGEG_SOURCE_MANIFEST:{source_name}")
        if source_inputs[source_name]["raw_manifest_sha256"] != EXPECTED_RAW_MANIFEST_SHA256[source_name]:
            raise ValueError(f"UNEXPECTED_STAGEG_RAW_MANIFEST:{source_name}")

    import pyarrow.parquet as parquet
    symbols: dict[str, dict] = {}
    normalized_root = output_root / "normalized"
    normalized_root.mkdir()
    for symbol in SYMBOLS:
        base_item = paper_manifest["symbols"][symbol]
        base_daily_path = base_root / base_item["daily_path"]
        base_funding_path = base_root / base_item["funding_path"]
        if _sha256(base_daily_path) != base_item["daily_sha256"] or _sha256(base_funding_path) != base_item["funding_sha256"]:
            raise ValueError(f"BASE_NORMALIZED_HASH_MISMATCH:{symbol}")
        base_rows = parquet.read_table(base_daily_path).to_pylist()
        tail_daily_path = tail_root / "normalized" / f"bybit-{symbol}-daily.parquet"
        tail_rows = parquet.read_table(tail_daily_path).to_pylist()
        rebuilt_base = _rebuild_daily_from_raw(base_manifest, base_root, symbol)
        rebuilt_tail = _rebuild_daily_from_raw(tail_manifest, tail_root, symbol)
        if not _daily_rows_equal(base_rows, rebuilt_base):
            raise ValueError(f"BASE_DAILY_NOT_REPRODUCIBLE_FROM_RAW:{symbol}")
        if not _daily_rows_equal(tail_rows, rebuilt_tail):
            raise ValueError(f"TAIL_DAILY_NOT_REPRODUCIBLE_FROM_RAW:{symbol}")
        rows = sorted(base_rows + tail_rows, key=lambda row: int(row["open_time_ms"]))
        if len({int(row["open_time_ms"]) for row in rows}) != len(rows):
            raise ValueError(f"WARMUP_DUPLICATE_SESSION:{symbol}")
        _validate_daily_rows(rows, symbol=symbol)
        target = normalized_root / f"bybit-{symbol}-daily.parquet"
        pq.write_table(pa.Table.from_pylist(rows), target, compression="zstd")
        symbols[symbol] = {
            "signal_source": "BYBIT_LINEAR_PUBLIC_DAILY_KLINE",
            "daily_path": target.relative_to(output_root).as_posix(),
            "daily_sha256": _sha256(target),
            "daily_rows": len(rows),
            "first_open_ms": int(rows[0]["open_time_ms"]),
            "last_open_ms": int(rows[-1]["open_time_ms"]),
            "last_completed_close_ms": int(rows[-1]["open_time_ms"]) + DAY_MS,
            "daily_gaps": 0,
            "daily_duplicates": 0,
            "mark_close_provenance": "BYBIT_LINEAR_PUBLIC_DAILY_MARK_KLINE",
            "mark_close_complete": all(row.get("mark_close") is not None for row in rows),
        }
    if symbols["BTCUSDT"]["first_open_ms"] != symbols["SOLUSDT"]["first_open_ms"] or symbols["BTCUSDT"]["last_open_ms"] != symbols["SOLUSDT"]["last_open_ms"]:
        raise ValueError("WARMUP_SYMBOL_SESSION_RANGE_MISMATCH")

    now_ms = int(datetime.now(UTC).timestamp() * 1000) if now_ms is None else now_ms
    last_close = symbols["BTCUSDT"]["last_completed_close_ms"]
    current_session_open = now_ms // DAY_MS * DAY_MS
    if last_close != current_session_open:
        raise ValueError("WARMUP_LATEST_COMPLETED_SESSION_MISSING")
    if last_close - symbols["BTCUSDT"]["first_open_ms"] < WARMUP_MS:
        raise ValueError("WARMUP_SHORTER_THAN_24_MONTHS")

    tail_funding_off_grid = {
        item["symbol"]: {
            report["series"]: len(report["off_expected_schedule"])
            for report in item["reports"]
            if report["series"] == "funding_8h"
        }
        for item in tail_manifest["symbols"]
    }
    base_funding_off_grid = {
        item["symbol"]: {
            report["series"]: len(report["off_expected_schedule"])
            for report in item["reports"]
            if report["series"] == "funding_8h"
        }
        for item in base_manifest["symbols"]
    }
    result = {
        "schema": "coinmaster-stageg-bybit-signal-warmup-v1",
        "venue": "bybit",
        "category": "linear",
        "captured_at": datetime.now(UTC).isoformat(),
        "signal_source": "BYBIT_LINEAR_PUBLIC_DAILY_KLINE",
        "execution_source": "HYPERLIQUID_PUBLIC_MAINNET_MARK_AND_QUOTE",
        "warmup_start_ms": symbols["BTCUSDT"]["first_open_ms"],
        "warmup_end_exclusive_ms": last_close,
        "completed_sessions": len(pq.read_table(normalized_root / "bybit-BTCUSDT-daily.parquet").to_pylist()),
        "provenance": source_inputs,
        "funding": {
            "strategy_warmup_usage": "NOT_USED_FOR_HL_SANDBOX_CASH",
            "current_source": "PUBLIC_HYPERLIQUID_MARK_AND_FUNDING_OBSERVATIONS_ONLY",
            "historical_bybit_off_grid_funding_timestamps": {
                "base": base_funding_off_grid,
                "tail": tail_funding_off_grid,
            },
            "hl_funding_cash": "UNPOSTED_UNTIL_CAUSAL_SETTLEMENT_AND_NATIVE_SANDBOX_CASH_POSTING_ARE_VERIFIED",
        },
        "symbols": symbols,
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return manifest_path


def extend_stageg_bybit_warmup(*, predecessor_manifest: Path, tail_root: Path, output_root: Path, now_ms: int | None = None) -> Path:
    """Append a newly captured public daily tail without rewriting prior evidence.

    The result embeds a complete predecessor artifact plus the new,
    content-addressed Bybit pages. It is deliberately a new v2 artifact, so a
    restart can validate every inherited and appended byte without relying on
    a mutable data mount.
    """
    if output_root.exists():
        raise FileExistsError("REFUSE_TO_OVERWRITE_STAGEG_WARMUP_ARTIFACT")
    predecessor = json.loads(predecessor_manifest.read_text())
    predecessor_end = int(predecessor["warmup_end_exclusive_ms"])
    predecessor_rows, predecessor_state = load_stageg_bybit_warmup(predecessor_manifest, now_ms=predecessor_end)
    if predecessor_state != "READY":
        raise ValueError(f"PREDECESSOR_WARMUP_NOT_VERIFIED:{predecessor_state}")
    tail_manifest_path = tail_root / "bybit" / "manifest.json"
    tail_manifest = json.loads(tail_manifest_path.read_text())
    if (tail_manifest.get("venue"), tail_manifest.get("category")) != ("bybit", "linear"):
        raise ValueError("TAIL_SIGNAL_SOURCE_NOT_BYBIT_LINEAR")
    if int(datetime.fromisoformat(tail_manifest["requested_start"].replace("Z", "+00:00")).timestamp() * 1000) != predecessor_end:
        raise ValueError("WARMUP_SOURCE_BOUNDARY_MISMATCH")
    _validate_coverage(tail_manifest, require_daily_complete=True)
    now_ms = int(datetime.now(UTC).timestamp() * 1000) if now_ms is None else now_ms
    tail_end = int(datetime.fromisoformat(tail_manifest["requested_end_exclusive"].replace("Z", "+00:00")).timestamp() * 1000)
    if tail_end != now_ms // DAY_MS * DAY_MS:
        raise ValueError("WARMUP_LATEST_COMPLETED_SESSION_MISSING")

    output_root.mkdir(parents=True)
    predecessor_out = output_root / "sources" / "predecessor"
    shutil.copytree(predecessor_manifest.parent, predecessor_out)
    append_out = output_root / "sources" / "append"
    append_out.mkdir(parents=True)
    shutil.copy2(tail_manifest_path, append_out / "manifest.json")
    raw_inputs = _manifest_raw_inputs(tail_manifest_path, tail_root, normalize_absolute_paths=True)
    appended_raw: list[dict[str, str]] = []
    for item in raw_inputs:
        source, destination = tail_root / item["path"], append_out / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        appended_raw.append({"path": destination.relative_to(output_root).as_posix(), "sha256": item["sha256"]})

    normalized_root = output_root / "normalized"
    normalized_root.mkdir()
    symbols: dict[str, dict] = {}
    for symbol in SYMBOLS:
        appended = _rebuild_daily_from_raw(tail_manifest, tail_root, symbol)
        rows = list(predecessor_rows[symbol]) + appended
        if len({int(row["open_time_ms"]) for row in rows}) != len(rows):
            raise ValueError(f"WARMUP_DUPLICATE_SESSION:{symbol}")
        _validate_daily_rows(rows, symbol=symbol)
        target = normalized_root / f"bybit-{symbol}-daily.parquet"
        pq.write_table(pa.Table.from_pylist(rows), target, compression="zstd")
        symbols[symbol] = {
            "signal_source": "BYBIT_LINEAR_PUBLIC_DAILY_KLINE",
            "daily_path": target.relative_to(output_root).as_posix(),
            "daily_sha256": _sha256(target), "daily_rows": len(rows),
            "first_open_ms": int(rows[0]["open_time_ms"]),
            "last_open_ms": int(rows[-1]["open_time_ms"]),
            "last_completed_close_ms": int(rows[-1]["open_time_ms"]) + DAY_MS,
            "daily_gaps": 0, "daily_duplicates": 0,
            "mark_close_provenance": "BYBIT_LINEAR_PUBLIC_DAILY_MARK_KLINE",
            "mark_close_complete": all(row.get("mark_close") is not None for row in rows),
        }
    if symbols["BTCUSDT"]["last_completed_close_ms"] != tail_end or symbols["SOLUSDT"]["last_completed_close_ms"] != tail_end:
        raise ValueError("WARMUP_SYMBOL_SESSION_RANGE_MISMATCH")
    manifest = {
        "schema": "coinmaster-stageg-bybit-signal-warmup-v2",
        "venue": "bybit", "category": "linear",
        "captured_at": datetime.now(UTC).isoformat(),
        "signal_source": "BYBIT_LINEAR_PUBLIC_DAILY_KLINE",
        "execution_source": "HYPERLIQUID_PUBLIC_MAINNET_MARK_AND_QUOTE",
        "warmup_start_ms": symbols["BTCUSDT"]["first_open_ms"],
        "warmup_end_exclusive_ms": tail_end,
        "completed_sessions": symbols["BTCUSDT"]["daily_rows"],
        "provenance": {
            "predecessor_manifest_path": (predecessor_out / "manifest.json").relative_to(output_root).as_posix(),
            "predecessor_manifest_sha256": _sha256(predecessor_out / "manifest.json"),
            "append_manifest_path": (append_out / "manifest.json").relative_to(output_root).as_posix(),
            "append_manifest_sha256": _sha256(append_out / "manifest.json"),
            "append_raw_manifest_sha256": tail_manifest["raw_manifest_sha256"],
            "append_raw_files": appended_raw,
        },
        "funding": {"strategy_warmup_usage": "NOT_USED_FOR_HL_SANDBOX_CASH", "hl_funding_cash": "UNPOSTED_ADAPTER_HAS_NEXT_PAYMENT_ONLY_NO_SETTLEMENT_ORACLE"},
        "symbols": symbols,
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest_path


def load_stageg_bybit_warmup(manifest_path: Path, *, now_ms: int | None = None) -> tuple[dict[str, tuple[dict, ...]], str]:
    """Verify the prepared artifact and return Bybit rows without relabelling."""
    try:
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("schema") not in {"coinmaster-stageg-bybit-signal-warmup-v1", "coinmaster-stageg-bybit-signal-warmup-v2"} or manifest.get("venue") != "bybit" or manifest.get("category") != "linear":
            return {}, "INVALID_STAGEG_WARMUP_SCHEMA_OR_VENUE"
        if manifest["schema"].endswith("v1"):
            for source_name, source in manifest["provenance"].items():
                if source["manifest_sha256"] != EXPECTED_SOURCE_MANIFEST_SHA256[source_name]:
                    return {}, f"UNEXPECTED_STAGEG_SOURCE_MANIFEST_{source_name.upper()}"
                if source["raw_manifest_sha256"] != EXPECTED_RAW_MANIFEST_SHA256[source_name]:
                    return {}, f"UNEXPECTED_STAGEG_RAW_MANIFEST_{source_name.upper()}"
                source_manifest = manifest_path.parent / source["manifest_path"]
                if _sha256(source_manifest) != source["manifest_sha256"]:
                    return {}, f"STAGEG_SOURCE_MANIFEST_HASH_MISMATCH_{source_name.upper()}"
                raw_hashes = []
                for raw in source["raw_files"]:
                    raw_path = manifest_path.parent / raw["path"]
                    if _sha256(raw_path) != raw["sha256"] or _canonical_raw_hash(raw_path) != raw["sha256"]:
                        return {}, f"STAGEG_RAW_PAGE_HASH_MISMATCH_{source_name.upper()}"
                    raw_hashes.append(raw["sha256"])
                if hashlib.sha256("".join(sorted(raw_hashes)).encode()).hexdigest() != source["raw_manifest_sha256"]:
                    return {}, f"STAGEG_RAW_MANIFEST_MISMATCH_{source_name.upper()}"
        else:
            provenance = manifest["provenance"]
            predecessor_path = manifest_path.parent / provenance["predecessor_manifest_path"]
            predecessor = json.loads(predecessor_path.read_text())
            if _sha256(predecessor_path) != provenance["predecessor_manifest_sha256"]:
                return {}, "STAGEG_PREDECESSOR_MANIFEST_HASH_MISMATCH"
            _, predecessor_state = load_stageg_bybit_warmup(predecessor_path, now_ms=int(predecessor["warmup_end_exclusive_ms"]))
            if predecessor_state != "READY":
                return {}, f"STAGEG_PREDECESSOR_INVALID:{predecessor_state}"
            append_manifest_path = manifest_path.parent / provenance["append_manifest_path"]
            append_manifest = json.loads(append_manifest_path.read_text())
            if _sha256(append_manifest_path) != provenance["append_manifest_sha256"]:
                return {}, "STAGEG_APPEND_MANIFEST_HASH_MISMATCH"
            raw_hashes = []
            for raw in provenance["append_raw_files"]:
                raw_path = manifest_path.parent / raw["path"]
                if _sha256(raw_path) != raw["sha256"] or _canonical_raw_hash(raw_path) != raw["sha256"]:
                    return {}, "STAGEG_APPEND_RAW_PAGE_HASH_MISMATCH"
                raw_hashes.append(raw["sha256"])
            if hashlib.sha256("".join(sorted(raw_hashes)).encode()).hexdigest() != provenance["append_raw_manifest_sha256"]:
                return {}, "STAGEG_APPEND_RAW_MANIFEST_MISMATCH"
            _validate_coverage(append_manifest, require_daily_complete=True)
        symbols: dict[str, tuple[dict, ...]] = {}
        for symbol in SYMBOLS:
            item = manifest["symbols"][symbol]
            daily = manifest_path.parent / item["daily_path"]
            if _sha256(daily) != item["daily_sha256"]:
                return {}, f"STAGEG_DAILY_HASH_MISMATCH_{symbol}"
            rows = pq.read_table(daily).to_pylist()
            _validate_daily_rows(rows, symbol=symbol)
            if manifest["schema"].endswith("v2"):
                appended = _rebuild_daily_from_raw(append_manifest, append_manifest_path.parent, symbol)
                if not appended or not _daily_rows_equal(rows[-len(appended):], appended):
                    return {}, f"STAGEG_APPEND_DAILY_NOT_REPRODUCIBLE_FROM_RAW_{symbol}"
            if len(rows) != item["daily_rows"] or len(rows) < 730 or not item["mark_close_complete"]:
                return {}, f"STAGEG_DAILY_COVERAGE_INVALID_{symbol}"
            if int(rows[-1]["open_time_ms"]) + DAY_MS != int(manifest["warmup_end_exclusive_ms"]):
                return {}, f"STAGEG_LATEST_SESSION_MISMATCH_{symbol}"
            symbols[symbol] = tuple(rows)
        if symbols["BTCUSDT"][0]["open_time_ms"] != symbols["SOLUSDT"][0]["open_time_ms"] or symbols["BTCUSDT"][-1]["open_time_ms"] != symbols["SOLUSDT"][-1]["open_time_ms"]:
            return {}, "STAGEG_SYMBOL_RANGE_MISMATCH"
        now_ms = int(datetime.now(UTC).timestamp() * 1000) if now_ms is None else now_ms
        latest_close_ms = int(manifest["warmup_end_exclusive_ms"])
        if latest_close_ms != now_ms // DAY_MS * DAY_MS:
            return {}, "WARMUP_LATEST_COMPLETED_SESSION_MISSING"
        if latest_close_ms - int(manifest["warmup_start_ms"]) < WARMUP_MS:
            return {}, "WARMUP_SHORTER_THAN_24_MONTHS"
        return symbols, "READY"
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return {}, "MISSING_OR_INVALID_STAGEG_WARMUP"
