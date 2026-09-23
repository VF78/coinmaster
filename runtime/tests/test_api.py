import sys
import time
import sqlite3
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from coinmaster.api.app import BASELINE_CONFIG, ControlStore, PreflightInput, RunInput, RunRecord, StrategyConfig, _catalog_entry, immutable_research_reference, create_app, fixture_report, utcnow
from coinmaster.api.research_jobs import ResearchJobManager
from coinmaster.research.catalog import RESEARCH_CATALOG
import pytest


def test_api_openapi_and_immutable_configuration(tmp_path) -> None:
    app = create_app(str(tmp_path / "control.sqlite"), "test-token")
    assert "/api/v1/runs" in app.openapi()["paths"]
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    assert store.get_config(config.id).config_hash == config.config_hash


def test_fixture_report_is_native_synthetic_evidence_only() -> None:
    report = fixture_report()
    assert report == {
        "terminal_total_usdt": "15632.05000000",
        "fills": 5,
        "label": "SYNTHETIC_P1_FIXTURE",
        "ranking_eligible": False,
    }


def test_preflight_requires_explicit_valid_beta_and_three_sol_levels() -> None:
    missing = PreflightInput(venue="bybit", btc_notional="90000", sol_multipliers=[1, 1.5, 2])
    assert missing.beta is None
    supplied = PreflightInput(venue="bybit", btc_notional="90000", beta="1.5", selected_leverage="20", sol_multipliers=[1, 1.5, 2])
    assert supplied.beta == "1.5" and len(supplied.sol_multipliers) == 3
    with pytest.raises(ValueError):
        PreflightInput(venue="bybit", btc_notional="90000", beta="0", sol_multipliers=[1, 1.5, 2])


@pytest.mark.parametrize(("field", "value"), [
    ("initial_total_usdt", "9000"),
    ("initial_active_fraction", 0.9),
    ("include_zero_waves", False),
    ("freeze_sigma_on_first_sol_fill", False),
    ("sol_z_stop", 1.0),
    ("btc_close_stop_fraction", 0.02),
    ("portfolio_loss_limit_fraction", 0.1),
    ("future_sol_margin_fraction", 0.1),
    ("insufficient_margin", "clip"),
    ("reserve_transfer_fraction", 0.1),
    ("reserve_trigger_multiple", 5.0),
])
def test_unimplemented_paper_controls_reject_non_v0_values(field, value) -> None:
    candidate = {**BASELINE_CONFIG, field: value}
    with pytest.raises(ValueError, match=f"UNSUPPORTED_PAPER_CONFIG:{field}"):
        StrategyConfig.model_validate(candidate)


def test_unimplemented_paper_controls_keep_exact_inactive_v0_values() -> None:
    config = StrategyConfig.model_validate(BASELINE_CONFIG)
    assert config.insufficient_margin == "reject"
    assert config.reserve_transfer_fraction == 0
    assert config.future_sol_margin_fraction == 0


def _wait_for_terminal(manager: ResearchJobManager, run_id: str):
    for _ in range(100):
        run = manager.refresh(run_id)
        if run.status not in {"RUNNING", "CANCEL_REQUESTED"}:
            return run
        time.sleep(0.02)
    raise AssertionError("research helper did not finish")


def _helper(mode: str) -> dict[str, list[str]]:
    return {mode: [sys.executable, "-m", "coinmaster.research.job_test_helper", "--mode", mode]}


def test_research_job_lifecycle_isolated_progressing_and_persists_result(tmp_path) -> None:
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    manager = ResearchJobManager(store, tmp_path / "data", _helper("complete"))
    run = manager.start(config, "complete")
    assert run.status == "RUNNING" and run.pid and run.process_group and run.request_hash
    for _ in range(100):
        observed = manager.refresh(run.id)
        if observed.status == "RUNNING" and (observed.progress or 0) >= 10:
            break
        time.sleep(0.01)
    else:
        raise AssertionError("research helper did not publish progress")
    terminal = _wait_for_terminal(manager, run.id)
    assert terminal.status == "COMPLETED" and terminal.progress == 100
    assert terminal.report and {key: terminal.report[key] for key in ("status", "ranking_eligible", "terminal_total")} == {"status": "NOT_FAITHFUL_DIAGNOSTIC", "ranking_eligible": False, "terminal_total": "UNKNOWN_TEST_HELPER"}
    assert terminal.finished_at and terminal.heartbeat_at


