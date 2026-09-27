"""Native Sandbox proof for the sealed HL Stage-G attachment wiring.

This is intentionally an isolated, credential-free test seam.  It uses the
real Stage-G candidate, HYPERLIQUID BTC/SOL identifiers, public-profile margin
policy, and only Nautilus' SandboxExecutionClient.  The deterministic two
intent probe avoids manufacturing a daily signal; the production attachment
gate is tested separately and remains blocked until a confirmed funding
settlement source exists.
"""
from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from nautilus_trader.adapters.hyperliquid.execution import HyperliquidExecutionClient
from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.common import Environment
from nautilus_trader.common.component import TestClock
from nautilus_trader.common.factories import OrderFactory
from nautilus_trader.config import LoggingConfig
from nautilus_trader.live.config import LiveExecEngineConfig, RoutingConfig, TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.currencies import BTC, SOL, USD, USDC
from nautilus_trader.model.data import BarSpecification, BarType, MarkPriceUpdate, QuoteTick, TradeTick
from nautilus_trader.model.enums import AggressorSide, AggregationSource, BarAggregation, PriceType, LiquiditySide, OrderSide, TimeInForce
from nautilus_trader.model.identifiers import ClientId, InstrumentId, StrategyId, Symbol, TradeId, TraderId, Venue
from nautilus_trader.model.events import OrderFilled
from nautilus_trader.model.instruments import CryptoPerpetual
from nautilus_trader.model.objects import Money, Price, Quantity

from coinmaster.domain.wave_overlay import DailyBar, Episode, Features, Intent
from coinmaster.ops.hyperliquid_testnet import (
    BTC_PERP,
    SOL_PERP,
    SANDBOX_LEVERAGES,
    SANDBOX_MARK_MAX_AGE_NS,
    LifecycleHooks,
    HyperliquidTestnetNode,
    cross_venue_stage_g_gate,
)
from coinmaster.ops.hl_sandbox_money import SandboxLiveExecClientFactory as HyperliquidUsdcSandboxFactory, HyperliquidUsdcFeeModel, HyperliquidUsdcSandboxExecutionClient, model_fx_pair_and_quote, model_fx_ready, native_equity, native_money_projection
from coinmaster.ops.paper import PaperRuntime
from coinmaster.ops.stage_g_config import load_candidate
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig, _native_account_money, _native_limit_price
from coinmaster.venues.hyperliquid_profile import HyperliquidProfileEnvironment, HyperliquidVenueProfile
from coinmaster.venues.margin_policy import HyperliquidSandboxMarginPolicy
from coinmaster.venues.marks import venue_mark_data_type


ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
HYPERLIQUID = Venue("HYPERLIQUID")


def _perpetual(symbol: str, base, tick: str, step: str, *, quote=USDC) -> CryptoPerpetual:
    """Local instrument metadata for the public HL IDs; no adapter request."""
    return CryptoPerpetual(
        InstrumentId(Symbol(f"{symbol}-PERP"), HYPERLIQUID), Symbol(symbol), base, quote, USDC,
        False, len(tick.partition(".")[2]), len(step.partition(".")[2]),
        Price.from_str(tick), Quantity.from_str(step), 0, 0,
        min_quantity=Quantity.from_str(step), min_notional=Money(Decimal("10"), quote),
        margin_init=Decimal("0.025"), margin_maint=Decimal("0.0125"),
        maker_fee=Decimal("0.00015"), taker_fee=Decimal("0.00045"),
    )


def _public_perpetual(symbol: str, base, tick: str, step: str) -> CryptoPerpetual:
    fields = CryptoPerpetual.to_dict(_perpetual(symbol, base, tick, step, quote=USD))
    fields.update(maker_fee="0", taker_fee="0")
    return CryptoPerpetual.from_dict(fields)


HL_BTC = _public_perpetual("BTC-USD", BTC, "0.1", "0.00001")
HL_SOL = _public_perpetual("SOL-USD", SOL, "0.01", "0.01")
assert HL_BTC.id == BTC_PERP
assert HL_SOL.id == SOL_PERP


def _quote(instrument_id: InstrumentId, bid: str, ask: str, ts_ns: int) -> QuoteTick:
    return QuoteTick(
        instrument_id, Price.from_str(bid), Price.from_str(ask),
        Quantity.from_str("1000.00000"), Quantity.from_str("1000.00000"), ts_ns, ts_ns,
    )


class AttachedStageGEntryExitProbe(WaveOverlayStrategy):
    """Exercise the real adapter's submit/fill callbacks with test intents.

Daily decision generation is outside this lifecycle proof. Calling the
existing ``_submit_intent`` path retains Stage-G order normalization,
    public-mark margin gate, LifecycleHooks journal, native fees, and native
    cache ownership rather than introducing a second matching engine.
    """
    def __init__(self, config: WaveOverlayStrategyConfig) -> None:
        super().__init__(config)
        self.step = 0

    def on_start(self) -> None:
        # The real adapter subscribes its public routes; the test injects only
        # local deterministic quotes/marks into this native node.
        self.subscribe_quote_ticks(self.config.btc_id)

    def on_quote_tick(self, tick: QuoteTick) -> None:
        if tick.instrument_id != self.config.btc_id or self.step >= 2:
            return
        self.on_mark_price(MarkPriceUpdate(self.config.btc_id, Price.from_str("60000.0"), tick.ts_event, tick.ts_init))
        self.on_mark_price(MarkPriceUpdate(self.config.sol_id, Price.from_str("150.00"), tick.ts_event, tick.ts_init))
        # The tier gate uses current marks to calculate active marked equity.
        self._current_btc_mark = self._latest_marks[self.config.btc_id]
        self._current_sol_mark = self._latest_marks[self.config.sol_id]
        if self.step == 0:
            intent = Intent("hl-stageg-entry", "hl-stageg-lifecycle", "BTC_ENTRY", 0, 1, quantity=0.01)
        else:
            intent = Intent("hl-stageg-exit", "hl-stageg-lifecycle", "BTC_REDUCE", 0, -1, quantity=0.01, limit_price=self.exit_price)
        self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), None, 0, ts_now=tick.ts_event)
        self.step += 1


def test_public_instrument_stays_usd_quoted_and_model_fx_is_explicit() -> None:
    assert (HL_BTC.quote_currency, HL_BTC.settlement_currency) == (USD, USDC)
    fx_pair, fx_quote = model_fx_pair_and_quote()
    assert (fx_pair.base_currency, fx_pair.quote_currency) == (USD, USDC)
    assert fx_quote.bid_price.as_decimal() == fx_quote.ask_price.as_decimal() == 1


def test_native_money_reads_usdc_account_for_usd_quote_and_never_uses_seed() -> None:
    usd_quoted = _perpetual("BTC-USD", BTC, "0.1", "0.00001", quote=USD)
    assert usd_quoted.quote_currency == USD
    account = SimpleNamespace(
        base_currency=USDC,
        balance_total=lambda currency: Money(Decimal("8765"), USDC) if currency == USDC else None,
        balance_free=lambda currency: Money(Decimal("7654"), USDC) if currency == USDC else None,
    )
    assert _native_account_money(account) == Decimal("8765")
    assert _native_account_money(account, free=True) == Decimal("7654")
    cache = SimpleNamespace(
        account_for_venue=lambda venue: account,
        instrument=lambda instrument_id: HL_BTC,
        positions_open=lambda: [],
    )
    strategy = SimpleNamespace(config=SimpleNamespace(btc_id=BTC_PERP, sol_id=SOL_PERP, active_seed=Decimal("10000")), cache=cache)
    btc_mark = SimpleNamespace(price=Decimal("60000"))
    sol_mark = SimpleNamespace(price=Decimal("150"))
    assert WaveOverlayStrategy._active_marked(strategy, btc_mark, sol_mark) == 8765.0
    cache.account_for_venue = lambda venue: None
    with pytest.raises(ValueError, match="NATIVE_ACCOUNT_OR_INSTRUMENT_MISSING"):
        WaveOverlayStrategy._active_marked(strategy, btc_mark, sol_mark)


