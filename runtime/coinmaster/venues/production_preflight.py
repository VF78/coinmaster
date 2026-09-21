"""Venue-neutral production order and margin preflight.

This layer deliberately depends only on a venue profile.  It is not a
Nautilus fixture, a research simulator, or a venue-specific margin module.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class MarginTier:
    lower_bound: Decimal
    max_leverage: Decimal


@dataclass(frozen=True)
class ProductionInstrument:
    instrument_id: str
    quantity_increment: Decimal
    min_quantity: Decimal
    min_notional: Decimal
    max_price_decimals: int
    max_price_significant_figures: int
    max_market_notional: Decimal
    max_limit_notional: Decimal
    margin_tiers: tuple[MarginTier, ...]


@dataclass(frozen=True)
class PreflightDecision:
    allowed: bool
    reason: str | None
    normalized_notional: Decimal | None
    required_initial_margin: Decimal | None
    maintenance_margin: Decimal | None
    applicable_max_leverage: Decimal | None


def _decimal_places(value: Decimal) -> int:
    return max(0, -value.normalize().as_tuple().exponent)


def _significant_figures(value: Decimal) -> int:
    digits = value.normalize().as_tuple().digits
    first = next((index for index, digit in enumerate(digits) if digit), len(digits))
    return len(digits) - first


class ProductionVenuePreflight:
    """Validate an order and its disclosed margin requirements before submit.

    ``available_collateral`` is optional because a public profile cannot know
    a wallet's cross/isolated state.  Omitting it leaves order-format and
    leverage validation usable but correctly refuses an increase as account
    margin is unknown.
    """

    def __init__(self, instruments: dict[str, ProductionInstrument]) -> None:
        self._instruments = dict(instruments)

    def evaluate(
        self,
        *,
        instrument_id: str,
        price: Decimal,
        quantity: Decimal,
        selected_leverage: Decimal,
        order_type: str,
        position_notional_before: Decimal = Decimal("0"),
        available_collateral: Decimal | None = None,
    ) -> PreflightDecision:
        instrument = self._instruments.get(instrument_id)
        if instrument is None:
            return self._reject("UNKNOWN_INSTRUMENT")
        if price <= 0 or quantity <= 0 or selected_leverage <= 0 or position_notional_before < 0:
            return self._reject("NON_POSITIVE_OR_INVALID_INPUT")
        if quantity < instrument.min_quantity:
            return self._reject("MIN_QUANTITY")
        if quantity % instrument.quantity_increment:
            return self._reject("QUANTITY_INCREMENT")
        if _decimal_places(price) > instrument.max_price_decimals:
            return self._reject("PRICE_DECIMALS")
        if price != price.to_integral_value() and _significant_figures(price) > instrument.max_price_significant_figures:
            return self._reject("PRICE_SIGNIFICANT_FIGURES")
        notional = price * quantity
        if notional < instrument.min_notional:
            return self._reject("MIN_NOTIONAL")
        maximum = instrument.max_market_notional if order_type == "market" else instrument.max_limit_notional if order_type == "limit" else None
        if maximum is None:
            return self._reject("UNKNOWN_ORDER_TYPE")
        if notional > maximum:
            return self._reject("MAX_ORDER_NOTIONAL")
        prospective_notional = position_notional_before + notional
        tier = max((item for item in instrument.margin_tiers if item.lower_bound <= prospective_notional), key=lambda item: item.lower_bound)
        if selected_leverage > tier.max_leverage:
            return self._reject("LEVERAGE_EXCEEDS_MARGIN_TIER", tier.max_leverage)
        initial = prospective_notional / selected_leverage
        # Hyperliquid documents maintenance rate as half the maximum initial
        # margin rate for the tier.  Deduction keeps tiers continuous.
        maintenance = self._maintenance_margin(instrument.margin_tiers, prospective_notional)
        if available_collateral is None:
            return self._reject("ACCOUNT_COLLATERAL_UNKNOWN", tier.max_leverage, initial, maintenance, notional)
        if initial > available_collateral:
            return self._reject("INSUFFICIENT_COLLATERAL", tier.max_leverage, initial, maintenance, notional)
        return PreflightDecision(True, None, notional, initial, maintenance, tier.max_leverage)

    @staticmethod
    def _maintenance_margin(tiers: tuple[MarginTier, ...], notional: Decimal) -> Decimal:
        applicable = max((tier for tier in tiers if tier.lower_bound <= notional), key=lambda item: item.lower_bound)
        rate = Decimal("1") / applicable.max_leverage / Decimal("2")
        deduction = Decimal("0")
        prior_rate = Decimal("0")
        for tier in tiers:
            if tier.lower_bound > applicable.lower_bound:
                break
            current_rate = Decimal("1") / tier.max_leverage / Decimal("2")
            deduction += tier.lower_bound * (current_rate - prior_rate)
            prior_rate = current_rate
        return max(Decimal("0"), notional * rate - deduction)

    @staticmethod
    def _reject(
        reason: str,
        maximum_leverage: Decimal | None = None,
        initial: Decimal | None = None,
        maintenance: Decimal | None = None,
        notional: Decimal | None = None,
    ) -> PreflightDecision:
        return PreflightDecision(False, reason, notional, initial, maintenance, maximum_leverage)
