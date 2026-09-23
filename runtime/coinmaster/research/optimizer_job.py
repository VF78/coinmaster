"""One bounded Stage-G axis on the existing native Nautilus diagnostic engine."""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Callable

from coinmaster.ops.stage_g_config import candidate_content_hash, load_candidate
from coinmaster.research.job_protocol import report_summary, sha256_file, wait_for_launch_permit
from coinmaster.research.native_baseline import MINUTE_MS, TRADING_END_MS, TRADING_START_MS, _candidate_from_job_config, run_native_diagnostic, save_diagnostic_report

SEARCH_SPACE = "stageg-btc-notional-one-axis-v1"
AXIS = ("7.375", "7.625", "7.875", "8.125", "8.375")
STAGE_G = Path(__file__).resolve().parents[2] / "configs" / "stage-g-v1.json"


def search_spec() -> dict:
    return {"search_space": SEARCH_SPACE, "axis": "btc_notional_multiplier", "values": list(AXIS), "max_variants": len(AXIS), "objective": "terminal ACTIVE+RESERVE TOTAL", "source_candidate_sha256": load_candidate(STAGE_G).sha256}


def config_blockers(config: dict) -> list[str]:
    try:
        candidate = _candidate_from_job_config(config)
        return [] if candidate_content_hash(candidate) == load_candidate(STAGE_G).sha256 else ["CONFIG_NOT_SEALED_STAGE_G"]
    except (KeyError, TypeError, ValueError) as error:
        return [str(error)]


@lru_cache(maxsize=8)
def _verify_files(root: str, manifest_stat: tuple, file_stats: tuple, expected_hashes: tuple) -> tuple[str, ...]:
    blockers = []
    for (name, path, *_), digest in zip(file_stats, expected_hashes):
        hasher = hashlib.sha256()
        with Path(path).open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                hasher.update(chunk)
        if hasher.hexdigest() != digest:
            blockers.append(f"{name}:SHA256_MISMATCH")
    return tuple(blockers)


def source_blockers(root: Path) -> tuple[list[str], str | None]:
    """Verify exact four complete streams; cache only while all file stats agree."""
    root = root.resolve()
    manifest = root / "bybit-1m" / "manifest.json"
    if not manifest.is_file():
        return ["MISSING_1M_MANIFEST"], None
    try:
        raw = manifest.read_bytes()
        data = json.loads(raw)
        digest = hashlib.sha256(raw).hexdigest()
        if data.get("start") != "2024-09-01T00:00:00+00:00" or data.get("end_exclusive") != "2026-09-01T00:00:00+00:00":
            return ["SOURCE_INTERVAL_MISMATCH"], digest
        found = {(item.get("symbol"), stream.get("stream")): stream for item in data.get("symbols", []) for stream in item.get("streams", [])}
        expected = {(symbol, stream) for symbol in ("BTCUSDT", "SOLUSDT") for stream in ("execution", "mark")}
        if set(found) != expected:
            return ["SOURCE_STREAM_SET_MISMATCH"], digest
        blockers, stats, hashes = [], [], []
        for symbol, stream in sorted(expected):
            name = f"{symbol}:{stream}"
            item = found[symbol, stream]
            expected_minutes = (TRADING_END_MS - TRADING_START_MS) // MINUTE_MS
            if item.get("missing_count") != 0 or item.get("received") != expected_minutes or item.get("expected") != expected_minutes or item.get("status") == "PARTIAL_RESUMABLE":
                blockers.append(f"{name}:INCOMPLETE")
            source = root / "normalized" / f"bybit-{symbol}-{stream}-1m.parquet"
            stated = Path(str(item.get("parquet", "")))
            if stated.name != source.name or not isinstance(item.get("parquet_sha256"), str) or len(item["parquet_sha256"]) != 64:
                blockers.append(f"{name}:INVALID_MANIFEST_ENTRY")
                continue
            try:
                stat = source.stat()
            except OSError:
                blockers.append(f"{name}:MISSING_PARQUET")
                continue
            stats.append((name, str(source), stat.st_ino, stat.st_size, stat.st_mtime_ns))
            hashes.append(item["parquet_sha256"])
        if blockers:
            return blockers, digest
        # File metadata participates in the cache key without being read into the report.
        return list(_verify_files(str(root), (manifest.stat().st_mtime_ns, manifest.stat().st_size), tuple(stats), tuple(hashes))), digest
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return ["INVALID_1M_MANIFEST"], None


def compact_candidate(candidate_id: str, candidate, report: dict, artifact: Path) -> dict:
    active, reserve, total = (Decimal(str(report[key])) for key in ("terminal_active", "terminal_reserve", "terminal_total"))
    if not all(item.is_finite() for item in (active, reserve, total)) or active + reserve != total:
        raise ValueError("TERMINAL_TOTAL_RECONCILIATION_FAILED")
    if report.get("status") not in {"NOT_FAITHFUL_DIAGNOSTIC", "LIQUIDATED_EARLY_CUTOFF"}:
        raise ValueError("UNEXPECTED_NATIVE_CLASSIFICATION")
    return {"candidate_id": candidate_id, "candidate_sha256": candidate_content_hash(candidate), "btc_notional_multiplier": str(candidate.btc_notional_multiplier), "classification": report["status"], "ranking_eligible": False, "terminal_active": str(active), "terminal_reserve": str(reserve), "terminal_total": str(total), "roi": report.get("summary", {}).get("roi"), "drawdown_percent": report.get("summary", {}).get("max_drawdown_percent"), "liquidations": report.get("liquidation_count"), "maker_fees": report.get("fee_attribution", {}).get("maker", {}).get("fees"), "taker_fees": report.get("fee_attribution", {}).get("taker", {}).get("fees"), "funding": report.get("funding"), "fills": report.get("fills"), "limitations": report.get("limitations", []), "artifact": str(artifact), "artifact_sha256": sha256_file(artifact)}


