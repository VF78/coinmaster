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


def validated_dex_names(names):
    if (not isinstance(names,(tuple,list)) or not 1<=len(names)<=32
        or any(not isinstance(name,str) for name in names) or len(set(names))!=len(names)
        or '' not in names):
        raise IncompleteInfoReport('UNIFIED_DEX_CATALOG_MALFORMED')
    return tuple(names)


def parse_perp_dex_directory(raw):
    if not isinstance(raw,list) or not 1<=len(raw)<=32:
        raise IncompleteInfoReport('UNIFIED_DEX_DISCOVERY_BOUND_UNKNOWN')
    return validated_dex_names(['' if item is None else item.get('name') if isinstance(item,dict) else None for item in raw])


async def bounded_info_requests(info,bodies,*,width=8):
    """Independent prepaid requests only; all dispatched calls finish before fail."""
    import asyncio,time
    if type(width) is not int or not 1<=width<=8:
        raise IncompleteInfoReport('INFO_PARALLELISM_INVALID')
    results=[];provenance=[]
    async def measured(body):
        started=time.monotonic_ns()
        try:return await info(body)
        finally:provenance.append((body.get('type'),body.get('dex'),started,time.monotonic_ns()))
    for offset in range(0,len(bodies),width):
        pending=asyncio.gather(*(measured(body) for body in bodies[offset:offset+width]),return_exceptions=True)
        try:batch=await asyncio.shield(pending)
        except asyncio.CancelledError:
            await pending
            raise
        failures=[value for value in batch if isinstance(value,BaseException)]
        if failures:
            error=IncompleteInfoReport('INFO_PARALLEL_BATCH_INCOMPLETE')
            error.request_provenance=tuple(provenance)
            raise error from failures[0]
        results.extend(batch)
    return tuple(results),tuple(provenance)


