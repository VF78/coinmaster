"""Constructor-free actual-profile denial predicate and failure artifact tests."""
import ast
from copy import deepcopy
import hashlib
import importlib.metadata
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from coinmaster.research import cm2_fixture_e04 as fixture

class E04FailureTests(unittest.TestCase):
    def test_actual_profile_raw_quantity_fault_precedes_margin_bypass(self):
        from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
        from nautilus_trader.backtest.config import BacktestEngineConfig
        from nautilus_trader.common.component import TestClock
        from nautilus_trader.common.factories import OrderFactory
        from nautilus_trader.model.identifiers import TraderId,StrategyId
        from nautilus_trader.model.objects import Quantity
        from nautilus_trader.model.enums import OrderSide,TimeInForce
        inputs=Path(__file__).parent/'fixtures/hl-current-20261029'
        expected={'native-btc-sol-raw.json':'8b818bff35fe19b1bb43b157453b5acae6ba2c23dbf92f5cbfe58bdae94ab6c4',
            'hyperliquid-meta-BTC-SOL-20261029.json':'3611d651c7973b61460c2430c95723f992bb69520bd33fb7c76fb354074197cf',
            'execution-profile-inputs.json':'0a3c32cb92c47174911ac834b31a61464b97fc9a602cca537fccde9fe6fc0ed5'}
        for name,digest in expected.items():self.assertEqual(hashlib.sha256((inputs/name).read_bytes()).hexdigest(),digest)
        with patch('nautilus_trader.backtest.engine.BacktestEngine',side_effect=AssertionError('NO_ENGINE')) as engine:
            sol=load_current_hl_diagnostic(inputs).instruments[1]
            self.assertEqual(sol.size_precision,2)
            self.assertEqual(str(sol.min_notional),'10.00000000 USDC')
            self.assertIsNone(sol.min_quantity)
            self.assertFalse(BacktestEngineConfig().risk_engine.bypass)
            factory=OrderFactory(TraderId('CM2-001'),StrategyId('CM2-001'),TestClock())
            order=factory.market(instrument_id=sol.id,order_side=OrderSide.BUY,
                quantity=Quantity.from_str(fixture.DENIED_QUANTITY_TEXT),time_in_force=TimeInForce.IOC)
            self.assertEqual(str(order.quantity),'0.001')
            self.assertEqual(order.quantity.precision,3)
            self.assertGreater(order.quantity.precision,sol.size_precision)
            engine.assert_not_called()
        native=Path(importlib.metadata.distribution('nautilus_trader').locate_file('nautilus_trader'))
        source=(native/'risk/engine.pyx').read_text()
        check=source.split('cpdef bint _check_order(self,',1)[1].split('cpdef bint _check_order_price',1)[0]
        self.assertIn('self._check_order_quantity(instrument, order)',check)
        quantity=source.split('cpdef str _check_quantity(self,',1)[1]
        self.assertIn('quantity._mem.precision > instrument.size_precision',quantity)
        account=source.split('cpdef bint _check_orders_risk_for_account(self,',1)[1]
        self.assertLess(account.index('if account.is_margin_account:'),account.index('instrument.min_notional is not None'))
        self.assertIn('if account.is_margin_account:\n            return True',account)
        # This proves the pinned source predicate/object shape, not a DENIED event.
    def test_denied_fixture_branch_uses_raw_Quantity_not_normalizing_make_qty(self):
        tree=ast.parse(Path(fixture.__file__).read_text())
        branch=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and isinstance(n.test,ast.Compare)
            and any(isinstance(c,ast.Constant) and c.value=='DENIED' for c in n.test.comparators))
        quantities=[kw.value for node in branch.body for call in ast.walk(node) if isinstance(call,ast.Call)
                    for kw in call.keywords if kw.arg=='quantity']
        self.assertEqual(len(quantities),1)
        quantity=quantities[0]
        self.assertIsInstance(quantity,ast.Call)
        self.assertEqual(ast.unparse(quantity.func),'Quantity.from_str')
    def test_delayed_ack_old_phase_blocks_short_new_schedule_does_not(self):
        from dataclasses import replace
        from decimal import Decimal as D
        from coinmaster.strategy.cm2_policy import Config,State,Snapshot,decide,MINUTE_NS
        cfg=Config(load=8,core=.5,hedge_fraction=.75)
        flat=Snapshot(D(10000),D(0),D(0),D(950),D(100),btc_entry_fees=D(0),btc_signed_funding=D(0))
        start=State(parent=1,last_hour=fixture.fixed_feature(8).closed_ns)
        st=start;observed=[]
        for minute,hour,unknown in ((503,8,True),(505,8,False),(541,9,False),(601,9,False),(661,11,False),(721,12,False),(961,16,False)):
            result=decide(cfg,fixture.fixed_feature(hour),replace(flat,unknown_orders=unknown),st,
                now_ns=fixture.START_NS+minute*MINUTE_NS)
            observed.append(result.reason);st=result.state
        self.assertEqual(observed,['UNKNOWN_DRAIN_AND_FIXED_TRIM','INVENTORY_RECHECK','VALIDITY_RECOVERY_WAIT',
            'UNKNOWN_DRAIN_AND_FIXED_TRIM','VALIDITY_RECOVERY_WAIT','NO_BREAKOUT','BTC_BREAKOUT_ENTRY'])
        # Corrected script has NO unknown fault before the intended short entry.
        entry=decide(cfg,fixture.fixed_feature(9),flat,start,now_ns=fixture.START_NS+541*MINUTE_NS)
        self.assertEqual(entry.reason,'BTC_BREAKOUT_ENTRY');self.assertLess(entry.btc_target,0)
        held=replace(flat,btc_qty=D(-40),btc_mark=D(960),btc_vwap=D(950),btc_entry_fees=D('16.416'))
        adverse=decide(cfg,fixture.fixed_feature(9),held,entry.state,now_ns=fixture.START_NS+542*MINUTE_NS)
        self.assertEqual(adverse.btc_target,D(-40))
        stale=decide(cfg,fixture.fixed_feature(9),held,adverse.state,now_ns=fixture.START_NS+601*MINUTE_NS)
        self.assertEqual(stale.btc_target,D(-20))
        held=replace(held,btc_qty=D(-20))
        a=decide(cfg,fixture.fixed_feature(11),held,stale.state,now_ns=fixture.START_NS+661*MINUTE_NS)
        b=decide(cfg,fixture.fixed_feature(12),held,a.state,now_ns=fixture.START_NS+721*MINUTE_NS)
        self.assertEqual(a.reason,'VALIDITY_RECOVERY_WAIT');self.assertEqual(b.btc_target,D(-20))
        tree=ast.parse(Path(fixture.__file__).read_text());faults={}
        for node in ast.walk(tree):
            if not isinstance(node,ast.If) or not isinstance(node.test,ast.Compare):continue
            if not isinstance(node.test.left,ast.Name) or node.test.left.id!='m':continue
            if len(node.test.comparators)!=1 or not isinstance(node.test.comparators[0],ast.Constant):continue
            minute=node.test.comparators[0].value
            for child in node.body:
                for call in ast.walk(child):
                    if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and call.func.attr=='append' and call.args and isinstance(call.args[0],ast.Constant):
                        faults[call.args[0].value]=minute
        self.assertEqual(faults['DELAYED_ACK'],1022);self.assertEqual(faults['UNKNOWN_ACK'],1025)
        self.assertGreater(faults['DELAYED_ACK'],1021);self.assertLess(faults['UNKNOWN_ACK'],1030)
        self.assertEqual(fixture.QUEUE_PULSE_MINUTES,(1026,1034))
    def test_partial_export_is_exclusive_read_only_facts_and_never_final_PASS(self):
        evidence={'native_cache_snapshot':{'positions':[['SOL','0.01']],'cash':'9999.999568'},
            'native_orders':[{'status_name':'FILLED','quantity':'0.01','filled_quantity':'0.01'}],
            'native_adapter':{'fill_audit':[{'qty':'0.01','px':'100','commission':'0.000432'}]},
            'retained_observer_state':{'sequence':17,'peak':'10000'}}
        before=deepcopy(evidence)
        with TemporaryDirectory() as output:
            path=fixture.write_partial_failure_evidence(output,{'run_id':'SYNTHETIC_TEST'},
                ValueError('E04_SENTINEL_REQUIRES_NATIVE_FLAT'),native_clock_ns=1,evidence=evidence)
            body=path.read_bytes();packet=json.loads(body)
            self.assertEqual(packet['checks'],'UNKNOWN_NOT_FINALIZED')
            self.assertEqual(packet['financial_qualification'],'UNKNOWN_ABORTED_PREFIX')
            self.assertEqual(packet['native_evidence'],before)
            self.assertFalse(packet['terminal_close_or_synthetic_fill_performed_by_export'])
            self.assertFalse(packet['ranking_eligible'])
            with self.assertRaises(FileExistsError):
                fixture.write_partial_failure_evidence(output,{},RuntimeError('later'),native_clock_ns=2,evidence={})
            self.assertEqual(path.read_bytes(),body)
        self.assertEqual(evidence,before)
        tree=ast.parse(Path(fixture.__file__).read_text())
        handler=next(n for n in ast.walk(tree) if isinstance(n,ast.ExceptHandler)
            and isinstance(n.type,ast.Name) and n.type.id=='BaseException')
        actions={n.func.attr for n in ast.walk(handler) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(actions & {'submit_order','cancel_order','end','finish_after_engine_end','summary','adjust_account','adjust_balance'})
        self.assertTrue(any(isinstance(n,ast.Raise) and n.exc is None for n in handler.body))

if __name__=='__main__':unittest.main()
