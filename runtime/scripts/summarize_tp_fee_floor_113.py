"""Summarize the bounded #113 native reports without a second PnL model."""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "var" / "data" / "runs"
RUNS = ROOT / "tp-fee-floor-113"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_csv_sha256(path: Path) -> str:
    rows = list(csv.DictReader(path.open()))
    for row in rows:
        row.pop("init_id", None)
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def funding_rows_sha256(path: Path) -> str:
    with sqlite3.connect(path) as database:
        rows = database.execute("SELECT * FROM funding_events ORDER BY ts_event, event_id").fetchall()
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def read_run(name: str, report_path: Path, fills_path: Path) -> dict:
    report = json.loads(report_path.read_text())
    audit = report["fill_audit"]
    native_rows = list(csv.DictReader(fills_path.open()))
    by_entry_time = defaultdict(list)
    for row in native_rows:
        if "BTC" in row["instrument_id"] and row["is_reduce_only"] == "False":
            ns = int(datetime.fromisoformat(row["ts_last"]).timestamp() * 1_000_000_000)
            by_entry_time[ns].append(row)
    entry_qty = entry_notional = entry_fee = Decimal("0")
    episode_side = None
    prior_action = None
    tp_nonpositive = tp_negative = tp_zero = 0
    tp_net_min = None
    tp_count = 0
    for row in audit:
        action = row["action"]
        if action == "BTC_ENTRY":
            matches = by_entry_time[int(row["fill_ns"])]
            if len(matches) != 1 or matches[0]["side"] not in ("BUY", "SELL"):
                raise ValueError("ENTRY_NATIVE_SIDE_AMBIGUOUS")
            side = 1 if matches[0]["side"] == "BUY" else -1
            if prior_action != "BTC_ENTRY":
                entry_qty = entry_notional = entry_fee = Decimal("0")
                episode_side = side
            elif side != episode_side:
                raise ValueError("PARTIAL_ENTRY_SIDE_MISMATCH")
            entry_qty += Decimal(row["qty"])
            entry_notional += Decimal(row["notional"])
            entry_fee += Decimal(row["commission"])
        elif action == "BTC_REDUCE":
            if episode_side is None or entry_qty <= 0:
                raise ValueError("TP_WITHOUT_NATIVE_ENTRY")
            qty, px = Decimal(row["qty"]), Decimal(row["px"])
            p0 = entry_notional / entry_qty
            # Diagnostic trading-fee classification only; native cash remains authoritative.
            net = episode_side * qty * (px - p0) - entry_fee * qty / entry_qty - Decimal(row["commission"])
            tp_count += 1
            tp_nonpositive += net <= 0
            tp_negative += net < 0
            tp_zero += net == 0
            tp_net_min = net if tp_net_min is None else min(tp_net_min, net)
        prior_action = action
    fee = report["fee_attribution"]
    turnover = sum((Decimal(fee[x]["notional"]) for x in ("maker", "taker", "unknown")), Decimal("0"))
    if turnover != sum((Decimal(row["notional"]) for row in audit), Decimal("0")):
        raise ValueError("NATIVE_TURNOVER_RECONCILIATION_MISMATCH")
    sol_add = [(row["level"], row["fill_ns"]) for row in audit if row["action"] == "SOL_ADD"]
    return {
        "version": name, "status": report["status"], "total": report["terminal_total"],
        "roi_percent": str(Decimal(report["summary"]["roi"]) * 100),
        "fees": report["native_fees"], "turnover": str(turnover),
        "btc_tp_fills": tp_count, "sol_fills": sum("SOL" in row["instrument"] for row in audit),
        "sol_add_fills": len(sol_add), "sol_add_level_counts": dict(Counter(level for level, _ in sol_add)),
        "sol_add_events": sol_add, "liquidations": report["liquidation_count"],
        "tp_nonpositive_after_trading_fees": tp_nonpositive,
        "tp_negative_after_trading_fees": tp_negative,
        "tp_zero_after_trading_fees": tp_zero,
        "tp_min_trading_fee_net": str(tp_net_min),
        "funding_count": report["funding"]["count"],
        "funding_signed_amount": report["funding"]["signed_amount"],
        "data_hash": report["data_hash"], "code_hash": report["code_hash"],
        "config_hash": report["config_hash"], "policy_hash": report["policy_hash"],
        "report_path": str(report_path), "report_sha256": sha256(report_path),
        "fills_path": str(fills_path), "fills_sha256": sha256(fills_path),
    }


