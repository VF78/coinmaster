"""Entrypoint for the isolated hl-stageg-testnet native Nautilus process."""
from __future__ import annotations

import json
import logging
import os
import signal
import time
from pathlib import Path

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
        # Optional, deliberately one-way handoff to the runtime sidecar.  The
        # sidecar cannot open this worker's SQLite journal or send it commands.
        projection_path = environment.get("COINMASTER_HL_STAGEG_PROJECTION_PATH")
        self.projection_path = Path(projection_path) if projection_path else None
        require_testnet_sandbox(environment)
        self.candidate = load_candidate(self.instance.strategy_config)
        self.runtime = PaperRuntime(self.instance.state_db, self.instance.instance_id, int(120e9))
        self.runtime.acquire()
        # Sandbox cache cannot be restored into a later process. Durable open
        # state therefore remains MANAGE_ONLY after restart without querying a
        # Hyperliquid account.
        durable_recovery = self.runtime.recovery_state()
        self.recovery_state = durable_recovery
        self.reconciled = durable_recovery == "FLAT_RESTART"
        self.native = HyperliquidTestnetNode(instance=self.instance, candidate=self.candidate.candidate, state=self.runtime)
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
        if getattr(self, "reconciled", self.runtime.recovery_state() == "FLAT_RESTART") and native is not None and native.node.is_running() and native.strategy is not None:
            positions, orders = self.native.sandbox_snapshot()
            self.runtime.snapshot(
                ts_ns=time.time_ns(), positions=positions, orders=orders,
                funding_event_ids=self.runtime.funding_event_ids(), reconciled=True,
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
            "safe_for_increase": health.safe_for_increase and self.native.gate.attachable,
            "warnings": list(dict.fromkeys((*health.warnings, self.recovery_state))),
            "orders_enabled": result["orders_enabled"],
        })
        self._publish_projection(result)
        return result

    def _publish_projection(self, status: dict) -> None:
        """Atomically publish only the bounded, safe UI read model.

        The status file has no commands, secrets, private paths, raw logs, or
        journal payloads.  An operator provisions a readable handoff path
        separately; a missing path cannot affect the trading node.
        """
        if self.projection_path is None:
            return
        gate = self.native.gate
        projection = {
            "version": "hl-stageg-projection-v1",
            "instance_id": "hl-stageg-testnet",
            "projection_state": "READY",
            "observed_at_ns": time.time_ns(),
            "mode": "sandbox",
            "environment": "mainnet-public",
            "live_order_capability": False,
            "process_state": status["state"],
            "reconciliation": status["reconciliation"],
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
            # Native Sandbox account values are only shown once a dedicated
            # verified projection field exists.  Do not turn missing money
            # into zero in this UI bridge.
            "account": {},
            "funding_state": gate.funding_state,
            "feeds": status["feeds"],
            "positions": [dict(item, provenance="SANDBOX") for item in self.runtime_snapshot()[0]],
            "orders": [dict(item, provenance="SANDBOX") for item in self.runtime_snapshot()[1]],
            "events": [dict(item, provenance="SANDBOX") for item in self.runtime.events(0, 100)],
            "event_cursor": max((item["cursor"] for item in self.runtime.events(0, 100)), default=0),
            "provenance": "SANDBOX_LOCAL_READ_ONLY_WORKER_PROJECTION",
            "warnings": list(dict.fromkeys(status["warnings"])),
        }
        try:
            self.projection_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.projection_path.with_name(f".{self.projection_path.name}.tmp")
            temporary.write_text(json.dumps(projection, sort_keys=True, separators=(",", ":")))
            temporary.chmod(0o640)
            temporary.replace(self.projection_path)
        except OSError as error:
            LOG.warning("hl sandbox projection unavailable: %s", type(error).__name__)

    def runtime_snapshot(self) -> tuple[list[dict], list[dict]]:
        """Expose durable state only through the bounded worker projection."""
        return self.runtime.projection_snapshot()

    def close(self) -> None:
        self.runtime.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    worker = TestnetWorker(); worker.start()
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
        while not stopped:
            LOG.info("hl testnet status=%s", json.dumps(worker.status(), sort_keys=True))
            time.sleep(5)
    finally:
        worker.close()


if __name__ == "__main__":
    main()
