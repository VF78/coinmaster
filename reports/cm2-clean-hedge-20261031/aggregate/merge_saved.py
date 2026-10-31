"""Hash-bound saved-report merge only; stdlib, no engines or PnL calculations."""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

MODEL = "CM2_EXACT_HOST_BINARY_SAVED_MERGE_V1"
PARAMS = ("trend_hours", "load", "stop_atr", "core", "hedge_trigger", "hedge_fraction", "buffer")
PIN_KEYS = ("source_commit", "python_sha256", "native_engine_sha256",
            "native_binary_hashes", "source_hashes", "data_hash", "execution_policy_hash",
            "seed", "run_interval", "fees", "currency")
STATUSES = ("physical_status", "financial_status", "structural_status", "numeric_goal_status",
            "robustness_status", "persistence_status", "model_status")
HEX = re.compile(r"[0-9a-f]{64}")

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def bound(ref):
    if not HEX.fullmatch(str(ref.get("sha256", ""))) or sha(ref["path"]) != ref["sha256"]:
        raise ValueError("INPUT_HASH_MISMATCH")
    return json.loads(Path(ref["path"]).read_text())

def finite(value):
    try:
        n = Decimal(str(value))
        return str(n) if n.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None

def present(value):
    return value is not None and value != "" and value != {} and value != []

def pin_errors(p):
    errors = ["MISSING_PIN:" + k for k in PIN_KEYS if not present(p.get(k))]
    for k in ("python_sha256", "native_engine_sha256", "data_hash", "execution_policy_hash"):
        if present(p.get(k)) and not HEX.fullmatch(str(p[k])):
            errors.append("INVALID_HASH_PIN:" + k)
    if present(p.get("source_commit")) and not re.fullmatch(r"[0-9a-f]{40}", str(p["source_commit"])):
        errors.append("INVALID_SOURCE_COMMIT")
    for k in ("source_hashes", "native_binary_hashes"):
        if present(p.get(k)) and (not isinstance(p[k], dict) or
                not all(HEX.fullmatch(str(v)) for v in p[k].values())):
            errors.append("INVALID_HASH_MAP:" + k)
    if finite(p.get("seed")) is None or Decimal(finite(p.get("seed")) or "0") <= 0:
        errors.append("UNKNOWN_POSITIVE_SEED")
    interval = p.get("run_interval", {})
    if not isinstance(interval, dict) or not all(present(interval.get(k)) for k in ("start", "end_exclusive")):
        errors.append("UNKNOWN_INTERVAL")
    return errors

