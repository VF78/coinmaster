"""Optional native-equity controller regressions; explicit boundary fakes, engines0."""
from dataclasses import replace
from decimal import Decimal as D
import json
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch
from coinmaster.strategy.cm2_policy import Config, State, observe_emergency_equity, decide, btc_child_permission, validate_emergency_checkpoint
from coinmaster.strategy.cm2_native import CM2Strategy
from coinmaster.strategy.cm2_checkpoint import KEY, canonical, decode
from runtime.tests.test_cm2_policy import feat, snap, state, configured

class EmergencyDrawdownTests(unittest.TestCase):
    def seeded(self, cfg=None):
        cfg = cfg or configured(emergency_drawdown_fraction=.45)
        return observe_emergency_equity(cfg, State(), D(10000), known=True, now_ns=1, initial=True)

    def test_initial_seed_first_loss_rising_peak_and_equality_latch(self):
        cfg = configured(emergency_drawdown_fraction=.45)
        st = self.seeded(cfg)
        st = observe_emergency_equity(cfg, st, D(5600), known=True, now_ns=2)
        self.assertFalse(st.emergency_latched)
        st = observe_emergency_equity(cfg, st, D(12000), known=True, now_ns=3)
        self.assertEqual(st.emergency_peak_equity, D(12000))
        st = observe_emergency_equity(cfg, st, D(6600), known=True, now_ns=4)
        self.assertTrue(st.emergency_latched)
        self.assertEqual(st.emergency_trigger_peak_equity, D(12000))
        self.assertEqual((st.emergency_trigger_equity, st.emergency_trigger_ns, st.emergency_trigger_fraction), (D(6600), 4, D('.45')))
        for changed in (replace(cfg, emergency_drawdown_fraction=.9), replace(cfg, emergency_drawdown_fraction=None)):
            later = observe_emergency_equity(changed, st, D(30000), known=True, now_ns=5)
            self.assertTrue(later.emergency_latched)
            self.assertEqual(later.emergency_trigger_equity, D(6600))
            self.assertEqual(later.emergency_peak_equity, D(30000))
            self.assertEqual(later.emergency_trigger_peak_equity, D(12000))
            self.assertEqual(later.emergency_trigger_peak_equity*(D(1)-later.emergency_trigger_fraction), D(6600))
            result = decide(changed, feat(), snap(btc_qty=D(0)), later)
            self.assertEqual(result.reason, 'EMERGENCY_DRAWDOWN_DRAIN')
            self.assertEqual(result.btc_target, D(0))

    def test_unknown_and_unseeded_valuation_do_not_invent_peak_or_trigger(self):
        cfg = configured(emergency_drawdown_fraction=.45)
        unseeded = observe_emergency_equity(cfg, State(), D(5000), known=True, now_ns=2)
        self.assertIsNone(unseeded.emergency_peak_equity)
        self.assertFalse(unseeded.emergency_valuation_known)
        for equity, known in [(D(1), False), (D('NaN'), True), (None, True)]:
            st = observe_emergency_equity(cfg, self.seeded(cfg), equity, known=known, now_ns=3)
            self.assertEqual(st.emergency_peak_equity, D(10000))
            self.assertFalse(st.emergency_latched)
            self.assertFalse(st.emergency_valuation_known)
            held = decide(cfg, feat(), snap(btc_qty=D(0)), st)
            self.assertEqual(held.reason, 'EMERGENCY_EQUITY_UNKNOWN')
            stop = decide(cfg, feat(), snap(btc_qty=D(1), btc_mark=D(90)), replace(st, direction=1, stop=95))
            self.assertEqual(stop.reason, 'PROTECTIVE_STOP')

    def test_disabled_is_identity_and_unchanged_policy_decision(self):
        cfg = configured()
        st = state()
        self.assertIsNone(cfg.emergency_drawdown_fraction)
        self.assertIs(observe_emergency_equity(cfg, st, D(1), known=False, now_ns=2), st)
        self.assertEqual(decide(cfg, feat(), snap(), st), decide(replace(cfg, emergency_drawdown_fraction=None), feat(), snap(), st))
        fake = N(config=N(policy=cfg), policy_state=st, _snapshot=lambda ns: self.fail('disabled path sampled equity'))
        CM2Strategy._check_emergency_drawdown(fake, 10)
        self.assertIs(fake.policy_state, st)

    def test_normal_parent_drain_keeps_peak_and_latch_does_not_clear_when_flat(self):
        cfg = configured(emergency_drawdown_fraction=.45)
        seeded = replace(self.seeded(cfg), draining=True)
        clean = decide(cfg, feat(), snap(btc_qty=D(0)), seeded).state
        self.assertEqual(clean.emergency_peak_equity, D(10000))
        self.assertTrue(clean.emergency_valuation_known)
        latched = observe_emergency_equity(cfg, clean, D(5500), known=True, now_ns=4)
        flat = decide(cfg, feat(), snap(btc_qty=D(0)), latched).state
        self.assertTrue(flat.emergency_latched)
        self.assertTrue(flat.draining)

    def test_seed_uses_native_initial_cash_only_when_no_positions_orders_or_history(self):
        cfg = configured(emergency_drawdown_fraction=.45)
        cash = N(as_decimal=lambda: D(10000))
        account = N(base_currency='USDC', balance_total=lambda c: cash)
        for positions, orders, owned, expected in [([], [], {}, D(10000)), ([object()], [], {}, None), ([], [object()], {}, None), ([], [], {'old': {}}, None)]:
            fake = N(config=N(policy=cfg, btc_id=N(venue='V')), policy_state=State(), _owned=owned, clock=N(timestamp_ns=lambda: 1), cache=N(positions_open=lambda: positions, orders_open=lambda: orders, orders_inflight=lambda: [], account_for_venue=lambda v: account), _persist_checkpoint=lambda: None)
            CM2Strategy._seed_emergency_peak(fake)
            self.assertEqual(fake.policy_state.emergency_peak_equity, expected)

    def test_adapter_latches_cancels_both_then_uses_existing_native_ro_quote_path(self):
        from runtime.tests.test_cm2_final_send_contract import FinalSendTest
        with patch('nautilus_trader.backtest.engine.BacktestEngine', side_effect=AssertionError('NO_ENGINE')) as engine:
            fake, btc, tick, original, _, sent, canceled = FinalSendTest().fixture(qty=D(1), price=D(1000), draining=False)
            cfg = configured(emergency_drawdown_fraction=.45)
            fake.config.policy = cfg
            fake.policy_state = replace(self.seeded(cfg), direction=1, parent=1, btc_target=D(1), sol_target=D(-10), btc_intent='HOLD')
            current = replace(original, equity=D(5500), btc_qty=D(1), sol_qty=D(-10), btc_pending=D('.5'))
            fake._snapshot = lambda ns: current
            fake._latest_marks = {i: N(ts_event=fake.clock.now) for i in (fake.config.btc_id, fake.config.sol_id)}
            orders = {fake.config.btc_id: N(client_order_id='BTC-pending', is_reduce_only=False), fake.config.sol_id: N(client_order_id='SOL-pending', is_reduce_only=False)}
            fake._orders = lambda i: [orders[i]]
            CM2Strategy._check_emergency_drawdown(fake, fake.clock.now)
            self.assertTrue(fake.policy_state.emergency_latched)
            self.assertEqual(len(canceled), 2)
            first_deadline = fake._drain['deadline_ns']
            self.assertFalse(fake._liquidating)
            self.assertEqual(set(fake._drain['scoped_zero_ids']), {str(fake.config.btc_id), str(fake.config.sol_id)})
            # Explicit post-ACK input boundary; no native fill/status is synthesized.
            current = replace(current, btc_pending=D(0))
            fake._orders = lambda i: []
            for i in (fake.config.btc_id, fake.config.sol_id):
                CM2Strategy.on_quote_tick(fake, N(**vars(fake._quotes[i]), instrument_id=i))
            self.assertEqual(len(sent), 2)
            self.assertTrue(all(o.is_reduce_only and o.order_type.name == 'MARKET' for o in sent))
            self.assertEqual(fake._drain['deadline_ns'], first_deadline)
            self.assertEqual((current.btc_qty, current.sol_qty), (D(1), D(-10)))
            # A late-fill quantity snapshot remains inside the same latched drain.
            current = replace(current, btc_qty=D('1.5'))
            CM2Strategy._update_drain(fake, fake.clock.now, current, decide(cfg, fake.current_features, current, fake.policy_state))
            self.assertEqual(fake._drain['deadline_ns'], first_deadline)
            self.assertTrue(fake.policy_state.emergency_latched)
            engine.assert_not_called()

    def test_checkpoint_retains_latch_and_rejects_missing_peak_or_trigger(self):
        from runtime.tests.test_cm2_checkpoint import CheckpointTests
        helper = CheckpointTests()
        helper.setUp()
        try:
            obj = helper.fake()
            cfg = configured(emergency_drawdown_fraction=.45)
            obj.config.policy = cfg
            latched = observe_emergency_equity(cfg, self.seeded(cfg), D(5500), known=True, now_ns=4)
            obj.policy_state = latched
            saved = obj.on_save()
            obj.policy_state = State()
            obj.on_load(saved)
            self.assertEqual(obj.policy_state, latched)
            doc = decode(json.loads(saved[KEY]))
            doc['domain']['policy_state'].pop('emergency_peak_equity')
            body = canonical(doc)
            obj._checkpoint_revision = helper.store.persist(body, obj._checkpoint_revision)
            with self.assertRaisesRegex(ValueError, 'EMERGENCY_STATE_REQUIRED'):
                obj.on_load({KEY: body})
            self.assertTrue(obj.policy_state.emergency_latched)
            for bad in (replace(latched, emergency_peak_equity=None), replace(latched, emergency_trigger_equity=None), replace(latched, emergency_trigger_peak_equity=None)):
                with self.assertRaises(ValueError):
                    validate_emergency_checkpoint(bad, enabled=True)
            obj.config.policy = replace(cfg, emergency_drawdown_fraction=None)
            with self.assertRaises(ValueError):
                obj.on_load(saved)
            self.assertTrue(obj.policy_state.emergency_latched)
        finally:
            helper.tearDown()

    def test_between_mark_native_cash_loss_latches_before_admission(self):
        from runtime.tests.test_cm2_final_send_contract import FinalSendTest
        fake, btc, _, original, _, sent, _ = FinalSendTest().fixture(qty=D(1), price=D(1000), draining=False)
        cfg = configured(emergency_drawdown_fraction=.45)
        fake.config.policy = cfg
        fake.policy_state = replace(self.seeded(cfg), direction=1, parent=1, btc_target=D(1))
        current = replace(original, equity=D(5500))
        fake._snapshot = lambda ns: current
        # Identical still-fresh marks; only authoritative current cash changed.
        fake._latest_marks = {i: N(ts_event=fake.clock.now-1) for i in (fake.config.btc_id, fake.config.sol_id)}
        fake.cache.account_for_venue = lambda venue: N()
        result = CM2Strategy._admit(fake, btc.id, D(1), D(1000), original, fake.clock.now)
        self.assertFalse(result)
        self.assertTrue(fake.policy_state.emergency_latched)
        self.assertEqual(fake.policy_state.emergency_trigger_equity, D(5500))
        self.assertEqual(fake.policy_state.emergency_trigger_peak_equity, D(10000))
        self.assertEqual(sent, [])

    def test_same_native_valuation_observes_mm_breach_and_dd_latch(self):
        from runtime.tests.test_cm2_final_send_contract import FinalSendTest
        from coinmaster.venues.marks import venue_mark
        fake, btc, _, original, _, _, _ = FinalSendTest().fixture(qty=D(1), price=D(1000), draining=False)
        cfg = configured(emergency_drawdown_fraction=.45)
        fake.config.policy = cfg
        fake.policy_state = replace(self.seeded(cfg), direction=1, parent=1, btc_target=D(1))
        current = replace(original, equity=D(5500))
        fake._snapshot = lambda ns: current
        fake._latest_marks = {}
        position = N(instrument_id=btc.id, quantity=N(as_decimal=lambda: D(1)))
        fake.cache.positions_open = lambda: [position]
        fake.config.margin_policy = N(update_mark=lambda mark: None, margin_for=lambda *a: (D(0), D(6000)))
        fake._liquidation_checks = 0
        fake._liquidation_unknown = 0
        fake._risk_unknown = False
        fake.liquidation_audit = []
        fake._check_liquidation = lambda ns: CM2Strategy._check_liquidation(fake, ns)
        for iid in (fake.config.btc_id, fake.config.sol_id):
            CM2Strategy.on_data(fake, venue_mark(iid, D(1000), fake.clock.now))
        self.assertEqual(fake._liquidation_checks, 1)
        self.assertEqual(len(fake.liquidation_audit), 1)
        self.assertTrue(fake._liquidating)
        self.assertTrue(fake.policy_state.emergency_latched)
        self.assertEqual(fake.policy_state.emergency_trigger_equity, D(5500))

    def test_invalid_fraction_rejected_without_implicit_default(self):
        for value in (0, -1, 1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                Config(emergency_drawdown_fraction=value)

if __name__ == '__main__':
    unittest.main()
