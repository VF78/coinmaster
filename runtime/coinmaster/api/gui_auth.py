"""Single-operator browser sessions for the isolated GUI/API."""
from __future__ import annotations

import hashlib
import hmac
import html
import ipaddress
import secrets
import sqlite3
import time
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse


SESSION_COOKIE = "__Host-cm-session"
PREAUTH_COOKIE = "__Host-cm-preauth"
IDLE_SECONDS = 30 * 60
ABSOLUTE_SECONDS = 12 * 60 * 60


def password_hash(password: str, *, salt: bytes | None = None) -> str:
    """Return a self-describing, memory-hard scrypt verifier; never log input."""
    salt = salt or secrets.token_bytes(32)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=1 << 15, r=8, p=1, maxmem=128 << 20)
    return f"scrypt$15$8$1${salt.hex()}${digest.hex()}"


def _valid_hash(encoded: str) -> bool:
    try:
        scheme, cost, r, p, salt, digest = encoded.split("$")
        return scheme == "scrypt" and cost == "15" and r == "8" and p == "1" and len(bytes.fromhex(salt)) >= 16 and len(bytes.fromhex(digest)) == 64
    except (ValueError, TypeError):
        return False


def _password_matches(password: str, encoded: str) -> bool:
    if not _valid_hash(encoded):
        return False
    salt = bytes.fromhex(encoded.split("$")[4])
    return hmac.compare_digest(password_hash(password, salt=salt), encoded)


class GuiAuth:
    def __init__(self, *, username: str | None, encoded_password: str | None, database: str, origin: str | None, bearer_token: str | None):
        configured = (bool(username), bool(encoded_password), bool(origin))
        if any(configured) and not all(configured):
            raise ValueError("GUI login requires username, password hash and origin together")
        if encoded_password and not _valid_hash(encoded_password):
            raise ValueError("GUI password hash is invalid or too weak")
        if origin and (not origin.startswith("https://") or origin.rstrip("/") != origin or "/" in origin[8:]):
            raise ValueError("GUI origin must be an exact HTTPS origin")
        self.username = username
        self.encoded_password = encoded_password
        self.origin = origin
        self.bearer_token = bearer_token
        self.database = Path(database)
        self.credential_fingerprint = hashlib.sha256((encoded_password or "").encode()).hexdigest()
        if self.enabled:
            self.database.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as db:
                db.execute("""CREATE TABLE IF NOT EXISTS gui_sessions (
                    token_hash TEXT PRIMARY KEY, credential_fingerprint TEXT NOT NULL,
                    created_at INTEGER NOT NULL, touched_at INTEGER NOT NULL, revoked_at INTEGER
                )""")
                db.execute("""CREATE TABLE IF NOT EXISTS gui_login_failures (
                    source TEXT PRIMARY KEY, window_start INTEGER NOT NULL, attempts INTEGER NOT NULL
                )""")

    @property
    def enabled(self) -> bool:
        return bool(self.username and self.encoded_password and self.origin)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=5)
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def _session(self, token: str | None) -> bool:
        if not self.enabled or not token or len(token) != 64 or any(char not in "0123456789abcdefABCDEF" for char in token):
            return False
        now = int(time.time())
        digest = hashlib.sha256(bytes.fromhex(token)).hexdigest()
        with self._connect() as db:
            row = db.execute("SELECT credential_fingerprint,created_at,touched_at,revoked_at FROM gui_sessions WHERE token_hash=?", (digest,)).fetchone()
            if not row or row[3] is not None or row[0] != self.credential_fingerprint or now - row[1] >= ABSOLUTE_SECONDS or now - row[2] >= IDLE_SECONDS:
                return False
            if now - row[2] >= 60:
                db.execute("UPDATE gui_sessions SET touched_at=? WHERE token_hash=?", (now, digest))
        return True

    def csrf(self, token: str) -> str:
        return hmac.new(bytes.fromhex(token), b"coinmaster-gui-csrf-v1", hashlib.sha256).hexdigest()

    def authorize(self, request: Request, authorization: str | None, csrf_token: str | None) -> str:
        peer = request.client.host if request.client else ""
        try:
            loopback = ipaddress.ip_address(peer).is_loopback
        except ValueError:
            loopback = False
        public_proxy = request.headers.get("x-coinmaster-public-proxy") == "1"
        if loopback and not public_proxy and self.bearer_token and authorization and hmac.compare_digest(authorization, f"Bearer {self.bearer_token}"):
            return "automation"
        token = request.cookies.get(SESSION_COOKIE)
        if not self._session(token):
            raise HTTPException(401, "operator session required")
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("origin") != self.origin or not csrf_token or not hmac.compare_digest(csrf_token, self.csrf(token)):
                raise HTTPException(403, "session write requires origin and CSRF token")
        return "session"

    def login_page(self, request: Request) -> HTMLResponse | RedirectResponse:
        if not self.enabled:
            raise HTTPException(503, "operator login is not configured")
        if self._session(request.cookies.get(SESSION_COOKIE)):
            return RedirectResponse("/", status_code=303)
        challenge = secrets.token_hex(32)
        notice = '<p role="alert">Invalid credentials. Please try again.</p>' if request.query_params.get("invalid") == "1" else ""
        page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Coinmaster24 · Sign in</title><style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#101827;color:#e5eef9;font:16px system-ui}}main{{box-sizing:border-box;width:min(22rem,calc(100vw - 2rem));padding:2rem;border:1px solid #34465d;border-radius:1rem;background:#172235}}label{{display:block;margin:1rem 0}}input{{display:block;box-sizing:border-box;width:100%;margin-top:.4rem;padding:.7rem;background:#0f1726;color:inherit;border:1px solid #60758f;border-radius:.4rem}}button{{width:100%;padding:.75rem;background:#38cbb9;color:#08201d;border:0;border-radius:.4rem;font-weight:700}}p{{color:#eeb0b8}}</style>
