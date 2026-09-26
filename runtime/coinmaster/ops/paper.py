"""Fail-closed durable control plane for the local native paper worker.

This owns paper intent state only; it never loads credentials or creates live
adapters/orders. A separate native worker may read the durable snapshots.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
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
    def __init__(self, database: Path, owner: str, max_data_age_ns: int, *, require_native_cash: bool = False) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        # The SQLite owner row is durable identity, not an exclusive process
        # lease.  This OS lock is held from acquire until close or process exit.
        self._process_lock_path = database.with_name(database.name + ".owner.lock")
        self._process_lock_fd: int | None = None
        self._live_account_lock_fd: int | None = None
        self._live_account_identity: tuple[str, str] | None = None
        self._local_sandbox_active = False
        self.require_native_cash = require_native_cash
        self.db, self.owner, self.max_data_age_ns = sqlite3.connect(database, check_same_thread=False), owner, max_data_age_ns
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_lock (id INTEGER PRIMARY KEY CHECK(id=1), owner TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_commands (idempotency_key TEXT PRIMARY KEY, command TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_command_audit (idempotency_key TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL, ts_ns INTEGER NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_events (event_id TEXT PRIMARY KEY, kind TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_deposit_protection (id INTEGER PRIMARY KEY CHECK(id=1), instance_id TEXT NOT NULL, account_id TEXT NOT NULL, currency TEXT NOT NULL, body TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_deposit_audit (event_key TEXT PRIMARY KEY, action TEXT NOT NULL, old_body TEXT, new_body TEXT NOT NULL, ts_ns INTEGER NOT NULL)")
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
        # A terminal fill can arrive after the last snapshot and before a
        # process crash. Its revision remains dirty until a coherent native
        # cache snapshot is durably recorded.
        # A live-recovery pre-submit boundary commits the exact strategy
        # episode/order mapping with its intent in one SQLite transaction.
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_strategy_checkpoint (id INTEGER PRIMARY KEY CHECK(id=1), body BLOB NOT NULL, native_revision INTEGER NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_recovered_fills (trade_id TEXT PRIMARY KEY)")
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_native_revision (id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER NOT NULL)")
        self.db.execute("INSERT OR IGNORE INTO paper_native_revision VALUES (1, 0)")
        self.db.commit()

    @_journal_locked
    def native_revision(self) -> int:
        return int(self.db.execute("SELECT value FROM paper_native_revision WHERE id=1").fetchone()[0])

    def _bump_native_revision(self) -> None:
        self.db.execute("UPDATE paper_native_revision SET value=value+1 WHERE id=1")

    @_journal_locked
    def acquire_live_account(
        self, account_ref: str, venue: str, *, lock_root: Path = Path("/run/lock/coinmaster"),
    ) -> None:
        """Hold one account+venue OS lease across SQLite paths until close/exit."""
        if (
            not isinstance(account_ref, str) or len(account_ref) != 42
            or not account_ref.startswith("0x") or venue != "HYPERLIQUID"
            or not isinstance(lock_root, Path) or not lock_root.is_absolute()
        ):
            raise ValueError("LIVE_ACCOUNT_LEASE_SCOPE_INVALID")
        try:
            int(account_ref[2:], 16)
        except ValueError as exc:
            raise ValueError("LIVE_ACCOUNT_LEASE_SCOPE_INVALID") from exc
        identity = (venue, account_ref.lower())
        if self._live_account_lock_fd is not None:
            if identity != self._live_account_identity:
                raise RuntimeError("LIVE_ACCOUNT_LEASE_REBIND_FORBIDDEN")
            return
        lock_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        digest = hashlib.sha256(f"{venue}:{account_ref.lower()}".encode()).hexdigest()
        fd = os.open(lock_root / f"{digest}.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException as exc:
            os.close(fd)
            raise RuntimeError("LIVE_ACCOUNT_ALREADY_OWNED") from exc
        self._live_account_lock_fd = fd
        self._live_account_identity = identity

    @_journal_locked
    def coherent_snapshot(self) -> bool:
        row = self.db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone()
        if row is None:
            return False
        snapshot = json.loads(row[0])
        return (
            snapshot.get("reconciled") is True
            and snapshot.get("native_revision") == self.native_revision()
            and snapshot.get("native_account_currency") == "USDC"
            and snapshot.get("native_account_total") is not None
            and snapshot.get("strategy_restartable") is True
        )


    @_journal_locked
    def acquire(self) -> None:
        if self._process_lock_fd is not None:
            return
        fd = os.open(self._process_lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError("PAPER_PROCESS_LOCKED") from error
            try:
                self.db.execute("INSERT INTO paper_lock VALUES (1, ?)", (self.owner,))
                self.db.commit()
            except sqlite3.IntegrityError as error:
                row = self.db.execute("SELECT owner FROM paper_lock WHERE id=1").fetchone()
                if not row or row[0] != self.owner:
                    raise RuntimeError("PAPER_OWNER_LOCKED") from error
            self._process_lock_fd = fd
        except BaseException:
            os.close(fd)
            raise

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
    def entry_control_command(self, command: str, idempotency_key: str) -> str:
        """Persist an exact Stage-G entry admission command before acknowledgement."""
        if command not in {"pause-new-entries", "resume-new-entries"}:
            raise ValueError("unsupported entry control command")
        previous = self.db.execute(
            "SELECT command FROM paper_commands WHERE idempotency_key=?", (idempotency_key,)
        ).fetchone()
        if previous is not None:
            if previous[0] != command:
                raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
            return "DUPLICATE"
        self.db.execute("INSERT INTO paper_commands VALUES (?, ?)", (idempotency_key, command))
        self.db.execute(
            "INSERT INTO paper_command_audit VALUES (?, ?, ?, strftime('%s','now') * 1000000000)",
            (idempotency_key, command, "ACCEPTED"),
        )
        self.db.commit()
        return "ACCEPTED"

    @_journal_locked
    def entry_control_state(self) -> str:
        row = self.db.execute(
            "SELECT command FROM paper_command_audit WHERE command IN ('pause-new-entries', 'resume-new-entries') "
            "ORDER BY ts_ns DESC, rowid DESC LIMIT 1"
        ).fetchone()
        return "PAUSED" if row is not None and row[0] == "pause-new-entries" else "RUNNING"

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
            self._bump_native_revision()
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    @_journal_locked
    def record_submission(self, *, client_order_id: str, intent_id: str, episode_id: str, action: str, instrument_id: str, quantity: str, reduce_only: bool, strategy_state: bytes | None = None, order_shape: dict | None = None) -> bool:
        """Durably mark a native submit before handing it to Nautilus.

        ``SUBMITTING`` is intentionally uncertain until a terminal callback;
        it therefore survives a crash-before-ACK as a recovery gate.
        """
        if strategy_state is not None and (not isinstance(strategy_state, bytes) or not strategy_state):
            raise ValueError("INVALID_STRATEGY_CHECKPOINT")
        if order_shape is not None and set(order_shape) != {"side", "kind", "tif", "post_only", "price"}:
            raise ValueError("INVALID_DURABLE_ORDER_SHAPE")
        body = json.dumps({"quantity": quantity, "reduce_only": reduce_only, "shape": order_shape}, sort_keys=True)
        try:
            self.db.execute(
                "INSERT INTO paper_intents VALUES (?, ?, ?, ?, ?, 'SUBMITTING', ?)",
                (client_order_id, intent_id, episode_id, action, instrument_id, body),
            )
            self._bump_native_revision()
            if strategy_state is not None:
                self.db.execute(
                    "INSERT OR REPLACE INTO paper_strategy_checkpoint VALUES (1, ?, ?)",
                    (strategy_state, self.native_revision()),
                )
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            self.db.rollback()
            return False

    @_journal_locked
    def strategy_checkpoint(self) -> tuple[bytes, int] | None:
        row = self.db.execute("SELECT body,native_revision FROM paper_strategy_checkpoint WHERE id=1").fetchone()
        return (bytes(row[0]), int(row[1])) if row else None

    @_journal_locked
    def has_applied_fill(self, trade_id: str) -> bool:
        return self.db.execute("SELECT 1 FROM paper_recovered_fills WHERE trade_id=?", (trade_id,)).fetchone() is not None

    def has_recovered_fill(self, trade_id: str) -> bool:
        return self.has_applied_fill(trade_id)

    @_journal_locked
    def applied_fill_ids(self) -> frozenset[str]:
        """Return the durable domain fill cursor for native event parity."""
        return frozenset(
            row[0] for row in self.db.execute("SELECT trade_id FROM paper_recovered_fills")
        )

    @_journal_locked
    def commit_applied_fills(self, trade_ids: list[str], strategy_state: bytes) -> bool:
        """Atomically persist domain state and all native trade IDs it includes."""
        if not trade_ids or len(set(trade_ids)) != len(trade_ids) or any(not item for item in trade_ids):
            raise ValueError("INVALID_APPLIED_FILL_IDS")
        if not isinstance(strategy_state, bytes) or not strategy_state:
            raise ValueError("INVALID_APPLIED_FILL_CHECKPOINT")
        try:
            self.db.executemany(
                "INSERT INTO paper_recovered_fills VALUES (?)",
                [(item,) for item in trade_ids],
            )
            self._bump_native_revision()
            self.db.execute(
                "INSERT OR REPLACE INTO paper_strategy_checkpoint VALUES (1, ?, ?)",
                (strategy_state, self.native_revision()),
            )
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            self.db.rollback()
            return False

    def commit_recovered_fill(self, trade_id: str, strategy_state: bytes) -> bool:
        return self.commit_applied_fills([trade_id], strategy_state)

    @_journal_locked
    def acknowledge_submission(self, client_order_id: str) -> None:
        self.db.execute("UPDATE paper_intents SET state='ACKED' WHERE client_order_id=? AND state='SUBMITTING'", (client_order_id,))
        self.db.commit()

    @_journal_locked
    def terminal_submission(self, client_order_id: str, strategy_state: bytes | None = None) -> None:
        if strategy_state is not None and (not isinstance(strategy_state, bytes) or not strategy_state):
            raise ValueError("INVALID_STRATEGY_CHECKPOINT")
        try:
            changed = self.db.execute(
                "UPDATE paper_intents SET state='TERMINAL' WHERE client_order_id=? AND state!='TERMINAL'",
                (client_order_id,),
            ).rowcount
            if changed:
                self._bump_native_revision()
                if strategy_state is not None:
                    self.db.execute(
                        "INSERT OR REPLACE INTO paper_strategy_checkpoint VALUES (1, ?, ?)",
                        (strategy_state, self.native_revision()),
                    )
            elif strategy_state is not None and not self.db.execute(
                "SELECT 1 FROM paper_intents WHERE client_order_id=?", (client_order_id,),
            ).fetchone():
                raise ValueError("UNKNOWN_TERMINAL_SUBMISSION")
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    @_journal_locked
    def pending_submissions(self) -> list[dict]:
        return [
            {"client_order_id": row[0], "intent_id": row[1], "episode_id": row[2], "action": row[3], "instrument_id": row[4], "state": row[5], "body": json.loads(row[6])}
            for row in self.db.execute("SELECT client_order_id,intent_id,episode_id,action,instrument_id,state,body FROM paper_intents WHERE state != 'TERMINAL' ORDER BY client_order_id")
        ]

    @_journal_locked
    def all_submissions(self) -> list[dict]:
        return [
            {"client_order_id": row[0], "intent_id": row[1], "episode_id": row[2], "action": row[3],
             "instrument_id": row[4], "state": row[5], "body": json.loads(row[6])}
            for row in self.db.execute(
                "SELECT client_order_id,intent_id,episode_id,action,instrument_id,state,body FROM paper_intents ORDER BY client_order_id"
            )
        ]

    @_journal_locked
    def recovery_state(self) -> str:
        """Return the only supported restart contract for durable exposure."""
        row = self.db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone()
        snapshot = json.loads(row[0]) if row else None
        if self.pending_native_funding():
            return "MANAGE_ONLY_PENDING_NATIVE_FUNDING"
        pending = self.pending_submissions()
        # A local Sandbox process may continue to manage a reconciled resting
        # BTC take-profit. The order must be visible in this snapshot and
        # match its own acknowledged durable reduction record exactly. This
        # exception is deliberately process-local: the same bytes after a
        # restart remain MANAGE_ONLY because Sandbox cannot restore its cache.
        if pending and self._local_sandbox_active and self._owned_open_btc_reductions(snapshot, pending):
            return "ACTIVE_OWNED_REDUCTIONS"
        if pending:
            return "MANAGE_ONLY_PENDING_INTENT"
        if snapshot is None:
            activity = self.db.execute("SELECT EXISTS(SELECT 1 FROM paper_events UNION ALL SELECT 1 FROM paper_intents UNION ALL SELECT 1 FROM paper_native_funding)").fetchone()[0]
            if activity:
                return "RECOVERY_REQUIRED_UNSNAPSHOTTED_NATIVE_STATE"
        revision = self.native_revision()
        if snapshot and snapshot.get("native_revision") is None and not self._local_sandbox_active:
            legacy_activity = self.db.execute("SELECT EXISTS(SELECT 1 FROM paper_events UNION ALL SELECT 1 FROM paper_intents UNION ALL SELECT 1 FROM paper_native_funding)").fetchone()[0]
            if legacy_activity:
                return "RECOVERY_REQUIRED_LEGACY_UNSNAPSHOTTED_STATE"
        elif snapshot and snapshot.get("native_revision") != revision and not self._local_sandbox_active:
            return "RECOVERY_REQUIRED_UNSNAPSHOTTED_NATIVE_STATE"
        if snapshot and (snapshot.get("positions") or snapshot.get("orders")) and not self._local_sandbox_active:
            return "MANAGE_ONLY_DURABLE_OPEN_STATE"
        if self.require_native_cash and not self._local_sandbox_active and snapshot:
            if snapshot.get("strategy_restartable") is not True:
                activity = self.db.execute("SELECT EXISTS(SELECT 1 FROM paper_events UNION ALL SELECT 1 FROM paper_intents UNION ALL SELECT 1 FROM paper_native_funding)").fetchone()[0]
                if activity:
                    return "RECOVERY_REQUIRED_STRATEGY_STATE"
            if not snapshot.get("native_account_total") or snapshot.get("native_account_currency") != "USDC":
                activity = self.db.execute("SELECT EXISTS(SELECT 1 FROM paper_events UNION ALL SELECT 1 FROM paper_intents UNION ALL SELECT 1 FROM paper_native_funding)").fetchone()[0]
                if activity:
                    return "RECOVERY_REQUIRED_ACCOUNT_SNAPSHOT"
        return "FLAT_RESTART"

    @staticmethod
    def _owned_open_btc_reductions(snapshot: dict | None, pending: list[dict]) -> bool:
        """Accept only snapshot-confirmed owned BTC TP reductions in-process."""
        if not snapshot or snapshot.get("reconciled") is not True:
            return False
        orders = snapshot.get("orders")
        if not isinstance(orders, list) or not orders:
            return False
        records = {item["client_order_id"]: item for item in pending}
        for order in orders:
            if not isinstance(order, dict):
                return False
            client_order_id = order.get("client_order_id")
            record = records.get(client_order_id)
            if (
                not isinstance(client_order_id, str)
                or record is None
                or record["state"] != "ACKED"
                or record["action"] != "BTC_REDUCE"
                or record["instrument_id"] != order.get("instrument_id")
                or record["body"].get("reduce_only") is not True
                or order.get("reduce_only") is not True
            ):
                return False
        return len(records) == len(orders)

    @_journal_locked
    def flat_native_cash(self) -> Decimal | None:
        if self.recovery_state() != "FLAT_RESTART":
            return None
        row = self.db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone()
        snapshot = json.loads(row[0]) if row else {}
        total = snapshot.get("native_account_total")
        if total is None:
            return Decimal("10000")  # Legacy pristine Sandbox only.
        if snapshot.get("native_account_currency") != "USDC" or snapshot.get("positions") or snapshot.get("orders"):
            return None
        cash = Decimal(total)
        return cash if cash.is_finite() and cash > 0 else None

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
        changed = self.db.execute("UPDATE paper_native_funding SET state='POSTED' WHERE event_id=? AND state='PREPARED'", (event_id,)).rowcount
        self.db.execute("INSERT OR IGNORE INTO paper_events VALUES (?, 'funding')", (event_id,))
        if changed:
            self._bump_native_revision()
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
    def snapshot(self, *, ts_ns: int, positions: list[dict], orders: list[dict], funding_event_ids: list[str], reconciled: bool = True, expected_revision: int | None = None, native_account_total: str | None = None, strategy_restartable: bool | None = None, run_epoch: str | None = None) -> bool:
        revision = self.native_revision()
        if expected_revision is not None and revision != expected_revision:
            self.heartbeat(ts_ns)
            return False
        body = {"ts_ns": ts_ns, "positions": positions, "orders": orders, "funding_event_ids": funding_event_ids, "reconciled": reconciled, "native_revision": revision}
        if native_account_total is not None:
            cash = Decimal(native_account_total)
            if not cash.is_finite() or cash <= 0:
                raise ValueError("INVALID_NATIVE_ACCOUNT_TOTAL")
            body["native_account_total"] = str(cash)
            body["native_account_currency"] = "USDC"
        if strategy_restartable is not None:
            body["strategy_restartable"] = strategy_restartable
        if run_epoch is not None:
            body["run_epoch"] = run_epoch
        self.db.execute("INSERT OR REPLACE INTO paper_snapshot VALUES (1, ?)", (json.dumps(body, sort_keys=True),)); self.db.commit()
        if reconciled:
            self._local_sandbox_active = True
        return True

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
        paused = self.entry_control_state() == "PAUSED"
        warnings: list[str] = []
        if snapshot is None: warnings.append("MISSING_SNAPSHOT")
        elif now_ns - snapshot["ts_ns"] > self.max_data_age_ns: warnings.append("STALE_DATA")
        recovery = self.recovery_state()
        if recovery not in {"FLAT_RESTART", "ACTIVE_OWNED_REDUCTIONS"}: warnings.append(recovery)
        if snapshot and not snapshot.get("reconciled", False): warnings.append("SANDBOX_RECONCILIATION_MISMATCH")
        if snapshot and snapshot["orders"] and not self._owned_open_btc_reductions(snapshot, self.pending_submissions()): warnings.append("UNRECONCILED_ORDERS")
        return PaperHealth(self.owner, paused, "flatten-paper" in commands, not warnings and not paused, tuple(warnings))

    @_journal_locked
    def events(self, cursor: int = 0, limit: int = 100) -> list[dict]:
        return [{"cursor": row[0], "event_id": row[1], "kind": row[2]} for row in self.db.execute("SELECT rowid, event_id, kind FROM paper_events WHERE rowid > ? ORDER BY rowid LIMIT ?", (cursor, limit))]

    @_journal_locked
    def projection_snapshot(self) -> tuple[list[dict], list[dict]]:
        """Bounded state for a worker-owned, read-only status projection."""
        row = self.db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone()
        snapshot = json.loads(row[0]) if row else {}
        return snapshot.get("positions", []), snapshot.get("orders", [])

    @_journal_locked
    def projection_events(self, limit: int = 100) -> tuple[list[dict], int]:
        """Return the latest bounded event window and the durable high-water cursor."""
        rows = list(self.db.execute("SELECT rowid,event_id,kind FROM paper_events ORDER BY rowid DESC LIMIT ?", (limit,)))
        cursor = self.db.execute("SELECT COALESCE(MAX(rowid), 0) FROM paper_events").fetchone()[0]
        rows.reverse()
        return ([{"cursor": row[0], "event_id": row[1], "kind": row[2]} for row in rows], cursor)

    @_journal_locked
    def deposit_protection_state(self, *, instance_id: str, account_id: str) -> dict | None:
        row = self.db.execute(
            "SELECT instance_id,account_id,currency,body FROM paper_deposit_protection WHERE id=1"
        ).fetchone()
        if row is None:
            return None
        if row[:3] != (instance_id, account_id, "USDC"):
            raise ValueError("DEPOSIT_ACCOUNT_IDENTITY_MISMATCH")
        body = json.loads(row[3])
        if not isinstance(body, dict):
            raise ValueError("DEPOSIT_STATE_INVALID")
        return body

    @_journal_locked
    def deposit_audit_action(self, event_key: str) -> str | None:
        row = self.db.execute(
            "SELECT action FROM paper_deposit_audit WHERE event_key=?", (event_key,)
        ).fetchone()
        return row[0] if row else None

    @_journal_locked
    def save_deposit_protection(
        self, *, instance_id: str, account_id: str, action: str,
        event_key: str, state: dict, ts_ns: int,
    ) -> bool:
        if not instance_id or not account_id or not action or not event_key or not isinstance(state, dict):
            raise ValueError("DEPOSIT_SAVE_INVALID")
        existing = self.deposit_protection_state(instance_id=instance_id, account_id=account_id)
        body = json.dumps(state, sort_keys=True, separators=(",", ":"))
        prior = self.db.execute(
            "SELECT action,new_body FROM paper_deposit_audit WHERE event_key=?", (event_key,)
        ).fetchone()
        if prior is not None:
            if prior != (action, body):
                raise ValueError("DEPOSIT_IDEMPOTENCY_CONFLICT")
            return False
        old_body = None if existing is None else json.dumps(existing, sort_keys=True, separators=(",", ":"))
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO paper_deposit_protection VALUES (1, ?, ?, 'USDC', ?)",
                (instance_id, account_id, body),
            )
            self.db.execute(
                "INSERT INTO paper_deposit_audit VALUES (?, ?, ?, ?, ?)",
                (event_key, action, old_body, body, ts_ns),
            )
        return True

    @_journal_locked
    def close(self) -> None:
        try:
            self.db.close()
        finally:
            if self._live_account_lock_fd is not None:
                fcntl.flock(self._live_account_lock_fd, fcntl.LOCK_UN)
                os.close(self._live_account_lock_fd)
                self._live_account_lock_fd = None
                self._live_account_identity = None
            if self._process_lock_fd is not None:
                fcntl.flock(self._process_lock_fd, fcntl.LOCK_UN)
                os.close(self._process_lock_fd)
                self._process_lock_fd = None
