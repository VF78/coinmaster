from __future__ import annotations

import json
import time
from decimal import Decimal
from types import SimpleNamespace

import pytest
from nautilus_trader.adapters.hyperliquid.config import HyperliquidDataClientConfig
from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig

from coinmaster.ops.hyperliquid_testnet import (
    BTC_PERP,
    NativeSandboxFundingPoster,
    cross_venue_stage_g_gate,
    FeedBook,
    FeedObserver,
    HyperliquidTestnetNode,
    LifecycleHooks,
    LifecycleRequest,
    PUBLIC_MAINNET_ENVIRONMENT,
    assert_native_testnet_only,
    hyperliquid_testnet_node_config,
    require_testnet_sandbox,
)
from coinmaster.ops.native_paper_node import sandbox_cash_posting_supported
from coinmaster.ops.paper import PaperRuntime
from coinmaster.ops.stage_g_config import ConfigurationError, load_testnet_instance_config
from coinmaster.ops.stage_g_config import load_candidate
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig
from coinmaster.venues.marks import venue_mark_data_type
from nautilus_trader.model.data import BarSpecification, BarType
from nautilus_trader.model.enums import AggregationSource, BarAggregation, PriceType
from nautilus_trader.model.identifiers import ClientId, InstrumentId


ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
def _environment(**overrides: str) -> dict[str, str]:
    value = {
        "COINMASTER_LIVE_ENABLED": "false",
        "COINMASTER_HL_TESTNET_ENABLED": "true",
        "COINMASTER_HL_TESTNET_ENVIRONMENT": "mainnet",
        # Corrected D3 does not consume either of these values.
        "HYPERLIQUID_TESTNET_PK": "must-not-be-read",
        "COINMASTER_HL_TESTNET_MASTER_ACCOUNT_ADDRESS": "must-not-be-read",
    }
    value.update(overrides)
    return value


def test_hl_stageg_testnet_identity_is_strict_and_has_a_separate_state_db() -> None:
    instance = load_testnet_instance_config(ROOT / "configs/hl-stageg-testnet.instance.json")
    assert instance.instance_id == "hl-stageg-testnet"
    assert instance.venue == "HYPERLIQUID"
    assert instance.environment == "mainnet"
    assert instance.mode == "sandbox"
    assert instance.state_db.name == "hl-stageg-testnet.sqlite"
    assert instance.state_db.parent == __import__("pathlib").Path("/var/lib/coinmaster-hl-stageg-testnet").resolve()
    assert instance.strategy_config.name == "stage-g-v1.json"
    assert instance.signal_warmup_manifest.name == "manifest.json"


@pytest.mark.parametrize("change,reason", [
    ({"COINMASTER_LIVE_ENABLED": "true"}, "HL_TESTNET_REFUSES_LIVE_ENABLED"),
    ({"COINMASTER_HL_TESTNET_ENABLED": "false"}, "HL_TESTNET_NOT_EXPLICITLY_ENABLED"),
    ({"COINMASTER_HL_TESTNET_ENVIRONMENT": "testnet"}, "HL_PUBLIC_MAINNET_ENVIRONMENT_GUARD"),
])
def test_testnet_runtime_guard_fails_closed_before_native_client_construction(change, reason) -> None:
    with pytest.raises(RuntimeError, match=reason):
        require_testnet_sandbox(_environment(**change))


def test_native_config_has_one_mainnet_data_and_native_sandbox_execution_route() -> None:
    require_testnet_sandbox(_environment())
    config = hyperliquid_testnet_node_config(trader_id="COINMASTER-HL-STAGEG-TESTNET")
    assert set(config.data_clients) == {"BYBIT-PUBLIC-SIGNAL", "HYPERLIQUID-MAINNET-DATA"}
    assert set(config.exec_clients) == {"SANDBOX"}
    data = config.data_clients["HYPERLIQUID-MAINNET-DATA"]
    bybit = config.data_clients["BYBIT-PUBLIC-SIGNAL"]
    execution = config.exec_clients["SANDBOX"]
    from nautilus_trader.adapters.bybit.config import BybitDataClientConfig
    assert isinstance(bybit, BybitDataClientConfig) and bybit.api_key is None and bybit.api_secret is None
    assert isinstance(data, HyperliquidDataClientConfig) and data.environment is PUBLIC_MAINNET_ENVIRONMENT
    assert isinstance(execution, SandboxExecutionClientConfig)
    assert execution.venue == "HYPERLIQUID" and execution.base_currency == "USDC"
    assert execution.starting_balances == ["10000 USDC"]
    assert execution.leverages == {BTC_PERP: Decimal("40"), InstrumentId.from_str("SOL-USD-PERP.HYPERLIQUID"): Decimal("20")}
    assert sandbox_cash_posting_supported() is True
    assert_native_testnet_only(config)
    source = (ROOT / "coinmaster/ops/hyperliquid_testnet.py").read_text()
    assert "HyperliquidLiveExecClientFactory" not in source
    assert "HyperliquidExecClientConfig" not in source
    assert "HYPERLIQUID_TESTNET_PK" not in source
    assert "SandboxLiveExecClientFactory" in source


