from __future__ import annotations

from datetime import datetime, timedelta


def _ema(prev: float | None, value: float, span: int) -> float:
    alpha = 2.0 / (span + 1.0)
    if prev is None:
        return value
    return alpha * value + (1 - alpha) * prev


def _floor_bucket(ts: datetime, interval_min: int) -> datetime:
    minute = (ts.minute // interval_min) * interval_min
    return ts.replace(minute=minute, second=0, microsecond=0)


def _resample(candles: list[dict], interval_min: int) -> list[dict]:
    out: list[dict] = []
    cur = None
    cur_bucket = None

    for c in candles:
        b = _floor_bucket(c["timestamp"], interval_min)
        if cur_bucket != b:
            if cur is not None:
                out.append(cur)
            cur_bucket = b
            cur = {
                "timestamp": b,
                "end_ts": c["timestamp"],
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
                "volume": c["volume"],
            }
        else:
            cur["high"] = max(cur["high"], c["high"])
            cur["low"] = min(cur["low"], c["low"])
            cur["close"] = c["close"]
            cur["volume"] += c["volume"]
            cur["end_ts"] = c["timestamp"]

    if cur is not None:
        out.append(cur)
    return out


def attach_features(candles: list[dict], atr_period: int = 14) -> list[dict]:
    out = []
    ema_fast = None
    ema_slow = None
    tr_window = []
    prev_close = None

    for c in candles:
        tr = c["high"] - c["low"]
        if prev_close is not None:
            tr = max(tr, abs(c["high"] - prev_close), abs(c["low"] - prev_close))
        tr_window.append(tr)
        if len(tr_window) > atr_period:
            tr_window.pop(0)
        atr = sum(tr_window) / len(tr_window)

        ema_fast = _ema(ema_fast, c["close"], 20)
        ema_slow = _ema(ema_slow, c["close"], 100)
        ret_1 = 0.0 if prev_close is None else (c["close"] / prev_close - 1.0)

        item = dict(c)
        item.update({"atr": atr, "ema_fast": ema_fast, "ema_slow": ema_slow, "ret_1": ret_1})
        out.append(item)
        prev_close = c["close"]

    return out


def _engulf_sweep_signals(tf: list[dict], sweep_lookback: int) -> tuple[set[datetime], set[datetime]]:
    long_ts: set[datetime] = set()
    short_ts: set[datetime] = set()

    for i in range(1, len(tf)):
        prev = tf[i - 1]
        cur = tf[i]
        hist = tf[max(0, i - sweep_lookback) : i]
        if not hist:
            continue

        local_low = min(x["low"] for x in hist)
        local_high = max(x["high"] for x in hist)

        bull_engulf = (
            cur["close"] > cur["open"]
            and prev["close"] < prev["open"]
            and cur["close"] >= prev["open"]
            and cur["open"] <= prev["close"]
        )
        bear_engulf = (
            cur["close"] < cur["open"]
            and prev["close"] > prev["open"]
            and cur["close"] <= prev["open"]
            and cur["open"] >= prev["close"]
        )

        sweep_low_cur = cur["low"] < local_low
        sweep_low_prev = prev["low"] < local_low
        sweep_high_cur = cur["high"] > local_high
        sweep_high_prev = prev["high"] > local_high

        if bull_engulf and (sweep_low_cur or sweep_low_prev):
            long_ts.add(cur["end_ts"])
        if bear_engulf and (sweep_high_cur or sweep_high_prev):
            short_ts.add(cur["end_ts"])

    return long_ts, short_ts


def _fvg_inversion_signals(
    tf: list[dict],
    min_gap_pct: float,
    retest_window_bars: int,
    inversion_lookahead_bars: int = 96,
) -> tuple[set[datetime], set[datetime]]:
    long_ts: set[datetime] = set()
    short_ts: set[datetime] = set()

    n = len(tf)
    for i in range(2, n):
        a = tf[i - 2]
        c = tf[i]

        # bearish FVG (gap down): possible long inversion when price reclaims above zone upper
        gap_down = a["low"] - c["high"]
        if gap_down > 0 and (gap_down / max(1e-9, a["close"])) >= min_gap_pct:
            zone_upper = a["low"]
            j_end = min(n, i + 1 + inversion_lookahead_bars)
            inv_idx = None
            for j in range(i + 1, j_end):
                if tf[j]["close"] > zone_upper:
                    inv_idx = j
                    break
            if inv_idx is not None:
                r_end = min(n, inv_idx + 1 + retest_window_bars)
                for k in range(inv_idx + 1, r_end):
                    if tf[k]["low"] <= zone_upper and tf[k]["close"] > zone_upper:
                        long_ts.add(tf[k]["end_ts"])
                        break

        # bullish FVG (gap up): possible short inversion when price loses zone lower
        gap_up = c["low"] - a["high"]
        if gap_up > 0 and (gap_up / max(1e-9, a["close"])) >= min_gap_pct:
            zone_lower = a["high"]
            j_end = min(n, i + 1 + inversion_lookahead_bars)
            inv_idx = None
            for j in range(i + 1, j_end):
                if tf[j]["close"] < zone_lower:
                    inv_idx = j
                    break
            if inv_idx is not None:
                r_end = min(n, inv_idx + 1 + retest_window_bars)
                for k in range(inv_idx + 1, r_end):
                    if tf[k]["high"] >= zone_lower and tf[k]["close"] < zone_lower:
                        short_ts.add(tf[k]["end_ts"])
                        break

    return long_ts, short_ts


def generate_entry_signal(
    candles: list[dict],
    bias: str = "both",
    sweep_lookback: int = 6,
    fvg_min_gap_pct: float = 0.00025,
    fvg_retest_window_bars: int = 8,
) -> list[int]:
    """
    v1 entry implementation (approximation of requested discretionary logic):
    - Engulfing + local sweep on 5m/15m/1H
    - Fallback: FVG inversion + retest on 1H/4H

    TODO (v1.1): tighten exact ICT/FVG definitions after manual label validation.
    """
    if bias not in {"long", "short", "both"}:
        raise ValueError("bias must be long|short|both")

    tf_5 = _resample(candles, 5)
    tf_15 = _resample(candles, 15)
    tf_60 = _resample(candles, 60)
    tf_240 = _resample(candles, 240)

    long_ts: set[datetime] = set()
    short_ts: set[datetime] = set()

    for tf in (tf_5, tf_15, tf_60):
        l, s = _engulf_sweep_signals(tf, sweep_lookback=sweep_lookback)
        long_ts.update(l)
        short_ts.update(s)

    for tf in (tf_60, tf_240):
        l, s = _fvg_inversion_signals(
            tf,
            min_gap_pct=fvg_min_gap_pct,
            retest_window_bars=fvg_retest_window_bars,
        )
        long_ts.update(l)
        short_ts.update(s)

    signals: list[int] = []
    for c in candles:
        ts = c["timestamp"]
        l = ts in long_ts
        s = ts in short_ts

        sig = 0
        if l and not s and bias in {"long", "both"}:
            sig = 1
        elif s and not l and bias in {"short", "both"}:
            sig = -1
        elif l and s:
            sig = 0
        signals.append(sig)

    return signals
