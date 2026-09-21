from __future__ import annotations

import subprocess
import sys
import threading
import time

from coinmaster.ops.paper import PaperRuntime
from coinmaster.ops.paper_worker import Worker, _log_startup
from coinmaster.ops.stage_g_config import InstanceConfig


class _Cache:
    def positions_open(self) -> list[object]: return []
    def orders_open(self) -> list[object]: return []


class _Feed:
    def due_funding(self, now_ns: int) -> tuple[()]: return ()


class _Native:
    feed = _Feed()
    class node:
        cache = _Cache()


def _flat_worker(path) -> Worker:
    worker = Worker.__new__(Worker)
    worker.runtime = PaperRuntime(path, "test-paper", int(1e9))
    worker.runtime.acquire()
    worker.native = _Native()
    worker.recovery_state = "FLAT_RESTART"
    worker.reconciled = True
    worker._poll_lock = threading.Lock()
    worker._poll_stop = threading.Event()
    worker._poll_thread = None
    worker.poll_interval_s = 0.01
    return worker


def test_autonomous_worker_poll_refreshes_snapshot_without_http(tmp_path) -> None:
    worker = _flat_worker(tmp_path / "paper.sqlite")
    worker.start_polling()
    time.sleep(0.06)  # No HTTP request is made during this observation.
    assert worker.runtime.health(time.time_ns()).warnings == ()
    worker.shutdown()


def test_process_crash_after_submit_before_ack_restarts_manage_only(tmp_path) -> None:
    """A real Sandbox lifecycle dies after partial BTC fill and SOL submit."""
    path = tmp_path / "paper.sqlite"
    child = (
        "import sys; from pathlib import Path; "
        "from coinmaster.ops.native_sandbox_selftest import run_crash_after_partial_fill; "
        "run_crash_after_partial_fill(Path(sys.argv[1]))"
    )
    result = subprocess.run([sys.executable, "-c", child, str(path)], check=False)
    assert result.returncode < 0
    restarted = PaperRuntime(path, "paper-crash-harness", 1_000_000_000)
    restarted.acquire()
    assert restarted.recovery_state() == "MANAGE_ONLY_PENDING_INTENT"
    assert not restarted.reconcile(positions=[], orders=[])
    restarted.heartbeat(2)
    assert not restarted.health(2).safe_for_increase
    snapshot = restarted.db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone()[0]
    assert '"signed_quantity": "0.6"' in snapshot
    pending = restarted.pending_submissions()
    assert pending[0]["episode_id"] == "native-btc-sol-crash-group"
    assert pending[0]["instrument_id"] == "SOLUSDT-LINEAR.BYBIT"
    assert [item["kind"] for item in restarted.events()] == ["fill", "fill"]
    restarted.close()


def test_startup_identity_and_hash_are_emitted_at_info_level(caplog, tmp_path) -> None:
    instance = InstanceConfig(
        instance_id="paper-stage-g", venue="BYBIT", mode="paper",
        strategy_config=tmp_path / "stage-g.json", state_db=tmp_path / "paper.sqlite",
        trader_id="COINMASTER-PAPER-G", strategy_id="stage-g-v1", order_id_tag="SG", path=tmp_path / "instance.json",
    )
    with caplog.at_level("INFO"):
        _log_startup(instance, "a" * 64)
    assert "instance_id=paper-stage-g venue=BYBIT mode=paper" in caplog.text
    assert "strategy_id=stage-g-v1 order_id_tag=SG" in caplog.text
    assert f"strategy_config_sha256={'a' * 64}" in caplog.text
