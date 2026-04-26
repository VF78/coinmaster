# flake8: noqa: F401
# isort: skip_file
"""
CoinMasterStrategy — Stage 1 Freqtrade port baseline.

This strategy intentionally keeps execution/backtest/hyperopt inside native
Freqtrade. It ports the current CoinMaster Trading Rules core:

- body engulfing + liquidity sweep
- FVG retrace baseline
- ADX / EMA regime guard
- ATR impulse quality guard
- expected R:R guard
- leverage and stake sizing callbacks
- time-stop exit

Manual confirmation is deliberately not implemented.
"""

from __future__ import annotations

from datetime import datetime
from functools import reduce
from typing import Optional

import numpy as np
import pandas as pd
from pandas import DataFrame

import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import DecimalParameter, IntParameter, IStrategy


class CoinMasterStrategy(IStrategy):
    INTERFACE_VERSION = 3

    can_short = True
    timeframe = "15m"
    process_only_new_candles = True
    startup_candle_count = 240

    # CoinMaster manages exits by explicit SL/TP/time-stop logic, not static ROI.
    minimal_roi = {"0": 100}
    stoploss = -0.02
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Current optimized/default CoinMaster-style params. These are intentionally
    # hyperoptable where Freqtrade supports it cleanly.
    engulfing_lookback = IntParameter(10, 120, default=70, space="buy")
    fvg_retrace = DecimalParameter(20, 80, decimals=0, default=60, space="buy")
    fvg_min_width_pct = DecimalParameter(0, 2, decimals=2, default=1.0, space="buy")
    adx_min = DecimalParameter(0, 40, decimals=1, default=0.0, space="buy")
    min_impulse_atr = DecimalParameter(0, 2, decimals=2, default=0.0, space="buy")
    min_expected_rr = DecimalParameter(0, 5, decimals=2, default=0.0, space="buy")
    time_stop_bars = IntParameter(0, 96, default=10, space="sell")

    # Non-hyperopt runtime defaults matching current CoinMaster intent.
    max_leverage_value = 10.0
    risk_per_trade_pct = 3.0
    exit_close_pct = 80.0
    tp_levels_pct = (1.0, 2.0, 7.0)
    sl_pct = 2.0

    plot_config = {
        "main_plot": {
            "ema_fast": {"color": "orange"},
            "ema_slow": {"color": "blue"},
            "fvg_top": {"color": "rgba(0, 180, 0, 0.5)"},
            "fvg_bottom": {"color": "rgba(180, 0, 0, 0.5)"},
        },
        "subplots": {
            "Regime": {"adx": {"color": "white"}},
            "Volatility": {"atr": {"color": "yellow"}, "body_atr": {"color": "purple"}},
        },
    }

    @staticmethod
    def _body_top(dataframe: DataFrame) -> pd.Series:
        return dataframe[["open", "close"]].max(axis=1)

    @staticmethod
    def _body_bottom(dataframe: DataFrame) -> pd.Series:
        return dataframe[["open", "close"]].min(axis=1)

    @staticmethod
    def _expected_rr(close: pd.Series, side: str, sl_pct: float, tp_levels_pct: tuple[float, ...]) -> pd.Series:
        risk = close * (sl_pct / 100.0)
        if len(tp_levels_pct) == 0:
            return pd.Series(0.0, index=close.index)
        avg_reward_pct = sum(tp_levels_pct) / len(tp_levels_pct)
        reward = close * (avg_reward_pct / 100.0)
        return reward / risk.replace(0, np.nan)

    @staticmethod
    def _annotate_fvg(dataframe: DataFrame, lookback: int, retrace_pct: float, min_width_pct: float) -> DataFrame:
        """Annotate latest qualifying FVG zone per row.

        This is a first native-Freqtrade baseline of CoinMaster's FVG logic.
        It keeps the signal inside the dataframe so backtesting/hyperopt stay
        reproducible. HTF/informative refinement belongs to follow-up work in
        issue #65, not to a separate engine.
        """
        n = len(dataframe)
        fvg_dir = np.zeros(n, dtype=int)
        fvg_top = np.full(n, np.nan)
        fvg_bottom = np.full(n, np.nan)
        fvg_trigger = np.full(n, np.nan)
        fvg_width_pct = np.full(n, np.nan)

        highs = dataframe["high"].to_numpy(dtype=float)
        lows = dataframe["low"].to_numpy(dtype=float)
        closes = dataframe["close"].to_numpy(dtype=float)

        for i in range(2, n):
            start = max(2, i - lookback + 1)
            latest = None
            for j in range(start, i + 1):
                c0_high = highs[j - 2]
                c0_low = lows[j - 2]
                c2_high = highs[j]
                c2_low = lows[j]

                if c0_high < c2_low:
                    bottom = c0_high
                    top = c2_low
                    width = top - bottom
                    ref = max(abs((top + bottom) / 2), np.finfo(float).eps)
                    width_pct = width / ref * 100
                    if width_pct >= min_width_pct:
                        latest = (1, top, bottom, width_pct)

                if c0_low > c2_high:
                    bottom = c2_high
                    top = c0_low
                    width = top - bottom
                    ref = max(abs((top + bottom) / 2), np.finfo(float).eps)
                    width_pct = width / ref * 100
                    if width_pct >= min_width_pct:
                        latest = (-1, top, bottom, width_pct)

            if latest is None:
                continue
            direction, top, bottom, width_pct = latest
            width = top - bottom
            trigger = top - width * (retrace_pct / 100.0) if direction == 1 else bottom + width * (retrace_pct / 100.0)
            price = closes[i]
            retraced = (bottom <= price <= trigger) if direction == 1 else (trigger <= price <= top)
            if retraced:
                fvg_dir[i] = direction
                fvg_top[i] = top
                fvg_bottom[i] = bottom
                fvg_trigger[i] = trigger
                fvg_width_pct[i] = width_pct

        dataframe["fvg_dir"] = fvg_dir
        dataframe["fvg_top"] = fvg_top
        dataframe["fvg_bottom"] = fvg_bottom
        dataframe["fvg_trigger"] = fvg_trigger
        dataframe["fvg_width_pct"] = fvg_width_pct
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=55)
        dataframe["ema_slow_slope"] = dataframe["ema_slow"] - dataframe["ema_slow"].shift(3)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        body_top = self._body_top(dataframe)
        body_bottom = self._body_bottom(dataframe)
        prev_body_top = body_top.shift(1)
        prev_body_bottom = body_bottom.shift(1)

        dataframe["bullish_body_engulf"] = (
            (dataframe["close"] > dataframe["open"])
            & (body_bottom <= prev_body_bottom)
            & (body_top >= prev_body_top)
        )
        dataframe["bearish_body_engulf"] = (
            (dataframe["close"] < dataframe["open"])
            & (body_bottom <= prev_body_bottom)
            & (body_top >= prev_body_top)
        )

        lookback = int(self.engulfing_lookback.value)
        history_low = dataframe["low"].shift(2).rolling(lookback).min()
        history_high = dataframe["high"].shift(2).rolling(lookback).max()
        pair_low = pd.concat([dataframe["low"].shift(1), dataframe["low"]], axis=1).min(axis=1)
        pair_high = pd.concat([dataframe["high"].shift(1), dataframe["high"]], axis=1).max(axis=1)

        dataframe["sweep_low"] = pair_low < history_low
        dataframe["sweep_high"] = pair_high > history_high
        dataframe["engulf_long"] = dataframe["bullish_body_engulf"] & dataframe["sweep_low"]
        dataframe["engulf_short"] = dataframe["bearish_body_engulf"] & dataframe["sweep_high"]

        dataframe["body_atr"] = (dataframe["close"] - dataframe["open"]).abs() / dataframe["atr"].replace(0, np.nan)
        candle_range = (dataframe["high"] - dataframe["low"]).replace(0, np.nan)
        dataframe["close_position"] = (dataframe["close"] - dataframe["low"]) / candle_range

        dataframe["regime_long"] = (
            (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["ema_slow_slope"] >= 0)
            & (dataframe["adx"] >= float(self.adx_min.value))
        )
        dataframe["regime_short"] = (
            (dataframe["ema_fast"] < dataframe["ema_slow"])
            & (dataframe["ema_slow_slope"] <= 0)
            & (dataframe["adx"] >= float(self.adx_min.value))
        )

        dataframe["expected_rr"] = self._expected_rr(dataframe["close"], "long", self.sl_pct, self.tp_levels_pct)
        dataframe = self._annotate_fvg(
            dataframe,
            lookback=10,
            retrace_pct=float(self.fvg_retrace.value),
            min_width_pct=float(self.fvg_min_width_pct.value),
        )
        return dataframe

    def _common_entry_guards(self, dataframe: DataFrame, side: str) -> list[pd.Series]:
        if side == "long":
            close_quality = dataframe["close_position"] >= 0.75
            regime = dataframe["regime_long"]
        else:
            close_quality = dataframe["close_position"] <= 0.25
            regime = dataframe["regime_short"]
        return [
            dataframe["volume"] > 0,
            regime,
            dataframe["body_atr"].fillna(0) >= float(self.min_impulse_atr.value),
            close_quality.fillna(False),
            dataframe["expected_rr"].fillna(0) >= float(self.min_expected_rr.value),
        ]

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        long_signal = dataframe["engulf_long"] | (dataframe["fvg_dir"] == 1)
        short_signal = dataframe["engulf_short"] | (dataframe["fvg_dir"] == -1)

        long_conditions = [long_signal] + self._common_entry_guards(dataframe, "long")
        short_conditions = [short_signal] + self._common_entry_guards(dataframe, "short")

        dataframe.loc[reduce(lambda x, y: x & y, long_conditions), ["enter_long", "enter_tag"]] = (1, "coinmaster_long")
        dataframe.loc[reduce(lambda x, y: x & y, short_conditions), ["enter_short", "enter_tag"]] = (1, "coinmaster_short")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe["engulf_short"]) & (dataframe["volume"] > 0), ["exit_long", "exit_tag"]] = (1, "opposite_engulf")
        dataframe.loc[(dataframe["engulf_long"]) & (dataframe["volume"] > 0), ["exit_short", "exit_tag"]] = (1, "opposite_engulf")
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs):
        bars = int(self.time_stop_bars.value)
        if bars > 0:
            elapsed = current_time - trade.open_date_utc
            timeframe_minutes = 15
            if elapsed.total_seconds() >= bars * timeframe_minutes * 60 and current_profit <= 0:
                return "time_stop_no_follow_through"
        return None

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        # Freqtrade clamps returned stake into [min_stake, max_stake]. Use a
        # simple risk-per-trade cap as Stage 1 baseline and let Freqtrade own
        # wallet/available-capital accounting.
        total = self.wallets.get_total_stake_amount() if self.wallets else max_stake
        risk_stake = total * (self.risk_per_trade_pct / max(self.sl_pct, 0.01)) / 100.0
        return min(proposed_stake, risk_stake, max_stake)

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, side: str,
                 **kwargs) -> float:
        return float(min(self.max_leverage_value, max_leverage))
