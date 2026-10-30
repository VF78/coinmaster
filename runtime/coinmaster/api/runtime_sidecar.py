"""Loopback-only P5 runtime projection; it never imports Nautilus execution."""
from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.request
import urllib.parse
import time
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, StrictBool, field_validator, model_validator

from coinmaster.api.app import create_app as create_control_app
from coinmaster.api.gui_auth import GuiAuth, SESSION_COOKIE
from coinmaster.api.hl_public_candles import public_candles
from coinmaster.ops.stage_g_config import load_candidate, load_testnet_instance_config


UNKNOWN = "UNKNOWN"


class RuntimeSchema(BaseModel):
    """Strict, deliberately string-valued wire contract for operator money."""
    model_config = ConfigDict(extra="forbid")


class RuntimeStrategy(RuntimeSchema):
    strategy_class: str
    config_hash: str
    config_name: str | None = None
    registered: bool | None = None
    running: bool | None = None
    entries_enabled: bool | None = None


class RuntimeBalances(RuntimeSchema):
    active_usdt: str
    reserve_usdt: str
    total_usdt: str
    native_cash: str
    modelled_funding_cash: str
    funding_state: str


class RuntimeFeed(RuntimeSchema):
    state: str
    mark: str | None = None
    mark_age_ns: int | None = None
    quote_age_ns: int | None = None
    funding_rate: str | None = None
    funding_age_ns: int | None = None
    next_funding_ns: int | None = None


class RuntimeEvent(RuntimeSchema):
    cursor: int
    event_id: str
    kind: str


class RuntimeFunding(RuntimeSchema):
    event_id: str
    instrument_id: str
    settlement_ns: int
    rate: str
    mark: str
    cash_delta: str
    state: str


class RuntimePosition(RuntimeSchema):
    instrument_id: str
    signed_quantity: str


class RuntimeOrder(RuntimeSchema):
    client_order_id: str


class RuntimeMargin(RuntimeSchema):
    im: str
    mm: str
    free_margin: str


class RuntimeState(RuntimeSchema):
    version: str
    mode: Literal["paper", "UNKNOWN"]
    live_order_capability: bool | None = None
    worker_state: str
    strategy: RuntimeStrategy
    reconciliation: str
    lock: str
    balances: RuntimeBalances
    positions: list[RuntimePosition]
    orders: list[RuntimeOrder]
    fills: list[RuntimeEvent]
    feeds: dict[str, RuntimeFeed]
    margin: RuntimeMargin
    rejects: str
    fees: str
    transfers: str
    funding: list[RuntimeFunding]
    warnings: list[str]
    events: list[RuntimeEvent]
    event_cursor: int


class RuntimeEventsResponse(RuntimeSchema):
    events: list[RuntimeEvent]
    next_cursor: int
    warnings: list[str] = []


class RuntimeCommandResponse(RuntimeSchema):
    command: Literal["pause-new-entries", "resume-new-entries", "flatten-paper"]
    idempotency_key: str
    status: Literal["ACCEPTED", "DUPLICATE"]
    mode: Literal["paper"]


# This contract is intentionally independent from RuntimeState.  The latter
# is the older coinmaster-paper projection and must never be relabelled as
# this isolated Hyperliquid/Sandbox instance.
class HlStagegHashes(RuntimeSchema):
    candidate_sha256: str
    strategy_sha256: str
    execution_policy_sha256: str


class HlStagegWarmup(RuntimeSchema):
    state: str
    rows: int | None = None


