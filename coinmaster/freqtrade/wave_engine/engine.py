#!/usr/bin/env python3
"""Research-only 4H wave engine prototype.

The implementation is intentionally self-contained and uses only Python's
standard library so it can run in the current repo sandbox without requiring
the full Freqtrade/pandas environment. It operates on closed candles only.
"""

from __future__ import annotations

import csv
import itertools
import json
import math
import random
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Literal

Direction = Literal["long", "short"]
RegimeState = Literal["flat", "long", "short"]
WaveEngineType = Literal["atr_zigzag", "pct_zigzag"]
BreakBasis = Literal["wick", "close"]

TIMEFRAME_SECONDS = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
}


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True)
class Pivot:
    timestamp: datetime
    price: float
    kind: Literal["high", "low"]
    candle_index: int
    threshold: float


@dataclass(frozen=True)
class RegimeSnapshot:
    timestamp: datetime
    state: RegimeState
    sequence_id: int
    break_count: int
    last_break_direction: str | None
    last_high_price: float | None
    last_low_price: float | None
    confirmed_wave_id: int | None
    confirmed_at: datetime | None


@dataclass(frozen=True)
class EntrySignal:
    symbol: str
    timeframe: str
    timestamp: datetime
    side: Direction
    entry_price: float
    regime_state: RegimeState
    reason: str
    context_id: str
    impulse_start_price: float
    target_extremum_price: float
    pullback_ratio: float | None
    wave_sequence_id: int
    confirmed_wave_id: int | None


@dataclass(frozen=True)
class TradeResult:
    symbol: str
    timeframe: str
    side: Direction
    reason: str
    context_id: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    stop_price: float
    tp1_price: float
    tp2_price: float
    tp3_price: float
    profit_ratio: float
    profit_abs: float
    exit_reason: str
    tp1_hit: bool
    tp2_hit: bool
    tp3_hit: bool
    bars_held: int
    max_adverse_excursion: float
    max_favorable_excursion: float


@dataclass(frozen=True)
class ResearchMetrics:
    roi_pct: float
    profit_abs: float
    profit_factor: float | None
    max_drawdown_pct: float
    winrate_pct: float
    trades: int
    wins: int
    losses: int
    top_trade_stress_abs: float
    top_trade_stress_pct_of_profit: float


@dataclass(frozen=True)
class WaveEngineProfile:
    symbol: str = "BTC/USDC:USDC"
    direction_tf: str = "4h"
    entry_timeframes: tuple[str, ...] = ("5m", "15m", "1h")
    wave_engine: WaveEngineType = "atr_zigzag"
    break_basis: BreakBasis = "wick"
    atr_period: int = 14
    atr_mult: float = 2.5
    pct_move: float = 0.03
    flat_extreme_lookback_hours: int = 100
    pullback_ratio: float = 0.5
    impulse_sl_buffer: float = 0.0033
    max_sl_pct: float = 0.03
    tp1_max_pct: float = 0.015
    tp2_pct: float = 0.03
    tp3_pct: float = 0.06
    time_stop_hours: int = 8
    stake_per_trade: float = 1.0


DEFAULT_PROFILE = WaveEngineProfile()


def _ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    raise TypeError(f"unsupported timestamp: {value!r}")


def _round(value: float) -> float:
    return round(float(value), 8)


