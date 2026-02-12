from __future__ import annotations


def _ema(prev: float | None, value: float, span: int) -> float:
    alpha = 2.0 / (span + 1.0)
    if prev is None:
        return value
    return alpha * value + (1 - alpha) * prev


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


def generate_entry_signal(candles: list[dict], bias: str = "both") -> list[int]:
    """Placeholder entry hook. TODO: replace with exact v1 engulfing/sweep/FVG rules."""
    if bias not in {"long", "short", "both"}:
        raise ValueError("bias must be long|short|both")

    signals = []
    for c in candles:
        long_cond = c["ema_fast"] > c["ema_slow"] and c["ret_1"] > 0
        short_cond = c["ema_fast"] < c["ema_slow"] and c["ret_1"] < 0
        s = 0
        if bias in {"long", "both"} and long_cond:
            s = 1
        if bias in {"short", "both"} and short_cond:
            s = -1
        signals.append(s)
    return signals
