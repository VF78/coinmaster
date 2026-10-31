"""Constructor-free shared full API/probe protocol tests; real pipeline runs in probe child."""
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import Mock,patch
import tempfile
import pytest
from coinmaster.research.cm2_runner import full_native_kwargs,full_api_boundary_probe,worker_process_spec,wait_native_child,record_native_child

def request(root):
    return {"stage":"anchors","run_id":"CM2_ANCHOR_JOINT_R1","policy":{},
        "data_root":str(root/"public-data"),"warmup_root":str(root/"warmup"),
        "artifact_dir":str(root/"actual-case"),"current_hl_execution_inputs":str(root/"public-profile"),
        "_request_path":str(root/"request.json")}

def test_full_kwargs_explicitly_satisfy_existing_current_hl_guard():
    from coinmaster.research.qualification_policy import research_qualification
    with tempfile.TemporaryDirectory() as td:
        kwargs=full_native_kwargs(request(Path(td)))
        assert kwargs["qualification_mode"]=="execution_diagnostic"
        assert kwargs["qualification_quantity_model"]=="hl_current_usdc"
        assert research_qualification(kwargs["qualification_mode"],kwargs["qualification_quantity_model"],
            kwargs["qualification_instrument_metadata"],kwargs["qualification_deposit_runtime"],
            kwargs["qualification_deposit_equity_reader"],kwargs["qualification_deposit_account_id"])==({}, {})
        with pytest.raises(ValueError,match="EXECUTION_DIAGNOSTIC_CURRENT_HL_NO_DP_ONLY"):
            research_qualification("execution_diagnostic","legacy_bybit",None,None,None,"")

def test_probe_and_worker_kwargs_differ_only_in_artifact_directory():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);r=request(root)
        worker=full_native_kwargs(r)
        probe=full_native_kwargs(r,artifact_dir=root/"isolated-probe")
        assert probe.pop("artifact_dir")==root/"isolated-probe"
        worker.pop("artifact_dir")
        assert worker==probe

def test_api_probe_child_has_same_safe_flags_environment_without_attempt_lease():
    with tempfile.TemporaryDirectory() as td:
        r=request(Path(td))
        command,env,cwd=worker_process_spec(r,None,"digest",api_probe=True)
        assert command[1:3]==["-B","-s"] and "--api-probe" in command
        assert "--worker" not in command and "--lease-fd" not in command
        assert "--probe-dir" in command
        assert env["PYTHONNOUSERSITE"]=="1" and env["OMP_NUM_THREADS"]=="1"
        assert cwd==str(Path(r["artifact_dir"]).resolve())

def fake_pipeline(**kwargs):
    # Protocol-only fake; NOT evidence of the real full data pipeline.
    import nautilus_trader.backtest.engine as ne
    from coinmaster.research.native_baseline import ExecutionPolicy,FixedBaseFeePolicy
    qualification_mode=kwargs["qualification_mode"]
    qualification_quantity_model=kwargs["qualification_quantity_model"]
    qualification_instrument_metadata=kwargs["qualification_instrument_metadata"]
    qualification_deposit_runtime=kwargs["qualification_deposit_runtime"]
    qualification_deposit_equity_reader=kwargs["qualification_deposit_equity_reader"]
    qualification_deposit_account_id=kwargs["qualification_deposit_account_id"]
    policy=ExecutionPolicy()
    fee_policy=FixedBaseFeePolicy(venue="hyperliquid",hyperliquid_maker="0.000144",hyperliquid_taker="0.000432")
    current_hl=N(instruments=(N(id="BTC",settlement_currency="USDC"),N(id="SOL",settlement_currency="USDC")),
        evidence={"input_sha256":{"public-only":"test"}})
    selected_leverage=(("BTC",Decimal(40)),("SOL",Decimal(20)))
    initial_active_seed=kwargs["initial_active_seed"]
    trading_start_ms=kwargs["trading_start_ms"]
    trading_end_ms=kwargs["trading_end_ms"]
    warmup_start_ms=0
    research_cm2=kwargs["research_cm2"]
    journal=None
    ne.BacktestEngine(None)
    raise AssertionError("REAL_CONSTRUCTOR_MUST_NOT_RETURN")

def test_interception_protocol_requires_one_boundary_and_restores_constructor():
    from coinmaster.research import native_baseline as nb
    import nautilus_trader.backtest.engine as ne
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        sentinel=Mock(side_effect=AssertionError("REAL_NATIVE_ENGINE_MUST_NOT_BE_CALLED"))
        with patch.object(ne,"BacktestEngine",sentinel),patch.object(nb,"run_native_diagnostic",fake_pipeline):
            result=full_api_boundary_probe(request(root),root/"isolated-probe")
            assert result["boundary_calls"]==1 and result["native_engine_constructions"]==0
            assert ne.BacktestEngine is sentinel
            sentinel.assert_not_called()

def test_preboundary_failure_is_not_success_and_constructor_is_restored():
    from coinmaster.research import native_baseline as nb
    import nautilus_trader.backtest.engine as ne
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        sentinel=Mock(side_effect=AssertionError("REAL_NATIVE_ENGINE_MUST_NOT_BE_CALLED"))
        with patch.object(ne,"BacktestEngine",sentinel),patch.object(nb,"run_native_diagnostic",side_effect=ValueError("GUARD_FAILED")):
            with pytest.raises(ValueError,match="GUARD_FAILED"):
                full_api_boundary_probe(request(root),root/"isolated-probe")
            assert ne.BacktestEngine is sentinel
            sentinel.assert_not_called()


def test_exact_child_wait_usage_does_not_aggregate_prior_probe_child():
    import subprocess,sys
    child=subprocess.Popen([sys.executable,"-B","-s","-c","raise SystemExit(7)"])
    code,peak=wait_native_child(child)
    assert code==7 and child.returncode==7
    assert child.wait(timeout=.1)==7
    assert peak>0


def test_native_child_identity_is_exclusive_safe_and_inspectable():
    import json,os
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        result=record_native_child(root,12345,"CM2_ANCHOR_JOINT_R1","a"*64)
        stored=json.loads((root/"native-child.json").read_text())
        assert stored==result
        assert stored["native_child_pid"]==12345 and stored["parent_pid"]==os.getpid()
        assert stored["status"]=="RUNNING" and stored["spawn_utc"].endswith("+00:00")
        assert set(stored)=={"status","native_child_pid","parent_pid","run_id","request_sha256","spawn_utc"}
        with pytest.raises(FileExistsError):
            record_native_child(root,67890,"OTHER","b"*64)
