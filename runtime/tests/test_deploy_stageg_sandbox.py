"""Isolated Stage-G activation rollback and repeat-deploy regression."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from coinmaster.ops.paper import PaperRuntime
from scripts import deploy_stageg_sandbox as deploy


def test_failed_health_rolls_back_source_and_journal_then_repeat_is_noop(tmp_path: Path, monkeypatch) -> None:
    old, new = "a" * 40, "b" * 40
    installed = tmp_path / "installed"
    release = tmp_path / "releases" / new / "runtime"
    for root, commit in ((installed, old), (release, new)):
        (root / "coinmaster/strategy").mkdir(parents=True)
        (root / ".release-commit").write_text(commit + "\n")
        (root / "coinmaster/strategy/wave_overlay.py").write_text(commit + "\n")
    db = tmp_path / "state.sqlite"
    journal = PaperRuntime(db, "hl-stageg-testnet", int(120e9), require_native_cash=True)
    journal.acquire()
    journal.snapshot(
        ts_ns=1, positions=[], orders=[], funding_event_ids=[],
        native_account_total="10000", strategy_restartable=True,
    )
    journal.close()
    unit = tmp_path / "stageg.service"
    unit.write_text("test unit\n")
    monkeypatch.setattr(deploy, "INSTALLED", installed)
    monkeypatch.setattr(deploy, "RELEASES", tmp_path / "releases")
    monkeypatch.setattr(deploy, "BACKUPS", tmp_path / "backups")
    monkeypatch.setattr(deploy, "DB", db)
    monkeypatch.setattr(deploy, "UNIT_FILE", unit)
    monkeypatch.setattr(deploy, "stage_check", lambda commit: None)
    monkeypatch.setattr(deploy, "installed_check", lambda commit: (
        None if (installed / ".release-commit").read_text().strip() == commit
        else (_ for _ in ()).throw(RuntimeError("wrong installed commit"))
    ))
    monkeypatch.setattr(deploy.time, "sleep", lambda seconds: None)
    service = {"active": True, "pid": 100, "stops": 0, "starts": 0, "fail_new": True}

    def fake_out(*args: str) -> str:
        assert args[:4] == ("systemctl", "show", "-P", args[3])
        field, unit_name = args[3], args[4]
        if field == "ActiveState":
            return "active" if unit_name != deploy.TRADER or service["active"] else "inactive"
        if field == "MainPID":
            return str(service["pid"] if unit_name == deploy.TRADER else 200 if unit_name == deploy.PEERS[0] else 300)
        if field == "NRestarts":
            return "0"
        raise AssertionError(args)

    def fake_run(*args: str, cwd=None, env=None) -> None:
        if args[0] == "systemctl":
            assert args[2] == deploy.TRADER
            if args[1] == "stop":
                service["active"] = False
                service["stops"] += 1
            else:
                service["active"] = True
                service["starts"] += 1
                service["pid"] += 1
            return
        subprocess.run(args, cwd=cwd, env=env, check=True)

    def fake_status() -> dict:
        commit = (installed / ".release-commit").read_text().strip()
        strategy = installed / "coinmaster/strategy/wave_overlay.py"
        return {
            "process_state": "DATA_STALE" if commit == new and service["fail_new"] else "PUBLIC_FEEDS_READY",
            "native_thread_alive": True,
            "recovery_required": False,
            "live_order_capability": False,
            "positions": [],
            "orders": [],
            "warmup": {"state": "READY"},
            "gates": {"approval_state": "SEALED_APPROVAL_MATCH"},
            "hashes": {"strategy_sha256": hashlib.sha256(strategy.read_bytes()).hexdigest()},
            "account": {"native_cash": "10000"},
            "deposit_protection": {"state": "ARMED"},
            "feeds": {coin: {"state": "READY"} for coin in deploy.COINS},
        }

    monkeypatch.setattr(deploy, "out", fake_out)
    monkeypatch.setattr(deploy, "run", fake_run)
    monkeypatch.setattr(deploy, "status", fake_status)

    with pytest.raises(RuntimeError, match="TRADER_HEALTH_TIMEOUT"):
        deploy.activate(new)
    assert (installed / ".release-commit").read_text().strip() == old
    assert (installed / "coinmaster/strategy/wave_overlay.py").read_text() == old + "\n"
    assert service["active"] and service["starts"] == 2 and service["stops"] == 2
    assert next((tmp_path / "backups").iterdir()).joinpath("result").read_text().startswith("ROLLED_BACK:")
    assert deploy.flat_cash() == 10000

    service["fail_new"] = False
    backup = deploy.activate(new)
    assert Path(backup).joinpath("result").read_text() == "ACTIVE\n"
    counts = (service["starts"], service["stops"])
    assert deploy.activate(new) == "ALREADY_ACTIVE"
    assert (service["starts"], service["stops"]) == counts
    assert (installed / ".release-commit").read_text().strip() == new
