"""Durable, owned-process lifecycle for the one canonical native research runner."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from coinmaster.research.native_baseline import _candidate_from_job_config, coverage_blockers
from coinmaster.research.job_protocol import report_summary

if TYPE_CHECKING:
    from coinmaster.api.app import ConfigurationRecord, ControlStore, RunRecord


MAX_STDOUT_BYTES = 256 * 1024
ACTIVE = {"STARTING", "RUNNING", "CANCEL_REQUESTED"}


class ResearchJobManager:
    """Owns process groups created by this manager and nothing else."""
    def __init__(self, store: "ControlStore", data_root: Path, command_allowlist: dict[str, list[str]] | None = None, test_options: dict[str, Any] | None = None) -> None:
        self.store, self.data_root, self.test_options = store, data_root, test_options
        self.commands = command_allowlist or {"native_baseline": [sys.executable, "-m", "coinmaster.research.native_baseline"]}
        self.processes: dict[str, subprocess.Popen[str]] = {}
        self.lock = threading.RLock()
        self._reconcile_restart()

    @staticmethod
    def _now() -> str:
        from coinmaster.api.app import utcnow
        return utcnow()

    @staticmethod
    def _request_hash(payload: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _ps_identity(pid: int, request_path: Path) -> tuple[int, str] | None:
        try:
            # ``lstart`` binds the identity to this process incarnation, rather
            # than trusting a reusable PID plus command/process-group alone.
            output = subprocess.check_output(["ps", "-o", "pgid=", "-o", "lstart=", "-o", "command=", "-p", str(pid)], text=True).strip()
            if not output:
                return None
            pgid_text, command = output.split(None, 1)
            if str(request_path) not in command:
                return None
            return int(pgid_text), hashlib.sha256(output.encode()).hexdigest()
        except (OSError, subprocess.CalledProcessError, ValueError):
            # macOS sandbox tests deny ``ps``.  This fallback is accepted only
            # for injected test commands; production restart recovery refuses
            # to signal a process unless the command line was verified above.
            try:
                pgid = os.getpgid(pid)
                return pgid, "fallback:" + hashlib.sha256(f"{pid}:{pgid}:{request_path}".encode()).hexdigest()
            except OSError:
                return None

    def _work_dir(self, run_id: str) -> Path:
        path = self.data_root / "runs" / "jobs" / run_id
        path.mkdir(parents=True, exist_ok=False)
        os.chmod(path, 0o700)
        return path

    @staticmethod
    def _write_launch_permit(path: Path, request_hash: str, owner: str, process: subprocess.Popen[str], identity: str) -> None:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"request_hash": request_hash, "owner_token": owner, "pid": process.pid, "process_identity": identity}, sort_keys=True) + "\n")
        os.chmod(temporary, 0o600)
        temporary.replace(path)

    def _reconcile_restart(self) -> None:
        """Stop only a surviving child whose command and owner file still match."""
        for run in self.store.runs():
            if run.kind != "research" or run.status not in ACTIVE:
                continue
            evidence = [*run.evidence, "CONTROL_RESTART_ORPHANED_PROCESS"]
            owned = self._owned_identity(run)
            if owned is not None:
                _, pgid = owned
                if self._terminate_group(pgid):
                    evidence.append("ORPHAN_OWNED_PROCESS_TERMINATED")
                    self._finish_after_verified_death(run.id, "INTERRUPTED", evidence)
                else:
                    self.store.update_run(run.id, status="CANCEL_REQUESTED", evidence=[*evidence, "ORPHAN_TERMINATION_UNCONFIRMED_LEASE_HELD"], cancel_requested_at=self._now(), heartbeat_at=self._now())
            else:
                if self._group_gone(run.process_group):
                    self._finish_after_verified_death(run.id, "INTERRUPTED", [*evidence, "ORPHAN_PROCESS_GROUP_CONFIRMED_GONE"])
                else:
                    self.store.update_run(run.id, status="CANCEL_REQUESTED", evidence=[*evidence, "ORPHAN_IDENTITY_MISMATCH_LEASE_HELD"], cancel_requested_at=self._now(), heartbeat_at=self._now())

    def _owned_identity(self, run: "RunRecord") -> tuple[int, int] | None:
        if not run.pid or not run.process_group or not run.process_identity or not run.work_dir:
            return None
        request_path = Path(run.work_dir) / "request.json"
        owner_path = Path(run.work_dir) / "owner.token"
        try:
            token = owner_path.read_text().strip()
        except OSError:
            return None
        row = self.store.db.execute("SELECT owner_token FROM runs WHERE id=?", (run.id,)).fetchone()
        if not row or not secrets.compare_digest(token, row[0] or ""):
            return None
        identity = self._ps_identity(run.pid, request_path)
        if identity is None:
            return None
        pgid, digest = identity
        if digest.startswith("fallback:") and run.command_name == "native_baseline" and self.test_options is None:
            return None
        return (run.pid, pgid) if pgid == run.process_group and secrets.compare_digest(digest, run.process_identity) else None

    def start(self, config: "ConfigurationRecord", command_name: str | None, idempotency_key: str | None = None) -> "RunRecord":
        from coinmaster.api.app import RunRecord
        command_name = command_name or "native_baseline"
        if command_name not in self.commands:
            raise ValueError("RESEARCH_COMMAND_NOT_ALLOWED")
        if idempotency_key:
            existing = self.store.run_for_idempotency(idempotency_key)
            if existing is not None:
                if existing.config_id == config.id and existing.command_name == command_name:
                    return existing
                raise ValueError("IDEMPOTENCY_KEY_REUSED")
        with self.lock:
            run_id, owner = uuid4().hex, secrets.token_urlsafe(24)
            work_dir = self._work_dir(run_id)
            owner_path, request_path, permit_path = work_dir / "owner.token", work_dir / "request.json", work_dir / "launch-permit.json"
            owner_path.write_text(owner + "\n")
            os.chmod(owner_path, 0o600)
            request = {"config_hash": config.config_hash, "config": config.config.model_dump(), "data_root": str(self.data_root), "artifact_dir": str(work_dir / "artifacts"), "launch_permit": str(permit_path), "launch_owner_token": owner}
            request_hash = self._request_hash(request)
            request["request_hash"] = request_hash
            if self.test_options is not None:
                request["test_options"] = self.test_options
            request_path.write_text(json.dumps(request, sort_keys=True) + "\n")
            os.chmod(request_path, 0o600)
            try:
                _candidate_from_job_config(request["config"])
            except (KeyError, TypeError, ValueError) as error:
                return self.store.save_run(RunRecord(id=run_id, config_id=config.id, kind="research", status="BLOCKED", evidence=[str(error)], created_at=self._now(), report={"type": "result", "status": "BLOCKED", "request_hash": request_hash, "config_hash": config.config_hash, "blockers": [str(error)]}, request_hash=request_hash, command_name=command_name, work_dir=str(work_dir), idempotency_key=idempotency_key, progress=100, finished_at=self._now()))
            blocked = coverage_blockers(self.data_root) if command_name == "native_baseline" and self.test_options is None else []
            if blocked:
                return self.store.save_run(RunRecord(id=run_id, config_id=config.id, kind="research", status="BLOCKED", evidence=blocked, created_at=self._now(), report={"type": "result", "status": "BLOCKED", "request_hash": request_hash, "config_hash": config.config_hash, "blockers": blocked}, request_hash=request_hash, command_name=command_name, work_dir=str(work_dir), idempotency_key=idempotency_key, progress=100, finished_at=self._now()))
            starting_record = RunRecord(id=run_id, config_id=config.id, kind="research", status="STARTING", evidence=["NATIVE_RESEARCH_START_INTENT"], created_at=self._now(), request_hash=request_hash, command_name=command_name, work_dir=str(work_dir), idempotency_key=idempotency_key, progress=0)
            if command_name == "native_baseline":
                acquired, existing = self.store.acquire_research_start(starting_record)
                if acquired == "EXISTING":
                    if existing and existing.config_id == config.id and existing.command_name == command_name:
                        return existing
                    raise ValueError("IDEMPOTENCY_KEY_REUSED")
                if acquired == "BUSY":
                    raise ValueError("CANONICAL_RESEARCH_ALREADY_ACTIVE")
            else:
                self.store.save_run(starting_record)
            self.store.update_run(run_id, owner_token=owner)
            command = [part.replace("{job_request}", str(request_path)) for part in self.commands[command_name]]
            if "{job_request}" not in self.commands[command_name]:
                command.extend(["--job-request", str(request_path)])
            try:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
                identity = self._ps_identity(process.pid, request_path)
                if identity is None:
                    raise RuntimeError("PROCESS_IDENTITY_UNVERIFIABLE")
                pgid, digest = identity
                started = self.store.update_run(run_id, status="RUNNING", pid=process.pid, process_group=pgid, process_identity=digest, started_at=self._now(), heartbeat_at=self._now())
                self._write_launch_permit(permit_path, request_hash, owner, process, digest)
            except Exception as error:
                if "process" in locals():
                    if self._terminate_process(process):
                        self._finish_after_verified_death(run_id, "FAILED", ["RESEARCH_LAUNCH_FAILED", type(error).__name__])
                    else:
                        self.store.update_run(run_id, status="CANCEL_REQUESTED", evidence=["RESEARCH_LAUNCH_FAILED", type(error).__name__, "PROCESS_DEATH_UNCONFIRMED_LEASE_HELD"], cancel_requested_at=self._now(), heartbeat_at=self._now())
                else:
                    # Popen itself failed, so no child exists to prove/reap.
                    self.store.update_run(run_id, status="FAILED", evidence=["RESEARCH_LAUNCH_FAILED", type(error).__name__], finished_at=self._now(), progress=100, release_research_lease=True)
                raise RuntimeError("RESEARCH_LAUNCH_FAILED") from error
            self.processes[run_id] = process
            threading.Thread(target=self._observe, args=(run_id, process), daemon=True, name=f"coinmaster-research-{run_id[:8]}").start()
            return started

    @staticmethod
    def _group_gone(pgid: int | None) -> bool:
        if not pgid:
            return False
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return True
        except OSError:
            return False
        return False

    def _finish_after_verified_death(self, run_id: str, status: str, evidence: list[str], report: dict[str, Any] | None = None) -> "RunRecord":
        run = self.store.get_run(run_id)
        if self.store.has_research_lease(run_id) and not self._group_gone(run.process_group):
            return self.store.update_run(run_id, status="CANCEL_REQUESTED", evidence=[*run.evidence, "PROCESS_DEATH_UNCONFIRMED_LEASE_HELD"], cancel_requested_at=self._now(), heartbeat_at=self._now())
        values: dict[str, Any] = {"status": status, "evidence": evidence, "finished_at": self._now(), "progress": 100}
        if report is not None:
            values["report"] = report
        return self.store.update_run(run_id, release_research_lease=True, **values)

    @classmethod
    def _terminate_process(cls, process: subprocess.Popen[str]) -> bool:
        try:
            pgid = os.getpgid(process.pid)
        except OSError:
            pgid = None
        try:
            if pgid:
                os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                if pgid:
                    os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
            process.wait(timeout=1)
        return process.poll() is not None and cls._group_gone(pgid)

    @staticmethod
    def _terminate_group(pgid: int) -> bool:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            return ResearchJobManager._group_gone(pgid)
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            try:
                os.killpg(pgid, 0)
            except ProcessLookupError:
                return True
            time.sleep(0.02)
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            if ResearchJobManager._group_gone(pgid):
                return True
            time.sleep(0.02)
        return ResearchJobManager._group_gone(pgid)

    def _observe(self, run_id: str, process: subprocess.Popen[str]) -> None:
        lines: list[str] = []
        size = 0
        try:
            assert process.stdout is not None
            for line in process.stdout:
                size += len(line.encode())
                if size > MAX_STDOUT_BYTES:
                    self._terminate_process(process)
                    raise RuntimeError("RESEARCH_STDOUT_LIMIT")
                lines.append(line)
                item = self._typed(line)
                if item and item.get("type") == "progress" and self._matches(run_id, item):
                    self.store.update_run(run_id, heartbeat_at=self._now(), progress=max(0, min(99, int(item["progress"]))))
            code = process.wait()
            self._finalize(run_id, code, lines)
        except Exception as error:
            self._terminate_process(process)
            with self.lock:
                run = self.store.get_run(run_id)
                if run.status in ACTIVE:
                    self._finish_after_verified_death(run_id, "FAILED", [*run.evidence, "RESEARCH_OBSERVER_FAILED", type(error).__name__])
        finally:
            with self.lock:
                self.processes.pop(run_id, None)

    @staticmethod
    def _typed(line: str) -> dict[str, Any] | None:
        try:
            value = json.loads(line)
            return value if isinstance(value, dict) and isinstance(value.get("type"), str) else None
        except json.JSONDecodeError:
            return None

    def _matches(self, run_id: str, item: dict[str, Any]) -> bool:
        run = self.store.get_run(run_id)
        return item.get("request_hash") == run.request_hash and item.get("config_hash") == self.store.get_config(run.config_id).config_hash

    def _finalize(self, run_id: str, code: int, lines: list[str]) -> None:
        with self.lock:
            self._finalize_locked(run_id, code, lines)

    def _finalize_locked(self, run_id: str, code: int, lines: list[str]) -> None:
        run = self.store.get_run(run_id)
        if run.status not in ACTIVE:
            return  # A restart/cancel terminal transition wins this observer.
        result = next((item for item in reversed([self._typed(line) for line in lines]) if item and item.get("type") == "result"), None)
        if run.status == "CANCEL_REQUESTED":
            self._finish_after_verified_death(run_id, "CANCELED", [*run.evidence, "CANCELED_OWNED_PROCESS_GROUP"])
            return
        if not result or not self._matches(run_id, result):
            self._finish_after_verified_death(run_id, "FAILED", ["INVALID_OR_MISSING_TYPED_RESULT", f"EXIT_CODE:{code}"])
            return
        if result.get("status") == "BLOCKED" and code == 2:
            self._finish_after_verified_death(run_id, "BLOCKED", list(result.get("blockers", [])), result)
            return
        artifact = Path(str(result.get("artifact", "")))
        work = Path(run.work_dir or "")
        if code != 0 or result.get("status") != "COMPLETED" or not artifact.is_file() or work not in artifact.parents:
            self._finish_after_verified_death(run_id, "FAILED", ["RESULT_VALIDATION_FAILED", f"EXIT_CODE:{code}"], result)
            return
        envelope = artifact.parent / "result-envelope.json"
        try:
            expected = str(result["artifact_sha256"])
            actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
            stored_envelope = json.loads(envelope.read_text())
            report = json.loads(artifact.read_text())
        except (KeyError, OSError, TypeError, json.JSONDecodeError):
            expected = actual = ""
            stored_envelope, report = {}, None
        if (
            not envelope.is_file() or expected != actual
            or stored_envelope.get("request_hash") != run.request_hash
            or stored_envelope.get("config_hash") != self.store.get_config(run.config_id).config_hash
            or stored_envelope.get("artifact") != str(artifact)
            or stored_envelope.get("artifact_sha256") != expected
            or stored_envelope.get("summary") != result.get("summary")
            or not isinstance(report, dict)
            or report_summary(report) != result.get("summary")
        ):
            self._finish_after_verified_death(run_id, "FAILED", ["RESULT_ARTIFACT_HASH_MISMATCH"], result)
            return
        persisted_report = {**report, "request_hash": run.request_hash, "request_config_hash": self.store.get_config(run.config_id).config_hash, "artifact": str(artifact), "artifact_sha256": actual}
        self._finish_after_verified_death(run_id, "COMPLETED", ["NATIVE_RESEARCH_RESULT", str(report.get("status", "UNKNOWN"))], persisted_report)

    def refresh(self, run_id: str) -> "RunRecord":
        run = self.store.get_run(run_id)
        with self.lock:
            process = self.processes.get(run_id)
        if process and process.poll() is None and run.status == "RUNNING":
            return self.store.update_run(run_id, heartbeat_at=self._now())
        return run

    def cancel(self, run_id: str) -> "RunRecord":
        with self.lock:
            run = self.store.get_run(run_id)
            if run.status not in {"RUNNING", "STARTING", "CANCEL_REQUESTED"}:
                return self.store.cancel(run_id)
            process, owned = self.processes.get(run_id), self._owned_identity(run)
            if owned is None:
                if self._group_gone(run.process_group):
                    return self._finish_after_verified_death(run_id, "INTERRUPTED", [*run.evidence, "PROCESS_GROUP_CONFIRMED_GONE"])
                return self.store.update_run(run_id, status="CANCEL_REQUESTED", evidence=[*run.evidence, "CANCEL_CONFLICT_IDENTITY_UNVERIFIABLE_LEASE_HELD"], cancel_requested_at=self._now(), heartbeat_at=self._now())
            if run.status != "CANCEL_REQUESTED":
                self.store.update_run(run_id, status="CANCEL_REQUESTED", cancel_requested_at=self._now(), heartbeat_at=self._now())
            terminated = self._terminate_process(process) if process is not None else self._terminate_group(owned[1])
            if not terminated:
                return self.store.update_run(run_id, status="CANCEL_REQUESTED", evidence=[*self.store.get_run(run_id).evidence, "CANCEL_CONFLICT_TERMINATION_UNCONFIRMED_LEASE_HELD"], heartbeat_at=self._now())
            return self._finish_after_verified_death(run_id, "CANCELED", [*self.store.get_run(run_id).evidence, "CANCELED_OWNED_PROCESS_GROUP"])
