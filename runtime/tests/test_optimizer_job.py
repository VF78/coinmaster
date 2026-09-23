"""Tiny injected evidence only; never launch a full economic optimizer."""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from coinmaster.api.app import BASELINE_CONFIG, ControlStore, StrategyConfig, research_capabilities
from coinmaster.api.research_jobs import ResearchJobManager
from coinmaster.research.optimizer_job import AXIS, STAGE_G, config_blockers, load_candidate, run_search, search_spec, source_blockers, verify_compact_result
from coinmaster.research.native_baseline import MINUTE_MS, TRADING_END_MS, TRADING_START_MS


def sealed_config() -> StrategyConfig:
    candidate = asdict(load_candidate(STAGE_G).candidate)
    value = {**BASELINE_CONFIG, **{key: item for key, item in candidate.items() if key in BASELINE_CONFIG}}
    value["sol_size_multipliers_H"] = candidate["sol_size_multipliers_h"]
    value["max_parent_notional"] = str(candidate["max_parent_notional"])
    value["venue"] = "bybit"
    return StrategyConfig.model_validate(value)


def manifest_fixture(root: Path) -> None:
    entries = []
    for symbol in ("BTCUSDT", "SOLUSDT"):
        streams = []
        for stream in ("execution", "mark"):
            target = root / "normalized" / f"bybit-{symbol}-{stream}-1m.parquet"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(f"fixture:{symbol}:{stream}".encode())
            expected = (TRADING_END_MS - TRADING_START_MS) // MINUTE_MS
            streams.append({"stream": stream, "received": expected, "expected": expected, "missing_count": 0, "parquet": str(target), "parquet_sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
        entries.append({"symbol": symbol, "streams": streams})
    manifest = root / "bybit-1m" / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"start": "2024-09-01T00:00:00+00:00", "end_exclusive": "2026-09-01T00:00:00+00:00", "symbols": entries}))


def test_optimizer_preflight_requires_sealed_config_and_verified_four_streams(tmp_path: Path) -> None:
    root = tmp_path / "data"
    manifest_fixture(root)
    assert source_blockers(root)[0] == []
    assert config_blockers(sealed_config().model_dump()) == []
    store = ControlStore(str(tmp_path / "control.sqlite"))
    sealed = store.save_config(sealed_config())
    assert research_capabilities(root, sealed).optimizer_state == "READY"
    assert research_capabilities(root, sealed, lease_busy=True).optimizer_blocker == "NATIVE_RESEARCH_WORKER_BUSY"
    assert research_capabilities(root).optimizer_state == "BLOCKED"
    assert config_blockers(StrategyConfig.model_validate(BASELINE_CONFIG).model_dump()) == ["CONFIG_NOT_SEALED_STAGE_G"]
    source = root / "normalized" / "bybit-BTCUSDT-execution-1m.parquet"
    source.write_bytes(b"tampered")
    assert source_blockers(root)[0] == ["BTCUSDT:execution:SHA256_MISMATCH"]


def test_optimizer_injected_native_rows_rank_total_and_verify_evidence(tmp_path: Path) -> None:
    config = sealed_config().model_dump()
    work = tmp_path / "job"
    request = {"config": config, "data_root": str(tmp_path), "artifact_dir": str(work / "artifacts"), "request_hash": "request", "config_hash": "config", "source_manifest_sha256": "source", "search": search_spec()}
    emitted = []
    def evaluator(root, *, candidate, **kwargs):
        active = str(candidate.btc_notional_multiplier * 100)
        return {"status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible": False, "terminal_active": active, "terminal_reserve": "5", "terminal_total": str(candidate.btc_notional_multiplier * 100 + 5), "summary": {"roi": "0.1", "max_drawdown_percent": "0.2"}, "liquidation_count": 0, "fee_attribution": {"maker": {"fees": "1"}, "taker": {"fees": "2"}}, "funding": {"count": 1, "signed_amount": "UNKNOWN"}, "fills": 2, "limitations": ["diagnostic"]}
    report = run_search(request, evaluator=evaluator, verify_source=lambda _: ([], "source"), emit=lambda value, **_: emitted.append(json.loads(value)))
    assert len(report["top20"]) == len(AXIS) == 5
    assert report["top20"][0]["candidate_id"] == "btc-8.375"
    assert report["top20"][0]["terminal_total"] == "842.5"
    assert report["ranking_eligible"] is False and len(emitted) == 5 and emitted[-1]["progress"] == 99
    assert verify_compact_result(report, work, request)
    first = Path(report["top20"][0]["artifact"])
    first.write_text(first.read_text() + " ")
    assert not verify_compact_result(report, work, request)


def test_optimizer_shares_baseline_lease_and_idempotent_cancel(tmp_path: Path) -> None:
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(sealed_config())
    commands = {name: [sys.executable, "-m", "coinmaster.research.job_test_helper", "--mode", "sleep"] for name in ("native_baseline", "native_optimizer")}
    manager = ResearchJobManager(store, tmp_path / "data", commands, test_options={})
    search = search_spec()
    run = manager.start(config, "native_optimizer", "optimizer-key", search)
    assert manager.start(config, "native_optimizer", "optimizer-key", search).id == run.id
    with pytest.raises(ValueError, match="CANONICAL_RESEARCH_ALREADY_ACTIVE"):
        manager.start(config, "native_baseline")
    with pytest.raises(ValueError, match="OPTIMIZER_SEARCH_MISMATCH"):
        manager.start(config, "native_optimizer", optimizer_search={"max_variants": 100})
    assert manager.cancel(run.id).status in {"CANCELED", "CANCEL_REQUESTED"}
    assert not store.has_research_lease(run.id)
