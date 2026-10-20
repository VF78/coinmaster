"""Research-only, file-backed native audit; no execution or monetary ledger."""
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import hashlib
import json
import os
import sqlite3


class AuditRows:
    def __init__(self, archive, kind):
        self.archive, self.kind = archive, kind
        self.count = 0

    def append(self, row):
        self.archive.db.execute("INSERT INTO rows(kind,payload) VALUES (?,?)",
                                (self.kind, json.dumps(row)))
        self.count += 1

    def __len__(self):
        return self.count

    def __iter__(self):
        for (body,) in self.archive.db.execute("SELECT payload FROM rows WHERE kind=? ORDER BY seq", (self.kind,)):
            yield json.loads(body)

    def __getitem__(self, index):
        if index < 0:
            index += self.count
        row = self.archive.db.execute("SELECT payload FROM rows WHERE kind=? ORDER BY seq LIMIT 1 OFFSET ?",
                                      (self.kind, index)).fetchone()
        if row is None:
            raise IndexError(index)
        return json.loads(row[0])

    def reference(self):
        return self.archive.reference("rows", self.kind, self.count)


class AuditIds:
    def __init__(self, archive):
        self.archive = archive

    def __contains__(self, key):
        return self.archive.db.execute("SELECT 1 FROM trade_ids WHERE id=?", (key,)).fetchone() is not None

    def add(self, key):
        self.archive.db.execute("INSERT OR IGNORE INTO trade_ids VALUES (?)", (key,))

    def __len__(self):
        return self.archive.db.execute("SELECT count(*) FROM trade_ids").fetchone()[0]


class OrderContexts(Mapping):
    """Keep mutable current contexts intact; flush them only at runner boundaries."""
    def __init__(self, archive):
        self.archive, self.current = archive, {}

    def __setitem__(self, key, row):
        self.current[key] = row

    def __getitem__(self, key):
        if key not in self.current:
            row = self.archive.db.execute("SELECT payload FROM contexts WHERE id=?", (key,)).fetchone()
            if row is None:
                raise KeyError(key)
            self.current[key] = json.loads(row[0])
        return self.current[key]

    def __iter__(self):
        self.flush()
        for (key,) in self.archive.db.execute("SELECT id FROM contexts"):
            yield key

    def __len__(self):
        return self.archive.db.execute("SELECT count(*) FROM contexts").fetchone()[0] + sum(
            self.archive.db.execute("SELECT 1 FROM contexts WHERE id=?", (key,)).fetchone() is None for key in self.current)

    def flush(self):
        self.archive.db.executemany("INSERT OR REPLACE INTO contexts VALUES (?,?)",
                                   ((key, json.dumps(row)) for key, row in self.current.items()))

    def reference(self):
        return self.archive.reference("contexts", None, len(self))


class CashRows:
    def __init__(self, archive, start=None, end=None, initial=None):
        self.archive, self.start, self.end, self.initial = archive, start, end, initial

    def __iter__(self):
        if self.initial is not None:
            yield dict(timestamp=self.start.isoformat(), active=str(self.initial), reserve="0", total=str(self.initial))
        for ns, body in self.archive.db.execute("SELECT ns,payload FROM native WHERE kind='account' ORDER BY ns,seq"):
            from pandas import Timestamp
            point = Timestamp(ns, unit="ns", tz="UTC")
            if self.start is not None and not self.start <= point < self.end:
                continue
            state = json.loads(body)
            for balance in state["balances"]:
                yield dict(timestamp=str(point), active=balance["total"], reserve="0", total=balance["total"])

    def __bool__(self):
        return True

    def __getitem__(self, index):
        if index == 0:
            return next(iter(self))
        if index == -1:
            last = None
            for last in self:
                pass
            if last is None:
                raise IndexError(index)
            return last
        raise IndexError(index)

    def monthly_returns(self, initial):
        months = {}
        for point in self:
            months[point["timestamp"][:7]] = Decimal(point["total"])
        if not months:
            return []
        first, last = min(months), max(months)
        cursor = datetime.fromisoformat(first + "-01").replace(tzinfo=timezone.utc)
        previous, result = initial, []
        while cursor.strftime("%Y-%m") <= last:
            month = cursor.strftime("%Y-%m")
            total = months.get(month, previous)
            result.append(dict(month=month, total=str(total), return_=str(total / previous - 1)))
            result[-1]["return"] = result[-1].pop("return_")
            previous = total
            cursor = cursor.replace(year=cursor.year + (cursor.month == 12), month=1 if cursor.month == 12 else cursor.month + 1)
        return result

    def reference(self):
        return self.archive.reference("native", "account", sum(1 for _ in self)) | {
            "view": "native_cash_balances", "start": self.start.isoformat() if self.start else None,
            "end_exclusive": self.end.isoformat() if self.end else None, "initial": str(self.initial) if self.initial is not None else None}


