"""Causal BTC/SOL wave-overlay signals and fill-driven episode state.

This module deliberately has no Nautilus, venue, account, or execution imports.
It emits intents only; an adapter submits them and calls ``on_fill`` plus
``on_parent_cancelled`` from confirmed native events.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import exp, log, sqrt
from typing import Literal
from collections import deque
from uuid import uuid4


UTC = timezone.utc
Side = Literal[1, -1]
Action = Literal["BTC_ENTRY", "BTC_REDUCE", "SOL_ADD", "SOL_HALF_EXIT", "SOL_EXIT", "CLOSE_ALL"]


@dataclass(frozen=True)
class DailyBar:
    open_time: datetime
    close_time: datetime
    available_at: datetime
    btc_open: float
    btc_close: float
    sol_close: float

    def __post_init__(self) -> None:
        if self.open_time.tzinfo != UTC or self.close_time.tzinfo != UTC or self.available_at.tzinfo != UTC:
            raise ValueError("all bar times must be UTC")
        if self.available_at < self.close_time:
            raise ValueError("a bar cannot be available before it closes")
        if min(self.btc_open, self.btc_close, self.sol_close) <= 0:
            raise ValueError("prices must be positive")


@dataclass(frozen=True)
class Candidate:
    ema_period: int = 21
    beta_days: int = 270
    relative_days: int = 65
    z_history_days: int = 180
    wave_history_days: int = 730
    wave_min_count: int = 8
    wave_quantiles: tuple[float, float, float] = (0.10, 0.30, 0.60)
    btc_tp_fractions_initial_qty: tuple[float, float, float] = (0.15, 0.25, 0.35)
    btc_notional_multiplier: float = 9.0
    max_parent_notional: float = 10_000_000.0
    sol_size_multipliers_h: tuple[float, float, float] = (1.0, 1.5, 2.0)
    sol_entry_z: tuple[float, float, float] = (1.25, 2.50, 3.75)
    sol_exit_half_z: float = 0.375
    sol_exit_all_z: float = 0.125
    sol_max_holding_days: int = 14
    btc_close_trail_fraction: float = 0.03


@dataclass(frozen=True)
class Features:
    index: int
    side: Side
    beta: float | None
    relative: float | None
    mu: float | None
    sigma: float | None
    z: float | None


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _population_std(values: list[float]) -> float:
    mean = _mean(values)
    return sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def linear_quantile(values: list[float], q: float) -> float:
    """The spec's linear interpolation, including valid zero MFE values."""
    if not values or not 0 <= q <= 1:
        raise ValueError("quantile requires values and q in [0, 1]")
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def batch_features_for(bars: list[DailyBar], config: Candidate) -> list[Features]:
    """Compute only values available at each close; no future row is inspected."""
    if any(bars[index].close_time >= bars[index + 1].close_time for index in range(len(bars) - 1)):
        raise ValueError("bars must be strictly chronological")
    ema: list[float] = []
    returns_b: list[float | None] = []
    returns_s: list[float | None] = []
    relatives: list[float | None] = []
    result: list[Features] = []
    alpha = 2 / (config.ema_period + 1)
    for index, bar in enumerate(bars):
        ema.append(bar.btc_close if not ema else alpha * bar.btc_close + (1 - alpha) * ema[-1])
        side: Side = 1 if bar.btc_close > ema[-1] else -1
        returns_b.append(None if index == 0 else log(bar.btc_close / bars[index - 1].btc_close))
        returns_s.append(None if index == 0 else log(bar.sol_close / bars[index - 1].sol_close))
        beta: float | None = None
        if index >= config.beta_days:
            paired = [(returns_s[i], returns_b[i]) for i in range(index - config.beta_days + 1, index + 1)]
            if all(left is not None and right is not None for left, right in paired):
                sol_returns = [left for left, _ in paired if left is not None]
                btc_returns = [right for _, right in paired if right is not None]
                mean_s, mean_b = _mean(sol_returns), _mean(btc_returns)
                variance = _mean([(value - mean_b) ** 2 for value in btc_returns])
                if variance:
                    beta = _mean([(sol - mean_s) * (btc - mean_b) for sol, btc in zip(sol_returns, btc_returns)]) / variance
        relative: float | None = None
        if beta is not None and index >= config.relative_days:
            relative = log(bar.sol_close / bars[index - config.relative_days].sol_close) - beta * log(bar.btc_close / bars[index - config.relative_days].btc_close)
        relatives.append(relative)
        history = relatives[max(0, index - config.z_history_days):index]
        mu = _mean(history) if len(history) == config.z_history_days and all(value is not None for value in history) else None
        sigma = _population_std(history) if mu is not None else None
        z = None if relative is None or sigma in (None, 0) else (relative - mu) / sigma
        result.append(Features(index, side, beta, relative, mu, sigma, z))
    return result


