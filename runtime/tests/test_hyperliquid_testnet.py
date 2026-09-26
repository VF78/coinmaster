from __future__ import annotations

import json
import time
from decimal import Decimal
from types import SimpleNamespace

import pytest
from nautilus_trader.adapters.hyperliquid.config import HyperliquidDataClientConfig
from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig

from coinmaster.domain.wave_overlay import Intent
from coinmaster.ops.hyperliquid_testnet import (
    BTC_PERP,
    NativeSandboxFundingPoster,
    SOL_PERP,
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
from nautilus_trader.model.enums import AggregationSource, BarAggregation, PriceType, TimeInForce
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
    assert str(instance.signal_warmup_manifest) == "/var/lib/coinmaster-hl-stageg-testnet/data/current/manifest.json"


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
    continued = hyperliquid_testnet_node_config(trader_id="COINMASTER-HL-STAGEG-TESTNET", starting_cash=Decimal("9999.87654321"))
    assert continued.exec_clients["SANDBOX"].starting_balances == ["9999.87654321 USDC"]
    assert execution.leverages == {BTC_PERP: Decimal("40"), InstrumentId.from_str("SOL-USD-PERP.HYPERLIQUID"): Decimal("20")}
    assert sandbox_cash_posting_supported() is True
    assert_native_testnet_only(config)
    source = (ROOT / "coinmaster/ops/hyperliquid_testnet.py").read_text()
    assert "HYPERLIQUID_TESTNET_PK" not in source
    assert "SandboxLiveExecClientFactory" in source


def test_cross_venue_gate_preserves_bybit_signal_ids_and_labels_unposted_funding() -> None:
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
    assert gate.funding_state == "OBSERVED_MODELLED_UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT"
    assert gate.capital_state == "NOMINAL_10000_USDC_SANDBOX_SEED_VS_10000_USDT_RESEARCH_1_TO_1_ASSUMPTION"
    assert gate.approval_state == "SEALED_APPROVAL_MATCH"
    assert gate.attachable is False


def test_verified_latest_bybit_tail_unlocks_attachment_without_posting_scheduled_funding() -> None:
    manifest = ROOT / "var/data/stageg-bybit-warmup-20260923-verified3/manifest.json"
    document = json.loads(manifest.read_text())
    assert document["completed_sessions"] == 1482
    assert document["provenance"]["append_raw_manifest_sha256"] == "0974b9e0d2c39a0cdf6afa6a522540710ebbdb5b3ec0569659532b87da7fb7e0"
    assert {item["daily_gaps"] for item in document["symbols"].values()} == {0}
    gate = cross_venue_stage_g_gate(
        candidate=load_candidate(ROOT / "configs/stage-g-v1.json").candidate,
        warmup_manifest=manifest,
        strategy_path=ROOT / "coinmaster/strategy/wave_overlay.py",
        profile_root=ROOT,
        now_ns=1_790_121_600_000_000_000,
    )
    assert gate.warmup_state == "READY"
    assert gate.approval_state == "SEALED_APPROVAL_MATCH"
    assert gate.funding_state == "OBSERVED_MODELLED_UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT"
    assert gate.attachable is True


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


def test_flat_daily_decision_retries_once_after_entry_gate_reopens() -> None:
    class DeferredEntryProbe(WaveOverlayStrategy):
        @property
        def cache(self):
            return SimpleNamespace(positions_open=lambda: [])

    gate_open = False
    strategy = DeferredEntryProbe(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP, sol_id=SOL_PERP,
        btc_bar_type=BarType(InstrumentId.from_str("BTCUSDT-LINEAR.BYBIT"), BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL),
        sol_bar_type=BarType(InstrumentId.from_str("SOLUSDT-LINEAR.BYBIT"), BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL),
        btc_mark_data_type=venue_mark_data_type(BTC_PERP), sol_mark_data_type=venue_mark_data_type(SOL_PERP),
        mark_client_id=ClientId("fixture"), active_seed=Decimal("10000"),
        entries_gate=lambda: gate_open,
    ))
    session = 86_400_000_000_000
    current = SimpleNamespace(ts_event=session)
    strategy._current_btc = strategy._current_sol = current
    strategy._current_btc_mark = strategy._current_sol_mark = current
    strategy._bars = [object()]  # The probe owns the deterministic domain output below.
    strategy._current_signals = [SimpleNamespace(sigma=None)]
    decisions: list[int] = []
    strategy._active_marked = lambda *_args: 10_000  # type: ignore[method-assign]
    strategy._domain.decide = lambda _bars, _signals, index, _active: (  # type: ignore[method-assign]
        decisions.append(index) or [Intent("deferred-entry", "episode", "BTC_ENTRY", None, 1, requested_notional=100)]
    )

    strategy._advance_current_day()
    assert strategy._deferred_entry_session == session
    assert decisions == [] and strategy._queued_intents == []

    gate_open = True
    quote = SimpleNamespace(instrument_id=InstrumentId.from_str("ETH-USD-PERP.HYPERLIQUID"), ts_event=session)
    strategy.on_quote_tick(quote)
    strategy.on_quote_tick(quote)
    assert decisions == [0]
    assert [intent.id for intent, _, _ in strategy._queued_intents] == ["deferred-entry"]
    assert strategy._deferred_entry_session is None

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



