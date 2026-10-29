"""Single native Strategy adapter for the BTC/SOL wave-overlay domain.

Orders are made by Nautilus; this adapter never simulates fills, balance, fees,
or funding.  It is deliberately not declared a research baseline until a
finer execution/settlement-mark dataset and liquidation validation exist.
"""
from __future__ import annotations
from coinmaster.strategy.next_band import NextBandResearch, NextClosedBar
from coinmaster.strategy.residual_recovery import ResidualRecoveryResearch

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_EVEN
from math import log
import pandas as pd

from coinmaster.domain.deposit_protection import DepositProtection, percent

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType, CustomData, DataType, FundingRateUpdate, MarkPriceUpdate, QuoteTick
from nautilus_trader.model.enums import BarAggregation, OrderSide, TimeInForce
from nautilus_trader.model.events import OrderAccepted, OrderCanceled, OrderDenied, OrderExpired, OrderFilled, OrderRejected
from nautilus_trader.model.identifiers import ClientId, ClientOrderId, InstrumentId
from nautilus_trader.trading.strategy import Strategy

from coinmaster.domain.wave_overlay import btc_management_price
from coinmaster.strategy.hedge_band import HedgeBandResearch
from coinmaster.strategy.split_cover import SplitCoverResearch
from coinmaster.strategy.conditional_hedge import ConditionalSolResearch
from coinmaster.strategy.risk_first_sol import SolRiskFirstResearch
from coinmaster.strategy.immediate_insurance import ImmediateSolInsurance
from coinmaster.strategy.alpha_cushion import AlphaCushionResearch
from coinmaster.strategy.carry_pair import CarryPairResearch

from coinmaster.domain.wave_overlay import Candidate, DailyBar, Intent, WaveOverlayState, features_for
from coinmaster.venues.margin_policy import MarginMark, MarginPolicy
from coinmaster.venues.marks import VenueMark
from coinmaster.venues.signals import DailySignalBar


class WaveOverlayStrategyConfig(StrategyConfig, frozen=True):
    btc_id: InstrumentId
    sol_id: InstrumentId
    btc_bar_type: BarType
    sol_bar_type: BarType
    btc_mark_data_type: DataType
    sol_mark_data_type: DataType
    mark_client_id: ClientId
    active_seed: Decimal
    # This is injected by the venue boundary. Production must never obtain a
    # margin policy from research fixtures or a different venue.
    margin_policy: MarginPolicy | None = None
    # Compatibility inputs for research callers. They are deliberately inert
    # here: research injects its own policy explicitly.
    tier_marks: tuple["MarkPriceUpdate", ...] = ()
    tier_selected_leverage: tuple[tuple[InstrumentId, Decimal], ...] = ()
    max_mark_age_ns: int = 0
    trading_start_open_ns: int | None = None
    terminal_close_at_ns: int | None = None
    candidate: Candidate = Candidate()
    tp_fee_floor_v1: bool = False
    research_v0_execution_repairs: bool = False
    research_v0_zero_tp_netting: bool = True
    research_v0_deferred_selective_zero_tp: bool = False
    research_v0_selective_lifecycle_repairs: bool = False
    research_v3_risk: str | None = None
    research_btc_split50: bool = False
    research_btc_split_planref_v1: bool = False
    research_btc_split_tp_ioc: bool = False
    research_btc_split_discount: Decimal = Decimal("0.0025")
    research_sol_btc_open_only: bool = False
    research_wait_4h: bool = False
    research_wait_persist: bool = False
    research_zero_retrace: bool = False
    research_sol_dominant: bool = False
    research_residual_recovery: bool = False
    research_c1_btc_cut_divisor: int = 2
    research_c1_restore_dd: Decimal = Decimal(".35")
    research_c1_global_cut_arm: bool = False
    research_c1_first_fresh_h4: bool = False
    research_c1_btc_postcut_d1: bool = False
    research_next_signals: tuple[DataType, ...] = ()
    research_h4_ema: int | None = None
    research_h4_gamma: Decimal = Decimal(".5")
    research_h4_seed: tuple[tuple[int, float], ...] = ()
    research_h4_bar_type: BarType | None = None
    research_regime_reentry_band: Decimal | None = None
    research_band_daily_seed: tuple[tuple[int, float, float], ...] = ()
    research_sol_cover: Decimal | None = None
    research_conditional_sol: bool = False
    research_alpha_cushion: bool = False
    research_chop_pair: bool = False
    research_carry_daily_seed: tuple[tuple[int, float, float], ...] = ()
    research_immediate_sol: str | None = None
    research_immediate_lookback: int = 90
    research_sol_risk_first: str | None = None
    research_cover_hour_seed: tuple[tuple[int, float, float], ...] = ()
    research_h1_b1: str | None = None
    research_h1_adverse_fraction: Decimal = Decimal("0.025")
    research_confirmation_bars: tuple[BarType, ...] = ()
    research_btc_direction_sizing: bool = False
    research_btc_drawdown_sizing: bool = False
    research_btc_episode_loss_20: bool = False
    research_sol_remaining_btc_hedge: bool = False
    research_portfolio_protect_45: bool = False
    research_sol_notional_cap_multiple: Decimal | None = None
    max_gross_to_active: Decimal = Decimal("50")
    # A verified history is supplied before native start.  It is feature state
    # only: it never replays old decisions or orders.
    seed_bars: tuple[DailyBar, ...] = ()
    entries_enabled: bool = True
    entries_gate: object | None = None
    event_sink: object | None = None
    native_fill_sink: object | None = None
    submission_sink: object | None = None
    live_mark_client_id: ClientId | None = None
    btc_signal_data_type: DataType | None = None
    sol_signal_data_type: DataType | None = None
    # Signals retain their source-venue identity; execution IDs above may be
    # different instruments/venues (for example Bybit signals, HL Sandbox).
    btc_signal_id: InstrumentId | None = None
    sol_signal_id: InstrumentId | None = None
    signal_client_id: ClientId | None = None
    # Optional, sparse reporting checkpoints.  They use the same native
    # account/cache and paired CustomData marks as the strategy, never a
    # second PnL or matching model.
    reporting_checkpoint_ns: tuple[int, ...] = ()
    execution_delay_ns: int = 0
    # Immutable execution-policy identity written into every native fill audit.
    execution_policy_hash: str = ""
    execution_policy_version: str = ""
    # Reserved for a future adapter event carrying a confirmed venue
    # settlement. ``FundingRateUpdate.next_funding_ns`` is explicitly *not*
    # such an event: it names the next scheduled payment.
    funding_sink: object | None = None
    live_start_approved: bool = False
    live_initial_capital_limit_usdc: str = "0"
    live_account_mode: str = "disabled"
    live_equity_basis: str = "HYPERLIQUID_CLASSIC_PERPS_ACCOUNT_VALUE_V1"
    deposit_runtime: object | None = None
    deposit_instance_id: str = ""
    deposit_account_id: str = ""
    deposit_equity_reader: object | None = None
    deposit_initialization_allowed: object | None = None
    deposit_high_water_allowed: object | None = None


def _native_account_money(account, *, free: bool = False) -> Decimal:
    """Read native account cash in its ledger currency; absent cash fails closed."""
    currency = account.base_currency
    if currency is None:
        raise ValueError("NATIVE_ACCOUNT_BASE_CURRENCY_MISSING")
    balance = account.balance_free(currency) if free else account.balance_total(currency)
    if balance is None:
        raise ValueError(f"NATIVE_ACCOUNT_BALANCE_MISSING:{currency}")
    return balance.as_decimal()


def _native_limit_price(instrument, raw_price: Decimal):
    # Keep HL native order identity equal to the adapter wire limit price.
    price = instrument.make_price(raw_price)
    if instrument.id.venue.value != "HYPERLIQUID":
        return price
    value = price.as_decimal()
    if not value.is_finite() or value <= 0:
        raise ValueError("INVALID_HYPERLIQUID_LIMIT_PRICE")
    # Pinned HL 1.231 normalizes to five significant figures on submission.
    quantum = Decimal(1).scaleb(value.adjusted() - 4)
    canonical = value.quantize(quantum, rounding=ROUND_HALF_EVEN)
    result = instrument.make_price(canonical)
    if result.as_decimal() != canonical:
        raise ValueError("HYPERLIQUID_LIMIT_PRICE_PRECISION_MISMATCH")
    return result


def _fee_floor_price(instrument, episode, *, maker: bool):
    """Outward native/wire price covering confirmed entry and planned exit fees."""
    if (episode.btc_entry_qty_exact <= 0 or episode.btc_entry_notional_exact <= 0
            or episode.btc_entry_fee_fill_count != episode.btc_entry_fill_count):
        raise ValueError("BTC_TP_ENTRY_FEE_EVIDENCE_INCOMPLETE")
    p0 = episode.btc_entry_notional_exact / episode.btc_entry_qty_exact
    fi = episode.btc_entry_fees_exact / episode.btc_entry_notional_exact
    fo = Decimal(str(instrument.maker_fee if maker else instrument.taker_fee))
    if fi < 0 or fo < 0 or fo >= 1:
        raise ValueError("INVALID_BTC_TP_FEE_RATE")
    be = p0 * (1 + fi) / (1 - fo) if episode.side == 1 else p0 * (1 - fi) / (1 + fo)
    upward = episode.side == 1
    rounding = ROUND_CEILING if upward else ROUND_FLOOR
    step = instrument.price_increment.as_decimal()
    native = (be / step).to_integral_value(rounding=rounding) * step
    if instrument.id.venue.value == "HYPERLIQUID":
        quantum = Decimal(1).scaleb(native.adjusted() - 4)
        native = (native / quantum).to_integral_value(rounding=rounding) * quantum
    result = _native_limit_price(instrument, native)
    if (upward and result.as_decimal() < be) or (not upward and result.as_decimal() > be):
        raise ValueError("BTC_TP_WIRE_PRICE_INSIDE_FEE_FLOOR")
    return result


