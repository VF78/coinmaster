"""Loopback-only P5 runtime projection; it never imports Nautilus execution."""
from __future__ import annotations

import json
import os
import sqlite3
import urllib.request
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from coinmaster.api.app import create_app as create_control_app


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


def create_runtime_app(database: str | None = None, token: str | None = None, worker_url: str | None = None, worker_token: str | None = None, control_database: str | None = None) -> FastAPI:
    expected = token if token is not None else os.getenv("COINMASTER_RUNTIME_API_TOKEN")
    relay_token = worker_token if worker_token is not None else os.getenv("COINMASTER_PAPER_CONTROL_TOKEN")
    reader = RuntimeReader(database or os.getenv("COINMASTER_PAPER_DB", "/var/lib/coinmaster-paper/paper.sqlite"), worker_url or os.getenv("COINMASTER_PAPER_WORKER_URL", "http://127.0.0.1:18181"))
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