def main() -> None:
    rows = [
        read_run("G4_archive", ROOT / "g4-archive-reference.json", ROOT / "g4-archive-reference-fills.csv"),
        read_run("V0", RUNS / "v0/v0.json", RUNS / "v0/v0-fills.csv"),
        read_run("V1", RUNS / "v1/v1.json", RUNS / "v1/v1-fills.csv"),
    ]
    winner = "v1" if Decimal(rows[2]["total"]) > Decimal(rows[1]["total"]) else "v0"
    repeat = read_run("repeat_" + winner, RUNS / ("repeat_" + winner) / ("repeat_" + winner + ".json"), RUNS / ("repeat_" + winner) / ("repeat_" + winner + "-fills.csv"))
    selected = rows[2] if winner == "v1" else rows[1]
    match_fields = ("total", "fees", "turnover", "btc_tp_fills", "sol_fills", "liquidations", "funding_count", "tp_nonpositive_after_trading_fees")
    parity = all(selected[key] == repeat[key] for key in match_fields)
    if not parity:
        raise ValueError("WINNER_NATIVE_REPEAT_MISMATCH")
    winner_root = RUNS / winner
    repeat_root = RUNS / ("repeat_" + winner)
    execution_parity = {}
    for kind in ("fills", "orders"):
        first = normalized_csv_sha256(winner_root / f"{winner}-{kind}.csv")
        again = normalized_csv_sha256(repeat_root / f"repeat_{winner}-{kind}.csv")
        if first != again:
            raise ValueError(f"WINNER_NATIVE_REPEAT_{kind.upper()}_MISMATCH")
        execution_parity[kind + "_normalized_sha256"] = first
    first_funding = funding_rows_sha256(winner_root / f"{winner}-funding.sqlite")
    repeat_funding = funding_rows_sha256(repeat_root / f"repeat_{winner}-funding.sqlite")
    if first_funding != repeat_funding:
        raise ValueError("WINNER_NATIVE_REPEAT_FUNDING_ROWS_MISMATCH")
    execution_parity["funding_rows_sha256"] = first_funding
    first_report = json.loads((winner_root / f"{winner}.json").read_text())
    repeat_report = json.loads((repeat_root / f"repeat_{winner}.json").read_text())
    if first_report["fee_attribution"] != repeat_report["fee_attribution"]:
        raise ValueError("WINNER_NATIVE_REPEAT_FEE_SPLIT_MISMATCH")
    v0, v1, g4 = rows[1], rows[2], rows[0]
    counter_v0, counter_v1 = Counter(map(tuple, v0["sol_add_events"])), Counter(map(tuple, v1["sol_add_events"]))
    only_v0, only_v1 = counter_v0 - counter_v1, counter_v1 - counter_v0
    summary = {
        "status": "NOT_FAITHFUL_DIAGNOSTIC", "winner": winner, "winner_repeat_exact_economics": parity, "winner_repeat_native_artifacts": execution_parity,
        "rows": [{k:v for k,v in row.items() if k != "sol_add_events"} for row in rows],
        "repeat": {k:v for k,v in repeat.items() if k != "sol_add_events"},
        "deltas": {
            "delta_floor": str(Decimal(v1["total"]) - Decimal(v0["total"])),
            "delta_control_vs_archive": str(Decimal(v0["total"]) - Decimal(g4["total"])),
            "delta_final_vs_archive": str(Decimal(v1["total"]) - Decimal(g4["total"])),
            "funding_signed_delta": "UNKNOWN_NATIVE_JOURNAL_HAS_POST_TOTAL_ONLY",
        },
        "sol_add_changes": {
            "v0_only_fill_count": sum(only_v0.values()), "v1_only_fill_count": sum(only_v1.values()),
            "v0_only_first_ten": [list(item) for item in list(only_v0.elements())[:10]],
            "v1_only_first_ten": [list(item) for item in list(only_v1.elements())[:10]],
            "matching_fill_count": sum((counter_v0 & counter_v1).values()),
        },
        "limitations": ["Native 1-minute close proxy; no historical BBO/L2 or full liquidation evidence.", "Funding signed amount is not exported by the native journal and remains unknown.", "The archive uses older code and is not a clean fee-floor control."],
    }
    json_path = RUNS / "comparison.json"
    csv_path = RUNS / "comparison.csv"
    json_path.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n")
    with csv_path.open("w", newline="") as handle:
        columns = ("version", "total", "roi_percent", "fees", "turnover", "btc_tp_fills", "sol_fills", "sol_add_fills", "liquidations", "tp_nonpositive_after_trading_fees", "funding_count")
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator='\n')
        writer.writeheader()
        writer.writerows({key: row[key] for key in columns} for row in rows)
    print(json.dumps({"winner": winner, "deltas": summary["deltas"], "json": str(json_path), "json_sha256": sha256(json_path), "csv": str(csv_path), "csv_sha256": sha256(csv_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
