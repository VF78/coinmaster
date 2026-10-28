"""Scoped strict Info report owner for pinned Nautilus 1.231 Hyperliquid execution.

Native LiveExecutionEngine still applies reports and owns orders, fills and PnL.
This adapter never falls back to the pinned opaque bulk report methods.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import deque
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.request import Request, urlopen

from nautilus_trader.adapters.hyperliquid.execution import HyperliquidExecutionClient
from nautilus_trader.adapters.hyperliquid.factories import (
    _resolve_environment, _resolve_product_types,
    get_cached_hyperliquid_http_client, get_cached_hyperliquid_instrument_provider,
)
from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.live.factories import LiveExecClientFactory
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.enums import OrderStatus
from nautilus_trader.model.events import OrderDenied

from coinmaster.ops.hl_info_receipt import IncompleteInfoReport, collect_info_receipt
from coinmaster.ops.hl_live_money import collect_selected_cross_assets, live_perps_money_view, cheap_portfolio_observation
from coinmaster.ops.hl_qualified_reports import qualified_mass_status
from coinmaster.ops.live_recovery import NativeLiveRecoveryScope
from coinmaster.strategy.live_recovery import RecoverableWaveOverlayStrategy, durable_decision_checkpoint


InfoTransport = Callable[[dict[str, Any]], Awaitable[Any]]


class InfoWeightBudget:
    """One bounded strict generation; leave shared-IP headroom for other users."""

    def __init__(self, info: InfoTransport, limit: int = 400) -> None:
        self.info, self.limit, self.used = info, limit, 0

    async def __call__(self, body: dict[str, Any]):
        kind = body["type"]
        if kind not in {'userRole','clearinghouseState','orderStatus','frontendOpenOrders','userAbstraction','userDexAbstraction','userFillsByTime','activeAssetData'}:
            raise IncompleteInfoReport('LIVE_INFO_UNSUPPORTED_REQUEST')
        cost = 60 if kind == "userRole" else 2 if kind in {
            "clearinghouseState", "orderStatus",
        } else 20
        if self.used + cost > self.limit:
            raise IncompleteInfoReport("LIVE_INFO_RATE_BUDGET_EXCEEDED")
        self.used += cost
        value = await self.info(body)
        if kind == "userFillsByTime" and isinstance(value, list):
            self.used += (len(value) + 19) // 20
            if self.used > self.limit:
                raise IncompleteInfoReport("LIVE_INFO_RATE_BUDGET_EXCEEDED")
        return value


def finite_generation_reservation(uncached_orders):
    if type(uncached_orders) is not int or not 0<=uncached_orders<=15:
        raise IncompleteInfoReport('LIVE_INFO_SCOPE_EXCEEDS_GENERATION_CAP')
    return 540+4*uncached_orders


class ReadinessInfoBudget:
    """Atomic prepaid admission; known unused reservation refunded exactly once."""
    def __init__(self):self.spent=deque();self.next_affordable=None
    def reserve(self,weight,now):
        if type(weight) is not int or not 0<weight<=1000:raise IncompleteInfoReport('LIVE_INFO_COST_UNKNOWN')
        while self.spent and now-self.spent[0][0]>=60:self.spent.popleft()
        used=sum(item[1] for item in self.spent)
        if used+weight>1000:
            for item in self.spent:
                used-=item[1]
                if used+weight<=1000:self.next_affordable=item[0]+60;break
            raise IncompleteInfoReport('LIVE_INFO_RATE_BUDGET_EXCEEDED')
        entry=[now,weight,False];self.spent.append(entry);self.next_affordable=None
        return entry
    def settle(self,reservation,actual):
        if (reservation[2] or type(actual) is not int or actual<0):
            raise IncompleteInfoReport('LIVE_INFO_RESERVATION_SETTLEMENT_INVALID')
        overflow=actual>reservation[1]
        reservation[1]=actual;reservation[2]=True
        self.next_affordable=None
        if overflow:raise IncompleteInfoReport('LIVE_INFO_RESERVATION_COST_OVERFLOW')


class SingleAttemptInfoTransport:
    """Pinned collector transport: exactly one urllib POST, no injected retry."""
    def __init__(self,*,testnet,timeout):self.testnet=testnet;self.timeout=timeout
    async def __call__(self,body):
        return await read_info_http(body,testnet=self.testnet,timeout=self.timeout)


def _native_order_fingerprint(order):
    return [str(order.client_order_id),str(order.venue_order_id),str(order.account_id),str(order.strategy_id),
        str(order.instrument_id),str(order.status),str(order.quantity),str(order.filled_qty),
        sorted(map(str,order.trade_ids)),bool(order.is_closed),bool(order.is_pending_cancel)]


def _proven_local_denial(row: dict, order: Any) -> bool:
    """A native OrderDenied with no venue or fill can never require orderStatus."""
    return (
        row.get("state") == "TERMINAL"
        and order.status == OrderStatus.DENIED
        and order.venue_order_id is None
        and order.filled_qty.as_decimal() == 0
        and not order.trade_ids
        and any(isinstance(event, OrderDenied) for event in order.events)
    )
_WS_HANDLERS = (
    (nautilus_pyo3.AccountState, "_handle_account_state"),
    (nautilus_pyo3.OrderAccepted, "_handle_order_accepted_pyo3"),
    (nautilus_pyo3.OrderCanceled, "_handle_order_canceled_pyo3"),
    (nautilus_pyo3.OrderExpired, "_handle_order_expired_pyo3"),
    (nautilus_pyo3.OrderUpdated, "_handle_order_updated_pyo3"),
    (nautilus_pyo3.OrderRejected, "_handle_order_rejected_pyo3"),
    (nautilus_pyo3.OrderCancelRejected, "_handle_order_cancel_rejected_pyo3"),
    (nautilus_pyo3.OrderModifyRejected, "_handle_order_modify_rejected_pyo3"),
    (nautilus_pyo3.OrderStatusReport, "_handle_order_status_report_pyo3"),
    (nautilus_pyo3.FillReport, "_handle_fill_report_pyo3"),
    (nautilus_pyo3.PositionStatusReport, "_handle_position_status_report_pyo3"),
)


async def read_info_http(body: dict[str, Any], *, testnet: bool, timeout: float) -> Any:
    """Bounded read-only POST; no wallet, order endpoint or extra dependency."""
    url = "https://api.hyperliquid-testnet.xyz/info" if testnet else "https://api.hyperliquid.xyz/info"
    request = Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    def read() -> Any:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise IncompleteInfoReport("INFO_HTTP_STATUS")
            return json.load(response)
    return await asyncio.wait_for(asyncio.to_thread(read), timeout=timeout + 1)


class QualifiedInfoBoundary:
    """Mixin shared by the native owner and credential-free fake-node probes."""

    def configure_info_boundary(
        self, scope: NativeLiveRecoveryScope, info: InfoTransport,
        applied_fill_ids: Callable[[], frozenset[str]], *, max_ws_messages: int = 256,
    ) -> None:
        if not isinstance(scope, NativeLiveRecoveryScope) or max_ws_messages <= 0:
            raise ValueError("RECOVERY_SCOPE_OR_WS_LIMIT_INVALID")
        if getattr(self, "_account_address", scope.account_ref).lower() != scope.account_ref.lower():
            raise RuntimeError("RECOVERY_ACCOUNT_ADDRESS_MISMATCH")
        if hasattr(self, "_cm_scope"):
            raise RuntimeError("RECOVERY_BOUNDARY_ALREADY_CONFIGURED")
        socket = getattr(self, "_ws_client", None)
        # Report-only probes may have no socket; such a boundary can never
        # release LIVE. A real client must expose the patched native epoch.
        if socket is None:
            self._cm_ws_epoch = None
        else:
            epoch_reader = getattr(socket, "connection_epoch", None)
            if not callable(epoch_reader):
                raise RuntimeError("WS_CONNECTION_EPOCH_UNAVAILABLE")
            epoch = epoch_reader()
            if not isinstance(epoch, int) or epoch < 0:
                raise RuntimeError("WS_CONNECTION_EPOCH_INVALID")
            self._cm_ws_epoch = epoch
        self._cm_scope = scope
        self._cm_info = info
        self._cm_applied_fill_ids = applied_fill_ids
        self._cm_ws_queue = deque()
        self._cm_ws_limit = max_ws_messages
        self._cm_ws_phase = "BUFFERING"
        self._cm_ws_failure = None
        self._cm_parity_task = None
        self._cm_last_receipt = None
        self._cm_last_margin_assets = None
        self._cm_last_revision = None
        self._cm_runtime = None
        self._cm_inputs_enabled=False
        self._cm_inputs_budget=ReadinessInfoBudget()
        self._cm_money_task=None
        self._cm_account_refresh_wait=None
        self._cm_next_money_request=0.0
        self._cm_generation_started_ns=None
        self._cm_bootstrapped = False
        self._cm_suspend_recovery = None
        self._cm_resume_recovery = None
        self._cm_info_usage = deque()
        self._cm_parity_lock = asyncio.Lock()
        self._cm_refresh_task = None
        self._cm_parity_verifier = None

    def _cm_transport_ok(self) -> bool:
        socket = getattr(self, "_ws_client", None)
        try:
            # The native writer increments this epoch before reconnect becomes
            # active. Two reads bracket current-state checks so a hidden
            # disconnect/reconnect cannot restore a pre-gap healthy view.
            before = socket.connection_epoch()
            active = socket.is_active() and not socket.is_closed()
            after = socket.connection_epoch()
            if before != self._cm_ws_epoch or after != before:
                self._cm_fail("WS_CONNECTION_EPOCH_CHANGED")
                return False
        except BaseException:
            active = False
        if not active:
            self._cm_fail("WS_TRANSPORT_INACTIVE")
        return bool(active)

    def recovery_healthy(self) -> bool:
        if self._cm_ws_failure is not None or self._cm_ws_phase != "LIVE":
            return False
        return self._cm_transport_ok()

    def _cm_fail(self, reason: str) -> None:
        self._cm_ws_failure = reason
        if getattr(self, "_cm_revoke_recovery", None) is not None:
            self._cm_revoke_recovery()

    def bind_recovery_revocation(self, revoke: Callable[[], None]) -> None:
        if not callable(revoke):
            raise TypeError("RECOVERY_REVOCATION_REQUIRED")
        self._cm_revoke_recovery = revoke

    def bind_recovery_suspension(
        self, suspend: Callable[[], None], resume: Callable[[], None],
    ) -> None:
        if not callable(suspend) or not callable(resume):
            raise TypeError("RECOVERY_SUSPENSION_CALLBACKS_REQUIRED")
        self._cm_suspend_recovery = suspend
        self._cm_resume_recovery = resume

    def _cm_require_healthy(self) -> None:
        if self._cm_ws_failure is not None:
            raise RuntimeError("RECOVERY_REQUIRED:" + self._cm_ws_failure)

    def _handle_msg(self, msg: Any) -> None:
        if self._cm_ws_failure is not None:
            return
        if not any(isinstance(msg, kind) for kind, _ in _WS_HANDLERS):
            self._cm_fail("WS_UNKNOWN_EVENT")
            return
        if self._cm_ws_phase != "LIVE":
            if len(self._cm_ws_queue) >= self._cm_ws_limit:
                self._cm_fail("WS_BUFFER_OVERFLOW")
            else:
                self._cm_ws_queue.append(msg)
            return
        self._cm_dispatch(msg)

    def _cm_dispatch(self, msg: Any) -> None:
        try:
            for kind, handler in _WS_HANDLERS:
                if isinstance(msg, kind):
                    getattr(self, handler)(msg)
                    if isinstance(msg, nautilus_pyo3.PositionStatusReport):
                        # Pinned 1.231 only logs these reports; no cache effect.
                        self._cm_fail("WS_POSITION_NO_NATIVE_EFFECT")
                        raise RuntimeError("WS_POSITION_NO_NATIVE_EFFECT")
                    return
            raise RuntimeError("WS_UNKNOWN_EVENT")
        except BaseException:
            if self._cm_ws_failure is None:
                self._cm_fail("WS_DISPATCH_FAILED")
            raise

    def _cm_owned_scope(self):
        """Freeze journal/cache identity for one current-process Info generation."""
        if not self._cm_bootstrapped:
            revision=self._cm_runtime.native_revision() if getattr(self,"_cm_management_only",False) and self._cm_runtime is not None else None
            return self._cm_scope, revision, tuple(self._cache.orders(venue=self.venue)), self._cm_applied_fill_ids(), None
        runtime = self._cm_runtime
        if runtime is None:
            raise IncompleteInfoReport("LIVE_DURABLE_RUNTIME_MISSING")
        revision = runtime.native_revision()
        rows = runtime.all_submissions()
        native_orders = tuple(self._cache.orders(venue=self.venue))
        by_client = {str(order.client_order_id): order for order in native_orders}
        if len(by_client) != len(native_orders):
            raise IncompleteInfoReport("LIVE_DUPLICATE_NATIVE_ORDER")
        if set(by_client) - {row["client_order_id"] for row in rows}:
            raise IncompleteInfoReport("LIVE_FOREIGN_NATIVE_ORDER")
        if set(by_client) != {row["client_order_id"] for row in rows}:
            raise IncompleteInfoReport("LIVE_DURABLE_ORDER_NOT_IN_CACHE")
        durable = []
        signature = []
        local_denied = set()
        for row in rows:
            client = row["client_order_id"]
            order = by_client[client]
            cloid = str(nautilus_pyo3.hyperliquid_cloid_from_client_order_id(
                nautilus_pyo3.ClientOrderId(client)
            ))
            oid = int(str(order.venue_order_id)) if order.venue_order_id is not None else None
            if _proven_local_denial(row, order):
                local_denied.add(client)
            else:
                durable.append((client, cloid, oid))
            signature.append((
                client, oid, str(order.status), str(order.filled_qty),
                tuple(str(tid) for tid in order.trade_ids),
            ))
        applied = runtime.applied_fill_ids()
        if runtime.native_revision() != revision:
            raise IncompleteInfoReport("LIVE_DURABLE_REVISION_MOVED")
        venue_orders = tuple(order for order in native_orders if str(order.client_order_id) not in local_denied)
        return replace(self._cm_scope, durable_orders=tuple(durable)), revision, venue_orders, applied, tuple(signature)

    async def _cm_refresh_native_account_for_generation(self):
        account=self._cache.account_for_venue(self.venue)
        event=getattr(account,'last_event',None)
        old=getattr(event,'id',None) or getattr(event,'event_id',None)
        query_started_ns=self._clock.timestamp_ns()
        self._cm_strategy.query_account(self.account_id)
        while True:
            if time.monotonic_ns()-self._cm_generation_started_ns>9_000_000_000:
                raise IncompleteInfoReport('LIVE_NATIVE_ACCOUNT_GENERATION_STALE')
            account=self._cache.account_for_venue(self.venue);event=getattr(account,'last_event',None)
            current=getattr(event,'id',None) or getattr(event,'event_id',None)
            if current and current!=old and getattr(event,'ts_init',0)>=query_started_ns:return
            await asyncio.sleep(.01)

    async def generate_mass_status(self, lookback_mins=None):
        self._cm_last_receipt = None
        self._cm_last_margin_assets = None
        self._cm_last_revision = None
        try:
            self._cm_require_healthy()
            if self._cm_bootstrapped and self._cm_ws_phase == "LIVE" and self._cm_suspend_recovery is not None:
                self._cm_suspend_recovery()
            for attempt in range(1 if self._cm_inputs_enabled else 4):
                cached_terminal={};archived_fills=();query_anchor_ms=query_anchor_tid=None
                reservation=None;native_refresh_cost=0
                if self._cm_inputs_enabled:
                    frozen_scope,_,native_orders,applied,frozen_signature=self._cm_owned_scope()
                    frozen_applied=applied
                    fingerprints={str(o.client_order_id):_native_order_fingerprint(o) for o in native_orders}
                    cached_terminal,archived_fills,query_anchor_ms,query_anchor_tid=self._cm_runtime.info_query_evidence(fingerprints,applied)
                    fresh_orders=len(frozen_scope.durable_orders)-len(cached_terminal)
                    # Reserve complete minimum before ANY request; terminal history
                    # remains retained and validated, only redundant status reads go.
                    reservation=self._cm_inputs_budget.reserve(finite_generation_reservation(fresh_orders),time.monotonic())
                    self._cm_generation_started_ns=time.monotonic_ns()
                now = time.monotonic()
                while self._cm_info_usage and now - self._cm_info_usage[0][0] >= 60:
                    self._cm_info_usage.popleft()
                # Legacy attempts stay under400; readiness prepaid600 includes native16.
                # Legacy retries also consume the
                # rolling 1000/min budget. The transport wrapper enforces the
                # remaining allowance on each request, including fill rows.
                remaining = 1000 - sum(weight for _, weight in self._cm_info_usage)
                if remaining <= 0:
                    raise IncompleteInfoReport("LIVE_INFO_RATE_BUDGET_EXCEEDED")
                weighted_info = InfoWeightBudget(self._cm_info, 584 if self._cm_inputs_enabled else min(400, remaining))
                revision = None
                try:
                    if self._cm_inputs_enabled:
                        if type(self._cm_info) is not SingleAttemptInfoTransport:
                            raise IncompleteInfoReport('LIVE_READINESS_TRANSPORT_SINGLE_ATTEMPT_REQUIRED')
                        native_refresh_cost=16
                        await self._cm_refresh_native_account_for_generation()
                    scope, revision, native_orders, applied, signature = self._cm_owned_scope()
                    if self._cm_inputs_enabled and (scope.durable_orders!=frozen_scope.durable_orders or applied!=frozen_applied or signature!=frozen_signature):
                        raise IncompleteInfoReport('LIVE_RESERVED_SCOPE_MOVED')
                    expected = {cloid: oid for _, cloid, oid in scope.durable_orders}
                    end = self._clock.timestamp_ns() // 1_000_000
                    async def sweep(at: int):
                        return await collect_info_receipt(
                            weighted_info, account=scope.account_ref, dex=scope.dex,
                            anchor_ms=scope.anchor_ms, anchor_tid=scope.anchor_tid,
                            end_ms=at, expected_orders=expected, owned_coins=scope.owned_coins,
                            require_money_scope=True,cached_terminal_statuses=cached_terminal,
                            archived_fills=archived_fills,query_anchor_ms=query_anchor_ms,query_anchor_tid=query_anchor_tid,
                            allow_fill_subdivision=not self._cm_inputs_enabled,
                        )

                    first = await sweep(end)
                    second = await sweep(max(end + 1, self._clock.timestamp_ns() // 1_000_000))
                    selected_assets = await collect_selected_cross_assets(
                        weighted_info, account_ref=scope.account_ref, coins=scope.owned_coins,
                    )
                    instruments = {
                        coin: self._cache.instrument(InstrumentId.from_str(f"{coin}-USD-PERP.HYPERLIQUID"))
                        for coin in scope.owned_coins
                    }
                    if any(item is None for item in instruments.values()):
                        raise IncompleteInfoReport("NATIVE_INSTRUMENT_MISSING")
                    mass = qualified_mass_status(
                        first, second, expected_account_ref=scope.account_ref, expected_dex=scope.dex,
                        account_id=self.account_id, client_id=self.id, venue=self.venue,
                        instruments=instruments, durable_orders={
                            client: (cloid, oid) for client, cloid, oid in scope.durable_orders
                        }, native_orders=native_orders, applied_trade_ids=applied,
                        ts_init=self._clock.timestamp_ns(),
                    )
                    if revision is not None:
                        _, current_revision, _, current_applied, current_signature = self._cm_owned_scope()
                        if (current_revision, current_applied, current_signature) != (revision, applied, signature):
                            raise IncompleteInfoReport("LIVE_DURABLE_REVISION_MOVED")
                    if self._cm_inputs_enabled and time.monotonic_ns()-self._cm_generation_started_ns>9_000_000_000:
                        raise IncompleteInfoReport('LIVE_INFO_GENERATION_OLDEST_RESPONSE_STALE')
                    self._cm_last_receipt = second
                    self._cm_last_margin_assets = selected_assets
                    self._cm_last_revision = revision
                    return mass
                except IncompleteInfoReport as error:
                    race = (
                        revision is not None and self._cm_runtime is not None
                        and self._cm_runtime.native_revision() != revision
                    )
                    if attempt == 3 or not (
                        str(error) in {
                            "ORDER_STATUS_UNKNOWN", "LIVE_DURABLE_ORDER_NOT_IN_CACHE",
                            "LIVE_DURABLE_REVISION_MOVED",
                        }
                        or (race and str(error) in {
                            "INFO_GENERATION_NOT_CONVERGED",
                            "OPEN_ORDER_STATUS_FIELD_MISMATCH",
                            "ORDER_OPEN_STATUS_MISMATCH",
                        })
                    ):
                        raise
                    await asyncio.sleep(0.25)
                finally:
                    if self._cm_inputs_enabled and reservation is not None:
                        self._cm_inputs_budget.settle(reservation,weighted_info.used+native_refresh_cost)
                    elif weighted_info.used:
                        self._cm_info_usage.append((now, weighted_info.used))
        except IncompleteInfoReport as error:
            if str(error) == "LIVE_INFO_RATE_BUDGET_EXCEEDED":
                if self._cm_suspend_recovery is not None:
                    self._cm_suspend_recovery()
            elif self._cm_ws_failure is None:
                self._cm_fail("INFO_GENERATION_FAILED")
            raise
        except BaseException:
            if self._cm_ws_failure is None:
                self._cm_fail("INFO_GENERATION_FAILED")
            raise

    async def release_after_effect_parity(
        self, verify: Callable[[Any], Awaitable[bool]], *, monitor_interval_secs: float = 5.0,
    ) -> None:
        """Release WS only after fresh strict reports match native/domain/account effects.

        A successful handler return is never a delivery receipt. The verifier must
        examine actual native state; this method does not confirm strategy recovery.
        """
        self._cm_require_healthy()
        if self._cm_ws_phase != "BUFFERING" or not 0 < monitor_interval_secs <= 60:
            raise RuntimeError("WS_HANDOVER_STATE_OR_MONITOR_INVALID")
        if not self._cm_transport_ok():
            self._cm_require_healthy()
        for _ in range(4):
            while self._cm_ws_queue:
                self._cm_require_healthy()
                self._cm_dispatch(self._cm_ws_queue.popleft())
            await asyncio.sleep(0)
            self._cm_require_healthy()
            if getattr(self, "_pending_fills", {}):
                self._cm_fail("WS_FILL_PENDING_WITHOUT_NATIVE_EFFECT")
                self._cm_require_healthy()
            mass = await self.generate_mass_status()
            if self._cm_ws_queue:
                continue
            try:
                verified = await verify(mass)
            except BaseException:
                self._cm_fail("WS_EFFECT_PARITY_FAILED")
                raise
            if verified is not True:
                self._cm_fail("WS_EFFECT_PARITY_FAILED")
                break
            if self._cm_ws_queue:
                continue
            self._cm_require_healthy()
            if not self._cm_transport_ok():
                self._cm_require_healthy()
            self._cm_ws_phase = "LIVE"
            self._cm_parity_verifier = verify
            self._cm_parity_task = asyncio.get_running_loop().create_task(
                self._cm_monitor_parity(verify, monitor_interval_secs)
            )
            return
        if self._cm_ws_failure is None:
            self._cm_fail("WS_HANDOVER_NOT_CONVERGED")
        self._cm_require_healthy()

    def request_effect_parity_refresh(self) -> bool:
        """One candidate-triggered strict refresh, serialized with the monitor."""
        if self._cm_inputs_enabled and self._cm_inputs_budget.next_affordable is not None and time.monotonic()<self._cm_inputs_budget.next_affordable:
            if getattr(self,'_cm_affordable_handle',None) is None:
                def wake():
                    self._cm_affordable_handle=None
                    self.request_effect_parity_refresh()
                self._cm_affordable_handle=asyncio.get_running_loop().call_later(self._cm_inputs_budget.next_affordable-time.monotonic(),wake)
            return False
        if self._cm_ws_phase != "LIVE" or self._cm_ws_failure or self._cm_parity_verifier is None:
            return False
        if self._cm_refresh_task is None or self._cm_refresh_task.done():
            self._cm_refresh_task = asyncio.get_running_loop().create_task(
                self._cm_refresh_effect_parity()
            )
        return True

    async def _cm_refresh_effect_parity(self) -> None:
        try:
            async with self._cm_parity_lock:
                if self._cm_suspend_recovery is not None:
                    self._cm_suspend_recovery()
                mass = await self.generate_mass_status()
                if await self._cm_parity_verifier(mass) is not True:
                    raise IncompleteInfoReport("LIVE_OWNED_EFFECT_PARITY_FAILED")
                self._cm_require_healthy()
                if not self._cm_transport_ok():
                    self._cm_require_healthy()
                if self._cm_resume_recovery is not None:
                    self._cm_resume_recovery()
        except IncompleteInfoReport as error:
            # Shared-IP budget exhaustion leaves the candidate queued. No
            # evidence is accepted and the increase gate stays suspended.
            if str(error) == "LIVE_INFO_RATE_BUDGET_EXCEEDED":
                self.request_effect_parity_refresh()  # one earliest-affordable scheduled wake
            else:
                self._cm_fail("WS_ON_DEMAND_EFFECT_PARITY_FAILED")
        except asyncio.CancelledError:
            self._cm_fail("WS_ON_DEMAND_EFFECT_PARITY_CANCELED")
            raise
        except BaseException:
            self._cm_fail("WS_ON_DEMAND_EFFECT_PARITY_FAILED")

    async def collect_user_funding_observation(self,strategy):
        """One actual bounded cashflow page; no funding forecast or cash posting."""
        if not self._cm_inputs_enabled or not self.recovery_healthy():return False
        async with self._cm_parity_lock:
            cursor=self._cm_runtime.evidence_cursor('userFunding')
            start=self._cm_scope.anchor_ms if cursor is None else cursor['end_ms']
            end=min(self._clock.timestamp_ns()//1_000_000,start+86_400_000)
            if end<=start:return False
            # Separate bounded source observation, never inside a600 generation.
            # Official per20-row item weight applies to userFunding as to fills.
            reservation=self._cm_inputs_budget.reserve(45,time.monotonic());actual=20
            try:
                rows=await self._cm_info({'type':'userFunding','user':self._cm_scope.account_ref,'startTime':start,'endTime':end})
                if isinstance(rows,list):actual+=(len(rows)+19)//20
                if not isinstance(rows,list) or len(rows)>=500:raise IncompleteInfoReport('LIVE_FUNDING_PAGE_COMPLETENESS_UNKNOWN')
                if any(type(row.get('time')) is not int or not start<=row['time']<=end for row in rows):raise IncompleteInfoReport('LIVE_FUNDING_PAGE_TIME_INVALID')
                self._cm_runtime.record_funding_page(rows,expected_cursor=cursor,next_cursor={'end_ms':end},complete=True)
            finally:self._cm_inputs_budget.settle(reservation,actual)
            if rows:strategy._live_inputs_dirty=True;strategy._last_live_input_observation=None
            return True

    def request_portfolio_observation(self,strategy):
        if not self._cm_inputs_enabled or not self.recovery_healthy() or time.monotonic()<self._cm_next_money_request:return False
        if self._cm_money_task is not None and not self._cm_money_task.done():return True
        self._cm_next_money_request=time.monotonic()+1
        self._cm_money_task=asyncio.get_running_loop().create_task(self._cm_collect_portfolio_observation(strategy))
        return True

    async def _cm_collect_portfolio_observation(self,strategy):
        try:
            async with self._cm_parity_lock:
                if not self.recovery_healthy():return
                account=self._cache.account_for_venue(self.venue)
                event_id=str(getattr(getattr(account,'last_event',None),'id',None) or getattr(getattr(account,'last_event',None),'event_id',''))
                started=time.monotonic_ns()
                if self._cm_account_refresh_wait is not None:
                    old_id,query_started=self._cm_account_refresh_wait
                    if event_id==old_id:return  # Real native AccountState has not arrived.
                    if started-query_started>9_000_000_000:
                        self._cm_account_refresh_wait=None
                        raise IncompleteInfoReport('PORTFOLIO_ACCOUNT_REFRESH_STALE')
                    started=query_started;self._cm_account_refresh_wait=None
                    strategy._live_inputs_dirty=False
                revision=self._cm_runtime.native_revision();epoch=strategy._c1_fill_epoch;ws=self._cm_ws_epoch
                fingerprints=tuple(_native_order_fingerprint(o) for o in self._cache.orders(venue=self.venue))
                self._cm_inputs_budget.reserve(2,time.monotonic())
                raw=await self._cm_info({'type':'clearinghouseState','user':self._cm_scope.account_ref,'dex':self._cm_scope.dex})
                complete=time.monotonic_ns();available=self._clock.timestamp_ns()
                if not self.recovery_healthy() or self._cm_runtime.native_revision()!=revision or strategy._c1_fill_epoch!=epoch or self._cm_ws_epoch!=ws or fingerprints!=tuple(_native_order_fingerprint(o) for o in self._cache.orders(venue=self.venue)):
                    raise IncompleteInfoReport('PORTFOLIO_NATIVE_REVISION_MOVED')
                account=self._cache.account_for_venue(self.venue)
                if getattr(strategy,'_live_inputs_dirty',False):raise IncompleteInfoReport('PORTFOLIO_ACCOUNT_REFRESH_REQUIRED')
                observation=cheap_portfolio_observation(raw,account_id=str(self.account_id),native_account=account,
                    native_positions=tuple(self._cache.positions_open()),strategy_id=str(strategy.id),revision=revision,
                    fill_epoch=epoch,ws_epoch=ws,started_ns=started,completed_ns=complete,available_ns=available)
                strategy._last_live_input_observation=observation
                self._cm_runtime.append_evidence('portfolio:'+str(available),'account',dict(source='ONE_CLEARINGHOUSE_RESPONSE',raw=raw,
                    native_account_event_id=observation.native_account_event_id,generation_started_ns=started,response_completed_ns=complete,
                    source_available_ns=available,native_revision=revision,fill_epoch=epoch,ws_epoch=ws,command_capability=False))
        except IncompleteInfoReport as error:
            strategy._last_live_input_observation=None
            strategy._live_inputs_reason=str(error)
            if str(error)=='PORTFOLIO_ACCOUNT_REFRESH_REQUIRED' and self._cm_account_refresh_wait is None:
                try:
                    # v1.231 source: perp2+spot2, each <=4 HTTP attempts =>16.
                    self._cm_inputs_budget.reserve(16,time.monotonic())
                    account=self._cache.account_for_venue(self.venue)
                    old=str(getattr(getattr(account,'last_event',None),'id',None) or getattr(getattr(account,'last_event',None),'event_id',''))
                    self._cm_account_refresh_wait=(old,time.monotonic_ns())
                    strategy.query_account(self.account_id)  # Stock public command path.
                except BaseException as query_error:
                    self._cm_account_refresh_wait=None;strategy._live_inputs_reason=repr(query_error)
            # A money failure never revokes an independent ownership certificate.
        except BaseException as error:
            strategy._last_live_input_observation=None;strategy._live_inputs_reason=repr(error)

    def save_verified_query_evidence(self,strategy,receipt,orders):
        if not self._cm_inputs_enabled:return
        if self._cm_generation_started_ns is None or time.monotonic_ns()-self._cm_generation_started_ns>9_000_000_000:
            raise IncompleteInfoReport('LIVE_INFO_GENERATION_OLDEST_RESPONSE_STALE')
        rows={row['client_order_id']:row for row in self._cm_runtime.all_submissions()};proofs={}
        statuses={str(item['order']['order'].get('cloid','')).lower():item for item in receipt.order_statuses}
        for order in orders:
            client=str(order.client_order_id)
            if client not in rows or rows[client]['state']!='TERMINAL' or not order.is_closed or order.is_pending_cancel:continue
            cloid=str(nautilus_pyo3.hyperliquid_cloid_from_client_order_id(nautilus_pyo3.ClientOrderId(client)))
            status=statuses.get(cloid.lower())
            if status is None or status['order']['status'] not in ('filled','canceled'):continue
            journal_fills=self._cm_runtime._journal_order_fills(client)
            if {str(row[0]) for row in journal_fills}!=set(map(str,order.trade_ids)):continue
            proofs[cloid]=dict(client_id=client,native_fingerprint=_native_order_fingerprint(order),journal_fills=journal_fills,status=status)
        self._cm_runtime.save_verified_info_checkpoint(receipt,proofs,self._cm_runtime.native_revision())

    async def _cm_monitor_parity(
        self, verify: Callable[[Any], Awaitable[bool]], interval: float,
    ) -> None:
        try:
            while self._cm_ws_phase == "LIVE" and self._cm_ws_failure is None:
                await asyncio.sleep(interval)
                if self._cm_inputs_enabled:
                    # Cheap transport health only. Expiry never launches full Info.
                    if not self._cm_transport_ok():return
                    continue
                if not self._cm_transport_ok():
                    return
                seen_parity_error = False
                for attempt in range(4):
                    try:
                        async with self._cm_parity_lock:
                            if self._cm_suspend_recovery is not None:
                                self._cm_suspend_recovery()
                            mass = await self.generate_mass_status()
                            if await verify(mass) is not True:
                                raise IncompleteInfoReport("LIVE_OWNED_EFFECT_PARITY_FAILED")
                            self._cm_require_healthy()
                            if not self._cm_transport_ok():
                                self._cm_require_healthy()
                            if self._cm_resume_recovery is not None:
                                self._cm_resume_recovery()
                        break
                    except IncompleteInfoReport as error:
                        if str(error) == "LIVE_INFO_RATE_BUDGET_EXCEEDED":
                            if seen_parity_error:
                                raise  # A proved mismatch may not be erased by retry budget.
                            break  # Stale evidence blocks increases until a later affordable read.
                        seen_parity_error = True
                        if attempt == 3 or str(error) not in {
                            "LIVE_VERIFIER_REVISION_MOVED", "LIVE_OWNED_ORDER_SET_MISMATCH",
                            "LIVE_OWNED_ORDER_PARITY_FAILED", "LIVE_OWNED_FILL_PARITY_FAILED",
                            "LIVE_EPISODE_POSITION_MISMATCH", "LIVE_MONEY_NATIVE_BALANCE_MISMATCH",
                            "LIVE_OWNED_EFFECT_PARITY_FAILED",
                        }:
                            raise
                        await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            if self._cm_ws_failure is None:
                self._cm_fail("WS_PARITY_MONITOR_CANCELED")
            raise
        except BaseException:
            if self._cm_ws_failure is None:
                self._cm_fail("WS_PERIODIC_EFFECT_PARITY_FAILED")


class QualifiedHyperliquidExecutionClient(QualifiedInfoBoundary, HyperliquidExecutionClient):
    def __init__(self, *, scope: NativeLiveRecoveryScope, info: InfoTransport,
                 applied_fill_ids: Callable[[], frozenset[str]], **native_kwargs) -> None:
        super().__init__(**native_kwargs)
        self.configure_info_boundary(scope, info, applied_fill_ids)

    async def _disconnect(self) -> None:
        self._cm_fail("WS_DISCONNECTED")
        if self._cm_parity_task is not None:
            self._cm_parity_task.cancel()
        if self._cm_refresh_task is not None:
            self._cm_refresh_task.cancel()
        await super()._disconnect()

    async def generate_order_status_reports(self, command):
        raise RuntimeError("UNQUALIFIED_NATIVE_ORDER_BULK_FORBIDDEN")

    async def generate_fill_reports(self, command):
        raise RuntimeError("UNQUALIFIED_NATIVE_FILL_BULK_FORBIDDEN")

    async def generate_position_status_reports(self, command):
        raise RuntimeError("UNQUALIFIED_NATIVE_POSITION_BULK_FORBIDDEN")

    async def generate_order_status_report(self, command):
        raise RuntimeError("UNQUALIFIED_NATIVE_ORDER_SINGLE_FORBIDDEN")


class ScopedHyperliquidExecClientFactory(LiveExecClientFactory):
    """Must be explicitly bound to one account and durable runtime before build."""
    _scope = None
    _runtime = None
    _info = None
    _strategy = None

    @classmethod
    def bind(
        cls, scope: NativeLiveRecoveryScope, runtime, strategy, info: InfoTransport | None = None,
        *, account_lock_root: Path = Path("/run/lock/coinmaster"),
    ):
        if not isinstance(scope, NativeLiveRecoveryScope) or runtime is None or strategy is None:
            raise ValueError("RECOVERY_SCOPE_AND_STRATEGY_REQUIRED")
        journal_ids = {row["client_order_id"] for row in runtime.all_submissions()}
        scoped_ids = {client for client, _, _ in scope.durable_orders}
        if journal_ids != scoped_ids:
            raise ValueError("RECOVERY_DURABLE_SCOPE_MISMATCH")
        acquire = getattr(runtime, "acquire_live_account", None)
        if not callable(acquire):
            raise RuntimeError("LIVE_ACCOUNT_LEASE_REQUIRED")
        acquire(scope.account_ref, "HYPERLIQUID", lock_root=account_lock_root)
        class Bound(cls):
            _scope = scope
            _runtime = runtime
            _strategy = strategy
            _info = info
        return Bound

    @classmethod
    def create(cls, loop, name, config, msgbus, cache, clock):
        if cls._scope is None or cls._runtime is None or cls._strategy is None:
            raise RuntimeError("RECOVERY_SCOPE_NOT_BOUND")
        if config.include_builder_attribution:
            raise RuntimeError("LIVE_BUILDER_FEE_UNQUALIFIED")
        environment = _resolve_environment(config.environment)
        address = nautilus_pyo3.hyperliquid_resolve_execution_account_address(
            private_key=config.private_key, vault_address=config.vault_address,
            account_address=config.account_address, environment=environment,
        )
        if not address or address.lower() != cls._scope.account_ref.lower():
            raise RuntimeError("RECOVERY_ACCOUNT_ADDRESS_MISMATCH")
        client = get_cached_hyperliquid_http_client(
            private_key=config.private_key, vault_address=config.vault_address,
            account_address=config.account_address, timeout_secs=config.http_timeout_secs,
            environment=environment, proxy_url=config.proxy_url,
            normalize_prices=config.normalize_prices,
            include_builder_attribution=config.include_builder_attribution,
        )
        provider = get_cached_hyperliquid_instrument_provider(
            client=client, config=config.instrument_provider,
            product_types=_resolve_product_types(config.product_types),
        )
        info = cls._info
        if info is None:
            info = SingleAttemptInfoTransport(testnet=environment == nautilus_pyo3.HyperliquidEnvironment.TESTNET,
                timeout=config.http_timeout_secs)
        owner = QualifiedHyperliquidExecutionClient(
            loop=loop, client=client, msgbus=msgbus, cache=cache, clock=clock,
            instrument_provider=provider, config=config, name=name, account_address=address,
            scope=cls._scope, info=info, applied_fill_ids=cls._runtime.applied_fill_ids,
        )
        owner._cm_runtime = cls._runtime
        bind_clean_flat_live_handover(owner, cls._strategy, cls._runtime,manage_only=getattr(cls._strategy,"_manage_only_preparation",False))
        return owner


def bind_clean_flat_live_handover(
    client: QualifiedInfoBoundary, strategy, runtime, *,
    monitor_interval_secs: float = 30.0, manage_only: bool = False,
) -> None:
    """Require clean-flat restart bootstrap, then monitor current-process owned state.

    Native startup reconciliation precedes strategy on_start. Existing open
    exposure still fails closed on restart; only orders born after this clean
    bootstrap can enter the periodic owned-state parity path.
    """
    if not isinstance(client, QualifiedInfoBoundary) or not hasattr(client, "_cm_scope"):
        raise RuntimeError("LIVE_HANDOVER_CLIENT_UNQUALIFIED")
    if not isinstance(strategy, RecoverableWaveOverlayStrategy):
        raise RuntimeError("LIVE_HANDOVER_STRATEGY_UNQUALIFIED")
    scope = client._cm_scope
    client._cm_management_only=manage_only
    client._cm_inputs_enabled=getattr(strategy,'_input_readiness_preparation',False)
    client._cm_strategy=strategy
    if client._cm_inputs_enabled:
        if type(client._cm_info) is not SingleAttemptInfoTransport:
            raise RuntimeError('LIVE_READINESS_TRANSPORT_SINGLE_ATTEMPT_REQUIRED')
        strategy._live_input_request=lambda:client.request_portfolio_observation(strategy)
        strategy._live_input_ws_epoch=lambda:client._cm_ws_epoch
    if strategy.config.research_residual_recovery and not manage_only:
        raise RuntimeError("E4_C1_LIVE_REQUIRES_MANAGE_ONLY_PREPARATION")
    if manage_only and (not strategy._manage_only_preparation or not strategy._checkpoint_policy_valid):
        raise RuntimeError("MANAGEMENT_POLICY_LOAD_REQUIRED")
    expected_ids = (
        InstrumentId.from_str("BTC-USD-PERP.HYPERLIQUID"),
        InstrumentId.from_str("SOL-USD-PERP.HYPERLIQUID"),
    )
    if (
        client.venue.value != "HYPERLIQUID"
        or (strategy.config.btc_id, strategy.config.sol_id) != expected_ids
        or scope.dex != "" or scope.owned_coins != frozenset({"BTC", "SOL"})
    ):
        raise RuntimeError("LIVE_HANDOVER_INSTRUMENT_SCOPE_MISMATCH")
    if runtime is None or not callable(getattr(runtime, "all_submissions", None)):
        raise RuntimeError("LIVE_HANDOVER_DURABLE_RUNTIME_REQUIRED")
    latest_money = [None]

    async def verify(mass) -> bool:
        if (
            strategy.cache is not client._cache
            or strategy.msgbus is not client._msgbus
            or strategy.trader_id != client.trader_id
        ):
            raise IncompleteInfoReport("LIVE_HANDOVER_NATIVE_ROUTE_MISMATCH")
        receipt = client._cm_last_receipt
        if getattr(client,'_cm_inputs_enabled',False) and (client._cm_generation_started_ns is None or time.monotonic_ns()-client._cm_generation_started_ns>9_000_000_000):raise IncompleteInfoReport('LIVE_INFO_GENERATION_OLDEST_RESPONSE_STALE')
        if client._cm_bootstrapped and runtime.native_revision() != client._cm_last_revision:
            raise IncompleteInfoReport("LIVE_VERIFIER_REVISION_MOVED")
        if receipt is None or mass.account_id != client.account_id or mass.venue != client.venue:
            raise IncompleteInfoReport("LIVE_HANDOVER_GENERATION_MISSING")
        if not manage_only and not client._cm_bootstrapped and scope.durable_orders:
            raise IncompleteInfoReport("LIVE_OPEN_FUNDING_CURSOR_UNPROVEN")
        native_orders = tuple(client._cache.orders(venue=client.venue))
        native_positions = tuple(client._cache.positions_open())
        if not manage_only and not client._cm_bootstrapped:
            if (
                scope.durable_orders or runtime.all_submissions() or runtime.applied_fill_ids()
                or mass.order_reports or mass.fill_reports or mass.position_reports
                or native_orders or native_positions
                or strategy._domain.episode is not None or strategy._pending_by_order
            ):
                raise IncompleteInfoReport("LIVE_OPEN_FUNDING_CURSOR_UNPROVEN")
        else:
            rows = runtime.all_submissions()
            journal = {row["client_order_id"]: row for row in rows}
            orders = {str(order.client_order_id): order for order in native_orders}
            reports = {
                str(report.client_order_id): report
                for report in mass.order_reports.values()
            }
            local_denied = {
                client_id for client_id, row in journal.items()
                if client_id in orders and _proven_local_denial(row, orders[client_id])
            }
            if (
                len(journal) != len(rows)
                or len(orders) != len(native_orders)
                or len(reports) != len(mass.order_reports)
                or set(journal) != set(orders) or set(reports) != set(journal) - local_denied
                or not set(strategy._pending_by_order).issubset(journal)
                or set(strategy._pending_by_order) & local_denied
            ):
                raise IncompleteInfoReport("LIVE_OWNED_ORDER_SET_MISMATCH")
            for client_id, order in orders.items():
                if client_id in local_denied:
                    continue
                report = reports[client_id]
                row = journal[client_id]
                if (
                    str(order.strategy_id) != str(strategy.id)
                    or row["instrument_id"] != str(order.instrument_id)
                    or report.instrument_id != order.instrument_id
                    or report.venue_order_id != order.venue_order_id
                    or report.quantity != order.quantity
                    or report.filled_qty != order.filled_qty
                    or report.order_status != order.status
                    or bool(report.reduce_only) != bool(row["body"]["reduce_only"])
                ):
                    raise IncompleteInfoReport("LIVE_OWNED_ORDER_PARITY_FAILED")
            fill_ids = [
                str(report.trade_id)
                for batch in mass.fill_reports.values() for report in batch
            ]
            if len(fill_ids) != len(set(fill_ids)) or set(fill_ids) != runtime.applied_fill_ids():
                raise IncompleteInfoReport("LIVE_OWNED_FILL_PARITY_FAILED")
            if any(str(position.strategy_id) != str(strategy.id) for position in native_positions):
                raise IncompleteInfoReport("LIVE_FOREIGN_NATIVE_POSITION")
            episode = strategy._domain.episode
            by_coin = {str(position.instrument_id): position for position in native_positions}
            if len(by_coin) != len(native_positions) or (episode is None and by_coin):
                raise IncompleteInfoReport("LIVE_EPISODE_POSITION_MISMATCH")
            if episode is not None and not manage_only:
                btc = by_coin.get(str(strategy.config.btc_id))
                sol = by_coin.get(str(strategy.config.sol_id))
                # Domain float arithmetic may drift below one native lot;
                # normalize only within half an actual instrument size step.
                def same_episode_size(value: float, native_size: Decimal, instrument_id: InstrumentId) -> bool:
                    instrument = client._cache.instrument(instrument_id)
                    domain_size = Decimal(str(value))
                    if instrument is None or not domain_size.is_finite():
                        return False
                    step = instrument.size_increment.as_decimal()
                    if step <= 0:
                        return False
                    normalized = (domain_size / step).to_integral_value() * step
                    return abs(domain_size - normalized) < step / 2 and normalized == native_size

                if (
                    not same_episode_size(episode.btc_open_qty, btc.quantity.as_decimal() if btc else Decimal("0"), strategy.config.btc_id)
                    or not same_episode_size(episode.sol_qty, sol.quantity.as_decimal() if sol else Decimal("0"), strategy.config.sol_id)
                    or (btc is not None and btc.is_long != (episode.side == 1))
                    or (sol is not None and sol.is_long != (episode.side == -1))
                ):
                    raise IncompleteInfoReport("LIVE_EPISODE_POSITION_MISMATCH")
        checkpoint = runtime.strategy_checkpoint()
        if checkpoint is not None and durable_decision_checkpoint(checkpoint[0]) != durable_decision_checkpoint(
            strategy.on_save()["wave_overlay_live_recovery_v1"]
        ):
            raise IncompleteInfoReport("LIVE_HANDOVER_DOMAIN_CHECKPOINT_MISMATCH")
        if manage_only:
            from coinmaster.ops.live_recovery import ManagementCertificate,management_cache_evidence
            from coinmaster.strategy.live_recovery import recovery_policy_hash
            now_ns=client._clock.timestamp_ns()
            generation=receipt.end_ms*1_000_000
            revision=client._cm_last_revision
            if (not receipt.fill_anchor_proven or receipt.account.lower()!=scope.account_ref.lower() or receipt.dex!=scope.dex
                or not 0<=now_ns-generation<=9_000_000_000 or type(revision) is not int or revision!=runtime.native_revision()
                or not strategy._checkpoint_policy_valid
                or strategy._loaded_policy_sha256!=recovery_policy_hash(strategy.config,strategy._candidate)):
                raise IncompleteInfoReport("MANAGEMENT_GENERATION_UNPROVEN")
            venue_positions=[p for batch in mass.position_reports.values() for p in batch]
            by_report={str(p.instrument_id):p for p in venue_positions}
            if len(by_report)!=len(venue_positions) or set(by_report)!=set(by_coin):
                raise IncompleteInfoReport("MANAGEMENT_FRESH_POSITION_SET_MISMATCH")
            for instrument,position in by_coin.items():
                report=by_report[instrument]
                quantity=report.quantity.as_decimal()
                side="LONG" if position.is_long else "SHORT"
                if (str(report.account_id)!=str(client.account_id) or report.position_side.name!=side
                    or not quantity.is_finite() or quantity<=0 or quantity!=position.quantity.as_decimal()):
                    raise IncompleteInfoReport("MANAGEMENT_FRESH_POSITION_PARITY_FAILED")
            # Every held native lifecycle must be attributable to journal-owned
            # orders and already-applied execution IDs. No floating size inference.
            for position in native_positions:
                if not position.events or any(str(e.client_order_id) not in journal or str(e.trade_id) not in runtime.applied_fill_ids() or journal[str(e.client_order_id)]["episode_id"]!=episode.id for e in position.events):
                    raise IncompleteInfoReport("MANAGEMENT_POSITION_LINEAGE_UNKNOWN")
            if any(str(p.account_id)!=str(client.account_id) for p in native_positions):
                raise IncompleteInfoReport("MANAGEMENT_POSITION_ACCOUNT_MISMATCH")
            for order in native_orders:
                report=reports.get(str(order.client_order_id))
                if str(order.client_order_id) in local_denied:continue
                if (report is None or str(report.account_id)!=str(client.account_id)
                    or (order.account_id is not None and str(order.account_id)!=str(client.account_id))
                    or report.order_side!=order.side):
                    raise IncompleteInfoReport("MANAGEMENT_ORDER_ACCOUNT_OR_SIDE_MISMATCH")
            positions,orders,signature=management_cache_evidence(client._cache,client.venue)
            runtime.reconcile_management_commands({o[0] for o in orders if o[4]},revision)
            if runtime.native_revision()!=revision:raise IncompleteInfoReport("MANAGEMENT_GENERATION_REVISION_MOVED")
            if getattr(client,'_cm_inputs_enabled',False):client.save_verified_query_evidence(strategy,receipt,native_orders)
            strategy._management_certificate=ManagementCertificate(revision,generation+9_000_000_000,
                recovery_policy_hash(strategy.config,strategy._candidate),signature,
                hashlib.sha256(durable_decision_checkpoint(strategy.on_save()["wave_overlay_live_recovery_v1"])).hexdigest(),
                positions,orders,generation,client.recovery_healthy)
            return True
        account = client._cache.account_for_venue(client.venue)
        candidate_money = live_perps_money_view(
            receipt, account_ref=scope.account_ref, dex=scope.dex,
            account_id=str(client.account_id), native_account=account,
            native_positions=native_positions, now_ms=client._clock.timestamp_ns() // 1_000_000,
            selected_assets=client._cm_last_margin_assets or (),
            native_revision=runtime.native_revision(),
        )
        if not candidate_money.selected_assets:
            raise IncompleteInfoReport("LIVE_SELECTED_MARGIN_UNKNOWN")
        if (not client._cm_bootstrapped
                and candidate_money.equity != getattr(
                    runtime, "flat_epoch_balance", strategy.config.active_seed)):
            raise IncompleteInfoReport("LIVE_FLAT_EPOCH_BALANCE_CHANGED")
        if client._cm_bootstrapped and runtime.native_revision() != client._cm_last_revision:
            raise IncompleteInfoReport("LIVE_VERIFIER_REVISION_MOVED")
        if getattr(client,'_cm_inputs_enabled',False):client.save_verified_query_evidence(strategy,receipt,native_orders)
        latest_money[0] = candidate_money
        return True

    async def release() -> None:
        await client.release_after_effect_parity(
            verify, monitor_interval_secs=monitor_interval_secs,
        )
        if manage_only:
            if strategy._management_certificate is None or not client.recovery_healthy():
                raise RuntimeError("MANAGEMENT_HANDOVER_UNCONFIRMED")
            client._cm_bootstrapped=True
            strategy.recovery_confirmed=False
            return
        if latest_money[0] is None or not client.recovery_healthy():
            raise RuntimeError("LIVE_HANDOVER_UNCONFIRMED")
        client._cm_bootstrapped = True
        strategy.recovery_confirmed = True

    strategy.attach_live_money_view(lambda: latest_money[0])
    strategy.attach_live_refresh(client.request_effect_parity_refresh)
    strategy.attach_recovery_health(client.recovery_healthy)
    client.bind_recovery_revocation(strategy.revoke_management if manage_only else lambda: setattr(strategy, "recovery_confirmed", False))
    client.bind_recovery_suspension(
        strategy.revoke_management if manage_only else lambda: setattr(strategy, "recovery_confirmed", False),
        (lambda: None) if manage_only else lambda: setattr(strategy, "recovery_confirmed", client.recovery_healthy()),
    )
    strategy.attach_recovery_runtime(runtime)
    strategy.attach_post_drain_verifier(release)
