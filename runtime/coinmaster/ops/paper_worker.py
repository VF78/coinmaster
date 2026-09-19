"""Paper-only loopback worker backed by one native Nautilus TradingNode."""
from __future__ import annotations

import json, os, time
from http.server import BaseHTTPRequestHandler, HTTPServer

from coinmaster.ops.paper import PaperRuntime
from coinmaster.ops.native_paper_node import NativePaperNode


class Worker:
    def __init__(self) -> None:
        if os.getenv("COINMASTER_LIVE_ENABLED", "false").lower() != "false":
            raise RuntimeError("PAPER_WORKER_REFUSES_LIVE_ENABLED")
        from pathlib import Path

        self.runtime = PaperRuntime(Path(os.environ.get("COINMASTER_PAPER_DB", "var/paper/paper.sqlite")), os.environ.get("COINMASTER_PAPER_OWNER", "coinmaster-paper"), int(120e9))
        self.runtime.acquire()
        manifest = Path(os.environ.get("COINMASTER_PAPER_HISTORY_MANIFEST", "var/data/paper-warmup-manifest.json"))
        self.native = NativePaperNode(manifest, native_event_sink=self.runtime.record_native_event)
        self.native.prime()
        self.native.start()

    def poll(self) -> None:
        status = self.native.status()
        positions = [str(item) for item in self.native.node.cache.positions_open()]
        orders = [str(item) for item in self.native.node.cache.orders_open()]
        # A next funding time/rate is observation evidence, not a posting.  Do
        # not record it as funded until a confirmed settlement mark is applied
        # through the durable native funding journal.
        self.runtime.snapshot(ts_ns=time.time_ns(), positions=positions, orders=orders, funding_event_ids=[])

    def status(self) -> dict:
        health = self.runtime.health(time.time_ns())
        native = self.native.status()
        native.update({"mode": "paper", "safe_for_increase": health.safe_for_increase and native["state"] == "READY", "warnings": health.warnings})
        return native


def main() -> None:
    worker = Worker(); worker.poll()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in {"/health", "/status"}: self.send_error(404); return
            worker.poll(); body = json.dumps(worker.status()).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
        def log_message(self, *_): pass
    HTTPServer((os.environ.get("COINMASTER_PAPER_HOST", "127.0.0.1"), int(os.environ.get("COINMASTER_PAPER_PORT", "18181"))), Handler).serve_forever()

if __name__ == "__main__": main()