def test_cross_venue_gate_preserves_bybit_signal_ids_and_blocks_unproven_parity() -> None:
    gate = cross_venue_stage_g_gate(
        candidate=load_candidate(ROOT / "configs/stage-g-v1.json").candidate,
        warmup_manifest=ROOT / "var/data/paper-warmup-manifest.json",
        strategy_path=ROOT / "coinmaster/strategy/wave_overlay.py",
        profile_root=ROOT,
        now_ns=1_790_000_000_000_000_000,
    )
    assert gate.signal_ids == ("BTCUSDT-LINEAR.BYBIT", "SOLUSDT-LINEAR.BYBIT")
    assert gate.execution_ids == (str(BTC_PERP), "SOL-USD-PERP.HYPERLIQUID")
    assert gate.warmup_state == "INVALID_STAGEG_WARMUP_SCHEMA_OR_VENUE"
    assert gate.margin_policy_state == "READY_PUBLIC_HL_MAINNET_TIERS_LOCAL_SANDBOX_LEVERAGE"
    assert gate.execution_policy_state == "FIXED_PUBLIC_BASE_FEES_NATIVE_SANDBOX_COMMISSION_AUDITED"
    assert gate.funding_state == "BLOCKED_FUNDING_SETTLEMENT_ORACLE_NEXT_PAYMENT_ONLY"
    assert gate.capital_state == "NOMINAL_10000_USDC_SANDBOX_SEED_VS_10000_USDT_RESEARCH_1_TO_1_ASSUMPTION"
    assert gate.approval_state == "SEALED_APPROVAL_MATCH"
    assert gate.attachable is False


def test_daily_signal_keeps_bybit_identity_while_pairing_to_hl_execution_bar_type() -> None:
    signal_btc = InstrumentId.from_str("BTCUSDT-LINEAR.BYBIT")
    signal_sol = InstrumentId.from_str("SOLUSDT-LINEAR.BYBIT")
    execution_btc = BTC_PERP
    execution_sol = InstrumentId.from_str("SOL-USD-PERP.HYPERLIQUID")
    btc_bar = BarType(signal_btc, BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL)
    sol_bar = BarType(signal_sol, BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL)
    strategy = WaveOverlayStrategy(WaveOverlayStrategyConfig(
        btc_id=execution_btc, sol_id=execution_sol, btc_bar_type=btc_bar, sol_bar_type=sol_bar,
        btc_mark_data_type=venue_mark_data_type(execution_btc), sol_mark_data_type=venue_mark_data_type(execution_sol),
        mark_client_id=ClientId("HL-MAINNET"), active_seed=0,
        btc_signal_id=signal_btc, sol_signal_id=signal_sol,
    ))
    from coinmaster.venues.signals import DailySignalBar
    signal = DailySignalBar(signal_btc, 100, 110, 90, 105, 86_400_000_000_000)
    strategy.on_data(signal)
    paired = strategy._day[signal.ts_event]
    assert paired[btc_bar] is signal
    assert signal.instrument_id == signal_btc  # never relabel source provenance as HL.
    assert strategy.config.btc_bar_type.instrument_id == signal_btc
    assert strategy.config.sol_bar_type.instrument_id == signal_sol
    assert execution_btc not in (signal_btc, signal_sol)