def row(entry):
    s = bound(entry["summary"])
    request = bound(entry["request"])
    comparison = bound(entry["comparison"])
    provenance = s.get("provenance", {})
    if provenance.get("request_sha256") != entry["request"]["sha256"]:
        raise ValueError("SUMMARY_REQUEST_HASH_MISMATCH")
    matches = [r for r in comparison.get("cases", [])
               if (r.get("case"), r.get("run_id")) == (s.get("case"), s.get("run_id"))]
    if len(matches) != 1:
        raise ValueError("COMPARISON_MEMBERSHIP_NOT_UNIQUE")
    c = matches[0]
    for key in ("TOTAL", "financial_status", "report_sha256", "comparison_group_hash"):
        expected = provenance.get("report_sha256") if key == "report_sha256" else s.get(key)
        if c.get(key) != expected:
            raise ValueError("COMPARISON_SUMMARY_MISMATCH:" + key)
    p = entry.get("pins", {})
    errors = pin_errors(p)
    for kind in ("settled", "coherent"):
        member_dd = finite(c.get(kind + "_DD_including_final_close"))
        summary_dd = finite(s.get("with_final_close_DD_percent", {}).get(kind))
        if member_dd is None or summary_dd is None or Decimal(member_dd) != Decimal(summary_dd):
            errors.append("COMPARISON_SUMMARY_DD_UNPROVEN:" + kind)
    for key, expected in (("source_hashes", provenance.get("source_hashes")),
                          ("data_hash", provenance.get("data_hash")),
                          ("execution_policy_hash", provenance.get("policy_hash")),
                          ("seed", s.get("native_seed"))):
        if not present(expected) or p.get(key) != expected:
            errors.append("SUMMARY_PIN_UNPROVEN:" + key)
    if request.get("source_commit") is not None and request["source_commit"] != p.get("source_commit"):
        errors.append("REQUEST_SOURCE_COMMIT_UNPROVEN")
    if not present(s.get("comparison_group_hash")):
        errors.append("ANALYZER_GROUP_MISSING")
    policy = request.get("policy", {})
    params = {k: finite(policy.get(k)) for k in PARAMS}
    if any(v is None for v in params.values()):
        errors.append("ECONOMIC_PARAMETERS_UNKNOWN")
    raw = provenance.get("original_report_sha256", provenance.get("report_sha256"))
    if not HEX.fullmatch(str(raw)):
        errors.append("RAW_REPORT_HASH_UNKNOWN")
    metrics = {"TOTAL": finite(s.get("TOTAL")), "liquidations": finite(s.get("liquidations")),
               "runtime_seconds": finite(entry.get("runtime_seconds")),
               "peak_rss_bytes": finite(entry.get("peak_rss_bytes"))}
    for basis in ("interval", "with_final_close"):
        for kind in ("settled", "coherent"):
            metrics[basis + "_" + kind + "_DD_percent"] = finite(
                s.get(basis + "_DD_percent", {}).get(kind))
    strict = [metrics["with_final_close_" + k + "_DD_percent"] for k in ("settled", "coherent")]
    if any(v is None for v in [metrics["TOTAL"], *strict]):
        errors.append("NUMERIC_OBJECTIVE_UNKNOWN")
    if any(v is not None and Decimal(v) < 0 for v in strict):
        errors.append("NEGATIVE_DRAWDOWN_INVALID")
    # Include original analyzer group to retain its interval/fee/currency restrictions.
    group_pins = {**p, "analyzer_comparison_group_hash": s.get("comparison_group_hash"),
                  "measurement_pins": {k: provenance.get(k) for k in
                      ("algorithm", "analyzer_sha256", "native_dd_source_sha256",
                       "native_observer_source_sha256", "qualification_model_id")}}
    group = hashlib.sha256(json.dumps(group_pins, sort_keys=True).encode()).hexdigest() if not errors else None
    return {"case": s.get("case"), "run_id": s.get("run_id"), "host": entry.get("host"),
            **{k: s.get(k, "UNKNOWN") for k in STATUSES}, **metrics,
            "economic_parameters": params, "mode": request.get("policy", {}).get("mode"),
            "input_hashes": {k: entry[k]["sha256"] for k in ("summary", "comparison", "request")},
            "raw_report_sha256": raw, "pins": p,
            "qualification_provenance": {k: provenance.get(k) for k in
                ("report_sha256", "original_report_sha256", "derived_receipt_sha256", "qualification_model_id")}, "comparison_group_hash": group,
            "unknown_reasons": errors, "pareto_native_numeric": None,
            "scope": "NOT_WINNER_NUMERIC_ONLY_NO_IMPLEMENTATION_OR_ROBUSTNESS_CLAIM"}

def merge(manifest):
    if manifest.get("schema_version") != 1:
        raise ValueError("SCHEMA_VERSION_1_REQUIRED")
    rows = [row(e) for e in manifest.get("cases", [])]
    for key in ("case", "run_id", "raw_report_sha256"):
        counts = Counter(r[key] for r in rows if present(r[key]))
        for r in rows:
            if not present(r[key]) or counts[r[key]] > 1:
                r["unknown_reasons"].append("MISSING_OR_DUPLICATE:" + key)
                r["comparison_group_hash"] = None
    usable = [r for r in rows if not r["unknown_reasons"] and r["financial_status"] == "PASS"]
    def objective(r):
        return Decimal(r["TOTAL"]), max(Decimal(r["with_final_close_" + k + "_DD_percent"])
                                       for k in ("settled", "coherent"))
    for r in usable:
        total, dd = objective(r)
        r["pareto_native_numeric"] = not any(
            x["comparison_group_hash"] == r["comparison_group_hash"] and
            objective(x)[0] >= total and objective(x)[1] <= dd and objective(x) != (total, dd)
            for x in usable)
    return {"model_id": MODEL, "scope": "NOT_WINNER_EXACT_SOURCE_BINARY_PIN_GROUPS_ONLY",
            "new_engine_constructions": 0, "cases": rows,
            "input_manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    packet = merge(json.loads(args.manifest.read_text()))
    packet["input_manifest_file_sha256"] = sha(args.manifest)
    packet["helper_sha256"] = sha(__file__)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "COMPARISON.json").write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    fields = list(packet["cases"][0]) if packet["cases"] else ["case"]
    for name, rows in (("COMPARISON.csv", packet["cases"]),
                       ("PARETO.csv", [r for r in packet["cases"] if r["pareto_native_numeric"] is True])):
        with (args.out / name).open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v
                              for k, v in r.items()} for r in rows)

if __name__ == "__main__":
    main()
