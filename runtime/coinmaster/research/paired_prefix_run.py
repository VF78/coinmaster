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
START_MS=1725148800000
END_MS=1736899200000
SLOTS={1:"MATCHED_OFF_CONTROL",2:"B2_PAIRED",3:"B2_F0_PAIRED",4:"ONE_CONCRETE_CORRECTION_OR_RESERVE"}
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


def claim_attempt(path,freeze,variant,artifact_dir):
    if freeze.get("internal_go") is not True or freeze.get("independent_review")!="PASS" or freeze.get("launch_gates")!="PASS":
        raise ValueError("ROOT_INTERNAL_GO_AND_REVIEWED_LAUNCH_GATES_REQUIRED")
    if freeze.get("protocol_sha256")!=PROTOCOL_SHA or freeze.get("full_max")!=0:
        raise ValueError("FROZEN_APPROVED_PREFIX_SCOPE_REQUIRED")
    if variant not in VARIANTS:raise ValueError("UNAPPROVED_VARIANT")
    with ledger_transaction(path) as ledger:
        if ledger["physical_prefix_max"]!=4 or ledger["full_max"]!=0 or ledger["protocol_sha256"]!=PROTOCOL_SHA:
            raise ValueError("INVALID_CANONICAL_LEDGER")
        if ledger["physical_started"]>=4:raise ValueError("PHYSICAL_PREFIX_BUDGET_EXHAUSTED")
        if any(s["status"]=="STARTED" for s in ledger["slots"]):raise ValueError("NATIVE_PREFIX_OWNER_ALREADY_RUNNING")
        physical=ledger["physical_started"]+1
        number=int(freeze["logical_slot"])
        if number not in SLOTS:raise ValueError("INVALID_LOGICAL_SLOT")
        slot=ledger["slots"][number-1]
        required={1:"OFF",2:"B2",3:"B2_F0"}.get(number)
        if required is not None and variant!=required:raise ValueError("FROZEN_SLOT_ORDER_REQUIRED")
        if number==4 and not freeze.get("concrete_correction_reserve_reason"):
            raise ValueError("RESERVE_REQUIRES_ONE_CONCRETE_CORRECTION_REASON")
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
        print(json.dumps(dict(status="PREPARED_ENGINE_NOT_IMPORTED",variant=args.variant,
            calendar=freeze["calendar"],seed="10000",source_commit=freeze["source_commit"],
            native_launch_requires="--launch AND durable physical ledger claim AND root internal GO")))
        return
    attempt=claim_attempt(args.ledger,freeze,args.variant,args.artifact_dir)
    try:
        verify_freeze(freeze)
        if args.artifact_dir.exists():raise ValueError("ATTEMPT_ARTIFACT_DIR_MUST_BE_NEW")
        args.artifact_dir.mkdir(parents=True)
        from decimal import Decimal as D
        import nautilus_trader
        if nautilus_trader.__version__!="1.231.0":raise ValueError("PINNED_NATIVE_ENGINE_VERSION_REQUIRED")
        from coinmaster.domain.wave_overlay import Candidate
        from coinmaster.research.paired_signal_feed import load_paired_signal_feed
        from coinmaster.research.native_baseline import run_native_diagnostic,ExecutionPolicy,FixedBaseFeePolicy,save_diagnostic_report
        from coinmaster.research.native_audit import audit_json_default
        c=json.loads(Path(freeze["expected_r3_config"]).read_text())
        if c["research_btc_q_mode"]!="CLEAN_Q" or c["research_btc_split_discount"]!="0.005" or not c["research_btc_real_u"]:
            raise ValueError("EXACT_APPROVED_R3_SOURCE_CONFIG_REQUIRED")
        feed=load_paired_signal_feed(Path(freeze["signal_feed"]),freeze["signal_feed_sha256"],START_MS*1000000,END_MS*1000000)
        result=run_native_diagnostic(Path(freeze["data_root"]),include_funding=True,
            candidate=Candidate(**c["candidate"]),execution_policy=ExecutionPolicy(**c["execution_policy"]),
            fixed_base_fee_policy=FixedBaseFeePolicy(**c["fixed_base_fee_policy"]),
            trading_start_ms=START_MS,trading_end_ms=END_MS,initial_active_seed=D(10000),
            artifact_dir=args.artifact_dir,artifact_label="paired-prefix-"+args.variant,
            research_v0_execution_repairs=c["research_v0_execution_repairs"],research_v0_zero_tp_netting=c["research_v0_zero_tp_netting"],
            research_v0_deferred_selective_zero_tp=c["research_v0_deferred_selective_zero_tp"],
            research_v0_selective_lifecycle_repairs=c["research_v0_selective_lifecycle_repairs"],
            observe_minute_risk=True,research_btc_direction_sizing=c["research_btc_direction_sizing"],
            research_btc_split50=c["research_btc_split50"],research_btc_split_planref_v1=c["research_btc_split_planref_v1"],
            research_btc_split_tp_ioc=c["research_btc_split_tp_ioc"],research_btc_split_discount=c["research_btc_split_discount"],
            research_btc_real_u=c["research_btc_real_u"],research_btc_q_mode=c["research_btc_q_mode"],
            research_sol_off=c["research_sol_off"],research_wait_4h=c["next_band_research"]["wait_4h"],
            research_regime_reentry_band=c["hedge_band_research"]["regime_reentry_band"],
            research_paired_policy=True,research_paired_prefix=VARIANTS[args.variant],research_paired_signal_rows=feed)
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