def test_native_sandbox_funding_poster_is_idempotent_and_uses_only_confirmed_hl_identity(tmp_path) -> None:
    class Exchange:
        def __init__(self): self.adjustments = []
        def adjust_account(self, money): self.adjustments.append(money)

    runtime = PaperRuntime(tmp_path / "funding.sqlite", "hl-stageg-testnet", int(120e9)); runtime.acquire()
    exchange = Exchange()
    poster = NativeSandboxFundingPoster(exchange=exchange, runtime=runtime)
    poster(instrument_id=BTC_PERP, settlement_ns=100, rate=Decimal("0.01"), settlement_mark=Decimal("100"), signed_quantity=Decimal("2"))
    poster(instrument_id=BTC_PERP, settlement_ns=100, rate=Decimal("0.01"), settlement_mark=Decimal("100"), signed_quantity=Decimal("2"))
    assert [item.as_decimal() for item in exchange.adjustments] == [Decimal("-2.00")]
    assert runtime.pending_native_funding() == []
    runtime.close()


def test_next_funding_timestamp_is_observation_only_not_an_early_cash_post() -> None:
    from nautilus_trader.model.data import FundingRateUpdate, MarkPriceUpdate
    from nautilus_trader.model.objects import Price

    posted = []
    bar = BarType(BTC_PERP, BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL)
    strategy = WaveOverlayStrategy(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP, sol_id=InstrumentId.from_str("SOL-USD-PERP.HYPERLIQUID"), btc_bar_type=bar, sol_bar_type=bar,
        btc_mark_data_type=venue_mark_data_type(BTC_PERP), sol_mark_data_type=venue_mark_data_type(InstrumentId.from_str("SOL-USD-PERP.HYPERLIQUID")),
        mark_client_id=ClientId("fixture"), active_seed=0,
        funding_sink=lambda **kwargs: posted.append(kwargs),
    ))
    strategy.on_mark_price(MarkPriceUpdate(BTC_PERP, Price.from_str("100"), 100, 100))
    strategy.on_funding_rate(FundingRateUpdate(BTC_PERP, Decimal("0.01"), 100, 100, next_funding_ns=200))
    assert posted == []


def test_d1_lifecycle_hooks_cover_native_submit_cancel_reduce_only_post_only_taker_partial_fill_and_pause(tmp_path) -> None:
    runtime = PaperRuntime(tmp_path / "testnet.sqlite", "hl-stageg-testnet", int(120e9))
    runtime.acquire(); runtime.snapshot(ts_ns=time.time_ns(), positions=[], orders=[], funding_event_ids=[])
    hooks = LifecycleHooks(runtime)
    maker = LifecycleRequest("oid-maker", "i-maker", "e", "BTC_REDUCE", str(BTC_PERP), "0.01", True, "LIMIT", "GTC", True)
    assert hooks.before_native_submit(maker)
    # Invoke the existing D1 strategy callbacks, which discover the optional
    # .acknowledge/.terminal interface rather than calling helper methods.
    bar = BarType(BTC_PERP, BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL)
    strategy = WaveOverlayStrategy(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP, sol_id=BTC_PERP, btc_bar_type=bar, sol_bar_type=bar,
        btc_mark_data_type=venue_mark_data_type(BTC_PERP), sol_mark_data_type=venue_mark_data_type(BTC_PERP),
        mark_client_id=ClientId("fixture"), active_seed=0, event_sink=hooks.record_event, submission_sink=hooks,
    ))
    strategy.on_order_event(SimpleNamespace(client_order_id="oid-maker", ts_event=1, ts_init=1))
    hooks.on_native_partial_fill("trade-partial-1")
    strategy.on_order_canceled(SimpleNamespace(client_order_id="oid-maker"))
    assert runtime.pending_submissions() == []
    assert [item["kind"] for item in runtime.events()] == ["order", "fill"]
    with pytest.raises(ValueError, match="POST_ONLY_REQUIRES_LIMIT_GTC"):
        hooks.before_native_submit(LifecycleRequest("bad", "i", "e", "BTC_REDUCE", str(BTC_PERP), "1", True, "MARKET", "IOC", True))
    taker_reduce = LifecycleRequest("oid-taker", "i-taker", "e", "SOL_EXIT", str(BTC_PERP), "0.01", True, "MARKET", "IOC")
    assert hooks.before_native_submit(taker_reduce)  # reductions bypass pause.
    assert runtime.command("pause-new-entries", "pause")
    entry = LifecycleRequest("oid-entry", "i-entry", "e", "BTC_ENTRY", str(BTC_PERP), "0.01", False, "MARKET", "IOC")
    assert not hooks.before_native_submit(entry)
    runtime.close()


