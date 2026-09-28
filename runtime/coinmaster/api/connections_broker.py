"""Isolated display-only account connection broker. No order or generic signing API."""
from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from coinmaster.api.gui_auth import SESSION_COOKIE

ORIGIN = "https://coinmaster24.com"
ID_RE = re.compile(r"^[0-9a-f]{32}$")
ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
KEY_RE = re.compile(r"^(0x)?[0-9a-fA-F]{64}$")
MAX_BODY = 16_384


class ConnectionStore:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.root.is_symlink() or self.root.stat().st_mode & 0o077:
            raise RuntimeError("connection store must be private")
        self.lock_path = self.root / ".lock"

    @contextmanager
    def locked(self):
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _write(self, name: str, data: dict):
        fd, temp = tempfile.mkstemp(prefix=".pending-", dir=self.root)
        try:
            with os.fdopen(fd, "w") as file:
                os.fchmod(file.fileno(), 0o600)
                json.dump(data, file, separators=(",", ":"))
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, self.root / name)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def save(self, item: dict):
        self._write(item["id"] + ".json", item)

    def get(self, connection_id: str) -> dict:
        if not ID_RE.fullmatch(connection_id):
            raise HTTPException(404, "connection not found")
        path = self.root / (connection_id + ".json")
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd) as file:
                return json.load(file)
        except (FileNotFoundError, ValueError, OSError):
            raise HTTPException(404, "connection not found") from None

    def all(self) -> list[dict]:
        result = []
        for path in sorted(self.root.glob("*.json")):
            if ID_RE.fullmatch(path.stem):
                result.append(self.get(path.stem))
        return result

    def selection(self) -> str | None:
        try:
            fd = os.open(self.root / "display", os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd) as file:
                selected = file.read(32)
            return selected if ID_RE.fullmatch(selected) else None
        except FileNotFoundError:
            return None

    def select(self, connection_id: str | None):
        if connection_id is None:
            (self.root / "display").unlink(missing_ok=True)
        else:
            fd, temp = tempfile.mkstemp(prefix=".pending-", dir=self.root)
            try:
                with os.fdopen(fd, "w") as file:
                    file.write(connection_id)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temp, self.root / "display")
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)


def public_item(item: dict) -> dict:
    return {key: item[key] for key in ("id", "venue", "account_label", "last_tested_at", "verification_state")}


async def _bounded_body(request: Request) -> bytes:
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BODY:
            raise HTTPException(413, "request too large")
        chunks.append(chunk)
    return b"".join(chunks)


def _json_object(body: bytes) -> dict:
    if len(body) > MAX_BODY:
        raise HTTPException(413, "request too large")
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError):
        raise HTTPException(400, "invalid JSON") from None
    if not isinstance(value, dict):
        raise HTTPException(400, "JSON object required")
    return value


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _read_url(request: urllib.request.Request) -> dict:
    try:
        with urllib.request.build_opener(_RejectRedirects).open(request, timeout=5) as response:
            raw = response.read(65_537)
        if len(raw) > 65_536:
            raise ValueError("large response")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("invalid response")
        return parsed
    except (urllib.error.URLError, ValueError, TimeoutError, OSError):
        raise ValueError("venue unavailable") from None


def _test_hyperliquid(item: dict) -> dict:
    address = item["master_address"]
    request = urllib.request.Request(
        "https://api.hyperliquid.xyz/info",
        data=json.dumps({"type": "clearinghouseState", "user": address}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "CoinMaster-read-only-connection/1"},
        method="POST",
    )
    try:
        response = _read_url(request)
        if not isinstance(response.get("assetPositions"), list):
            raise ValueError("invalid observation")
        observed = "REACHABLE"
    except ValueError:
        observed = "ERROR"
    return {
        "public_observation": observed,
        "agent_authorization": "UNVERIFIED" if item.get("agent_private_key") else "NOT_PROVIDED",
    }


def _test_bybit(item: dict) -> dict:
    timestamp = str(int(time.time() * 1000))
    key = item["api_key"]
    secret = item["api_secret"]
    recv_window = "5000"
    signature = hmac.new(secret.encode(), (timestamp + key + recv_window).encode(), hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        "https://api.bybit.com/v5/user/query-api",
        headers={
            "X-BAPI-API-KEY": key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "X-BAPI-SIGN": signature,
            "User-Agent": "CoinMaster-read-only-connection/1",
        },
        method="GET",
    )
    try:
        response = _read_url(request)
        result = response.get("result")
        if response.get("retCode") != 0 or not isinstance(result, dict) or type(result.get("readOnly")) is not int or result["readOnly"] != 1:
            raise ValueError("key is invalid or not read-only")
        return {"read_only_access": "VERIFIED"}
    except ValueError:
        return {"read_only_access": "ERROR"}


