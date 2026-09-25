"""Entrypoint for the isolated hl-stageg-testnet native Nautilus process."""
from __future__ import annotations

import json
import logging
import os
import signal
import time
import uuid
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import urlsplit

from coinmaster.ops.hyperliquid_testnet import HyperliquidTestnetNode, require_testnet_sandbox
from coinmaster.ops.paper import PaperRuntime
from coinmaster.ops.stage_g_config import ConfigurationError, load_candidate, load_testnet_instance_config


LOG = logging.getLogger(__name__)


class TestnetWorker:
    """One process / one node / one durable local Sandbox state DB."""
    def __init__(self, environment: dict[str, str] | None = None) -> None:
        environment = os.environ if environment is None else environment
        path = environment.get("COINMASTER_HL_TESTNET_INSTANCE_CONFIG")
        if not path:
            raise ConfigurationError("MISSING_HL_TESTNET_INSTANCE_CONFIG")
        self.instance = load_testnet_instance_config(Path(path))
        self.run_epoch = uuid.uuid4().hex
        require_testnet_sandbox(environment)
        self.candidate = load_candidate(self.instance.strategy_config)
        self.runtime = PaperRuntime(self.instance.state_db, self.instance.instance_id, int(120e9), require_native_cash=True)
        self.runtime.acquire()
        # Only a coherent flat predecessor can seed the next local Sandbox.
        # Open or uncertain native state stays frozen for explicit recovery.
        durable_recovery = self.runtime.recovery_state()
        self.recovery_state = durable_recovery
        self.reconciled = durable_recovery == "FLAT_RESTART"
        self.starting_cash = self.runtime.flat_native_cash() if self.reconciled else None
        self.native = HyperliquidTestnetNode(
            instance=self.instance, candidate=self.candidate.candidate, state=self.runtime,
            starting_cash=self.starting_cash if self.starting_cash is not None else Decimal("10000"),
        )
        self.native.prime()

    def start(self) -> None:
        self.native.start()

    def poll(self) -> None:
        # Sandbox is the only execution venue here, making its native cache
        # authoritative for this process only. A later process receives the
        # persisted open state and remains MANAGE_ONLY.
        native = getattr(self, "native", None)
        # A later process cannot inspect or restore the former process's
        # Sandbox cache. Never replace durable open/uncertain state with an
        # empty fresh cache: that would falsely manufacture FLAT_RESTART.
        if getattr(self, "reconciled", self.runtime.recovery_state() == "FLAT_RESTART") and native is not None and native.node.is_running() and native.strategy is not None and native._seed_verified:
            revision = self.runtime.native_revision()
            positions, orders = self.native.sandbox_snapshot()
            try:
                native_cash = self.native.native_account_total()
            except ValueError:
                self.runtime.heartbeat(time.time_ns())
                return
            self.runtime.snapshot(
                ts_ns=time.time_ns(), positions=positions, orders=orders,
                funding_event_ids=self.runtime.funding_event_ids(), reconciled=True,
                expected_revision=revision, native_account_total=str(native_cash),
                strategy_restartable=self.native.strategy_restartable(), run_epoch=self.run_epoch,
            )
        else:
            self.runtime.heartbeat(time.time_ns())

    def status(self) -> dict:
        self.poll()
        self.recovery_state = self.runtime.recovery_state()
        result = self.native.status()
        health = self.runtime.health(time.time_ns())
        result.update({
            "candidate_hash": self.candidate.sha256,
            "recovery_state": self.recovery_state,
            "reconciliation": "SANDBOX_LOCAL_PROCESS_RECONCILIATION_ONLY",
            "safe_for_increase": health.safe_for_increase and result["orders_enabled"],
            "recovery_required": self.recovery_state != "FLAT_RESTART",
            "recovery_capability": "NO_NATIVE_SANDBOX_REHYDRATION",
            "run_epoch": self.run_epoch,
            "virtual_capital_resets_on_flat_restart": False if self.starting_cash is not None else True,
            "sandbox_starting_cash_usdc": str(self.starting_cash) if self.starting_cash is not None else None,
            "native_thread_alive": bool(self.native._thread and self.native._thread.is_alive()),
            "warnings": list(dict.fromkeys((*health.warnings, self.recovery_state))),
            "orders_enabled": result["orders_enabled"],
        })
        return result

    def projection(self) -> dict[str, Any]:
        """Return a bounded, one-way read model with no command surface."""
        status = self.native.status()
        recovery_state = self.runtime.recovery_state()
        health = self.runtime.health(time.time_ns())
        gate = self.native.gate
        events, event_cursor = self.runtime.projection_events(100)
        account: dict[str, str] = {}
        account_warning: tuple[str, ...] = ()
        if recovery_state == "FLAT_RESTART" and self.native.node.is_running() and self.native.strategy is not None:
            positions, orders = self.native.sandbox_snapshot()
            # The local Sandbox ledger is authoritative only while this
            # process owns it. Project its actual USDC total as cash, but do
            # not manufacture equity, margin, PnL, fees, or fills from it.
            try:
                native_cash = self.native.native_account_total()
                if not native_cash.is_finite() or native_cash <= 0:
                    raise ValueError("INVALID_NATIVE_USDC_TOTAL")
                account = {"native_cash": str(native_cash)}
            except (ValueError, ArithmeticError):
                account_warning = ("NATIVE_SANDBOX_ACCOUNT_UNAVAILABLE",)
        else:
            positions, orders = self.runtime_snapshot()
        return {
            "version": "hl-stageg-projection-v1",
            "instance_id": "hl-stageg-testnet",
            "projection_state": "READY",
            "observed_at_ns": time.time_ns(),
            "mode": "sandbox",
            "environment": "mainnet-public",
            "live_order_capability": False,
            "run_epoch": self.run_epoch,
            "virtual_capital_resets_on_flat_restart": False if self.starting_cash is not None else True,
            "sandbox_starting_cash_usdc": str(self.starting_cash) if self.starting_cash is not None else None,
            "recovery_required": recovery_state != "FLAT_RESTART",
            "recovery_capability": "NO_NATIVE_SANDBOX_REHYDRATION",
            "native_thread_alive": bool(self.native._thread and self.native._thread.is_alive()),
            "process_state": status["state"],
            "reconciliation": "SANDBOX_LOCAL_PROCESS_RECONCILIATION_ONLY",
            "hashes": {
                "candidate_sha256": gate.candidate_hash,
                "strategy_sha256": gate.strategy_code_hash,
                "execution_policy_sha256": gate.execution_policy_hash,
            },
            "warmup": status["warmup"],
            "gates": {
                "attachable": gate.attachable,
                "approval_state": gate.approval_state,
                "margin_policy_state": gate.margin_policy_state,
                "execution_policy_state": gate.execution_policy_state,
                "capital_state": gate.capital_state,
            },
            "account": account,
            "funding_state": gate.funding_state,
            "feeds": status["feeds"],
            "positions": [dict(item, provenance="SANDBOX") for item in positions],
            "orders": [dict(item, provenance="SANDBOX") for item in orders],
            "events": [dict(item, provenance="SANDBOX") for item in events],
            "event_cursor": event_cursor,
            "provenance": "SANDBOX_LOCAL_READ_ONLY_WORKER_PROJECTION",
            "warnings": list(dict.fromkeys((*health.warnings, *account_warning, recovery_state))),
        }

    def runtime_snapshot(self) -> tuple[list[dict], list[dict]]:
        """Expose durable state only through the bounded worker projection."""
        return self.runtime.projection_snapshot()

    def flat_quiescent(self) -> bool:
        if self.runtime.recovery_state() != "FLAT_RESTART" or not self.runtime.coherent_snapshot():
            return False
        if self.runtime.pending_submissions() or self.runtime.pending_native_funding():
            return False
        durable_positions, durable_orders = self.runtime.projection_snapshot()
        native_positions, native_orders = self.native.sandbox_snapshot()
        if durable_positions or durable_orders or native_positions or native_orders:
            return False
        if not self.native.strategy_restartable():
            return False
        try:
            cash = self.native.native_account_total()
        except ValueError:
            return False
        return cash.is_finite() and cash > 0

    def close(self) -> None:
        stopped = self.native.stop()
        if stopped and self.reconciled and self.native.strategy is not None:
            revision = self.runtime.native_revision()
            positions, orders = self.native.sandbox_snapshot()
            try:
                native_cash = self.native.native_account_total()
            except ValueError:
                self.runtime.heartbeat(time.time_ns())
            else:
                self.runtime.snapshot(
                    ts_ns=time.time_ns(), positions=positions, orders=orders,
                    funding_event_ids=self.runtime.funding_event_ids(), reconciled=True,
                    expected_revision=revision, native_account_total=str(native_cash),
                    strategy_restartable=self.native.strategy_restartable(), run_epoch=self.run_epoch,
                )
        elif not stopped:
            self.runtime.heartbeat(time.time_ns())
        if stopped:
            self.runtime.close()