<main><h1>Coinmaster24</h1><h2>Operator sign in</h2>{notice}<form method="post" action="/login"><input type="hidden" name="challenge" value="{html.escape(challenge)}"><label>Username<input name="username" autocomplete="username" required></label><label>Password<input name="password" type="password" autocomplete="current-password" required></label><button type="submit">Sign in</button></form></main></html>"""
        response = HTMLResponse(page, headers={"Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'", "X-Frame-Options": "DENY"})
        response.set_cookie(PREAUTH_COOKIE, challenge, secure=True, httponly=True, samesite="strict", path="/")
        return response

    async def login(self, request: Request) -> RedirectResponse:
        if not self.enabled:
            raise HTTPException(503, "operator login is not configured")
        if request.headers.get("origin") != self.origin:
            raise HTTPException(403, "login origin mismatch")
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/x-www-form-urlencoded":
            raise HTTPException(415, "expected form submission")
        body = await request.body()
        if len(body) > 4096:
            raise HTTPException(413, "login form too large")
        try:
            form = parse_qs(body.decode("utf-8"), strict_parsing=True)
            username, password, challenge = (form[key][0] for key in ("username", "password", "challenge"))
        except (UnicodeError, ValueError, KeyError, IndexError):
            raise HTTPException(400, "invalid login form") from None
        cookie = request.cookies.get(PREAUTH_COOKIE)
        if not cookie or not hmac.compare_digest(challenge, cookie):
            raise HTTPException(403, "login challenge mismatch")
        peer = request.client.host if request.client else "unknown"
        now = int(time.time())
        with self._connect() as db:
            row = db.execute("SELECT window_start,attempts FROM gui_login_failures WHERE source=?", (peer,)).fetchone()
            if row and now - row[0] < 900 and row[1] >= 5:
                raise HTTPException(429, "login temporarily limited", headers={"Retry-After": str(900 - (now - row[0]))})
        valid = hmac.compare_digest(username, self.username or "") and _password_matches(password, self.encoded_password or "")
        if not valid:
            with self._connect() as db:
                if row and now - row[0] < 900:
                    db.execute("UPDATE gui_login_failures SET attempts=attempts+1 WHERE source=?", (peer,))
                else:
                    db.execute("INSERT OR REPLACE INTO gui_login_failures(source,window_start,attempts) VALUES (?,?,1)", (peer, now))
            return RedirectResponse("/login?invalid=1", status_code=303)
        token = secrets.token_hex(32)
        digest = hashlib.sha256(bytes.fromhex(token)).hexdigest()
        with self._connect() as db:
            db.execute("DELETE FROM gui_login_failures WHERE source=?", (peer,))
            db.execute("INSERT INTO gui_sessions(token_hash,credential_fingerprint,created_at,touched_at,revoked_at) VALUES (?,?,?,?,NULL)", (digest, self.credential_fingerprint, now, now))
        response = RedirectResponse("/", status_code=303, headers={"Cache-Control": "no-store"})
        response.set_cookie(SESSION_COOKIE, token, secure=True, httponly=True, samesite="strict", path="/")
        response.delete_cookie(PREAUTH_COOKIE, path="/", secure=True, httponly=True, samesite="strict")
        return response

    def logout(self, token: str | None) -> None:
        if not token or len(token) != 64:
            return
        try:
            digest = hashlib.sha256(bytes.fromhex(token)).hexdigest()
        except ValueError:
            return
        with self._connect() as db:
            db.execute("UPDATE gui_sessions SET revoked_at=? WHERE token_hash=?", (int(time.time()), digest))
