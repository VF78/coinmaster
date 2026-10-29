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
from nautilus_trader.model.objects import AccountBalance,MarginBalance

from coinmaster.ops.hl_info_receipt import IncompleteInfoReport, collect_info_receipt
from coinmaster.ops.hl_live_money import collect_selected_cross_assets, live_perps_money_view, cheap_portfolio_observation, cheap_unified_observation
from coinmaster.ops.hl_qualified_reports import qualified_mass_status
from coinmaster.ops.live_recovery import NativeLiveRecoveryScope
from coinmaster.strategy.live_recovery import RecoverableWaveOverlayStrategy, durable_decision_checkpoint


InfoTransport = Callable[[dict[str, Any]], Awaitable[Any]]


class InfoWeightBudget:
    """One bounded strict generation; leave shared-IP headroom for other users."""

    def __init__(self, info: InfoTransport, limit: int = 400, charge=None) -> None:
        self.info, self.limit, self.used = info, limit, 0
        self.charge=charge

    async def __call__(self, body: dict[str, Any]):
        kind = body["type"]
        if kind not in {'userRole','clearinghouseState','orderStatus','frontendOpenOrders','userAbstraction','userDexAbstraction','userFillsByTime','activeAssetData','spotClearinghouseState','userNonFundingLedgerUpdates'}:
            raise IncompleteInfoReport('LIVE_INFO_UNSUPPORTED_REQUEST')
        cost = 60 if kind == "userRole" else 2 if kind in {
            "clearinghouseState", "orderStatus", "spotClearinghouseState",
        } else 20
        if self.used + cost > self.limit:
            raise IncompleteInfoReport("LIVE_INFO_RATE_BUDGET_EXCEEDED")
        self.used += cost
        if self.charge is not None:self.charge(cost,time.monotonic())
        value = await self.info(body)
        if kind in ("userFillsByTime","userNonFundingLedgerUpdates") and isinstance(value,list):
            extra=(len(value)+19)//20
            self.used += extra
            if extra and self.charge is not None:self.charge(extra,time.monotonic())
            if self.used > self.limit:
                raise IncompleteInfoReport("LIVE_INFO_RATE_BUDGET_EXCEEDED")
        return value


def held_sample_reservation(dex_count):
    if type(dex_count) is not int or not 1<=dex_count<=32:
        raise IncompleteInfoReport('UNIFIED_DEX_COUNT_UNKNOWN')
    return 28+2*dex_count


def finite_generation_reservation(uncached_orders,*,unified=False,dex_count=None):
    if type(uncached_orders) is not int or not 0<=uncached_orders<=15:
        raise IncompleteInfoReport('LIVE_INFO_SCOPE_EXCEEDS_GENERATION_CAP')
    if unified:
        if type(dex_count) is not int or not 1<=dex_count<=32:raise IncompleteInfoReport("UNIFIED_DEX_COUNT_UNKNOWN")
        return 397+4*dex_count+4*uncached_orders
    return 540+4*uncached_orders


class ReadinessInfoBudget:
    """Atomic prepaid admission; known unused reservation refunded exactly once."""
    def __init__(self):
        import threading
        self._lock=threading.RLock()
        self.spent=deque();self.next_affordable=None
    def reserve(self,weight,now):
        with self._lock:
            if type(weight) is not int or not 0<weight<=1000:raise IncompleteInfoReport('LIVE_INFO_COST_UNKNOWN')
            self.spent=deque(item for item in self.spent if not item[2] or now-item[0]<60)
            used=sum(item[1] for item in self.spent)
            if used+weight>1000:
                self.next_affordable=None
                for item in self.spent:
                    if not item[2]:continue
                    used-=item[1]
                    if used+weight<=1000:self.next_affordable=item[0]+60;break
                raise IncompleteInfoReport('LIVE_INFO_RATE_BUDGET_EXCEEDED')
            entry=[now,weight,False,[]];self.spent.append(entry);self.next_affordable=None
            return entry
    def remaining(self,now):
        with self._lock:
            self.spent=deque(item for item in self.spent if not item[2] or now-item[0]<60)
            return 1000-sum(item[1] for item in self.spent)
    def protects_held_schedule(self,now,*,additional=0,next_due=None,sample_weight=48):
        with self._lock:
            """Forecast prepaid48/6s renewals against actual unexpired charges.
            Up to3s budget wait leaves the unchanged9s freshness gate in force.
            Actual HTTP delay can still make evidence UNKNOWN; no latency guarantee.
            """
            if type(sample_weight) is not int or not 1<=sample_weight<=1000:return False
            if additional and additional+10*sample_weight>1000:return False
            self.remaining(now)
            charges=[(item[0]+60,item[1]) for item in self.spent]
            if additional:charges.append((now+69,additional))
            if sum(weight for expiry,weight in charges)>1000:return False
            due=max(now,next_due if next_due is not None else now)
            for index in range(10):
                at=due+index*6
                active=[(expiry,weight) for expiry,weight in charges if expiry>at]
                used=sum(weight for _,weight in active)
                affordable=at
                for expiry,weight in sorted(active):
                    if used+sample_weight<=1000:break
                    used-=weight;affordable=expiry
                if used+sample_weight>1000 or affordable-at>3:return False
                charges.append((affordable+60,sample_weight))
            return True
    def note(self,reservation,weight,now):
        with self._lock:
            if reservation[2] or type(weight) is not int or weight<0 or now<reservation[0]:
                raise IncompleteInfoReport('LIVE_INFO_CHARGE_INVALID')
            if weight:reservation[3].append((now,weight))
    def settle(self,reservation,actual,*,now=None):
        with self._lock:
            if (reservation[2] or type(actual) is not int or actual<0):
                raise IncompleteInfoReport('LIVE_INFO_RESERVATION_SETTLEMENT_INVALID')
            overflow=actual>reservation[1]
            notes=reservation[3]
            noted=sum(weight for _,weight in notes)
            if noted>actual:raise IncompleteInfoReport('LIVE_INFO_SETTLEMENT_BELOW_RECORDED_CHARGES')
            # Entire bound remains reserved until atomic settlement; afterwards each
            # real request/item charge retains its own time, never early start expiry.
            fallback=reservation[0] if now is None else now
            charges=[*notes]
            if actual>noted:charges.append((fallback,actual-noted))
            self.spent=deque(item for item in self.spent if item is not reservation)
            self.spent.extend([at,weight,True,[]] for at,weight in charges)
            self.spent=deque(sorted(self.spent,key=lambda item:item[0]))
            reservation[1]=actual;reservation[2]=True
            self.next_affordable=None
            if overflow:raise IncompleteInfoReport('LIVE_INFO_RESERVATION_COST_OVERFLOW')



