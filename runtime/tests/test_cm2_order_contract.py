"""Audited request/clock contracts: pure/plains fakes and native objects only."""
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch
import unittest
from coinmaster.strategy.cm2_order_contract import *
from coinmaster.strategy.cm2_execution import order_plan,ExecutionLimits
from coinmaster.strategy.cm2_native import CM2Strategy
from coinmaster.strategy.cm2_policy import Config,State,Snapshot,Features,Decision,HOUR_NS
from coinmaster.venues.hyperliquid_profile import HyperliquidVenueProfile,HyperliquidProfileEnvironment,Evidence

class Clock:
    def __init__(self,now):self.now=now;self.alerts={}
    def timestamp_ns(self):return self.now
    @property
    def timer_names(self):return list(self.alerts)
    def set_time_alert_ns(self,name,ns,callback):self.alerts[name]=(ns,callback)
    def cancel_timer(self,name):del self.alerts[name]
    def advance(self,now):
        self.now=now
        for name,(ns,callback) in list(self.alerts.items()):
            if ns<=now:del self.alerts[name];callback(N(ts_event=ns))

class RequestContractTest(unittest.TestCase):
    def setUp(self):
        self.profile=HyperliquidVenueProfile(environment=HyperliquidProfileEnvironment.MAINNET,
            evidence=Evidence("TEST_PUBLIC","2026-10-29","0"*64))
        self.btc=self.profile.instruments["BTC-USD-PERP.HYPERLIQUID"]
        self.sol=self.profile.instruments["SOL-USD-PERP.HYPERLIQUID"]

    def test_cap_classification_and_boundaries(self):
        for spec,px,market,limit in ((self.btc,D(80000),D(30000000),D(300000000)),
                                    (self.sol,D(200),D(5000000),D(50000000))):
            for intent,tif,cap in (("MARKET","IOC",market),("LIMIT","IOC",market),("LIMIT","GTC",limit)):
                terms=request_terms(spec,px,"BUY",intent,tif)
                self.assertEqual(terms.cap,cap)
                self.assertTrue(validate_request(spec,cap/px,terms,intent,tif)[0])
                self.assertEqual(validate_request(spec,cap/px+spec.quantity_increment,terms,intent,tif)[1],"REQUEST_MAX_NOTIONAL")
            self.assertIn("BACKEND_UNKNOWN",request_terms(spec,px,"BUY","LIMIT","IOC").classification)
        with self.assertRaises(ValueError):request_cap(self.btc,"STOP","IOC")

    def test_price_integer_exception_and_aggressive_direction(self):
        for spec,price in ((self.btc,D("10000.1")),(self.sol,D("123.4567"))):
            self.assertFalse(valid_price(spec,price))
            sell=aggressive_price(spec,price,"SELL");buy=aggressive_price(spec,price,"BUY")
            self.assertLessEqual(sell,price);self.assertGreaterEqual(buy,price)
            self.assertTrue(valid_price(spec,sell));self.assertTrue(valid_price(spec,buy))
            self.assertTrue(valid_price(spec,D("123456789")))
        self.assertEqual(aggressive_price(self.sol,D("123.4567"),"SELL"),D("123.45"))
        self.assertEqual(aggressive_price(self.btc,D("10000.1"),"BUY"),D("10001"))
        for bad in (D(0),D(-1),D("NaN"),D("Infinity")):
            with self.assertRaises(ValueError):aggressive_price(self.btc,bad,"BUY")

    def test_final_normalized_minimum_quantity_and_cap(self):
        terms=request_terms(self.sol,D("123.4567"),"BUY","LIMIT","IOC")
        self.assertEqual(validate_request(self.sol,D(".01"),terms,"LIMIT","IOC")[1],"CONSERVATIVE_RESEARCH_MIN_NOTIONAL")
        self.assertEqual(validate_request(self.sol,D("1.001"),terms,"LIMIT","IOC")[1],"REQUEST_QUANTITY_FORMAT")
        self.assertEqual(validate_request(self.sol,D(1),replace(terms,limit_price=D("123.4567")),"LIMIT","IOC")[1],"REQUEST_PRICE_FORMAT")
        self.assertFalse(validate_request(self.sol,D(1),replace(terms,cap=D(999)),"LIMIT","IOC")[0])

    def test_venue_cap_always_but_participation_ordinary_only(self):
        for sign in (D(1),D(-1)):
            args=dict(actual=sign*D(1000),target=D(0),pending=D(0),unknown=False,price=D(1000),
                step=D(".00001"),min_qty=D(".00001"),min_notional=D(10),max_child=D(100),
                venue_max_child_notional=D(10000),venue_reference_price=D(1001))
            p=order_plan(**args,emergency=True)
            self.assertLessEqual(abs(p.signed_quantity)*D(1001),D(10000))
            self.assertLess(abs(p.signed_quantity),abs(args["actual"]))
            self.assertLessEqual(abs(order_plan(**args).signed_quantity)*D(1000),D(100))
        p=order_plan(actual=D("8.48"),target=D(0),pending=D(0),unknown=False,price=D("141.3"),
            step=D(".01"),min_qty=D(".01"),min_notional=D(10),max_child=D("1e100"),
            venue_max_child_notional=D("8.46")*D("141.3"),emergency=True)
        self.assertEqual(p.signed_quantity,D("-8.40"))

    def test_clock_bbo_contract(self):
        def q(bid=100,ask=101,ns=100):
            return N(ts_event=ns,bid_price=N(as_decimal=lambda:D(bid)),ask_price=N(as_decimal=lambda:D(ask)))
        self.assertTrue(bbo_status(q(),100)[0])
        self.assertFalse(bbo_status(q(),100+FRESH_NS+1)[0])
        self.assertFalse(bbo_status(q(ns=101),100)[0])
        self.assertFalse(bbo_status(q(bid=102),100)[0])
        self.assertFalse(bbo_status(q(bid=0),100)[0])

    def test_drain_scope_deadline_and_checkpoint_validation(self):
        d=drain_update(None,100,["SOL"])
        self.assertEqual(d["deadline_ns"],100+DRAIN_NS)
        d2=drain_update(d,101,["BTC"])
        self.assertEqual(d2["first_ns"],100)
        self.assertEqual(d2["scoped_zero_ids"],["BTC","SOL"])
        self.assertTrue(drain_update(d2,100+DRAIN_NS,[])["reconcile_required"])
        self.assertEqual(validate_drain(d2,["BTC","SOL"]),d2)
        for changed in ({"deadline_ns":101+DRAIN_NS},{"scoped_zero_ids":["FOREIGN"]},{"reconcile_required":1}):
            with self.assertRaises(ValueError):validate_drain({**d2,**changed},["BTC","SOL"])
        self.assertEqual(risk_only_target(D(10),D(20)),D(10))
        self.assertEqual(risk_only_target(D(-10),D(20)),D(0))

    def test_deadline_alert_without_quotes_retains_inventory_and_replay_deadline(self):
        now=100;clock=Clock(now);canceled=[];writes=[]
        unsafe=N(client_order_id="profit",is_reduce_only=True)
        safe=N(client_order_id="risk",is_reduce_only=True)
        fake=N(id="PURE",clock=clock,config=N(btc_id="BTC",sol_id="SOL",terminal_close_at_ns=10**25),
            _liquidating=False,_drain=None,drain_audit=[],_orders=lambda iid:[unsafe,safe] if iid=="BTC" else [],
            _order_audit={"profit":{"admission":{"intent":"POSITIVE_HARVEST"}},"risk":{"admission":{"intent":"RISK_TRIM"}}},
            cancel_order=lambda o:canceled.append(o.client_order_id),_persist_checkpoint=lambda:writes.append(1),
            _chain_audit=lambda *args:None)
        s=Snapshot(D(10000),D(10),D(-1),D(1000),D(100))
        decision=Decision(D(0),D(0),"STOP",State(draining=True))
        CM2Strategy._update_drain(fake,now,s,decision)
        first=dict(fake._drain)
        CM2Strategy._update_drain(fake,101,s,decision)
        self.assertEqual(fake._drain,first);self.assertEqual(len(clock.timer_names),1)
        clock.advance(first["deadline_ns"])
        self.assertTrue(fake._drain["reconcile_required"]);self.assertEqual(canceled,["profit"])
        self.assertEqual(s.btc_qty,D(10)) # never fake-flat or mutate native snapshot
        CM2Strategy._on_drain_deadline(fake,None)
        self.assertEqual(canceled,["profit"])
        saved=dict(fake._drain);fake._drain=validate_drain(saved,["BTC","SOL"])
        CM2Strategy._arm_drain_alert(fake)
        self.assertEqual(fake._drain["deadline_ns"],first["deadline_ns"])
        CM2Strategy._update_drain(fake,clock.now,replace(s,btc_qty=D(0),sol_qty=D(0)),decision)
        self.assertIsNotNone(fake._drain) # terminal ACKs not resolved
        fake._orders=lambda iid:[]
        CM2Strategy._update_drain(fake,clock.now,replace(s,btc_qty=D(0),sol_qty=D(0)),decision)
        self.assertIsNone(fake._drain)
        self.assertGreaterEqual(len(writes),2)

    def test_ordinary_capacity_uses_upper_request_reference_after_rounding(self):
        price=D("123.4567");terms=request_terms(self.sol,price,"SELL","LIMIT","IOC")
        p=order_plan(actual=D(100),target=D(0),pending=D(0),unknown=False,
            price=terms.minimum_reference_price,step=D(".01"),min_qty=D(".01"),min_notional=D(10),
            max_child=D(1000),venue_max_child_notional=terms.cap,venue_reference_price=terms.cap_reference_price)
        self.assertLessEqual(abs(p.signed_quantity)*price,D(1000))
        self.assertTrue(validate_request(self.sol,abs(p.signed_quantity),terms,"LIMIT","IOC")[0])

    def test_actual_public_TestClock_deadline_delivery_engine_blocked(self):
        from nautilus_trader.common.component import TestClock
        with patch("nautilus_trader.backtest.engine.BacktestEngine",side_effect=AssertionError("NO_ENGINE")) as engine:
            clock=TestClock();clock.set_time(100)
            fake=N(id="CLOCK_OBJECT_ONLY",clock=clock,config=N(btc_id="BTC",sol_id="SOL"),
                _drain=drain_update(None,100,["SOL"]),drain_audit=[],_orders=lambda iid:[],
                _order_audit={},_persist_checkpoint=lambda:None,_chain_audit=lambda *a:None)
            CM2Strategy._arm_drain_alert(fake)
            deadline=fake._drain["deadline_ns"]
            handlers=clock.advance_time(deadline)
            self.assertEqual(len(handlers),1)
            for handler in handlers:handler.handle()
            self.assertTrue(fake._drain["reconcile_required"])
            self.assertEqual(fake._drain["first_ns"],100)
            engine.assert_not_called()

    def test_actual_normal_hedge_release_starts_sol_only_native_clock_deadline(self):
        from coinmaster.strategy.cm2_policy import decide
        from runtime.tests.test_cm2_policy import feat,snap,state
        from nautilus_trader.common.component import TestClock
        with patch("nautilus_trader.backtest.engine.BacktestEngine",side_effect=AssertionError("NO_ENGINE")) as engine:
            for sign in (D(1),D(-1)):
                f=feat(t=201*HOUR_NS,close=1000,residual_z=0,btc_return6=float(sign)*.01)
                snapshot=snap(btc_qty=sign*D(20),sol_qty=-sign*D(100),btc_mark=D(1000),sol_mark=D(100))
                st=state(direction=int(sign),btc_target=sign*D(20),unhedged_btc_target=sign*D(20),
                    sol_target=-sign*D(100),hedge_active=True,release_count=1,last_hour=200*HOUR_NS,
                    stop=800 if sign>0 else 1200)
                decision=decide(Config(),f,snapshot,st,now_ns=f.available_ns+1)
                self.assertEqual(decision.reason,"CORE_HOLD")
                self.assertEqual(decision.sol_target,D(0))
                self.assertFalse(decision.cancel_increases)
                self.assertFalse(decision.state.draining)
                self.assertEqual(decision.btc_target,snapshot.btc_qty)
                clock=TestClock();clock.set_time(f.available_ns+1)
                fake=N(id="NORMAL_RELEASE",clock=clock,config=N(btc_id="BTC",sol_id="SOL",terminal_close_at_ns=10**25),
                    _liquidating=False,_drain=None,drain_audit=[],_orders=lambda iid:[],
                    _order_audit={},_persist_checkpoint=lambda:None,_chain_audit=lambda *a:None,cancel_order=lambda order:None)
                CM2Strategy._update_drain(fake,clock.timestamp_ns(),snapshot,decision)
                first=dict(fake._drain)
                self.assertEqual(first["scoped_zero_ids"],["SOL"])
                self.assertEqual(len(clock.timer_names),1)
                clock.set_time(clock.timestamp_ns()+10_000_000_000)
                again=decide(Config(),f,snapshot,decision.state,now_ns=clock.timestamp_ns())
                CM2Strategy._update_drain(fake,clock.timestamp_ns(),snapshot,again)
                self.assertEqual(fake._drain,first)
                handlers=clock.advance_time(first["deadline_ns"])
                for handler in handlers:handler.handle()
                self.assertTrue(fake._drain["reconcile_required"])
                self.assertEqual(fake._drain["deadline_ns"],first["deadline_ns"])
                self.assertEqual(snapshot.btc_qty,sign*D(20))
                self.assertEqual(decision.btc_target,snapshot.btc_qty)
            engine.assert_not_called()

    def test_zero_net_owned_sol_orders_still_start_and_hold_scope(self):
        clock=Clock(100);canceled=[]
        orders=[N(client_order_id="a",is_reduce_only=False),N(client_order_id="b",is_reduce_only=False)]
        fake=N(id="PENDING_ZERO_NET",clock=clock,config=N(btc_id="BTC",sol_id="SOL",terminal_close_at_ns=10**25),
            _liquidating=False,_drain=None,drain_audit=[],_orders=lambda iid:orders if iid=="SOL" else [],
            _order_audit={},_persist_checkpoint=lambda:None,_chain_audit=lambda *a:None,
            cancel_order=lambda order:canceled.append(order.client_order_id))
        snapshot=Snapshot(D(10000),D(20),D(0),D(1000),D(100),sol_pending=D(0))
        decision=Decision(D(20),D(0),"CORE_HOLD",State())
        CM2Strategy._update_drain(fake,100,snapshot,decision)
        self.assertEqual(fake._drain["scoped_zero_ids"],["SOL"])
        deadline=fake._drain["deadline_ns"]
        clock.advance(deadline)
        self.assertEqual(canceled,["a","b"])
        CM2Strategy._update_drain(fake,deadline,snapshot,decision)
        self.assertIsNotNone(fake._drain) # cancel request is not terminal ACK
        orders.clear()
        CM2Strategy._update_drain(fake,deadline,snapshot,decision)
        self.assertIsNone(fake._drain)

    def test_native_objects_guarded_engine_and_aggressive_profit_geometry(self):
        from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
        from nautilus_trader.common.factories import OrderFactory
        from nautilus_trader.common.component import TestClock
        from nautilus_trader.model.identifiers import TraderId,StrategyId
        from nautilus_trader.model.enums import OrderSide
        from coinmaster.strategy.cm2_policy import btc_child_permission
        with patch("nautilus_trader.backtest.engine.BacktestEngine",side_effect=AssertionError("NO_ENGINE")) as engine:
            profile=load_current_hl_diagnostic(Path(__file__).parent/"fixtures/hl-current-20261029")
            btc=profile.instruments[0];factory=OrderFactory(TraderId("AUDIT-001"),StrategyId("AUDIT-001"),TestClock())
            for sign,quote in ((D(1),D("1001.1")),(D(-1),D("998.9"))):
                terms=request_terms(self.btc,quote,"SELL" if sign>0 else "BUY","LIMIT","IOC")
                state=State(direction=int(sign),parent=1,btc_target=sign*D(".75"),btc_intent="POSITIVE_HARVEST",harvest_target=sign*D(".75"))
                s=Snapshot(D(10000),sign,D(0),quote,D(100),btc_vwap=D(1000),
                    btc_entry_fees=D(".432"),btc_signed_funding=D(0))
                f=Features(HOUR_NS,HOUR_NS,True,hedge_valid=True)
                allowed,_=btc_child_permission(Config(),f,s,state,now_ns=HOUR_NS+1,executable_price=terms.limit_price)
                self.assertTrue(allowed)
                fake=N(config=N(btc_id=btc.id),policy_state=state,cache=N(instrument=lambda iid:btc),order_factory=factory)
                o=CM2Strategy._make_order(fake,btc.id,OrderSide.SELL if sign>0 else OrderSide.BUY,
                    btc.make_qty(D(".25")),True,terms.limit_price)
                self.assertEqual(o.price.as_decimal(),terms.limit_price)
                self.assertTrue(valid_price(self.btc,o.price.as_decimal()))
            # An adverse legal rounding can erase the strict cost buffer: HOLD.
            quote=D("1001.1");terms=request_terms(self.btc,quote,"SELL","LIMIT","IOC")
            near=replace(s,btc_qty=D(1),btc_mark=quote,btc_vwap=D("1000.2"))
            self.assertFalse(btc_child_permission(Config(),f,near,replace(state,direction=1,btc_target=D(".75")),
                now_ns=HOUR_NS+1,executable_price=terms.limit_price)[0])
            engine.assert_not_called()

if __name__=="__main__":unittest.main()
