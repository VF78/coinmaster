from __future__ import annotations

import subprocess
import sys
import threading
import time

from coinmaster.ops.paper import PaperRuntime
from coinmaster.ops.paper_worker import Worker


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
    """A real child process dies after durable submit evidence, before ACK."""
    path = tmp_path / "paper.sqlite"
    child = (
        "import os,signal,sys; from pathlib import Path; "
        "from coinmaster.ops.paper import PaperRuntime; "
        "r=PaperRuntime(Path(sys.argv[1]), 'paper', 1000000000); r.acquire(); "
        "r.snapshot(ts_ns=1, positions=[{'instrument_id':'BTCUSDT-LINEAR.BYBIT','signed_quantity':'1.000'}], "
        "orders=[{'client_order_id':'sandbox-sol-pending'}], funding_event_ids=[]); "
        "r.record_submission(client_order_id='sandbox-sol-pending', intent_id='sol-add', episode_id='btc-sol-group', "
        "action='SOL_ADD', instrument_id='SOLUSDT-LINEAR.BYBIT', quantity='10.0', reduce_only=False); "
        "os.kill(os.getpid(), signal.SIGKILL)"
    )
    result = subprocess.run([sys.executable, "-c", child, str(path)], check=False)
    assert result.returncode < 0
    restarted = PaperRuntime(path, "paper", 1_000_000_000)
    restarted.acquire()
    assert restarted.recovery_state() == "MANAGE_ONLY_PENDING_INTENT"
    assert not restarted.reconcile(positions=[], orders=[])
    restarted.heartbeat(2)
    assert not restarted.health(2).safe_for_increase
    assert restarted.pending_submissions()[0]["episode_id"] == "btc-sol-group"
    restarted.close()