class SingleAttemptInfoTransport:
    """Pinned collector transport: exactly one urllib POST, no injected retry."""
    def __init__(self,*,testnet,timeout):self.testnet=testnet;self.timeout=timeout
    async def __call__(self,body):
        if body.get('type')=='allDexsClearinghouseState':raise IncompleteInfoReport('INFO_HTTP_WS_SUBSCRIPTION_UNSUPPORTED')
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
        applied_fill_ids: Callable[[], frozenset[str]], *, max_ws_messages: int = 256,readiness_budget=None,
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
        self._cm_unified=False
        self._cm_unified_mode_proof=None
        self._cm_unified_account_task=None
        self._cm_unified_refresh_task=None
        self._cm_unified_native_started_ns=None
        self._cm_unified_generation_reservation=None
        self._cm_unified_native_charge=0
        self._cm_unified_discovery=None
        self._cm_directory_task=None
        self._cm_last_generation_bound=None
        self._cm_account_context={}
        self._cm_cashflow_page=None
        self._cm_financial_authority=None
        self._cm_inputs_budget=readiness_budget if readiness_budget is not None else ReadinessInfoBudget()
        self._cm_money_task=None
        self._cm_account_refresh_wait=None
        self._cm_next_money_request=0.0
        self._cm_generation_started_ns=None
        self._cm_bootstrapped = False
        self._cm_suspend_recovery = None
        self._cm_resume_recovery = None
        self._cm_info_usage = deque()
        self._cm_parity_lock = asyncio.Lock()
        self._cm_money_lock = asyncio.Lock()
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
                    if self._cm_unified and handler!='_handle_account_state':
                        client_id=getattr(msg,'client_order_id',None)
                        if client_id is not None and str(client_id) not in {row['client_order_id'] for row in self._cm_runtime.all_submissions()}:
                            self._cm_unified_discovery=None
                            self._cm_fail('UNIFIED_UNKNOWN_ORDER_ACTIVITY')
                            raise IncompleteInfoReport('UNIFIED_UNKNOWN_ORDER_ACTIVITY')
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
            revision=self._cm_runtime.native_revision() if (getattr(self,"_cm_management_only",False) or getattr(self,"_cm_inputs_enabled",False)) and self._cm_runtime is not None else None
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

    def _cm_context_current(self):
        from coinmaster.strategy.live_recovery import recovery_policy_hash
        proof=self._cm_account_context;now=time.monotonic_ns()
        return (bool(proof) and proof.get('master_role')=='user' and proof.get('agent_role')=='agent'
            and proof.get('account_sha256')==hashlib.sha256(self._cm_scope.account_ref.lower().encode()).hexdigest()
            and proof.get('signer_sha256')==getattr(self._cm_strategy,'_signer_sha256',None)
            and proof.get('policy_sha256')==recovery_policy_hash(self._cm_strategy.config,self._cm_strategy._candidate)
            and proof.get('ws_epoch')==self._cm_ws_epoch and proof.get('dex_abstraction') is False
            and type(proof.get('verified_at_ns')) is int and 0<=now-proof['verified_at_ns']<=300_000_000_000
            and (proof.get('agent_expiry_unix_ms') is None or proof['agent_expiry_unix_ms']*1_000_000>time.time_ns()))

    async def qualify_account_context(self):
        from coinmaster.strategy.live_recovery import recovery_policy_hash
        if self._cm_context_current():return
        proof=self._cm_account_context;now=time.monotonic_ns()
        if proof and (proof.get('account_sha256')!=hashlib.sha256(self._cm_scope.account_ref.lower().encode()).hexdigest() or proof.get('signer_sha256')!=getattr(self._cm_strategy,'_signer_sha256',None)):
            raise IncompleteInfoReport('ACCOUNT_CONTEXT_BINDING_MISMATCH')
        roles_fresh=(proof.get('master_role')=='user' and proof.get('agent_role')=='agent' and type(proof.get('verified_at_ns')) is int and 0<=now-proof['verified_at_ns']<=300_000_000_000)
        bound=20 if roles_fresh else 140
        if self._cache.positions_open() and not self._cm_inputs_budget.protects_held_schedule(time.monotonic(),additional=bound,next_due=self._cm_next_money_request,sample_weight=self._cm_held_weight()):raise IncompleteInfoReport('LIVE_INFO_PROTECTED_HEADROOM')
        cost=0;reservation=self._cm_inputs_budget.reserve(bound,time.monotonic())
        try:
            if not roles_fresh:
                if not proof.get('agent_address'):raise IncompleteInfoReport('ACCOUNT_CONTEXT_AGENT_REFERENCE_REQUIRED')
                started=time.monotonic_ns();cost+=60;master=await self._cm_info({'type':'userRole','user':self._cm_scope.account_ref})
                cost+=60;agent=await self._cm_info({'type':'userRole','user':proof['agent_address']})
                if (not isinstance(master,dict) or master.get('role')!='user' or not isinstance(agent,dict) or agent.get('role')!='agent'
                    or agent.get('data',{}).get('user','').lower()!=self._cm_scope.account_ref.lower()):raise IncompleteInfoReport('ACCOUNT_CONTEXT_ROLE_CHANGED')
                proof={**proof,'master_role':'user','agent_role':'agent','verified_at_ns':started}
            cost+=20;dex=await self._cm_info({'type':'userDexAbstraction','user':self._cm_scope.account_ref})
            if dex is not False:raise IncompleteInfoReport('ACCOUNT_CONTEXT_DEX_UNSUPPORTED')
            proof={**proof,'dex_abstraction':False,'policy_sha256':recovery_policy_hash(self._cm_strategy.config,self._cm_strategy._candidate),'ws_epoch':self._cm_ws_epoch}
            self._cm_account_context=proof
            if not self._cm_context_current():raise IncompleteInfoReport('ACCOUNT_CONTEXT_EXPIRED')
        finally:self._cm_inputs_budget.settle(reservation,cost,now=time.monotonic())

    def _cm_receipt_context(self):
        if not self._cm_context_current():raise IncompleteInfoReport('ACCOUNT_CONTEXT_EXPIRED')
        mode=self._cm_unified_mode_proof
        if mode is None or time.monotonic_ns()-mode['started_ns']>9_000_000_000 or mode['ws_epoch']!=self._cm_ws_epoch:
            raise IncompleteInfoReport('UNIFIED_MODE_PROOF_STALE')
        if not self._cm_dex_directory_current():raise IncompleteInfoReport('UNIFIED_DEX_DIRECTORY_REFRESH_PENDING')
        return {**self._cm_account_context,'mode':'unifiedAccount','mode_observed_at_ns':mode['started_ns'],'dex_names':self._cm_unified_discovery['dex_names']}

    async def _cm_collect_cashflow_page(self,weighted):
        cursor=self._cm_runtime.evidence_cursor('userNonFundingLedgerUpdates')
        start=self._cm_scope.anchor_ms if cursor is None else cursor['end_ms']
        end=self._clock.timestamp_ns()//1_000_000
        rows=await weighted({'type':'userNonFundingLedgerUpdates','user':self._cm_scope.account_ref,'startTime':start,'endTime':end})
        if not isinstance(rows,list) or len(rows)>=500:raise IncompleteInfoReport('LIVE_CASHFLOW_COVERAGE_UNKNOWN')
        if any(not isinstance(row,dict) or type(row.get('time')) is not int or not start<=row['time']<=end or not isinstance(row.get('hash'),str) or not isinstance(row.get('delta'),dict) or not row['delta'].get('type') for row in rows):
            raise IncompleteInfoReport('LIVE_CASHFLOW_ROW_MALFORMED')
        return dict(rows=rows,start_ms=start,end_ms=end,expected_cursor=cursor,complete=True)

    def _cm_unified_discovery_current(self):
        from coinmaster.strategy.live_recovery import recovery_policy_hash
        proof=self._cm_unified_discovery
        return (proof is not None and proof['account']==self._cm_scope.account_ref.lower()
            and proof['ws_epoch']==self._cm_ws_epoch
            and proof['policy_sha256']==recovery_policy_hash(self._cm_strategy.config,self._cm_strategy._candidate))

    def _cm_held_weight(self):
        if not self._cm_unified:return 48
        from coinmaster.ops.hl_info_receipt import validated_dex_names
        return 28+2*len(validated_dex_names(self._cm_unified_discovery['dex_names']))

    def _cm_dex_directory_current(self):
        proof=self._cm_unified_discovery
        at=proof.get('directory_observed_ns') if proof is not None else None
        return (self._cm_unified_discovery_current() and type(at) is int
            and 0<=time.monotonic_ns()-at<=300_000_000_000)

    def _cm_validate_unified_dex_directory(self,raw):
        if (not self._cm_unified_discovery_current() or not isinstance(raw,(tuple,list))
            or tuple(item[0] for item in raw if isinstance(item,(tuple,list)) and len(item)==2)!=self._cm_unified_discovery['dex_names']):
            self._cm_unified_discovery=None
            raise IncompleteInfoReport('UNIFIED_DEX_DIRECTORY_CHANGED')

    async def _cm_qualified_info(self,body):
        if body.get('type')=='allDexsClearinghouseState':
            raise IncompleteInfoReport('INFO_HTTP_WS_SUBSCRIPTION_UNSUPPORTED')
        return await self._cm_info(body)

    async def qualify_unified_prestart_orders(self):
        """One bounded catalog snapshot, not perpetual universal order authority."""
        from coinmaster.strategy.live_recovery import recovery_policy_hash
        from coinmaster.ops.hl_info_receipt import parse_perp_dex_directory,bounded_info_requests
        if not self._cm_unified:return
        if self._cm_unified_discovery_current():return
        if type(self._cm_info) is not SingleAttemptInfoTransport:raise IncompleteInfoReport('LIVE_READINESS_TRANSPORT_SINGLE_ATTEMPT_REQUIRED')
        reservation=self._cm_inputs_budget.reserve(660,time.monotonic());cost=0;started=time.monotonic_ns()
        try:
            cost=20;self._cm_inputs_budget.note(reservation,20,time.monotonic())
            raw=await self._cm_info({'type':'perpDexs'})
            names=parse_perp_dex_directory(raw);directory_observed=time.monotonic_ns()
            scope,_,_,_,_=self._cm_owned_scope();known=dict((cloid.lower(),oid) for _,cloid,oid in scope.durable_orders)
            async def observed(body):
                nonlocal cost
                cost+=20;self._cm_inputs_budget.note(reservation,20,time.monotonic())
                return await self._cm_info(body)
            batches,provenance=await bounded_info_requests(observed,[dict(type='frontendOpenOrders',user=scope.account_ref,dex=name) for name in names])
            for dex,orders in zip(names,batches):
                if not isinstance(orders,list) or len(orders)>=2000:raise IncompleteInfoReport('UNIFIED_ORDER_DISCOVERY_INCOMPLETE')
                for row in orders:
                    if not isinstance(row,dict) or dex or row.get('coin') not in scope.owned_coins:raise IncompleteInfoReport('UNIFIED_FOREIGN_RESTING_ORDER')
                    cloid=row.get('cloid');oid=row.get('oid')
                    if not ((isinstance(cloid,str) and cloid.lower() in known) or any(value is not None and value==oid for value in known.values())):
                        raise IncompleteInfoReport('UNIFIED_UNKNOWN_RESTING_ORDER')
            if time.monotonic_ns()-started>9_000_000_000:raise IncompleteInfoReport('UNIFIED_ORDER_DISCOVERY_STALE')
            self._cm_unified_discovery=dict(account=scope.account_ref.lower(),ws_epoch=self._cm_ws_epoch,
                policy_sha256=recovery_policy_hash(self._cm_strategy.config,self._cm_strategy._candidate),
                dex_names=names,started_ns=started,completed_ns=time.monotonic_ns(),
                directory_observed_ns=directory_observed,directory_sha256=hashlib.sha256(json.dumps(names).encode()).hexdigest(),
                request_provenance=provenance,
                scope='PRESTART_SNAPSHOT_ACCOUNT_EXCLUSIVE_WRITER_NOT_UNIVERSAL_FUTURE_GTC_PROOF')
        except BaseException:self._cm_unified_discovery=None;raise
        finally:self._cm_inputs_budget.settle(reservation,cost,now=time.monotonic())

    async def _cm_refresh_dex_directory(self):
        from coinmaster.ops.hl_info_receipt import parse_perp_dex_directory
        reservation=self._cm_inputs_budget.reserve(20,time.monotonic());cost=0
        try:
            cost=20;self._cm_inputs_budget.note(reservation,20,time.monotonic())
            raw=await self._cm_info({'type':'perpDexs'})
            names=parse_perp_dex_directory(raw)
            if not self._cm_unified_discovery_current() or names!=self._cm_unified_discovery['dex_names']:
                raise IncompleteInfoReport('UNIFIED_DEX_DIRECTORY_CHANGED')
            # Only actual metadata is renewed; original foreign-order snapshot untouched.
            self._cm_unified_discovery['directory_observed_ns']=time.monotonic_ns()
            self._cm_unified_discovery['directory_sha256']=hashlib.sha256(json.dumps(names).encode()).hexdigest()
        except IncompleteInfoReport as error:
            if str(error)!='LIVE_INFO_RATE_BUDGET_EXCEEDED':
                self._cm_unified_discovery=None;self._cm_fail('UNIFIED_DEX_DIRECTORY_UNKNOWN')
            raise
        finally:self._cm_inputs_budget.settle(reservation,cost,now=time.monotonic())

    def request_unified_directory_refresh(self):
        if not self._cm_unified or self._cm_unified_discovery is None:return False
        at=self._cm_unified_discovery.get('directory_observed_ns')
        if type(at) is int and 0<=time.monotonic_ns()-at<240_000_000_000:return False
        if self._cm_directory_task is not None and not self._cm_directory_task.done():return True
        if not self._cm_inputs_budget.protects_held_schedule(time.monotonic(),additional=20,
            next_due=self._cm_next_money_request,sample_weight=self._cm_held_weight()):return False
        async def refresh():
            try:await self._cm_refresh_dex_directory()
            except IncompleteInfoReport as error:
                self._cm_strategy._live_inputs_reason=str(error)
        self._cm_directory_task=asyncio.get_running_loop().create_task(refresh())
        return True

    async def qualify_unified_dex_directory(self):
        if self._cm_dex_directory_current():return
        if not self.request_unified_directory_refresh():
            raise IncompleteInfoReport('UNIFIED_DEX_DIRECTORY_REFRESH_PENDING')
        await asyncio.shield(self._cm_directory_task)
        if not self._cm_dex_directory_current():
            raise IncompleteInfoReport('UNIFIED_DEX_DIRECTORY_REFRESH_PENDING')

    async def _cm_refresh_native_account_for_generation(self):
        account=self._cache.account_for_venue(self.venue)
        event=getattr(account,'last_event',None)
        old=getattr(event,'id',None) or getattr(event,'event_id',None)
        query_started_ns=self._clock.timestamp_ns()
        self._cm_strategy.query_account(self.account_id)
        while True:
            self._cm_require_healthy()
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
                    if self._cm_unified:
                        await self.qualify_unified_prestart_orders()
                        await self.qualify_unified_dex_directory()
                        await self.qualify_account_context()
                    frozen_scope,_,native_orders,applied,frozen_signature=self._cm_owned_scope()
                    frozen_applied=applied
                    fingerprints={str(o.client_order_id):_native_order_fingerprint(o) for o in native_orders}
                    cached_terminal,archived_fills,query_anchor_ms,query_anchor_tid=self._cm_runtime.info_query_evidence(fingerprints,applied)
                    fresh_orders=len(frozen_scope.durable_orders)-len(cached_terminal)
                    # Reserve complete minimum before ANY request; terminal history
                    # remains retained and validated, only redundant status reads go.
                    if self._cm_unified and not self._cm_unified_discovery_current():raise IncompleteInfoReport('UNIFIED_PRESTART_DISCOVERY_REQUIRED')
                    bound=finite_generation_reservation(fresh_orders,unified=self._cm_unified,dex_count=len(self._cm_unified_discovery["dex_names"]) if self._cm_unified else None)
                    if self._cache.positions_open() and not self._cm_inputs_budget.protects_held_schedule(time.monotonic(),additional=bound,next_due=self._cm_next_money_request,sample_weight=self._cm_held_weight()):
                        raise IncompleteInfoReport('LIVE_INFO_PROTECTED_HEADROOM')
                    reservation=self._cm_inputs_budget.reserve(bound,time.monotonic())
                    self._cm_generation_started_ns=time.monotonic_ns()
                    if self._cm_unified:
                        self._cm_unified_generation_reservation=reservation;self._cm_unified_native_charge=0
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
                weighted_info = InfoWeightBudget(self._cm_qualified_info if self._cm_unified else self._cm_info, (bound-(28 if self._cm_unified else 16)) if self._cm_inputs_enabled else min(400, remaining),charge=(lambda cost,at:self._cm_inputs_budget.note(reservation,cost,at)) if reservation is not None else None)
                revision = None
                try:
                    if self._cm_inputs_enabled:
                        if type(self._cm_info) is not SingleAttemptInfoTransport:
                            raise IncompleteInfoReport('LIVE_READINESS_TRANSPORT_SINGLE_ATTEMPT_REQUIRED')
                        native_refresh_cost=0 if self._cm_unified else 16
                        await self._cm_refresh_native_account_for_generation()
                        if self._cm_unified:native_refresh_cost=self._cm_unified_native_charge
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
                            account_mode='unifiedAccount' if self._cm_unified else 'disabled',
                            account_context=self._cm_receipt_context() if self._cm_unified else None,
                        )

                    first = await sweep(end)
                    second = await sweep(max(end + 1, self._clock.timestamp_ns() // 1_000_000))
                    selected_assets = await collect_selected_cross_assets(
                        weighted_info, account_ref=scope.account_ref, coins=scope.owned_coins,require_venue_limits=self._cm_unified,
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
                    if self._cm_unified:self._cm_cashflow_page=await self._cm_collect_cashflow_page(weighted_info)
                    if revision is not None:
                        _, current_revision, _, current_applied, current_signature = self._cm_owned_scope()
                        if (current_revision, current_applied, current_signature) != (revision, applied, signature):
                            raise IncompleteInfoReport("LIVE_DURABLE_REVISION_MOVED")
                    if self._cm_inputs_enabled and time.monotonic_ns()-self._cm_generation_started_ns>9_000_000_000:
                        raise IncompleteInfoReport('LIVE_INFO_GENERATION_OLDEST_RESPONSE_STALE')
                    self._cm_last_receipt = second
                    self._cm_last_margin_assets = selected_assets
                    self._cm_last_revision = revision
                    if self._cm_inputs_enabled:self._cm_last_generation_bound=bound
                    return mass
                except IncompleteInfoReport as error:
                    race = (
                        revision is not None and self._cm_runtime is not None
                        and self._cm_runtime.native_revision() != revision
                    )
                    if self._cm_inputs_enabled or attempt == 3 or not (
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
                        if self._cm_unified:
                            native_refresh_cost=self._cm_unified_native_charge
                            self._cm_unified_generation_reservation=None
                        self._cm_inputs_budget.settle(reservation,weighted_info.used+native_refresh_cost,now=time.monotonic())
                    elif weighted_info.used:
                        self._cm_info_usage.append((now, weighted_info.used))
        except IncompleteInfoReport as error:
            if str(error) in ("LIVE_INFO_RATE_BUDGET_EXCEEDED","LIVE_INFO_PROTECTED_HEADROOM"):
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
            self._cm_parity_task = None if self._cm_inputs_enabled else asyncio.get_running_loop().create_task(
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
            elif getattr(self._cm_strategy,'_active_c1_authorized',False) and str(error) in (
                'ACCOUNT_CONTEXT_EXPIRED','LIVE_INFO_PROTECTED_HEADROOM','LIVE_EXTERNAL_CASHFLOW_QUARANTINED','UNIFIED_DEX_DIRECTORY_REFRESH_PENDING'):
                self._cm_strategy._live_inputs_reason=str(error)
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
            if self._cm_unified and (not self._cm_dex_directory_current() or self.request_unified_directory_refresh()):return False
            cursor=self._cm_runtime.evidence_cursor('userFunding')
            start=self._cm_scope.anchor_ms if cursor is None else cursor['end_ms']
            end=min(self._clock.timestamp_ns()//1_000_000,start+86_400_000)
            if end<=start:return False
            # Separate bounded source observation, never inside a600 generation.
            # Official per20-row item weight applies to userFunding as to fills.
            if self._cache.positions_open() and not self._cm_inputs_budget.protects_held_schedule(time.monotonic(),additional=45,next_due=self._cm_next_money_request,sample_weight=self._cm_held_weight()):return False
            reservation=self._cm_inputs_budget.reserve(45,time.monotonic());actual=20
            try:
                rows=await self._cm_info({'type':'userFunding','user':self._cm_scope.account_ref,'startTime':start,'endTime':end})
                if isinstance(rows,list):actual+=(len(rows)+19)//20
                if not isinstance(rows,list) or len(rows)>=500:raise IncompleteInfoReport('LIVE_FUNDING_PAGE_COMPLETENESS_UNKNOWN')
                if any(type(row.get('time')) is not int or not start<=row['time']<=end for row in rows):raise IncompleteInfoReport('LIVE_FUNDING_PAGE_TIME_INVALID')
                self._cm_runtime.record_funding_page(rows,expected_cursor=cursor,next_cursor={'end_ms':end},complete=True)
            finally:self._cm_inputs_budget.settle(reservation,actual,now=time.monotonic())
            if rows:strategy._live_inputs_dirty=True;strategy._last_live_input_observation=None
            return True

    def request_portfolio_observation(self,strategy):
        if not self._cm_inputs_enabled or not self.recovery_healthy() or time.monotonic()<self._cm_next_money_request:return False
        if self._cm_money_task is not None and not self._cm_money_task.done():return True
        self._cm_next_money_request=time.monotonic()+(6 if self._cm_unified else 1)
        self._cm_money_task=asyncio.get_running_loop().create_task(self._cm_collect_portfolio_observation(strategy))
        return True

    async def _cm_reserve_held_read(self,weight,started_ns):
        for attempt in range(2):
            try:return self._cm_inputs_budget.reserve(weight,time.monotonic())
            except IncompleteInfoReport:
                wake=self._cm_inputs_budget.next_affordable
                if attempt or wake is None or wake-time.monotonic()>3 or wake*1_000_000_000-started_ns>=9_000_000_000:raise
                await asyncio.sleep(max(0,wake-time.monotonic()))
                self._cm_require_healthy()
        raise IncompleteInfoReport('LIVE_INFO_RATE_BUDGET_EXCEEDED')

    async def _cm_collect_portfolio_observation(self,strategy):
        try:
            async with self._cm_money_lock:
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
                if self._cm_unified:
                    if not self._cm_unified_discovery_current():raise IncompleteInfoReport('UNIFIED_PRESTART_DISCOVERY_REQUIRED')
                    # Stock public account path: mode20 + native spot<=8; allDEX20.
                    # Await its actual generated AccountState before consuming native evidence.
                    started=time.monotonic_ns()
                    old_event_id=event_id
                    query_started_ns=self._clock.timestamp_ns()
                    await self._update_account_state()
                    while True:
                        account=self._cache.account_for_venue(self.venue)
                        event=getattr(account,'last_event',None)
                        current_id=str(getattr(event,'id',None) or getattr(event,'event_id',''))
                        if current_id!=old_event_id and getattr(event,'ts_init',0)>=query_started_ns:break
                        if time.monotonic_ns()-started>=9_000_000_000:
                            raise IncompleteInfoReport('PORTFOLIO_ACCOUNT_REFRESH_STALE')
                        await asyncio.sleep(.01)
                    proof=self._cm_unified_mode_proof
                    if proof is None or proof['ws_epoch']!=ws:
                        raise IncompleteInfoReport('PORTFOLIO_ACCOUNT_REFRESH_REQUIRED')
                    started=min(started,proof['started_ns'])
                    from coinmaster.ops.hl_info_receipt import collect_per_dex_states
                    names=self._cm_unified_discovery['dex_names']
                    reservation=await self._cm_reserve_held_read(2*len(names),started)
                    cost=0
                    async def observed(body):
                        nonlocal cost
                        cost+=2;self._cm_inputs_budget.note(reservation,2,time.monotonic())
                        return await self._cm_qualified_info(body)
                    try:
                        all_dex,provenance=await collect_per_dex_states(observed,account=self._cm_scope.account_ref,dex_names=names)
                    finally:self._cm_inputs_budget.settle(reservation,cost,now=time.monotonic())
                    raw=None
                    strategy._live_inputs_dirty=False
                else:
                    self._cm_inputs_budget.reserve(2,time.monotonic())
                    raw=await self._cm_info({'type':'clearinghouseState','user':self._cm_scope.account_ref,'dex':self._cm_scope.dex})
                complete=time.monotonic_ns();available=self._clock.timestamp_ns()
                if not self.recovery_healthy() or self._cm_runtime.native_revision()!=revision or strategy._c1_fill_epoch!=epoch or self._cm_ws_epoch!=ws or fingerprints!=tuple(_native_order_fingerprint(o) for o in self._cache.orders(venue=self.venue)):
                    raise IncompleteInfoReport('PORTFOLIO_NATIVE_REVISION_MOVED')
                account=self._cache.account_for_venue(self.venue)
                if getattr(strategy,'_live_inputs_dirty',False):raise IncompleteInfoReport('PORTFOLIO_ACCOUNT_REFRESH_REQUIRED')
                producer=cheap_unified_observation if self._cm_unified else cheap_portfolio_observation
                positional=(raw,all_dex) if self._cm_unified else (raw,)
                observation=producer(*positional,account_id=str(self.account_id),native_account=account,
                    native_positions=tuple(self._cache.positions_open()),strategy_id=str(strategy.id),revision=revision,
                    fill_epoch=epoch,ws_epoch=ws,started_ns=started,completed_ns=complete,available_ns=available,
                    **({'native_open_orders':tuple(self._cache.orders_open(venue=self.venue)),'native_spot_money':proof['native_spot_money']} if self._cm_unified else {}))
                strategy._last_live_input_observation=observation
                self._cm_runtime.append_evidence('portfolio:'+str(available),'account',dict(source='UNIFIED_SPOT_REPORTED_TOTAL' if self._cm_unified else 'ONE_CLEARINGHOUSE_RESPONSE',raw=raw,equity_basis=observation.equity_basis,
                    native_account_event_id=observation.native_account_event_id,generation_started_ns=started,response_completed_ns=complete,
                    source_available_ns=available,native_revision=revision,fill_epoch=epoch,ws_epoch=ws,command_capability=False,
                    dex_source='CLIENT_ASSEMBLED_EXPLICIT_PER_DEX_HTTP' if self._cm_unified else None,
                    dex_request_provenance=provenance if self._cm_unified else ()))
                if self._cm_unified:self.request_unified_directory_refresh()
        except IncompleteInfoReport as error:
            strategy._last_live_input_observation=None
            strategy._live_inputs_reason=str(error)
            if str(error) in ('UNIFIED_FOREIGN_DEX_EXPOSURE','UNIFIED_ISOLATED_EXPOSURE',
                'UNIFIED_UNKNOWN_NATIVE_ORDER','UNIFIED_NATIVE_POSITION_SCOPE','UNIFIED_DEX_DIRECTORY_CHANGED'):
                self._cm_fail('UNIFIED_FOREIGN_OR_UNKNOWN_ACTIVITY')
            if str(error) in ('PORTFOLIO_ACCOUNT_REFRESH_REQUIRED','UNIFIED_NATIVE_ACCOUNT_REFRESH_REQUIRED') and self._cm_account_refresh_wait is None:
                try:
                    # v1.231 source: perp2+spot2, each <=4 HTTP attempts =>16.
                    if not self._cm_unified:self._cm_inputs_budget.reserve(16,time.monotonic())
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
                 applied_fill_ids: Callable[[], frozenset[str]],readiness_budget=None, **native_kwargs) -> None:
        super().__init__(**native_kwargs)
        self.configure_info_boundary(scope,info,applied_fill_ids,readiness_budget=readiness_budget)

    async def _update_account_state(self):
        if not getattr(self,'_cm_unified',False):return await super()._update_account_state()
        task=self._cm_unified_account_task
        if task is None or task.done():
            self._cm_unified_native_started_ns=time.monotonic_ns()
            task=self._cm_unified_account_task=asyncio.get_running_loop().create_task(self._cm_collect_unified_native_account())
        elif self._cm_unified_generation_reservation is not None:
            self._cm_generation_started_ns=min(self._cm_generation_started_ns,self._cm_unified_native_started_ns)
        return await task

    async def _cm_collect_unified_native_account(self):
        from coinmaster.ops.hl_unified_account import native_spot_usdc_dicts
        started=self._cm_unified_native_started_ns;prepaid=self._cm_unified_generation_reservation is not None and not self._cm_unified_native_charge
        reservation=None;cost=0
        try:
            if not prepaid:reservation=await self._cm_reserve_held_read(28,started)
            cost=20
            charged_reservation=self._cm_unified_generation_reservation if prepaid else reservation
            self._cm_inputs_budget.note(charged_reservation,20,time.monotonic())
            if prepaid:self._cm_unified_native_charge=cost
            mode=await self._cm_info({'type':'userAbstraction','user':self._cm_scope.account_ref})
            if mode!='unifiedAccount':raise IncompleteInfoReport('UNIFIED_MODE_MISMATCH')
            cost+=8
            if prepaid:self._cm_unified_native_charge=cost
            native=await self._client.request_spot_balances()  # Stock native readonly public API, <=4*2.
            self._cm_inputs_budget.note(charged_reservation,8,time.monotonic())
            balance,margin=native_spot_usdc_dicts(native)
            completed=time.monotonic_ns()
            if completed-started>9_000_000_000:raise IncompleteInfoReport('UNIFIED_NATIVE_ACCOUNT_STALE')
            self._cm_require_healthy()
            self.generate_account_state(balances=[AccountBalance.from_dict(balance)],margins=[MarginBalance.from_dict(margin)],
                reported=True,ts_event=self._clock.timestamp_ns())
            from coinmaster.ops.hl_unified_account import amount
            self._cm_unified_mode_proof=dict(mode=mode,started_ns=started,completed_ns=completed,ws_epoch=self._cm_ws_epoch,native_spot_money=tuple(amount(balance[k]) for k in ('total','locked','free')))
        except BaseException:
            self._cm_unified_mode_proof=None
            import sys
            error=sys.exception()
            if not isinstance(error,IncompleteInfoReport) or str(error)!='LIVE_INFO_RATE_BUDGET_EXCEEDED':
                self._cm_fail('UNIFIED_NATIVE_ACCOUNT_UNKNOWN')
            raise
        finally:
            if reservation is not None:self._cm_inputs_budget.settle(reservation,cost,now=time.monotonic())

    def _handle_account_state(self,msg):
        if not getattr(self,'_cm_unified',False):return super()._handle_account_state(msg)
        # The1.231 WS account payload uses the old perp/spot heuristic. Never let
        # it overwrite this mode-aware reported state; refresh the public spot path.
        # This legacy payload is not Unified capital truth. Coalesce a demand
        # into the <=6s held refresh; never charge28 for every WS message.
        strategy=getattr(self,'_cm_strategy',None)
        if strategy is not None:self.request_portfolio_observation(strategy)

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
    _readiness_budget=None
    _account_context=None
    _scope = None
    _runtime = None
    _info = None
    _strategy = None

    @classmethod
    def bind(
        cls, scope: NativeLiveRecoveryScope, runtime, strategy, info: InfoTransport | None = None,
        *, account_lock_root: Path = Path("/run/lock/coinmaster"),readiness_budget=None,account_context=None,
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
            _readiness_budget=readiness_budget
            _account_context=account_context
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
        if getattr(cls._strategy,'_live_account_mode','disabled')=='unifiedAccount':
            from coinmaster.ops.hl_unified_instruments import get_unified_instrument_provider
            provider=get_unified_instrument_provider(client,config.instrument_provider,_resolve_product_types(config.product_types))
        else:
            provider=get_cached_hyperliquid_instrument_provider(client=client,config=config.instrument_provider,
                product_types=_resolve_product_types(config.product_types))
        info = cls._info
        if info is None:
            info = SingleAttemptInfoTransport(testnet=environment == nautilus_pyo3.HyperliquidEnvironment.TESTNET,
                timeout=config.http_timeout_secs)
        owner = QualifiedHyperliquidExecutionClient(
            loop=loop, client=client, msgbus=msgbus, cache=cache, clock=clock,
            instrument_provider=provider, config=config, name=name, account_address=address,
            scope=cls._scope,info=info,applied_fill_ids=cls._runtime.applied_fill_ids,readiness_budget=cls._readiness_budget,
        )
        owner._cm_runtime = cls._runtime
        owner._cm_account_context=dict(cls._account_context or {})
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
    active_c1=getattr(strategy,'_active_c1_authorized',False)
    c1_owned=manage_only or active_c1
    client._cm_management_only=manage_only
    client._cm_inputs_enabled=getattr(strategy,'_input_readiness_preparation',False)
    client._cm_unified=getattr(strategy,'_live_account_mode','disabled')=='unifiedAccount'
    client._cm_strategy=strategy
    context=getattr(client,'_cm_account_context',{})
    if context:
        from coinmaster.strategy.live_recovery import recovery_policy_hash
        client._cm_account_context={**context,'policy_sha256':recovery_policy_hash(strategy.config,strategy._candidate),'ws_epoch':client._cm_ws_epoch}
        strategy._signer_sha256=context.get('signer_sha256')
    if client._cm_inputs_enabled:
        if type(client._cm_info) is not SingleAttemptInfoTransport:
            raise RuntimeError('LIVE_READINESS_TRANSPORT_SINGLE_ATTEMPT_REQUIRED')
        strategy._live_input_request=lambda:client.request_portfolio_observation(strategy)
        strategy._live_input_ws_epoch=lambda:client._cm_ws_epoch
        strategy._fresh_init_generation_validator=lambda: (client._cm_ws_failure is None and client._cm_transport_ok() and client._cm_generation_started_ns is not None and time.monotonic_ns()-client._cm_generation_started_ns<=9_000_000_000)
    if strategy.config.research_residual_recovery and not c1_owned:
        raise RuntimeError("E4_C1_LIVE_REQUIRES_MANAGE_ONLY_PREPARATION")
    if c1_owned and ((manage_only and not strategy._manage_only_preparation) or (not strategy._checkpoint_policy_valid and strategy._fresh_c1_init_intent!='INITIALIZE_FRESH_C1_EPOCH')):
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
        if not c1_owned and not client._cm_bootstrapped and scope.durable_orders:
            raise IncompleteInfoReport("LIVE_OPEN_FUNDING_CURSOR_UNPROVEN")
        native_orders = tuple(client._cache.orders(venue=client.venue))
        native_positions = tuple(client._cache.positions_open())
        if not c1_owned and not client._cm_bootstrapped:
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
        initialized_this_verify=False
        if getattr(strategy,'_fresh_c1_init_intent',None) is not None:
            if (not getattr(client,'_cm_inputs_enabled',False) or not c1_owned
                or scope.durable_orders or runtime.all_submissions() or runtime.applied_fill_ids()
                or mass.order_reports or mass.fill_reports or mass.position_reports
                or native_orders or native_positions or strategy.cache.orders_inflight()):
                raise IncompleteInfoReport('C1_INIT_NATIVE_FLAT_UNPROVEN')
            initial_money=live_perps_money_view(receipt,account_ref=scope.account_ref,dex=scope.dex,
                account_id=str(client.account_id),native_account=client._cache.account_for_venue(client.venue),
                native_positions=(),now_ms=client._clock.timestamp_ns()//1_000_000,max_age_ms=9_000,
                selected_assets=client._cm_last_margin_assets or (),native_revision=runtime.native_revision())
            if not initial_money.selected_assets:raise IncompleteInfoReport('LIVE_SELECTED_MARGIN_UNKNOWN')
            strategy.initialize_clean_flat_c1_epoch(initial_money,intent=strategy._fresh_c1_init_intent,now_ns=client._clock.timestamp_ns(),history_anchor_ms=receipt.start_ms,cashflow_page=client._cm_cashflow_page)
            initialized_this_verify=True
        if getattr(client,'_cm_unified',False) and not initialized_this_verify:
            page=client._cm_cashflow_page
            # Virgin initializer atomically installed its baseline cursor already.
            runtime.record_cashflow_page(page)
            strategy.accept_cashflow_basis(page)
        elif initialized_this_verify and getattr(client,'_cm_unified',False):strategy.accept_cashflow_basis(client._cm_cashflow_page)
        checkpoint = runtime.strategy_checkpoint()
        if checkpoint is not None and durable_decision_checkpoint(checkpoint[0]) != durable_decision_checkpoint(
            strategy.on_save()["wave_overlay_live_recovery_v1"]
        ):
            raise IncompleteInfoReport("LIVE_HANDOVER_DOMAIN_CHECKPOINT_MISMATCH")
        if c1_owned:
            from coinmaster.ops.live_recovery import ManagementCertificate,management_cache_evidence
            from coinmaster.strategy.live_recovery import recovery_policy_hash
            now_ns=client._clock.timestamp_ns()
            generation=receipt.end_ms*1_000_000
            revision=client._cm_last_revision
            fresh_flat_epoch=(getattr(client,'_cm_inputs_enabled',False) and runtime.c1_initialization() is not None and not scope.durable_orders and not native_orders and not native_positions and not receipt.fills)
            if ((not receipt.fill_anchor_proven and not fresh_flat_epoch) or receipt.account.lower()!=scope.account_ref.lower() or receipt.dex!=scope.dex
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
            if manage_only:return True
            strategy.establish_owned_effect_chain(account_id=client.account_id,ws_epoch=client._cm_ws_epoch,
                policy_sha256=recovery_policy_hash(strategy.config,strategy._candidate))
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
        if (not c1_owned and not client._cm_bootstrapped
                and candidate_money.equity != getattr(
                    runtime, "flat_epoch_balance", strategy.config.active_seed)):
            raise IncompleteInfoReport("LIVE_FLAT_EPOCH_BALANCE_CHANGED")
        if client._cm_bootstrapped and runtime.native_revision() != client._cm_last_revision:
            raise IncompleteInfoReport("LIVE_VERIFIER_REVISION_MOVED")
        if getattr(client,'_cm_inputs_enabled',False):client.save_verified_query_evidence(strategy,receipt,native_orders)
        if active_c1:strategy.accept_live_financial_authority(started_ns=client._cm_generation_started_ns)
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

    if active_c1:
        strategy._live_context_current=lambda:client._cm_context_current() and client._cm_dex_directory_current()
        strategy._live_increase_headroom=lambda:(type(client._cm_last_generation_bound) is int and client._cm_last_generation_bound+10*client._cm_held_weight()<=1000 and client._cm_inputs_budget.protects_held_schedule(time.monotonic(),next_due=client._cm_next_money_request,sample_weight=client._cm_held_weight()))
    strategy.attach_live_money_view(lambda: latest_money[0])
    strategy.attach_live_refresh(client.request_effect_parity_refresh)
    strategy.attach_recovery_health(client.recovery_healthy)
    def suspend_active():
        latest_money[0]=None
        strategy.suspend_live_financial_authority()
    def resume_active():
        strategy.recovery_confirmed=client.recovery_healthy()
    def revoke_active():
        strategy.recovery_confirmed=False
        strategy._owned_effect_chain=None
        suspend_active()
    client.bind_recovery_revocation(strategy.revoke_management if manage_only else revoke_active)
    client.bind_recovery_suspension(
        strategy.revoke_management if manage_only else suspend_active if active_c1 else lambda: setattr(strategy, "recovery_confirmed", False),
        (lambda: None) if manage_only else resume_active if active_c1 else lambda: setattr(strategy, "recovery_confirmed", client.recovery_healthy()),
    )
    strategy.attach_recovery_runtime(runtime)
    strategy.attach_post_drain_verifier(release)
