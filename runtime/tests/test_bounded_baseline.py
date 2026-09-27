"""Bounded native baseline request is signed, source-checked, and fail-closed."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from coinmaster.api.app import BASELINE_CONFIG, ControlStore, StrategyConfig
from coinmaster.api.research_jobs import MAX_JOB_ADDRESS_SPACE_BYTES, MAX_JOB_WALL_SECONDS, ResearchJobManager
from coinmaster.research.native_baseline import DAY_MS, TRADING_START_MS, WARMUP_START_MS, run_job_request, validate_bounded_interval
from coinmaster.research.optimizer_job import source_blockers
from test_optimizer_job import manifest_fixture, sealed_config

WEEK = {"start": "2024-09-01", "end_exclusive": "2024-09-08"}


def test_bounded_interval_uses_daily_warmup_and_limits_minute_window() -> None:
    start, end = validate_bounded_interval(WEEK)
    assert start == TRADING_START_MS and end - start == 7 * DAY_MS
    assert start - WARMUP_START_MS == 730 * DAY_MS
    for invalid in (
        {},
        {"start": "2024-09-01", "end_exclusive": "2024-09-09"},
        {"start": "2024-08-31", "end_exclusive": "2024-09-01"},
        {"start": "2026-08-31", "end_exclusive": "2026-09-02"},
        {"start": "2024-09-08", "end_exclusive": "2024-09-08"},
        {"start": "2024-09-01T00:00:00Z", "end_exclusive": "2024-09-08"},
        {"start": "2024-09-01", "end_exclusive": "2024-09-08", "extra": "ignored"},
    ):
        with pytest.raises(ValueError, match="INVALID_BOUNDED_INTERVAL"):
            validate_bounded_interval(invalid)


def test_bounded_run_requires_distinct_sealed_config_and_verified_source(tmp_path: Path) -> None:
    store = ControlStore(str(tmp_path / "control.sqlite"))
    original = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    sealed = store.save_config(sealed_config())
    assert original.id != sealed.id and original.config_hash != sealed.config_hash
    manager = ResearchJobManager(store, tmp_path / "data")
    blocked = manager.start(sealed, "native_baseline", bounded_interval=WEEK)
    assert blocked.status == "BLOCKED" and blocked.pid is None and blocked.evidence == ["MISSING_1M_MANIFEST"]
    manifest_fixture(tmp_path / "data")
    blocked = manager.start(original, "native_baseline", bounded_interval=WEEK)
    assert blocked.status == "BLOCKED" and blocked.pid is None and blocked.evidence == ["CONFIG_NOT_SEALED_STAGE_G"]
    with pytest.raises(ValueError, match="BOUNDED_INTERVAL_COMMAND_MISMATCH"):
        manager.start(sealed, "native_optimizer", bounded_interval=WEEK)
    assert MAX_JOB_ADDRESS_SPACE_BYTES == 1536 * 1024 * 1024
    assert MAX_JOB_WALL_SECONDS == 6 * 60 * 60
    env = manager.isolated_child_environment({"OPENBLAS_NUM_THREADS": "8", "HYPERLIQUID_PRIVATE_KEY": "fixture-secret"})
    assert env["OPENBLAS_NUM_THREADS"] == env["OMP_NUM_THREADS"] == env["MKL_NUM_THREADS"] == env["NUMEXPR_NUM_THREADS"] == "1"
    assert env["ARROW_NUM_THREADS"] == "2" and "HYPERLIQUID_PRIVATE_KEY" not in env


def test_bounded_request_hash_source_and_one_worker_lease(tmp_path: Path) -> None:
    data = tmp_path / "data"
    manifest_fixture(data)
    source_errors, source_hash = source_blockers(data)
    assert source_errors == [] and source_hash
    store = ControlStore(str(tmp_path / "control.sqlite"))
    sealed = store.save_config(sealed_config())
    commands = {"native_baseline": [sys.executable, "-m", "coinmaster.research.job_test_helper", "--mode", "sleep"]}
    manager = ResearchJobManager(store, data, commands)
    run = manager.start(sealed, "native_baseline", "bounded-key", bounded_interval=WEEK)
    try:
        assert run.status == "RUNNING" and run.pid and store.has_research_lease(run.id)
        request = json.loads((Path(run.work_dir) / "request.json").read_text())
        assert request["bounded_interval"] == WEEK and request["source_manifest_sha256"] == source_hash
        assert request["request_hash"] == manager._request_hash({k: v for k, v in request.items() if k != "request_hash"})
        assert manager.start(sealed, "native_baseline", "bounded-key", bounded_interval=WEEK).id == run.id
        with pytest.raises(ValueError, match="IDEMPOTENCY_KEY_REUSED"):
            manager.start(sealed, "native_baseline", "bounded-key", bounded_interval={"start": "2024-09-02", "end_exclusive": "2024-09-08"})
        with pytest.raises(ValueError, match="CANONICAL_RESEARCH_ALREADY_ACTIVE"):
            manager.start(sealed, "native_baseline", bounded_interval=WEEK)
    finally:
        manager.cancel(run.id)


@pytest.mark.parametrize(("interval", "source_hash", "expected"), [
    (WEEK, "wrong", "SOURCE_MANIFEST_CHANGED"),
    ({"start": "2024-09-01", "end_exclusive": "2024-09-09"}, "actual", "INVALID_BOUNDED_INTERVAL"),
])
def test_child_rejects_changed_source_or_invalid_signed_interval(tmp_path: Path, monkeypatch, capsys, interval, source_hash, expected) -> None:
    from coinmaster.research import native_baseline
    data = tmp_path / "data"
    manifest_fixture(data)
    actual = source_blockers(data)[1]
    request = {"config": sealed_config().model_dump(), "data_root": str(data), "artifact_dir": str(tmp_path / "artifacts"), "launch_permit": str(tmp_path / "permit.json"), "launch_owner_token": "fixture-owner", "bounded_interval": interval, "source_manifest_sha256": actual if source_hash == "actual" else source_hash}
    request["config_hash"] = hashlib.sha256(json.dumps(request["config"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    request["request_hash"] = hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request))
    monkeypatch.setattr(native_baseline, "wait_for_launch_permit", lambda _: True)
    assert run_job_request(path) == 2
    result = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert result["status"] == "BLOCKED" and expected in result["blockers"]
