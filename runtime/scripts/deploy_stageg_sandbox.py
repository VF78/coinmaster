#!/usr/bin/env python3
"""Stage and activate one exact Stage-G Sandbox commit with automatic rollback."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RELEASES = Path("/srv/coinmaster/stageg-releases")
INSTALLED = Path("/srv/coinmaster/runtime")
DB = Path("/var/lib/coinmaster-hl-stageg-testnet/hl-stageg-testnet.sqlite")
BACKUPS = Path("/var/lib/coinmaster-hl-stageg-testnet/backups")
UNIT_FILE = Path("/etc/systemd/system/coinmaster-hl-stageg-testnet.service")
PYTHON = INSTALLED / ".venv/bin/python"
LOCK = Path("/run/coinmaster-stageg-deploy.lock")
TRADER = "coinmaster-hl-stageg-testnet.service"
PEERS = ("coinmaster-paper.service", "coinmaster-runtime.service")
COINS = ("BTC-USD-PERP.HYPERLIQUID", "SOL-USD-PERP.HYPERLIQUID")


def run(*args: str, cwd: Path | None = None, env: dict | None = None) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)


def out(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def active(unit: str) -> bool:
    return out("systemctl", "show", "-P", "ActiveState", unit) == "active"


def pid(unit: str) -> int:
    return int(out("systemctl", "show", "-P", "MainPID", unit))


def status() -> dict:
    with urllib.request.urlopen("http://127.0.0.1:18183/status", timeout=3) as response:
        return json.load(response)


def manifest_check(commit: str, root: Path) -> None:
    run(
        sys.executable, str(root / "scripts/release_manifest.py"), "verify",
        "--runtime-root", str(root), "--release-root", str(root.parent),
        "--manifest", str(root / "release-manifest.json"),
        "--expected-commit", commit, "--component", "trader",
    )


def stage_check(commit: str) -> None:
    root = RELEASES / commit / "runtime"
    manifest_check(commit, root)
    env = dict(os.environ, PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE="1")
    gate = (
        "from pathlib import Path\n"
        "from coinmaster.ops.stage_g_config import load_candidate\n"
        "from coinmaster.ops.hyperliquid_testnet import cross_venue_stage_g_gate\n"
        "r=Path.cwd();g=cross_venue_stage_g_gate(candidate=load_candidate(r/configs/stage-g-v1.json).candidate,"
        "warmup_manifest=Path(/var/lib/coinmaster-hl-stageg-testnet/data/current/manifest.json),"
        "strategy_path=r/coinmaster/strategy/wave_overlay.py,profile_root=r)\n"
        "assert g.warmup_state==READY and g.approval_state==SEALED_APPROVAL_MATCH and g.attachable\n"
    )
    run(str(PYTHON), "-c", gate, cwd=root, env=env)
    run(
        str(PYTHON), "-m", "pytest", "-q",
        str(root / "tests/test_hyperliquid_testnet.py")
        + "::test_stageg_prime_registers_trading_strategy_with_native_market_exit",
        cwd=root, env=env,
    )


def installed_check(commit: str) -> None:
    if (INSTALLED / ".release-commit").read_text().strip() != commit:
        raise RuntimeError("INSTALLED_COMMIT_MISMATCH")
    code = (
        "import json,sys\n"
        "from pathlib import Path\n"
        "r=Path.cwd();sys.path.insert(0,str(r/scripts));import release_manifest as m\n"
        "x=json.loads((r/release-manifest.json).read_text())\n"
        "assert x[source][commit]==sys.argv[1]\n"
        "assert m.code_tree(r)==x[runtime_coinmaster]\n"
        "assert m.seal_inputs(r)==x[sealed_inputs]\n"
    )
    run(str(PYTHON), "-c", code, commit, cwd=INSTALLED)


def stage(commit: str) -> str:
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise RuntimeError("INVALID_COMMIT")
    if out("git", "-C", str(REPO), "rev-parse", "HEAD") != commit:
        raise RuntimeError("SOURCE_HEAD_MISMATCH")
    if out("git", "-C", str(REPO), "status", "--porcelain=v1", "--untracked-files=all"):
        raise RuntimeError("SOURCE_DIRTY")
    release = RELEASES / commit
    if release.exists():
        stage_check(commit)
        return "ALREADY_STAGED"
    incoming = RELEASES / (commit + ".incoming")
    if incoming.exists():
        raise RuntimeError("INCOMPLETE_STAGE_EXISTS")
    incoming.mkdir(parents=True)
    renamed = False
    try:
        archive = subprocess.check_output(["git", "-C", str(REPO), "archive", commit, "runtime"])
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(incoming, filter="data")
        root = incoming / "runtime"
        (root / ".release-commit").write_text(commit + "\n")
        run(
            sys.executable, str(root / "scripts/release_manifest.py"), "generate",
            "--source-root", str(REPO), "--runtime-root", str(root),
            "--release-root", str(incoming), "--component", "trader",
            "--output", str(root / "release-manifest.json"),
        )
        incoming.rename(release)
        renamed = True
        stage_check(commit)
        for item in release.rglob("*"):
            item.chmod(item.stat().st_mode & ~0o222)
        release.chmod(release.stat().st_mode & ~0o222)
        return "STAGED"
    except Exception:
        shutil.rmtree(incoming, ignore_errors=True)
        if renamed:
            shutil.rmtree(release, ignore_errors=True)
        raise


def flat_cash() -> Decimal:
    sys.path.insert(0, str(INSTALLED))
    from coinmaster.ops.paper import PaperRuntime

    journal = PaperRuntime(DB, "hl-stageg-testnet", int(120e9), require_native_cash=True)
    journal.acquire()
    try:
        if (
            journal.recovery_state() != "FLAT_RESTART"
            or not journal.coherent_snapshot()
            or journal.projection_snapshot() != ([], [])
            or journal.pending_submissions()
            or journal.pending_native_funding()
        ):
            raise RuntimeError("DURABLE_STATE_NOT_CONFIRMED_FLAT")
        cash = journal.flat_native_cash()
        if cash is None or not cash.is_finite() or cash <= 0:
            raise RuntimeError("DURABLE_CASH_UNKNOWN")
        return cash
    finally:
        journal.close()


def copy_db(source: Path, target: Path) -> None:
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("BACKUP_DB_INTEGRITY_FAILED")
    finally:
        dst.close()
        src.close()


def copy_runtime(source: Path) -> None:
    run(
        "rsync", "-a", "--checksum", "--delete", "--exclude=/.venv/",
        "--exclude=__pycache__/", "--exclude=.pytest_cache/",
        str(source) + "/", str(INSTALLED) + "/",
    )


def health(cash: Decimal, peers: dict[str, int]) -> None:
    last = None
    for _ in range(18):
        try:
            worker_pid = pid(TRADER)
            for sample in range(3):
                s = status()
                expected_sha = hashlib.sha256((INSTALLED / "coinmaster/strategy/wave_overlay.py").read_bytes()).hexdigest()
                if (
                    not active(TRADER) or worker_pid <= 0 or pid(TRADER) != worker_pid
                    or int(out("systemctl", "show", "-P", "NRestarts", TRADER)) != 0
                    or any(not active(unit) or pid(unit) != peer for unit, peer in peers.items())
                    or s.get("process_state") != "PUBLIC_FEEDS_READY"
                    or s.get("native_thread_alive") is not True
                    or s.get("recovery_required") is not False
                    or s.get("live_order_capability") is not False
                    or s.get("positions") != [] or s.get("orders") != []
                    or s.get("warmup", {}).get("state") != "READY"
                    or s.get("gates", {}).get("approval_state") != "SEALED_APPROVAL_MATCH"
                    or s.get("hashes", {}).get("strategy_sha256") != expected_sha
                    or Decimal(s.get("account", {}).get("native_cash", "NaN")) != cash
                    or s.get("deposit_protection", {}).get("state") not in {"ARMED", "TRIPPED_FLAT"}
                    or any(s.get("feeds", {}).get(coin, {}).get("state") != "READY" for coin in COINS)
                ):
                    raise RuntimeError("TRADER_HEALTH_NOT_READY")
                if sample < 2:
                    time.sleep(5)
            return
        except Exception as error:
            last = error
            time.sleep(5)
    raise RuntimeError(f"TRADER_HEALTH_TIMEOUT:{last}")


def backup_source(target: Path) -> None:
    def exclude(item: tarfile.TarInfo) -> tarfile.TarInfo | None:
        return None if any(p in {".venv", "__pycache__", ".pytest_cache"} for p in Path(item.name).parts) else item

    with tarfile.open(target, "w:gz") as tar:
        tar.add(INSTALLED, arcname=".", filter=exclude)


def activate(commit: str) -> str:
    stage_check(commit)
    prior = (INSTALLED / ".release-commit").read_text().strip()
    peers = {unit: pid(unit) for unit in PEERS}
    if prior == commit:
        installed_check(commit)
        cash = Decimal(status().get("account", {}).get("native_cash", "NaN"))
        if not cash.is_finite() or cash <= 0:
            raise RuntimeError("ACTIVE_CASH_UNKNOWN")
        health(cash, peers)
        return "ALREADY_ACTIVE"
    s = status()
    if (
        not active(TRADER) or s.get("process_state") != "PUBLIC_FEEDS_READY"
        or s.get("native_thread_alive") is not True
        or s.get("recovery_required") is not False
        or s.get("live_order_capability") is not False
        or s.get("positions") != [] or s.get("orders") != []
    ):
        raise RuntimeError("PRESTOP_WORKER_NOT_FLAT_READY")
    cash = Decimal(s.get("account", {}).get("native_cash", "NaN"))
    if not cash.is_finite() or cash <= 0:
        raise RuntimeError("PRESTOP_CASH_UNKNOWN")
    backup = BACKUPS / f"stageg-pre-{commit}-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}"
    backup.mkdir(mode=0o700, parents=True)
    backup_source(backup / "installed-runtime.tar.gz")
    shutil.copy2(UNIT_FILE, backup / "prior.unit")
    (backup / "prior.identity").write_text(json.dumps({"commit": prior, "trader_pid": pid(TRADER), "peers": peers}) + "\n")
    run("systemctl", "stop", TRADER)
    try:
        if active(TRADER) or flat_cash() != cash:
            raise RuntimeError("STOPPED_STATE_NOT_FLAT")
        copy_db(DB, backup / "stopped-state.sqlite")
        copy_runtime(RELEASES / commit / "runtime")
        installed_check(commit)
        run("systemctl", "start", TRADER)
        health(cash, peers)
        (backup / "result").write_text("ACTIVE\n")
        return str(backup)
    except BaseException as error:
        try:
            if active(TRADER):
                run("systemctl", "stop", TRADER)
            with tempfile.TemporaryDirectory(prefix="stageg-rollback-") as tmp:
                with tarfile.open(backup / "installed-runtime.tar.gz", "r:gz") as tar:
                    tar.extractall(tmp, filter="data")
                copy_runtime(Path(tmp))
            if (backup / "stopped-state.sqlite").exists():
                copy_db(backup / "stopped-state.sqlite", DB)
            run("systemctl", "start", TRADER)
            if (INSTALLED / ".release-commit").read_text().strip() != prior:
                raise RuntimeError("ROLLBACK_COMMIT_MISMATCH")
            if (INSTALLED / "release-manifest.json").exists():
                installed_check(prior)
            health(cash, peers)
            (backup / "result").write_text(f"ROLLED_BACK:{type(error).__name__}\n")
        except BaseException as restore_error:
            raise RuntimeError(f"ROLLBACK_FAILED:{restore_error}") from error
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("stage", "activate"))
    parser.add_argument("commit", help="exact 40-character source commit")
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("root is required")
    with LOCK.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = stage(args.commit) if args.action == "stage" else activate(args.commit)
        print(result, args.commit)


if __name__ == "__main__":
    main()