async def _run_lifecycle(journal_path, *, losing: bool = False) -> tuple[AttachedStageGEntryExitProbe, PaperRuntime, TradingNode]:
    candidate = load_candidate(ROOT / "configs/stage-g-v1.json").candidate
    gate = cross_venue_stage_g_gate(
        candidate=candidate,
        warmup_manifest=ROOT / "var/data/stageg-bybit-warmup-20260923-verified3/manifest.json",
        strategy_path=ROOT / "coinmaster/strategy/wave_overlay.py",
        profile_root=ROOT,
        now_ns=1_790_121_600_000_000_000,
    )
    assert gate.attachable is True
    assert gate.funding_state == "OBSERVED_MODELLED_UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT"
    profile = HyperliquidVenueProfile.from_snapshot(ROOT, environment=HyperliquidProfileEnvironment.MAINNET)
    runtime = PaperRuntime(journal_path, "hl-stageg-lifecycle", 10**20)
    runtime.acquire()
    runtime.snapshot(ts_ns=1, positions=[], orders=[], funding_event_ids=[])
    hooks = LifecycleHooks(runtime)
    policy = HyperliquidSandboxMarginPolicy(profile, SANDBOX_LEVERAGES, SANDBOX_MARK_MAX_AGE_NS)
    daily = BarType(
        InstrumentId.from_str("BTCUSDT-LINEAR.BYBIT"),
        BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL,
    )
    sol_daily = BarType(
        InstrumentId.from_str("SOLUSDT-LINEAR.BYBIT"),
        BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL,
    )
    strategy = AttachedStageGEntryExitProbe(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP, sol_id=SOL_PERP, btc_bar_type=daily, sol_bar_type=sol_daily,
        btc_mark_data_type=venue_mark_data_type(BTC_PERP), sol_mark_data_type=venue_mark_data_type(SOL_PERP),
        mark_client_id=ClientId("HYPERLIQUID-MAINNET-DATA"), live_mark_client_id=ClientId("HYPERLIQUID-MAINNET-DATA"),
        active_seed=Decimal("10000"), margin_policy=policy, candidate=candidate,
        entries_enabled=True, entries_gate=lambda: True, event_sink=hooks.record_event, submission_sink=hooks,
        btc_signal_id=InstrumentId.from_str("BTCUSDT-LINEAR.BYBIT"), sol_signal_id=InstrumentId.from_str("SOLUSDT-LINEAR.BYBIT"),
        execution_policy_hash=gate.execution_policy_hash,
        execution_policy_version="hl-mainnet-public-data-native-sandbox-v1",
    ))
    strategy.exit_price = 59990.0 if losing else 60010.0
    config = TradingNodeConfig(
        environment=Environment.LIVE, trader_id="HL-STAGEG-LIFECYCLE-PROBE", logging=LoggingConfig(log_level="ERROR"),
        exec_engine=LiveExecEngineConfig(reconciliation=False),
        exec_clients={"SANDBOX": SandboxExecutionClientConfig(
            venue="HYPERLIQUID", starting_balances=["10000 USDC"], base_currency="USDC",
            leverages=dict(SANDBOX_LEVERAGES), use_reduce_only=True,
            routing=RoutingConfig(venues=frozenset({"HYPERLIQUID"})),
        )},
    )
    node = TradingNode(config=config, loop=asyncio.get_running_loop())
    node.add_exec_client_factory("SANDBOX", HyperliquidUsdcSandboxFactory)
    node.build()
    node.cache.add_instrument(HL_BTC)
    node.cache.add_instrument(HL_SOL)
    fx_pair, fx_quote = model_fx_pair_and_quote()
    node.cache.add_instrument(fx_pair)
    node.cache.add_quote_tick(fx_quote)
    assert model_fx_ready(node.cache)
    node.trader.add_strategy(strategy)
    await node.kernel.start_async()
    quotes = (
        (_quote(BTC_PERP, "59999.0", "60000.0", 1), _quote(BTC_PERP, "59980.0", "59981.0", 2), _quote(BTC_PERP, "59991.0", "59992.0", 3))
        if losing else
        (_quote(BTC_PERP, "59999.0", "60000.0", 1), _quote(BTC_PERP, "60001.0", "60002.0", 2), _quote(BTC_PERP, "60011.0", "60012.0", 3))
    )
    for tick in quotes:
        node.kernel.data_engine.process(tick)
        await asyncio.sleep(0.05)
        if tick.ts_event == 1:
            account = node.cache.account_for_venue(HYPERLIQUID)
            strategy.entry_money = {
                "total": account.balance_total(USDC).as_decimal(),
                "free": account.balance_free(USDC).as_decimal(),
                "locked": account.balance_locked(USDC).as_decimal(),
                "positions": len(node.cache.positions_open()),
            }
            # A later public provider refresh must retain its canonical USD
            # quote; the native fee model still posts USDC on the maker fill.
            node.kernel.data_engine.process(HL_BTC)
            await asyncio.sleep(0.05)
            assert node.cache.instrument(BTC_PERP).quote_currency == USD
    return strategy, runtime, node


def test_hl_stageg_configured_native_sandbox_entry_exit_fees_account_and_manage_only_restart(tmp_path) -> None:
    """The actual sealed attachment must remain Sandbox-only and restart-safe."""
    async def scenario():
        strategy, runtime, node = await _run_lifecycle(tmp_path / "hl-stageg.sqlite")
        try:
            fills = node.trader.generate_order_fills_report()
            account = node.trader.generate_account_report(HYPERLIQUID)
            assert len(fills) == 2
            assert node.cache.positions_open() == []
            assert not account.empty
            assert [item["instrument"] for item in strategy.fill_audit] == [str(BTC_PERP), str(BTC_PERP)]
            assert [item["action"] for item in strategy.fill_audit] == ["BTC_ENTRY", "BTC_REDUCE"]
            assert all(Decimal(item["commission"]) > 0 for item in strategy.fill_audit)
            assert [item["native_liquidity_side"] for item in strategy.fill_audit] == ["TAKER", "MAKER"]
            assert [Decimal(item["commission"]) for item in strategy.fill_audit] == [
                Decimal("600.00") * Decimal("0.00045"),
                Decimal("600.10") * Decimal("0.00015"),
            ]
            assert all(item["commission_currency"] == "USDC" for item in strategy.fill_audit)
            assert strategy.entry_money == {
                "total": Decimal("9999.73"),
                "free": Decimal("9999.54"),
                "locked": Decimal("0.19"),
                "positions": 1,
            }
            native_account = node.cache.account_for_venue(HYPERLIQUID)
            expected_total = Decimal("10000") + Decimal("0.01") * Decimal("10") - sum(
                Decimal(item["commission"]) for item in strategy.fill_audit
            )
            assert native_account.balance_total(USDC).as_decimal() == expected_total
            assert native_account.balance_free(USDC).as_decimal() == expected_total
            assert native_account.balance_locked(USDC).as_decimal() == 0
            assert runtime.pending_submissions() == []

            # A durable position copied from the actual native entry identity
            # must not be erased merely because a new Sandbox cache starts
            # empty. This is the supported restart contract for local Sandbox.
            restart_path = tmp_path / "restart.sqlite"
            crashed = PaperRuntime(restart_path, "hl-stageg-lifecycle", 10**20)
            crashed.acquire()
            crashed.snapshot(ts_ns=1, positions=[{"instrument_id": str(BTC_PERP), "signed_quantity": "0.01000"}], orders=[], funding_event_ids=[])
            crashed.close()
            restarted = PaperRuntime(restart_path, "hl-stageg-lifecycle", 10**20)
            restarted.acquire()
            assert restarted.recovery_state() == "MANAGE_ONLY_DURABLE_OPEN_STATE"
            assert not restarted.reconcile(positions=[], orders=[])
            restarted.close()
        finally:
            runtime.close()
            await node.kernel.stop_async()
            node.kernel.dispose()

    asyncio.run(scenario())



