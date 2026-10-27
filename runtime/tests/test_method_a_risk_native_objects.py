"""Actual stock objects only. No backtest imports or constructors."""
import sys
import unittest
from pathlib import Path
from decimal import Decimal as D
from nautilus_trader.model.objects import Money
from nautilus_trader.model.currencies import USDT
from coinmaster.venues.bybit_profile import BybitVenueProfile


class NativeRiskObjects(unittest.TestCase):
    def test_stock_money_precision_is_not_raw_decimal_parity(self):
        self.assertEqual(USDT.precision,8)
        self.assertEqual(Money(D('1.123456786'),USDT).as_decimal(),D('1.12345679'))
        self.assertNotEqual(Money(D('1.123456785'),USDT).as_decimal(),D('1.123456785'))
        self.assertFalse(any(k.startswith('nautilus_trader.backtest') for k in sys.modules))

    def test_frozen_profile_coefficient_bound(self):
        profile=BybitVenueProfile.from_raw(Path(__file__).resolve().parents[1])
        width=max(len(v.as_tuple().digits)+abs(v.as_tuple().exponent) for tiers in profile.tiers.values() for t in tiers for v in (t.cap,t.im,t.mm,t.deduction,t.max_leverage))
        self.assertEqual(width,10)

    def test_zero_shock_parity_can_hold_on_actual_native_lattice(self):
        profile=BybitVenueProfile.from_raw(Path(__file__).resolve().parents[1])
        for symbol,qty,price,lev in (('BTCUSDT','1.096','57721.5','40'),('BTCUSDT','275','100','40'),('SOLUSDT','109','172.02','20')):
            n=D(qty)*D(price);tier=profile.tier_for(symbol,n)
            raw=(n*max(tier.im,1/D(lev)),max(D(0),n*tier.mm-tier.deduction))
            self.assertEqual(raw,tuple(Money(v,USDT).as_decimal() for v in raw))
        # This is source/object feasibility, not actual simultaneous account
        # getter parity. M2 must still bind getters to actual positions/marks.

if __name__=='__main__':unittest.main()
