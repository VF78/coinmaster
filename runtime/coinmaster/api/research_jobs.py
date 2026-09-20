"""Isolated, fail-closed local lifecycle for native research subprocesses."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from coinmaster.research.native_baseline import coverage_blockers

if TYPE_CHECKING:
    from coinmaster.api.app import ConfigurationRecord, ControlStore, RunRecord


class ResearchJobManager:
    """Owns only child process groups created by this control process."""
    def __init__(self, store: "ControlStore", data_root: Path, command_allowlist: dict[str, list[str]] | None = None) -> None:
        self.store, self.data_root = store, data_root
        self.commands = command_allowlist or {"native_baseline": [sys.executable, "-m", "coinmaster.research.native_baseline", "--data-root", str(data_root)]}
        self.processes: dict[str, subprocess.Popen[str]] = {}
        self.lock = threading.RLock()
        self.store.reconcile_orphaned_research()

    def start(self, config: "ConfigurationRecord", command_name: str | None) -> "RunRecord":
        from coinmaster.api.app import RunRecord, utcnow
        command_name = command_name or "native_baseline"
        if command_name not in self.commands:
            raise ValueError("RESEARCH_COMMAND_NOT_ALLOWED")
        request = {"config_id": config.id, "config_hash": config.config_hash, "command": command_name}
        request_hash = __import__("hashlib").sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if command_name == "native_baseline":
            blockers = coverage_blockers(self.data_root)
            if blockers:
                return self.store.save_run(RunRecord(id=__import__("uuid").uuid4().hex, config_id=config.id, kind="research", status="BLOCKED", evidence=blockers, created_at=utcnow(), report={"status": "BLOCKED", "blockers": blockers}, request_hash=request_hash, command_name=command_name, progress=100, finished_at=utcnow()))
        process = subprocess.Popen(self.commands[command_name], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
        run = self.store.save_run(RunRecord(id=__import__("uuid").uuid4().hex, config_id=config.id, kind="research", status="RUNNING", evidence=["NATIVE_RESEARCH_SUBPROCESS"], created_at=utcnow(), request_hash=request_hash, command_name=command_name, pid=process.pid, process_group=os.getpgid(process.pid), started_at=utcnow(), heartbeat_at=utcnow(), progress=0))
        with self.lock:
            self.processes[run.id] = process
        threading.Thread(target=self._observe, args=(run.id, process), daemon=True, name=f"coinmaster-research-{run.id[:8]}").start()
        return run

    def _observe(self, run_id: str, process: subprocess.Popen[str]) -> None:
        lines: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            lines.append(line)
            progress = self._progress(lines)
            self.store.update_run(run_id, heartbeat_at=__import__("coinmaster.api.app", fromlist=["utcnow"]).utcnow(), progress=progress)
        code = process.wait()
        with self.lock:
            self.processes.pop(run_id, None)
        run = self.store.get_run(run_id)
        report = self._json_report(lines)
        if run.cancel_requested_at is not None:
            status, evidence = "CANCELED", [*run.evidence, "CANCELED_OWNED_PROCESS_GROUP"]
        elif code == 2 and report and report.get("status") == "BLOCKED":
            status, evidence = "BLOCKED", list(report.get("blockers", []))
        elif code == 0 and report is not None:
            status, evidence = "COMPLETED", ["NATIVE_RESEARCH_RESULT", str(report.get("status", "UNKNOWN"))]
        else:
            status, evidence = "FAILED", ["NATIVE_RESEARCH_PROCESS_FAILED", f"EXIT_CODE:{code}"]
        self.store.update_run(run_id, status=status, evidence=evidence, report=report, heartbeat_at=__import__("coinmaster.api.app", fromlist=["utcnow"]).utcnow(), progress=100, finished_at=__import__("coinmaster.api.app", fromlist=["utcnow"]).utcnow())

    @staticmethod
    def _json_report(lines: list[str]) -> dict[str, Any] | None:
        for line in reversed(lines):
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                pass
        return None

    @staticmethod
    def _progress(lines: list[str]) -> int:
        for line in reversed(lines):
            try:
                value = json.loads(line)
                if isinstance(value, dict) and isinstance(value.get("progress"), int):
                    return max(0, min(99, value["progress"]))
            except json.JSONDecodeError:
                pass
        return 0

    def refresh(self, run_id: str) -> "RunRecord":
        run = self.store.get_run(run_id)
        with self.lock:
            process = self.processes.get(run_id)
        if process is not None and process.poll() is None:
            return self.store.update_run(run_id, heartbeat_at=__import__("coinmaster.api.app", fromlist=["utcnow"]).utcnow())
        return run

    def cancel(self, run_id: str) -> "RunRecord":
        run = self.store.get_run(run_id)
        if run.status not in {"RUNNING", "CANCEL_REQUESTED"}:
            return self.store.cancel(run_id)
        with self.lock:
            process = self.processes.get(run_id)
        if process is None or run.process_group is None:
            return self.store.update_run(run_id, status="INTERRUPTED", evidence=[*run.evidence, "CONTROL_RESTART_ORPHANED_PROCESS"], finished_at=__import__("coinmaster.api.app", fromlist=["utcnow"]).utcnow())
        self.store.update_run(run_id, status="CANCEL_REQUESTED", cancel_requested_at=__import__("coinmaster.api.app", fromlist=["utcnow"]).utcnow(), heartbeat_at=__import__("coinmaster.api.app", fromlist=["utcnow"]).utcnow())
        os.killpg(run.process_group, signal.SIGTERM)
        return self.store.get_run(run_id)