class HlStagegDepositProtection(RuntimeSchema):
    state: Literal["NOT_INITIALIZED", "RECOVERY_REQUIRED", "ARMED", "EQUITY_UNAVAILABLE", "EXITING", "TRIPPED_FLAT", "EXIT_INCOMPLETE"]
    drawdown_limit_percent: int
    currency: str | None = None
    equity: str | None = None
    high_water_equity: str | None = None
    threshold_equity: str | None = None
    observed_at_ns: int | None = None
    # Worker wire values are UTC epoch nanoseconds; normalize exactly to ISO
    # text before returning to browsers, whose Number type cannot hold int64 ns.
    last_daily_close_utc: str | None = None
    daily_sample_missed: StrictBool
    trigger: dict[str, str] | None = None

    @field_validator("last_daily_close_utc", mode="before")
    @classmethod
    def worker_utc_ns_to_iso(cls, value: object) -> str | None:
        if value is None:
            return None
        if type(value) is not int or value < 0:
            raise ValueError("invalid UTC epoch nanoseconds")
        seconds, nanoseconds = divmod(value, 1_000_000_000)
        try:
            instant = datetime.fromtimestamp(seconds, timezone.utc)
        except (OverflowError, OSError, ValueError) as error:
            raise ValueError("invalid UTC epoch nanoseconds") from error
        return f"{instant:%Y-%m-%dT%H:%M:%S}.{nanoseconds:09d}Z"

    @field_validator("equity", "high_water_equity", "threshold_equity")
    @classmethod
    def decimal_or_unavailable(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            if not Decimal(value).is_finite():
                raise ValueError("non-finite deposit protection decimal")
        except InvalidOperation as error:
            raise ValueError("invalid deposit protection decimal") from error
        return value


class HlStagegProtectionCommandRequest(RuntimeSchema):
    idempotency_key: str
    drawdown_limit_percent: int

    @field_validator("idempotency_key")
    @classmethod
    def nonempty_idempotency_key(cls, value: str) -> str:
        if not value.strip() or len(value) > 200:
            raise ValueError("invalid idempotency key")
        return value

    @field_validator("drawdown_limit_percent", mode="before")
    @classmethod
    def strict_percent(cls, value: Any) -> int:
        if type(value) is not int or not 1 <= value <= 99:
            raise ValueError("drawdown_limit_percent must be an integer from 1 to 99")
        return value


class HlStagegProtectionResetRequest(RuntimeSchema):
    idempotency_key: str
    confirm: Literal[True]

    @field_validator("idempotency_key")
    @classmethod
    def nonempty_idempotency_key(cls, value: str) -> str:
        if not value.strip() or len(value) > 200:
            raise ValueError("invalid idempotency key")
        return value

    @field_validator("confirm", mode="before")
    @classmethod
    def require_explicit_confirmation(cls, value: Any) -> bool:
        if value is not True:
            raise ValueError("confirm must be true")
        return True


class HlStagegProtectionCommand(RuntimeSchema):
    instance_id: Literal["hl-stageg-testnet", "hl-stageg-live"]
    command: Literal["set-deposit-protection", "reset-deposit-protection"]
    idempotency_key: str
    status: Literal["APPLIED"]
    deposit_protection: HlStagegDepositProtection


class HlStagegAccount(RuntimeSchema):
    status: Literal["AVAILABLE", "PARTIAL", "UNAVAILABLE"] = "UNAVAILABLE"
    observed_at_ns: int | None = None
    native_cash: str | None = None
    native_free: str | None = None
    native_locked: str | None = None
    realized_pnl_net_fees: str | None = None
    unrealized_pnl: str | None = None
    fees: str | None = None
    mark_state: Literal["CURRENT", "STALE_OR_MISSING"] | None = None
    equity: str | None = None
    im: str | None = None
    mm: str | None = None
    free_margin: str | None = None

    @field_validator("native_cash", "native_free", "native_locked", "realized_pnl_net_fees", "unrealized_pnl", "fees", "equity", "im", "mm", "free_margin")
    @classmethod
    def decimal_or_unavailable(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            if not Decimal(value).is_finite():
                raise ValueError("non-finite account decimal")
        except InvalidOperation as error:
            raise ValueError("invalid account decimal") from error
        return value

    @model_validator(mode="before")
    @classmethod
    def classify_native_fields(cls, value: Any) -> Any:
        if isinstance(value, dict) and "status" not in value:
            fields = ("native_cash", "native_free", "native_locked", "realized_pnl_net_fees", "unrealized_pnl", "fees", "equity")
            known = sum(value.get(field) is not None for field in fields)
            return {**value, "status": "AVAILABLE" if known == len(fields) else "PARTIAL" if known else "UNAVAILABLE"}
        return value


class HlStagegEntryControl(RuntimeSchema):
    state: Literal["RUNNING", "PAUSED"]
    capability: Literal["READY", "UNAVAILABLE"]


class HlStagegEvent(RuntimeSchema):
    cursor: int
    event_id: str
    kind: str
    provenance: Literal["SANDBOX", "LIVE"] = "SANDBOX"


class HlStagegPosition(RuntimeSchema):
    instrument_id: str
    signed_quantity: str
    average_entry_price: str | None = None
    provenance: Literal["SANDBOX", "LIVE"] = "SANDBOX"

    @field_validator("average_entry_price")
    @classmethod
    def native_average_entry(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                if not Decimal(value).is_finite() or Decimal(value) <= 0:
                    raise ValueError("invalid native average entry")
            except InvalidOperation as error:
                raise ValueError("invalid native average entry") from error
        return value


class HlStagegOrder(RuntimeSchema):
    client_order_id: str
    instrument_id: str | None = None
    account_id: str | None = None
    venue_order_id: str | None = None
    side: str | None = None
    order_type: str | None = None
    time_in_force: str | None = None
    price: str | None = None
    quantity: str | None = None
    filled_quantity: str | None = None
    leaves_quantity: str | None = None
    reduce_only: bool | None = None
    post_only: bool | None = None
    status: str | None = None
    submitted_at_ns: int | None = None
    updated_at_ns: int | None = None
    provenance: Literal["SANDBOX", "LIVE"] = "SANDBOX"


class HlStagegProjection(RuntimeSchema):
    version: Literal["hl-stageg-projection-v1"]
    instance_id: Literal["hl-stageg-testnet", "hl-stageg-live"]
    projection_state: Literal["READY", "STALE", "UNAVAILABLE", "INVALID"]
    observed_at_ns: int | None = None
    mode: Literal["sandbox", "live"]
    environment: Literal["mainnet-public", "mainnet"]
    live_order_capability: bool = False
    profile: dict[str, Any] | None = None
    real_order_approval: bool = False
    runtime_release_commit: str | None = None
    runtime_master_address_sha256: str | None = None
    run_epoch: str | None = None
    virtual_capital_resets_on_flat_restart: bool | None = None
    sandbox_starting_cash_usdc: str | None = None
    recovery_required: bool | None = None
    recovery_capability: str | None = None
    native_thread_alive: bool | None = None
    process_state: str
    reconciliation: str
    hashes: HlStagegHashes
    warmup: HlStagegWarmup
    gates: dict[str, str | bool]
    account: HlStagegAccount
    entry_control: HlStagegEntryControl
    funding_state: str
    feeds: dict[str, RuntimeFeed]
    positions: list[HlStagegPosition]
    deposit_protection: HlStagegDepositProtection | None = None
    orders: list[HlStagegOrder]
    events: list[HlStagegEvent]
    event_cursor: int
    provenance: Literal["SANDBOX_LOCAL_READ_ONLY_WORKER_PROJECTION", "NATIVE_MAINNET_OWNED_ACCOUNT"]
    warnings: list[str]


# This is intentionally a source-identity document, not another runtime
# projection. It lets the Strategy page describe exactly what is sealed for
# the isolated Sandbox worker without suggesting account facts or a mutable
# control channel exist.
class HlStagegStrategy(RuntimeSchema):
    version: Literal["hl-stageg-strategy-v1"]
    instance_id: Literal["hl-stageg-testnet", "hl-stageg-live"]
    source_state: Literal["SEALED_CONFIGURATION_CHECKED", "INVALID"]
    running_state: Literal["RUNNING_MATCH", "MISMATCH", "NOT_CONFIRMED"]
    strategy_id: str
    mode: Literal["sandbox", "live"]
    environment: Literal["mainnet-public", "mainnet"]
    candidate: dict[str, str]
    hashes: HlStagegHashes
    capital_assumption: str
    research_comparison_assumption: str
    public_venue_profile: str
    account_margin: str
    account_fee_schedule: str
    funding_treatment: str
    promotion_enabled: Literal[False] = False
    promotion_reason: Literal["SEPARATE_NATIVE_LIFECYCLE_GATE_REQUIRED"]
    warnings: list[str]


class HlStagegControlAction(RuntimeSchema):
    enabled: bool = False
    blocker: str | None = None
    requires_confirmation: bool = False


class HlStagegControls(RuntimeSchema):
    instance_id: Literal["hl-stageg-testnet", "hl-stageg-live"] = "hl-stageg-testnet"
    mode: Literal["sandbox", "live"] = "sandbox"
    projection_state: Literal["READY", "STALE", "UNAVAILABLE", "INVALID"]
    pause: HlStagegControlAction
    resume: HlStagegControlAction
    flatten: HlStagegControlAction
    promotion: HlStagegControlAction


class HlStagegControlCommand(RuntimeSchema):
    instance_id: Literal["hl-stageg-testnet", "hl-stageg-live"]
    command: Literal["pause-new-entries", "resume-new-entries"]
    idempotency_key: str
    status: Literal["ACCEPTED", "DUPLICATE"]
    entry_control: Literal["RUNNING", "PAUSED"]


def hl_stageg_controls(projection: HlStagegProjection, control_transport_available: bool = False) -> HlStagegControls:
    """No mutation route exists until the isolated native worker owns commands.

    The legacy /runtime/commands relay targets coinmaster-paper and must never
    be represented as authority over this HL Stage-G Sandbox instance.
    """
    live_denied = projection.mode == "live" and (not projection.real_order_approval or not projection.live_order_capability)
    unavailable = "EXACT_LIVE_ORDER_APPROVAL_REQUIRED" if live_denied else None if projection.projection_state == "READY" else f"NATIVE_PROJECTION_{projection.projection_state}"
    enabled = (
        unavailable is None
        and projection.native_thread_alive is True
        and projection.entry_control.capability == "READY"
        and control_transport_available
    )
    blocker = None if enabled else unavailable or (
        "NATIVE_ENTRY_CONTROL_UNAVAILABLE" if projection.entry_control.capability != "READY" else "NATIVE_ENTRY_CONTROL_TRANSPORT_UNAVAILABLE"
    )
    return HlStagegControls(
        instance_id=projection.instance_id, mode=projection.mode,
        projection_state=projection.projection_state,
        pause=HlStagegControlAction(enabled=enabled, blocker=blocker),
        resume=HlStagegControlAction(enabled=enabled, blocker=blocker),
        flatten=HlStagegControlAction(blocker=unavailable or "NO_IDEMPOTENT_NATIVE_FLATTEN_RECOVERY", requires_confirmation=True),
        promotion=HlStagegControlAction(blocker="SEPARATE_NATIVE_LIFECYCLE_GATE_REQUIRED"),
    )


def _worker_health(url: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/health", timeout=3) as response:
            return json.loads(response.read())
    except Exception:
        return {"state": "WORKER_DISCONNECTED", "warnings": ["WORKER_DISCONNECTED"]}


class RuntimeReader:
    def __init__(self, database: str, worker_url: str) -> None:
        self.database, self.worker_url = database, worker_url

    def _db(self) -> sqlite3.Connection | None:
        try:
            return sqlite3.connect(f"file:{Path(self.database).resolve()}?mode=ro", uri=True)
        except sqlite3.Error:
            return None

    def runtime(self) -> RuntimeState:
        health = _worker_health(self.worker_url)
        db = self._db(); snapshot: dict[str, Any] = {}; events: list[dict] = []; funding: list[dict] = []
        if db is not None:
            try:
                row = db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone(); snapshot = json.loads(row[0]) if row else {}
                events = [{"cursor": r[0], "event_id": r[1], "kind": r[2]} for r in db.execute("SELECT rowid,event_id,kind FROM paper_events ORDER BY rowid DESC LIMIT 100")]
                funding = [{"event_id": r[0], "instrument_id": r[1], "settlement_ns": r[2], "rate": r[3], "mark": r[4], "cash_delta": r[5], "state": r[6]} for r in db.execute("SELECT event_id,instrument_id,settlement_ns,rate,mark,cash_delta,state FROM paper_funding_ledger ORDER BY settlement_ns DESC")]
            except sqlite3.Error:
                health.setdefault("warnings", []).append("JOURNAL_UNAVAILABLE")
            finally: db.close()
        warnings = list(health.get("warnings", []))
        if not snapshot: warnings.append("MISSING_SNAPSHOT")
        strategy = health.get("strategy", {})
        return RuntimeState.model_validate({
            "version": "runtime-v1", "mode": health.get("mode", "paper"), "live_order_capability": health.get("live_order_capability"), "worker_state": health.get("state", "WORKER_DISCONNECTED"),
            "strategy": {key: strategy.get(key) for key in ("strategy_class", "config_hash", "config_name", "registered", "running", "entries_enabled") if strategy.get(key) is not None} or {"strategy_class": UNKNOWN, "config_hash": UNKNOWN},
            "reconciliation": health.get("reconciliation", UNKNOWN), "lock": "UNKNOWN_READ_ONLY_SIDECAR",
            "balances": {"active_usdt": UNKNOWN, "reserve_usdt": UNKNOWN, "total_usdt": UNKNOWN, "native_cash": UNKNOWN, "modelled_funding_cash": str(sum((__import__('decimal').Decimal(x["cash_delta"]) for x in funding), __import__('decimal').Decimal("0"))), "funding_state": "MODELLED_LEDGER_UNPOSTED"},
            "positions": snapshot.get("positions", []), "orders": snapshot.get("orders", []), "fills": [x for x in events if x["kind"] == "fill"],
            "feeds": {key: {field: value.get(field) for field in ("state", "mark", "mark_age_ns", "quote_age_ns", "funding_rate", "funding_age_ns") if value.get(field) is not None} for key, value in health.get("feeds", {}).items()}, "margin": {"im": UNKNOWN, "mm": UNKNOWN, "free_margin": UNKNOWN}, "rejects": UNKNOWN, "fees": UNKNOWN, "transfers": UNKNOWN,
            "funding": funding, "warnings": warnings, "events": list(reversed(events)), "event_cursor": events[0]["cursor"] if events else 0,
        })

    def events(self, cursor: int) -> RuntimeEventsResponse:
        db = self._db()
        if db is None: return RuntimeEventsResponse(events=[], next_cursor=cursor, warnings=["JOURNAL_UNAVAILABLE"])
        try:
            rows = [{"cursor": r[0], "event_id": r[1], "kind": r[2]} for r in db.execute("SELECT rowid,event_id,kind FROM paper_events WHERE rowid > ? ORDER BY rowid LIMIT 100", (cursor,))]
            return RuntimeEventsResponse(events=rows, next_cursor=rows[-1]["cursor"] if rows else cursor)
        finally: db.close()

    def command(self, command: str, key: str, token: str) -> RuntimeCommandResponse:
        request = urllib.request.Request(f"{self.worker_url.rstrip('/')}/commands", data=json.dumps({"command": command}).encode(), method="POST", headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=5) as response: return RuntimeCommandResponse.model_validate(json.loads(response.read()))
        except Exception as error:
            raise HTTPException(503, "paper worker command channel unavailable") from error


class HlPublicCandle(RuntimeSchema):
    open_time_ms: int
    close_time_ms: int
    open: str
    high: str
    low: str
    close: str
    volume: str
    trades: int


class HlPublicCandles(RuntimeSchema):
    version: Literal["hl-public-candles-v1"]
    venue: Literal["HYPERLIQUID"]
    environment: Literal["mainnet-public", "mainnet"]
    source: Literal["OFFICIAL_INFO_CANDLE_SNAPSHOT"]
    execution_evidence: Literal[False]
    coin: Literal["BTC", "SOL"]
    interval: Literal["1m", "5m", "15m", "1h", "4h", "1d"]
    state: Literal["READY", "STALE", "UNAVAILABLE", "INVALID"]
    observed_at_ms: int | None
    latest_closed_at_ms: int | None
    candles: list[HlPublicCandle]
    reason: str | None


class HlNativeEquityWindow(RuntimeSchema):
    state: Literal["AVAILABLE", "UNAVAILABLE"]
    baseline_at_ns: int | None
    baseline_equity_usdc: str | None
    change_usdc: str | None
    change_percent: str | None

    @field_validator("baseline_equity_usdc", "change_usdc", "change_percent")
    @classmethod
    def finite_decimal(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                if not Decimal(value).is_finite():
                    raise ValueError("invalid native equity decimal")
            except InvalidOperation as error:
                raise ValueError("invalid native equity decimal") from error
        return value


class HlNativeEquityChanges(RuntimeSchema):
    version: Literal["hl-native-equity-changes-v1"]
    instance_id: Literal["hl-stageg-testnet", "hl-stageg-live"]
    run_epoch: str | None
    source: Literal["NATIVE_SANDBOX_ACCOUNT", "NATIVE_LIVE_ACCOUNT"]
    state: Literal["READY", "STALE", "UNAVAILABLE", "INVALID"]
    as_of_ns: int | None
    equity_usdc: str | None
    windows: dict[str, HlNativeEquityWindow]

    @field_validator("equity_usdc")
    @classmethod
    def finite_equity(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                if not Decimal(value).is_finite():
                    raise ValueError("invalid native equity")
            except InvalidOperation as error:
                raise ValueError("invalid native equity") from error
        return value

    @model_validator(mode="after")
    def exact_windows(self):
        if set(self.windows) != {"24h", "7d", "30d"}:
            raise ValueError("invalid native equity windows")
        if self.state == "READY" and (not self.run_epoch or self.as_of_ns is None or self.equity_usdc is None):
            raise ValueError("incomplete native equity identity")
        for item in self.windows.values():
            values = (item.baseline_at_ns, item.baseline_equity_usdc, item.change_usdc, item.change_percent)
            if item.state == "UNAVAILABLE" and any(value is not None for value in values):
                raise ValueError("unavailable native equity window carries values")
            if item.state == "AVAILABLE" and any(value is None for value in values):
                raise ValueError("available native equity window is incomplete")
        return self


class HlStagegFill(RuntimeSchema):
    cursor: int
    trade_id: str
    native_event_id: str | None
    client_order_id: str | None
    venue_order_id: str | None
    episode_id: str | None
    instrument_id: str
    action: str | None = None
    order_side: str | None
    quantity: str
    price: str
    commission_amount: str | None
    commission_currency: str | None
    liquidity_side: str | None
    ts_event_ns: int | None
    ts_init_ns: int | None


class HlStagegFillHistory(RuntimeSchema):
    fills: list[HlStagegFill]
    next_cursor: int
    detail_store_available: bool
    historical_id_only_count: int
    version: Literal["hl-stageg-native-fills-v1"]
    instance_id: Literal["hl-stageg-testnet", "hl-stageg-live"]
    run_epoch: str

    @field_validator("run_epoch")
    @classmethod
    def nonempty_run_epoch(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("run_epoch is required")
        return value


class HlStagegFillReader:
    """Relay exact future-fill facts over the authenticated loopback worker API."""
    def __init__(self, url: str, token: str | None, instance_id: str = "hl-stageg-testnet") -> None:
        self.url, self.token = url.rstrip("/"), token
        self.instance_id = instance_id

    def history(self, cursor: int = 0, limit: int = 100) -> HlStagegFillHistory:
        if cursor < 0 or not 1 <= limit <= 100:
            raise HTTPException(422, "fill history query bounds invalid")
        if not self.token:
            raise HTTPException(503, "Stage-G fill history is unavailable")
        request = urllib.request.Request(
            f"{self.url}/fills?cursor={cursor}&limit={limit}", method="GET",
            headers={"Accept": "application/json", "Authorization": f"Bearer {self.token}",
                     "X-Coinmaster-Instance": self.instance_id},
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                payload = json.loads(response.read())
            result = HlStagegFillHistory.model_validate(payload)
            if result.version != "hl-stageg-native-fills-v1" or result.instance_id != self.instance_id or not result.run_epoch:
                raise ValueError("invalid Stage-G fill response identity")
            return result
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(503, "Stage-G fill journal is unavailable") from error


class HlNativeEquityReader:
    """Proxy this process's worker-owned history without reading its SQLite."""
    MAX_AGE_NS = 600_000_000_000
    MAX_FUTURE_SKEW_NS = 5_000_000_000

    def __init__(self, url: str, token: str | None, instance_id: str = "hl-stageg-testnet") -> None:
        self.url, self.token = url.rstrip("/"), token
        self.instance_id = instance_id

    def unavailable(self, state: Literal["UNAVAILABLE", "INVALID", "STALE"]) -> HlNativeEquityChanges:
        return HlNativeEquityChanges.model_validate({
            "version": "hl-native-equity-changes-v1", "instance_id": self.instance_id,
            "run_epoch": None, "source": "NATIVE_LIVE_ACCOUNT" if self.instance_id == "hl-stageg-live" else "NATIVE_SANDBOX_ACCOUNT", "state": state,
            "as_of_ns": None, "equity_usdc": None,
            "windows": {key: {"state": "UNAVAILABLE", "baseline_at_ns": None,
                              "baseline_equity_usdc": None, "change_usdc": None,
                              "change_percent": None} for key in ("24h", "7d", "30d")},
        })

    def changes(self) -> HlNativeEquityChanges:
        if not self.token:
            return self.unavailable("UNAVAILABLE")
        request = urllib.request.Request(
            f"{self.url}/equity-changes", method="GET",
            headers={"Accept": "application/json", "Authorization": f"Bearer {self.token}",
                     "X-Coinmaster-Instance": self.instance_id},
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                payload = json.loads(response.read())
            result = HlNativeEquityChanges.model_validate(payload)
            if result.instance_id != self.instance_id or result.source != ("NATIVE_LIVE_ACCOUNT" if self.instance_id == "hl-stageg-live" else "NATIVE_SANDBOX_ACCOUNT"):
                return self.unavailable("INVALID")
            if result.state == "READY":
                now_ns = time.time_ns()
                if result.as_of_ns > now_ns + self.MAX_FUTURE_SKEW_NS:
                    return self.unavailable("INVALID")
                if now_ns - result.as_of_ns > self.MAX_AGE_NS:
                    return self.unavailable("STALE")
            return result
        except (OSError, TimeoutError):
            return self.unavailable("UNAVAILABLE")
        except (ValueError, TypeError):
            return self.unavailable("INVALID")


class HlStagegProjectionReader:
    """Read only the HL worker's loopback GET endpoint, never a journal."""
    MAX_AGE_NS = 15_000_000_000
    MAX_FUTURE_SKEW_NS = 5_000_000_000

    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")

    @staticmethod
    def unavailable(state: Literal["STALE", "UNAVAILABLE", "INVALID"], warning: str) -> HlStagegProjection:
        return HlStagegProjection.model_validate({
            "version": "hl-stageg-projection-v1", "instance_id": "hl-stageg-testnet",
            "projection_state": state, "mode": "sandbox", "environment": "mainnet-public",
            "live_order_capability": False, "process_state": "WORKER_PROJECTION_UNAVAILABLE",
            "reconciliation": UNKNOWN,
            "hashes": {"candidate_sha256": UNKNOWN, "strategy_sha256": UNKNOWN, "execution_policy_sha256": UNKNOWN},
            "warmup": {"state": UNKNOWN}, "gates": {}, "account": {}, "entry_control": {"state": "RUNNING", "capability": "UNAVAILABLE"},
            "funding_state": "UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT",
            "feeds": {}, "positions": [], "orders": [], "events": [], "event_cursor": 0,
            "provenance": "SANDBOX_LOCAL_READ_ONLY_WORKER_PROJECTION", "warnings": [warning],
        })

    def runtime(self) -> HlStagegProjection:
        try:
            request = urllib.request.Request(f"{self.url}/status", method="GET", headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=2) as response:
                payload = json.loads(response.read())
            # The worker fixes identity and capability too, but validate them
            # again at the API boundary to fail closed on a swapped endpoint.
            projection = HlStagegProjection.model_validate(payload)
            if projection.instance_id != "hl-stageg-testnet" or projection.mode != "sandbox" or projection.projection_state != "READY" or projection.live_order_capability is not False:
                return self.unavailable("INVALID", "INVALID_HL_STAGEG_PROJECTION")
            now_ns = time.time_ns()
            if projection.observed_at_ns is None or projection.observed_at_ns > now_ns + self.MAX_FUTURE_SKEW_NS:
                return self.unavailable("INVALID", "INVALID_HL_STAGEG_OBSERVATION_TIME")
            if now_ns - projection.observed_at_ns > self.MAX_AGE_NS:
                return self.unavailable("STALE", "HL_STAGEG_STATUS_STALE")
            return projection
        except (OSError, TimeoutError):
            return self.unavailable("UNAVAILABLE", "HL_STAGEG_PROJECTION_UNAVAILABLE")
        except (ValueError, TypeError):
            return self.unavailable("INVALID", "INVALID_HL_STAGEG_PROJECTION")


def live_order_approval_matches(projection: HlStagegProjection) -> bool:
    """Read the exact installed Live seal and owner approval; never infer from UI."""
    try:
        root = Path("/srv/coinmaster/hl-live/current").resolve(strict=True)
        identity = json.loads((root / "live-release.json").read_text())
        fingerprint = json.loads((root / "configs/hl-stageg-live.account-fingerprint.json").read_text())
        approval = json.loads(Path("/etc/coinmaster/live-order-approval.json").read_text())
        profile = projection.profile or {}
        return (projection.instance_id == "hl-stageg-live" and projection.mode == "live"
                and projection.projection_state == "READY" and projection.live_order_capability is True
                and projection.reconciliation == "CURRENT" and projection.recovery_required is False
                and projection.native_thread_alive is True and bool(projection.run_epoch)
                and projection.observed_at_ns is not None
                and -HlStagegProjectionReader.MAX_FUTURE_SKEW_NS <= time.time_ns() - projection.observed_at_ns <= HlStagegProjectionReader.MAX_AGE_NS
                and approval.get("schema") == "coinmaster-live-order-approval-v1"
                and approval.get("instance_id") == "hl-stageg-live" and approval.get("orders_approved") is True
                and approval.get("pilot_capital_usdc") == "82"
                and approval.get("release_commit") == identity["source_commit"] == projection.runtime_release_commit
                and approval.get("master_address_sha256") == fingerprint["master_address_sha256"] == projection.runtime_master_address_sha256
                and all(approval.get(key) == identity[key] == profile.get(key)
                        for key in ("strategy_sha256", "candidate_sha256", "profile_sha256")))
    except (OSError, ValueError, KeyError, TypeError):
        return False


class HlLiveProjectionReader(HlStagegProjectionReader):
    """Project native Live facts; never substitute the Sandbox or planned seed."""
    @staticmethod
    def unavailable(state, warning):
        payload = HlStagegProjectionReader.unavailable(state, warning).model_dump()
        payload.update(instance_id="hl-stageg-live", mode="live", environment="mainnet",
                       provenance="NATIVE_MAINNET_OWNED_ACCOUNT", process_state="LIVE_INACTIVE_OR_UNAVAILABLE")
        return HlStagegProjection.model_validate(payload)

    def runtime(self):
        try:
            request = urllib.request.Request(f"{self.url}/status", headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=2) as response:
                raw = json.loads(response.read())
            if (raw.get("instance_id") != "hl-stageg-live" or raw.get("mode") != "live"
                    or raw.get("environment") != "mainnet" or raw.get("live_order_capability") is not True
                    or raw.get("version") != "hl-stageg-live-projection-v1"
                    or raw.get("provenance") != "NATIVE_MAINNET_OWNED_ACCOUNT" or not raw.get("run_epoch")):
                raise ValueError("identity mismatch")
            observed = raw.get("observed_at_ns")
            if type(observed) is not int or observed > time.time_ns() + self.MAX_FUTURE_SKEW_NS:
                raise ValueError("observation time unavailable")
            if time.time_ns() - observed > self.MAX_AGE_NS:
                return self.unavailable("STALE", "LIVE_STATUS_STALE")
            profile = raw.get("profile") or {}
            account = raw.get("account") or {}
            account_fields = {key: account[key] for key in HlStagegAccount.model_fields if key in account}
            account_fields.update(native_free=account.get("withdrawable"), native_locked=account.get("margin_used"),
                                  observed_at_ns=observed)
            if raw.get("account_state") != "CURRENT":
                account_fields = {}
            hashes = {key: profile.get(key, UNKNOWN) for key in HlStagegHashes.model_fields}
            gates = {"attachable": raw.get("orders_enabled") is True}
            result = HlStagegProjection.model_validate({
                "version": "hl-stageg-projection-v1", "instance_id": "hl-stageg-live", "mode": "live",
                "environment": "mainnet", "projection_state": "READY", "observed_at_ns": observed,
                "live_order_capability": True, "run_epoch": raw["run_epoch"], "profile": profile,
                "runtime_release_commit": raw.get("release_commit"),
                "runtime_master_address_sha256": raw.get("master_address_sha256"),
                "process_state": raw.get("state", UNKNOWN), "reconciliation": "CURRENT" if raw.get("account_state") == "CURRENT" else UNKNOWN,
                "recovery_required": raw.get("recovery_required", True), "recovery_capability": raw.get("recovery_capability"),
                "native_thread_alive": raw.get("native_thread_alive") is True,
                "hashes": hashes, "warmup": {"state": UNKNOWN, **{key: value for key, value in raw.get("warmup", {}).items() if key in HlStagegWarmup.model_fields}},
                "gates": gates, "account": account_fields, "entry_control": raw.get("entry_control", {"state": "PAUSED", "capability": "UNAVAILABLE"}),
                "funding_state": "NATIVE_ACCOUNT_SETTLEMENT", "feeds": raw.get("feeds", {}),
                "positions": [{**row, "provenance": "LIVE"} for row in raw.get("positions", [])],
                "orders": [{**row, "provenance": "LIVE"} for row in raw.get("orders", [])],
                "events": [{**row, "provenance": "LIVE"} for row in raw.get("events", [])],
                "event_cursor": raw.get("event_cursor", 0), "deposit_protection": raw.get("deposit_protection"),
                "provenance": "NATIVE_MAINNET_OWNED_ACCOUNT", "warnings": ["EXACT_LIVE_ORDER_APPROVAL_REQUIRED"],
            })
            approved = raw.get("real_order_approval") is True and live_order_approval_matches(result)
            return result.model_copy(update={"real_order_approval": approved, "warnings": [] if approved else ["EXACT_LIVE_ORDER_APPROVAL_REQUIRED"]})
        except (OSError, TimeoutError):
            return self.unavailable("UNAVAILABLE", "LIVE_WORKER_UNAVAILABLE")
        except (ValueError, TypeError, KeyError):
            return self.unavailable("INVALID", "INVALID_LIVE_PROJECTION")


class HlStagegControlRelay:
    """Relay only entry admission commands to the exact loopback Stage-G worker."""
    def __init__(self, url: str, token: str | None, instance_id: str = "hl-stageg-testnet") -> None:
        self.url, self.token = url.rstrip("/"), token
        self.instance_id = instance_id

    def command(self, command: Literal["pause-new-entries", "resume-new-entries"], idempotency_key: str) -> HlStagegControlCommand:
        if not self.token:
            raise HTTPException(503, "Stage-G native entry control is unavailable")
        request = urllib.request.Request(
            f"{self.url}/controls/{command}", data=b"{}", method="POST",
            headers={"Authorization": f"Bearer {self.token}", "Idempotency-Key": idempotency_key,
                     "X-Coinmaster-Instance": self.instance_id, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                payload = HlStagegControlCommand.model_validate(json.loads(response.read()))
        except urllib.error.HTTPError as error:
            if error.code == 409:
                raise HTTPException(409, "Stage-G idempotency key conflicts with a prior command") from error
            raise HTTPException(503, "Stage-G native entry control is unavailable") from error
        except (OSError, TimeoutError, ValueError, TypeError):
            raise HTTPException(503, "Stage-G native entry control is unavailable")
        if payload.instance_id != self.instance_id or payload.command != command or payload.idempotency_key != idempotency_key:
            raise HTTPException(503, "Stage-G native entry control identity mismatch")
        return payload


class HlStagegDepositProtectionRelay:
    """Relay bounded deposit policy commands to the instance-bound loopback worker."""
    def __init__(self, url: str, token: str | None, instance_id: str = "hl-stageg-testnet") -> None:
        self.url, self.token = url.rstrip("/"), token
        self.instance_id = instance_id

    def command(self, command: Literal["set-deposit-protection", "reset-deposit-protection"], body: dict[str, Any]) -> HlStagegProtectionCommand:
        if not self.token:
            raise HTTPException(503, "Stage-G deposit protection control is unavailable")
        request = urllib.request.Request(
            f"{self.url}/controls/{command}", data=json.dumps(body).encode(), method="POST",
            headers={"Authorization": f"Bearer {self.token}", "X-Coinmaster-Instance": self.instance_id,
                     "Idempotency-Key": str(body.get("idempotency_key", "")), "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                payload = HlStagegProtectionCommand.model_validate(json.loads(response.read()))
        except urllib.error.HTTPError as error:
            if error.code == 409:
                raise HTTPException(409, "Stage-G idempotency key conflicts with a prior command") from error
            raise HTTPException(503, "Stage-G deposit protection control is unavailable") from error
        except (OSError, TimeoutError, ValueError, TypeError):
            raise HTTPException(503, "Stage-G deposit protection control is unavailable")
        if payload.instance_id != self.instance_id or payload.command != command or payload.idempotency_key != body.get("idempotency_key"):
            raise HTTPException(503, "Stage-G deposit protection identity mismatch")
        readback = payload.deposit_protection
        now_ns = time.time_ns()
        if readback.observed_at_ns is None or readback.observed_at_ns > now_ns + HlStagegProjectionReader.MAX_FUTURE_SKEW_NS or now_ns - readback.observed_at_ns > HlStagegProjectionReader.MAX_AGE_NS:
            raise HTTPException(503, "Stage-G deposit protection read-back is stale")
        if command == "set-deposit-protection" and readback.drawdown_limit_percent != body.get("drawdown_limit_percent"):
            raise HTTPException(503, "Stage-G deposit protection percentage read-back mismatch")
        if command == "reset-deposit-protection":
            if readback.state != "ARMED" or readback.trigger is not None or readback.equity is None or readback.high_water_equity is None:
                raise HTTPException(503, "Stage-G deposit protection reset read-back mismatch")
            if Decimal(readback.equity) != Decimal(readback.high_water_equity):
                raise HTTPException(503, "Stage-G deposit protection reset baseline mismatch")
        return payload


class HlStagegStrategyReader:
    """Load and verify only the checked-in identity of the sealed candidate."""

    def __init__(self, runtime_root: Path | None = None, projection_reader: HlStagegProjectionReader | None = None) -> None:
        self.runtime_root = runtime_root or Path(__file__).resolve().parents[2]
        self.projection_reader = projection_reader

    @staticmethod
    def _running_state(hashes: dict[str, str], projection: HlStagegProjection | None) -> Literal["RUNNING_MATCH", "MISMATCH", "NOT_CONFIRMED"]:
        if projection is None or projection.projection_state != "READY" or projection.process_state in {
            "DATA_STALE/PAUSED", "WORKER_DISCONNECTED", "WORKER_PROJECTION_UNAVAILABLE",
        }:
            return "NOT_CONFIRMED"
        projected = projection.hashes.model_dump()
        if all(hashes[key] == projected[key] for key in hashes):
            return "RUNNING_MATCH"
        return "MISMATCH"

    def strategy(self) -> HlStagegStrategy:
        unknown_hashes = {"candidate_sha256": UNKNOWN, "strategy_sha256": UNKNOWN, "execution_policy_sha256": UNKNOWN}
        try:
            configs = self.runtime_root / "configs"
            approval = json.loads((configs / "stage-g-hl-sandbox-approval.json").read_text(encoding="utf-8"))
            instance = load_testnet_instance_config(configs / "hl-stageg-testnet.instance.json")
            loaded = load_candidate(configs / "stage-g-v1.json")
            strategy_hash = str(approval.get("strategy_sha256", UNKNOWN))
            hashes = {
                "candidate_sha256": loaded.sha256,
                "strategy_sha256": strategy_hash,
                "execution_policy_sha256": str(approval.get("execution_policy_sha256", UNKNOWN)),
            }
            if (
                approval.get("schema") != "coinmaster-stageg-hl-sandbox-approval-v1"
                or approval.get("candidate_sha256") != loaded.sha256
                or len(strategy_hash) != 64 or any(c not in "0123456789abcdef" for c in strategy_hash)
            ):
                raise ValueError("SEALED_APPROVAL_MISMATCH")
            projection = self.projection_reader.runtime() if self.projection_reader else None
            running_state = self._running_state(hashes, projection)
            candidate = {
                key: json.dumps(value, separators=(",", ":")) if isinstance(value, tuple) else str(value).lower() if isinstance(value, bool) else str(value)
                for key, value in asdict(loaded.candidate).items()
            }
            return HlStagegStrategy(
                version="hl-stageg-strategy-v1", instance_id="hl-stageg-testnet", source_state="SEALED_CONFIGURATION_CHECKED",
                running_state=running_state,
                strategy_id=instance.strategy_id, mode="sandbox", environment="mainnet-public", candidate=candidate, hashes=hashes,
                capital_assumption="10,000 USDC nominal Sandbox seed; not an observed account balance",
                research_comparison_assumption="10,000 USDT comparison only under an explicit 1:1 assumption",
                public_venue_profile="Current public Hyperliquid mainnet tiers and Sandbox leverage policy; account-specific tier is not claimed",
                account_margin=UNKNOWN, account_fee_schedule=UNKNOWN,
                funding_treatment="OBSERVED_MODELLED_UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT",
                promotion_enabled=False, promotion_reason="SEPARATE_NATIVE_LIFECYCLE_GATE_REQUIRED",
                warnings=["ACCOUNT_SPECIFIC_MARGIN_UNKNOWN", "ACCOUNT_SPECIFIC_FEES_UNKNOWN", "NO_RUNNING_INSTANCE_MUTATION"] + ([] if running_state == "RUNNING_MATCH" else [f"HL_STAGEG_RUNNING_{running_state}"]),
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return HlStagegStrategy(
                version="hl-stageg-strategy-v1", instance_id="hl-stageg-testnet", source_state="INVALID",
                running_state="NOT_CONFIRMED",
                strategy_id=UNKNOWN, mode="sandbox", environment="mainnet-public", candidate={}, hashes=unknown_hashes,
                capital_assumption="UNKNOWN", research_comparison_assumption="UNKNOWN", public_venue_profile="UNKNOWN",
                account_margin=UNKNOWN, account_fee_schedule=UNKNOWN,
                funding_treatment="UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT",
                promotion_enabled=False, promotion_reason="SEPARATE_NATIVE_LIFECYCLE_GATE_REQUIRED",
                warnings=["INVALID_SEALED_STAGEG_SOURCE"],
            )


class HlLiveStrategyReader:
    """Checked-in planned profile, separate from native account facts."""
    def __init__(self, runtime_root=None, projection_reader=None):
        self.root = runtime_root or Path(__file__).resolve().parents[2]
        self.projection_reader = projection_reader

    def strategy(self):
        fallback = dict(version="hl-stageg-strategy-v1", instance_id="hl-stageg-live", mode="live", environment="mainnet",
                        source_state="INVALID", running_state="NOT_CONFIRMED", strategy_id="UNKNOWN", candidate={},
                        hashes={key: UNKNOWN for key in HlStagegHashes.model_fields}, capital_assumption="Planned capital unavailable; observed account values remain separate",
                        research_comparison_assumption=UNKNOWN, public_venue_profile="Hyperliquid mainnet", account_margin=UNKNOWN,
                        account_fee_schedule=UNKNOWN, funding_treatment="NATIVE_ACCOUNT_SETTLEMENT", promotion_enabled=False,
                        promotion_reason="SEPARATE_NATIVE_LIFECYCLE_GATE_REQUIRED", warnings=["LIVE_PROFILE_UNAVAILABLE"])
        try:
            from coinmaster.ops.hl_live_profile import load_live_profile
            loaded = load_candidate(self.root / "configs/hl-live-v3-dp50.candidate.json")
            profile = load_live_profile(self.root, loaded.candidate)
            profile_hash = profile["profile_sha256"]
            candidate = {key: json.dumps(value, separators=(",", ":")) if isinstance(value, tuple) else str(value).lower() if isinstance(value, bool) else str(value) for key, value in asdict(loaded.candidate).items()}
            candidate.pop("btc_notional_multiplier", None)
            for key in ("deposit_protection_percent", "btc_long_notional_multiplier", "btc_short_notional_multiplier"):
                candidate[key] = str(profile[key])
            projection = self.projection_reader.runtime() if self.projection_reader else None
            matches = bool(projection and projection.projection_state == "READY" and projection.profile and projection.profile.get("profile_sha256") == profile_hash)
            fallback.update(source_state="SEALED_CONFIGURATION_CHECKED", running_state="RUNNING_MATCH" if matches else "NOT_CONFIRMED",
                            strategy_id="V3+DP50", candidate=candidate,
                            hashes={"candidate_sha256": loaded.sha256, "strategy_sha256": profile["strategy_sha256"], "execution_policy_sha256": UNKNOWN},
                            capital_assumption="Planned initial capital: " + profile["initial_capital_usdc"] + " USDC; this is not an observed account balance",
                            warnings=["EXACT_LIVE_ORDER_APPROVAL_REQUIRED"])
        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            pass
        return HlStagegStrategy.model_validate(fallback)


def create_runtime_app(database: str | None = None, token: str | None = None, worker_url: str | None = None, worker_token: str | None = None, control_database: str | None = None, hl_stageg_status_url: str | None = None, hl_stageg_control_token: str | None = None, runtime_root: Path | None = None, operator_username: str | None = None, operator_password_hash: str | None = None, session_database: str | None = None, public_origin: str | None = None) -> FastAPI:
    expected = token if token is not None else os.getenv("COINMASTER_RUNTIME_API_TOKEN")
    relay_token = worker_token if worker_token is not None else os.getenv("COINMASTER_PAPER_CONTROL_TOKEN")
    reader = RuntimeReader(database or os.getenv("COINMASTER_PAPER_DB", "/var/lib/coinmaster-paper/paper.sqlite"), worker_url or os.getenv("COINMASTER_PAPER_WORKER_URL", "http://127.0.0.1:18181"))
    hl_reader = HlStagegProjectionReader(hl_stageg_status_url or os.getenv("COINMASTER_HL_STAGEG_STATUS_URL", "http://127.0.0.1:18183"))
    hl_control = HlStagegControlRelay(hl_reader.url, hl_stageg_control_token if hl_stageg_control_token is not None else os.getenv("COINMASTER_HL_STAGEG_CONTROL_TOKEN"))
    hl_protection_control = HlStagegDepositProtectionRelay(hl_reader.url, hl_stageg_control_token if hl_stageg_control_token is not None else os.getenv("COINMASTER_HL_STAGEG_CONTROL_TOKEN"))
    hl_strategy_reader = HlStagegStrategyReader(runtime_root, hl_reader)
    hl_fill_reader = HlStagegFillReader(hl_reader.url, hl_stageg_control_token if hl_stageg_control_token is not None else os.getenv("COINMASTER_HL_STAGEG_CONTROL_TOKEN"))
    hl_equity_reader = HlNativeEquityReader(hl_reader.url, hl_stageg_control_token if hl_stageg_control_token is not None else os.getenv("COINMASTER_HL_STAGEG_CONTROL_TOKEN"))
    app = FastAPI(title="Coinmaster Paper Runtime API", version="1.0.0", docs_url=None, openapi_url=None)
    gui_auth = GuiAuth(
        username=operator_username if operator_username is not None else os.getenv("COINMASTER_GUI_USERNAME"),
        encoded_password=operator_password_hash if operator_password_hash is not None else os.getenv("COINMASTER_GUI_PASSWORD_HASH"),
        database=session_database or os.getenv("COINMASTER_GUI_SESSION_DB", "/var/lib/coinmaster-native-gui/auth.sqlite"),
        origin=public_origin if public_origin is not None else os.getenv("COINMASTER_GUI_ORIGIN"), bearer_token=expected,
    )
    def auth(request: Request, authorization: str | None = Header(default=None), x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token")) -> str:
        return gui_auth.authorize(request, authorization, x_csrf_token)

    @app.post("/internal/connections/verify-session", include_in_schema=False)
    def verify_connection_session(request: Request):
        """Narrow broker callback: verify a browser session, never a bearer token."""
        import hmac
        shared = os.getenv("COINMASTER_CONNECTION_VERIFY_TOKEN")
        supplied = request.headers.get("x-coinmaster-connection-verify-token", "")
        if not shared or not hmac.compare_digest(supplied, shared):
            raise HTTPException(403, "internal verifier unavailable")
        if not request.client or request.client.host not in ("127.0.0.1", "::1"):
            raise HTTPException(403, "loopback required")
        cookie = request.cookies.get(SESSION_COOKIE)
        if not gui_auth._session(cookie):
            raise HTTPException(401, "operator session required")
        intended = request.headers.get("x-coinmaster-original-method")
        if intended not in ("GET", "POST", "PUT", "DELETE"):
            raise HTTPException(403, "invalid original method")
        if intended != "GET" and (request.headers.get("origin") != gui_auth.origin or not cookie or not hmac.compare_digest(request.headers.get("x-csrf-token", ""), gui_auth.csrf(cookie))):
            raise HTTPException(403, "session write requires origin and CSRF token")
        return JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})

    @app.get("/login", include_in_schema=False)
    def login_page(request: Request):
        return gui_auth.login_page(request)

    @app.post("/login", include_in_schema=False)
    async def login(request: Request):
        return await gui_auth.login(request)

    @app.get("/api/v1/auth/session", include_in_schema=False)
    def gui_session(request: Request):
        cookie = request.cookies.get(SESSION_COOKIE)
        if not gui_auth._session(cookie):
            raise HTTPException(401, "operator session required")
        return JSONResponse({"username": gui_auth.username, "csrf_token": gui_auth.csrf(cookie)}, headers={"Cache-Control": "no-store"})

    @app.post("/api/v1/auth/logout", include_in_schema=False, dependencies=[Depends(auth)])
    def gui_logout(request: Request):
        cookie = request.cookies.get(SESSION_COOKIE)
        if not cookie:
            raise HTTPException(401, "operator session required")
        gui_auth.logout(cookie)
        response = JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})
        response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="strict")
        return response

    @app.get("/api/v1/openapi.json", include_in_schema=False, dependencies=[Depends(auth)])
    def openapi_document() -> JSONResponse:
        return JSONResponse(app.openapi())

    # The SPA has one loopback origin.  Reuse the control app's routes rather
    # than mirror its configuration, research, or immutable-run semantics.
    # The outer dependency also protects its otherwise informational health
    # endpoint, so every /api/v1 route uses the runtime operator token.
    control = create_control_app(
        database=control_database or os.getenv("COINMASTER_RUNTIME_CONTROL_DB", str(Path(__file__).resolve().parents[2] / "var/runtime-control.sqlite")),
        token=expected,
        include_legacy_runtime=False,
        # Legacy research runners require a separately qualified frozen profile.
        research_commands={},
        auth_dependency=auth,
    )
    app.include_router(control.router, dependencies=[Depends(auth)])

    @app.api_route("/api/v1/connections", methods=["GET", "POST"], include_in_schema=False, dependencies=[Depends(auth)])
    @app.api_route("/api/v1/connections/{path:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False, dependencies=[Depends(auth)])
    async def connection_broker(request: Request, path: str = ""):
        # Existing broker retains authorization and private credential ownership.
        if path and any(segment in ("", ".", "..") for segment in path.split("/")):
            raise HTTPException(404, "connection route not found")
        try:
            too_large = int(request.headers.get("content-length", "0")) > 16384
        except ValueError:
            raise HTTPException(400, "invalid request size") from None
        if too_large:
            raise HTTPException(413, "request too large")
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > 16384:
                raise HTTPException(413, "request too large")
            chunks.append(chunk)
        body = b"".join(chunks)
        headers = {key: request.headers[key] for key in ("cookie", "origin", "x-csrf-token", "content-type") if key in request.headers}
        headers["Host"] = "coinmaster24.com"
        url = "http://127.0.0.1:18184/api/v1/connections" + ("/" + urllib.parse.quote(path, safe="/") if path else "")
        probe = urllib.request.Request(url, data=body if request.method != "GET" else None, headers=headers, method=request.method)
        def fetch_broker():
            try:
                with urllib.request.urlopen(probe, timeout=5) as upstream:
                    return upstream.read(350001), upstream.status
            except urllib.error.HTTPError as error:
                return error.read(350001), error.code
            except (OSError, TimeoutError):
                raise HTTPException(503, "Account connection service unavailable") from None
        raw, code = await run_in_threadpool(fetch_broker)
        if len(raw) > 350000:
            raise HTTPException(503, "Account connection response unavailable")
        return Response(raw, status_code=code, media_type="application/json", headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/runtime", response_model=RuntimeState, dependencies=[Depends(auth)])
    def runtime() -> RuntimeState: return reader.runtime()
    @app.get("/api/v1/runtime/events", response_model=RuntimeEventsResponse, dependencies=[Depends(auth)])
    def events(cursor: int = Query(0, ge=0)) -> RuntimeEventsResponse: return reader.events(cursor)
    @app.get("/api/v1/instances/hl-stageg-testnet", response_model=HlStagegProjection, dependencies=[Depends(auth)])
    def hl_stageg_runtime() -> HlStagegProjection:
        return hl_reader.runtime()
    @app.get("/api/v1/instances/hl-stageg-testnet/fills", response_model=HlStagegFillHistory, dependencies=[Depends(auth)])
    def hl_stageg_fills(cursor: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)) -> HlStagegFillHistory:
        return hl_fill_reader.history(cursor, limit)
    @app.get("/api/v1/instances/hl-stageg-testnet/equity-changes", response_model=HlNativeEquityChanges, dependencies=[Depends(auth)])
    def hl_stageg_equity_changes() -> HlNativeEquityChanges:
        return hl_equity_reader.changes()
    @app.get("/api/v1/markets/hyperliquid/candles", response_model=HlPublicCandles, dependencies=[Depends(auth)])
    def hl_public_candles(
        coin: Literal["BTC", "SOL"], interval: Literal["1m", "5m", "15m", "1h", "4h", "1d"],
        limit: int = Query(200, ge=1, le=500),
    ) -> HlPublicCandles:
        return HlPublicCandles.model_validate(public_candles(coin, interval, limit))
    @app.get("/api/v1/instances/hl-stageg-testnet/strategy", response_model=HlStagegStrategy, dependencies=[Depends(auth)])
    def hl_stageg_strategy() -> HlStagegStrategy:
        return hl_strategy_reader.strategy()
    @app.get("/api/v1/instances/hl-stageg-testnet/controls", response_model=HlStagegControls, dependencies=[Depends(auth)])
    def hl_stageg_control_capabilities() -> HlStagegControls:
        return hl_stageg_controls(hl_reader.runtime(), control_transport_available=bool(hl_control.token))
    @app.post("/api/v1/instances/hl-stageg-testnet/controls/set-deposit-protection", response_model=HlStagegProtectionCommand, dependencies=[Depends(auth)])
    def set_hl_stageg_deposit_protection(body: HlStagegProtectionCommandRequest) -> HlStagegProtectionCommand:
        return hl_protection_control.command("set-deposit-protection", body.model_dump())
    @app.post("/api/v1/instances/hl-stageg-testnet/controls/reset-deposit-protection", response_model=HlStagegProtectionCommand, dependencies=[Depends(auth)])
    def reset_hl_stageg_deposit_protection(body: HlStagegProtectionResetRequest) -> HlStagegProtectionCommand:
        return hl_protection_control.command("reset-deposit-protection", body.model_dump())
    @app.post("/api/v1/instances/hl-stageg-testnet/controls/{command}", response_model=HlStagegControlCommand, dependencies=[Depends(auth)])
    def hl_stageg_control_command(command: Literal["pause-new-entries", "resume-new-entries"], idempotency_key: str = Header(alias="Idempotency-Key")) -> HlStagegControlCommand:
        if not idempotency_key:
            raise HTTPException(422, "Idempotency-Key is required")
        result = hl_control.command(command, idempotency_key)
        projection = hl_reader.runtime()
        if projection.projection_state != "READY" or projection.entry_control.state != result.entry_control:
            raise HTTPException(503, "Stage-G entry control read-back mismatch")
        return result
    live_reader = HlLiveProjectionReader("http://127.0.0.1:18185")
    live_token = os.getenv("COINMASTER_HL_LIVE_CONTROL_TOKEN")
    live_fills = HlStagegFillReader(live_reader.url, live_token, "hl-stageg-live")
    live_equity = HlNativeEquityReader(live_reader.url, live_token, "hl-stageg-live")
    live_entry_control = HlStagegControlRelay(live_reader.url, live_token, "hl-stageg-live")
    live_protection_control = HlStagegDepositProtectionRelay(live_reader.url, live_token, "hl-stageg-live")

    @app.get("/api/v1/instances/hl-stageg-live", response_model=HlStagegProjection, dependencies=[Depends(auth)])
    def live_runtime():
        return live_reader.runtime()

    @app.get("/api/v1/instances/hl-stageg-live/strategy", response_model=HlStagegStrategy, dependencies=[Depends(auth)])
    def live_strategy():
        return HlLiveStrategyReader(runtime_root, live_reader).strategy()

    @app.get("/api/v1/instances/hl-stageg-live/controls", response_model=HlStagegControls, dependencies=[Depends(auth)])
    def live_controls():
        return hl_stageg_controls(live_reader.runtime(), bool(live_token))

    @app.get("/api/v1/instances/hl-stageg-live/fills", response_model=HlStagegFillHistory, dependencies=[Depends(auth)])
    def live_fill_history(cursor: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)):
        return live_fills.history(cursor, limit)

    @app.get("/api/v1/instances/hl-stageg-live/equity-changes", response_model=HlNativeEquityChanges, dependencies=[Depends(auth)])
    def live_equity_changes():
        return live_equity.changes()

    def require_live_controls():
        if not Path("/etc/coinmaster/live-order-approval.json").is_file():
            raise HTTPException(403, "Exact release, account and profile approval is required before Live controls can be enabled.")
        projection = live_reader.runtime()
        if not projection.real_order_approval or not live_order_approval_matches(projection):
            raise HTTPException(403, "Exact release, account and profile approval is required before Live controls can be enabled.")
        if not hl_stageg_controls(projection, bool(live_token)).pause.enabled:
            raise HTTPException(503, "Live native controls are unavailable. Refresh current account state.")
        return projection

    def require_live_readback(before):
        fresh = require_live_controls()
        if (fresh.run_epoch != before.run_epoch or fresh.runtime_release_commit != before.runtime_release_commit
                or fresh.runtime_master_address_sha256 != before.runtime_master_address_sha256):
            raise HTTPException(503, "Live control read-back identity mismatch")
        return fresh

    @app.post("/api/v1/instances/hl-stageg-live/controls/set-deposit-protection", response_model=HlStagegProtectionCommand, dependencies=[Depends(auth)])
    def live_set_protection(body: HlStagegProtectionCommandRequest):
        before = require_live_controls()
        result = live_protection_control.command("set-deposit-protection", body.model_dump())
        require_live_readback(before)
        return result

    @app.post("/api/v1/instances/hl-stageg-live/controls/reset-deposit-protection", response_model=HlStagegProtectionCommand, dependencies=[Depends(auth)])
    def live_reset_protection(body: HlStagegProtectionResetRequest):
        before = require_live_controls()
        result = live_protection_control.command("reset-deposit-protection", body.model_dump())
        require_live_readback(before)
        return result

    @app.post("/api/v1/instances/hl-stageg-live/controls/{command}", response_model=HlStagegControlCommand, dependencies=[Depends(auth)])
    def live_control(command: Literal["pause-new-entries", "resume-new-entries"], idempotency_key: str = Header(alias="Idempotency-Key")):
        before = require_live_controls()
        if not idempotency_key:
            raise HTTPException(422, "Idempotency-Key is required")
        result = live_entry_control.command(command, idempotency_key)
        fresh = require_live_readback(before)
        if fresh.entry_control.state != result.entry_control:
            raise HTTPException(503, "Live entry control read-back mismatch")
        return result

    if relay_token:
        @app.post("/api/v1/runtime/commands/{command}", response_model=RuntimeCommandResponse, dependencies=[Depends(auth)])
        def command(command: Literal["pause-new-entries", "resume-new-entries", "flatten-paper"], idempotency_key: str = Header(alias="Idempotency-Key")) -> RuntimeCommandResponse:
            if not idempotency_key: raise HTTPException(422, "Idempotency-Key is required")
            return reader.command(command, idempotency_key, relay_token)
    dist = Path(os.getenv("COINMASTER_RUNTIME_DIST", Path(__file__).resolve().parents[3] / "coinmaster/dist"))
    if dist.is_dir():
        asset_root = (dist / "assets").resolve()
        @app.get("/assets/{path:path}", include_in_schema=False, dependencies=[Depends(auth)])
        def assets(path: str):
            target = (asset_root / path).resolve()
            if not target.is_relative_to(asset_root) or not target.is_file():
                raise HTTPException(404, "asset not found")
            return FileResponse(target)

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str, request: Request, authorization: str | None = Header(default=None)):
            if path == "api" or path.startswith("api/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            try:
                auth(request, authorization, None)
            except HTTPException as error:
                if error.status_code != 401:
                    raise
                return RedirectResponse("/login", status_code=303)
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-store"})
    return app


app = create_runtime_app()