def test_research_job_cancellation_only_targets_owned_process_group(tmp_path) -> None:
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    manager = ResearchJobManager(store, tmp_path / "data", _helper("sleep"))
    run = manager.start(config, "sleep")
    requested = manager.cancel(run.id)
    assert requested.status in {"CANCEL_REQUESTED", "CANCELED"} and requested.cancel_requested_at
    terminal = _wait_for_terminal(manager, run.id)
    assert terminal.status == "CANCELED"
    assert "CANCELED_OWNED_PROCESS_GROUP" in terminal.evidence


def test_production_research_missing_data_is_blocked_without_spawn(tmp_path) -> None:
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    manager = ResearchJobManager(store, tmp_path / "missing-data")
    run = manager.start(config, None)
    assert run.status == "BLOCKED" and run.pid is None
    assert run.evidence == ["MISSING_1M_MANIFEST"]


def test_unmappable_saved_config_blocks_before_native_spawn(tmp_path) -> None:
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate({**BASELINE_CONFIG, "venue": "hyperliquid"}))
    manager = ResearchJobManager(store, tmp_path / "data")
    run = manager.start(config, None)
    assert run.status == "BLOCKED" and run.pid is None
    assert run.evidence == ["UNMAPPABLE_CONFIG:venue"]


def test_control_restart_marks_running_research_orphaned(tmp_path) -> None:
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    store.save_run(RunRecord(id="orphan", config_id=config.id, kind="research", status="RUNNING", evidence=["NATIVE_RESEARCH_SUBPROCESS"], created_at=utcnow(), request_hash="hash", command_name="native_baseline", pid=123, process_group=123, started_at=utcnow(), heartbeat_at=utcnow(), progress=10))
    ResearchJobManager(store, tmp_path / "data")
    recovered = store.get_run("orphan")
    assert recovered.status == "INTERRUPTED"
    assert "CONTROL_RESTART_ORPHANED_PROCESS" in recovered.evidence


def test_control_restart_terminates_real_owned_surviving_child(tmp_path) -> None:
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    first = ResearchJobManager(store, tmp_path / "data", _helper("sleep"))
    run = first.start(config, "sleep")
    child = first.processes[run.id]
    ResearchJobManager(store, tmp_path / "data", _helper("sleep"))
    child.wait(timeout=3)
    recovered = store.get_run(run.id)
    assert recovered.status == "INTERRUPTED"
    assert "ORPHAN_OWNED_PROCESS_TERMINATED" in recovered.evidence


def test_research_launch_db_failure_reaps_child(tmp_path, monkeypatch) -> None:
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    manager = ResearchJobManager(store, tmp_path / "data", _helper("sleep"))
    original = store.update_run
    failed = False
    def fail_running(run_id, **values):
        nonlocal failed
        if values.get("status") == "RUNNING" and not failed:
            failed = True
            raise sqlite3.OperationalError("injected")
        return original(run_id, **values)
    monkeypatch.setattr(store, "update_run", fail_running)
    with pytest.raises(RuntimeError, match="RESEARCH_LAUNCH_FAILED"):
        manager.start(config, "sleep")
    assert failed
    assert all(run.status not in {"STARTING", "RUNNING", "CANCEL_REQUESTED"} for run in store.runs())


def test_research_cancel_escalates_term_ignoring_owned_child(tmp_path) -> None:
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    manager = ResearchJobManager(store, tmp_path / "data", _helper("ignore-term"))
    run = manager.start(config, "ignore-term")
    manager.cancel(run.id)
    assert _wait_for_terminal(manager, run.id).status == "CANCELED"