def _make_item(body: dict) -> dict:
    venue = body.get("venue")
    connection_id = secrets.token_hex(16)
    base = {"id": connection_id, "venue": venue, "last_tested_at": None}
    if venue == "hyperliquid":
        if set(body) - {"venue", "master_address", "agent_private_key"}:
            raise HTTPException(400, "unsupported fields")
        address = body.get("master_address")
        agent = body.get("agent_private_key")
        if not isinstance(address, str) or not ADDRESS_RE.fullmatch(address):
            raise HTTPException(400, "invalid master address")
        if agent is not None and (not isinstance(agent, str) or not KEY_RE.fullmatch(agent)):
            raise HTTPException(400, "invalid agent key")
        base.update(master_address=address, account_label="Hyperliquid " + address[:6] + "…" + address[-4:],
                    agent_private_key=agent,
                    verification_state={"public_observation": "UNTESTED",
                                        "agent_authorization": "UNVERIFIED" if agent else "NOT_PROVIDED"})
    elif venue == "bybit":
        if set(body) != {"venue", "api_key", "api_secret"}:
            raise HTTPException(400, "api_key and api_secret required")
        key, secret = body["api_key"], body["api_secret"]
        if not isinstance(key, str) or not isinstance(secret, str) or not (8 <= len(key) <= 128) or not (8 <= len(secret) <= 128) or any(ord(c) < 33 or ord(c) > 126 for c in key + secret):
            raise HTTPException(400, "invalid Bybit credentials")
        base.update(api_key=key, api_secret=secret, account_label="Bybit account",
                    verification_state={"read_only_access": "UNTESTED"})
    else:
        raise HTTPException(400, "unsupported venue")
    return base


def create_connections_app(*, store_root: str | None = None, verify_token: str | None = None,
                           verifier_url: str | None = None, verifier=None) -> FastAPI:
    store = ConnectionStore(store_root or os.getenv("COINMASTER_CONNECTION_STORE", "/var/lib/coinmaster-connections"))
    token = verify_token if verify_token is not None else os.getenv("COINMASTER_CONNECTION_VERIFY_TOKEN", "")
    verify_url = verifier_url or "http://127.0.0.1:18182/internal/connections/verify-session"
    app = FastAPI(title="CoinMaster connection broker", docs_url=None, redoc_url=None, openapi_url=None)

    def authorize(request: Request):
        if request.headers.get("host") != "coinmaster24.com":
            raise HTTPException(403, "invalid host")
        cookie = request.cookies.get(SESSION_COOKIE)
        if not cookie or len(cookie) != 64 or not re.fullmatch(r"[0-9a-fA-F]{64}", cookie):
            raise HTTPException(401, "operator session required")
        if request.method != "GET" and (request.headers.get("origin") != ORIGIN or not request.headers.get("x-csrf-token")):
            raise HTTPException(403, "session write requires origin and CSRF token")
        if verifier is not None:
            status = verifier(request)
        else:
            if not token:
                raise HTTPException(503, "session verifier unavailable")
            headers = {
                "Cookie": SESSION_COOKIE + "=" + cookie,
                "X-Coinmaster-Connection-Verify-Token": token,
                "X-Coinmaster-Original-Method": request.method,
            }
            if request.method != "GET":
                headers["Origin"] = request.headers["origin"]
                headers["X-CSRF-Token"] = request.headers["x-csrf-token"]
            probe = urllib.request.Request(verify_url, data=b"", headers=headers, method="POST")
            try:
                with urllib.request.urlopen(probe, timeout=2) as response:
                    status = response.status
            except urllib.error.HTTPError as error:
                status = error.code
            except (urllib.error.URLError, TimeoutError, OSError):
                raise HTTPException(503, "session verifier unavailable") from None
        if status != 200:
            raise HTTPException(status if status in (401, 403) else 503, "operator session required")

    @app.middleware("http")
    async def no_cache(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/api/v1/connections")
    def list_connections(request: Request):
        authorize(request)
        with store.locked():
            return {"connections": [public_item(item) for item in store.all()],
                    "display_connection_id": store.selection()}

    @app.post("/api/v1/connections", status_code=201)
    async def add_connection(request: Request):
        authorize(request)
        if request.headers.get("content-type", "").split(";")[0].lower() != "application/json":
            raise HTTPException(415, "JSON required")
        item = _make_item(_json_object(await _bounded_body(request)))
        with store.locked():
            store.save(item)
        return public_item(item)

    @app.post("/api/v1/connections/{connection_id}/test")
    def test_connection(connection_id: str, request: Request):
        authorize(request)
        with store.locked():
            item = store.get(connection_id)
            item["verification_state"] = _test_hyperliquid(item) if item["venue"] == "hyperliquid" else _test_bybit(item)
            item["last_tested_at"] = datetime.now(timezone.utc).isoformat()
            store.save(item)
            return public_item(item)

    @app.delete("/api/v1/connections/{connection_id}", status_code=204)
    def remove_connection(connection_id: str, request: Request):
        authorize(request)
        with store.locked():
            store.get(connection_id)
            (store.root / (connection_id + ".json")).unlink()
            if store.selection() == connection_id:
                store.select(None)
        return Response(status_code=204)

    @app.put("/api/v1/connections/display")
    async def display_connection(request: Request):
        authorize(request)
        if request.headers.get("content-type", "").split(";")[0].lower() != "application/json":
            raise HTTPException(415, "JSON required")
        body = _json_object(await _bounded_body(request))
        if set(body) != {"connection_id"}:
            raise HTTPException(400, "connection_id required")
        connection_id = body["connection_id"]
        if connection_id is not None and (not isinstance(connection_id, str) or not ID_RE.fullmatch(connection_id)):
            raise HTTPException(400, "invalid connection_id")
        with store.locked():
            if connection_id is not None:
                store.get(connection_id)
            store.select(connection_id)
            return {"display_connection_id": store.selection()}

    return app
