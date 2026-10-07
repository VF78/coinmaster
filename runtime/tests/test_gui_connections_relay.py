"""Real loopback relay preserves Host and allows the broker auth callback."""
import asyncio
import io
import socket
import threading
import time
import urllib.request
from pathlib import Path
import pytest
import uvicorn
from fastapi import Request, HTTPException
from coinmaster.api.runtime_sidecar import create_runtime_app
from coinmaster.api.connections_broker import create_connections_app
from coinmaster.api.gui_auth import GuiAuth, SESSION_COOKIE

def request(method, body=b"", headers=()):
    async def receive(): return {"type":"http.request", "body":body, "more_body":False}
    return Request({"type":"http", "method":method, "path":"/api/v1/connections", "headers":headers, "client":("127.0.0.1",1234), "scheme":"http"}, receive)

def relay(app):
    return next(route for route in app.routes if getattr(route, "path", "") == "/api/v1/connections")

def test_relay_filters_bearer_and_bounds_body_before_network(tmp_path, monkeypatch):
    app = create_runtime_app(database=str(tmp_path / "missing.sqlite"), control_database=str(tmp_path / "control.sqlite"), token="operator")
    route = relay(app)
    auth = next(dep.call for dep in route.dependant.dependencies if dep.call.__name__ == "auth")
    with pytest.raises(HTTPException) as denied: auth(request("GET"), None, None)
    assert denied.value.status_code == 401
    calls = []
    class Reply(io.BytesIO): status = 200
    def upstream(probe, timeout):
        calls.append((probe, threading.get_ident()))
        return Reply(b'{"connections":[],"display_connection_id":null}')
    monkeypatch.setattr("coinmaster.api.runtime_sidecar.urllib.request.urlopen", upstream)
    main_thread = threading.get_ident()
    result = asyncio.run(route.endpoint(request("GET", headers=[(b"authorization",b"Bearer operator"),(b"cookie",(SESSION_COOKIE+"="+"a"*64).encode())])))
    assert result.status_code == 200 and calls[0][1] != main_thread
    probe = calls[0][0]
    assert probe.get_header("Host") == "coinmaster24.com" and probe.get_header("Authorization") is None
    with pytest.raises(HTTPException) as large:
        asyncio.run(route.endpoint(request("POST", b"x"*16385)))
    assert large.value.status_code == 413 and len(calls) == 1

def start_server(app):
    sock = socket.socket()
    sock.bind(("127.0.0.1",0)); sock.listen()
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    for _ in range(100):
        if server.started: return server, thread, port
        time.sleep(.02)
    raise AssertionError("isolated server startup failed")

def test_real_loopback_broker_callback_does_not_deadlock(tmp_path, monkeypatch):
    monkeypatch.setenv("COINMASTER_CONNECTION_VERIFY_TOKEN", "test-verifier")
    monkeypatch.setattr(GuiAuth, "_session", lambda self, cookie: cookie == "a"*64)
    sidecar = create_runtime_app(database=str(tmp_path/"missing.sqlite"), control_database=str(tmp_path/"control.sqlite"), token="operator")
    api, api_thread, api_port = start_server(sidecar)
    broker_app = create_connections_app(store_root=str(tmp_path/"connections"), verify_token="test-verifier", verifier_url="http://127.0.0.1:"+str(api_port)+"/internal/connections/verify-session")
    broker, broker_thread, broker_port = start_server(broker_app)
    original = urllib.request.urlopen
    def mapped(probe, *args, **kwargs):
        if isinstance(probe, urllib.request.Request) and probe.full_url.startswith("http://127.0.0.1:18184/"):
            probe = urllib.request.Request(probe.full_url.replace(":18184/",":"+str(broker_port)+"/"), data=probe.data, headers=dict(probe.header_items()), method=probe.method)
        return original(probe,*args,**kwargs)
    monkeypatch.setattr("coinmaster.api.runtime_sidecar.urllib.request.urlopen", mapped)
    try:
        probe = urllib.request.Request("http://127.0.0.1:"+str(api_port)+"/api/v1/connections", headers={"Authorization":"Bearer operator","Cookie":SESSION_COOKIE+"="+"a"*64})
        with original(probe,timeout=4) as result:
            assert result.status == 200
            assert result.read() == b'{"connections":[],"display_connection_id":null}'
    finally:
        api.should_exit = True; broker.should_exit = True
        api_thread.join(3); broker_thread.join(3)
