"""Restricted native factual-fill reconstruction and event-commit crash proof.

No data/execution network clients, production journal hook or second PnL engine.
Recovery uses original order definitions and native matcher fills, plus a single
boundary quote; it does not replay the historical market-input stream. Fixed
async waits are fixture scheduling only, never a production completion barrier.
"""
from test_hl_sandbox_open_replay import (
    StableOrderProbe, WaveOverlayStrategyConfig, BarSpecification, BarType,
    BarAggregation, PriceType, InstrumentId, AggregationSource, BTC_PERP, SOL_PERP,
    venue_mark_data_type, ClientId, Decimal, TradingNodeConfig, Environment,
    LoggingConfig, LiveExecEngineConfig, SandboxExecutionClientConfig,
    SANDBOX_LEVERAGES, RoutingConfig, TradingNode, SandboxLiveExecClientFactory,
    HL_BTC, HL_SOL, model_fx_pair_and_quote, quote, TradeTick, Price, Quantity,
    AggressorSide, TradeId, snapshot, ClientOrderId, asyncio,
)
from nautilus_trader.model.orders.unpacker import OrderUnpacker
from nautilus_trader.model.events import OrderInitialized, OrderSubmitted, OrderAccepted, OrderFilled
import json
import os
import signal
import sys
import subprocess
import hashlib
from pathlib import Path
import pytest

class CaptureFactory(SandboxLiveExecClientFactory):
    client = None
    @staticmethod
    def create(loop, name, config, portfolio, msgbus, cache, clock):
        CaptureFactory.client = SandboxLiveExecClientFactory.create(loop, name, config, portfolio, msgbus, cache, clock)
        return CaptureFactory.client

# Pinned node builder injects portfolio only for this exact factory name.
CaptureFactory.__name__ = "SandboxLiveExecClientFactory"

def read_facts(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b"\n"):
        raise ValueError("INCOMPLETE_RECORD")
    records = {"events": [], "inits": {}}
    for line in raw.splitlines():
        envelope = json.loads(line)
        payload = envelope["payload"]
        if hashlib.sha256(payload.encode()).hexdigest() != envelope["sha256"]:
            raise ValueError("CORRUPT_RECORD")
        row = json.loads(payload)
        records["events"].append(row["event"])
        records["inits"][row["event"]["client_order_id"]] = row["init"]
    return records

