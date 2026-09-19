"""Risk-increasing intent reservation; this is not a balance or PnL ledger."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class MarginReservation:
    requested_im: Decimal
    filled_im: Decimal = Decimal("0")
    canceled: bool = False

    @property
    def held_im(self) -> Decimal:
        # Native position IM owns filled exposure. This book reserves only pending parent risk.
        return Decimal("0") if self.canceled else max(Decimal("0"), self.requested_im - self.filled_im)


class MarginReservations:
    def __init__(self) -> None:
        self._by_intent: dict[str, MarginReservation] = {}

    def reserve(self, intent_id: str, requested_im: Decimal) -> None:
        if intent_id in self._by_intent:
            raise ValueError(f"duplicate margin intent: {intent_id}")
        self._by_intent[intent_id] = MarginReservation(requested_im=requested_im)

    def record_fill(self, intent_id: str, filled_im: Decimal) -> None:
        reservation = self._by_intent[intent_id]
        reservation.filled_im += filled_im

    def cancel_remainder(self, intent_id: str) -> None:
        self._by_intent[intent_id].canceled = True

    def total_held_im(self) -> Decimal:
        return sum((item.held_im for item in self._by_intent.values()), Decimal("0"))
