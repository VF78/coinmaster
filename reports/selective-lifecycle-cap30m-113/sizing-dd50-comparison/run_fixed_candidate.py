"""Exactly one native API call for C/V1/V2; no optimizer or alternative engine."""
import hashlib,json,sys
from pathlib import Path
from dataclasses import replace
from decimal import Decimal
from datetime import datetime,timezone
from coinmaster.research import native_baseline as n
from coinmaster.domain.wave_overlay import Candidate
job=Path(sys.argv[1]);variant=sys.argv[2];multiple={"c":7.875,"v1":6.3,"v2":5.5}[variant]
data=job/"source/var/data";control_path=data/"runs/tp-fee-floor-113/v0/v0.json";out=job/"result"
assert not out.exists()
assert n.sha256_file(control_path)=="d6a29d6e0e9ac586b911f2802cbe89602a05d2c0d73026d08ed76082a8a934f9"
control=json.loads(control_path.read_text());config=control["config"]
assert control["status"]=="NOT_FAITHFUL_DIAGNOSTIC"
assert Decimal(control["summary"]["terminal_total"])==Decimal("3386491.65211338")
assert all(config.get(k)==v for k,v in n.BASELINE_CONFIG.items())
assert config["run_interval"]["initial_active_seed"]=="10000" and config["tp_fee_floor_v1"] is False
assert config["run_interval"]["start"]==datetime.fromtimestamp(n.TRADING_START_MS/1000,tz=timezone.utc).isoformat()
assert config["run_interval"]["end_exclusive"]==datetime.fromtimestamp(n.TRADING_END_MS/1000,tz=timezone.utc).isoformat()
assert config["execution_policy"]==control["policy"]
actual=hashlib.sha256(json.dumps(json.loads((data/"bybit-1m/manifest.json").read_text()),sort_keys=True,separators=(",",":")).encode()).hexdigest();assert actual==control["data_hash"]
candidate=replace(Candidate(**config["candidate"]),max_parent_notional=30_000_000.0,btc_notional_multiplier=multiple)
policy=n.ExecutionPolicy(**config["execution_policy"]);fees=n.FixedBaseFeePolicy(**config["fixed_base_fee_policy"]);assert fees.hash==config["fee_policy_hash"]
out.mkdir(parents=True,exist_ok=False);label="sizing-"+variant
report=n.run_native_diagnostic(data,include_funding=True,candidate=candidate,execution_policy=policy,fixed_base_fee_policy=fees,initial_active_seed=Decimal("10000"),artifact_dir=out,artifact_label=label,research_v0_execution_repairs=True,research_v0_zero_tp_netting=False,research_v0_deferred_selective_zero_tp=True,research_v0_selective_lifecycle_repairs=True,observe_minute_risk=True)
report["control_report_sha256"]=n.sha256_file(control_path);report["control_terminal_total"]=control["summary"]["terminal_total"]
artifact=n.save_diagnostic_report(data,report,label,out)
print(json.dumps({"status":"COMPLETED","artifact":str(artifact),"artifact_sha256":n.sha256_file(artifact)}))
