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
    def test_stock_touch_depth_and_finite_native_reduction_without_engine(self):
        from decimal import Decimal as D
        from pathlib import Path
        from nautilus_trader.common.component import TestClock
        from nautilus_trader.common.factories import OrderFactory
        from nautilus_trader.model.identifiers import TraderId,StrategyId
        from nautilus_trader.model.enums import OrderSide,TimeInForce
        from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
        from coinmaster.research.native_full_fill import ZeroImpactFullFillDiagnostic
        from coinmaster.research import cm2_fixture_v4 as fixture
        with patch('nautilus_trader.backtest.engine.BacktestEngine',side_effect=AssertionError('NO_ACTUAL_ENGINE')) as native:
            btc=load_current_hl_diagnostic(Path(__file__).parent/'fixtures/hl-current-20261029').instruments[0]
            factory=OrderFactory(TraderId('CM2-001'),StrategyId('CM2-001'),TestClock())
            model=fixture.V4PartialModel()
            self.assertFalse(ZeroImpactFullFillDiagnostic().is_limit_filled())
            self.assertTrue(model.is_limit_filled())
            qty=fixture.finite_reduction_witness_quantity(D('39.11125'),D('20.490195'))
            self.assertEqual(qty,D(10));self.assertGreater(qty,fixture.STOCK_LIMIT_TOUCH_DEPTH)
            order=factory.limit(btc.id,OrderSide.SELL,btc.make_qty(qty),btc.make_price('1200'),time_in_force=TimeInForce.GTC,reduce_only=True)
            book=model.get_orderbook_for_fill_simulation(btc,order,btc.make_price('1200'),btc.make_price('1200'))
            fills=book.simulate_fills(order,btc.price_precision,btc.size_precision,False)
            self.assertEqual(sum(q.as_decimal() for _,q in fills),D(5))
            self.assertLess(sum(q.as_decimal() for _,q in fills),qty)
            for actual,target,want in [('8','2','6'),('8','7','1'),('8','8','0'),('8','-1','0'),('-8','-2','0')]:
                self.assertEqual(fixture.finite_reduction_witness_quantity(D(actual),D(target)),D(want))
            market=factory.market(btc.id,OrderSide.SELL,btc.make_qty('1'),time_in_force=TimeInForce.IOC,reduce_only=True)
            a=model.get_orderbook_for_fill_simulation(btc,market,btc.make_price('1000'),btc.make_price('1000')).simulate_fills(market,btc.price_precision,btc.size_precision,True)
            b=ZeroImpactFullFillDiagnostic().get_orderbook_for_fill_simulation(btc,market,btc.make_price('1000'),btc.make_price('1000')).simulate_fills(market,btc.price_precision,btc.size_precision,True)
            self.assertEqual(a,b)
            native.assert_not_called()
    def test_trim_witness_after_two_held_adverse_hours_has_finite_actual_target(self):
        from decimal import Decimal as D
        from dataclasses import replace
        from coinmaster.research import cm2_fixture_v4 as fixture
        from coinmaster.strategy.cm2_policy import State,decide,MINUTE_NS
        from runtime.tests.test_cm2_policy import snap
        cfg=fixture.test_policy(fixture.TRIM_FIXTURE_ID)
        f0=fixture.fixed_feature(0,'btc_trim');f1=fixture.fixed_feature(1,'btc_trim');f2=fixture.fixed_feature(2,'btc_trim')
        s=snap(btc_qty=D(0));first=decide(cfg,f0,s,State(),now_ns=f0.closed_ns+MINUTE_NS)
        held=replace(s,btc_qty=D(40));parent=decide(cfg,f0,held,first.state,now_ns=f0.closed_ns+2*MINUTE_NS)
        self.assertEqual(parent.state.activate_count,0)
        one=decide(cfg,f1,held,parent.state,now_ns=f1.closed_ns+MINUTE_NS)
        self.assertEqual(one.state.activate_count,1);self.assertFalse(one.state.hedge_active)
        two=decide(cfg,f2,replace(held,btc_mark=D(1020)),one.state,now_ns=f2.closed_ns+MINUTE_NS)
        self.assertEqual(two.state.activate_count,2);self.assertTrue(two.state.hedge_active)
        self.assertEqual(two.reason,'MATCHED_BTC_TRIM');self.assertEqual(two.state.btc_intent,'RISK_TRIM')
        self.assertGreater(fixture.finite_reduction_witness_quantity(D(38),two.btc_target),fixture.STOCK_LIMIT_TOUCH_DEPTH)
        self.assertGreater(fixture.witness_clock('btc_trim')['submit'],2*HOUR_NS)
    def test_native_witness_touch_after_cancel_before_actual_latency_ack(self):
        from coinmaster.research import cm2_fixture_v4 as fixture
        for mode in ('joint','btc_trim'):
            c=fixture.witness_clock(mode)
            self.assertLess(c['submit'],c['cancel'])
            self.assertLess(c['cancel'],c['touch'])
            self.assertLess(c['touch'],c['revert'])
            self.assertLess(c['revert'],c['cancel']+fixture.CANCEL_LATENCY_NS)
    def test_script_is_finite_and_feature_available_at_own_clock(self):
        module=runner.engineering_fixture_module({'fixture_id':'cm2-systematic-repair-native-v4'})
        for hour in range(12):
            f=module.fixed_feature(hour)
            self.assertEqual(f.available_ns,f.closed_ns)
            self.assertGreaterEqual(f.closed_ns,module.START_NS)
            self.assertLess(f.closed_ns,module.END_NS)
        with self.assertRaises(KeyError):module.fixed_feature(12)

if __name__=='__main__':unittest.main()