class FeatureState:
    """Incremental causal feature calculator; batch_features_for is its oracle."""
    def __init__(self, config: Candidate) -> None:
        self.config, self.bars, self.ema = config, [], None
        self.rs: deque[tuple[float, float]] = deque(maxlen=config.beta_days)
        self.relatives: deque[float | None] = deque(maxlen=config.z_history_days)

    def append(self, bar: DailyBar) -> Features:
        if self.bars and bar.close_time <= self.bars[-1].close_time:
            raise ValueError("bars must be strictly chronological")
        alpha = 2 / (self.config.ema_period + 1)
        self.ema = bar.btc_close if self.ema is None else alpha * bar.btc_close + (1 - alpha) * self.ema
        side: Side = 1 if bar.btc_close > self.ema else -1
        beta = relative = mu = sigma = z = None
        if self.bars:
            self.rs.append((log(bar.sol_close / self.bars[-1].sol_close), log(bar.btc_close / self.bars[-1].btc_close)))
        if len(self.rs) == self.config.beta_days:
            sol_returns, btc_returns = [x for x, _ in self.rs], [y for _, y in self.rs]
            mean_s, mean_b = _mean(sol_returns), _mean(btc_returns)
            variance = _mean([(value - mean_b) ** 2 for value in btc_returns])
            beta = _mean([(sol - mean_s) * (btc - mean_b) for sol, btc in zip(sol_returns, btc_returns)]) / variance if variance else None
        if beta is not None and len(self.bars) >= self.config.relative_days:
            old = self.bars[-self.config.relative_days]
            relative = log(bar.sol_close / old.sol_close) - beta * log(bar.btc_close / old.btc_close)
        if len(self.relatives) == self.config.z_history_days and all(value is not None for value in self.relatives):
            values = [value for value in self.relatives if value is not None]
            mu, sigma = _mean(values), _population_std(values)
            z = None if relative is None or sigma == 0 else (relative - mu) / sigma
        self.relatives.append(relative)
        self.bars.append(bar)
        return Features(len(self.bars) - 1, side, beta, relative, mu, sigma, z)


def features_for(bars: list[DailyBar], config: Candidate) -> list[Features]:
    state = FeatureState(config)
    return [state.append(bar) for bar in bars]


def completed_wave_levels(bars: list[DailyBar], features: list[Features], at_index: int, config: Candidate, side: Side) -> tuple[float, float, float] | None:
    """Use only waves finished strictly before this decision's bar."""
    mfes: list[float] = []
    start = 0
    while start < at_index:
        wave_side = features[start].side
        end = start + 1
        while end < at_index and features[end].side == wave_side:
            end += 1
        # A run is completed only because an observed opposite-side signal follows it.
        # The dataset's first regime has no observed preceding switch, so it is
        # not a completed statistical wave.
        if start > 0 and end < at_index and wave_side == side and start + 1 < len(bars):
            entry = bars[start + 1].btc_open
            closes = [bars[i].btc_close for i in range(start + 1, end + 1)]
            signed = [wave_side * (close / entry - 1) for close in closes]
            if bars[end].close_time >= bars[at_index].close_time - timedelta(days=config.wave_history_days):
                mfes.append(max(0.0, max(signed)))
        start = end
    if len(mfes) < config.wave_min_count:
        return None
    return tuple(linear_quantile(mfes, quantile) for quantile in config.wave_quantiles)  # type: ignore[return-value]