class FillTimes:
    def __init__(self, archive):
        self.archive = archive

    def __iter__(self):
        for (body,) in self.archive.db.execute("SELECT payload FROM native WHERE kind='order' ORDER BY id"):
            row = json.loads(body)
            if Decimal(row["filled_qty"]) > 0:
                yield row["ts_last"]

    def reference(self):
        return self.archive.reference("native", "order", sum(1 for _ in self)) | {"view": "filled_order_ts_last"}


class NativeAuditArchive:
    def __init__(self, path, strategy):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # An archive belongs to exactly one fresh engine; never resume or merge.
        if self.path.exists():
            raise ValueError("NATIVE_AUDIT_NAMESPACE_EXISTS")
        self.db = sqlite3.connect(self.path)
        self.db.executescript("""
            PRAGMA journal_mode=DELETE;
            PRAGMA synchronous=FULL;
            PRAGMA cache_size=-2048;
            PRAGMA temp_store=FILE;
            CREATE TABLE rows(seq INTEGER PRIMARY KEY,kind TEXT,payload TEXT);
            CREATE INDEX rows_kind ON rows(kind,seq);
            CREATE TABLE trade_ids(id TEXT PRIMARY KEY);
            CREATE TABLE contexts(id TEXT PRIMARY KEY,payload TEXT);
            CREATE TABLE native(seq INTEGER PRIMARY KEY,kind TEXT,id TEXT,ns INTEGER,payload TEXT,UNIQUE(kind,id));
            CREATE INDEX native_time ON native(kind,ns,seq);
        """)
        self.strategy = strategy
        self.rows = {name: AuditRows(self, name) for name in ("risk_first_sol_audit", "fill_audit")}
        for name, rows in self.rows.items():
            for row in getattr(strategy, name):
                rows.append(row)
            setattr(strategy, name, rows)
        self.contexts = OrderContexts(self)
        for key, row in strategy._order_audit.items():
            self.contexts[key] = row
        strategy._order_audit = self.contexts
        ids = AuditIds(self)
        for key in strategy._seen_trade_ids:
            ids.add(key)
        strategy._seen_trade_ids = ids
        self.digest = None
        self.checkpoints = 0
        self.native_counts = {}

    def count(self, kind):
        return self.native_counts.get(kind, 0)

    def native(self, kind, key, ns, row):
        payload = json.dumps(row, default=str)
        inserted = self.db.execute("INSERT OR IGNORE INTO native(kind,id,ns,payload) VALUES (?,?,?,?)",
                                   (kind, key, ns, payload)).rowcount
        if inserted:
            self.native_counts[kind] = self.native_counts.get(kind, 0) + 1
        else:
            self.db.execute("UPDATE native SET ns=?,payload=? WHERE kind=? AND id=?", (ns, payload, kind, key))

    def capture(self, engine, timestamp, final=False):
        """Only after engine.run returns: archive first, commit, then supported purge."""
        from nautilus_trader.model.events import AccountState
        strategy = self.strategy
        protected = set(strategy._pending_by_order) | set(strategy._forced_close_orders) | set(strategy._rf_sol_orders) | set(strategy._v3_orders) | set(strategy._deposit_exit_orders)
        orders = engine.cache.orders()
        by_id = {str(order.client_order_id): order for order in orders}
        eligible = []
        for order in orders:
            oid = str(order.client_order_id)
            linked = order.linked_order_ids or ()
            safe = order.is_closed and oid not in protected and not any(
                str(key) in protected or str(key) in by_id and not by_id[str(key)].is_closed for key in linked
            )
            if not safe and not final:
                continue
            self.native("order", oid, order.ts_last or order.ts_init, order.to_dict())
            for event in order.events:
                self.native("order_event", str(event.id), event.ts_event, type(event).to_dict(event))
            if safe:
                eligible.append(order)
        account = engine.cache.account_for_venue(strategy.config.btc_id.venue)
        for event in account.events:
            self.native("account", str(event.id), event.ts_event, AccountState.to_dict(event))
        positions = []
        pending_instruments = {strategy.config.btc_id if intent.action.startswith("BTC") else strategy.config.sol_id
                               for intent in strategy._pending_by_order.values()}
        pending_instruments.update(order.instrument_id for order in orders
                                   if not order.is_closed or str(order.client_order_id) in protected)
        unmapped_protected = protected - set(by_id) - set(strategy._pending_by_order)
        for position in engine.cache.positions_closed():
            if unmapped_protected or position.instrument_id in pending_instruments:
                continue
            self.native("position", f"{position.id}:{position.ts_opened}:{position.ts_closed}", position.ts_closed, position.to_dict())
            for snapshot in engine.cache.position_snapshots(position.id):
                self.native("position_snapshot", f"{snapshot.id}:{snapshot.ts_opened}:{snapshot.ts_closed}", snapshot.ts_closed, snapshot.to_dict())
            positions.append(position)
        self.contexts.flush()
        self.db.commit()  # FULL fsync completes before a native object is released.
        before = (account.balance_total(), account.balance_free(), account.balance_locked(), tuple(account.commissions().items()))
        for order in eligible:
            engine.cache.purge_order(order.client_order_id, False)
        for position in positions:
            engine.cache.purge_position(position.id, False)
        engine.cache.purge_account_events(timestamp, 0, False)
        after = (account.balance_total(), account.balance_free(), account.balance_locked(), tuple(account.commissions().items()))
        if before != after:
            raise AssertionError("ARCHIVAL_CHANGED_NATIVE_ACCOUNT")
        # Exact historical lookup is retained on disk, including mutable accept_ns.
        self.contexts.current.clear()
        self.checkpoints += 1
        return dict(checkpoint=self.checkpoints, native_orders=len(engine.cache.orders()),
                    native_positions=len(engine.cache.positions()), account_events=len(account.events),
                    archived_orders=self.count("order"), archived_account_events=self.count("account"),
                    audit_rows={name: len(rows) for name, rows in self.rows.items()},
                    mutable_contexts=len(self.contexts.current))

    def reference(self, table, kind, count):
        return dict(schema="coinmaster.native-audit.sqlite.v1", path=str(self.path), table=table,
                    kind=kind, rows=count, sha256=self.digest, completeness="ALL_EMITTED_ROWS", sampling="UNCHANGED_EXISTING_POLICY")

    def freeze(self):
        self.contexts.flush()
        self.db.commit()
        digest = hashlib.sha256()
        with self.path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        self.digest = digest.hexdigest()

    def export_orders(self, target, filled=False):
        """Reproduce native ReportProvider rows, in bounded DataFrame chunks."""
        import pandas as pd
        columns = []
        for (body,) in self.db.execute("SELECT payload FROM native WHERE kind='order' ORDER BY id"):
            row = json.loads(body)
            if filled and Decimal(row["filled_qty"]) <= 0:
                continue
            columns.extend(key for key in row if key not in columns)
        path = Path(target)
        temporary = path.with_suffix(".tmp")
        count, batch = 0, []
        with temporary.open("w") as stream:
            if not columns:
                pd.DataFrame().to_csv(stream)
            def flush():
                frame = pd.DataFrame(batch, columns=columns).set_index("client_order_id")
                if filled:
                    for key in ("ts_init", "ts_last"):
                        frame[key] = pd.to_datetime(frame[key], unit="ns", utc=True)
                frame.to_csv(stream, header=count == 0)
                stream.flush(); os.fsync(stream.fileno())
            for (body,) in self.db.execute("SELECT payload FROM native WHERE kind='order' ORDER BY id"):
                row = json.loads(body)
                if filled and Decimal(row["filled_qty"]) <= 0:
                    continue
                batch.append(row)
                if len(batch) == 256:
                    flush(); count += len(batch); batch.clear()
            if batch:
                flush(); count += len(batch)
            stream.flush(); os.fsync(stream.fileno())
        temporary.replace(path)
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return dict(path=str(path), sha256=digest.hexdigest(), rows=count)

    def close(self):
        self.db.commit()
        self.db.close()



def audit_json_default(value):
    reference = getattr(value, "reference", None)
    if callable(reference):
        return reference()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
