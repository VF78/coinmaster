"""Isolated Stage-G activation rollback and repeat-deploy regression."""
from __future__ import annotations

import hashlib
import json
import sys
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
            return "inactive" if unit_name == deploy.PEERS[0] else "active" if unit_name != deploy.TRADER or service["active"] else "inactive"
        if field == "UnitFileState" and unit_name == deploy.PEERS[0]:
            return "disabled"
        if field == "MainPID":
            return str(service["pid"] if unit_name == deploy.TRADER else 0 if unit_name == deploy.PEERS[0] else 300)
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
    monkeypatch.setattr(deploy, "paper_port_open", lambda: False)

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


def test_stage_and_installed_python_checks_execute_against_release_fixture(tmp_path: Path, monkeypatch) -> None:
    commit = "a" * 40
    root = tmp_path / "releases" / commit / "runtime"
    (root / "coinmaster/ops").mkdir(parents=True)
    (root / "coinmaster/strategy").mkdir(parents=True)
    (root / "configs").mkdir()
    (root / "tests").mkdir()
    (root / "scripts").mkdir()
    (root / "coinmaster/__init__.py").write_text("")
    (root / "coinmaster/ops/__init__.py").write_text("")
    (root / "coinmaster/ops/stage_g_config.py").write_text(
        "from types import SimpleNamespace\n"
        "def load_candidate(path):\n"
        "    assert path.name == \"stage-g-v1.json\"\n"
        "    return SimpleNamespace(candidate=\"candidate\")\n"
    )
    (root / "coinmaster/ops/hyperliquid_testnet.py").write_text(
        "from pathlib import Path\nfrom types import SimpleNamespace\n"
        "def cross_venue_stage_g_gate(**kwargs):\n"
        "    assert kwargs[\"candidate\"] == \"candidate\"\n"
        "    assert kwargs[\"warmup_manifest\"] == Path(\"/var/lib/coinmaster-hl-stageg-testnet/data/current/manifest.json\")\n"
        "    return SimpleNamespace(warmup_state=\"READY\", approval_state=\"SEALED_APPROVAL_MATCH\", attachable=True)\n"
    )
    (root / "scripts/release_manifest.py").write_text(
        "def code_tree(root): return {\"ok\": 1}\n"
        "def seal_inputs(root): return {\"ok\": 2}\n"
    )
    (root / "release-manifest.json").write_text(json.dumps({
        "source": {"commit": commit}, "runtime_coinmaster": {"ok": 1},
        "sealed_inputs": {"ok": 2},
    }))
    (root / ".release-commit").write_text(commit + "\n")
    monkeypatch.setattr(deploy, "RELEASES", tmp_path / "releases")
    monkeypatch.setattr(deploy, "INSTALLED", root)
    monkeypatch.setattr(deploy, "PYTHON", Path(sys.executable))
    monkeypatch.setattr(deploy, "manifest_check", lambda *_: None)
    commands = []
    def execute(*args, cwd=None, env=None):
        commands.append(args)
        if len(args) > 1 and args[1] == "-c":
            subprocess.run(args, cwd=cwd, env=env, check=True)
    monkeypatch.setattr(deploy, "run", execute)
    deploy.stage_check(commit)
    deploy.installed_check(commit)
    assert sum(len(command) > 1 and command[1] == "-c" for command in commands) == 2
    assert any(len(command) > 2 and command[1:3] == ("-m", "pytest") for command in commands)


def test_retired_paper_peer_is_explicit_and_active_or_open_port_fails(tmp_path: Path, monkeypatch) -> None:
    state = {"paper_active": "inactive", "paper_unit": "disabled", "paper_pid": 0,
             "runtime_active": "active", "runtime_pid": 300, "port": False}
    paper, runtime = deploy.PEERS
    def fake_out(*args):
        field, unit = args[3], args[4]
        if unit == paper:
            return {"ActiveState": state["paper_active"], "UnitFileState": state["paper_unit"],
                    "MainPID": str(state["paper_pid"])}[field]
        return {"ActiveState": state["runtime_active"], "MainPID": str(state["runtime_pid"])}[field]
    monkeypatch.setattr(deploy, "out", fake_out)
    monkeypatch.setattr(deploy, "paper_port_open", lambda: state["port"])
    peers = {paper: 0, runtime: 300}
    assert deploy.peers_healthy(peers)
    state["paper_active"], state["paper_pid"] = "active", 400
    assert not deploy.peers_healthy(peers)
    state["paper_active"], state["paper_pid"] = "inactive", 0
    state["port"] = True
    assert not deploy.peers_healthy(peers)
    state["port"] = False
    state["runtime_pid"] = 301
    assert not deploy.peers_healthy(peers)
