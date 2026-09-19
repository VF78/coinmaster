"""Fail-closed durable control plane for the local native paper worker.

This owns paper intent state only; it never loads credentials or creates live
adapters/orders. A separate native worker may read the durable snapshots.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class PaperHealth:
    owner: str | None
    paused_new_entries: bool
    flatten_requested: bool
    safe_for_increase: bool
    warnings: tuple[str, ...]


class PaperRuntime:
    def __init__(self, database: Path, owner: str, max_data_age_ns: int) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self.db, self.owner, self.max_data_age_ns = sqlite3.connect(database), owner, max_data_age_ns
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_lock (id INTEGER PRIMARY KEY CHECK(id=1), owner TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_commands (idempotency_key TEXT PRIMARY KEY, command TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_command_audit (idempotency_key TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL, ts_ns INTEGER NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_events (event_id TEXT PRIMARY KEY, kind TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_snapshot (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)")
        # SandboxExecutionClient exposes no supported live-account cash
        # adjustment API in Nautilus 1.231.  Funding is therefore recorded in
        # this separate, explicitly modelled/reconciled ledger and never
        # presented as sandbox account cash.
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_funding_ledger (event_id TEXT PRIMARY KEY, instrument_id TEXT NOT NULL, settlement_ns INTEGER NOT NULL, rate TEXT NOT NULL, mark TEXT NOT NULL, cash_delta TEXT NOT NULL, state TEXT NOT NULL)")
        self.db.commit()

    def acquire(self) -> None:
        try:
            self.db.execute("INSERT INTO paper_lock VALUES (1, ?)", (self.owner,)); self.db.commit()
        except sqlite3.IntegrityError as error:
            row = self.db.execute("SELECT owner FROM paper_lock WHERE id=1").fetchone()
            if row and row[0] == self.owner:
                return  # Controlled restart of the same paper owner.
            raise RuntimeError("PAPER_OWNER_LOCKED") from error

    def command(self, command: str, idempotency_key: str) -> bool:
        if command not in {"pause-new-entries", "resume-new-entries", "flatten-paper"}:
            raise ValueError("unsupported paper command")
        try:
            self.db.execute("INSERT INTO paper_commands VALUES (?, ?)", (idempotency_key, command))
            self.db.execute("INSERT INTO paper_command_audit VALUES (?, ?, ?, strftime('%s','now') * 1000000000)", (idempotency_key, command, "ACCEPTED"))
            self.db.commit(); return True
        except sqlite3.IntegrityError:
            return False

    def record_native_event(self, event_id: str, kind: str) -> bool:
        """Durably de-duplicate native order/fill/funding event identities.

        This is an audit/restart guard only.  It never creates an order, fill,
        funding posting, account balance, or synthetic execution event.
        """
        if kind not in {"order", "fill", "funding", "account", "position"}:
            raise ValueError("unsupported native event kind")
        try:
            self.db.execute("INSERT INTO paper_events VALUES (?, ?)", (event_id, kind))
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def funding_cash_delta(signed_quantity: Decimal, settlement_mark: Decimal, rate: Decimal) -> Decimal:
        """Positive Bybit funding means longs pay and shorts receive."""
        return -(signed_quantity * settlement_mark * rate)

    def record_modelled_funding(self, *, event_id: str, instrument_id: str, settlement_ns: int, rate: Decimal, mark: Decimal, signed_quantity: Decimal) -> bool:
        """Atomically de-duplicate one normalized venue settlement in the model ledger."""
        delta = self.funding_cash_delta(signed_quantity, mark, rate)
        try:
            self.db.execute(
                "INSERT INTO paper_funding_ledger VALUES (?, ?, ?, ?, ?, ?, ?)",
                (event_id, instrument_id, settlement_ns, str(rate), str(mark), str(delta), "MODELLED_LEDGER_UNPOSTED"),
            )
            self.db.execute("INSERT INTO paper_events VALUES (?, ?)", (event_id, "funding"))
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            self.db.rollback()
            return False

    def reconcile(self, *, positions: list[dict], orders: list[dict]) -> bool:
        """A restored non-flat snapshot must match the fresh sandbox state."""
        row = self.db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone()
        if row is None:
            return True  # Default paper start is explicitly flat.
        previous = json.loads(row[0])
        return previous.get("positions", []) == positions and previous.get("orders", []) == orders

    def funding_event_ids(self) -> list[str]:
        return [row[0] for row in self.db.execute("SELECT event_id FROM paper_funding_ledger ORDER BY event_id")]

    def snapshot(self, *, ts_ns: int, positions: list[dict], orders: list[dict], funding_event_ids: list[str], reconciled: bool = True) -> None:
        body = {"ts_ns": ts_ns, "positions": positions, "orders": orders, "funding_event_ids": funding_event_ids, "reconciled": reconciled}
        self.db.execute("INSERT OR REPLACE INTO paper_snapshot VALUES (1, ?)", (json.dumps(body, sort_keys=True),)); self.db.commit()

    def health(self, now_ns: int) -> PaperHealth:
        row = self.db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone()
        snapshot = json.loads(row[0]) if row else None
        commands = {row[0] for row in self.db.execute("SELECT command FROM paper_commands")}
        latest_entry_control = self.db.execute("SELECT command FROM paper_command_audit WHERE command IN ('pause-new-entries', 'resume-new-entries') ORDER BY ts_ns DESC, rowid DESC LIMIT 1").fetchone()
        paused = latest_entry_control[0] == "pause-new-entries" if latest_entry_control else "pause-new-entries" in commands
        warnings: list[str] = []
        if snapshot is None: warnings.append("MISSING_SNAPSHOT")
        elif now_ns - snapshot["ts_ns"] > self.max_data_age_ns: warnings.append("STALE_DATA")
        if snapshot and not snapshot.get("reconciled", False): warnings.append("SANDBOX_RECONCILIATION_MISMATCH")
        if snapshot and snapshot["orders"]: warnings.append("UNRECONCILED_ORDERS")
        return PaperHealth(self.owner, paused, "flatten-paper" in commands, not warnings and not paused, tuple(warnings))

    def events(self, cursor: int = 0, limit: int = 100) -> list[dict]:
        return [{"cursor": row[0], "event_id": row[1], "kind": row[2]} for row in self.db.execute("SELECT rowid, event_id, kind FROM paper_events WHERE rowid > ? ORDER BY rowid LIMIT ?", (cursor, limit))]

    def close(self) -> None: self.db.close()