def test_exit_vs_cancel_race_has_one_truthful_terminal_state(tmp_path) -> None:
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    manager = ResearchJobManager(store, tmp_path / "data", _helper("complete"))
    run = manager.start(config, "complete")
    time.sleep(0.45)
    terminal = manager.cancel(run.id)
    terminal = _wait_for_terminal(manager, terminal.id)
    assert terminal.status in {"CANCELED", "COMPLETED"}


def test_wrong_typed_result_hash_never_completes(tmp_path) -> None:
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    manager = ResearchJobManager(store, tmp_path / "data", _helper("wrong-hash"))
    run = manager.start(config, "wrong-hash")
    assert _wait_for_terminal(manager, run.id).status == "FAILED"


def test_large_artifact_completes_with_compact_stdout_envelope(tmp_path) -> None:
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    manager = ResearchJobManager(store, tmp_path / "data", _helper("large-report"))
    run = manager.start(config, "large-report")
    terminal = _wait_for_terminal(manager, run.id)
    artifact = Path(terminal.work_dir) / "artifacts" / "result.json"
    envelope = json.loads((artifact.parent / "result-envelope.json").read_text())
    assert terminal.status == "COMPLETED" and artifact.stat().st_size > 707 * 1024
    assert "report" not in envelope and len(json.dumps(envelope)) < 4_096


def test_tampered_result_artifact_never_completes(tmp_path) -> None:
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    manager = ResearchJobManager(store, tmp_path / "data", _helper("tampered-artifact"))
    assert _wait_for_terminal(manager, manager.start(config, "tampered-artifact").id).status == "FAILED"


def test_observer_progress_db_failure_reaps_owned_running_child(tmp_path, monkeypatch) -> None:
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    manager = ResearchJobManager(store, tmp_path / "data", _helper("sleep"))
    original = store.update_run
    failed = False
    def fail_progress(run_id, **values):
        nonlocal failed
        if values.get("progress") == 10 and not failed:
            failed = True
            raise sqlite3.OperationalError("injected progress failure")
        return original(run_id, **values)
    monkeypatch.setattr(store, "update_run", fail_progress)
    run = manager.start(config, "sleep")
    child = manager.processes[run.id]
    terminal = _wait_for_terminal(manager, run.id)
    assert failed and terminal.status == "FAILED"
    assert child.poll() is not None


def test_child_aborts_without_permit_when_manager_dies_after_popen(tmp_path) -> None:
    database, data = tmp_path / "control.sqlite", tmp_path / "data"
    setup = ControlStore(str(database))
    config = setup.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    script = """
import os, sys
from pathlib import Path
from coinmaster.api.app import ControlStore
from coinmaster.api.research_jobs import ResearchJobManager
store = ControlStore(sys.argv[1])
config = store.get_config(sys.argv[2])
original = store.update_run
def abort_after_popen(run_id, **values):
    if values.get('status') == 'RUNNING': os._exit(97)
    return original(run_id, **values)
store.update_run = abort_after_popen
ResearchJobManager(store, Path(sys.argv[3]), {'sleep': [sys.executable, '-m', 'coinmaster.research.job_test_helper', '--mode', 'sleep']}).start(config, 'sleep')
"""
    crashed = subprocess.run([sys.executable, "-c", script, str(database), config.id, str(data)], cwd=Path(__file__).parents[1])
    assert crashed.returncode == 97
    runs = setup.runs()
    assert len(runs) == 1 and runs[0].status == "STARTING" and runs[0].pid is None
    time.sleep(2)
    assert not (Path(runs[0].work_dir) / "artifacts").exists()
    recovered_store = ControlStore(str(database))
    ResearchJobManager(recovered_store, data, _helper("sleep"))
    recovered = recovered_store.get_run(runs[0].id)
    assert recovered.status == "CANCEL_REQUESTED"
    assert "ORPHAN_IDENTITY_MISMATCH_LEASE_HELD" in recovered.evidence