def test_stageg_prime_registers_trading_strategy_with_native_market_exit(tmp_path) -> None:
    from coinmaster.venues.hyperliquid_profile import HyperliquidProfileEnvironment, HyperliquidVenueProfile

    class Trader:
        def __init__(self) -> None:
            self.added = []

        def add_strategy(self, strategy) -> None:
            self.added.append(strategy)

    runtime = PaperRuntime(tmp_path / "stageg-prime.sqlite", "hl-stageg-testnet", int(120e9), require_native_cash=True)
    runtime.acquire()
    try:
        node = HyperliquidTestnetNode.__new__(HyperliquidTestnetNode)
        node.warmup_bundle = SimpleNamespace(bars=())
        node.warmup_state = "READY"
        node.gate = SimpleNamespace(attachable=True, execution_policy_hash="policy")
        node.profile = HyperliquidVenueProfile.from_snapshot(ROOT, environment=HyperliquidProfileEnvironment.MAINNET)
        node.starting_cash = Decimal("10000")
        node.candidate = load_candidate(ROOT / "configs/stage-g-v1.json").candidate
        node.hooks = SimpleNamespace(record_event=lambda event: None)
        node.state = runtime
        node.instance = SimpleNamespace(instance_id="hl-stageg-testnet")
        node._sandbox_exchange = lambda: SimpleNamespace()
        node.node = SimpleNamespace(trader=Trader())
        node.feed = FeedBook(ids=(BTC_PERP, SOL_PERP))
        node.feed_observer = None
        node.strategy = None
        node.prime_error = None

        node.prime()

        assert node.prime_error is None
        assert [type(item).__name__ for item in node.node.trader.added] == ["FeedObserver", "WaveOverlayStrategy"]
        assert node.strategy.config.market_exit_time_in_force == TimeInForce.IOC
        assert node.strategy.config.market_exit_reduce_only is True
    finally:
        runtime.close()

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



def _utc_signal_probe(seed_close_ns: int):
    from datetime import UTC, datetime, timedelta
    from coinmaster.domain.wave_overlay import DailyBar
    from coinmaster.venues.marks import VenueMark
    from coinmaster.venues.signals import DailySignalBar

    day = 86_400_000_000_000
    btc_source = InstrumentId.from_str("BTCUSDT-LINEAR.BYBIT")
    sol_source = InstrumentId.from_str("SOLUSDT-LINEAR.BYBIT")
    btc_bar = BarType(btc_source, BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL)
    sol_bar = BarType(sol_source, BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL)
    close = datetime.fromtimestamp(seed_close_ns / 1_000_000_000, UTC)
    seed = DailyBar(close - timedelta(days=1), close, close, 100, 101, 30)
    strategy = WaveOverlayStrategy(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP, sol_id=SOL_PERP,
        btc_bar_type=btc_bar, sol_bar_type=sol_bar,
        btc_mark_data_type=venue_mark_data_type(BTC_PERP),
        sol_mark_data_type=venue_mark_data_type(SOL_PERP),
        mark_client_id=ClientId("fixture"), active_seed=Decimal("10000"),
        seed_bars=(seed,), btc_signal_id=btc_source, sol_signal_id=sol_source,
    ))
    decisions = []
    strategy._advance_current_day = lambda: decisions.append(strategy._current_btc.ts_event)
    def feed(session: int) -> None:
        strategy._marks_by_session[session] = {
            BTC_PERP: VenueMark(BTC_PERP, Decimal("100"), session),
            SOL_PERP: VenueMark(SOL_PERP, Decimal("30"), session),
        }
        strategy.on_data(DailySignalBar(btc_source, 100, 110, 90, 101, session))
        strategy.on_data(DailySignalBar(sol_source, 30, 33, 27, 30, session))
    return strategy, decisions, feed, seed, day


def test_utc_late_pair_duplicate_and_gap_are_contiguous_and_idempotent() -> None:
    seed_close = 1_672_617_600_000_000_000
    strategy, decisions, feed, seed, day = _utc_signal_probe(seed_close)
    feed(seed_close + 2 * day)
    assert len(strategy._bars) == 1
    assert strategy.daily_decision_status()["reason"] == "WAITING_CONTIGUOUS_PAIRED_SESSION"
    feed(seed_close + day)
    assert [int(row.close_time.timestamp() * 1_000_000_000) for row in strategy._bars] == [
        seed_close, seed_close + day, seed_close + 2 * day,
    ]
    assert decisions == [seed_close + 2 * day]
    feed(seed_close + day)
    feed(seed_close + 2 * day)
    assert len(strategy._bars) == 3
    assert decisions == [seed_close + 2 * day]


