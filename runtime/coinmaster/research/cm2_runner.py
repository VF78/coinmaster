"""CM2-only construction and scoped native entrypoint; old runner remains default."""
from __future__ import annotations
import argparse
import csv
from dataclasses import dataclass,asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from coinmaster.strategy.cm2_policy import Config, Hour, Day, HOUR_NS
from coinmaster.strategy.cm2_execution import ExecutionLimits

WARMUP_HASHES = {
    "BTCUSDT":"04c00080fc0f6ec9e0499896da2b009f61bd15925d6ce3663e0cf81ac0ee97de",
    "SOLUSDT":"3a040f6f4ca3aec99ea4802f9dcb9b27a3fe24c91a7edcf820434dfc5d9a9506",
}

@dataclass(frozen=True)
class CM2RunConfig:
    policy: Config
    warmup_root: Path
    absolute_child_limit: Decimal = Decimal("1e100")
    daily_seed_path: Path | None = None
    daily_seed_sha256: str | None = None
    def daily_seed(self,start_ns):
        if self.policy.core_signal != "slow_d1_h4":
            return ()
        if self.daily_seed_path is None or self.daily_seed_sha256 is None:
            raise ValueError("CM2_GENUINE_PINNED_D1_SEED_REQUIRED")
        if hashlib.sha256(self.daily_seed_path.read_bytes()).hexdigest() != self.daily_seed_sha256:
            raise ValueError("CM2_D1_SEED_PIN_MISMATCH")
        if self.daily_seed_path.suffix == ".parquet":
            import pyarrow.parquet as pq
            raw=pq.read_table(self.daily_seed_path,columns=["open_time_ms","open","high","low","close"]).to_pylist()
        else:
            with self.daily_seed_path.open() as handle:
                raw=list(csv.DictReader(handle))
        # Saved dataset contract: UTC OPEN labels; availability is MODELLED at close.
        rows=tuple(Day(int(r["open_time_ms"])*1_000_000+24*HOUR_NS,
                int(r["open_time_ms"])*1_000_000+24*HOUR_NS,
                *(float(r[k]) for k in ("open","high","low","close"))) for r in raw
                if int(r["open_time_ms"])*1_000_000+24*HOUR_NS <= start_ns)
        if len(rows)<35 or rows[-1].closed_ns != start_ns or any(
            b.closed_ns-a.closed_ns != 24*HOUR_NS for a,b in zip(rows,rows[1:])):
            raise ValueError("CM2_GENUINE_CONTIGUOUS_PRESTART_D1_REQUIRED")
        return rows
    def seed(self,start_ns):
        paired={}
        for symbol,expected in WARMUP_HASHES.items():
            path=self.warmup_root/f"data-warmup-{symbol}-1h.csv"
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("CM2_WARMUP_PIN_MISMATCH:"+symbol)
            with path.open() as handle:
                paired[symbol]={int(row["open_time_ms"])*1_000_000+HOUR_NS:row for row in csv.DictReader(handle)
                    if int(row["open_time_ms"])*1_000_000+HOUR_NS <= start_ns}
        keys=sorted(set(paired["BTCUSDT"]) & set(paired["SOLUSDT"]))[-169:]
        if len(keys)!=169 or keys[-1]!=start_ns or any(b-a!=HOUR_NS for a,b in zip(keys,keys[1:])):
            raise ValueError("CM2_EXACT_169_PRESTART_HOURS_REQUIRED")
        return tuple(Hour(t,t,*(float(paired["BTCUSDT"][t][k]) for k in ("open","high","low","close")),
                          float(paired["SOLUSDT"][t]["close"])) for t in keys)