def verify_compact_result(report: dict, work: Path, request: dict) -> bool:
    """Rebuild every compact row from private native evidence before completion."""
    try:
        rows = report["top20"]
        if (report["search"] != search_spec() or report["source_manifest_sha256"] != request["source_manifest_sha256"]
                or not isinstance(rows, list) or len(rows) != len(AXIS) or report["completed_variants"] != len(AXIS)):
            return False
        base = load_candidate(STAGE_G).candidate
        rebuilt = []
        for value in AXIS:
            candidate_id = f"btc-{value}"
            artifact = work / "artifacts" / candidate_id / "native-result.json"
            if not artifact.is_file():
                return False
            native = json.loads(artifact.read_text())
            candidate = replace(base, btc_notional_multiplier=float(value))
            rebuilt.append(compact_candidate(candidate_id, candidate, native, artifact))
        rebuilt.sort(key=lambda row: (-Decimal(row["terminal_total"]), row["candidate_id"]))
        return rows == rebuilt and report["terminal_total"] == rebuilt[0]["terminal_total"] and report["ranking_eligible"] is False
    except (KeyError, OSError, TypeError, ValueError, ArithmeticError, json.JSONDecodeError):
        return False


def run_search(request: dict, evaluator: Callable = run_native_diagnostic, verify_source: Callable = source_blockers, emit: Callable = print) -> dict:
    spec = search_spec()
    if request.get("search") != spec or config_blockers(request["config"]):
        raise ValueError("OPTIMIZER_SEARCH_OR_CONFIG_MISMATCH")
    blockers, source_hash = verify_source(Path(request["data_root"]))
    if blockers:
        raise ValueError("SOURCE_BLOCKED:" + ",".join(blockers))
    if source_hash != request.get("source_manifest_sha256"):
        raise ValueError("SOURCE_MANIFEST_CHANGED")
    root, artifacts = Path(request["data_root"]), Path(request["artifact_dir"])
    artifacts.mkdir(parents=True, exist_ok=True)
    base = load_candidate(STAGE_G).candidate
    rows = []
    for index, value in enumerate(AXIS, 1):
        candidate = replace(base, btc_notional_multiplier=float(value))
        candidate_id = f"btc-{value}"
        report = evaluator(root, include_funding=True, candidate=candidate, artifact_dir=artifacts / candidate_id, artifact_label="native-result", stop_on_liquidation=False)
        artifact = save_diagnostic_report(root, report, "native-result", artifacts / candidate_id)
        rows.append(compact_candidate(candidate_id, candidate, report, artifact))
        emit(json.dumps({"type": "progress", "request_hash": request["request_hash"], "config_hash": request["config_hash"], "progress": min(99, index * 99 // len(AXIS)), "completed_variants": index, "budget": len(AXIS)}, sort_keys=True), flush=True)
    rows.sort(key=lambda row: (-Decimal(row["terminal_total"]), row["candidate_id"]))
    return {"status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible": False, "objective": spec["objective"], "search": spec, "source_manifest_sha256": source_hash, "completed_variants": len(rows), "top20": rows[:20], "terminal_total": rows[0]["terminal_total"], "limitations": ["Native 1m diagnostic only; ranking is not faithful execution evidence", "No promotion or order routing"]}


def run_job_request(path: Path) -> int:
    try:
        request = json.loads(path.read_text())
        keys = ("config_hash", "config", "data_root", "artifact_dir", "launch_permit", "launch_owner_token", "search", "source_manifest_sha256")
        canonical = json.dumps({key: request[key] for key in keys}, sort_keys=True, separators=(",", ":"))
        if hashlib.sha256(canonical.encode()).hexdigest() != request["request_hash"]:
            return 1
        if hashlib.sha256(json.dumps(request["config"], sort_keys=True, separators=(",", ":")).encode()).hexdigest() != request["config_hash"]:
            return 1
        if not wait_for_launch_permit(request):
            return 1
        report = run_search(request)
        artifact = save_diagnostic_report(Path(request["data_root"]), report, "result", Path(request["artifact_dir"]))
        envelope = {"type": "result", "status": "COMPLETED", "request_hash": request["request_hash"], "config_hash": request["config_hash"], "artifact": str(artifact), "artifact_sha256": sha256_file(artifact), "summary": report_summary(report)}
        (artifact.parent / "result-envelope.json").write_text(json.dumps(envelope, sort_keys=True) + "\n")
        print(json.dumps(envelope, sort_keys=True), flush=True)
        return 0
    except Exception as error:
        print(json.dumps({"type": "result", "status": "BLOCKED" if isinstance(error, ValueError) else "FAILED", "request_hash": request.get("request_hash") if "request" in locals() else None, "config_hash": request.get("config_hash") if "request" in locals() else None, "blockers": [str(error)] if isinstance(error, ValueError) else [type(error).__name__]}, sort_keys=True), flush=True)
        return 2 if isinstance(error, ValueError) else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-request", type=Path, required=True)
    raise SystemExit(run_job_request(parser.parse_args().job_request))


if __name__ == "__main__":
    main()
