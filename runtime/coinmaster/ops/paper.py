"""Fail-closed durable control plane for the local native paper worker.

This owns paper intent state only; it never loads credentials or creates live
adapters/orders. A separate native worker may read the durable snapshots.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
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
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_snapshot (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)")
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
        if command not in {"pause-new-entries", "flatten"}:
            raise ValueError("unsupported paper command")
        try:
            self.db.execute("INSERT INTO paper_commands VALUES (?, ?)", (idempotency_key, command)); self.db.commit(); return True
        except sqlite3.IntegrityError:
            return False

    def snapshot(self, *, ts_ns: int, positions: list[dict], orders: list[dict], funding_event_ids: list[str]) -> None:
        body = {"ts_ns": ts_ns, "positions": positions, "orders": orders, "funding_event_ids": funding_event_ids}
        self.db.execute("INSERT OR REPLACE INTO paper_snapshot VALUES (1, ?)", (json.dumps(body, sort_keys=True),)); self.db.commit()

    def health(self, now_ns: int) -> PaperHealth:
        row = self.db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone()
        snapshot = json.loads(row[0]) if row else None
        commands = {row[0] for row in self.db.execute("SELECT command FROM paper_commands")}
        warnings: list[str] = []
        if snapshot is None: warnings.append("MISSING_SNAPSHOT")
        elif now_ns - snapshot["ts_ns"] > self.max_data_age_ns: warnings.append("STALE_DATA")
        if snapshot and snapshot["orders"]: warnings.append("UNRECONCILED_ORDERS")
        return PaperHealth(self.owner, "pause-new-entries" in commands, "flatten" in commands, not warnings and "pause-new-entries" not in commands, tuple(warnings))

    def close(self) -> None: self.db.close()
