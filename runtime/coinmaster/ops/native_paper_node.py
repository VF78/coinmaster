"""Fail-closed native Nautilus paper TradingNode.

This module has one execution route only: Nautilus' sandbox execution client
for the BYBIT venue.  The Bybit and Hyperliquid adapters are data clients only;
private venue execution factories are deliberately neither imported nor
registered here.
"""
from __future__ import annotations

import asyncio
import os
import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from nautilus_trader.adapters.bybit import BybitLiveDataClientFactory
from nautilus_trader.adapters.bybit.config import BybitDataClientConfig
from nautilus_trader.adapters.hyperliquid import HyperliquidLiveDataClientFactory
from nautilus_trader.adapters.hyperliquid.config import HyperliquidDataClientConfig
from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.adapters.sandbox.factory import SandboxLiveExecClientFactory
from nautilus_trader.common import Environment
from nautilus_trader.config import InstrumentProviderConfig, LoggingConfig, StrategyConfig
from nautilus_trader.live.config import LiveExecEngineConfig, RoutingConfig, TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.data import FundingRateUpdate, MarkPriceUpdate, QuoteTick
from nautilus_trader.model.identifiers import ClientId, InstrumentId
from nautilus_trader.trading.strategy import Strategy


BYBIT_IDS = (
    InstrumentId.from_str("BTCUSDT-LINEAR.BYBIT"),
    InstrumentId.from_str("SOLUSDT-LINEAR.BYBIT"),
)
EXECUTION_FACTORY_ALLOWLIST = (SandboxLiveExecClientFactory,)
MAX_DATA_AGE_NS = 120_000_000_000
WARMUP_DAYS = 730


def scrub_private_execution_environment(environment: dict[str, str] | None = None) -> tuple[str, ...]:
    """Remove private venue credentials so public clients can never source them.

    The adapters default to environment credentials when config fields are
    ``None``.  Scrubbing before their construction makes that fallback safe.
    """
    environment = os.environ if environment is None else environment
    removed: list[str] = []
    for name in list(environment):
        upper = name.upper()
        private_bybit = upper.startswith("BYBIT_") and any(
            token in upper for token in ("KEY", "SECRET", "PRIVATE", "WALLET")
        )
        private_hyperliquid = upper.startswith("HYPERLIQUID_") and any(
            token in upper for token in ("KEY", "SECRET", "PRIVATE", "WALLET")
        )
        if private_bybit or private_hyperliquid:
            environment.pop(name, None)
            removed.append(name)
    return tuple(sorted(removed))


def _history_ready(path: Path) -> tuple[bool, str]:
    """Require a gap-free, public-data manifest with the full daily warmup."""
    try:
        import json

        manifest = json.loads(path.read_text())
        symbols = {item["symbol"]: item for item in manifest["symbols"]}
        for symbol in ("BTCUSDT", "SOLUSDT"):
            reports = symbols[symbol]["reports"]
            daily = next(item for item in reports if item["series"] == "kline_daily")
            if daily["expected"] < WARMUP_DAYS or daily["missing"] or daily["duplicate_timestamps"]:
                return False, f"INVALID_WARMUP_{symbol}"
    except (OSError, KeyError, StopIteration, ValueError, TypeError):
        return False, "MISSING_OR_INVALID_WARMUP_MANIFEST"
    return True, "READY"


def native_paper_node_config() -> TradingNodeConfig:
    """Return config containing public data and exactly one sandbox exec route."""
    return TradingNodeConfig(
        environment=Environment.LIVE,
        trader_id="COINMASTER-PAPER",
        logging=LoggingConfig(log_level="INFO", log_colors=False),
        # Sandbox cannot report a remote account/order history.  It is the
        # native source of this paper account, so remote reconciliation is not
        # meaningful; PaperRuntime snapshots provide the durable restart gate.
        exec_engine=LiveExecEngineConfig(reconciliation=False),
        data_clients={
            "BYBIT-PUBLIC": BybitDataClientConfig(
                api_key=None,
                api_secret=None,
                instrument_provider=InstrumentProviderConfig(load_ids=frozenset(BYBIT_IDS)),
                routing=RoutingConfig(venues=frozenset({"BYBIT"})),
            ),
            "HYPERLIQUID-PUBLIC": HyperliquidDataClientConfig(
                # Hyperliquid's provider supports filtered load_all, not
                # per-ID loading.  This loads only BTC/SOL perpetuals into
                # the cache and does not require a wallet.
                instrument_provider=InstrumentProviderConfig(
                    load_all=True,
                    filters={"bases": ("BTC", "SOL"), "market_types": ("perp",)},
                ),
                routing=RoutingConfig(venues=frozenset({"HYPERLIQUID"})),
            ),
        },
        exec_clients={
            "SANDBOX": SandboxExecutionClientConfig(
                venue="BYBIT",
                starting_balances=["100000 USDT"],
                base_currency="USDT",
                default_leverage=Decimal("1"),
                use_reduce_only=True,
            ),
        },
    )


