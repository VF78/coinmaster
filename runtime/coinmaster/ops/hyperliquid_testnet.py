"""D3's isolated Hyperliquid public-data / native-sandbox dry-run boundary.

This is not a second engine or a bespoke exchange transport.  It consumes
Nautilus 1.231's public Hyperliquid MAINNET adapter and uses Nautilus'
``SandboxExecutionClient`` as its *only* execution route.  It has no API
wallet, account query, Hyperliquid execution factory, or exchange-order path.
"""
from __future__ import annotations

import asyncio
import os
import threading
import time
from dataclasses import dataclass
from typing import Mapping

from nautilus_trader.adapters.hyperliquid import HyperliquidLiveDataClientFactory
from nautilus_trader.adapters.hyperliquid.config import HyperliquidDataClientConfig
from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.adapters.sandbox.execution import SandboxExecutionClient
from nautilus_trader.adapters.sandbox.factory import SandboxLiveExecClientFactory
from nautilus_trader.common import Environment
from nautilus_trader.config import InstrumentProviderConfig, LoggingConfig
from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.live.config import LiveExecEngineConfig, RoutingConfig, TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.identifiers import ClientId, InstrumentId

from coinmaster.domain.wave_overlay import Candidate
from coinmaster.ops.native_paper_node import EXECUTION_FACTORY_ALLOWLIST, FeedBook, FeedObserver, FeedObserverConfig, scrub_private_execution_environment
from coinmaster.ops.paper import PaperRuntime
from coinmaster.ops.stage_g_config import TestnetInstanceConfig, candidate_content_hash


PUBLIC_MAINNET_ENVIRONMENT = nautilus_pyo3.HyperliquidEnvironment.MAINNET
BTC_PERP = InstrumentId.from_str("BTC-USD-PERP.HYPERLIQUID")
SOL_PERP = InstrumentId.from_str("SOL-USD-PERP.HYPERLIQUID")
TESTNET_IDS = (BTC_PERP, SOL_PERP)
NATIVE_TESTNET_FACTORIES = (HyperliquidLiveDataClientFactory, SandboxLiveExecClientFactory)


@dataclass(frozen=True)
class LifecycleRequest:
    """A durable audit hook for an order which Nautilus, not this class, owns."""
    client_order_id: str
    intent_id: str
    episode_id: str
    action: str
    instrument_id: str
    quantity: str
    reduce_only: bool
    order_kind: str
    time_in_force: str
    post_only: bool = False


class LifecycleHooks:
    """Dependency-injectable native lifecycle audit/restart gate.

    These hooks do not create, sign, transport, or match orders.  They are
    called by the existing D1 strategy adapter around Nautilus-native order
    lifecycle callbacks and remain testable with plain fixtures.
    """
    def __init__(self, runtime: PaperRuntime) -> None:
        self.runtime = runtime

    @staticmethod
    def validate_shape(request: LifecycleRequest) -> None:
        if request.instrument_id not in {str(item) for item in TESTNET_IDS}:
            raise ValueError("UNKNOWN_TESTNET_INSTRUMENT")
        if request.post_only and (request.order_kind != "LIMIT" or request.time_in_force != "GTC"):
            raise ValueError("POST_ONLY_REQUIRES_LIMIT_GTC")
        if request.order_kind == "MARKET" and request.time_in_force != "IOC":
            raise ValueError("TAKER_MARKET_REQUIRES_IOC")

    def before_native_submit(self, request: LifecycleRequest) -> bool:
        self.validate_shape(request)
        # A reduction is an exposure-decreasing safety action; entries require
        # a fresh, unpaused, flat-restart runtime state immediately before the
        # native submit happens.
        if not request.reduce_only and not self.runtime.health(time.time_ns()).safe_for_increase:
            return False
        return self.runtime.record_submission(
            client_order_id=request.client_order_id,
            intent_id=request.intent_id,
            episode_id=request.episode_id,
            action=request.action,
            instrument_id=request.instrument_id,
            quantity=request.quantity,
            reduce_only=request.reduce_only,
        )

    def __call__(self, **kwargs) -> bool:
        """Adapter for the existing D1 strategy's pre-native-submit hook."""
        return self.before_native_submit(LifecycleRequest(
            client_order_id=kwargs["client_order_id"], intent_id=kwargs["intent_id"], episode_id=kwargs["episode_id"],
            action=kwargs["action"], instrument_id=kwargs["instrument_id"], quantity=kwargs["quantity"],
            reduce_only=kwargs["reduce_only"], order_kind=kwargs["order_kind"],
            time_in_force=kwargs["time_in_force"], post_only=kwargs["post_only"],
        ))

    def record_event(self, event_id: str, kind: str) -> bool:
        recorded = self.runtime.record_native_event(event_id, kind)
        if kind == "order":
            self.runtime.acknowledge_submission(event_id)
        return recorded

    def on_native_order_event(self, client_order_id: str) -> None:
        self.record_event(client_order_id, "order")

    def on_native_partial_fill(self, trade_id: str) -> None:
        self.runtime.record_native_event(trade_id, "fill")

    def on_native_terminal(self, client_order_id: str) -> None:
        self.terminal(client_order_id)

    # These names are the exact optional D1 strategy callback interface.
    def acknowledge(self, client_order_id: str) -> None:
        self.runtime.acknowledge_submission(client_order_id)

    def terminal(self, client_order_id: str) -> None:
        self.runtime.terminal_submission(client_order_id)