@pytest.mark.parametrize("fail_exit", [False, True])
def test_hl_stageg_native_sandbox_deposit_exit_shares_durable_journal(tmp_path, fail_exit) -> None:
    """Real HL-ID Sandbox fills, native equity and one PaperRuntime own the latch."""
    async def scenario() -> None:
        candidate = load_candidate(ROOT / "configs/stage-g-v1.json").candidate
        profile = HyperliquidVenueProfile.from_snapshot(ROOT, environment=HyperliquidProfileEnvironment.MAINNET)
        runtime = PaperRuntime(tmp_path / "stageg-deposit.sqlite", "hl-stageg-deposit", 10**20, require_native_cash=True)
        runtime.acquire()
        runtime.snapshot(
            ts_ns=1, positions=[], orders=[], funding_event_ids=[],
            native_account_total="10000", strategy_restartable=True,
        )
        hooks = LifecycleHooks(runtime)
        generic_kinds = []
        def generic_event(event_id, kind):
            generic_kinds.append(kind)
            return hooks.record_event(event_id, kind)
        policy = HyperliquidSandboxMarginPolicy(profile, SANDBOX_LEVERAGES, SANDBOX_MARK_MAX_AGE_NS)

        class DepositProbe(WaveOverlayStrategy):
            def __init__(self, config):
                super().__init__(config)
                self.quotes = 0
                self.exit_checks = 0
                self.exit_attempts = 0

            def market_exit(self):
                self.exit_attempts += 1
                if fail_exit:
                    raise RuntimeError("NATIVE_EXIT_FAILED")
                return super().market_exit()

            def on_quote_tick(self, tick):
                if tick.instrument_id != self.config.btc_id or self.quotes >= 3:
                    return
                self.on_mark_price(MarkPriceUpdate(
                    self.config.btc_id, tick.bid_price, tick.ts_event, tick.ts_init,
                ))
                self.on_mark_price(MarkPriceUpdate(
                    self.config.sol_id, Price.from_str("150.00"), tick.ts_event, tick.ts_init,
                ))
                self._current_btc_mark = self._latest_marks[self.config.btc_id]
                self._current_sol_mark = self._latest_marks[self.config.sol_id]
                self.quotes += 1
                if self.quotes == 1:
                    self._domain.episode = Episode(
                        "deposit-episode", 1, 10000, 1.0, wave_levels=(0.1, 0.2, 0.3),
                    )
                    intent = Intent("deposit-entry", "deposit-episode", "BTC_ENTRY", None, 1, quantity=0.1)
                    self._domain.episode.pending[intent.id] = intent
                    self._submit_intent(
                        intent, float(tick.bid_price), float(tick.ask_price),
                        None, 0, ts_now=tick.ts_event,
                    )
                elif self.quotes == 2:
                    super().on_quote_tick(tick)
                else:
                    self.exit_checks += 1
                    self._deposit_check()

        config = WaveOverlayStrategyConfig(
            btc_id=BTC_PERP, sol_id=SOL_PERP,
            btc_bar_type=BarType(
                InstrumentId.from_str("BTCUSDT-LINEAR.BYBIT"),
                BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL,
            ),
            sol_bar_type=BarType(
                InstrumentId.from_str("SOLUSDT-LINEAR.BYBIT"),
                BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL,
            ),
            btc_mark_data_type=venue_mark_data_type(BTC_PERP),
            sol_mark_data_type=venue_mark_data_type(SOL_PERP),
            mark_client_id=ClientId("HYPERLIQUID-MAINNET-DATA"),
            live_mark_client_id=ClientId("HYPERLIQUID-MAINNET-DATA"),
            active_seed=Decimal("10000"), margin_policy=policy, candidate=candidate,
            entries_enabled=True, entries_gate=lambda: runtime.entry_control_state() == "RUNNING",
            event_sink=generic_event, native_fill_sink=runtime.record_native_fill, submission_sink=hooks,
            market_exit_time_in_force=TimeInForce.IOC, market_exit_reduce_only=True,
            deposit_runtime=runtime, deposit_instance_id="hl-stageg-deposit",
            deposit_account_id="HYPERLIQUID-001",
            deposit_equity_reader=lambda strategy: native_equity(
                strategy.cache, strategy._latest_marks, now_ns=time.time_ns(),
            ),
            deposit_initialization_allowed=lambda: True,
        )
        strategy = DepositProbe(config)
        node = TradingNode(config=TradingNodeConfig(
            environment=Environment.LIVE, trader_id="HL-STAGEG-DEPOSIT-PROBE",
            logging=LoggingConfig(log_level="ERROR"),
            exec_engine=LiveExecEngineConfig(reconciliation=False),
            exec_clients={"SANDBOX": SandboxExecutionClientConfig(
                venue="HYPERLIQUID", starting_balances=["10000 USDC"], base_currency="USDC",
                leverages=dict(SANDBOX_LEVERAGES), use_reduce_only=True,
                routing=RoutingConfig(venues=frozenset({"HYPERLIQUID"})),
            )},
        ), loop=asyncio.get_running_loop())
        node.add_exec_client_factory("SANDBOX", HyperliquidUsdcSandboxFactory)
        node.build()
        node.cache.add_instrument(HL_BTC)
        node.cache.add_instrument(HL_SOL)
        fx_pair, fx_quote = model_fx_pair_and_quote()
        node.cache.add_instrument(fx_pair)
        node.cache.add_quote_tick(fx_quote)
        node.trader.add_strategy(strategy)
        await node.kernel.start_async()
        server = thread = None
        try:
            assert strategy._deposit_check()
            runtime.entry_control_command("pause-new-entries", "set-limit")
            runtime.snapshot(
                ts_ns=time.time_ns(), positions=[], orders=[], funding_event_ids=[],
                native_account_total="10000", strategy_restartable=True,
            )
            if fail_exit:
                set_result = strategy.apply_deposit_control(
                    "set-deposit-protection", "limit-one", drawdown_limit_percent=1,
                )
                assert set_result["drawdown_limit_percent"] == 1
                runtime.entry_control_command("resume-new-entries", "resume-after-limit")
            else:
                # The real control handler schedules the command on this attached native loop.
                # The sidecar is replaceable while the same TradingNode remains alive.
                import os
                import threading
                from coinmaster.api.runtime_sidecar import create_runtime_app
                from coinmaster.ops.hyperliquid_testnet_worker import TestnetWorker, create_status_server
                from test_runtime_sidecar import _ready_hl_projection

                class AttachedWorker:
                    instance = SimpleNamespace(instance_id="hl-stageg-testnet")
                    run_epoch = "attached-deposit-probe"
                    deposit_control = TestnetWorker.deposit_control

                    def __init__(self):
                        self.runtime = runtime
                        self.native = SimpleNamespace(strategy=strategy, node=node, loop=asyncio.get_running_loop())

                    def projection(self):
                        body = _ready_hl_projection(instance_id=self.instance.instance_id)
                        # Use this attached node's native cache and money model; the
                        # loopback /fills endpoint reads the same durable journal.
                        body["positions"], body["orders"] = HyperliquidTestnetNode.sandbox_snapshot(
                            SimpleNamespace(node=node),
                        )
                        body["account"] = native_money_projection(
                            strategy.cache, strategy._latest_marks, now_ns=time.time_ns(),
                        )
                        body["events"], body["event_cursor"] = runtime.projection_events(100)
                        body["entry_control"] = {"state": runtime.entry_control_state(), "capability": "READY"}
                        body["deposit_protection"] = strategy.deposit_projection()
                        return body

                worker = AttachedWorker()
                server = create_status_server(worker, port=0, control_token="worker-secret")
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                trader_pid, trader_identity = os.getpid(), id(node)
                api_url = f"http://127.0.0.1:{server.server_address[1]}"

                def sidecar():
                    return create_runtime_app(
                        database=str(tmp_path / "missing.sqlite"),
                        control_database=str(tmp_path / "control.sqlite"),
                        token="operator-secret", hl_stageg_status_url=api_url,
                        hl_stageg_control_token="worker-secret",
                    )

                async def api_call(app, method, path, body=None, *, authorized=True, command_key=None):
                    import json
                    headers = [(b"host", b"localhost"), (b"content-type", b"application/json")]
                    if authorized:
                        headers.append((b"authorization", b"Bearer operator-secret"))
                    if command_key:
                        headers.append((b"idempotency-key", command_key.encode()))
                    scope = {
                        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                        "scheme": "http", "method": method, "path": path, "raw_path": path.encode(),
                        "query_string": b"", "headers": headers, "server": ("localhost", 80),
                        "client": ("127.0.0.1", 4321), "root_path": "",
                    }
                    payload = json.dumps(body).encode() if body is not None else b""
                    messages = []
                    received = False

                    async def receive():
                        nonlocal received
                        if not received:
                            received = True
                            return {"type": "http.request", "body": payload, "more_body": False}
                        return {"type": "http.disconnect"}

                    async def send(message):
                        messages.append(message)

                    await app(scope, receive, send)
                    start = next(item for item in messages if item["type"] == "http.response.start")
                    response = b"".join(item.get("body", b"") for item in messages if item["type"] == "http.response.body")
                    return start["status"], json.loads(response)

                async def relay(app, method, path, body=None, *, authorized=True, command_key=None):
                    # Sidecar HTTP and worker HTTP block; keep native callbacks running.
                    return await asyncio.to_thread(
                        lambda: asyncio.run(api_call(app, method, path, body, authorized=authorized, command_key=command_key)),
                    )

                app = sidecar()
                path = "/api/v1/instances/hl-stageg-testnet/controls/set-deposit-protection"
                command = {"idempotency_key": "limit-one-" + "a" * 24, "drawdown_limit_percent": 1}
                assert (await relay(app, "POST", path, command, authorized=False))[0] == 401
                status, applied = await relay(app, "POST", path, command)
                assert status == 200 and applied["status"] == "APPLIED"
                assert applied["deposit_protection"]["drawdown_limit_percent"] == 1
                assert strategy.deposit_projection()["threshold_equity"] == "9900"
                # Recreate the ASGI app; trader identity and command state survive.
                app = sidecar()
                status, projection = await relay(app, "GET", "/api/v1/instances/hl-stageg-testnet")
                assert status == 200
                assert projection["deposit_protection"]["drawdown_limit_percent"] == 1
                assert projection["deposit_protection"]["threshold_equity"] == "9900"
                assert os.getpid() == trader_pid and id(node) == trader_identity and node.is_running()
                status, resumed = await relay(
                    app, "POST", "/api/v1/instances/hl-stageg-testnet/controls/resume-new-entries",
                    command_key="resume-after-limit-" + "b" * 24,
                )
                assert status == 200 and resumed["entry_control"] == "RUNNING"
                assert runtime.entry_control_state() == "RUNNING"

            node.kernel.data_engine.process(_quote(BTC_PERP, "59999.0", "60000.0", time.time_ns()))
            await asyncio.sleep(0.1)
            assert len(node.cache.positions_open()) == 1
            assert strategy.deposit_projection()["state"] == "ARMED"
            if not fail_exit:
                status, opened = await relay(app, "GET", "/api/v1/instances/hl-stageg-testnet")
                assert status == 200 and opened["projection_state"] == "READY"
                assert opened["positions"] == [{"instrument_id": str(BTC_PERP), "signed_quantity": "0.1", "average_entry_price": "60000.0", "provenance": "SANDBOX"}]
                assert opened["orders"] == []
                assert opened["account"]["native_cash"] == str(node.cache.account_for_venue(HYPERLIQUID).balance_total(USDC).as_decimal())
                status, first_fills = await relay(app, "GET", "/api/v1/instances/hl-stageg-testnet/fills")
                assert status == 200 and len(first_fills["fills"]) == 1
                assert first_fills["fills"][0]["trade_id"] == runtime.native_fill_details()[0]["trade_id"]
            node.kernel.data_engine.process(_quote(BTC_PERP, "59999.0", "60000.0", time.time_ns()))
            await asyncio.sleep(0.1)
            assert len(node.cache.orders_open()) == 3
            assert len(runtime.pending_submissions()) == 3
            assert runtime.entry_control_state() == "RUNNING"
            if not fail_exit:
                status, working = await relay(app, "GET", "/api/v1/instances/hl-stageg-testnet")
                assert status == 200 and working["deposit_protection"]["state"] == "ARMED"
                assert working["deposit_protection"]["threshold_equity"] == "9900"
                assert (await relay(app, "GET", "/api/v1/instances/hl-stageg-testnet", authorized=False))[0] == 401
                assert working["positions"] == opened["positions"]
                assert {item["client_order_id"] for item in working["orders"]} == {
                    str(order.client_order_id) for order in node.cache.orders_open()
                }
                assert len(working["orders"]) == 3
                assert all(item["reduce_only"] and item["provenance"] == "SANDBOX" for item in working["orders"])
                native_orders = {str(order.client_order_id): order for order in node.cache.orders_open()}
                for item in working["orders"]:
                    native = native_orders[item["client_order_id"]]
                    assert item["side"] == native.side.name == "SELL"
                    assert item["order_type"] == native.order_type.name == "LIMIT"
                    assert item["time_in_force"] == native.time_in_force.name
                    assert item["price"] == str(native.price)
                    assert item["quantity"] == str(native.quantity)
                    assert item["filled_quantity"] == str(native.filled_qty)
                    assert item["leaves_quantity"] == str(native.leaves_qty)
                    assert item["status"] == native.status.name == "ACCEPTED"
                    assert item["post_only"] is native.is_post_only
                    assert item["account_id"] == str(native.account_id)
                    assert item["venue_order_id"] == (str(native.venue_order_id) if native.venue_order_id else None)
                    assert item["submitted_at_ns"] == (native.ts_submitted or None)
                    assert item["updated_at_ns"] == (native.ts_last or None)
                assert Decimal(working["account"]["equity"]) == native_equity(
                    strategy.cache, strategy._latest_marks, now_ns=time.time_ns(),
                )
                assert working["entry_control"]["state"] == "RUNNING"
            node.kernel.data_engine.process(_quote(BTC_PERP, "58899.0", "58900.0", time.time_ns()))
            await asyncio.sleep(0.1)

            fills = node.trader.generate_order_fills_report()
            expected_state = "EXIT_INCOMPLETE" if fail_exit else "TRIPPED_FLAT"
            assert strategy.exit_checks == strategy.exit_attempts == 1
            assert len(fills) == (1 if fail_exit else 2)
            assert bool(node.cache.positions_open()) == fail_exit
            assert len(node.cache.orders_open()) == (3 if fail_exit else 0)
            assert node.cache.orders_inflight() == []
            assert len(runtime.pending_submissions()) == (3 if fail_exit else 0)
            assert runtime.entry_control_state() == ("RUNNING" if fail_exit else "PAUSED")
            assert runtime.db.execute(
                "SELECT COUNT(*) FROM paper_command_audit WHERE command='pause-new-entries'"
            ).fetchone()[0] == (1 if fail_exit else 2)
            assert [item["action"] for item in strategy.fill_audit] == (
                ["BTC_ENTRY"] if fail_exit else ["BTC_ENTRY", "MARKET_EXIT"]
            )
            assert all(Decimal(item["commission"]) > 0 for item in strategy.fill_audit)
            assert strategy.deposit_projection()["state"] == expected_state
            saved = runtime.deposit_protection_state(
                instance_id="hl-stageg-deposit", account_id="HYPERLIQUID-001",
            )
            assert saved["latched"] and saved["exit_state"] == expected_state
            assert len([item for item in runtime.events() if item["kind"] == "fill"]) == len(fills)
            assert "fill" not in generic_kinds  # No second event-sink write.
            details = runtime.native_fill_details()
            assert len(details) == len(fills)
            assert len({item["trade_id"] for item in details}) == len(details)
            assert all(item["instrument_id"] == str(BTC_PERP) and item["order_side"] in {"BUY", "SELL"} for item in details)
            assert all(item["quantity"] and item["price"] and item["commission_currency"] == "USDC" for item in details)
            assert all(item["ts_event_ns"] is not None and item["native_event_id"] is not None for item in details)
            assert node.cache.account_for_venue(HYPERLIQUID).balance_total(USDC).as_decimal() < Decimal("10000")
            if not fail_exit:
                from coinmaster.api.runtime_sidecar import HlStagegProjection
                HlStagegProjection.model_validate(worker.projection())
                status, tripped = await relay(app, "GET", "/api/v1/instances/hl-stageg-testnet")
                assert status == 200 and tripped["projection_state"] == "READY", tripped
                assert tripped["positions"] == [] and tripped["orders"] == []
                assert tripped["deposit_protection"]["state"] == "TRIPPED_FLAT"
                assert tripped["deposit_protection"]["drawdown_limit_percent"] == 1
                assert tripped["deposit_protection"]["trigger"]["reason"] == "DEPOSIT_DRAWDOWN_LIMIT"
                assert tripped["deposit_protection"]["trigger"]["threshold_equity"] == "9900"
                assert tripped["entry_control"]["state"] == "PAUSED"
                assert tripped["account"]["native_cash"] == str(node.cache.account_for_venue(HYPERLIQUID).balance_total(USDC).as_decimal())
                assert Decimal(tripped["account"]["fees"]) == sum(
                    (Decimal(item["commission"]) for item in strategy.fill_audit), Decimal("0"),
                )
                status, closed_fills = await relay(app, "GET", "/api/v1/instances/hl-stageg-testnet/fills")
                assert status == 200 and len(closed_fills["fills"]) == 2
                assert {item["trade_id"] for item in closed_fills["fills"]} == {
                    item["trade_id"] for item in runtime.native_fill_details()
                }
                assert os.getpid() == trader_pid and id(node) == trader_identity and node.is_running()
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            await node.kernel.stop_async()
            node.kernel.dispose()
            runtime.close()

    asyncio.run(scenario())
    reopened = PaperRuntime(
        tmp_path / "stageg-deposit.sqlite", "hl-stageg-deposit", 10**20, require_native_cash=True,
    )
    reopened.acquire()
    try:
        saved = reopened.deposit_protection_state(
            instance_id="hl-stageg-deposit", account_id="HYPERLIQUID-001",
        )
        assert saved["latched"] and saved["exit_state"] == ("EXIT_INCOMPLETE" if fail_exit else "TRIPPED_FLAT")
        assert len(reopened.pending_submissions()) == (3 if fail_exit else 0)
        assert reopened.entry_control_state() == ("RUNNING" if fail_exit else "PAUSED")
        if not fail_exit:
            reopened.entry_control_command("resume-new-entries", "resume-after-dp")
            assert reopened.entry_control_state() == "RUNNING"
            assert reopened.deposit_protection_state(
                instance_id="hl-stageg-deposit", account_id="HYPERLIQUID-001",
            )["latched"]
    finally:
        reopened.close()

