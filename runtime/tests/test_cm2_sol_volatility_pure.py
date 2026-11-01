"""Synthetic contract checks only; no native packages or historical payloads."""
from dataclasses import replace
from decimal import Decimal as D, localcontext, ROUND_HALF_EVEN
import pytest
from coinmaster.strategy.cm2_sol_volatility import (
    DAY_NS, PairedDailyClose, daily_volatility_coefficient as coefficient,
)


def history(count=61):
    return [PairedDailyClose(i * DAY_NS, "100" if i % 2 == 0 else "200",
                            "100" if i % 2 == 0 else "400") for i in range(count)]


def test_hand_derived_sample_variance_ratio():
    rows = history()
    with localcontext() as ctx:
        ctx.prec = 50
        ctx.rounding = ROUND_HALF_EVEN
        # Thirty of each return: BTC {1,-.5}; SOL {3,-.75}.
        btc_std = (D(60) * D(".75") ** 2 / 59).sqrt()
        sol_std = (D(60) * D("1.875") ** 2 / 59).sqrt()
        expected = sol_std / btc_std
    assert coefficient(rows, decision_ns=60 * DAY_NS) == expected
    assert abs(expected - D("2.5")) < D("1e-48")


def test_completed_close_equality_and_future_rejection():
    rows = history()
    assert coefficient(rows, decision_ns=60 * DAY_NS) is not None
    assert coefficient(rows, decision_ns=60 * DAY_NS - 1) is None


def test_rolling_window_exactly_sixty_returns_and_scale_invariance():
    rows = history(62)
    rows[0] = replace(rows[0], btc_close="99999999", sol_close="0.00001")
    expected = coefficient(rows[1:], decision_ns=61 * DAY_NS)
    assert coefficient(rows, decision_ns=61 * DAY_NS) == expected
    scaled = [replace(r, btc_close=str(D(r.btc_close) * 7),
                      sol_close=str(D(r.sol_close) * 11)) for r in rows[1:]]
    assert coefficient(scaled, decision_ns=61 * DAY_NS) == expected


def test_local_precision_and_rounding_do_not_leak_or_depend_on_caller():
    rows = history()
    expected = coefficient(rows, decision_ns=60 * DAY_NS)
    with localcontext() as ctx:
        ctx.prec = 8
        assert coefficient(rows, decision_ns=60 * DAY_NS) == expected
        assert ctx.prec == 8


@pytest.mark.parametrize("bad", ["0", "-1", "NaN", "Infinity", "bad", 1.0, D("1")])
@pytest.mark.parametrize("asset", ["btc_close", "sol_close"])
def test_invalid_exact_close_is_unavailable(bad, asset):
    rows = history()
    rows[20] = replace(rows[20], **{asset: bad})
    assert coefficient(rows, decision_ns=60 * DAY_NS) is None


def test_insufficient_gapped_duplicate_unordered_and_non_utc_unavailable():
    rows = history()
    assert coefficient(rows[:-1], decision_ns=60 * DAY_NS) is None
    for modified in (
        rows[:20] + rows[21:],
        rows[:20] + [rows[19]] + rows[21:],
        rows[:20] + [rows[21], rows[20]] + rows[22:],
        [replace(r, close_ns=r.close_ns + 1) for r in rows],
    ):
        assert coefficient(modified, decision_ns=61 * DAY_NS) is None


def test_zero_volatility_is_not_substituted_or_clamped():
    rows = history()
    assert coefficient([replace(r, btc_close="100") for r in rows],
                       decision_ns=60 * DAY_NS) is None
    assert coefficient([replace(r, sol_close="100") for r in rows],
                       decision_ns=60 * DAY_NS) is None
    assert coefficient(rows, decision_ns=True) is None

def test_missing_latest_completed_day_is_unavailable():
    assert coefficient(history(), decision_ns=61 * DAY_NS) is None


def test_latest_completed_boundary_is_current_through_same_utc_day():
    rows = history()
    assert coefficient(rows, decision_ns=61 * DAY_NS - 1) == coefficient(
        rows, decision_ns=60 * DAY_NS)
