"""Scoped strict Info report owner for pinned Nautilus 1.231 Hyperliquid execution.

Native LiveExecutionEngine still applies reports and owns orders, fills and PnL.
This adapter never falls back to the pinned opaque bulk report methods.
"""
from __future__ import annotations

import asyncio
import json
from collections import deque
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

from coinmaster.ops.hl_info_receipt import IncompleteInfoReport, collect_info_receipt
from coinmaster.ops.hl_live_money import live_perps_money_view
from coinmaster.ops.hl_qualified_reports import qualified_mass_status
from coinmaster.ops.live_recovery import NativeLiveRecoveryScope
from coinmaster.strategy.live_recovery import RecoverableWaveOverlayStrategy


InfoTransport = Callable[[dict[str, Any]], Awaitable[Any]]
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
        self._cm_scope = scope
        self._cm_info = info
        self._cm_applied_fill_ids = applied_fill_ids
        self._cm_ws_queue = deque()
        self._cm_ws_limit = max_ws_messages
        self._cm_ws_phase = "BUFFERING"
        self._cm_ws_failure = None
        self._cm_parity_task = None
        self._cm_last_receipt = None

    def _cm_transport_ok(self) -> bool:
        socket = getattr(self, "_ws_client", None)
        try:
            active = socket is not None and socket.is_active() and not socket.is_closed()
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

    async def generate_mass_status(self, lookback_mins=None):
        self._cm_last_receipt = None
        try:
            self._cm_require_healthy()
            scope = self._cm_scope
            expected = {cloid: oid for _, cloid, oid in scope.durable_orders}
            end = self._clock.timestamp_ns() // 1_000_000
            async def sweep(at: int):
                return await collect_info_receipt(
                    self._cm_info, account=scope.account_ref, dex=scope.dex,
                    anchor_ms=scope.anchor_ms, anchor_tid=scope.anchor_tid,
                    end_ms=at, expected_orders=expected, owned_coins=scope.owned_coins,
                    require_money_scope=True,
                )
            first = await sweep(end)
            second = await sweep(max(end + 1, self._clock.timestamp_ns() // 1_000_000))
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
                }, native_orders=self._cache.orders(venue=self.venue),
                applied_trade_ids=self._cm_applied_fill_ids(), ts_init=self._clock.timestamp_ns(),
            )
            self._cm_last_receipt = second
            return mass
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
            self._cm_parity_task = asyncio.get_running_loop().create_task(
                self._cm_monitor_parity(verify, monitor_interval_secs)
            )
            return
        if self._cm_ws_failure is None:
            self._cm_fail("WS_HANDOVER_NOT_CONVERGED")
        self._cm_require_healthy()

    async def _cm_monitor_parity(
        self, verify: Callable[[Any], Awaitable[bool]], interval: float,
    ) -> None:
        try:
            while self._cm_ws_phase == "LIVE" and self._cm_ws_failure is None:
                await asyncio.sleep(interval)
                if not self._cm_transport_ok():
                    return
                mass = await self.generate_mass_status()
                if await verify(mass) is not True:
                    self._cm_fail("WS_PERIODIC_EFFECT_PARITY_FAILED")
                    return
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
    def bind(cls, scope: NativeLiveRecoveryScope, runtime, strategy, info: InfoTransport | None = None):
        if not isinstance(scope, NativeLiveRecoveryScope) or runtime is None or strategy is None:
            raise ValueError("RECOVERY_SCOPE_AND_STRATEGY_REQUIRED")
        journal_ids = {row["client_order_id"] for row in runtime.all_submissions()}
        scoped_ids = {client for client, _, _ in scope.durable_orders}
        if journal_ids != scoped_ids:
            raise ValueError("RECOVERY_DURABLE_SCOPE_MISMATCH")
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
            info = lambda body: read_info_http(
                body, testnet=environment == nautilus_pyo3.HyperliquidEnvironment.TESTNET,
                timeout=config.http_timeout_secs,
            )
        owner = QualifiedHyperliquidExecutionClient(
            loop=loop, client=client, msgbus=msgbus, cache=cache, clock=clock,
            instrument_provider=provider, config=config, name=name, account_address=address,
            scope=cls._scope, info=info, applied_fill_ids=cls._runtime.applied_fill_ids,
        )
        bind_clean_flat_live_handover(owner, cls._strategy, cls._runtime)
        return owner


def bind_clean_flat_live_handover(
    client: QualifiedInfoBoundary, strategy, runtime, *,
    monitor_interval_secs: float = 5.0,
) -> None:
    """Bind one strict clean-flat post-drain owner; open funding remains unproved.

    The native engine has already applied startup mass status before strategy
    on_start. This callback only checks its effects and never posts PnL or fills.
    Open exposure or unresolved orders stay RECOVERY_REQUIRED until a venue
    funding cursor and owned partial-TP handover have their own proof.
    """
    if not isinstance(client, QualifiedInfoBoundary) or not hasattr(client, "_cm_scope"):
        raise RuntimeError("LIVE_HANDOVER_CLIENT_UNQUALIFIED")
    if not isinstance(strategy, RecoverableWaveOverlayStrategy):
        raise RuntimeError("LIVE_HANDOVER_STRATEGY_UNQUALIFIED")
    scope = client._cm_scope
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
        if receipt is None or mass.account_id != client.account_id or mass.venue != client.venue:
            raise IncompleteInfoReport("LIVE_HANDOVER_GENERATION_MISSING")
        if (
            scope.durable_orders or runtime.all_submissions() or runtime.applied_fill_ids()
            or mass.order_reports or mass.fill_reports or mass.position_reports
            or client._cache.orders(venue=client.venue) or client._cache.positions_open()
            or strategy._domain.episode is not None or strategy._pending_by_order
        ):
            raise IncompleteInfoReport("LIVE_OPEN_FUNDING_CURSOR_UNPROVEN")
        checkpoint = runtime.strategy_checkpoint()
        if checkpoint is not None and checkpoint[0] != strategy.on_save()["wave_overlay_live_recovery_v1"]:
            raise IncompleteInfoReport("LIVE_HANDOVER_DOMAIN_CHECKPOINT_MISMATCH")
        account = client._cache.account_for_venue(client.venue)
        latest_money[0] = live_perps_money_view(
            receipt, account_ref=scope.account_ref, dex=scope.dex,
            account_id=str(client.account_id), native_account=account,
            native_positions=(), now_ms=client._clock.timestamp_ns() // 1_000_000,
        )
        return True

    async def release() -> None:
        await client.release_after_effect_parity(
            verify, monitor_interval_secs=monitor_interval_secs,
        )
        if latest_money[0] is None or not client.recovery_healthy():
            raise RuntimeError("LIVE_HANDOVER_UNCONFIRMED")
        strategy.recovery_confirmed = True

    strategy.attach_live_money_view(lambda: latest_money[0])
    strategy.attach_recovery_health(client.recovery_healthy)
    client.bind_recovery_revocation(lambda: setattr(strategy, "recovery_confirmed", False))
    strategy.attach_recovery_runtime(runtime)
    strategy.attach_post_drain_verifier(release)
