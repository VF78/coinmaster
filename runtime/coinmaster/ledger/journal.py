from __future__ import annotations

import sqlite3
from decimal import Decimal


class NativeEventJournal:
    """Stores event IDs and validates snapshots; never calculates trading PnL."""

    def __init__(self, database: str = ":memory:") -> None:
        self.durable = database != ":memory:"
        self.db = sqlite3.connect(database)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS funding_events ("
            "event_id TEXT PRIMARY KEY, instrument_id TEXT NOT NULL, ts_event INTEGER NOT NULL, "
            "rate TEXT NOT NULL, settlement_mark TEXT NOT NULL, account_total_after TEXT NOT NULL)"
        )
        self.db.execute("CREATE TABLE IF NOT EXISTS transfers (event_id TEXT PRIMARY KEY, active_before TEXT NOT NULL, active_after TEXT NOT NULL, reserve_before TEXT NOT NULL, reserve_after TEXT NOT NULL)")

    def has_funding(self, event_id: str) -> bool:
        return self.db.execute(
            "SELECT 1 FROM funding_events WHERE event_id = ?", (event_id,),
        ).fetchone() is not None

    def record_funding(
        self,
        event_id: str,
        instrument_id: str,
        ts_event: int,
        rate: Decimal,
        settlement_mark: Decimal,
        native_account_total_after: Decimal,
    ) -> bool:
        cursor = self.db.execute(
            "INSERT OR IGNORE INTO funding_events VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, instrument_id, ts_event, str(rate), str(settlement_mark), str(native_account_total_after)),
        )
        self.db.commit()
        return cursor.rowcount == 1

    def funding_audit(self) -> list[tuple[str, str, int, str, str, str]]:
        return self.db.execute(
            "SELECT event_id, instrument_id, ts_event, rate, settlement_mark, account_total_after "
            "FROM funding_events ORDER BY ts_event, event_id",
        ).fetchall()

    def close(self) -> None:
        self.db.close()

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
