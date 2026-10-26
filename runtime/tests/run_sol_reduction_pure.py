"""Approved selected engine-free suite. Constructor tripwire installed BEFORE tests."""
from pathlib import Path
import argparse,json,sys
p=argparse.ArgumentParser();p.add_argument("--receipt",required=True);p.add_argument("--focused",action="store_true");args=p.parse_args()
import nautilus_trader.backtest.engine as engine
original=engine.BacktestEngine
attempts=[]
class GuardMeta(type):
    def __getattr__(cls,name):return getattr(original,name)
    def __call__(cls,*a,**kw):
        attempts.append("FORBIDDEN_BACKTEST_ENGINE_CONSTRUCTOR")
        raise AssertionError(attempts[-1])
class NoEngine(metaclass=GuardMeta):pass
engine.BacktestEngine=NoEngine
import pytest
selected=["tests/test_sol_reduction_v2_pure.py"]
if not args.focused:selected += ["tests/test_btc_flat_drain_pure.py","tests/test_native_account_snapshot_pure.py","tests/test_sol_standing_pure.py","tests/test_btc_trim_pure.py","tests/test_a0_rights_pure.py","tests/test_standing_tp_pure.py","tests/test_sol_standing_supervisor_pure.py"]
rc=pytest.main(["-q","-p","no:cacheprovider",*selected])
receipt=dict(status="ENGINE_FREE_PASS"if rc==0 and not attempts else"ENGINE_FREE_FAILED",pytest_exit_code=int(rc),selected_files=selected,constructor_tripwire_installed_before_test_import=True,forbidden_constructor_attempts=attempts,actual_engine_constructors=0,native_matching=0,pure_constructed_events_not_native_evidence=True)
Path(args.receipt).write_text(json.dumps(receipt,indent=2)+"\n")
raise SystemExit(0 if rc==0 and not attempts else 1)
