from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class SummaryMetrics:
    trades: int
    win_rate: float
    profit_factor: float
    expectancy_r: float
    avg_r: float
    roi_total: float
    annualized_return: float
    max_drawdown: float
    tp1_or_more_share: float
    tp2_or_more_share: float
    tp3_share: float
    stop_share: float


def _max_drawdown(equity_curve: list[dict]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]["equity"]
    worst = 0.0
    for x in equity_curve:
        eq = x["equity"]
        peak = max(peak, eq)
        dd = eq / peak - 1.0
        worst = min(worst, dd)
    return worst


def _annualized_from_total(total_return: float, periods: int, bars_per_year: int) -> float:
    if periods <= 0 or bars_per_year <= 0:
        return 0.0
    years = periods / bars_per_year
    if years <= 0:
        return 0.0
    return (1.0 + total_return) ** (1.0 / years) - 1.0


def build_summary(trades: list[dict], equity_curve: list[dict], bars_per_year: int) -> SummaryMetrics:
    if not trades or not equity_curve:
        return SummaryMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    pnls = [t["pnl_net"] for t in trades]
    rs = [t["r_multiple"] for t in trades]
    wins = [p > 0 for p in pnls]
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    pf = (gross_profit / gross_loss) if gross_loss > 0 else 999.0

    eq0 = equity_curve[0]["equity"]
    eqn = equity_curve[-1]["equity"]
    roi = (eqn / eq0 - 1.0) if eq0 > 0 else 0.0

    n = len(trades)
    return SummaryMetrics(
        trades=n,
        win_rate=sum(1 for w in wins if w) / n,
        profit_factor=pf,
        expectancy_r=sum(rs) / n,
        avg_r=sum(rs) / n,
        roi_total=roi,
        annualized_return=_annualized_from_total(roi, len(equity_curve), bars_per_year),
        max_drawdown=_max_drawdown(equity_curve),
        tp1_or_more_share=sum(1 for t in trades if t["tp_hits"] >= 1) / n,
        tp2_or_more_share=sum(1 for t in trades if t["tp_hits"] >= 2) / n,
        tp3_share=sum(1 for t in trades if t["tp_hits"] >= 3) / n,
        stop_share=sum(1 for t in trades if t["stopped"] == 1) / n,
    )


def summary_to_row(summary: SummaryMetrics) -> dict:
    return asdict(summary)
