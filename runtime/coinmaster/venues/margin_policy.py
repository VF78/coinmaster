"""Public-profile margin policies for native strategy risk gates.

This module deliberately has no dependency on research fixtures or Bybit
profiles.  A policy consumes only an explicit public mark and a local Sandbox
leverage selection; it does not claim to know a real Hyperliquid account.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from nautilus_trader.model.identifiers import InstrumentId

from coinmaster.venues.hyperliquid_profile import HyperliquidVenueProfile
from coinmaster.venues.production_preflight import ProductionVenuePreflight


@dataclass(frozen=True)
class MarginMark:
    instrument_id: InstrumentId
    price: Decimal
    ts_event: int


class MarginPolicy(Protocol):
    """Minimal injected interface used by the strategy risk gate."""

    def margin_for(self, instrument_id: InstrumentId, quantity: Decimal, ts_now: int) -> tuple[Decimal, Decimal, Decimal]: ...


class HyperliquidSandboxMarginPolicy:
    """Current public HL tiers applied to an explicitly local Sandbox model.

    ``selected_leverage`` is a Sandbox configuration choice, not a claim about
    a Hyperliquid account's cross/isolated leverage.  Both native instrument
    IDs and public profile IDs must match exactly.
    """

    def __init__(
        self,
        profile: HyperliquidVenueProfile,
        selected_leverage: dict[InstrumentId, Decimal],
        max_mark_age_ns: int,
    ) -> None:
        if max_mark_age_ns < 0:
            raise ValueError("max mark age must be non-negative")
        self._profile = profile
        self._selected_leverage = dict(selected_leverage)
        self._max_mark_age_ns = max_mark_age_ns
        self._marks: dict[InstrumentId, MarginMark] = {}

    def update_mark(self, mark: MarginMark) -> None:
        if mark.price <= 0:
            raise ValueError("non-positive public mark")
        previous = self._marks.get(mark.instrument_id)
        if previous is None or mark.ts_event >= previous.ts_event:
            self._marks[mark.instrument_id] = mark

    def margin_for(self, instrument_id: InstrumentId, quantity: Decimal, ts_now: int) -> tuple[Decimal, Decimal, Decimal]:
        leverage = self._selected_leverage.get(instrument_id)
        mark = self._marks.get(instrument_id)
        profile_id = str(instrument_id)
        instrument = self._profile.instruments.get(profile_id)
        if leverage is None or leverage <= 0 or instrument is None or mark is None:
            raise ValueError("missing explicit sandbox leverage, public profile, or mark")
        if mark.ts_event > ts_now or ts_now - mark.ts_event > self._max_mark_age_ns:
            raise ValueError("stale public mark")
        notional = abs(quantity) * mark.price
        tier = max((item for item in instrument.margin_tiers if item.lower_bound <= notional), key=lambda item: item.lower_bound)
        if leverage > tier.max_leverage:
            raise ValueError("selected sandbox leverage exceeds public tier")
        initial = notional / leverage
        maintenance = ProductionVenuePreflight._maintenance_margin(instrument.margin_tiers, notional)
        return initial, maintenance, mark.price
