from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest
from nautilus_trader.adapters.hyperliquid.config import HyperliquidDataClientConfig, HyperliquidExecClientConfig

from coinmaster.ops.hyperliquid_testnet import (
    BTC_PERP,
    FeedBook,
    FeedObserver,
    HyperliquidTestnetNode,
    LifecycleHooks,
    LifecycleRequest,
    TESTNET_ENVIRONMENT,
    TestnetAuthContext,
    assert_native_testnet_only,
    hyperliquid_testnet_node_config,
    require_testnet_auth,
)
from coinmaster.ops.paper import PaperRuntime
from coinmaster.ops.stage_g_config import ConfigurationError, load_testnet_instance_config
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig
from coinmaster.venues.marks import venue_mark_data_type
from nautilus_trader.model.data import BarSpecification, BarType
from nautilus_trader.model.enums import AggregationSource, BarAggregation, PriceType
from nautilus_trader.model.identifiers import ClientId


ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
MASTER = "0x1234567890abcdef1234567890abcdef12345678"


def _environment(**overrides: str) -> dict[str, str]:
    value = {
        "COINMASTER_LIVE_ENABLED": "false",
        "COINMASTER_HL_TESTNET_ENABLED": "true",
        "COINMASTER_HL_TESTNET_ENVIRONMENT": "testnet",
        "HYPERLIQUID_TESTNET_PK": "runtime-only-fixture-not-a-secret",
        "COINMASTER_HL_TESTNET_MASTER_ACCOUNT_ADDRESS": MASTER,
    }
    value.update(overrides)
    return value


def test_hl_stageg_testnet_identity_is_strict_and_has_a_separate_state_db() -> None:
    instance = load_testnet_instance_config(ROOT / "configs/hl-stageg-testnet.instance.json")
    assert instance.instance_id == "hl-stageg-testnet"
    assert instance.venue == "HYPERLIQUID"
    assert instance.environment == "testnet"
    assert instance.state_db.name == "hl-stageg-testnet.sqlite"
    assert instance.state_db.parent.name == "testnet"
    assert instance.strategy_config.name == "stage-g-v1.json"


@pytest.mark.parametrize("change,reason", [
    ({"COINMASTER_LIVE_ENABLED": "true"}, "HL_TESTNET_REFUSES_LIVE_ENABLED"),
    ({"COINMASTER_HL_TESTNET_ENABLED": "false"}, "HL_TESTNET_NOT_EXPLICITLY_ENABLED"),
    ({"COINMASTER_HL_TESTNET_ENVIRONMENT": "mainnet"}, "HL_TESTNET_ENVIRONMENT_GUARD"),
    ({"HYPERLIQUID_TESTNET_PK": ""}, "HL_TESTNET_API_WALLET_SECRET_MISSING"),
    ({"COINMASTER_HL_TESTNET_MASTER_ACCOUNT_ADDRESS": "agent-address-is-not-an-account"}, "HL_TESTNET_MASTER_ACCOUNT_ADDRESS_REQUIRED"),
])
def test_testnet_runtime_guard_fails_closed_before_native_client_construction(change, reason) -> None:
    with pytest.raises(RuntimeError, match=reason):
        require_testnet_auth(_environment(**change))


def test_native_config_has_one_testnet_data_and_execution_route_and_explicit_master_query_target() -> None:
    auth = require_testnet_auth(_environment())
    config = hyperliquid_testnet_node_config(trader_id="COINMASTER-HL-STAGEG-TESTNET", auth=auth)
    assert set(config.data_clients) == {"HYPERLIQUID-TESTNET-DATA"}
    assert set(config.exec_clients) == {"HYPERLIQUID-TESTNET-EXEC"}
    data = config.data_clients["HYPERLIQUID-TESTNET-DATA"]
    execution = config.exec_clients["HYPERLIQUID-TESTNET-EXEC"]
    assert isinstance(data, HyperliquidDataClientConfig) and data.environment is TESTNET_ENVIRONMENT
    assert isinstance(execution, HyperliquidExecClientConfig) and execution.environment is TESTNET_ENVIRONMENT
    assert execution.private_key is None
    assert execution.account_address == MASTER
    assert execution.include_builder_attribution is False
    assert_native_testnet_only(config, auth)


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


def test_testnet_instance_rejects_mainnet_or_an_agent_address_field(tmp_path) -> None:
    source = json.loads((ROOT / "configs/hl-stageg-testnet.instance.json").read_text())
    source["environment"] = "mainnet"
    path = tmp_path / "instance.json"; path.write_text(json.dumps(source))
    with pytest.raises(ConfigurationError, match="UNSUPPORTED_TESTNET_INSTANCE_IDENTITY"):
        load_testnet_instance_config(path)
    source = json.loads((ROOT / "configs/hl-stageg-testnet.instance.json").read_text())
    source["agent_address"] = MASTER
    path.write_text(json.dumps(source))
    with pytest.raises(ConfigurationError, match="TESTNET_INSTANCE_FIELDS_MISMATCH"):
        load_testnet_instance_config(path)
