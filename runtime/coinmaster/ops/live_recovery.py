"""Fail-closed native-report reconciliation for a future live adapter.

This owns no exchange transport, matching, fills, PnL, or account posting.
Nautilus remains authoritative; recovered intents are never resubmitted.
"""
from __future__ import annotations

import time
import hashlib
import json
from dataclasses import dataclass
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

from nautilus_trader.model.currencies import USDC
from nautilus_trader.model.enums import OrderSide, OrderStatus

from coinmaster.ops.paper import PaperRuntime

if TYPE_CHECKING:
    from coinmaster.strategy.live_recovery import RecoverableWaveOverlayStrategy


@dataclass(frozen=True)
class NativeLiveRecoveryScope:
    """Explicit read-only venue identity and durable cursor for a live owner.

    This is separate from Sandbox instance config and contains no credential.
    A factory must bind it to one selected execution account before any Info
    generation; it never grants readiness by construction.
    """
    account_ref: str
    dex: str
    anchor_ms: int
    anchor_tid: int | None
    durable_orders: tuple[tuple[str, str, int | None], ...]
    owned_coins: frozenset[str]
    fill_anchor_ms: int | None = None
    fill_anchor_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.account_ref, str)
            or len(self.account_ref) != 42
            or not self.account_ref.startswith("0x")
        ):
            raise ValueError("LIVE_ACCOUNT_REF_REQUIRED")
        try:
            if int(self.account_ref[2:], 16) == 0:
                raise ValueError("LIVE_ACCOUNT_REF_REQUIRED")
        except ValueError as exc:
            raise ValueError("LIVE_ACCOUNT_REF_REQUIRED") from exc
        if (
            not isinstance(self.dex, str)
            or isinstance(self.anchor_ms, bool)
            or not isinstance(self.anchor_ms, int)
            or self.anchor_ms < 0
            or (self.anchor_tid is not None and (
                isinstance(self.anchor_tid, bool)
                or not isinstance(self.anchor_tid, int)
                or self.anchor_tid < 0
            ))
            or not self.owned_coins
            or not self.owned_coins.issubset({"BTC", "SOL"})
        ):
            raise ValueError("LIVE_INFO_CURSOR_INVALID")
        if len({item[0] for item in self.durable_orders}) != len(self.durable_orders):
            raise ValueError("LIVE_DURABLE_ORDER_DUPLICATE")
        if self.anchor_tid is not None and not self.durable_orders:
            raise ValueError("LIVE_ANCHOR_WITHOUT_DURABLE_ORDER")
        if ((self.fill_anchor_ms is None)!=(self.fill_anchor_fingerprint is None)
            or (self.fill_anchor_ms is not None and (self.anchor_tid is None
                or type(self.fill_anchor_ms) is not int or self.fill_anchor_ms<self.anchor_ms
                or not isinstance(self.fill_anchor_fingerprint,str)
                or len(self.fill_anchor_fingerprint)!=64
                or any(c not in '0123456789abcdef' for c in self.fill_anchor_fingerprint)))):
            raise ValueError("LIVE_APPLIED_ANCHOR_BINDING_INVALID")


def owned_fill_anchor_fingerprint(*,account_ref,dex,trade_id,cloid,oid,instrument_id,side,
                                 quantity,price,fee,currency,liquidity,ts_event_ns):
    if (currency!='USDC' or side not in ('BUY','SELL') or liquidity not in ('MAKER','TAKER')
        or type(ts_event_ns) is not int or ts_event_ns<=0 or ts_event_ns%1_000_000
        or not str(trade_id).isdigit() or not str(oid).isdigit()):
        raise ValueError('LIVE_APPLIED_ANCHOR_ECONOMICS_UNKNOWN')
    def number(value):
        result=Decimal(str(value))
        if not result.is_finite():raise ValueError('LIVE_APPLIED_ANCHOR_ECONOMICS_UNKNOWN')
        return format(result.normalize(),'f')
    if Decimal(str(quantity))<=0 or Decimal(str(price))<=0:
        raise ValueError('LIVE_APPLIED_ANCHOR_ECONOMICS_UNKNOWN')
    payload=(account_ref.lower(),dex,str(int(trade_id)),cloid.lower(),str(int(oid)),
        str(instrument_id),side,number(quantity),number(price),number(fee),currency,liquidity,ts_event_ns)
    return hashlib.sha256(json.dumps(payload,separators=(',',':')).encode()).hexdigest()


