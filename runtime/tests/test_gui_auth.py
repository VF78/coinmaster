"""Real HTTP checks for the single GUI login and shared runtime/control auth."""
from __future__ import annotations

import asyncio
import json
import re
import sqlite3
import time
from contextlib import contextmanager
from urllib.parse import urlencode, urlsplit

from coinmaster.api.gui_auth import password_hash
from coinmaster.api.runtime_sidecar import create_runtime_app


@contextmanager
def serve(app):
    yield app


def request(app, method: str, path: str, *, headers: dict[str, str] | None = None, body: bytes | None = None):
    parsed = urlsplit(path)
    header_values = {"Host": "coinmaster24.com", "X-Coinmaster-Public-Proxy": "1", **(headers or {})}
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "scheme": "https", "method": method,
        "path": parsed.path, "raw_path": parsed.path.encode(), "query_string": parsed.query.encode(),
        "headers": [(key.lower().encode(), value.encode()) for key, value in header_values.items()],
        "server": ("coinmaster24.com", 443), "client": ("127.0.0.1", 12345), "root_path": ""}
    sent = []
    async def exchange():
        received = False
        async def receive():
            nonlocal received
            if not received:
                received = True
                return {"type": "http.request", "body": body or b"", "more_body": False}
            return {"type": "http.disconnect"}
        async def send(message):
            sent.append(message)
        await app(scope, receive, send)
    asyncio.run(exchange())
    start = next(message for message in sent if message["type"] == "http.response.start")
    response_headers = {}
    for key, value in start["headers"]:
        decoded_key = key.decode().lower()
        response_headers[decoded_key] = (response_headers.get(decoded_key, "") + ("\n" if decoded_key in response_headers else "") + value.decode())
    return start["status"], response_headers, b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")


