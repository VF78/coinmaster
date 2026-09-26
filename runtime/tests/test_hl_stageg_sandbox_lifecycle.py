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
from decimal import Decimal
from types import SimpleNamespace

import pytest

from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.common import Environment
from nautilus_trader.config import LoggingConfig
from nautilus_trader.live.config import LiveExecEngineConfig, RoutingConfig, TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.currencies import BTC, SOL, USD, USDC
from nautilus_trader.model.data import BarSpecification, BarType, MarkPriceUpdate, QuoteTick
from nautilus_trader.model.enums import AggregationSource, BarAggregation, PriceType, LiquiditySide, TimeInForce
from nautilus_trader.model.identifiers import ClientId, InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import CryptoPerpetual
from nautilus_trader.model.objects import Money, Price, Quantity

from coinmaster.domain.wave_overlay import Intent
from coinmaster.ops.hyperliquid_testnet import (
    BTC_PERP,
    SOL_PERP,
    SANDBOX_LEVERAGES,
    SANDBOX_MARK_MAX_AGE_NS,
    LifecycleHooks,
    cross_venue_stage_g_gate,
)
from coinmaster.ops.hl_sandbox_money import SandboxLiveExecClientFactory as HyperliquidUsdcSandboxFactory, HyperliquidUsdcFeeModel, HyperliquidUsdcSandboxExecutionClient, model_fx_pair_and_quote, model_fx_ready, native_equity
from coinmaster.ops.paper import PaperRuntime
from coinmaster.ops.stage_g_config import load_candidate
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig, _native_account_money
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



def test_hl_stageg_native_sandbox_deposit_exit_shares_durable_journal(tmp_path) -> None:
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
        policy = HyperliquidSandboxMarginPolicy(profile, SANDBOX_LEVERAGES, SANDBOX_MARK_MAX_AGE_NS)

        class DepositProbe(WaveOverlayStrategy):
            def __init__(self, config):
                super().__init__(config)
                self.quotes = 0
                self.exit_checks = 0

            def on_quote_tick(self, tick):
                if tick.instrument_id != self.config.btc_id or self.quotes >= 2:
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
                    intent = Intent("deposit-entry", "deposit-episode", "BTC_ENTRY", 0, 1, quantity=0.1)
                    self._submit_intent(
                        intent, float(tick.bid_price), float(tick.ask_price),
                        None, 0, ts_now=tick.ts_event,
                    )
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
            event_sink=hooks.record_event, submission_sink=hooks,
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
        try:
            assert strategy._deposit_check()
            runtime.entry_control_command("pause-new-entries", "set-limit")
            runtime.snapshot(
                ts_ns=time.time_ns(), positions=[], orders=[], funding_event_ids=[],
                native_account_total="10000", strategy_restartable=True,
            )
            set_result = strategy.apply_deposit_control(
                "set-deposit-protection", "limit-one", drawdown_limit_percent=1,
            )
            assert set_result["drawdown_limit_percent"] == 1
            runtime.entry_control_command("resume-new-entries", "resume-after-limit")

            node.kernel.data_engine.process(_quote(BTC_PERP, "59999.0", "60000.0", time.time_ns()))
            await asyncio.sleep(0.1)
            assert len(node.cache.positions_open()) == 1
            assert strategy.deposit_projection()["state"] == "ARMED"
            node.kernel.data_engine.process(_quote(BTC_PERP, "58899.0", "58900.0", time.time_ns()))
            await asyncio.sleep(0.1)

            fills = node.trader.generate_order_fills_report()
            assert strategy.exit_checks == 1
            assert len(fills) == 2
            assert node.cache.positions_open() == []
            assert runtime.pending_submissions() == []
            assert [item["action"] for item in strategy.fill_audit] == ["BTC_ENTRY", "MARKET_EXIT"]
            assert all(Decimal(item["commission"]) > 0 for item in strategy.fill_audit)
            assert strategy.deposit_projection()["state"] == "TRIPPED_FLAT"
            saved = runtime.deposit_protection_state(
                instance_id="hl-stageg-deposit", account_id="HYPERLIQUID-001",
            )
            assert saved["latched"] and saved["exit_state"] == "TRIPPED_FLAT"
            assert len([item for item in runtime.events() if item["kind"] == "fill"]) == len(fills)
            assert node.cache.account_for_venue(HYPERLIQUID).balance_total(USDC).as_decimal() < Decimal("10000")
        finally:
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
        assert saved["latched"] and saved["exit_state"] == "TRIPPED_FLAT"
        assert reopened.pending_submissions() == []
    finally:
        reopened.close()

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
