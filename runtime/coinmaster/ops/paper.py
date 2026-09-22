"""Fail-closed durable control plane for the local native paper worker.

This owns paper intent state only; it never loads credentials or creates live
adapters/orders. A separate native worker may read the durable snapshots.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from functools import wraps
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


def _journal_locked(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapped


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
        self._lock = threading.RLock()
        self._local_sandbox_active = False
        self.db, self.owner, self.max_data_age_ns = sqlite3.connect(database, check_same_thread=False), owner, max_data_age_ns
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_lock (id INTEGER PRIMARY KEY CHECK(id=1), owner TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_commands (idempotency_key TEXT PRIMARY KEY, command TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_command_audit (idempotency_key TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL, ts_ns INTEGER NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_events (event_id TEXT PRIMARY KEY, kind TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_snapshot (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)")
        # A native Sandbox cache is process-local.  Persist the intent before
        # submit so a crash between submit and its ACK cannot look flat after
        # restart.  We deliberately do not attempt an unsupported cache/group
        # reconstruction: pending work moves the worker to MANAGE_ONLY.
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_intents (client_order_id TEXT PRIMARY KEY, intent_id TEXT NOT NULL, episode_id TEXT NOT NULL, action TEXT NOT NULL, instrument_id TEXT NOT NULL, state TEXT NOT NULL, body TEXT NOT NULL)")
        # Legacy diagnostic ledger. It is never a substitute for a native
        # Sandbox account posting.
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_funding_ledger (event_id TEXT PRIMARY KEY, instrument_id TEXT NOT NULL, settlement_ns INTEGER NOT NULL, rate TEXT NOT NULL, mark TEXT NOT NULL, cash_delta TEXT NOT NULL, state TEXT NOT NULL)")
        # A native Sandbox account adjustment cannot share SQLite's
        # transaction. Persist PREPARED before the native call; a crash in
        # that window is deliberately MANAGE_ONLY rather than risking a
        # duplicate funding post after restart.
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_native_funding (event_id TEXT PRIMARY KEY, instrument_id TEXT NOT NULL, settlement_ns INTEGER NOT NULL, rate TEXT NOT NULL, mark TEXT NOT NULL, cash_delta TEXT NOT NULL, state TEXT NOT NULL)")
        self.db.commit()

    @_journal_locked
    def acquire(self) -> None:
        try:
            self.db.execute("INSERT INTO paper_lock VALUES (1, ?)", (self.owner,)); self.db.commit()
        except sqlite3.IntegrityError as error:
            row = self.db.execute("SELECT owner FROM paper_lock WHERE id=1").fetchone()
            if row and row[0] == self.owner:
                return  # Controlled restart of the same paper owner.
            raise RuntimeError("PAPER_OWNER_LOCKED") from error

    @_journal_locked
    def command(self, command: str, idempotency_key: str) -> bool:
        if command not in {"pause-new-entries", "resume-new-entries", "flatten-paper"}:
            raise ValueError("unsupported paper command")
        try:
            self.db.execute("INSERT INTO paper_commands VALUES (?, ?)", (idempotency_key, command))
            self.db.execute("INSERT INTO paper_command_audit VALUES (?, ?, ?, strftime('%s','now') * 1000000000)", (idempotency_key, command, "ACCEPTED"))
            self.db.commit(); return True
        except sqlite3.IntegrityError:
            return False

    @_journal_locked
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

    @_journal_locked
    def record_submission(self, *, client_order_id: str, intent_id: str, episode_id: str, action: str, instrument_id: str, quantity: str, reduce_only: bool) -> bool:
        """Durably mark a native submit before handing it to Nautilus.

        ``SUBMITTING`` is intentionally uncertain until a terminal callback;
        it therefore survives a crash-before-ACK as a recovery gate.
        """
        body = json.dumps({"quantity": quantity, "reduce_only": reduce_only}, sort_keys=True)
        try:
            self.db.execute(
                "INSERT INTO paper_intents VALUES (?, ?, ?, ?, ?, 'SUBMITTING', ?)",
                (client_order_id, intent_id, episode_id, action, instrument_id, body),
            )
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    @_journal_locked
    def acknowledge_submission(self, client_order_id: str) -> None:
        self.db.execute("UPDATE paper_intents SET state='ACKED' WHERE client_order_id=? AND state='SUBMITTING'", (client_order_id,))
        self.db.commit()

    @_journal_locked
    def terminal_submission(self, client_order_id: str) -> None:
        self.db.execute("UPDATE paper_intents SET state='TERMINAL' WHERE client_order_id=?", (client_order_id,))
        self.db.commit()

    @_journal_locked
    def pending_submissions(self) -> list[dict]:
        return [
            {"client_order_id": row[0], "intent_id": row[1], "episode_id": row[2], "action": row[3], "instrument_id": row[4], "state": row[5], "body": json.loads(row[6])}
            for row in self.db.execute("SELECT client_order_id,intent_id,episode_id,action,instrument_id,state,body FROM paper_intents WHERE state != 'TERMINAL' ORDER BY client_order_id")
        ]

    @_journal_locked
    def recovery_state(self) -> str:
        """Return the only supported restart contract for durable exposure."""
        row = self.db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone()
        snapshot = json.loads(row[0]) if row else None
        if self.pending_submissions():
            return "MANAGE_ONLY_PENDING_INTENT"
        if self.pending_native_funding():
            return "MANAGE_ONLY_PENDING_NATIVE_FUNDING"
        if snapshot and (snapshot.get("positions") or snapshot.get("orders")) and not self._local_sandbox_active:
            return "MANAGE_ONLY_DURABLE_OPEN_STATE"
        return "FLAT_RESTART"

    @staticmethod
    def funding_cash_delta(signed_quantity: Decimal, settlement_mark: Decimal, rate: Decimal) -> Decimal:
        """Positive Bybit funding means longs pay and shorts receive."""
        return -(signed_quantity * settlement_mark * rate)

    @_journal_locked
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

    @_journal_locked
    def prepare_native_funding(self, *, event_id: str, instrument_id: str, settlement_ns: int, rate: Decimal, mark: Decimal, signed_quantity: Decimal) -> tuple[bool, Decimal]:
        """Durably reserve exactly one native funding adjustment."""
        delta = self.funding_cash_delta(signed_quantity, mark, rate)
        try:
            self.db.execute(
                "INSERT INTO paper_native_funding VALUES (?, ?, ?, ?, ?, ?, 'PREPARED')",
                (event_id, instrument_id, settlement_ns, str(rate), str(mark), str(delta)),
            )
            self.db.commit()
            return True, delta
        except sqlite3.IntegrityError:
            return False, delta

    @_journal_locked
    def complete_native_funding(self, event_id: str) -> None:
        self.db.execute("UPDATE paper_native_funding SET state='POSTED' WHERE event_id=? AND state='PREPARED'", (event_id,))
        self.db.execute("INSERT OR IGNORE INTO paper_events VALUES (?, 'funding')", (event_id,))
        self.db.commit()

    @_journal_locked
    def pending_native_funding(self) -> list[str]:
        return [row[0] for row in self.db.execute("SELECT event_id FROM paper_native_funding WHERE state='PREPARED' ORDER BY event_id")]

    @_journal_locked
    def reconcile(self, *, positions: list[dict], orders: list[dict]) -> bool:
        """Only a documented flat restart can be reconciled automatically."""
        if self.recovery_state() != "FLAT_RESTART":
            return False
        row = self.db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone()
        if row is None:
            return True  # Default paper start is explicitly flat.
        previous = json.loads(row[0])
        return previous.get("positions", []) == positions and previous.get("orders", []) == orders

    @_journal_locked
    def funding_event_ids(self) -> list[str]:
        return [row[0] for row in self.db.execute("SELECT event_id FROM paper_funding_ledger ORDER BY event_id")]

    @_journal_locked
    def snapshot(self, *, ts_ns: int, positions: list[dict], orders: list[dict], funding_event_ids: list[str], reconciled: bool = True) -> None:
        body = {"ts_ns": ts_ns, "positions": positions, "orders": orders, "funding_event_ids": funding_event_ids, "reconciled": reconciled}
        self.db.execute("INSERT OR REPLACE INTO paper_snapshot VALUES (1, ?)", (json.dumps(body, sort_keys=True),)); self.db.commit()
        if reconciled:
            self._local_sandbox_active = True

    @_journal_locked
    def heartbeat(self, ts_ns: int) -> None:
        """Refresh liveness without replacing uncertain durable exposure."""
        row = self.db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone()
        if row is None:
            return
        body = json.loads(row[0]); body["ts_ns"] = ts_ns; body["reconciled"] = False
        self.db.execute("UPDATE paper_snapshot SET body=? WHERE id=1", (json.dumps(body, sort_keys=True),)); self.db.commit()

    @_journal_locked
    def health(self, now_ns: int) -> PaperHealth:
        row = self.db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone()
        snapshot = json.loads(row[0]) if row else None
        commands = {row[0] for row in self.db.execute("SELECT command FROM paper_commands")}
        latest_entry_control = self.db.execute("SELECT command FROM paper_command_audit WHERE command IN ('pause-new-entries', 'resume-new-entries') ORDER BY ts_ns DESC, rowid DESC LIMIT 1").fetchone()
        paused = latest_entry_control[0] == "pause-new-entries" if latest_entry_control else "pause-new-entries" in commands
        warnings: list[str] = []
        if snapshot is None: warnings.append("MISSING_SNAPSHOT")
        elif now_ns - snapshot["ts_ns"] > self.max_data_age_ns: warnings.append("STALE_DATA")
        recovery = self.recovery_state()
        if recovery != "FLAT_RESTART": warnings.append(recovery)
        if snapshot and not snapshot.get("reconciled", False): warnings.append("SANDBOX_RECONCILIATION_MISMATCH")
        if snapshot and snapshot["orders"]: warnings.append("UNRECONCILED_ORDERS")
        return PaperHealth(self.owner, paused, "flatten-paper" in commands, not warnings and not paused, tuple(warnings))

    @_journal_locked
    def events(self, cursor: int = 0, limit: int = 100) -> list[dict]:
        return [{"cursor": row[0], "event_id": row[1], "kind": row[2]} for row in self.db.execute("SELECT rowid, event_id, kind FROM paper_events WHERE rowid > ? ORDER BY rowid LIMIT ?", (cursor, limit))]

    @_journal_locked
    def close(self) -> None: self.db.close()
