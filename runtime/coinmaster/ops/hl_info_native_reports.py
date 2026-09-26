"""Strict, conditional HL Info facts as pinned Nautilus 1.231 report objects.

This adapter does not connect an execution client, seed a native cache, invent
an account balance, or certify automatic recovery. The caller must keep
LiveExecutionEngine reconciliation fenced on any conditional or failed batch.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.reports import FillReport, OrderStatusReport, PositionStatusReport
from nautilus_trader.model.currencies import USDC
from nautilus_trader.model.enums import (
    LiquiditySide, OrderSide, OrderStatus, OrderType, PositionSide, TimeInForce,
)
from nautilus_trader.model.identifiers import (
    AccountId, ClientOrderId, InstrumentId, TradeId, VenueOrderId,
)
from nautilus_trader.model.objects import Money

from coinmaster.ops.hl_info_receipt import IncompleteInfoReport, InfoReceipt


@dataclass(frozen=True)
class NativeInfoReports:
    evidence_state: str
    reason: str
    order_reports: tuple[OrderStatusReport, ...] = ()
    fill_reports: tuple[FillReport, ...] = ()
    position_reports: tuple[PositionStatusReport, ...] = ()
    recovery_required: bool = True
    complete: bool = False

    def require_complete(self) -> None:
        raise IncompleteInfoReport(
            "INFO_REPORT_FAILED" if self.evidence_state == "FAILED"
            else "INFO_CONDITIONAL_NO_ATOMIC_SNAPSHOT"
        )


def _ms(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise IncompleteInfoReport(f"BAD_{name}")
    return value * 1_000_000


def _decimal(value, name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (ValueError, ArithmeticError, TypeError) as exc:
        raise IncompleteInfoReport(f"BAD_{name}") from exc
    if not result.is_finite():
        raise IncompleteInfoReport(f"BAD_{name}")
    return result


def _side(value) -> OrderSide:
    if value == "B":
        return OrderSide.BUY
    if value == "A":
        return OrderSide.SELL
    raise IncompleteInfoReport("BAD_ORDER_SIDE")


def _instrument(cache, coin: str, owned: Mapping[str, InstrumentId]):
    instrument_id = owned.get(coin)
    if instrument_id is None:
        raise IncompleteInfoReport("UNOWNED_INFO_COIN")
    instrument = cache.instrument(instrument_id)
    if instrument is None or instrument.id != instrument_id:
        raise IncompleteInfoReport("NATIVE_INSTRUMENT_MISSING")
    return instrument


def _qty(instrument, value, name: str):
    number = _decimal(value, name)
    if number < 0:
        raise IncompleteInfoReport(f"BAD_{name}")
    native = instrument.make_qty(number)
    if native.as_decimal() != number:
        raise IncompleteInfoReport(f"IMPRECISE_{name}")
    return native


def _px(instrument, value):
    number = _decimal(value, "PRICE")
    if number <= 0:
        raise IncompleteInfoReport("BAD_PRICE")
    native = instrument.make_price(number)
    if native.as_decimal() != number:
        raise IncompleteInfoReport("IMPRECISE_PRICE")
    return native


def _order_kind(row: dict):
    if row.get("orderType") == "Limit":
        tif = row.get("tif")
        if tif in ("Alo", "Gtc", "Ioc"):
            return OrderType.LIMIT, TimeInForce.IOC if tif == "Ioc" else TimeInForce.GTC, tif == "Alo"
    elif row.get("orderType") == "Market" and row.get("tif") == "FrontendMarket":
        return OrderType.MARKET, TimeInForce.IOC, False
    raise IncompleteInfoReport("UNSUPPORTED_INFO_ORDER_SHAPE")


def normalize_info_receipt(
    receipt: InfoReceipt,
    *,
    account_ref: str,
    account_id: AccountId,
    expected_orders: Mapping[str, int | None],
    coin_to_instrument: Mapping[str, InstrumentId],
    cache,
) -> NativeInfoReports:
    """Return native report facts, explicitly conditional on Info completeness."""
    if receipt.account != account_ref or not receipt.conditional_only:
        raise IncompleteInfoReport("INFO_RECEIPT_IDENTITY_MISMATCH")
    if not isinstance(account_id, AccountId) or not expected_orders or not coin_to_instrument:
        raise IncompleteInfoReport("NATIVE_REPORT_SCOPE_MISSING")
    if len(receipt.order_statuses) != len(expected_orders):
        raise IncompleteInfoReport("ORDER_STATUS_SET_INCOMPLETE")
    oid_to_cloid: dict[int, str] = {}
    for cloid, expected_oid in expected_orders.items():
        if not isinstance(cloid, str) or len(cloid) != 34 or not cloid.startswith("0x"):
            raise IncompleteInfoReport("BAD_DURABLE_CLOID")
        for status in receipt.order_statuses:
            order = status.get("order", {}).get("order", {})
            if not isinstance(order, dict):
                raise IncompleteInfoReport("BAD_ORDER_STATUS")
            oid = order.get("oid")
            if order.get("cloid") == cloid or (expected_oid is not None and oid == expected_oid):
                if not isinstance(oid, int) or isinstance(oid, bool) or oid < 0:
                    raise IncompleteInfoReport("BAD_VENUE_OID")
                if expected_oid is not None and oid != expected_oid:
                    raise IncompleteInfoReport("DURABLE_OID_MISMATCH")
                if expected_oid is None and order.get("cloid") != cloid:
                    raise IncompleteInfoReport("LOST_ACK_CLOID_UNPROVED")
                if oid in oid_to_cloid or cloid in oid_to_cloid.values():
                    raise IncompleteInfoReport("DUPLICATE_ORDER_ALIAS")
                oid_to_cloid[oid] = cloid
    if len(oid_to_cloid) != len(expected_orders):
        raise IncompleteInfoReport("ORDER_IDENTITY_SET_INCOMPLETE")
    frontend = {row["oid"]: row for row in receipt.open_orders}
    if len(frontend) != len(receipt.open_orders):
        raise IncompleteInfoReport("DUPLICATE_FRONTEND_ORDER")
    order_reports = []
    for status in receipt.order_statuses:
        wrapper = status["order"]
        row = wrapper["order"]
        oid = row["oid"]
        cloid = oid_to_cloid.get(oid)
        if cloid is None or row.get("isTrigger") is not False:
            raise IncompleteInfoReport("UNOWNED_OR_TRIGGER_ORDER")
        instrument = _instrument(cache, row.get("coin"), coin_to_instrument)
        original = _qty(instrument, row.get("origSz"), "ORIGINAL_SIZE")
        leaves = _qty(instrument, row.get("sz"), "LEAVES")
        if original.as_decimal() <= 0 or leaves.as_decimal() > original.as_decimal():
            raise IncompleteInfoReport("BAD_ORDER_QUANTITY")
        filled = instrument.make_qty(original.as_decimal() - leaves.as_decimal())
        kind, tif, post_only = _order_kind(row)
        if not isinstance(row.get("reduceOnly"), bool):
            raise IncompleteInfoReport("BAD_REDUCE_ONLY")
        state = wrapper.get("status")
        if state == "open":
            if leaves.as_decimal() <= 0:
                raise IncompleteInfoReport("OPEN_ORDER_WITHOUT_LEAVES")
            order_status = OrderStatus.PARTIALLY_FILLED if filled.as_decimal() > 0 else OrderStatus.ACCEPTED
            current = frontend.get(oid)
            if current is None or any(
                current.get(key) != row.get(key)
                for key in ("coin", "side", "origSz", "sz", "reduceOnly", "limitPx")
            ):
                raise IncompleteInfoReport("FRONTEND_ORDER_STATUS_MISMATCH")
        elif state == "filled" and leaves.as_decimal() == 0:
            order_status = OrderStatus.FILLED
        elif state == "canceled":
            order_status = OrderStatus.CANCELED
        else:
            raise IncompleteInfoReport("UNKNOWN_NATIVE_ORDER_STATUS")
        price = _px(instrument, row.get("limitPx")) if kind == OrderType.LIMIT else None
        order_reports.append(OrderStatusReport(
            account_id, instrument.id, VenueOrderId(str(oid)), _side(row.get("side")),
            kind, tif, order_status, original, filled, UUID4(),
            _ms(row.get("timestamp"), "ORDER_TIME"),
            _ms(wrapper.get("statusTimestamp"), "STATUS_TIME"),
            _ms(receipt.end_ms, "OBSERVATION_TIME"),
            client_order_id=ClientOrderId(cloid), price=price,
            post_only=post_only, reduce_only=row["reduceOnly"],
        ))
    if set(frontend) != {
        row["order"]["order"]["oid"] for row in receipt.order_statuses
        if row["order"]["status"] == "open"
    }:
        raise IncompleteInfoReport("FRONTEND_OPEN_SET_MISMATCH")
    fill_reports = []
    for row in receipt.fills:
        oid = row["oid"]
        cloid = oid_to_cloid.get(oid)
        if cloid is None or not isinstance(row.get("crossed"), bool):
            raise IncompleteInfoReport("FILL_OWNERSHIP_OR_LIQUIDITY_UNKNOWN")
        instrument = _instrument(cache, row.get("coin"), coin_to_instrument)
        fee = _decimal(row.get("fee"), "FEE")
        fill_reports.append(FillReport(
            account_id, instrument.id, VenueOrderId(str(oid)), TradeId(str(row["tid"])),
            _side(row.get("side")), _qty(instrument, row.get("sz"), "FILL_SIZE"),
            _px(instrument, row.get("px")), Money(fee, USDC),
            LiquiditySide.TAKER if row["crossed"] else LiquiditySide.MAKER,
            UUID4(), _ms(row.get("time"), "FILL_TIME"),
            _ms(receipt.end_ms, "OBSERVATION_TIME"),
            client_order_id=ClientOrderId(cloid),
        ))
    position_reports = []
    for row in receipt.positions:
        instrument = _instrument(cache, row.get("coin"), coin_to_instrument)
        signed = _decimal(row.get("szi"), "POSITION_SIZE")
        if signed == 0:
            continue
        position_reports.append(PositionStatusReport(
            account_id, instrument.id,
            PositionSide.LONG if signed > 0 else PositionSide.SHORT,
            _qty(instrument, abs(signed), "POSITION_SIZE"), UUID4(),
            _ms(receipt.end_ms, "OBSERVATION_TIME"),
            _ms(receipt.end_ms, "OBSERVATION_TIME"),
        ))
    return NativeInfoReports(
        "CONDITIONAL_ONLY", "INFO_NO_COMMON_SNAPSHOT_OR_COMPLETE_FILL_CURSOR",
        tuple(order_reports), tuple(fill_reports), tuple(position_reports),
    )


def normalize_info_receipt_or_fail(*args, **kwargs) -> NativeInfoReports:
    try:
        return normalize_info_receipt(*args, **kwargs)
    except (IncompleteInfoReport, ValueError) as error:
        return NativeInfoReports("FAILED", str(error))
