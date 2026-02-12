from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PositionSizingResult:
    qty: float
    risk_amount: float
    stop_distance: float
    stop_pct: float


def compute_stop_distance(entry: float, structure_stop: float, atr: float, atr_buffer_mult: float, stop_cap_pct: float) -> float:
    raw_distance = abs(entry - structure_stop) + atr * atr_buffer_mult
    cap_distance = entry * stop_cap_pct
    return max(1e-9, min(raw_distance, cap_distance))


def size_position(equity: float, risk_per_trade: float, entry: float, stop_distance: float) -> PositionSizingResult:
    risk_amount = equity * risk_per_trade
    qty = risk_amount / stop_distance if stop_distance > 0 else 0.0
    stop_pct = stop_distance / entry if entry > 0 else 0.0
    return PositionSizingResult(qty=qty, risk_amount=risk_amount, stop_distance=stop_distance, stop_pct=stop_pct)