def assert_sandbox_only(config: TradingNodeConfig, factories: tuple[type, ...]) -> None:
    """Reject any config/factory expansion before a node is built."""
    if set(config.exec_clients) != {"SANDBOX"}:
        raise RuntimeError("PAPER_EXEC_CONFIG_NOT_SANDBOX_ONLY")
    sandbox = config.exec_clients["SANDBOX"]
    if not isinstance(sandbox, SandboxExecutionClientConfig):
        raise RuntimeError("PAPER_EXEC_CONFIG_NOT_SANDBOX")
    if sandbox.venue != "BYBIT":
        raise RuntimeError("PAPER_SANDBOX_VENUE_MISMATCH")
    if factories != EXECUTION_FACTORY_ALLOWLIST:
        raise RuntimeError("PAPER_EXEC_FACTORY_NOT_SANDBOX_ONLY")


@dataclass
class FeedBook:
    """Native callback observations only; it never manufactures market data."""
    ids: tuple[InstrumentId, ...] = ()
    _lock: threading.Lock = field(default_factory=threading.Lock)
    quotes: dict[str, tuple[str, int]] = field(default_factory=dict)
    marks: dict[str, tuple[str, int]] = field(default_factory=dict)
    funding: dict[str, tuple[str, int, int | None]] = field(default_factory=dict)
    native_event_sink: Callable[[str, str], bool] | None = None

    def quote(self, tick: QuoteTick) -> None:
        with self._lock:
            self.quotes[str(tick.instrument_id)] = (str((tick.bid_price.as_decimal() + tick.ask_price.as_decimal()) / 2), tick.ts_init)

    def mark(self, update: MarkPriceUpdate) -> None:
        with self._lock:
            self.marks[str(update.instrument_id)] = (str(update.value.as_decimal()), update.ts_init)

    def funding_rate(self, update: FundingRateUpdate) -> None:
        with self._lock:
            self.funding[str(update.instrument_id)] = (str(update.rate), update.ts_init, update.next_funding_ns)

    def native_event(self, event_id: str, kind: str) -> None:
        if self.native_event_sink is not None:
            self.native_event_sink(event_id, kind)

    def status(self, now_ns: int) -> dict[str, dict[str, Any]]:
        with self._lock:
            result: dict[str, dict[str, Any]] = {}
            for instrument_id in self.ids:
                key = str(instrument_id)
                mark = self.marks.get(key)
                quote = self.quotes.get(key)
                funding = self.funding.get(key)
                ages = [now_ns - item[1] for item in (mark, quote, funding) if item]
                result[key] = {
                    "mark": mark[0] if mark else None,
                    "mark_age_ns": now_ns - mark[1] if mark else None,
                    "quote_age_ns": now_ns - quote[1] if quote else None,
                    "funding_rate": funding[0] if funding else None,
                    "funding_age_ns": now_ns - funding[1] if funding else None,
                    "next_funding_ns": funding[2] if funding else None,
                    "state": "READY" if len(ages) == 3 and max(ages) <= MAX_DATA_AGE_NS else "DATA_STALE",
                }
            return result


class FeedObserverConfig(StrategyConfig, frozen=True):
    instrument_ids: tuple[InstrumentId, ...]
    client_ids: tuple[ClientId, ...]
    feed: FeedBook


class FeedObserver(Strategy):
    """Subscribes to native public feeds and observes native event callbacks."""
    def on_start(self) -> None:
        for instrument_id, client_id in zip(self.config.instrument_ids, self.config.client_ids, strict=True):
            self.subscribe_quote_ticks(instrument_id, client_id=client_id)
            self.subscribe_mark_prices(instrument_id, client_id=client_id)
            self.subscribe_funding_rates(instrument_id, client_id=client_id)

    def on_quote_tick(self, tick: QuoteTick) -> None:
        self.config.feed.quote(tick)

    def on_mark_price(self, update: MarkPriceUpdate) -> None:
        self.config.feed.mark(update)

    def on_funding_rate(self, update: FundingRateUpdate) -> None:
        self.config.feed.funding_rate(update)

    def on_order_event(self, event) -> None:
        self.config.feed.native_event(str(event.client_order_id), "order")

    def on_order_filled(self, event) -> None:
        self.config.feed.native_event(str(event.trade_id), "fill")

    def on_position_event(self, event) -> None:
        self.config.feed.native_event(f"{event.position_id}:{event.ts_init}", "position")


