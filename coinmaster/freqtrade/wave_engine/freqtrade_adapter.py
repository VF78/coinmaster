"""Research-only adapter between Freqtrade dataframes and the Wave Engine prototype."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

try:
    import pandas as pd
except Exception:  # pragma: no cover - local workspace may not have pandas
    pd = None  # type: ignore[assignment]

try:
    from .engine import (
        EntrySignal,
        RegimeSnapshot,
        WaveEngineProfile,
        _stop_price,
        _tp1_price,
        build_regime,
        detect_pivots,
        generate_entry_signals,
        profile_to_dict,
    )
except Exception:  # pragma: no cover - copied flat into temp strategy path
    from engine import (  # type: ignore[no-redef]
        EntrySignal,
        RegimeSnapshot,
        WaveEngineProfile,
        _stop_price,
        _tp1_price,
        build_regime,
        detect_pivots,
        generate_entry_signals,
        profile_to_dict,
    )

BASE_TIMEFRAME = "5m"
INFORMATIVE_TIMEFRAMES = ("15m", "1h", "4h")
PROFILE_PATH = Path(__file__).resolve().with_name("wave_engine_profiles.selected.json")


def _iso_to_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value)
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def _load_snapshot(path: str | Path | None = None) -> dict[str, Any]:
    candidate = Path(path) if path else PROFILE_PATH
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("pairs"), dict):
        raise ValueError(f"invalid Wave Engine profile snapshot: {candidate}")
    return payload


def load_pair_profile(pair: str, path: str | Path | None = None) -> WaveEngineProfile | None:
    snapshot = _load_snapshot(path)
    raw = snapshot["pairs"].get(pair)
    if not isinstance(raw, dict):
        return None
    entry_tf = str(raw.get("entry_timeframe") or raw.get("timeframe") or BASE_TIMEFRAME).strip()
    return WaveEngineProfile(
        symbol=str(raw.get("symbol") or pair),
        direction_tf="4h",
        entry_timeframes=(entry_tf,),
        wave_engine="pct_zigzag" if raw.get("wave_engine") == "pct_zigzag" else "atr_zigzag",
        break_basis="close" if raw.get("break_basis") == "close" else "wick",
        atr_period=int(raw.get("atr_period", 14) or 14),
        atr_mult=float(raw.get("atr_mult", 2.5) or 2.5),
        pct_move=float(raw.get("pct_move", 0.03) or 0.03),
        flat_extreme_lookback_hours=int(raw.get("flat_extreme_lookback_hours", 120) or 120),
        pullback_ratio=float(raw.get("pullback_ratio", 0.5) or 0.5),
        impulse_sl_buffer=float(raw.get("impulse_sl_buffer", 0.0033) or 0.0033),
        max_sl_pct=float(raw.get("max_sl_pct", 0.03) or 0.03),
        tp1_max_pct=float(raw.get("tp1_max_pct", 0.015) or 0.015),
        tp2_pct=float(raw.get("tp2_pct", 0.03) or 0.03),
        tp3_pct=float(raw.get("tp3_pct", 0.06) or 0.06),
        time_stop_hours=int(raw.get("time_stop_hours", 8) or 8),
        stake_per_trade=float(raw.get("stake_per_trade", 1.0) or 1.0),
    )


def snapshot_summary(path: str | Path | None = None) -> dict[str, Any]:
    snapshot = _load_snapshot(path)
    pairs = snapshot["pairs"]
    return {
        "snapshot_path": str(Path(path) if path else PROFILE_PATH),
        "pairs": sorted(pairs.keys()),
        "selected_from": snapshot.get("selected_from"),
        "selected_at": snapshot.get("selected_at"),
        "research_only": bool(snapshot.get("research_only", True)),
    }


def _build_candle_frame(dataframe: Any) -> Any:
    if pd is None:
        raise RuntimeError("pandas is required for native Wave Engine adapter execution")
    frame = dataframe.copy()
    if "date" not in frame:
        raise ValueError("dataframe is missing 'date' column")
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    keep = ["date", "open", "high", "low", "close", "volume"]
    for column in keep:
        if column not in frame:
            raise ValueError(f"dataframe is missing '{column}' column")
    frame = frame[keep].dropna(subset=["date", "open", "high", "low", "close"]).copy()
    frame = frame.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    return frame


def _frame_to_candles(frame: Any) -> list[Any]:
    try:
        from .engine import Candle
    except Exception:  # pragma: no cover - copied flat into temp strategy path
        from engine import Candle  # type: ignore[no-redef]

    candles = []
    for row in frame.itertuples(index=False):
        candles.append(
            Candle(
                timestamp=row.date.to_pydatetime(),
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(getattr(row, "volume", 0.0) or 0.0),
            )
        )
    return candles


def _safe_base_frame(dataframe: Any) -> Any:
    frame = _build_candle_frame(dataframe)
    frame["enter_long"] = 0
    frame["enter_short"] = 0
    frame["exit_long"] = 0
    frame["exit_short"] = 0
    frame["enter_tag"] = ""
    frame["exit_tag"] = ""
    frame["wave_enabled"] = 0
    frame["wave_profile_timeframe"] = ""
    frame["wave_regime_state"] = "flat"
    frame["wave_regime_sequence_id"] = 0
    frame["wave_regime_confirmed_wave_id"] = -1
    frame["wave_signal_long"] = 0
    frame["wave_signal_short"] = 0
    frame["wave_stop_price"] = float("nan")
    frame["wave_tp1_price"] = float("nan")
    frame["wave_tp2_price"] = float("nan")
    frame["wave_tp3_price"] = float("nan")
    frame["wave_time_stop_hours"] = float("nan")
    frame["wave_signal_time"] = ""
    frame["wave_reason"] = ""
    return frame


def _project_regime(base_frame: Any, regimes: list[RegimeSnapshot]) -> Any:
    if pd is None or not regimes:
        return base_frame
    # Only project decision-relevant regime state into the native Freqtrade
    # dataframe.  Sequence / confirmed wave ids are useful debug metadata in
    # replay exports, but they are not used by entry/exit decisions and can
    # legitimately vary with different recursive-analysis startup windows.
    # Keeping them constant here avoids false-positive recursive variance
    # without changing trading behavior.
    regime_frame = pd.DataFrame(
        [
            {
                "date": snapshot.timestamp,
                "wave_regime_state": snapshot.state,
            }
            for snapshot in regimes
        ]
    ).sort_values("date")
    projected = pd.merge_asof(
        base_frame.sort_values("date"),
        regime_frame,
        on="date",
        direction="backward",
        suffixes=("", "_merge"),
    )
    merged = "wave_regime_state_merge"
    if merged in projected:
        projected["wave_regime_state"] = projected[merged].combine_first(projected["wave_regime_state"])
        projected = projected.drop(columns=[merged])
    projected["wave_regime_state"] = projected["wave_regime_state"].fillna("flat")
    projected["wave_regime_sequence_id"] = 0
    projected["wave_regime_confirmed_wave_id"] = -1
    return projected


def compute_pair_research_frame(
    pair: str,
    dataframe: Any,
    get_informative_dataframe: Callable[[str], Any | None],
    profile_path: str | Path | None = None,
) -> tuple[Any, dict[str, dict[str, Any]], dict[str, Any]]:
    if pd is None:
        raise RuntimeError("pandas is required for native Wave Engine adapter execution")
    profile = load_pair_profile(pair, profile_path)
    base_frame = _safe_base_frame(dataframe)
    if profile is None:
        return base_frame, {}, {"pair": pair, "enabled": False, "reason": "pair_not_selected"}

    frames_by_tf = {BASE_TIMEFRAME: _build_candle_frame(dataframe)}
    required_timeframes = set(profile.entry_timeframes) | {"4h"}
    for timeframe in required_timeframes:
        if timeframe == BASE_TIMEFRAME:
            continue
        informative = get_informative_dataframe(timeframe)
        if informative is None or len(informative.index) == 0:
            return base_frame, {}, {"pair": pair, "enabled": False, "reason": f"missing_{timeframe}"}
        frames_by_tf[timeframe] = _build_candle_frame(informative)

    if "4h" not in frames_by_tf or len(frames_by_tf["4h"].index) < 3:
        return base_frame, {}, {"pair": pair, "enabled": False, "reason": "insufficient_4h_data"}

    candles_by_tf = {timeframe: _frame_to_candles(frame) for timeframe, frame in frames_by_tf.items()}
    pivots = detect_pivots(candles_by_tf["4h"], profile)
    regimes = build_regime(candles_by_tf["4h"], pivots, profile.break_basis)
    signals = generate_entry_signals(pair, profile, candles_by_tf, regimes)

    signal_context_by_tag: dict[str, dict[str, Any]] = {}
    base_frame = _project_regime(base_frame, regimes)
    base_frame["wave_enabled"] = 1
    base_frame["wave_profile_timeframe"] = profile.entry_timeframes[0]

    for signal in signals:
        base_mask = base_frame["date"] == pd.Timestamp(signal.timestamp)
        if not bool(base_mask.any()):
            continue
        tag = _signal_tag(signal)
        stop_price = _stop_price(signal, profile)
        tp1_price = _tp1_price(signal, profile)
        tp2_price = signal.entry_price * (1.0 + profile.tp2_pct if signal.side == "long" else 1.0 - profile.tp2_pct)
        tp3_price = signal.entry_price * (1.0 + profile.tp3_pct if signal.side == "long" else 1.0 - profile.tp3_pct)
        signal_context_by_tag[tag] = {
            "pair": pair,
            "side": signal.side,
            "signal_time": signal.timestamp.isoformat(),
            "signal_timeframe": signal.timeframe,
            "entry_price": float(signal.entry_price),
            "stop_price": float(stop_price),
            "tp1_price": float(tp1_price),
            "tp2_price": float(tp2_price),
            "tp3_price": float(tp3_price),
            "time_stop_hours": int(profile.time_stop_hours),
            "profile": profile_to_dict(profile),
            "reason": signal.reason,
            "context_id": signal.context_id,
        }
        side_column = "long" if signal.side == "long" else "short"
        base_frame.loc[base_mask, f"wave_signal_{side_column}"] = 1
        base_frame.loc[base_mask, f"enter_{side_column}"] = 1
        base_frame.loc[base_mask, "enter_tag"] = tag
        base_frame.loc[base_mask, "wave_stop_price"] = float(stop_price)
        base_frame.loc[base_mask, "wave_tp1_price"] = float(tp1_price)
        base_frame.loc[base_mask, "wave_tp2_price"] = float(tp2_price)
        base_frame.loc[base_mask, "wave_tp3_price"] = float(tp3_price)
        base_frame.loc[base_mask, "wave_time_stop_hours"] = int(profile.time_stop_hours)
        base_frame.loc[base_mask, "wave_signal_time"] = signal.timestamp.isoformat()
        base_frame.loc[base_mask, "wave_reason"] = signal.reason

    base_frame.loc[
        (base_frame["wave_regime_state"] == "short") | (base_frame["wave_signal_short"] == 1),
        ["exit_long", "exit_tag"],
    ] = (1, "wave_regime_or_signal_flip")
    base_frame.loc[
        (base_frame["wave_regime_state"] == "long") | (base_frame["wave_signal_long"] == 1),
        ["exit_short", "exit_tag"],
    ] = (1, "wave_regime_or_signal_flip")

    meta = {
        "pair": pair,
        "enabled": True,
        "profile": profile_to_dict(profile),
        "signal_count": len(signals),
        "pivot_count": len(pivots),
        "regime_count": len(regimes),
    }
    return base_frame, signal_context_by_tag, meta


def _signal_tag(signal: EntrySignal) -> str:
    side_code = "L" if signal.side == "long" else "S"
    return f"wave:{side_code}:{signal.timeframe}:{int(signal.timestamp.timestamp())}"
