from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from nautilus_trader.model.objects import Price
from coinmaster.domain.wave_overlay import Candidate, Episode, Intent, WaveOverlayState
from coinmaster.strategy.wave_overlay import _fee_floor_price


def instrument(venue="HYPERLIQUID", maker="0.00015", taker="0.00045", tick="1"):
    return SimpleNamespace(
        id=SimpleNamespace(venue=SimpleNamespace(value=venue)),
        maker_fee=Decimal(maker), taker_fee=Decimal(taker),
        price_increment=Price.from_str(tick),
        make_price=lambda value: Price.from_str(str(value)),
    )


@pytest.mark.parametrize(("side", "maker_expected", "taker_expected"), [
    (1, Decimal("83502"), Decimal("83527")),
    (-1, Decimal("83400"), Decimal("83375")),
])
def test_hl_outward_fee_floor_from_confirmed_entry_fees(side, maker_expected, taker_expected):
    episode = Episode("e", side, 10000, 1, btc_entry_qty_exact=Decimal("1"),
                      btc_entry_notional_exact=Decimal("83451"),
                      btc_entry_fees_exact=Decimal("37.55295"),
                      btc_entry_fill_count=1, btc_entry_fee_fill_count=1)
    venue = instrument()
    assert _fee_floor_price(venue, episode, maker=True).as_decimal() == maker_expected
    assert _fee_floor_price(venue, episode, maker=False).as_decimal() == taker_expected
    tp3 = Decimal("85970") if side == 1 else Decimal("81000")
    floor = _fee_floor_price(venue, episode, maker=True).as_decimal()
    assert (max if side == 1 else min)(tp3, floor) == tp3


def test_confirmed_partial_entry_vwap_fee_and_sol_rights():
    state = WaveOverlayState(Candidate())
    episode = Episode("e", 1, 10000, 1, wave_levels=(0, 0.01, 0.03))
    state.episode = episode
    entry = Intent("entry", "e", "BTC_ENTRY", None, 1, quantity=2)
    episode.pending[entry.id] = entry
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    state.on_fill(entry.id, 1, 83450, now, entry_fee=Decimal("37.5525"))
    state.on_fill(entry.id, 1, 83452, now, entry_fee=Decimal("37.5534"))
    assert episode.btc_entry_notional_exact == Decimal("166902")
    assert episode.btc_entry_fees_exact == Decimal("75.1059")
    assert episode.btc_entry_notional_exact / episode.btc_entry_qty_exact == Decimal("83451")
    state.on_parent_terminal(entry.id)
    tp = state.plan_confirmed_btc_targets()[0]
    assert episode.sol_rights == set()
    state.on_fill(tp.id, tp.quantity / 2, 83502, now)
    assert episode.sol_right_fraction[0] == pytest.approx(0.5)
    state.on_parent_cancelled(tp.id)
    replacement = state.plan_confirmed_btc_targets()[0]
    assert replacement.quantity == pytest.approx(tp.quantity / 2)
    assert _fee_floor_price(instrument(), episode, maker=True).as_decimal() == Decimal("83502")


def test_missing_entry_fee_fails_closed():
    episode = Episode("e", 1, 10000, 1, btc_entry_qty_exact=Decimal("1"),
                      btc_entry_notional_exact=Decimal("83451"), btc_entry_fill_count=1)
    with pytest.raises(ValueError, match="BTC_TP_ENTRY_FEE_EVIDENCE_INCOMPLETE"):
        _fee_floor_price(instrument(), episode, maker=True)
