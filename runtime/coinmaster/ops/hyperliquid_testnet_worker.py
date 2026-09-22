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
    """One process / one node / one durable state DB, with no order activation."""
    def __init__(self, environment: dict[str, str] | None = None) -> None:
        environment = os.environ if environment is None else environment
        path = environment.get("COINMASTER_HL_TESTNET_INSTANCE_CONFIG")
        if not path:
            raise ConfigurationError("MISSING_HL_TESTNET_INSTANCE_CONFIG")
        self.instance = load_testnet_instance_config(Path(path))
        require_testnet_sandbox(environment)
        self.candidate = load_candidate(self.instance.strategy_config)
        self.runtime = PaperRuntime(self.instance.state_db, self.instance.instance_id, int(120e9))
        self.runtime.acquire()
        # Local absence is never remote-flat evidence. A prior durable open
        # state remains MANAGE_ONLY; a locally flat DB is still UNVERIFIED
        # until a separately authorized native account/order reconciliation
        # records authenticated evidence.
        durable_recovery = self.runtime.recovery_state()
        self.recovery_state = durable_recovery if durable_recovery != "FLAT_RESTART" else "UNVERIFIED_REMOTE_STATE"
        self.reconciled = False
        self.native = HyperliquidTestnetNode(instance=self.instance, candidate=self.candidate.candidate, state=self.runtime)
        self.native.prime()

    def start(self) -> None:
        self.native.start()

    def poll(self) -> None:
        # Do not snapshot a local Sandbox cache as exchange reconciliation
        # proof. It is a local model, not a Hyperliquid account report.
        self.runtime.heartbeat(time.time_ns())

    def status(self) -> dict:
        self.poll()
        result = self.native.status()
        health = self.runtime.health(time.time_ns())
        result.update({
            "candidate_hash": self.candidate.sha256,
            "recovery_state": self.recovery_state,
            "reconciliation": "SANDBOX_NO_REMOTE_RECONCILIATION",
            "safe_for_increase": False,
            "warnings": list(dict.fromkeys((*health.warnings, self.recovery_state))),
            "orders_enabled": False,
        })
        return result

    def close(self) -> None:
        self.runtime.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    worker = TestnetWorker(); worker.start()
    LOG.info(
        "hl testnet startup instance_id=%s environment=testnet strategy_id=%s candidate_sha256=%s orders_enabled=false",
        worker.instance.instance_id, worker.instance.strategy_id, worker.candidate.sha256,
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
