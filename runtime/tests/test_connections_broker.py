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
    assert one["account_label"] != two["account_label"]
    assert "SENTINEL" not in one["account_label"] + two["account_label"]
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
        payload = json.loads(request.data)
        if payload == {"type": "clearinghouseState", "user": address}:
            return {"assetPositions": []}
        assert payload["type"] == "userRole"
        assert payload["user"] == "0x1563915e194d8cfba1943570603f7606a3115508"
        return {"role": "agent", "data": {"user": address}}

    monkeypatch.setattr("coinmaster.api.connections_broker._read_url", fake_read_url)
    status, raw = call(app, "POST", "/api/v1/connections/" + item["id"] + "/test", headers=auth_headers())
    assert status == 200
    assert json.loads(raw)["verification_state"] == {"public_observation": "REACHABLE", "agent_authorization": "VERIFIED"}


def test_saved_hyperliquid_agent_key_update_verifies_role_and_persists_safely(tmp_path, monkeypatch):
    import os
    from nautilus_trader.core.nautilus_pyo3 import hyperliquid_resolve_execution_account_address

    root = tmp_path / "broker"
    master = "0x" + "1" * 40
    key = "0x" + "2" * 64
    agent = hyperliquid_resolve_execution_account_address(private_key=key)
    app = create_connections_app(store_root=str(root), verifier=lambda request: 200 if request.headers.get("x-csrf-token") == CSRF else 403)
    status, raw = call(app, "POST", "/api/v1/connections", {"venue": "hyperliquid", "master_address": master}, headers=auth_headers())
    assert status == 201
    connection_id = json.loads(raw)["id"]
    route = "/api/v1/connections/" + connection_id + "/agent-key"
    body = {"agent_private_key": key}
    assert call(app, "PUT", route, body, headers={"Cookie": COOKIE})[0] == 403
    assert call(app, "PUT", route, body, headers={**auth_headers(), "X-CSRF-Token": "wrong"})[0] == 403
    assert call(app, "PUT", route, body, headers={**auth_headers(), "Origin": "https://elsewhere.invalid"})[0] == 403
    assert call(app, "PUT", route, {"agent_private_key": "bad"}, headers=auth_headers())[0] == 400

    seen = []
    def role_response(request):
        payload = json.loads(request.data)
        seen.append(payload)
        assert request.full_url == "https://api.hyperliquid.xyz/info" and request.get_method() == "POST"
        return {"role": "agent", "data": {"user": master.upper().replace("0X", "0x")}}
    monkeypatch.setattr("coinmaster.api.connections_broker._read_url", role_response)
    status, raw = call(app, "PUT", route, body, headers=auth_headers())
    assert status == 200 and b"222222" not in raw
    assert json.loads(raw)["verification_state"]["agent_authorization"] == "VERIFIED"
    assert seen == [{"type": "userRole", "user": agent}]
    record = root / (connection_id + ".json")
    assert record.stat().st_mode & 0o077 == 0 and root.stat().st_mode & 0o077 == 0
    assert json.loads(record.read_text())["agent_private_key"] == key
    restarted = create_connections_app(store_root=str(root), verifier=lambda _: 200)
    assert b"222222" not in call(restarted, "GET", "/api/v1/connections", headers=auth_headers())[1]

    monkeypatch.setattr("coinmaster.api.connections_broker._read_url", lambda _: {"role": "agent", "data": {"user": "0x" + "3" * 40}})
    status, raw = call(restarted, "POST", "/api/v1/connections/" + connection_id + "/test", headers=auth_headers())
    assert status == 200 and json.loads(raw)["verification_state"]["agent_authorization"] == "MISMATCH"
    monkeypatch.setattr("coinmaster.api.connections_broker._read_url", lambda _: {"role": "missing"})
    status, raw = call(restarted, "PUT", route, body, headers=auth_headers())
    assert status == 200 and json.loads(raw)["verification_state"]["agent_authorization"] == "NOT_AUTHORIZED"
    monkeypatch.setattr("coinmaster.api.connections_broker._read_url", lambda _: (_ for _ in ()).throw(ValueError("secret failure")))
    status, raw = call(restarted, "PUT", route, body, headers=auth_headers())
    assert status == 200 and json.loads(raw)["verification_state"]["agent_authorization"] == "ERROR"
    assert b"secret failure" not in raw


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


