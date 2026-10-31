"""E04 script/admission/API checks only: zero native engines or fixture runs."""
import ast
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
import importlib.metadata
import unittest
from unittest.mock import patch
from coinmaster.research import cm2_fixture_e04 as fixture
from coinmaster.strategy.cm2_policy import Config,Snapshot,State,decide,reconcile_btc_intent,HOUR_NS,MINUTE_NS
from coinmaster.strategy.cm2_execution import stage_targets


class E04PureTests(unittest.TestCase):
    def test_exact_contract_and_constructor_free_rejection(self):
        self.assertEqual(fixture.FIXTURE_ID,'cm2-current-child-native-v2')
        self.assertEqual(fixture.END_NS-fixture.START_NS,18*HOUR_NS)
        with patch('builtins.__import__',side_effect=AssertionError('IMPORT_BEFORE_CONTRACT_REJECTION')):
            with self.assertRaisesRegex(ValueError,'18H_CONTRACT'):
                fixture.run_fixture({'fixture_id':'wrong'})
        tree=ast.parse(Path(fixture.__file__).read_text())
        engines=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='BacktestEngine']
        self.assertEqual(len(engines),1)
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('adjust_account','adjust_balance') for n in ast.walk(tree)))
    def test_causal_script_capacity_prices_and_fixed_signed_funding(self):
        for h in (1,10):
            with self.assertRaises(KeyError):fixture.fixed_feature(h)
        for h in set(range(18))-{1,10}:
            f=fixture.fixed_feature(h)
            self.assertEqual(f.available_ns,fixture.START_NS+h*HOUR_NS)
            self.assertEqual(f.closed_ns,f.available_ns)
        self.assertEqual(fixture.btc_turnover(1)*D('.01')/D(1000),40)
        self.assertEqual(fixture.btc_turnover(540)*D('.01')/D(950),40)
        for minute,prices in ((2,(1000,100)),(3,(990,100)),(301,(1070,90)),(302,(1070,90)),
            (303,(990,100)),(361,(1070,90)),(541,(950,100)),(542,(960,100)),(841,(880,110)),
            (842,(880,110)),(843,(960,100)),(901,(880,110)),(1021,(980,100))):
            self.assertEqual(fixture.minute_prices(minute),tuple(map(D,prices)))
        first=-D(20)*D(990)*D('.0001')+D('148.5')*D(100)*D('.0001')
        second=D(20)*D(960)*D('.0001')-D(144)*D(100)*D('.0001')
        self.assertEqual((first,second),fixture.FUNDING_EXPECTED)
        self.assertEqual(first+second,D('-.015'))
        self.assertEqual(fixture.QUEUED_LATENCY_NS,240*1_000_000_000)
        self.assertEqual(fixture.QUEUE_PULSE_MINUTES,(504,1034))
        self.assertEqual(D(2)*D(980)*D('.000432'),D('.84672'))
    def snapshot(self,qty=40,price=990,sol=0):
        return Snapshot(D(10000),D(qty),D(sol),D(price),D(100),btc_vwap=D(1000),
            btc_entry_fees=D('17.28')*D(qty)/40,btc_signed_funding=D(0))
    def test_adverse_child_stale_clock_and_recovery_retained_cap(self):
        cfg=Config(load=8,core=.5,hedge_fraction=.75)
        st=State(direction=1,parent=1,initial_r=30,stop=970,extreme=1000,
            last_hour=fixture.START_NS,btc_target=D(80),unhedged_btc_target=D(80),
            btc_intent='INITIAL_ENTRY',intent_hour=fixture.START_NS)
        decision=decide(cfg,fixture.fixed_feature(0),self.snapshot(),st,now_ns=fixture.START_NS+3*MINUTE_NS)
        self.assertEqual(decision.btc_target,40)
        stale=decide(cfg,fixture.fixed_feature(0),self.snapshot(),decision.state,now_ns=fixture.START_NS+61*MINUTE_NS)
        self.assertEqual(stale.btc_target,20)
        repeated=decide(cfg,fixture.fixed_feature(0),self.snapshot(20),stale.state,now_ns=fixture.START_NS+62*MINUTE_NS)
        self.assertEqual(repeated.btc_target,20)
        st=repeated.state
        for h in (2,3):
            decision=decide(cfg,fixture.fixed_feature(h),self.snapshot(20),st,now_ns=fixture.START_NS+h*HOUR_NS+MINUTE_NS)
            self.assertEqual(decision.btc_target,20);st=decision.state
    def test_finite_harvest_guard_stage_and_unfilled_revoke(self):
        cfg=Config(load=8,core=.5,hedge_fraction=.75)
        s=replace(self.snapshot(20,1070,D('-148.5')),sol_mark=D(90),btc_signed_funding=D('-1.98'))
        st=State(direction=1,parent=1,initial_r=30,stop=970,extreme=990,last_hour=fixture.START_NS+4*HOUR_NS,
            btc_target=D(20),unhedged_btc_target=D(20),btc_intent='RISK_TRIM',hedge_active=True,activate_count=2)
        decision=decide(cfg,fixture.fixed_feature(5),s,st,now_ns=fixture.START_NS+5*HOUR_NS+MINUTE_NS)
        self.assertEqual(decision.state.harvest_target,10)
        bt,so,staged=stage_targets(decision,s,fixture.fixed_feature(5),sol_step=D('.01'),sol_min_qty=D('.01'),sol_min_notional=D(10))
        self.assertTrue(staged);self.assertEqual(bt,20);self.assertEqual(so,D('-118.88'))
        revoked,allowed,_=reconcile_btc_intent(cfg,fixture.fixed_feature(5),replace(s,btc_mark=D(990)),decision.state,
            now_ns=fixture.START_NS+5*HOUR_NS+3*MINUTE_NS,executable_price=D(990))
        self.assertFalse(allowed);self.assertFalse(revoked.harvested);self.assertIsNone(revoked.harvest_target)
        partial=replace(s,btc_qty=D(15),sol_qty=D(0),btc_entry_fees=D('6.48'))
        retained,allowed,_=reconcile_btc_intent(cfg,fixture.fixed_feature(6),partial,decision.state,
            now_ns=fixture.START_NS+6*HOUR_NS+MINUTE_NS+1,executable_price=D(1070))
        self.assertTrue(allowed);self.assertEqual(retained.harvest_target,10)
    def test_explicit_fixture_latency_fields_and_no_implicit_default(self):
        from nautilus_trader.backtest.models import LatencyModel
        zero=LatencyModel(base_latency_nanos=0)
        delayed=LatencyModel(base_latency_nanos=0,insert_latency_nanos=fixture.QUEUED_LATENCY_NS)
        self.assertEqual((zero.base_latency_nanos,zero.insert_latency_nanos,zero.cancel_latency_nanos),(0,0,0))
        self.assertEqual((delayed.base_latency_nanos,delayed.insert_latency_nanos,delayed.cancel_latency_nanos),
                         (0,fixture.QUEUED_LATENCY_NS,0))
        calls=[n for n in ast.walk(ast.parse(Path(fixture.__file__).read_text()))
               if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='LatencyModel']
        self.assertEqual(len(calls),3)
        for call in calls:
            base=next(k.value for k in call.keywords if k.arg=='base_latency_nanos')
            self.assertIsInstance(base,ast.Constant);self.assertEqual(base.value,0)
    def test_installed_public_fault_and_partial_api_source(self):
        native=Path(importlib.metadata.distribution('nautilus_trader').locate_file('nautilus_trader'))
        factory=(native/'common/factories.pyx').read_text()
        exchange=(native/'backtest/engine.pyx').read_text()
        partial=(native/'backtest/models/fill.pyx').read_text()
        self.assertIn('bint post_only = False',factory)
        self.assertIn('cpdef void set_latency_model(self, LatencyModel latency_model)',exchange)
        self.assertIn('command.ts_init + self.latency_model.insert_latency_nanos',exchange)
        self.assertIn('use_message_queue: bool = True',exchange)
        self.assertIn('cdef class LimitOrderPartialFillModel',partial)
        self.assertIn('size=Quantity(5, instrument.size_precision)',partial)


if __name__=='__main__':unittest.main()
