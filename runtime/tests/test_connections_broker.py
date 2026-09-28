"""Focused credential-broker invariants with sentinel secrets only."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit

from coinmaster.api.connections_broker import create_connections_app

COOKIE = "__Host-cm-session=" + "a" * 64
ORIGIN = "https://coinmaster24.com"
CSRF = "b" * 64


def call(app, method, path, body=None, headers=None):
    parsed = urlsplit(path)
    values = {"Host": "coinmaster24.com", **(headers or {})}
    if body is not None:
        values["Content-Type"] = "application/json"
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "scheme": "https", "method": method, "path": parsed.path,
        "raw_path": parsed.path.encode(), "query_string": parsed.query.encode(),
        "headers": [(k.lower().encode(), v.encode()) for k, v in values.items()],
        "server": ("coinmaster24.com", 443), "client": ("127.0.0.1", 12345), "root_path": "",
    }
    sent = []

    async def exchange():
        received = False

        async def receive():
            nonlocal received
            if not received:
                received = True
                return {"type": "http.request", "body": json.dumps(body).encode() if body is not None else b"", "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        await app(scope, receive, send)

    asyncio.run(exchange())
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    payload = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, payload


def auth_headers():
    return {"Cookie": COOKIE, "Origin": ORIGIN, "X-CSRF-Token": CSRF}


def test_multiple_connections_no_secret_echo_and_display_selection(tmp_path):
    def verifier(request):
        return 200 if request.cookies.get("__Host-cm-session") == "a" * 64 and (
            request.method == "GET" or (
                request.headers.get("origin") == ORIGIN and request.headers.get("x-csrf-token") == CSRF
            )
        ) else 403
    root = str(tmp_path / "broker")
    app = create_connections_app(store_root=root, verifier=verifier)
    assert call(app, "GET", "/api/v1/connections")[0] == 401
    assert call(app, "GET", "/api/v1/connections", headers={"Authorization": "Bearer machine-token"})[0] == 401
    assert call(app, "POST", "/api/v1/connections", {"venue": "bybit", "api_key": "SENTINEL_KEY_ONE", "api_secret": "SENTINEL_SECRET_ONE"}, headers={"Cookie": COOKIE})[0] == 403
    assert call(app, "POST", "/api/v1/connections", {"venue": "bybit", "api_key": "SENTINEL_KEY_ONE", "api_secret": "SENTINEL_SECRET_ONE"}, headers={**auth_headers(), "X-CSRF-Token": "wrong"})[0] == 403
    status, raw = call(app, "POST", "/api/v1/connections", {"venue": "bybit", "api_key": "SENTINEL_KEY_ONE", "api_secret": "SENTINEL_SECRET_ONE"}, headers=auth_headers())
    assert status == 201
    assert b"SENTINEL" not in raw
    one = json.loads(raw)
    status, raw = call(app, "POST", "/api/v1/connections", {"venue": "bybit", "api_key": "SENTINEL_KEY_TWO", "api_secret": "SENTINEL_SECRET_TWO"}, headers=auth_headers())
    assert status == 201
    two = json.loads(raw)
    assert one["id"] != two["id"]
    status, raw = call(app, "PUT", "/api/v1/connections/display", {"connection_id": two["id"]}, headers=auth_headers())
    assert status == 200 and json.loads(raw)["display_connection_id"] == two["id"]
    restarted = create_connections_app(store_root=root, verifier=verifier)
    status, raw = call(restarted, "GET", "/api/v1/connections", headers=auth_headers())
    collection = json.loads(raw)
    assert status == 200 and len(collection["connections"]) == 2
    assert collection["display_connection_id"] == two["id"] and b"SENTINEL" not in raw
    assert (Path(root) / (one["id"] + ".json")).stat().st_mode & 0o077 == 0
    assert call(restarted, "DELETE", "/api/v1/connections/" + two["id"], headers=auth_headers())[0] == 204
    assert json.loads(call(restarted, "GET", "/api/v1/connections", headers=auth_headers())[1])["display_connection_id"] is None
    assert call(restarted, "POST", "/api/v1/connections/" + two["id"] + "/test", headers=auth_headers())[0] == 404
    assert call(restarted, "POST", "/api/v1/connections/not-an-id/test", headers=auth_headers())[0] == 404


def test_hyperliquid_public_state_is_not_agent_authorization(tmp_path, monkeypatch):
    app = create_connections_app(store_root=str(tmp_path / "broker"), verifier=lambda _: 200)
    address = "0x" + "1" * 40
    status, raw = call(app, "POST", "/api/v1/connections", {"venue": "hyperliquid", "master_address": address, "agent_private_key": "0x" + "2" * 64}, headers=auth_headers())
    assert status == 201 and b"222222" not in raw
    item = json.loads(raw)
    assert item["verification_state"] == {"public_observation": "UNTESTED", "agent_authorization": "UNVERIFIED"}

    def fake_read_url(request):
        assert request.full_url == "https://api.hyperliquid.xyz/info"
        assert json.loads(request.data) == {"type": "clearinghouseState", "user": address}
        return {"assetPositions": []}

    monkeypatch.setattr("coinmaster.api.connections_broker._read_url", fake_read_url)
    status, raw = call(app, "POST", "/api/v1/connections/" + item["id"] + "/test", headers=auth_headers())
    assert status == 200
    assert json.loads(raw)["verification_state"] == {"public_observation": "REACHABLE", "agent_authorization": "UNVERIFIED"}


def test_bybit_queries_key_metadata_only_and_requires_read_only(tmp_path, monkeypatch):
    app = create_connections_app(store_root=str(tmp_path / "broker"), verifier=lambda _: 200)
    status, raw = call(app, "POST", "/api/v1/connections", {"venue": "bybit", "api_key": "SENTINEL_KEY", "api_secret": "SENTINEL_SECRET"}, headers=auth_headers())
    item = json.loads(raw)
    assert status == 201
    called = []

    def fake_read_url(request):
        called.append(request)
        return {"retCode": 0, "result": {"apiKey": "SENTINEL_KEY", "secret": "", "readOnly": 0}}

    monkeypatch.setattr("coinmaster.api.connections_broker._read_url", fake_read_url)
    status, raw = call(app, "POST", "/api/v1/connections/" + item["id"] + "/test", headers=auth_headers())
    assert status == 200 and json.loads(raw)["verification_state"] == {"read_only_access": "ERROR"}
    assert b"SENTINEL" not in raw
    assert len(called) == 1 and called[0].get_method() == "GET"
    assert called[0].full_url == "https://api.bybit.com/v5/user/query-api"
    assert "X-bapi-sign" in called[0].headers
    monkeypatch.setattr("coinmaster.api.connections_broker._read_url", lambda _: {"retCode": 0, "result": {"apiKey": "SENTINEL_KEY", "readOnly": 1}})
    status, raw = call(app, "POST", "/api/v1/connections/" + item["id"] + "/test", headers=auth_headers())
    assert status == 200 and json.loads(raw)["verification_state"] == {"read_only_access": "VERIFIED"}
    assert b"SENTINEL" not in raw


def test_internal_verifier_requires_real_session_origin_and_csrf(tmp_path, monkeypatch):
    import hashlib
    import time
    from coinmaster.api.gui_auth import GuiAuth, password_hash
    from coinmaster.api.runtime_sidecar import create_runtime_app

    monkeypatch.setenv("COINMASTER_CONNECTION_VERIFY_TOKEN", "isolated-verifier-token")
    verifier_db = str(tmp_path / "auth.sqlite")
    encoded = password_hash("test password", salt=b"fixed-salt-for-test-0123456789abc")
    auth = GuiAuth(username="operator", encoded_password=encoded, database=verifier_db,
                   origin=ORIGIN, bearer_token="machine-token")
    token = "a" * 64
    digest = hashlib.sha256(bytes.fromhex(token)).hexdigest()
    now = int(time.time())
    with auth._connect() as db:
        db.execute("INSERT INTO gui_sessions(token_hash,credential_fingerprint,created_at,touched_at,revoked_at) VALUES(?,?,?,?,NULL)",
                   (digest, auth.credential_fingerprint, now, now))
    app = create_runtime_app(database=str(tmp_path / "paper.sqlite"), control_database=str(tmp_path / "control.sqlite"),
                             token="machine-token", worker_token="", worker_url="http://127.0.0.1:9",
                             operator_username="operator", operator_password_hash=encoded,
                             session_database=verifier_db, public_origin=ORIGIN)
    route = "/internal/connections/verify-session"
    internal = {"X-Coinmaster-Connection-Verify-Token": "isolated-verifier-token",
                "X-Coinmaster-Original-Method": "POST"}
    assert call(app, "POST", route, headers={**internal, "Authorization": "Bearer machine-token"})[0] == 401
    assert call(app, "POST", route, headers={**internal, "Cookie": COOKIE})[0] == 403
    assert call(app, "POST", route, headers={**internal, "Cookie": COOKIE, "Origin": ORIGIN, "X-CSRF-Token": "wrong"})[0] == 403
    assert call(app, "POST", route, headers={**internal, "Cookie": COOKIE, "Origin": ORIGIN, "X-CSRF-Token": auth.csrf(token)})[0] == 200
    assert call(app, "POST", route, headers={"Cookie": COOKIE, "Origin": ORIGIN, "X-CSRF-Token": auth.csrf(token),
                                              "X-Coinmaster-Original-Method": "POST"})[0] == 403
