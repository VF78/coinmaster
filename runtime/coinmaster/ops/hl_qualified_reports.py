"""Strict Info-to-native report boundary for a bounded reconciliation generation.

The caller owns the read-only Info transport and the durable native cache.
This module never sends orders, mutates the cache, posts PnL, or declares
recovery healthy. Rejected generations produce no ExecutionMassStatus.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Mapping, Sequence

from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.reports import (
    ExecutionMassStatus, FillReport, OrderStatusReport, PositionStatusReport,
)
from nautilus_trader.model.currencies import USDC
from nautilus_trader.model.enums import (
    LiquiditySide, OrderSide, OrderStatus, OrderType, PositionSide, TimeInForce,
)
from nautilus_trader.model.identifiers import (
    AccountId, ClientId, ClientOrderId, TradeId, Venue, VenueOrderId,
)
from nautilus_trader.model.objects import Money, Price, Quantity

from coinmaster.ops.hl_info_receipt import InfoReceipt, IncompleteInfoReport


def _precise(value: object, precision: int, label: str) -> Decimal:
    number = Decimal(str(value))
    if not number.is_finite() or number != number.quantize(Decimal(1).scaleb(-precision)):
        raise IncompleteInfoReport(f"BAD_{label}_PRECISION")
    return number


def _same_generation(first: InfoReceipt, second: InfoReceipt) -> None:
    # A genuinely later, overlapping read must repeat execution structure.
    # Mark/equity/collateral fields may move between Info calls; the latest
    # values are checked against the native account after conversion.
    def position_structure(rows: tuple[dict, ...]) -> tuple:
        return tuple((row.get("coin"), row.get("szi"), row.get("entryPx"), row.get("leverage")) for row in rows)
    # Comparing dataclass equality would require identical end_ms and could
    # accidentally certify a replay of one response as two observations.
    if (
        first.start_ms != second.start_ms
        or not first.start_ms < first.end_ms < second.end_ms
        or first.account != second.account or first.dex != second.dex
        or first.anchor_tid != second.anchor_tid
        or first.fill_anchor_proven != second.fill_anchor_proven
        or first.open_orders != second.open_orders
        or first.order_statuses != second.order_statuses
        or position_structure(first.positions) != position_structure(second.positions)
        or first.fills != second.fills
        or first.account_role != second.account_role
        or first.abstraction != second.abstraction
        or first.dex_abstraction != second.dex_abstraction
    ):
        raise IncompleteInfoReport("INFO_GENERATION_NOT_CONVERGED")


def qualified_mass_status(
    first: InfoReceipt,
    second: InfoReceipt,
    *,
    expected_account_ref: str,
    expected_dex: str,
    account_id: AccountId,
    client_id: ClientId,
    venue: Venue,
    instruments: Mapping[str, object],
    durable_orders: Mapping[str, tuple[str, int | None]],
    native_orders: Sequence[object],
    applied_trade_ids: frozenset[str],
    ts_init: int,
) -> ExecutionMassStatus:
    """Convert two converged strict generations; require exact native fill prefix.

    durable_orders maps native ClientOrderId to (derived CLOID, known OID).
    The native order cache must include every applied fill, including those
    before the retained Info anchor. Missing economics are never inferred
    from the TID-only journal.
    """
    _same_generation(first, second)
    receipt = second
    if (
        receipt.account.lower() != expected_account_ref.lower()
        or receipt.dex != expected_dex
        or not expected_account_ref.startswith("0x")
        or len(expected_account_ref) != 42
    ):
        raise IncompleteInfoReport("INFO_ACCOUNT_SCOPE_MISMATCH")
    if not instruments or not set(instruments).issubset({"BTC", "SOL"}):
        raise IncompleteInfoReport("BAD_INSTRUMENT_SCOPE")
    if not isinstance(ts_init, int) or ts_init <= 0:
        raise IncompleteInfoReport("BAD_REPORT_TIME")
    if not isinstance(applied_trade_ids, frozenset):
        raise IncompleteInfoReport("BAD_APPLIED_PREFIX")
    if receipt.fill_anchor_proven and str(receipt.anchor_tid) not in applied_trade_ids:
        raise IncompleteInfoReport("ANCHOR_NOT_IN_APPLIED_PREFIX")
    cloid_clients: dict[str, str] = {}
    known_oids: dict[int, str] = {}
    for client, (cloid, oid) in durable_orders.items():
        derived = nautilus_pyo3.hyperliquid_cloid_from_client_order_id(
            nautilus_pyo3.ClientOrderId(client)
        )
        if str(derived).lower() != cloid.lower() or cloid.lower() in cloid_clients:
            raise IncompleteInfoReport("DURABLE_CLOID_MISMATCH")
        cloid_clients[cloid.lower()] = client
        if oid is not None:
            if oid in known_oids:
                raise IncompleteInfoReport("DUPLICATE_DURABLE_OID")
            known_oids[oid] = client
    if len(receipt.order_statuses) != len(durable_orders):
        raise IncompleteInfoReport("DURABLE_STATUS_SET_MISMATCH")

    order_rows: dict[str, tuple[dict, str, int]] = {}
    oid_clients: dict[int, str] = {}
    for status in receipt.order_statuses:
        item = status["order"]
        row = item["order"]
        oid = row["oid"]
        client = cloid_clients.get(str(row.get("cloid", "")).lower())
        if client is None:
            client = known_oids.get(oid)
        if client is None or client in order_rows or (durable_orders[client][1] not in (None, oid)):
            raise IncompleteInfoReport("ORDER_DURABLE_IDENTITY_MISMATCH")
        coin = row["coin"]
        if coin not in instruments or oid in oid_clients:
            raise IncompleteInfoReport("ORDER_INSTRUMENT_OR_OID_MISMATCH")
        order_rows[client] = (row, item["status"], item["statusTimestamp"])
        oid_clients[oid] = client
    if set(order_rows) != set(durable_orders):
        raise IncompleteInfoReport("DURABLE_STATUS_SET_MISMATCH")

    native_by_client: dict[str, object] = {}
    native_types: dict[str, OrderType] = {}
    prefix: dict[str, object] = {}
    for order in native_orders:
        client = str(order.client_order_id)
        if client not in durable_orders or client in native_by_client:
            raise IncompleteInfoReport("NATIVE_ORDER_SET_MISMATCH")
        native_by_client[client] = order
        row, _, _ = order_rows[client]
        instrument = instruments[row["coin"]]
        tif = TimeInForce.IOC if row["tif"] == "Ioc" else TimeInForce.GTC
        side = OrderSide.BUY if row["side"] == "B" else OrderSide.SELL
        native_type = order.order_type
        if native_type not in (OrderType.LIMIT, OrderType.MARKET):
            raise IncompleteInfoReport("NATIVE_ORDER_TYPE_UNSUPPORTED")
        if (
            order.instrument_id != instrument.id
            or order.side != side
            or order.time_in_force != tif
            or Decimal(str(order.quantity)) != Decimal(row["origSz"])
            or bool(order.is_reduce_only) != row["reduceOnly"]
            or (order.venue_order_id is not None and str(order.venue_order_id) != str(row["oid"]))
        ):
            raise IncompleteInfoReport("NATIVE_ORDER_SHAPE_MISMATCH")
        if native_type == OrderType.MARKET:
            # The pinned adapter submits native MARKET/IOC as a protective
            # venue Limit/Ioc. The calculated wire price is not order.price.
            if row["orderType"] != "Limit" or row["tif"] != "Ioc" or order.is_post_only or order.has_price:
                raise IncompleteInfoReport("MARKET_WIRE_SHAPE_MISMATCH")
        elif (
            Decimal(str(order.price)) != Decimal(row["limitPx"])
            or bool(order.is_post_only) != (row["tif"] == "Alo")
        ):
            raise IncompleteInfoReport("NATIVE_ORDER_SHAPE_MISMATCH")
        native_types[client] = native_type
        for event in order.events:
            if not hasattr(event, "trade_id"):
                continue
            tid = str(event.trade_id)
            if tid in prefix:
                raise IncompleteInfoReport("DUPLICATE_NATIVE_FILL")
            if (
                str(event.client_order_id) != client
                or str(event.venue_order_id) != str(row["oid"])
                or event.instrument_id != instrument.id
                or event.account_id != account_id
            ):
                raise IncompleteInfoReport("NATIVE_FILL_IDENTITY_MISMATCH")
            if tid in applied_trade_ids:
                prefix[tid] = event
            elif event.ts_event // 1_000_000 < receipt.start_ms:
                raise IncompleteInfoReport("UNAPPLIED_FILL_BEFORE_ANCHOR")
    if set(prefix) != applied_trade_ids:
        raise IncompleteInfoReport("APPLIED_PREFIX_NOT_PERSISTED")

    reports: dict[str, FillReport] = {}
    fill_qty = defaultdict(lambda: Decimal("0"))
    for tid, event in prefix.items():
        client = str(event.client_order_id)
        row, _, _ = order_rows[client]
        instrument = instruments[row["coin"]]
        qty = _precise(event.last_qty, instrument.size_precision, "NATIVE_FILL_SIZE")
        px = _precise(event.last_px, instrument.price_precision, "NATIVE_FILL_PRICE")
        if event.commission.currency != USDC or event.order_side != (OrderSide.BUY if row["side"] == "B" else OrderSide.SELL):
            raise IncompleteInfoReport("NATIVE_FILL_ECONOMICS_MISMATCH")
        reports[tid] = FillReport(
            account_id, instrument.id, VenueOrderId(str(row["oid"])), TradeId(tid),
            event.order_side, Quantity.from_str(str(qty)), Price.from_str(str(px)),
            event.commission, event.liquidity_side, UUID4(), event.ts_event, ts_init,
            client_order_id=ClientOrderId(client),
        )
        fill_qty[client] += qty

    for raw in receipt.fills:
        tid = str(raw["tid"])
        client = oid_clients[raw["oid"]]
        row, _, _ = order_rows[client]
        instrument = instruments[row["coin"]]
        qty = _precise(raw["sz"], instrument.size_precision, "FILL_SIZE")
        px = _precise(raw["px"], instrument.price_precision, "FILL_PRICE")
        fee = Decimal(str(raw["fee"]))
        side = OrderSide.BUY if raw["side"] == "B" else OrderSide.SELL
        liquidity = LiquiditySide.TAKER if raw["crossed"] else LiquiditySide.MAKER
        if side != (OrderSide.BUY if row["side"] == "B" else OrderSide.SELL):
            raise IncompleteInfoReport("FILL_ORDER_SIDE_MISMATCH")
        previous = reports.get(tid)
        if previous is not None:
            if (
                previous.client_order_id != ClientOrderId(client)
                or previous.last_qty.as_decimal() != qty
                or previous.last_px.as_decimal() != px
                or previous.commission.as_decimal() != fee
                or previous.liquidity_side != liquidity
                or previous.ts_event != raw["time"] * 1_000_000
            ):
                raise IncompleteInfoReport("ANCHOR_NATIVE_ECONOMICS_MISMATCH")
            continue
        reports[tid] = FillReport(
            account_id, instrument.id, VenueOrderId(str(raw["oid"])), TradeId(tid),
            side, Quantity.from_str(str(qty)), Price.from_str(str(px)),
            Money(fee, USDC), liquidity, UUID4(), raw["time"] * 1_000_000, ts_init,
            client_order_id=ClientOrderId(client),
        )
        fill_qty[client] += qty

    orders = []
    for client, (row, status, status_ms) in order_rows.items():
        instrument = instruments[row["coin"]]
        total = _precise(row["origSz"], instrument.size_precision, "ORDER_SIZE")
        leaves = _precise(row["sz"], instrument.size_precision, "ORDER_LEAVES")
        px = _precise(row["limitPx"], instrument.price_precision, "ORDER_PRICE")
        if fill_qty[client] != total - leaves:
            raise IncompleteInfoReport("ORDER_FILL_QUANTITY_GAP")
        order_status = (
            OrderStatus.PARTIALLY_FILLED if fill_qty[client] else OrderStatus.ACCEPTED
        ) if status == "open" else (
            OrderStatus.FILLED if status == "filled" else OrderStatus.CANCELED
        )
        native_type = native_types.get(client)
        if native_type is None:
            # Raw Limit/Ioc cannot identify an absent native MARKET intent.
            if row["tif"] == "Ioc":
                raise IncompleteInfoReport("NATIVE_IOC_KIND_UNPROVED")
            native_type = OrderType.LIMIT
        orders.append(OrderStatusReport(
            account_id, instrument.id, VenueOrderId(str(row["oid"])),
            OrderSide.BUY if row["side"] == "B" else OrderSide.SELL,
            native_type, TimeInForce.IOC if row["tif"] == "Ioc" else TimeInForce.GTC,
            order_status, Quantity.from_str(str(total)), Quantity.from_str(str(fill_qty[client])),
            UUID4(), row["timestamp"] * 1_000_000, status_ms * 1_000_000, ts_init,
            client_order_id=ClientOrderId(client),
            price=None if native_type == OrderType.MARKET else Price.from_str(str(px)),
            post_only=row["tif"] == "Alo", reduce_only=row["reduceOnly"],
        ))

    positions = []
    for row in receipt.positions:
        coin = row["coin"]
        if coin not in instruments:
            raise IncompleteInfoReport("POSITION_INSTRUMENT_MISMATCH")
        instrument = instruments[coin]
        size = _precise(row["szi"], instrument.size_precision, "POSITION_SIZE")
        if size == 0:
            continue
        avg = Decimal(str(row["entryPx"]))
        if not avg.is_finite() or avg <= 0:
            raise IncompleteInfoReport("BAD_POSITION_ENTRY_PRICE")
        positions.append(PositionStatusReport(
            account_id, instrument.id,
            PositionSide.LONG if size > 0 else PositionSide.SHORT,
            Quantity.from_str(str(abs(size))), UUID4(),
            receipt.end_ms * 1_000_000, ts_init, avg_px_open=avg,
        ))
    mass = ExecutionMassStatus(client_id, account_id, venue, UUID4(), ts_init)
    mass.add_order_reports(orders)
    mass.add_fill_reports(list(reports.values()))
    mass.add_position_reports(positions)
    return mass
