from decimal import Decimal as D
import pytest
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.objects import Price, Quantity
from coinmaster.domain.wave_overlay import Episode
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from coinmaster.venues.marks import VenueMark
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
from test_wave_native_integration import lifecycle_config, native_engine


@pytest.mark.parametrize("side", [1, -1])
@pytest.mark.parametrize("cap", [None, D("6")])
def test_native_sol_cap_partial_fill_retries_and_default(side, cap):
    class Probe(WaveOverlayStrategy):
        def __init__(self, config):
            super().__init__(config)
            self.snapshots = []
        def on_quote_tick(self, tick):
            if tick.instrument_id != self.config.sol_id:
                return
            self._latest_marks = {BTC_PERP.id: VenueMark(BTC_PERP.id, D("100"), tick.ts_event),
                                  SOL_PERP.id: VenueMark(SOL_PERP.id, D("100"), tick.ts_event)}
            if self._domain.episode is None:
                self._domain.episode = Episode("cap", -side, 10000, 1.0)
            intent = self._domain._intent(self._domain.episode, "SOL_ADD", side, 0, requested_notional=100000)
            self._submit_intent(intent, 100, 100, 0.01, 0, ts_now=tick.ts_event)
            # Try again in the same callback: pending native submission must
            # prevent both admissions claiming the same available room.
            duplicate = self._domain._intent(self._domain.episode, "SOL_ADD", side, 1, requested_notional=100000)
            self._submit_intent(duplicate, 100, 100, 0.01, 0, ts_now=tick.ts_event)
        def _advance_current_day(self):
            pass
        def _tier_allows_increase(self, *args):
            return True
    strategy = Probe(lifecycle_config(research_sol_notional_cap_multiple=cap, max_mark_age_ns=100))
    engine = native_engine(strategy)
    ticks = [QuoteTick(SOL_PERP.id, Price.from_str("100.00"), Price.from_str("100.00"),
                       Quantity.from_str("250.0"), Quantity.from_str("250.0"), t, t) for t in range(1, 6)]
    engine.add_data(ticks); engine.run()
    try:
        position = engine.cache.positions_open()[0]
        if cap is not None:
            assert position.quantity.as_decimal() == D("596.4")
            assert len(strategy.fill_audit) == 3
            assert strategy._domain.episode.sol_qty == float(position.quantity)
            assert strategy._domain.episode.sol_add_filled_notional[0] == 59640
            assert any(row.get("reason") == "SOL_SUBMISSION_PENDING" for row in strategy.sol_cap_admission_audit)
            for row in strategy.sol_cap_admission_audit:
                if "native_equity" in row:
                    assert D(row["prospective_notional_upper"]) <= D("6") * (D(row["native_equity"]) - D(row["reserved_taker_fee"]))
        else:
            assert position.quantity.as_decimal() > D("600")
            assert strategy.sol_cap_admission_audit == []
    finally:
        engine.dispose()


def test_cap_missing_stale_and_future_marks_fail_closed():
    strategy = WaveOverlayStrategy(lifecycle_config(research_sol_notional_cap_multiple=D("6"), max_mark_age_ns=10))
    engine = native_engine(strategy)
    try:
        assert strategy._research_sol_cap_quantity(D("100"), D("100"), 20) == 0
        for timestamp in (1, 21):
            strategy._latest_marks = {i: VenueMark(i, D("100"), timestamp) for i in (BTC_PERP.id, SOL_PERP.id)}
            assert strategy._research_sol_cap_quantity(D("100"), D("100"), 20) == 0
        assert all(row["reason"] == "FRESH_NATIVE_MARKS_MISSING" for row in strategy.sol_cap_admission_audit)
    finally:
        engine.dispose()

def test_cap_quantity_reserves_fee_and_mark_execution_gap_and_floors():
    class Probe(WaveOverlayStrategy):
        def __init__(self, config):
            super().__init__(config)
            self.quantities = []
        def on_quote_tick(self, tick):
            self._latest_marks = {i: VenueMark(i, D("100"), tick.ts_event) for i in (BTC_PERP.id, SOL_PERP.id)}
            for executable in (D("99"), D("100"), D("101")):
                q = self._research_sol_cap_quantity(D("1000"), executable, tick.ts_event)
                self.quantities.append(q)
                audit = self.sol_cap_admission_audit[-1]
                total = D(audit["prospective_notional_upper"])
                equity = D(audit["native_equity"])
                reserve = D(audit["reserved_taker_fee"]) + D(audit["reserved_mark_execution_gap_loss"])
                assert total <= 6 * (equity - reserve)
                step = SOL_PERP.size_increment.as_decimal()
                unit = max(executable, D("100")) + 6 * (executable * SOL_PERP.taker_fee + abs(executable - 100))
                assert (q + step) * unit > 60000
                assert q % step == 0
    strategy = Probe(lifecycle_config(research_sol_notional_cap_multiple=D("6"), max_mark_age_ns=10))
    engine = native_engine(strategy)
    engine.add_data([QuoteTick(SOL_PERP.id, Price.from_str("100.00"), Price.from_str("100.00"),
                     Quantity.from_str("1000.0"), Quantity.from_str("1000.0"), 1, 1)])
    engine.run()
    try:
        assert strategy.quantities[1] > strategy.quantities[0] > strategy.quantities[2]
    finally:
        engine.dispose()
