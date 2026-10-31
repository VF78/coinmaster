"""Fixture dispatch/actual import boundary interception; native engine zero."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import patch
import unittest
from coinmaster.research import cm2_runner as runner

class FixtureBoundaryTests(unittest.TestCase):
    def test_unknown_fixture_cannot_dispatch(self):
        with self.assertRaisesRegex(ValueError,'UNKNOWN_ENGINEERING_FIXTURE'):
            runner.engineering_fixture_module({'fixture_id':'unfrozen'})
    def test_actual_fixture_api_import_site_intercepted_and_restored(self):
        import nautilus_trader.backtest.engine as engine
        original=engine.BacktestEngine
        def actual_import_site(request):
            from nautilus_trader.backtest.engine import BacktestEngine
            BacktestEngine()  # intercepted, never original native constructor
        fixture=NS(__file__=__file__,run_fixture=actual_import_site)
        with TemporaryDirectory() as output,patch.object(runner,'engineering_fixture_module',return_value=fixture):
            receipt=runner.fixture_api_boundary_probe({'fixture_id':'cm2-current-child-native-v2',
                'start_ns':1,'end_ns':2},output)
            self.assertEqual(receipt['boundary_calls'],1)
            self.assertEqual(receipt['native_engine_constructions'],0)
            self.assertEqual(json.loads((Path(output)/'api-boundary-proof.json').read_text()),receipt)
        self.assertIs(engine.BacktestEngine,original)
    def test_missing_native_boundary_rejected_and_restored(self):
        import nautilus_trader.backtest.engine as engine
        original=engine.BacktestEngine
        with TemporaryDirectory() as output,patch.object(runner,'engineering_fixture_module',
                return_value=NS(__file__=__file__,run_fixture=lambda request:None)):
            with self.assertRaisesRegex(ValueError,'BOUNDARY_NOT_REACHED'):
                runner.fixture_api_boundary_probe({'fixture_id':'cm2-current-child-native-v2'},output)
        self.assertIs(engine.BacktestEngine,original)
    def test_worker_counts_new_dispatch_actual_import_site_without_native(self):
        import nautilus_trader.backtest.engine as engine
        sentinel=NS(status='fixture-result')
        def fake_engine(*args,**kwargs):return sentinel
        def actual_import_site(request):
            from nautilus_trader.backtest.engine import BacktestEngine
            return BacktestEngine()
        with TemporaryDirectory() as directory:
            root=Path(directory);lock=root/'lease';lock.touch()
            with lock.open('r') as fd,patch.object(engine,'BacktestEngine',fake_engine),patch.object(
                    runner,'engineering_fixture_module',return_value=NS(run_fixture=actual_import_site)):
                result=runner.run_worker({'stage':'engineering','shared_lock_path':str(lock),
                    'artifact_dir':str(root)},fd.fileno())
            self.assertIs(result,sentinel)
            self.assertEqual(json.loads((root/'engine-construction-count.json').read_text())['engine_constructions'],1)

if __name__=='__main__':unittest.main()
