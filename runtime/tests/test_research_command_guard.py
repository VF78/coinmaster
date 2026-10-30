"""Disabled research admission leaves archived viewing and recovery available."""
import sys

import pytest
from fastapi import HTTPException

from coinmaster.api import app as control_api
from coinmaster.api.app import BASELINE_CONFIG, ControlStore, RunInput, RunRecord, StrategyConfig, create_app, utcnow
from coinmaster.api.research_jobs import ResearchJobManager
from coinmaster.api.runtime_sidecar import create_runtime_app


def endpoint(app, path, method="GET"):
    for route in app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
        if hasattr(route, "original_router"):
            try:
                return endpoint(route.original_router, path, method)
            except LookupError:
                pass
    raise LookupError((path, method))


def test_none_retains_default_commands_and_explicit_commands_are_preserved(tmp_path):
    store = ControlStore(str(tmp_path / "control.sqlite"))
    default = ResearchJobManager(store, tmp_path / "data")
    assert default.commands == {
        "native_baseline": [sys.executable, "-m", "coinmaster.research.native_baseline"],
        "native_optimizer": [sys.executable, "-m", "coinmaster.research.optimizer_job"],
    }
    commands = {"custom": ["explicit-command"]}
    assert ResearchJobManager(store, tmp_path / "data", commands).commands == commands


@pytest.mark.parametrize("command", [None, "native_baseline", "native_optimizer"])
def test_empty_allowlist_blocks_before_side_effects(tmp_path, monkeypatch, command):
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    data_root = tmp_path / "data"
    manager = ResearchJobManager(store, data_root, {})
    def forbidden(*args, **kwargs):
        pytest.fail("disabled job reached launch admission or subprocess")
    monkeypatch.setattr(manager, "_work_dir", forbidden)
    monkeypatch.setattr(manager, "_assert_one_shared_worker", forbidden)
    monkeypatch.setattr("coinmaster.api.research_jobs.subprocess.Popen", forbidden)
    with pytest.raises(ValueError, match="^RESEARCH_COMMAND_NOT_ALLOWED$"):
        manager.start(config, command)
    assert store.runs() == []
    assert store.db.execute("SELECT count(*) FROM research_leases").fetchone()[0] == 0
    assert not data_root.exists()


@pytest.mark.parametrize("allowed", [{}, {"native_baseline": ["baseline"]}, {"native_optimizer": ["optimizer"]}])
def test_capabilities_use_same_allowlist_even_when_data_and_config_are_ready(tmp_path, monkeypatch, allowed):
    monkeypatch.setattr(control_api, "coverage_blockers", lambda _: [])
    monkeypatch.setattr(control_api, "source_blockers", lambda _: ([], "source-hash"))
    monkeypatch.setattr(control_api, "config_blockers", lambda _: [])
    app = create_app(str(tmp_path / "control.sqlite"), "operator", research_commands=allowed)
    config = endpoint(app, "/api/v1/configurations", "POST")(control_api.ConfigurationInput(config=BASELINE_CONFIG))
    capabilities = endpoint(app, "/api/v1/research/capabilities")(config.id)
    for command, state, blockers in (
        ("native_baseline", capabilities.baseline_state, capabilities.baseline_blockers),
        ("native_optimizer", capabilities.optimizer_state, capabilities.optimizer_blockers),
    ):
        assert state == ("READY" if command in allowed else "BLOCKED")
        assert blockers == ([] if command in allowed else ["RESEARCH_COMMAND_NOT_ALLOWED"])
    assert capabilities.optimizer_blocker == (None if "native_optimizer" in allowed else "RESEARCH_COMMAND_NOT_ALLOWED")


def test_runtime_binding_blocks_new_jobs_and_keeps_archived_backtest_readable(tmp_path):
    database = str(tmp_path / "control.sqlite")
    app = create_runtime_app(database=str(tmp_path / "missing.sqlite"), control_database=database, token="operator", worker_url="http://127.0.0.1:9")
    store = ControlStore(database)
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    create_run = endpoint(app, "/api/v1/runs", "POST")
    for command in ("native_baseline", "native_optimizer"):
        with pytest.raises(HTTPException) as error:
            create_run(RunInput(config_id=config.id, kind="research", research_command=command), None)
        assert error.value.status_code == 422
        assert error.value.detail == "RESEARCH_COMMAND_NOT_ALLOWED"
    capabilities = endpoint(app, "/api/v1/research/capabilities")(config.id)
    assert capabilities.baseline_state == capabilities.optimizer_state == "BLOCKED"
    assert capabilities.baseline_blockers[0] == capabilities.optimizer_blocker == "RESEARCH_COMMAND_NOT_ALLOWED"
    archived = create_run(RunInput(config_id=config.id, kind="backtest"), None)
    assert archived.status == "COMPLETED_ARTIFACT_REFERENCE"
    assert endpoint(app, "/api/v1/runs/{run_id}")(archived.id) == archived
    assert endpoint(app, "/api/v1/runs")() == [archived]
    assert endpoint(app, "/api/v1/runs/{run_id}/report")(archived.id) == archived.model_dump()
    assert store.db.execute("SELECT count(*) FROM research_leases").fetchone()[0] == 0


def test_empty_allowlist_keeps_restart_reconciliation(tmp_path):
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    store.save_run(RunRecord(id="orphan", config_id=config.id, kind="research", status="RUNNING", evidence=[], created_at=utcnow(), command_name="native_baseline", pid=2147483647, process_group=2147483647))
    ResearchJobManager(store, tmp_path / "data", {})
    recovered = store.get_run("orphan")
    assert recovered.status == "INTERRUPTED"
    assert "CONTROL_RESTART_ORPHANED_PROCESS" in recovered.evidence
