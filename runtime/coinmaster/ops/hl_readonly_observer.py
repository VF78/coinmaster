"""Read-only Hyperliquid account observation with no execution capability.

This uses only the public Info endpoint and keeps every receipt conditional.
It never clears a recovery fence, resubmits an order, or owns a native client.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping

from coinmaster.ops.hl_info_receipt import (
    IncompleteInfoReport, InfoReceipt, InfoTransport, collect_info_receipt,
)

INFO_URL = "https://api.hyperliquid.xyz/info"
ACCOUNT_ENV = "COINMASTER_HL_READONLY_ACCOUNT_REF"
_ALLOWED_FIELDS = {
    "userRole": frozenset({"type", "user"}),
    "clearinghouseState": frozenset({"type", "user", "dex"}),
    "frontendOpenOrders": frozenset({"type", "user", "dex"}),
    "orderStatus": frozenset({"type", "user", "oid"}),
    "userFillsByTime": frozenset({"type", "user", "startTime", "endTime", "aggregateByTime"}),
}
_MAX_BODY = 2_000_000


def _account_ref(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"0x[0-9a-fA-F]{40}", value) is None:
        raise ValueError("INVALID_PUBLIC_ACCOUNT_REF")
    if int(value[2:], 16) == 0:
        raise ValueError("INVALID_PUBLIC_ACCOUNT_REF")
    return value


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class ReadOnlyInfoHttp:
    """Small allowlisted HTTP transport; no signing or exchange endpoint."""

    def __init__(self, account_ref: str, timeout_s: float = 5.0) -> None:
        self.account_ref = _account_ref(account_ref)
        if not 0 < timeout_s <= 30:
            raise ValueError("INVALID_INFO_TIMEOUT")
        self.timeout_s = timeout_s
        self._opener = urllib.request.build_opener(_NoRedirect)

    async def __call__(self, body: dict[str, Any]) -> Any:
        if not isinstance(body, dict) or body.get("type") not in _ALLOWED_FIELDS:
            raise ValueError("INFO_REQUEST_NOT_ALLOWED")
        if set(body) != _ALLOWED_FIELDS[body["type"]]:
            raise ValueError("INFO_REQUEST_FIELDS_NOT_ALLOWED")
        if body.get("user") != self.account_ref:
            raise ValueError("INFO_ACCOUNT_SCOPE_MISMATCH")
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        return await asyncio.to_thread(self._post, encoded)

    def _post(self, encoded: bytes) -> Any:
        request = urllib.request.Request(
            INFO_URL, data=encoded, method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        with self._opener.open(request, timeout=self.timeout_s) as response:
            if response.status != 200:
                raise ValueError("INFO_HTTP_STATUS")
            if "application/json" not in response.headers.get("Content-Type", ""):
                raise ValueError("INFO_CONTENT_TYPE")
            raw = response.read(_MAX_BODY + 1)
            if len(raw) > _MAX_BODY:
                raise ValueError("INFO_BODY_TOO_LARGE")
        return json.loads(raw)


@dataclass(frozen=True)
class ReadOnlyAccountStatus:
    account_ref: str
    connection_state: str
    evidence_state: str
    observed_at_ms: int | None
    account_value: str | None
    open_orders: int | None
    positions: int | None
    fills: int | None
    reason: str
    recovery_required: bool = True
    orders_enabled: bool = False
    retry_uncertain_orders: bool = False
    live_order_capability: bool = False


class ReadOnlyAccountObserver:
    """Fail closed through disconnect, stale reads and conditional resync."""

    def __init__(
        self,
        *,
        account_ref: str,
        info: InfoTransport,
        dex: str,
        anchor_ms: int,
        anchor_tid: int | None,
        expected_orders: dict[str, int | None],
        owned_coins: frozenset[str],
        max_age_ms: int = 10_000,
        request_timeout_s: float = 20.0,
    ) -> None:
        self.account_ref = _account_ref(account_ref)
        if not isinstance(dex, str) or not isinstance(max_age_ms, int) or max_age_ms <= 0:
            raise ValueError("INVALID_OBSERVER_SCOPE")
        if not 0 < request_timeout_s <= 60:
            raise ValueError("INVALID_OBSERVER_TIMEOUT")
        self.info = info
        self.dex = dex
        self.anchor_ms = anchor_ms
        self.anchor_tid = anchor_tid
        self.expected_orders = dict(expected_orders)
        self.owned_coins = owned_coins
        self.max_age_ms = max_age_ms
        self.request_timeout_s = request_timeout_s
        self._receipt: InfoReceipt | None = None
        self._observed_at_ms: int | None = None
        self._state = "UNKNOWN"
        self._reason = "NOT_OBSERVED"
        self._generation = 0

    @classmethod
    def from_environment(cls, environment: Mapping[str, str], **kwargs):
        account_ref = environment.get(ACCOUNT_ENV)
        if account_ref is None:
            raise ValueError("PUBLIC_ACCOUNT_REF_MISSING")
        return cls(account_ref=account_ref, **kwargs)

    def disconnect(self) -> None:
        self._generation += 1
        self._receipt = None
        self._observed_at_ms = None
        self._state = "RECOVERY_REQUIRED"
        self._reason = "INFO_DISCONNECTED"

    async def observe(self, *, now_ms: int | None = None) -> ReadOnlyAccountStatus:
        explicit_clock = now_ms is not None
        now_ms = time.time_ns() // 1_000_000 if now_ms is None else now_ms
        if isinstance(now_ms, bool) or not isinstance(now_ms, int) or now_ms < self.anchor_ms:
            raise ValueError("INVALID_OBSERVATION_TIME")
        self._generation += 1
        generation = self._generation
        self._receipt = None
        self._observed_at_ms = None
        self._state = "RECOVERING"
        self._reason = "INFO_READ_IN_PROGRESS"
        try:
            role = await asyncio.wait_for(
                self.info({"type": "userRole", "user": self.account_ref}),
                timeout=self.request_timeout_s,
            )
            if not isinstance(role, dict) or role.get("role") not in {"user", "subAccount"}:
                raise IncompleteInfoReport("PUBLIC_ACCOUNT_ROLE_UNVERIFIED")
            receipt = await asyncio.wait_for(
                collect_info_receipt(
                    self.info, account=self.account_ref, dex=self.dex,
                    anchor_ms=self.anchor_ms, anchor_tid=self.anchor_tid,
                    end_ms=now_ms, expected_orders=self.expected_orders,
                    owned_coins=self.owned_coins,
                ),
                timeout=self.request_timeout_s,
            )
        except Exception as error:
            if generation != self._generation:
                return self.status(now_ms=now_ms if explicit_clock else None)
            self._state = "RECOVERY_REQUIRED"
            self._reason = (
                str(error) if isinstance(error, IncompleteInfoReport)
                else "INFO_TIMEOUT" if isinstance(error, asyncio.TimeoutError)
                else "INFO_READ_FAILED"
            )
            return self.status(now_ms=now_ms if explicit_clock else None)
        if generation != self._generation:
            return self.status(now_ms=now_ms if explicit_clock else None)
        self._receipt = receipt
        self._observed_at_ms = now_ms
        self._state = "CONNECTED_INFO"
        self._reason = "CONDITIONAL_ONLY_NO_ATOMIC_SNAPSHOT"
        return self.status(now_ms=now_ms if explicit_clock else None)

    def status(self, *, now_ms: int | None = None) -> ReadOnlyAccountStatus:
        now_ms = time.time_ns() // 1_000_000 if now_ms is None else now_ms
        fresh = (
            self._receipt is not None and self._observed_at_ms is not None
            and 0 <= now_ms - self._observed_at_ms <= self.max_age_ms
        )
        receipt = self._receipt if fresh else None
        state = self._state if fresh or self._receipt is None else "STALE"
        reason = self._reason if state != "STALE" else "INFO_OBSERVATION_STALE"
        return ReadOnlyAccountStatus(
            account_ref=self.account_ref,
            connection_state=state,
            evidence_state="CONDITIONAL_ONLY" if receipt is not None else "UNKNOWN",
            observed_at_ms=self._observed_at_ms,
            account_value=receipt.account_value if receipt is not None else None,
            open_orders=len(receipt.open_orders) if receipt is not None else None,
            positions=len(receipt.positions) if receipt is not None else None,
            fills=len(receipt.fills) if receipt is not None else None,
            reason=reason,
        )
