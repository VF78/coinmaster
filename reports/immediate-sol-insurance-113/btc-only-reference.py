#!/usr/bin/env python3
"""One standalone native BTC reference; report-side adapter, not an optimizer."""
from pathlib import Path
from decimal import Decimal
import hashlib
import json
from coinmaster.domain.wave_overlay import Candidate
from coinmaster.research.native_baseline import run_native_diagnostic, save_diagnostic_report, ExecutionPolicy, FixedBaseFeePolicy
job=Path(__file__).resolve().parent
selected=json.loads((job/"winning-config.json").read_text())
config=selected["config"]
expected=dict(config["candidate"])
expected["sol_overlay_enabled"]=False
candidate=Candidate(**expected)
assert candidate.sol_overlay_enabled is False
artifact_dir=job/"result"
if artifact_dir.exists():
    raise ValueError("FRESH_BTC_ONLY_RESULT_DIRECTORY_REQUIRED")
artifact_dir.mkdir()
report=run_native_diagnostic(
    job/"source/runtime/var/data",include_funding=True,candidate=candidate,
    initial_active_seed=Decimal("10000"),
    execution_policy=ExecutionPolicy(**config["execution_policy"]),
    fixed_base_fee_policy=FixedBaseFeePolicy(**config["fixed_base_fee_policy"]),
    artifact_dir=artifact_dir,artifact_label="winner-btc-only",
    research_v0_execution_repairs=True,research_v0_zero_tp_netting=False,
    research_v0_deferred_selective_zero_tp=True,research_v0_selective_lifecycle_repairs=True,
    observe_minute_risk=True,research_btc_direction_sizing=True,
    research_btc_split50=True,research_btc_split_planref_v1=True,
    research_btc_split_tp_ioc=True,research_btc_split_discount="0.0025",
)
report["btc_only_reference"]={"winning_artifact_sha256":selected["artifact_sha256"],"winning_source_commit":selected["source_commit"],"candidate_delta":{"sol_overlay_enabled":[True,False]},"component_fill_net_is_not_standalone_roi":True}
path=save_diagnostic_report(job/"source/runtime/var/data",report,"winner-btc-only",artifact_dir)
print(json.dumps({"completed_artifact":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}))
