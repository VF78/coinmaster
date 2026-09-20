"""Fail-closed native Nautilus paper TradingNode.

This module has one execution route only: Nautilus' sandbox execution client
for the BYBIT venue.  The Bybit and Hyperliquid adapters are data clients only;
private venue execution factories are deliberately neither imported nor
registered here.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from nautilus_trader.adapters.bybit import BybitLiveDataClientFactory
from nautilus_trader.adapters.bybit.config import BybitDataClientConfig
from nautilus_trader.adapters.hyperliquid import HyperliquidLiveDataClientFactory
from nautilus_trader.adapters.hyperliquid.config import HyperliquidDataClientConfig
from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.adapters.sandbox.execution import SandboxExecutionClient
from nautilus_trader.adapters.sandbox.factory import SandboxLiveExecClientFactory
from nautilus_trader.common import Environment
from nautilus_trader.config import InstrumentProviderConfig, LoggingConfig, StrategyConfig
from nautilus_trader.live.config import LiveExecEngineConfig, RoutingConfig, TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.data import BarSpecification, BarType, FundingRateUpdate, MarkPriceUpdate, QuoteTick
from nautilus_trader.model.enums import AggregationSource, BarAggregation, PriceType
from nautilus_trader.model.identifiers import ClientId, InstrumentId, Venue
from nautilus_trader.trading.strategy import Strategy

from coinmaster.domain.wave_overlay import Candidate, DailyBar
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig
from coinmaster.venues.marks import venue_mark_data_type


BYBIT_IDS = (
    InstrumentId.from_str("BTCUSDT-LINEAR.BYBIT"),
    InstrumentId.from_str("SOLUSDT-LINEAR.BYBIT"),
)
EXECUTION_FACTORY_ALLOWLIST = (SandboxLiveExecClientFactory,)
MAX_DATA_AGE_NS = 120_000_000_000
# Bybit's captured public manifest specifies the BTCUSDT/SOLUSDT linear
# funding cadence as eight hours.  This is only a bounded fallback when the
# live update lacks the venue-provided next settlement timestamp; it is never
# applied to Hyperliquid, whose cadence must come from its own update.
BYBIT_FUNDING_INTERVAL_NS = 8 * 60 * 60 * 1_000_000_000
# Hyperliquid's official funding documentation specifies hourly payments. Its
# adapter currently exposes no next settlement timestamp, so this is a
# venue-documented scheduling window, not a guessed transport cadence.
HYPERLIQUID_FUNDING_INTERVAL_NS = 60 * 60 * 1_000_000_000
WARMUP_DAYS = 730
DAY_NS = 86_400_000_000_000


@dataclass(frozen=True)
class WarmupBundle:
    bars: tuple[DailyBar, ...]
    source_hash: str
    rows: int
    first_open_ns: int
    last_close_ns: int


def paper_candidate(name: str) -> Candidate:
    """Return an explicitly selected paper candidate, never an optimizer pick."""
    if name == "corrected-v0":
        return Candidate()
    if name == "research-6.48":
        # Research-only candidate: selecting it requires an explicit service
        # configuration and is surfaced in health/config hashing.
        from dataclasses import replace
        return replace(Candidate(), btc_notional_multiplier=6.48)
    raise ValueError("unknown paper strategy config")


def candidate_hash(name: str, candidate: Candidate) -> str:
    from dataclasses import asdict
    return hashlib.sha256(json.dumps({"name": name, "candidate": asdict(candidate)}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sandbox_cash_posting_supported() -> bool:
    """Pinned 1.231 client API check; only SimulationModule.exchange has it."""
    return callable(getattr(SandboxExecutionClient, "adjust_account", None))


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


def _load_warmup(path: Path) -> tuple[WarmupBundle | None, str]:
    """Verify and return causal BTC/SOL daily seed bars from immutable data."""
    try:
        manifest = json.loads(path.read_text())
        if manifest["schema"] != "coinmaster-paper-warmup-v1":
            return None, "INVALID_WARMUP_SCHEMA"
        rows_by_symbol: dict[str, list[dict[str, Any]]] = {}
        for symbol in ("BTCUSDT", "SOLUSDT"):
            item = manifest["symbols"][symbol]
            if item["daily_rows"] < WARMUP_DAYS or item["daily_gaps"] or item["daily_duplicates"]:
                return None, f"INVALID_WARMUP_{symbol}"
            daily = path.parent / item["daily_path"]
            funding = path.parent / item["funding_path"]
            for artifact, expected in ((daily, item["daily_sha256"]), (funding, item["funding_sha256"])):
                if hashlib.sha256(artifact.read_bytes()).hexdigest() != expected:
                    return None, f"WARMUP_HASH_MISMATCH_{symbol}"
            import pyarrow.parquet as pq
            rows = pq.read_table(daily).to_pylist()
            if len(rows) < WARMUP_DAYS or any(row.get("mark_close") is None for row in rows):
                return None, f"INVALID_WARMUP_DAILY_DATA_{symbol}"
            rows_by_symbol[symbol] = rows
    except (OSError, KeyError, ValueError, TypeError):
        return None, "MISSING_OR_INVALID_WARMUP_MANIFEST"
    btc_rows, sol_rows = rows_by_symbol["BTCUSDT"], rows_by_symbol["SOLUSDT"]
    if len(btc_rows) != len(sol_rows) or any(left["open_time_ms"] != right["open_time_ms"] for left, right in zip(btc_rows, sol_rows)):
        return None, "WARMUP_SYMBOL_SESSION_MISMATCH"
    bars: list[DailyBar] = []
    for btc, sol in zip(btc_rows, sol_rows):
        open_ns = int(btc["open_time_ms"]) * 1_000_000
        close_ns = open_ns + DAY_NS
        close = datetime.fromtimestamp(close_ns / 1_000_000_000, UTC)
        bars.append(DailyBar(
            datetime.fromtimestamp(open_ns / 1_000_000_000, UTC),
            close,
            close,  # static verified history was available before live start
            float(btc["open"]), float(btc["close"]), float(sol["close"]),
        ))
    return WarmupBundle(tuple(bars), manifest["source_manifest_sha256"], len(bars), int(btc_rows[0]["open_time_ms"]) * 1_000_000, int(btc_rows[-1]["open_time_ms"]) * 1_000_000 + DAY_NS), "READY"


def _history_ready(path: Path) -> tuple[bool, str]:
    """Compatibility probe for callers that need only the fail-closed gate."""
    bundle, state = _load_warmup(path)
    return bundle is not None, state


def bybit_daily_bar_type(instrument_id: InstrumentId) -> BarType:
    return BarType(instrument_id, BarSpecification(1, BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL)


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
    mark_history: dict[str, list[tuple[Decimal, int]]] = field(default_factory=dict)
    funding_history: dict[str, list[tuple[Decimal, int, int | None]]] = field(default_factory=dict)
    native_event_sink: Callable[[str, str], bool] | None = None

    def quote(self, tick: QuoteTick) -> None:
        with self._lock:
            self.quotes[str(tick.instrument_id)] = (str((tick.bid_price.as_decimal() + tick.ask_price.as_decimal()) / 2), tick.ts_init)

    def mark(self, update: MarkPriceUpdate) -> None:
        with self._lock:
            self.marks[str(update.instrument_id)] = (str(update.value.as_decimal()), update.ts_init)
            history = self.mark_history.setdefault(str(update.instrument_id), [])
            history.append((update.value.as_decimal(), update.ts_event))
            del history[:-32]

    def funding_rate(self, update: FundingRateUpdate) -> None:
        with self._lock:
            self.funding[str(update.instrument_id)] = (str(update.rate), update.ts_init, update.next_funding_ns)
            history = self.funding_history.setdefault(str(update.instrument_id), [])
            history.append((Decimal(update.rate), update.ts_event, update.next_funding_ns))
            del history[:-32]

    def due_funding(self, now_ns: int) -> tuple[dict[str, Any], ...]:
        """Normalize stable Bybit settlement IDs with only causal live marks."""
        with self._lock:
            result: list[dict[str, Any]] = []
            for instrument_id in self.ids:
                key = str(instrument_id)
                candidates = [item for item in self.funding_history.get(key, []) if item[2] is not None and item[1] <= item[2] <= now_ns]
                if not candidates:
                    continue
                rate, _, settlement_ns = max(candidates, key=lambda item: item[1])
                assert settlement_ns is not None
                marks = [item for item in self.mark_history.get(key, []) if item[1] <= settlement_ns]
                if not marks:
                    continue  # Never borrow a post-settlement mark.
                mark, mark_ts = max(marks, key=lambda item: item[1])
                result.append({
                    "event_id": f"bybit:{key}:{settlement_ns}",
                    "instrument_id": key,
                    "settlement_ns": settlement_ns,
                    "rate": rate,
                    "mark": mark,
                    "mark_ts_ns": mark_ts,
                })
            return tuple(result)

    def native_event(self, event_id: str, kind: str) -> None:
        if self.native_event_sink is not None:
            self.native_event_sink(event_id, kind)

    @staticmethod
    def _funding_current(instrument_id: InstrumentId, received_ns: int, next_funding_ns: int | None, now_ns: int) -> bool:
        """Keep a rate current through its venue-defined settlement window.

        Quotes and marks are executable/marking inputs and stay on the short
        transport TTL. Funding is a scheduled observation, so a 120-second
        quote TTL is not a valid freshness rule for it. Missing scheduling
        metadata remains fail-closed except for the verified Bybit 8h cadence.
        """
        if instrument_id.venue == Venue("HYPERLIQUID"):
            # Hyperliquid's subscribed active-asset-context update exposes no
            # next settlement timestamp. Its official venue rule is hourly
            # funding, so accept this rate through that documented window;
            # after it (plus transport grace) a missing update is stale.
            return now_ns <= received_ns + HYPERLIQUID_FUNDING_INTERVAL_NS + MAX_DATA_AGE_NS
        deadline = next_funding_ns
        if deadline is None and instrument_id.venue == Venue("BYBIT"):
            deadline = received_ns + BYBIT_FUNDING_INTERVAL_NS
        return deadline is not None and now_ns <= deadline + MAX_DATA_AGE_NS

    def status(self, now_ns: int) -> dict[str, dict[str, Any]]:
        with self._lock:
            result: dict[str, dict[str, Any]] = {}
            for instrument_id in self.ids:
                key = str(instrument_id)
                mark = self.marks.get(key)
                quote = self.quotes.get(key)
                funding = self.funding.get(key)
                quote_mark_ready = bool(mark and quote) and all(
                    now_ns - item[1] <= MAX_DATA_AGE_NS for item in (mark, quote)
                )
                funding_ready = funding is not None and self._funding_current(instrument_id, funding[1], funding[2], now_ns)
                result[key] = {
                    "mark": mark[0] if mark else None,
                    "mark_age_ns": now_ns - mark[1] if mark else None,
                    "quote_age_ns": now_ns - quote[1] if quote else None,
                    "funding_rate": funding[0] if funding else None,
                    "funding_age_ns": now_ns - funding[1] if funding else None,
                    "next_funding_ns": funding[2] if funding else None,
                    "state": "READY" if quote_mark_ready and funding_ready else "DATA_STALE",
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
    def __init__(self, history_manifest: Path, native_event_sink: Callable[[str, str], bool] | None = None, entries_gate: Callable[[], bool] | None = None, submission_sink: object | None = None, strategy_name: str = "corrected-v0") -> None:
        if os.getenv("COINMASTER_LIVE_ENABLED", "false").lower() != "false":
            raise RuntimeError("PAPER_WORKER_REFUSES_LIVE_ENABLED")
        self.scrubbed_environment = scrub_private_execution_environment()
        self.warmup_bundle, self.history_state = _load_warmup(history_manifest)
        self.history_ready = self.warmup_bundle is not None
        self.strategy_name = strategy_name
        self.candidate = paper_candidate(strategy_name)
        self.strategy_hash = candidate_hash(strategy_name, self.candidate)
        self.entries_gate = entries_gate
        self.submission_sink = submission_sink
        self.loop = asyncio.new_event_loop()
        self.config = native_paper_node_config()
        assert_sandbox_only(self.config, EXECUTION_FACTORY_ALLOWLIST)
        self.node = TradingNode(config=self.config, loop=self.loop)
        self.node.add_data_client_factory("BYBIT", BybitLiveDataClientFactory)
        self.node.add_data_client_factory("HYPERLIQUID", HyperliquidLiveDataClientFactory)
        self.node.add_exec_client_factory("SANDBOX", SandboxLiveExecClientFactory)
        self.node.build()
        self.feed = FeedBook(native_event_sink=native_event_sink)
        self.strategy: WaveOverlayStrategy | None = None
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
            for instrument in self.node.cache.instruments(venue=Venue("HYPERLIQUID"))
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
            # Daily bars come directly from Bybit public data.  The strategy
            # consumes the live MarkPriceUpdate as a VenueMark-equivalent
            # dual input, never as quote/MID/execution data.
            btc_bar, sol_bar = bybit_daily_bar_type(BYBIT_IDS[0]), bybit_daily_bar_type(BYBIT_IDS[1])
            self.strategy = WaveOverlayStrategy(WaveOverlayStrategyConfig(
                btc_id=BYBIT_IDS[0],
                sol_id=BYBIT_IDS[1],
                btc_bar_type=btc_bar,
                sol_bar_type=sol_bar,
                btc_mark_data_type=venue_mark_data_type(BYBIT_IDS[0]),
                sol_mark_data_type=venue_mark_data_type(BYBIT_IDS[1]),
                mark_client_id=ClientId("BYBIT"),
                live_mark_client_id=ClientId("BYBIT"),
                active_seed=Decimal("100000"),
                tier_selected_leverage=((BYBIT_IDS[0], Decimal("40")), (BYBIT_IDS[1], Decimal("20"))),
                max_mark_age_ns=MAX_DATA_AGE_NS,
                candidate=self.candidate,
                seed_bars=self.warmup_bundle.bars if self.warmup_bundle else (),
                entries_enabled=self.history_ready,
                entries_gate=self._entries_enabled,
                event_sink=self.feed.native_event_sink,
                submission_sink=self.submission_sink,
            ))
            self.node.trader.add_strategy(self.strategy)
        except Exception as error:
            self.prime_error = type(error).__name__

    def start(self) -> None:
        # A failed public prime is deliberately not retried by an alternate
        # transport.  The process still exposes fail-closed health.
        if self.prime_error is not None:
            return
        self._thread = threading.Thread(target=self.node.run, name="coinmaster-native-paper", daemon=True)
        self._thread.start()

    def _entries_enabled(self) -> bool:
        external = self.entries_gate() if self.entries_gate is not None else True
        return self.history_ready and self.prime_error is None and external and bool(self.feed.status(time.time_ns())) and all(
            item["state"] == "READY" for item in self.feed.status(time.time_ns()).values()
        )

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
            "strategy": {
                "strategy_class": f"{WaveOverlayStrategy.__module__}.{WaveOverlayStrategy.__name__}",
                "registered": self.strategy is not None,
                "running": self.node.is_running() and self.strategy is not None,
                "config_name": self.strategy_name,
                "config_hash": self.strategy_hash,
                "warmup_rows": self.warmup_bundle.rows if self.warmup_bundle else 0,
                "warmup_range_ns": [self.warmup_bundle.first_open_ns, self.warmup_bundle.last_close_ns] if self.warmup_bundle else None,
                "warmup_hash": self.warmup_bundle.source_hash if self.warmup_bundle else None,
                "entries_enabled": self._entries_enabled(),
            },
            # Sandbox does not generate venue funding cash adjustments.  A
            # posting remains blocked until a venue settlement mark and stable
            # funding event ID are normalized into the durable journal.
            "funding_posting_state": "UNPOSTED_REQUIRES_CONFIRMED_SETTLEMENT_MARK",
            "sandbox_cash_posting_supported": sandbox_cash_posting_supported(),
            "feeds": feeds,
            "state": "READY" if ready else "DATA_STALE/PAUSED",
            "prime_error": self.prime_error,
            "scrubbed_private_environment": list(self.scrubbed_environment),
        }