class WaveOverlayStrategy(ResidualRecoveryResearch, NextBandResearch, HedgeBandResearch, CarryPairResearch, AlphaCushionResearch, ImmediateSolInsurance, SolRiskFirstResearch, ConditionalSolResearch, SplitCoverResearch, Strategy):
    """Turns completed native daily bars into later native market orders."""
    def __init__(self, config: WaveOverlayStrategyConfig) -> None:
        super().__init__(config)
        self._split_cover_init()
        self._risk_first_init()
        self._conditional_init()
        self._insurance_init()
        self._alpha_init()
        self._carry_init()
        if config.research_chop_pair and (not config.candidate.sol_overlay_enabled or not config.research_btc_split_tp_ioc or config.research_alpha_cushion or config.research_sol_risk_first or config.research_immediate_sol or config.research_conditional_sol or config.research_sol_cover is not None or config.research_h1_b1 or config.research_v3_risk or len(config.research_confirmation_bars)!=4):
            raise ValueError("CHOP_PAIR_REQUIRES_EXCLUSIVE_WINNER_NATIVE_BARS")
        if config.research_alpha_cushion and (not config.candidate.sol_overlay_enabled or not config.research_btc_split_tp_ioc or config.research_sol_risk_first or config.research_immediate_sol or config.research_conditional_sol or config.research_sol_cover is not None or config.research_h1_b1 or len(config.research_confirmation_bars)!=4):
            raise ValueError("ALPHA_CUSHION_REQUIRES_SELECTED_BTC_ORIGINAL_ALPHA_EXCLUSIVE_NATIVE_BARS")
        if config.research_immediate_sol is not None and (config.research_immediate_sol not in {"i25","i25-light","i25-recovery","i33"} or not 30<=config.research_immediate_lookback<=180 or not config.research_btc_split_tp_ioc or config.candidate.sol_overlay_enabled or config.research_sol_risk_first or config.research_conditional_sol or config.research_sol_cover is not None or config.research_h1_b1 or len(config.research_confirmation_bars)!=4):
            raise ValueError("IMMEDIATE_INSURANCE_REQUIRES_EXCLUSIVE_SELECTED_BTC_AND_ORIGINAL_SOL_OFF")
        self._cover_seed(config.research_cover_hour_seed)
        if config.research_sol_risk_first is not None and (config.research_sol_risk_first not in {"cap50","dd-cov","split-atr","alpha-corridor-v1"} or config.research_conditional_sol or config.research_sol_cover is not None or config.research_h1_b1 or not config.candidate.sol_overlay_enabled):
            raise ValueError("RISK_FIRST_REQUIRES_EXCLUSIVE_VARIANT_ORIGINAL_OVERLAY")
        if config.research_conditional_sol and (not config.research_btc_split_tp_ioc or not config.candidate.sol_overlay_enabled or config.research_sol_cover is not None or len(config.research_confirmation_bars)!=4):
            raise ValueError("CONDITIONAL_REQUIRES_SELECTED_BTC_ORIGINAL_SOL_AND_NATIVE_BARS")
        if config.research_btc_split_tp_ioc and (not config.research_btc_split_planref_v1 or config.tp_fee_floor_v1):
            raise ValueError("TP_IOC_REQUIRES_PLANREF_V3")
        if config.research_btc_split_planref_v1 and (not config.research_btc_split50 or config.research_btc_split_discount != Decimal("0.0025")):
            raise ValueError("PLANREF_V1_REQUIRES_BTC025_SPLIT")
        if config.research_btc_split_discount not in (Decimal("0.0025"),Decimal("0.005")):
            raise ValueError("SPLIT_DISCOUNT_NOT_AUTHORIZED_CANDIDATE")
        if config.research_btc_split50 or config.research_sol_cover is not None:
            if not config.research_v0_selective_lifecycle_repairs or config.research_h1_b1 or config.research_v3_risk or config.research_btc_drawdown_sizing or config.research_sol_remaining_btc_hedge or config.research_portfolio_protect_45 or config.research_sol_notional_cap_multiple:
                raise ValueError("SPLIT_COVER_REQUIRES_V3_CONTROL")
            if config.research_sol_cover is not None and (config.research_sol_cover not in (Decimal("0.5"),Decimal("0.75"),Decimal("1")) or config.candidate.sol_overlay_enabled or len(config.research_confirmation_bars)!=4):
                raise ValueError("SOL_COVER_REQUIRES_SINGLE_OWNER_AND_NATIVE_BARS")
        if config.research_sol_notional_cap_multiple is not None and config.research_sol_notional_cap_multiple != Decimal("6"):
            raise ValueError("RESEARCH_SOL_CAP_REQUIRES_6X")
        if config.research_portfolio_protect_45 and config.research_sol_notional_cap_multiple is not None:
            raise ValueError("RESEARCH_RISK_VARIANTS_MUTUALLY_EXCLUSIVE")
        if sum((config.research_btc_episode_loss_20, config.research_sol_remaining_btc_hedge,
                config.research_portfolio_protect_45, config.research_sol_notional_cap_multiple is not None)) > 1:
            raise ValueError("RESEARCH_RISK_VARIANTS_MUTUALLY_EXCLUSIVE")
        if config.research_btc_direction_sizing or config.research_btc_drawdown_sizing:
            if (sum((config.research_btc_direction_sizing, config.research_btc_drawdown_sizing,
                     config.research_btc_episode_loss_20, config.research_sol_remaining_btc_hedge,
                     config.research_portfolio_protect_45, config.research_sol_notional_cap_multiple is not None,
                     config.tp_fee_floor_v1)) != 1 or config.candidate.btc_notional_multiplier != 7.875):
                raise ValueError("RESEARCH_BTC_SIZING_REQUIRES_SEPARATE_7_875_CONTROL")
        if config.research_v3_risk is not None:
            if config.research_v3_risk not in {"b25", "s10_15", "r2", "t3"}:
                raise ValueError("RESEARCH_V3_RISK_INVALID")
            if any((config.research_btc_direction_sizing, config.research_btc_drawdown_sizing,
                    config.research_btc_episode_loss_20, config.research_sol_remaining_btc_hedge,
                    config.research_portfolio_protect_45, config.research_sol_notional_cap_multiple is not None,
                    config.tp_fee_floor_v1)) or config.candidate.btc_notional_multiplier != 7.875:
                raise ValueError("RESEARCH_V3_RISK_REQUIRES_SEPARATE_V3_CONTROL")
        if config.research_h1_b1 is not None:
            if config.research_h1_b1 not in {"h1", "b1"}:
                raise ValueError("RESEARCH_H1_B1_INVALID")
            if any((config.research_v3_risk, config.research_btc_direction_sizing,
                    config.research_btc_drawdown_sizing, config.research_btc_episode_loss_20,
                    config.research_sol_remaining_btc_hedge, config.research_portfolio_protect_45,
                    config.research_sol_notional_cap_multiple is not None, config.tp_fee_floor_v1,
                    config.deposit_runtime is not None)) or not config.research_v0_selective_lifecycle_repairs:
                raise ValueError("RESEARCH_H1_B1_REQUIRES_SEPARATE_V3_CONTROL")
            if config.research_h1_adverse_fraction != Decimal("0.025"):
                raise ValueError("RESEARCH_H1_FIXED_ADVERSE_2_5_PERCENT")
            if len(config.research_confirmation_bars) != 4:
                raise ValueError("RESEARCH_H1_B1_REQUIRES_NATIVE_CONFIRMATION_BARS")
        self._hedge_band_init()
        self._next_init()
        self._c1_init()
        self.h1_b1_audit: list[dict[str, object]] = []
        self._confirmation_state: dict[BarType, dict] = {}
        self._confirmation_events: dict[tuple, tuple[int, int]] = {}
        self._b1_candidate: dict | None = None
        self._b1_consuming = False
        self._b1_btc_quote_sequence = 0
        self._h1_cycle: dict | None = None
        self._h1_confirmation_receipts: dict[tuple, tuple[int, int]] = {}
        self._h1_sol_quote_sequence = 0
        self.v3_risk_audit: list[dict[str, object]] = []
        self._v3_reduction: dict | None = None
        self._v3_orders: dict[str, dict] = {}
        self._v3_sol_cycle: dict | None = None
        self._v3_sol_block_episode: str | None = None
        self._v3_regime_wait = False
        self._v3_daily_side = None
        self._v3_daily_count = 0
        self._v3_daily_ns = None
        self._v3_trail_wait_ns = None
        self._v3_fill_checkpoints: list[dict] = []
        self._btc_sizing_peak = config.active_seed
        self._btc_sizing_reduced = False
        self._btc_sizing_last_ns: int | None = None
        self._btc_sizing_equity: Decimal | None = None
        self._btc_sizing_dd = Decimal("0")
        self.btc_sizing_audit: list[dict[str, object]] = []
        self._btc_loss_episode_id: str | None = None
        self._btc_loss_reference: Decimal | None = None
        self._btc_loss_realized: dict[str, Decimal] = {}
        self.btc_episode_loss_audit: list[dict[str, object]] = []
        self.sol_hedge_admission_audit: list[dict[str, str]] = []
        self._research_protect_peak = config.active_seed
        self._research_protect_latch: dict[str, object] | None = None
        self.research_protection_audit: list[dict[str, object]] = []
        self.sol_cap_admission_audit: list[dict[str, str]] = []
        self._candidate = replace(config.candidate, sol_overlay_enabled=False) if config.research_h1_b1 == "h1" else config.candidate
        self._domain = WaveOverlayState(self._candidate)
        self._domain.research_sol_cover = config.research_sol_cover is not None
        self._domain.research_h4_owned = config.research_h4_ema is not None
        self._bars: list[DailyBar] = list(config.seed_bars)
        self._last_accepted_session: int | None = (
            int(self._bars[-1].close_time.timestamp() * 1_000_000_000) if self._bars else None
        )
        self._latest_seen_session: int | None = self._last_accepted_session
        self._daily_decision_reason = "SEED_ONLY"
        self._pending_verified_backfill: tuple[DailyBar, ...] | None = None
        self._backfill_error: str | None = None
        self._pending_by_order: dict[str, Intent] = {}
        self._sigma_by_order: dict[str, float | None] = {}
        self._decision_index_by_order: dict[str, int] = {}
        self._last_sol_close: float | None = None
        self._day: dict[int, dict[BarType, Bar]] = {}
        self._marks_by_session: dict[int, dict[InstrumentId, VenueMark]] = {}
        self._current_btc: Bar | None = None
        self._current_sol: Bar | None = None
        self._current_btc_mark: VenueMark | None = None
        self._current_sol_mark: VenueMark | None = None
        self._current_signals = features_for(self._bars, self._candidate)
        # A completed daily tuple can arrive while the fail-closed entry gate
        # is paused (for example, while fresh warmup is being verified). Keep
        # only that current flat session for a one-shot retry on a later quote.
        # Queued/submitted work already has its own native lifecycle handling.
        self._deferred_entry_session: int | None = None
        self._latest_marks: dict[InstrumentId, VenueMark] = {}
        self._queued_intents: list[tuple[Intent, float | None, int]] = []
        self._queued_intent_ready_ns: dict[str, int] = {}
        self._deferred_selective_entries: dict[str, dict] = {}
        self._selected_entry_audits: dict[str, dict] = {}
        self._mandatory_sol_exit: tuple[Intent, float | None, int] | None = None
        self._mandatory_sol_retry_after_ns = 0
        # Fixed accepted leaves across native IOC children.
        self._accepted_reductions: dict[tuple[str, str, int | None], tuple[Intent, Decimal]] = {}
        self._queued_close_submitted: dict[str, set[InstrumentId]] = {}
        self._group_close_reconciliation_pending = False
        self._liquidating = False
        self._liquidation_waiting: set[InstrumentId] = set()
        self._liquidation_orders: set[str] = set()
        self._liquidation_submitted: set[InstrumentId] = set()
        self.liquidation_audit: list[dict[str, str]] = []
        self.pre_submit_gate_blocks: list[dict[str, str]] = []
        self.marked_equity_checkpoints: dict[int, dict[str, str]] = {}
        self._terminal_order_ids: set[str] = set()
        self._order_audit: dict[str, dict[str, object]] = {}
        self.fill_audit: list[dict[str, str]] = []
        self.entry_sizing_audit: list[dict[str, object]] = []
        self._seen_trade_ids: set[str] = set()
        self._deposit_exit_orders: set[str] = set()
        self._deposit_storage_failed = False
        self._deposit_exit_started = False
        self._deposit_timer_name = f"COINMASTER_DEPOSIT_CHECK:{self.id}"
        self._deposit = DepositProtection()
        if config.deposit_runtime is not None:
            stored = config.deposit_runtime.deposit_protection_state(
                instance_id=config.deposit_instance_id, account_id=config.deposit_account_id,
            )
            if stored is not None:
                self._deposit = DepositProtection.from_durable(stored)
        self._forced_close_reason: str | None = None
        self._forced_close_intent: Intent | None = None
        self._forced_close_submitted: set[InstrumentId] = set()
        self._forced_close_orders: set[str] = set()
        self.terminal_lifecycle: dict[str, object] = {
            "reason": "NOT_TRIGGERED",
            "status": "NOT_TRIGGERED",
            "trigger_ts": None,
            "close_fills": [],
            "lockout": False,
        }

    def on_start(self) -> None:
        for confirmation_bar in self.config.research_confirmation_bars:
            self.subscribe_bars(confirmation_bar)
        for kind in self.config.research_next_signals:
            self.subscribe_data(kind, client_id=self.config.signal_client_id)
        if self.config.research_h4_bar_type is not None:
            self.subscribe_bars(self.config.research_h4_bar_type)
        self.subscribe_bars(self.config.btc_bar_type)
        self.subscribe_bars(self.config.sol_bar_type)
        # Research feeds explicit VenueMark CustomData.  The live Bybit data
        # adapter publishes MarkPriceUpdate, which is converted below into the
        # same non-matching domain input rather than using MID/quote prices.
        if self.config.live_mark_client_id is None:
            self.subscribe_data(self.config.btc_mark_data_type, client_id=self.config.mark_client_id)
            self.subscribe_data(self.config.sol_mark_data_type, client_id=self.config.mark_client_id)
        else:
            self.subscribe_mark_prices(self.config.btc_id, client_id=self.config.live_mark_client_id)
            self.subscribe_mark_prices(self.config.sol_id, client_id=self.config.live_mark_client_id)
        if self.config.signal_client_id is not None and self.config.btc_signal_data_type is not None and self.config.sol_signal_data_type is not None:
            self.subscribe_data(self.config.btc_signal_data_type, client_id=self.config.signal_client_id)
            self.subscribe_data(self.config.sol_signal_data_type, client_id=self.config.signal_client_id)
        self.subscribe_quote_ticks(self.config.btc_id)
        self.subscribe_quote_ticks(self.config.sol_id)
        if self.config.funding_sink is not None:
            self.subscribe_funding_rates(self.config.btc_id, client_id=self.config.live_mark_client_id)
            self.subscribe_funding_rates(self.config.sol_id, client_id=self.config.live_mark_client_id)
        if self.config.deposit_runtime is not None:
            self.clock.set_timer(
                self._deposit_timer_name, pd.Timedelta(seconds=1), None, None,
                self._on_deposit_timer, True, False,
            )

    def on_stop(self) -> None:
        if self.config.deposit_runtime is not None and self._deposit_timer_name in self.clock.timer_names:
            self.clock.cancel_timer(self._deposit_timer_name)

    def on_bar(self, bar: Bar) -> None:
        h4 = self.config.research_h4_bar_type
        if h4 is not None and bar.bar_type in (h4, h4.standard()):
            if bar.bar_type.instrument_id != self.config.sol_id or bar.bar_type.spec.aggregation != BarAggregation.HOUR or bar.bar_type.spec.step != 4:
                raise ValueError("H4_EXPLICIT_BAR_TYPE_REQUIRED")
            self._hedge_h4_bar(bar)
            return
        if any(bar.bar_type == kind.standard() or bar.bar_type == kind for kind in self.config.research_confirmation_bars):
            self._cover_bar(bar)
            self._conditional_bar(bar)
            self._risk_first_bar(bar)
            self._insurance_bar(bar)
            self._alpha_bar(bar)
            self._carry_bar(bar)
            self._on_confirmation_bar(bar)
            return
        if bar.bar_type not in (self.config.btc_bar_type, self.config.sol_bar_type):
            return
        session = bar.ts_event
        self._latest_seen_session = max(self._latest_seen_session or session, session)
        self._apply_verified_backfill()
        if self._last_accepted_session is not None and session <= self._last_accepted_session:
            return
        self._latest_seen_session = max(self._latest_seen_session or session, session)
        paired = self._day.setdefault(session, {})
        paired[bar.bar_type] = bar
        self._try_advance_session(session)

    def _on_confirmation_bar(self, bar: Bar) -> None:
        """Completed native bars only; no quote/mark accumulator or future bar."""
        state = self._confirmation_state.setdefault(bar.bar_type, {})
        if bar.ts_event <= state.get("timestamp_ns", -1):
            return
        close = float(bar.close)
        old_high, old_low = state.get("high"), state.get("low")
        count = state.get("count", 0) + 1
        state.update(timestamp_ns=bar.ts_event, high=float(bar.high), low=float(bar.low),
                     count=count)
        if old_high is None:
            return
        side = 1 if close > old_high else -1 if close < old_low else 0
        if side:
            instrument_id = bar.bar_type.instrument_id
            # OR: same-boundary 15m/1h bars produce one confirmation token.
            self._confirmation_events[(instrument_id, side)] = (bar.ts_event, side)
            if bar.bar_type.spec.aggregation == BarAggregation.HOUR:
                self._confirmation_events[(instrument_id, "1h", side)] = (bar.ts_event, side)
            if self.config.research_h1_b1 == "h1" and instrument_id == self.config.sol_id:
                # Native close timers can publish only after this boundary's
                # quotes have already settled. Own the first future SOL quote,
                # not an execution from the book cached before bar receipt.
                receipt = (self.clock.timestamp_ns(), self._h1_sol_quote_sequence + 1)
                self._h1_confirmation_receipts[(instrument_id, side)] = receipt
                if bar.bar_type.spec.aggregation == BarAggregation.HOUR:
                    self._h1_confirmation_receipts[(instrument_id, "1h", side)] = receipt
            if self.config.research_h1_b1 == "b1" and instrument_id == self.config.btc_id:
                candidate = self._b1_candidate
                if candidate and bar.ts_event > candidate["armed_ns"] and side == candidate["side"]:
                    candidate["confirmed_ns"] = bar.ts_event
                    candidate["confirmation_receipt_ns"] = self.clock.timestamp_ns()
                    candidate["eligible_quote_sequence"] = self._b1_btc_quote_sequence + 1

    def _b1_flat_resolved(self) -> bool:
        return not (self.cache.positions_open() or self.cache.orders_open() or
                    self._pending_by_order or self._queued_intents or
                    self._forced_close_reason or self._group_close_reconciliation_pending or
                    self._liquidating or self._mandatory_sol_exit)

    def _b1_gate_daily(self) -> bool:
        if self.config.research_h1_b1 != "b1" or self._domain.episode is not None:
            return True
        ns, side = self._current_btc.ts_event, self._current_signals[-1].side
        if not self._b1_flat_resolved():
            return False
        candidate = self._b1_candidate
        if candidate is None or candidate["daily_ns"] != ns:
            self._b1_candidate = {"daily_ns": ns, "armed_ns": max(ns, self.clock.timestamp_ns()),
                                  "side": side, "confirmed_ns": None}
            self.h1_b1_audit.append({"event": "B1_ARM", **self._b1_candidate})
            return False
        return self._b1_consuming and candidate["confirmed_ns"] is not None

    @staticmethod
    def _confirmation_receipt_is_current(close_ns, receipt, quote_sequence: int, ts_now: int) -> bool:
        """First traded-instrument quote after receipt, at most one 1m cadence old."""
        return bool(close_ns is not None and receipt and receipt[1] == quote_sequence
                    and receipt[0] is not None and close_ns <= receipt[0] <= ts_now
                    and 0 <= ts_now-close_ns <= 60_000_000_000)

    def _confirmation_marks_current(self, ts_now: int) -> bool:
        return self.config.max_mark_age_ns > 0 and all(
            self._latest_marks.get(iid) is not None
            and 0 <= ts_now-self._latest_marks[iid].ts_event <= self.config.max_mark_age_ns
            for iid in (self.config.btc_id, self.config.sol_id))

    def _h1_confirmation_is_current(self, key: tuple, token, ts_now: int) -> bool:
        return self._confirmation_receipt_is_current(
            token[0] if token else None, self._h1_confirmation_receipts.get(key),
            self._h1_sol_quote_sequence, ts_now)

    def _h1_native_fill(self, intent: Intent, event) -> None:
        if self.config.research_h1_b1 != "h1" or self._h1_cycle is None:
            return
        cycle = self._h1_cycle
        if intent.reason == "H1_STAGE1":
            if not cycle["first_fill_ns"]:
                cycle["first_fill_ns"] = event.ts_event
                cycle["beta"] = cycle["entry_beta"]
            cycle["first_qty"] += event.last_qty.as_decimal()
        elif intent.action == "BTC_REDUCE" and cycle["first_fill_ns"] and event.ts_event > cycle["first_fill_ns"]:
            cycle["tp_ns"] = cycle["tp_ns"] or event.ts_event
        self.h1_b1_audit.append({"event": "H1_NATIVE_FILL", "action": intent.action, "reason": intent.reason,
            "timestamp_ns": event.ts_event, "quantity": str(event.last_qty), "price": str(event.last_px),
            "commission": str(event.commission), "order_id": str(event.client_order_id), "intent_id": intent.id})

    def _h1_check(self, ts_now: int) -> None:
        if self.config.research_h1_b1 != "h1" or not self._domain.episode:
            return
        episode = self._domain.episode
        if episode.btc_entry_vwap is None or self._forced_close_reason or self._liquidating:
            return
        positions = {p.instrument_id: p for p in self.cache.positions_open()}
        btc, sol = positions.get(self.config.btc_id), positions.get(self.config.sol_id)
        if self._h1_cycle is not None and self._h1_cycle["episode_id"] != episode.id:
            self._h1_cycle = None
        cycle = self._h1_cycle
        mark = self._latest_marks.get(self.config.btc_id)
        if mark is None or mark.ts_event > ts_now:
            return
        adverse = -Decimal(episode.side) * (mark.price / Decimal(str(episode.btc_entry_vwap)) - 1)
        if cycle is None:
            if btc is None or adverse <= self.config.research_h1_adverse_fraction:
                return
            cycle = self._h1_cycle = {"episode_id": episode.id, "armed_ns": ts_now,
                "first_fill_ns": None, "first_qty": Decimal(0), "first_terminal": False,
                "stage1_attempted": False, "stage2_attempted": False, "tp_ns": None,
                "closed": False, "beta": None, "entry_beta": None}
            self.h1_b1_audit.append({"event": "H1_ARM", "timestamp_ns": ts_now, "adverse": str(adverse)})
        if not cycle["stage1_attempted"] and adverse <= self.config.research_h1_adverse_fraction:
            self._h1_cycle = None
            return
        sol_work = any(i.action.startswith("SOL") for i in self._pending_by_order.values()) or any(i.action.startswith("SOL") for i, _, _ in self._queued_intents)
        if cycle["stage1_attempted"] and not sol_work:
            cycle["first_terminal"] = True
            if not cycle["first_qty"]:
                cycle["closed"] = True
        quantities = (btc.quantity.as_decimal() if btc else Decimal(0), sol.quantity.as_decimal() if sol else Decimal(0))
        if cycle.get("exposure_quantities") != quantities:
            cycle["exposure_quantities"] = quantities
            sol_mark = self._latest_marks.get(self.config.sol_id)
            beta = cycle["beta"] or cycle["entry_beta"]
            btc_notional = quantities[0] * mark.price * episode.side
            sol_notional = quantities[1] * sol_mark.price * -episode.side if sol_mark else None
            self.h1_b1_audit.append({"event": "H1_NATIVE_EXPOSURE", "timestamp_ns": ts_now,
                "native_btc_quantity": str(quantities[0]), "native_sol_quantity": str(quantities[1]),
                "signed_btc_mark_notional": str(btc_notional), "signed_sol_mark_notional": str(sol_notional),
                "frozen_beta": str(beta), "beta_net_mark_exposure": str(btc_notional + beta * sol_notional) if beta and sol_notional is not None else None})
        confirm = self._confirmation_events.get((self.config.sol_id, -episode.side))
        reverse = self._confirmation_events.get((self.config.sol_id, "1h", episode.side))
        timeout = cycle["first_fill_ns"] and ts_now >= cycle["first_fill_ns"] + 14 * 86_400_000_000_000
        recovery = cycle["first_fill_ns"] and adverse <= Decimal("0.01") and reverse and self._h1_confirmation_is_current((self.config.sol_id, "1h", episode.side), reverse, ts_now) and reverse[0] > cycle["first_fill_ns"] and reverse[1] == episode.side
        if btc is None or timeout or recovery or cycle["closed"]:
            reason = "H1_BTC_FLAT" if btc is None else "H1_TIMEOUT" if timeout else "H1_RECOVERY" if recovery else "H1_CYCLE_CLOSED"
            cycle["closed"] = True
            self._discard_queued_intents(lambda i: i.action == "SOL_ADD")
            for order in list(self.cache.orders_open()):
                if order.instrument_id == self.config.sol_id and not order.is_reduce_only:
                    self.cancel_order(order)
            if sol is not None and not self._mandatory_sol_exit and not self._has_owned_sol_exit():
                intent = self._domain._intent(episode, "SOL_EXIT", episode.side, None,
                    quantity=float(sol.quantity), reason="SOL_HARD_TIMEOUT")
                self.h1_b1_audit.append({"event": "H1_EXIT", "reason": reason, "timestamp_ns": ts_now})
                self._preempt_with_mandatory_sol_exit(intent, episode.fixed_sigma, len(self._bars)-1)
            return
        if sol_work or self._mandatory_sol_exit or self._has_owned_sol_exit() or any(o.instrument_id == self.config.sol_id for o in self.cache.orders_open()):
            return
        if not self._confirmation_marks_current(ts_now):
            return
        if not self._h1_confirmation_is_current((self.config.sol_id, -episode.side), confirm, ts_now) or confirm[1] != -episode.side:
            return
        level = 0 if not cycle["stage1_attempted"] else 1
        if level == 0:
            if adverse <= self.config.research_h1_adverse_fraction or confirm[0] <= cycle["armed_ns"]:
                return
            beta = self._current_signals[-1].beta
            if beta is None or not 0.2 < beta < 4:
                return
            cycle["entry_beta"] = Decimal(str(beta))
            notional = Decimal("0.5") * btc.quantity.as_decimal() * mark.price / cycle["entry_beta"]
            intent = self._domain._intent(episode, "SOL_ADD", -episode.side, 0,
                requested_notional=float(notional), reason="H1_STAGE1")
            cycle["stage1_attempted"] = True
        else:
            if cycle["stage2_attempted"] or not cycle["first_terminal"] or not cycle["tp_ns"] or confirm[0] <= cycle["tp_ns"]:
                return
            intent = self._domain._intent(episode, "SOL_ADD", -episode.side, 1,
                quantity=float(cycle["first_qty"]), reason="H1_STAGE2")
            cycle["stage2_attempted"] = True
        self._queued_intents.append((intent, self._current_signals[-1].sigma, len(self._bars)-1))
        self._queued_intent_ready_ns[intent.id] = ts_now
        self.h1_b1_audit.append({"event": intent.reason, "timestamp_ns": ts_now, "confirmation_ns": confirm[0],
            "confirmation_receipt_ns": self._h1_confirmation_receipts[(self.config.sol_id, -episode.side)][0],
            "confirmation_age_ns": ts_now-confirm[0], "sol_quote_sequence": self._h1_sol_quote_sequence,
            "btc_remaining": str(btc.quantity), "btc_mark": str(mark.price), "beta": str(cycle["entry_beta"]),
            "quantity": intent.quantity, "requested_notional": intent.requested_notional,
            "intent_id": intent.id, "first_sol_fill_ns": cycle["first_fill_ns"],
            "qualifying_btc_tp_ns": cycle["tp_ns"], "actual_stage1_quantity": str(cycle["first_qty"]),
            "first_parent_terminal": cycle["first_terminal"]})

    def on_data(self, data) -> None:
        incoming=getattr(data,'data',data)
        if isinstance(incoming,NextClosedBar):
            self._next_closed_bar(incoming)
            return
        """Receive explicit marks without ever making them execution data."""
        # Native fill and position events are not guaranteed to reach strategy
        # callbacks in cache-finalized order. The next public data event is a
        # causal reconciliation point before any new daily decision.
        if self._group_close_reconciliation_pending:
            self._reconcile_group_flat()
        # The DataEngine unwraps ``CustomData`` before strategy delivery in
        # Nautilus 1.231.  Accept the wrapper too so the routing contract is
        # explicit at this boundary and remains compatible with direct calls.
        mark = data.data if isinstance(data, CustomData) else data
        if isinstance(mark, DailySignalBar):
            signal_ids = (self.config.btc_signal_id or self.config.btc_id, self.config.sol_signal_id or self.config.sol_id)
            if mark.instrument_id not in signal_ids:
                return
            self._latest_seen_session = max(self._latest_seen_session or mark.ts_event, mark.ts_event)
            self._apply_verified_backfill()
            execution_id = self.config.btc_id if mark.instrument_id == signal_ids[0] else self.config.sol_id
            bar_type = self.config.btc_bar_type if execution_id == self.config.btc_id else self.config.sol_bar_type
            if self._last_accepted_session is not None and mark.ts_event <= self._last_accepted_session:
                return
            self._latest_seen_session = max(self._latest_seen_session or mark.ts_event, mark.ts_event)
            self._day.setdefault(mark.ts_event, {})[bar_type] = mark
            self._c1_observed_btc_d1(mark)
            # Input ordering is mark -> signal -> quote.  Retain only the two
            # latest marks and pair them here at the daily boundary.
            latest = self._latest_marks.get(execution_id)
            if latest is not None and latest.ts_event == mark.ts_event:
                self._on_venue_mark(latest)
            self._try_advance_session(mark.ts_event)
            return
        if not isinstance(mark, VenueMark):
            return
        if mark.instrument_id not in (self.config.btc_id, self.config.sol_id):
            return
        self._latest_marks[mark.instrument_id] = mark
        self._update_margin_mark(mark.instrument_id, mark.price, mark.ts_event)
        self._check_mark_first_liquidation(mark.ts_event)
        self._research_check_portfolio_protection(mark.ts_event)
        self._research_check_btc_episode_loss(mark.ts_event)
        self._research_sample_btc_sizing(mark.ts_event)
        self._research_check_v3_risk(mark.ts_event)
        # Avoid a per-minute session map: only a daily signal can make a mark
        # actionable for features, and it will re-pair the retained mark.
        if mark.ts_event in self._day:
            self._on_venue_mark(mark)

    def on_mark_price(self, update: MarkPriceUpdate) -> None:
        """Bridge a public venue mark into the existing non-matching input.

        The mark remains a strategy/risk value only.  It is never published as
        a quote, trade, bar, MID, or execution price.
        """
        if update.instrument_id not in (self.config.btc_id, self.config.sol_id):
            return
        mark = VenueMark(
            update.instrument_id,
            update.value.as_decimal(),
            update.ts_event,
            getattr(update, "ts_init", update.ts_event),
        )
        self._latest_marks[update.instrument_id] = mark
        self._update_margin_mark(mark.instrument_id, mark.price, mark.ts_event)
        self._check_mark_first_liquidation(mark.ts_event)
        # Public updates are intraday while Bybit daily bars close at UTC day
        # boundaries.  Keep the last causal mark for that day's close rather
        # than requiring an impossible timestamp equality.
        session = ((update.ts_event + 86_400_000_000_000 - 1) // 86_400_000_000_000) * 86_400_000_000_000
        self._on_venue_mark(mark, session=session)

    def on_funding_rate(self, update: FundingRateUpdate) -> None:
        """Observe rates without mistaking the next scheduled payment for settlement.

        Nautilus' ``FundingRateUpdate.next_funding_ns`` is the *next* payment
        timestamp. The public Hyperliquid adapter supplies no prior/confirmed
        settlement identity or settlement mark in this update. Posting from it
        would charge funding early, so this path intentionally remains a
        no-op until the adapter provides a confirmed settlement event.
        """
        return

    def _on_venue_mark(self, mark: VenueMark, *, session: int | None = None) -> None:
        session = mark.ts_event if session is None else session
        if self._last_accepted_session is not None and session <= self._last_accepted_session:
            return
        self._marks_by_session.setdefault(session, {})[mark.instrument_id] = mark
        if (
            mark.ts_event in self.config.reporting_checkpoint_ns
            and mark.ts_event not in self.marked_equity_checkpoints
            and all(item in self._latest_marks and self._latest_marks[item].ts_event == mark.ts_event for item in (self.config.btc_id, self.config.sol_id))
        ):
            self.marked_equity_checkpoints[mark.ts_event] = {
                "timestamp": str(mark.ts_event),
                "marked_total": str(self._active_marked(self._latest_marks[self.config.btc_id], self._latest_marks[self.config.sol_id])),
                "basis": "NATIVE_CASH_PLUS_OPEN_POSITION_UNREALIZED_AT_PAIRED_VENUE_MARK",
            }
        self._try_advance_session(session)

    def _research_check_portfolio_protection(self, ts_now: int, *, after_observation: bool = False) -> None:
        """45% protective epoch peak, sampled only at paired causal marks."""
        if getattr(self, "_research_protection_defer_to_recorder", False) and not after_observation:
            return
        if not self.config.research_portfolio_protect_45 or self._research_protect_latch is not None or self._liquidating:
            return
        if self.config.terminal_close_at_ns is not None and ts_now >= self.config.terminal_close_at_ns:
            return
        marks = self._latest_marks
        if not all(i in marks and marks[i].ts_event == ts_now for i in (self.config.btc_id, self.config.sol_id)):
            return
        account = self.cache.account_for_venue(self.config.btc_id.venue)
        if account is None:
            return
        equity = _native_account_money(account)
        for position in self.cache.positions_open():
            if position.instrument_id in marks:
                instrument = self.cache.instrument(position.instrument_id)
                if instrument is None:
                    return
                equity += position.unrealized_pnl(instrument.make_price(marks[position.instrument_id].price)).as_decimal()
        self._research_protect_peak = max(self._research_protect_peak, equity)
        if equity > self._research_protect_peak * Decimal("0.55"):
            return
        episode = self._domain.episode
        latch = {"event": "BREACH", "timestamp_ns": str(ts_now), "decision_index": len(self._bars) - 1,
                 "old_episode_id": episode.id if episode else None,
                 "protective_peak": str(self._research_protect_peak), "native_equity": str(equity)}
        self._research_protect_latch = latch
        self.research_protection_audit.append(dict(latch))
        self._begin_forced_close("RESEARCH_PORTFOLIO_45")
        if not self.cache.positions_open() and not self.cache.orders_open():
            self._group_close_reconciliation_pending = True
            self._reconcile_group_flat()


    def _v3_equity(self) -> Decimal:
        account = self.cache.account_for_venue(self.config.btc_id.venue)
        equity = _native_account_money(account)
        for position in self.cache.positions_open():
            instrument = self.cache.instrument(position.instrument_id)
            equity += position.unrealized_pnl(instrument.make_price(self._latest_marks[position.instrument_id].price)).as_decimal()
        return equity

    def _v3_capture_sol_cycle(self, event) -> None:
        if self.config.research_v3_risk != "s10_15":
            return
        position = self.cache.position(event.position_id)
        if position is None or position.instrument_id != self.config.sol_id:
            return
        cycle = self._v3_sol_cycle
        if cycle is None or (cycle["flat"] and position.quantity.as_decimal() > 0):
            marks = [self._latest_marks.get(i) for i in (self.config.btc_id, self.config.sol_id)]
            if any(m is None or not 0 <= event.ts_event - m.ts_event <= self.config.max_mark_age_ns for m in marks):
                raise ValueError("V3_SOL_ANCHOR_FRESH_PAIRED_MARKS_REQUIRED")
            cycle = {"anchor": None, "anchor_marks": dict(self._latest_marks), "anchor_ns": event.ts_event, "realized": {}, "stage": 0, "flat": False}
            self._v3_sol_cycle = cycle
        cycle["realized"][str(position.id)] = position.realized_pnl.as_decimal() if position.realized_pnl is not None else Decimal("0")
        cycle["flat"] = not any(p.instrument_id == self.config.sol_id for p in self.cache.positions_open())

    def _v3_finalize_sol_anchor(self, ts_now: int) -> None:
        cycle = self._v3_sol_cycle
        if cycle is None or cycle["anchor"] is not None:
            return
        # Native accounting commits after fill/position callbacks. Post-quote
        # observer finalizes the first-fill checkpoint, using frozen first-fill
        # paired marks, never the next minute's price or callback cash deltas.
        current = self._latest_marks
        self._latest_marks = cycle["anchor_marks"]
        try:
            cycle["anchor"] = self._v3_equity()
        finally:
            self._latest_marks = current
        if cycle["anchor"] <= 0:
            raise ValueError("V3_SOL_ANCHOR_NOT_POSITIVE")
        self.v3_risk_audit.append({"event": "SOL_CYCLE_ANCHOR", "timestamp_ns": str(cycle["anchor_ns"]), "accounting_checkpoint_ns": str(ts_now), "anchor_equity": str(cycle["anchor"]), "mark_ns": str(cycle["anchor_ns"])})

    def _research_check_v3_risk(self, ts_now: int, *, after_observation: bool = False) -> None:
        mode = self.config.research_v3_risk
        if not mode or (getattr(self, "_research_protection_defer_to_recorder", False) and not after_observation):
            return
        if self.config.terminal_close_at_ns is not None and ts_now >= self.config.terminal_close_at_ns:
            return
        if not all(i in self._latest_marks and self._latest_marks[i].ts_event == ts_now for i in (self.config.btc_id, self.config.sol_id)):
            return
        equity = self._v3_equity()
        self._btc_sizing_peak = max(self._btc_sizing_peak, equity)
        self._btc_sizing_equity, self._btc_sizing_last_ns = equity, ts_now
        self._btc_sizing_dd = (self._btc_sizing_peak - equity) / self._btc_sizing_peak
        if mode == "b25" and self._btc_sizing_reduced and self._btc_sizing_dd <= Decimal(".15"):
            self._btc_sizing_reduced = False
            self.v3_risk_audit.append({"event": "B25_REARM", "timestamp_ns": str(ts_now), "global_peak": str(self._btc_sizing_peak)})
        episode = self._domain.episode
        if episode is None or self._liquidating or self._forced_close_reason is not None:
            return
        positions = self.cache.positions_open()
        if mode == "b25" and not self._btc_sizing_reduced and self._btc_sizing_dd >= Decimal(".25"):
            pnl = sum(self._btc_loss_realized.values(), Decimal("0")) if self._btc_loss_episode_id == episode.id else Decimal("0")
            for p in positions:
                if p.instrument_id == self.config.btc_id:
                    pnl += p.unrealized_pnl(self.cache.instrument(p.instrument_id).make_price(self._latest_marks[p.instrument_id].price)).as_decimal()
            if self._btc_loss_episode_id == episode.id and pnl < 0 and any(p.instrument_id == self.config.btc_id for p in positions):
                self._btc_sizing_reduced = True
                self._v3_begin_reduction(self.config.btc_id, Decimal(".5"), "B25", ts_now, {"btc_episode_net_pnl": str(pnl)})
        elif mode == "s10_15" and self._v3_sol_cycle is not None and self._v3_sol_cycle["anchor"] is not None:
            cycle = self._v3_sol_cycle
            pnl = sum(cycle["realized"].values(), Decimal("0"))
            for p in positions:
                if p.instrument_id == self.config.sol_id:
                    pnl += p.unrealized_pnl(self.cache.instrument(p.instrument_id).make_price(self._latest_marks[p.instrument_id].price)).as_decimal()
            loss = -pnl / cycle["anchor"]
            stage = 2 if loss >= Decimal(".15") else 1 if loss >= Decimal(".10") else 0
            if stage > cycle["stage"] and any(p.instrument_id == self.config.sol_id for p in positions):
                self._v3_sol_block_episode = episode.id
                ordinary_owned = (self._mandatory_sol_exit is not None or self._has_owned_sol_exit()
                    or any(i.action in {"SOL_HALF_EXIT", "SOL_EXIT"} for i, _, _ in self._queued_intents)
                    or any(i.action in {"SOL_HALF_EXIT", "SOL_EXIT"} for i in self._pending_by_order.values()))
                if ordinary_owned:
                    self._discard_queued_intents(lambda i: i.action == "SOL_ADD")
                    return
                cycle["stage"] = stage
                self._v3_begin_reduction(self.config.sol_id, Decimal("1") if stage == 2 else Decimal(".5"), "S15" if stage == 2 else "S10", ts_now, {"sol_cycle_net_pnl": str(pnl), "loss_fraction": str(loss), "anchor_equity": str(cycle["anchor"])})
        elif mode == "t3" and episode.btc_entry_vwap is not None and episode.best_f > .03:
            f = Decimal(episode.side) * (self._latest_marks[self.config.btc_id].price / Decimal(str(episode.btc_entry_vwap)) - 1)
            if f <= Decimal(str(episode.best_f)) - Decimal(".03"):
                self._v3_trail_trigger_ns = ts_now
                self._v3_trail_wait_ns = max(ts_now, self._current_btc.ts_event if self._current_btc else ts_now)
                episode.close_reason = "RESEARCH_V3_T3"
                self.v3_risk_audit.append({"event": "T3_TRIGGER", "timestamp_ns": str(ts_now), "native_equity": str(equity), "daily_best_f": episode.best_f, "minute_f": str(f)})
                self._begin_forced_close("RESEARCH_V3_T3")
                self._group_close_reconciliation_pending = True

    def _v3_begin_reduction(self, instrument_id, fraction: Decimal, reason: str, ts_now: int, detail: dict) -> None:
        position = next(p for p in self.cache.positions_open() if p.instrument_id == instrument_id)
        # Upgrade SOL half to full without creating concurrent reduction children.
        held = position.quantity.as_decimal()
        step = self.cache.instrument(instrument_id).size_increment.as_decimal()
        target_remaining = ((held * (1 - fraction)) // step) * step
        target = held - target_remaining
        if self._v3_reduction is not None:
            if reason != "S15":
                return
            owner = self._v3_reduction
            owner["remaining"] = position.quantity.as_decimal()
            owner["reason"] = reason
            for order in self.cache.orders_open():
                if order.instrument_id == instrument_id:
                    self.cancel_order(order)
        else:
            owner = {"instrument_id": instrument_id, "remaining": target, "reason": reason, "trigger_ns": ts_now, "retry_ns": ts_now, "orders": set()}
            self._v3_reduction = owner
        owner["pre_action_equity"] = self._v3_equity()
        self.v3_risk_audit.append({"event": "PROTECTIVE_TRIGGER", "reason": reason, "timestamp_ns": str(ts_now), "native_equity": str(owner["pre_action_equity"]), "global_peak": str(self._btc_sizing_peak), "drawdown_fraction": str(self._btc_sizing_dd), "quantity": str(target), **detail})
        self._discard_queued_intents(lambda intent: (intent.action.startswith("BTC") if instrument_id == self.config.btc_id else intent.action.startswith("SOL")))
        self._accepted_reductions = {k: v for k, v in self._accepted_reductions.items() if not k[1].startswith("BTC" if instrument_id == self.config.btc_id else "SOL")}
        for order in list(self.cache.orders_open()):
            if order.instrument_id == instrument_id and str(order.client_order_id) not in owner["orders"]:
                self.cancel_order(order)

    def _v3_submit_reduction(self, tick: QuoteTick) -> None:
        owner = self._v3_reduction
        instrument_id = owner["instrument_id"]
        if tick.instrument_id != instrument_id or tick.ts_event < max(owner["trigger_ns"], owner["retry_ns"]):
            return
        if owner["orders"]:
            return
        outstanding = [o for o in self.cache.orders_open() if o.instrument_id == instrument_id]
        if outstanding:
            for order in outstanding:
                self.cancel_order(order)
            return
        if any((i.action.startswith("BTC") if instrument_id == self.config.btc_id else i.action.startswith("SOL")) for i in self._pending_by_order.values()):
            return
        position = next((p for p in self.cache.positions_open() if p.instrument_id == instrument_id), None)
        if position is None:
            self._v3_reduction = None
            return
        instrument = self.cache.instrument(instrument_id)
        step = instrument.size_increment.as_decimal()
        rounded = (min(owner["remaining"], position.quantity.as_decimal()) // step) * step
        qty = instrument.make_qty(rounded)
        if qty.as_decimal() <= 0:
            self._v3_reduction = None
            self._queue_confirmed_btc_targets(None, len(self._bars)-1, tick.ts_event)
            return
        order = self.order_factory.market(instrument_id, OrderSide.SELL if position.is_long else OrderSide.BUY, qty, time_in_force=TimeInForce.IOC, reduce_only=True)
        if not self._record_submission(order, f"v3:{order.client_order_id}", "v3_protection", "PROTECTIVE_REDUCTION", owner["reason"], None):
            return
        oid = str(order.client_order_id)
        owner["orders"].add(oid)
        self._v3_orders[oid] = owner
        self.v3_risk_audit.append({"event": "PROTECTIVE_SUBMIT", "reason": owner["reason"], "order_id": oid, "timestamp_ns": str(tick.ts_event), "trigger_ns": str(owner["trigger_ns"]), "quote_ns": str(tick.ts_event), "executable_quote": str(tick.bid_price if position.is_long else tick.ask_price), "quantity": str(qty), "latency_ns": str(tick.ts_event-owner["trigger_ns"]), "native_equity": str(self._v3_equity())})
        self.submit_order(order)

    def _v3_finalize_fill_checkpoints(self, ts_now: int) -> None:
        if (self.config.research_v3_risk == "b25"
                and (self.config.terminal_close_at_ns is None or ts_now < self.config.terminal_close_at_ns)
                and all(i in self._latest_marks and self._latest_marks[i].ts_event == ts_now for i in (self.config.btc_id, self.config.sol_id))):
            self._btc_sizing_peak = max(self._btc_sizing_peak, self._v3_equity())
        for audit in self._v3_fill_checkpoints:
            audit["native_accounting_checkpoint_ns"] = str(ts_now)
            audit["native_equity_after_accounting"] = str(self._v3_equity())
            audit["equity_overshoot_after_accounting"] = str(Decimal(audit["pre_action_equity"])-self._v3_equity())
        self._v3_fill_checkpoints.clear()

    def _v3_reduction_fill(self, event) -> None:
        owner = self._v3_orders[str(event.client_order_id)]
        owner["remaining"] = max(Decimal("0"), owner["remaining"] - event.last_qty.as_decimal())
        episode = self._domain.episode
        if episode is not None:
            if event.instrument_id == self.config.btc_id:
                episode.btc_open_qty = max(0., episode.btc_open_qty - float(event.last_qty))
            else:
                episode.sol_qty = max(0., episode.sol_qty - float(event.last_qty))
                if episode.sol_qty == 0:
                    episode.sol_first_fill_at = episode.fixed_sigma = None
                    episode.sol_half_done = False
        self.v3_risk_audit.append({"event": "PROTECTIVE_FILL", "reason": owner["reason"], "order_id": str(event.client_order_id), "timestamp_ns": str(event.ts_event), "trigger_ns": str(owner["trigger_ns"]), "price": str(event.last_px), "quantity": str(event.last_qty), "commission": str(event.commission), "latency_ns": str(event.ts_event-owner["trigger_ns"]), "native_equity": str(self._v3_equity()), "equity_overshoot": str(owner["pre_action_equity"]-self._v3_equity())})
        self.v3_risk_audit[-1]["pre_action_equity"] = str(owner["pre_action_equity"])
        self._v3_fill_checkpoints.append(self.v3_risk_audit[-1])
        order = self.cache.order(event.client_order_id)
        if order is not None and order.is_closed:
            self._terminal_submission(str(event.client_order_id))
            self._v3_reduction_terminal(str(event.client_order_id), event.ts_event)

    def _v3_reduction_terminal(self, oid: str, ts_now: int) -> None:
        owner = self._v3_orders.pop(oid)
        owner["orders"].discard(oid)
        owner["retry_ns"] = ts_now + 60_000_000_000
        if owner["remaining"] <= 0 and self._v3_reduction is owner:
            self._v3_reduction = None
            if owner["instrument_id"] == self.config.btc_id:
                self._discard_queued_intents(lambda i: i.action.startswith("BTC"))
                self._queue_confirmed_btc_targets(None, len(self._bars)-1, ts_now)

    def _research_sample_btc_sizing(self, ts_now: int) -> None:
        """Whole native equity, once per paired minute before signals/quotes."""
        if not self.config.research_btc_drawdown_sizing or (self._btc_sizing_last_ns is not None and ts_now <= self._btc_sizing_last_ns):
            return
        if self.config.terminal_close_at_ns is not None and ts_now >= self.config.terminal_close_at_ns:
            return
        marks = self._latest_marks
        if not all(i in marks and marks[i].ts_event == ts_now for i in (self.config.btc_id, self.config.sol_id)):
            return
        account = self.cache.account_for_venue(self.config.btc_id.venue)
        if account is None:
            return
        equity = _native_account_money(account)
        for position in self.cache.positions_open():
            instrument = self.cache.instrument(position.instrument_id)
            equity += position.unrealized_pnl(instrument.make_price(marks[position.instrument_id].price)).as_decimal()
        self._btc_sizing_last_ns = ts_now
        self._btc_sizing_equity = equity
        self._btc_sizing_peak = max(self._btc_sizing_peak, equity)
        self._btc_sizing_dd = (self._btc_sizing_peak - equity) / self._btc_sizing_peak
        previous = self._btc_sizing_reduced
        if self._btc_sizing_dd >= Decimal("0.25"):
            self._btc_sizing_reduced = True
        elif self._btc_sizing_dd <= Decimal("0.15"):
            self._btc_sizing_reduced = False
        if previous != self._btc_sizing_reduced:
            self.btc_sizing_audit.append({"event": "DRAWDOWN_STATE_CHANGE", "timestamp_ns": str(ts_now),
                "native_equity": str(equity), "global_paired_minute_peak": str(self._btc_sizing_peak),
                "drawdown_fraction": str(self._btc_sizing_dd), "reduced": self._btc_sizing_reduced})

    def _research_btc_entry_multiplier(self) -> float | None:
        if self.config.research_v3_risk or self.config.research_h1_b1:
            base = 5.5 if self._current_signals[-1].side == 1 else 7.875
            return base / 2 if self.config.research_v3_risk == "b25" and self._btc_sizing_reduced else base
        if self.config.research_btc_direction_sizing:
            return 5.5 if self._current_signals[-1].side == 1 else 7.875
        if self.config.research_btc_drawdown_sizing:
            if self._btc_sizing_last_ns is None:
                raise ValueError("RESEARCH_BTC_SIZING_PAIRED_NATIVE_SAMPLE_MISSING")
            return 3.9375 if self._btc_sizing_reduced else 7.875
        return None

    def _research_capture_btc_episode(self, event) -> None:
        """Native Position.realized_pnl already includes settlement-currency fees."""
        if not (self.config.research_btc_episode_loss_20 or self.config.research_v3_risk == "b25"):
            return
        episode = self._domain.episode
        position = self.cache.position(event.position_id)
        if episode is None or position is None or position.instrument_id != self.config.btc_id:
            return
        if self._btc_loss_episode_id != episode.id:
            # Only a first confirmed BTC fill establishes this immutable basis.
            if episode.btc_initial_qty <= 0:
                return
            marks = [self._latest_marks.get(i) for i in (self.config.btc_id, self.config.sol_id)]
            if any(m is None or self.config.max_mark_age_ns <= 0
                   or not 0 <= event.ts_event - m.ts_event <= self.config.max_mark_age_ns for m in marks):
                raise ValueError("BTC_LOSS_REFERENCE_FRESH_MARKS_MISSING")
            self._btc_loss_episode_id = episode.id
            account = self.cache.account_for_venue(self.config.btc_id.venue)
            self._btc_loss_reference = _native_account_money(account)
            for held in self.cache.positions_open():
                instrument = self.cache.instrument(held.instrument_id)
                mark = self._latest_marks[held.instrument_id]
                self._btc_loss_reference += held.unrealized_pnl(instrument.make_price(mark.price)).as_decimal()
            if self._btc_loss_reference <= 0:
                raise ValueError("BTC_LOSS_REFERENCE_EQUITY_NOT_POSITIVE")
            self._btc_loss_realized.clear()
            self.btc_episode_loss_audit.append({"event": "REFERENCE", "episode_id": episode.id,
                "timestamp_ns": str(event.ts_event), "native_equity_reference": str(self._btc_loss_reference)})
        if any(fee.currency != position.settlement_currency for fee in position.commissions()):
            raise ValueError("BTC_LOSS_NATIVE_COMMISSION_CURRENCY_UNSUPPORTED")
        self._btc_loss_realized[str(position.id)] = position.realized_pnl.as_decimal() if position.realized_pnl is not None else Decimal("0")

    def _research_check_btc_episode_loss(self, ts_now: int, *, after_observation: bool = False) -> None:
        if getattr(self, "_research_protection_defer_to_recorder", False) and not after_observation:
            return
        if (not self.config.research_btc_episode_loss_20 or self._research_protect_latch is not None
                or self._liquidating or self._forced_close_reason is not None):
            return
        if self.config.terminal_close_at_ns is not None and ts_now >= self.config.terminal_close_at_ns:
            return
        episode = self._domain.episode
        if episode is None or episode.id != self._btc_loss_episode_id or self._btc_loss_reference is None:
            return
        marks = self._latest_marks
        if not all(i in marks and marks[i].ts_event == ts_now for i in (self.config.btc_id, self.config.sol_id)):
            return
        pnl = sum(self._btc_loss_realized.values(), Decimal("0"))
        instrument = self.cache.instrument(self.config.btc_id)
        for position in self.cache.positions_open():
            if position.instrument_id == self.config.btc_id:
                pnl += position.unrealized_pnl(instrument.make_price(marks[self.config.btc_id].price)).as_decimal()
        if pnl > -Decimal("0.20") * self._btc_loss_reference:
            return
        latch = {"event": "BREACH", "timestamp_ns": str(ts_now), "decision_index": len(self._bars) - 1,
                 "old_episode_id": episode.id, "reason": "RESEARCH_BTC_EPISODE_LOSS_20",
                 "native_equity_reference": str(self._btc_loss_reference), "native_btc_episode_net_pnl": str(pnl)}
        self._research_protect_latch = latch
        self.btc_episode_loss_audit.append(dict(latch))
        self._begin_forced_close("RESEARCH_BTC_EPISODE_LOSS_20")
        self._group_close_reconciliation_pending = True
        self._reconcile_group_flat()

    def _research_protection_next_decision_eligible(self) -> bool:
        latch = self._research_protect_latch
        return bool(latch is not None and self._current_btc is not None
                    and len(self._bars) - 1 > latch["decision_index"]
                    and self._current_btc.ts_event > int(latch["timestamp_ns"])
                    and not self.cache.positions_open() and not self.cache.orders_open()
                    and not self._pending_by_order and self._forced_close_reason is None
                    and self._domain.episode is None)

    def _check_mark_first_liquidation(self, ts_now: int) -> None:
        if self.config.deposit_runtime is not None and self._deposit.latched:
            return  # Native market_exit owns every close after the drawdown latch.
        if self._liquidating or any(item not in self._latest_marks for item in (self.config.btc_id, self.config.sol_id)):
            return
        if not self.config.research_v0_execution_repairs:
            if self._latest_marks[self.config.btc_id].ts_event != ts_now or self._latest_marks[self.config.sol_id].ts_event != ts_now:
                return
        else:
            exposed = {item.instrument_id for item in self.cache.positions_open() if item.instrument_id in (self.config.btc_id, self.config.sol_id)}
            age = self.config.max_mark_age_ns
            if age <= 0 or any(
                self._latest_marks[item].ts_event > ts_now or ts_now - self._latest_marks[item].ts_event > age
                for item in exposed
            ):
                return
        positions = [item for item in self.cache.positions_open() if item.instrument_id in (self.config.btc_id, self.config.sol_id)]
        if not positions or self.config.margin_policy is None:
            return
        account = self.cache.account_for_venue(self.config.btc_id.venue)
        base = self.cache.instrument(self.config.btc_id)
        if account is None or base is None:
            return
        try:
            policy = self.config.margin_policy
            equity, maintenance = _native_account_money(account), Decimal("0")
            for position in positions:
                instrument = self.cache.instrument(position.instrument_id)
                if instrument is None:
                    return
                mark = self._latest_marks[position.instrument_id].price
                equity += position.unrealized_pnl(instrument.make_price(mark)).as_decimal()
                maintenance += policy.margin_for(position.instrument_id, position.quantity.as_decimal(), ts_now)[1]
        except ValueError:
            return
        if equity > maintenance:
            return
        self._liquidating = True
        self._accepted_reductions.clear()
        self._queued_intents.clear()
        self._queued_intent_ready_ns.clear()
        self._deferred_selective_entries.clear()
        self._selected_entry_audits.clear()
        self._liquidation_waiting = {position.instrument_id for position in positions}
        self.liquidation_audit.append({
            "trigger_ts": str(ts_now),
            "marked_equity": str(equity),
            "tier_maintenance_margin": str(maintenance),
            "status": "ARMED",
            "close_fills": [],
            "close_value": "0",
            "lockout": "true",
        })
        self._begin_forced_close("LIQUIDATION")

    def _try_advance_session(self, session: int) -> None:
        """Consume each paired UTC close once and only in contiguous order."""
        while self._day:
            if self._deferred_entry_session is not None and self._halt_on_deferred_daily_decision():
                return
            next_session = (
                self._last_accepted_session + 86_400_000_000_000
                if self._last_accepted_session is not None else min(self._day)
            )
            paired = self._day.get(next_session)
            marks = self._marks_by_session.get(next_session)
            required = (self.config.btc_bar_type, self.config.sol_bar_type)
            if paired is None or marks is None or any(item not in paired for item in required) or any(
                item not in marks for item in (self.config.btc_id, self.config.sol_id)
            ):
                self._daily_decision_reason = "WAITING_CONTIGUOUS_PAIRED_SESSION"
                return
            btc, sol = paired[self.config.btc_bar_type], paired[self.config.sol_bar_type]
            btc_mark, sol_mark = marks[self.config.btc_id], marks[self.config.sol_id]
            del self._day[next_session]
            del self._marks_by_session[next_session]
            close_time = datetime.fromtimestamp(next_session / 1_000_000_000, UTC)
            available_at = datetime.fromtimestamp(
                max(btc.ts_init, sol.ts_init, btc_mark.ts_init, sol_mark.ts_init, next_session) / 1_000_000_000, UTC,
            )
            if self.config.research_regime_reentry_band is not None:
                self._hb_daily_ohlc[next_session] = (float(btc.high), float(btc.low))
            self._carry_daily_bar(btc)
            self._bars.append(DailyBar(close_time - timedelta(days=1), close_time, available_at, float(btc.open), float(btc.close), float(sol.close)))
            self._last_accepted_session = next_session
            self._last_sol_close = float(sol.close)
            self._current_btc, self._current_sol = btc, sol
            self._current_btc_mark, self._current_sol_mark = btc_mark, sol_mark
            self._current_signals = features_for(self._bars, self._candidate)
            if next_session < (self._latest_seen_session or next_session):
                # This session arrived after a newer signal. It repairs the
                # feature chain but must never replay an old execution price.
                self._daily_decision_reason = "BACKFILL_FEATURES_ONLY"
                continue
            if self.config.terminal_close_at_ns is not None and next_session >= self.config.terminal_close_at_ns:
                self._submit_terminal_closes()
                return
            self._daily_decision_reason = "CURRENT_PAIRED_SESSION"
            self._advance_current_day()

    def queue_verified_backfill(self, rows: list[DailyBar]) -> None:
        """Hand off a validated same-source artifact to the native callback thread."""
        self._pending_verified_backfill = tuple(rows)

    def _apply_verified_backfill(self) -> None:
        rows = self._pending_verified_backfill
        if rows is None:
            return
        self._pending_verified_backfill = None
        try:
            self.backfill_signal_history(list(rows))
        except ValueError as error:
            self._backfill_error = str(error)
            self._daily_decision_reason = "SIGNAL_BACKFILL_GAP"

    def backfill_signal_history(self, rows: list[DailyBar]) -> int:
        """Import verified same-source closed days as features, never trades."""
        # Only sessions strictly before the latest observed live signal may be
        # repaired from verified history. A partial earlier live session must
        # not block its own verified replacement or replay an old decision.
        cutoff = self._latest_seen_session
        if cutoff is None or (self._last_accepted_session is not None and cutoff <= self._last_accepted_session):
            return 0
        appended = 0
        for row in rows:
            session = int(row.close_time.timestamp() * 1_000_000_000)
            if self._last_accepted_session is not None and session <= self._last_accepted_session:
                continue
            if cutoff is not None and session >= cutoff:
                break
            if self._last_accepted_session is not None and session != self._last_accepted_session + 86_400_000_000_000:
                raise ValueError("SIGNAL_BACKFILL_GAP")
            self._bars.append(row)
            self._last_accepted_session = session
            # The verified same-source row supersedes any incomplete live
            # tuple/mark for this closed session; neither may hold the cursor.
            self._day.pop(session, None)
            self._marks_by_session.pop(session, None)
            appended += 1
        if appended:
            self._current_signals = features_for(self._bars, self._candidate)
            if self._deferred_entry_session is not None and self._deferred_entry_session <= self._last_accepted_session:
                self._deferred_entry_session = None
            self._daily_decision_reason = "BACKFILL_FEATURES_ONLY"
            # A current paired session may already be waiting behind the
            # repaired gap. Consume it once, never the historical row above.
            self._try_advance_session(cutoff)
        return appended

    def daily_decision_status(self) -> dict[str, object]:
        return {
            "accepted_session_ns": self._last_accepted_session,
            "latest_seen_session_ns": self._latest_seen_session,
            "deferred_entry_session_ns": self._deferred_entry_session,
            "reason": self._daily_decision_reason,
            "backfill_error": self._backfill_error,
        }

    def _advance_current_day(self) -> None:
        if self.config.deposit_runtime is not None and self._deposit.latched:
            self._daily_decision_reason = "DEPOSIT_PROTECTION_LATCHED"
            return
        if self._current_btc is None or self._current_sol is None or self._current_btc_mark is None or self._current_sol_mark is None:
            return
        # Bars are emitted at close.  Features may warm up beforehand, but no
        # domain decision (and therefore no order) may occur before the
        # configured interval's first daily open.
        if self.config.trading_start_open_ns is not None and self._current_btc.ts_event - 86_400_000_000_000 < self.config.trading_start_open_ns:
            return
        if self._liquidating or self._backfill_error is not None:
            return
        if not self._hedge_band_allowed():
            return
        if not self._b1_gate_daily():
            self._daily_decision_reason = "B1_WAIT_FRESH_CONFIRMATION"
            return
        if self.config.research_v3_risk:
            ns = self._current_btc.ts_event
            side = self._current_signals[-1].side
            if ns != self._v3_daily_ns:
                self._v3_daily_count = self._v3_daily_count + 1 if side == self._v3_daily_side else 1
                self._v3_daily_side, self._v3_daily_ns = side, ns
            if self._domain.episode is None:
                if self._v3_trail_wait_ns is not None and ns <= self._v3_trail_wait_ns:
                    return
                if self.config.research_v3_risk == "r2" and self._v3_regime_wait:
                    if self._v3_daily_count < 2 or self.cache.positions_open() or self.cache.orders_open() or self._pending_by_order:
                        return
                    self._v3_regime_wait = False
                    self.v3_risk_audit.append({"event": "R2_REARM", "timestamp_ns": str(ns), "side": side, "consecutive_daily_closes": self._v3_daily_count})
        rearm_candidate = self._research_protection_next_decision_eligible() if self._research_protect_latch is not None else False
        if self._research_protect_latch is not None and not rearm_candidate:
            self._daily_decision_reason = "RESEARCH_RISK_WAIT_NEXT_EPISODE"
            return
        entries_enabled = self._entries_enabled(ignore_research_protection=True) if rearm_candidate else self._entries_enabled()
        if not entries_enabled and not self.cache.positions_open():
            # `_try_advance_session` has intentionally consumed its paired
            # source tuple by now. Preserve this exact session so reopening a
            # readiness/control gate can evaluate the same causal daily bar.
            self._deferred_entry_session = self._current_btc.ts_event
            self._daily_decision_reason = "DEFERRED_ENTRY_GATE"
            return
        if self._deferred_entry_session == self._current_btc.ts_event:
            self._deferred_entry_session = None
        if self._carry_daily(self._current_btc.ts_event):
            self._daily_decision_reason = "CHOP_PAIR_OWNED_NO_BACKLOG"
            return
        self._bind_native_lots()
        if self._split_unfinished() and self._domain.episode is not None:
            # Mandatory regime/trail decisions precede the domain pending lock;
            # only ordinary work waits for completion of this same parent.
            self._domain.episode.pending[self._split_parent["intent"].id] = self._split_parent["intent"]
        intents = self._domain.decide(
            self._bars, self._current_signals, len(self._bars) - 1,
            self._active_marked(self._current_btc_mark, self._current_sol_mark),
            **({"btc_notional_multiplier": self._research_btc_entry_multiplier()} if (self.config.research_btc_direction_sizing or self.config.research_btc_drawdown_sizing or self.config.research_v3_risk or self.config.research_h1_b1) else {}),
        )
        if self.config.research_btc_direction_sizing or self.config.research_btc_drawdown_sizing or self.config.research_v3_risk or self.config.research_h1_b1:
            for entry in intents:
                if entry.action == "BTC_ENTRY":
                    self.btc_sizing_audit.append({"event": "EPISODE_ENTRY_SIZING", "episode_id": entry.episode_id,
                        "timestamp_ns": str(self._current_btc.ts_event), "side": entry.side,
                        "frozen_multiplier": str(self._domain.episode.btc_sizing_multiplier),
                        "requested_notional": str(entry.requested_notional),
                        "native_sample_ns": str(self._btc_sizing_last_ns),
                        "global_paired_minute_peak": str(self._btc_sizing_peak),
                        "drawdown_fraction": str(self._btc_sizing_dd), "reduced": self._btc_sizing_reduced})
        if rearm_candidate:
            entry = next((intent for intent in intents if intent.action == "BTC_ENTRY"), None)
            if entry is None:
                return  # No new genuine domain episode: protection remains latched.
            old = self._research_protect_latch
            if entry.episode_id == old["old_episode_id"]:
                raise ValueError("RESEARCH_PROTECTION_OLD_EPISODE_REENTRY")
            account = self.cache.account_for_venue(self.config.btc_id.venue)
            if self.config.research_portfolio_protect_45:
                self._research_protect_peak = _native_account_money(account)
            self.research_protection_audit.append({"event": "REARM_NEXT_EPISODE", "timestamp_ns": str(self._current_btc.ts_event),
                "decision_index": len(self._bars) - 1, "old_episode_id": old["old_episode_id"], "new_episode_id": entry.episode_id,
                "protective_peak": str(self._research_protect_peak), "global_observer_peak_reset": False})
            if self.config.research_btc_episode_loss_20:
                self.btc_episode_loss_audit.append({"event": "REARM_NEXT_EPISODE", "timestamp_ns": str(self._current_btc.ts_event), "old_episode_id": old["old_episode_id"], "new_episode_id": entry.episode_id, "global_observer_peak_reset": False})
            self._research_protect_latch = None
        self._daily_decision_reason = getattr(self._domain, "last_decision_reason", "CURRENT_DECISION_EVALUATED") if not intents else "CURRENT_DECISION_INTENTS"
        for intent in intents:
            if self.config.research_sol_btc_open_only and intent.action == "SOL_ADD" and self._hb_position(self.config.btc_id) is None:
                self._domain.on_parent_terminal(intent.id)
                continue
            if intent.action == "CLOSE_ALL":
                if self.config.research_v3_risk == "r2" and intent.reason == "REGIME":
                    self._v3_regime_wait = True
                    self.v3_risk_audit.append({"event": "R2_REGIME_CLOSE_WAIT", "timestamp_ns": str(self._current_btc.ts_event), "side": self._v3_daily_side, "consecutive_daily_closes": self._v3_daily_count})
                # A mandatory group exit owns the next executable quotes.  It
                # must not wait behind an older queued SOL add or planned exit.
                self._discard_queued_intents(lambda queued: queued.id != intent.id)
                self._begin_forced_close(intent.reason or "CLOSE_ALL", intent)
                return
            if ((intent.action == "SOL_EXIT" and intent.reason == "SOL_HARD_TIMEOUT")
                    or (intent.action in {"SOL_HALF_EXIT", "SOL_EXIT"} and self._v3_reduction is not None
                        and self._v3_reduction["instrument_id"] == self.config.sol_id)):
                if self._v3_reduction is not None and self._v3_reduction["instrument_id"] == self.config.sol_id:
                    self._v3_reduction = None
                self._preempt_with_mandatory_sol_exit(intent, self._current_signals[-1].sigma, len(self._bars) - 1)
                return
            if self._v3_reduction is not None and (intent.action.startswith("BTC") if self._v3_reduction["instrument_id"] == self.config.btc_id else intent.action.startswith("SOL")):
                self._domain.on_parent_terminal(intent.id)
                continue
            if self.config.research_v0_selective_lifecycle_repairs and (
                self._reduction_key(intent) in self._accepted_reductions
                or (intent.action.startswith("SOL") and self._has_owned_sol_exit())
            ):
                self._domain.on_parent_terminal(intent.id)
                continue
            self._queued_intents.append((intent, self._current_signals[-1].sigma, len(self._bars) - 1))
            self._queued_intent_ready_ns[intent.id] = self._current_btc.ts_event + self.config.execution_delay_ns

    def _halt_on_deferred_daily_decision(self) -> bool:
        return False

    def _retry_deferred_daily_decision(self) -> None:
        """Retry one blocked flat daily decision after its entry gate reopens."""
        if self._current_btc is None or self._deferred_entry_session != self._current_btc.ts_event:
            return
        if self.cache.positions_open():
            # A native position is authoritative; a deferred flat entry must
            # never add risk after the state has changed.
            self._deferred_entry_session = None
            return
        if not self._entries_enabled():
            return
        # Clear before deciding. If the final gate closes again, the regular
        # path reinstates the same session; otherwise later quotes cannot
        # create a duplicate domain decision.
        self._deferred_entry_session = None
        self._advance_current_day()

    def on_quote_tick(self,tick:QuoteTick,*,decision_ns:int|None=None)->None:
        """Only real quotes execute; optional live decision clock never rewrites tick."""
        ts_decision=tick.ts_event if decision_ns is None else decision_ns
        if self.config.research_residual_recovery and (self._forced_close_reason or self._liquidating or self._mandatory_sol_exit is not None):self._c1_revoke(ts_decision,"MANDATORY_QUOTE_PRIORITY")
        if self.config.research_h1_b1 == "h1" and tick.instrument_id == self.config.sol_id:
            self._h1_sol_quote_sequence += 1
        if self.config.research_h1_b1 == "b1" and tick.instrument_id == self.config.btc_id:
            self._b1_btc_quote_sequence += 1
        if self._v3_reduction is not None and tick.instrument_id == self._v3_reduction["instrument_id"] and self._forced_close_reason is None and not self._liquidating and self._mandatory_sol_exit is None:
            self._v3_submit_reduction(tick)
            return
        if self.config.deposit_runtime is not None and self._deposit.latched:
            self._risk_first_sol_stop("DP")
            self._split_stop("DP")
            if self.config.research_v0_deferred_selective_zero_tp:
                self._discard_queued_intents(lambda queued: queued.action == "BTC_ENTRY")
            return
        if self.config.research_v0_deferred_selective_zero_tp and tick.instrument_id == self.config.btc_id:
            self._activate_selective_sol_rights(tick)
        # Verified artifacts are queued off-thread. A quote may apply one
        # after the latest paired session is buffered, but must not consume
        # warmup history before any live signal establishes a safe cutoff.
        if self._latest_seen_session is not None and (
            self._last_accepted_session is None or self._latest_seen_session > self._last_accepted_session
        ):
            self._apply_verified_backfill()
        self._retry_deferred_daily_decision()
        if self._mandatory_sol_exit is not None:
            # A timeout is allowed to cancel a stale/resting SOL reduction,
            # then uses the actual native position leaves on the next SOL
            # quote. No queued increase may pass while this is in progress.
            if (tick.instrument_id != self.config.sol_id
                    or (self.config.research_residual_recovery and self._c1_own_pending())
                    or any(order.instrument_id == self.config.sol_id for order in self.cache.orders_open())
                    or any(owner["instrument_id"] == self.config.sol_id for owner in self._v3_orders.values())
                    or (self.config.research_h1_b1 == "h1" and any(i.action == "SOL_ADD" for i in self._pending_by_order.values()))):
                return
            intent, sigma, index = self._mandatory_sol_exit
            if self.config.research_v0_execution_repairs and ts_decision < self._mandatory_sol_retry_after_ns:
                return
            self._mandatory_sol_exit = None
            self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), sigma, index, ts_now=ts_decision)
            return
        if self._forced_close_reason is not None:
            self._submit_forced_close_on_quote(tick)
            return
        if self._liquidating:
            if tick.instrument_id in self._liquidation_waiting and tick.instrument_id not in self._liquidation_submitted:
                position = next((item for item in self.cache.positions_open() if item.instrument_id == tick.instrument_id), None)
                instrument = self.cache.instrument(tick.instrument_id)
                if position is not None and instrument is not None:
                    order = self.order_factory.market(instrument_id=tick.instrument_id, order_side=OrderSide.SELL if position.is_long else OrderSide.BUY, quantity=instrument.make_qty(position.quantity.as_decimal()), time_in_force=TimeInForce.IOC, reduce_only=True)
                    if self._record_submission(order, f"liquidation:{order.client_order_id}", "liquidation", "LIQUIDATION_CLOSE"):
                        self._liquidation_submitted.add(tick.instrument_id); self._liquidation_orders.add(str(order.client_order_id)); self.submit_order(order)
            return
        if self._carry_check(tick):
            return
        if self.config.research_h1_b1 == "b1" and tick.instrument_id == self.config.btc_id:
            candidate = self._b1_candidate
            if (candidate and candidate["confirmed_ns"] is not None
                    and self._confirmation_receipt_is_current(candidate["confirmed_ns"],
                        (candidate.get("confirmation_receipt_ns"), candidate.get("eligible_quote_sequence")),
                        self._b1_btc_quote_sequence, ts_decision)
                    and self._confirmation_marks_current(ts_decision)
                    and self._b1_flat_resolved()
                    and self._entries_enabled()):
                self._current_btc_mark = self._latest_marks.get(self.config.btc_id)
                self._current_sol_mark = self._latest_marks.get(self.config.sol_id)
                self._b1_consuming = True
                try:
                    self._advance_current_day()
                finally:
                    self._b1_consuming = False
                if self._domain.episode is not None:
                    self.h1_b1_audit.append({"event": "B1_CONFIRMED_ENTRY", **candidate,
                                            "quote_ns": ts_decision})
                    self._b1_candidate = None
        if tick.instrument_id == self.config.sol_id:
            self._h1_check(ts_decision)
        self._split_check(tick)
        self._cover_check(tick)
        self._conditional_check(tick)
        self._risk_first_sol_check(tick)
        for item in list(self._queued_intents):
            intent, sigma, index = item
            if ts_decision < self._queued_intent_ready_ns.get(intent.id, 0):
                continue
            if self._split_unfinished() and intent.action == "BTC_REDUCE":
                continue
            if self._split_tp_ioc_eligible(intent) and any(self._reduction_key(owned)==self._reduction_key(intent) for owned in self._pending_by_order.values()):
                continue
            target = self.config.btc_id if intent.action.startswith("BTC") else self.config.sol_id
            if intent.action == "CLOSE_ALL":
                self._queued_intents.remove(item)
                self._queued_intent_ready_ns.pop(intent.id, None)
                self._begin_forced_close(intent.reason or "CLOSE_ALL", intent)
                continue
            if target == tick.instrument_id:
                if self.config.research_v0_selective_lifecycle_repairs and intent.action == "BTC_REDUCE" and intent.limit_price is None and self._reduction_key(intent) in self._accepted_reductions:
                    episode = self._domain.episode
                    if episode is None or episode.btc_entry_vwap is None or intent.level is None:
                        continue
                    threshold = Decimal(str(btc_management_price(episode))) * (1 + episode.side * Decimal(str(episode.wave_levels[intent.level])))
                    eligible = tick.bid_price.as_decimal() >= threshold if episode.side == 1 else tick.ask_price.as_decimal() <= threshold
                    if not eligible:
                        continue  # Retain conditional leaves on adverse quotes.
                if self.config.research_v0_selective_lifecycle_repairs and intent.action == "SOL_ADD" and self._has_owned_sol_exit():
                    self._discard_queued_intents(lambda queued: queued.id == intent.id)
                    continue
                if self.config.research_v0_deferred_selective_zero_tp and intent.action == "BTC_ENTRY":
                    selected = self._select_deferred_btc_entry(intent, tick)
                    if selected is None:
                        continue
                    if selected <= 0:
                        self._queued_intents.remove(item)
                        self._queued_intent_ready_ns.pop(intent.id, None)
                        self._deferred_selective_entries.pop(intent.id, None)
                        self._selected_entry_audits.pop(intent.id, None)
                        self._domain.on_parent_terminal(intent.id)
                        continue
                    self._queued_intents.remove(item)
                    self._queued_intent_ready_ns.pop(intent.id, None)
                    self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), sigma, index, ts_now=ts_decision, entry_override_qty=selected)
                    self._deferred_selective_entries.pop(intent.id, None)
                    continue
                if self.config.research_v0_execution_repairs and intent.action == "SOL_ADD":
                    stale = self._stale_sol_add(intent, index)
                    if stale is None:
                        continue  # Wait for a paired executable current session.
                    if stale:
                        self._queued_intents.remove(item)
                        self._queued_intent_ready_ns.pop(intent.id, None)
                        self._domain.on_parent_terminal(intent.id)
                        if self._mandatory_sol_exit is None and not any(
                            queued.action in {"SOL_HALF_EXIT", "SOL_EXIT", "CLOSE_ALL"}
                            and queued.episode_id == intent.episode_id for queued, _, _ in self._queued_intents
                        ):
                            self._advance_current_day()
                        continue
                if not self._next_before_submit(intent,ts_decision):
                    continue
                self._queued_intents.remove(item)
                self._queued_intent_ready_ns.pop(intent.id, None)
                self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), sigma, index, ts_now=ts_decision)

        self._hedge_quote(tick)
        self._next_quote(tick,decision_ns=ts_decision)
        self._c1_quote(tick,decision_ns=ts_decision)

    def _select_deferred_btc_entry(self, intent: Intent, tick: QuoteTick) -> Decimal | None:
        """Observe q0, then choose entry lots from the next causal BTC quote."""
        episode = self._domain.episode
        instrument = self.cache.instrument(self.config.btc_id)
        if episode is None or episode.id != intent.episode_id or instrument is None or episode.wave_levels is None:
            return Decimal("0")
        plan = self._deferred_selective_entries.get(intent.id)
        if plan is None:
            price = tick.ask_price.as_decimal() if intent.side == 1 else tick.bid_price.as_decimal()
            if price <= 0 or intent.requested_notional is None:
                return Decimal("0")
            step = instrument.size_increment.as_decimal()
            # Match the existing q0 native entry's float-to-Decimal lot path.
            gross_quantity = float(Decimal(str(intent.requested_notional)) / price)
            gross_lots = int(Decimal(str(gross_quantity)) // step)
            if gross_lots <= 0:
                return Decimal("0")
            fractions = tuple(Decimal(str(value)) for value in self._candidate.btc_tp_fractions_initial_qty)
            target_lots = {}
            assigned = 0
            for level, fraction in enumerate(fractions):
                lots = gross_lots - assigned if level == len(fractions) - 1 and sum(fractions) == Decimal("1") else int((Decimal(gross_lots) * fraction).to_integral_value(rounding=ROUND_FLOOR))
                target_lots[level] = lots
                assigned += lots
            self._deferred_selective_entries[intent.id] = {
                "q0_ns": tick.ts_event,
                "session_ns": self._last_accepted_session,
                "gross_lots": gross_lots,
                "target_lots": target_lots,
                "zero_levels": {level for level, value in enumerate(episode.wave_levels) if Decimal(str(value)) == 0},
                "reference_wire_price": _native_limit_price(instrument, price).as_decimal(),
                "step": step,
            }
            return None
        if tick.ts_event <= plan["q0_ns"]:
            return None
        if (
            self.config.max_mark_age_ns <= 0 or tick.ts_event - plan["q0_ns"] > self.config.max_mark_age_ns
            or self._last_accepted_session != plan["session_ns"]
            or (self.config.terminal_close_at_ns is not None and tick.ts_event >= self.config.terminal_close_at_ns)
            or not self._entries_enabled() or self._forced_close_reason is not None or self._liquidating
        ):
            return Decimal("0")
        quote_side = tick.bid_price.as_decimal() if episode.side == 1 else tick.ask_price.as_decimal()
        reference = plan["reference_wire_price"]
        passive = reference > quote_side if episode.side == 1 else reference < quote_side
        # This is a prediction about the old q0-reference target at q1, not
        # an oracle for a new entry's later q2 target.
        omitted = plan["zero_levels"] if passive else set()
        net_lots = sum(lots for level, lots in plan["target_lots"].items() if level not in omitted)
        episode.btc_reference_qty = float(Decimal(plan["gross_lots"]) * plan["step"])
        episode.btc_reference_target_lots = dict(plan["target_lots"]) if passive else {}
        episode.btc_omitted_zero_levels = set(omitted)
        # Both branches retain the original planned entry denominator, so a
        # partial native fill cannot grant a full TP-derived SOL right.
        episode.btc_net_planned_qty = float(Decimal(net_lots) * plan["step"])
        episode.btc_zero_resting_suppressed = set() if passive else set(plan["zero_levels"])
        if passive:
            episode.btc_deferred_right_reference_price = reference
        self._selected_entry_audits[intent.id] = {
            "episode_id": episode.id, "intent_id": intent.id,
            "q0_ns": str(plan["q0_ns"]), "q1_ns": str(tick.ts_event),
            "reference_wire_price": str(reference),
            "q1_bid": str(tick.bid_price), "q1_ask": str(tick.ask_price),
            "branch": "PASSIVE_NET_ZERO_LEVELS" if passive else "MARKETABLE_FULL_ENTRY_FALLBACK",
            "reference_btc_qty": str(episode.btc_reference_qty),
            "net_submitted_btc_qty": str(Decimal(net_lots) * plan["step"]),
            "confirmed_native_entry_qty": "0",
            "omitted_zero_levels": sorted(omitted),
            "reference_target_lots": dict(plan["target_lots"]),
            "sol_right_activations": [],
        }
        return Decimal(net_lots) * plan["step"]

    def _activate_selective_sol_rights(self, tick: QuoteTick) -> None:
        episode = self._domain.episode
        if episode is None or episode.btc_deferred_right_reference_price is None or self._forced_close_reason is not None or self._liquidating or (self.config.deposit_runtime is not None and self._deposit.latched):
            return
        reference = episode.btc_deferred_right_reference_price
        crossed = tick.bid_price.as_decimal() >= reference if episode.side == 1 else tick.ask_price.as_decimal() <= reference
        earned = episode.btc_initial_qty > 0 and any(episode.sol_right_fraction.get(level, 0) > 0 for level in episode.btc_omitted_zero_levels)
        if crossed and (not self.config.research_v0_selective_lifecycle_repairs or earned):
            episode.btc_deferred_right_touched = True
        if not episode.btc_deferred_right_touched or not self._bars:
            return
        session = int(self._bars[-1].close_time.timestamp() * 1_000_000_000)
        if (
            self._current_btc is None or self._current_sol is None
            or self._current_btc.ts_event != session or self._current_sol.ts_event != session
            or self._last_accepted_session != session
            or (self._latest_seen_session is not None and self._latest_seen_session != session)
        ):
            return  # A feature-only backfill is never an executable decision.
        newly_active = sorted(level for level in episode.btc_omitted_zero_levels if level in episode.sol_right_fraction and level not in episode.sol_rights)
        if not newly_active:
            return
        for level in newly_active:
            episode.sol_rights.add(level)
            episode.sol_right_decision_index[level] = len(self._bars) - 1
        if self.entry_sizing_audit:
            self.entry_sizing_audit[-1]["sol_right_activations"].append({
                "timestamp_ns": str(tick.ts_event), "levels": newly_active,
                "confirmed_native_entry_qty": str(episode.btc_initial_qty),
            })
        if self._mandatory_sol_exit is None and self._forced_close_reason is None:
            self._advance_current_day()

    def _stale_sol_add(self, intent: Intent, index: int) -> bool | None:
        if self.config.research_h1_b1 == "h1" and intent.reason in {"H1_STAGE1", "H1_STAGE2"}:
            episode = self._domain.episode
            return episode is None or episode.id != intent.episode_id or self._h1_cycle is None or self._h1_cycle["closed"]
        episode = self._domain.episode
        if episode is None or intent.episode_id != episode.id or not self._bars:
            return True
        # Verified backfill is feature history only. It cannot authorize an
        # increase or an exit until its newest row is the accepted paired
        # executable session carried by both native daily bars.
        session = int(self._bars[-1].close_time.timestamp() * 1_000_000_000)
        if (
            self._current_btc is None or self._current_sol is None
            or self._current_btc.ts_event != session or self._current_sol.ts_event != session
            or self._last_accepted_session != session
            or (self._latest_seen_session is not None and self._latest_seen_session != session)
        ):
            return None
        latest = len(self._bars) - 1
        if latest <= index:
            return False
        if self._current_signals[latest].side != episode.side:
            return True
        feature = self._current_signals[latest]
        bar = self._bars[latest]
        if episode.sol_qty and episode.sol_first_fill_at is not None and bar.close_time >= episode.sol_first_fill_at + timedelta(days=self._candidate.sol_max_holding_days):
            return True
        if not self._candidate.episode_fixed_beta:
            z = feature.z if episode.fixed_sigma is None else (
                (feature.relative - feature.mu) / episode.fixed_sigma
                if feature.relative is not None and feature.mu is not None else None
            )
        elif latest >= self._candidate.relative_days:
            prior = self._bars[latest - self._candidate.relative_days]
            relative = log(bar.sol_close / prior.sol_close) - episode.beta_entry * log(bar.btc_close / prior.btc_close)
            z = (relative - feature.mu) / feature.sigma if feature.mu is not None and feature.sigma not in (None, 0) else None
        else:
            z = None
        if z is None:
            return True
        signed_z = episode.side * z
        if episode.sol_qty and episode.sol_first_fill_at is not None and (
            (not episode.sol_half_done and signed_z <= self._candidate.sol_exit_half_z)
            or (episode.sol_half_done and episode.sol_half_decision_index is not None and latest > episode.sol_half_decision_index and signed_z <= self._candidate.sol_exit_all_z)
        ):
            return True
        level = intent.level
        return (
            level is None or level not in episode.sol_rights
            or feature.beta is None or not 0.2 < feature.beta < 4
            or signed_z < self._candidate.sol_entry_z[level]
            or (not self._candidate.sol_late_entry_after_tp and episode.sol_right_decision_index.get(level) != latest)
            or episode.h is None
            or episode.h * self._candidate.sol_size_multipliers_h[level] * episode.sol_right_fraction.get(level, 1.0)
               <= episode.sol_add_filled_notional.get(level, 0.0)
        )

    def _active_marked(self, btc_mark: VenueMark, sol_mark: VenueMark) -> float:
        account = self.cache.account_for_venue(self.config.btc_id.venue)
        instrument = self.cache.instrument(self.config.btc_id)
        if account is None or instrument is None:
            raise ValueError("NATIVE_ACCOUNT_OR_INSTRUMENT_MISSING")
        # Native account is the monetary source; this does not fabricate a UI
        # balance.  Full marked-equity reconciliation is still a baseline gate.
        marked = _native_account_money(account)
        mark_by_instrument = {self.config.btc_id: btc_mark.price, self.config.sol_id: sol_mark.price}
        for position in self.cache.positions_open():
            mark = mark_by_instrument.get(position.instrument_id)
            position_instrument = self.cache.instrument(position.instrument_id)
            if mark is not None and position_instrument is not None:
                marked += position.unrealized_pnl(position_instrument.make_price(mark)).as_decimal()
        return float(marked)

    def _research_sol_cap_quantity(self, requested: Decimal, executable: Decimal, ts_now: int) -> Decimal:
        """Entry-only bound from native money/exposure, reserving actual taker fee.

        Every retry uses current native exposure. Existing SOL is never resized.
        """
        multiple = self.config.research_sol_notional_cap_multiple
        if multiple is None:
            return requested
        instrument = self.cache.instrument(self.config.sol_id)
        audit = {"timestamp_ns": str(ts_now), "requested_quantity": str(requested)}
        self.sol_cap_admission_audit.append(audit)
        try:
            if instrument is None or executable <= 0:
                raise ValueError("INSTRUMENT_OR_EXECUTABLE_MISSING")
            if any(order.instrument_id == self.config.sol_id and not order.is_reduce_only for order in self.cache.orders_open()):
                raise ValueError("SOL_OPENING_ORDER_PENDING")
            if any(intent.action == "SOL_ADD" for intent in self._pending_by_order.values()):
                raise ValueError("SOL_SUBMISSION_PENDING")
            marks = {}
            for current_id in (self.config.btc_id, self.config.sol_id):
                mark = self._latest_marks.get(current_id)
                if mark is None or self.config.max_mark_age_ns <= 0 or not 0 <= ts_now - mark.ts_event <= self.config.max_mark_age_ns:
                    raise ValueError("FRESH_NATIVE_MARKS_MISSING")
                current_instrument = self.cache.instrument(current_id)
                if current_instrument is None:
                    raise ValueError("INSTRUMENT_MISSING")
                marks[current_id] = current_instrument.make_price(mark.price)
            account = self.cache.account_for_venue(self.config.btc_id.venue)
            if account is None:
                raise ValueError("NATIVE_ACCOUNT_MISSING")
            equity = _native_account_money(account)
            held = Decimal("0")
            for position in self.cache.positions_open():
                if position.instrument_id not in marks:
                    continue
                mark = marks[position.instrument_id]
                equity += position.unrealized_pnl(mark).as_decimal()
                if position.instrument_id == self.config.sol_id:
                    held += position.quantity.as_decimal() * mark.as_decimal()
            price = max(executable, marks[self.config.sol_id].as_decimal())
            fee = max(Decimal("0"), instrument.taker_fee)
            gap_loss = abs(executable - marks[self.config.sol_id].as_decimal())
            room = max(Decimal("0"), multiple * equity - held)
            step = instrument.size_increment.as_decimal()
            admitted = min(requested, (room / (price + multiple * (executable * fee + gap_loss)) // step) * step) if equity > 0 else Decimal("0")
            audit.update(native_equity=str(equity), held_sol_mark_notional=str(held), executable_price=str(executable), sol_mark=str(marks[self.config.sol_id]), cap_multiple=str(multiple), admitted_quantity=str(admitted), prospective_notional_upper=str(held + admitted * price), reserved_taker_fee=str(admitted * executable * fee), reserved_mark_execution_gap_loss=str(admitted * gap_loss))
            return admitted
        except ValueError as error:
            audit.update(admitted_quantity="0", reason=str(error))
            return Decimal("0")

    def _research_sol_hedge_quantity(self, requested: Decimal, executable: Decimal, ts_now: int) -> Decimal:
        """Clip only an already-earned budget to aggregate remaining native BTC/beta."""
        audit = {"timestamp_ns": str(ts_now), "requested_quantity": str(requested)}
        self.sol_hedge_admission_audit.append(audit)
        try:
            episode = self._domain.episode
            beta = Decimal(str(episode.beta_entry)) if episode is not None else Decimal("NaN")
            if not beta.is_finite() or not Decimal("0.2") < beta < Decimal("4"):
                raise ValueError("VALID_EPISODE_BETA_MISSING")
            if any(o.instrument_id == self.config.sol_id and not o.is_reduce_only for o in self.cache.orders_open()) or any(i.action == "SOL_ADD" for i in self._pending_by_order.values()):
                raise ValueError("SOL_OPENING_OWNERSHIP_PENDING")
            marks = {}
            for iid in (self.config.btc_id, self.config.sol_id):
                mark = self._latest_marks.get(iid)
                if mark is None or self.config.max_mark_age_ns <= 0 or not 0 <= ts_now - mark.ts_event <= self.config.max_mark_age_ns:
                    raise ValueError("FRESH_NATIVE_MARKS_MISSING")
                marks[iid] = self.cache.instrument(iid).make_price(mark.price).as_decimal()
            held = Decimal("0")
            btc = Decimal("0")
            for position in self.cache.positions_open():
                if position.instrument_id == self.config.sol_id:
                    held += position.quantity.as_decimal() * marks[self.config.sol_id]
                elif position.instrument_id == self.config.btc_id:
                    btc += position.quantity.as_decimal() * marks[self.config.btc_id]
            target = btc / Decimal(str(episode.beta_entry))
            room = max(Decimal("0"), target - held)
            instrument = self.cache.instrument(self.config.sol_id)
            step = instrument.size_increment.as_decimal()
            # Upper-bound mark and execution notional; existing admission below
            # retains its lot/minimum/fee/free-margin checks unchanged.
            price = max(executable, marks[self.config.sol_id])
            if price <= 0:
                raise ValueError("EXECUTABLE_PRICE_INVALID")
            admitted = min(requested, (room / price // step) * step)
            audit.update(beta_entry=str(episode.beta_entry), native_remaining_btc_notional=str(btc),
                         native_held_sol_notional=str(held), hedge_target_notional=str(target),
                         admitted_quantity=str(admitted), sol_mark=str(marks[self.config.sol_id]))
            return admitted
        except ValueError as error:
            audit.update(admitted_quantity="0", reason=str(error))
            return Decimal("0")

    def _free_margin_for_increase(self, account) -> Decimal:
        return _native_account_money(account, free=True)

    def _deny_local_entry(self, intent: Intent, reason: str, ts_now: int | None) -> None:
        if self._conditional_enabled():
            self._conditional_failed(intent, ts_now or self.clock.timestamp_ns())
        self._selected_entry_audits.pop(intent.id, None)
        if intent.reason and intent.reason.startswith("SOL_COVER") and self._cover_cycle:
            self._cover_cycle["incomplete"] = True
            self._cover_cycle["retry_after_ns"] = (ts_now or self.clock.timestamp_ns()) + 3_600_000_000_000
        self.pre_submit_gate_blocks.append({
            "timestamp": str(ts_now or 0),
            "intent_id": intent.id,
            "action": intent.action,
            "reason": reason,
        })
        if intent.action == "BTC_ENTRY" and self._split_parent and self._split_parent["episode_id"] == intent.episode_id:
            self._split_stop("LOCAL_DENIED:"+reason)
        self._daily_decision_reason = f"LOCAL_ENTRY_DENIED:{reason}"
        self._domain.on_parent_terminal(intent.id)

    def _submit_intent(self, intent: Intent, bid_price: float, ask_price: float, sigma: float | None, decision_index: int, only_instrument: InstrumentId | None = None, ts_now: int | None = None, entry_override_qty: Decimal | None = None) -> None:
        if self._carry_busy() and not self._carry_physical and intent.action != "CLOSE_ALL":
            self._domain.on_parent_terminal(intent.id)
            return
        if self.config.research_sol_risk_first=="split-atr" and intent.action=="SOL_ADD" and not self._rf_sol_child and any(p["intent"].id==intent.id for p in self._rf_sol_parents):
            return  # Accepted logical group identity is idempotent.
        if self.config.research_sol_risk_first=="split-atr" and intent.action in {"SOL_HALF_EXIT","SOL_EXIT"}:
            if self._risk_first_sol_stop(intent.reason or intent.action):
                self._rf_sol_waiting_exits.add(intent.id)
                if not any(q[0].id==intent.id for q in self._queued_intents):self._queued_intents.append((intent,sigma,decision_index))
                return
            if intent.id in self._rf_sol_waiting_exits:
                self._rf_sol_waiting_exits.discard(intent.id)
                if intent.action=="SOL_EXIT":
                    held=next((p.quantity.as_decimal() for p in self.cache.positions_open() if p.instrument_id==self.config.sol_id),Decimal(0))
                    intent=replace(intent,quantity=float(held),requested_notional=None)
                    if self._domain.episode is not None:self._domain.episode.pending[intent.id]=intent
        if self.config.deposit_runtime is not None and self._deposit.latched:
            self._domain.on_parent_terminal(intent.id)
            return
        if intent.action == "CLOSE_ALL":
            for position in self.cache.positions_open():
                if position.instrument_id not in (self.config.btc_id, self.config.sol_id):
                    continue
                if only_instrument is not None and position.instrument_id != only_instrument:
                    continue
                instrument = self.cache.instrument(position.instrument_id)
                if instrument is None:
                    continue
                side = OrderSide.SELL if position.is_long else OrderSide.BUY
                order = self.order_factory.market(instrument_id=position.instrument_id, order_side=side, quantity=instrument.make_qty(position.quantity.as_decimal()), time_in_force=TimeInForce.IOC, reduce_only=True)
                client_order_id = str(order.client_order_id)
                self._pending_by_order[client_order_id] = intent
                self._sigma_by_order[client_order_id] = sigma
                self._decision_index_by_order[client_order_id] = decision_index
                if not self._record_submission(order, intent.id, intent.episode_id, intent.action):
                    self._pending_by_order.pop(client_order_id, None)
                    self._sigma_by_order.pop(client_order_id, None)
                    self._decision_index_by_order.pop(client_order_id, None)
                    continue
                self.submit_order(order)
            return
        if intent.action == "SOL_ADD" and (self.config.research_sol_btc_open_only or self.config.research_h4_ema is not None) and self._hb_position(self.config.btc_id) is None:
            self._domain.on_parent_terminal(intent.id)
            return
        if not self._next_before_submit(intent, ts_now or self.clock.timestamp_ns()):
            return
        instrument_id = self.config.btc_id if intent.action.startswith("BTC") else self.config.sol_id
        instrument = self.cache.instrument(instrument_id)
        if instrument is None:
            if intent.action == "BTC_ENTRY":
                self._deny_local_entry(intent, "INSTRUMENT_MISSING", ts_now)
            return
        side = OrderSide.BUY if intent.side == 1 else OrderSide.SELL
        executable_price = Decimal(str(ask_price if side == OrderSide.BUY else bid_price))
        quantity = intent.quantity
        if (intent.action == "BTC_ENTRY" or intent.action == "SOL_ADD" and (self._rf_sol_child or self._carry_physical)) and entry_override_qty is not None:
            quantity = entry_override_qty
        elif intent.action == "BTC_ENTRY" and intent.requested_notional is not None:
            quantity = float(Decimal(str(intent.requested_notional)) / executable_price)
        if intent.action == "SOL_ADD" and intent.requested_notional is not None and not self._rf_sol_child:
            quantity = float(Decimal(str(min(intent.requested_notional, self._candidate.max_parent_notional))) / executable_price)
        if quantity is None or quantity <= 0:
            if intent.action == "BTC_ENTRY":
                self._deny_local_entry(intent, "QUANTITY_INVALID", ts_now)
            return
        reduce_only = intent.action in {"BTC_REDUCE", "SOL_HALF_EXIT", "SOL_EXIT"}
        if reduce_only:
            position = next((item for item in self.cache.positions_open() if item.instrument_id == instrument_id), None)
            if position is None:
                self._domain.on_parent_terminal(intent.id)
                return
            quantity = min(quantity, float(position.quantity))
        step = instrument.size_increment.as_decimal()
        rounded = (Decimal(str(quantity)) // step) * step
        if intent.action == "SOL_ADD" and self._v3_sol_block_episode is not None:
            episode = self._domain.episode
            if episode is None or episode.id == self._v3_sol_block_episode or any(p.instrument_id == self.config.sol_id for p in self.cache.positions_open()):
                self._domain.on_parent_terminal(intent.id)
                return
            self.v3_risk_audit.append({"event": "SOL_NEW_EPISODE_REARM", "timestamp_ns": str(ts_now), "old_episode_id": self._v3_sol_block_episode, "new_episode_id": episode.id})
            self._v3_sol_block_episode = None
            self._v3_sol_cycle = None
        if intent.action == "SOL_ADD" and self.config.research_sol_notional_cap_multiple is not None:
            rounded = self._research_sol_cap_quantity(rounded, executable_price, ts_now or 0)
        if intent.action == "SOL_ADD" and self.config.research_sol_remaining_btc_hedge:
            rounded = self._research_sol_hedge_quantity(rounded, executable_price, ts_now or 0)
        if self.config.research_v0_execution_repairs and self.config.research_v0_zero_tp_netting and intent.action == "BTC_ENTRY" and rounded > 0 and not self._split_child_submit:
            episode = self._domain.episode
            if episode is None or episode.wave_levels is None:
                raise ValueError("BTC_ENTRY_WAVE_LEVELS_MISSING")
            reference_lots = int(rounded / step)
            fractions = tuple(Decimal(str(value)) for value in self._candidate.btc_tp_fractions_initial_qty)
            reference_targets: dict[int, int] = {}
            assigned = 0
            for level, fraction in enumerate(fractions):
                lots = reference_lots - assigned if level == len(fractions) - 1 and sum(fractions) == Decimal("1") else int((Decimal(reference_lots) * fraction).to_integral_value(rounding=ROUND_FLOOR))
                reference_targets[level] = lots
                assigned += lots
            omitted = {level for level, threshold in enumerate(episode.wave_levels) if Decimal(str(threshold)) == 0}
            net_lots = sum(lots for level, lots in reference_targets.items() if level not in omitted)
            episode.btc_reference_qty = float(rounded)
            episode.btc_net_planned_qty = float(Decimal(net_lots) * step)
            episode.btc_reference_target_lots = reference_targets
            episode.btc_omitted_zero_levels = omitted
            rounded = Decimal(net_lots) * step
        if rounded <= 0:
            # A sub-step request is a reject, never an implicit size increase.
            if intent.action == "BTC_ENTRY":
                self._deny_local_entry(intent, "ZERO_TP_NO_NET_ENTRY" if self.config.research_v0_execution_repairs and self.config.research_v0_zero_tp_netting else "QUANTITY_BELOW_STEP", ts_now)
            else:
                self._domain.on_parent_terminal(intent.id)
            return
        if self.config.research_v0_selective_lifecycle_repairs and intent.action == "BTC_ENTRY" and not self._split_child_submit:
            cap = Decimal(str(self._candidate.max_parent_notional))
            rounded = min(rounded, (cap / executable_price // step) * step)
            episode = self._domain.episode
            if episode is not None:
                # Gross reference/H stays fixed; actual-fill rights use q1 net.
                episode.btc_net_planned_qty = float(rounded)
            audit = self._selected_entry_audits.get(intent.id)
            if audit is not None:
                audit["admitted_net_quantity"] = str(rounded)
                audit["parent_notional_cap"] = str(cap)
            if rounded <= 0:
                self._deny_local_entry(intent, "PARENT_CAP_BELOW_STEP", ts_now)
                return
        if self._conditional_enabled() and intent.action.startswith("SOL") and not self._conditional_physical:
            if intent.action=="SOL_ADD":
                rounded=self._risk_first_admit(rounded,ts_now or 0)
                episode=self._domain.episode
                legal=episode is not None and intent.level in episode.sol_rights and intent.id in episode.pending
                if legal:
                    authorized=episode.h*self._candidate.sol_size_multipliers_h[intent.level]*episode.sol_right_fraction.get(intent.level,1.0)-episode.sol_add_filled_notional.get(intent.level,0)-episode.sol_ownership_transfer_credit.get(intent.level,0)-episode.sol_risk_retired_notional.get(intent.level,0)
                    legal=rounded*executable_price<=Decimal(str(authorized))+instrument.size_increment.as_decimal()*executable_price
                minimum=(instrument.min_quantity is None or rounded>=instrument.min_quantity.as_decimal()) and (instrument.min_notional is None or rounded*executable_price>=instrument.min_notional.as_decimal())
                increment=self._conditional_original_increment(rounded)
                if not legal or not minimum or not self._alpha_admit(rounded,executable_price,ts_now or 0) or not self._entries_enabled() or not self._tier_allows_increase(instrument_id,side,increment,ts_now or 0):
                    self._deny_local_entry(intent,"ORIGINAL_CONDITIONAL_ADMISSION_DENIED",ts_now)
                    return
            self._conditional_original(intent,rounded,executable_price,sigma,decision_index,ts_now or 0)
            return
        # Increases are gated at the last safe point, after executable-price
        # sizing/normalization and immediately before native order creation.
        # Reductions deliberately bypass both the pause/stale and margin gates.
        if not reduce_only:
            now = ts_now if ts_now is not None else self._current_btc.ts_event if self._current_btc else 0
            min_quantity = instrument.min_quantity.as_decimal() if instrument.min_quantity is not None else None
            min_notional = instrument.min_notional.as_decimal() if instrument.min_notional is not None else None
            meets_minimum = (min_quantity is None or rounded >= min_quantity) and (min_notional is None or rounded * executable_price >= min_notional)
            if not meets_minimum or not self._entries_enabled() or not self._tier_allows_increase(instrument_id, side, rounded, now):
                self.log.warning(f"Rejecting {intent.action}: pre-submit increase gate or minimum failed")
                self._deny_local_entry(intent, "PRE_SUBMIT_INCREASE_GATE_OR_MINIMUM", now)
                return
        if intent.action == "SOL_ADD":
            rounded = self._risk_first_sol_prepare(intent,rounded,step,ts_now or 0,sigma,decision_index)
        if intent.action == "BTC_ENTRY":
            rounded = self._split_prepare(intent, rounded, step, ts_now or 0, sigma, decision_index)
        # Control A makes every planned SOL exit a native taker IOC.  Resting
        # post-only liquidity remains only for explicit BTC TP targets.
        passive_reduction = intent.action == "BTC_REDUCE" and intent.limit_price is not None
        if passive_reduction and self._split_tp_ioc_eligible(intent):
            quote_tick = self.cache.quote_tick(instrument_id)
            target = _native_limit_price(instrument, Decimal(str(intent.limit_price))).as_decimal()
            crossed = quote_tick is not None and (target >= quote_tick.ask_price.as_decimal() if side == OrderSide.BUY else target <= quote_tick.bid_price.as_decimal())
            if crossed:
                # Same intent/level/target leaves, real IOC money and taker fees.
                intent = replace(intent, limit_price=None)
                self._domain.episode.pending[intent.id] = intent
                passive_reduction = False
                self._split_parent.setdefault("positive_tp_ioc_catchups", []).append({
                    "timestamp_ns":ts_now,"level":intent.level,"quantity":str(rounded),
                    "target_price":str(target),"executable_price":str(executable_price)})
        split_limit = self._split_limit(intent, instrument, rounded) if intent.action == "BTC_ENTRY" else self._risk_first_sol_limit(intent,instrument,rounded) if intent.action=="SOL_ADD" else None
        if split_limit is not None:
            order = split_limit
        elif passive_reduction:
            raw_price = Decimal(str(intent.limit_price)) if intent.limit_price is not None else executable_price
            # For a planned SOL z exit, quote at the passive side.  A target
            # BTC price is supplied by the confirmed-entry plan above.
            if intent.limit_price is None:
                quote_tick = self.cache.quote_tick(instrument_id)
                if quote_tick is None:
                    self._domain.on_parent_cancelled(intent.id)
                    return
                raw_price = quote_tick.ask_price.as_decimal() if side == OrderSide.SELL else quote_tick.bid_price.as_decimal()
            limit_price = _native_limit_price(instrument, raw_price)
            if self.config.tp_fee_floor_v1:
                episode = self._domain.episode
                if episode is None:
                    raise ValueError("BTC_TP_EPISODE_MISSING")
                floor = _fee_floor_price(instrument, episode, maker=True)
                if (episode.side == 1 and limit_price.as_decimal() < floor.as_decimal()) or (episode.side == -1 and limit_price.as_decimal() > floor.as_decimal()):
                    limit_price = floor
            quote_tick = self.cache.quote_tick(instrument_id)
            if quote_tick is not None:
                # Check the exact wire-equivalent native price.  A five-sig
                # rounding step may otherwise turn a passive quote marketable.
                canonical = limit_price.as_decimal()
                if (side == OrderSide.BUY and canonical >= quote_tick.ask_price.as_decimal()) or (side == OrderSide.SELL and canonical <= quote_tick.bid_price.as_decimal()):
                    self._domain.on_parent_cancelled(intent.id)
                    return
            order = self.order_factory.limit(
                instrument_id=instrument_id, order_side=side, quantity=instrument.make_qty(rounded),
                price=limit_price, time_in_force=TimeInForce.GTC,
                post_only=True, reduce_only=True,
            )
        elif intent.action == "BTC_REDUCE" and self.config.tp_fee_floor_v1:
            episode = self._domain.episode
            if episode is None:
                raise ValueError("BTC_TP_EPISODE_MISSING")
            floor = _fee_floor_price(instrument, episode, maker=False)
            quote_tick = self.cache.quote_tick(instrument_id)
            executable = None if quote_tick is None else (quote_tick.bid_price.as_decimal() if side == OrderSide.SELL else quote_tick.ask_price.as_decimal())
            if executable is None or (side == OrderSide.SELL and executable < floor.as_decimal()) or (side == OrderSide.BUY and executable > floor.as_decimal()):
                self._domain.on_parent_cancelled(intent.id)
                return
            order = self.order_factory.limit(
                instrument_id=instrument_id, order_side=side, quantity=instrument.make_qty(rounded),
                price=floor, time_in_force=TimeInForce.IOC, post_only=False, reduce_only=True,
            )
        else:
            order = self.order_factory.market(instrument_id=instrument_id, order_side=side, quantity=instrument.make_qty(rounded), time_in_force=TimeInForce.IOC, reduce_only=reduce_only)
        client_order_id = str(order.client_order_id)
        self._risk_first_sol_bind(intent,order)
        self._pending_by_order[client_order_id] = intent
        # A pre-submit durable checkpoint must see the exact order-to-episode
        # mapping before native transport can accept or fill this order.
        self._sigma_by_order[client_order_id] = sigma
        self._decision_index_by_order[client_order_id] = decision_index
        if not self._record_submission(order, intent.id, intent.episode_id, intent.action, intent.reason, intent.level):
            if self.config.research_sol_risk_first=="split-atr":self._risk_first_sol_terminal(client_order_id,ts_now or 0,"LOCAL_UNSENT_PREP_DENIED")
            self._pending_by_order.pop(client_order_id, None)
            self._sigma_by_order.pop(client_order_id, None)
            self._decision_index_by_order.pop(client_order_id, None)
            if intent.action == "BTC_ENTRY":
                self._deny_local_entry(intent, "DURABLE_SUBMIT_PREP_REJECTED", ts_now)
            else:
                self._domain.on_parent_terminal(intent.id)
            return
        self._own_accepted_reduction(intent, rounded)
        if intent.action == "BTC_ENTRY":
            self._daily_decision_reason = "NATIVE_SUBMISSION_PENDING_ACK"
            if intent.id in self._selected_entry_audits:
                self.entry_sizing_audit.append(self._selected_entry_audits.pop(intent.id))
            elif self.config.research_v0_execution_repairs and self.config.research_v0_zero_tp_netting:
                episode = self._domain.episode
                assert episode is not None
                self.entry_sizing_audit.append({
                    "episode_id": episode.id,
                    "intent_id": intent.id,
                    "reference_btc_qty": str(episode.btc_reference_qty),
                    "net_submitted_btc_qty": str(rounded),
                    "confirmed_native_entry_qty": "0",
                    "omitted_zero_levels": sorted(episode.btc_omitted_zero_levels),
                    "reference_target_lots": dict(episode.btc_reference_target_lots),
                })
        self._c1_bind_submission(intent,client_order_id,ts_now or self.clock.timestamp_ns())
        self.submit_order(order)

    @staticmethod
    def _reduction_key(intent: Intent) -> tuple[str, str, int | None]:
        return intent.episode_id, intent.action, intent.level

    def _has_owned_sol_exit(self) -> bool:
        return any(key[1] in {"SOL_HALF_EXIT", "SOL_EXIT"} for key in self._accepted_reductions)

    def _own_accepted_reduction(self, intent: Intent, quantity: Decimal) -> None:
        if not self.config.research_v0_selective_lifecycle_repairs:
            return
        episode = self._domain.episode
        ordinary_sol = intent.reason in {"SOL_Z_HALF_EXIT", "SOL_Z_FULL_EXIT"}
        zero_fallback = (episode is not None and intent.action == "BTC_REDUCE" and intent.limit_price is None and intent.level in episode.btc_zero_resting_suppressed)
        positive_tp_fallback = self._split_tp_ioc_eligible(intent) and intent.limit_price is None
        if ordinary_sol or zero_fallback or positive_tp_fallback:
            self._accepted_reductions.setdefault(self._reduction_key(intent), (intent, quantity))

    def _requeue_accepted_reduction(self, intent: Intent, sigma: float | None, index: int, ts_event: int) -> None:
        if self._carry_busy():
            return
        key = self._reduction_key(intent)
        owner = self._accepted_reductions.get(key)
        if owner is None:
            return
        if self._forced_close_reason is not None or self._liquidating or self._mandatory_sol_exit is not None or (self.config.deposit_runtime is not None and self._deposit.latched):
            self._accepted_reductions.pop(key, None)
            return
        episode = self._domain.episode
        if episode is None or episode.id != intent.episode_id or owner[1] <= 0:
            self._accepted_reductions.pop(key, None)
            return
        # Unknown ACK and queued children retain exclusive ownership.
        if any(self._reduction_key(item) == key for item in self._pending_by_order.values()) or any(self._reduction_key(item) == key for item, _, _ in self._queued_intents):
            return
        instrument_id = self.config.btc_id if intent.action == "BTC_REDUCE" else self.config.sol_id
        position = next((item for item in self.cache.positions_open() if item.instrument_id == instrument_id), None)
        if position is None:
            self._accepted_reductions.pop(key, None)
            return
        leaves = min(owner[1], position.quantity.as_decimal())
        child = self._domain._intent(episode, intent.action, intent.side, intent.level, quantity=float(leaves), reason=intent.reason)
        self._queued_intents.append((child, sigma, index))
        self._queued_intent_ready_ns[child.id] = ts_event + 60_000_000_000

    def _discard_queued_intents(self, predicate) -> None:
        """Terminally remove queued work that a mandatory exit supersedes."""
        retained: list[tuple[Intent, float | None, int]] = []
        for queued in self._queued_intents:
            intent, _, _ = queued
            if predicate(intent):
                self._queued_intent_ready_ns.pop(intent.id, None)
                self._deferred_selective_entries.pop(intent.id, None)
                self._selected_entry_audits.pop(intent.id, None)
                self._domain.on_parent_terminal(intent.id)
            else:
                retained.append(queued)
        self._queued_intents = retained

    def _preempt_with_mandatory_sol_exit(self, intent: Intent, sigma: float | None, index: int) -> None:
        """Cancel SOL leaves before a timeout reduces the reconciled remainder."""
        if self._conditional_enabled():
            self._conditional_cancel_original_adds(self.clock.timestamp_ns())
        if self.config.deposit_runtime is not None and self._deposit.latched:
            self._domain.on_parent_terminal(intent.id)
            return
        if self._mandatory_sol_exit is not None:
            # The first timeout remains authoritative while cancellation and
            # the next executable SOL quote are pending. A later daily
            # decision creates a new domain intent, so terminally remove that
            # duplicate rather than overwriting the original and orphaning it.
            self._domain.on_parent_terminal(intent.id)
            return
        self._accepted_reductions = {key: owner for key, owner in self._accepted_reductions.items() if not key[1].startswith("SOL")}
        self._discard_queued_intents(lambda queued: queued.action.startswith("SOL") and queued.id != intent.id)
        for order in list(self.cache.orders_open()):
            if order.instrument_id == self.config.sol_id:
                self.cancel_order(order)
        self._mandatory_sol_exit = (intent, sigma, index)

    def _rearm_mandatory_sol_exit(self, ts_event: int) -> None:
        if self._mandatory_sol_exit is not None or self._forced_close_reason is not None or self._liquidating or (self.config.deposit_runtime is not None and self._deposit.latched):
            return
        episode = self._domain.episode
        position = next((item for item in self.cache.positions_open() if item.instrument_id == self.config.sol_id), None)
        if episode is None or position is None or position.quantity.as_decimal() <= 0:
            return
        intent = self._domain._intent(episode, "SOL_EXIT", episode.side, None, quantity=float(position.quantity), reason="SOL_HARD_TIMEOUT")
        self._mandatory_sol_exit = (intent, episode.fixed_sigma, len(self._bars) - 1)
        self._mandatory_sol_retry_after_ns = ts_event + 60_000_000_000

    def _ordinary_forced_close_active(self) -> bool:
        return (self._forced_close_reason not in {None, "LIQUIDATION", "TERMINAL_BOUNDARY_SETTLEMENT"}
                and not (self.config.deposit_runtime is not None and self._deposit.latched))

    def _begin_forced_close(self, reason: str, intent: Intent | None = None) -> None:
        if self.config.research_residual_recovery:self._c1_revoke(self.clock.timestamp_ns(),"MANDATORY_GROUP_CLOSE")
        self._risk_first_sol_stop(reason)
        self._split_stop(reason)
        if self.config.deposit_runtime is not None and self._deposit.latched:
            return
        """Cancel every resting order before closing actual cache leaves taker."""
        # Terminal settlement is the final authority: it may supersede an
        # earlier liquidation-close attempt whose native leaves remain open.
        # A liquidation likewise supersedes a prior ordinary regime/trail
        # close; only an already-active liquidation remains idempotent.
        supersedes = reason == "TERMINAL_BOUNDARY_SETTLEMENT" or (
            reason == "LIQUIDATION" and self._forced_close_reason not in {None, "LIQUIDATION"}
        )
        if self._forced_close_reason is not None and not supersedes:
            return
        # A forced group close owns both instruments. A queued timeout has no
        # authority to wait for a SOL quote ahead of liquidation, regime,
        # trail, or terminal settlement. Clear its domain marker before the
        # cancellation callbacks race with a native fill; the forced path
        # always reads actual cache leaves for its reduce-only quantity.
        if self._mandatory_sol_exit is not None:
            timeout, _, _ = self._mandatory_sol_exit
            self._mandatory_sol_exit = None
            self._domain.on_parent_terminal(timeout.id)
        self._v3_reduction = None
        self._accepted_reductions.clear()
        self._discard_queued_intents(lambda _queued: True)
        self._forced_close_reason = reason
        self._forced_close_intent = intent
        self._forced_close_submitted.clear()
        for order in list(self.cache.orders_open()):
            self.cancel_order(order)

    def _submit_forced_close_on_quote(self, tick: QuoteTick) -> None:
        # Cancel confirmation/reconciliation is authoritative: no market close
        # is submitted while a resting reduction can still consume leaves.
        if self.cache.orders_open() or (self._carry_busy() and self.cache.orders_inflight()) or ((self.config.research_v3_risk or self._carry_busy()) and self._pending_by_order):
            return
        if self._forced_close_reason == "RESEARCH_V3_T3" and tick.ts_event < self._v3_trail_trigger_ns:
            return
        position = next((item for item in self.cache.positions_open() if item.instrument_id == tick.instrument_id), None)
        if position is None or tick.instrument_id in self._forced_close_submitted:
            if not self.cache.positions_open() and self._forced_close_intent is not None:
                self._domain.on_parent_terminal(self._forced_close_intent.id)
                self._group_close_reconciliation_pending = True
                self._reconcile_group_flat()
            return
        instrument = self.cache.instrument(tick.instrument_id)
        if instrument is None:
            return
        order = self.order_factory.market(
            instrument_id=tick.instrument_id, order_side=OrderSide.SELL if position.is_long else OrderSide.BUY,
            quantity=instrument.make_qty(position.quantity.as_decimal()), time_in_force=TimeInForce.IOC, reduce_only=True,
        )
        forced_action = "TERMINAL_CLOSE" if self._forced_close_reason == "TERMINAL_BOUNDARY_SETTLEMENT" else "LIQUIDATION_CLOSE" if self._forced_close_reason == "LIQUIDATION" else "FORCED_CLOSE"
        if not self._record_submission(order, f"{self._forced_close_reason}:{order.client_order_id}", "forced", forced_action, self._forced_close_reason, None):
            return
        if self._forced_close_reason == "RESEARCH_V3_T3":
            self.v3_risk_audit.append({"event": "PROTECTIVE_SUBMIT", "reason": "T3", "order_id": str(order.client_order_id), "instrument_id": str(tick.instrument_id), "timestamp_ns": str(tick.ts_event), "trigger_ns": str(self._v3_trail_trigger_ns), "latency_ns": str(tick.ts_event-self._v3_trail_trigger_ns), "quote_ns": str(tick.ts_event), "executable_quote": str(tick.bid_price if position.is_long else tick.ask_price), "quantity": str(order.quantity)})
        self._forced_close_submitted.add(tick.instrument_id)
        self._forced_close_orders.add(str(order.client_order_id))
        if self._forced_close_reason == "TERMINAL_BOUNDARY_SETTLEMENT":
            self._terminal_order_ids.add(str(order.client_order_id))
            self.terminal_lifecycle["status"] = "CLOSE_SUBMITTED"
        elif self._forced_close_reason == "LIQUIDATION":
            self._liquidation_orders.add(str(order.client_order_id))
        self.submit_order(order)

    def _submit_forced_closes_from_cache(self) -> None:
        """Continue a forced close after the final native cancel confirmation."""
        if self.config.deposit_runtime is not None and self._deposit.latched:
            return
        if self.cache.orders_open() or (self._carry_busy() and (self.cache.orders_inflight() or self._pending_by_order)):
            return
        if self.config.research_v3_risk == "t3" and self._forced_close_reason == "RESEARCH_V3_T3":
            return
        for position in list(self.cache.positions_open()):
            if position.instrument_id not in (self.config.btc_id, self.config.sol_id) or position.instrument_id in self._forced_close_submitted:
                continue
            # A market order remains native taker; this read only verifies a
            # current native book exists to match it against.
            if self.cache.quote_tick(position.instrument_id) is None:
                continue
            instrument = self.cache.instrument(position.instrument_id)
            if instrument is None:
                continue
            order = self.order_factory.market(
                instrument_id=position.instrument_id,
                order_side=OrderSide.SELL if position.is_long else OrderSide.BUY,
                quantity=instrument.make_qty(position.quantity.as_decimal()),
                time_in_force=TimeInForce.IOC, reduce_only=True,
            )
            forced_action = "TERMINAL_CLOSE" if self._forced_close_reason == "TERMINAL_BOUNDARY_SETTLEMENT" else "LIQUIDATION_CLOSE" if self._forced_close_reason == "LIQUIDATION" else "FORCED_CLOSE"
            if not self._record_submission(order, f"{self._forced_close_reason}:{order.client_order_id}", "forced", forced_action, self._forced_close_reason, None):
                continue
            self._forced_close_submitted.add(position.instrument_id)
            self._forced_close_orders.add(str(order.client_order_id))
            if self._forced_close_reason == "TERMINAL_BOUNDARY_SETTLEMENT":
                self._terminal_order_ids.add(str(order.client_order_id))
                self.terminal_lifecycle["status"] = "CLOSE_SUBMITTED"
            elif self._forced_close_reason == "LIQUIDATION":
                self._liquidation_orders.add(str(order.client_order_id))
            self.submit_order(order)

    def _submit_terminal_closes(self) -> None:
        self._risk_first_sol_stop("TERMINAL")
        self._split_stop("TERMINAL")
        """Realize all remaining native positions on the terminal quote only."""
        trigger_ts = self._current_btc.ts_event if self._current_btc is not None else None
        self.terminal_lifecycle = {
            "reason": "TERMINAL_BOUNDARY_SETTLEMENT",
            "status": "NO_OPEN_POSITION",
            "trigger_ts": str(trigger_ts) if trigger_ts is not None else None,
            "close_fills": [],
            "lockout": True,
        }
        if self.config.research_v0_selective_lifecycle_repairs:
            self._accepted_reductions.clear()
            submitted = {item.id for item in self._pending_by_order.values()}
            self._discard_queued_intents(lambda queued: queued.id not in submitted)
            if self.cache.orders_open() or self._pending_by_order:
                self.terminal_lifecycle["status"] = "AWAITING_NATIVE_TERMINAL"
                self._begin_forced_close("TERMINAL_BOUNDARY_SETTLEMENT")
                return
        if not any(position.instrument_id in (self.config.btc_id, self.config.sol_id) for position in self.cache.positions_open()):
            self.terminal_lifecycle["status"] = "FLAT"
            return
        self._begin_forced_close("TERMINAL_BOUNDARY_SETTLEMENT")

    def _tier_allows_increase(self, instrument_id: InstrumentId, side: OrderSide, quantity: Decimal, ts_now: int) -> bool:
        if self.config.deposit_runtime is not None and not self._deposit_check():
            return False
        """Fail closed on missing/stale public marks; reductions bypass this gate."""
        if self.config.margin_policy is None:
            return False
        try:
            policy = self.config.margin_policy
            positions = {item.instrument_id: item for item in self.cache.positions_open()}
            required = Decimal("0")
            gross = Decimal("0")
            current_required: dict[InstrumentId, Decimal] = {}
            marks = {}
            for current_id in (self.config.btc_id, self.config.sol_id):
                position = positions.get(current_id)
                current = (
                    position.quantity.as_decimal() if position is not None and position.is_long
                    else -position.quantity.as_decimal() if position is not None
                    else Decimal("0")
                )
                prospective = current + (quantity if side == OrderSide.BUY else -quantity) if current_id == instrument_id else current
                if self.config.research_btc_split50 or self.config.research_sol_cover:
                    prospective = self._split_cover_margin_reserve(current_id, prospective, ts_now)
                if prospective:
                    initial, maintenance, mark = policy.margin_for(current_id, prospective, ts_now)
                    required += initial + maintenance if self.config.research_v0_selective_lifecycle_repairs else initial
                    gross += abs(prospective) * mark
                    marks[current_id] = mark
                if self.config.research_v0_selective_lifecycle_repairs and current:
                    initial, maintenance, mark = policy.margin_for(current_id, current, ts_now)
                    current_required[current_id] = initial + maintenance
                    marks[current_id] = mark
            account = self.cache.account_for_venue(self.config.btc_id.venue)
            instrument = self.cache.instrument(self.config.btc_id)
            if self.config.research_v0_selective_lifecycle_repairs:
                if account is None:
                    return False
                active = _native_account_money(account)
                for current_id, position in positions.items():
                    if current_id not in marks:
                        continue
                    current_instrument = self.cache.instrument(current_id)
                    if current_instrument is None:
                        return False
                    active += position.unrealized_pnl(current_instrument.make_price(marks[current_id])).as_decimal()
                # Only actual native reservations can offset fresh policy
                # requirements. CustomData may update policy before native
                # locks reprice, so current policy cost is never itself credit.
                opening_ids = {
                    order.instrument_id for order in self.cache.orders_open()
                    if not getattr(order, "is_reduce_only", False)
                }
                reserved_credit = Decimal("0")
                for current_id, policy_current in current_required.items():
                    native_reserved = Decimal("0")
                    for accessor in ("margin_maint", "margin_init"):
                        # Opening/unknown order IM stays reserved. Confirmed
                        # reduce-only targets cannot increase native exposure.
                        if accessor == "margin_init" and current_id in opening_ids:
                            continue
                        value = getattr(account, accessor)(current_id)
                        if value is not None:
                            if value.currency != instrument.quote_currency:
                                raise ValueError("NATIVE_MARGIN_CURRENCY_MISMATCH")
                            native_reserved += value.as_decimal()
                    reserved_credit += min(policy_current, native_reserved)
                required = max(Decimal("0"), required - reserved_credit)
            else:
                active = Decimal(str(self._active_marked(self._current_btc_mark, self._current_sol_mark))) if self._current_btc_mark and self._current_sol_mark else Decimal("0")
            return account is not None and instrument is not None and active > 0 and gross <= active * self.config.max_gross_to_active and required <= self._free_margin_for_increase(account)
        except ValueError:
            return False

    def _update_margin_mark(self, instrument_id: InstrumentId, price: Decimal, ts_event: int) -> None:
        """Offer each causal public mark to an injected venue policy."""
        policy = self.config.margin_policy
        update = getattr(policy, "update_mark", None) if policy is not None else None
        if callable(update):
            update(MarginMark(instrument_id, price, ts_event))

    def on_order_filled(self, event: OrderFilled) -> None:
        trade_id = str(event.trade_id)
        if trade_id in self._seen_trade_ids:
            return
        # The audit event may have committed just before a crash; it is not
        # an atomic receipt that the domain fill was applied.
        self._c1_native_fill(event)
        self._record_native_fill(event)
        self._seen_trade_ids.add(trade_id)
        if self.config.research_sol_risk_first=="alpha-corridor-v1":
            self._rf_dirty=True
            self._rf_fill_epoch+=1
            self._rf_last_fill_ns=event.ts_event
        self._record_fill_audit(event)
        self._carry_native_fill(event)
        if str(event.client_order_id) in self._v3_orders:
            self._v3_reduction_fill(event)
            return
        if str(event.client_order_id) in self._deposit_exit_orders:
            order = self.cache.order(event.client_order_id)
            if order is not None and order.is_closed:
                self._terminal_submission(str(event.client_order_id))
            self._reconcile_deposit_flat()
            return
        if str(event.client_order_id) in self._liquidation_orders:
            if self.liquidation_audit:
                audit = self.liquidation_audit[-1]
                fills = audit["close_fills"]
                assert isinstance(fills, list)
                fills.append({"instrument_id": str(event.instrument_id), "timestamp": str(event.ts_event), "value": str(event.last_qty.as_decimal() * event.last_px.as_decimal())})
                audit["close_value"] = str(sum((Decimal(item["value"]) for item in fills), Decimal("0")))
            order = self.cache.order(event.client_order_id)
            if order is not None and order.is_closed:
                self._terminal_submission(str(event.client_order_id))
            self._reconcile_liquidation_flat()
            return
        if str(event.client_order_id) in self._terminal_order_ids:
            fills = self.terminal_lifecycle["close_fills"]
            assert isinstance(fills, list)
            fills.append({"instrument_id": str(event.instrument_id), "timestamp": str(event.ts_event), "value": str(event.last_qty.as_decimal() * event.last_px.as_decimal())})
            order = self.cache.order(event.client_order_id)
            if order is not None and order.is_closed:
                self._terminal_submission(str(event.client_order_id))
            self._reconcile_terminal_flat()
            return
        if str(event.client_order_id) in self._forced_close_orders:
            if self._forced_close_reason == "RESEARCH_V3_T3":
                trigger = next(r for r in reversed(self.v3_risk_audit) if r["event"] == "T3_TRIGGER")
                audit = {"event": "PROTECTIVE_FILL", "reason": "T3", "instrument_id": str(event.instrument_id), "order_id": str(event.client_order_id), "timestamp_ns": str(event.ts_event), "trigger_ns": str(self._v3_trail_trigger_ns), "latency_ns": str(event.ts_event-self._v3_trail_trigger_ns), "price": str(event.last_px), "quantity": str(event.last_qty), "commission": str(event.commission), "pre_action_equity": trigger["native_equity"]}
                self.v3_risk_audit.append(audit)
                self._v3_fill_checkpoints.append(audit)
            order = self.cache.order(event.client_order_id)
            if order is not None and order.is_closed:
                self._terminal_submission(str(event.client_order_id))
                if self._forced_close_intent is not None:
                    self._domain.on_parent_terminal(self._forced_close_intent.id)
                self._group_close_reconciliation_pending = True
                self._reconcile_group_flat()
            return
        intent = self._pending_by_order.get(str(event.client_order_id))
        if intent is None:
            return
        order = self.cache.order(event.client_order_id)
        closed = order is not None and order.is_closed
        entry_fee = None
        if intent.action == "BTC_ENTRY" and (self.config.tp_fee_floor_v1 or self.config.research_zero_retrace):
            instrument = self.cache.instrument(event.instrument_id)
            if instrument is None or event.commission is None or event.commission.currency != instrument.quote_currency:
                raise ValueError("BTC_TP_ENTRY_FEE_CURRENCY_UNSUPPORTED")
            entry_fee = event.commission.as_decimal()
        self._h1_native_fill(intent, event)
        self._risk_first_sol_fill(intent,event)
        self._split_native_fill(intent, event)
        self._cover_native_fill(intent, event)
        self._apply_confirmed_domain_fill(
            intent, str(event.client_order_id), float(event.last_qty), float(event.last_px),
            event.ts_event, closed, entry_fee=entry_fee,
            entry_qty=event.last_qty.as_decimal() if intent.action == "BTC_ENTRY" else None,
            entry_price=event.last_px.as_decimal() if intent.action == "BTC_ENTRY" else None,
        )
        self._after_domain_fill(event)
        if closed:
            self._terminal_submission(str(event.client_order_id))
            if self._forced_close_reason is not None:
                self._group_close_reconciliation_pending = True
                return  # Existing forced executor owns actual late-fill leaves.
            if intent.action == "CLOSE_ALL":
                self._group_close_reconciliation_pending = True
                self._reconcile_group_flat()
                return
            # An entry fills at the next executable event, not at the former
            # signal close; only reduction -> add -> exit phases may continue.
            if intent.action != "BTC_ENTRY":
                if self.config.research_v0_execution_repairs and intent.action == "SOL_EXIT" and intent.reason == "SOL_HARD_TIMEOUT":
                    self._rearm_mandatory_sol_exit(event.ts_event)
                self._advance_current_day()
            elif self.config.research_v0_execution_repairs and self._domain.episode is not None and self._domain.episode.btc_omitted_zero_levels:
                self._advance_current_day()

    def _apply_confirmed_domain_fill(
        self, intent: Intent, client_order_id: str, quantity: float,
        price: float, ts_event: int, order_closed: bool,
        entry_fee: Decimal | None = None,
        entry_qty: Decimal | None = None, entry_price: Decimal | None = None,
    ) -> None:
        """Pure episode/intent transition shared by callbacks and report replay."""
        self._bind_native_lots()
        sigma = self._sigma_by_order.get(client_order_id)
        key = self._reduction_key(intent)
        if key in self._accepted_reductions:
            original, leaves = self._accepted_reductions[key]
            remaining = max(Decimal("0"), leaves - Decimal(str(quantity)))
            if remaining == 0:
                self._accepted_reductions.pop(key)
            else:
                self._accepted_reductions[key] = original, remaining
        when = datetime.fromtimestamp(ts_event / 1_000_000_000, UTC)
        if self._c1_fill(intent,quantity,price,ts_event):
            pass
        elif self._next_risk_fill(intent,quantity,ts_event):
            pass
        elif intent.reason == "CHOP_PAIR_SINGLE_GRANT" and self._carry_busy():
            pass  # Native inventory only; original alpha history/basis is retained.
        elif self._conditional_enabled() and intent.reason in {"CONDITIONAL_NET_ADD","CONDITIONAL_NET_EXIT"}:
            self._conditional_fill(intent,quantity,price,ts_event)
        elif self.config.research_h4_ema is not None and intent.action.startswith("SOL"):
            self._hedge_sol_fill(intent, quantity, ts_event)
        else:
            self._domain.on_fill(
                intent.id, quantity, price, when, sigma,
                decision_index=self._confirmed_fill_cycle(intent, client_order_id), entry_fee=entry_fee,
                entry_qty=entry_qty, entry_price=entry_price,
            )
        if intent.action == "BTC_ENTRY":
            self._hb_wait_regime = False
            self._next_release=None
            self._next_count=0
        if intent.action == "BTC_REDUCE":
            self._hedge_btc_flat(intent, ts_event)
        if intent.action.startswith("BTC"):
            self._hedge_refresh(ts_event)
        self._insurance_btc_fill(intent,price,ts_event)
        self._alpha_btc_fill(intent,ts_event)
        if intent.action == "BTC_ENTRY" and self.config.research_btc_split_planref_v1:
            ep = self._domain.episode
            p = self._split_parent
            if ep is not None and p is not None and ep.id == p["episode_id"]:
                p["planref_v1_p0"] = ep.btc_planref_vwap
                p["planref_v1_actual_blended_vwap"] = ep.btc_entry_notional_exact / ep.btc_entry_qty_exact
                p["planref_v1_h_actual"] = ep.h
                p["planref_v1_gross_reference_qty"] = ep.btc_reference_qty or ep.btc_initial_qty
                p["planref_v1_beta"] = ep.beta_entry
        if intent.action == "BTC_ENTRY" and self.config.research_v0_execution_repairs and self.entry_sizing_audit:
            episode = self._domain.episode
            if episode is not None:
                self.entry_sizing_audit[-1]["confirmed_native_entry_qty"] = str(episode.btc_initial_qty)
        if intent.action == "SOL_HALF_EXIT" and self._domain.episode is not None and self._domain.episode.sol_half_done:
            self._domain.on_half_exit_decision(max(self._decision_index_by_order.get(client_order_id, intent.decision_index), len(self._bars) - 1))
        if not order_closed:
            return
        self._hedge_terminal(intent, ts_event, "FILLED_TERMINAL")
        if self._conditional_enabled():
            self._conditional_attempt_terminal(intent,ts_event,"NATIVE_TERMINAL_AFTER_FILL",client_order_id)
        self._next_terminal(intent,ts_event)
        self._domain.on_parent_terminal(intent.id)
        self._pending_by_order.pop(client_order_id, None)
        self._sigma_by_order.pop(client_order_id, None)
        self._decision_index_by_order.pop(client_order_id, None)
        if self.config.research_sol_risk_first=="split-atr":self._risk_first_sol_terminal(client_order_id,ts_event,"FILL_TERMINAL")
        self._requeue_accepted_reduction(intent, sigma, intent.decision_index, ts_event)
        if intent.action == "BTC_ENTRY":
            self._queue_confirmed_btc_targets(sigma, intent.decision_index, ts_event)

    def _bind_native_lots(self) -> None:
        cache = getattr(self, "cache", None)
        instrument = getattr(cache, "instrument", None)
        if not callable(instrument):
            return
        btc, sol = instrument(self.config.btc_id), instrument(self.config.sol_id)
        if btc is not None and sol is not None:
            self._domain.set_execution_lots(
                btc=btc.size_increment.as_decimal(), sol=sol.size_increment.as_decimal(),
            )

    def _queue_confirmed_btc_targets(self, sigma: float | None, decision_index: int, ready_ns: int) -> None:
        """Queue every remaining confirmed-entry target for the next quote."""
        if self._forced_close_reason is not None or self._split_unfinished() or self._carry_busy():
            return
        if self.config.deposit_runtime is not None and self._deposit.latched:
            return
        self._bind_native_lots()
        for target in self._domain.plan_confirmed_btc_targets():
            self._queued_intents.append((target, sigma, decision_index))
            self._queued_intent_ready_ns[target.id] = ready_ns + 1

    def _has_confirmed_btc_remainder(self, intent: Intent) -> bool:
        """Return whether a canceled BTC parent had a confirmed unsold remainder."""
        episode = self._domain.episode
        if episode is None or self._carry_busy() or self._forced_close_reason is not None or self._liquidating or (self.config.deposit_runtime is not None and self._deposit.latched):
            return False
        if intent.action == "BTC_ENTRY":
            return episode.btc_initial_qty > 0 and episode.btc_open_qty > 0
        return (
            intent.action == "BTC_REDUCE"
            and intent.level is not None
            and intent.level not in episode.btc_filled_tps
            and episode.btc_tp_filled_qty.get(intent.level, 0.0) > 0
        )

    def _after_domain_fill(self, event: OrderFilled) -> None:
        """Optional durable domain checkpoint, before any follow-on decision."""

    def on_order_canceled(self, event: OrderCanceled) -> None:
        self._terminal_submission(str(event.client_order_id))
        client_order_id = str(event.client_order_id)
        if client_order_id in self._v3_orders:
            self._v3_reduction_terminal(client_order_id, event.ts_event)
            return
        if client_order_id in self._forced_close_orders:
            order = self.cache.order(event.client_order_id)
            if order is not None:
                self._forced_close_submitted.discard(order.instrument_id)
            self._forced_close_orders.discard(client_order_id)
        intent = self._pending_by_order.pop(str(event.client_order_id), None)
        self._next_terminal(intent,event.ts_event)
        self._hedge_terminal(intent, event.ts_event, "CANCELED")
        if self._conditional_enabled():
            self._conditional_attempt_terminal(intent,event.ts_event,"CANCELED",str(event.client_order_id))
        if intent is not None and intent.action == "BTC_ENTRY":
            self._daily_decision_reason = (
                "PARTIAL_ENTRY_RETAINED" if self._domain.episode is not None and self._domain.episode.btc_initial_qty > 0
                else "NATIVE_ENTRY_ZERO_FILL_CANCELED"
            )
        sigma = self._sigma_by_order.pop(str(event.client_order_id), None)
        decision_index = self._decision_index_by_order.pop(str(event.client_order_id), 0)
        if intent is not None:
            self._domain.on_parent_cancelled(intent.id)
            if self._has_confirmed_btc_remainder(intent):
                # IOC entry and TP parents can cancel after a real partial
                # fill. Re-plan from confirmed domain leaves; the next quote
                # still sizes every reduction against the native position.
                self._queue_confirmed_btc_targets(sigma, decision_index, event.ts_event)
                if self.config.research_v0_execution_repairs and intent.action == "BTC_ENTRY" and self._domain.episode is not None and self._domain.episode.btc_omitted_zero_levels:
                    self._advance_current_day()
        if intent is not None:
            self._requeue_accepted_reduction(intent, sigma, decision_index, event.ts_event)
        if self.config.research_sol_risk_first=="split-atr":self._risk_first_sol_terminal(client_order_id,event.ts_event,"CANCELED")
        self._reconcile_terminal_flat()
        if intent is not None and self.config.research_v0_execution_repairs and intent.action == "SOL_EXIT" and intent.reason == "SOL_HARD_TIMEOUT":
            self._rearm_mandatory_sol_exit(event.ts_event)
        if self._forced_close_reason is not None and not self.cache.orders_open():
            self._submit_forced_closes_from_cache()
        if self._ordinary_forced_close_active() or self._research_protect_latch is not None:
            self._group_close_reconciliation_pending = True
            self._reconcile_group_flat()

    def on_order_event(self, event) -> None:
        # Event identity, not client order identity, preserves the sequence
        # Submitted -> Accepted -> terminal without manufacturing an ACK.
        event_id = getattr(event, "id", None)
        if event_id is None:
            event_id = f"{event.client_order_id}:{type(event).__name__}:{getattr(event, 'ts_event', getattr(event, 'ts_init', ''))}"
        self._record_native_event(str(event_id), "order")
        if isinstance(event, OrderAccepted):
            self._accept_native_order(event)

    def on_order_accepted(self, event: OrderAccepted) -> None:
        self._accept_native_order(event)

    def _accept_native_order(self, event: OrderAccepted) -> None:
        context = self._order_audit.get(str(event.client_order_id))
        if context is not None and context.get("accept_ns") is None:
            context["accept_ns"] = str(event.ts_event)
        self._acknowledge_submission(str(event.client_order_id))
        if self.config.research_sol_risk_first=="split-atr":
            owned=self._rf_sol_orders.get(str(event.client_order_id))
            if owned and owned[0]["stopped"]:
                order=self.cache.order(event.client_order_id)
                if order is not None and not order.is_closed:self.cancel_order(order)
        if self._v3_reduction is not None:
            order = self.cache.order(event.client_order_id)
            if order is not None and order.instrument_id == self._v3_reduction["instrument_id"] and str(event.client_order_id) not in self._v3_orders and not order.is_closed:
                self.cancel_order(order)
        if self._forced_close_reason is not None or self._research_protect_latch is not None:
            order = self.cache.order(event.client_order_id)
            if order is not None and not order.is_closed and not order.is_reduce_only and order.instrument_id in (self.config.btc_id, self.config.sol_id):
                self.cancel_order(order)


    def on_order_denied(self, event: OrderDenied) -> None:
        self._terminal_without_fill(str(event.client_order_id))

    def on_position_event(self, event) -> None:
        self._hedge_refresh(event.ts_event)
        self._insurance_position(event)
        self._record_native_event(f"{event.position_id}:{event.ts_init}", "position")
        self._research_capture_btc_episode(event)
        self._v3_capture_sol_cycle(event)
        if self._ordinary_forced_close_active():
            self._submit_forced_closes_from_cache()
        self._reconcile_group_flat()
        self._reconcile_liquidation_flat()
        self._reconcile_terminal_flat()
        self._reconcile_deposit_flat()
        if self._research_protect_latch is not None and self.cache.positions_open() and self._forced_close_reason is None:
            self._begin_forced_close("RESEARCH_PORTFOLIO_45")

    def _reconcile_group_flat(self) -> None:
        """Clear a completed close group after the native cache is actually flat."""
        if not self._group_close_reconciliation_pending or self.cache.positions_open() or self.cache.orders_open():
            return
        if self._pending_by_order or (self._carry_busy() and self.cache.orders_inflight()) or ((self.config.research_sol_btc_open_only or self.config.research_h4_ema is not None) and (self._queued_intents or self.cache.orders_inflight())):
            return  # An opening order awaiting terminal native receipt may still fill.
        if self.config.research_residual_recovery and (self.cache.orders_inflight() or self._queued_intents):return
        self._group_close_reconciliation_pending = False
        if self._c1_state is not None:
            self._c1_log("GROUP_FLAT_RESET", self.clock.timestamp_ns(), credit_expired=self._c1_state["credit"])
            self._c1_state = None
        if self._insurance_enabled() and self._insurance_cycle:
            self._insurance_cycle.update(closed=True,target=Decimal(0))
        self._carry_flat()
        reason = self._domain.on_group_flat()
        if self._forced_close_reason not in {"LIQUIDATION", "TERMINAL_BOUNDARY_SETTLEMENT"}:
            self._forced_close_reason = None
            self._forced_close_intent = None
            self._forced_close_orders.clear()
        if reason == "REGIME":
            if self.config.research_regime_reentry_band is not None:
                self._hb_wait_regime = True
                self._next_latch_ns=self.clock.timestamp_ns()
                self._next_daily_ns=None
                self._next_count=0
                self._next_daily()
                self._hb_log("WAIT_REGIME_REENTRY", self.clock.timestamp_ns())
            self._advance_current_day()

    def _reconcile_liquidation_flat(self) -> None:
        if not self._liquidating or self.cache.positions_open() or self.cache.orders_open():
            return
        if self.liquidation_audit and self.liquidation_audit[-1]["status"] == "FLAT_LOCKED":
            return
        self._domain.on_liquidation()
        if self.liquidation_audit:
            self.liquidation_audit[-1]["status"] = "FLAT_LOCKED"

    def _reconcile_terminal_flat(self) -> None:
        if self.terminal_lifecycle["status"] not in {"CLOSE_SUBMITTED", "AWAITING_NATIVE_TERMINAL"} or self.cache.positions_open() or self.cache.orders_open():
            return
        if self.config.research_v0_selective_lifecycle_repairs and self._pending_by_order:
            return
        self.terminal_lifecycle["status"] = "FLAT"
        self._c1_terminal_flat(self.clock.timestamp_ns())

    def reporting_state(self) -> dict[str, object]:
        """Authoritative native adapter state for diagnostic-only exports."""
        self._reconcile_liquidation_flat()
        self._reconcile_terminal_flat()
        if self.terminal_lifecycle["status"]=="FLAT":self._c1_terminal_flat(self.clock.timestamp_ns())
        return {
            "hedge_band_audit": self.hedge_band_audit,
            "liquidations": self.liquidation_audit,
            "liquidation_lockout": self._liquidating,
            "terminal_lifecycle": self.terminal_lifecycle,
            "terminal_open_orders": len(self.cache.orders_open()),
            "pre_submit_tier_margin_gate_blocks": self.pre_submit_gate_blocks,
            "marked_equity_checkpoints": [self.marked_equity_checkpoints[key] for key in sorted(self.marked_equity_checkpoints)],
            "fill_audit": self.fill_audit,
            "entry_sizing_audit": self.entry_sizing_audit,
        }

    def on_order_rejected(self, event: OrderRejected) -> None:
        self._terminal_without_fill(str(event.client_order_id))

    def on_order_expired(self, event: OrderExpired) -> None:
        self._terminal_without_fill(str(event.client_order_id))

    def _terminal_without_fill(self, client_order_id: str) -> None:
        forced_close_terminal = client_order_id in self._forced_close_orders
        failed_intent = self._pending_by_order.get(client_order_id)
        self._c1_terminal(failed_intent,self.clock.timestamp_ns())
        self._hedge_terminal(failed_intent, self.clock.timestamp_ns(), "DENIED_REJECTED_EXPIRED")
        if self._conditional_enabled():
            self._conditional_failed(failed_intent,self.clock.timestamp_ns(),client_order_id)
        if failed_intent and failed_intent.reason and failed_intent.reason.startswith("SOL_COVER") and self._cover_cycle:
            self._cover_cycle["incomplete"] = True
            self._cover_cycle["retry_after_ns"] = self.clock.timestamp_ns() + 3_600_000_000_000
        if failed_intent and failed_intent.action == "BTC_ENTRY" and self._split_parent and self._split_parent["episode_id"] == failed_intent.episode_id:
            self._split_stop("NATIVE_DENIED_OR_REJECTED_OR_EXPIRED")
        self._terminal_submission(client_order_id)
        if client_order_id in self._v3_orders:
            self._v3_reduction_terminal(client_order_id, self.clock.timestamp_ns())
            return
        if client_order_id in self._deposit_exit_orders and self._deposit.exit_state == "EXITING":
            self._deposit.exit_state = "EXIT_INCOMPLETE"
            now_ns = self.clock.timestamp_ns()
            self._persist_deposit("EXIT_INCOMPLETE", f"deposit:exit-terminal:{client_order_id}:{now_ns}", now_ns)
        if client_order_id in self._forced_close_orders:
            order = self.cache.order(ClientOrderId(client_order_id))
            if order is not None:
                self._forced_close_submitted.discard(order.instrument_id)
            self._forced_close_orders.discard(client_order_id)
        intent = self._pending_by_order.pop(client_order_id, None)
        if intent is not None and intent.action == "BTC_ENTRY":
            self._daily_decision_reason = (
                "PARTIAL_ENTRY_RETAINED" if self._domain.episode is not None and self._domain.episode.btc_initial_qty > 0
                else "NATIVE_ENTRY_ZERO_FILL_TERMINAL"
            )
        sigma = self._sigma_by_order.pop(client_order_id, None)
        decision_index = self._decision_index_by_order.pop(client_order_id, 0)
        if intent is not None:
            self._domain.on_parent_terminal(intent.id)
            if self._has_confirmed_btc_remainder(intent):
                self._queue_confirmed_btc_targets(sigma, decision_index, 0)
                if self.config.research_v0_execution_repairs and intent.action == "BTC_ENTRY" and self._domain.episode is not None and self._domain.episode.btc_omitted_zero_levels:
                    self._advance_current_day()
        if intent is not None and self._reduction_key(intent) in self._accepted_reductions:
            self._requeue_accepted_reduction(intent, sigma, decision_index, self.clock.timestamp_ns())
        if self.config.research_sol_risk_first=="split-atr":self._risk_first_sol_terminal(client_order_id,self.clock.timestamp_ns(),"DENIED_REJECTED_EXPIRED")
        self._reconcile_terminal_flat()
        if intent is not None and self.config.research_v0_execution_repairs and intent.action == "SOL_EXIT" and intent.reason == "SOL_HARD_TIMEOUT":
            self._rearm_mandatory_sol_exit(self.clock.timestamp_ns())
        # A synchronous native denial must not resubmit into the same throttle.
        # Known terminal leaves remain eligible for the existing fresh-quote path.
        if not forced_close_terminal and self._forced_close_reason is not None and not self.cache.orders_open():
            self._submit_forced_closes_from_cache()
        if self._ordinary_forced_close_active() or self._research_protect_latch is not None:
            self._group_close_reconciliation_pending = True
            self._reconcile_group_flat()

    def _on_deposit_timer(self, _event) -> None:
        # Callback delivery can precede the final native cache update.
        self._reconcile_deposit_flat()
        self._deposit_check()

    def _deposit_equity(self) -> Decimal | None:
        reader = self.config.deposit_equity_reader
        if not callable(reader):
            return None
        try:
            value = reader(self)
            return value if isinstance(value, Decimal) and value.is_finite() else None
        except Exception:
            return None

    def _persist_deposit(self, action: str, key: str, now_ns: int) -> None:
        try:
            self.config.deposit_runtime.save_deposit_protection(
                instance_id=self.config.deposit_instance_id,
                account_id=self.config.deposit_account_id,
                action=action, event_key=key, state=self._deposit.durable(), ts_ns=now_ns,
            )
        except Exception:
            self._deposit_storage_failed = True
            self.log.error("Deposit protection persistence failed; increases blocked")

    def _deposit_check(self) -> bool:
        if self.config.deposit_runtime is None:
            return True
        now_ns = self.clock.timestamp_ns()
        current = self._deposit_equity()
        if self._deposit.high_water is None:
            allowed = self.config.deposit_initialization_allowed
            if (
                current is not None and current > 0 and callable(allowed) and allowed()
                and not self.cache.positions_open() and not self.cache.orders_open()
                and not self.cache.orders_inflight()
            ):
                self._deposit.initialize(current, now_ns)
                self._persist_deposit("INITIALIZE", f"deposit:init:{now_ns}", now_ns)
            return self._deposit.high_water is not None and not self._deposit_storage_failed
        high_water_allowed=self.config.deposit_high_water_allowed
        changed,tripped=self._deposit.observe(current,now_ns,allow_high_water=(bool(high_water_allowed()) if callable(high_water_allowed) else True))
        if changed:
            action = "TRIGGER" if tripped else "UTC_BOUNDARY"
            key = f"deposit:{action.lower()}:{now_ns if tripped else self._deposit.last_boundary_ns}"
            self._persist_deposit(action, key, now_ns)
        if tripped:
            self._start_deposit_exit(now_ns)
        return (
            current is not None and not self._deposit.latched
            and not self._deposit.daily_sample_missed
            and not self._deposit_storage_failed
        )

    def _start_deposit_exit(self, now_ns: int) -> None:
        self._split_stop("DP")
        self._v3_reduction = None
        self._accepted_reductions.clear()
        self._discard_queued_intents(lambda _queued: True)
        if self._mandatory_sol_exit is not None:
            intent, _, _ = self._mandatory_sol_exit
            self._mandatory_sol_exit = None
            self._domain.on_parent_terminal(intent.id)
        if self._deposit_exit_started:
            return
        self._deposit_exit_started = True
        if self._forced_close_reason is not None or self._liquidating or self.is_exiting():
            self._deposit.exit_state = "EXIT_INCOMPLETE"
            self._persist_deposit("EXIT_INCOMPLETE", f"deposit:competing:{now_ns}", now_ns)
            return
        try:
            self.market_exit()
        except Exception:
            self._deposit.exit_state = "EXIT_INCOMPLETE"
            self._persist_deposit("EXIT_INCOMPLETE", f"deposit:market-exit-error:{now_ns}", now_ns)
            self.log.error("Native market exit failed; deposit latch retained")

    def submit_order(self, order, *args, **kwargs):
        if self.config.deposit_runtime is not None and self._deposit.latched and "MARKET_EXIT" not in (order.tags or ()):
            self.log.warning("Deposit market exit owns closure; other orders blocked")
            return None
        if self.config.deposit_runtime is not None and not order.is_reduce_only and not self._deposit_check():
            self.log.warning("Deposit protection blocks native increase submission")
            return None
        if self.config.deposit_runtime is not None and "MARKET_EXIT" in (order.tags or ()):
            if (
                not self._deposit.latched or not order.is_reduce_only
                or order.time_in_force != TimeInForce.IOC
                or order.instrument_id not in (self.config.btc_id, self.config.sol_id)
            ):
                raise RuntimeError("DEPOSIT_NATIVE_EXIT_ORDER_INVALID")
            oid = str(order.client_order_id)
            if not self._record_submission(order, f"deposit:{oid}", "deposit-protection", "MARKET_EXIT", "DEPOSIT_DRAWDOWN_LIMIT"):
                self._deposit.exit_state = "EXIT_INCOMPLETE"
                return
            self._deposit_exit_orders.add(oid)
        return super().submit_order(order, *args, **kwargs)

    def _reconcile_deposit_flat(self) -> bool:
        """Finish only after native cache and durable submit state confirm flat."""
        if (
            self.config.deposit_runtime is None
            or not self._deposit.latched
            or not self._deposit_exit_started
            or self._deposit.exit_state != "EXITING"
            or self.cache.positions_open()
            or self.cache.orders_open()
            or self.cache.orders_inflight()
            or self.config.deposit_runtime.pending_submissions()
        ):
            return False
        self._deposit.exit_state = "TRIPPED_FLAT"
        self._domain.episode = None
        self._pending_by_order.clear()
        now_ns = self.clock.timestamp_ns()
        self._persist_deposit("TRIPPED_FLAT", f"deposit:exit:{now_ns}", now_ns)
        return True

    def post_market_exit(self) -> None:
        if self.config.deposit_runtime is None or not self._deposit.latched:
            return
        if self._reconcile_deposit_flat():
            return
        # Nautilus may finalize its own exit while a submitted order is still
        # invisible in the cache. Only a zero-submit attempt is a known failure.
        if self._deposit.exit_state == "EXITING" and not self._deposit_exit_orders:
            self._deposit.exit_state = "EXIT_INCOMPLETE"
            now_ns = self.clock.timestamp_ns()
            self._persist_deposit("EXIT_INCOMPLETE", f"deposit:exit-no-submit:{now_ns}", now_ns)

    def deposit_projection(self) -> dict[str, object]:
        result = self._deposit.projection()
        if self._deposit_storage_failed:
            result["state"] = "NOT_INITIALIZED/RECOVERY_REQUIRED"
        return result

    def apply_deposit_control(
        self, command: str, key: str, *, drawdown_limit_percent: int | None = None,
        confirm: bool = False,
    ) -> dict[str, object]:
        if self.config.deposit_runtime is None or not key:
            raise ValueError("DEPOSIT_CONTROL_UNAVAILABLE")
        runtime = self.config.deposit_runtime
        if (
            runtime.entry_control_state() != "PAUSED"
            or runtime.recovery_state() != "FLAT_RESTART"
            or not runtime.coherent_snapshot()
            or runtime.projection_snapshot() != ([], [])
            or not runtime.reconcile(positions=[], orders=[])
            or self.cache.positions_open()
            or self.cache.orders_open()
            or self.cache.orders_inflight()
            or runtime.pending_submissions() or runtime.pending_native_funding()
            or self._queued_intents or self._mandatory_sol_exit is not None
            or self._pending_by_order or self._domain.episode is not None
            or self._forced_close_reason is not None or self._liquidating
            or self._group_close_reconciliation_pending or self.is_exiting()
            or (self._deposit.latched and self._deposit.exit_state != "TRIPPED_FLAT")
        ):
            raise ValueError("DEPOSIT_CONTROL_REQUIRES_PAUSED_CONFIRMED_FLAT")
        if command == "set-deposit-protection":
            action = f"{command}:{percent(drawdown_limit_percent)}"
        elif command == "reset-deposit-protection" and confirm is True:
            action = command
        else:
            raise ValueError("DEPOSIT_CONTROL_INVALID")
        event_key = f"deposit:control:{key}"
        prior = runtime.deposit_audit_action(event_key)
        if prior is not None:
            if prior != action:
                raise ValueError("DEPOSIT_IDEMPOTENCY_CONFLICT")
            return self.deposit_projection()
        now_ns = self.clock.timestamp_ns()
        current = self._deposit_equity()
        if current is None or current <= 0:
            raise ValueError("DEPOSIT_CONTROL_EQUITY_UNKNOWN")
        if command == "set-deposit-protection":
            self._deposit.limit_percent = percent(drawdown_limit_percent)
        else:
            self._deposit.reset(current, now_ns)
            self._deposit_exit_started = False
        self._persist_deposit(action, event_key, now_ns)
        if self._deposit_storage_failed:
            raise RuntimeError("DEPOSIT_CONTROL_PERSISTENCE_FAILED")
        return self.deposit_projection()

    def _entries_enabled(self, *, ignore_research_protection: bool = False) -> bool:
        if self._research_protect_latch is not None and not ignore_research_protection:
            return False
        if self.config.research_v0_selective_lifecycle_repairs and self.terminal_lifecycle.get("lockout"):
            return False
        if self.config.deposit_runtime is not None and not self._deposit_check():
            return False
        gate = self.config.entries_gate
        return self.config.entries_enabled and (bool(gate()) if callable(gate) else True)

    def _confirmed_fill_cycle(self, intent: Intent, client_order_id: str) -> int:
        """Map a confirmed TP fill to the current causal decision cycle.

        A BTC target may rest across daily decisions. Strict H3 rights must
        use the cycle in which Nautilus confirms that fill, not its old target
        creation/submission index. Other intents retain their own decision
        context for audit and exit ordering.
        """
        if intent.action == "BTC_REDUCE":
            return max(0, len(self._bars) - 1)
        return self._decision_index_by_order.get(client_order_id, max(0, len(self._bars) - 1))

    def _record_native_fill(self, event: OrderFilled) -> None:
        sink = self.config.native_fill_sink
        if not callable(sink):
            self._record_native_event(str(event.trade_id), "fill")
            return
        optional = lambda value: None if value is None else str(value)
        sink(
            trade_id=str(event.trade_id), native_event_id=optional(getattr(event, "id", None)),
            client_order_id=optional(getattr(event, "client_order_id", None)),
            venue_order_id=optional(getattr(event, "venue_order_id", None)),
            instrument_id=str(event.instrument_id),
            order_side=optional(getattr(getattr(event, "order_side", None), "name", None)),
            quantity=str(event.last_qty.as_decimal()), price=str(event.last_px.as_decimal()),
            commission_amount=str(event.commission.as_decimal()) if event.commission is not None else None,
            commission_currency=str(event.commission.currency) if event.commission is not None else None,
            liquidity_side=optional(getattr(getattr(event, "liquidity_side", None), "name", None)),
            ts_event_ns=getattr(event, "ts_event", None), ts_init_ns=getattr(event, "ts_init", None),
        )

    def _record_native_event(self, event_id: str, kind: str) -> bool | None:
        sink = self.config.event_sink
        return sink(event_id, kind) if callable(sink) else None

    def _record_submission(self, order, intent_id: str, episode_id: str, action: str, reason: str | None = None, level: int | None = None) -> bool:
        self._order_audit[str(order.client_order_id)] = {
            "venue": str(order.instrument_id.venue), "instrument": str(order.instrument_id),
            "action": action, "reason": reason or action, "level": "" if level is None else str(level),
            "order_type": str(order.order_type), "post_only": str(bool(order.is_post_only)).lower(),
            "submit_ns": str(order.ts_init), "accept_ns": None,
        }
        sink = self.config.submission_sink
        if not callable(sink):
            return True
        return bool(sink(
            client_order_id=str(order.client_order_id), intent_id=intent_id, episode_id=episode_id,
            action=action, instrument_id=str(order.instrument_id), quantity=str(order.quantity), reduce_only=bool(order.is_reduce_only),
            order_kind=getattr(order.order_type, "name", str(order.order_type)),
            time_in_force=getattr(order.time_in_force, "name", str(order.time_in_force)),
            order_side=getattr(order.side, "name", str(order.side)),
            post_only=bool(order.is_post_only),
            price=str(order.price) if order.has_price else None,
        ))

    def _record_fill_audit(self, event: OrderFilled) -> None:
        """Preserve native fill facts; classification is never inferred."""
        context = self._order_audit.get(str(event.client_order_id), {})
        liquidity = getattr(event.liquidity_side, "name", str(event.liquidity_side))
        commission = event.commission.as_decimal()
        self.fill_audit.append({
            "venue": str(context.get("venue", event.instrument_id.venue)),
            "instrument": str(event.instrument_id),
            "action": str(context.get("action", "UNKNOWN")),
            "reason": str(context.get("reason", "UNKNOWN")),
            "level": str(context.get("level", "")),
            "order_type": str(event.order_type),
            "post_only": str(context.get("post_only", "false")),
            "submit_ns": str(context.get("submit_ns", event.ts_init)),
            "accept_ns": str(context.get("accept_ns") or event.ts_init),
            "fill_ns": str(event.ts_event),
            "qty": str(event.last_qty.as_decimal()),
            "px": str(event.last_px.as_decimal()),
            "native_liquidity_side": str(liquidity),
            "notional": str(event.last_qty.as_decimal() * event.last_px.as_decimal()),
            "commission": str(commission),
            "commission_currency": str(event.commission.currency),
            "policy_hash": self.config.execution_policy_hash,
        })

    def _acknowledge_submission(self, client_order_id: str) -> None:
        sink = self.config.submission_sink
        if callable(sink):
            acknowledge = getattr(sink, "acknowledge", None)
            if callable(acknowledge):
                acknowledge(client_order_id)

    def _terminal_submission(self, client_order_id: str) -> None:
        sink = self.config.submission_sink
        if callable(sink):
            terminal = getattr(sink, "terminal", None)
            if callable(terminal):
                terminal(client_order_id)
