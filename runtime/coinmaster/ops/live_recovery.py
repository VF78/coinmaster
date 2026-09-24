"""Fail-closed native-report reconciliation for a future live adapter.

This owns no exchange transport, matching, fills, PnL, or account posting.
Nautilus remains authoritative; recovered intents are never resubmitted.
"""
from __future__ import annotations

import time
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from nautilus_trader.model.enums import OrderSide

from coinmaster.ops.paper import PaperRuntime

if TYPE_CHECKING:
    from coinmaster.strategy.live_recovery import RecoverableWaveOverlayStrategy


class LiveRecoverySubmissionSink:
    def __init__(self, runtime: PaperRuntime, strategy: "RecoverableWaveOverlayStrategy", owned_instruments: frozenset[str]) -> None:
        if not owned_instruments:
            raise ValueError("EMPTY_RECOVERY_OWNERSHIP")
        self.runtime = runtime
        self.strategy = strategy
        self.owned_instruments = owned_instruments

    def __call__(self, **request) -> bool:
        if request["instrument_id"] not in self.owned_instruments:
            raise ValueError("UNOWNED_RECOVERY_INSTRUMENT")
        if not request["reduce_only"] and not self.runtime.health(time.time_ns()).safe_for_increase:
            return False
        checkpoint = self.strategy.on_save()["wave_overlay_live_recovery_v1"]
        return self.runtime.record_submission(
            client_order_id=request["client_order_id"],
            intent_id=request["intent_id"],
            episode_id=request["episode_id"],
            action=request["action"],
            instrument_id=request["instrument_id"],
            quantity=request["quantity"],
            reduce_only=request["reduce_only"],
            strategy_state=checkpoint,
        )


