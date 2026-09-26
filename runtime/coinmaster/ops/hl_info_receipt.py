"""Read-only Hyperliquid Info evidence; never an automatic recovery gate.

The caller supplies an authenticated/selected account address and an async Info
transport. A receipt is conditional: Info endpoints have no common snapshot cursor.
Native execution reports and account state must still be reconciled separately.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Awaitable, Callable


InfoTransport = Callable[[dict[str, Any]], Awaitable[Any]]
MAX_FILLS = 2000


class IncompleteInfoReport(ValueError):
    """The venue evidence cannot certify even a conditional report batch."""


@dataclass(frozen=True)
class InfoReceipt:
    account: str
    dex: str
    start_ms: int
    end_ms: int
    open_orders: tuple[dict, ...]
    positions: tuple[dict, ...]
    fills: tuple[dict, ...]
    order_statuses: tuple[dict, ...]
    fill_anchor_proven: bool = False
    conditional_only: bool = True
    account_value: str = ""


def _number(value: Any, name: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise IncompleteInfoReport(f"BAD_{name}") from exc
    if not number.is_finite():
        raise IncompleteInfoReport(f"BAD_{name}")
    return number


def _oid(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise IncompleteInfoReport("BAD_OID")
    return value


def _order_fields(row: dict) -> None:
    """Reject raw rows missing native order-report identity or economics."""
    if row.get("side") not in ("B", "A") or type(row.get("reduceOnly")) is not bool:
        raise IncompleteInfoReport("BAD_ORDER_FLAGS")
    original = _number(row.get("origSz"), "ORIGINAL_SIZE")
    leaves = _number(row.get("sz"), "ORDER_LEAVES")
    if original <= 0 or leaves < 0 or leaves > original:
        raise IncompleteInfoReport("BAD_ORDER_SIZE")
    if row.get("orderType") != "Limit" or row.get("tif") not in ("Gtc", "Ioc", "Alo"):
        raise IncompleteInfoReport("UNSUPPORTED_ORDER_TYPE_OR_TIF")
    if _number(row.get("limitPx"), "LIMIT_PRICE") <= 0:
        raise IncompleteInfoReport("BAD_LIMIT_PRICE")
    timestamp = row.get("timestamp")
    if isinstance(timestamp, bool) or not isinstance(timestamp, int) or timestamp < 0:
        raise IncompleteInfoReport("BAD_ORDER_TIMESTAMP")


def _fill(row: Any, start: int, end: int) -> tuple[int, int, int]:
    if not isinstance(row, dict):
        raise IncompleteInfoReport("BAD_FILL")
    time = row.get("time")
    tid = row.get("tid")
    if isinstance(time, bool) or not isinstance(time, int) or not start <= time <= end:
        raise IncompleteInfoReport("BAD_FILL_TIME")
    if isinstance(tid, bool) or not isinstance(tid, int) or tid < 0:
        raise IncompleteInfoReport("BAD_FILL_TID")
    oid = _oid(row.get("oid"))
    if not isinstance(row.get("coin"), str) or not row["coin"]:
        raise IncompleteInfoReport("BAD_FILL_COIN")
    if row.get("side") not in ("B", "A"):
        raise IncompleteInfoReport("BAD_FILL_SIDE")
    if _number(row.get("sz"), "FILL_SIZE") <= 0 or _number(row.get("px"), "FILL_PRICE") <= 0:
        raise IncompleteInfoReport("BAD_FILL_ECONOMICS")
    _number(row.get("fee"), "FILL_FEE")
    if type(row.get("crossed")) is not bool:
        raise IncompleteInfoReport("BAD_FILL_LIQUIDITY")
    if not isinstance(row.get("feeToken"), str) or row["feeToken"].strip() != "USDC":
        raise IncompleteInfoReport("UNKNOWN_FILL_FEE_CURRENCY")
    if not isinstance(row.get("hash"), str) or not row["hash"].startswith("0x"):
        raise IncompleteInfoReport("BAD_FILL_HASH")
    return time, tid, oid


async def collect_info_receipt(
    info: InfoTransport,
    *,
    account: str,
    dex: str,
    anchor_ms: int,
    anchor_tid: int | None,
    end_ms: int,
    expected_orders: dict[str, int | None],
    owned_coins: frozenset[str],
) -> InfoReceipt:
    """Collect a validated, bounded batch; raises on uncertainty.

    expected_orders maps durable 16-byte hex CLOIDs to known OIDs or None
    (lost ACK). An inclusive applied-fill anchor must be returned. No receipt
    proves a cross-endpoint atomic snapshot or enables automatic takeover.
    """
    if not isinstance(account, str) or len(account) != 42 or not account.startswith("0x"):
        raise IncompleteInfoReport("BAD_ACCOUNT")
    try:
        int(account[2:], 16)
    except ValueError as exc:
        raise IncompleteInfoReport("BAD_ACCOUNT") from exc
    if (
        not isinstance(dex, str) or isinstance(anchor_ms, bool) or isinstance(end_ms, bool)
        or not isinstance(anchor_ms, int) or not isinstance(end_ms, int)
        or not 0 <= anchor_ms <= end_ms
    ):
        raise IncompleteInfoReport("BAD_SCOPE")
    if anchor_tid is not None and (isinstance(anchor_tid, bool) or not isinstance(anchor_tid, int) or anchor_tid < 0):
        raise IncompleteInfoReport("BAD_ANCHOR")
    if not owned_coins or not all(isinstance(x, str) and x for x in owned_coins):
        raise IncompleteInfoReport("BAD_OWNERSHIP")
    if anchor_tid is not None and not expected_orders:
        raise IncompleteInfoReport("ANCHOR_WITHOUT_DURABLE_ORDER")
    known_oids = set()
    for cloid, oid in expected_orders.items():
        if not isinstance(cloid, str) or len(cloid) != 34 or not cloid.startswith("0x"):
            raise IncompleteInfoReport("BAD_CLOID")
        try:
            int(cloid[2:], 16)
        except ValueError as exc:
            raise IncompleteInfoReport("BAD_CLOID") from exc
        if oid is not None:
            oid = _oid(oid)
            if oid in known_oids:
                raise IncompleteInfoReport("DUPLICATE_DURABLE_VENUE_ORDER_ID")
            known_oids.add(oid)

    async def request(body: dict[str, Any]) -> Any:
        try:
            return await info(body)
        except Exception as exc:
            raise IncompleteInfoReport("INFO_TRANSPORT_FAILED") from exc

    open_orders = await request({"type": "frontendOpenOrders", "user": account, "dex": dex})
    state = await request({"type": "clearinghouseState", "user": account, "dex": dex})
    if not isinstance(open_orders, list) or not isinstance(state, dict) or not isinstance(state.get("assetPositions"), list):
        raise IncompleteInfoReport("MALFORMED_ACCOUNT_OR_ORDERS")
    summary = state.get("marginSummary")
    if not isinstance(summary, dict):
        raise IncompleteInfoReport("MALFORMED_ACCOUNT_SUMMARY")
    account_value = _number(summary.get("accountValue"), "ACCOUNT_VALUE")
    if account_value < 0:
        raise IncompleteInfoReport("BAD_ACCOUNT_VALUE")
    for field in ("totalRawUsd", "totalMarginUsed", "totalNtlPos"):
        if _number(summary.get(field), field) < 0:
            raise IncompleteInfoReport(f"BAD_{field}")
    if _number(state.get("withdrawable"), "WITHDRAWABLE") < 0:
        raise IncompleteInfoReport("BAD_WITHDRAWABLE")

    statuses = []
    resolved_oids = set()
    oid_coin: dict[int, str] = {}
    for cloid, expected_oid in expected_orders.items():
        status = await request({"type": "orderStatus", "user": account, "oid": cloid})
        if not isinstance(status, dict) or status.get("status") != "order" or not isinstance(status.get("order"), dict):
            raise IncompleteInfoReport("ORDER_STATUS_UNKNOWN")
        item = status["order"]
        order = item.get("order")
        if not isinstance(order, dict):
            raise IncompleteInfoReport("MALFORMED_ORDER_STATUS")
        actual_oid = _oid(order.get("oid"))
        returned_cloid = order.get("cloid")
        if returned_cloid is not None and (
            not isinstance(returned_cloid, str) or returned_cloid.lower() != cloid.lower()
        ):
            raise IncompleteInfoReport("CLOID_MISMATCH")
        if expected_oid is None and returned_cloid is None:
            raise IncompleteInfoReport("LOST_ACK_CLOID_UNPROVED")
        if expected_oid is not None and actual_oid != expected_oid:
            raise IncompleteInfoReport("ORDER_ID_MISMATCH")
        if actual_oid in resolved_oids or (actual_oid in known_oids and expected_oid is None):
            raise IncompleteInfoReport("DUPLICATE_VENUE_ORDER_ID")
        resolved_oids.add(actual_oid)
        known_oids.add(actual_oid)
        if order.get("coin") not in owned_coins:
            raise IncompleteInfoReport("FOREIGN_ORDER")
        if item.get("status") not in ("open", "filled", "canceled"):
            raise IncompleteInfoReport("UNKNOWN_ORDER_TERMINAL")
        _order_fields(order)
        status_timestamp = item.get("statusTimestamp")
        if isinstance(status_timestamp, bool) or not isinstance(status_timestamp, int) or status_timestamp < order["timestamp"]:
            raise IncompleteInfoReport("BAD_STATUS_TIMESTAMP")
        oid_coin[actual_oid] = order["coin"]
        statuses.append(status)

    open_oids = set()
    for row in open_orders:
        if not isinstance(row, dict) or row.get("coin") not in owned_coins:
            raise IncompleteInfoReport("FOREIGN_OPEN_ORDER")
        oid = _oid(row.get("oid"))
        if oid not in known_oids or oid in open_oids:
            raise IncompleteInfoReport("UNKNOWN_OPEN_ORDER")
        if row["coin"] != oid_coin[oid]:
            raise IncompleteInfoReport("OPEN_ORDER_COIN_MISMATCH")
        if _number(row.get("sz"), "OPEN_LEAVES") <= 0 or _number(row.get("origSz"), "ORIGINAL_SIZE") <= 0:
            raise IncompleteInfoReport("BAD_OPEN_ORDER_SIZE")
        status_order = next(item["order"]["order"] for item in statuses if item["order"]["order"]["oid"] == oid)
        # frontendOpenOrders omits some orderStatus fields (notably TIF).
        # Compare every shared conversion field without inventing missing ones.
        for field in ("side", "origSz", "sz", "limitPx", "reduceOnly", "orderType", "timestamp"):
            if row.get(field) != status_order.get(field):
                raise IncompleteInfoReport("OPEN_ORDER_STATUS_FIELD_MISMATCH")
        if "tif" in row and row["tif"] != status_order["tif"]:
            raise IncompleteInfoReport("OPEN_ORDER_STATUS_FIELD_MISMATCH")
        open_oids.add(oid)
    status_open = {
        item["order"]["order"]["oid"] for item in statuses
        if item["order"]["status"] == "open"
    }
    if status_open != open_oids:
        raise IncompleteInfoReport("ORDER_OPEN_STATUS_MISMATCH")
    positions = []
    seen_positions = set()
    for row in state["assetPositions"]:
        if not isinstance(row, dict) or not isinstance(row.get("position"), dict):
            raise IncompleteInfoReport("MALFORMED_POSITION")
        position = row["position"]
        if position.get("coin") not in owned_coins:
            raise IncompleteInfoReport("FOREIGN_POSITION")
        size = _number(position.get("szi"), "POSITION_SIZE")
        if size and _number(position.get("entryPx"), "POSITION_ENTRY_PRICE") <= 0:
            raise IncompleteInfoReport("BAD_POSITION_ENTRY_PRICE")
        if position["coin"] in seen_positions:
            raise IncompleteInfoReport("DUPLICATE_POSITION")
        seen_positions.add(position["coin"])
        positions.append(position)

    fills_by_tid: dict[int, dict] = {}
    fill_requests = 0

    async def window(start: int, end: int) -> None:
        nonlocal fill_requests
        fill_requests += 1
        if fill_requests > 128:
            raise IncompleteInfoReport("FILL_WINDOW_REQUEST_LIMIT")
        rows = await request({
            "type": "userFillsByTime", "user": account,
            "startTime": start, "endTime": end, "aggregateByTime": False,
        })
        if not isinstance(rows, list) or len(rows) > MAX_FILLS:
            raise IncompleteInfoReport("MALFORMED_OR_OVERSIZE_FILLS")
        for row in rows:
            time, tid, oid = _fill(row, start, end)
            if row["coin"] not in owned_coins or oid not in known_oids:
                raise IncompleteInfoReport("FOREIGN_OR_UNKNOWN_FILL")
            if row["coin"] != oid_coin[oid]:
                raise IncompleteInfoReport("FILL_COIN_MISMATCH")
            previous = fills_by_tid.get(tid)
            if previous is not None and previous != row:
                raise IncompleteInfoReport("CONFLICTING_DUPLICATE_FILL")
            fills_by_tid[tid] = row
        if len(rows) == MAX_FILLS:
            if start == end:
                raise IncompleteInfoReport("SATURATED_FILL_TIMESTAMP")
            mid = (start + end) // 2
            await window(start, mid)
            await window(mid + 1, end)

    await window(anchor_ms, end_ms)
    if anchor_tid is not None and (
        anchor_tid not in fills_by_tid or fills_by_tid[anchor_tid]["time"] != anchor_ms
    ):
        raise IncompleteInfoReport("ANCHOR_NOT_RETAINED")
    fills = tuple(sorted(fills_by_tid.values(), key=lambda item: (item["time"], item["tid"])))
    return InfoReceipt(
        account, dex, anchor_ms, end_ms, tuple(open_orders), tuple(positions),
        fills, tuple(statuses), fill_anchor_proven=anchor_tid is not None,
        account_value=str(account_value),
    )
