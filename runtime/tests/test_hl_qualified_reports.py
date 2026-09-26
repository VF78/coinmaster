"""Fake Info and real Nautilus order-event report conversion; no network."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from decimal import Decimal

import pytest
from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.model.currencies import USDC
from nautilus_trader.model.enums import LiquiditySide, OrderSide, OrderType, TimeInForce
from nautilus_trader.model.events import OrderAccepted, OrderFilled
from nautilus_trader.model.identifiers import (
    AccountId, ClientId, ClientOrderId, StrategyId, TradeId, TraderId, Venue, VenueOrderId,
)
from nautilus_trader.model.objects import Money, Price, Quantity
from nautilus_trader.model.orders import LimitOrder, MarketOrder

from coinmaster.ops.hl_info_receipt import IncompleteInfoReport, collect_info_receipt
from coinmaster.ops.hl_qualified_reports import qualified_mass_status
from test_hl_info_receipt import ACCOUNT, ANCHOR, BASE, FakeInfo
from test_hl_stageg_sandbox_lifecycle import HL_BTC, HL_SOL


CLIENT = "HLTG-RESTART-PROBE-1"
CLOID = str(nautilus_pyo3.hyperliquid_cloid_from_client_order_id(
    nautilus_pyo3.ClientOrderId(CLIENT)
))
ACCOUNT_ID = AccountId("HYPERLIQUID-master")
TRADER = TraderId("HL-TEST")
STRATEGY = StrategyId("stage-g-recovery-probe")


def raw(*, anchor_qty="0.001", anchor_fee="0.009"):
    data = deepcopy(BASE)
    data["frontendOpenOrders"][0]["cloid"] = CLOID
    data["orderStatus"]["order"]["order"]["cloid"] = CLOID
    data["userFillsByTime"] = [{**ANCHOR, "sz": anchor_qty, "fee": anchor_fee}]
    return data


def receipt(data=None, *, known_oid=7, anchor_tid=9, anchor_ms=100, end_ms=200):
    return asyncio.run(collect_info_receipt(
        FakeInfo(data or raw()), account=ACCOUNT, dex="", anchor_ms=anchor_ms,
        anchor_tid=anchor_tid, end_ms=end_ms,
        expected_orders={CLOID: known_oid}, owned_coins=frozenset({"BTC", "SOL"}),
    ))


def native_order(*, include_prefix=True, include_anchor=True, anchor_qty="0.001"):
    client = ClientOrderId(CLIENT)
    venue = VenueOrderId("7")
    order = LimitOrder(
        TRADER, STRATEGY, HL_BTC.id, client, OrderSide.SELL,
        Quantity.from_str("0.03000"), Price.from_str("60010.0"),
        UUID4(), 90_000_000, time_in_force=TimeInForce.GTC,
        post_only=True, reduce_only=True,
    )
    order.apply(OrderAccepted(
        TRADER, STRATEGY, HL_BTC.id, client, venue, ACCOUNT_ID,
        UUID4(), 90_000_000, 90_000_000,
    ))
    for tid, time, qty, fee in (
        (8, 99, "0.00400", "0.036"),
        (9, 100, anchor_qty, "0.009"),
    ):
        if (tid == 8 and not include_prefix) or (tid == 9 and not include_anchor):
            continue
        order.apply(OrderFilled(
            TRADER, STRATEGY, HL_BTC.id, client, venue, ACCOUNT_ID,
            TradeId(str(tid)), None, OrderSide.SELL, OrderType.LIMIT,
            Quantity.from_str(qty), Price.from_str("60010.0"),
            USDC, Money(Decimal(fee), USDC), LiquiditySide.MAKER,
            UUID4(), time * 1_000_000, time * 1_000_000,
        ))
    return order


def convert(data=None, *, native=None, applied=frozenset({"8", "9"}), known_oid=7):
    anchor = 9 if applied else None
    start = 100 if anchor else 90
    a = receipt(data, known_oid=known_oid, anchor_tid=anchor, anchor_ms=start)
    b = receipt(data, known_oid=known_oid, anchor_tid=anchor, anchor_ms=start, end_ms=201)
    return qualified_mass_status(
        a, b, expected_account_ref=ACCOUNT, expected_dex="",
        account_id=ACCOUNT_ID, client_id=ClientId("HYPERLIQUID"),
        venue=Venue("HYPERLIQUID"), instruments={"BTC": HL_BTC, "SOL": HL_SOL},
        durable_orders={CLIENT: (CLOID, known_oid)}, native_orders=[native] if native else [],
        applied_trade_ids=applied, ts_init=201_000_000,
    )


def test_partial_tp_applied_prefix_and_anchored_suffix_make_native_mass_status():
    order = native_order()
    mass = convert(native=order)
    assert len(mass.order_reports) == 1
    assert sum(map(len, mass.fill_reports.values())) == 2
    assert len(mass.position_reports) == 1
    report = next(iter(mass.order_reports.values()))
    assert report.filled_qty.as_decimal() == Decimal("0.005")
    assert {str(fill.trade_id) for batch in mass.fill_reports.values() for fill in batch} == {"8", "9"}
    assert next(iter(mass.position_reports.values()))[0].quantity.as_decimal() == Decimal("0.025")


def test_missing_persisted_prefix_never_becomes_authoritative():
    with pytest.raises(IncompleteInfoReport, match="APPLIED_PREFIX_NOT_PERSISTED"):
        convert(native=native_order(include_prefix=False))


def test_retained_anchor_must_match_native_fill_economics():
    data = raw(anchor_qty="0.001", anchor_fee="0.010")
    with pytest.raises(IncompleteInfoReport, match="ANCHOR_NATIVE_ECONOMICS_MISMATCH"):
        convert(data, native=native_order())


def test_lost_ack_without_applied_prefix_uses_exact_raw_rows():
    data = raw(anchor_qty="0.005", anchor_fee="0.045")
    mass = convert(data, applied=frozenset(), known_oid=None)
    assert len(mass.order_reports) == len(mass.fill_reports) == len(mass.position_reports) == 1
    assert next(iter(mass.order_reports.values())).filled_qty.as_decimal() == Decimal("0.005")


def test_nonconverged_generation_and_missing_fill_fail_closed():
    first = receipt()
    changed = raw(anchor_qty="0.002")
    second = receipt(changed, end_ms=201)
    with pytest.raises(IncompleteInfoReport, match="INFO_GENERATION_NOT_CONVERGED"):
        qualified_mass_status(
            first, second, expected_account_ref=ACCOUNT, expected_dex="",
            account_id=ACCOUNT_ID, client_id=ClientId("HYPERLIQUID"),
            venue=Venue("HYPERLIQUID"), instruments={"BTC": HL_BTC, "SOL": HL_SOL},
            durable_orders={CLIENT: (CLOID, 7)}, native_orders=[native_order()],
            applied_trade_ids=frozenset({"8", "9"}), ts_init=201_000_000,
        )
    with pytest.raises(IncompleteInfoReport, match="ANCHOR_NOT_IN_APPLIED_PREFIX"):
        convert(native=native_order(include_anchor=False), applied=frozenset({"8"}))

def test_account_economics_changed_between_sweeps_fail_closed():
    first = receipt()
    data = raw()
    data["clearinghouseState"]["marginSummary"]["totalRawUsd"] = "9999"
    second = receipt(data, end_ms=201)
    with pytest.raises(IncompleteInfoReport, match="INFO_GENERATION_NOT_CONVERGED"):
        qualified_mass_status(
            first, second, expected_account_ref=ACCOUNT, expected_dex="",
            account_id=ACCOUNT_ID, client_id=ClientId("HYPERLIQUID"),
            venue=Venue("HYPERLIQUID"), instruments={"BTC": HL_BTC, "SOL": HL_SOL},
            durable_orders={CLIENT: (CLOID, 7)}, native_orders=[native_order()],
            applied_trade_ids=frozenset({"8", "9"}), ts_init=202_000_000,
        )



def test_open_position_mark_only_account_value_change_cannot_qualify_monitor_generation():
    # No order, fill, raw cash, or position-size change: an ordinary mark
    # update moves accountValue while the position stays open. The current
    # exact two-sweep comparator rejects it, so this cannot certify a live
    # periodic monitor for open exposure.
    first = receipt()
    data = raw()
    data["clearinghouseState"]["marginSummary"]["accountValue"] = "9999.20"
    second = receipt(data, end_ms=201)
    assert first.open_orders == second.open_orders
    assert first.order_statuses == second.order_statuses
    assert first.fills == second.fills
    assert first.positions == second.positions
    assert first.account_summary[1] == second.account_summary[1]  # raw cash
    with pytest.raises(IncompleteInfoReport, match="INFO_GENERATION_NOT_CONVERGED"):
        qualified_mass_status(
            first, second, expected_account_ref=ACCOUNT, expected_dex="",
            account_id=ACCOUNT_ID, client_id=ClientId("HYPERLIQUID"),
            venue=Venue("HYPERLIQUID"), instruments={"BTC": HL_BTC, "SOL": HL_SOL},
            durable_orders={CLIENT: (CLOID, 7)}, native_orders=[native_order()],
            applied_trade_ids=frozenset({"8", "9"}), ts_init=202_000_000,
        )


def test_identical_replayed_sweep_does_not_count_as_convergence():
    one = receipt()
    with pytest.raises(IncompleteInfoReport, match="INFO_GENERATION_NOT_CONVERGED"):
        qualified_mass_status(
            one, one, expected_account_ref=ACCOUNT, expected_dex="",
            account_id=ACCOUNT_ID, client_id=ClientId("HYPERLIQUID"),
            venue=Venue("HYPERLIQUID"), instruments={"BTC": HL_BTC, "SOL": HL_SOL},
            durable_orders={CLIENT: (CLOID, 7)}, native_orders=[native_order()],
            applied_trade_ids=frozenset({"8", "9"}), ts_init=202_000_000,
        )


def test_native_order_fill_gap_and_instrument_precision_fail_closed():
    order = native_order()
    data = raw()
    data["frontendOpenOrders"][0]["sz"] = "0.024"
    data["orderStatus"]["order"]["order"]["sz"] = "0.024"
    with pytest.raises(IncompleteInfoReport, match="ORDER_FILL_QUANTITY_GAP"):
        convert(data, native=order)
    data = raw()
    data["userFillsByTime"][0]["px"] = "60010.01"
    with pytest.raises(IncompleteInfoReport, match="BAD_FILL_PRICE_PRECISION"):
        convert(data, native=order)

def test_wrong_account_or_dex_scope_rejects_mass_status():
    first = receipt()
    second = receipt(end_ms=201)
    with pytest.raises(IncompleteInfoReport, match="INFO_ACCOUNT_SCOPE_MISMATCH"):
        qualified_mass_status(
            first, second, expected_account_ref="0x" + "c" * 40, expected_dex="",
            account_id=ACCOUNT_ID, client_id=ClientId("HYPERLIQUID"),
            venue=Venue("HYPERLIQUID"), instruments={"BTC": HL_BTC, "SOL": HL_SOL},
            durable_orders={CLIENT: (CLOID, 7)}, native_orders=[native_order()],
            applied_trade_ids=frozenset({"8", "9"}), ts_init=202_000_000,
        )

@pytest.mark.parametrize(
    ("side", "reduce_only", "position_size"),
    [
        (OrderSide.BUY, False, "0.01000"),
        (OrderSide.SELL, True, "0"),
    ],
)
def test_strategy_market_ioc_wire_limit_maps_to_native_market(side, reduce_only, position_size):
    client = ClientOrderId(CLIENT)
    venue = VenueOrderId("7")
    order = MarketOrder(
        TRADER, STRATEGY, HL_BTC.id, client, side,
        Quantity.from_str("0.01000"), UUID4(), 90_000_000,
        time_in_force=TimeInForce.IOC, reduce_only=reduce_only,
    )
    order.apply(OrderAccepted(
        TRADER, STRATEGY, HL_BTC.id, client, venue, ACCOUNT_ID,
        UUID4(), 90_000_000, 90_000_000,
    ))
    order.apply(OrderFilled(
        TRADER, STRATEGY, HL_BTC.id, client, venue, ACCOUNT_ID,
        TradeId("9"), None, side, OrderType.MARKET,
        Quantity.from_str("0.01000"), Price.from_str("60000.0"),
        USDC, Money(Decimal("0.27"), USDC), LiquiditySide.TAKER,
        UUID4(), 100_000_000, 100_000_000,
    ))
    data = raw(anchor_qty="0.01000", anchor_fee="0.27")
    row = data["orderStatus"]["order"]["order"]
    row.update(
        side="B" if side == OrderSide.BUY else "A",
        origSz="0.01000", sz="0", reduceOnly=reduce_only,
        orderType="Limit", tif="Ioc", limitPx="60200.0",
    )
    data["orderStatus"]["order"]["status"] = "filled"
    data["frontendOpenOrders"] = []
    data["userFillsByTime"][0].update(
        side="B" if side == OrderSide.BUY else "A",
        px="60000.0", crossed=True,
    )
    if position_size == "0":
        data["clearinghouseState"]["assetPositions"] = []
    else:
        data["clearinghouseState"]["assetPositions"][0]["position"].update(
            szi=position_size, entryPx="60000.123456",
        )
    mass = convert(data, native=order, applied=frozenset({"9"}))
    report = next(iter(mass.order_reports.values()))
    assert report.order_type == OrderType.MARKET
    assert report.time_in_force == TimeInForce.IOC
    assert report.price is None
    assert report.reduce_only is reduce_only
    assert report.filled_qty.as_decimal() == Decimal("0.01")
    assert sum(map(len, mass.fill_reports.values())) == 1
    if position_size == "0":
        assert not mass.position_reports
    else:
        position = next(iter(mass.position_reports.values()))[0]
        assert position.avg_px_open == Decimal("60000.123456")


def test_market_wire_shape_and_absent_native_ioc_kind_fail_closed():
    data = raw(anchor_qty="0.005", anchor_fee="0.045")
    row = data["orderStatus"]["order"]["order"]
    row.update(origSz="0.005", sz="0", tif="Ioc", limitPx="60020.0")
    data["orderStatus"]["order"]["status"] = "filled"
    data["frontendOpenOrders"] = []
    with pytest.raises(IncompleteInfoReport, match="NATIVE_IOC_KIND_UNPROVED"):
        convert(data, applied=frozenset(), known_oid=None)
