"""Closed-history epoch boundary; never reconstructs or adopts open exposure."""
from __future__ import annotations

import hashlib
import json
import time
from decimal import Decimal

from coinmaster.ops.paper import PaperRuntime, _journal_locked
from coinmaster.strategy.live_recovery import _decode, _FIELDS, _C1_SCHEMA, checkpoint_structure


class LiveEpochRuntime(PaperRuntime):
    """Keep the complete SQLite audit while scoping native parity to this epoch."""

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.db.execute("CREATE TABLE IF NOT EXISTS live_evidence_payloads (cursor INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL,kind TEXT NOT NULL,body TEXT NOT NULL,UNIQUE(event_id,kind))")
        self.db.execute("CREATE TABLE IF NOT EXISTS live_evidence_cursors (source TEXT PRIMARY KEY,body TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS live_info_checkpoint (id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL)")
        self.db.commit()

    @_journal_locked
    def append_evidence(self,event_id,kind,payload,*,commit=True):
        if not event_id or kind not in ('decision','command','ACK','fill','account','funding_cash','funding_rate','signal','Info'):
            raise ValueError('LIVE_EVIDENCE_ID_OR_KIND_INVALID')
        body=json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False,default=str)
        prior=self.db.execute('SELECT body FROM live_evidence_payloads WHERE event_id=? AND kind=?',(event_id,kind)).fetchone()
        if prior is not None:
            old=json.loads(prior[0]);current=json.loads(body)
            if isinstance(old,dict) and isinstance(current,dict):
                old.pop('received_ns',None);current.pop('received_ns',None)
            if old!=current:raise ValueError('LIVE_EVIDENCE_CONFLICTING_DUPLICATE')
            return False
        self.db.execute('INSERT INTO live_evidence_payloads(event_id,kind,body) VALUES (?,?,?)',(event_id,kind,body))
        if commit:self.db.commit()
        return True

    @_journal_locked
    def evidence_cursor(self,source):
        row=self.db.execute('SELECT body FROM live_evidence_cursors WHERE source=?',(source,)).fetchone()
        return json.loads(row[0]) if row else None

    @_journal_locked
    def record_funding_page(self,rows,*,expected_cursor,next_cursor,complete):
        # Actual userFunding cashflows only. Never invokes Sandbox cash posting.
        if not complete or not isinstance(next_cursor,dict):raise ValueError('LIVE_FUNDING_PAGE_INCOMPLETE')
        try:
            self.db.execute('BEGIN IMMEDIATE')
            if self.evidence_cursor('userFunding')!=expected_cursor:raise ValueError('LIVE_FUNDING_CURSOR_MOVED')
            for row in rows:
                if not isinstance(row,dict) or type(row.get('time')) is not int or not row.get('hash') or not isinstance(row.get('delta'),dict):
                    raise ValueError('LIVE_FUNDING_CASHFLOW_INVALID')
                delta=row['delta'];amount=Decimal(str(delta.get('usdc')))
                if delta.get('coin') not in ('BTC','SOL') or not amount.is_finite():raise ValueError('LIVE_FUNDING_CASHFLOW_SCOPE')
                key='funding:'+str(row['hash'])+':'+str(row['time'])+':'+delta['coin']
                self.append_evidence(key,'funding_cash',dict(source='ACTUAL_VENUE_USERFUNDING',native=row,cash_posted=False),commit=False)
            self.db.execute('INSERT OR REPLACE INTO live_evidence_cursors VALUES (?,?)',('userFunding',json.dumps(next_cursor,sort_keys=True)))
            self.db.commit()
        except BaseException:self.db.rollback();raise

    def _journal_order_fills(self,client_id):
        rows=self.db.execute('SELECT trade_id,native_event_id,client_order_id,venue_order_id,instrument_id,order_side,quantity,price,commission_amount,commission_currency,liquidity_side,ts_event_ns,ts_init_ns FROM paper_native_fill_details WHERE client_order_id=? ORDER BY trade_id',(client_id,)).fetchall()
        return [list(row) for row in rows]

    @_journal_locked
    def save_verified_info_checkpoint(self,receipt,terminal_proofs,expected_revision):
        if self.native_revision()!=expected_revision:raise ValueError('LIVE_INFO_CHECKPOINT_REVISION_MOVED')
        body=dict(start_ms=receipt.start_ms,anchor_tid=receipt.anchor_tid,end_ms=receipt.end_ms,
            fills=list(receipt.fills),terminal_proofs=terminal_proofs,revision=expected_revision)
        self.db.execute('INSERT OR REPLACE INTO live_info_checkpoint VALUES (1,?)',(json.dumps(body,sort_keys=True),))
        self.append_evidence('Info:'+str(receipt.end_ms)+':'+str(expected_revision),'Info',body,commit=False)
        self.db.commit()

    @_journal_locked
    def info_query_evidence(self,native_fingerprints,applied):
        row=self.db.execute('SELECT body FROM live_info_checkpoint WHERE id=1').fetchone()
        if row is None:return {},(),None,None
        old=json.loads(row[0]);fills=old['fills'];known={str(fill['tid']) for fill in fills}
        if not known.issubset(applied):raise ValueError('LIVE_INFO_ARCHIVED_FILL_DISAPPEARED')
        latest=max(fills,key=lambda f:(f['time'],f['tid'])) if fills else None
        if latest is not None:
            # A newly received fill older than our tail revokes that tail; re-read
            # original history, retaining all journal evidence and all ownership.
            for tid in applied-known:
                native=self.db.execute('SELECT ts_event_ns FROM paper_native_fill_details WHERE trade_id=?',(tid,)).fetchone()
                if native is None or native[0] is None:raise ValueError('LIVE_INFO_FILL_CLOCK_UNKNOWN')
                if native[0]//1_000_000<latest['time']:return {},(),None,None
        cached={}
        unresolved={json.loads(command)['client_order_id'] for (command,) in self.db.execute("SELECT command FROM paper_command_audit WHERE status='MANAGE_SUBMITTING'")}
        states={row['client_order_id']:row['state'] for row in self.all_submissions()}
        for cloid,proof in old['terminal_proofs'].items():
            client=proof['client_id']
            if (client not in unresolved and states.get(client)=='TERMINAL'
                and native_fingerprints.get(client)==proof['native_fingerprint']
                and self._journal_order_fills(client)==proof['journal_fills']):cached[cloid]=proof['status']
        return cached,tuple(fills),latest['time'] if latest else None,latest['tid'] if latest else None

    def c1_initialization(self):
        return self.evidence_cursor('c1_epoch_initialization')

    @_journal_locked
    def initialize_c1_epoch(self,*,intent,checkpoint,policy_sha256,equity,account_total,account_event_id,
                            expected_revision,now_ns,history_anchor_ms):
        """One virgin epoch marker + canonical state + native flat snapshot commit."""
        if intent!='INITIALIZE_FRESH_C1_EPOCH' or type(history_anchor_ms) is not int or not 0<=history_anchor_ms<=now_ns//1_000_000:raise ValueError('C1_INIT_EXPLICIT_INTENT_REQUIRED')
        if (not isinstance(equity,Decimal) or not equity.is_finite() or equity<=0
            or equity!=account_total or not account_event_id):raise ValueError('C1_INIT_NATIVE_EQUITY_UNKNOWN')
        body=json.loads(checkpoint);checkpoint_structure(body)
        if body.get('schema')!=_C1_SCHEMA or body.get('policy_sha256')!=policy_sha256:
            raise ValueError('C1_INIT_POLICY_UNKNOWN')
        try:
            self.db.execute('BEGIN IMMEDIATE')
            if (self._live_account_identity is None or self.entry_control_state()!='PAUSED' or self.recovery_state()!='FLAT_RESTART'
                or self.c1_initialization() is not None or self.strategy_checkpoint() is not None
                or self.all_submissions() or self.applied_fill_ids() or self.pending_submissions()
                or self.pending_native_funding() or self.native_revision()!=expected_revision
                or self.db.execute('SELECT EXISTS(SELECT 1 FROM paper_native_fill_details)').fetchone()[0]
                or self.db.execute("SELECT EXISTS(SELECT 1 FROM paper_events WHERE kind='fill')").fetchone()[0]
                or self.db.execute("SELECT EXISTS(SELECT 1 FROM paper_command_audit WHERE command!='pause-new-entries' OR status!='ACCEPTED')").fetchone()[0]):
                raise ValueError('C1_INIT_PRIOR_OR_UNCERTAIN_STATE')
            marker=dict(schema='coinmaster-live-c1-initialization-v1',policy_sha256=policy_sha256,
                checkpoint_sha256=hashlib.sha256(checkpoint).hexdigest(),initial_equity=str(equity),
                native_account_event_id=str(account_event_id),native_revision=expected_revision,initialized_ns=now_ns,history_anchor_ms=history_anchor_ms)
            self.db.execute('INSERT INTO live_evidence_cursors VALUES (?,?)',('c1_epoch_initialization',json.dumps(marker,sort_keys=True)))
            self.db.execute('INSERT INTO paper_strategy_checkpoint VALUES (1,?,?)',(checkpoint,expected_revision))
            snapshot=dict(ts_ns=now_ns,positions=[],orders=[],funding_event_ids=[],reconciled=True,
                native_revision=expected_revision,native_account_total=str(account_total),native_account_currency='USDC',strategy_restartable=True)
            self.db.execute('INSERT OR REPLACE INTO paper_snapshot VALUES (1,?)',(json.dumps(snapshot,sort_keys=True),))
            self.append_evidence('c1-epoch-initialize','Info',marker,commit=False)
            self.db.commit()
        except BaseException:self.db.rollback();raise
        return marker

    @_journal_locked
    def commit_applied_fills(self,trade_ids,strategy_state):
        """Typed native-fill payload and applied-ID/checkpoint share one commit."""
        try:
            for trade_id in trade_ids:
                row=self.db.execute('SELECT native_event_id,client_order_id,venue_order_id,instrument_id,order_side,quantity,price,commission_amount,commission_currency,liquidity_side,ts_event_ns,ts_init_ns FROM paper_native_fill_details WHERE trade_id=?',(trade_id,)).fetchone()
                if row is None:raise ValueError('LIVE_TYPED_FILL_NATIVE_FACTS_MISSING')
                keys=('native_event_id','client_order_id','venue_order_id','instrument_id','order_side','quantity','price','commission_amount','commission_currency','liquidity_side','ts_event_ns','ts_init_ns')
                self.append_evidence(trade_id,'fill',dict(source='ACTUAL_NATIVE_FILL',trade_id=trade_id,native=dict(zip(keys,row))),commit=False)
            return super().commit_applied_fills(trade_ids,strategy_state)
        except BaseException:self.db.rollback();raise

    @_journal_locked
    def acquire(self) -> None:
        if self._process_lock_fd is not None:return
        if self.db.in_transaction:raise RuntimeError("LIVE_ACQUIRE_PENDING_TRANSACTION")
        super().acquire()
        # PaperRuntime's same-owner INSERT conflict leaves an empty SQLite
        # transaction open. End only that failed INSERT, never commit or erase
        # any durable pending command/checkpoint on restart.
        if self.db.in_transaction:self.db.rollback()

    def prepare_flat_epoch(self, *, release_commit: str) -> Decimal | None:
        rows = super().all_submissions()
        checkpoint = super().strategy_checkpoint()
        self._retired_orders = frozenset()
        self._retired_fills = frozenset()
        self._retired_checkpoint = None
        if not rows and checkpoint is None:
            if self.recovery_state() != "FLAT_RESTART":
                raise RuntimeError("LIVE_RESTART_MANUAL_RECOVERY_REQUIRED")
            return None
        raw = self.db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone()
        snapshot = json.loads(raw[0]) if raw else {}
        revision = self.native_revision()
        if (not rows or any(row["state"] != "TERMINAL" for row in rows)
                or checkpoint is None or checkpoint[1] != revision
                or snapshot.get("native_revision") != revision
                or snapshot.get("reconciled") is not True
                or snapshot.get("positions") or snapshot.get("orders")
                or snapshot.get("native_account_currency") != "USDC"
                or self.pending_native_funding()):
            raise RuntimeError("LIVE_FLAT_HISTORY_UNPROVEN")
        cash = Decimal(snapshot["native_account_total"])
        if not cash.is_finite() or cash <= 0:
            raise RuntimeError("LIVE_FLAT_HISTORY_BALANCE_INVALID")
        protection = self.deposit_protection_state(
            instance_id=self.owner, account_id="HYPERLIQUID-master")
        if protection is None:
            raise RuntimeError("LIVE_FLAT_HISTORY_DEPOSIT_ANCHOR_MISSING")
        body = json.loads(checkpoint[0])
        if body.get("schema")==_C1_SCHEMA:
            checkpoint_structure(body)
            # No closed-epoch retirement of C1 global H/rights/causal clocks.
            # The next process must load the exact policy-bound checkpoint.
            raise RuntimeError("C1_E4_CHECKPOINT_REQUIRES_MANAGE_ONLY")
        if (body.get("schema") != "coinmaster-wave-overlay-live-recovery-v1"
                or set(body) != {"schema", "candidate_sha256", "strategy_id", "domain", "state"}
                or not set(body["state"]).issubset(_FIELDS)
                or set(body["domain"]) != {"episode", "locked_after_liquidation", "decision_index"}):
            raise RuntimeError("LIVE_FLAT_HISTORY_CHECKPOINT_UNKNOWN")
        domain = body["domain"]
        if domain["locked_after_liquidation"]:
            raise RuntimeError("LIVE_FLAT_HISTORY_LOCKED")
        episode = domain["episode"]
        if episode is not None:
            if episode.get("t") != "Episode":
                raise RuntimeError("LIVE_FLAT_HISTORY_EPISODE_UNKNOWN")
            for field in ("btc_open_qty", "sol_qty"):
                value = Decimal(str(_decode(episode["v"][field])))
                if not value.is_finite() or value != 0:
                    raise RuntimeError("LIVE_FLAT_HISTORY_EXPOSURE")
        unresolved = (
            "_pending_by_order", "_queued_intents", "_mandatory_sol_exit",
            "_forced_close_reason", "_forced_close_intent", "_forced_close_submitted",
            "_forced_close_orders", "_group_close_reconciliation_pending",
            "_liquidating", "_liquidation_waiting", "_liquidation_orders",
            "_accepted_reductions", "_deferred_selective_entries",
        )
        for name in unresolved:
            value = _decode(body["state"][name]) if name in body["state"] else None
            if not value:
                continue
            if name != "_forced_close_submitted":
                raise RuntimeError("LIVE_FLAT_HISTORY_UNRESOLVED_DECISION")
            # Production _reconcile_group_flat clears the completed group
            # reason/intent/orders but retains its instrument tombstone.
            # Retire only after all other decisions are empty (checked by
            # this loop), the native snapshot is flat/revision-matched, and
            # the instrument has a fully filled owned terminal close receipt.
            if not isinstance(value, set) or not set(map(str, value)).issubset({
                    "BTC-USD-PERP.HYPERLIQUID", "SOL-USD-PERP.HYPERLIQUID"}):
                raise RuntimeError("LIVE_FLAT_HISTORY_UNRESOLVED_DECISION")
            for instrument in map(str, value):
                proven = False
                for row in rows:
                    if (row["instrument_id"] != instrument or row["action"] != "FORCED_CLOSE"
                            or row["body"].get("reduce_only") is not True):
                        continue
                    closing_fills = self.db.execute(
                        "SELECT quantity FROM paper_native_fill_details "
                        "WHERE client_order_id=? AND instrument_id=?",
                        (row["client_order_id"], instrument))
                    filled = sum((Decimal(fill[0]) for fill in closing_fills), Decimal("0"))
                    if filled == Decimal(row["body"]["quantity"]) and filled > 0:
                        proven = True
                        break
                if not proven:
                    raise RuntimeError("LIVE_FLAT_HISTORY_UNRESOLVED_DECISION")
        fills = super().applied_fill_ids()
        details = self.db.execute(
            "SELECT trade_id,client_order_id FROM paper_native_fill_details").fetchall()
        ids = frozenset(row["client_order_id"] for row in rows)
        if {row[0] for row in details} != fills or any(row[1] not in ids for row in details):
            raise RuntimeError("LIVE_FLAT_HISTORY_FILL_OWNERSHIP_UNKNOWN")
        # Preserve original checkpoint, ledger and DP state. This audit records an
        # attempted transition; venue flat/money parity still gates recovery.
        audit = json.dumps({
            "schema": "coinmaster-live-flat-epoch-v1",
            "release_commit": release_commit,
            "checkpoint_sha256": hashlib.sha256(checkpoint[0]).hexdigest(),
            "checkpoint": body, "snapshot": snapshot,
            "retired_orders": sorted(ids), "retired_fills": sorted(fills),
            "deposit_protection": protection,
            "state": "AWAITING_FRESH_NATIVE_FLAT_PARITY",
        }, sort_keys=True)
        event_id = "flat-epoch:" + hashlib.sha256(audit.encode()).hexdigest()
        self.db.execute("INSERT OR IGNORE INTO paper_events VALUES (?, ?)", (event_id, audit))
        self.db.commit()
        self._retired_orders, self._retired_fills = ids, fills
        self._retired_checkpoint = checkpoint
        self.flat_epoch_balance = cash
        return cash

    def native_equity_changes(self, *, run_epoch, now_ns):
        result = super().native_equity_changes(run_epoch=run_epoch, now_ns=now_ns)
        return {**result, "instance_id": self.owner, "source": "NATIVE_LIVE_ACCOUNT"}

    def all_submissions(self):
        return [row for row in super().all_submissions()
                if row["client_order_id"] not in getattr(self, "_retired_orders", ())]

    def applied_fill_ids(self):
        return super().applied_fill_ids() - getattr(self, "_retired_fills", frozenset())

    def strategy_checkpoint(self):
        result = super().strategy_checkpoint()
        return None if result == getattr(self, "_retired_checkpoint", None) else result


    @_journal_locked
    def reserve_management(self,*,command_id,kind,client_order_id,instrument_id,quantity,side,episode_id,expected_revision,strategy_state):
        """Existing journal transaction + account lease; uncertainty survives restart."""
        if self._live_account_identity is None:raise RuntimeError("LIVE_ACCOUNT_LEASE_REQUIRED")
        try:
            self.db.execute("BEGIN IMMEDIATE")
            if self.native_revision()!=expected_revision:
                self.db.rollback();return False
            unresolved=self.db.execute("SELECT command FROM paper_command_audit WHERE status='MANAGE_SUBMITTING'").fetchall()
            if unresolved:
                self.db.rollback();return False
            if kind=="REDUCE" and any(r["body"].get("reduce_only") and r["state"]!="TERMINAL" for r in self.all_submissions()):
                self.db.rollback();return False
            command=json.dumps(dict(kind=kind,client_order_id=client_order_id,instrument_id=instrument_id),sort_keys=True)
            self.db.execute("INSERT INTO paper_command_audit VALUES (?,?,?,?)",(command_id,command,"MANAGE_SUBMITTING",time.time_ns()))
            self.append_evidence(command_id,'command',dict(state='RESERVED_BEFORE_DISPATCH',kind=kind,client_order_id=client_order_id,instrument_id=instrument_id,quantity=quantity,side=side,episode_id=episode_id,native_revision=expected_revision),commit=False)
            if kind=="REDUCE":
                return self.record_submission(client_order_id=client_order_id,intent_id=command_id,episode_id=episode_id,
                    action="FORCED_CLOSE",instrument_id=instrument_id,quantity=quantity,reduce_only=True,
                    strategy_state=strategy_state,order_shape=dict(side=side,kind="MARKET",tif="IOC",post_only=False,price=None))
            if kind!="CANCEL":raise ValueError("MANAGEMENT_ACTION_FORBIDDEN")
            self._bump_native_revision()
            self.db.execute("INSERT OR REPLACE INTO paper_strategy_checkpoint VALUES (1,?,?)",(strategy_state,self.native_revision()))
            self.db.commit();return True
        except BaseException:
            self.db.rollback();raise

    @_journal_locked
    def reconcile_management_commands(self,terminal_client_ids,expected_revision):
        """Only a complete fresh owned report may resolve uncertain command audit."""
        if self.native_revision()!=expected_revision:raise RuntimeError("MANAGEMENT_RESOLUTION_REVISION_MOVED")
        for key,command in self.db.execute("SELECT idempotency_key,command FROM paper_command_audit WHERE status='MANAGE_SUBMITTING'").fetchall():
            if json.loads(command)["client_order_id"] in terminal_client_ids:
                self.db.execute("UPDATE paper_command_audit SET status='MANAGE_TERMINAL_OBSERVED' WHERE idempotency_key=?",(key,))
        self.db.commit()