def test_signed_read_redirect_does_not_forward_credentials():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    import urllib.request
    import pytest
    from coinmaster.api.connections_broker import _read_url

    received = []

    class Target(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(self.headers.get("X-BAPI-API-KEY"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    target = ThreadingHTTPServer(("127.0.0.1", 0), Target)

    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:" + str(target.server_port) + "/receive")
            self.end_headers()

        def log_message(self, *args):
            pass

    redirect = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    threads = [Thread(target=server.serve_forever, daemon=True) for server in (target, redirect)]
    for thread in threads:
        thread.start()
    try:
        request = urllib.request.Request(
            "http://127.0.0.1:" + str(redirect.server_port) + "/start",
            headers={"X-BAPI-API-KEY": "SENTINEL_KEY", "X-BAPI-SIGN": "SENTINEL_SIGNATURE"},
        )
        with pytest.raises(ValueError, match="venue unavailable"):
            _read_url(request)
        assert received == []
    finally:
        redirect.shutdown()
        target.shutdown()
        redirect.server_close()
        target.server_close()

def test_store_syncs_parent_directory_and_nginx_streams_secret_bodies(tmp_path, monkeypatch):
    import os
    import stat

    from coinmaster.api.connections_broker import create_connections_app

    directory_syncs = []
    real_fsync = os.fsync

    def tracked_fsync(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            directory_syncs.append(True)
        return real_fsync(fd)

    monkeypatch.setattr("coinmaster.api.connections_broker.os.fsync", tracked_fsync)
    app = create_connections_app(store_root=str(tmp_path / "broker"), verifier=lambda _: 200)
    status, raw = call(app, "POST", "/api/v1/connections",
                       {"venue": "bybit", "api_key": "SENTINEL_KEY", "api_secret": "SENTINEL_SECRET"},
                       headers=auth_headers())
    assert status == 201 and len(directory_syncs) >= 1
    connection_id = json.loads(raw)["id"]
    assert call(app, "PUT", "/api/v1/connections/display", {"connection_id": connection_id}, headers=auth_headers())[0] == 200
    assert len(directory_syncs) >= 2
    assert call(app, "DELETE", "/api/v1/connections/" + connection_id, headers=auth_headers())[0] == 204
    assert len(directory_syncs) >= 4

    nginx = (Path(__file__).parents[1] / "ops" / "coinmaster24.com.https.nginx").read_text()
    broker_location = nginx.split("location ^~ /api/v1/connections {", 1)[1].split("}", 1)[0]
    assert "proxy_request_buffering off;" in broker_location
    assert "proxy_http_version 1.1;" in broker_location

def test_disconnect_crash_clears_selection_before_record_removal(tmp_path, monkeypatch):
    import pytest
    from coinmaster.api.connections_broker import create_connections_app

    root = str(tmp_path / "broker")
    app = create_connections_app(store_root=root, verifier=lambda _: 200)
    status, raw = call(app, "POST", "/api/v1/connections",
                       {"venue": "bybit", "api_key": "SENTINEL_KEY", "api_secret": "SENTINEL_SECRET"},
                       headers=auth_headers())
    assert status == 201
    connection_id = json.loads(raw)["id"]
    assert call(app, "PUT", "/api/v1/connections/display", {"connection_id": connection_id},
                headers=auth_headers())[0] == 200

    original_unlink = Path.unlink

    def crash_before_record_unlink(path, *args, **kwargs):
        if path.name == connection_id + ".json":
            raise OSError("injected crash before record removal")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", crash_before_record_unlink)
    with pytest.raises(OSError, match="injected crash"):
        call(app, "DELETE", "/api/v1/connections/" + connection_id, headers=auth_headers())
    monkeypatch.setattr(Path, "unlink", original_unlink)

    restarted = create_connections_app(store_root=root, verifier=lambda _: 200)
    status, raw = call(restarted, "GET", "/api/v1/connections", headers=auth_headers())
    assert status == 200
    state = json.loads(raw)
    assert state["display_connection_id"] is None
    assert [item["id"] for item in state["connections"]] == [connection_id]

    # Even an older interrupted deletion with a dangling display file is
    # reported as no selection after the record disappears.
    (Path(root) / (connection_id + ".json")).unlink()
    (Path(root) / "display").write_text(connection_id)
    status, raw = call(restarted, "GET", "/api/v1/connections", headers=auth_headers())
    assert status == 200 and json.loads(raw)["display_connection_id"] is None


def test_root_admin_repin_preserves_private_store_owner(tmp_path):
    import os
    from coinmaster.api.connections_broker import ConnectionStore
    if os.geteuid() != 0:
        import pytest
        pytest.skip("UID ownership acceptance requires isolated root fixture")
    root = tmp_path / "private-store"
    root.mkdir(mode=0o700)
    os.chown(root, 65534, 65534)
    store = ConnectionStore(str(root))
    item = {"id":"a"*32,"venue":"hyperliquid","account_label":"non-secret fixture"}
    store.save(item)
    record = root / ("a"*32+".json")
    assert record.stat().st_uid == 65534 and record.stat().st_gid == 65534
    assert record.stat().st_mode & 0o777 == 0o600
    assert root.stat().st_mode & 0o777 == 0o700
    item["account_label"] = "admin repin fixture"
    store.save(item)
    assert record.stat().st_uid == 65534
    assert store.get("a"*32)["account_label"] == "admin repin fixture"

def test_permission_error_is_storage_unavailable_not_missing(tmp_path, monkeypatch):
    import os
    import pytest
    from fastapi import HTTPException
    from coinmaster.api.connections_broker import ConnectionStore
    store = ConnectionStore(str(tmp_path / "private-store"))
    original = os.open
    def denied(path, *args, **kwargs):
        if str(path).endswith("a"*32+".json"): raise PermissionError()
        return original(path,*args,**kwargs)
    monkeypatch.setattr(os,"open",denied)
    with pytest.raises(HTTPException) as error: store.get("a"*32)
    assert error.value.status_code == 503
