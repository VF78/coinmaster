"""Loopback-only P5 runtime projection; it never imports Nautilus execution."""
from __future__ import annotations

import json
import os
import sqlite3
import urllib.request
import time
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from coinmaster.api.app import create_app as create_control_app
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


class HlStagegAccount(RuntimeSchema):
    native_cash: str = UNKNOWN
    equity: str = UNKNOWN
    im: str = UNKNOWN
    mm: str = UNKNOWN
    free_margin: str = UNKNOWN


class HlStagegEvent(RuntimeSchema):
    cursor: int
    event_id: str
    kind: str
    provenance: Literal["SANDBOX"] = "SANDBOX"


class HlStagegPosition(RuntimeSchema):
    instrument_id: str
    signed_quantity: str
    provenance: Literal["SANDBOX"] = "SANDBOX"


class HlStagegOrder(RuntimeSchema):
    client_order_id: str
    instrument_id: str | None = None
    provenance: Literal["SANDBOX"] = "SANDBOX"


class HlStagegProjection(RuntimeSchema):
    version: Literal["hl-stageg-projection-v1"]
    instance_id: Literal["hl-stageg-testnet"]
    projection_state: Literal["READY", "STALE", "UNAVAILABLE", "INVALID"]
    observed_at_ns: int | None = None
    mode: Literal["sandbox"]
    environment: Literal["mainnet-public"]
    live_order_capability: Literal[False] = False
    process_state: str
    reconciliation: str
    hashes: HlStagegHashes
    warmup: HlStagegWarmup
    gates: dict[str, str | bool]
    account: HlStagegAccount
    funding_state: str
    feeds: dict[str, RuntimeFeed]
    positions: list[HlStagegPosition]
    orders: list[HlStagegOrder]
    events: list[HlStagegEvent]
    event_cursor: int
    provenance: Literal["SANDBOX_LOCAL_READ_ONLY_WORKER_PROJECTION"]
    warnings: list[str]


# This is intentionally a source-identity document, not another runtime
# projection. It lets the Strategy page describe exactly what is sealed for
# the isolated Sandbox worker without suggesting account facts or a mutable
# control channel exist.
class HlStagegStrategy(RuntimeSchema):
    version: Literal["hl-stageg-strategy-v1"]
    instance_id: Literal["hl-stageg-testnet"]
    source_state: Literal["SEALED_SOURCE_CHECKED", "INVALID"]
    strategy_id: str
    mode: Literal["sandbox"]
    environment: Literal["mainnet-public"]
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
            "warmup": {"state": UNKNOWN}, "gates": {}, "account": {},
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
            if projection.projection_state != "READY" or projection.live_order_capability is not False:
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