def test_two_managers_atomically_admit_one_canonical_owner(tmp_path) -> None:
    database, data = str(tmp_path / "control.sqlite"), tmp_path / "data"
    first_store, second_store = ControlStore(database), ControlStore(database)
    config = first_store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    commands = {"native_baseline": [sys.executable, "-m", "coinmaster.research.job_test_helper", "--mode", "sleep"]}
    first = ResearchJobManager(first_store, data, commands, test_options={})
    second = ResearchJobManager(second_store, data, commands, test_options={})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(manager.start, config, None, "same-canonical-request") for manager in (first, second)]
        accepted = [future.result() for future in futures]
    assert len({run.id for run in accepted}) == 1
    assert sum(run.status in {"STARTING", "RUNNING", "CANCEL_REQUESTED"} for run in first_store.runs()) == 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(manager.start, config, None) for manager in (first, second)]
        rejected = [future.exception() for future in futures]
    assert all(isinstance(error, ValueError) and str(error) == "CANONICAL_RESEARCH_ALREADY_ACTIVE" for error in rejected)
    owner = next(manager for manager in (first, second) if accepted[0].id in manager.processes)
    assert owner.cancel(accepted[0].id).status in {"CANCEL_REQUESTED", "CANCELED"}
    assert _wait_for_terminal(owner, accepted[0].id).status == "CANCELED"


def test_non_owner_manager_cancels_verified_child_before_releasing_canonical_lease(tmp_path) -> None:
    database, data = str(tmp_path / "control.sqlite"), tmp_path / "data"
    owner_store, observer_store = ControlStore(database), ControlStore(database)
    config = owner_store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    commands = {"native_baseline": [sys.executable, "-m", "coinmaster.research.job_test_helper", "--mode", "sleep"]}
    owner = ResearchJobManager(owner_store, data, commands, test_options={})
    observer = ResearchJobManager(observer_store, data, commands, test_options={})
    run = owner.start(config, None)
    child = owner.processes[run.id]
    canceled = observer.cancel(run.id)
    child.wait(timeout=3)
    assert canceled.status == "CANCELED" and child.poll() is not None
    assert not observer_store.has_research_lease(run.id)
    successor = observer.start(config, None)
    assert successor.id != run.id
    assert observer.cancel(successor.id).status in {"CANCEL_REQUESTED", "CANCELED"}
    assert _wait_for_terminal(observer, successor.id).status == "CANCELED"


def test_non_owner_identity_mismatch_keeps_canonical_lease_and_refuses_successor(tmp_path) -> None:
    database, data = str(tmp_path / "control.sqlite"), tmp_path / "data"
    owner_store, observer_store = ControlStore(database), ControlStore(database)
    config = owner_store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    commands = {"native_baseline": [sys.executable, "-m", "coinmaster.research.job_test_helper", "--mode", "sleep"]}
    owner = ResearchJobManager(owner_store, data, commands, test_options={})
    observer = ResearchJobManager(observer_store, data, commands, test_options={})
    run = owner.start(config, None)
    identity = run.process_identity
    observer_store.update_run(run.id, process_identity="tampered")
    conflict = observer.cancel(run.id)
    assert conflict.status == "CANCEL_REQUESTED"
    assert "CANCEL_CONFLICT_IDENTITY_UNVERIFIABLE_LEASE_HELD" in conflict.evidence
    assert observer_store.has_research_lease(run.id)
    with pytest.raises(ValueError, match="CANONICAL_RESEARCH_ALREADY_ACTIVE"):
        observer.start(config, None)
    owner_store.update_run(run.id, process_identity=identity)
    assert owner.cancel(run.id).status in {"CANCEL_REQUESTED", "CANCELED"}
    assert _wait_for_terminal(owner, run.id).status == "CANCELED"


def test_research_idempotency_and_artifacts_are_per_job(tmp_path) -> None:
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    manager = ResearchJobManager(store, tmp_path / "data", _helper("complete"))
    first = manager.start(config, "complete", "same-request")
    assert manager.start(config, "complete", "same-request").id == first.id
    assert _wait_for_terminal(manager, first.id).status == "COMPLETED"
    second = manager.start(config, "complete", "second-request")
    assert _wait_for_terminal(manager, second.id).status == "COMPLETED"
    assert first.work_dir != second.work_dir
    assert (Path(first.work_dir) / "artifacts" / "result.json").is_file()
    assert (Path(second.work_dir) / "artifacts" / "result.json").is_file()