def applied_owned_fill_anchor(runtime,native_orders,*,account_ref,dex,account_id,strategy_id,cloid_for,history_anchor_ms):
    """Local candidate only: exact atomically applied owned native event + durable detail."""
    applied=runtime.applied_fill_ids()
    if not applied:return None
    journal={r['client_order_id']:r for r in runtime.all_submissions()}
    orders={str(o.client_order_id):o for o in native_orders}
    details=runtime.db.execute('SELECT trade_id,native_event_id,client_order_id,venue_order_id,instrument_id,order_side,quantity,price,commission_amount,commission_currency,liquidity_side,ts_event_ns,ts_init_ns FROM paper_native_fill_details').fetchall()
    # Explicitly exclude uncommitted/native-only details from candidate selection.
    selected=[row for row in details if str(row[0]) in applied]
    if len(selected)!=len(applied) or {str(row[0]) for row in selected}!=applied:
        raise ValueError('LIVE_APPLIED_ANCHOR_DETAILS_MISSING')
    candidates=[]
    for tid,event_id,client,oid,instrument,side,qty,px,fee,currency,liquidity,ts,init in selected:
        order=orders.get(client);row=journal.get(client)
        if (order is None or row is None or str(order.strategy_id)!=str(strategy_id)
            or str(order.account_id)!=str(account_id) or str(order.instrument_id)!=instrument
            or row['instrument_id']!=instrument or str(order.venue_order_id)!=str(oid)
            or instrument not in ('BTC-USD-PERP.HYPERLIQUID','SOL-USD-PERP.HYPERLIQUID')
            or not event_id or type(ts) is not int or type(init) is not int or init<ts
            or ts//1_000_000<history_anchor_ms or str(tid) not in set(map(str,order.trade_ids))):
            raise ValueError('LIVE_APPLIED_ANCHOR_OWNERSHIP_UNKNOWN')
        events=[e for e in order.events if str(getattr(e,'trade_id',''))==str(tid)]
        if len(events)!=1:raise ValueError('LIVE_APPLIED_ANCHOR_NATIVE_EVENT_UNKNOWN')
        event=events[0]
        if (str(getattr(event,'id',None))!=str(event_id) or str(event.client_order_id)!=client
            or str(event.venue_order_id)!=str(oid) or str(event.instrument_id)!=instrument
            or str(event.account_id)!=str(account_id)
            or getattr(event.order_side,'name',str(event.order_side))!=side
            or event.last_qty.as_decimal()!=Decimal(qty) or event.last_px.as_decimal()!=Decimal(px)
            or event.commission.as_decimal()!=Decimal(fee) or str(event.commission.currency)!=currency
            or getattr(event.liquidity_side,'name',str(event.liquidity_side))!=liquidity
            or event.ts_event!=ts):
            raise ValueError('LIVE_APPLIED_ANCHOR_NATIVE_ECONOMICS_MISMATCH')
        fingerprint=owned_fill_anchor_fingerprint(account_ref=account_ref,dex=dex,trade_id=tid,
            cloid=cloid_for(client),oid=oid,instrument_id=instrument,side=side,quantity=qty,
            price=px,fee=fee,currency=currency,liquidity=liquidity,ts_event_ns=ts)
        candidates.append((ts//1_000_000,int(tid),fingerprint))
    return min(candidates)


class LiveRecoverySubmissionSink:
    def __init__(self, runtime: PaperRuntime, strategy: "RecoverableWaveOverlayStrategy", owned_instruments: frozenset[str]) -> None:
        if not owned_instruments:
            raise ValueError("EMPTY_RECOVERY_OWNERSHIP")
        self.runtime = runtime
        self.strategy = strategy
        self.owned_instruments = owned_instruments

    def __call__(self, **request) -> bool:
        if request["instrument_id"] not in self.owned_instruments:
            raise ValueError("UNOWNED_RECOVERY_INSTRUMENT")
        if not request["reduce_only"] and not self.runtime.health(time.time_ns()).safe_for_increase:
            return False
        checkpoint = self.strategy.on_save()["wave_overlay_live_recovery_v1"]
        return self.runtime.record_submission(
            client_order_id=request["client_order_id"],
            intent_id=request["intent_id"],
            episode_id=request["episode_id"],
            action=request["action"],
            instrument_id=request["instrument_id"],
            quantity=request["quantity"],
            reduce_only=request["reduce_only"],
            strategy_state=checkpoint,
            order_shape={
                "side": request["order_side"], "kind": request["order_kind"],
                "tif": request["time_in_force"], "post_only": request["post_only"],
                "price": request["price"],
            } if all(key in request for key in ("order_side", "order_kind", "time_in_force", "post_only", "price")) else None,
        )


class LiveRecoveryReconciler:
    """Validate a complete native report set before one domain/checkpoint commit."""

    def __init__(self, runtime: PaperRuntime, strategy: "RecoverableWaveOverlayStrategy", expected_account_id: str) -> None:
        self.runtime = runtime
        self.strategy = strategy
        self.expected_account_id = expected_account_id

    def apply_partial_fills(self, reports: list, native_orders: list, native_positions: list, order_reports: list, native_account=None) -> None:
        self.strategy.recovery_confirmed = False
        owned = {str(self.strategy.config.btc_id), str(self.strategy.config.sol_id)}
        strategy_id = str(self.strategy.id)
        journal = {item["client_order_id"]: item for item in self.runtime.all_submissions()}
        orders = {str(item.client_order_id): item for item in native_orders}
        status = {str(item.client_order_id): item for item in order_reports}
        if len(orders) != len(native_orders) or len(status) != len(order_reports) or set(status) != set(orders):
            raise ValueError("RECOVERY_DUPLICATE_NATIVE_ORDER")
        expected_open = set(self.strategy._pending_by_order)
        if not expected_open.issubset(orders):
            raise ValueError("RECOVERY_EXPECTED_ORDER_MISSING")
        episode = self.strategy._domain.episode
        if episode is None:
            raise ValueError("RECOVERY_EPISODE_MISSING")
        checkpoint = self.runtime.strategy_checkpoint()
        current = self.strategy.on_save()["wave_overlay_live_recovery_v1"]
        if checkpoint is None or checkpoint[0] != current:
            raise ValueError("RECOVERY_CHECKPOINT_LINEAGE_MISMATCH")

        reports_by_order = defaultdict(list)
        seen_trades = set()
        for report in reports:
            trade_id = str(report.trade_id)
            if not trade_id or trade_id in seen_trades:
                raise ValueError("RECOVERY_DUPLICATE_NATIVE_FILL")
            seen_trades.add(trade_id)
            order_id = str(report.client_order_id)
            reports_by_order[order_id].append(report)
            order = orders.get(order_id)
            intent = self.strategy._pending_by_order.get(order_id)
            recorded = journal.get(order_id)
            previously_applied = self.runtime.has_applied_fill(trade_id)
            if (
                order is None or recorded is None
                or (intent is None and (not order.is_closed or not previously_applied))
                or (intent is not None and (
                    recorded["intent_id"] != intent.id
                    or recorded["episode_id"] != intent.episode_id
                    or recorded["action"] != intent.action
                    or intent.id not in episode.pending
                ))
                or recorded["instrument_id"] != str(report.instrument_id)
                or str(report.account_id) != self.expected_account_id
                or str(report.venue_order_id) != str(order.venue_order_id)
                or report.instrument_id != order.instrument_id
                or report.order_side != order.side
                or (intent is not None and order.side != (OrderSide.BUY if intent.side == 1 else OrderSide.SELL))
                or Decimal(str(report.last_qty)) <= 0
                or Decimal(str(report.last_px)) <= 0
            ):
                raise ValueError("RECOVERY_FILL_IDENTITY_MISMATCH")
        for order_id, order in orders.items():
            intent = self.strategy._pending_by_order.get(order_id)
            recorded = journal.get(order_id)
            status_report = status[order_id]
            if (
                recorded is None
                or (intent is None and (not order.is_closed or any(
                    not self.runtime.has_applied_fill(str(trade)) for trade in order.trade_ids
                )))
                or str(status_report.account_id) != self.expected_account_id
                or (order.account_id is not None and str(order.account_id) != self.expected_account_id)
                or str(status_report.venue_order_id) != str(order.venue_order_id)
                or status_report.instrument_id != order.instrument_id
                or status_report.order_side != order.side
                or status_report.filled_qty.as_decimal() != order.filled_qty.as_decimal()
                or bool(status_report.reduce_only) != bool(recorded["body"]["reduce_only"])
                or bool(order.is_reduce_only) != bool(recorded["body"]["reduce_only"])
                or status_report.quantity.as_decimal() != Decimal(recorded["body"]["quantity"])
                or order.quantity.as_decimal() != status_report.quantity.as_decimal()
                or str(order.strategy_id) != strategy_id
                or str(order.instrument_id) not in owned
                or recorded["instrument_id"] != str(order.instrument_id)
                or (intent is not None and (
                    recorded["intent_id"] != intent.id
                    or recorded["episode_id"] != intent.episode_id
                    or recorded["action"] != intent.action
                    or intent.id not in episode.pending
                    or order.side != (OrderSide.BUY if intent.side == 1 else OrderSide.SELL)
                ))
            ):
                raise ValueError("RECOVERY_ORDER_OWNERSHIP_MISMATCH")
            if intent is not None and intent.action == "BTC_REDUCE":
                shape = recorded["body"].get("shape")
                expected_side = "BUY" if intent.side == 1 else "SELL"
                if not isinstance(shape, dict) or set(shape) != {"side", "kind", "tif", "post_only", "price"}:
                    raise ValueError("RECOVERY_ORDER_SHAPE_MISSING")
                if (
                    shape["side"] != expected_side
                    or shape["kind"] != "LIMIT"
                    or shape["tif"] != "GTC"
                    or shape["post_only"] is not True
                    or shape["price"] is None
                    or shape["price"] != str(order.price)
                    or status_report.price is None
                    or Decimal(shape["price"]) != status_report.price.as_decimal()
                    or getattr(order.order_type, "name", None) != shape["kind"]
                    or getattr(status_report.order_type, "name", None) != shape["kind"]
                    or getattr(order.time_in_force, "name", None) != shape["tif"]
                    or getattr(status_report.time_in_force, "name", None) != shape["tif"]
                    or not order.is_post_only or not status_report.post_only
                    or (not order.is_closed and status_report.order_status not in {
                        OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED
                    })
                ):
                    raise ValueError("RECOVERY_ORDER_SHAPE_MISMATCH")
            known_ids = {str(item) for item in order.trade_ids}
            reported_ids = {str(item.trade_id) for item in reports_by_order[order_id]}
            quantity = sum((item.last_qty.as_decimal() for item in reports_by_order[order_id]), Decimal("0"))
            if known_ids != reported_ids or quantity != order.filled_qty.as_decimal():
                raise ValueError("RECOVERY_NATIVE_FILL_SET_MISMATCH")

        positions = {str(item.instrument_id): item for item in native_positions}
        if len(positions) != len(native_positions):
            raise ValueError("RECOVERY_DUPLICATE_NATIVE_POSITION")
        for position in native_positions:
            if (
                str(position.instrument_id) not in owned
                or str(position.account_id) != self.expected_account_id
                or str(position.strategy_id) != strategy_id
            ):
                raise ValueError("RECOVERY_POSITION_OWNERSHIP_MISMATCH")
        if native_account is None or str(native_account.id) != self.expected_account_id:
            raise ValueError("RECOVERY_ACCOUNT_IDENTITY_MISMATCH")
        total = native_account.balance_total(USDC)
        if total is None or total.currency != USDC or not total.as_decimal().is_finite() or total.as_decimal() <= 0:
            raise ValueError("RECOVERY_NATIVE_USDC_BALANCE_MISSING")

        # Work on a detached, versioned domain copy. Rejected reports leave
        # live memory, SQLite checkpoint, and trade cursor byte-identical.
        candidate = type(self.strategy)(self.strategy.config)
        candidate.on_load({"wave_overlay_live_recovery_v1": current})
        missing = []
        ordered_reports = sorted(reports, key=lambda item: (item.ts_event, str(item.trade_id)))
        last_trade_by_order = {
            order_id: str(max(items, key=lambda item: (item.ts_event, str(item.trade_id))).trade_id)
            for order_id, items in reports_by_order.items() if items
        }
        for report in ordered_reports:
            trade_id = str(report.trade_id)
            if self.runtime.has_applied_fill(trade_id):
                continue
            order_id = str(report.client_order_id)
            intent = candidate._pending_by_order.get(order_id)
            if intent is None:
                raise ValueError("RECOVERY_MISSING_INTENT_FOR_UNAPPLIED_FILL")
            if intent.action == "BTC_ENTRY" and getattr(candidate.config, "tp_fee_floor_v1", False):
                instrument = self.strategy.cache.instrument(report.instrument_id)
                if instrument is None or report.commission is None or report.commission.currency != instrument.quote_currency:
                    raise ValueError("BTC_TP_ENTRY_FEE_CURRENCY_UNSUPPORTED")
            candidate._apply_confirmed_domain_fill(
                intent, order_id, float(report.last_qty), float(report.last_px), report.ts_event,
                orders[order_id].is_closed and trade_id == last_trade_by_order[order_id],
                **({
                    "entry_fee": report.commission.as_decimal() if intent.action == "BTC_ENTRY" and candidate.config.tp_fee_floor_v1 and report.commission is not None else None,
                    "entry_qty": report.last_qty.as_decimal() if intent.action == "BTC_ENTRY" else None,
                    "entry_price": report.last_px.as_decimal() if intent.action == "BTC_ENTRY" else None,
                } if hasattr(candidate.config, "tp_fee_floor_v1") else {}),
            )
            missing.append(trade_id)
        candidate_episode = candidate._domain.episode
        assert candidate_episode is not None
        btc = positions.get(str(self.strategy.config.btc_id))
        sol = positions.get(str(self.strategy.config.sol_id))
        native_btc = btc.quantity.as_decimal() if btc is not None else Decimal("0")
        native_sol = sol.quantity.as_decimal() if sol is not None else Decimal("0")
        if (
            abs(Decimal(str(candidate_episode.btc_open_qty)) - native_btc) > Decimal("0.000000001")
            or abs(Decimal(str(candidate_episode.sol_qty)) - native_sol) > Decimal("0.000000001")
            or (btc is not None and btc.is_long != (candidate_episode.side == 1))
            or (sol is not None and sol.is_long != (candidate_episode.side == -1))
        ):
            raise ValueError("RECOVERY_EPISODE_POSITION_MISMATCH")
        if missing:
            state = candidate.on_save()["wave_overlay_live_recovery_v1"]
            if not self.runtime.commit_applied_fills(missing, state):
                raise ValueError("RECOVERY_FILL_CURSOR_CONFLICT")
            self.strategy.on_load({"wave_overlay_live_recovery_v1": state})


@dataclass(frozen=True)
class ManagementCertificate:
    revision: int
    expires_ns: int
    policy_sha256: str
    cache_signature: str
    decision_sha256: str
    positions: tuple
    orders: tuple
    generation_ns: int
    transport_healthy: object


def _management_order_evidence(order):
    return (str(order.client_order_id),str(order.venue_order_id) if order.venue_order_id is not None else None,
        str(order.instrument_id),bool(order.is_reduce_only),bool(order.is_closed),order.side.name,
        str(order.quantity.as_decimal()),str(order.filled_qty.as_decimal()),order.status.name,str(order.strategy_id),
        str(order.account_id) if order.account_id is not None else None,bool(order.is_pending_cancel))


def management_cache_evidence(cache, venue):
    positions=tuple(sorted((str(p.instrument_id),str(p.id),"BUY" if p.is_long else "SELL",str(p.quantity.as_decimal()),str(p.strategy_id),str(p.account_id)) for p in cache.positions_open()))
    orders=tuple(sorted(_management_order_evidence(o) for o in cache.orders(venue=venue)))
    signature=hashlib.sha256(json.dumps((positions,orders),separators=(",",":")).encode()).hexdigest()
    return positions,orders,signature


def durable_management_scope(runtime,account_ref,dex,cloid_for):
    """Use existing durable history, never replace open history with a new-now anchor."""
    rows=runtime.all_submissions()
    checkpoint=runtime.strategy_checkpoint()
    details=runtime.db.execute("SELECT trade_id,ts_event_ns FROM paper_native_fill_details ORDER BY ts_event_ns,trade_id").fetchall()
    if not rows and not details and checkpoint is not None:
        marker=getattr(runtime,'c1_initialization',lambda:None)()
        body=json.loads(checkpoint[0])
        if (marker is not None and marker.get('schema')=='coinmaster-live-c1-initialization-v1'
            and body.get('policy_sha256')==marker.get('policy_sha256')
            and type(marker.get('history_anchor_ms')) is int and marker['history_anchor_ms']>=0):
            return NativeLiveRecoveryScope(account_ref,dex,marker['history_anchor_ms'],None,(),frozenset({'BTC','SOL'}))
    if not rows or checkpoint is None or not details or any(r[1] is None for r in details):
        raise ValueError("MANAGEMENT_DURABLE_CURSOR_UNKNOWN")
    # Query from the earliest retained actual fill; strict full-set parity still
    # rejects truncated/missing history. Do not guess a missing venue fill ID.
    anchor=min(int(r[1]) for r in details)//1_000_000
    try:anchor_tid=min(int(r[0]) for r in details if int(r[1])//1_000_000==anchor)
    except (TypeError,ValueError):raise ValueError("MANAGEMENT_DURABLE_CURSOR_UNKNOWN") from None
    durable=tuple((r["client_order_id"],cloid_for(r["client_order_id"]),None) for r in rows)
    marker=getattr(runtime,'c1_initialization',lambda:None)()
    if marker is not None:
        history=marker.get('history_anchor_ms')
        if type(history) is not int or not 0<=history<=anchor:raise ValueError('MANAGEMENT_DURABLE_CURSOR_UNKNOWN')
        # Restart retains the original session window; native cache must re-prove any held anchor.
        return NativeLiveRecoveryScope(account_ref,dex,history,None,durable,frozenset({"BTC","SOL"}))
    return NativeLiveRecoveryScope(account_ref,dex,anchor,anchor_tid,durable,frozenset({"BTC","SOL"}))


def reserve_managed_action(strategy,cert,command_id,kind,order,*,now_ns):
    """Validate one immutable native generation, then durably reserve before dispatch."""
    from coinmaster.strategy.live_recovery import recovery_policy_hash,durable_decision_checkpoint,_KEY
    runtime=strategy._recovery_runtime
    if (not strategy._manage_only_preparation or not strategy._checkpoint_policy_valid or runtime is None
        or cert.policy_sha256!=recovery_policy_hash(strategy.config,strategy._candidate)
        or strategy._loaded_policy_sha256!=cert.policy_sha256
        or not cert.generation_ns<=now_ns<=cert.expires_ns or not cert.transport_healthy()
        or runtime.native_revision()!=cert.revision):
        raise RuntimeError("MANAGEMENT_EVIDENCE_STALE_OR_UNKNOWN")
    positions,orders,signature=management_cache_evidence(strategy.cache,strategy.config.btc_id.venue)
    if signature!=cert.cache_signature:raise RuntimeError("MANAGEMENT_NATIVE_GENERATION_MOVED")
    current=strategy.on_save()[_KEY]
    checkpoint=runtime.strategy_checkpoint()
    if (checkpoint is None or hashlib.sha256(durable_decision_checkpoint(current)).hexdigest()!=cert.decision_sha256
        or durable_decision_checkpoint(checkpoint[0])!=durable_decision_checkpoint(current)):
        raise RuntimeError("MANAGEMENT_CHECKPOINT_MOVED")
    if str(order.strategy_id)!=str(strategy.id) or order.instrument_id not in (strategy.config.btc_id,strategy.config.sol_id):
        raise RuntimeError("MANAGEMENT_FOREIGN_ORDER")
    client=str(order.client_order_id)
    rows={r["client_order_id"]:r for r in runtime.all_submissions()}
    if kind=="CANCEL":
        known=[o for o in orders if o[0]==client]
        actual=[o for o in strategy.cache.orders(venue=strategy.config.btc_id.venue) if str(o.client_order_id)==client]
        if (len(known)!=1 or len(actual)!=1 or client not in rows or known[0][1] is None
            or known[0][4] or known[0][11] or _management_order_evidence(order)!=known[0]
            or _management_order_evidence(actual[0])!=known[0]):
            raise RuntimeError("MANAGEMENT_CANCEL_OWNERSHIP_UNKNOWN")
        dispatch_order=actual[0] # Send the certified current cache object, never a caller substitute.
    elif kind=="REDUCE":
        held=[p for p in positions if p[0]==str(order.instrument_id)]
        if (len(held)!=1 or held[0][4]!=str(strategy.id) or not order.is_reduce_only
            or order.side.name==held[0][2] or not Decimal(0)<order.quantity.as_decimal()<=Decimal(held[0][3])
            or (order.account_id is not None and str(order.account_id)!=held[0][5])
            or client in rows or any(o[2]==str(order.instrument_id) and o[3] and not o[4] for o in orders)
            or order.time_in_force.name!="IOC" or order.order_type.name!="MARKET"):
            raise RuntimeError("MANAGEMENT_REDUCE_NOT_VERIFIED")
        if strategy._domain.episode is None:raise RuntimeError("MANAGEMENT_EPISODE_UNKNOWN")
        dispatch_order=order
    else:raise RuntimeError("MANAGEMENT_ACTION_FORBIDDEN")
    # Reserve under the existing runtime account/journal lock. A second
    # certificate at this revision cannot reserve after this command bumps it.
    prior=set(strategy._forced_close_orders)
    if kind=="REDUCE":strategy._forced_close_orders.add(client)
    try:
        checkpoint=strategy.on_save()[_KEY]
        if not runtime.reserve_management(command_id=command_id,kind=kind,client_order_id=client,
            instrument_id=str(order.instrument_id),quantity=str(order.quantity.as_decimal()),
            side=order.side.name,episode_id=strategy._domain.episode.id if strategy._domain.episode else "CANCEL_OWNED",
            expected_revision=cert.revision,strategy_state=checkpoint):
            raise RuntimeError("MANAGEMENT_RESERVATION_NOT_COMMITTED")
    except BaseException:
        strategy._forced_close_orders=prior
        raise
    return dispatch_order
