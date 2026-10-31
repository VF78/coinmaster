"""Actual CM2 callback on explicit fakes; native order objects, no native fills/engine."""
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch
import unittest
from coinmaster.strategy.cm2_native import CM2Strategy
from coinmaster.strategy.cm2_policy import Config,State,Snapshot,Features,Decision,HOUR_NS
from coinmaster.strategy.cm2_execution import ExecutionLimits
from coinmaster.strategy.cm2_order_contract import MODEL_ID,FRESH_NS
from test_cm2_order_contract import Clock

class FinalSendTest(unittest.TestCase):
    def fixture(self,symbol="BTC",qty=D(500),price=D(80000),draining=True,known=True,harvest=False):
        from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
        from nautilus_trader.common.factories import OrderFactory
        from nautilus_trader.common.component import TestClock
        from nautilus_trader.model.identifiers import TraderId,StrategyId
        profile=load_current_hl_diagnostic(Path(__file__).parent/"fixtures/hl-current-20261029")
        btc,sol=profile.instruments;i=btc if symbol=="BTC" else sol
        now=200*HOUR_NS+1;clock=Clock(now);sent=[];canceled=[]
        quote=lambda px:N(ts_event=now,bid_price=N(as_decimal=lambda:px),ask_price=N(as_decimal=lambda:px))
        s=Snapshot(D("1e9"),qty if symbol=="BTC" else D(0),qty if symbol=="SOL" else D(0),
            price if symbol=="BTC" else D(80000),price if symbol=="SOL" else D(200),
            btc_vwap=D(1000),btc_entry_fees=D(".432"),btc_signed_funding=D(0),data_known=known)
        st=State(direction=1,parent=1,btc_target=D(".75") if harvest else D(0),sol_target=D(0),
            btc_intent="POSITIVE_HARVEST" if harvest else "RISK_TRIM",draining=draining,
            harvest_target=D(".75") if harvest else None,last_hour=200*HOUR_NS)
        f=Features(200*HOUR_NS,200*HOUR_NS,True,hedge_valid=True,beta_guard=1,close=float(s.btc_mark))
        cfg=N(btc_id=btc.id,sol_id=sol.id,policy=Config(),trading_start_open_ns=0,terminal_close_at_ns=10**25,
            limits=ExecutionLimits(D("1e100")),margin_policy=profile.margin_policy(FRESH_NS),
            execution_policy_hash="UNCHANGED_NATIVE_FILL_POLICY",exit_fee_rate=D(".000432"))
        fake=N(id="FAKE-ADAPTER",clock=clock,config=cfg,current_features=f,policy_state=st,
            _quotes={btc.id:quote(s.btc_mark),sol.id:quote(s.sol_mark)},_snapshot=lambda ns:s,
            _owned={},_order_audit={},_last_child={},_drain=None,drain_audit=[],
            _liquidating=False,_restore_failed=False,pre_submit_gate_blocks=[],child_permission_audit=[],
            _admission_sources={"cm2_order_contract.py":"source-test-hash"},target_blockers={},
            orphan_started_ns=None,orphan_intervals=[],cache=N(instrument=lambda iid:btc if iid==btc.id else sol),
            _orders=lambda iid:[],cancel_order=lambda o:canceled.append(o),_persist_checkpoint=lambda:None,
            _chain_audit=lambda *a:None,_audit=lambda *a:None,_child_capacity=lambda iid,ns:D(1),
            submit_order=lambda o:sent.append(o),
            order_factory=OrderFactory(TraderId("AUDIT-001"),StrategyId("AUDIT-001"),TestClock()))
        fake._permission_context=lambda *a:CM2Strategy._permission_context(fake,*a)
        fake._make_order=lambda *a:CM2Strategy._make_order(fake,*a)
        fake._admit=lambda *a:True # margin is separately tested; no fake account constructed here.
        decision=Decision(st.btc_target,st.sol_target,"TEST_ONLY_EXPLICIT_STOP" if draining else "TEST_ONLY_HARVEST",st,draining)
        return fake,i,quote(price),s,decision,sent,canceled

    def test_actual_callback_segments_emergency_and_terminal_per_asset(self):
        with patch("nautilus_trader.backtest.engine.BacktestEngine",side_effect=AssertionError("NO_ENGINE")) as engine:
            for symbol,qty,px,expected in (("BTC",D(500),D(80000),D(375)),("SOL",D(50000),D(200),D(25000))):
                for terminal in (False,True):
                    fake,i,tick,s,decision,sent,_=self.fixture(symbol,qty,px,known=False)
                    if terminal:fake.config.terminal_close_at_ns=fake.clock.now
                    with patch("coinmaster.strategy.cm2_native.decide",return_value=decision):
                        CM2Strategy.on_quote_tick(fake,N(**vars(tick),instrument_id=i.id))
                    self.assertEqual(len(sent),1)
                    self.assertEqual(sent[0].quantity.as_decimal(),expected)
                    self.assertTrue(sent[0].is_reduce_only)
                    self.assertEqual(sent[0].order_type.name,"MARKET")
                    context=next(iter(fake._order_audit.values()))["admission"]
                    self.assertEqual(context["mark_risk_measurement"],"UNKNOWN_REDUCTION_ON_FRESH_BBO")
                    self.assertEqual(context["execution_model_id"],MODEL_ID)
                    self.assertIn("UNKNOWN",context["market_wire_price_and_backend_classification"])
            engine.assert_not_called()

    def test_protected_aggressive_price_then_actual_permission_hold_or_send(self):
        with patch("nautilus_trader.backtest.engine.BacktestEngine",side_effect=AssertionError("NO_ENGINE")):
            for quote,basis,should_send in ((D("10001.1"),D("9992.3"),False),(D("10010.1"),D(9990),True)):
                fake,i,tick,s,decision,sent,_=self.fixture(qty=D(1),price=quote,draining=False,harvest=True)
                s=replace(s,btc_vwap=basis,btc_entry_fees=basis*D(".000432"))
                fake._snapshot=lambda ns:s;fake._child_capacity=lambda *a:D("1e9")
                with patch("coinmaster.strategy.cm2_native.decide",return_value=decision):
                    CM2Strategy.on_quote_tick(fake,N(**vars(tick),instrument_id=i.id))
                self.assertEqual(bool(sent),should_send)
                if should_send:
                    self.assertEqual(sent[0].price.as_decimal(),D(10010))
                    context=next(iter(fake._order_audit.values()))["admission"]
                    self.assertEqual(context["original_executable_quote"],"10010.1")
                    self.assertEqual(D(context["normalized_protective_limit"]),D(10010))
                    self.assertFalse(context["protected_limit_is_executable_quote"])
                else:self.assertTrue(any("PROTECTIVE_LIMIT_RIGHT_OR_COST" in b["reason"] for b in fake.pre_submit_gate_blocks))

    def test_stale_native_clock_and_future_bbo_cancel_profit_without_submission(self):
        for age in (FRESH_NS+1,-1):
            fake,i,tick,s,decision,sent,canceled=self.fixture(qty=D(1),price=D(1100),draining=False,harvest=True)
            fake.clock.now=tick.ts_event+age
            order=N(client_order_id="working-profit",is_reduce_only=True)
            fake._orders=lambda iid:[order]
            fake._order_audit={"working-profit":{"admission":{"intent":"POSITIVE_HARVEST"}}}
            CM2Strategy.on_quote_tick(fake,N(**vars(tick),instrument_id=i.id))
            self.assertEqual(sent,[]);self.assertEqual(canceled,[order])
            self.assertTrue(fake.pre_submit_gate_blocks)

    def test_final_native_quantity_or_shape_mutation_is_blocked(self):
        fake,i,tick,s,decision,sent,_=self.fixture()
        original=fake._make_order
        def wrong(*args):
            return original(args[0],args[1],i.make_qty(D(400)),args[3],args[4])
        fake._make_order=wrong
        with patch("coinmaster.strategy.cm2_native.decide",return_value=decision):
            CM2Strategy.on_quote_tick(fake,N(**vars(tick),instrument_id=i.id))
        self.assertEqual(sent,[]);self.assertEqual(fake._owned,{})
        self.assertTrue(any("FINAL_NATIVE_REQUEST_MISMATCH" in b["reason"] for b in fake.pre_submit_gate_blocks))

    def test_missing_mark_never_uses_quote_or_price_one_for_equity(self):
        fake,i,tick,s,decision,sent,_=self.fixture(qty=D(1))
        pos=N(quantity=N(as_decimal=lambda:D(1)),is_long=True,avg_px_open=1000,
            unrealized_pnl=lambda px:(_ for _ in ()).throw(AssertionError("NO_FAKE_MARK_VALUATION")))
        fake._position=lambda iid:pos if iid==i.id else None
        fake.cache.account_for_venue=lambda venue:N(base_currency="USDC",balance_total=lambda c:N(as_decimal=lambda:D(10000)))
        fake._latest_marks={};fake._risk_unknown=False;fake._sync_funding=lambda:None
        fake._entry_fees=D(0);fake._parent_funding=D(0);fake._parent_cost_known=True
        result=CM2Strategy._snapshot(fake,fake.clock.now)
        self.assertFalse(result.data_known)
        self.assertEqual((result.btc_mark,result.sol_mark),(D(0),D(0)))
        self.assertEqual(result.equity,D(10000))

if __name__=="__main__":unittest.main()
