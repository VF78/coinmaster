from __future__ import annotations

from .config import BacktestConfig
from .risk import compute_stop_distance, size_position


def _apply_round_trip_cost(price: float, cfg: BacktestConfig) -> float:
    return price * 2.0 * (cfg.fee_per_side + cfg.slippage_per_side)


def _record_trade(
    trades: list[dict],
    entry_ts,
    exit_ts,
    side,
    entry_price,
    exit_price,
    entry_qty,
    realized_trade_pnl,
    risk_amount,
    tp_hits,
    stopped,
):
    trades.append(
        {
            "entry_ts": entry_ts.isoformat(),
            "exit_ts": exit_ts.isoformat(),
            "side": side,
            "entry": entry_price,
            "exit": exit_price,
            "qty": entry_qty,
            "pnl_net": realized_trade_pnl,
            "r_multiple": realized_trade_pnl / max(risk_amount, 1e-9),
            "tp_hits": tp_hits,
            "stopped": stopped,
        }
    )


def run_backtest(candles: list[dict], signal: list[int], cfg: BacktestConfig):
    equity = cfg.initial_equity
    day_start_equity = equity
    daily_stop_triggered = False
    current_day = None

    in_pos = False
    pos_side = 0
    pos_qty = 0.0
    entry_qty = 0.0
    entry_idx = -1
    entry_ts = None
    entry_price = 0.0
    risk_amount = 0.0
    stop_price = 0.0
    tp_prices = []
    tp_fractions_left = []
    tp_hits = 0
    realized_trade_pnl = 0.0

    trades = []
    equity_curve = []

    for i, row in enumerate(candles):
        ts = row["timestamp"]
        bar_day = ts.date()
        if current_day != bar_day:
            current_day = bar_day
            day_start_equity = equity
            daily_stop_triggered = False

        if not daily_stop_triggered and equity <= day_start_equity * (1.0 - cfg.daily_hard_stop_dd):
            daily_stop_triggered = True
            if in_pos:
                exit_price = row["close"]
                pnl_gross = pos_side * (exit_price - entry_price) * pos_qty
                pnl_net = pnl_gross - _apply_round_trip_cost(entry_price, cfg) * pos_qty
                realized_trade_pnl += pnl_net
                equity += pnl_net
                _record_trade(
                    trades,
                    entry_ts,
                    ts,
                    pos_side,
                    entry_price,
                    exit_price,
                    entry_qty,
                    realized_trade_pnl,
                    risk_amount,
                    tp_hits,
                    stopped=1,
                )
                in_pos = False

        if in_pos:
            high = row["high"]
            low = row["low"]

            stopped = (low <= stop_price) if pos_side == 1 else (high >= stop_price)
            if stopped:
                exit_price = stop_price
                pnl_gross = pos_side * (exit_price - entry_price) * pos_qty
                pnl_net = pnl_gross - _apply_round_trip_cost(entry_price, cfg) * pos_qty
                realized_trade_pnl += pnl_net
                equity += pnl_net
                _record_trade(
                    trades,
                    entry_ts,
                    ts,
                    pos_side,
                    entry_price,
                    exit_price,
                    entry_qty,
                    realized_trade_pnl,
                    risk_amount,
                    tp_hits,
                    stopped=1,
                )
                in_pos = False
            else:
                # partial take-profits
                for j, tp in enumerate(tp_prices):
                    frac_left = tp_fractions_left[j]
                    if frac_left <= 0:
                        continue
                    hit = (high >= tp) if pos_side == 1 else (low <= tp)
                    if hit:
                        close_qty = min(entry_qty * frac_left, pos_qty)
                        pnl_part = pos_side * (tp - entry_price) * close_qty
                        pnl_part -= _apply_round_trip_cost(entry_price, cfg) * close_qty
                        realized_trade_pnl += pnl_part
                        equity += pnl_part
                        pos_qty -= close_qty
                        tp_fractions_left[j] = 0.0
                        tp_hits += 1

                        # management updates after TP1/TP2
                        if j == 0:
                            # move to breakeven + costs
                            be = entry_price + pos_side * _apply_round_trip_cost(entry_price, cfg)
                            if pos_side == 1:
                                stop_price = max(stop_price, be)
                            else:
                                stop_price = min(stop_price, be)
                        elif j == 1:
                            # simple ATR trailing from current close
                            trail = row["close"] - pos_side * 1.2 * row["atr"]
                            if pos_side == 1:
                                stop_price = max(stop_price, trail)
                            else:
                                stop_price = min(stop_price, trail)

                # full-exit rules for remaining position
                bars_in_trade = i - entry_idx
                reverse_signal = signal[i] == -pos_side
                timeout = bars_in_trade >= cfg.max_bars_in_trade

                if pos_qty > 1e-12 and (reverse_signal or timeout):
                    exit_price = row["close"]
                    pnl_gross = pos_side * (exit_price - entry_price) * pos_qty
                    pnl_net = pnl_gross - _apply_round_trip_cost(entry_price, cfg) * pos_qty
                    realized_trade_pnl += pnl_net
                    equity += pnl_net
                    pos_qty = 0.0

                if pos_qty <= 1e-12:
                    _record_trade(
                        trades,
                        entry_ts,
                        ts,
                        pos_side,
                        entry_price,
                        row["close"],
                        entry_qty,
                        realized_trade_pnl,
                        risk_amount,
                        tp_hits,
                        stopped=0,
                    )
                    in_pos = False

        if (not in_pos) and (not daily_stop_triggered):
            s = signal[i]
            if s != 0:
                entry = row["close"]
                lookback = candles[max(0, i - 12) : i + 1]
                if s == 1:
                    structure_stop = min(x["low"] for x in lookback)
                else:
                    structure_stop = max(x["high"] for x in lookback)

                stop_dist = compute_stop_distance(entry, structure_stop, row["atr"], cfg.atr_buffer_mult, cfg.stop_cap_pct)
                sizing = size_position(equity, cfg.risk_per_trade, entry, stop_dist)
                if sizing.qty > 0:
                    in_pos = True
                    pos_side = s
                    pos_qty = sizing.qty
                    entry_qty = sizing.qty
                    entry_idx = i
                    entry_ts = ts
                    entry_price = entry
                    risk_amount = sizing.risk_amount
                    stop_price = entry - stop_dist if s == 1 else entry + stop_dist
                    tp_prices = [
                        entry + s * cfg.tp1_r * stop_dist,
                        entry + s * cfg.tp2_r * stop_dist,
                        entry + s * cfg.tp3_r * stop_dist,
                    ]
                    tp_fractions_left = [cfg.tp1_fraction, cfg.tp2_fraction, cfg.tp3_fraction]
                    tp_hits = 0
                    realized_trade_pnl = 0.0

        equity_curve.append({"timestamp": ts.isoformat(), "equity": equity})

    return trades, equity_curve