def test_research_api_duplicate_post_returns_same_owned_run(tmp_path) -> None:
    database = str(tmp_path / "control.sqlite")
    store = ControlStore(database)
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    app = create_app(database, "operator", research_commands=_helper("complete"), research_data_root=tmp_path / "data")
    route = next(item for item in app.routes if getattr(item, "path", None) == "/api/v1/runs" and "POST" in getattr(item, "methods", set()))
    payload = {"config_id": config.id, "kind": "research", "research_command": "complete"}
    first = route.endpoint(RunInput.model_validate(payload), "duplicate")
    second = route.endpoint(RunInput.model_validate(payload), "duplicate")
    assert first.id == second.id


def test_canonical_runner_smoke_consumes_saved_config_and_writes_unique_artifacts(tmp_path) -> None:
    from test_native_baseline import write_streaming_fixture
    start, end = write_streaming_fixture(tmp_path / "data")
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    manager = ResearchJobManager(store, tmp_path / "data", test_options={"warmup_start_ms": 0, "trading_start_ms": start, "trading_end_ms": end, "weekly_batch_minutes": 24 * 60, "cursor_batch_rows": 60, "include_funding": False})
    run = manager.start(config, None)
    terminal = _wait_for_terminal(manager, run.id)
    assert terminal.status == "COMPLETED"
    assert terminal.request_hash and terminal.report and terminal.report["request_config_hash"] == config.config_hash
    request = json.loads((Path(terminal.work_dir) / "request.json").read_text())
    assert request["config_hash"] == config.config_hash and request["config"] == config.config.model_dump()
    assert (Path(terminal.work_dir) / "artifacts" / "result-envelope.json").is_file()


def test_openapi_exposes_research_lifecycle_status_fields(tmp_path) -> None:
    spec = create_app(str(tmp_path / "control.sqlite"), "test-token").openapi()
    run_input = spec["components"]["schemas"]["RunInput"]
    assert "research" in run_input["properties"]["kind"]["enum"]
    run = spec["components"]["schemas"]["RunRecord"]
    for field in ("request_hash", "pid", "process_group", "heartbeat_at", "progress", "cancel_requested_at", "finished_at"):
        assert field in run["properties"]


def test_research_capabilities_blocks_optimizer_and_missing_baseline_data(tmp_path) -> None:
    app = create_app(str(tmp_path / "control.sqlite"), "test-token", research_data_root=tmp_path / "missing-data")
    route = next(item for item in app.routes if getattr(item, "path", None) == "/api/v1/research/capabilities")
    body = route.endpoint()
    assert body.baseline_state == "BLOCKED" and body.baseline_blockers == ["MISSING_1M_MANIFEST"]
    assert body.baseline_start == "2024-09-01" and body.baseline_end_exclusive == "2026-09-01"
    assert body.baseline_objective == "TOTAL only"
    assert body.optimizer_state == "BLOCKED"
    assert body.optimizer_blocker == "MISSING_1M_MANIFEST"
    assert "CONFIG_REQUIRED" in body.optimizer_blockers
    assert body.optimizer_search["max_variants"] == 5
    assert "/api/v1/research/capabilities" in app.openapi()["paths"]


def test_research_catalog_is_read_only_and_backtest_is_an_artifact_reference(tmp_path) -> None:
    app = create_app(str(tmp_path / "control.sqlite"), "test-token")
    assert "/api/v1/research/catalog" in app.openapi()["paths"]
    selected = _catalog_entry(next(item for item in RESEARCH_CATALOG if item["selected"]))
    assert selected["id"] == "bybit-reporting-v2-selected-7.5"
    assert selected["classification"] == "NOT_FAITHFUL_DIAGNOSTIC"
    assert selected["artifact_state"] in {"VERIFIED_LOCAL", "ARTIFACT_NOT_LOCAL"}
    evidence, report = immutable_research_reference()
    assert "NO_NEW_BACKTEST_COMPUTE" in evidence
    assert report["catalog_id"] == selected["id"]
