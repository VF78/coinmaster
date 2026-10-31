"""Quote-protected native order objects and actual cost geometry; engine zero."""
from decimal import Decimal as D
from types import SimpleNamespace as NS
import unittest
from coinmaster.strategy.cm2_policy import actual_harvest_geometry,State
from coinmaster.strategy.cm2_native import CM2Strategy
from nautilus_trader.model.enums import OrderSide,OrderType,TimeInForce

class HarvestExecutionTests(unittest.TestCase):
    def order_fake(self):
        from nautilus_trader.common.component import TestClock
        from nautilus_trader.common.factories import OrderFactory
        from nautilus_trader.model.identifiers import InstrumentId,TraderId,StrategyId
        from nautilus_trader.model.objects import Price
        btc=InstrumentId.from_str('BTC-USD-PERP.HYPERLIQUID')
        factory=OrderFactory(TraderId('CM2-001'),StrategyId('CM2-001'),TestClock())
        instrument=NS(make_price=lambda price:Price.from_str(str(price.quantize(D('.1')))))
        return NS(config=NS(btc_id=btc),policy_state=State(btc_intent='POSITIVE_HARVEST'),
            cache=NS(instrument=lambda iid:instrument),order_factory=factory),instrument
    def test_real_native_quote_limit_IOC_both_sides_no_engine(self):
        from nautilus_trader.model.objects import Quantity
        fake,_=self.order_fake()
        for side,price in ((OrderSide.SELL,D(1070)),(OrderSide.BUY,D(930))):
            order=CM2Strategy._make_order(fake,fake.config.btc_id,side,Quantity.from_str('5.00000'),True,price)
            self.assertEqual(order.order_type,OrderType.LIMIT)
            self.assertEqual(order.time_in_force,TimeInForce.IOC)
            self.assertEqual(order.price.as_decimal(),price)
            self.assertTrue(order.is_reduce_only)
            self.assertFalse(order.is_post_only)
    def test_native_price_coercion_cannot_weaken_quote_protection(self):
        from nautilus_trader.model.objects import Price,Quantity
        fake,instrument=self.order_fake()
        instrument.make_price=lambda price:Price.from_str('1069.9')
        before=fake.order_factory.get_client_order_id_count()
        self.assertIsNone(CM2Strategy._make_order(fake,fake.config.btc_id,OrderSide.SELL,
            Quantity.from_str('5.00000'),True,D(1070)))
        self.assertEqual(fake.order_factory.get_client_order_id_count(),before)
    def test_safety_and_SOL_reductions_keep_market_IOC(self):
        from nautilus_trader.model.objects import Quantity
        from nautilus_trader.model.identifiers import InstrumentId
        fake,_=self.order_fake()
        sol=InstrumentId.from_str('SOL-USD-PERP.HYPERLIQUID')
        for iid,intent in ((fake.config.btc_id,'RISK_TRIM'),(sol,'POSITIVE_HARVEST'),(fake.config.btc_id,'DRAINING_HARVEST')):
            fake.policy_state=State(btc_intent='POSITIVE_HARVEST' if intent=='DRAINING_HARVEST' else intent,
                                    draining=intent=='DRAINING_HARVEST')
            order=CM2Strategy._make_order(fake,iid,OrderSide.SELL,Quantity.from_str('5.00000'),True,D(1070))
            self.assertEqual(order.order_type,OrderType.MARKET)
            self.assertEqual(order.time_in_force,TimeInForce.IOC)
    def geometry(self,**changes):
        args=dict(signed_before_qty=D(40),filled_qty=D(10),fill_price=D(1070),native_vwap=D(1000),
            allocated_entry_fees=D('4.32'),allocated_signed_funding=D('-.495'),
            native_commission=D('4.6224'),native_tick=D('.1'),known=True)
        args.update(changes)
        return actual_harvest_geometry(**args)
    def test_actual_native_fee_funding_geometry_long_short_and_drift(self):
        self.assertEqual(self.geometry()['status'],'PASS')
        self.assertEqual(self.geometry(signed_before_qty=D(-40),fill_price=D(930))['status'],'PASS')
        self.assertEqual(self.geometry(fill_price=D(1000))['status'],'FAIL')
        self.assertEqual(self.geometry(allocated_signed_funding=D(-1000))['status'],'FAIL')
        self.assertEqual(self.geometry(native_commission=D(1000))['status'],'FAIL')
        for changes in ({'known':False},{'native_vwap':None},{'filled_qty':D(41)}):
            self.assertEqual(self.geometry(**changes)['status'],'UNKNOWN')
    def test_actual_handler_post_submit_native_funding_drift_quarantines(self):
        class ID(str):venue='SIM'
        btc=ID('BTC')
        for funding,expected in ((D('-1.98'),'PASS'),(D(-4000),'FAIL')):
            pos=NS(entry=OrderSide.BUY,quantity=NS(as_decimal=lambda:D(30)),avg_px_open=1000)
            instrument=NS(settlement_currency='USDC',price_increment=NS(as_decimal=lambda:D('.1')))
            fake=NS(config=NS(btc_id=btc,execution_policy_hash='fixture'),
                policy_state=State(direction=1,parent=1,btc_target=D(30),btc_intent='POSITIVE_HARVEST',
                    harvest_target=D(30),harvest_start_qty=D(40)),_seen_trade_ids=set(),
                _order_audit={'harvest':{'reduce_only':True,'admission':{'parent':1,'intent':'POSITIVE_HARVEST'}}},
                cache=NS(position=lambda pid:pos,instrument=lambda iid:instrument),fill_audit=[],
                _entry_fees=D('17.28'),_btc_cost_qty=D(40),_parent_funding=D(0),_parent_cost_known=True,
                _restore_failed=False,_liquidating=False,_terminal_event=lambda *a,**k:None,
                _persist_checkpoint=lambda:None,_chain_audit=lambda *a:None)
            fake._sync_funding=lambda:setattr(fake,'_parent_funding',funding)
            fake._actual_harvest_fill_geometry=lambda e,foreign:CM2Strategy._actual_harvest_fill_geometry(fake,e,foreign)
            event=NS(trade_id='actual-event-like-id',client_order_id='harvest',instrument_id=btc,position_id='native-position',
                commission=NS(as_decimal=lambda:D('4.6224'),currency='USDC'),order_side=OrderSide.SELL,
                last_qty=NS(as_decimal=lambda:D(10)),last_px=NS(as_decimal=lambda:D(1070)),liquidity_side='TAKER',ts_event=1)
            CM2Strategy.on_order_filled(fake,event)
            self.assertEqual(fake.fill_audit[0]['actual_harvest_geometry']['status'],expected)
            self.assertEqual(fake._restore_failed,expected!='PASS')
            self.assertEqual(fake.policy_state.draining,expected!='PASS')
            self.assertTrue(fake.policy_state.harvested)
            self.assertEqual(fake._parent_funding,funding*D('.75'))
            self.assertEqual(pos.quantity.as_decimal(),D(30))  # read-only native facts

if __name__=='__main__':unittest.main()
