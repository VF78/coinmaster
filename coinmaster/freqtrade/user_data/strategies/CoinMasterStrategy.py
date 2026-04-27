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
- leverage and stake sizing callbacks
- time-stop exit

Manual confirmation is deliberately not implemented.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from functools import reduce
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from pandas import DataFrame

import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import DecimalParameter, IntParameter, IStrategy, stoploss_from_open


logger = logging.getLogger(__name__)


class CoinMasterStrategy(IStrategy):
    INTERFACE_VERSION = 3

    can_short = True
    timeframe = "15m"
    process_only_new_candles = True
    startup_candle_count = 240

    # CoinMaster manages exits by explicit SL/TP/time-stop logic, not static ROI.
    minimal_roi = {"0": 100}
    stoploss = -0.99
    use_custom_stoploss = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    position_adjustment_enable = True
    max_entry_position_adjustment = 0

    # Current optimized/default CoinMaster-style params. These are intentionally
    # hyperoptable where Freqtrade supports it cleanly.
    engulfing_lookback = IntParameter(10, 120, default=70, space="buy")
    fvg_retrace = DecimalParameter(20, 80, decimals=0, default=60, space="buy")
    fvg_min_width_pct = DecimalParameter(0, 2, decimals=2, default=1.0, space="buy")
    adx_min = DecimalParameter(0, 40, decimals=1, default=0.0, space="buy")
    min_impulse_atr = DecimalParameter(0, 2, decimals=2, default=0.0, space="buy")
    time_stop_bars = IntParameter(0, 96, default=10, space="sell")

    # Non-hyperopt runtime defaults matching current CoinMaster intent.
    max_leverage_value = 10.0
    risk_per_trade_pct = 3.0
    exit_close_pct = 80.0
    tp_levels_pct = (1.0, 2.0, 7.0)
    sl_pct = 2.0

    runtime_rules_path = Path("/freqtrade/user_data/runtime/trading_rules.json")
    fallback_runtime_rules_path = Path(__file__).resolve().parents[1] / "runtime" / "trading_rules.json"

    @property
    def protections(self) -> list[dict[str, object]]:
        """Native Freqtrade risk locks for Stage 1.

        These replace the legacy CoinMaster daily-drawdown UI/watchdog with
        Freqtrade's own lock/protection machinery so FreqUI/API can surface the
        resulting locks without a second execution engine.
        """
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 1},
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 96,
                "trade_limit": 3,
                "stop_duration_candles": 16,
                "required_profit": 0.0,
                "only_per_pair": False,
                "only_per_side": False,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 96,
                "trade_limit": 5,
                "stop_duration_candles": 16,
                "max_allowed_drawdown": 0.10,
                "calculation_mode": "equity",
            },
            {
                "method": "LowProfitPairs",
                "lookback_period_candles": 96,
                "trade_limit": 4,
                "stop_duration_candles": 16,
                "required_profit": -0.03,
                "only_per_pair": True,
                "only_per_side": False,
            },
        ]

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

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._runtime_rules_mtime: float | None = None
        self._runtime_strategy_params: dict[str, object] = {}
        self._refresh_runtime_rules(force=True)

    def _runtime_number(self, key: str, default: float) -> float:
        value = self._runtime_strategy_params.get(key)
        try:
            number = float(value)
        except (TypeError, ValueError):
            return float(default)
        return number if np.isfinite(number) else float(default)

    def _runtime_int(self, key: str, default: int) -> int:
        return int(round(self._runtime_number(key, float(default))))

    def _runtime_tuple(self, key: str, default: tuple[float, ...]) -> tuple[float, ...]:
        value = self._runtime_strategy_params.get(key)
        if not isinstance(value, list):
            return default
        result: list[float] = []
        for item in value[:3]:
            try:
                number = float(item)
            except (TypeError, ValueError):
                continue
            if np.isfinite(number) and number > 0:
                result.append(number)
        return tuple(result) if result else default

    def _runtime_bool(self, key: str, default: bool = False) -> bool:
        value = self._runtime_strategy_params.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        if isinstance(value, (int, float)):
            return bool(value)
        return default

    @staticmethod
    def _tp_current_exit_fraction(level_count: int, completed_exits: int) -> float:
        """Return the fraction of the *current remaining* position to exit.

        Trading Rules semantics:
        - 1 TP  -> close 100% at TP1.
        - 2 TPs -> close 50% at TP1, then 100% of the remainder at TP2.
        - 3 TPs -> close 34% at TP1, 33% of original at TP2, remainder at TP3.

        Freqtrade partial exits work on current `trade.stake_amount`, which is
        reduced after every filled partial exit. Therefore TP2 in the 3-level
        plan closes 33 / 66 = 50% of the remaining stake.
        """
        if level_count <= 1:
            return 1.0
        if level_count == 2:
            return 0.5 if completed_exits == 0 else 1.0
        if completed_exits == 0:
            return 0.34
        if completed_exits == 1:
            return 0.5
        return 1.0

    @staticmethod
    def _price_move_pct(trade: Trade, current_rate: float) -> float:
        open_rate = float(trade.open_rate or 0.0)
        rate = float(current_rate or 0.0)
        if open_rate <= 0 or rate <= 0:
            return 0.0
        if trade.is_short:
            return (open_rate - rate) / open_rate * 100.0
        return (rate - open_rate) / open_rate * 100.0

    def _refresh_runtime_rules(self, force: bool = False) -> None:
        path = self.runtime_rules_path if self.runtime_rules_path.exists() else self.fallback_runtime_rules_path
        if not path.exists():
            return

        try:
            stat = path.stat()
            if not force and self._runtime_rules_mtime == stat.st_mtime:
                return
            payload = json.loads(path.read_text(encoding="utf-8"))
            params = payload.get("freqtrade", {}).get("strategy_params", {})
            if not isinstance(params, dict):
                return
            self._runtime_strategy_params = params
            self._runtime_rules_mtime = stat.st_mtime
            logger.info("Loaded CoinMaster runtime Trading Rules from %s", path)
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            logger.warning("Could not load CoinMaster runtime Trading Rules from %s: %s", path, exc)

    def bot_loop_start(self, current_time: datetime, **kwargs) -> None:
        # Freqtrade-native hook: keep operator Trading Rules hot-reloadable
        # without introducing a second execution engine.
        self._refresh_runtime_rules()

    @staticmethod
    def _body_top(dataframe: DataFrame) -> pd.Series:
        return dataframe[["open", "close"]].max(axis=1)

    @staticmethod
    def _body_bottom(dataframe: DataFrame) -> pd.Series:
        return dataframe[["open", "close"]].min(axis=1)

    @staticmethod
    def _annotate_fvg(
        dataframe: DataFrame,
        lookback: int,
        retrace_pct: float,
        min_width_pct: float,
        require_sweep: bool,
        sweep_lookback: int,
        require_first_touch: bool,
        max_zone_age: int,
    ) -> DataFrame:
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

                sweep_start = max(0, j - 2 - sweep_lookback)
                sweep_history_high = np.nanmax(highs[sweep_start:j - 2]) if j - 2 > sweep_start else np.nan
                sweep_history_low = np.nanmin(lows[sweep_start:j - 2]) if j - 2 > sweep_start else np.nan
                impulse_low = np.nanmin(lows[j - 2:j + 1])
                impulse_high = np.nanmax(highs[j - 2:j + 1])
                swept_low = np.isfinite(sweep_history_low) and impulse_low < sweep_history_low
                swept_high = np.isfinite(sweep_history_high) and impulse_high > sweep_history_high

                if c0_high < c2_low:
                    bottom = c0_high
                    top = c2_low
                    width = top - bottom
                    ref = max(abs((top + bottom) / 2), np.finfo(float).eps)
                    width_pct = width / ref * 100
                    if width_pct >= min_width_pct and (not require_sweep or swept_low):
                        latest = (1, top, bottom, width_pct, j)

                if c0_low > c2_high:
                    bottom = c2_high
                    top = c0_low
                    width = top - bottom
                    ref = max(abs((top + bottom) / 2), np.finfo(float).eps)
                    width_pct = width / ref * 100
                    if width_pct >= min_width_pct and (not require_sweep or swept_high):
                        latest = (-1, top, bottom, width_pct, j)

            if latest is None:
                continue
            direction, top, bottom, width_pct, completion_index = latest
            width = top - bottom
            trigger = top - width * (retrace_pct / 100.0) if direction == 1 else bottom + width * (retrace_pct / 100.0)
            price = closes[i]
            retraced = (bottom <= price <= trigger) if direction == 1 else (trigger <= price <= top)
            if retraced:
                if require_first_touch:
                    # Reject zones that were touched before the current candle,
                    # and reject zones older than the configured max age.
                    zone_age = i - completion_index
                    if zone_age > max_zone_age:
                        continue
                    prior_lows = lows[completion_index + 1:i]
                    prior_highs = highs[completion_index + 1:i]
                    if len(prior_lows) > 0 and np.any((prior_lows <= top) & (prior_highs >= bottom)):
                        continue
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
        self._refresh_runtime_rules()
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

        lookback = self._runtime_int("engulfing_lookback", int(self.engulfing_lookback.value))
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

        regime_enabled = self._runtime_bool("regime_filter_enabled", True)
        adx_enabled = self._runtime_bool("adx_enabled", False)
        adx_min = self._runtime_number("adx_min", float(self.adx_min.value)) if adx_enabled else 0.0
        dataframe["regime_long"] = True if not regime_enabled else (
            (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["ema_slow_slope"] >= 0)
            & (dataframe["adx"] >= adx_min)
        )
        dataframe["regime_short"] = True if not regime_enabled else (
            (dataframe["ema_fast"] < dataframe["ema_slow"])
            & (dataframe["ema_slow_slope"] <= 0)
            & (dataframe["adx"] >= adx_min)
        )

        dataframe = self._annotate_fvg(
            dataframe,
            lookback=self._runtime_int("max_zone_age_candles", 10),
            retrace_pct=self._runtime_number("fvg_retrace", float(self.fvg_retrace.value)),
            min_width_pct=self._runtime_number("fvg_min_width_pct", float(self.fvg_min_width_pct.value)),
            require_sweep=self._runtime_bool("fvg_require_sweep", False),
            sweep_lookback=self._runtime_int("fvg_sweep_lookback_candles", 20),
            require_first_touch=self._runtime_bool("fvg_require_first_touch", False),
            max_zone_age=self._runtime_int("max_zone_age_candles", 12),
        )
        return dataframe

    def _common_entry_guards(self, dataframe: DataFrame, side: str) -> list[pd.Series]:
        if side == "long":
            close_quality = dataframe["close_position"] >= 0.75
            regime = dataframe["regime_long"]
        else:
            close_quality = dataframe["close_position"] <= 0.25
            regime = dataframe["regime_short"]
        min_impulse_atr = (
            self._runtime_number("min_impulse_atr", float(self.min_impulse_atr.value))
            if self._runtime_bool("min_impulse_atr_enabled", False)
            else 0.0
        )
        return [
            dataframe["volume"] > 0,
            regime,
            dataframe["body_atr"].fillna(0) >= min_impulse_atr,
            close_quality.fillna(False),
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
        self._refresh_runtime_rules()
        exit_enabled = self._runtime_number("exit_close_pct", self.exit_close_pct) > 0
        exit_timeframes = self._runtime_strategy_params.get("emergency_exit_timeframes")
        timeframe_enabled = not isinstance(exit_timeframes, list) or self.timeframe in exit_timeframes
        if exit_enabled and timeframe_enabled:
            dataframe.loc[(dataframe["engulf_short"]) & (dataframe["volume"] > 0), ["exit_long", "exit_tag"]] = (1, "opposite_engulf")
            dataframe.loc[(dataframe["engulf_long"]) & (dataframe["volume"] > 0), ["exit_short", "exit_tag"]] = (1, "opposite_engulf")
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs):
        self._refresh_runtime_rules()
        bars = self._runtime_int("time_stop_bars", int(self.time_stop_bars.value)) if self._runtime_bool("time_stop_enabled", False) else 0
        if bars > 0:
            elapsed = current_time - trade.open_date_utc
            timeframe_minutes = 15
            if elapsed.total_seconds() >= bars * timeframe_minutes * 60 and current_profit <= 0:
                return "time_stop_no_follow_through"
        return None

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        self._refresh_runtime_rules()
        sl_pct = self._runtime_number("sl_pct", self.sl_pct)
        leverage = max(float(getattr(trade, "leverage", 1.0) or 1.0), 1.0)

        # After the first partial TP is filled, protect the remaining position
        # at break-even using Freqtrade's native custom stoploss helper.
        if int(getattr(trade, "nr_of_successful_exits", 0) or 0) > 0:
            breakeven_stop = stoploss_from_open(0.0, current_profit, is_short=trade.is_short, leverage=leverage)
            if breakeven_stop > 0:
                return breakeven_stop

        return -min(max(sl_pct / 100.0 * leverage, 0.001), 0.99)

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> float | None | tuple[float | None, str | None]:
        """Native Freqtrade partial take-profit handling.

        This is intentionally strict: only one filled TP adjustment advances the
        next target, using `trade.nr_of_successful_exits` as durable state. That
        prevents repeated partial exits on every bot loop while the price remains
        above the same target.
        """
        self._refresh_runtime_rules()
        if getattr(trade, "has_open_orders", False):
            return None

        tp_levels_pct = self._runtime_tuple("tp_levels_pct", self.tp_levels_pct)[:3]
        if not tp_levels_pct:
            return None

        completed_exits = int(getattr(trade, "nr_of_successful_exits", 0) or 0)
        if completed_exits >= len(tp_levels_pct):
            return None

        price_move_pct = self._price_move_pct(trade, current_rate)
        target_pct = tp_levels_pct[completed_exits]
        if price_move_pct < target_pct:
            return None

        current_stake = float(getattr(trade, "stake_amount", 0.0) or 0.0)
        if current_stake <= 0:
            return None

        is_final_target = completed_exits >= len(tp_levels_pct) - 1
        fraction = self._tp_current_exit_fraction(len(tp_levels_pct), completed_exits)
        stake_to_exit = current_stake if is_final_target else current_stake * fraction

        # Avoid exchange-minimum dust failures on partial exits. If the final TP
        # is reached, close the full remainder; otherwise wait for the next loop.
        if min_stake is not None and stake_to_exit < float(min_stake) and not is_final_target:
            if price_move_pct >= tp_levels_pct[-1]:
                stake_to_exit = current_stake
                is_final_target = True
            else:
                return None

        stake_to_exit = min(stake_to_exit, current_stake)
        if stake_to_exit <= 0:
            return None

        tag = f"tp{completed_exits + 1}_{'final' if is_final_target else 'partial'}"
        return -stake_to_exit, tag

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        # Freqtrade clamps returned stake into [min_stake, max_stake]. Coin
        # Distribution is interpreted as per-asset margin allocation: a 45%
        # BTC row means BTC entries may use at most 45% of total stake balance
        # as margin. Optional risk and gross exposure caps further reduce it.
        self._refresh_runtime_rules()
        total = self.wallets.get_total_stake_amount() if self.wallets else max_stake
        allocation_cap = total * (self._allocation_pct_for_pair(pair) / 100.0)

        effective_leverage = max(float(leverage or 1.0), 1.0)
        max_leverage_value = self._runtime_number("max_leverage_value", self.max_leverage_value)
        effective_leverage = min(effective_leverage, max(max_leverage_value, 1.0))

        risk_per_trade_pct = self._runtime_number("risk_per_trade_pct", self.risk_per_trade_pct) if self._runtime_bool("risk_per_trade_enabled", False) else 0.0
        sl_pct = self._runtime_number("sl_pct", self.sl_pct)
        risk_stake = total * (risk_per_trade_pct / 100.0) / max(sl_pct / 100.0, 0.0001) / effective_leverage if risk_per_trade_pct > 0 else max_stake

        gross_stake = max_stake
        if self._runtime_bool("portfolio_gross_cap_enabled", False):
            gross_cap_pct = self._runtime_number("portfolio_gross_cap", 0.0)
            if gross_cap_pct > 0:
                gross_stake = total * (gross_cap_pct / 100.0) / effective_leverage

        stake = min(proposed_stake, allocation_cap, risk_stake, gross_stake, max_stake)
        if min_stake is not None and stake < min_stake:
            return 0.0
        return max(stake, 0.0)

    def _allocation_pct_for_pair(self, pair: str) -> float:
        allocations = self._runtime_strategy_params.get("coin_allocations")
        if not isinstance(allocations, dict):
            return 100.0
        direct = allocations.get(pair)
        if isinstance(direct, dict):
            return self._safe_pct(direct.get("pct"), 100.0)
        base = pair.split("/", 1)[0]
        symbol = f"xyz:{base[4:]}" if base.startswith("XYZ-") else base.upper()
        for value in allocations.values():
            if not isinstance(value, dict):
                continue
            if str(value.get("symbol", "")).upper() == symbol.upper():
                return self._safe_pct(value.get("pct"), 100.0)
        return 100.0

    @staticmethod
    def _safe_pct(value, default: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        if not np.isfinite(number):
            return default
        return max(0.0, min(100.0, number))

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, side: str,
                 **kwargs) -> float:
        self._refresh_runtime_rules()
        max_leverage_value = self._runtime_number("max_leverage_value", self.max_leverage_value)
        return float(min(max_leverage_value, max_leverage))