class NativePaperNode:
    """Owns a single native node and the public-feed warmup/readiness gates."""
    def __init__(self, history_manifest: Path, native_event_sink: Callable[[str, str], bool] | None = None) -> None:
        if os.getenv("COINMASTER_LIVE_ENABLED", "false").lower() != "false":
            raise RuntimeError("PAPER_WORKER_REFUSES_LIVE_ENABLED")
        self.scrubbed_environment = scrub_private_execution_environment()
        self.history_ready, self.history_state = _history_ready(history_manifest)
        self.loop = asyncio.new_event_loop()
        self.config = native_paper_node_config()
        assert_sandbox_only(self.config, EXECUTION_FACTORY_ALLOWLIST)
        self.node = TradingNode(config=self.config, loop=self.loop)
        self.node.add_data_client_factory("BYBIT", BybitLiveDataClientFactory)
        self.node.add_data_client_factory("HYPERLIQUID", HyperliquidLiveDataClientFactory)
        self.node.add_exec_client_factory("SANDBOX", SandboxLiveExecClientFactory)
        self.node.build()
        self.feed = FeedBook(native_event_sink=native_event_sink)
        self.prime_error: str | None = None
        self._thread: threading.Thread | None = None

    async def _prime_public_instruments(self) -> tuple[InstrumentId, ...]:
        """Load/cache public instruments before the sandbox client's connect()."""
        clients = self.node.kernel.data_engine._clients  # Nautilus has no public lookup API.
        await clients[ClientId("BYBIT")].instrument_provider.initialize()
        await clients[ClientId("HYPERLIQUID")].instrument_provider.initialize()
        for client in clients.values():
            provider = client.instrument_provider
            for currency in provider.currencies().values():
                self.node.kernel.cache.add_currency(currency)
            for instrument in provider.get_all().values():
                self.node.kernel.cache.add_instrument(instrument)
        hyperliquid_ids = tuple(
            instrument.id
            for instrument in self.node.cache.instruments(venue="HYPERLIQUID")
            if getattr(instrument.base_currency, "code", None) in {"BTC", "SOL"}
        )
        if len(hyperliquid_ids) != 2 or any(self.node.cache.instrument(item) is None for item in BYBIT_IDS):
            raise RuntimeError("PAPER_REQUIRED_INSTRUMENTS_NOT_LOADED")
        return (*BYBIT_IDS, *sorted(hyperliquid_ids, key=str))

    def prime(self) -> None:
        try:
            instrument_ids = self.loop.run_until_complete(self._prime_public_instruments())
            self.feed.ids = instrument_ids
            self.node.trader.add_strategy(
                FeedObserver(
                    FeedObserverConfig(
                        instrument_ids=instrument_ids,
                        client_ids=(ClientId("BYBIT"), ClientId("BYBIT"), ClientId("HYPERLIQUID"), ClientId("HYPERLIQUID")),
                        feed=self.feed,
                    ),
                ),
            )
        except Exception as error:
            self.prime_error = type(error).__name__

    def start(self) -> None:
        # A failed public prime is deliberately not retried by an alternate
        # transport.  The process still exposes fail-closed health.
        if self.prime_error is not None:
            return
        self._thread = threading.Thread(target=self.node.run, name="coinmaster-native-paper", daemon=True)
        self._thread.start()

    def status(self) -> dict[str, Any]:
        now_ns = time.time_ns()
        feeds = self.feed.status(now_ns)
        data_ready = bool(feeds) and all(item["state"] == "READY" for item in feeds.values())
        ready = self.history_ready and data_ready and self.prime_error is None
        return {
            "node_class": type(self.node).__name__,
            "node_built": self.node.is_built(),
            "node_running": self.node.is_running(),
            "data_client_classes": ["BybitDataClient", "HyperliquidDataClient"],
            "execution_client_classes": ["SandboxExecutionClient"],
            "execution_factory_allowlist": [f"{SandboxLiveExecClientFactory.__module__}.{SandboxLiveExecClientFactory.__name__}"],
            "live_order_capability": False,
            "warmup": {"days_required": WARMUP_DAYS, "state": self.history_state},
            # Sandbox does not generate venue funding cash adjustments.  A
            # posting remains blocked until a venue settlement mark and stable
            # funding event ID are normalized into the durable journal.
            "funding_posting_state": "UNPOSTED_REQUIRES_CONFIRMED_SETTLEMENT_MARK",
            "feeds": feeds,
            "state": "READY" if ready else "DATA_STALE/PAUSED",
            "prime_error": self.prime_error,
            "scrubbed_private_environment": list(self.scrubbed_environment),
        }
