#!/usr/bin/env python3
"""Export Wave Engine replay JSON from local Freqtrade OHLCV data.

Expected execution environment:
- Freqtrade container or Python env with pandas + freqtrade installed.
- Source tree mounted at /wave-engine-src (or available on sys.path).
- Canonical OHLCV store mounted at /freqtrade/user_data/data/hyperliquid.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from freqtrade.data.history import get_datahandler
from freqtrade.enums import CandleType

SOURCE_ROOT = Path(__file__).resolve().parent
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from engine import (  # noqa: E402
    Candle,
    EntrySignal,
    Pivot,
    RegimeSnapshot,
    WaveEngineProfile,
    _profit_ratio,
    _stop_price,
    _tp1_price,
    build_regime,
    detect_pivots,
    generate_entry_signals,
)
from freqtrade_adapter import load_pair_profile  # noqa: E402


def _to_utc(value: str | None, fallback: datetime | None = None) -> datetime | None:
    if value is None:
        return fallback
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _frame_to_candles(frame: pd.DataFrame) -> list[Candle]:
    candles: list[Candle] = []
    for row in frame.itertuples(index=False):
        candles.append(
            Candle(
                timestamp=pd.Timestamp(row.date).to_pydatetime().astimezone(UTC),
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(getattr(row, "volume", 0.0) or 0.0),
            )
        )
    return candles


def _load_frame(datadir: Path, pair: str, timeframe: str, start: datetime, end: datetime | None) -> pd.DataFrame:
    handler = get_datahandler(datadir, data_format="feather")
    frame = handler.ohlcv_load(pair, timeframe, CandleType.FUTURES, warn_no_data=False)
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], utc=True)
    out = out.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    out = out[out["date"] >= pd.Timestamp(start)]
    if end is not None:
        out = out[out["date"] <= pd.Timestamp(end)]
    return out.reset_index(drop=True)


def _pivot_markers(pivots: list[Pivot]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    markers: list[dict[str, Any]] = []
    waves: list[dict[str, Any]] = []
    for index, pivot in enumerate(pivots):
        direction = "high" if pivot.kind == "high" else "low"
        markers.append(
            {
                "id": f"pivot-{index}",
                "kind": "pivot",
                "time": _iso(pivot.timestamp),
                "price": float(pivot.price),
                "side": direction,
                "label": "Pivot high" if pivot.kind == "high" else "Pivot low",
                "text": f"{pivot.kind} {pivot.price:.2f}",
                "color": "#8da2c6",
                "shape": "square",
            }
        )
        if index == 0:
            continue
        prev = pivots[index - 1]
        waves.append(
            {
                "id": f"wave-{index - 1}-{index}",
                "direction": "up" if pivot.price >= prev.price else "down",
                "startTime": _iso(prev.timestamp),
                "startPrice": float(prev.price),
                "endTime": _iso(pivot.timestamp),
                "endPrice": float(pivot.price),
                "confirmed": True,
                "threshold": float(pivot.threshold),
            }
        )
    return markers, waves


def _regime_markers(regimes: list[RegimeSnapshot]) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    prev_state = "flat"
    prev_sequence = 0
    for snapshot in regimes:
        if snapshot.sequence_id > prev_sequence:
            direction = snapshot.last_break_direction or "up"
            price = snapshot.last_high_price if direction == "up" else snapshot.last_low_price
            markers.append(
                {
                    "id": f"break-{snapshot.sequence_id}",
                    "kind": "structural_break",
                    "time": _iso(snapshot.timestamp),
                    "price": float(price) if price is not None else None,
                    "label": f"Break {snapshot.sequence_id}",
                    "text": f"{direction} / count {snapshot.break_count}",
                    "color": "#f6c85f" if direction == "up" else "#f08a5d",
                    "shape": "circle",
                }
            )
            prev_sequence = snapshot.sequence_id
        if snapshot.state != prev_state:
            markers.append(
                {
                    "id": f"regime-{_iso(snapshot.timestamp)}",
                    "kind": "regime",
                    "time": _iso(snapshot.timestamp),
                    "price": float(snapshot.last_high_price or snapshot.last_low_price or 0.0) or None,
                    "label": f"Regime {snapshot.state}",
                    "text": f"{prev_state} -> {snapshot.state}",
                    "color": "#34d399" if snapshot.state == "long" else ("#f87171" if snapshot.state == "short" else "#7c8aa5"),
                    "shape": "circle",
                    "regimeState": snapshot.state,
                }
            )
            prev_state = snapshot.state
    return markers


def _signal_markers(signals: list[EntrySignal]) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    for index, signal in enumerate(signals):
        markers.append(
            {
                "id": f"entry-{index}",
                "kind": "entry",
                "time": _iso(signal.timestamp),
                "price": float(signal.entry_price),
                "side": signal.side,
                "label": f"Entry {signal.side}",
                "text": f"{signal.timeframe} / {signal.reason}",
                "color": "#22c55e" if signal.side == "long" else "#ef4444",
                "shape": "arrowUp" if signal.side == "long" else "arrowDown",
            }
        )
    return markers


def _detailed_trade_replay(
    pair: str,
    profile: WaveEngineProfile,
    candles_by_tf: dict[str, list[Candle]],
    signals: list[EntrySignal],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    trade_rows: list[dict[str, Any]] = []
    markers: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    next_available_time: datetime | None = None
    by_timestamp: dict[str, dict[datetime, int]] = {
        timeframe: {candle.timestamp: index for index, candle in enumerate(candles)}
        for timeframe, candles in candles_by_tf.items()
    }

    for trade_index, signal in enumerate(signals):
        if next_available_time and signal.timestamp < next_available_time:
            continue
        candles = candles_by_tf.get(signal.timeframe, [])
        entry_index = by_timestamp.get(signal.timeframe, {}).get(signal.timestamp)
        if entry_index is None or entry_index >= len(candles) - 1:
            continue

        trade_id = f"trade-{trade_index + 1}"
        stop_price = float(_stop_price(signal, profile))
        tp1_price = float(_tp1_price(signal, profile))
        tp2_price = float(signal.entry_price * (1.0 + profile.tp2_pct if signal.side == "long" else 1.0 - profile.tp2_pct))
        tp3_price = float(signal.entry_price * (1.0 + profile.tp3_pct if signal.side == "long" else 1.0 - profile.tp3_pct))
        be_price = float(signal.entry_price)
        fractions = [0.34, 0.33, 0.33]
        remaining = 1.0
        realized = 0.0
        tp1_hit = False
        tp2_hit = False
        tp3_hit = False
        exit_reason = "dataset_end"
        exit_price = float(candles[-1].close)
        exit_time = candles[-1].timestamp
        trade_events: list[dict[str, Any]] = []

        for label, price, color in (
            ("SL", stop_price, "#ef4444"),
            ("TP1", tp1_price, "#22c55e"),
            ("TP2", tp2_price, "#10b981"),
            ("TP3", tp3_price, "#34d399"),
        ):
            segments.append(
                {
                    "id": f"{trade_id}-{label.lower()}",
                    "kind": "sl" if label == "SL" else "tp",
                    "label": label,
                    "color": color,
                    "price": price,
                    "startTime": _iso(signal.timestamp),
                    "endTime": _iso(candles[-1].timestamp),
                    "tradeId": trade_id,
                }
            )

        for forward_index in range(entry_index + 1, len(candles)):
            candle = candles[forward_index]
            active_stop = be_price if tp1_hit else stop_price

            if signal.side == "long":
                if candle.low <= active_stop:
                    exit_reason = "breakeven_stop" if tp1_hit else "stoploss"
                    exit_price = active_stop
                    exit_time = candle.timestamp
                    realized += remaining * _profit_ratio(signal.side, signal.entry_price, exit_price)
                    trade_events.append(
                        {
                            "id": f"{trade_id}-exit",
                            "kind": "sl",
                            "time": _iso(candle.timestamp),
                            "price": exit_price,
                            "side": signal.side,
                            "label": "SL hit" if not tp1_hit else "BE stop",
                            "text": exit_reason,
                            "color": "#ef4444",
                            "shape": "arrowDown",
                            "tradeId": trade_id,
                        }
                    )
                    next_available_time = candle.timestamp
                    remaining = 0.0
                    break
                if not tp1_hit and candle.high >= tp1_price:
                    realized += fractions[0] * _profit_ratio(signal.side, signal.entry_price, tp1_price)
                    remaining -= fractions[0]
                    tp1_hit = True
                    trade_events.append(
                        {
                            "id": f"{trade_id}-tp1",
                            "kind": "tp",
                            "time": _iso(candle.timestamp),
                            "price": tp1_price,
                            "side": signal.side,
                            "label": "TP1",
                            "text": "SL -> BE",
                            "color": "#22c55e",
                            "shape": "circle",
                            "tradeId": trade_id,
                        }
                    )
                if tp1_hit and not tp2_hit and candle.high >= tp2_price:
                    realized += fractions[1] * _profit_ratio(signal.side, signal.entry_price, tp2_price)
                    remaining -= fractions[1]
                    tp2_hit = True
                    trade_events.append(
                        {
                            "id": f"{trade_id}-tp2",
                            "kind": "tp",
                            "time": _iso(candle.timestamp),
                            "price": tp2_price,
                            "side": signal.side,
                            "label": "TP2",
                            "text": "Partial",
                            "color": "#10b981",
                            "shape": "circle",
                            "tradeId": trade_id,
                        }
                    )
                if tp2_hit and not tp3_hit and candle.high >= tp3_price:
                    realized += remaining * _profit_ratio(signal.side, signal.entry_price, tp3_price)
                    remaining = 0.0
                    tp3_hit = True
                    exit_reason = "tp3"
                    exit_price = tp3_price
                    exit_time = candle.timestamp
                    trade_events.append(
                        {
                            "id": f"{trade_id}-tp3",
                            "kind": "tp",
                            "time": _iso(candle.timestamp),
                            "price": tp3_price,
                            "side": signal.side,
                            "label": "TP3 / exit",
                            "text": exit_reason,
                            "color": "#34d399",
                            "shape": "arrowDown",
                            "tradeId": trade_id,
                        }
                    )
                    next_available_time = candle.timestamp
                    break
            else:
                if candle.high >= active_stop:
                    exit_reason = "breakeven_stop" if tp1_hit else "stoploss"
                    exit_price = active_stop
                    exit_time = candle.timestamp
                    realized += remaining * _profit_ratio(signal.side, signal.entry_price, exit_price)
                    trade_events.append(
                        {
                            "id": f"{trade_id}-exit",
                            "kind": "sl",
                            "time": _iso(candle.timestamp),
                            "price": exit_price,
                            "side": signal.side,
                            "label": "SL hit" if not tp1_hit else "BE stop",
                            "text": exit_reason,
                            "color": "#ef4444",
                            "shape": "arrowUp",
                            "tradeId": trade_id,
                        }
                    )
                    next_available_time = candle.timestamp
                    remaining = 0.0
                    break
                if not tp1_hit and candle.low <= tp1_price:
                    realized += fractions[0] * _profit_ratio(signal.side, signal.entry_price, tp1_price)
                    remaining -= fractions[0]
                    tp1_hit = True
                    trade_events.append(
                        {
                            "id": f"{trade_id}-tp1",
                            "kind": "tp",
                            "time": _iso(candle.timestamp),
                            "price": tp1_price,
                            "side": signal.side,
                            "label": "TP1",
                            "text": "SL -> BE",
                            "color": "#22c55e",
                            "shape": "circle",
                            "tradeId": trade_id,
                        }
                    )
                if tp1_hit and not tp2_hit and candle.low <= tp2_price:
                    realized += fractions[1] * _profit_ratio(signal.side, signal.entry_price, tp2_price)
                    remaining -= fractions[1]
                    tp2_hit = True
                    trade_events.append(
                        {
                            "id": f"{trade_id}-tp2",
                            "kind": "tp",
                            "time": _iso(candle.timestamp),
                            "price": tp2_price,
                            "side": signal.side,
                            "label": "TP2",
                            "text": "Partial",
                            "color": "#10b981",
                            "shape": "circle",
                            "tradeId": trade_id,
                        }
                    )
                if tp2_hit and not tp3_hit and candle.low <= tp3_price:
                    realized += remaining * _profit_ratio(signal.side, signal.entry_price, tp3_price)
                    remaining = 0.0
                    tp3_hit = True
                    exit_reason = "tp3"
                    exit_price = tp3_price
                    exit_time = candle.timestamp
                    trade_events.append(
                        {
                            "id": f"{trade_id}-tp3",
                            "kind": "tp",
                            "time": _iso(candle.timestamp),
                            "price": tp3_price,
                            "side": signal.side,
                            "label": "TP3 / exit",
                            "text": exit_reason,
                            "color": "#34d399",
                            "shape": "arrowUp",
                            "tradeId": trade_id,
                        }
                    )
                    next_available_time = candle.timestamp
                    break

            hours_held = (candle.timestamp - signal.timestamp).total_seconds() / 3600.0
            if hours_held >= profile.time_stop_hours:
                exit_reason = "time_stop"
                exit_price = float(candle.close)
                exit_time = candle.timestamp
                realized += remaining * _profit_ratio(signal.side, signal.entry_price, exit_price)
                trade_events.append(
                    {
                        "id": f"{trade_id}-time-stop",
                        "kind": "time_stop",
                        "time": _iso(candle.timestamp),
                        "price": exit_price,
                        "side": signal.side,
                        "label": "Time stop",
                        "text": f"{profile.time_stop_hours}h",
                        "color": "#fbbf24",
                        "shape": "circle",
                        "tradeId": trade_id,
                    }
                )
                next_available_time = candle.timestamp
                remaining = 0.0
                break

        segments = [
            {
                **segment,
                "endTime": _iso(exit_time) if segment["tradeId"] == trade_id else segment["endTime"],
            }
            for segment in segments
        ]

        markers.extend(trade_events)
        markers.append(
            {
                "id": f"{trade_id}-entry",
                "kind": "entry",
                "time": _iso(signal.timestamp),
                "price": float(signal.entry_price),
                "side": signal.side,
                "label": f"Trade {trade_index + 1}",
                "text": signal.reason,
                "color": "#22c55e" if signal.side == "long" else "#ef4444",
                "shape": "arrowUp" if signal.side == "long" else "arrowDown",
                "tradeId": trade_id,
            }
        )
        markers.append(
            {
                "id": f"{trade_id}-final-exit",
                "kind": "exit",
                "time": _iso(exit_time),
                "price": float(exit_price),
                "side": signal.side,
                "label": f"Exit {exit_reason}",
                "text": f"PnL {realized:.4f}",
                "color": "#cbd5e1",
                "shape": "circle",
                "tradeId": trade_id,
            }
        )
        trade_rows.append(
            {
                "id": trade_id,
                "pair": pair,
                "timeframe": signal.timeframe,
                "side": signal.side,
                "entryTime": _iso(signal.timestamp),
                "exitTime": _iso(exit_time),
                "entryPrice": float(signal.entry_price),
                "exitPrice": float(exit_price),
                "exitReason": exit_reason,
                "levels": {
                    "stop": stop_price,
                    "tp1": tp1_price,
                    "tp2": tp2_price,
                    "tp3": tp3_price,
                },
                "events": trade_events,
            }
        )
    return trade_rows, markers, segments


def _selected_profile_summary(pair: str, profile: WaveEngineProfile) -> dict[str, Any]:
    return {
        "symbol": pair.split("/", 1)[0],
        "pair": pair,
        "waveEngine": profile.wave_engine,
        "breakBasis": profile.break_basis,
        "entryTimeframe": profile.entry_timeframes[0],
        "pctMove": float(profile.pct_move),
        "atrMult": float(profile.atr_mult),
        "flatExtremeLookbackHours": int(profile.flat_extreme_lookback_hours),
        "pullbackRatio": float(profile.pullback_ratio),
        "impulseSlBuffer": float(profile.impulse_sl_buffer),
        "maxSlPct": float(profile.max_sl_pct),
        "tp1MaxPct": float(profile.tp1_max_pct),
        "tp2Pct": float(profile.tp2_pct),
        "tp3Pct": float(profile.tp3_pct),
        "timeStopHours": int(profile.time_stop_hours),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Wave Engine replay JSON from local Freqtrade OHLCV data.")
    parser.add_argument("--pair", default="BTC/USDC:USDC")
    parser.add_argument("--timeframe", default="5m", choices=["5m", "15m", "1h"])
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end")
    parser.add_argument("--datadir", default="/freqtrade/user_data/data/hyperliquid")
    args = parser.parse_args()

    start = _to_utc(f"{args.start}T00:00:00+00:00")
    end = _to_utc(f"{args.end}T23:59:59+00:00") if args.end else None
    if start is None:
        raise SystemExit("start is required")

    profile = load_pair_profile(args.pair)
    if profile is None:
        raise SystemExit(f"pair is not configured in wave_engine_profiles.selected.json: {args.pair}")

    datadir = Path(args.datadir)
    required_timeframes = sorted(set(profile.entry_timeframes) | {"4h", args.timeframe}, key=lambda value: {"5m": 0, "15m": 1, "1h": 2, "4h": 3}[value])
    frames_by_tf = {
        timeframe: _load_frame(datadir, args.pair, timeframe, start, end)
        for timeframe in required_timeframes
    }
    if any(frame.empty for frame in frames_by_tf.values()):
        missing = [timeframe for timeframe, frame in frames_by_tf.items() if frame.empty]
        raise SystemExit(f"missing ohlcv data for: {', '.join(missing)}")

    candles_by_tf = {timeframe: _frame_to_candles(frame) for timeframe, frame in frames_by_tf.items()}
    pivots = detect_pivots(candles_by_tf["4h"], profile)
    regimes = build_regime(candles_by_tf["4h"], pivots, profile.break_basis)
    signals = generate_entry_signals(args.pair, profile, candles_by_tf, regimes)

    pivot_markers, waves = _pivot_markers(pivots)
    regime_markers = _regime_markers(regimes)
    trades, trade_markers, segments = _detailed_trade_replay(args.pair, profile, candles_by_tf, signals)

    payload = {
        "ok": True,
        "request": {
            "pair": args.pair,
            "timeframe": args.timeframe,
            "start": args.start,
            "end": args.end,
        },
        "dataSource": {
            "kind": "freqtrade_feather",
            "path": str(datadir),
            "note": "Research-only local Freqtrade futures OHLCV store",
        },
        "profile": _selected_profile_summary(args.pair, profile),
        "candles": [
            {
                "timestamp": _iso(candle.timestamp),
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.close),
                "volume": float(candle.volume),
            }
            for candle in candles_by_tf[args.timeframe]
        ],
        "waves": waves,
        "markers": pivot_markers + regime_markers + trade_markers,
        "segments": segments,
        "trades": trades,
        "debug": {
            "pivots": len(pivots),
            "regimes": len(regimes),
            "signals": len(signals),
            "tradeCount": len(trades),
            "timeframesLoaded": required_timeframes,
        },
    }
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
