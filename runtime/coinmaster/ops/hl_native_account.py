"""Read-only USDC balance view shared by native Sandbox and HL margin accounts.

A pinned 1.231 Hyperliquid account is multi-currency (base_currency=None).
Its USDC balance_total is an adapter-reported collateral figure, not a
verified equity value. Never add position PnL to it or use it as live equity.
"""
from __future__ import annotations

from decimal import Decimal

from nautilus_trader.model.currencies import USDC


def native_usdc_balances(account) -> dict[str, Decimal]:
    """Return exact native account amounts; missing values remain errors."""
    if account is None or account.base_currency not in (None, USDC):
        raise ValueError("NATIVE_USDC_ACCOUNT_MISSING")
    amounts: dict[str, Decimal] = {}
    for name, getter in (
        ("total", account.balance_total),
        ("free", account.balance_free),
        ("locked", account.balance_locked),
    ):
        value = getter(USDC)
        if value is None or value.currency != USDC:
            raise ValueError(f"NATIVE_USDC_{name.upper()}_UNKNOWN")
        amount = value.as_decimal()
        if not amount.is_finite():
            raise ValueError(f"NATIVE_USDC_{name.upper()}_INVALID")
        amounts[name] = amount
    if amounts["total"] != amounts["free"] + amounts["locked"]:
        raise ValueError("NATIVE_USDC_BALANCE_INVARIANT")
    return amounts


def native_live_usdc_projection(account) -> dict[str, str | None]:
    """Expose reported HL balances without fabricating cash or account equity.

    Pinned 1.231 starts from HL `totalRawUsd` but raises a nonnegative total
    to `withdrawable` when free exceeds it. This native total is not the HL
    `accountValue`. Account-wide margin is kept separate from locked.
    """
    amounts = native_usdc_balances(account)
    margin = account.account_margins().get(USDC) if callable(getattr(account, "account_margins", None)) else None
    initial = maintenance = None
    if margin is not None:
        for value in (margin.initial, margin.maintenance):
            if value.currency != USDC or not value.as_decimal().is_finite():
                raise ValueError("NATIVE_USDC_MARGIN_INVALID")
        initial = str(margin.initial.as_decimal())
        maintenance = str(margin.maintenance.as_decimal())
    return {
        "native_balance_total": str(amounts["total"]),
        "native_free": str(amounts["free"]),
        "native_locked": str(amounts["locked"]),
        "native_margin_initial": initial,
        "native_margin_maintenance": maintenance,
        "cash": None,
        "equity": None,
        "money_state": "UNKNOWN_NATIVE_HL_ACCOUNT_VALUE_UNMAPPED",
    }