def test_deposit_post_market_exit_waits_for_created_native_order_visibility_gap() -> None:
    """A premature Nautilus finalizer cannot turn an unknown exit into failure."""
    writes = []
    deposit = SimpleNamespace(latched=True, exit_state="EXITING")
    probe = SimpleNamespace(
        config=SimpleNamespace(deposit_runtime=SimpleNamespace(pending_submissions=lambda: [])),
        _deposit=deposit, _deposit_exit_started=True, _deposit_exit_orders={"exit-order"},
        cache=SimpleNamespace(positions_open=lambda: [object()], orders_open=lambda: [], orders_inflight=lambda: []),
        clock=SimpleNamespace(timestamp_ns=lambda: 10),
        _persist_deposit=lambda *args: writes.append(args),
    )
    probe._reconcile_deposit_flat = lambda: WaveOverlayStrategy._reconcile_deposit_flat(probe)
    WaveOverlayStrategy.post_market_exit(probe)
    assert deposit.exit_state == "EXITING" and writes == []
    probe._deposit_exit_orders.clear()
    WaveOverlayStrategy.post_market_exit(probe)
    assert deposit.exit_state == "EXIT_INCOMPLETE"
    assert writes == [("EXIT_INCOMPLETE", "deposit:exit-no-submit:10", 10)]