async def collect_per_dex_states(info,*,account,dex_names):
    names=validated_dex_names(dex_names)
    values,provenance=await bounded_info_requests(info,[dict(type='clearinghouseState',user=account,dex=name) for name in names])
    for value in values:
        if not isinstance(value,dict) or not isinstance(value.get('assetPositions'),list):
            raise IncompleteInfoReport('UNIFIED_DEX_POSITION_SET_UNKNOWN')
    return tuple(zip(names,values)),provenance


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
    anchor_tid: int | None = None
    account_summary: tuple[str, str, str, str, str] = ()
    cross_account_summary: tuple[str, str, str, str] = ()
    account_role: str = ""
    abstraction: str = ""
    dex_abstraction: bool | None = None
    cached_terminal_cloids: tuple[str, ...] = ()
    query_start_ms: int | None = None
    query_anchor_tid: int | None = None
    account_mode: str = "disabled"
    spot_balances: tuple[dict,...] = ()
    all_dex_states: tuple = ()
    equity_basis: str = "HYPERLIQUID_CLASSIC_PERPS_ACCOUNT_VALUE_V1"
    context_verified_at_ns: int | None = None
    mode_observed_at_ns: int | None = None
    dex_state_provenance: tuple = ()


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
    require_money_scope: bool = False,
    cached_terminal_statuses: dict | None = None, archived_fills: tuple = (),
    query_anchor_ms: int | None = None, query_anchor_tid: int | None = None,
    allow_fill_subdivision: bool = True,
    account_mode: str = "disabled",account_context: dict | None = None,
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
    cached_terminal_statuses=cached_terminal_statuses or {}
    if set(cached_terminal_statuses)-set(expected_orders):raise IncompleteInfoReport('CACHED_TERMINAL_SCOPE_UNKNOWN')
    query_start=anchor_ms if query_anchor_ms is None else query_anchor_ms
    if type(query_start) is not int or not anchor_ms<=query_start<=end_ms:raise IncompleteInfoReport('QUERY_ANCHOR_INVALID')
    if (query_anchor_ms is None)!=(query_anchor_tid is None):raise IncompleteInfoReport('QUERY_ANCHOR_INCOMPLETE')
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
        except IncompleteInfoReport:
            raise
        except Exception as exc:
            raise IncompleteInfoReport("INFO_TRANSPORT_FAILED") from exc

    open_orders = await request({"type": "frontendOpenOrders", "user": account, "dex": dex})
    if account_mode not in ('disabled','unifiedAccount'):raise IncompleteInfoReport('UNSUPPORTED_ACCOUNT_ABSTRACTION')
    spot_rows=();all_dex_rows=();dex_provenance=()
    if account_mode=='unifiedAccount':
        from coinmaster.ops.hl_unified_account import default_dex_state,spot_usdc
        if dex!='':raise IncompleteInfoReport('UNIFIED_DEFAULT_DEX_REQUIRED')
        if account_context is None:raise IncompleteInfoReport('UNIFIED_VERIFIED_DEX_DIRECTORY_REQUIRED')
        all_dex,dex_provenance=await collect_per_dex_states(request,account=account,dex_names=account_context.get('dex_names'))
        state=default_dex_state(all_dex)
        spot=await request({'type':'spotClearinghouseState','user':account})
        spot_usdc(spot);spot_rows=tuple(spot['balances']);all_dex_rows=tuple((item[0],item[1]) for item in all_dex)
    else:state = await request({"type": "clearinghouseState", "user": account, "dex": dex})
    if not isinstance(open_orders, list) or not isinstance(state, dict) or not isinstance(state.get("assetPositions"), list):
        raise IncompleteInfoReport("MALFORMED_ACCOUNT_OR_ORDERS")
    summary = state.get("marginSummary")
    if not isinstance(summary, dict):
        raise IncompleteInfoReport("MALFORMED_ACCOUNT_SUMMARY")
    account_value = _number(summary.get("accountValue"), "ACCOUNT_VALUE")
    if account_value < 0 and account_mode=="disabled":
        raise IncompleteInfoReport("BAD_ACCOUNT_VALUE")
    totals = []
    for field in ("totalRawUsd", "totalMarginUsed", "totalNtlPos"):
        value = _number(summary.get(field), field)
        if field != "totalRawUsd" and value < 0:
            raise IncompleteInfoReport(f"BAD_{field}")
        totals.append(str(value))
    withdrawable = _number(state.get("withdrawable"), "WITHDRAWABLE")
    if withdrawable < 0 and account_mode=="disabled":
        raise IncompleteInfoReport("BAD_WITHDRAWABLE")
    cross_values: tuple[str, str, str, str] = ()
    role = abstraction = ""
    dex_abstraction = None
    if require_money_scope:
        cross = state.get("crossMarginSummary")
        if not isinstance(cross, dict):
            raise IncompleteInfoReport("CROSS_MARGIN_SUMMARY_MISSING")
        cross_numbers = tuple(
            _number(cross.get(field), "CROSS_" + field)
            for field in ("accountValue", "totalRawUsd", "totalMarginUsed", "totalNtlPos")
        )
        if (cross_numbers[0] < 0 and account_mode=="disabled") or cross_numbers[2] < 0 or cross_numbers[3] < 0:
            raise IncompleteInfoReport("BAD_CROSS_MARGIN_SUMMARY")
        cross_values = tuple(str(value) for value in cross_numbers)
        if account_mode=='unifiedAccount' and account_context is not None:
            role=account_context['master_role'];abstraction=account_context['mode'];dex_abstraction=account_context['dex_abstraction']
        else:
            raw_role=await request({'type':'userRole','user':account})
            raw_abstraction=await request({'type':'userAbstraction','user':account})
            dex_abstraction=await request({'type':'userDexAbstraction','user':account})
            role=raw_role.get('role') if isinstance(raw_role,dict) else ''
            abstraction=raw_abstraction if isinstance(raw_abstraction,str) else ''
        if role != "user" or abstraction != account_mode or dex_abstraction is not False:
            raise IncompleteInfoReport("UNSUPPORTED_ACCOUNT_ABSTRACTION")

    statuses = []
    resolved_oids = set()
    oid_coin: dict[int, str] = {}
    for cloid, expected_oid in expected_orders.items():
        if cloid in cached_terminal_statuses:
            status=cached_terminal_statuses[cloid]
            if status.get('order',{}).get('status') not in ('filled','canceled'):
                raise IncompleteInfoReport('CACHED_STATUS_NOT_TERMINAL')
        else:
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
        if not allow_fill_subdivision and len(rows)>=MAX_FILLS:
            raise IncompleteInfoReport('LIVE_FILL_RESPONSE_SATURATED')
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

    await window(query_start, end_ms)
    if query_anchor_tid is not None and (query_anchor_tid not in fills_by_tid or fills_by_tid[query_anchor_tid]['time']!=query_start):
        raise IncompleteInfoReport('QUERY_ANCHOR_NOT_RETAINED')
    for raw in archived_fills:
        _,tid,oid=_fill(raw,anchor_ms,query_start)
        if oid not in known_oids or raw['coin']!=oid_coin[oid]:raise IncompleteInfoReport('ARCHIVED_FILL_SCOPE_UNKNOWN')
        if tid in fills_by_tid and fills_by_tid[tid]!=raw:raise IncompleteInfoReport('CONFLICTING_ARCHIVED_FILL')
        fills_by_tid[tid]=raw
    if anchor_tid is not None and (
        anchor_tid not in fills_by_tid or fills_by_tid[anchor_tid]["time"] != anchor_ms
    ):
        raise IncompleteInfoReport("ANCHOR_NOT_RETAINED")
    fills = tuple(sorted(fills_by_tid.values(), key=lambda item: (item["time"], item["tid"])))
    return InfoReceipt(
        account, dex, anchor_ms, end_ms, tuple(open_orders), tuple(positions),
        fills, tuple(statuses), fill_anchor_proven=anchor_tid is not None,
        account_value=str(account_value), anchor_tid=anchor_tid,
        account_summary=(str(account_value), *totals, str(withdrawable)),
        cross_account_summary=cross_values, account_role=role,
        abstraction=abstraction, dex_abstraction=dex_abstraction,
        cached_terminal_cloids=tuple(sorted(cached_terminal_statuses)),query_start_ms=query_anchor_ms,query_anchor_tid=query_anchor_tid,
        account_mode=account_mode,spot_balances=spot_rows,all_dex_states=all_dex_rows,
        equity_basis=('HYPERLIQUID_UNIFIED_SPOT_USDC_REPORTED_TOTAL_V1' if account_mode=='unifiedAccount' else 'HYPERLIQUID_CLASSIC_PERPS_ACCOUNT_VALUE_V1'),
        context_verified_at_ns=account_context.get('verified_at_ns') if account_context else None,
        mode_observed_at_ns=account_context.get('mode_observed_at_ns') if account_context else None,
        dex_state_provenance=dex_provenance,
    )
