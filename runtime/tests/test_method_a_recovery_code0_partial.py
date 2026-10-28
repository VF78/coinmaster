"""Only peer-P1 closure checks; actual Cache/Order chain, engine imports blocked."""
import unittest
from decimal import Decimal as D
from dataclasses import replace
from types import SimpleNamespace as NS
from test_method_a_recovery_code0 import Probe,STATE,FEATURE,UUID4,OrderFilled,OrderSide,OrderType,USDT,Money,LiquiditySide,TradeId,PositionId,QuoteTick
from nautilus_trader.model.events import OrderCanceled,OrderUpdated
from coinmaster.strategy.method_a_risk_native import MethodARiskResearch
from coinmaster.strategy.method_a_risk import MINUTE


def actor():
    p=Probe();p._mr_after_busy=False;p._mr_sequence=0;p._pair['caps']=NS(bmax=STATE.btc)
    p._pair_qty=lambda iid:abs(p.state.btc if iid==p.btc.id else p.state.sol)
    p.canceled_increases=[];p._pair_cancel_btc_increases=lambda ns:p.canceled_increases.append(ns)
    p._mr_recovery_ready=lambda iid,ns:False
    p._pair_sol_events=set();p._pair_sol_retire_check=lambda ns:None
    p.protection_calls=[];p._pair_protect=lambda ns:p.protection_calls.append(ns)
    p._pair_submit(p.sol.id,1,D('132.9'),'SOL_CAP',p.ns)
    o=p.sent[0];p.accept(o);p.cache.add_order(o);p.cache.update_order(o)
    p._pair_orders[str(o.client_order_id)]['accepted']=True
    return p,o


def partial(p,o,qty=D('.1')):
    e=OrderFilled(p.trader,p.id,p.sol.id,o.client_order_id,o.venue_order_id,p.account,TradeId('RECOVERY-PARTIAL'),PositionId('SOL-POS'),OrderSide.BUY,OrderType.LIMIT,p.sol.make_qty(qty),p.sol.make_price(D('132.9')),USDT,Money(qty*D('132.9')*D('.00055'),USDT),LiquiditySide.TAKER,UUID4(),p.ns,p.ns)
    o.apply(e);p.cache.update_order(o)
    p.state=replace(STATE,sol=STATE.sol+qty,equity=STATE.equity-e.commission.as_decimal())
    return e


def canceled(p,o):
    e=OrderCanceled(p.trader,p.id,p.sol.id,o.client_order_id,o.venue_order_id,p.account,UUID4(),p.ns,p.ns)
    o.apply(e);p.cache.update_order(o);return e


