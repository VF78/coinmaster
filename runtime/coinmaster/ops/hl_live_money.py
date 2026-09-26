"""Perps-only live money view from one strict, reconciled Hyperliquid Info receipt.

This does not post cash, funding, fees or PnL. Venue accountValue already
includes position value and all venue cash effects; adding native UPNL again
would double count. Unsupported account abstraction/margin modes fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Awaitable, Callable, Sequence

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
class SelectedCrossAsset:
    coin: str
    leverage: int
    mark: Decimal


async def collect_selected_cross_assets(
    info: Callable[[dict[str, Any]], Awaitable[Any]], *,
    account_ref: str, coins: frozenset[str],
) -> tuple[SelectedCrossAsset, ...]:
    """Read the selected account's leverage/mark, never side-indexed capacity."""
    if not coins or not coins.issubset({"BTC", "SOL"}):
        raise IncompleteInfoReport("LIVE_ASSET_SCOPE_UNKNOWN")
    selected = []
    for coin in sorted(coins):
        try:
            raw = await info({"type": "activeAssetData", "user": account_ref, "coin": coin})
        except IncompleteInfoReport:
            raise
        except Exception as exc:
            raise IncompleteInfoReport("LIVE_ASSET_TRANSPORT_FAILED") from exc
        if (
            not isinstance(raw, dict) or not isinstance(raw.get("user"), str)
            or raw["user"].lower() != account_ref.lower()
            or raw.get("coin") != coin or not isinstance(raw.get("leverage"), dict)
            or raw["leverage"].get("type") != "cross"
            or type(raw["leverage"].get("value")) is not int
            or raw["leverage"]["value"] <= 0
        ):
            raise IncompleteInfoReport("LIVE_ASSET_ACCOUNT_OR_LEVERAGE_UNKNOWN")
        mark = _amount(raw.get("markPx"), "SELECTED_MARK")
        if mark <= 0:
            raise IncompleteInfoReport("LIVE_ASSET_MARK_UNKNOWN")
        selected.append(SelectedCrossAsset(coin, raw["leverage"]["value"], mark))
    return tuple(selected)


@dataclass(frozen=True)
class LivePerpsMoneyView:
    account: str
    dex: str
    end_ms: int
    equity: Decimal
    free_collateral: Decimal
    margin_used: Decimal
    raw_usd: Decimal
    selected_assets: tuple[SelectedCrossAsset, ...] = ()
    position_sizes: tuple[tuple[str, Decimal], ...] = ()
    native_revision: int | None = None

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
    max_age_ms: int = 10_000, selected_assets: tuple[SelectedCrossAsset, ...] = (),
    native_revision: int | None = None,
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
    # Pinned 1.231 preserves negative cross totalRawUsd. It only raises
    # nonnegative total to withdrawable; neither projection is venue equity.
    if (
        native_total is None or native_free is None
        or native_total.currency != USDC or native_free.currency != USDC
        or native_total.as_decimal() != (cross_raw if cross_raw < 0 else max(cross_raw, free))
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
    if selected_assets and (
        len(selected_assets) != 2 or {item.coin for item in selected_assets} != {"BTC", "SOL"}
    ):
        raise IncompleteInfoReport("LIVE_ASSET_SCOPE_UNKNOWN")
    view = LivePerpsMoneyView(
        account_ref, dex, receipt.end_ms, equity, free, margin, raw,
        selected_assets, tuple(sorted(raw_positions.items())), native_revision,
    )
    view.require_fresh(now_ms, max_age_ms)
    return view



def prospective_cross_margin_ok(
    view: LivePerpsMoneyView, *,
    positions: dict[str, Decimal],
    pending_openings: Sequence[tuple[str, str, Decimal]],
    coin: str, side: str, quantity: Decimal,
    max_gross_multiple: Decimal,
    fee_reserve_rate: Decimal = Decimal("0.0005"),
) -> bool:
    """Total worst-side IM plus opening costs against venue equity, not withdrawable."""
    assets = {item.coin: item for item in view.selected_assets}
    if (
        set(assets) != {"BTC", "SOL"} or set(positions) - set(assets)
        or coin not in assets or side not in {"BUY", "SELL"}
        or not quantity.is_finite() or quantity <= 0
        or not fee_reserve_rate.is_finite() or fee_reserve_rate < Decimal("0.00045")
        or max_gross_multiple <= 0
    ):
        return False
    buys = {name: Decimal("0") for name in assets}
    sells = {name: Decimal("0") for name in assets}
    fees_notional = quantity * assets[coin].mark
    for pending_coin, pending_side, leaves in pending_openings:
        if (
            pending_coin not in assets or pending_side not in {"BUY", "SELL"}
            or not leaves.is_finite() or leaves <= 0
        ):
            return False
        (buys if pending_side == "BUY" else sells)[pending_coin] += leaves
        fees_notional += leaves * assets[pending_coin].mark
    (buys if side == "BUY" else sells)[coin] += quantity
    prospective_im = gross = Decimal("0")
    for name, asset in assets.items():
        current = positions.get(name, Decimal("0"))
        if not current.is_finite() or asset.mark <= 0 or asset.leverage <= 0:
            return False
        worst = max(abs(current + buys[name]), abs(current - sells[name]))
        prospective_im += worst * asset.mark / asset.leverage
        gross += worst * asset.mark
    # totalMarginUsed is a floor for native margin not explained by our
    # selected BTC/SOL model. Never subtract existing IM from accountValue twice.
    required = max(view.margin_used, prospective_im)
    return (
        required + fees_notional * fee_reserve_rate <= view.equity
        and gross <= view.equity * max_gross_multiple
    )
