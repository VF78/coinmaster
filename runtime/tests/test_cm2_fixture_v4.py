"""No-engine v4 fixture contract checks; the actual API0 receipt is separate."""
import importlib
from dataclasses import asdict
from unittest.mock import patch
import unittest
from coinmaster.research import cm2_runner as runner
from coinmaster.strategy.cm2_policy import Config,HOUR_NS

class FixtureV4PrepTest(unittest.TestCase):
    def test_public_selector_import_and_test_policy_do_not_construct_engine(self):
        with patch('nautilus_trader.backtest.engine.BacktestEngine',side_effect=AssertionError('NO_ACTUAL_ENGINE')) as native:
            module=runner.engineering_fixture_module({'fixture_id':'cm2-systematic-repair-native-v4'})
            self.assertEqual(module.END_NS-module.START_NS,12*HOUR_NS)
            self.assertIsNotNone(module.TEST_ONLY_POLICY.parent_risk_fraction)
            self.assertIsNone(Config().parent_risk_fraction)
            self.assertEqual(module.TEST_ONLY_POLICY.version,'cm2-v2')
            native.assert_not_called()
    def test_variants_have_separate_frozen_modes_and_identical_single_engine_contract(self):
        module=runner.engineering_fixture_module({'fixture_id':'cm2-systematic-repair-trim-native-v4'})
        trim=module.test_policy(module.TRIM_FIXTURE_ID);joint=module.test_policy(module.FIXTURE_ID)
        self.assertEqual(trim.mode,'btc_trim');self.assertEqual(joint.mode,'joint')
        self.assertEqual(trim.restore_lifetime_ns,HOUR_NS)
        self.assertEqual(module.fixed_feature(4,trim.mode).close,1000)
        self.assertEqual(module.prices(260,trim.mode)[0],1000)
    def test_wrong_fixture_policy_refuses_before_native_boundary(self):
        module=runner.engineering_fixture_module({'fixture_id':'cm2-systematic-repair-native-v4'})
        with patch('nautilus_trader.backtest.engine.BacktestEngine',side_effect=AssertionError('NO_ACTUAL_ENGINE')) as native:
            with self.assertRaisesRegex(ValueError,'TEST_ONLY_POLICY_REQUIRED'):
                module.run_fixture({'fixture_id':module.FIXTURE_ID,'start_ns':module.START_NS,'end_ns':module.END_NS,'fixture_policy':asdict(Config())})
            native.assert_not_called()
    def test_stock_cancel_latency_api_without_engine(self):
        from nautilus_trader.backtest.models import LatencyModel
        with patch('nautilus_trader.backtest.engine.BacktestEngine',side_effect=AssertionError('NO_ACTUAL_ENGINE')) as native:
            model=LatencyModel(base_latency_nanos=0,cancel_latency_nanos=120_000_000_000)
            self.assertEqual(type(model).__name__,'LatencyModel')
            native.assert_not_called()
    def test_script_is_finite_and_feature_available_at_own_clock(self):
        module=runner.engineering_fixture_module({'fixture_id':'cm2-systematic-repair-native-v4'})
        for hour in range(12):
            f=module.fixed_feature(hour)
            self.assertEqual(f.available_ns,f.closed_ns)
            self.assertGreaterEqual(f.closed_ns,module.START_NS)
            self.assertLess(f.closed_ns,module.END_NS)
        with self.assertRaises(KeyError):module.fixed_feature(12)

if __name__=='__main__':unittest.main()
