"""Public no--run dispatch protocol only; mocked probe, no API/native execution."""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import patch
import unittest
from coinmaster.research import cm2_runner as runner

class PublicFixtureProbeDispatchTest(unittest.TestCase):
    def test_public_no_run_probe_dispatch_and_unchanged_paths(self):
        cases=(("engineering","cm2-residual-dust-native-v1",1),
               ("engineering","cm2-current-child-native-v2",1),
               ("engineering","cm2-connected-native-v1",0),
               ("anchors",None,1))
        for stage,fixture_id,expected in cases:
            with self.subTest(stage=stage,fixture_id=fixture_id),TemporaryDirectory() as directory:
                root=Path(directory);request_path=root/"request.json";receipt_path=root/"resources.json"
                request_path.write_text(json.dumps({"stage":stage,"fixture_id":fixture_id,
                    "artifact_dir":str(root/"actual-case"),"run_id":"SYNTHETIC_DISPATCH"}))
                receipt_path.write_text("{}")
                def mock_probe(command,**kwargs):
                    self.assertIn("--api-probe",command)
                    self.assertNotIn("--worker",command)
                    self.assertNotIn("--lease-fd",command)
                    probe=Path(command[command.index("--probe-dir")+1])
                    (probe/"api-boundary-proof.json").write_text(json.dumps({
                        "status":"ACTUAL_API_ENGINE_BOUNDARY_PASS",
                        "boundary_calls":1,"native_engine_constructions":0}))
                    return NS(returncode=0,stdout="SYNTHETIC_MOCK_PROBE_NOT_ACTUAL_API")
                with patch.object(runner,"preflight") as preflight,patch("subprocess.run",side_effect=mock_probe) as child,patch.object(
                        runner,"acquire_shared_lease",side_effect=AssertionError("NO_LEASE_NO_RUN")),patch.object(
                        runner,"register_attempt",side_effect=AssertionError("NO_ATTEMPT_NO_RUN")),patch.object(
                        runner,"run_worker",side_effect=AssertionError("NO_ENGINE_NO_RUN")),patch(
                        "nautilus_trader.backtest.engine.BacktestEngine",side_effect=AssertionError("NO_NATIVE_CONSTRUCTOR")) as constructor,redirect_stdout(io.StringIO()) as output:
                    runner.main(["--request",str(request_path),"--resource-receipt",str(receipt_path)])
                preflight.assert_called_once()
                constructor.assert_not_called()
                self.assertEqual(child.call_count,expected)
                self.assertIn("CM2_PREFLIGHT_READY_NO_ENGINE_NO_ATTEMPT",output.getvalue())
                self.assertFalse((root/"actual-case").exists())

if __name__=="__main__":unittest.main()