def test_verified_gap_backfill_updates_features_without_retrotrade_and_restart_waits() -> None:
    from datetime import timedelta
    from coinmaster.domain.wave_overlay import DailyBar

    seed_close = 1_672_617_600_000_000_000
    strategy, decisions, feed, seed, day = _utc_signal_probe(seed_close)
    future = seed_close + 3 * day
    rows = [
        DailyBar(seed.close_time + timedelta(days=i-1), seed.close_time + timedelta(days=i),
                 seed.close_time + timedelta(days=i), 100+i, 101+i, 30+i)
        for i in (1, 2)
    ]
    strategy.queue_verified_backfill(rows)
    assert decisions == [] and len(strategy._bars) == 1
    feed(future)
    assert decisions == [future]
    assert len(strategy._bars) == 4
    assert strategy.daily_decision_status()["accepted_session_ns"] == future

    # A fresh process receives only verified feature history, never a
    # process-local deferred order or retroactive quote execution.
    restarted, restarted_decisions, _, _, _ = _utc_signal_probe(future)
    assert restarted._deferred_entry_session is None
    assert restarted_decisions == []
    assert restarted.daily_decision_status()["accepted_session_ns"] == future



def test_verified_backfill_repairs_partial_prior_day_without_retrotrade() -> None:
    from datetime import timedelta
    from coinmaster.domain.wave_overlay import DailyBar
    from coinmaster.venues.marks import VenueMark
    from coinmaster.venues.signals import DailySignalBar

    seed_close = 1_672_617_600_000_000_000
    strategy, decisions, feed, seed, day = _utc_signal_probe(seed_close)
    prior, current = seed_close + day, seed_close + 2 * day
    btc_id = strategy.config.btc_signal_id
    strategy._marks_by_session[prior] = {
        BTC_PERP: VenueMark(BTC_PERP, Decimal("100"), prior),
    }
    strategy.on_data(DailySignalBar(btc_id, 100, 110, 90, 101, prior))
    feed(current)
    assert decisions == []
    assert prior in strategy._day and prior in strategy._marks_by_session
    assert strategy.daily_decision_status()["reason"] == "WAITING_CONTIGUOUS_PAIRED_SESSION"

    verified_prior = DailyBar(
        seed.close_time, seed.close_time + timedelta(days=1),
        seed.close_time + timedelta(days=1), 100, 101, 30,
    )
    strategy.queue_verified_backfill([verified_prior])
    assert decisions == []
    strategy._apply_verified_backfill()  # The next native callback applies the queued artifact.
    assert [int(row.close_time.timestamp() * 1_000_000_000) for row in strategy._bars] == [
        seed_close, prior, current,
    ]
    assert prior not in strategy._day and prior not in strategy._marks_by_session
    assert decisions == [current]
    assert strategy.daily_decision_status()["accepted_session_ns"] == current
    feed(prior)
    feed(current)
    assert decisions == [current]

    # Intraday quotes before the first live close cannot consume the queued
    # artifact before a safe current-session cutoff exists.
    fresh, _, _, _, _ = _utc_signal_probe(seed_close)
    fresh.queue_verified_backfill([verified_prior])
    fresh.on_quote_tick(SimpleNamespace())
    assert fresh._pending_verified_backfill == (verified_prior,)


def test_late_sol_signal_completes_btc_day_once() -> None:
    from coinmaster.venues.marks import VenueMark
    from coinmaster.venues.signals import DailySignalBar

    seed_close = 1_672_617_600_000_000_000
    strategy, decisions, _, _, day = _utc_signal_probe(seed_close)
    session = seed_close + day
    strategy._marks_by_session[session] = {
        BTC_PERP: VenueMark(BTC_PERP, Decimal("100"), session),
        SOL_PERP: VenueMark(SOL_PERP, Decimal("30"), session),
    }
    btc_id = strategy.config.btc_signal_id
    sol_id = strategy.config.sol_signal_id
    strategy.on_data(DailySignalBar(btc_id, 100, 110, 90, 101, session))
    assert len(strategy._bars) == 1 and decisions == []
    strategy.on_data(DailySignalBar(sol_id, 30, 33, 27, 30, session))
    strategy.on_data(DailySignalBar(sol_id, 30, 33, 27, 30, session))
    assert len(strategy._bars) == 2
    assert decisions == [session]