class LiveRecoveryReconciler:
    """Validate a complete native report set before one domain/checkpoint commit."""

    def __init__(self, runtime: PaperRuntime, strategy: "RecoverableWaveOverlayStrategy", expected_account_id: str) -> None:
        self.runtime = runtime
        self.strategy = strategy
        self.expected_account_id = expected_account_id

    def apply_partial_fills(self, reports: list, native_orders: list, native_positions: list, order_reports: list) -> None:
        self.strategy.recovery_confirmed = False
        owned = {str(self.strategy.config.btc_id), str(self.strategy.config.sol_id)}
        strategy_id = str(self.strategy.id)
        journal = {item["client_order_id"]: item for item in self.runtime.pending_submissions()}
        orders = {str(item.client_order_id): item for item in native_orders}
        status = {str(item.client_order_id): item for item in order_reports}
        if len(orders) != len(native_orders) or len(status) != len(order_reports) or set(status) != set(orders):
            raise ValueError("RECOVERY_DUPLICATE_NATIVE_ORDER")
        episode = self.strategy._domain.episode
        if episode is None:
            raise ValueError("RECOVERY_EPISODE_MISSING")
        checkpoint = self.runtime.strategy_checkpoint()
        current = self.strategy.on_save()["wave_overlay_live_recovery_v1"]
        if checkpoint is None or checkpoint[0] != current:
            raise ValueError("RECOVERY_CHECKPOINT_LINEAGE_MISMATCH")

        reports_by_order = defaultdict(list)
        seen_trades = set()
        for report in reports:
            trade_id = str(report.trade_id)
            if not trade_id or trade_id in seen_trades:
                raise ValueError("RECOVERY_DUPLICATE_NATIVE_FILL")
            seen_trades.add(trade_id)
            order_id = str(report.client_order_id)
            reports_by_order[order_id].append(report)
            order = orders.get(order_id)
            intent = self.strategy._pending_by_order.get(order_id)
            recorded = journal.get(order_id)
            if (
                order is None or intent is None or recorded is None
                or recorded["intent_id"] != intent.id
                or recorded["episode_id"] != intent.episode_id
                or recorded["instrument_id"] != str(report.instrument_id)
                or recorded["action"] != intent.action
                or intent.id not in episode.pending
                or str(report.account_id) != self.expected_account_id
                or str(report.venue_order_id) != str(order.venue_order_id)
                or report.instrument_id != order.instrument_id
                or report.order_side != order.side
                or order.side != (OrderSide.BUY if intent.side == 1 else OrderSide.SELL)
                or Decimal(str(report.last_qty)) <= 0
                or Decimal(str(report.last_px)) <= 0
            ):
                raise ValueError("RECOVERY_FILL_IDENTITY_MISMATCH")
        for order_id, order in orders.items():
            intent = self.strategy._pending_by_order.get(order_id)
            recorded = journal.get(order_id)
            status_report = status[order_id]
            if (
                intent is None or recorded is None
                or str(status_report.account_id) != self.expected_account_id
                or (order.account_id is not None and str(order.account_id) != self.expected_account_id)
                or str(status_report.venue_order_id) != str(order.venue_order_id)
                or status_report.instrument_id != order.instrument_id
                or status_report.order_side != order.side
                or status_report.filled_qty.as_decimal() != order.filled_qty.as_decimal()
                or str(order.strategy_id) != strategy_id
                or str(order.instrument_id) not in owned
                or order.is_closed
                or recorded["intent_id"] != intent.id
                or recorded["instrument_id"] != str(order.instrument_id)
                or recorded["action"] != intent.action
            ):
                raise ValueError("RECOVERY_ORDER_OWNERSHIP_MISMATCH")
            known_ids = {str(item) for item in order.trade_ids}
            reported_ids = {str(item.trade_id) for item in reports_by_order[order_id]}
            quantity = sum((item.last_qty.as_decimal() for item in reports_by_order[order_id]), Decimal("0"))
            if known_ids != reported_ids or quantity != order.filled_qty.as_decimal():
                raise ValueError("RECOVERY_NATIVE_FILL_SET_MISMATCH")

        positions = {str(item.instrument_id): item for item in native_positions}
        if len(positions) != len(native_positions):
            raise ValueError("RECOVERY_DUPLICATE_NATIVE_POSITION")
        for position in native_positions:
            if (
                str(position.instrument_id) not in owned
                or str(position.account_id) != self.expected_account_id
                or str(position.strategy_id) != strategy_id
            ):
                raise ValueError("RECOVERY_POSITION_OWNERSHIP_MISMATCH")

        # Work on a detached, versioned domain copy. Rejected reports leave
        # live memory, SQLite checkpoint, and trade cursor byte-identical.
        candidate = type(self.strategy)(self.strategy.config)
        candidate.on_load({"wave_overlay_live_recovery_v1": current})
        missing = []
        for report in sorted(reports, key=lambda item: (item.ts_event, str(item.trade_id))):
            trade_id = str(report.trade_id)
            if self.runtime.has_applied_fill(trade_id):
                continue
            order_id = str(report.client_order_id)
            intent = candidate._pending_by_order[order_id]
            candidate._domain.on_fill(
                intent.id, float(report.last_qty), float(report.last_px),
                datetime.fromtimestamp(report.ts_event / 1_000_000_000, UTC),
                candidate._sigma_by_order.get(order_id),
                decision_index=candidate._confirmed_fill_cycle(intent, order_id),
            )
            missing.append(trade_id)
        candidate_episode = candidate._domain.episode
        assert candidate_episode is not None
        btc = positions.get(str(self.strategy.config.btc_id))
        sol = positions.get(str(self.strategy.config.sol_id))
        native_btc = btc.quantity.as_decimal() if btc is not None else Decimal("0")
        native_sol = sol.quantity.as_decimal() if sol is not None else Decimal("0")
        if (
            abs(Decimal(str(candidate_episode.btc_open_qty)) - native_btc) > Decimal("0.000000001")
            or abs(Decimal(str(candidate_episode.sol_qty)) - native_sol) > Decimal("0.000000001")
            or (btc is not None and btc.is_long != (candidate_episode.side == 1))
            or (sol is not None and sol.is_long != (candidate_episode.side == -1))
        ):
            raise ValueError("RECOVERY_EPISODE_POSITION_MISMATCH")
        if missing:
            state = candidate.on_save()["wave_overlay_live_recovery_v1"]
            if not self.runtime.commit_applied_fills(missing, state):
                raise ValueError("RECOVERY_FILL_CURSOR_CONFLICT")
            self.strategy.on_load({"wave_overlay_live_recovery_v1": state})
