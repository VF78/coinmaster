from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/native_gui_worker_gate.py"
spec = importlib.util.spec_from_file_location("native_gui_worker_gate", SCRIPT)
assert spec and spec.loader
worker_gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker_gate)
FIXTURE = Path(__file__).parent / "fixtures/hl_stageg_owned_tp_status.json"


def test_raw_worker_gate_accepts_fresh_status_when_old_api_rejects_reduce_only() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["orders"][0]["reduce_only"] is True

    class OldApiOrder(BaseModel):
        model_config = ConfigDict(extra="forbid")
        client_order_id: str

    # The installed old GUI API rejects the worker's newer order field, while
    # the deployment preflight fingerprints the raw, read-only worker status.
    with pytest.raises(ValidationError, match="reduce_only"):
        OldApiOrder.model_validate(payload["orders"][0])
    state, strategy = worker_gate.worker_fingerprint(payload, now_ns=payload["observed_at_ns"])
    assert state == "READY"
    assert strategy == payload["hashes"]["strategy_sha256"]


def test_raw_worker_gate_rejects_stale_wrong_identity_or_live_capability() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    observed = payload["observed_at_ns"]
    with pytest.raises(ValueError, match="stale"):
        worker_gate.worker_fingerprint(payload, now_ns=observed + worker_gate.MAX_AGE_NS + 1)
    with pytest.raises(ValueError, match="identity or safety"):
        worker_gate.worker_fingerprint({**payload, "instance_id": "other"}, now_ns=observed)
    with pytest.raises(ValueError, match="identity or safety"):
        worker_gate.worker_fingerprint({**payload, "live_order_capability": True}, now_ns=observed)
