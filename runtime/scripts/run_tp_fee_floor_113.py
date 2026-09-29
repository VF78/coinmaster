"""Run one isolated #113 G4 V0/V1 native diagnostic from verified archive config."""
from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal
from dataclasses import asdict
from pathlib import Path

from coinmaster.domain.wave_overlay import Candidate
from coinmaster.research.native_baseline import (
    ExecutionPolicy, FixedBaseFeePolicy, run_native_diagnostic, save_diagnostic_report,
)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"v0", "v1", "repeat_v0", "repeat_v1"}:
        raise SystemExit("usage: run_tp_fee_floor_113.py v0|v1|repeat_v0|repeat_v1")
    version = sys.argv[1]
    root = Path(__file__).resolve().parents[1] / "var" / "data"
    archive_path = root / "runs" / "g4-archive-reference.json"
    archive = json.loads(archive_path.read_text())
    manifest = json.loads((root / "bybit-1m" / "manifest.json").read_text())
    data_hash = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if data_hash != archive["data_hash"]:
        raise ValueError("G4_SOURCE_MANIFEST_HASH_MISMATCH")
    candidate = Candidate(**archive["config"]["candidate"])
    policy = ExecutionPolicy(**archive["policy"])
    fee_policy = FixedBaseFeePolicy(**archive["config"]["fixed_base_fee_policy"])
    if policy.hash != archive["policy_hash"] or fee_policy.hash != archive["config"]["fee_policy_hash"]:
        raise ValueError("G4_POLICY_HASH_MISMATCH")
    output = root / "runs" / "tp-fee-floor-113" / version
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("RUN_DIRECTORY_NOT_EMPTY")
    report = run_native_diagnostic(
        root, include_funding=True, candidate=candidate, execution_policy=policy,
        fixed_base_fee_policy=fee_policy, initial_active_seed=Decimal("10000"),
        artifact_dir=output, artifact_label=version,
        tp_fee_floor_v1=version.endswith("v1"),
    )
    saved = save_diagnostic_report(root, report, version, output)
    print(json.dumps({"version": version, "total": report["terminal_total"],
                      "fees": report["native_fees"], "fills": report["fills"],
                      "liquidations": report["liquidation_count"],
                      "report": str(saved),
                      "sha256": hashlib.sha256(saved.read_bytes()).hexdigest()}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