def build_strategy(run_config, *, instruments, minute_bars, margin_policy, start_ns, end_ns,
                   mark_types,mark_client,journal,exit_fee_rate,execution_hash,risk_recorder=None,coherent_observer=None):
    from coinmaster.strategy.cm2_native import CM2Strategy, CM2StrategyConfig
    cls=CM2Strategy
    if risk_recorder is not None:
        from coinmaster.research.minute_risk import observed_neutral_strategy_type
        cls=observed_neutral_strategy_type(cls,risk_recorder)
    from coinmaster.research.cm2_funding_reader import NativeSignedFundingReader
    native_signed_funding=NativeSignedFundingReader(journal)
    from coinmaster.strategy.cm2_checkpoint import NativeCheckpointStore,observer_continuity
    checkpoint_store=NativeCheckpointStore(journal)
    return cls(CM2StrategyConfig(btc_id=instruments[0].id,sol_id=instruments[1].id,
        btc_bar_type=minute_bars[instruments[0].id],sol_bar_type=minute_bars[instruments[1].id],
        btc_mark_data_type=mark_types[0],sol_mark_data_type=mark_types[1],mark_client_id=mark_client,
        policy=run_config.policy,limits=ExecutionLimits(run_config.absolute_child_limit),
        margin_policy=margin_policy,trading_start_open_ns=start_ns,terminal_close_at_ns=end_ns,
        seed_hours=run_config.seed(start_ns),seed_days=run_config.daily_seed(start_ns),exit_fee_rate=exit_fee_rate,
        execution_policy_hash=execution_hash,funding_reader=native_signed_funding,
        checkpoint_store=checkpoint_store,continuity_reader=lambda:observer_continuity(risk_recorder,coherent_observer)))

def auxiliary_audits(strategy):
    if hasattr(strategy,"cm2_audit"):
        return {"native_cm2_audit":strategy.cm2_audit}
    return dict(native_risk_first_audit=strategy.risk_first_sol_audit,
                native_carry_audit=strategy.carry_pair_audit,native_carry_counts=strategy.carry_pair_counts,
                native_alpha_audit=strategy.alpha_cushion_audit,native_alpha_counts=strategy.alpha_cushion_counts)

def complete_report(result,strategy,engine,journal,seed,coherent):
    from coinmaster.research.native_accounting import native_position_lifecycles
    postings=journal.funding_cash_audit() if journal else []
    signed=sum((Decimal(row[5]) for row in postings),Decimal(0))
    result["funding_cash_audit"]=postings
    result["funding"]["signed_amount"]=str(signed)
    lifecycle=native_position_lifecycles(engine.cache)
    complete=not lifecycle["unknown"] and all(p["closed"] and p["realized_pnl"] is not None for p in lifecycle["positions"]) and not engine.cache.positions_open()
    realized=sum((Decimal(p["realized_pnl"]) for p in lifecycle["positions"]),Decimal(0)) if complete else None
    bridge=Decimal(result["terminal_active"])-seed-realized-signed if complete else None
    result["native_cash_reconciliation"]={
        "status":"EXACT" if bridge==0 else "UNKNOWN_UNALLOCATED_NATIVE_BRIDGE",
        "native_position_lifecycle_export":lifecycle,
        "native_realized_total":str(realized) if complete else None,
        "signed_funding":str(signed),"unallocated_bridge":str(bridge) if complete else None,
        "fees_policy":"NATIVE_POSITION_REALIZED_ALREADY_INCLUDES_COMMISSIONS",
        "actual_native_cash_transitions":(coherent or {}).get("native_cash_transitions")}
    result["cm2"]=strategy.reporting_state()["cm2"]
    result["config"].pop("candidate",None)
    result["config"]["cm2"]=result["cm2"]["policy"]
    result["config"]["cm2_request_contract"]=result["cm2"]["request_contract"]
    result["request_execution_model_id"]=result["cm2"]["request_execution_model_id"]
    result["request_contract_sha256"]=result["cm2"]["request_contract_sha256"]
    result["cm2"]["capacity_model"]={"participation":"0.01","source":"PREVIOUS_COMPLETED_MINUTE_TURNOVER",
        "cadence":"ONE_CHILD_PER_MINUTE_PER_SYMBOL","emergency_reductions":"EXEMPT",
        "historical_queue":"UNKNOWN_M1_FULL_FILL_ZERO_IMPACT_PROXY"}
    result["cm2"]["structural_diagnostics"]="UNKNOWN_PENDING_NATIVE_ACCEPTANCE"
    result["source_hashes"]={str(path.relative_to(Path(__file__).parents[1])):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (Path(__file__),Path(__file__).parents[1]/"strategy/cm2_policy.py",
                     Path(__file__).parents[1]/"strategy/cm2_execution.py",Path(__file__).parents[1]/"strategy/cm2_native.py",
                     Path(__file__).parents[1]/"strategy/cm2_order_contract.py",Path(__file__).parents[1]/"strategy/cm2_checkpoint.py",Path(__file__).with_name("cm2_funding_reader.py"),Path(__file__).with_name("cm2_committed_validation.py"))}
    # The config hash includes the new economic policy, unlike the legacy wrapper.
    result["config_hash"]=hashlib.sha256(json.dumps(result["config"],sort_keys=True,separators=(",",":")).encode()).hexdigest()

