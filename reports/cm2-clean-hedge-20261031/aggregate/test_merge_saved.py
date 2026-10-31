"""Synthetic saved-report inputs only; no native imports."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location("merge_saved",Path(__file__).with_name("merge_saved.py"))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
H="a"*64

class MergeTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def ref(self,name,value):
        p=self.root/name;p.write_text(json.dumps(value));return {"path":str(p),"sha256":m.sha(p)}
    def case(self,name,total="100",dd="20",binary=H):
        policy=dict(zip(m.PARAMS,[72,4,3,.75,.75,.45,.08]));policy["mode"]="joint"
        req=self.ref(name+"request",{"policy":policy,"source_commit":"b"*40})
        s={"case":name,"run_id":name,"TOTAL":total,"native_seed":"10000","financial_status":"PASS",
           "structural_status":"UNKNOWN","model_status":"MODEL_LIMITED","numeric_goal_status":"FAIL",
           "comparison_group_hash":H,"with_final_close_DD_percent":{"settled":dd,"coherent":dd},
           "provenance":{"request_sha256":req["sha256"],"report_sha256":m.hashlib.sha256(name.encode()).hexdigest(),
                         "source_hashes":{"policy":H},"data_hash":H,"policy_hash":H}}
        comp={"cases":[{"case":name,"run_id":name,"TOTAL":total,"financial_status":"PASS",
                        "comparison_group_hash":H,"report_sha256":s["provenance"]["report_sha256"],
                        "settled_DD_including_final_close":dd,"coherent_DD_including_final_close":dd}]}
        pins=dict(source_commit="b"*40,python_sha256=H,native_engine_sha256=binary,
                  native_binary_hashes={"objects":H},source_hashes={"policy":H},data_hash=H,
                  execution_policy_hash=H,seed="10000",
                  run_interval={"start":"2024-09-01","end_exclusive":"2026-09-01"},
                  fees={"rate":"0.000432"},currency="USDC")
        return dict(host="synthetic",summary=self.ref(name+"summary",s),request=req,
                    comparison=self.ref(name+"comparison",comp),pins=pins)
    def run_cases(self,*cases):
        return m.merge({"schema_version":1,"cases":list(cases)})["cases"]
    def test_dominated_equal_unknown_and_model_limited(self):
        a,b,c=self.case("a","100","20"),self.case("b","90","21"),self.case("c","100","20")
        rows=self.run_cases(a,b,c)
        self.assertEqual([r["pareto_native_numeric"] for r in rows],[True,False,True])
        self.assertEqual(rows[0]["structural_status"],"UNKNOWN")
        self.assertEqual(rows[0]["model_status"],"MODEL_LIMITED")
        self.assertIsNone(rows[0]["runtime_seconds"])
    def test_cross_binary_isolation(self):
        a,b=self.case("a"),self.case("b","90","21","c"*64)
        self.assertEqual([r["pareto_native_numeric"] for r in self.run_cases(a,b)],[True,True])
    def test_missing_pin(self):
        a=self.case("a");del a["pins"]["python_sha256"]
        r=self.run_cases(a)[0]
        self.assertIsNone(r["comparison_group_hash"]);self.assertIsNone(r["pareto_native_numeric"])
    def test_duplicate_case_and_run(self):
        a=self.case("a");rows=self.run_cases(a,copy.deepcopy(a))
        self.assertTrue(all(r["pareto_native_numeric"] is None for r in rows))
        self.assertIn("MISSING_OR_DUPLICATE:run_id",rows[0]["unknown_reasons"])
    def test_duplicate_raw_hash_different_identity(self):
        a,b=self.case("a"),self.case("b")
        sa=m.bound(a["summary"]);sb=m.bound(b["summary"])
        sb["provenance"]["report_sha256"]=sa["provenance"]["report_sha256"]
        b["summary"]=self.ref("bsummary2",sb)
        c=m.bound(b["comparison"]);c["cases"][0]["report_sha256"]=sa["provenance"]["report_sha256"]
        b["comparison"]=self.ref("bcomparison2",c)
        self.assertTrue(all(r["pareto_native_numeric"] is None for r in self.run_cases(a,b)))
    def test_nonfinite(self):
        for value in ("NaN","Infinity","-Infinity","garbage",None):
            with self.subTest(value=value):
                r=self.run_cases(self.case("a",value))[0]
                self.assertIsNone(r["TOTAL"]);self.assertIsNone(r["pareto_native_numeric"])
        self.assertEqual(m.finite("1.2345678901234567890123456789"),"1.2345678901234567890123456789")
    def test_bad_hash(self):
        a=self.case("a");a["summary"]["sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"INPUT_HASH_MISMATCH"):self.run_cases(a)
    def test_comparison_not_bound_to_summary(self):
        a=self.case("a");c=m.bound(a["comparison"]);c["cases"][0]["TOTAL"]="999"
        a["comparison"]=self.ref("badcomp",c)
        with self.assertRaisesRegex(ValueError,"COMPARISON_SUMMARY_MISMATCH"):self.run_cases(a)
    def test_comparison_dd_mismatch_missing_nonfinite(self):
        for kind in ("settled", "coherent"):
            for bad in ("99", None, "NaN", "Infinity"):
                with self.subTest(kind=kind,bad=bad):
                    a=self.case("a");c=m.bound(a["comparison"])
                    key=kind+"_DD_including_final_close"
                    if bad is None:del c["cases"][0][key]
                    else:c["cases"][0][key]=bad
                    a["comparison"]=self.ref("bad_dd",c)
                    r=self.run_cases(a)[0]
                    self.assertIsNone(r["comparison_group_hash"])
                    self.assertIsNone(r["pareto_native_numeric"])
                    self.assertIn("COMPARISON_SUMMARY_DD_UNPROVEN:"+kind,r["unknown_reasons"])
    def test_numerically_equal_dd_representation(self):
        a=self.case("a");c=m.bound(a["comparison"])
        c["cases"][0]["settled_DD_including_final_close"]="20.00"
        a["comparison"]=self.ref("equal_dd",c)
        self.assertTrue(self.run_cases(a)[0]["pareto_native_numeric"])
    def test_summary_request_mismatch(self):
        a=self.case("a");a["request"]=self.ref("otherrequest",{"policy":{}})
        with self.assertRaisesRegex(ValueError,"SUMMARY_REQUEST_HASH_MISMATCH"):self.run_cases(a)

if __name__=="__main__":unittest.main()
