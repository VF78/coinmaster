"""Explicit research child policy; observes native receipts without changing them."""
from decimal import Decimal as D

CHILD_CAP = D("1000")


def child_quantity(intended, step):
    if not intended.is_finite() or not step.is_finite() or intended < 0 or step <= 0:
        raise ValueError("INVALID_EXPLICIT_CHILD_QUANTITY")
    return (min(intended, CHILD_CAP) // step) * step


class SystemContractResearch:
    def _sc_init(self):
        self.system_contract_audit = []
        self._sc_attempts = {}
        self._sc_orders = {}
        self._sc_seen_events = set()

    def _sc_sol_quantity(self, intent, intended, step, price, ns):
        if not self.config.research_sol_explicit_child:
            return intended
        allowed = child_quantity(intended, step)
        # The domain has already consumed this level's original D1 attempt.
        # Keep the original notional right and intent unchanged.
        row = dict(event="SOL_ATTEMPT", timestamp_ns=int(ns), intent_id=intent.id,
                   episode_id=intent.episode_id, level=intent.level,
                   decision_index=intent.decision_index,
                   next_attempt_earliest_decision_index=intent.decision_index + 1,
                   next_attempt_condition="ORIGINAL_D1_SIGNAL_RIGHT_AND_ADMISSION",
                   original_remaining_notional=str(intent.requested_notional),
                   intended_quantity=str(intended), allowed_quantity=str(allowed),
                   submitted_quantity="0", filled_quantity="0", filled_notional="0",
                   unused_right_notional=str(intent.requested_notional),
                   executable_price=str(price), native_status="NOT_SUBMITTED")
        self._sc_attempts[intent.id] = row
        self.system_contract_audit.append(row)
        return allowed

    def _sc_bind(self, intent, order):
        row = self._sc_attempts.get(intent.id)
        if row is None:
            return
        row["client_order_id"] = str(order.client_order_id)
        row["submitted_quantity"] = str(order.quantity.as_decimal())
        self._sc_orders[str(order.client_order_id)] = row

    def _sc_denied(self, intent, reason):
        row = self._sc_attempts.get(intent.id)
        if row is not None:
            row["local_denial"] = reason
            row["native_status"] = "LOCAL_UNSENT"
            row["submitted_quantity"] = "0"

    def _sc_native_event(self, event):
        row = self._sc_orders.get(str(event.client_order_id))
        if row is None:
            return
        identity = str(event.id)
        if identity in self._sc_seen_events:
            return
        self._sc_seen_events.add(identity)
        order = self.cache.order(event.client_order_id)
        if order is not None:
            row["native_status"] = order.status.name
        qty = getattr(event, "last_qty", None)
        if qty is not None:
            price = event.last_px.as_decimal()
            row["filled_quantity"] = str(D(row["filled_quantity"]) + qty.as_decimal())
            row["filled_notional"] = str(D(row["filled_notional"]) + qty.as_decimal() * price)
            row["unused_right_notional"] = str(max(D(0), D(row["original_remaining_notional"]) - D(row["filled_notional"])))
        self.system_contract_audit.append(dict(event=type(event).__name__,
            native_event_id=identity, timestamp_ns=int(event.ts_event),
            client_order_id=str(event.client_order_id),
            native_status=row["native_status"], filled_quantity=row["filled_quantity"],
            unused_right_notional=row["unused_right_notional"],
            commission=str(getattr(event, "commission", "UNKNOWN_NOT_A_FILL"))))
