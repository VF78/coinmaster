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
from decimal import Decimal
from types import SimpleNamespace

import pytest

from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.adapters.sandbox.factory import SandboxLiveExecClientFactory
from nautilus_trader.common import Environment
from nautilus_trader.config import LoggingConfig
from nautilus_trader.live.config import LiveExecEngineConfig, RoutingConfig, TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.currencies import BTC, SOL, USD, USDC
from nautilus_trader.model.data import BarSpecification, BarType, MarkPriceUpdate, QuoteTick
from nautilus_trader.model.enums import AggregationSource, BarAggregation, PriceType
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
        min_quantity=Quantity.from_str(step), min_notional=Money(Decimal("10"), USDC),
        margin_init=Decimal("0.025"), margin_maint=Decimal("0.0125"),
        maker_fee=Decimal("0.00015"), taker_fee=Decimal("0.00045"),
    )


HL_BTC = _perpetual("BTC-USD", BTC, "0.1", "0.00001")
HL_SOL = _perpetual("SOL-USD", SOL, "0.01", "0.01")
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
            intent = Intent("hl-stageg-exit", "hl-stageg-lifecycle", "BTC_REDUCE", 0, -1, quantity=0.01)
        self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), None, 0, ts_now=tick.ts_event)
        self.step += 1


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


async def _run_lifecycle(journal_path) -> tuple[AttachedStageGEntryExitProbe, PaperRuntime, TradingNode]:
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
    node.add_exec_client_factory("SANDBOX", SandboxLiveExecClientFactory)
    node.build()
    node.cache.add_instrument(HL_BTC)
    node.cache.add_instrument(HL_SOL)
    node.trader.add_strategy(strategy)
    await node.kernel.start_async()
    for tick in (_quote(BTC_PERP, "59999.0", "60000.0", 1), _quote(BTC_PERP, "60001.0", "60002.0", 2)):
        node.kernel.data_engine.process(tick)
        await asyncio.sleep(0.05)
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
            assert all(item["commission_currency"] == "USDC" for item in strategy.fill_audit)
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