def test_native_usdc_fee_model_preserves_tiny_partial_maker_precision() -> None:
    model = HyperliquidUsdcFeeModel()
    order = SimpleNamespace(liquidity_side=LiquiditySide.MAKER)
    commission = model.get_commission(
        order, Quantity.from_str("0.00001"), Price.from_str("60000.0"), HL_BTC,
    )
    assert commission.currency == USDC
    assert commission.as_decimal() == Decimal("0.00009")
    assert sum((commission.as_decimal() for _ in range(2)), Decimal("0")) == Decimal("0.00018")
    partial = model.get_commission(
        order, Quantity.from_str("0.00500"), Price.from_str("60000.1"), HL_BTC,
    )
    assert partial.as_decimal() == Decimal("0.04500008")


def test_model_fx_missing_blocks_native_order_gate() -> None:
    cache = SimpleNamespace(get_xrate=lambda venue, source, target, side: 0.0)
    assert not model_fx_ready(cache)
    with pytest.raises(RuntimeError, match="HL_SANDBOX_MODEL_FX_MISSING"):
        HyperliquidUsdcSandboxExecutionClient.submit_order(
            SimpleNamespace(_cache=cache), SimpleNamespace(order=SimpleNamespace(instrument_id=BTC_PERP)),
        )
    cache.get_xrate = lambda venue, source, target, side: 1.0
    assert model_fx_ready(cache)


def test_native_losing_maker_exit_reconciles_usdc_cash(tmp_path) -> None:
    async def scenario():
        strategy, runtime, node = await _run_lifecycle(tmp_path / "losing.sqlite", losing=True)
        try:
            fills = strategy.fill_audit
            assert [item["native_liquidity_side"] for item in fills] == ["TAKER", "MAKER"]
            assert [Decimal(item["commission"]) for item in fills] == [Decimal("0.27"), Decimal("0.089985")]
            assert node.cache.positions_open() == []
            account = node.cache.account_for_venue(HYPERLIQUID)
            expected = Decimal("10000") - Decimal("0.10") - Decimal("0.27") - Decimal("0.089985")
            assert account.balance_total(USDC).as_decimal() == expected
            assert account.balance_free(USDC).as_decimal() == expected
            assert account.balance_locked(USDC).as_decimal() == 0
        finally:
            runtime.close()
            await node.kernel.stop_async()
            node.kernel.dispose()

    asyncio.run(scenario())


