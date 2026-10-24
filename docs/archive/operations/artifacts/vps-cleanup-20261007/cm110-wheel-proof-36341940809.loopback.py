import asyncio
from websockets.asyncio.server import serve
from nautilus_trader.core import nautilus_pyo3
from coinmaster.ops.hl_live_execution import QualifiedInfoBoundary
from coinmaster.ops.live_recovery import NativeLiveRecoveryScope

async def main():
    sessions = []
    replacement = asyncio.Event()

    async def handler(socket):
        index = len(sessions)
        sessions.append([])
        if index == 1:
            replacement.set()
        try:
            async for frame in socket:
                sessions[index].append(frame)
                if index == 0:
                    await socket.close(code=1000)
        except Exception as exc:
            print("server_close", type(exc).__name__)

    async with serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = nautilus_pyo3.HyperliquidWebSocketClient(
            url=f"ws://127.0.0.1:{port}",
            environment=nautilus_pyo3.HyperliquidEnvironment.TESTNET,
            account_id="HYPERLIQUID-master",
        )
        await client.connect(asyncio.get_running_loop(), [], lambda message: None)
        initial = (client.connection_epoch(), client.is_active(), client.is_closed())
        print("initial", initial)
        assert initial == (0, True, False)
        boundary = QualifiedInfoBoundary()
        boundary._ws_client = client
        scope = NativeLiveRecoveryScope("0x" + "a" * 40, "", 1, None, (), frozenset({"BTC"}))
        boundary.configure_info_boundary(scope, lambda _: None, lambda: frozenset())
        boundary._cm_ws_phase = "LIVE"
        assert boundary.recovery_healthy()
        await client.subscribe_all_mids()
        await asyncio.wait_for(replacement.wait(), timeout=10)
        await asyncio.sleep(0.5)
        after = (client.connection_epoch(), client.is_active(), client.is_closed())
        print("after_reconnect", after)
        print("sessions", len(sessions))
        print("first_frames", sessions[0])
        print("replacement_frames", sessions[1])
        assert after[0] >= 1 and after[1:] == (True, False)
        assert not boundary.recovery_healthy()
        assert boundary._cm_ws_failure == "WS_CONNECTION_EPOCH_CHANGED"
        print("live_boundary_failure", boundary._cm_ws_failure)
        assert any("allMids" in frame for frame in sessions[0])
        assert any("allMids" in frame for frame in sessions[1])
        await client.close()

asyncio.run(main())
