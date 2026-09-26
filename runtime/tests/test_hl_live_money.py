"""Strict live-only HL account money mapping, with no exchange calls."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

import pytest
from nautilus_trader.accounting.accounts.margin import MarginAccount
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.model.currencies import USDC
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.events import AccountState
from nautilus_trader.model.identifiers import AccountId, InstrumentId
from nautilus_trader.model.objects import AccountBalance, Money, Quantity

from coinmaster.ops.hl_info_receipt import InfoReceipt, IncompleteInfoReport
from coinmaster.ops.hl_live_money import live_perps_money_view
from coinmaster.strategy.live_recovery import RecoverableWaveOverlayStrategy
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from test_live_recovery_state import _strategy

REF = "0x" + "a" * 40
ACCOUNT = "HYPERLIQUID-master"


def receipt(*, equity="10000", raw="10000", margin="0", notional="0",
            free="10000", positions=(), fills=(), orders=()):
    return InfoReceipt(
        REF, "", 1, 100, orders, positions, fills, (),
        account_summary=(equity, raw, margin, notional, free),
        cross_account_summary=(equity, raw, margin, notional),
        account_role="user", abstraction="disabled", dex_abstraction=False,
    )


def native_account(total, free):
    locked = Decimal(total) - Decimal(free)
    event = AccountState(
        AccountId(ACCOUNT), AccountType.MARGIN, None, True,
        [AccountBalance(Money(total, USDC), Money(locked, USDC), Money(free, USDC))],
        [], {}, UUID4(), 1, 1,
    )
    return MarginAccount(event)


def native_position(coin, qty, *, long=True):
    return SimpleNamespace(
        account_id=AccountId(ACCOUNT),
        instrument_id=InstrumentId.from_str(f"{coin}-USD-PERP.HYPERLIQUID"),
        quantity=Quantity.from_str(qty), is_long=long,
    )


def view(raw, account, positions=(), now=100):
    return live_perps_money_view(
        raw, account_ref=REF, dex="", account_id=ACCOUNT,
        native_account=account, native_positions=positions,
        now_ms=now, max_age_ms=10,
    )


def test_flat_standard_cross_uses_venue_equity_and_withdrawable():
    result = view(receipt(), native_account("10000", "10000"))
    assert (result.equity, result.free_collateral, result.margin_used) == (
        Decimal("10000"), Decimal("10000"), Decimal("0"),
    )


def test_btc_sol_partial_tp_fees_and_native_clamp_do_not_double_count_upnl():
    positions = (
        {"coin": "BTC", "szi": "0.01000", "entryPx": "60000", "positionValue": "600", "unrealizedPnl": "0", "leverage": {"type": "cross"}},
        {"coin": "SOL", "szi": "-0.200", "entryPx": "250", "positionValue": "50", "unrealizedPnl": "0", "leverage": {"type": "cross"}},
    )
    raw = receipt(
        equity="10009.55", raw="9359.55", margin="80", notional="650",
        free="9950", positions=positions,
        orders=({"coin": "BTC", "oid": 7, "sz": "0.005", "reduceOnly": True},),
        fills=({"coin": "BTC", "tid": 9, "fee": "0.45", "sz": "0.005"},),
    )
    native = (native_position("BTC", "0.01000"), native_position("SOL", "0.200", long=False))
    result = view(raw, native_account("9950", "9950"), native)
    assert result.equity == Decimal("10009.55")
    assert result.free_collateral == Decimal("9950")
    assert result.raw_usd == Decimal("9359.55")
    assert result.equity != Decimal("10009.55") + Decimal("20")  # No native UPNL added.
    strategy = RecoverableWaveOverlayStrategy(_strategy().config)
    strategy.attach_live_money_view(lambda: replace(result, end_ms=__import__("time").time_ns() // 1_000_000))
    strategy.recovery_confirmed = True
    assert strategy._active_marked(None, None) == 10009.55
    assert strategy._free_margin_for_increase(None) == Decimal("9950")


@pytest.mark.parametrize("change,reason", [
    ({"abstraction": "unifiedAccount"}, "ACCOUNT_SCOPE_OR_MODE"),
    ({"abstraction": "portfolioMargin"}, "ACCOUNT_SCOPE_OR_MODE"),
    ({"account_role": "vault"}, "ACCOUNT_SCOPE_OR_MODE"),
    ({"dex_abstraction": True}, "ACCOUNT_SCOPE_OR_MODE"),
    ({"cross_account_summary": ()}, "ACCOUNT_SCOPE_OR_MODE"),
    ({"cross_account_summary": ("9999", "10000", "0", "0")}, "SUMMARY_INCONSISTENT"),
])
def test_unsupported_or_inconsistent_account_fails_closed(change, reason):
    with pytest.raises(IncompleteInfoReport, match=reason):
        view(replace(receipt(), **change), native_account("10000", "10000"))


def test_stale_native_balance_and_isolated_position_fail_closed():
    with pytest.raises(IncompleteInfoReport, match="STALE"):
        view(receipt(), native_account("10000", "10000"), now=111)
    with pytest.raises(IncompleteInfoReport, match="NATIVE_BALANCE_MISMATCH"):
        view(receipt(), native_account("9999", "9999"))
    isolated = ({"coin": "BTC", "szi": "0.01", "leverage": {"type": "isolated"}},)
    with pytest.raises(IncompleteInfoReport, match="ISOLATED_POSITION"):
        view(receipt(positions=isolated), native_account("10000", "10000"), (native_position("BTC", "0.01"),))


def test_live_strategy_does_not_arm_or_submit_local_synthetic_liquidation():
    strategy = RecoverableWaveOverlayStrategy(_strategy().config)
    strategy._check_mark_first_liquidation(123)
    assert strategy._liquidating is False
    strategy._liquidating = True  # Even a restored legacy marker cannot submit.
    strategy.recovery_confirmed = True
    with pytest.raises(RuntimeError, match="LIVE_LOCAL_LIQUIDATION_FORBIDDEN"):
        strategy.on_quote_tick(SimpleNamespace(instrument_id=strategy.config.btc_id))
    assert strategy.recovery_confirmed is False
    assert not strategy._liquidation_orders


def test_mixed_long_short_uses_account_value_without_raw_plus_notional_shortcut():
    # Hyperliquid's official mixed-side cassette disproves a universal
    # accountValue = totalRawUsd + totalNtlPos identity.
    positions = (
        {"coin": "BTC", "szi": "-0.00785", "entryPx": "26951.0",
         "positionValue": "211.64542", "unrealizedPnl": "-0.08007",
         "leverage": {"type": "cross"}},
        {"coin": "SOL", "szi": "7.39", "entryPx": "19.6789",
         "positionValue": "145.5091", "unrealizedPnl": "0.082029",
         "leverage": {"type": "cross"}},
    )
    raw = receipt(
        equity="1182.312496", raw="86.549602", margin="17.857726",
        notional="357.15452", free="1010.57173", positions=positions,
    )
    native = (native_position("BTC", "0.00785", long=False), native_position("SOL", "7.39"))
    result = view(raw, native_account("1010.57173", "1010.57173"), native)
    assert result.equity == Decimal("1182.312496")
    assert result.equity != result.raw_usd + Decimal("357.15452")


def test_negative_native_total_preserved_and_valid_reduction_gate_open(monkeypatch):
    import time

    positions = ({
        "coin": "BTC", "szi": "0.10000", "entryPx": "2000",
        "positionValue": "200", "unrealizedPnl": "0",
        "leverage": {"type": "cross"},
    },)
    raw = receipt(
        equity="100", raw="-100", margin="25", notional="200",
        free="50", positions=positions,
    )
    native = (native_position("BTC", "0.10000"),)
    result = view(raw, native_account("-100", "50"), native)
    assert (result.equity, result.free_collateral, result.raw_usd) == (
        Decimal("100"), Decimal("50"), Decimal("-100"),
    )
    with pytest.raises(IncompleteInfoReport, match="NATIVE_BALANCE_MISMATCH"):
        view(raw, native_account("50", "50"), native)

    strategy = RecoverableWaveOverlayStrategy(_strategy().config)
    strategy.attach_live_money_view(
        lambda: replace(result, end_ms=time.time_ns() // 1_000_000),
    )
    strategy.recovery_confirmed = True
    strategy._feeds_fresh = lambda *_args: True
    monkeypatch.setattr(WaveOverlayStrategy, "_record_submission", lambda *_args, **_kwargs: True)
    assert strategy._record_submission("reduce-only-probe") is True
