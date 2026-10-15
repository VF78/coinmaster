"""Closed-history epoch boundary; never reconstructs or adopts open exposure."""
from __future__ import annotations

import hashlib
import json
import time
from decimal import Decimal

from coinmaster.ops.paper import PaperRuntime
from coinmaster.strategy.live_recovery import _decode, _FIELDS


class LiveEpochRuntime(PaperRuntime):
    """Keep the complete SQLite audit while scoping native parity to this epoch."""

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
        if any(_decode(body["state"][name]) for name in unresolved if name in body["state"]):
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
