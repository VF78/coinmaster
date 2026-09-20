import sys
import time
import sqlite3
import json
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
