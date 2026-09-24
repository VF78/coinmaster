"""Refresh the isolated Stage-G signal warmup from genuine public Bybit pages.

The current symlink changes only after the complete successor artifact passes
raw-page hash, daily coverage, and latest-completed-session checks. No worker
database, strategy, order route, or historical source artifact is modified.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from coinmaster.ops.stage_g_config import load_testnet_instance_config
from coinmaster.ops.stage_g_warmup import DAY_MS, extend_stageg_bybit_warmup, load_stageg_bybit_warmup
from coinmaster.research.bybit_data import ingest


def _promote(data_root: Path, artifact: Path) -> None:
    temporary = data_root / f".current-{uuid.uuid4().hex}"
    temporary.symlink_to(artifact.name, target_is_directory=True)
    os.replace(temporary, data_root / "current")


def refresh_stageg_warmup(data_root: Path, *, now_ms: int | None = None) -> Path:
    data_root = data_root.resolve(strict=True)
    now_ms = int(datetime.now(UTC).timestamp() * 1000) if now_ms is None else now_ms
    today_ms = now_ms // DAY_MS * DAY_MS
    today = datetime.fromtimestamp(today_ms / 1000, UTC)
    pointer = data_root / "current"
    lock_path = data_root / ".stageg-warmup-refresh.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = (pointer / "manifest.json").resolve(strict=True)
        # The pointer must resolve to one immediate immutable artifact.
        if current.parent.parent != data_root or current.name != "manifest.json":
            raise ValueError("WARMUP_POINTER_OUTSIDE_ISOLATED_ROOT")
        predecessor_end = int(json.loads(current.read_text())["warmup_end_exclusive_ms"])
        _, predecessor_state = load_stageg_bybit_warmup(current, now_ms=predecessor_end)
        if predecessor_state != "READY":
            raise ValueError(f"WARMUP_PREDECESSOR_INVALID:{predecessor_state}")
        if predecessor_end == today_ms:
            return current
        if predecessor_end > today_ms:
            raise ValueError("WARMUP_PREDECESSOR_IN_FUTURE")
        prefix = f"stageg-bybit-warmup-{today:%Y%m%d}-verified-"
        for candidate in sorted(data_root.glob(prefix + "*/manifest.json")):
            _, state = load_stageg_bybit_warmup(candidate, now_ms=today_ms)
            if state == "READY":
                _promote(data_root, candidate.parent)
                return candidate
        tail = data_root / f"bybit-tail-{today:%Y%m%d}-{uuid.uuid4().hex[:8]}"
        start = datetime.fromtimestamp(predecessor_end / 1000, UTC).isoformat()
        end = today.isoformat()
        ingest(start, end, tail)
        tail_manifest = json.loads((tail / "bybit/manifest.json").read_text())
        artifact = data_root / f"{prefix}{tail_manifest['raw_manifest_sha256'][:12]}"
        if artifact.exists():
            raise FileExistsError("VERIFIED_ARTIFACT_NAME_COLLISION")
        staging = data_root / f".stageg-artifact-{uuid.uuid4().hex}"
        manifest = extend_stageg_bybit_warmup(
            predecessor_manifest=current, tail_root=tail, output_root=staging, now_ms=today_ms,
        )
        _, state = load_stageg_bybit_warmup(manifest, now_ms=today_ms)
        if state != "READY":
            raise ValueError(f"WARMUP_SUCCESSOR_INVALID:{state}")
        staging.rename(artifact)
        _promote(data_root, artifact)
        return artifact / "manifest.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    configured = os.environ.get("COINMASTER_HL_TESTNET_INSTANCE_CONFIG")
    if configured:
        instance = load_testnet_instance_config(Path(configured))
        expected = args.data_root.resolve(strict=True) / "current" / "manifest.json"
        if instance.signal_warmup_manifest != expected:
            raise ValueError("STAGEG_UNIT_ENV_WARMUP_MISMATCH")
    manifest = refresh_stageg_warmup(args.data_root)
    print(json.dumps({"manifest": str(manifest), "state": "READY"}, sort_keys=True))


if __name__ == "__main__":
    main()
