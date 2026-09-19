"""Deterministically export the local FastAPI contract without opening a listener."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coinmaster.api.app import create_app

target = Path(__file__).resolve().parents[2] / "coinmaster/src/web/lib/nautilus.openapi.json"
target.write_text(json.dumps(create_app(database=":memory:", token="typegen").openapi(), sort_keys=True, indent=2) + "\n")
