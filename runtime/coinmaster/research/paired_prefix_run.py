"""Bounded native research launcher. Root GO + one physical ledger required.

Import and prepare are engine-free. A claimed attempt is durable before source,
config, data, engine import or export can fail. Failed attempts are never reused.
"""
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
import argparse
import fcntl
import hashlib
import json
import os
import tempfile
import uuid

PROTOCOL_SHA="9de474042ab5c2757b043a0272f4a5869f4c4d2c968d6adb7aebbdf28efc19a1"
LOT_PROTOCOL_SHA="0e7bca174c0268f0dc2769a4918d7017d88e98f84115ee52ad22dd59c97ca7be"
LOT_APPROVAL_SHA="8da53003133e9d9781545975a37d929239834bbbbe141b3db84c6fd21d63ab8f"
LOT_BASE_SOURCE="3323f08c57ede411058f93d96acee88928c93481"
START_MS=1725148800000
END_MS=1736899200000
SLOTS={1:"MATCHED_OFF_CONTROL",2:"B2_PAIRED",3:"B2_F0_PAIRED",4:"ONE_CONCRETE_CORRECTION_OR_RESERVE",5:"VALID_OFF_AFTER_NONTRADING_BOUNDARY_REPAIR",6:"LOT_CORRIDOR_MATCHED_OFF",7:"LOT_CORRIDOR_B2",8:"LOT_CORRIDOR_COMBINED"}
VARIANTS={"OFF":None,"B2":"B2","B2_F0":"B2_F0"}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()


