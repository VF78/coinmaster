"""Deterministically export the paper runtime sidecar contract."""
from __future__ import annotations
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coinmaster.api.runtime_sidecar import create_runtime_app

target = Path(__file__).resolve().parents[2] / "coinmaster/src/web/lib/runtime.openapi.json"
target.write_text(json.dumps(create_runtime_app(database=":memory:", token="typegen", worker_url="http://127.0.0.1:9", worker_token="typegen").openapi(), sort_keys=True, indent=2) + "\n")