def test_attached_hl_two_episode_native_btc_sol_lifecycle_uses_one_journal(tmp_path) -> None:
    """Real Sandbox fills and production snapshots bridge TP rights to SOL and a later episode."""
    async def scenario() -> None:
        runtime = PaperRuntime(tmp_path / "two-episode.sqlite", "attached-two-episode", 10**20)
        runtime.acquire()
        runtime.snapshot(ts_ns=1, positions=[], orders=[], funding_event_ids=[], native_account_total="10000", strategy_restartable=True)
        hooks = LifecycleHooks(runtime)
        candidate = load_candidate(ROOT / "configs/stage-g-v1.json").candidate
        profile = HyperliquidVenueProfile.from_snapshot(ROOT, environment=HyperliquidProfileEnvironment.MAINNET)
        policy = HyperliquidSandboxMarginPolicy(profile, SANDBOX_LEVERAGES, SANDBOX_MARK_MAX_AGE_NS)

        class Probe(WaveOverlayStrategy):
            def __init__(self, config):
                super().__init__(config)
                self.next_intent = None
                self.cycle = 0

            def on_start(self):
                self.subscribe_quote_ticks(self.config.btc_id)

            def on_quote_tick(self, tick):
                self.on_mark_price(MarkPriceUpdate(self.config.btc_id, Price.from_str("60000.0"), tick.ts_event, tick.ts_init))
                self.on_mark_price(MarkPriceUpdate(self.config.sol_id, Price.from_str("150.00"), tick.ts_event, tick.ts_init))
                self._current_btc_mark = self._latest_marks[self.config.btc_id]
                self._current_sol_mark = self._latest_marks[self.config.sol_id]
                self.cycle += 1
                if self.next_intent is not None:
                    intent, self.next_intent = self.next_intent, None
                    bid, ask = (float(tick.bid_price), float(tick.ask_price)) if intent.action.startswith("BTC") else (149.99, 150.01)
                    self._submit_intent(intent, bid, ask, 1.0, self.cycle, ts_now=tick.ts_event)
                else:
                    super().on_quote_tick(tick)

        config = WaveOverlayStrategyConfig(
            btc_id=BTC_PERP, sol_id=SOL_PERP,
            btc_bar_type=BarType(InstrumentId.from_str("BTCUSDT-LINEAR.BYBIT"), BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL),
            sol_bar_type=BarType(InstrumentId.from_str("SOLUSDT-LINEAR.BYBIT"), BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL),
            btc_mark_data_type=venue_mark_data_type(BTC_PERP), sol_mark_data_type=venue_mark_data_type(SOL_PERP),
            mark_client_id=ClientId("HYPERLIQUID-MAINNET-DATA"), active_seed=Decimal("10000"),
            candidate=candidate, margin_policy=policy, entries_enabled=True, entries_gate=lambda: True,
            event_sink=hooks.record_event, native_fill_sink=runtime.record_native_fill, submission_sink=hooks,
        )
        strategy = Probe(config)
        node = TradingNode(config=TradingNodeConfig(
            environment=Environment.LIVE, trader_id="HL-TWO-EPISODE-PROBE", logging=LoggingConfig(log_level="ERROR"),
            exec_engine=LiveExecEngineConfig(reconciliation=False),
            exec_clients={"SANDBOX": SandboxExecutionClientConfig(
                venue="HYPERLIQUID", starting_balances=["10000 USDC"], base_currency="USDC",
                leverages=dict(SANDBOX_LEVERAGES), use_reduce_only=True,
                routing=RoutingConfig(venues=frozenset({"HYPERLIQUID"})),
            )},
        ), loop=asyncio.get_running_loop())
        node.add_exec_client_factory("SANDBOX", HyperliquidUsdcSandboxFactory)
        node.build()
        node.cache.add_instrument(HL_BTC)
        node.cache.add_instrument(HL_SOL)
        pair, fx = model_fx_pair_and_quote()
        node.cache.add_instrument(pair)
        node.cache.add_quote_tick(fx)
        node.trader.add_strategy(strategy)

        async def btc_quote(bid: str, ask: str, ts: int) -> None:
            node.kernel.data_engine.process(_quote(BTC_PERP, bid, ask, ts))
            await asyncio.sleep(0.1)

        def native_snapshot(*, restartable: bool) -> None:
            # Exact production cache->journal path; a stale flat fixture must
            # never grant a SOL increase while acknowledged BTC TP orders rest.
            positions, orders = HyperliquidTestnetNode.sandbox_snapshot(SimpleNamespace(node=node))
            assert runtime.snapshot(
                ts_ns=time.time_ns(), positions=positions, orders=orders,
                funding_event_ids=runtime.funding_event_ids(), expected_revision=runtime.native_revision(),
                native_account_total=str(node.cache.account_for_venue(HYPERLIQUID).balance_total(USDC).as_decimal()),
                strategy_restartable=restartable, run_epoch="attached-two-episode",
            )

        await node.kernel.start_async()
        try:
            first = Episode("episode-one", 1, 10000, 1.0, wave_levels=(0.0001, 0.0002, 0.0003))
            strategy._domain.episode = first
            entry = Intent("first-entry", first.id, "BTC_ENTRY", None, 1, quantity=0.00167, decision_index=1)
            first.pending[entry.id] = entry
            strategy.next_intent = entry
            await btc_quote("59999.0", "60000.0", 1)
            assert [(row["action"], row["qty"]) for row in strategy.fill_audit] == [("BTC_ENTRY", "0.00167")]
            await btc_quote("60000.0", "60001.0", 2)
            assert sorted(str(order.price) for order in node.cache.orders_open()) == ["60006.0", "60012.0", "60018.0"]
            positions, orders = HyperliquidTestnetNode.sandbox_snapshot(SimpleNamespace(node=node))
            assert positions == [{
                "instrument_id": str(BTC_PERP), "signed_quantity": "0.00167",
                "average_entry_price": str(node.cache.positions_open()[0].avg_px_open),
            }]
            assert {order["price"] for order in orders} == {"60006.0", "60012.0", "60018.0"}
            assert all(order["side"] == "SELL" and order["order_type"] == "LIMIT"
                       and order["status"] == "ACCEPTED" and order["reduce_only"]
                       and order["post_only"] and order["filled_quantity"] == "0.00000"
                       for order in orders)

            node.kernel.data_engine.process(TradeTick(BTC_PERP, Price.from_str("60006.0"), Quantity.from_str("0.00010"), AggressorSide.BUYER, TradeId("ATTACHED-PART-ONE"), 3, 3))
            await asyncio.sleep(0.1)
            target = next(order for order in node.cache.orders_open() if order.has_price and str(order.price) == "60006.0")
            assert str(target.filled_qty) == "0.00010" and str(target.leaves_qty) == "0.00025"
            _, partial_orders = HyperliquidTestnetNode.sandbox_snapshot(SimpleNamespace(node=node))
            partial = next(order for order in partial_orders if order["client_order_id"] == str(target.client_order_id))
            assert (partial["price"], partial["quantity"], partial["filled_quantity"], partial["leaves_quantity"]) == (
                "60006.0", "0.00035", "0.00010", "0.00025",
            )
            confirmed = next(event for event in target.events if isinstance(event, OrderFilled))
            before_duplicate = (len(strategy.fill_audit), len(runtime.native_fill_details()), runtime.native_revision(), first.btc_open_qty)
            strategy.on_order_filled(confirmed)
            assert (len(strategy.fill_audit), len(runtime.native_fill_details()), runtime.native_revision(), first.btc_open_qty) == before_duplicate
            strategy.cancel_order(target)
            await asyncio.sleep(0.1)
            assert target.status.name == "CANCELED"
            await btc_quote("60005.0", "60007.0", 4)
            replacement = next(order for order in node.cache.orders_open() if order.has_price and str(order.price) == "60006.0")
            assert str(replacement.quantity) == "0.00025" and replacement.status.name == "ACCEPTED"
            _, replacement_orders = HyperliquidTestnetNode.sandbox_snapshot(SimpleNamespace(node=node))
            assert str(target.client_order_id) not in {order["client_order_id"] for order in replacement_orders}
            replaced = next(order for order in replacement_orders if order["client_order_id"] == str(replacement.client_order_id))
            assert (replaced["price"], replaced["quantity"], replaced["filled_quantity"], replaced["leaves_quantity"]) == (
                "60006.0", "0.00025", "0.00000", "0.00025",
            )
            node.kernel.data_engine.process(TradeTick(BTC_PERP, Price.from_str("60006.0"), Quantity.from_str("0.00025"), AggressorSide.BUYER, TradeId("ATTACHED-PART-TWO"), 5, 5))
            await asyncio.sleep(0.1)
            assert first.sol_right_fraction[0] == pytest.approx(1.0)

            native_snapshot(restartable=False)
            assert runtime.recovery_state() == "ACTIVE_OWNED_REDUCTIONS"
            assert runtime.health(time.time_ns()).safe_for_increase
            node.kernel.data_engine.process(QuoteTick(SOL_PERP, Price.from_str("149.99"), Price.from_str("150.01"), Quantity.from_str("1000.00"), Quantity.from_str("1000.00"), 6, 6))
            sol_add = strategy._domain._intent(first, "SOL_ADD", -first.side, 0, requested_notional=30)
            strategy.next_intent = sol_add
            await btc_quote("60000.0", "60001.0", 6)
            assert first.sol_qty == pytest.approx(0.2)
            two_positions, _ = HyperliquidTestnetNode.sandbox_snapshot(SimpleNamespace(node=node))
            assert {item["instrument_id"] for item in two_positions} == {str(BTC_PERP), str(SOL_PERP)}
            for item in two_positions:
                native = next(position for position in node.cache.positions_open() if str(position.instrument_id) == item["instrument_id"])
                assert item["average_entry_price"] == str(native.avg_px_open)
                assert Decimal(item["signed_quantity"]) == (
                    native.quantity.as_decimal() if native.is_long else -native.quantity.as_decimal()
                )
            # Make native SOL price PnL exceed USD's cent precision so cash
            # reconciliation tests realized PnL as well as exact USDC fees.
            node.kernel.data_engine.process(QuoteTick(
                SOL_PERP, Price.from_str("150.99"), Price.from_str("151.01"),
                Quantity.from_str("1000.00"), Quantity.from_str("1000.00"), 7, 7,
            ))
            await asyncio.sleep(0.1)
            day = datetime(1970, 1, 1, tzinfo=UTC)
            bar = DailyBar(day, day + timedelta(seconds=1), day + timedelta(seconds=1), 60000.0, 60000.0, 150.0)
            half = strategy._domain._sol_exits(first, Features(7, 1, 1.0, 0.0, 0.0, 1.0, 0.3), bar, 7, z=0.3)
            assert len(half) == 1 and half[0].action == "SOL_HALF_EXIT"
            strategy.next_intent = half[0]
            await btc_quote("60000.0", "60001.0", 7)
            assert first.sol_qty == pytest.approx(0.1) and first.sol_half_done
            full = strategy._domain._sol_exits(first, Features(8, 1, 1.0, 0.0, 0.0, 1.0, 0.1), bar, 8, z=0.1)
            assert len(full) == 1 and full[0].action == "SOL_EXIT"
            strategy.next_intent = full[0]
            await btc_quote("60000.0", "60001.0", 8)
            assert first.sol_qty == 0 and all(position.instrument_id != SOL_PERP for position in node.cache.positions_open())

            strategy._begin_forced_close("TEST_GROUP_CLOSE")
            await asyncio.sleep(0.1)
            await btc_quote("60000.0", "60001.0", 9)
            assert strategy._domain.episode is None
            assert node.cache.positions_open() == [] and node.cache.orders_open() == [] and runtime.pending_submissions() == []
            native_snapshot(restartable=True)
            assert runtime.recovery_state() == "FLAT_RESTART"

            second = Episode("episode-two", 1, 10000, 1.0, wave_levels=(0.0001, 0.0002, 0.0003))
            strategy._domain.episode = second
            entry_two = Intent("second-entry", second.id, "BTC_ENTRY", None, 1, quantity=0.00167, decision_index=10)
            second.pending[entry_two.id] = entry_two
            strategy.next_intent = entry_two
            await btc_quote("59999.0", "60000.0", 10)
            assert [(str(position.instrument_id), str(position.quantity)) for position in node.cache.positions_open()] == [(str(BTC_PERP), "0.00167")]
            await btc_quote("60000.0", "60001.0", 11)
            assert sorted(str(order.price) for order in node.cache.orders_open()) == ["60006.0", "60012.0", "60018.0"]
            node.kernel.data_engine.process(TradeTick(
                BTC_PERP, Price.from_str("60006.0"), Quantity.from_str("0.00035"),
                AggressorSide.BUYER, TradeId("ATTACHED-SECOND-TP"), 12, 12,
            ))
            await asyncio.sleep(0.1)
            assert second.sol_right_fraction[0] == pytest.approx(1.0)
            native_snapshot(restartable=False)
            assert runtime.health(time.time_ns()).safe_for_increase
            node.kernel.data_engine.process(QuoteTick(
                SOL_PERP, Price.from_str("149.99"), Price.from_str("150.01"),
                Quantity.from_str("1000.00"), Quantity.from_str("1000.00"), 13, 13,
            ))
            second_sol_add = strategy._domain._intent(second, "SOL_ADD", -second.side, 0, requested_notional=30)
            strategy.next_intent = second_sol_add
            await btc_quote("60000.0", "60001.0", 13)
            assert second.sol_qty == pytest.approx(0.2)
            assert {str(position.instrument_id) for position in node.cache.positions_open()} == {str(BTC_PERP), str(SOL_PERP)}
            node.kernel.data_engine.process(QuoteTick(
                SOL_PERP, Price.from_str("150.99"), Price.from_str("151.01"),
                Quantity.from_str("1000.00"), Quantity.from_str("1000.00"), 14, 14,
            ))
            await asyncio.sleep(0.1)
            second_half = strategy._domain._sol_exits(second, Features(14, 1, 1.0, 0.0, 0.0, 1.0, 0.3), bar, 14, z=0.3)
            assert len(second_half) == 1 and second_half[0].action == "SOL_HALF_EXIT"
            strategy.next_intent = second_half[0]
            await btc_quote("60000.0", "60001.0", 14)
            assert second.sol_qty == pytest.approx(0.1) and second.sol_half_done
            second_full = strategy._domain._sol_exits(second, Features(15, 1, 1.0, 0.0, 0.0, 1.0, 0.1), bar, 15, z=0.1)
            assert len(second_full) == 1 and second_full[0].action == "SOL_EXIT"
            strategy.next_intent = second_full[0]
            await btc_quote("60000.0", "60001.0", 15)
            assert second.sol_qty == 0 and all(position.instrument_id != SOL_PERP for position in node.cache.positions_open())
            strategy._begin_forced_close("TEST_SECOND_CLOSE")
            await asyncio.sleep(0.1)
            await btc_quote("60000.0", "60001.0", 16)
            assert strategy._domain.episode is None
            assert node.cache.positions_open() == [] and node.cache.orders_open() == [] and node.cache.orders_inflight() == []
            assert runtime.pending_submissions() == []
            assert len(runtime.all_submissions()) == 17
            assert all(row["state"] == "TERMINAL" for row in runtime.all_submissions())
            native_snapshot(restartable=True)
            assert runtime.recovery_state() == "FLAT_RESTART"

            fills = runtime.native_fill_details()
            assert len(fills) == len(strategy.fill_audit) == 13
            assert len({row["trade_id"] for row in fills}) == len(fills)
            assert [row["action"] for row in strategy.fill_audit] == [
                "BTC_ENTRY", "BTC_REDUCE", "BTC_REDUCE", "SOL_ADD", "SOL_HALF_EXIT", "SOL_EXIT",
                "FORCED_CLOSE", "BTC_ENTRY", "BTC_REDUCE", "SOL_ADD", "SOL_HALF_EXIT", "SOL_EXIT", "FORCED_CLOSE",
            ]
            assert [row["native_liquidity_side"] for row in strategy.fill_audit].count("MAKER") == 3
            assert [row["native_liquidity_side"] for row in strategy.fill_audit].count("TAKER") == 10
            fees = sum((Decimal(row["commission_amount"]) for row in fills), Decimal("0"))
            assert fees == sum((Decimal(row["commission"]) for row in strategy.fill_audit), Decimal("0"))
            assert fees == Decimal("0.22194063")
            positions = node.trader.generate_positions_report().to_dict("records")
            assert len(positions) == 4 and all(row["side"] == "FLAT" for row in positions)
            sol_positions = [row for row in positions if str(row["instrument_id"]) == str(SOL_PERP)]
            assert len(sol_positions) == 2
            assert all(Decimal(str(row["realized_pnl"]).split()[0]) == Decimal("-0.20") for row in sol_positions)
            realized = sum((Decimal(str(row["realized_pnl"]).split()[0]) for row in positions), Decimal("0"))
            account = node.cache.account_for_venue(HYPERLIQUID)
            cash = account.balance_total(USDC).as_decimal()
            assert cash == Decimal("10000") + realized - fees == Decimal("9999.37805937")
            assert account.balance_free(USDC).as_decimal() == cash
            assert account.balance_locked(USDC).as_decimal() == 0
            assert runtime.flat_native_cash() == cash
        finally:
            await node.kernel.stop_async()
            node.kernel.dispose()
            runtime.close()

    asyncio.run(scenario())
    reopened = PaperRuntime(tmp_path / "two-episode.sqlite", "attached-two-episode", 10**20)
    reopened.acquire()
    try:
        assert len(reopened.native_fill_details()) == 13
        assert reopened.pending_submissions() == []
        assert reopened.flat_native_cash() == Decimal("9999.37805937")
    finally:
        reopened.close()


