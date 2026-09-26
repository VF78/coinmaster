"""Narrow pinned-1.231 Hyperliquid clean-flat report boundary.

Nautilus still owns submit/cancel, WebSocket conversion, cache, and reconciliation.
The current live worker is blocked before construction. Open exposure has no
qualified path here; a clean-flat scope must be installed before startup.
"""
from __future__ import annotations

import asyncio
import threading
from decimal import Decimal
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from nautilus_trader.adapters.hyperliquid.execution import HyperliquidExecutionClient
from nautilus_trader.adapters.hyperliquid.factories import (
    _resolve_environment,
    _resolve_product_types,
    get_cached_hyperliquid_http_client,
    get_cached_hyperliquid_instrument_provider,
)
from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.live.factories import LiveExecClientFactory
from nautilus_trader.model.currencies import USDC

from coinmaster.ops.hl_info_receipt import InfoTransport, collect_info_receipt


MAX_BUFFERED_WS_EVENTS = 4096


@dataclass(frozen=True)
class CleanFlatScope:
    account: str
    dex: str
    start_ms: int
    owned_coins: frozenset[str]
    # Recheck the durable journal/checkpoint on every generation, not a fresh cache.
    durable_state_empty: Callable[[], bool]


class QualifiedHyperliquidExecutionClient(HyperliquidExecutionClient):
    """Only a verified clean-flat generation can produce native mass status."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._clean_flat_scope: CleanFlatScope | None = None
        self._qualified_info: InfoTransport | None = None
        self._report_generation = 0
        self._report_lock = asyncio.Lock()
        self._qualified_generation: int | None = None
        self._native_sweep_active = False
        self._ws_lock = threading.Lock()
        self._ws_gate = "BUFFERING"
        self._ws_buffer: deque[Any] = deque()

    def install_clean_flat_scope(self, scope: CleanFlatScope, info: InfoTransport) -> None:
        if not isinstance(scope, CleanFlatScope) or not callable(info):
            raise ValueError("HL_CLEAN_FLAT_SCOPE_REQUIRED")
        if scope.owned_coins != frozenset({"BTC", "SOL"}) or scope.dex != "":
            raise ValueError("HL_OPEN_OR_NONPERP_SCOPE_UNSUPPORTED")
        if not callable(scope.durable_state_empty):
            raise ValueError("HL_DURABLE_STATE_CHECK_REQUIRED")
        if self._report_generation or self._qualified_generation is not None:
            raise RuntimeError("HL_REPORT_SCOPE_ALREADY_USED")
        if scope.account.lower() != str(self._account_address).lower():
            raise ValueError("HL_REPORT_ACCOUNT_SCOPE_MISMATCH")
        self._clean_flat_scope, self._qualified_info = scope, info

    def _handle_msg(self, msg: Any) -> None:
        drain = False
        with self._ws_lock:
            if self._ws_gate == "FAILED":
                return
            if len(self._ws_buffer) >= MAX_BUFFERED_WS_EVENTS:
                self._ws_gate = "FAILED"
                self._ws_buffer.clear()
                return
            self._ws_buffer.append(msg)
            if self._ws_gate == "RELEASED":
                self._ws_gate = "DRAINING"
                drain = True
        if drain:
            self._drain_ws()

    def _drain_ws(self) -> None:
        while True:
            with self._ws_lock:
                if self._ws_gate == "FAILED":
                    raise RuntimeError("HL_REPORT_WS_BUFFER_OVERFLOW")
                if not self._ws_buffer:
                    self._ws_gate = "RELEASED"
                    return
                msg = self._ws_buffer.popleft()
            super()._handle_msg(msg)

    def release_ws_after_strategy_start(self) -> None:
        """Called only in strategy.on_start, after successful engine reconciliation."""
        with self._ws_lock:
            if self._qualified_generation is None or self._ws_gate != "BUFFERING":
                raise RuntimeError("HL_REPORT_HANDOVER_UNQUALIFIED")
            self._ws_gate = "DRAINING"
        self._drain_ws()

    def _log_report_error(self, error: BaseException, kind: str) -> None:
        super()._log_report_error(error, kind)
        raise error

    async def generate_order_status_reports(self, command):
        if not self._native_sweep_active:
            raise RuntimeError("HL_DIRECT_ORDER_REPORT_UNQUALIFIED")
        return await super().generate_order_status_reports(command)

    async def generate_fill_reports(self, command):
        if not self._native_sweep_active:
            raise RuntimeError("HL_DIRECT_FILL_REPORT_UNQUALIFIED")
        return await super().generate_fill_reports(command)

    async def generate_position_status_reports(self, command):
        if not self._native_sweep_active:
            raise RuntimeError("HL_DIRECT_POSITION_REPORT_UNQUALIFIED")
        return await super().generate_position_status_reports(command)

    async def generate_order_status_report(self, command):
        raise RuntimeError("HL_OPEN_EXPOSURE_REPORT_UNQUALIFIED")

    def _cache_is_clean_flat(self) -> bool:
        return not self._cache.orders(venue=self.venue) and not self._cache.positions(venue=self.venue)

    async def generate_mass_status(self, lookback_mins: int | None = None):
        async with self._report_lock:
            return await self._generate_one_mass_status(lookback_mins)

    async def _generate_one_mass_status(self, lookback_mins: int | None):
        if self._qualified_generation is not None:
            return None
        self._report_generation += 1
        generation = self._report_generation
        scope, info = self._clean_flat_scope, self._qualified_info
        if scope is None or info is None or not self._cache_is_clean_flat():
            return None
        with self._ws_lock:
            if self._ws_gate != "BUFFERING":
                return None
        try:
            if not scope.durable_state_empty():
                return None
            receipts = []
            for _ in range(2):
                end_ms = self._clock.timestamp_ns() // 1_000_000
                if scope.start_ms >= end_ms:
                    return None
                receipt = await collect_info_receipt(
                    info, account=scope.account, dex=scope.dex,
                    anchor_ms=scope.start_ms, anchor_tid=None, end_ms=end_ms,
                    expected_orders={}, owned_coins=scope.owned_coins,
                )
                if (
                    receipt.open_orders or receipt.positions or receipt.fills
                    or Decimal(receipt.account_value) <= 0
                ):
                    return None
                receipts.append(receipt)
            if receipts[1].end_ms < receipts[0].end_ms:
                return None
            self._native_sweep_active = True
            try:
                mass = await super().generate_mass_status(lookback_mins)
            finally:
                self._native_sweep_active = False
            if mass is None or mass.order_reports or mass.fill_reports or mass.position_reports:
                return None
            account = self._cache.account_for_venue(self.venue)
            if account is None or str(account.id) != str(self.account_id):
                return None
            usdc_total = account.balance_total(USDC)
            if usdc_total is None or not usdc_total.as_decimal().is_finite() or usdc_total.as_decimal() <= 0:
                return None
            with self._ws_lock:
                if self._ws_gate != "BUFFERING":
                    return None
                self._qualified_generation = generation
            return mass
        except (asyncio.CancelledError, Exception):
            return None

    async def _disconnect(self) -> None:
        with self._ws_lock:
            self._ws_gate = "FAILED"
            self._ws_buffer.clear()
            self._qualified_generation = None
        await super()._disconnect()


class QualifiedHyperliquidLiveExecClientFactory(LiveExecClientFactory):
    """Native factory construction with only the execution class replaced."""

    @staticmethod
    def create(loop, name, config, msgbus, cache, clock):
        environment = _resolve_environment(config.environment)
        account_address = nautilus_pyo3.hyperliquid_resolve_execution_account_address(
            private_key=config.private_key, vault_address=config.vault_address,
            account_address=config.account_address, environment=environment,
        )
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
        return QualifiedHyperliquidExecutionClient(
            loop=loop, client=client, msgbus=msgbus, cache=cache, clock=clock,
            instrument_provider=provider, config=config, name=name,
            account_address=account_address,
        )
