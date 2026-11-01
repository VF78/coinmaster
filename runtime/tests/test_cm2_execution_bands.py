"""Core-independent frozen execution geometry; no engine constructors."""
from dataclasses import asdict, replace
from decimal import Decimal as D
import json
import unittest
from coinmaster.strategy.cm2_policy import Config, State, Features, Day, Hour, HOUR_NS, features, slow_features, decide, btc_child_permission, execution_band_width
from coinmaster.strategy.cm2_checkpoint import canonical, decode
from runtime.tests.test_cm2_policy import feat, snap, state, configured

class ExecutionBandTests(unittest.TestCase):
    def base_and_slow(self, d=1):
        f = feat(close=1010 if d > 0 else 990, channel_high=1005, channel_low=995, atr=10, execution_atr=3)
        days = tuple(Day(f.closed_ns-(34-i)*24*HOUR_NS, f.closed_ns-(34-i)*24*HOUR_NS, 1000+d*i, 1050+d*i, 950+d*i, 1000+d*i) for i in range(35))
        return f, slow_features(f, days, (Hour(f.closed_ns, f.closed_ns, 1000, 1010, 990, 1000, 100),), f.available_ns)

    def test_h1_simple_atr24_survives_d1_core_replacement(self):
        for d in (1, -1):
            base, slow = self.base_and_slow(d)
            self.assertEqual(slow.execution_atr, 3)
            self.assertNotEqual(slow.atr, base.atr)
            widths = []
            for mode, f in [('h1_breakout', base), ('slow_d1_h4', slow)]:
                result = decide(configured(core_signal=mode, initial_band_atr=2), f, snap(btc_qty=D(0)), State())
                self.assertNotEqual(result.btc_target, 0)
                self.assertEqual(result.state.initial_anchor, D(1000))
                widths.append(result.state.initial_band_width)
            self.assertEqual(widths, [D(6), D(6)])
        hours = tuple(Hour(i*HOUR_NS, i*HOUR_NS, 1000, 1002, 998, 1000, 100) for i in range(1, 171))
        normal = features(hours, Config(), hours[-1].available_ns)
        self.assertEqual((normal.atr, normal.execution_atr), (4, 4))

    def test_initial_width_does_not_follow_future_execution_or_core_atr(self):
        for d in (1, -1):
            f, _ = self.base_and_slow(d)
            cfg = configured(initial_band_atr=2)
            admitted = decide(cfg, f, snap(btc_qty=D(0)), State()).state
            for rolling, core in [(1, 1), (1000, 10000), (0, 10)]:
                later = replace(f, execution_atr=rolling, atr=core)
                self.assertTrue(btc_child_permission(cfg, later, snap(btc_qty=D(0)), admitted, now_ns=f.available_ns+2, executable_price=D(1000+d*6))[0])
                self.assertFalse(btc_child_permission(cfg, later, snap(btc_qty=D(0)), admitted, now_ns=f.available_ns+2, executable_price=D(1000+d*7))[0])
            self.assertEqual(admitted.initial_band_width, D(6))

    def test_restore_frozen_width_expiry_and_no_epoch_rearm(self):
        for d in (1, -1):
            f, _ = self.base_and_slow(d)
            cfg = configured(mode='btc_trim', restore_band_atr=2, restore_lifetime_ns=HOUR_NS)
            st = state(direction=d, btc_target=D(d), stop=900 if d > 0 else 1100, btc_intent='MATCHED_RESTORE', restore_target=D(d), restore_anchor=D(1000), restore_band_width=D(6), restore_deadline_ns=f.available_ns+HOUR_NS, last_hour=f.closed_ns)
            actual = snap(btc_qty=D(d)*D('.5'))
            changed = replace(f, execution_atr=10000, atr=1000)
            self.assertTrue(btc_child_permission(cfg, changed, actual, st, now_ns=f.available_ns+2, executable_price=D(1000+d*6))[0])
            self.assertFalse(btc_child_permission(cfg, changed, actual, st, now_ns=f.available_ns+2, executable_price=D(1000+d*7))[0])
            later = replace(changed, closed_ns=f.closed_ns+HOUR_NS, available_ns=f.available_ns+HOUR_NS, close=1000)
            result = decide(cfg, later, actual, st, now_ns=st.restore_deadline_ns+1)
            self.assertEqual(result.btc_target, actual.btc_qty)
            self.assertEqual((result.state.restore_anchor, result.state.restore_band_width, result.state.restore_deadline_ns), (st.restore_anchor, st.restore_band_width, st.restore_deadline_ns))
            self.assertNotEqual(result.state.btc_intent, 'MATCHED_RESTORE')

    def test_missing_unknown_units_and_legacy_missing_width_fail_closed(self):
        f, _ = self.base_and_slow()
        cfg = configured(initial_band_atr=2)
        for unknown in (0, -1, float('nan'), float('inf'), None):
            self.assertIsNone(execution_band_width(2, unknown))
            held = decide(cfg, replace(f, execution_atr=unknown), snap(btc_qty=D(0)), State())
            self.assertEqual((held.btc_target, held.reason), (D(0), 'EXECUTION_ATR_UNKNOWN'))
        admitted = decide(cfg, f, snap(btc_qty=D(0)), State()).state
        old = asdict(admitted)
        old.pop('initial_band_width')
        old.pop('restore_band_width')
        self.assertFalse(btc_child_permission(cfg, f, snap(btc_qty=D(0)), State(**old), now_ns=f.available_ns+2, executable_price=D(1000))[0])
        for width in (None, D(0), D('NaN'), D('Infinity')):
            self.assertFalse(btc_child_permission(cfg, f, snap(btc_qty=D(0)), replace(admitted, initial_band_width=width), now_ns=f.available_ns+2, executable_price=D(1000))[0])

    def test_checkpoint_roundtrip_retains_widths_and_execution_unit(self):
        f, _ = self.base_and_slow()
        st = decide(configured(initial_band_atr=2), f, snap(btc_qty=D(0)), State()).state
        st = replace(st, restore_band_width=D('2.75'), restore_anchor=D(1000), restore_deadline_ns=123)
        restored = decode(json.loads(canonical({'state': asdict(st), 'features': asdict(f)})))
        self.assertEqual(State(**restored['state']), st)
        self.assertEqual(canonical(Features(**restored['features'])), canonical(f))

    def test_unknown_execution_geometry_does_not_suppress_known_stop(self):
        for d in (1, -1):
            result = decide(configured(), replace(feat(), execution_atr=0), snap(btc_qty=D(d), btc_mark=D(90 if d > 0 else 110)), state(direction=d, stop=95 if d > 0 else 105))
            self.assertEqual((result.reason, result.btc_target), ('PROTECTIVE_STOP', D(0)))
            self.assertTrue(result.state.draining)

if __name__ == '__main__':
    unittest.main()