async def run_probe(records=None, journal_path=None, crash_at=None):
    spec = BarSpecification(1, BarAggregation.DAY, PriceType.LAST)
    btc_bar = BarType(InstrumentId.from_str("BTCUSDT-LINEAR.BYBIT"), spec, AggregationSource.EXTERNAL)
    sol_bar = BarType(InstrumentId.from_str("SOLUSDT-LINEAR.BYBIT"), spec, AggregationSource.EXTERNAL)
    strategy = StableOrderProbe(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP, sol_id=SOL_PERP,
        btc_bar_type=btc_bar, sol_bar_type=sol_bar,
        btc_mark_data_type=venue_mark_data_type(BTC_PERP),
        sol_mark_data_type=venue_mark_data_type(SOL_PERP),
        mark_client_id=ClientId("HYPERLIQUID-MAINNET-DATA"),
        active_seed=Decimal("10000"),
    ))
    config = TradingNodeConfig(
        environment=Environment.LIVE, trader_id="HL-OPEN-REPLAY-PROBE",
        logging=LoggingConfig(log_level="ERROR"),
        exec_engine=LiveExecEngineConfig(reconciliation=False),
        exec_clients={"SANDBOX": SandboxExecutionClientConfig(
            venue="HYPERLIQUID", starting_balances=["10000 USDC"],
            base_currency="USDC", leverages=dict(SANDBOX_LEVERAGES),
            use_reduce_only=True,
            routing=RoutingConfig(venues=frozenset({"HYPERLIQUID"})),
        )},
    )
    node = TradingNode(config=config, loop=asyncio.get_running_loop())
    node.add_exec_client_factory("SANDBOX", CaptureFactory)
    node.build()
    node.cache.add_instrument(HL_BTC)
    node.cache.add_instrument(HL_SOL)
    pair, fx_quote = model_fx_pair_and_quote()
    node.cache.add_instrument(pair)
    node.cache.add_quote_tick(fx_quote)
    node.trader.add_strategy(strategy)
    # Capture native order output before LiveExecutionEngine can enqueue it.
    journal = []
    original = node.kernel.exec_engine.process
    def capture(event):
        journal.append(type(event).to_dict(event))
        partial = isinstance(event, OrderFilled) and str(event.client_order_id) == "CM-REPLAY-TP"
        if partial and crash_at == "before_append":
            os.kill(os.getpid(), signal.SIGKILL)
        if journal_path:
            row = {"event": type(event).to_dict(event), "init": OrderInitialized.to_dict(node.cache.order(event.client_order_id).events[0])}
            payload = json.dumps(row, sort_keys=True)
            envelope = {"payload": payload, "sha256": hashlib.sha256(payload.encode()).hexdigest()}
            with open(journal_path, "a") as stream:
                stream.write(json.dumps(envelope) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        if partial and crash_at == "after_append_before_delivery":
            os.kill(os.getpid(), signal.SIGKILL)
        original(event)
    node.kernel.msgbus.deregister("ExecEngine.process", original)
    node.kernel.msgbus.register("ExecEngine.process", capture)
    accounts = []
    # Derived account facts are validation evidence; do not apply them twice.
    node.kernel.msgbus.subscribe("events.account.*", lambda event: accounts.append(type(event).to_dict(event)))
    def after_order(event):
        if isinstance(event, OrderFilled) and str(event.client_order_id) == "CM-REPLAY-TP" and crash_at == "after_native_application":
            os.kill(os.getpid(), signal.SIGKILL)
    node.kernel.msgbus.subscribe("events.order.*", after_order)
    await node.kernel.start_async()
    client = CaptureFactory.client
    try:
        if records is None:
            for event in [quote(1, "59999.0", "60000.0"), quote(2, "60001.0", "60002.0"), quote(3, "60009.0", "60011.0"), TradeTick(BTC_PERP, Price.from_str("60010.0"), Quantity.from_str("0.00500"), AggressorSide.BUYER, TradeId("PARTIAL-TRADE-1"), 4, 4)]:
                node.kernel.data_engine.process(event)
                await asyncio.sleep(.05)
            inits = {str(o.client_order_id): OrderInitialized.to_dict(o.events[0]) for o in node.cache.orders()}
            records = json.loads(json.dumps({"events": journal, "inits": inits, "accounts": accounts}))
        else:
            strategy.step = 2
            # One boundary market snapshot, not historical market-input replay.
            node.cache.add_quote_tick(quote(3, "60009.0", "60011.0"))
            matcher = client.exchange.get_matching_engine(BTC_PERP)
            for row in records["events"]:
                order_id = ClientOrderId(row["client_order_id"])
                order = node.cache.order(order_id)
                if order is None:
                    order = OrderUnpacker.unpack(records["inits"][str(order_id)])
                    node.cache.add_order(order)
                client.test_clock.set_time(row["ts_event"])
                if row["type"] == "OrderSubmitted":
                    node.kernel.exec_engine.process(OrderSubmitted.from_dict(row))
                elif row["type"] == "OrderAccepted":
                    # Generate native acceptance and register the still-unfilled order.
                    matcher.accept_order(order)
                elif row["type"] == "OrderFilled":
                    fill = OrderFilled.from_dict(row)
                    matcher.fill_order(order, fill.last_px, fill.last_qty, fill.liquidity_side, fill.position_id, node.cache.position_for_order(order_id))
                else:
                    raise AssertionError("UNHANDLED_NATIVE_EVENT:" + row["type"])
                await asyncio.sleep(.05)
        boundary = snapshot(node, strategy)
        # Restore only latest quote context after native factual reconstruction.
        node.kernel.data_engine.process(quote(5, "60009.0", "60011.0"))
        await asyncio.sleep(.05)
        node.kernel.data_engine.process(TradeTick(BTC_PERP, Price.from_str("60010.0"), Quantity.from_str("0.02500"), AggressorSide.BUYER, TradeId("REMAINDER-TRADE-2"), 6, 6))
        await asyncio.sleep(.05)
        after = snapshot(node, strategy)
        return records, boundary, after
    finally:
        await node.kernel.stop_async()
        node.kernel.dispose()


def test_native_factual_fill_reconstruction():
    async def scenario():
        records, before, after = await run_probe()
        _, restored, next_state = await run_probe(records)
        assert before["cash"] == ("9999.1949925", "9998.7249925", "0.47")
        assert restored == before
        assert next_state == after
        assert next_state["next_decisions"] == ["HOLD_WORKING_PARTIAL_TP"]
        assert next_state["positions"] == []
        assert len(next_state["fills"]) == 3
    asyncio.run(scenario())


@pytest.mark.parametrize("window", ["before_append", "after_append_before_delivery", "after_native_application"])
def test_native_event_crash_prefix(tmp_path, window):
    path = tmp_path / "events.jsonl"
    child = subprocess.run([sys.executable, __file__, "--crash", str(path), window], capture_output=True, timeout=30)
    assert child.returncode == -signal.SIGKILL, child.stderr.decode()
    records = read_facts(path)
    assert len(records["events"]) == (4 if window == "before_append" else 5)
    async def scenario():
        _, first, after = await run_probe(records)
        _, repeated, after_repeated = await run_probe(read_facts(path))
        assert first == repeated
        assert after == after_repeated
        qty = "0.03000" if window == "before_append" else "0.02500"
        assert first["positions"] == [(str(BTC_PERP), qty, True)]
        if window != "before_append":
            assert first["cash"] == ("9999.1949925", "9998.7249925", "0.47")
            assert after["positions"] == []
            assert after["cash"] == ("9999.219955", "9999.219955", "0")
            assert len(after["fills"]) == 3
        else:
            assert first["cash"][0] == "9999.19"
            assert after["positions"] == [(str(BTC_PERP), "0.00500", True)]
    asyncio.run(scenario())
    valid = path.read_bytes()
    path.write_bytes(valid[:-1])
    with pytest.raises(ValueError, match="INCOMPLETE_RECORD"):
        read_facts(path)
    path.write_bytes(valid.replace(b"60010", b"60011", 1))
    with pytest.raises(ValueError, match="CORRUPT_RECORD"):
        read_facts(path)

if __name__ == "__main__" and len(sys.argv) == 4 and sys.argv[1] == "--crash":
    asyncio.run(run_probe(journal_path=sys.argv[2], crash_at=sys.argv[3]))
