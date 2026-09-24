"""Credential-free pre-submit recovery boundary for a future live adapter.

This owns no exchange transport, matching, fills, PnL, or reconciliation.
Nautilus remains authoritative; a recovered intent never resubmits itself.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

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
    """Apply only missing strategy-domain transitions from native venue reports."""

    def __init__(self, runtime: PaperRuntime, strategy: "RecoverableWaveOverlayStrategy", expected_account_id: str) -> None:
        self.runtime = runtime
        self.strategy = strategy
        self.expected_account_id = expected_account_id

    def apply_partial_fills(self, reports: list, native_orders: list, native_positions: list) -> None:
        from datetime import UTC, datetime
        from math import isclose

        self.strategy.recovery_confirmed = False
        orders = {str(order.client_order_id): order for order in native_orders}
        if len(orders) != len(native_orders):
            raise ValueError("RECOVERY_DUPLICATE_NATIVE_ORDER")
        episode = self.strategy._domain.episode
        if episode is None:
            raise ValueError("RECOVERY_EPISODE_MISSING")
        for report in sorted(reports, key=lambda item: (item.ts_event, str(item.trade_id))):
            trade_id = str(report.trade_id)
            if self.runtime.has_recovered_fill(trade_id):
                continue
            order_id = str(report.client_order_id)
            intent = self.strategy._pending_by_order.get(order_id)
            order = orders.get(order_id)
            if (
                str(report.account_id) != self.expected_account_id
                or intent is None or intent.id not in episode.pending
                or order is None or order.is_closed
                or report.instrument_id != order.instrument_id
                or report.venue_order_id != order.venue_order_id
                or report.last_qty.as_decimal() <= 0
                or intent.action not in {"BTC_ENTRY", "BTC_REDUCE", "SOL_ADD", "SOL_HALF_EXIT", "SOL_EXIT"}
                or report.instrument_id != (
                    self.strategy.config.btc_id if intent.action.startswith("BTC")
                    else self.strategy.config.sol_id
                )
            ):
                raise ValueError("RECOVERY_FILL_IDENTITY_MISMATCH")
            sigma = self.strategy._sigma_by_order.get(order_id)
            decision_index = self.strategy._confirmed_fill_cycle(intent, order_id)
            self.strategy._domain.on_fill(
                intent.id, float(report.last_qty), float(report.last_px),
                datetime.fromtimestamp(report.ts_event / 1_000_000_000, UTC),
                sigma, decision_index=decision_index,
            )
            state = self.strategy.on_save()["wave_overlay_live_recovery_v1"]
            if not self.runtime.commit_recovered_fill(trade_id, state):
                raise ValueError("RECOVERY_FILL_CURSOR_CONFLICT")
        positions = {str(position.instrument_id): position for position in native_positions}
        if len(positions) != len(native_positions):
            raise ValueError("RECOVERY_DUPLICATE_NATIVE_POSITION")
        btc = positions.get(str(self.strategy.config.btc_id))
        sol = positions.get(str(self.strategy.config.sol_id))
        native_btc = float(btc.quantity) if btc is not None else 0.0
        native_sol = float(sol.quantity) if sol is not None else 0.0
        if (
            not isclose(episode.btc_open_qty, native_btc, abs_tol=1e-9)
            or not isclose(episode.sol_qty, native_sol, abs_tol=1e-9)
            or (btc is not None and btc.is_long != (episode.side == 1))
            or (sol is not None and sol.is_long != (episode.side == -1))
        ):
            raise ValueError("RECOVERY_EPISODE_POSITION_MISMATCH")
