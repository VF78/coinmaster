# flake8: noqa: F401
# isort: skip_file
"""
CoinMasterStrategy — native Freqtrade execution of CoinMaster Trading Rules.

Implemented here (not in the companion UI/server):
- selectable entry timeframes: 5m / 15m / 1h / 4h
- HTF FVG retrace on 1h/4h with optional sweep, first-touch and max-age gates
- optional engulfing-body confirmation after FVG retrace touch
- regime filter on selected 1h/4h informative timeframe
- ADX / impulse quality guards, risk sizing, gross portfolio cap, time-stop

Opposite-engulfing exit UI/runtime support was intentionally removed; exits are
managed through SL/TP/time-stop logic.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from functools import reduce
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from pandas import DataFrame

import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import DecimalParameter, IntParameter, IStrategy, merge_informative_pair, stoploss_from_open


logger = logging.getLogger(__name__)


class CoinMasterStrategy(IStrategy):
    INTERFACE_VERSION = 3

    can_short = True
    # Base TF must be the smallest selectable entry TF so 5m signals can execute
    # honestly; higher TFs are merged via native informative dataframes.
    timeframe = "5m"
    informative_timeframes = ("15m", "1h", "4h")
    selectable_timeframes = ("5m", "15m", "1h", "4h")
    htf_fvg_timeframes = ("1h", "4h")
    process_only_new_candles = True
    startup_candle_count = 720

    minimal_roi = {"0": 100}
    stoploss = -0.99
    use_custom_stoploss = True
    use_exit_signal = False
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    position_adjustment_enable = True
    max_entry_position_adjustment = 0

    engulfing_lookback = IntParameter(10, 120, default=70, space="buy")
    fvg_retrace = DecimalParameter(20, 80, decimals=0, default=60, space="buy")
    fvg_min_width_pct = DecimalParameter(0, 2, decimals=2, default=1.0, space="buy")
    adx_min = DecimalParameter(0, 40, decimals=1, default=0.0, space="buy")
    min_impulse_atr = DecimalParameter(0, 2, decimals=2, default=0.0, space="buy")
    time_stop_bars = IntParameter(0, 288, default=30, space="sell")

    max_leverage_value = 10.0
    risk_per_trade_pct = 3.0
    tp_levels_pct = (1.0, 2.0, 7.0)
    sl_pct = 2.0

    runtime_rules_path = Path("/freqtrade/user_data/runtime/trading_rules.json")
    fallback_runtime_rules_path = Path(__file__).resolve().parents[1] / "runtime" / "trading_rules.json"
    radar_policy_path = Path("/freqtrade/user_data/runtime/radar_policy.json")
    fallback_radar_policy_path = Path(__file__).resolve().parents[1] / "runtime" / "radar_policy.json"
    radar_modes = {"both", "long_only", "short_only", "off"}

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
                "only_per_pair": False,
                "only_per_side": False,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 288,
                "trade_limit": 5,
                "stop_duration_candles": 48,
                "max_allowed_drawdown": 0.10,
                "calculation_mode": "equity",
            },
            {
                "method": "LowProfitPairs",
                "lookback_period_candles": 288,
                "trade_limit": 4,
                "stop_duration_candles": 48,
                "required_profit": -0.03,
                "only_per_pair": True,
                "only_per_side": False,
            },
        ]

    plot_config = {
        "main_plot": {
            "ema_fast": {"color": "orange"},
            "ema_slow": {"color": "blue"},
            "fvg_top_1h": {"color": "rgba(0, 180, 0, 0.5)"},
            "fvg_bottom_1h": {"color": "rgba(180, 0, 0, 0.5)"},
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
        self._radar_policy_mtime: float | None = None
        self._radar_policy_state: dict[str, object] = self._neutral_radar_policy("missing", "radar_missing_ignored")
        self._radar_last_status: str | None = None
        self._radar_logged_decisions: set[tuple[str, str, str, str]] = set()
        self._refresh_runtime_rules(force=True)
        self._refresh_radar_policy(force=True)

    def informative_pairs(self):
        dp = getattr(self, "dp", None)
        pairs = dp.current_whitelist() if dp else []
        return [(pair, tf) for pair in pairs for tf in self.informative_timeframes]

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

    def _runtime_timeframes(self, key: str, default: tuple[str, ...]) -> tuple[str, ...]:
        value = self._runtime_strategy_params.get(key)
        if not isinstance(value, list):
            return default
        result: list[str] = []
        for item in value:
            tf = str(item).lower().strip()
            if tf in self.selectable_timeframes and tf not in result:
                result.append(tf)
        return tuple(result) if result else default

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
        except Exception as exc:  # pragma: no cover
            logger.warning("Could not load CoinMaster runtime Trading Rules from %s: %s", path, exc)

    @staticmethod
    def _neutral_radar_policy(status: str, reason: str) -> dict[str, object]:
        return {
            "status": status,
            "active": False,
            "reason": reason,
            "global": {"mode": "both", "risk_multiplier": 1.0, "lock_new_entries": False, "reason": reason},
            "pairs": {},
        }

    @staticmethod
    def _parse_radar_time(value: object) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _safe_multiplier(value: object, default: float = 1.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        if not np.isfinite(number):
            return default
        return max(0.0, min(1.0, number))

    def _normalize_radar_scope(self, value: object, default_reason: str) -> dict[str, object] | None:
        if not isinstance(value, dict):
            return None
        mode = str(value.get("mode", "both")).lower().strip()
        if mode not in self.radar_modes:
            return None
        reason = str(value.get("reason") or default_reason).strip()[:120]
        return {
            "mode": mode,
            "risk_multiplier": self._safe_multiplier(value.get("risk_multiplier"), 1.0),
            "lock_new_entries": bool(value.get("lock_new_entries", False)),
            "reason": reason or default_reason,
        }

    def _set_radar_policy_state(self, state: dict[str, object]) -> None:
        status = str(state.get("status", "unknown"))
        reason = str(state.get("reason", ""))
        if status != self._radar_last_status:
            if status == "active":
                logger.info("Loaded active Radar policy from %s", state.get("path", self.radar_policy_path))
            elif status == "stale":
                logger.info("radar_stale_ignored: %s", reason)
            elif status == "invalid":
                logger.warning("radar_invalid_ignored: %s", reason)
            self._radar_last_status = status
        self._radar_policy_state = state

    def _refresh_radar_policy(self, force: bool = False) -> None:
        path = self.radar_policy_path if self.radar_policy_path.exists() else self.fallback_radar_policy_path
        if not path.exists():
            self._radar_policy_mtime = None
            self._set_radar_policy_state(self._neutral_radar_policy("missing", "radar_missing_ignored"))
            return
        try:
            stat = path.stat()
            if not force and self._radar_policy_mtime == stat.st_mtime:
                return
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or int(payload.get("schema_version", 0) or 0) != 1:
                self._radar_policy_mtime = stat.st_mtime
                self._set_radar_policy_state(self._neutral_radar_policy("invalid", "schema_version_invalid"))
                return

            global_policy = self._normalize_radar_scope(payload.get("global", {}), "global_default")
            if global_policy is None:
                self._radar_policy_mtime = stat.st_mtime
                self._set_radar_policy_state(self._neutral_radar_policy("invalid", "global_policy_invalid"))
                return

            enabled = bool((payload.get("global") or {}).get("enabled", True))
            valid_until = self._parse_radar_time(payload.get("valid_until"))
            if not enabled:
                self._radar_policy_mtime = stat.st_mtime
                self._set_radar_policy_state(self._neutral_radar_policy("disabled", "radar_disabled_ignored"))
                return
            if valid_until is None:
                self._radar_policy_mtime = stat.st_mtime
                self._set_radar_policy_state(self._neutral_radar_policy("invalid", "valid_until_invalid"))
                return
            if valid_until <= datetime.now(timezone.utc):
                self._radar_policy_mtime = stat.st_mtime
                self._set_radar_policy_state(self._neutral_radar_policy("stale", "valid_until_expired"))
                return

            raw_pairs = payload.get("pairs", {})
            if not isinstance(raw_pairs, dict):
                raw_pairs = {}
            pairs: dict[str, dict[str, object]] = {}
            for pair, raw_scope in raw_pairs.items():
                normalized = self._normalize_radar_scope(raw_scope, "pair_default")
                if normalized is not None:
                    pairs[str(pair)] = normalized

            self._radar_policy_mtime = stat.st_mtime
            self._set_radar_policy_state({
                "status": "active",
                "active": True,
                "reason": "active",
                "path": str(path),
                "updated_at": payload.get("updated_at"),
                "valid_until": payload.get("valid_until"),
                "global": global_policy,
                "pairs": pairs,
            })
        except Exception as exc:  # pragma: no cover
            self._set_radar_policy_state(self._neutral_radar_policy("invalid", f"read_failed:{exc}"))

    @staticmethod
    def _mode_allows_side(mode: str, side: str) -> bool:
        return mode == "both" or (mode == "long_only" and side == "long") or (mode == "short_only" and side == "short")

    def _radar_pair_scope(self, pair: str) -> dict[str, object] | None:
        pairs = self._radar_policy_state.get("pairs")
        if not isinstance(pairs, dict):
            return None
        direct = pairs.get(pair)
        if isinstance(direct, dict):
            return direct
        base = pair.split("/", 1)[0].upper()
        return next((scope for key, scope in pairs.items() if str(key).split("/", 1)[0].upper() == base and isinstance(scope, dict)), None)

    def _radar_effective_policy(self, pair: str, side: str) -> dict[str, object]:
        self._refresh_radar_policy()
        if not self._radar_policy_state.get("active"):
            return {"allowed": True, "risk_multiplier": 1.0, "code": str(self._radar_policy_state.get("reason", "radar_neutral")), "reason": str(self._radar_policy_state.get("reason", "radar_neutral"))}

        global_policy = self._radar_policy_state.get("global") if isinstance(self._radar_policy_state.get("global"), dict) else {}
        pair_policy = self._radar_pair_scope(pair) or {}
        global_mode = str(global_policy.get("mode", "both"))
        pair_mode = str(pair_policy.get("mode", "both"))
        global_reason = str(global_policy.get("reason", "global_policy"))
        pair_reason = str(pair_policy.get("reason", "pair_policy"))

        if bool(global_policy.get("lock_new_entries", False)) or global_mode == "off":
            return {"allowed": False, "risk_multiplier": 0.0, "code": "radar_block_global", "reason": global_reason}
        if pair_mode == "off":
            return {"allowed": False, "risk_multiplier": 0.0, "code": "radar_block_pair", "reason": pair_reason}
        if not self._mode_allows_side(global_mode, side) or not self._mode_allows_side(pair_mode, side):
            return {"allowed": False, "risk_multiplier": 0.0, "code": "radar_direction_mismatch", "reason": pair_reason if pair_policy else global_reason}

        multiplier = min(
            self._safe_multiplier(global_policy.get("risk_multiplier"), 1.0),
            self._safe_multiplier(pair_policy.get("risk_multiplier"), 1.0) if pair_policy else 1.0,
        )
        return {"allowed": multiplier > 0.0, "risk_multiplier": multiplier, "code": "radar_risk_multiplier_applied" if multiplier < 1.0 else "radar_allowed", "reason": pair_reason if pair_policy else global_reason}

    def _log_radar_decision(self, code: str, pair: str, side: str, reason: str, count: int | None = None) -> None:
        key = (code, pair, side, reason)
        if key in self._radar_logged_decisions:
            return
        self._radar_logged_decisions.add(key)
        suffix = f" candidates={count}" if count is not None else ""
        logger.info("%s pair=%s side=%s reason=%s%s", code, pair, side, reason, suffix)

    def bot_loop_start(self, current_time: datetime, **kwargs) -> None:
        self._refresh_runtime_rules()
        self._refresh_radar_policy()

    @staticmethod
    def _body_top(dataframe: DataFrame) -> pd.Series:
        return dataframe[["open", "close"]].max(axis=1)

    @staticmethod
    def _body_bottom(dataframe: DataFrame) -> pd.Series:
        return dataframe[["open", "close"]].min(axis=1)

    @staticmethod
    def _annotate_engulfing(dataframe: DataFrame, lookback: int) -> DataFrame:
        body_top = CoinMasterStrategy._body_top(dataframe)
        body_bottom = CoinMasterStrategy._body_bottom(dataframe)
        prev_body_top = body_top.shift(1)
        prev_body_bottom = body_bottom.shift(1)
        bullish_body = (dataframe["close"] > dataframe["open"]) & (body_bottom <= prev_body_bottom) & (body_top >= prev_body_top)
        bearish_body = (dataframe["close"] < dataframe["open"]) & (body_bottom <= prev_body_bottom) & (body_top >= prev_body_top)

        history_low = dataframe["low"].shift(2).rolling(lookback).min()
        history_high = dataframe["high"].shift(2).rolling(lookback).max()
        pair_low = pd.concat([dataframe["low"].shift(1), dataframe["low"]], axis=1).min(axis=1)
        pair_high = pd.concat([dataframe["high"].shift(1), dataframe["high"]], axis=1).max(axis=1)

        dataframe["bullish_body_engulf"] = bullish_body
        dataframe["bearish_body_engulf"] = bearish_body
        dataframe["sweep_low"] = pair_low < history_low
        dataframe["sweep_high"] = pair_high > history_high
        dataframe["engulf_long"] = bullish_body & dataframe["sweep_low"]
        dataframe["engulf_short"] = bearish_body & dataframe["sweep_high"]
        return dataframe

    @staticmethod
    def _annotate_quality(dataframe: DataFrame) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=55)
        dataframe["ema_slow_slope"] = dataframe["ema_slow"] - dataframe["ema_slow"].shift(3)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["body_atr"] = (dataframe["close"] - dataframe["open"]).abs() / dataframe["atr"].replace(0, np.nan)
        candle_range = (dataframe["high"] - dataframe["low"]).replace(0, np.nan)
        dataframe["close_position"] = (dataframe["close"] - dataframe["low"]) / candle_range
        return dataframe

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
        n = len(dataframe)
        fvg_dir = np.zeros(n, dtype=int)
        fvg_top = np.full(n, np.nan)
        fvg_bottom = np.full(n, np.nan)
        fvg_trigger = np.full(n, np.nan)
        fvg_width_pct = np.full(n, np.nan)
        fvg_age = np.full(n, np.nan)

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
            # A retrace/touch is a candle-range event, not a close-only event:
            # wicks into the retrace band should count, while first-touch logic
            # below still prevents old zones from repeatedly triggering.
            candle_low = lows[i]
            candle_high = highs[i]
            retraced = (candle_low <= trigger and candle_high >= bottom) if direction == 1 else (candle_low <= top and candle_high >= trigger)
            if not retraced:
                continue

            zone_age = i - completion_index
            if require_first_touch:
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
            fvg_age[i] = zone_age

        dataframe["fvg_dir"] = fvg_dir
        dataframe["fvg_top"] = fvg_top
        dataframe["fvg_bottom"] = fvg_bottom
        dataframe["fvg_trigger"] = fvg_trigger
        dataframe["fvg_width_pct"] = fvg_width_pct
        dataframe["fvg_age"] = fvg_age
        return dataframe

    def _prepare_signal_dataframe(self, dataframe: DataFrame, include_fvg: bool) -> DataFrame:
        lookback = self._runtime_int("engulfing_lookback", int(self.engulfing_lookback.value))
        dataframe = self._annotate_quality(dataframe.copy())
        dataframe = self._annotate_engulfing(dataframe, lookback)
        if include_fvg:
            max_zone_age = self._runtime_int("max_zone_age_candles", 12)
            dataframe = self._annotate_fvg(
                dataframe,
                lookback=max(max_zone_age, 2),
                retrace_pct=self._runtime_number("fvg_retrace", float(self.fvg_retrace.value)),
                min_width_pct=self._runtime_number("fvg_min_width_pct", float(self.fvg_min_width_pct.value)),
                require_sweep=self._runtime_bool("fvg_require_sweep", False),
                sweep_lookback=self._runtime_int("fvg_sweep_lookback_candles", 20),
                require_first_touch=self._runtime_bool("fvg_require_first_touch", False),
                max_zone_age=max_zone_age,
            )

        # Freqtrade's informative merge forward-fills columns. Pandas warns when
        # object-like bool columns are downcast during ffill, so keep signal flags
        # as compact numeric flags before merging. _bool_col() converts them back
        # to boolean gates at decision time.
        for col in ("bullish_body_engulf", "bearish_body_engulf", "sweep_low", "sweep_high", "engulf_long", "engulf_short"):
            if col in dataframe:
                dataframe[col] = dataframe[col].fillna(False).astype("int8")
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._refresh_runtime_rules()
        pair = metadata["pair"]

        dataframe = self._prepare_signal_dataframe(dataframe, include_fvg=False)
        for tf in self.informative_timeframes:
            if not getattr(self, "dp", None):
                continue
            informative = self.dp.get_pair_dataframe(pair=pair, timeframe=tf)
            if informative is None or informative.empty:
                continue
            informative = self._prepare_signal_dataframe(informative, include_fvg=tf in self.htf_fvg_timeframes)
            keep = [
                "date", "open", "high", "low", "close", "volume",
                "engulf_long", "engulf_short", "bullish_body_engulf", "bearish_body_engulf",
                "ema_fast", "ema_slow", "ema_slow_slope", "adx", "atr", "body_atr", "close_position",
            ]
            if tf in self.htf_fvg_timeframes:
                keep += ["fvg_dir", "fvg_top", "fvg_bottom", "fvg_trigger", "fvg_width_pct", "fvg_age"]
            dataframe = merge_informative_pair(dataframe, informative[keep], self.timeframe, tf, ffill=True)

        return dataframe

    def _tf_col(self, base: str, tf: str) -> str:
        return base if tf == self.timeframe else f"{base}_{tf}"

    def _bool_col(self, dataframe: DataFrame, base: str, tf: str) -> pd.Series:
        col = self._tf_col(base, tf)
        if col not in dataframe:
            return pd.Series(False, index=dataframe.index)
        return dataframe[col].fillna(False).astype(bool)

    def _num_col(self, dataframe: DataFrame, base: str, tf: str, default: float = np.nan) -> pd.Series:
        col = self._tf_col(base, tf)
        if col not in dataframe:
            return pd.Series(default, index=dataframe.index)
        return pd.to_numeric(dataframe[col], errors="coerce")

    def _entry_timeframes(self) -> tuple[str, ...]:
        return self._runtime_timeframes("entry_timeframes", ("15m",))

    @staticmethod
    def _symbol_from_pair(pair: str) -> str:
        base = str(pair or "").split("/", 1)[0]
        if base.startswith("XYZ-"):
            return f"xyz:{base[4:]}".upper().replace("XYZ:", "xyz:")
        return base.upper()

    def _bias_for_pair(self, pair: str) -> str:
        policy = self._runtime_strategy_params.get("bias_policy")
        if not isinstance(policy, dict):
            return "both"
        default_bias = str(policy.get("defaultBias") or "both").lower().strip()
        if default_bias not in {"long", "short", "both", "off"}:
            default_bias = "both"
        overrides = policy.get("symbolOverrides")
        if not isinstance(overrides, dict):
            return default_bias
        symbol = self._symbol_from_pair(pair)
        override = overrides.get(symbol)
        if not isinstance(override, dict) or str(override.get("mode") or "global").lower().strip() != "symbol":
            return default_bias
        bias = str(override.get("bias") or default_bias).lower().strip()
        return bias if bias in {"long", "short", "both", "off"} else default_bias

    def _side_enabled(self, pair: str, side: str) -> bool:
        value = self._runtime_strategy_params.get("enabled_sides")
        if isinstance(value, list):
            enabled = {str(item).lower().strip() for item in value}
            if side not in enabled:
                return False
        bias = self._bias_for_pair(pair)
        return bias == "both" or bias == side

    def _engulf_signal(self, dataframe: DataFrame, side: str) -> pd.Series:
        col = "engulf_long" if side == "long" else "engulf_short"
        signal = pd.Series(False, index=dataframe.index)
        for tf in self._entry_timeframes():
            signal = signal | self._bool_col(dataframe, col, tf)
        return signal

    def _confirmation_signal(self, dataframe: DataFrame, side: str) -> pd.Series:
        if not self._runtime_bool("fvg_require_confirmation", False):
            return pd.Series(True, index=dataframe.index)
        confirmations = self._runtime_timeframes("fvg_confirmation_timeframes", ("15m",))
        col = "engulf_long" if side == "long" else "engulf_short"
        signal = pd.Series(False, index=dataframe.index)
        for tf in confirmations:
            signal = signal | self._bool_col(dataframe, col, tf)
        return signal

    def _fvg_signal(self, dataframe: DataFrame, side: str) -> pd.Series:
        desired = 1 if side == "long" else -1
        selected_htfs = tuple(tf for tf in self._entry_timeframes() if tf in self.htf_fvg_timeframes)
        if not selected_htfs:
            selected_htfs = self.htf_fvg_timeframes
        signal = pd.Series(False, index=dataframe.index)
        for tf in selected_htfs:
            fvg_dir = self._num_col(dataframe, "fvg_dir", tf, 0).fillna(0).astype(int)
            signal = signal | (fvg_dir == desired)
        return signal & self._confirmation_signal(dataframe, side)

    def _regime_series(self, dataframe: DataFrame, side: str) -> pd.Series:
        if not self._runtime_bool("regime_filter_enabled", True):
            return pd.Series(True, index=dataframe.index)
        regime_tf = str(self._runtime_strategy_params.get("regime_tf") or "1h").lower()
        if regime_tf not in {"1h", "4h"}:
            regime_tf = "1h"
        ema_fast = self._num_col(dataframe, "ema_fast", regime_tf)
        ema_slow = self._num_col(dataframe, "ema_slow", regime_tf)
        slope = self._num_col(dataframe, "ema_slow_slope", regime_tf)
        adx = self._num_col(dataframe, "adx", regime_tf)
        adx_min = self._runtime_number("adx_min", float(self.adx_min.value)) if self._runtime_bool("adx_enabled", False) else 0.0
        if side == "long":
            return (ema_fast > ema_slow) & (slope >= 0) & (adx >= adx_min)
        return (ema_fast < ema_slow) & (slope <= 0) & (adx >= adx_min)

    def _common_entry_guards(self, dataframe: DataFrame, side: str) -> list[pd.Series]:
        close_quality = dataframe["close_position"] >= 0.75 if side == "long" else dataframe["close_position"] <= 0.25
        min_impulse_atr = (
            self._runtime_number("min_impulse_atr", float(self.min_impulse_atr.value))
            if self._runtime_bool("min_impulse_atr_enabled", False)
            else 0.0
        )
        return [
            dataframe["volume"] > 0,
            self._regime_series(dataframe, side).fillna(False),
            dataframe["body_atr"].fillna(0) >= min_impulse_atr,
            close_quality.fillna(False),
        ]

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = str(metadata.get("pair", ""))
        long_signal = (self._engulf_signal(dataframe, "long") | self._fvg_signal(dataframe, "long")) if self._side_enabled(pair, "long") else pd.Series(False, index=dataframe.index)
        short_signal = (self._engulf_signal(dataframe, "short") | self._fvg_signal(dataframe, "short")) if self._side_enabled(pair, "short") else pd.Series(False, index=dataframe.index)

        long_conditions = [long_signal] + self._common_entry_guards(dataframe, "long")
        short_conditions = [short_signal] + self._common_entry_guards(dataframe, "short")

        for side, conditions in (("long", long_conditions), ("short", short_conditions)):
            radar = self._radar_effective_policy(pair, side)
            base_candidates = reduce(lambda x, y: x & y, conditions)
            candidate_count = int(base_candidates.fillna(False).astype(bool).sum())
            if not bool(radar.get("allowed", True)):
                if candidate_count > 0:
                    self._log_radar_decision(str(radar.get("code", "radar_blocked")), pair, side, str(radar.get("reason", "radar_policy")), candidate_count)
                conditions.append(pd.Series(False, index=dataframe.index))
            elif float(radar.get("risk_multiplier", 1.0) or 1.0) < 1.0 and candidate_count > 0:
                self._log_radar_decision("radar_risk_multiplier_applied", pair, side, str(radar.get("reason", "radar_policy")), candidate_count)

        dataframe.loc[reduce(lambda x, y: x & y, long_conditions), ["enter_long", "enter_tag"]] = (1, "coinmaster_long")
        dataframe.loc[reduce(lambda x, y: x & y, short_conditions), ["enter_short", "enter_tag"]] = (1, "coinmaster_short")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs):
        self._refresh_runtime_rules()
        bars = self._runtime_int("time_stop_bars", int(self.time_stop_bars.value)) if self._runtime_bool("time_stop_enabled", False) else 0
        if bars > 0:
            elapsed = current_time - trade.open_date_utc
            timeframe_minutes = self._runtime_timeframe_minutes("time_stop_timeframe", self._primary_entry_timeframe())
            if elapsed.total_seconds() >= bars * timeframe_minutes * 60 and current_profit <= 0:
                return "time_stop_no_follow_through"
        return None

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        self._refresh_runtime_rules()
        sl_pct = self._runtime_number("sl_pct", self.sl_pct)
        leverage = max(float(getattr(trade, "leverage", 1.0) or 1.0), 1.0)
        if int(getattr(trade, "nr_of_successful_exits", 0) or 0) > 0:
            breakeven_stop = stoploss_from_open(0.0, current_profit, is_short=trade.is_short, leverage=leverage)
            if breakeven_stop > 0:
                return breakeven_stop
        return -min(max(sl_pct / 100.0 * leverage, 0.001), 0.99)

    @staticmethod
    def _tp_current_exit_fraction(level_count: int, completed_exits: int) -> float:
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

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> float | None | tuple[float | None, str | None]:
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

    @staticmethod
    def _timeframe_minutes(timeframe: str) -> int:
        tf = str(timeframe or "5m").lower().strip()
        if tf.endswith("m"):
            return max(1, int(float(tf[:-1] or 5)))
        if tf.endswith("h"):
            return max(1, int(float(tf[:-1] or 1) * 60))
        if tf.endswith("d"):
            return max(1, int(float(tf[:-1] or 1) * 24 * 60))
        return 5

    def _primary_entry_timeframe(self) -> str:
        entry_timeframes = self._runtime_timeframes("entry_timeframes", (self.timeframe,))
        return max(entry_timeframes, key=self._timeframe_minutes) if entry_timeframes else self.timeframe

    def _runtime_timeframe_minutes(self, key: str, default_tf: str) -> int:
        value = str(self._runtime_strategy_params.get(key) or default_tf).lower().strip()
        if value not in self.selectable_timeframes:
            value = default_tf
        return self._timeframe_minutes(value)

    @staticmethod
    def _open_gross_notional() -> float:
        try:
            trades = Trade.get_open_trades()
        except Exception:  # pragma: no cover - depends on Freqtrade runtime DB session
            return 0.0
        total_notional = 0.0
        for trade in trades:
            try:
                stake = float(getattr(trade, "stake_amount", 0.0) or 0.0)
                leverage = max(float(getattr(trade, "leverage", 1.0) or 1.0), 1.0)
            except (TypeError, ValueError):
                continue
            if np.isfinite(stake) and np.isfinite(leverage) and stake > 0:
                total_notional += stake * leverage
        return max(total_notional, 0.0)

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        self._refresh_runtime_rules()
        total = self.wallets.get_total_stake_amount() if self.wallets else max_stake

        # Coin Distribution is the operator's explicit margin sizing model:
        # a 33.3333% BTC row means a BTC entry targets 33.3333% of available
        # stake balance as margin. Freqtrade still performs its native exchange
        # min/max validation around the returned stake.
        allocation_stake = total * (self._allocation_pct_for_pair(pair) / 100.0)

        effective_leverage = min(max(float(leverage or 1.0), 1.0), max(self._runtime_number("max_leverage_value", self.max_leverage_value), 1.0))
        risk_per_trade_pct = self._runtime_number("risk_per_trade_pct", self.risk_per_trade_pct) if self._runtime_bool("risk_per_trade_enabled", False) else 0.0
        sl_pct = self._runtime_number("sl_pct", self.sl_pct)
        risk_stake = total * (risk_per_trade_pct / 100.0) / max(sl_pct / 100.0, 0.0001) / effective_leverage if risk_per_trade_pct > 0 else allocation_stake

        gross_stake = allocation_stake
        if self._runtime_bool("portfolio_gross_cap_enabled", False):
            gross_cap_pct = self._runtime_number("portfolio_gross_cap", 0.0)
            if gross_cap_pct > 0:
                gross_cap_notional = total * (gross_cap_pct / 100.0)
                remaining_notional = max(0.0, gross_cap_notional - self._open_gross_notional())
                gross_stake = remaining_notional / effective_leverage

        stake = min(allocation_stake, risk_stake, gross_stake, max_stake)
        radar = self._radar_effective_policy(pair, side)
        radar_multiplier = float(radar.get("risk_multiplier", 1.0) or 0.0) if bool(radar.get("allowed", True)) else 0.0
        if radar_multiplier < 1.0:
            self._log_radar_decision("radar_risk_multiplier_applied", pair, side, str(radar.get("reason", "radar_policy")))
        stake *= max(0.0, min(1.0, radar_multiplier))
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
