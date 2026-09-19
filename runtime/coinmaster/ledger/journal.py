from __future__ import annotations

import sqlite3
from decimal import Decimal


class NativeEventJournal:
    """Stores event IDs and validates snapshots; never calculates trading PnL."""

    def __init__(self, database: str = ":memory:") -> None:
        self.db = sqlite3.connect(database)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS funding_events (event_id TEXT PRIMARY KEY, account_total_after TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS transfers (event_id TEXT PRIMARY KEY, active_before TEXT NOT NULL, active_after TEXT NOT NULL, reserve_before TEXT NOT NULL, reserve_after TEXT NOT NULL)")

    def record_funding(self, event_id: str, native_account_total_after: Decimal) -> bool:
        cursor = self.db.execute(
            "INSERT OR IGNORE INTO funding_events VALUES (?, ?)",
            (event_id, str(native_account_total_after)),
        )
        self.db.commit()
        return cursor.rowcount == 1

    def record_transfer(self, event_id: str, active_before: Decimal, active_after: Decimal, reserve_before: Decimal, reserve_after: Decimal) -> bool:
        if active_before + reserve_before != active_after + reserve_after:
            raise ValueError("transfer changes TOTAL")
        cursor = self.db.execute(
            "INSERT OR IGNORE INTO transfers VALUES (?, ?, ?, ?, ?)",
            (event_id, str(active_before), str(active_after), str(reserve_before), str(reserve_after)),
        )
        self.db.commit()
        return cursor.rowcount == 1

    @staticmethod
    def assert_total(native_active: Decimal, reserve: Decimal, expected_total: Decimal) -> None:
        if native_active + reserve != expected_total:
            raise ValueError("native ACTIVE + RESERVE does not equal TOTAL")
