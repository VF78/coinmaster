"""D3's isolated, one-node Hyperliquid TESTNET integration boundary.

This is intentionally not a second engine or a bespoke exchange transport.
It uses Nautilus 1.231's native Hyperliquid data and execution factories.  The
process is disabled unless its explicit testnet guard and master account
address are present.  The API-wallet private key is deliberately left to the
native client to source from its runtime-only environment variable.
"""
from __future__ import annotations

import asyncio
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Mapping

from nautilus_trader.adapters.hyperliquid import HyperliquidLiveDataClientFactory, HyperliquidLiveExecClientFactory
from nautilus_trader.adapters.hyperliquid.config import HyperliquidDataClientConfig, HyperliquidExecClientConfig
from nautilus_trader.common import Environment
from nautilus_trader.config import InstrumentProviderConfig, LoggingConfig
from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.live.config import LiveExecEngineConfig, RoutingConfig, TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.identifiers import ClientId, InstrumentId

from coinmaster.domain.wave_overlay import Candidate
from coinmaster.ops.native_paper_node import FeedBook, FeedObserver, FeedObserverConfig
from coinmaster.ops.paper import PaperRuntime
from coinmaster.ops.stage_g_config import TestnetInstanceConfig, candidate_content_hash


TESTNET_ENVIRONMENT = nautilus_pyo3.HyperliquidEnvironment.TESTNET
BTC_PERP = InstrumentId.from_str("BTC-USD-PERP.HYPERLIQUID")
SOL_PERP = InstrumentId.from_str("SOL-USD-PERP.HYPERLIQUID")
TESTNET_IDS = (BTC_PERP, SOL_PERP)
ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]{40}")
NATIVE_TESTNET_FACTORIES = (HyperliquidLiveDataClientFactory, HyperliquidLiveExecClientFactory)


@dataclass(frozen=True)
class TestnetAuthContext:
    """Non-secret identity required before authenticated native queries exist."""
    master_account_address: str
    __test__ = False


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


def require_testnet_auth(environment: Mapping[str, str] | None = None) -> TestnetAuthContext:
    """Fail closed before constructing a client capable of account queries.

    The master account is not inferred from the API/agent signer.  Nautilus
    gets ``private_key=None`` below, allowing only its testnet runtime-secret
    resolution; this function never reads, copies, or logs that secret.
    """
    environment = os.environ if environment is None else environment
    if environment.get("COINMASTER_LIVE_ENABLED", "false").lower() != "false":
        raise RuntimeError("HL_TESTNET_REFUSES_LIVE_ENABLED")
    if environment.get("COINMASTER_HL_TESTNET_ENABLED") != "true":
        raise RuntimeError("HL_TESTNET_NOT_EXPLICITLY_ENABLED")
    if environment.get("COINMASTER_HL_TESTNET_ENVIRONMENT") != "testnet":
        raise RuntimeError("HL_TESTNET_ENVIRONMENT_GUARD")
    # Presence only: the value is passed directly to Nautilus through its
    # environment fallback and is never retained by Coinmaster code.
    if not environment.get("HYPERLIQUID_TESTNET_PK"):
        raise RuntimeError("HL_TESTNET_API_WALLET_SECRET_MISSING")
    address = environment.get("COINMASTER_HL_TESTNET_MASTER_ACCOUNT_ADDRESS")
    if not address or not ADDRESS_RE.fullmatch(address):
        raise RuntimeError("HL_TESTNET_MASTER_ACCOUNT_ADDRESS_REQUIRED")
    return TestnetAuthContext(master_account_address=address.lower())


