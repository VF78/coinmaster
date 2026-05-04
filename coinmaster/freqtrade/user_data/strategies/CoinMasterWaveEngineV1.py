# flake8: noqa: F401
"""Research-only native Freqtrade wrapper for the Wave Engine prototype.

This strategy is intentionally not wired into the running dry/live config.
Use the helper under `freqtrade/wave_engine/` to stage it into a temporary
research directory and run native validation commands there.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

try:
    import numpy as np
    import pandas as pd
    from pandas import DataFrame
except Exception:  # pragma: no cover - local workspace may not have pandas
    np = None  # type: ignore[assignment]
    pd = None  # type: ignore[assignment]

    class DataFrame:  # type: ignore[override]
        pass

try:
    from freqtrade.persistence import Trade
    from freqtrade.strategy import IStrategy, stoploss_from_absolute
except Exception:  # pragma: no cover - local workspace may not have freqtrade
    class IStrategy:  # type: ignore[override]
        INTERFACE_VERSION = 3

    class Trade:  # type: ignore[override]
        pass

    def stoploss_from_absolute(*args: Any, **kwargs: Any) -> float:
        return -0.99

try:
    from .freqtrade_adapter import BASE_TIMEFRAME, INFORMATIVE_TIMEFRAMES, PROFILE_PATH, compute_pair_research_frame, load_pair_profile, snapshot_summary
except Exception:  # pragma: no cover - copied flat into temp strategy path
    from freqtrade_adapter import BASE_TIMEFRAME, INFORMATIVE_TIMEFRAMES, PROFILE_PATH, compute_pair_research_frame, load_pair_profile, snapshot_summary  # type: ignore[no-redef]


class CoinMasterWaveEngineV1(IStrategy):
    INTERFACE_VERSION = 3

    can_short = True
    timeframe = BASE_TIMEFRAME
    process_only_new_candles = True
    startup_candle_count = 1440

    minimal_roi = {"0": 100}
    stoploss = -0.99
    use_custom_stoploss = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    position_adjustment_enable = True
    max_entry_position_adjustment = 0

    research_only = True
    wave_profile_path = PROFILE_PATH
    fallback_max_stoploss = 0.04
    partial_exit_fractions = (0.34, 0.50, 1.0)

    plot_config = {
        "main_plot": {},
        "subplots": {
            "Wave Engine": {
                "wave_signal_long": {"color": "#2da44e"},
                "wave_signal_short": {"color": "#cf222e"},
            }
        },
    }

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self._signal_context_by_pair: dict[str, dict[str, dict[str, Any]]] = {}
        self._pair_meta: dict[str, dict[str, Any]] = {}

    def informative_pairs(self):
        dp = getattr(self, "dp", None)
        pairs = dp.current_whitelist() if dp else []
        return [(pair, tf) for pair in pairs for tf in INFORMATIVE_TIMEFRAMES]

    @property
    def protections(self) -> list[dict[str, object]]:
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 1},
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 288,
                "trade_limit": 3,
                "stop_duration_candles": 48,
                "required_profit": 0.0,
                "only_per_pair": True,
                "only_per_side": False,
            },
        ]

    @classmethod
    def research_summary(cls) -> dict[str, Any]:
        return snapshot_summary(cls.wave_profile_path)

    def _blank_frame(self, dataframe: DataFrame) -> DataFrame:
        if pd is None:
            return dataframe
        frame = dataframe.copy()
        for column, value in (
            ("enter_long", 0),
            ("enter_short", 0),
            ("exit_long", 0),
            ("exit_short", 0),
            ("enter_tag", ""),
            ("exit_tag", ""),
            ("wave_enabled", 0),
            ("wave_profile_timeframe", ""),
            ("wave_regime_state", "flat"),
            ("wave_regime_sequence_id", 0),
            ("wave_regime_confirmed_wave_id", -1),
            ("wave_signal_long", 0),
            ("wave_signal_short", 0),
            ("wave_stop_price", np.nan if np is not None else 0.0),
            ("wave_tp1_price", np.nan if np is not None else 0.0),
            ("wave_tp2_price", np.nan if np is not None else 0.0),
            ("wave_tp3_price", np.nan if np is not None else 0.0),
            ("wave_time_stop_hours", np.nan if np is not None else 0.0),
            ("wave_signal_time", ""),
            ("wave_reason", ""),
        ):
            frame[column] = value
        return frame

    def _pair_profile(self, pair: str):
        return load_pair_profile(pair, self.wave_profile_path)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if pd is None:
            return self._blank_frame(dataframe)
        pair = str(metadata.get("pair") or "")
        if not pair:
            return self._blank_frame(dataframe)
        profile = self._pair_profile(pair)
        if profile is None:
            self._pair_meta[pair] = {"enabled": False, "reason": "pair_not_selected"}
            return self._blank_frame(dataframe)

        def _get_informative(timeframe: str):
            dp = getattr(self, "dp", None)
            if dp is None:
                return None
            try:
                return dp.get_pair_dataframe(pair=pair, timeframe=timeframe)
            except Exception:
                return None

        try:
            frame, signal_contexts, meta = compute_pair_research_frame(
                pair=pair,
                dataframe=dataframe,
                get_informative_dataframe=_get_informative,
                profile_path=self.wave_profile_path,
            )
        except Exception as exc:
            self._pair_meta[pair] = {"enabled": False, "reason": f"adapter_error:{exc}"}
            return self._blank_frame(dataframe)

        self._signal_context_by_pair.setdefault(pair, {}).update(signal_contexts)
        self._pair_meta[pair] = meta
        return frame

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if "enter_long" not in dataframe or "enter_short" not in dataframe:
            return self._blank_frame(dataframe)
        dataframe.loc[:, "enter_long"] = dataframe["enter_long"].fillna(0).astype("int8")
        dataframe.loc[:, "enter_short"] = dataframe["enter_short"].fillna(0).astype("int8")
        dataframe.loc[:, "enter_tag"] = dataframe["enter_tag"].fillna("")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if "exit_long" not in dataframe or "exit_short" not in dataframe:
            return self._blank_frame(dataframe)
        dataframe.loc[:, "exit_long"] = dataframe["exit_long"].fillna(0).astype("int8")
        dataframe.loc[:, "exit_short"] = dataframe["exit_short"].fillna(0).astype("int8")
        dataframe.loc[:, "exit_tag"] = dataframe["exit_tag"].fillna("")
        return dataframe

    def _signal_context(self, pair: str, trade: Trade) -> dict[str, Any] | None:
        pair_contexts = self._signal_context_by_pair.get(pair) or {}
        tag = str(getattr(trade, "enter_tag", "") or "")
        if tag and tag in pair_contexts:
            return pair_contexts[tag]

        opened_at = getattr(trade, "open_date_utc", None)
        if not isinstance(opened_at, datetime):
            return None
        fallback: tuple[datetime, dict[str, Any]] | None = None
        for candidate in pair_contexts.values():
            signal_time = candidate.get("signal_time")
            if not signal_time:
                continue
            try:
                signal_dt = datetime.fromisoformat(str(signal_time).replace("Z", "+00:00"))
            except ValueError:
                continue
            if signal_dt > opened_at:
                continue
            if fallback is None or signal_dt > fallback[0]:
                fallback = (signal_dt, candidate)
        return fallback[1] if fallback else None

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        context = self._signal_context(pair, trade)
        leverage = max(float(getattr(trade, "leverage", 1.0) or 1.0), 1.0)
        if int(getattr(trade, "nr_of_successful_exits", 0) or 0) > 0:
            return stoploss_from_absolute(float(getattr(trade, "open_rate", current_rate) or current_rate), current_rate, is_short=bool(getattr(trade, "is_short", False)), leverage=leverage)
        if context:
            absolute = float(context["stop_price"])
            return stoploss_from_absolute(absolute, current_rate, is_short=bool(getattr(trade, "is_short", False)), leverage=leverage)
        return -min(max(self.fallback_max_stoploss * leverage, 0.001), 0.99)

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ):
        context = self._signal_context(pair, trade)
        if not context:
            return None
        hours = float(context.get("time_stop_hours", 0) or 0)
        opened_at = getattr(trade, "open_date_utc", None)
        if isinstance(opened_at, datetime) and hours > 0 and current_time >= opened_at + timedelta(hours=hours):
            return "wave_time_stop"
        return None

    def adjust_trade_position(
        self,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: Optional[float],
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs,
    ) -> float | None | tuple[float | None, str | None]:
        pair = str(getattr(trade, "pair", "") or "")
        context = self._signal_context(pair, trade)
        if not context or getattr(trade, "has_open_orders", False):
            return None
        current_stake = float(getattr(trade, "stake_amount", 0.0) or 0.0)
        if current_stake <= 0:
            return None

        thresholds = [float(context["tp1_price"]), float(context["tp2_price"]), float(context["tp3_price"])]
        completed = int(getattr(trade, "nr_of_successful_exits", 0) or 0)
        if completed >= len(thresholds):
            return None
        is_short = bool(getattr(trade, "is_short", False))
        target = thresholds[completed]
        hit = current_rate <= target if is_short else current_rate >= target
        if not hit:
            return None

        fraction = self.partial_exit_fractions[completed] if completed < len(self.partial_exit_fractions) else 1.0
        is_final = completed >= len(thresholds) - 1
        stake_to_exit = current_stake if is_final else current_stake * fraction
        if min_stake is not None and stake_to_exit < float(min_stake) and not is_final:
            return None
        stake_to_exit = min(stake_to_exit, current_stake)
        if stake_to_exit <= 0:
            return None
        return -stake_to_exit, f"wave_tp{completed + 1}"
