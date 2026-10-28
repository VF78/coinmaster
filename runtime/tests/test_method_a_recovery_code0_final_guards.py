"""Three final fail-closed guard checks only; no old-suite rerun or engines."""
import unittest
from decimal import Decimal as D
from dataclasses import replace
from test_method_a_recovery_code0 import Probe,STATE,FEATURE,UUID4
from test_method_a_recovery_code0_partial import actor
from nautilus_trader.model.events import OrderUpdated


class FinalGuards(unittest.TestCase):
    def test_negative_signed_old_tp_cost_is_unknown(self):
        p=Probe();state=replace(STATE,pb=D(105))
        with self.assertRaisesRegex(ValueError,'CODE0_UNKNOWN_NEGATIVE_OLD_BTC_COST'):
            p._mr_code0_old(state,FEATURE,p._mr_liabilities(p.ns),p.ns)
        self.assertEqual(p.sent,[])

    def test_nonaffine_old_maker_fee_per_minlot_is_unknown_before_provenance(self):
        p=Probe(btc_tick='0.01');o=p.btc_order
        e=OrderUpdated(p.trader,p.id,p.btc.id,o.client_order_id,o.venue_order_id,p.account,o.quantity,p.btc.make_price(D('105.21')),None,UUID4(),p.ns,p.ns)
        o.apply(e);p.cache.update_order(o)
        # .001BTC *105.21*.00020=.000021042 USDT, not on Money1e-8.
        with self.assertRaisesRegex(ValueError,'CODE0_UNKNOWN_OLD_BTC_FEE_AFFINITY'):
            p._mr_code0_old(STATE,FEATURE,p._mr_liabilities(p.ns),p.ns)
        self.assertEqual(p.sent,[])

    def test_known_failed_or_stop_filled_state_preempts_native_drain(self):
        for fault in ('failed','stop_filled'):
            p,o=actor();start=p._pair['debt_since'];p._pair[fault]=True
            with self.assertRaisesRegex(ValueError,'CODE0_DRAIN_KNOWN_PROTECTION_FAULT'):
                p._mr_code0_drain(p.state,FEATURE,p.ns)
            self.assertEqual(p._pair['debt_since'],start)
            self.assertIn('code0_drain_oid',p._pair);self.assertEqual(len(p.sent),1)
            self.assertFalse(any(args[0] in {'CODE0_NATIVE_DRAIN_WAIT','CODE0_NATIVE_DRAIN_COMPLETE'} for args,kw in p.logs))

if __name__=='__main__':unittest.main()