def acquire_shared_lease(path):
    import fcntl
    stream=Path(path).open("a+")
    try:
        fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BaseException:
        stream.close()
        raise
    # Never LOCK_UN: a child may share this open-file-description.
    return stream

def preflight(request,receipt):
    required=("source_config_data_binary_freeze","independent_money_causality_review",
              "own_stage_root_GO","fresh_resource_check","secretless_environment")
    if receipt.get("status")!="R2_RELEASED" or not all(receipt.get(k) is True for k in required):
        raise ValueError("CM2_NATIVE_HOLD_RESOURCE_OR_SCOPED_GATE")
    if receipt.get("stage")!=request["stage"]:
        raise ValueError("CM2_STAGE_RECEIPT_MISMATCH")
    if not request.get("freeze_files"):
        raise ValueError("CM2_SOURCE_CONFIG_DATA_BINARY_FREEZE_REQUIRED")
    for item in request["freeze_files"]:
        path=Path(item["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item["sha256"]:
            raise ValueError("CM2_FREEZE_MISMATCH:"+str(path))
    cfg=CM2RunConfig(Config(**request["policy"]),Path(request["warmup_root"]),
        daily_seed_path=Path(request["daily_seed_path"]) if request.get("daily_seed_path") else None,
        daily_seed_sha256=request.get("daily_seed_sha256"))
    if request["stage"]=="engineering":
        fixture=engineering_fixture_module(request)
        if (request.get("fixture_id") not in getattr(fixture,"FIXTURE_IDS",(fixture.FIXTURE_ID,))
                or (request.get("start_ns"),request.get("end_ns")) != (fixture.START_NS,fixture.END_NS)):
            raise ValueError("CM2_EXPLICIT_BOUNDED_FIXTURE_CONTRACT_REQUIRED")
    else:
        cfg.seed(int(request.get("start_ns",1725148800000000000)))
        cfg.daily_seed(int(request.get("start_ns",1725148800000000000)))
        if cfg.policy.core_signal == "slow_d1_h4" and not any(
                Path(item["path"]) == cfg.daily_seed_path and item.get("sha256") == cfg.daily_seed_sha256
                for item in request["freeze_files"]):
            raise ValueError("CM2_D1_SEED_MUST_BE_IN_REQUEST_FREEZE")
    return cfg

def engineering_fixture_module(request):
    import importlib
    modules={"cm2-connected-native-v1":"coinmaster.research.cm2_fixture",
             "cm2-current-child-native-v2":"coinmaster.research.cm2_fixture_e04",
             "cm2-current-child-native-v3":"coinmaster.research.cm2_fixture_e08",
             "cm2-residual-dust-native-v1":"coinmaster.research.cm2_fixture_dust",
             "cm2-systematic-repair-native-v4":"coinmaster.research.cm2_fixture_v4",
             "cm2-systematic-repair-trim-native-v4":"coinmaster.research.cm2_fixture_v4",
             "cm2-execution-units-emergency-native-v1":"coinmaster.research.cm2_fixture_v4"}
    name=modules.get(request.get("fixture_id"))
    if name is None: raise ValueError("CM2_UNKNOWN_ENGINEERING_FIXTURE")
    return importlib.import_module(name)


def fixture_api_boundary_probe(request,probe):
    """Exercise the ACTUAL fixture up to its imported native constructor."""
    import nautilus_trader.backtest.engine as native_engine
    fixture=engineering_fixture_module(request)
    probe=Path(probe);probe.mkdir(parents=True,exist_ok=True)
    original=native_engine.BacktestEngine
    calls=[]
    class BoundaryReached(BaseException): pass
    def boundary(*args,**kwargs):
        calls.append(1)
        raise BoundaryReached()
    native_engine.BacktestEngine=boundary
    try:
        try: fixture.run_fixture({**request,"artifact_dir":str(probe)})
        except BoundaryReached: pass
        else: raise ValueError("CM2_FIXTURE_NATIVE_BOUNDARY_NOT_REACHED")
    finally:
        native_engine.BacktestEngine=original
    if len(calls)!=1: raise ValueError("CM2_FIXTURE_NATIVE_BOUNDARY_COUNT")
    receipt={"status":"ACTUAL_API_ENGINE_BOUNDARY_PASS","kind":"ENGINEERING_FIXTURE",
        "boundary_calls":len(calls),"native_engine_constructions":0,
        "fixture_id":request["fixture_id"],"start_ns":request["start_ns"],"end_ns":request["end_ns"],
        "only_kwarg_substitution":"artifact_dir","fixture_source_sha256":hashlib.sha256(Path(fixture.__file__).read_bytes()).hexdigest()}
    (probe/"api-boundary-proof.json").write_text(json.dumps(receipt,indent=2)+"\n")
    return receipt


def append_ledger(path,row):
    import fcntl,os
    with Path(path).open("a+") as stream:
        fcntl.flock(stream.fileno(),fcntl.LOCK_EX)
        stream.write(json.dumps(row,sort_keys=True)+"\n")
        stream.flush()
        os.fsync(stream.fileno())

def register_attempt(request,receipt):
    import fcntl,os
    budget=json.loads(Path(request["budget_path"]).read_text())
    ledger=Path(request["attempt_ledger"])
    ledger.parent.mkdir(parents=True,exist_ok=True)
    with ledger.open("a+") as stream:
        fcntl.flock(stream.fileno(),fcntl.LOCK_EX)
        stream.seek(0)
        rows=[json.loads(line) for line in stream if line.strip()]
        starts=[row for row in rows if row.get("status")=="STARTED"]
        if any(row["run_id"]==request["run_id"] for row in starts):
            raise ValueError("CM2_ATTEMPT_EXISTS_NO_REPLAY")
        stage=request["stage"]
        count=sum(row["stage"]==stage for row in starts)
        spec=budget["stages"][stage]
        if len(starts)>=budget["total_physical_cap"] or count>=spec["cap"]:
            raise ValueError("CM2_BUDGET_EXHAUSTED")
        if stage=="broad" and count>=spec["initial_block"] and receipt.get("second_broad_block_GO") is not True:
            raise ValueError("CM2_CONDITIONAL_BROAD_HOLD")
        if stage=="local" and receipt.get("explained_region_GO") is not True:
            raise ValueError("CM2_CONDITIONAL_LOCAL_HOLD")
        if stage=="qualification" and receipt.get("actual_finalist_GO") is not True:
            raise ValueError("CM2_QUALIFICATION_HOLD")
        entry={"run_id":request["run_id"],"stage":stage,"status":"STARTED",
               "scope_version":budget["scope_version"]}
        stream.seek(0,2)
        stream.write(json.dumps(entry,sort_keys=True)+"\n")
        stream.flush()
        os.fsync(stream.fileno())
    return entry

def validate_full_output(result,request):
    # Postprocessing only: project actual committed-native watermarks; preserve
    # sparse legacy recorder, original raw file, money and source/model IDs.
    from coinmaster.research.cm2_committed_validation import qualify,sha,provenance_files
    output=Path(request["artifact_dir"])
    raw=output/(request["run_id"]+"-raw-native.json")
    count=json.loads((output/"engine-construction-count.json").read_text())["engine_constructions"]
    proof=qualify(raw,output/"minute-native-settled-receipts.csv.gz",
        output/"coherent-native-events.jsonl.gz",output/"committed-wm-qualification-v1",
        Path(__file__).with_name("minute_risk.py"),Path(request["qualified_coverage_source"]),count,
        expected_report_sha=sha(raw),provenance=provenance_files(
            request=request.get("_request_path"),ledger=request.get("attempt_ledger"),
            engine_count_path=output/"engine-construction-count.json"))
    result["actual_feed_coverage"]=proof["coverage"]
    result["cm2"]["financial_checks"]=proof["checks"]
    result["cm2"]["accounting_status"]="PASS"
    result["derived_financial_status"]="PASS"
    result["committed_wm_qualification"]={k:proof[k] for k in
        ("qualification_model_id","original_report_sha256","parent_raw_model_ids","comparability","derived_report_sha256")}
    result["committed_wm_qualification_receipt"]=str(output/"committed-wm-qualification-v1/QUALIFICATION.json")


def full_native_kwargs(request, *, artifact_dir=None):
    """Single exact canonical full API contract shared by worker and probe."""
    return dict(data_root=Path(request["data_root"]),
        artifact_dir=Path(request["artifact_dir"]) if artifact_dir is None else Path(artifact_dir),
        artifact_label=request["run_id"],include_funding=True,
        current_hl_execution_inputs=Path(request["current_hl_execution_inputs"]),
        qualification_mode="execution_diagnostic",qualification_quantity_model="hl_current_usdc",
        qualification_instrument_metadata=None,qualification_deposit_runtime=None,
        qualification_deposit_equity_reader=None,qualification_deposit_account_id="",
        trading_start_ms=1725148800000,trading_end_ms=1788220800000,
        initial_active_seed=Decimal("10000"),observe_minute_risk=True,
        research_cm2=CM2RunConfig(Config(**request["policy"]),Path(request["warmup_root"]),
        daily_seed_path=Path(request["daily_seed_path"]) if request.get("daily_seed_path") else None,
        daily_seed_sha256=request.get("daily_seed_sha256")),
        weekly_batch_minutes=1440,cursor_batch_rows=1440)

def full_api_boundary_probe(request,probe_dir):
    """Run exact public-data pipeline; intercept BEFORE actual engine creation."""
    import inspect,time
    import nautilus_trader.backtest.engine as native_engine
    from coinmaster.research import native_baseline as nb
    probe=Path(probe_dir).resolve()
    case=Path(request["artifact_dir"]).resolve()
    if probe==case or probe.is_relative_to(case) or case.is_relative_to(probe):
        raise ValueError("PROBE_CASE_ARTIFACT_OVERLAP")
    probe.mkdir(parents=True,exist_ok=True)
    if (probe/"probe-io-provenance.json").exists() or (probe/"api-boundary-proof.json").exists():
        raise ValueError("PROBE_EVIDENCE_EXISTS_NO_REPLAY")
    kwargs=full_native_kwargs(request,artifact_dir=probe)
    original=native_engine.BacktestEngine
    calls=0;captured={};opened_journal=None
    class EngineBoundaryReached(BaseException): pass
    def boundary(*args,**kw):
        nonlocal calls,opened_journal
        calls+=1
        frame=inspect.currentframe().f_back
        try:
            if frame.f_code is not nb.run_native_diagnostic.__code__:
                raise ValueError("UNEXPECTED_ENGINE_BOUNDARY_CALLER")
            local=frame.f_locals
            # Approved fields only; never serialize the frame or account/env.
            profile=local["current_hl"]
            captured.update(qualification_mode=local["qualification_mode"],
                qualification_quantity_model=local["qualification_quantity_model"],
                deposit_parameters_disabled=all(local[k] is None for k in
                    ("qualification_instrument_metadata","qualification_deposit_runtime","qualification_deposit_equity_reader"))
                    and local["qualification_deposit_account_id"]=="",
                actual_execution_policy=asdict(local["policy"]),actual_fee_policy=asdict(local["fee_policy"]),
                initial_active_seed=str(local["initial_active_seed"]),
                trading_start_ms=local["trading_start_ms"],trading_end_ms=local["trading_end_ms"],
                warmup_start_ms=local["warmup_start_ms"],
                accounting_currencies=[str(i.settlement_currency) for i in profile.instruments],
                instruments=[str(i.id) for i in profile.instruments],
                public_profile_evidence=profile.evidence,
                selected_leverage={str(i):str(v) for i,v in local["selected_leverage"]},
                actual_cm2_policy=asdict(local["research_cm2"].policy))
            opened_journal=local.get("journal")
        finally:
            del frame
        raise EngineBoundaryReached()
    native_engine.BacktestEngine=boundary
    started=time.monotonic();reached=False;error=None
    try:
        nb.run_native_diagnostic(**kwargs)
        raise ValueError("API_RETURNED_WITHOUT_ENGINE_BOUNDARY")
    except EngineBoundaryReached:
        reached=True
    except BaseException as exc:
        error={"type":type(exc).__name__,"message":str(exc)}
        raise
    finally:
        native_engine.BacktestEngine=original
        if opened_journal is not None:
            opened_journal.close()
        provenance={"case_artifact_dir":str(case),"probe_artifact_dir":str(probe),
            "only_kwarg_substitution":"artifact_dir","boundary_calls":calls,
            "native_engine_constructions":0,"engine_boundary_reached":reached,
            "elapsed_seconds":time.monotonic()-started,"error":error}
        (probe/"probe-io-provenance.json").write_text(json.dumps(provenance,indent=2)+"\n")
    if calls!=1 or not reached:
        raise ValueError("EXACT_ONE_PREENGINE_BOUNDARY_REQUIRED")
    if (captured["qualification_mode"]!="execution_diagnostic"
        or captured["qualification_quantity_model"]!="hl_current_usdc"
        or not captured["deposit_parameters_disabled"]
        or captured["accounting_currencies"]!=["USDC","USDC"]
        or captured["initial_active_seed"]!="10000"
        or captured["trading_start_ms"]!=1725148800000 or captured["trading_end_ms"]!=1788220800000):
        raise ValueError("ACTUAL_CM2_NATIVE_API_CONTRACT_DRIFT")
    actual=captured["actual_fee_policy"]
    if actual["venue"]!="hyperliquid" or actual["hyperliquid_maker"]!="0.000144" or actual["hyperliquid_taker"]!="0.000432":
        raise ValueError("ACTUAL_CM2_NATIVE_FEE_DRIFT")
    receipt={"status":"ACTUAL_API_ENGINE_BOUNDARY_PASS","native_engine_constructions":0,
        "boundary_calls":calls,"probe_artifact_dir":str(probe),"only_kwarg_substitution":"artifact_dir",
        "captured":captured,"source_sha256":{
            "native_baseline":hashlib.sha256(Path(nb.__file__).read_bytes()).hexdigest(),
            "cm2_runner":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "provenance_sha256":hashlib.sha256((probe/"probe-io-provenance.json").read_bytes()).hexdigest()}
    (probe/"api-boundary-proof.json").write_text(json.dumps(receipt,indent=2,default=str)+"\n")
    return receipt

def run_worker(request,lease_fd):
    # Worker alone imports the runner capable of constructing a native engine.
    import os
    stat=os.fstat(lease_fd)
    target=os.stat(request["shared_lock_path"])
    if (stat.st_dev,stat.st_ino)!=(target.st_dev,target.st_ino):
        raise ValueError("CM2_LEASE_FD_INODE_MISMATCH")
    import nautilus_trader.backtest.engine as native_engine
    original=native_engine.BacktestEngine
    constructions=[]
    def exactly_one(*args,**kwargs):
        if constructions:
            raise RuntimeError("CM2_ONE_NATIVE_ENGINE_PER_ATTEMPT")
        constructions.append("RESERVED_BEFORE_CONSTRUCTOR")
        return original(*args,**kwargs)
    native_engine.BacktestEngine=exactly_one
    try:
        if request["stage"]=="engineering":
            result=engineering_fixture_module(request).run_fixture(request)
            if len(constructions)!=1: raise ValueError("CM2_ACTUAL_FIXTURE_ENGINE_CONSTRUCTOR_COUNT")
            return result
        from coinmaster.research.native_baseline import run_native_diagnostic,save_diagnostic_report
        result=run_native_diagnostic(**full_native_kwargs(request))
        (Path(request["artifact_dir"])/"engine-construction-count.json").write_text(
            json.dumps({"engine_constructions":len(constructions)})+"\n")
        # Preserve raw native evidence before an independent validation failure.
        save_diagnostic_report(Path(request["data_root"]),result,request["run_id"],Path(request["artifact_dir"]))
        validate_full_output(result,request)
        save_diagnostic_report(Path(request["data_root"]),result,request["run_id"],Path(request["artifact_dir"]))
    finally:
        native_engine.BacktestEngine=original
        (Path(request["artifact_dir"])/"engine-construction-count.json").write_text(
            json.dumps({"engine_constructions":len(constructions)})+"\n")

def worker_process_spec(request,lease_fd,digest,*,api_probe=False):
    """Literal secretless child contract; never copy the host environment."""
    import sys
    output=Path(request["artifact_dir"]).resolve()
    output.mkdir(parents=True,exist_ok=True)
    own_home=output/".worker-home"
    own_home.mkdir(exist_ok=True)
    child_env={"PATH":"/usr/bin:/bin:/usr/sbin:/sbin","HOME":str(own_home),
        "LANG":"C","LC_ALL":"C","TZ":"UTC","PYTHONUTF8":"1",
        "PYTHONNOUSERSITE":"1","PYTHONDONTWRITEBYTECODE":"1",
        "OMP_NUM_THREADS":"1","OPENBLAS_NUM_THREADS":"1","MKL_NUM_THREADS":"1",
        "VECLIB_MAXIMUM_THREADS":"1","NUMEXPR_NUM_THREADS":"1",
        "PYTHONPATH":str(Path(__file__).parents[2])}
    command=[sys.executable,"-B","-s","-m","coinmaster.research.cm2_runner",
        "--api-probe" if api_probe else "--worker",
        "--request",str(Path(request["_request_path"]).resolve()),"--request-sha256",digest]
    if not api_probe:
        command.extend(["--lease-fd",str(lease_fd)])
    else:
        command.extend(["--probe-dir",str(output)])
    return command,child_env,str(output)

def record_native_child(output,pid,run_id,request_sha256):
    """Persist only safe operational identity immediately after worker spawn."""
    import os
    from datetime import datetime,timezone
    receipt={"status":"RUNNING","native_child_pid":int(pid),"parent_pid":os.getpid(),
        "run_id":run_id,"request_sha256":request_sha256,
        "spawn_utc":datetime.now(timezone.utc).isoformat()}
    with (Path(output)/"native-child.json").open("x") as stream:
        stream.write(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    return receipt

def wait_native_child(child):
    """Per-PID rusage; earlier constructor-free probe is not this worker."""
    import os,sys
    _,status,usage=os.wait4(child.pid,0)
    child.returncode=os.waitstatus_to_exitcode(status)
    peak=int(usage.ru_maxrss)*(1 if sys.platform=="darwin" else 1024)
    return child.returncode,peak

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--request",type=Path,required=True)
    parser.add_argument("--resource-receipt",type=Path)
    parser.add_argument("--run",action="store_true")
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--api-probe",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--probe-dir",type=Path,help=argparse.SUPPRESS)
    parser.add_argument("--lease-fd",type=int,help=argparse.SUPPRESS)
    parser.add_argument("--request-sha256",help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    request_bytes=args.request.read_bytes()
    request=json.loads(request_bytes)
    digest=hashlib.sha256(request_bytes).hexdigest()
    if args.api_probe:
        if args.probe_dir is None or digest!=args.request_sha256:
            raise SystemExit("CM2_INTERNAL_PROBE_CONTRACT")
        if request["stage"]=="engineering": fixture_api_boundary_probe(request,args.probe_dir)
        else: full_api_boundary_probe(request,args.probe_dir)
        print("ACTUAL_API_ENGINE_BOUNDARY_PASS_CONSTRUCTORS0")
        return
    if args.worker:
        request["_request_path"]=str(args.request.resolve())
        if args.lease_fd is None or digest!=args.request_sha256:
            raise SystemExit("CM2_INTERNAL_WORKER_CONTRACT")
        return run_worker(request,args.lease_fd)
    if args.resource_receipt is None:
        raise SystemExit("CM2_NATIVE_HOLD_NO_RESOURCE_RECEIPT")
    receipt=json.loads(args.resource_receipt.read_text())
    preflight(request,receipt)
    if request["stage"]!="engineering" or request.get("fixture_id") in ("cm2-current-child-native-v2","cm2-current-child-native-v3","cm2-residual-dust-native-v1","cm2-systematic-repair-native-v4","cm2-systematic-repair-trim-native-v4","cm2-execution-units-emergency-native-v1"):
        import uuid,subprocess
        probe=Path(request.get("api_probe_root",str(Path(request["artifact_dir"]).parent/"api-probes")))/str(uuid.uuid4())
        command,env,cwd=worker_process_spec(
            {**request,"artifact_dir":str(probe),"_request_path":str(args.request)},None,digest,api_probe=True)
        result=subprocess.run(command,env=env,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        (probe/"api-probe-worker.log").write_text(result.stdout)
        if result.returncode:
            raise SystemExit("CM2_FULL_API_PREFLIGHT_FAILED_NO_ATTEMPT:"+str(probe))
        proof=json.loads((probe/"api-boundary-proof.json").read_text())
        if proof["status"]!="ACTUAL_API_ENGINE_BOUNDARY_PASS" or proof["boundary_calls"]!=1 or proof["native_engine_constructions"]!=0:
            raise SystemExit("CM2_FULL_API_PREFLIGHT_INVALID_NO_ATTEMPT")
    if not args.run:
        print("CM2_PREFLIGHT_READY_NO_ENGINE_NO_ATTEMPT")
        return
    import os,subprocess,sys,time
    try:
        shared=acquire_shared_lease(request["shared_lock_path"])
    except BlockingIOError:
        raise SystemExit("CM2_NATIVE_HOLD_SHARED_LEASE")
    # Closing parent FD does not unlock the inherited child FD.
    with shared:
        output=Path(request["artifact_dir"])
        output.mkdir(parents=True,exist_ok=True)
        entry=register_attempt(request,receipt)
        entry["request_sha256"]=digest
        (output/"ATTEMPT_STARTED.json").write_text(json.dumps(entry)+"\n")
        command,child_env,child_cwd=worker_process_spec(
            {**request,"_request_path":str(args.request)},shared.fileno(),digest)
        start=time.monotonic()
        child=None
        try:
            with (output/"worker.log").open("w") as log:
                child=subprocess.Popen(command,env=child_env,cwd=child_cwd,stdout=log,stderr=subprocess.STDOUT,
                                       pass_fds=(shared.fileno(),))
                child_identity=record_native_child(output,child.pid,request["run_id"],digest)
                code,peak=wait_native_child(child)
            terminal={**entry,"status":"COMPLETED" if code==0 else "FAILED","exit_code":code,
                      "elapsed_seconds":time.monotonic()-start,"true_child_peak_rss_bytes":peak,
                      "rss_basis":"WAIT4_EXACT_NATIVE_CHILD_RUSAGE_MAXRSS"}
            with (output/"native-child-terminal.json").open("x") as stream:
                stream.write(json.dumps({**child_identity,**terminal},indent=2,sort_keys=True)+"\n")
            append_ledger(request["attempt_ledger"],terminal)
            if code:
                raise SystemExit(code)
        except BaseException as error:
            if child is None:
                append_ledger(request["attempt_ledger"],{**entry,"status":"FAILED","error_type":type(error).__name__,
                    "elapsed_seconds":time.monotonic()-start})
            elif child.poll() is None:
                append_ledger(request["attempt_ledger"],{**entry,"status":"PARENT_INTERRUPTED_CHILD_STATE_UNKNOWN",
                    "child_pid":child.pid,"elapsed_seconds":time.monotonic()-start})
            raise

if __name__=="__main__": main()