def require_testnet_sandbox(environment: Mapping[str, str] | None = None) -> None:
    """Fail closed unless this is the explicitly enabled non-live dry run.

    This guard intentionally does not read an API-wallet secret or an account
    address.  Sandbox execution cannot authenticate with Hyperliquid and all
    state it creates remains local to the durable sandbox journal.
    """
    environment = os.environ if environment is None else environment
    if environment.get("COINMASTER_LIVE_ENABLED", "false").lower() != "false":
        raise RuntimeError("HL_TESTNET_REFUSES_LIVE_ENABLED")
    if environment.get("COINMASTER_HL_TESTNET_ENABLED") != "true":
        raise RuntimeError("HL_TESTNET_NOT_EXPLICITLY_ENABLED")
    if environment.get("COINMASTER_HL_TESTNET_ENVIRONMENT") != "mainnet":
        raise RuntimeError("HL_PUBLIC_MAINNET_ENVIRONMENT_GUARD")


def hyperliquid_testnet_node_config(*, trader_id: str) -> TradingNodeConfig:
    """Build exactly one public MAINNET-data + native-sandbox node route."""
    provider = InstrumentProviderConfig(load_ids=frozenset(TESTNET_IDS))
    routing = RoutingConfig(venues=frozenset({"HYPERLIQUID"}))
    return TradingNodeConfig(
        environment=Environment.LIVE,
        trader_id=trader_id,
        logging=LoggingConfig(log_level="INFO", log_colors=False),
        # Sandbox has no remote account/order history.  Durable recovery is
        # handled by PaperRuntime and must never be described as exchange
        # reconciliation.
        exec_engine=LiveExecEngineConfig(reconciliation=False),
        data_clients={
            "HYPERLIQUID-MAINNET-DATA": HyperliquidDataClientConfig(
                instrument_provider=provider, routing=routing, environment=PUBLIC_MAINNET_ENVIRONMENT,
            ),
        },
        exec_clients={
            "SANDBOX": SandboxExecutionClientConfig(
                venue="HYPERLIQUID",
                starting_balances=["100000 USDC"],
                base_currency="USDC",
                use_reduce_only=True,
                routing=routing,
            ),
        },
    )


def assert_native_testnet_only(config: TradingNodeConfig) -> None:
    """Reject any route beyond public mainnet data and native Sandbox exec."""
    if set(config.data_clients) != {"HYPERLIQUID-MAINNET-DATA"} or set(config.exec_clients) != {"SANDBOX"}:
        raise RuntimeError("HL_TESTNET_SINGLE_NATIVE_ROUTE_REQUIRED")
    data = config.data_clients["HYPERLIQUID-MAINNET-DATA"]
    execution = config.exec_clients["SANDBOX"]
    if not isinstance(data, HyperliquidDataClientConfig) or not isinstance(execution, SandboxExecutionClientConfig):
        raise RuntimeError("HL_TESTNET_NATIVE_CONFIG_REQUIRED")
    if data.environment is not PUBLIC_MAINNET_ENVIRONMENT:
        raise RuntimeError("HL_TESTNET_MAINNET_OR_UNSET_ENVIRONMENT")
    if execution.venue != "HYPERLIQUID" or execution.base_currency != "USDC":
        raise RuntimeError("HL_TESTNET_SANDBOX_VENUE_OR_CURRENCY_MISMATCH")
    if EXECUTION_FACTORY_ALLOWLIST != (SandboxLiveExecClientFactory,):
        raise RuntimeError("HL_TESTNET_EXECUTION_ALLOWLIST_MISMATCH")


