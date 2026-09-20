from coinmaster.research.native_validation import current_candidate, scenarios, stress_policy
from coinmaster.venues.signals import DailySignalBar, daily_signal
from coinmaster.research.native_fixture import BTC_PERP
from decimal import Decimal


def test_validation_candidate_and_scenarios_are_explicitly_bounded() -> None:
    assert current_candidate().btc_notional_multiplier == 2.4
    assert current_candidate().sol_entry_z == (1.125, 2.375, 3.625)
    planned = scenarios()
    assert tuple(item["id"] for item in planned) == (
        "control_full_24m", "validation_seen_2024_09_2025_09", "validation_seen_2025_09_2026_09",
        "fee_stress_1_25x", "fee_stress_1_50x", "execution_stress_2m_5bps", "execution_stress_5m_10bps",
    )
    assert all(item["policy"].execution_delay_minutes >= 1 for item in planned)


def test_stress_policy_versions_native_fee_latency_and_spread_assumptions() -> None:
    policy = stress_policy(delay_minutes=5, spread_bps="10", fee_multiplier="1.5")
    assert policy.version == "bybit-1m-close-validation-stress-v1"
    assert policy.execution_delay_minutes == 5
    assert policy.symmetric_adverse_spread_bps == "10"
    assert policy.fee_multiplier == "1.5"
    assert policy.nonmatching_daily_signals


def test_daily_signal_is_explicit_non_matching_custom_data() -> None:
    wrapped = daily_signal(BTC_PERP.id, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100.5"), 1)
    assert isinstance(wrapped.data, DailySignalBar)
    assert wrapped.data.instrument_id == BTC_PERP.id