def _safe_float(value: Any, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if not math.isfinite(number):
        return fallback
    return number


def _normalize_profile(raw: dict[str, Any]) -> WaveEngineProfile:
    entry_timeframes = tuple(
        tf for tf in raw.get("entry_timeframes", DEFAULT_PROFILE.entry_timeframes) if tf in ("5m", "15m", "1h")
    ) or DEFAULT_PROFILE.entry_timeframes
    return WaveEngineProfile(
        symbol=str(raw.get("symbol") or DEFAULT_PROFILE.symbol),
        direction_tf="4h",
        entry_timeframes=entry_timeframes,
        wave_engine="pct_zigzag" if raw.get("wave_engine") == "pct_zigzag" else "atr_zigzag",
        break_basis="close" if raw.get("break_basis") == "close" else "wick",
        atr_period=max(2, int(round(_safe_float(raw.get("atr_period"), DEFAULT_PROFILE.atr_period)))),
        atr_mult=min(4.0, max(1.5, _safe_float(raw.get("atr_mult"), DEFAULT_PROFILE.atr_mult))),
        pct_move=min(0.05, max(0.02, _safe_float(raw.get("pct_move"), DEFAULT_PROFILE.pct_move))),
        flat_extreme_lookback_hours=min(150, max(60, int(round(_safe_float(raw.get("flat_extreme_lookback_hours"), DEFAULT_PROFILE.flat_extreme_lookback_hours))))),
        pullback_ratio=min(0.8, max(0.4, _safe_float(raw.get("pullback_ratio"), DEFAULT_PROFILE.pullback_ratio))),
        impulse_sl_buffer=max(0.0, _safe_float(raw.get("impulse_sl_buffer"), DEFAULT_PROFILE.impulse_sl_buffer)),
        max_sl_pct=min(0.04, max(0.02, _safe_float(raw.get("max_sl_pct"), DEFAULT_PROFILE.max_sl_pct))),
        tp1_max_pct=max(0.0, _safe_float(raw.get("tp1_max_pct"), DEFAULT_PROFILE.tp1_max_pct)),
        tp2_pct=min(0.04, max(0.02, _safe_float(raw.get("tp2_pct"), DEFAULT_PROFILE.tp2_pct))),
        tp3_pct=min(0.08, max(0.04, _safe_float(raw.get("tp3_pct"), DEFAULT_PROFILE.tp3_pct))),
        time_stop_hours=min(16, max(4, int(round(_safe_float(raw.get("time_stop_hours"), DEFAULT_PROFILE.time_stop_hours))))),
        stake_per_trade=max(0.0001, _safe_float(raw.get("stake_per_trade"), DEFAULT_PROFILE.stake_per_trade)),
    )


def profile_to_dict(profile: WaveEngineProfile) -> dict[str, Any]:
    return asdict(profile)


def load_dataset(path: str | Path) -> dict[str, list[Candle]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_candles = payload.get("candles", payload)
    if not isinstance(raw_candles, dict):
        raise ValueError("dataset must be a mapping of timeframe -> candles or {'candles': {...}}")
    candles_by_tf: dict[str, list[Candle]] = {}
    for timeframe, rows in raw_candles.items():
        if timeframe not in TIMEFRAME_SECONDS:
            continue
        if not isinstance(rows, list):
            raise ValueError(f"candles[{timeframe}] must be a list")
        normalized = [
            Candle(
                timestamp=_ts(row["timestamp"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0.0)),
            )
            for row in rows
        ]
        normalized.sort(key=lambda candle: candle.timestamp)
        deduped: list[Candle] = []
        seen: set[datetime] = set()
        for candle in normalized:
            if candle.timestamp in seen:
                continue
            seen.add(candle.timestamp)
            deduped.append(candle)
        candles_by_tf[timeframe] = deduped
    if "4h" not in candles_by_tf:
        raise ValueError("dataset must include 4h candles")
    return candles_by_tf


def _atr(candles: list[Candle], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(candles)
    trs: list[float] = []
    prev_close = candles[0].close if candles else 0.0
    for index, candle in enumerate(candles):
        tr = max(candle.high - candle.low, abs(candle.high - prev_close), abs(candle.low - prev_close))
        trs.append(tr)
        prev_close = candle.close
        if index + 1 >= period:
            window = trs[index + 1 - period : index + 1]
            result[index] = sum(window) / period
    return result


def _threshold(profile: WaveEngineProfile, candle: Candle, atr_value: float | None, pivot_price: float) -> float:
    if profile.wave_engine == "pct_zigzag":
        return pivot_price * profile.pct_move
    return max(0.0, (atr_value or 0.0) * profile.atr_mult)


def detect_pivots(candles: list[Candle], profile: WaveEngineProfile) -> list[Pivot]:
    if len(candles) < 3:
        return []
    atrs = _atr(candles, profile.atr_period)
    pivots: list[Pivot] = []
    direction: Literal["up", "down"] | None = None
    extreme_index = 0
    extreme_price = candles[0].close

    for index in range(1, len(candles)):
        candle = candles[index]
        threshold = _threshold(profile, candle, atrs[index], max(extreme_price, 0.0000001))
        if direction in (None, "up"):
            if candle.high >= extreme_price:
                extreme_index = index
                extreme_price = candle.high
            if extreme_price - candle.low >= threshold > 0:
                # A ZigZag pivot is only knowable once the reversal threshold is
                # crossed on the current closed candle.  Keep the extremum price,
                # but timestamp the pivot at confirmation time so downstream
                # regime/entry logic cannot see an unconfirmed past pivot.
                pivots.append(
                    Pivot(
                        timestamp=candle.timestamp,
                        price=extreme_price,
                        kind="high",
                        candle_index=index,
                        threshold=threshold,
                    )
                )
                direction = "down"
                extreme_index = index
                extreme_price = candle.low
                continue
        if direction in (None, "down"):
            if candle.low <= extreme_price:
                extreme_index = index
                extreme_price = candle.low
            if candle.high - extreme_price >= threshold > 0:
                # A ZigZag pivot is only knowable once the reversal threshold is
                # crossed on the current closed candle.  Keep the extremum price,
                # but timestamp the pivot at confirmation time so downstream
                # regime/entry logic cannot see an unconfirmed past pivot.
                pivots.append(
                    Pivot(
                        timestamp=candle.timestamp,
                        price=extreme_price,
                        kind="low",
                        candle_index=index,
                        threshold=threshold,
                    )
                )
                direction = "up"
                extreme_index = index
                extreme_price = candle.high
    pivots.sort(key=lambda pivot: pivot.timestamp)
    deduped: list[Pivot] = []
    for pivot in pivots:
        if deduped and deduped[-1].timestamp == pivot.timestamp and deduped[-1].kind == pivot.kind:
            if pivot.kind == "high" and pivot.price > deduped[-1].price:
                deduped[-1] = pivot
            elif pivot.kind == "low" and pivot.price < deduped[-1].price:
                deduped[-1] = pivot
            continue
        deduped.append(pivot)
    return deduped


def build_regime(candles_4h: list[Candle], pivots: list[Pivot], break_basis: BreakBasis) -> list[RegimeSnapshot]:
    state: RegimeState = "flat"
    sequence_id = 0
    break_count = 0
    last_break_direction: str | None = None
    confirmed_wave_id: int | None = None
    confirmed_at: datetime | None = None
    last_high: Pivot | None = None
    last_low: Pivot | None = None
    broken_high_ts: datetime | None = None
    broken_low_ts: datetime | None = None
    snapshots: list[RegimeSnapshot] = []
    pivot_index = 0

    for candle in candles_4h:
        while pivot_index < len(pivots) and pivots[pivot_index].timestamp <= candle.timestamp:
            pivot = pivots[pivot_index]
            if pivot.kind == "high":
                last_high = pivot
            else:
                last_low = pivot
            pivot_index += 1

        basis_up = candle.close if break_basis == "close" else candle.high
        basis_down = candle.close if break_basis == "close" else candle.low
        up_broken = last_high and basis_up > last_high.price and broken_high_ts != last_high.timestamp
        down_broken = last_low and basis_down < last_low.price and broken_low_ts != last_low.timestamp

        event_direction: str | None = None
        if up_broken and down_broken:
            up_distance = abs(basis_up - last_high.price) if last_high else 0.0
            down_distance = abs(last_low.price - basis_down) if last_low else 0.0
            event_direction = "up" if up_distance >= down_distance else "down"
        elif up_broken:
            event_direction = "up"
        elif down_broken:
            event_direction = "down"

        if event_direction:
            sequence_id += 1
            if event_direction == last_break_direction:
                break_count = min(2, break_count + 1)
            else:
                last_break_direction = event_direction
                break_count = 1
            state = "flat" if break_count == 1 else ("long" if event_direction == "up" else "short")
            if event_direction == "up" and last_high:
                broken_high_ts = last_high.timestamp
            if event_direction == "down" and last_low:
                broken_low_ts = last_low.timestamp
            if state in ("long", "short"):
                confirmed_wave_id = sequence_id
                confirmed_at = candle.timestamp
            else:
                confirmed_wave_id = None
                confirmed_at = None

        snapshots.append(
            RegimeSnapshot(
                timestamp=candle.timestamp,
                state=state,
                sequence_id=sequence_id,
                break_count=break_count,
                last_break_direction=last_break_direction,
                last_high_price=last_high.price if last_high else None,
                last_low_price=last_low.price if last_low else None,
                confirmed_wave_id=confirmed_wave_id,
                confirmed_at=confirmed_at,
            )
        )
    return snapshots


def _is_bullish_engulfing(prev_candle: Candle, candle: Candle) -> bool:
    return (
        prev_candle.close < prev_candle.open
        and candle.close > candle.open
        and candle.open <= prev_candle.close
        and candle.close >= prev_candle.open
    )


def _is_bearish_engulfing(prev_candle: Candle, candle: Candle) -> bool:
    return (
        prev_candle.close > prev_candle.open
        and candle.close < candle.open
        and candle.open >= prev_candle.close
        and candle.close <= prev_candle.open
    )


def _segment_start_index(candles: list[Candle], start_time: datetime | None) -> int:
    if start_time is None:
        return 0
    for index, candle in enumerate(candles):
        if candle.timestamp >= start_time:
            return index
    return len(candles)


def _extreme_context(
    candles: list[Candle],
    index: int,
    start_index: int,
    side: Direction,
) -> tuple[int, int, int, float] | None:
    if index - start_index < 3:
        return None
    segment = candles[start_index:index]
    if side == "long":
        impulse_end_index = max(range(start_index, index), key=lambda idx: candles[idx].high)
        impulse_start_index = min(range(start_index, impulse_end_index + 1), key=lambda idx: candles[idx].low)
        if impulse_end_index >= index - 1:
            return None
        correction_index = min(range(impulse_end_index + 1, index + 1), key=lambda idx: candles[idx].low)
        impulse_range = candles[impulse_end_index].high - candles[impulse_start_index].low
        pullback = candles[impulse_end_index].high - candles[correction_index].low
    else:
        impulse_end_index = min(range(start_index, index), key=lambda idx: candles[idx].low)
        impulse_start_index = max(range(start_index, impulse_end_index + 1), key=lambda idx: candles[idx].high)
        if impulse_end_index >= index - 1:
            return None
        correction_index = max(range(impulse_end_index + 1, index + 1), key=lambda idx: candles[idx].high)
        impulse_range = candles[impulse_start_index].high - candles[impulse_end_index].low
        pullback = candles[correction_index].high - candles[impulse_end_index].low
    if impulse_range <= 0:
        return None
    ratio = pullback / impulse_range
    return impulse_start_index, impulse_end_index, correction_index, ratio


def generate_entry_signals(
    symbol: str,
    profile: WaveEngineProfile,
    candles_by_tf: dict[str, list[Candle]],
    regimes: list[RegimeSnapshot],
) -> list[EntrySignal]:
    signals: list[EntrySignal] = []
    used_context_ids: set[str] = set()
    regimes_by_tf = regimes

    for timeframe in profile.entry_timeframes:
        candles = candles_by_tf.get(timeframe, [])
        if len(candles) < 3:
            continue
        regime_index = 0
        for index in range(1, len(candles)):
            candle = candles[index]
            prev_candle = candles[index - 1]
            while regime_index + 1 < len(regimes_by_tf) and regimes_by_tf[regime_index + 1].timestamp <= candle.timestamp:
                regime_index += 1
            regime = regimes_by_tf[regime_index]
            bullish = _is_bullish_engulfing(prev_candle, candle)
            bearish = _is_bearish_engulfing(prev_candle, candle)
            if not bullish and not bearish:
                continue

            if regime.state == "flat":
                lookback_seconds = profile.flat_extreme_lookback_hours * 3600
                window_start = candle.timestamp.timestamp() - lookback_seconds
                lows = [item.low for item in candles[: index + 1] if item.timestamp.timestamp() >= window_start]
                highs = [item.high for item in candles[: index + 1] if item.timestamp.timestamp() >= window_start]
                if bullish and lows and min(lows) in (prev_candle.low, candle.low):
                    context_id = f"flat:{timeframe}:{regime.sequence_id}"
                    if context_id not in used_context_ids:
                        used_context_ids.add(context_id)
                        signals.append(
                            EntrySignal(
                                symbol=symbol,
                                timeframe=timeframe,
                                timestamp=candle.timestamp,
                                side="long",
                                entry_price=candle.close,
                                regime_state="flat",
                                reason="flat_body_engulfing_extreme",
                                context_id=context_id,
                                impulse_start_price=min(prev_candle.low, candle.low),
                                target_extremum_price=max(highs),
                                pullback_ratio=None,
                                wave_sequence_id=regime.sequence_id,
                                confirmed_wave_id=regime.confirmed_wave_id,
                            )
                        )
                elif bearish and highs and max(highs) in (prev_candle.high, candle.high):
                    context_id = f"flat:{timeframe}:{regime.sequence_id}"
                    if context_id not in used_context_ids:
                        used_context_ids.add(context_id)
                        signals.append(
                            EntrySignal(
                                symbol=symbol,
                                timeframe=timeframe,
                                timestamp=candle.timestamp,
                                side="short",
                                entry_price=candle.close,
                                regime_state="flat",
                                reason="flat_body_engulfing_extreme",
                                context_id=context_id,
                                impulse_start_price=max(prev_candle.high, candle.high),
                                target_extremum_price=min(lows),
                                pullback_ratio=None,
                                wave_sequence_id=regime.sequence_id,
                                confirmed_wave_id=regime.confirmed_wave_id,
                            )
                        )
                continue

            side: Direction = "long" if regime.state == "long" else "short"
            if side == "long" and not bullish:
                continue
            if side == "short" and not bearish:
                continue
            start_index = _segment_start_index(candles, regime.confirmed_at)
            context = _extreme_context(candles, index, start_index, side)
            if not context:
                continue
            impulse_start_index, impulse_end_index, correction_index, pullback = context
            if pullback < profile.pullback_ratio or pullback > 0.8:
                continue
            correction_ts = candles[correction_index].timestamp.isoformat()
            context_id = f"trend:{timeframe}:{regime.confirmed_wave_id}:{correction_ts}"
            if context_id in used_context_ids:
                continue
            used_context_ids.add(context_id)
            if side == "long":
                impulse_start_price = candles[impulse_start_index].low
                target_extremum_price = candles[impulse_end_index].high
            else:
                impulse_start_price = candles[impulse_start_index].high
                target_extremum_price = candles[impulse_end_index].low
            signals.append(
                EntrySignal(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=candle.timestamp,
                    side=side,
                    entry_price=candle.close,
                    regime_state=regime.state,
                    reason="trend_pullback_body_engulfing",
                    context_id=context_id,
                    impulse_start_price=impulse_start_price,
                    target_extremum_price=target_extremum_price,
                    pullback_ratio=_round(pullback),
                    wave_sequence_id=regime.sequence_id,
                    confirmed_wave_id=regime.confirmed_wave_id,
                )
            )
    signals.sort(key=lambda item: (item.timestamp, item.timeframe))
    return signals


def _stop_price(signal: EntrySignal, profile: WaveEngineProfile) -> float:
    if signal.side == "long":
        raw = signal.impulse_start_price * (1.0 - profile.impulse_sl_buffer)
        capped = signal.entry_price * (1.0 - profile.max_sl_pct)
        return max(raw, capped)
    raw = signal.impulse_start_price * (1.0 + profile.impulse_sl_buffer)
    capped = signal.entry_price * (1.0 + profile.max_sl_pct)
    return min(raw, capped)


def _tp1_price(signal: EntrySignal, profile: WaveEngineProfile) -> float:
    if signal.side == "long":
        cap = signal.entry_price * (1.0 + profile.tp1_max_pct)
        target = signal.target_extremum_price if signal.target_extremum_price > signal.entry_price else cap
        return min(target, cap)
    cap = signal.entry_price * (1.0 - profile.tp1_max_pct)
    target = signal.target_extremum_price if signal.target_extremum_price < signal.entry_price else cap
    return max(target, cap)


def _profit_ratio(side: Direction, entry_price: float, exit_price: float) -> float:
    if side == "long":
        return (exit_price - entry_price) / entry_price
    return (entry_price - exit_price) / entry_price


def simulate_trades(
    profile: WaveEngineProfile,
    candles_by_tf: dict[str, list[Candle]],
    signals: list[EntrySignal],
) -> list[TradeResult]:
    trades: list[TradeResult] = []
    next_available_time: datetime | None = None
    by_timestamp: dict[str, dict[datetime, int]] = {}
    for timeframe, candles in candles_by_tf.items():
        by_timestamp[timeframe] = {candle.timestamp: index for index, candle in enumerate(candles)}

    for signal in signals:
        if next_available_time and signal.timestamp < next_available_time:
            continue
        candles = candles_by_tf.get(signal.timeframe, [])
        timestamp_index = by_timestamp.get(signal.timeframe, {}).get(signal.timestamp)
        if timestamp_index is None or timestamp_index >= len(candles) - 1:
            continue
        stop_price = _stop_price(signal, profile)
        tp1_price = _tp1_price(signal, profile)
        tp2_price = signal.entry_price * (1.0 + profile.tp2_pct if signal.side == "long" else 1.0 - profile.tp2_pct)
        tp3_price = signal.entry_price * (1.0 + profile.tp3_pct if signal.side == "long" else 1.0 - profile.tp3_pct)
        be_price = signal.entry_price
        fractions = [0.34, 0.33, 0.33]
        remaining = 1.0
        realized = 0.0
        tp1_hit = False
        tp2_hit = False
        tp3_hit = False
        exit_reason = "time_stop"
        exit_price = candles[-1].close
        exit_time = candles[-1].timestamp
        max_adverse = 0.0
        max_favorable = 0.0
        bars_held = 0
        stop_after_tp1 = stop_price

        for forward_index in range(timestamp_index + 1, len(candles)):
            candle = candles[forward_index]
            bars_held += 1
            if signal.side == "long":
                max_adverse = min(max_adverse, (candle.low - signal.entry_price) / signal.entry_price)
                max_favorable = max(max_favorable, (candle.high - signal.entry_price) / signal.entry_price)
                active_stop = be_price if tp1_hit else stop_after_tp1
                if candle.low <= active_stop:
                    exit_reason = "stoploss" if not tp1_hit else "breakeven_stop"
                    exit_price = active_stop
                    exit_time = candle.timestamp
                    realized += remaining * _profit_ratio(signal.side, signal.entry_price, exit_price)
                    remaining = 0.0
                    next_available_time = candle.timestamp
                    break
                if not tp1_hit and candle.high >= tp1_price:
                    realized += fractions[0] * _profit_ratio(signal.side, signal.entry_price, tp1_price)
                    remaining -= fractions[0]
                    tp1_hit = True
                if tp1_hit and not tp2_hit and candle.high >= tp2_price:
                    realized += fractions[1] * _profit_ratio(signal.side, signal.entry_price, tp2_price)
                    remaining -= fractions[1]
                    tp2_hit = True
                if tp2_hit and not tp3_hit and candle.high >= tp3_price:
                    realized += remaining * _profit_ratio(signal.side, signal.entry_price, tp3_price)
                    remaining = 0.0
                    tp3_hit = True
                    exit_reason = "tp3"
                    exit_price = tp3_price
                    exit_time = candle.timestamp
                    next_available_time = candle.timestamp
                    break
            else:
                max_adverse = min(max_adverse, (signal.entry_price - candle.high) / signal.entry_price)
                max_favorable = max(max_favorable, (signal.entry_price - candle.low) / signal.entry_price)
                active_stop = be_price if tp1_hit else stop_after_tp1
                if candle.high >= active_stop:
                    exit_reason = "stoploss" if not tp1_hit else "breakeven_stop"
                    exit_price = active_stop
                    exit_time = candle.timestamp
                    realized += remaining * _profit_ratio(signal.side, signal.entry_price, exit_price)
                    remaining = 0.0
                    next_available_time = candle.timestamp
                    break
                if not tp1_hit and candle.low <= tp1_price:
                    realized += fractions[0] * _profit_ratio(signal.side, signal.entry_price, tp1_price)
                    remaining -= fractions[0]
                    tp1_hit = True
                if tp1_hit and not tp2_hit and candle.low <= tp2_price:
                    realized += fractions[1] * _profit_ratio(signal.side, signal.entry_price, tp2_price)
                    remaining -= fractions[1]
                    tp2_hit = True
                if tp2_hit and not tp3_hit and candle.low <= tp3_price:
                    realized += remaining * _profit_ratio(signal.side, signal.entry_price, tp3_price)
                    remaining = 0.0
                    tp3_hit = True
                    exit_reason = "tp3"
                    exit_price = tp3_price
                    exit_time = candle.timestamp
                    next_available_time = candle.timestamp
                    break

            hours_held = (candle.timestamp - signal.timestamp).total_seconds() / 3600.0
            if hours_held >= profile.time_stop_hours:
                exit_reason = "time_stop"
                exit_price = candle.close
                exit_time = candle.timestamp
                realized += remaining * _profit_ratio(signal.side, signal.entry_price, exit_price)
                remaining = 0.0
                next_available_time = candle.timestamp
                break
        if remaining > 0:
            exit_price = candles[-1].close
            exit_reason = "dataset_end"
            exit_time = candles[-1].timestamp
            realized += remaining * _profit_ratio(signal.side, signal.entry_price, exit_price)
        trades.append(
            TradeResult(
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                side=signal.side,
                reason=signal.reason,
                context_id=signal.context_id,
                entry_time=signal.timestamp,
                exit_time=exit_time,
                entry_price=_round(signal.entry_price),
                exit_price=_round(exit_price),
                stop_price=_round(stop_price),
                tp1_price=_round(tp1_price),
                tp2_price=_round(tp2_price),
                tp3_price=_round(tp3_price),
                profit_ratio=_round(realized),
                profit_abs=_round(realized * profile.stake_per_trade),
                exit_reason=exit_reason,
                tp1_hit=tp1_hit,
                tp2_hit=tp2_hit,
                tp3_hit=tp3_hit,
                bars_held=bars_held,
                max_adverse_excursion=_round(max_adverse),
                max_favorable_excursion=_round(max_favorable),
            )
        )
    return trades


def compute_metrics(trades: list[TradeResult]) -> ResearchMetrics:
    profit_abs = sum(trade.profit_abs for trade in trades)
    wins = sum(1 for trade in trades if trade.profit_abs > 0)
    losses = sum(1 for trade in trades if trade.profit_abs < 0)
    gross_profit = sum(trade.profit_abs for trade in trades if trade.profit_abs > 0)
    gross_loss = abs(sum(trade.profit_abs for trade in trades if trade.profit_abs < 0))
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for trade in trades:
        equity += trade.profit_abs
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    best_trade = max((trade.profit_abs for trade in trades), default=0.0)
    stress_abs = profit_abs - best_trade
    stress_pct = 0.0 if profit_abs == 0 else (stress_abs / profit_abs) * 100.0
    return ResearchMetrics(
        roi_pct=_round(profit_abs * 100.0),
        profit_abs=_round(profit_abs),
        profit_factor=None if gross_loss == 0 else _round(gross_profit / gross_loss),
        max_drawdown_pct=_round(max_drawdown * 100.0),
        winrate_pct=_round((wins / len(trades) * 100.0) if trades else 0.0),
        trades=len(trades),
        wins=wins,
        losses=losses,
        top_trade_stress_abs=_round(stress_abs),
        top_trade_stress_pct_of_profit=_round(stress_pct),
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    raise TypeError(f"unsupported json value: {type(value)!r}")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default) + "\n", encoding="utf-8")


def _write_csv(path: Path, trades: list[TradeResult]) -> None:
    fieldnames = list(asdict(trades[0]).keys()) if trades else list(asdict(TradeResult(
        symbol="",
        timeframe="",
        side="long",
        reason="",
        context_id="",
        entry_time=datetime.now(tz=UTC),
        exit_time=datetime.now(tz=UTC),
        entry_price=0.0,
        exit_price=0.0,
        stop_price=0.0,
        tp1_price=0.0,
        tp2_price=0.0,
        tp3_price=0.0,
        profit_ratio=0.0,
        profit_abs=0.0,
        exit_reason="",
        tp1_hit=False,
        tp2_hit=False,
        tp3_hit=False,
        bars_held=0,
        max_adverse_excursion=0.0,
        max_favorable_excursion=0.0,
    )).keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for trade in trades:
            row = asdict(trade)
            row["entry_time"] = trade.entry_time.isoformat()
            row["exit_time"] = trade.exit_time.isoformat()
            writer.writerow(row)


def _ensure_run_dir(output_root: str | Path, run_id: str) -> Path:
    root = Path(output_root)
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - surfaced to caller
        raise RuntimeError(f"cannot create output root {root}: {exc}") from exc
    run_dir = root / run_id
    run_dir.mkdir(parents=False, exist_ok=False)
    return run_dir


def _summarize_markdown(profile: WaveEngineProfile, pivots: list[Pivot], signals: list[EntrySignal], metrics: ResearchMetrics) -> str:
    return "\n".join(
        [
            "# Wave Engine research run",
            "",
            "## Profile",
            "",
            f"- Symbol: `{profile.symbol}`",
            f"- Wave engine: `{profile.wave_engine}`",
            f"- Break basis: `{profile.break_basis}`",
            f"- Entry TFs: `{', '.join(profile.entry_timeframes)}`",
            f"- Flat lookback: **{profile.flat_extreme_lookback_hours}h**",
            f"- Pullback ratio floor: **{profile.pullback_ratio:.2f}**",
            "",
            "## Result",
            "",
            f"- Pivots: **{len(pivots)}**",
            f"- Signals: **{len(signals)}**",
            f"- Trades: **{metrics.trades}**",
            f"- ROI: **{metrics.roi_pct}%**",
            f"- Profit: **{metrics.profit_abs}**",
            f"- Profit factor: **{metrics.profit_factor}**",
            f"- Max drawdown: **{metrics.max_drawdown_pct}%**",
            f"- Winrate: **{metrics.winrate_pct}%**",
            f"- Top-trade stress: **{metrics.top_trade_stress_abs}** ({metrics.top_trade_stress_pct_of_profit}% of total profit)",
            "",
            "## Notes",
            "",
            "- Closed-candle only; no unconfirmed pivot appended at dataset end.",
            "- Structural breaks are counted sequentially: first break => flat, second same-direction break => confirmed trend.",
            "- Same-candle SL/TP ambiguity is resolved conservatively by checking stop before targets.",
        ]
    ) + "\n"


def run_single_research(
    dataset_path: str | Path,
    profile_raw: dict[str, Any],
    output_root: str | Path,
    run_id: str | None = None,
) -> dict[str, Any]:
    profile = _normalize_profile(profile_raw)
    candles_by_tf = load_dataset(dataset_path)
    pivots = detect_pivots(candles_by_tf["4h"], profile)
    regimes = build_regime(candles_by_tf["4h"], pivots, profile.break_basis)
    signals = generate_entry_signals(profile.symbol, profile, candles_by_tf, regimes)
    trades = simulate_trades(profile, candles_by_tf, signals)
    metrics = compute_metrics(trades)
    run_name = run_id or datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = _ensure_run_dir(output_root, run_name)
    _write_json(run_dir / "profile.json", profile_to_dict(profile))
    _write_json(run_dir / "resolved-params.json", profile_to_dict(profile))
    _write_json(
        run_dir / "state.json",
        {
            "status": "completed",
            "run_id": run_name,
            "mode": "single",
            "symbol": profile.symbol,
            "dataset_path": str(dataset_path),
            "generated_at": datetime.now(tz=UTC),
        },
    )
    _write_json(run_dir / "pivots.json", pivots)
    _write_json(run_dir / "regime.json", regimes)
    _write_json(run_dir / "signals.json", signals)
    _write_json(run_dir / "trades.json", trades)
    _write_csv(run_dir / "trades.csv", trades)
    _write_json(run_dir / "metrics.json", metrics)
    (run_dir / "SUMMARY.md").write_text(_summarize_markdown(profile, pivots, signals, metrics), encoding="utf-8")
    return {"run_dir": str(run_dir), "metrics": asdict(metrics), "profile": profile_to_dict(profile)}


def _grid_values(mode: str) -> dict[str, list[Any]]:
    if mode == "deep":
        return {
            "wave_engine": ["atr_zigzag", "pct_zigzag"],
            "atr_mult": [round(x, 2) for x in [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]],
            "pct_move": [round(x, 4) for x in [0.02, 0.025, 0.03, 0.035, 0.04, 0.045, 0.05]],
            "break_basis": ["wick", "close"],
            "entry_timeframes": [("5m",), ("15m",), ("1h",)],
            "flat_extreme_lookback_hours": [60, 90, 120, 150],
            "pullback_ratio": [0.4, 0.5, 0.6, 0.7, 0.8],
            "max_sl_pct": [0.02, 0.025, 0.03, 0.035, 0.04],
            "tp2_pct": [0.02, 0.025, 0.03, 0.035, 0.04],
            "tp3_pct": [0.04, 0.05, 0.06, 0.07, 0.08],
            "time_stop_hours": [4, 6, 8, 10, 12, 14, 16],
        }
    return {
        "wave_engine": ["atr_zigzag", "pct_zigzag"],
        "atr_mult": [1.5, 2.5, 4.0],
        "pct_move": [0.02, 0.035, 0.05],
        "break_basis": ["wick", "close"],
        "entry_timeframes": [("5m",), ("15m",), ("1h",)],
        "flat_extreme_lookback_hours": [60, 100, 150],
        "pullback_ratio": [0.4, 0.5, 0.65, 0.8],
        "max_sl_pct": [0.02, 0.03, 0.04],
        "tp2_pct": [0.02, 0.03, 0.04],
        "tp3_pct": [0.04, 0.06, 0.08],
        "time_stop_hours": [4, 8, 12, 16],
    }


def _candidate_profiles(mode: str, max_candidates: int, sampling: str, seed: int) -> list[dict[str, Any]]:
    values = _grid_values(mode)
    randomizer = random.Random(seed)
    keys = list(values.keys())
    combos = list(itertools.product(*(values[key] for key in keys))) if sampling == "grid" else None
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    if combos is not None:
        for combo in combos[:max_candidates]:
            seen.add(combo)
            candidates.append(dict(zip(keys, combo)))
        return candidates

    attempts = 0
    max_attempts = max_candidates * 25
    while len(candidates) < max_candidates and attempts < max_attempts:
        attempts += 1
        combo = tuple(randomizer.choice(values[key]) for key in keys)
        if combo in seen:
            continue
        seen.add(combo)
        candidates.append(dict(zip(keys, combo)))
    return candidates


def run_matrix_research(
    dataset_path: str | Path,
    profile_raw: dict[str, Any],
    output_root: str | Path,
    mode: str,
    max_candidates: int,
    sampling: str,
    seed: int,
    run_id: str | None = None,
) -> dict[str, Any]:
    base_profile = profile_to_dict(_normalize_profile(profile_raw))
    candidates = _candidate_profiles(mode, max_candidates=max_candidates, sampling=sampling, seed=seed)
    run_name = run_id or datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = _ensure_run_dir(output_root, run_name)
    _write_json(
        run_dir / "profile.json",
        {
            "base_profile": base_profile,
            "matrix_mode": mode,
            "sampling": sampling,
            "seed": seed,
            "max_candidates": max_candidates,
        },
    )
    _write_json(run_dir / "state.json", {"status": "running", "mode": "matrix", "run_id": run_name, "generated_at": datetime.now(tz=UTC)})

    leaderboard: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        resolved = dict(base_profile)
        resolved.update(candidate)
        result = run_single_research(dataset_path, resolved, run_dir / "candidates", run_id=f"candidate-{index:03d}")
        metrics = result["metrics"]
        leaderboard.append(
            {
                "candidate_id": f"candidate-{index:03d}",
                "profile": resolved,
                "metrics": metrics,
                "run_dir": result["run_dir"],
            }
        )

    leaderboard.sort(
        key=lambda row: (
            row["metrics"]["roi_pct"],
            row["metrics"]["profit_factor"] if row["metrics"]["profit_factor"] is not None else -999.0,
            -row["metrics"]["max_drawdown_pct"],
        ),
        reverse=True,
    )
    best = leaderboard[0] if leaderboard else None
    _write_json(run_dir / "leaderboard.json", leaderboard)
    _write_json(run_dir / "resolved-params.json", best["profile"] if best else base_profile)
    _write_json(run_dir / "metrics.json", best["metrics"] if best else {})
    (run_dir / "SUMMARY.md").write_text(
        "\n".join(
            [
                "# Wave Engine matrix run",
                "",
                f"- Mode: `{mode}`",
                f"- Sampling: `{sampling}`",
                f"- Candidates: **{len(leaderboard)}**",
                f"- Seed: **{seed}**",
                "",
                "## Best candidate",
                "",
                json.dumps(best, indent=2, ensure_ascii=False, default=_json_default) if best else "No candidates generated.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_json(run_dir / "state.json", {"status": "completed", "mode": "matrix", "run_id": run_name, "generated_at": datetime.now(tz=UTC)})
    return {"run_dir": str(run_dir), "leaderboard_size": len(leaderboard), "best": best}
