#!/usr/bin/env python3
"""Build an immutable inactive Live82 payload; never start a trading process.

The optional pointer change only selects an inactive release. Real-order
permission remains the separate exact-account/release approval checked by
hl_live_worker before journal or credentials are accessed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile

REPO = Path(__file__).resolve().parents[2]
BASE = Path("/srv/coinmaster/hl-live")
DB = Path("/var/lib/coinmaster-hl-stageg-live/hl-stageg-live.sqlite")
WHEEL_SHA = "8ff3c6dcc150bc9ced8b96da80c4cf51645acf7efdc2b1d528634a3cad640b46"
UNIT = "coinmaster-hl-stageg-live.service"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def out(*args):
    return subprocess.check_output(args, text=True).strip()


def inactive():
    if (out("systemctl", "show", "-P", "ActiveState", UNIT) != "inactive"
            or out("systemctl", "show", "-P", "MainPID", UNIT) != "0"):
        raise RuntimeError("LIVE_MUST_BE_STOPPED_BY_OPERATOR_AT_FLAT")


def files(root):
    for p in root.rglob("*"):
        if p.is_symlink() and p.relative_to(root).as_posix() != ".venv":
            raise RuntimeError("LIVE_UNEXPECTED_PAYLOAD_SYMLINK")
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob("*"))
            if p.is_file() and not p.is_symlink() and ".venv" not in p.relative_to(root).parts
            and p.name != "live-release.json" and "__pycache__" not in p.parts}


def verify(root, commit):
    identity = json.loads((root / "live-release.json").read_text())
    if (identity["source_commit"] != commit or identity["state"] != "INACTIVE_NOT_ORDER_APPROVED"
            or identity["wheel_sha256"] != WHEEL_SHA or identity["files"] != files(root)):
        raise RuntimeError("LIVE_RELEASE_PAYLOAD_MISMATCH")
    sys.path.insert(0, str(root))
    from coinmaster.ops.hl_live_profile import load_live_profile
    from coinmaster.ops.stage_g_config import load_candidate
    profile = load_live_profile(root, load_candidate(root / "configs/hl-live-v3-dp50.candidate.json").candidate)
    if any(identity[key] != profile[key] for key in ("candidate_sha256", "strategy_sha256", "profile_sha256")):
        raise RuntimeError("LIVE_RELEASE_PROFILE_MISMATCH")
    if digest(root / identity["wheel_path"]) != WHEEL_SHA:
        raise RuntimeError("LIVE_QUALIFIED_WHEEL_MISMATCH")
    return identity


def flat_check():
    if not DB.exists():
        return
    marker = DB.parent / "manual-recovery-required"
    if marker.exists():
        raise RuntimeError("LIVE_MANUAL_RECOVERY_MARKER")
    # Validate a SQLite online backup. The original audit/lease/checkpoint is
    # never mutated by the deployment helper, nor is its journal reset.
    with tempfile.TemporaryDirectory(prefix="coinmaster-live-flat-") as directory:
        backup = Path(directory) / "journal.sqlite"
        with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as source, sqlite3.connect(backup) as target:
            source.backup(target)
        sys.path.insert(0, str(REPO / "runtime"))
        from coinmaster.ops.hl_live_epoch import LiveEpochRuntime
        journal = LiveEpochRuntime(backup, "hl-stageg-live", 10**20, require_native_cash=True)
        try:
            journal.prepare_flat_epoch(release_commit="inactive-pointer-validation")
        finally:
            journal.close()


def stage(commit, qualified):
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise RuntimeError("LIVE_INVALID_SOURCE_COMMIT")
    if out("git", "-C", str(REPO), "rev-parse", "HEAD") != commit:
        raise RuntimeError("LIVE_SOURCE_HEAD_MISMATCH")
    # Tracked source changes must be committed. Untracked reports are harmless.
    if out("git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("LIVE_SOURCE_DIRTY")
    previous = json.loads((qualified / "live-release.json").read_text())
    wheel_path = previous.get("wheel_path")
    wheels = list((qualified / "artifacts").glob("*.whl"))
    if not wheel_path:
        if len(wheels) != 1:
            raise RuntimeError("LIVE_QUALIFIED_WHEEL_UNPROVEN")
        wheel_path = str(wheels[0].relative_to(qualified))
    wheel = qualified / wheel_path
    if previous["wheel_sha256"] != WHEEL_SHA or digest(wheel) != WHEEL_SHA:
        raise RuntimeError("LIVE_QUALIFIED_WHEEL_MISMATCH")
    venv = (qualified / ".venv").resolve(strict=True)
    release = BASE / "releases" / (commit + "-v3-dp50-82-wheel-" + WHEEL_SHA[:12])
    if release.exists():
        verify(release, commit)
        return release
    incoming = release.with_name(release.name + ".incoming")
    incoming.mkdir(parents=True)
    try:
        archive = subprocess.check_output(["git", "-C", str(REPO), "archive", commit, "runtime"])
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            bundle.extractall(incoming, filter="data")
        root = incoming / "runtime"
        for item in list(root.iterdir()):
            item.rename(incoming / item.name)
        root.rmdir()
        sys.path.insert(0, str(incoming))
        from coinmaster.ops.hl_live_profile import load_live_profile
        from coinmaster.ops.stage_g_config import load_candidate
        profile = load_live_profile(incoming, load_candidate(incoming / "configs/hl-live-v3-dp50.candidate.json").candidate)
        target_wheel = incoming / "artifacts" / wheel.name
        target_wheel.parent.mkdir(exist_ok=True)
        shutil.copy2(wheel, target_wheel)
        (incoming / ".venv").symlink_to(venv, target_is_directory=True)
        identity = {
            "schema": "coinmaster-live-release-v1", "state": "INACTIVE_NOT_ORDER_APPROVED",
            "source_commit": commit, "profile_id": profile["profile_id"], "initial_capital_usdc": "82",
            "candidate_sha256": profile["candidate_sha256"], "strategy_sha256": profile["strategy_sha256"],
            "profile_sha256": profile["profile_sha256"], "wheel_sha256": WHEEL_SHA,
            "wheel_path": str(target_wheel.relative_to(incoming)),
            "qualified_venv": str(venv), "status_port": 18185, "files": files(incoming),
        }
        (incoming / "live-release.json").write_text(json.dumps(identity, sort_keys=True, indent=2) + "\n")
        verify(incoming, commit)
        incoming.rename(release)
        for item in release.rglob("*"):
            if not item.is_symlink():
                item.chmod(item.stat().st_mode & ~0o222)
        release.chmod(release.stat().st_mode & ~0o222)
    except BaseException:
        shutil.rmtree(incoming, ignore_errors=True)
        raise
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--qualified-release", type=Path, required=True)
    parser.add_argument("--select-inactive", action="store_true")
    args = parser.parse_args()
    inactive()
    release = stage(args.commit, args.qualified_release.resolve(strict=True))
    if args.select_inactive:
        inactive()
        flat_check()
        temporary = BASE / "current.next"
        if temporary.exists() or temporary.is_symlink():
            raise RuntimeError("LIVE_POINTER_UPDATE_ALREADY_PENDING")
        temporary.symlink_to(release)
        os.replace(temporary, BASE / "current")
    print(json.dumps({"release": str(release), "selected_inactive": args.select_inactive,
                      "native_started": False, "approval_created": False}))


if __name__ == "__main__":
    main()