@pytest.mark.parametrize("instrument,raw,expected", [
    (HL_BTC, "84583.5", "84584"),
    (HL_BTC, "84582.5", "84582"),
    (HL_BTC, "9999.9", "9999.9"),
    (HL_BTC, "99999.5", "100000"),
    (HL_SOL, "122.855", "122.86"),
    (HL_SOL, "1234.56", "1234.6"),
])
def test_hl_tp_native_price_equals_pinned_adapter_wire_price(instrument, raw, expected) -> None:
    native = _native_limit_price(instrument, Decimal(raw))
    wire = HyperliquidExecutionClient._round_to_significant_figures(None, native.as_decimal())
    assert native.as_decimal() == Decimal(expected) == wire


@pytest.mark.parametrize("side,raw,bid,ask,accepted,expected", [
    (-1, 84583.5, "84583.4", "84583.6", True, "84584"),
    (-1, 84583.4, "84583.3", "84583.6", False, None),
    (1, 84583.5, "84583.3", "84584.0", False, None),
    (1, 84582.5, "84582.0", "84583.0", True, "84582"),
])
def test_hl_tp_submit_checks_wire_equivalent_native_price_before_post_only(
    side, raw, bid, ask, accepted, expected,
) -> None:
    submitted = []
    canceled = []
    created = []
    durable_prices = []

    native_factory = OrderFactory(TraderId("TP-TESTER-001"), StrategyId("TP-TEST-001"), TestClock())

    def make_limit(**kwargs):
        created.append(kwargs)
        return native_factory.limit(**kwargs)

    position = SimpleNamespace(instrument_id=BTC_PERP, quantity=Quantity.from_str("0.01000"))
    fake = SimpleNamespace(
        config=SimpleNamespace(deposit_runtime=None, btc_id=BTC_PERP, sol_id=SOL_PERP),
        cache=SimpleNamespace(
            instrument=lambda _: HL_BTC,
            positions_open=lambda: [position],
            quote_tick=lambda _: _quote(BTC_PERP, bid, ask, 1),
        ),
        _domain=SimpleNamespace(on_parent_cancelled=canceled.append, on_parent_terminal=lambda _: None),
        order_factory=SimpleNamespace(limit=make_limit),
        _pending_by_order={}, _sigma_by_order={}, _decision_index_by_order={},
        _record_submission=lambda order, *args: durable_prices.append(str(order.price)) or True,
        submit_order=submitted.append,
    )
    intent = Intent("TP-intent", "TP-episode", "BTC_REDUCE", 0, side, quantity=0.005, limit_price=raw)
    WaveOverlayStrategy._submit_intent(fake, intent, float(bid), float(ask), None, 0, ts_now=1)
    if not accepted:
        assert created == submitted == durable_prices == []
        assert canceled == [intent.id]
    else:
        assert canceled == [] and len(submitted) == len(created) == 1
        kwargs = created[0]
        assert kwargs["post_only"] is True and kwargs["reduce_only"] is True
        assert kwargs["time_in_force"] == TimeInForce.GTC
        native = kwargs["price"].as_decimal()
        wire = HyperliquidExecutionClient._round_to_significant_figures(None, native)
        assert native == wire == Decimal(expected)
        assert Decimal(durable_prices[0]) == native
        # Capture the pinned adapters actual outbound submit arguments. No
        # signer, endpoint or connection is used by this fake WS boundary.
        outgoing = []

        class CapturingWS:
            def cache_cloid_mapping(self, *_):
                pass

            async def submit_order(self, _client, **fields):
                outgoing.append(fields)
                return None

        execution = SimpleNamespace(
            _check_time_in_force=lambda _: True,
            generate_order_submitted=lambda **_: None,
            _clock=TestClock(),
            _config=SimpleNamespace(normalize_prices=True),
            _round_to_significant_figures=lambda value: HyperliquidExecutionClient._round_to_significant_figures(None, value),
            _ws_client=CapturingWS(), _client=object(),
            _process_submit_reports=lambda _: None,
        )
        asyncio.run(HyperliquidExecutionClient._submit_order(
            execution, SimpleNamespace(order=submitted[0]),
        ))
        assert len(outgoing) == 1
        assert outgoing[0]["post_only"] is True and outgoing[0]["reduce_only"] is True
        assert Decimal(str(outgoing[0]["price"])) == native
        # Strict Info requires exact numeric equality with venue limitPx.
        assert native == Decimal(str(wire))


def test_native_market_order_snapshot_never_fabricates_limit_price() -> None:
    factory = OrderFactory(TraderId("TESTER-001"), StrategyId("SNAPSHOT-001"), TestClock())
    native = factory.market(
        instrument_id=BTC_PERP, order_side=OrderSide.BUY,
        quantity=Quantity.from_str("0.00010"), time_in_force=TimeInForce.IOC,
    )
    cache = SimpleNamespace(positions_open=lambda: [], orders_open=lambda: [native])
    positions, orders = HyperliquidTestnetNode.sandbox_snapshot(
        SimpleNamespace(node=SimpleNamespace(cache=cache)),
    )
    assert positions == []
    assert len(orders) == 1
    assert orders[0]["order_type"] == "MARKET"
    assert orders[0]["price"] is None
    assert orders[0]["submitted_at_ns"] is None
