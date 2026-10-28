"""M3 data/guard assertions only: no fills, account changes or engine."""
import hashlib,json,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import run_method_a_sol as runner
CASE=Path(__file__).resolve().parents[2]/"reports/method-a-verification-20261027/M3_DATA_CANDIDATE_APPROVED_20261028.json"

class M3CandidatePure(unittest.TestCase):
    def test_exact_causal_data_and_books(self):
        case=json.loads(CASE.read_text());rows={r['phase']:r for r in case['rows']}
        self.assertEqual(case['cancel_latency_ns'],2_000_000_000)
        self.assertEqual(case['expected_negative_reason'],'PARTIAL_NATIVE_STOP')
        self.assertEqual(rows['PRELOAD_CAP_BOOK_BEFORE_BTC_TPS']['quotes'][0]['asset'],'SOL')
        self.assertEqual(rows['PRELOAD_CAP_BOOK_BEFORE_BTC_TPS']['quotes'][0]['ask'],'132.9')
        self.assertEqual(rows['PRELOAD_CAP_BOOK_BEFORE_BTC_TPS']['quotes'][0]['ask_depth'],'10')
        self.assertLess(rows['PRELOAD_CAP_BOOK_BEFORE_BTC_TPS']['ns'],rows['BTC_TP0_ONLY']['ns'])
        self.assertEqual([rows[p]['quotes'][0]['bid_depth']for p in ('BTC_TP0_ONLY','BTC_TP1_ONLY','BTC_TP2_PARTIAL')],['116.875','116.874','116.251'])
        self.assertEqual(rows['SECOND_PARENT_FULL']['marks']['BTC'],rows['SECOND_PARENT_FULL']['quotes'][0]['bid'])
        self.assertEqual(rows['SECOND_PARENT_FULL']['marks']['BTC'],'100.3')
        self.assertEqual(rows['TINY_PROTECTED']['quotes'][0]['ask'],'128')
        self.assertEqual(rows['DECLARED_PARTIAL_STOP_FAULT']['quotes'][0]['bid_depth'],'.1')
        self.assertEqual(rows['DECLARED_PARTIAL_STOP_FAULT']['ns'],case['expected_negative_not_before_ns'])

    def test_exact_approved_bytes_and_reversible_data_only_patch(self):
        self.assertEqual(hashlib.sha256(CASE.read_bytes()).hexdigest(),"96cf5d004856e06742a88a0e61534d567deb373c41f9c8c705dd3eb275a802ba")
        case=json.loads(CASE.read_text())
        original=json.loads((CASE.parent/"m3-candidate/M3_DATA_PROPOSED.json").read_text())
        rows={r["phase"]:r for r in case["rows"]}
        self.assertEqual([q["asset"] for q in rows["CAP_PARTIAL"]["quotes"]],["BTC","SOL"])
        self.assertEqual(rows["CAP_PARTIAL"]["quotes"][0],dict(asset="BTC",bid="107",ask="107",bid_depth="116.251",ask_depth="1000"))
        for phase in ("LATE_TP0","LATE_TP1"):
            self.assertEqual(rows[phase]["quotes"][0]["ask_depth"],".2")
            rows[phase]["quotes"][0]["ask_depth"]=".1"
        rows["BTC_TP1_ONLY"]["quotes"][0]["bid_depth"]="116.875"
        rows["BTC_TP2_PARTIAL"]["quotes"][0]["bid_depth"]="116.250"
        rows["CAP_PARTIAL"]["quotes"].pop(0)
        self.assertEqual(case,original)

    def test_prepare_constructor_is_never_called(self):
        with patch.object(runner,'BacktestEngine',side_effect=AssertionError('FORBIDDEN_ENGINE')) as constructor:
            proof=runner.prepare(CASE)
        constructor.assert_not_called()
        self.assertEqual((len(proof['public_inputs']),proof['quote_count']),(140,57))
        self.assertEqual(proof['quote_universe'],{'BTC':25,'SOL':32})
        self.assertEqual(proof['engine_constructors'],0)
        self.assertFalse(proof['ready_to_launch'])

    def fault_context(self,stamp=100864_000_000_000,reason='PARTIAL_NATIVE_STOP'):
        engine=NS(cache=NS(orders=lambda:[]))
        strategy=NS(m3_risk=[dict(event='QUALIFICATION_NO_GO',timestamp_ns=str(stamp),reason=reason)],_pair_orders={})
        case=json.loads(CASE.read_text())
        return engine,strategy,case

    def test_expected_time_does_not_allow_wrong_reason(self):
        args=self.fault_context(reason='PROTECTION_OVERDUE_NEXT_QUOTE')
        with self.assertRaisesRegex(AssertionError,'M3_WRONG_EXPECTED_NATIVE_FAULT'):
            runner.assert_m3_fault(*args,100864_000_000_000)

    def test_earlier_no_go_cannot_be_relabelled(self):
        args=self.fault_context(stamp=100863_000_000_000)
        with self.assertRaisesRegex(AssertionError,'M3_UNEXPECTED_EARLY_OR_DUPLICATE_NO_GO'):
            runner.assert_m3_fault(*args,100865_000_000_000)

    def test_reason_without_actual_native_stop_is_rejected(self):
        args=self.fault_context()
        with self.assertRaisesRegex(AssertionError,'M3_MISSING_ACTUAL_FAULT_STOP'):
            runner.assert_m3_fault(*args,100864_000_000_000)