def hyperliquid_testnet_node_config(*, trader_id: str, auth: TestnetAuthContext) -> TradingNodeConfig:
    """Build config for exactly one native TESTNET node and execution route."""
    provider = InstrumentProviderConfig(load_ids=frozenset(TESTNET_IDS))
    routing = RoutingConfig(venues=frozenset({"HYPERLIQUID"}))
    return TradingNodeConfig(
        environment=Environment.LIVE,
        trader_id=trader_id,
        logging=LoggingConfig(log_level="INFO", log_colors=False),
        exec_engine=LiveExecEngineConfig(reconciliation=True),
        data_clients={
            "HYPERLIQUID-TESTNET-DATA": HyperliquidDataClientConfig(
                instrument_provider=provider, routing=routing, environment=TESTNET_ENVIRONMENT,
            ),
        },
        exec_clients={
            "HYPERLIQUID-TESTNET-EXEC": HyperliquidExecClientConfig(
                instrument_provider=provider,
                routing=routing,
                # Keep this None: Nautilus resolves HYPERLIQUID_TESTNET_PK at
                # runtime, and Coinmaster never receives/logs that value.
                private_key=None,
                account_address=auth.master_account_address,
                environment=TESTNET_ENVIRONMENT,
                include_builder_attribution=False,
            ),
        },
    )


def assert_native_testnet_only(config: TradingNodeConfig, auth: TestnetAuthContext) -> None:
    """Reject mainnet, an extra node route, or implicit agent-account query."""
    if set(config.data_clients) != {"HYPERLIQUID-TESTNET-DATA"} or set(config.exec_clients) != {"HYPERLIQUID-TESTNET-EXEC"}:
        raise RuntimeError("HL_TESTNET_SINGLE_NATIVE_ROUTE_REQUIRED")
    data = config.data_clients["HYPERLIQUID-TESTNET-DATA"]
    execution = config.exec_clients["HYPERLIQUID-TESTNET-EXEC"]
    if not isinstance(data, HyperliquidDataClientConfig) or not isinstance(execution, HyperliquidExecClientConfig):
        raise RuntimeError("HL_TESTNET_NATIVE_CONFIG_REQUIRED")
    if data.environment is not TESTNET_ENVIRONMENT or execution.environment is not TESTNET_ENVIRONMENT:
        raise RuntimeError("HL_TESTNET_MAINNET_OR_UNSET_ENVIRONMENT")
    if execution.private_key is not None or execution.vault_address is not None or execution.account_address != auth.master_account_address:
        raise RuntimeError("HL_TESTNET_ACCOUNT_QUERY_TARGET_REQUIRED")


class HyperliquidTestnetNode:
    """One OS-process owner of one Nautilus node; no activation of order flow."""
    def __init__(self, *, instance: TestnetInstanceConfig, candidate: Candidate, state: PaperRuntime, auth: TestnetAuthContext) -> None:
        self.instance, self.candidate, self.state, self.auth = instance, candidate, state, auth
        self.candidate_hash = candidate_content_hash(candidate)
        self.loop = asyncio.new_event_loop()
        self.config = hyperliquid_testnet_node_config(trader_id=instance.trader_id, auth=auth)
        assert_native_testnet_only(self.config, auth)
        self.node = TradingNode(config=self.config, loop=self.loop)
        self.node.add_data_client_factory("HYPERLIQUID", HyperliquidLiveDataClientFactory)
        self.node.add_exec_client_factory("HYPERLIQUID", HyperliquidLiveExecClientFactory)
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
            client_id = ClientId("HYPERLIQUID-TESTNET-DATA")
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
            "environment": "testnet",
            "node_class": type(self.node).__name__,
            "node_built": self.node.is_built(),
            "node_running": self.node.is_running(),
            "data_client_classes": ["HyperliquidDataClient"],
            "execution_client_classes": ["HyperliquidExecutionClient"],
            "execution_factories": [f"{item.__module__}.{item.__name__}" for item in NATIVE_TESTNET_FACTORIES],
            "candidate_hash": self.candidate_hash,
            "state_db": str(self.instance.state_db),
            "authenticated_query_account": self.auth.master_account_address,
            "orders_enabled": False,
            "trading_strategy_registered": False,
            "feed_observer_registered": self.feed_observer is not None,
            "feeds": feeds,
            "state": "PUBLIC_FEEDS_READY" if ready else "DATA_STALE/PAUSED",
            "prime_error": self.prime_error,
        }
