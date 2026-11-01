"""Locked SOL/BTC daily volatility coefficient; no runtime or money ownership."""
from dataclasses import dataclass
from decimal import Decimal, DecimalException, localcontext, ROUND_HALF_EVEN
from typing import Sequence

DAY_NS = 86_400_000_000_000
RETURN_DAYS = 60


@dataclass(frozen=True)
class PairedDailyClose:
    close_ns: int
    btc_close: str
    sol_close: str


def daily_volatility_coefficient(history: Sequence[PairedDailyClose], *,
                                 decision_ns: int) -> Decimal | None:
    """Last 60 paired simple returns, sample STD(SOL)/sample STD(BTC).

    None means unavailable, including zero BTC volatility. Inputs are exact
    positive close strings at consecutive completed UTC day boundaries.
    No episode, capital, target rounding or native execution state lives here.
    """
    if type(decision_ns) is not int or decision_ns < 0 or len(history) < RETURN_DAYS + 1:
        return None
    if history[-1].close_ns != (decision_ns // DAY_NS) * DAY_NS:
        return None
    previous_ns = None
    for day in history:
        if (type(day.close_ns) is not int or day.close_ns < 0
                or day.close_ns % DAY_NS or day.close_ns > decision_ns
                or previous_ns is not None and day.close_ns <= previous_ns):
            return None
        previous_ns = day.close_ns
    window = history[-(RETURN_DAYS + 1):]
    if any(b.close_ns - a.close_ns != DAY_NS for a, b in zip(window, window[1:])):
        return None
    try:
        with localcontext() as ctx:
            ctx.prec = 50
            ctx.rounding = ROUND_HALF_EVEN
            btc, sol = [], []
            for day in window:
                if type(day.btc_close) is not str or type(day.sol_close) is not str:
                    return None
                b, s = Decimal(day.btc_close), Decimal(day.sol_close)
                if not b.is_finite() or not s.is_finite() or b <= 0 or s <= 0:
                    return None
                btc.append(b)
                sol.append(s)
            def sample_std(prices):
                returns = [b / a - 1 for a, b in zip(prices, prices[1:])]
                mean = sum(returns, Decimal(0)) / RETURN_DAYS
                variance = sum(((r - mean) ** 2 for r in returns), Decimal(0)) / (RETURN_DAYS - 1)
                return variance.sqrt()
            btc_std = sample_std(btc)
            if not btc_std:
                return None
            coefficient = sample_std(sol) / btc_std
            return coefficient if coefficient.is_finite() and coefficient > 0 else None
    except (DecimalException, ValueError):
        return None