class HlStagegStrategyReader:
    """Load and verify only the checked-in identity of the sealed candidate."""

    def __init__(self, runtime_root: Path | None = None) -> None:
        self.runtime_root = runtime_root or Path(__file__).resolve().parents[2]

    def strategy(self) -> HlStagegStrategy:
        unknown_hashes = {"candidate_sha256": UNKNOWN, "strategy_sha256": UNKNOWN, "execution_policy_sha256": UNKNOWN}
        try:
            configs = self.runtime_root / "configs"
            approval = json.loads((configs / "stage-g-hl-sandbox-approval.json").read_text(encoding="utf-8"))
            instance = load_testnet_instance_config(configs / "hl-stageg-testnet.instance.json")
            loaded = load_candidate(configs / "stage-g-v1.json")
            strategy_hash = sha256((self.runtime_root / "coinmaster/strategy/wave_overlay.py").read_bytes()).hexdigest()
            hashes = {
                "candidate_sha256": loaded.sha256,
                "strategy_sha256": strategy_hash,
                "execution_policy_sha256": str(approval.get("execution_policy_sha256", UNKNOWN)),
            }
            if (
                approval.get("schema") != "coinmaster-stageg-hl-sandbox-approval-v1"
                or approval.get("candidate_sha256") != loaded.sha256
                or approval.get("strategy_sha256") != strategy_hash
            ):
                raise ValueError("SEALED_APPROVAL_MISMATCH")
            candidate = {
                key: json.dumps(value, separators=(",", ":")) if isinstance(value, tuple) else str(value).lower() if isinstance(value, bool) else str(value)
                for key, value in asdict(loaded.candidate).items()
            }
            return HlStagegStrategy(
                version="hl-stageg-strategy-v1", instance_id="hl-stageg-testnet", source_state="SEALED_SOURCE_CHECKED",
                strategy_id=instance.strategy_id, mode="sandbox", environment="mainnet-public", candidate=candidate, hashes=hashes,
                capital_assumption="10,000 USDC nominal Sandbox seed; not an observed account balance",
                research_comparison_assumption="10,000 USDT comparison only under an explicit 1:1 assumption",
                public_venue_profile="Current public Hyperliquid mainnet tiers and Sandbox leverage policy; account-specific tier is not claimed",
                account_margin=UNKNOWN, account_fee_schedule=UNKNOWN,
                funding_treatment="OBSERVED_MODELLED_UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT",
                promotion_enabled=False, promotion_reason="SEPARATE_NATIVE_LIFECYCLE_GATE_REQUIRED",
                warnings=["ACCOUNT_SPECIFIC_MARGIN_UNKNOWN", "ACCOUNT_SPECIFIC_FEES_UNKNOWN", "NO_RUNNING_INSTANCE_MUTATION"],
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return HlStagegStrategy(
                version="hl-stageg-strategy-v1", instance_id="hl-stageg-testnet", source_state="INVALID",
                strategy_id=UNKNOWN, mode="sandbox", environment="mainnet-public", candidate={}, hashes=unknown_hashes,
                capital_assumption="UNKNOWN", research_comparison_assumption="UNKNOWN", public_venue_profile="UNKNOWN",
                account_margin=UNKNOWN, account_fee_schedule=UNKNOWN,
                funding_treatment="UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT",
                promotion_enabled=False, promotion_reason="SEPARATE_NATIVE_LIFECYCLE_GATE_REQUIRED",
                warnings=["INVALID_SEALED_STAGEG_SOURCE"],
            )


def create_runtime_app(database: str | None = None, token: str | None = None, worker_url: str | None = None, worker_token: str | None = None, control_database: str | None = None, hl_stageg_status_url: str | None = None, runtime_root: Path | None = None) -> FastAPI:
    expected = token if token is not None else os.getenv("COINMASTER_RUNTIME_API_TOKEN")
    relay_token = worker_token if worker_token is not None else os.getenv("COINMASTER_PAPER_CONTROL_TOKEN")
    reader = RuntimeReader(database or os.getenv("COINMASTER_PAPER_DB", "/var/lib/coinmaster-paper/paper.sqlite"), worker_url or os.getenv("COINMASTER_PAPER_WORKER_URL", "http://127.0.0.1:18181"))
    hl_reader = HlStagegProjectionReader(hl_stageg_status_url or os.getenv("COINMASTER_HL_STAGEG_STATUS_URL", "http://127.0.0.1:18183"))
    hl_strategy_reader = HlStagegStrategyReader(runtime_root)
    app = FastAPI(title="Coinmaster Paper Runtime API", version="1.0.0", docs_url=None, openapi_url=None)
    def auth(authorization: str | None = Header(default=None)) -> None:
        if not expected or authorization != f"Bearer {expected}": raise HTTPException(401, "runtime token required")

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
    )
    app.include_router(control.router, dependencies=[Depends(auth)])

    @app.get("/api/v1/runtime", response_model=RuntimeState, dependencies=[Depends(auth)])
    def runtime() -> RuntimeState: return reader.runtime()
    @app.get("/api/v1/runtime/events", response_model=RuntimeEventsResponse, dependencies=[Depends(auth)])
    def events(cursor: int = Query(0, ge=0)) -> RuntimeEventsResponse: return reader.events(cursor)
    @app.get("/api/v1/instances/hl-stageg-testnet", response_model=HlStagegProjection, dependencies=[Depends(auth)])
    def hl_stageg_runtime() -> HlStagegProjection:
        return hl_reader.runtime()
    @app.get("/api/v1/instances/hl-stageg-testnet/strategy", response_model=HlStagegStrategy, dependencies=[Depends(auth)])
    def hl_stageg_strategy() -> HlStagegStrategy:
        return hl_strategy_reader.strategy()
    @app.post("/api/v1/runtime/commands/{command}", response_model=RuntimeCommandResponse, dependencies=[Depends(auth)])
    def command(command: Literal["pause-new-entries", "resume-new-entries", "flatten-paper"], idempotency_key: str = Header(alias="Idempotency-Key")) -> RuntimeCommandResponse:
        if not idempotency_key: raise HTTPException(422, "Idempotency-Key is required")
        if not relay_token: raise HTTPException(503, "paper worker command channel unavailable")
        return reader.command(command, idempotency_key, relay_token)
    dist = Path(os.getenv("COINMASTER_RUNTIME_DIST", Path(__file__).resolve().parents[3] / "coinmaster/dist"))
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            target = dist / path
            return FileResponse(target if path and target.is_file() else dist / "index.html")
    return app


app = create_runtime_app()
