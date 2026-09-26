"""One durable UTC high-water drawdown rule; no exchange or PnL authority."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

DAY_NS = 86_400_000_000_000
CLOSE_FRESH_NS = 120_000_000_000


def percent(value: int) -> int:
    if type(value) is not int or not 1 <= value <= 99:
        raise ValueError("DEPOSIT_PERCENT_INVALID")
    return value


def equity(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("DEPOSIT_EQUITY_INVALID")
    return value


@dataclass
class DepositProtection:
    limit_percent: int = 50
    high_water: Decimal | None = None
    last_boundary_ns: int | None = None
    latched: bool = False
    trigger: dict[str, str] | None = None
    exit_state: str | None = None
    daily_sample_missed: bool = False
    current_equity: Decimal | None = None
    observed_ns: int | None = None

    def __post_init__(self) -> None:
        percent(self.limit_percent)
        if self.high_water is not None and (not self.high_water.is_finite() or self.high_water <= 0):
            raise ValueError("DEPOSIT_HIGH_WATER_INVALID")
        if self.latched != (self.trigger is not None):
            raise ValueError("DEPOSIT_LATCH_MISMATCH")

    @property
    def threshold(self) -> Decimal | None:
        return None if self.high_water is None else self.high_water * Decimal(100 - self.limit_percent) / 100

    def initialize(self, value: Decimal, now_ns: int) -> None:
        value = equity(value)
        if value is None or value <= 0 or self.high_water is not None:
            raise ValueError("DEPOSIT_INITIAL_EQUITY_OR_STATE_INVALID")
        self.high_water = value
        self.last_boundary_ns = now_ns // DAY_NS * DAY_NS
        self.current_equity, self.observed_ns = value, now_ns

    def observe(self, value: Decimal | None, now_ns: int) -> tuple[bool, bool]:
        """Return (durable change, newly tripped); UNKNOWN never means zero."""
        value = equity(value)
        if self.high_water is None or self.last_boundary_ns is None:
            self.current_equity, self.observed_ns = value, now_ns
            return False, False
        previous_value, previous_ns = self.current_equity, self.observed_ns
        boundary = now_ns // DAY_NS * DAY_NS
        changed = False
        if boundary > self.last_boundary_ns:
            valid_close = (
                previous_value is not None and previous_ns is not None
                and previous_ns < boundary and previous_ns >= boundary - CLOSE_FRESH_NS
                and boundary == self.last_boundary_ns + DAY_NS
            )
            if valid_close and previous_value > self.high_water:
                self.high_water = previous_value
            self.daily_sample_missed = not valid_close
            self.last_boundary_ns = boundary
            changed = True
        self.current_equity, self.observed_ns = value, now_ns
        if value is not None and not self.latched and value <= self.threshold:
            self.latched = True
            self.exit_state = "EXITING"
            self.trigger = {
                "reason": "DEPOSIT_DRAWDOWN_LIMIT", "equity": str(value),
                "high_water_equity": str(self.high_water), "threshold_equity": str(self.threshold),
                "drawdown_limit_percent": str(self.limit_percent), "observed_at_ns": str(now_ns),
            }
            return True, True
        return changed, False

    def reset(self, value: Decimal, now_ns: int) -> None:
        value = equity(value)
        if value is None or value <= 0:
            raise ValueError("DEPOSIT_RESET_EQUITY_INVALID")
        self.high_water = value
        self.last_boundary_ns = now_ns // DAY_NS * DAY_NS
        self.current_equity, self.observed_ns = value, now_ns
        self.latched = False
        self.trigger = None
        self.exit_state = None
        self.daily_sample_missed = False

    def projection(self) -> dict[str, object]:
        state = (
            self.exit_state if self.latched else
            "NOT_INITIALIZED/RECOVERY_REQUIRED" if self.high_water is None else
            "EQUITY_UNAVAILABLE" if self.current_equity is None else "ARMED"
        )
        return {
            "state": state, "drawdown_limit_percent": self.limit_percent,
            "currency": "USDC", "equity": None if self.current_equity is None else str(self.current_equity),
            "high_water_equity": None if self.high_water is None else str(self.high_water),
            "threshold_equity": None if self.threshold is None else str(self.threshold),
            "observed_at_ns": self.observed_ns,
            "last_daily_close_utc": self.last_boundary_ns,
            "daily_sample_missed": self.daily_sample_missed,
            "trigger": self.trigger,
        }

    def durable(self) -> dict[str, object]:
        return {
            "schema": "coinmaster-deposit-protection-v1", "drawdown_limit_percent": self.limit_percent,
            "high_water_equity": None if self.high_water is None else str(self.high_water),
            "last_daily_close_utc": self.last_boundary_ns, "latched": self.latched,
            "trigger": self.trigger, "exit_state": self.exit_state,
            "daily_sample_missed": self.daily_sample_missed,
        }

    @classmethod
    def from_durable(cls, row: dict[str, object]) -> "DepositProtection":
        if row.get("schema") != "coinmaster-deposit-protection-v1":
            raise ValueError("DEPOSIT_STATE_SCHEMA_INVALID")
        high = row.get("high_water_equity")
        state = cls(
            limit_percent=percent(row["drawdown_limit_percent"]),
            high_water=None if high is None else Decimal(high),
            last_boundary_ns=row["last_daily_close_utc"], latched=row["latched"],
            trigger=row["trigger"], exit_state=row["exit_state"],
            daily_sample_missed=row["daily_sample_missed"],
        )
        if state.high_water is None or type(state.last_boundary_ns) is not int:
            raise ValueError("DEPOSIT_DURABLE_BASE_MISSING")
        return state