def test_one_login_protects_shell_assets_runtime_and_included_control_routes(tmp_path, monkeypatch):
    dist = tmp_path / "web"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<main>Coinmaster24 private shell</main>")
    (dist / "assets" / "app.js").write_text("export const privateApp = true")
    (dist / "private.txt").write_text("must not be served by asset traversal")
    monkeypatch.setenv("COINMASTER_RUNTIME_DIST", str(dist))
    db = tmp_path / "auth.sqlite"
    app = create_runtime_app(database=str(tmp_path / "missing-paper.sqlite"), control_database=str(tmp_path / "control.sqlite"),
        token="machine-token", worker_token="", worker_url="http://127.0.0.1:9", operator_username="operator",
        operator_password_hash=password_hash("a long test password", salt=b"fixed-salt-for-test-0123456789abc"),
        session_database=str(db), public_origin="https://coinmaster24.com")
    with serve(app) as port:
        assert request(port, "GET", "/")[0] == 303
        # A sign-prefixed token passes int(..., 16), then used to make
        # bytes.fromhex raise instead of treating the cookie as unauthenticated.
        malformed_cookie = "+" + "0" * 63
        assert request(port, "GET", "/api/v1/auth/session", headers={"Cookie": f"__Host-cm-session={malformed_cookie}"})[0] == 401
        assert request(port, "GET", "/assets/app.js")[0] == 401
        assert request(port, "GET", "/api/v1/configurations/default")[0] == 401
        assert request(port, "GET", "/api/v1/instances/hl-stageg-testnet/controls")[0] == 401
        assert request(port, "GET", "/api/v1/configurations/default", headers={"Authorization": "Bearer machine-token"})[0] == 401
        assert request(port, "GET", "/api/v1/configurations/default", headers={"Authorization": "Bearer machine-token", "X-Coinmaster-Public-Proxy": "0"})[0] == 200

        status, headers, body = request(port, "GET", "/login")
        assert status == 200 and b"Operator sign in" in body
        assert b"main{box-sizing:border-box;width:min(22rem,calc(100vw - 2rem))" in body
        challenge = re.search(rb'name="challenge" value="([0-9a-f]+)"', body).group(1).decode()
        preauth = headers["set-cookie"].split(";", 1)[0]
        form = urlencode({"username": "operator", "password": "a long test password", "challenge": challenge}).encode()
        base_headers = {"Cookie": preauth, "Content-Type": "application/x-www-form-urlencoded"}
        assert request(port, "POST", "/login", headers={**base_headers, "Origin": "https://evil.f-ai.studio"}, body=form)[0] == 403
        assert request(port, "POST", "/login", headers={**base_headers, "Origin": "https://cm.f-ai.studio"}, body=form)[0] == 403
        status, headers, _ = request(port, "POST", "/login", headers={**base_headers, "Origin": "https://coinmaster24.com"}, body=form)
        assert status == 303
        session_header = headers["set-cookie"]
        assert session_header.startswith("__Host-cm-session=")
        assert "Secure" in session_header and "HttpOnly" in session_header and "SameSite=strict" in session_header
        assert "domain=" not in session_header.lower()
        cookie = session_header.split(";", 1)[0]
        assert b"private shell" in request(port, "GET", "/", headers={"Cookie": cookie})[2]
        assert request(port, "GET", "/assets/app.js", headers={"Cookie": cookie})[0] == 200
        assert b"must not be served" not in request(port, "GET", "/assets/../private.txt", headers={"Cookie": cookie})[2]
        status, _, body = request(port, "GET", "/api/v1/not-a-route", headers={"Cookie": cookie})
        assert status == 404 and json.loads(body)["detail"] == "Not Found"
        assert request(port, "GET", "/api/v1/configurations/default", headers={"Cookie": cookie})[0] == 200
        status, _, body = request(port, "GET", "/api/v1/instances/hl-stageg-testnet/controls", headers={"Cookie": cookie})
        assert status == 200 and json.loads(body)["projection_state"] == "UNAVAILABLE"
        assert "/api/v1/runtime/commands/{command}" not in json.loads(request(port, "GET", "/api/v1/openapi.json", headers={"Cookie": cookie})[2])["paths"]
        status, _, body = request(port, "GET", "/api/v1/auth/session", headers={"Cookie": cookie})
        csrf = json.loads(body)["csrf_token"]
        assert status == 200 and len(csrf) == 64
        assert request(port, "POST", "/api/v1/runs/missing/cancel", headers={"Cookie": cookie, "Origin": "https://coinmaster24.com"})[0] == 403
        assert request(port, "POST", "/api/v1/runs/missing/cancel", headers={"Cookie": cookie, "Origin": "https://coinmaster24.com", "X-CSRF-Token": csrf})[0] == 404
        assert request(port, "POST", "/api/v1/auth/logout", headers={"Cookie": cookie, "Origin": "https://coinmaster24.com"})[0] == 403
        assert request(port, "POST", "/api/v1/auth/logout", headers={"Cookie": cookie, "Origin": "https://evil.f-ai.studio", "X-CSRF-Token": csrf})[0] == 403
        assert request(port, "POST", "/api/v1/auth/logout", headers={"Cookie": cookie, "Origin": "https://cm.f-ai.studio", "X-CSRF-Token": csrf})[0] == 403
        assert request(port, "POST", "/api/v1/auth/logout", headers={"Cookie": cookie, "Origin": "https://coinmaster24.com", "X-CSRF-Token": csrf})[0] == 200
        assert request(port, "GET", "/api/v1/configurations/default", headers={"Cookie": cookie})[0] == 401

        # Expiration is enforced from server-side state, independent of cookie lifetime.
        status, headers, body = request(port, "GET", "/login")
        challenge = re.search(rb'name="challenge" value="([0-9a-f]+)"', body).group(1).decode()
        preauth = headers["set-cookie"].split(";", 1)[0]
        form = urlencode({"username": "operator", "password": "a long test password", "challenge": challenge}).encode()
        _, headers, _ = request(port, "POST", "/login", headers={"Cookie": preauth, "Content-Type": "application/x-www-form-urlencoded", "Origin": "https://coinmaster24.com"}, body=form)
        second_cookie = headers["set-cookie"].split(";", 1)[0]
        with sqlite3.connect(db) as conn:
            conn.execute("UPDATE gui_sessions SET touched_at=? WHERE revoked_at IS NULL", (int(time.time()) - 1801,))
        assert request(port, "GET", "/api/v1/configurations/default", headers={"Cookie": second_cookie})[0] == 401