def test_submitted_is_not_accepted_and_native_denial_terminalizes_journal(tmp_path) -> None:
    runtime = PaperRuntime(tmp_path / "denied.sqlite", "hl-stageg-testnet", 10**20)
    runtime.acquire()
    assert runtime.record_submission(
        client_order_id="oid-denied", intent_id="intent-denied", episode_id="episode",
        action="BTC_ENTRY", instrument_id=str(BTC_PERP), quantity="0.01", reduce_only=False,
    )
    hooks = LifecycleHooks(runtime)
    bar = BarType(BTC_PERP, BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL)
    strategy = WaveOverlayStrategy(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP, sol_id=SOL_PERP, btc_bar_type=bar, sol_bar_type=bar,
        btc_mark_data_type=venue_mark_data_type(BTC_PERP),
        sol_mark_data_type=venue_mark_data_type(SOL_PERP),
        mark_client_id=ClientId("fixture"), active_seed=0,
        event_sink=hooks.record_event, submission_sink=hooks,
    ))
    strategy._order_audit["oid-denied"] = {"accept_ns": None}
    strategy.on_order_event(SimpleNamespace(client_order_id="oid-denied", ts_event=1))
    assert runtime.pending_submissions()[0]["state"] == "SUBMITTING"
    assert strategy._order_audit["oid-denied"]["accept_ns"] is None
    strategy.on_order_denied(SimpleNamespace(client_order_id="oid-denied"))
    assert runtime.pending_submissions() == []
    # A distinct native acceptance is the only event that can advance ACK.
    assert runtime.record_submission(
        client_order_id="oid-accepted", intent_id="intent-accepted", episode_id="episode",
        action="BTC_ENTRY", instrument_id=str(BTC_PERP), quantity="0.01", reduce_only=False,
    )
    strategy._order_audit["oid-accepted"] = {"accept_ns": None}
    strategy.on_order_accepted(SimpleNamespace(client_order_id="oid-accepted", ts_event=2))
    assert runtime.pending_submissions()[0]["state"] == "ACKED"
    assert strategy._order_audit["oid-accepted"]["accept_ns"] == "2"
    runtime.close()

def test_forced_close_native_fill_terminalizes_journal_once_and_clears_group(tmp_path) -> None:
    from nautilus_trader.model.currencies import USDC
    from nautilus_trader.model.enums import LiquiditySide
    from nautilus_trader.model.objects import Money, Price, Quantity
    from coinmaster.domain.wave_overlay import Episode

    runtime = PaperRuntime(tmp_path / "forced.sqlite", "hl-stageg-testnet", 10**20)
    runtime.acquire()
    assert runtime.record_submission(
        client_order_id="forced-oid", intent_id="forced-intent", episode_id="forced",
        action="FORCED_CLOSE", instrument_id=str(BTC_PERP), quantity="0.01", reduce_only=True,
    )
    hooks = LifecycleHooks(runtime)
    cache = SimpleNamespace(
        order=lambda _id: SimpleNamespace(is_closed=True),
        positions_open=lambda: [],
        orders_open=lambda: [],
    )

    class Probe(WaveOverlayStrategy):
        @property
        def cache(self):
            return cache

    bar = BarType(BTC_PERP, BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL)
    strategy = Probe(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP, sol_id=SOL_PERP, btc_bar_type=bar, sol_bar_type=bar,
        btc_mark_data_type=venue_mark_data_type(BTC_PERP),
        sol_mark_data_type=venue_mark_data_type(SOL_PERP),
        mark_client_id=ClientId("fixture"), active_seed=0,
        event_sink=hooks.record_event, submission_sink=hooks,
    ))
    close = Intent("forced-intent", "forced", "CLOSE_ALL", None, -1, reason="REGIME")
    strategy._domain.episode = Episode("forced", 1, 100, 1, close_reason="REGIME")
    strategy._domain.episode.pending[close.id] = close
    strategy._forced_close_reason = "REGIME"
    strategy._forced_close_intent = close
    strategy._forced_close_orders.add("forced-oid")
    strategy._order_audit["forced-oid"] = {"action": "FORCED_CLOSE"}
    fill = SimpleNamespace(
        trade_id="forced-trade", client_order_id="forced-oid", instrument_id=BTC_PERP,
        last_qty=Quantity.from_str("0.01"), last_px=Price.from_str("60000"),
        commission=Money(Decimal("0.27"), USDC), liquidity_side=LiquiditySide.TAKER,
        order_type="MARKET", ts_event=1, ts_init=1,
    )
    # Simulate a crash after audit insert but before the domain callback.
    assert runtime.record_native_event("forced-trade", "fill")
    strategy.on_order_filled(fill)
    assert runtime.pending_submissions() == []
    assert strategy._domain.episode is None
    assert strategy._forced_close_reason is None
    assert len(strategy.fill_audit) == 1
    revision = runtime.native_revision()
    strategy.on_order_filled(fill)
    assert runtime.native_revision() == revision
    assert len(strategy.fill_audit) == 1
    runtime.close()
