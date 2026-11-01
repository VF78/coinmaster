"""V3 exact native order objects and real policy callbacks; zero engines."""
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch
import unittest
import json
from coinmaster.research import cm2_fixture_e08 as fixture, cm2_fixture_e04 as old
from coinmaster.research.cm2_runner import engineering_fixture_module,fixture_api_boundary_probe
from coinmaster.strategy.cm2_native import CM2Strategy
from coinmaster.strategy.cm2_policy import State,Decision,MINUTE_NS
import test_cm2_final_send_contract as final_send
from tempfile import TemporaryDirectory


class E08Tests(unittest.TestCase):
    def test_version_script_and_safe_lookup(self):
        self.assertEqual(fixture.FIXTURE_ID,"cm2-current-child-native-v3")
        self.assertIs(engineering_fixture_module({"fixture_id":fixture.FIXTURE_ID}),fixture)
        for name in ("START_NS","END_NS","CAPACITY_NOTIONAL","FUNDING_EXPECTED","QUEUED_LATENCY_NS","QUEUE_PULSE_MINUTES"):
            self.assertEqual(getattr(fixture,name),getattr(old,name))
        for m in range(1081):self.assertEqual(fixture.minute_prices(m),old.minute_prices(m))
        for h in set(range(18))-{1,10}:self.assertEqual(fixture.fixed_feature(h),old.fixed_feature(h))
        with self.assertRaisesRegex(ValueError,"EXPECTED_NATIVE_SHAPED_ORDER_MISSING:LONG_GTC=missing"):
            fixture.shaped_orders({"LONG_GTC":"missing"},[])
        self.assertEqual(fixture.shaped_orders({},[]),{})

    def make(self,phase):
        qty=D(20) if phase=="LONG" else D(-20)
        price=D(1070) if phase=="LONG" else D(880)
        minute=302 if phase=="LONG" else 842
        fake,inst,_,s,_,sent,canceled=final_send.FinalSendTest().fixture(qty=qty,price=price,draining=False,harvest=True)
        now=fixture.START_NS+minute*MINUTE_NS-1
        fake.clock.now=now
        f=fixture.fixed_feature(5 if phase=="LONG" else 14)
        s=replace(s,btc_vwap=D(1000) if phase=="LONG" else D(950),btc_entry_fees=D("8.64"),
            btc_signed_funding=D(0))
        st=State(direction=1 if phase=="LONG" else -1,parent=1 if phase=="LONG" else 2,
            btc_target=qty/2,harvest_target=qty/2,harvest_start_qty=qty,
            btc_intent="POSITIVE_HARVEST",intent_hour=f.closed_ns,last_hour=f.closed_ns,
            initial_r=30,stop=970 if phase=="LONG" else 980,extreme=990 if phase=="LONG" else 960)
        fake.policy_state=st;fake.current_features=f;fake._snapshot=lambda ns:s
        fake.fixture_shapes={}
        fake._quotes[inst.id]=N(ts_event=now,bid_price=N(as_decimal=lambda:price),ask_price=N(as_decimal=lambda:price))
        return fake,inst,s,sent,canceled,now

    def test_owned_native_gtc_pending_wait_then_real_permission_cancel(self):
        with patch("nautilus_trader.backtest.engine.BacktestEngine",side_effect=AssertionError("NO_ENGINE")) as engine:
            for phase in ("LONG","SHORT"):
                fake,inst,s,sent,canceled,now=self.make(phase)
                order=fixture.working_harvest_sentinel(fake,phase,now)
                self.assertEqual(order.time_in_force.name,"GTC")
                self.assertEqual(order.quantity.as_decimal(),10)
                self.assertTrue(order.is_reduce_only)
                oid=str(order.client_order_id)
                self.assertEqual(sent,[order])
                admission=fake._order_audit[oid]["admission"]
                self.assertTrue(admission["test_only"])
                self.assertEqual(admission["parent"],fake.policy_state.parent)
                self.assertEqual(admission["intent"],"POSITIVE_HARVEST")
                fake._orders=lambda iid:[order] if iid==inst.id else []
                pending=D(-10) if phase=="LONG" else D(10)
                held=replace(s,btc_pending=pending)
                fake._snapshot=lambda ns:held
                fake.clock.now=now+1
                quote=fake._quotes[inst.id]
                tick=N(**vars(quote),instrument_id=inst.id)
                decision=Decision(fake.policy_state.btc_target,D(0),"TEST_HARVEST",fake.policy_state,False)
                with patch("coinmaster.strategy.cm2_native.decide",return_value=decision):
                    CM2Strategy.on_quote_tick(fake,tick)
                self.assertEqual(sent,[order]);self.assertEqual(canceled,[])
                adverse=D(990) if phase=="LONG" else D(960)
                fake.clock.now=now+MINUTE_NS+1
                held=replace(held,btc_mark=adverse)
                tick=N(instrument_id=inst.id,ts_event=fake.clock.now,
                    bid_price=N(as_decimal=lambda:adverse),ask_price=N(as_decimal=lambda:adverse))
                with patch("coinmaster.strategy.cm2_native.decide",return_value=decision):
                    CM2Strategy.on_quote_tick(fake,tick)
                self.assertIn(order,canceled)
                self.assertEqual(sent,[order])
            engine.assert_not_called()

    def test_invalid_budget_rejected_before_submission(self):
        fake,_,_,sent,_,now=self.make("LONG")
        fake.policy_state=replace(fake.policy_state,harvest_target=D(0))
        with self.assertRaisesRegex(ValueError,"FINITE_CURRENT_HARVEST_BUDGET10"):
            fixture.working_harvest_sentinel(fake,"LONG",now)
        self.assertEqual(sent,[])

    def test_partial_fullclose_residue_stays_visible_through_deadline(self):
        # A legal .15 full-close may fill only .12. This hypothetical native
        # snapshot is an explicit input, never an injected native fill or cache.
        from coinmaster.strategy.cm2_execution import order_plan
        initial=order_plan(actual=D("-.15"),target=D(0),pending=D(0),unknown=False,
            price=D(100),step=D(".01"),min_qty=D(".01"),max_child=D(100),emergency=True,min_notional=D(10))
        self.assertEqual(initial.signed_quantity,D(".15"))
        fake,inst,tick,s,decision,sent,_=final_send.FinalSendTest().fixture("SOL",qty=D("-.03"),price=D(100))
        with patch("coinmaster.strategy.cm2_native.decide",return_value=decision):
            CM2Strategy.on_quote_tick(fake,N(**vars(tick),instrument_id=inst.id))
        reason="CONSERVATIVE_RESEARCH_MIN_NOTIONAL_REDUCE_EXCEPTION_UNKNOWN"
        self.assertEqual(fake.target_blockers[str(inst.id)]["reason"],reason)
        self.assertEqual(fake.target_blockers[str(inst.id)]["actual"],"-0.03")
        deadline=fake._drain["deadline_ns"]
        fake.clock.advance(deadline)
        self.assertTrue(fake._drain["reconcile_required"])
        self.assertEqual(fake._drain["deadline_ns"],deadline)
        self.assertEqual(s.sol_qty,D("-.03"))
        self.assertEqual(sent,[])
        self.assertIn("RECONCILE",fake.drain_audit[-1]["kind"])

    def test_zero_quantity_is_rejected_never_close_all(self):
        from coinmaster.strategy.cm2_order_contract import request_terms,validate_request
        from coinmaster.strategy.cm2_execution import order_plan
        fake,inst,_,sent,_,_=self.make("LONG")
        spec=CM2Strategy._contract_spec(fake,inst.id,inst)
        terms=request_terms(spec,D(1070),"SELL","MARKET","IOC")
        self.assertEqual(validate_request(spec,D(0),terms,"MARKET","IOC"),(False,"REQUEST_QUANTITY_UNKNOWN"))
        plan=order_plan(actual=D(20),target=D(0),pending=D(0),unknown=False,
            price=D(1070),step=D(".00001"),min_qty=D(".00001"),max_child=D(".001"),min_notional=D(10))
        self.assertEqual(plan.action,"HOLD")
        self.assertEqual(plan.signed_quantity,0)
        self.assertEqual(sent,[])

    def test_missing_order_invariant_retains_structured_partial_evidence(self):
        with TemporaryDirectory() as output:
            try:fixture.shaped_orders({"SHORT_GTC":"native-id"},[])
            except ValueError as error:
                path=fixture.write_partial_failure_evidence(output,{"run_id":"TEST_ONLY"},error,
                    native_clock_ns=fixture.END_NS,evidence={"native_orders":[]})
            packet=json.loads(path.read_text())
            self.assertEqual(packet["status"],"FAILED_PARTIAL_NATIVE_EVIDENCE")
            self.assertIn("SHORT_GTC=native-id",packet["original_error"]["message"])
            self.assertFalse(packet["ranking_eligible"])
            self.assertEqual(packet["financial_qualification"],"UNKNOWN_ABORTED_PREFIX")

    def test_actual_v3_api_boundary_engine_zero(self):
        with TemporaryDirectory() as output:
            receipt=fixture_api_boundary_probe({"fixture_id":fixture.FIXTURE_ID,
                "start_ns":fixture.START_NS,"end_ns":fixture.END_NS,
                "current_hl_execution_inputs":str(Path(__file__).parent/"fixtures/hl-current-20261029")},output)
            self.assertEqual(receipt["native_engine_constructions"],0)
            self.assertEqual(receipt["boundary_calls"],1)

    def test_effective_fees_exact_once_native_profile(self):
        from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
        from coinmaster.venues.effective_fees import CURRENT_HL_FEES,effective_instrument_dict
        self.assertEqual((CURRENT_HL_FEES.taker,CURRENT_HL_FEES.maker),(D(".000432"),D(".000144")))
        once=effective_instrument_dict({"maker_fee":"0.0002","taker_fee":"0.0006"})
        self.assertEqual(effective_instrument_dict(once),once)
        profile=load_current_hl_diagnostic(Path(__file__).parent/"fixtures/hl-current-20261029")
        for inst in profile.instruments:
            self.assertEqual((inst.taker_fee,inst.maker_fee),(D(".000432"),D(".000144")))

if __name__=="__main__":unittest.main()