class HyperliquidTestnetNode:
    """One OS-process owner of public feeds and a local Sandbox account."""
    def __init__(self, *, instance: TestnetInstanceConfig, candidate: Candidate, state: PaperRuntime) -> None:
        self.instance, self.candidate, self.state = instance, candidate, state
        self.scrubbed_environment = scrub_private_execution_environment()
        self.candidate_hash = candidate_content_hash(candidate)
        self.loop = asyncio.new_event_loop()
        self.config = hyperliquid_testnet_node_config(trader_id=instance.trader_id)
        assert_native_testnet_only(self.config)
        self.node = TradingNode(config=self.config, loop=self.loop)
        self.node.add_data_client_factory("HYPERLIQUID", HyperliquidLiveDataClientFactory)
        self.node.add_exec_client_factory("SANDBOX", SandboxLiveExecClientFactory)
        self.node.build()
        self.hooks = LifecycleHooks(state)
        self.feed = FeedBook(ids=TESTNET_IDS, native_event_sink=self.hooks.record_event)
        self.feed_observer: FeedObserver | None = None
        self.prime_error: str | None = None
        self._thread: threading.Thread | None = None

    def prime(self) -> None:
        """Register only public BTC/SOL observation in the D3 running node.

        No trading strategy is registered: this is the execution boundary for
        D3, so neither entries nor reductions/cancels/forced closes can reach
        the native execution client. LifecycleHooks remain separately
        injectable test fixtures for the existing D1 strategy path.
        """
        try:
            client_id = ClientId("HYPERLIQUID-MAINNET-DATA")
            self.feed_observer = FeedObserver(FeedObserverConfig(
                instrument_ids=TESTNET_IDS, client_ids=(client_id, client_id), feed=self.feed,
            ))
            self.node.trader.add_strategy(self.feed_observer)
        except Exception as error:
            self.prime_error = type(error).__name__

    def start(self) -> None:
        if self.prime_error is None:
            self._thread = threading.Thread(target=self.node.run, name="hl-stageg-testnet-native", daemon=True)
            self._thread.start()

    def status(self) -> dict:
        feeds = self.feed.status(time.time_ns())
        ready = bool(feeds) and all(item["state"] == "READY" for item in feeds.values()) and self.prime_error is None
        return {
            "instance_id": self.instance.instance_id,
            "environment": "mainnet-public",
            "node_class": type(self.node).__name__,
            "node_built": self.node.is_built(),
            "node_running": self.node.is_running(),
            "data_client_classes": ["HyperliquidDataClient"],
            "execution_client_classes": [SandboxExecutionClient.__name__],
            "execution_factories": [f"{item.__module__}.{item.__name__}" for item in NATIVE_TESTNET_FACTORIES],
            "execution_factory_allowlist": [f"{SandboxLiveExecClientFactory.__module__}.{SandboxLiveExecClientFactory.__name__}"],
            "live_order_capability": False,
            "candidate_hash": self.candidate_hash,
            "state_db": str(self.instance.state_db),
            "orders_enabled": False,
            "trading_strategy_registered": False,
            "feed_observer_registered": self.feed_observer is not None,
            "feeds": feeds,
            "state": "PUBLIC_FEEDS_READY" if ready else "DATA_STALE/PAUSED",
            "prime_error": self.prime_error,
            "scrubbed_private_environment": list(self.scrubbed_environment),
            # Public rate/mark observations are not account postings. Sandbox
            # commissions/margin are native local-model outcomes, and actual
            # account fee tiers, funding cash and margin remain unknown.
            "accounting": {
                "fees": {"observed": "SANDBOX_NATIVE_FILL_COMMISSION", "modelled": "HYPERLIQUID_ACCOUNT_FEE_TIER_UNKNOWN"},
                "funding": {"observed": "PUBLIC_RATE_AND_MARK_ONLY", "modelled": "UNPOSTED_NO_SANDBOX_CASH_ADJUSTMENT"},
                "margin": {"observed": "NO_REMOTE_ACCOUNT", "modelled": "NATIVE_SANDBOX_INSTRUMENT_MODEL"},
            },
        }
