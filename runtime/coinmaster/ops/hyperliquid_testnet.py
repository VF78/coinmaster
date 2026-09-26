"""Isolated Stage-G public data and mode-specific native execution config.

The running dry-run uses Nautilus 1.231 Sandbox. A distinct live identity
selects Nautilus Hyperliquid execution config but is blocked before node build.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Mapping

from nautilus_trader.adapters.bybit import BybitLiveDataClientFactory
from nautilus_trader.adapters.bybit.config import BybitDataClientConfig
from nautilus_trader.adapters.hyperliquid import HyperliquidLiveDataClientFactory, HyperliquidLiveExecClientFactory
from nautilus_trader.adapters.hyperliquid.config import HyperliquidDataClientConfig, HyperliquidExecClientConfig
from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.adapters.sandbox.execution import SandboxExecutionClient
from nautilus_trader.adapters.sandbox.factory import SandboxLiveExecClientFactory
from nautilus_trader.common import Environment
from nautilus_trader.config import InstrumentProviderConfig, LoggingConfig
from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.live.config import LiveExecEngineConfig, RoutingConfig, TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.currencies import USDC
from nautilus_trader.model.identifiers import ClientId, InstrumentId
from nautilus_trader.model.objects import Money

from coinmaster.domain.wave_overlay import Candidate, DailyBar
from coinmaster.ops.native_paper_node import BYBIT_IDS, DAY_NS, FeedBook, FeedObserver, FeedObserverConfig, WarmupBundle, bybit_daily_bar_type, sandbox_cash_posting_supported, scrub_private_execution_environment
from coinmaster.ops.paper import PaperRuntime
from coinmaster.ops.hl_sandbox_money import SandboxLiveExecClientFactory as HyperliquidUsdcSandboxFactory, model_fx_pair_and_quote, model_fx_ready, native_equity
from coinmaster.ops.hl_native_account import native_usdc_balances
from coinmaster.ops.hl_live_execution import ScopedHyperliquidExecClientFactory
from coinmaster.ops.stage_g_warmup import load_stageg_bybit_warmup
from coinmaster.ops.stage_g_config import TestnetInstanceConfig, candidate_content_hash
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig
from coinmaster.venues.hyperliquid_profile import HyperliquidProfileEnvironment, HyperliquidVenueProfile, normalize_funding_event
from coinmaster.venues.margin_policy import HyperliquidSandboxMarginPolicy
from coinmaster.venues.marks import venue_mark_data_type


PUBLIC_MAINNET_ENVIRONMENT = nautilus_pyo3.HyperliquidEnvironment.MAINNET
BTC_PERP = InstrumentId.from_str("BTC-USD-PERP.HYPERLIQUID")
SOL_PERP = InstrumentId.from_str("SOL-USD-PERP.HYPERLIQUID")
TESTNET_IDS = (BTC_PERP, SOL_PERP)
PUBLIC_DATA_FACTORIES = (BybitLiveDataClientFactory, HyperliquidLiveDataClientFactory)
NATIVE_TESTNET_FACTORIES = (HyperliquidUsdcSandboxFactory,)
SANDBOX_LEVERAGES = {BTC_PERP: Decimal("40"), SOL_PERP: Decimal("20")}
SANDBOX_MARK_MAX_AGE_NS = 120_000_000_000


@dataclass(frozen=True)
class CrossVenueStageGGate:
    """Auditable boundary for sealed Bybit signals and HL Sandbox execution.

    This is deliberately a gate rather than a strategy adapter: changing
    signal venue IDs into execution IDs would relabel historical data and
    invalidate parity. A future adapter must consume this verified mapping.
    """
    signal_ids: tuple[str, str]
    execution_ids: tuple[str, str]
    candidate_hash: str
    strategy_code_hash: str
    execution_policy_hash: str
    warmup_state: str
    margin_policy_state: str
    execution_policy_state: str
    funding_state: str
    capital_state: str
    approval_state: str
    attachable: bool


def _sealed_approval_state(*, candidate_hash: str, strategy_code_hash: str, execution_policy_hash: str, approval_path: Path) -> str:
    try:
        approval = json.loads(approval_path.read_text())
        expected = {"schema", "candidate_sha256", "strategy_sha256", "execution_policy_sha256"}
        if set(approval) != expected or approval["schema"] != "coinmaster-stageg-hl-sandbox-approval-v1":
            return "BLOCKED_SEALED_APPROVAL_SCHEMA"
        if not all(isinstance(approval[item], str) for item in expected - {"schema"}):
            return "BLOCKED_SEALED_APPROVAL_SCHEMA"
        if approval["candidate_sha256"] != candidate_hash:
            return "BLOCKED_SEALED_CANDIDATE_MISMATCH"
        if approval["strategy_sha256"] != strategy_code_hash:
            return "BLOCKED_SEALED_STRATEGY_MISMATCH"
        if approval["execution_policy_sha256"] != execution_policy_hash:
            return "BLOCKED_SEALED_EXECUTION_POLICY_MISMATCH"
        return "SEALED_APPROVAL_MATCH"
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return "BLOCKED_SEALED_APPROVAL_MISSING_OR_INVALID"


def cross_venue_stage_g_gate(*, candidate: Candidate, warmup_manifest: Path, strategy_path: Path, profile_root: Path, now_ns: int | None = None) -> CrossVenueStageGGate:
    """Fail closed before attaching Stage-G to real public HL data.

    Bybit daily data remains the sealed winner's signal source. HL BTC/SOL
    are execution instruments only. Existing strategy code is rejected until
    it no longer imports research-only margin machinery.
    """
    _, warmup_state = load_stageg_bybit_warmup(warmup_manifest, now_ms=None if now_ns is None else now_ns // 1_000_000)
    source = strategy_path.read_bytes()
    strategy_code_hash = hashlib.sha256(source).hexdigest()
    profile = HyperliquidVenueProfile.from_snapshot(profile_root, environment=HyperliquidProfileEnvironment.MAINNET)
    margin_policy_state = "READY_PUBLIC_HL_MAINNET_TIERS_LOCAL_SANDBOX_LEVERAGE" if profile.instruments else "MISSING_HL_MAINNET_PROFILE"
    if b"research.native_fixture" in source or b"TierMarginPolicy" in source:
        margin_policy_state = "BLOCKED_RESEARCH_MARGIN_POLICY"
    execution_policy = {
        "version": "hl-mainnet-public-data-native-sandbox-v1",
        "maker_fee_assumption": "0.00015",
        "taker_fee_assumption": "0.00045",
        "fee_basis": "FIXED_PUBLIC_BASE_RATE_NOT_ACCOUNT_SPECIFIC",
        "execution_quality": "UNKNOWN_NO_24M_BBO_L2_OR_TRADE_TAPE",
        # A public update is evidence of a current rate and *future* schedule,
        # not of a payment which has already settled.  It is therefore useful
        # feed observability, but never an account posting or an attachment
        # blocker for this credential-free virtual run.
        "funding_cash": "OBSERVED_MODELLED_UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT",
    }
    execution_policy_hash = hashlib.sha256(
        json.dumps(execution_policy, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()
    candidate_hash = candidate_content_hash(candidate)
    approval_state = _sealed_approval_state(
        candidate_hash=candidate_hash, strategy_code_hash=strategy_code_hash,
        execution_policy_hash=execution_policy_hash,
        approval_path=profile_root / "configs" / "stage-g-hl-sandbox-approval.json",
    )
    execution_policy_state = "FIXED_PUBLIC_BASE_FEES_NATIVE_SANDBOX_COMMISSION_AUDITED"
    funding_state = "OBSERVED_MODELLED_UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT"
    capital_state = "NOMINAL_10000_USDC_SANDBOX_SEED_VS_10000_USDT_RESEARCH_1_TO_1_ASSUMPTION"
    attachable = (
        warmup_state == "READY"
        and margin_policy_state == "READY_PUBLIC_HL_MAINNET_TIERS_LOCAL_SANDBOX_LEVERAGE"
        and approval_state == "SEALED_APPROVAL_MATCH"
    )
    return CrossVenueStageGGate(
        signal_ids=("BTCUSDT-LINEAR.BYBIT", "SOLUSDT-LINEAR.BYBIT"),
        execution_ids=(str(BTC_PERP), str(SOL_PERP)),
        candidate_hash=candidate_hash,
        strategy_code_hash=strategy_code_hash,
        execution_policy_hash=execution_policy_hash,
        warmup_state=warmup_state,
        margin_policy_state=margin_policy_state,
        execution_policy_state=execution_policy_state,
        funding_state=funding_state,
        capital_state=capital_state,
        approval_state=approval_state,
        attachable=attachable,
    )


def load_stageg_warmup_bundle(path: Path, *, now_ns: int | None = None) -> tuple[WarmupBundle | None, str]:
    """Return feature-only Bybit history while retaining its source identity."""
    rows, state = load_stageg_bybit_warmup(path, now_ms=None if now_ns is None else now_ns // 1_000_000)
    if state != "READY":
        return None, state
    btc, sol = rows["BTCUSDT"], rows["SOLUSDT"]
    bars = []
    for btc_row, sol_row in zip(btc, sol, strict=True):
        open_ns = int(btc_row["open_time_ms"]) * 1_000_000
        close_ns = open_ns + DAY_NS
        bars.append(DailyBar(
            datetime.fromtimestamp(open_ns / 1_000_000_000, UTC),
            datetime.fromtimestamp(close_ns / 1_000_000_000, UTC),
            datetime.fromtimestamp(close_ns / 1_000_000_000, UTC),
            float(btc_row["open"]), float(btc_row["close"]), float(sol_row["close"]),
        ))
    return WarmupBundle(
        tuple(bars), hashlib.sha256(path.read_bytes()).hexdigest(), len(bars),
        int(btc[0]["open_time_ms"]) * 1_000_000, int(btc[-1]["open_time_ms"]) * 1_000_000 + DAY_NS,
    ), "READY"


class NativeSandboxFundingPoster:
    """Causal, durable native USDC funding post through Sandbox exchange.

    A pre-post journal reservation intentionally locks the virtual account to
    MANAGE_ONLY on a crash between persistence and ``adjust_account``.
    """

    def __init__(self, *, exchange, runtime: PaperRuntime) -> None:
        self.exchange = exchange
        self.runtime = runtime

    def __call__(self, *, instrument_id: InstrumentId, settlement_ns: int, rate: Decimal, settlement_mark: Decimal, signed_quantity: Decimal) -> None:
        event = normalize_funding_event(
            environment=HyperliquidProfileEnvironment.MAINNET,
            instrument_id=str(instrument_id), settlement_ns=settlement_ns,
            rate=rate, settlement_mark=settlement_mark,
        )
        accepted, delta = self.runtime.prepare_native_funding(
            event_id=event.event_id, instrument_id=event.instrument_id,
            settlement_ns=event.settlement_ns, rate=event.rate,
            mark=event.settlement_mark, signed_quantity=signed_quantity,
        )
        if not accepted:
            return
        self.exchange.adjust_account(Money(delta, USDC))
        self.runtime.complete_native_funding(event.event_id)


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
        # An order event may be Submitted, Denied, or unresolved.  Only the
        # strategy's native Accepted callback advances the durable ACK state.
        return self.runtime.record_native_event(event_id, kind)

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


def execution_factory_for_mode(mode: str):
    if mode == "sandbox":
        return "SANDBOX", HyperliquidUsdcSandboxFactory
    if mode == "live":
        return "HYPERLIQUID-LIVE", ScopedHyperliquidExecClientFactory
    raise ValueError("UNKNOWN_EXECUTION_MODE")


def hyperliquid_testnet_node_config(*, trader_id: str, starting_cash: Decimal = Decimal("10000"), execution_mode: str = "sandbox") -> TradingNodeConfig:
    """Build one native execution route; constructing the config never loads secrets."""
    execution_factory_for_mode(execution_mode)
    if execution_mode == "sandbox" and (not starting_cash.is_finite() or starting_cash <= 0):
        raise ValueError("INVALID_NATIVE_SANDBOX_STARTING_CASH")
    provider = InstrumentProviderConfig(load_ids=frozenset(TESTNET_IDS))
    routing = RoutingConfig(venues=frozenset({"HYPERLIQUID"}))
    bybit_routing = RoutingConfig(venues=frozenset({"BYBIT"}))
    return TradingNodeConfig(
        environment=Environment.LIVE,
        trader_id=trader_id,
        logging=LoggingConfig(log_level="INFO", log_colors=False),
        # Sandbox has no remote account/order history.  Durable recovery is
        # handled by PaperRuntime and must never be described as exchange
        # reconciliation.
        exec_engine=LiveExecEngineConfig(reconciliation=execution_mode == "live"),
        data_clients={
            "BYBIT-PUBLIC-SIGNAL": BybitDataClientConfig(
                api_key=None, api_secret=None,
                instrument_provider=InstrumentProviderConfig(load_ids=frozenset(BYBIT_IDS)),
                routing=bybit_routing,
            ),
            "HYPERLIQUID-MAINNET-DATA": HyperliquidDataClientConfig(
                instrument_provider=provider, routing=routing, environment=PUBLIC_MAINNET_ENVIRONMENT,
            ),
        },
        exec_clients={
            "SANDBOX": SandboxExecutionClientConfig(
                venue="HYPERLIQUID",
                # Stage-G sealed research begins with 10,000 USDT. The
                # Sandbox denomination uses an explicit nominal 1:1 model.
                starting_balances=[f"{starting_cash} USDC"],
                base_currency="USDC",
                leverages=dict(SANDBOX_LEVERAGES),
                use_reduce_only=True,
                routing=routing,
            ),
        } if execution_mode == "sandbox" else {
            "HYPERLIQUID-LIVE": HyperliquidExecClientConfig(
                instrument_provider=provider, routing=routing,
                environment=PUBLIC_MAINNET_ENVIRONMENT,
                private_key=None, vault_address=None, account_address=None,
            ),
        },
    )


def assert_native_testnet_only(config: TradingNodeConfig, execution_mode: str = "sandbox") -> None:
    """Require exactly one mode-specific native execution route."""
    expected_data = {"BYBIT-PUBLIC-SIGNAL", "HYPERLIQUID-MAINNET-DATA"}
    client_key, factory = execution_factory_for_mode(execution_mode)
    if set(config.data_clients) != expected_data or set(config.exec_clients) != {client_key}:
        raise RuntimeError("HL_TESTNET_SINGLE_NATIVE_ROUTE_REQUIRED")
    bybit = config.data_clients["BYBIT-PUBLIC-SIGNAL"]
    data = config.data_clients["HYPERLIQUID-MAINNET-DATA"]
    execution = config.exec_clients[client_key]
    expected_type = SandboxExecutionClientConfig if execution_mode == "sandbox" else HyperliquidExecClientConfig
    if not isinstance(bybit, BybitDataClientConfig) or not isinstance(data, HyperliquidDataClientConfig) or not isinstance(execution, expected_type):
        raise RuntimeError("HL_TESTNET_NATIVE_CONFIG_REQUIRED")
    if bybit.api_key is not None or bybit.api_secret is not None:
        raise RuntimeError("HL_TESTNET_BYBIT_SIGNAL_CLIENT_MUST_BE_PUBLIC")
    if data.environment is not PUBLIC_MAINNET_ENVIRONMENT:
        raise RuntimeError("HL_TESTNET_MAINNET_OR_UNSET_ENVIRONMENT")
    if execution_mode == "sandbox":
        if execution.venue != "HYPERLIQUID" or execution.base_currency != "USDC":
            raise RuntimeError("HL_TESTNET_SANDBOX_VENUE_OR_CURRENCY_MISMATCH")
        if factory is not HyperliquidUsdcSandboxFactory or not issubclass(factory, SandboxLiveExecClientFactory):
            raise RuntimeError("HL_TESTNET_EXECUTION_ALLOWLIST_MISMATCH")
    elif execution.environment is not PUBLIC_MAINNET_ENVIRONMENT or factory is not ScopedHyperliquidExecClientFactory:
        raise RuntimeError("HL_LIVE_NATIVE_FACTORY_MISMATCH")


class HyperliquidTestnetNode:
    """One OS-process owner of public feeds and a local Sandbox account."""
    def __init__(self, *, instance: TestnetInstanceConfig, candidate: Candidate, state: PaperRuntime, starting_cash: Decimal = Decimal("10000")) -> None:
        self.instance, self.candidate, self.state = instance, candidate, state
        self.starting_cash = starting_cash
        self._seed_verified = False
        self.scrubbed_environment = scrub_private_execution_environment()
        self.candidate_hash = candidate_content_hash(candidate)
        self.profile_root = Path(__file__).resolve().parents[2]
        self.profile = HyperliquidVenueProfile.from_snapshot(self.profile_root, environment=HyperliquidProfileEnvironment.MAINNET)
        self.warmup_bundle, self.warmup_state = load_stageg_warmup_bundle(instance.signal_warmup_manifest)
        self._warmup_verified_day = time.time_ns() // 86_400_000_000_000
        self._warmup_verified_target = instance.signal_warmup_manifest.resolve()
        self._warmup_checked_at_ns = time.time_ns()
        self.gate = cross_venue_stage_g_gate(
            candidate=candidate, warmup_manifest=instance.signal_warmup_manifest,
            strategy_path=self.profile_root / "coinmaster/strategy/wave_overlay.py",
            profile_root=self.profile_root,
        )
        self.loop = asyncio.new_event_loop()
        self.config = hyperliquid_testnet_node_config(trader_id=instance.trader_id, starting_cash=starting_cash, execution_mode=instance.mode)
        assert_native_testnet_only(self.config, instance.mode)
        if instance.mode != "sandbox":
            # A later approval must supply native account economics, complete
            # recovery, and a guarded order route before building a live node.
            raise RuntimeError("HL_LIVE_ROUTE_NOT_APPROVED")
        self.node = TradingNode(config=self.config, loop=self.loop)
        self.node.add_data_client_factory("BYBIT", BybitLiveDataClientFactory)
        self.node.add_data_client_factory("HYPERLIQUID", HyperliquidLiveDataClientFactory)
        self.node.add_exec_client_factory(*execution_factory_for_mode(instance.mode))
        self.node.build()
        # Model-only, constant 1:1 USD/USDC assumption in the same venue's
        # native Cache FX graph. This is never subscribed to public data.
        fx_pair, fx_quote = model_fx_pair_and_quote()
        self.node.cache.add_instrument(fx_pair)
        self.node.cache.add_quote_tick(fx_quote)
        self.hooks = LifecycleHooks(state)
        self.feed = FeedBook(ids=TESTNET_IDS, native_event_sink=self.hooks.record_event)
        self.feed_observer: FeedObserver | None = None
        self.strategy: WaveOverlayStrategy | None = None
        self.prime_error: str | None = None
        self._thread: threading.Thread | None = None

    def _sandbox_exchange(self):
        clients = self.node.kernel.exec_engine._clients  # Nautilus 1.231 lacks a public client lookup.
        client = next((item for item in clients.values() if isinstance(item, SandboxExecutionClient)), None)
        exchange = getattr(client, "exchange", None)
        if exchange is None or not sandbox_cash_posting_supported():
            raise RuntimeError("SANDBOX_NATIVE_CASH_POSTING_UNAVAILABLE")
        return exchange

    def _wave_strategy_config(self) -> WaveOverlayStrategyConfig:
        if self.warmup_bundle is None or not self.gate.attachable:
            raise RuntimeError(f"STAGEG_STRATEGY_ATTACHMENT_BLOCKED:{self.warmup_state}")
        policy = HyperliquidSandboxMarginPolicy(self.profile, SANDBOX_LEVERAGES, SANDBOX_MARK_MAX_AGE_NS)
        return WaveOverlayStrategyConfig(
            btc_id=BTC_PERP, sol_id=SOL_PERP,
            btc_bar_type=bybit_daily_bar_type(BYBIT_IDS[0]), sol_bar_type=bybit_daily_bar_type(BYBIT_IDS[1]),
            btc_mark_data_type=venue_mark_data_type(BTC_PERP), sol_mark_data_type=venue_mark_data_type(SOL_PERP),
            mark_client_id=ClientId("HYPERLIQUID-MAINNET-DATA"), live_mark_client_id=ClientId("HYPERLIQUID-MAINNET-DATA"),
            active_seed=self.starting_cash, margin_policy=policy,
            candidate=self.candidate, seed_bars=self.warmup_bundle.bars,
            entries_enabled=True, entries_gate=self._entries_enabled,
            event_sink=self.hooks.record_event, submission_sink=self.hooks,
            btc_signal_id=BYBIT_IDS[0], sol_signal_id=BYBIT_IDS[1],
            execution_policy_hash=self.gate.execution_policy_hash,
            execution_policy_version="hl-mainnet-public-data-native-sandbox-v1",
            funding_sink=NativeSandboxFundingPoster(exchange=self._sandbox_exchange(), runtime=self.state),
            market_exit_time_in_force=TimeInForce.IOC, market_exit_reduce_only=True,
            deposit_runtime=self.state, deposit_instance_id=self.instance.instance_id,
            deposit_account_id="HYPERLIQUID-001",
            deposit_equity_reader=lambda strategy: native_equity(
                strategy.cache, strategy._latest_marks, now_ns=time.time_ns(),
            ),
            deposit_initialization_allowed=lambda: (
                self._seed_verified and self.state.recovery_state() == "FLAT_RESTART"
                and not self.state.all_submissions() and not self.state.projection_events(1)[0]
            ),
        )

    def _refresh_warmup_readiness(self) -> None:
        """Pause at each UTC boundary until verified history and live bars agree."""
        now_ns = time.time_ns()
        day = now_ns // 86_400_000_000_000
        try:
            target = self.instance.signal_warmup_manifest.resolve(strict=True)
        except OSError:
            target = None
        if (
            day != self._warmup_verified_day
            or target != self._warmup_verified_target
            or now_ns - self._warmup_checked_at_ns >= 900_000_000_000
        ):
            bundle, state = load_stageg_warmup_bundle(self.instance.signal_warmup_manifest)
            self.warmup_bundle, self.warmup_state = bundle, state
            if self.strategy is not None and bundle is not None and state == "READY":
                self.strategy.queue_verified_backfill(bundle.bars)
            self._warmup_verified_day = day
            self._warmup_verified_target = target
            self._warmup_checked_at_ns = now_ns
        latest_live_close_ms = (
            self.strategy._current_btc.ts_event // 1_000_000
            if self.strategy is not None and self.strategy._current_btc is not None else 0
        )
        covered = latest_live_close_ms >= day * 86_400_000
        state = self.warmup_state if self.warmup_state != "READY" or covered else "STRATEGY_LIVE_SESSION_MISSING"
        self.gate = replace(
            self.gate, warmup_state=state,
            attachable=(state == "READY" and self.gate.approval_state == "SEALED_APPROVAL_MATCH"
                        and self.gate.margin_policy_state == "READY_PUBLIC_HL_MAINNET_TIERS_LOCAL_SANDBOX_LEVERAGE"),
        )

    def native_account_total(self) -> Decimal:
        account = self.node.cache.account_for_venue(BTC_PERP.venue)
        return native_usdc_balances(account)["total"]

    def strategy_restartable(self) -> bool:
        strategy = self.strategy
        if strategy is None:
            return False
        return (
            strategy._domain.episode is None
            and not strategy._domain.locked_after_liquidation
            and not strategy._queued_intents
            and strategy._mandatory_sol_exit is None
            and strategy._forced_close_reason is None
        )

    def _entries_enabled(self) -> bool:
        # This durable same-worker control is checked again at WaveOverlay's
        # final non-reduce submit boundary.  A read error fails closed; exits
        # bypass this callback in the strategy by design.
        try:
            if self.state.entry_control_state() == "PAUSED":
                return False
            self._refresh_warmup_readiness()
        except Exception:
            return False
        if not model_fx_ready(self.node.cache):
            return False
        if not self._seed_verified:
            try:
                self._seed_verified = self.native_account_total() == self.starting_cash
            except ValueError:
                return False
            if not self._seed_verified:
                return False
        feeds = self.feed.status(time.time_ns())
        protected = self.strategy is not None and self.strategy.deposit_projection()["state"] == "ARMED"
        return self.node.is_running() and self.gate.attachable and protected and self.state.health(time.time_ns()).safe_for_increase and bool(feeds) and all(item["state"] == "READY" for item in feeds.values())

    def prime(self) -> None:
        """Attach Stage-G only when fresh source and executable gates pass."""
        try:
            client_id = ClientId("HYPERLIQUID-MAINNET-DATA")
            self.feed_observer = FeedObserver(FeedObserverConfig(
                instrument_ids=TESTNET_IDS, client_ids=(client_id, client_id), feed=self.feed,
            ))
            self.node.trader.add_strategy(self.feed_observer)
            # Retain the observation-only test seam for a deliberately
            # incomplete object; real nodes always define an audited gate.
            if hasattr(self, "gate"):
                self.strategy = WaveOverlayStrategy(self._wave_strategy_config())
                self.node.trader.add_strategy(self.strategy)
        except Exception as error:
            self.prime_error = type(error).__name__

    def start(self) -> None:
        if self.prime_error is None:
            self._thread = threading.Thread(target=self.node.run, name="hl-stageg-testnet-native", daemon=True)
            self._thread.start()

    def stop(self) -> bool:
        """Stop native callbacks before the worker closes its durable journal."""
        if self._thread is None or not self._thread.is_alive():
            return True
        self.loop.call_soon_threadsafe(self.node.stop)
        self._thread.join(timeout=30)
        return not self._thread.is_alive()

    def sandbox_snapshot(self) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        """The local Sandbox cache is authoritative only for this process."""
        positions = [
            {"instrument_id": str(position.instrument_id), "signed_quantity": str(position.quantity.as_decimal() if position.is_long else -position.quantity.as_decimal())}
            for position in self.node.cache.positions_open()
            if position.instrument_id in TESTNET_IDS
        ]
        orders = [
            {
                "client_order_id": str(order.client_order_id),
                "instrument_id": str(order.instrument_id),
                "reduce_only": bool(order.is_reduce_only),
            }
            for order in self.node.cache.orders_open()
            if order.instrument_id in TESTNET_IDS
        ]
        return sorted(positions, key=lambda item: item["instrument_id"]), sorted(orders, key=lambda item: item["client_order_id"])

    def status(self) -> dict:
        self._refresh_warmup_readiness()
        feeds = self.feed.status(time.time_ns())
        ready = self.node.is_running() and bool(self._thread and self._thread.is_alive()) and bool(feeds) and all(item["state"] == "READY" for item in feeds.values()) and self.prime_error is None
        return {
            "instance_id": self.instance.instance_id,
            "environment": "mainnet-public",
            "node_class": type(self.node).__name__,
            "node_built": self.node.is_built(),
            "node_running": self.node.is_running(),
            "data_client_classes": ["BybitDataClient", "HyperliquidDataClient"],
            "data_factories": [f"{item.__module__}.{item.__name__}" for item in PUBLIC_DATA_FACTORIES],
            "execution_client_classes": [SandboxExecutionClient.__name__],
            "execution_factories": [f"{item.__module__}.{item.__name__}" for item in NATIVE_TESTNET_FACTORIES],
            "execution_factory_allowlist": [f"{SandboxLiveExecClientFactory.__module__}.{SandboxLiveExecClientFactory.__name__}"],
            "live_order_capability": False,
            "candidate_hash": self.candidate_hash,
            "state_db": str(self.instance.state_db),
            "orders_enabled": self._entries_enabled() if self.strategy is not None else False,
            "trading_strategy_registered": self.strategy is not None,
            "feed_observer_registered": self.feed_observer is not None,
            "feeds": feeds,
            "state": "PUBLIC_FEEDS_READY" if ready else "DATA_STALE/PAUSED",
            "prime_error": self.prime_error,
            "scrubbed_private_environment": list(self.scrubbed_environment),
            "warmup": {"state": self.warmup_state, "rows": self.warmup_bundle.rows if self.warmup_bundle else 0},
            "stage_g_gate": self.gate.__dict__,
            "daily_decision": self.strategy.daily_decision_status() if self.strategy is not None else None,
            "accounting": {
                "fees": {"observed": "SANDBOX_NATIVE_FILL_COMMISSION", "policy": "FIXED_HL_PUBLIC_BASE_MAKER_0.00015_TAKER_0.00045"},
                "funding": {
                    "observed": "PUBLIC_RATE_AND_FUTURE_SCHEDULE",
                    "modelled": "NO_SETTLEMENT_CASHFLOW_MODELLED",
                    "posting": "UNPOSTED_NEXT_PAYMENT_IS_NOT_CONFIRMED_SETTLEMENT",
                },
                "margin": {"observed": "NATIVE_SANDBOX_ACCOUNT", "policy": "CURRENT_PUBLIC_HL_MAINNET_TIERS_LOCAL_40X_BTC_20X_SOL"},
            },
        }
