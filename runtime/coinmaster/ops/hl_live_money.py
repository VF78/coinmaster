"""Perps-only live money view from one strict, reconciled Hyperliquid Info receipt.

This does not post cash, funding, fees or PnL. Venue accountValue already
includes position value and all venue cash effects; adding native UPNL again
would double count. Unsupported account abstraction/margin modes fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Sequence

from nautilus_trader.model.currencies import USDC

from coinmaster.ops.hl_info_receipt import InfoReceipt, IncompleteInfoReport


def _amount(value: str, name: str) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise IncompleteInfoReport("LIVE_MONEY_BAD_" + name) from exc
    if not result.is_finite():
        raise IncompleteInfoReport("LIVE_MONEY_BAD_" + name)
    return result


@dataclass(frozen=True)
class LivePerpsMoneyView:
    account: str
    dex: str
    end_ms: int
    equity: Decimal
    free_collateral: Decimal
    margin_used: Decimal
    raw_usd: Decimal

    def require_fresh(self, now_ms: int, max_age_ms: int) -> None:
        if (
            not isinstance(now_ms, int) or not isinstance(max_age_ms, int)
            or max_age_ms <= 0 or self.end_ms > now_ms + 1
            or now_ms - self.end_ms > max_age_ms
        ):
            raise IncompleteInfoReport("LIVE_MONEY_STALE_OR_UNKNOWN")


def live_perps_money_view(
    receipt: InfoReceipt, *, account_ref: str, dex: str, account_id: str,
    native_account, native_positions: Sequence[object], now_ms: int,
    max_age_ms: int = 10_000,
) -> LivePerpsMoneyView:
    if (
        not isinstance(receipt, InfoReceipt)
        or receipt.account.lower() != account_ref.lower() or receipt.dex != dex
        or receipt.account_role != "user" or receipt.abstraction != "disabled"
        or receipt.dex_abstraction is not False
        or len(receipt.account_summary) != 5
        or len(receipt.cross_account_summary) != 4
    ):
        raise IncompleteInfoReport("LIVE_MONEY_ACCOUNT_SCOPE_OR_MODE_UNKNOWN")
    equity, raw, margin, notional, free = (
        _amount(value, name) for value, name in zip(
            receipt.account_summary,
            ("EQUITY", "RAW_USD", "MARGIN", "NOTIONAL", "WITHDRAWABLE"),
        )
    )
    cross_equity, cross_raw, cross_margin, cross_notional = (
        _amount(value, name) for value, name in zip(
            receipt.cross_account_summary,
            ("CROSS_EQUITY", "CROSS_RAW_USD", "CROSS_MARGIN", "CROSS_NOTIONAL"),
        )
    )
    # A standard account with only cross-margin positions has identical
    # total/cross summaries. Isolated collateral cannot be mapped by this view.
    if (
        (equity, raw, margin, notional) !=
        (cross_equity, cross_raw, cross_margin, cross_notional)
        or equity <= 0 or margin < 0 or notional < 0 or free < 0
        or free > equity
    ):
        raise IncompleteInfoReport("LIVE_MONEY_SUMMARY_INCONSISTENT")
    if native_account is None or str(native_account.id) != account_id or native_account.base_currency is not None:
        raise IncompleteInfoReport("LIVE_MONEY_NATIVE_ACCOUNT_MISMATCH")
    native_total = native_account.balance_total(USDC)
    native_free = native_account.balance_free(USDC)
    # Pinned 1.231 Rust maps cross totalRawUsd through a nonnegative clamp
    # and raises total to withdrawable; that total is not venue equity.
    if (
        native_total is None or native_free is None
        or native_total.currency != USDC or native_free.currency != USDC
        or native_total.as_decimal() != max(cross_raw, free, Decimal("0"))
        or native_free.as_decimal() != free
    ):
        raise IncompleteInfoReport("LIVE_MONEY_NATIVE_BALANCE_MISMATCH")
    raw_positions = {}
    position_notional = Decimal("0")
    for row in receipt.positions:
        size = _amount(row["szi"], "POSITION_SIZE")
        if size == 0:
            continue
        leverage = row.get("leverage")
        if not isinstance(leverage, dict) or leverage.get("type") != "cross":
            raise IncompleteInfoReport("LIVE_MONEY_ISOLATED_POSITION_UNSUPPORTED")
        entry = _amount(row.get("entryPx"), "POSITION_ENTRY")
        value = _amount(row.get("positionValue"), "POSITION_VALUE")
        upnl = _amount(row.get("unrealizedPnl"), "POSITION_UPNL")
        if entry <= 0 or value <= 0 or abs(
            upnl - (value - abs(size) * entry) * (1 if size > 0 else -1)
        ) > Decimal("0.000001"):
            raise IncompleteInfoReport("LIVE_MONEY_POSITION_UPNL_MISMATCH")
        position_notional += value
        coin = row["coin"]
        if coin in raw_positions:
            raise IncompleteInfoReport("LIVE_MONEY_DUPLICATE_POSITION")
        raw_positions[coin] = size
    native = {}
    for position in native_positions:
        if str(position.account_id) != account_id:
            raise IncompleteInfoReport("LIVE_MONEY_NATIVE_POSITION_ACCOUNT")
        coin = str(position.instrument_id).split("-USD-PERP.")[0]
        if coin in native or coin not in {"BTC", "SOL"}:
            raise IncompleteInfoReport("LIVE_MONEY_NATIVE_POSITION_SCOPE")
        qty = position.quantity.as_decimal()
        native[coin] = qty if position.is_long else -qty
    if position_notional != notional:
        raise IncompleteInfoReport("LIVE_MONEY_NOTIONAL_POSITION_MISMATCH")
    if raw_positions != native:
        raise IncompleteInfoReport("LIVE_MONEY_POSITION_MISMATCH")
    view = LivePerpsMoneyView(account_ref, dex, receipt.end_ms, equity, free, margin, raw)
    view.require_fresh(now_ms, max_age_ms)
    return view
