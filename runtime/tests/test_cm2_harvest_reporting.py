"""Reporting-only mixed-asset regression; no native constructors or engines."""
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest
from coinmaster.strategy.cm2_native import CM2Strategy
from coinmaster.strategy.cm2_policy import Config

class HarvestReportingTests(unittest.TestCase):
    def report(self,fills):
        fake=NS(config=NS(btc_id='BTC',sol_id='SOL',policy=Config(),terminal_close_at_ns=1),
            clock=NS(timestamp_ns=lambda:1),cache=NS(positions_open=lambda:[],orders_open=lambda:[],orders_inflight=lambda:[]),
            liquidation_audit=[],_liquidating=False,pre_submit_gate_blocks=[],fill_audit=fills,entry_sizing_audit=[],
            cm2_audit=[],child_permission_audit=[],_order_audit={},target_blockers={},orphan_intervals=[],orphan_started_ns=None,
            _parent_cost_known=True,_checkpoint_revision=0,_restore_failed=False,_liquidation_checks=0,_liquidation_unknown=0)
        return CM2Strategy.reporting_state(fake)['cm2']
    def row(self,asset,status=None):
        row={'instrument':asset,'admission':{'intent':'POSITIVE_HARVEST'}}
        if status is not None:row['actual_harvest_geometry']={'status':status}
        return row
    def test_mixed_SOL_NA_cannot_create_BTC_unknown_or_hide_BTC_failure(self):
        fills=[self.row('BTC','PASS'),self.row('SOL'),self.row('BTC','PASS'),self.row('SOL')]
        before=deepcopy(fills);r=self.report(fills)
        self.assertEqual(r['ordinary_harvest_actual_geometry']['status'],'PASS')
        self.assertEqual((r['ordinary_harvest_actual_geometry']['fills'],r['ordinary_harvest_actual_geometry']['pass'],r['ordinary_harvest_actual_geometry']['unknown']),(2,2,0))
        self.assertEqual(r['sol_staging_harvest_context'],{'status':'NOT_APPLICABLE_BTC_NET_GEOMETRY','fills':2})
        self.assertEqual(fills,before)
        for status in ('FAIL','UNKNOWN',None):
            result=self.report([self.row('BTC',status),self.row('SOL','PASS')])['ordinary_harvest_actual_geometry']
            self.assertEqual(result['status'],status or 'UNKNOWN');self.assertEqual(result['fills'],1)
        self.assertEqual(self.report([self.row('SOL')])['ordinary_harvest_actual_geometry']['status'],'UNKNOWN')
        self.assertEqual(self.report([self.row('BTC','UNKNOWN'),self.row('BTC','FAIL')])['ordinary_harvest_actual_geometry']['status'],'FAIL')

if __name__=='__main__':unittest.main()
