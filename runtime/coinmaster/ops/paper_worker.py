"""Paper-only loopback worker backed by one native Nautilus TradingNode."""
from __future__ import annotations

import json, os, signal, threading, time
from decimal import Decimal
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
        self.mode = "paper"
        manifest = Path(os.environ.get("COINMASTER_PAPER_HISTORY_MANIFEST", "var/data/paper-warmup-manifest.json"))
        self.native = NativePaperNode(
            manifest,
            native_event_sink=self.runtime.record_native_event,
            entries_gate=lambda: self.runtime.health(time.time_ns()).safe_for_increase,
            strategy_name=os.environ.get("COINMASTER_PAPER_STRATEGY_CONFIG", "corrected-v0"),
        )
        self.native.prime()
        self.reconciled = self.runtime.reconcile(positions=[], orders=[])
        self.native.start()

    def _positions(self) -> list[dict]:
        result = []
        for item in self.native.node.cache.positions_open():
            quantity = item.quantity.as_decimal()
            result.append({"instrument_id": str(item.instrument_id), "signed_quantity": str(quantity if item.is_long else -quantity)})
        return sorted(result, key=lambda item: item["instrument_id"])

    def _orders(self) -> list[dict]:
        return sorted(({"client_order_id": str(item.client_order_id)} for item in self.native.node.cache.orders_open()), key=lambda item: item["client_order_id"])

    def poll(self) -> None:
        status = self.native.status()
        now_ns = time.time_ns()
        positions, orders = self._positions(), self._orders()
        position_by_id = {item["instrument_id"]: item for item in positions}
        # The pinned live SandboxExecutionClient has no supported account cash
        # adjustment method.  Funding is therefore an explicitly labelled
        # model ledger, never a rate-receipt or native cash posting.
        for event in self.native.feed.due_funding(now_ns):
            position = position_by_id.get(event["instrument_id"])
            signed_quantity = Decimal(position["signed_quantity"]) if position else Decimal("0")
            self.runtime.record_modelled_funding(
                event_id=event["event_id"], instrument_id=event["instrument_id"], settlement_ns=event["settlement_ns"],
                rate=event["rate"], mark=event["mark"], signed_quantity=signed_quantity,
            )
        self.runtime.snapshot(ts_ns=now_ns, positions=positions, orders=orders, funding_event_ids=self.runtime.funding_event_ids(), reconciled=self.reconciled)

    def status(self) -> dict:
        health = self.runtime.health(time.time_ns())
        native = self.native.status()
        native.update({
            "mode": "paper",
            "safe_for_increase": health.safe_for_increase and native["state"] == "READY",
            "warnings": health.warnings,
            "reconciliation": "RECONCILED" if self.reconciled else "SANDBOX_STATE_MISMATCH",
            "funding_posting_state": "MODELLED_LEDGER_UNPOSTED_NO_SUPPORTED_SANDBOX_CASH_ADJUSTMENT",
            "funding_ledger_event_ids": self.runtime.funding_event_ids(),
        })
        return native

    def command(self, command: str, idempotency_key: str) -> dict:
        if self.mode != "paper":
            raise RuntimeError("PAPER_WORKER_REFUSES_NON_PAPER_MODE")
        execution_clients = self.native.status().get("execution_client_classes", [])
        if execution_clients != ["SandboxExecutionClient"]:
            raise RuntimeError("PAPER_WORKER_REFUSES_NON_SANDBOX_EXECUTION")
        accepted = self.runtime.command(command, idempotency_key)
        # Flatten is deliberately a no-op when flat.  It is issued only by the
        # worker to its existing native Sandbox strategy; no UI process can
        # construct an order or execution client.
        if command == "flatten-paper" and self._positions() and self.native.strategy is not None:
            self.native.strategy._submit_terminal_closes()
        return {"command": command, "idempotency_key": idempotency_key, "status": "ACCEPTED" if accepted else "DUPLICATE", "mode": "paper"}


def main() -> None:
    worker = Worker(); worker.poll()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in {"/health", "/status"}: self.send_error(404); return
            worker.poll(); body = json.dumps(worker.status()).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
        def do_POST(self):
            if self.path != "/commands": self.send_error(404); return
            expected = os.environ.get("COINMASTER_PAPER_CONTROL_TOKEN")
            if not expected or self.headers.get("Authorization") != f"Bearer {expected}": self.send_error(401); return
            key = self.headers.get("Idempotency-Key")
            if not key: self.send_error(422, "Idempotency-Key is required"); return
            try:
                length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length))
                result = worker.command(payload["command"], key)
            except (KeyError, ValueError, json.JSONDecodeError) as error: self.send_error(422, str(error)); return
            body = json.dumps(result).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
        def log_message(self, *_): pass
    server = HTTPServer((os.environ.get("COINMASTER_PAPER_HOST", "127.0.0.1"), int(os.environ.get("COINMASTER_PAPER_PORT", "18181"))), Handler)
    def stop(*_): threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    server.serve_forever(); server.server_close()

if __name__ == "__main__": main()
