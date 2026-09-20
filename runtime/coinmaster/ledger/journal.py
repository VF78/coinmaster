from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path


class NativeEventJournal:
    """Stores event IDs and validates snapshots; never calculates trading PnL."""

    def __init__(self, database: str = ":memory:") -> None:
        self.durable = database != ":memory:"
        if self.durable:
            Path(database).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(database)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS funding_events ("
            "event_id TEXT PRIMARY KEY, instrument_id TEXT NOT NULL, ts_event INTEGER NOT NULL, "
            "rate TEXT NOT NULL, settlement_mark TEXT NOT NULL, account_total_after TEXT NOT NULL)"
        )
        self.db.execute("CREATE TABLE IF NOT EXISTS transfers (event_id TEXT PRIMARY KEY, active_before TEXT NOT NULL, active_after TEXT NOT NULL, reserve_before TEXT NOT NULL, reserve_after TEXT NOT NULL)")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS native_parent_order_audit ("
            "order_id TEXT NOT NULL, state TEXT NOT NULL, requested_qty TEXT NOT NULL, filled_qty TEXT NOT NULL, "
            "leaves_qty TEXT NOT NULL, canceled_qty TEXT NOT NULL, pending_reservation TEXT, "
            "position_initial_margin TEXT, position_maintenance_margin TEXT, native_locked TEXT NOT NULL, "
            "native_free TEXT NOT NULL, parent_fees TEXT NOT NULL, close_fees TEXT NOT NULL, "
            "PRIMARY KEY(order_id,state))",
        )
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(native_parent_order_audit)")}
        # The first partial-parent fixture named this raw engine snapshot as
        # native_margin_init. It is not position IM while a parent is pending.
        if "native_margin_init" in columns and "engine_margin_init_snapshot" not in columns:
            self.db.execute(
                "ALTER TABLE native_parent_order_audit RENAME COLUMN native_margin_init "
                "TO engine_margin_init_snapshot",
            )
            columns.remove("native_margin_init")
            columns.add("engine_margin_init_snapshot")
        for name in ("pending_reservation", "position_initial_margin", "position_maintenance_margin"):
            if name not in columns:
                self.db.execute(f"ALTER TABLE native_parent_order_audit ADD COLUMN {name} TEXT")

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

    def has_transfer(self, event_id: str) -> bool:
        return self.db.execute("SELECT 1 FROM transfers WHERE event_id=?", (event_id,)).fetchone() is not None

    def transfer_audit(self) -> list[tuple[str, str, str, str, str]]:
        return self.db.execute(
            "SELECT event_id,active_before,active_after,reserve_before,reserve_after FROM transfers ORDER BY event_id",
        ).fetchall()

    def record_native_parent_order(
        self, order_id: str, state: str, requested_qty: Decimal, filled_qty: Decimal, leaves_qty: Decimal,
        canceled_qty: Decimal, pending_reservation: Decimal | None, position_initial_margin: Decimal | None,
        position_maintenance_margin: Decimal | None, native_locked: Decimal, native_free: Decimal,
        parent_fees: Decimal, close_fees: Decimal,
    ) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO native_parent_order_audit "
            "(order_id,state,requested_qty,filled_qty,leaves_qty,canceled_qty,pending_reservation,"
            "position_initial_margin,position_maintenance_margin,native_locked,native_free,parent_fees,close_fees) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                order_id, state, str(requested_qty), str(filled_qty), str(leaves_qty), str(canceled_qty),
                str(pending_reservation) if pending_reservation is not None else None,
                str(position_initial_margin) if position_initial_margin is not None else None,
                str(position_maintenance_margin) if position_maintenance_margin is not None else None,
                str(native_locked), str(native_free), str(parent_fees), str(close_fees),
            ),
        )
        self.db.commit()

    def native_parent_order_audit(self) -> list[tuple[str, str, str, str, str, str, str | None, str | None, str | None, str, str, str, str]]:
        return self.db.execute(
            "SELECT order_id,state,requested_qty,filled_qty,leaves_qty,canceled_qty,pending_reservation,"
            "position_initial_margin,position_maintenance_margin,native_locked,native_free,parent_fees,close_fees "
            "FROM native_parent_order_audit ORDER BY rowid",
        ).fetchall()

    @staticmethod
    def assert_total(native_active: Decimal, reserve: Decimal, expected_total: Decimal) -> None:
        if native_active + reserve != expected_total:
            raise ValueError("native ACTIVE + RESERVE does not equal TOTAL")