class PartialClosure(unittest.TestCase):
    def test_partial_then_terminal_then_owned_resize_ack_then_fresh_residual_proof(self):
        p,o=actor();deadline=p._pair['debt_since'];partial(p,o)
        protection=list(p._pair_work(instrument=p.sol.id,kinds={'TP','STOP'}))
        for oid,owner,order in protection:
            owner['generation']=0
            owner['pending']=dict(sequence=1,generation=0,payload=(D('132.8'),owner['ack'][1],owner['ack'][2]),desired=None)
        p._mr_after_actual(p.ns);p._mr_after_actual(p.ns) # duplicate callback, no duplicate fill
        self.assertEqual(len(p.sent),1);self.assertEqual(p._pair['debt_since'],deadline)
        self.assertEqual(o.status.name,'PARTIALLY_FILLED');self.assertIn('code0_drain_oid',p._pair)
        self.assertFalse(p._mr_failed);self.assertTrue(all(not order.is_closed for oid,owner,order in protection))
        canceled(p,o);p._mr_after_actual(p.ns)
        self.assertIn('code0_drain_oid',p._pair);self.assertEqual(len(p.sent),1)
        # Exercise the EXISTING actual native modify-ACK consumer, not synthetic
        # mutation of owner.ack. Positive protection stays live throughout.
        for oid,owner,order in protection:
            payload=owner['pending']['payload']
            e=OrderUpdated(p.trader,p.id,p.sol.id,order.client_order_id,order.venue_order_id,p.account,p.sol.make_qty(payload[0]),order.price if owner['kind']=='TP' else None,order.trigger_price if owner['kind']=='STOP' else None,UUID4(),p.ns,p.ns)
            order.apply(e);p.cache.update_order(order);p._pair_sol_native_event(e,'TEST_PUBLIC_ACK')
            self.assertIsNone(owner['pending']);self.assertEqual(owner['last_ack_event_id'],str(e.id))
        p._mr_after_actual(p.ns)
        self.assertNotIn('code0_drain_oid',p._pair);self.assertEqual(len(p.sent),1)
        self.assertEqual(p._pair['debt_since'],deadline)
        decision=[kw for args,kw in p.logs if args[0]=='RECOVERY_DECISION'][-1]
        self.assertEqual((decision['selected_leg'],decision['quantity']),('SOL','132.8'))
        self.assertTrue(all(not order.is_closed for oid,owner,order in protection))

    def test_zero_fill_and_repeated_callback_keep_original_deadline(self):
        p,o=actor();start=p._pair['debt_since']
        p._mr_after_actual(p.ns);p._mr_after_actual(p.ns+1)
        self.assertEqual(p.state,STATE);self.assertEqual(len(p.sent),1);self.assertEqual(p._pair['debt_since'],start)
        with self.assertRaisesRegex(AssertionError,'RECOVERY_DEADLINE'):p._mr_after_actual(start+MINUTE+1)
        self.assertEqual(p._pair['debt_since'],start)
        q,other=actor();canceled(q,other);q._mr_after_actual(q.ns)
        self.assertNotIn('code0_drain_oid',q._pair)
        self.assertTrue(any(args[0]=='RECOVERY_DECISION' for args,kw in q.logs))
        self.assertEqual(q.state,STATE);self.assertEqual(len(q.sent),1)

    def test_actually_safe_partial_still_waits_without_pending_credit_or_debt_clear(self):
        p,o=actor();partial(p,o,D(20));start=p._pair['debt_since'];p._mr_after_actual(p.ns)
        self.assertEqual(p._pair['debt_since'],start);self.assertIn('code0_drain_oid',p._pair)
        wait=[kw for args,kw in p.logs if args[0]=='CODE0_NATIVE_DRAIN_WAIT'][-1]
        self.assertEqual(wait['pending_hedge_credit'],'0');self.assertEqual(len(p.sent),1)

    def test_stale_frame_foreign_order_and_resize_price_change_fail_closed(self):
        p,o=actor();p.state=replace(STATE,ps=D('132.91'))
        with self.assertRaisesRegex(AssertionError,'STALE_OR_UNKNOWN_DRAIN_FRAME'):p._mr_after_actual(p.ns)
        q,other=actor();foreign=q.order_factory.market(instrument_id=q.sol.id,order_side=OrderSide.BUY,quantity=q.sol.make_qty(D('.1')))
        q.accept(foreign);q.cache.add_order(foreign);q.cache.update_order(foreign)
        with self.assertRaisesRegex(AssertionError,'UNKNOWN_ORDER_OWNER'):q._mr_after_actual(q.ns)
        r,third=actor();partial(r,third)
        oid,owner,order=next(iter(r._pair_work(instrument=r.sol.id,kinds={'TP'})))
        owner['generation']=0;owner['pending']=dict(sequence=1,generation=0,payload=(D('132.8'),D(81),None))
        with self.assertRaisesRegex(AssertionError,'UNKNOWN_DRAIN_RESIZE_PAYLOAD'):r._mr_after_actual(r.ns)

    def test_old_btc_tp_full_during_sol_partial_still_drains_same_route(self):
        p,o=actor();partial(p,o);btc=p.btc_order
        e=OrderFilled(p.trader,p.id,p.btc.id,btc.client_order_id,btc.venue_order_id,p.account,TradeId('OLD-BTC-REMAINDER'),PositionId('BTC-POS'),OrderSide.SELL,OrderType.LIMIT,p.btc.make_qty(D(1)),btc.price,USDT,Money(D('.02104'),USDT),LiquiditySide.MAKER,UUID4(),p.ns,p.ns)
        btc.apply(e);p.cache.update_order(btc)
        p.state=replace(p.state,btc=D(0),equity=p.state.equity-D('1.82104'))
        p._mr_after_actual(p.ns)
        self.assertEqual(btc.status.name,'FILLED');self.assertIn('code0_drain_oid',p._pair)
        self.assertEqual(len(p.sent),1);self.assertFalse(p._mr_failed)
        self.assertTrue(any(args[0]=='CODE0_NATIVE_DRAIN_WAIT' for args,kw in p.logs))

    def test_btc_native_money_rounding_counterexample_is_denied(self):
        p=Probe(btc_tick='0.01');state=replace(STATE,pb=D('109.94'))
        p.cache.add_quote_tick(QuoteTick(p.btc.id,p.btc.make_price(state.pb),p.btc.make_price(state.pb),p.btc.make_qty(D(1000)),p.btc.make_qty(D(1000)),p.ns+1,p.ns+1))
        # Raw fee gives .1704065/unit <=phi .170407; Money rounding of
        # .001 lot fee raises bound to .17041/unit, so DENY, no tolerance.
        with self.assertRaisesRegex(ValueError,'NATIVE_FEE_ROUNDING_EXCEEDS_CAP'):p._mr_code0_price('BTC',state,p.ns+1)

if __name__=='__main__':unittest.main()