def create_status_server(worker: TestnetWorker, port: int = 18183) -> ThreadingHTTPServer:
    """Expose GET /status on IPv4 loopback only; mutation methods are 405."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if urlsplit(self.path).path != "/status":
                self.send_error(404)
                return
            try:
                payload = json.dumps(worker.projection(), sort_keys=True, separators=(",", ":")).encode()
            except Exception as error:
                LOG.warning("hl sandbox status projection failed: %s", type(error).__name__)
                self.send_error(503)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self) -> None: self.send_error(405)
        def do_PUT(self) -> None: self.send_error(405)
        def do_DELETE(self) -> None: self.send_error(405)
        def log_message(self, _format: str, *args: Any) -> None: return

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    worker = TestnetWorker(); worker.start()
    status_port = int(os.getenv("COINMASTER_HL_STAGEG_STATUS_PORT", "18183"))
    try:
        status_server = create_status_server(worker, status_port) if status_port > 0 else None
    except OSError as error:
        # An observability bind conflict must not prevent the isolated trader
        # from running; the sidecar will show UNAVAILABLE until it is fixed.
        LOG.error("hl sandbox read-only status listener unavailable: %s", type(error).__name__)
        status_server = None
    status_thread = Thread(target=status_server.serve_forever, name="hl-stageg-readonly-status", daemon=True) if status_server else None
    if status_thread is not None:
        status_thread.start()
    LOG.info(
        "hl sandbox startup instance_id=%s environment=mainnet-public strategy_id=%s candidate_sha256=%s orders_enabled=%s",
        worker.instance.instance_id, worker.instance.strategy_id, worker.candidate.sha256,
        worker.native.status()["orders_enabled"],
    )
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    try:
        ready_once = False
        stale_since_ns: int | None = None
        while not stopped:
            status = worker.status()
            LOG.info("hl testnet status=%s", json.dumps(status, sort_keys=True))
            if status["state"] == "PUBLIC_FEEDS_READY":
                ready_once = True
                stale_since_ns = None
            elif ready_once and stale_since_ns is None:
                stale_since_ns = time.time_ns()
            thread_failed = worker.native._thread is not None and not worker.native._thread.is_alive()
            prolonged_stale = stale_since_ns is not None and time.time_ns() - stale_since_ns > 900_000_000_000
            if (thread_failed or prolonged_stale or worker.native.prime_error is not None) and worker.flat_quiescent():
                raise RuntimeError("STAGEG_FLAT_WORKER_RESTART_REQUIRED")
            time.sleep(5)
    finally:
        if status_server is not None:
            status_server.shutdown()
            status_server.server_close()
        worker.close()


if __name__ == "__main__":
    main()