def test_observation_node_registers_only_feed_observer_and_has_no_native_order_path() -> None:
    class _Trader:
        def __init__(self): self.added = []
        def add_strategy(self, strategy): self.added.append(strategy)
    observation = HyperliquidTestnetNode.__new__(HyperliquidTestnetNode)
    observation.node = SimpleNamespace(trader=_Trader())
    observation.feed = FeedBook(ids=(BTC_PERP,))
    observation.feed_observer = None
    observation.prime_error = None
    observation.prime()
    assert observation.prime_error is None
    assert len(observation.node.trader.added) == 1
    assert isinstance(observation.node.trader.added[0], FeedObserver)
    assert not hasattr(observation, "strategy")


def test_unverified_worker_poll_does_not_snapshot_empty_native_cache_as_reconciled(tmp_path) -> None:
    from coinmaster.ops.hyperliquid_testnet_worker import TestnetWorker
    runtime = PaperRuntime(tmp_path / "testnet.sqlite", "hl-stageg-testnet", int(120e9))
    runtime.acquire()
    worker = TestnetWorker.__new__(TestnetWorker)
    worker.runtime = runtime
    worker.poll()
    assert runtime.db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone() is None
    assert runtime.health(time.time_ns()).safe_for_increase is False
    runtime.close()


def test_recovered_open_testnet_position_remains_manage_only_after_restart(tmp_path) -> None:
    path = tmp_path / "testnet.sqlite"
    original = PaperRuntime(path, "hl-stageg-testnet", int(120e9))
    original.acquire()
    original.snapshot(ts_ns=1, positions=[{"instrument_id": str(BTC_PERP), "signed_quantity": "0.01"}], orders=[], funding_event_ids=[])
    original.close()
    restarted = PaperRuntime(path, "hl-stageg-testnet", int(120e9))
    restarted.acquire()
    assert restarted.recovery_state() == "MANAGE_ONLY_DURABLE_OPEN_STATE"
    assert not restarted.reconcile(positions=[], orders=[])
    restarted.heartbeat(2)
    assert not restarted.health(2).safe_for_increase
    restarted.close()


def test_running_attached_node_never_overwrites_durable_open_recovery_with_empty_cache(tmp_path) -> None:
    from coinmaster.ops.hyperliquid_testnet_worker import TestnetWorker

    path = tmp_path / "testnet.sqlite"
    original = PaperRuntime(path, "hl-stageg-testnet", int(120e9)); original.acquire()
    original.snapshot(ts_ns=time.time_ns(), positions=[{"instrument_id": str(BTC_PERP), "signed_quantity": "0.01"}], orders=[], funding_event_ids=[])
    original.close()
    runtime = PaperRuntime(path, "hl-stageg-testnet", int(120e9)); runtime.acquire()
    worker = TestnetWorker.__new__(TestnetWorker)
    worker.runtime, worker.reconciled = runtime, False
    worker.native = SimpleNamespace(
        node=SimpleNamespace(is_running=lambda: True), strategy=object(),
        sandbox_snapshot=lambda: ([], []),
    )
    worker.poll()
    assert runtime.recovery_state() == "MANAGE_ONLY_DURABLE_OPEN_STATE"
    saved = runtime.db.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone()[0]
    assert str(BTC_PERP) in saved
    assert not runtime.health(time.time_ns()).safe_for_increase
    runtime.close()


def test_testnet_instance_rejects_mainnet_or_an_agent_address_field(tmp_path) -> None:
    source = json.loads((ROOT / "configs/hl-stageg-testnet.instance.json").read_text())
    source["environment"] = "testnet"
    path = tmp_path / "instance.json"; path.write_text(json.dumps(source))
    with pytest.raises(ConfigurationError, match="UNSUPPORTED_TESTNET_INSTANCE_IDENTITY"):
        load_testnet_instance_config(path)
    source = json.loads((ROOT / "configs/hl-stageg-testnet.instance.json").read_text())
    source["agent_address"] = "0x1234567890abcdef1234567890abcdef12345678"
    path.write_text(json.dumps(source))
    with pytest.raises(ConfigurationError, match="TESTNET_INSTANCE_FIELDS_MISMATCH"):
        load_testnet_instance_config(path)
    source = json.loads((ROOT / "configs/hl-stageg-testnet.instance.json").read_text())
    source["state_db"] = "/tmp/testnet.sqlite"
    path.write_text(json.dumps(source))
    with pytest.raises(ConfigurationError, match="UNSAFE_TESTNET_STATE_DB_PATH"):
        load_testnet_instance_config(path)
