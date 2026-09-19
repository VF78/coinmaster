"""Paper-only loopback worker; it has no private exchange or order transport."""
from __future__ import annotations

import json, os, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.request import urlopen

from coinmaster.ops.paper import PaperRuntime


class Worker:
    def __init__(self) -> None:
        if os.getenv("COINMASTER_LIVE_ENABLED", "false").lower() != "false":
            raise RuntimeError("PAPER_WORKER_REFUSES_LIVE_ENABLED")
        self.runtime = PaperRuntime(Path(os.environ.get("COINMASTER_PAPER_DB", "var/paper/paper.sqlite")), os.environ.get("COINMASTER_PAPER_OWNER", "coinmaster-paper"), int(120e9))
        self.runtime.acquire(); self.marks: dict[str, str] = {}; self.last_ns = 0; self.error: str | None = None

    def poll(self) -> None:
        try:
            url = "https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT"
            with urlopen(url, timeout=10) as response: payload = json.load(response)
            item = payload["result"]["list"][0]; self.marks["BTCUSDT"] = item["markPrice"]
            self.last_ns, self.error = time.time_ns(), None
            self.runtime.snapshot(ts_ns=self.last_ns, positions=[], orders=[], funding_event_ids=[])
        except Exception as error: self.error = type(error).__name__

    def status(self) -> dict:
        health = self.runtime.health(time.time_ns())
        return {"mode": "paper", "live_order_capability": False, "venue": "bybit_public_only", "marks": self.marks, "last_data_ns": self.last_ns, "error": self.error, "safe_for_increase": health.safe_for_increase, "warnings": health.warnings}


def main() -> None:
    worker = Worker(); worker.poll()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in {"/health", "/status"}: self.send_error(404); return
            worker.poll(); body = json.dumps(worker.status()).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
        def log_message(self, *_): pass
    HTTPServer((os.environ.get("COINMASTER_PAPER_HOST", "127.0.0.1"), int(os.environ.get("COINMASTER_PAPER_PORT", "18181"))), Handler).serve_forever()

if __name__ == "__main__": main()
