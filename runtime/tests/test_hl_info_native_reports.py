"""Fake Info to native reports: conditional evidence never enables takeover."""
from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest
from nautilus_trader.cache.cache import Cache
from nautilus_trader.execution.reports import FillReport, OrderStatusReport, PositionStatusReport
from nautilus_trader.model.enums import LiquiditySide, OrderStatus, PositionSide, TimeInForce
from nautilus_trader.model.identifiers import AccountId

from coinmaster.ops.hl_info_receipt import collect_info_receipt, IncompleteInfoReport
from coinmaster.ops.hl_info_native_reports import normalize_info_receipt, normalize_info_receipt_or_fail
from coinmaster.ops.hl_readonly_observer import ReadOnlyAccountObserver
from test_hl_info_receipt import ACCOUNT, ANCHOR, BASE, CLOID, FakeInfo
from test_hl_stageg_sandbox_lifecycle import HL_BTC, HL_SOL


ACCOUNT_ID = AccountId("HYPERLIQUID-master")
OWNED = {"BTC": HL_BTC.id, "SOL": HL_SOL.id}
EXPECTED = {CLOID: None}


def _data():
    data = deepcopy(BASE)
    data["frontendOpenOrders"][0] = deepcopy(data["frontendOpenOrders"][0])
    order = data["orderStatus"]["order"]["order"]
    order.update(
        isTrigger=False, orderType="Limit", tif="Alo", limitPx="60010.0",
        timestamp=100, reduceOnly=True,
    )
    data["orderStatus"]["order"]["statusTimestamp"] = 101
    data["frontendOpenOrders"][0].update(limitPx="60010.0")
    data["userFillsByTime"][0]["crossed"] = False
    return data


def _cache():
    cache = Cache()
    cache.add_instrument(HL_BTC)
    cache.add_instrument(HL_SOL)
    return cache


def _receipt(fake):
    return asyncio.run(collect_info_receipt(
        fake, account=ACCOUNT, dex="", anchor_ms=100, anchor_tid=9,
        end_ms=200, expected_orders=EXPECTED,
        owned_coins=frozenset(OWNED),
    ))


def _normalized(receipt):
    return normalize_info_receipt(
        receipt, account_ref=ACCOUNT, account_id=ACCOUNT_ID,
        expected_orders=EXPECTED, coin_to_instrument=OWNED, cache=_cache(),
    )


def test_lost_ack_partial_tp_normalizes_to_native_reports_but_stays_conditional():
    receipt = _receipt(FakeInfo(_data()))
    batch = _normalized(receipt)
    assert batch.evidence_state == "CONDITIONAL_ONLY"
    assert batch.recovery_required and not batch.complete
    order, = batch.order_reports
    fill, = batch.fill_reports
    position, = batch.position_reports
    assert isinstance(order, OrderStatusReport)
    assert isinstance(fill, FillReport)
    assert isinstance(position, PositionStatusReport)
    assert str(order.client_order_id) == CLOID
    assert str(order.venue_order_id) == "7"
    assert order.order_status == OrderStatus.PARTIALLY_FILLED
    assert order.time_in_force == TimeInForce.GTC
    assert order.post_only and order.reduce_only
    assert str(order.quantity) == "0.03000"
    assert str(order.filled_qty) == "0.00500"
    assert str(fill.trade_id) == "9"
    assert fill.liquidity_side == LiquiditySide.MAKER
    assert str(fill.commission) == "0.04500000 USDC"
    assert position.position_side == PositionSide.LONG
    assert str(position.quantity) == "0.02500"
    with pytest.raises(IncompleteInfoReport, match="NO_ATOMIC_SNAPSHOT"):
        batch.require_complete()


def test_disconnect_restart_reconnect_keeps_conditional_reports_and_no_replay():
    fake = FakeInfo(_data())
    async def scenario():
        class RoleFake(FakeInfo):
            async def __call__(self, body):
                if body["type"] == "userRole":
                    return {"role": "user"}
                return await super().__call__(body)
        info = RoleFake(_data())
        observer = ReadOnlyAccountObserver(
            account_ref=ACCOUNT, info=info, dex="", anchor_ms=100, anchor_tid=9,
            expected_orders=EXPECTED, owned_coins=frozenset(OWNED),
        )
        assert (await observer.observe(now_ms=200)).evidence_state == "CONDITIONAL_ONLY"
        observer.disconnect()
        assert observer.status(now_ms=201).connection_state == "RECOVERY_REQUIRED"
        # A restarted observer has no prior receipt and cannot grant recovery.
        restarted = ReadOnlyAccountObserver(
            account_ref=ACCOUNT, info=info, dex="", anchor_ms=100, anchor_tid=9,
            expected_orders=EXPECTED, owned_coins=frozenset(OWNED),
        )
        assert restarted.status(now_ms=201).evidence_state == "UNKNOWN"
        assert (await restarted.observe(now_ms=202)).recovery_required
    asyncio.run(scenario())
    first = _normalized(_receipt(fake))
    second = _normalized(_receipt(fake))
    assert [str(item.trade_id) for item in first.fill_reports] == ["9"]
    assert [str(item.trade_id) for item in second.fill_reports] == ["9"]
    assert [str(item.client_order_id) for item in first.order_reports] == [CLOID]
    assert not first.complete and not second.complete
    assert all(body["type"] in {"frontendOpenOrders", "clearinghouseState", "orderStatus", "userFillsByTime"} for body in fake.calls)


@pytest.mark.parametrize("fault", ["missing_crossed", "wrong_frontend_size", "wrong_cloid", "unknown_coin", "missing_status_time"])
def test_bad_or_external_report_fails_closed(fault):
    data = _data()
    if fault == "missing_crossed":
        data["userFillsByTime"][0].pop("crossed")
    elif fault == "wrong_frontend_size":
        data["frontendOpenOrders"][0]["sz"] = "0.020"
    elif fault == "wrong_cloid":
        data["orderStatus"]["order"]["order"]["cloid"] = "0x" + "c" * 32
    elif fault == "unknown_coin":
        data["clearinghouseState"]["assetPositions"][0]["position"]["coin"] = "ETH"
    elif fault == "missing_status_time":
        data["orderStatus"]["order"].pop("statusTimestamp")
    try:
        receipt = _receipt(FakeInfo(data))
    except IncompleteInfoReport:
        return
    batch = normalize_info_receipt_or_fail(
        receipt, account_ref=ACCOUNT, account_id=ACCOUNT_ID,
        expected_orders=EXPECTED, coin_to_instrument=OWNED, cache=_cache(),
    )
    assert batch.evidence_state == "FAILED"
    assert batch.recovery_required and not batch.complete
    assert not batch.order_reports and not batch.fill_reports and not batch.position_reports
    with pytest.raises(IncompleteInfoReport, match="INFO_REPORT_FAILED"):
        batch.require_complete()
