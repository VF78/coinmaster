#!/usr/bin/env python3
"""Explain why the Wave Engine is not currently entering.

Research/dry-run diagnostic helper. Reads local OHLCV + selected profile snapshot and
emits JSON with the latest regime, signal counts, and blocker counters per pair.
It does not mutate config, services, orders, or databases.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
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
    _extreme_context,
    _is_bearish_engulfing,
    _is_bullish_engulfing,
    _segment_start_index,
    build_regime,
    detect_pivots,
    generate_entry_signals,
)
from freqtrade_adapter import load_pair_profile, snapshot_summary  # noqa: E402


def _to_utc(value: str | None, fallback: datetime | None = None) -> datetime | None:
    if value is None:
        return fallback
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


def _frame_to_candles(frame: pd.DataFrame) -> list[Candle]:
    return [
        Candle(
            timestamp=pd.Timestamp(row.date).to_pydatetime().astimezone(UTC),
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(getattr(row, "volume", 0.0) or 0.0),
        )
        for row in frame.itertuples(index=False)
    ]


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


def _diagnose_pair(pair: str, datadir: Path, profile_path: str | None, start: datetime, end: datetime | None, recent_candles: int) -> dict[str, Any]:
    profile = load_pair_profile(pair, profile_path)
    if profile is None:
        return {"pair": pair, "enabled": False, "reason": "pair_not_selected"}

    required_tfs = set(profile.entry_timeframes) | {"4h"}
    candles_by_tf: dict[str, list[Candle]] = {}
    for timeframe in sorted(required_tfs):
        frame = _load_frame(datadir, pair, timeframe, start, end)
        candles_by_tf[timeframe] = _frame_to_candles(frame)
    if len(candles_by_tf.get("4h", [])) < 3:
        return {"pair": pair, "enabled": False, "reason": "insufficient_4h_data"}

    pivots = detect_pivots(candles_by_tf["4h"], profile)
    regimes = build_regime(candles_by_tf["4h"], pivots, profile.break_basis)
    signals = generate_entry_signals(pair, profile, candles_by_tf, regimes)
    latest_regime = regimes[-1] if regimes else None

    by_time = {snapshot.timestamp: snapshot for snapshot in regimes}
    report: dict[str, Any] = {
        "pair": pair,
        "enabled": True,
        "profile": {
            "wave_engine": profile.wave_engine,
            "break_basis": profile.break_basis,
            "entry_timeframes": list(profile.entry_timeframes),
            "pullback_ratio": profile.pullback_ratio,
            "flat_extreme_lookback_hours": profile.flat_extreme_lookback_hours,
            "max_sl_pct": profile.max_sl_pct,
            "tp2_pct": profile.tp2_pct,
            "tp3_pct": profile.tp3_pct,
            "time_stop_hours": profile.time_stop_hours,
        },
        "latest_regime": None if latest_regime is None else {
            "time": _iso(latest_regime.timestamp),
            "state": latest_regime.state,
            "sequence_id": latest_regime.sequence_id,
            "break_count": latest_regime.break_count,
            "last_break_direction": latest_regime.last_break_direction,
            "last_high_price": latest_regime.last_high_price,
            "last_low_price": latest_regime.last_low_price,
            "confirmed_at": _iso(latest_regime.confirmed_at),
        },
        "pivot_count": len(pivots),
        "signal_count_total": len(signals),
        "recent_signals": [
            {
                "time": _iso(signal.timestamp),
                "side": signal.side,
                "timeframe": signal.timeframe,
                "reason": signal.reason,
                "regime_state": signal.regime_state,
                "pullback_ratio": signal.pullback_ratio,
            }
            for signal in signals[-5:]
        ],
        "timeframes": {},
    }

    for timeframe in profile.entry_timeframes:
        candles = candles_by_tf.get(timeframe, [])
        counters: Counter[str] = Counter()
        examples: dict[str, Any] = {}
        if len(candles) < 3:
            report["timeframes"][timeframe] = {"enabled": False, "reason": "insufficient_entry_tf_data", "candles": len(candles)}
            continue

        regime_index = 0
        start_index = max(1, len(candles) - recent_candles)
        used_contexts: set[str] = set()
        for index in range(1, len(candles)):
            candle = candles[index]
            prev = candles[index - 1]
            while regime_index + 1 < len(regimes) and regimes[regime_index + 1].timestamp <= candle.timestamp:
                regime_index += 1
            regime = regimes[regime_index]
            if index < start_index:
                continue

            bullish = _is_bullish_engulfing(prev, candle)
            bearish = _is_bearish_engulfing(prev, candle)
            if bullish:
                counters["bullish_engulfing"] += 1
            if bearish:
                counters["bearish_engulfing"] += 1
            if not bullish and not bearish:
                counters["blocked_no_body_engulfing"] += 1
                continue

            if regime.state == "flat":
                counters["flat_regime_engulfing"] += 1
                lookback_seconds = profile.flat_extreme_lookback_hours * 3600
                window_start = candle.timestamp.timestamp() - lookback_seconds
                lows = [item.low for item in candles[: index + 1] if item.timestamp.timestamp() >= window_start]
                highs = [item.high for item in candles[: index + 1] if item.timestamp.timestamp() >= window_start]
                long_extreme = bool(bullish and lows and min(lows) in (prev.low, candle.low))
                short_extreme = bool(bearish and highs and max(highs) in (prev.high, candle.high))
                if long_extreme or short_extreme:
                    context_id = f"flat:{timeframe}:{regime.sequence_id}"
                    if context_id in used_contexts:
                        counters["blocked_context_already_used"] += 1
                    else:
                        counters["would_signal_flat"] += 1
                        used_contexts.add(context_id)
                        examples.setdefault("latest_would_signal", {"time": _iso(candle.timestamp), "side": "long" if long_extreme else "short", "reason": "flat_extreme"})
                else:
                    counters["blocked_flat_not_at_lookback_extreme"] += 1
                continue

            side = "long" if regime.state == "long" else "short"
            if side == "long" and not bullish:
                counters["blocked_trend_wrong_engulfing_side"] += 1
                continue
            if side == "short" and not bearish:
                counters["blocked_trend_wrong_engulfing_side"] += 1
                continue
            trend_start_index = _segment_start_index(candles, regime.confirmed_at)
            context = _extreme_context(candles, index, trend_start_index, side)
            if not context:
                counters["blocked_no_impulse_correction_context"] += 1
                continue
            _, _, correction_index, pullback = context
            if pullback < profile.pullback_ratio:
                counters["blocked_pullback_too_shallow"] += 1
                examples["latest_shallow_pullback"] = {"time": _iso(candle.timestamp), "side": side, "pullback": round(float(pullback), 4)}
                continue
            if pullback > 0.8:
                counters["blocked_pullback_too_deep"] += 1
                examples["latest_deep_pullback"] = {"time": _iso(candle.timestamp), "side": side, "pullback": round(float(pullback), 4)}
                continue
            context_id = f"trend:{timeframe}:{regime.confirmed_wave_id}:{candles[correction_index].timestamp.isoformat()}"
            if context_id in used_contexts:
                counters["blocked_context_already_used"] += 1
                continue
            used_contexts.add(context_id)
            counters["would_signal_trend"] += 1
            examples.setdefault("latest_would_signal", {"time": _iso(candle.timestamp), "side": side, "reason": "trend_pullback", "pullback": round(float(pullback), 4)})

        latest = candles[-1]
        report["timeframes"][timeframe] = {
            "candles": len(candles),
            "recent_candles_checked": max(0, len(candles) - start_index),
            "latest_candle": {"time": _iso(latest.timestamp), "open": latest.open, "high": latest.high, "low": latest.low, "close": latest.close},
            "blockers": dict(counters),
            "examples": examples,
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Wave Engine no-entry diagnostics.")
    parser.add_argument("--pairs", nargs="+", default=["BTC/USDC:USDC", "ETH/USDC:USDC", "HYPE/USDC:USDC"])
    parser.add_argument("--start", default=(datetime.now(UTC) - timedelta(days=14)).date().isoformat())
    parser.add_argument("--end")
    parser.add_argument("--datadir", default="/freqtrade/user_data/data/hyperliquid")
    parser.add_argument("--profile", default=None)
    parser.add_argument("--recent-candles", type=int, default=300)
    args = parser.parse_args()

    start = _to_utc(args.start)
    if start is None:
        raise RuntimeError("start is required")
    end = _to_utc(args.end)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "start": start.isoformat(),
        "end": end.isoformat() if end else None,
        "snapshot": snapshot_summary(args.profile),
        "pairs": [_diagnose_pair(pair, Path(args.datadir), args.profile, start, end, args.recent_candles) for pair in args.pairs],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