@dataclass(frozen=True)
class Intent:
    id: str
    episode_id: str
    action: Action
    level: int | None
    side: Side
    quantity: float | None = None
    requested_notional: float | None = None
    decision_index: int = -1


@dataclass
class Episode:
    id: str
    side: Side
    active_entry: float
    beta_entry: float
    btc_initial_qty: float = 0.0
    btc_open_qty: float = 0.0
    btc_entry_vwap: float | None = None
    h: float | None = None
    wave_levels: tuple[float, float, float] | None = None
    btc_tps: set[int] = field(default_factory=set)
    btc_filled_tps: set[int] = field(default_factory=set)
    sol_rights: set[int] = field(default_factory=set)
    sol_adds: set[int] = field(default_factory=set)
    sol_qty: float = 0.0
    sol_first_fill_at: datetime | None = None
    fixed_sigma: float | None = None
    sol_half_done: bool = False
    sol_half_decision_index: int | None = None
    best_f: float = 0.0
    pending: dict[str, Intent] = field(default_factory=dict)
    attempted_btc_at: dict[int, int] = field(default_factory=dict)
    attempted_sol_at: dict[int, int] = field(default_factory=dict)
    close_reason: str | None = None


class WaveOverlayState:
    """State changes only after native fills/cancel confirmations, never acknowledgements."""
    def __init__(self, config: Candidate) -> None:
        self.config = config
        self.episode: Episode | None = None
        self.locked_after_liquidation = False
        self._decision_index = -1

    def _intent(self, episode: Episode, action: Action, side: Side, level: int | None, **kwargs: float) -> Intent:
        intent = Intent(str(uuid4()), episode.id, action, level, side, decision_index=self._decision_index, **kwargs)
        episode.pending[intent.id] = intent
        return intent

    def decide(self, bars: list[DailyBar], all_features: list[Features], index: int, active_marked: float) -> list[Intent]:
        self._decision_index = index
        feature = all_features[index]
        episode = self.episode
        if episode is None:
            if self.locked_after_liquidation or feature.beta is None or not 0.2 < feature.beta < 4:
                return []
            levels = completed_wave_levels(bars, all_features, index, self.config, feature.side)
            if levels is None:
                return []
            episode = Episode(str(uuid4()), feature.side, active_marked, feature.beta, wave_levels=levels)
            self.episode = episode
            return [self._intent(episode, "BTC_ENTRY", feature.side, None, requested_notional=min(self.config.btc_notional_multiplier * active_marked, self.config.max_parent_notional))]
        if episode.pending:
            return []
        if feature.side != episode.side:
            episode.close_reason = "REGIME"
            return [self._intent(episode, "CLOSE_ALL", -episode.side, None)]
        if episode.btc_entry_vwap is None or episode.h is None:
            return []
        f = episode.side * (bars[index].btc_close / episode.btc_entry_vwap - 1)
        episode.best_f = max(episode.best_f, f, 0.0)
        if (episode.best_f > self.config.btc_close_trail_fraction and f <= episode.best_f - self.config.btc_close_trail_fraction):
            episode.close_reason = "TRAIL"
            return [self._intent(episode, "CLOSE_ALL", -episode.side, None)]
        intents: list[Intent] = []
        for level, threshold in enumerate(episode.wave_levels or ()):
            if f >= threshold and level not in episode.btc_filled_tps and episode.attempted_btc_at.get(level) != index:
                episode.attempted_btc_at[level] = index
                intents.append(self._intent(episode, "BTC_REDUCE", -episode.side, level, quantity=min(episode.btc_initial_qty * self.config.btc_tp_fractions_initial_qty[level], episode.btc_open_qty)))
        if intents:
            return intents
        # SOL rights come only from confirmed BTC reduce fills; additions follow reductions.
        # An invalid current beta permits only exits/reductions, never new risk.
        if feature.beta is None or not 0.2 < feature.beta < 4:
            return self._sol_exits(episode, feature, bars[index], index)
        z = feature.z if episode.fixed_sigma is None else (feature.relative - feature.mu) / episode.fixed_sigma if feature.relative is not None and feature.mu is not None else None
        if z is not None:
            signed_z = episode.side * z
            for level in sorted(episode.sol_rights):
                if level not in episode.sol_adds and episode.attempted_sol_at.get(level) != index and signed_z >= self.config.sol_entry_z[level]:
                    episode.attempted_sol_at[level] = index
                    intents.append(self._intent(episode, "SOL_ADD", -episode.side, level, requested_notional=episode.h * self.config.sol_size_multipliers_h[level]))
            if intents:
                return intents
        return self._sol_exits(episode, feature, bars[index], index, z)

    def _sol_exits(self, episode: Episode, feature: Features, bar: DailyBar, index: int, z: float | None = None) -> list[Intent]:
        if episode.sol_qty and episode.sol_first_fill_at is not None and bar.close_time >= episode.sol_first_fill_at + timedelta(days=self.config.sol_max_holding_days):
            return [self._intent(episode, "SOL_EXIT", episode.side, None, quantity=episode.sol_qty)]
        if z is None:
            return []
        signed_z = episode.side * z
        if episode.sol_qty and episode.sol_first_fill_at is not None:
            if not episode.sol_half_done and signed_z <= self.config.sol_exit_half_z:
                return [self._intent(episode, "SOL_HALF_EXIT", episode.side, None, quantity=episode.sol_qty / 2)]
            if episode.sol_half_done and episode.sol_half_decision_index is not None and index > episode.sol_half_decision_index and signed_z <= self.config.sol_exit_all_z:
                return [self._intent(episode, "SOL_EXIT", episode.side, None, quantity=episode.sol_qty)]
        return []

    def on_fill(self, intent_id: str, quantity: float, price: float, when: datetime, sigma: float | None = None) -> None:
        episode = self.episode
        if episode is None or intent_id not in episode.pending or quantity <= 0:
            return
        intent = episode.pending[intent_id]
        if intent.action == "BTC_ENTRY":
            prior = episode.btc_initial_qty
            episode.btc_entry_vwap = ((episode.btc_entry_vwap or 0) * prior + price * quantity) / (prior + quantity)
            episode.btc_initial_qty += quantity
            episode.btc_open_qty += quantity
        elif intent.action == "BTC_REDUCE" and intent.level is not None:
            episode.btc_filled_tps.add(intent.level)
            episode.sol_rights.add(intent.level)
            episode.btc_open_qty = max(0.0, episode.btc_open_qty - quantity)
        elif intent.action == "SOL_ADD":
            episode.sol_adds.add(intent.level)  # type: ignore[arg-type]
            episode.sol_qty += quantity
            if episode.sol_first_fill_at is None:
                episode.sol_first_fill_at, episode.fixed_sigma = when, sigma
            episode.sol_half_done = False
        elif intent.action == "SOL_HALF_EXIT":
            episode.sol_qty = max(0.0, episode.sol_qty - quantity)
            episode.sol_half_done = True
        elif intent.action == "SOL_EXIT":
            episode.sol_qty = max(0.0, episode.sol_qty - quantity)
            if episode.sol_qty == 0:
                episode.sol_first_fill_at = episode.fixed_sigma = None
                episode.sol_half_done = False
        elif intent.action == "CLOSE_ALL":
            return
        episode.h = (episode.btc_initial_qty * (episode.btc_entry_vwap or price)) / episode.beta_entry

    def on_parent_cancelled(self, intent_id: str) -> None:
        if self.episode is None:
            return
        self.episode.pending.pop(intent_id, None)

    def on_parent_terminal(self, intent_id: str) -> None:
        """Called only after a native terminal order state, never an ACK."""
        self.on_parent_cancelled(intent_id)

    def on_half_exit_decision(self, index: int) -> None:
        if self.episode is not None:
            self.episode.sol_half_decision_index = index

    def on_group_flat(self) -> str | None:
        """A native cache reconciliation confirmed both legs flat."""
        reason = self.episode.close_reason if self.episode else None
        self.episode = None
        return reason

    def on_liquidation(self) -> None:
        self.episode = None
        self.locked_after_liquidation = True