@contextmanager
def ledger_transaction(path):
    path=Path(path)
    with path.with_suffix(path.suffix+".lock").open("a+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        data=json.loads(path.read_text())
        yield data
        with tempfile.NamedTemporaryFile("w",dir=path.parent,prefix=".native-ledger-",delete=False) as f:
            json.dump(data,f,indent=2);f.write("\n");f.flush();os.fsync(f.fileno());temporary=f.name
        os.replace(temporary,path)


def effective_prefix_cap(freeze,ledger):
    """Default4; ceiling5 is inert without separately pinned owner amendment."""
    frozen=freeze.get("physical_prefix_max",4);recorded=ledger["physical_prefix_max"]
    if any(type(value) is not int or value not in (4,5,7) for value in (frozen,recorded)):
        raise ValueError("INVALID_PREFIX_CAP_OR_CEILING")
    cap=min(frozen,recorded)
    if cap==7:
        evidence=freeze.get("owner_budget_amendment",{})
        if evidence.get("sha256")!=LOT_APPROVAL_SHA or not evidence.get("path") or sha(evidence["path"])!=LOT_APPROVAL_SHA:
            raise ValueError("LOT_CORRIDOR_OWNER_APPROVAL_PIN_REQUIRED")
        approval=json.loads(Path(evidence["path"]).read_text())
        if (approval.get("status")!="APPROVED_BY_OWNER" or approval.get("authorized_native_prefix_max")!=7
            or approval.get("authorized_full_max")!=0 or approval.get("protocol_sha256")!=LOT_PROTOCOL_SHA
            or approval.get("base_source_commit")!=LOT_BASE_SOURCE or not approval.get("no_reserve")
            or freeze.get("protocol_sha256")!=LOT_PROTOCOL_SHA or ledger.get("protocol_sha256")!=LOT_PROTOCOL_SHA):
            raise ValueError("LOT_CORRIDOR_APPROVED_SCOPE_REQUIRED")
    if cap==5:
        evidence=freeze.get("owner_budget_amendment")
        if not isinstance(evidence,dict) or not evidence.get("path") or not evidence.get("sha256"):
            raise ValueError("EXPLICIT_OWNER_BUDGET_AMENDMENT_REQUIRED")
        path=Path(evidence["path"])
        if sha(path)!=evidence["sha256"]:raise ValueError("OWNER_BUDGET_AMENDMENT_PIN_MISMATCH")
        approval=json.loads(path.read_text())
        if approval.get("status")!="APPROVED_BY_OWNER" or approval.get("authorized_native_prefix_max")!=5 or approval.get("authorized_full_max")!=0 or approval.get("protocol_sha256")!=PROTOCOL_SHA or not str(approval.get("owner_exact_response","")).strip():
            raise ValueError("EXPLICIT_OWNER_BUDGET_AMENDMENT_REQUIRED")
    return cap


def claim_attempt(path,freeze,variant,artifact_dir):
    if freeze.get("internal_go") is not True or freeze.get("independent_review")!="PASS" or freeze.get("launch_gates")!="PASS":
        raise ValueError("ROOT_INTERNAL_GO_AND_REVIEWED_LAUNCH_GATES_REQUIRED")
    if freeze.get("protocol_sha256") not in (PROTOCOL_SHA,LOT_PROTOCOL_SHA) or freeze.get("full_max")!=0:
        raise ValueError("FROZEN_APPROVED_PREFIX_SCOPE_REQUIRED")
    if variant not in VARIANTS:raise ValueError("UNAPPROVED_VARIANT")
    with ledger_transaction(path) as ledger:
        if ledger["full_max"]!=0 or ledger["protocol_sha256"]!=freeze["protocol_sha256"]:
            raise ValueError("INVALID_CANONICAL_LEDGER")
        cap=effective_prefix_cap(freeze,ledger)
        if ledger["physical_started"]>=cap:raise ValueError("PHYSICAL_PREFIX_BUDGET_EXHAUSTED")
        if any(s["status"]=="STARTED" for s in ledger["slots"]):raise ValueError("NATIVE_PREFIX_OWNER_ALREADY_RUNNING")
        physical=ledger["physical_started"]+1
        number=int(freeze["logical_slot"])
        if number not in SLOTS:raise ValueError("INVALID_LOGICAL_SLOT")
        if number in (6,7,8):
            if cap!=7 or physical!={6:5,7:6,8:7}[number]:
                raise ValueError("LOT_CORRIDOR_PHYSICAL_SEQUENCE_REQUIRED")
        elif cap==7:
            raise ValueError("LOT_CORRIDOR_RETIRED_LOGICAL_SLOT")
        if number==5 and cap<5:raise ValueError("LOGICAL_SLOT5_REQUIRES_OWNER_AMENDMENT")
        slot=next((item for item in ledger["slots"] if item["slot"]==number),None)
        if slot is None:raise ValueError("LOGICAL_SLOT_NOT_AUTHORIZED_IN_LEDGER")
        required={1:"OFF",2:"B2",3:"B2_F0",5:"OFF",6:"OFF",7:"B2",8:"B2_F0"}.get(number)
        if required is not None and variant!=required:raise ValueError("FROZEN_SLOT_ORDER_REQUIRED")
        if number==4 and not freeze.get("concrete_correction_reserve_reason"):
            raise ValueError("RESERVE_REQUIRES_ONE_CONCRETE_CORRECTION_REASON")
        if number==5 and not freeze.get("non_trading_repair_reason"):
            raise ValueError("EXTRA_OFF_REQUIRES_REVIEWED_NONTRADING_REPAIR_REASON")
        if slot["status"]!="NOT_STARTED":raise ValueError("LOGICAL_SLOT_CANNOT_BE_REUSED")
        identity=freeze["monetary_source_identity"]
        if variant!="OFF":
            matched=any(a["variant"]=="OFF" and a["status"]=="COMPLETED" and a.get("monetary_source_identity")==identity for a in ledger.get("attempts",[]))
            if not matched:raise ValueError("MATCHED_COMPLETED_OFF_MONETARY_SOURCE_REQUIRED")
        if variant=="B2_F0":
            matched_b2=any(a["variant"]=="B2" and a["status"]=="COMPLETED" and a.get("monetary_source_identity")==identity for a in ledger.get("attempts",[]))
            if not matched_b2:raise ValueError("MATCHED_B2_ATTRIBUTION_SOURCE_REQUIRED")
        attempt=str(uuid.uuid4())
        slot.update(status="STARTED",attempt_id=attempt,variant=variant,started_utc=utc(),
            source_commit=freeze["source_commit"],monetary_source_identity=identity,physical_index=physical,artifact_dir=str(artifact_dir))
        ledger["physical_started"]=physical;ledger["status"]="PREFIX_ATTEMPT_RUNNING"
        ledger.setdefault("attempts",[]).append(dict(logical_slot=number,physical_index=physical,attempt_id=attempt,variant=variant,
            started_utc=slot["started_utc"],source_commit=freeze["source_commit"],monetary_source_identity=identity,status="STARTED"))
        return attempt


def finish_attempt(path,attempt,status,detail):
    with ledger_transaction(path) as ledger:
        entry=next(a for a in ledger["attempts"] if a["attempt_id"]==attempt)
        slot=next(s for s in ledger["slots"] if s.get("attempt_id")==attempt)
        entry.update(status=status,finished_utc=utc(),detail=detail)
        slot.update(status=status,finished_utc=entry["finished_utc"],detail=detail)
        if status=="COMPLETED":ledger["physical_completed"]+=1
        ledger["status"]="PREFIX_CHECKPOINT_REVIEW_REQUIRED"


def verify_freeze(freeze):
    root=Path(__file__).resolve().parents[3]
    if Path(freeze["source_root"]).resolve()!=root:raise ValueError("IMMUTABLE_SOURCE_ROOT_MISMATCH")
    for relative,digest in freeze["source_files"].items():
        if sha(root/relative)!=digest:raise ValueError("SOURCE_PIN_MISMATCH:"+relative)
    for item in freeze["input_files"]:
        if sha(item["path"])!=item["sha256"]:raise ValueError("INPUT_PIN_MISMATCH:"+Path(item["path"]).name)
    if sha(freeze["expected_r3_config"])!=freeze["expected_r3_config_sha256"]:
        raise ValueError("EXACT_R3_CONFIG_PIN_MISMATCH")
    if any(any(x in key.upper() for x in ("SECRET","TOKEN","API_KEY","PRIVATE_KEY","WALLET")) for key in os.environ):
        raise ValueError("RESEARCH_ENVIRONMENT_CONTAINS_CREDENTIAL_NAME")
    if freeze["calendar"]!="[2024-09-01T00:00:00Z,2025-01-15T00:00:00Z)" or str(freeze["seed"])!="10000":
        raise ValueError("FIXED_PREFIX_CALENDAR_AND_SEED_REQUIRED")


BOOL_REPORT_FLAGS = (
    "research_v0_execution_repairs", "research_v0_zero_tp_netting",
    "research_v0_deferred_selective_zero_tp", "research_v0_selective_lifecycle_repairs",
    "research_btc_split50", "research_btc_split_planref_v1", "research_btc_split_tp_ioc",
    "research_btc_real_u", "research_sol_off",
)
DIRECTION_DESCRIPTOR = {"freeze":"GENUINE_EPISODE_CREATION", "long":"5.5", "short":"7.875"}


def build_native_kwargs(config, data_root, artifact_dir, variant, feed, *, registered_control=None):
    """Decode the frozen report schema to the existing native CALL schema.

    A report descriptor is not a truthy flag. Every bool is checked strictly;
    only the exact archived direction descriptor maps to the old R3 True flag.
    No engine is constructed here; constructors validate native input objects.
    """
    from decimal import Decimal as D
    from inspect import signature
    from coinmaster.domain.wave_overlay import Candidate
    from coinmaster.research.native_baseline import run_native_diagnostic,ExecutionPolicy,FixedBaseFeePolicy
    if variant not in VARIANTS:raise ValueError("UNAPPROVED_VARIANT")
    if registered_control is not None:
        from coinmaster.research.registered_control import validate_config
        validate_config(config, registered_control)
    flags={}
    for key in BOOL_REPORT_FLAGS:
        value=config[key]
        if type(value) is not bool:raise ValueError("R3_REPORT_FLAG_NOT_BOOL:"+key)
        flags[key]=value
    if config["research_btc_direction_sizing"] != DIRECTION_DESCRIPTOR:
        raise ValueError("EXACT_R3_DIRECTION_DESCRIPTOR_REQUIRED")
    expected_q = "LEGACY_Q_CONTROL" if registered_control in ("R2", "R2_A0_V1") else "CLEAN_Q"
    if config["research_btc_q_mode"]!=expected_q or config["research_btc_split_discount"]!="0.005" or not flags["research_btc_real_u"]:
        raise ValueError("EXACT_APPROVED_R3_SOURCE_CONFIG_REQUIRED")
    wait=config["next_band_research"]["wait_4h"]
    if type(wait) is not bool:raise ValueError("R3_REPORT_FLAG_NOT_BOOL:wait_4h")
    kwargs=dict(data_root=Path(data_root),include_funding=True,
        candidate=Candidate(**config["candidate"]),execution_policy=ExecutionPolicy(**config["execution_policy"]),
        fixed_base_fee_policy=FixedBaseFeePolicy(**config["fixed_base_fee_policy"]),
        trading_start_ms=START_MS,trading_end_ms=END_MS,initial_active_seed=D(10000),
        artifact_dir=Path(artifact_dir),artifact_label="paired-prefix-"+variant,
        **flags,observe_minute_risk=True,research_btc_direction_sizing=True,
        research_btc_split_discount=config["research_btc_split_discount"],
        research_btc_q_mode=config["research_btc_q_mode"],research_wait_4h=wait,
        research_regime_reentry_band=config["hedge_band_research"]["regime_reentry_band"],
        research_paired_policy=True,research_paired_prefix=VARIANTS[variant],research_paired_signal_rows=feed)
    if registered_control is not None:
        kwargs["research_registered_control"] = registered_control
    # Bind the COMPLETE call against the actual installed source entrypoint,
    # including every omitted default; no partial hand-maintained signature.
    actual=signature(run_native_diagnostic)
    bound=actual.bind(**kwargs);bound.apply_defaults()
    scalar_types={"bool":bool,"int":int,"str":str,"Path":Path,"Decimal":D,"tuple":tuple,
        "ExecutionPolicy":ExecutionPolicy,"FixedBaseFeePolicy":FixedBaseFeePolicy}
    for key,parameter in actual.parameters.items():
        annotation=parameter.annotation
        if annotation is parameter.empty:continue  # candidate is validated by its actual constructor.
        name=annotation if isinstance(annotation,str) else annotation.__name__
        optional=name.endswith(" | None")
        if optional:name=name[:-7]
        value=bound.arguments[key]
        if value is None and optional:continue
        expected=scalar_types[name]
        valid=type(value) is expected if expected in (bool,int,str,tuple) else isinstance(value,expected)
        if not valid:raise ValueError("NATIVE_CALL_ARGUMENT_TYPE:"+key+":"+name)
    if kwargs["fixed_base_fee_policy"].hash!=config["fee_policy_hash"]:
        raise ValueError("EXACT_R3_NATIVE_FEE_POLICY_HASH_REQUIRED")
    return kwargs


def prepare_native_call(freeze, variant, artifact_dir):
    from coinmaster.research.paired_signal_feed import load_paired_signal_feed
    config=json.loads(Path(freeze["expected_r3_config"]).read_text())
    feed=load_paired_signal_feed(Path(freeze["signal_feed"]),freeze["signal_feed_sha256"],START_MS*1000000,END_MS*1000000)
    return build_native_kwargs(config,freeze["data_root"],artifact_dir,variant,feed)


def execute_prepared_call(kwargs, native_runner=None):
    """Single dispatch seam, captured by engine-free contract regression."""
    if native_runner is None:
        from coinmaster.research.native_baseline import run_native_diagnostic
        native_runner=run_native_diagnostic
    return native_runner(**kwargs)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--freeze",type=Path,required=True)
    parser.add_argument("--ledger",type=Path,required=True)
    parser.add_argument("--variant",choices=tuple(VARIANTS),required=True)
    parser.add_argument("--artifact-dir",type=Path,required=True)
    parser.add_argument("--launch",action="store_true")
    args=parser.parse_args();freeze=json.loads(args.freeze.read_text())
    if not args.launch:
        verify_freeze(freeze)
        prepared=prepare_native_call(freeze,args.variant,args.artifact_dir)
        print(json.dumps(dict(status="PREPARED_COMPLETE_NATIVE_CALL_VALIDATED_ENGINE_NOT_CONSTRUCTED",variant=args.variant,
            validated_kwargs=sorted(prepared),direction_sizing_native_bool=prepared["research_btc_direction_sizing"],
            calendar=freeze["calendar"],seed="10000",source_commit=freeze["source_commit"],
            native_launch_requires="--launch AND durable physical ledger claim AND root internal GO")))
        return
    attempt=claim_attempt(args.ledger,freeze,args.variant,args.artifact_dir)
    try:
        verify_freeze(freeze)
        if args.artifact_dir.exists():raise ValueError("ATTEMPT_ARTIFACT_DIR_MUST_BE_NEW")
        args.artifact_dir.mkdir(parents=True)
        import nautilus_trader
        if nautilus_trader.__version__!="1.231.0":raise ValueError("PINNED_NATIVE_ENGINE_VERSION_REQUIRED")
        from coinmaster.research.native_baseline import save_diagnostic_report
        from coinmaster.research.native_audit import audit_json_default
        prepared=prepare_native_call(freeze,args.variant,args.artifact_dir)
        result=execute_prepared_call(prepared)
        result=json.loads(json.dumps(result,default=audit_json_default))
        result["physical_prefix_attempt"]={"attempt_id":attempt,"variant":args.variant,"ledger":str(args.ledger),"source_commit":freeze["source_commit"]}
        path=save_diagnostic_report(Path(freeze["data_root"]),result,"paired-prefix-"+args.variant,args.artifact_dir)
        finish_attempt(args.ledger,attempt,"COMPLETED",dict(report=str(path),report_sha256=sha(path),
            coherent_observer=result["coherent_native_observer"]["status"],paired_failures=result["paired_prefix_audit"]["failures"]))
        print(json.dumps(dict(status="PHYSICAL_PREFIX_COMPLETED_REVIEW_REQUIRED",attempt_id=attempt,report=str(path))))
    except BaseException as error:
        finish_attempt(args.ledger,attempt,"FAILED",dict(error_type=type(error).__name__,error=str(error)))
        raise


if __name__=="__main__":main()
