"""Inactive staging gates do not alter journal/process/approval state."""
import importlib.util
from pathlib import Path
import sqlite3

import pytest

from test_hl_live_epoch import settled

spec = importlib.util.spec_from_file_location("stage_live82", Path(__file__).resolve().parents[1] / "scripts/stage_live82.py")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


@pytest.mark.parametrize("active,pid", (("active", "12"), ("inactive", "12"), ("failed", "0")))
def test_inactive_pointer_refuses_running_or_uncertain_process(monkeypatch, active, pid):
    monkeypatch.setattr(stage, "out", lambda *args: active if "ActiveState" in args else pid)
    with pytest.raises(RuntimeError, match="LIVE_MUST_BE_STOPPED"):
        stage.inactive()


def test_flat_validation_uses_backup_and_preserves_original_audit(tmp_path, monkeypatch):
    runtime, _ = settled(tmp_path, "91.227")
    path = tmp_path / "live.sqlite"
    original = runtime.db.iterdump()
    before = list(original)
    runtime.close()
    monkeypatch.setattr(stage, "DB", path)
    stage.flat_check()
    with sqlite3.connect(path) as db:
        assert list(db.iterdump()) == before


def test_flat_update_refuses_unknown_ack(tmp_path, monkeypatch):
    runtime, strategy = settled(tmp_path)
    runtime.record_submission(client_order_id="UNKNOWN", intent_id="unknown", episode_id="unknown",
        action="BTC_ENTRY", instrument_id=str(strategy.config.btc_id), quantity=".001", reduce_only=False)
    runtime.close()
    monkeypatch.setattr(stage, "DB", tmp_path / "live.sqlite")
    with pytest.raises(RuntimeError, match="LIVE_FLAT_HISTORY"):
        stage.flat_check()


def test_payload_rejects_extra_symlink(tmp_path):
    (tmp_path / "injected").symlink_to("/tmp")
    with pytest.raises(RuntimeError, match="UNEXPECTED_PAYLOAD_SYMLINK"):
        stage.files(tmp_path)
