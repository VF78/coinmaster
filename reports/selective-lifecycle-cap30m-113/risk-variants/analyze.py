"""Bounded read-only aggregation of the two approved native risk comparisons."""
import csv
import gzip
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AUDIT = HERE.parent / "minute-risk-audit"
JOBS = Path("/var/lib/coinmaster-native-gui/data/runs/jobs")
VARIANTS = {"solcap6": "cm113-solcap6-20261010", "portfolio45": "cm113-portfolio45-20261010"}

def utc(ns):
    return datetime.fromtimestamp(int(ns) / 1_000_000_000, timezone.utc).isoformat() if ns is not None else None

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def load(path):
    return json.loads(Path(path).read_text())

def endpoint(point):
    return {**point, "utc": utc(point["timestamp_ns"])} if point else None

def curve_summary(curve):
    return {**curve, "minimum": endpoint(curve["minimum"]), "top3_distinct_excursions": [
        {**episode, "peak": endpoint(episode["peak"]), "trough": endpoint(episode["trough"]),
         "recovery": endpoint(episode["recovery"])} for episode in curve["top3_distinct_excursions"]]}

def aggregate_fills(report):
    result = {}
    for fill in report["fill_audit"]:
        key = fill["instrument"].split("-")[0]
        item = result.setdefault(key, {"fills": 0, "notional": D(0), "fees": D(0), "actions": {}, "exit_reasons": {}})
        item["fills"] += 1
        item["notional"] += D(fill["notional"])
        item["fees"] += D(fill["commission"])
        action = item["actions"].setdefault(fill["action"], {"fills": 0, "notional": D(0), "fees": D(0)})
        action["fills"] += 1
        action["notional"] += D(fill["notional"])
        action["fees"] += D(fill["commission"])
        if fill["action"] not in ("BTC_ENTRY", "SOL_ADD"):
            reason = item["exit_reasons"].setdefault(fill["reason"], {"fills": 0, "notional": D(0), "exit_fees": D(0)})
            reason["fills"] += 1
            reason["notional"] += D(fill["notional"])
            reason["exit_fees"] += D(fill["commission"])
    assert sum(x["fills"] for x in result.values()) == report["fills"]
    assert sum((x["fees"] for x in result.values()), D(0)) == D(report["native_fees"])
    return result

def first_fill_divergence(control, variant):
    columns = ("fill_ns", "instrument", "action", "reason", "level", "qty", "px", "notional", "commission", "native_liquidity_side")
    a, b = control["fill_audit"], variant["fill_audit"]
    for index in range(max(len(a), len(b))):
        left, right = a[index] if index < len(a) else None, b[index] if index < len(b) else None
        if left is None or right is None or any(left.get(k) != right.get(k) for k in columns):
            return {"identical_preceding_native_fill_rows": index,
                    "control": {k: left.get(k) for k in columns} if left else None,
                    "variant": {k: right.get(k) for k in columns} if right else None,
                    "comparison": "ORDERED_NATIVE_MONETARY_FILL_FIELDS_NOT_COUNTERFACTUAL_ATTRIBUTION"}
    return None

def cap_stats(report):
    attempts = report.get("sol_cap_admission_audit", [])
    positive = [a for a in attempts if D(a["admitted_quantity"]) > 0]
    zero = [a for a in attempts if D(a["admitted_quantity"]) == 0]
    capped = [a for a in positive if D(a["admitted_quantity"]) < D(a["requested_quantity"])]
    for a in positive:
        reserve = D(a["reserved_taker_fee"]) + D(a["reserved_mark_execution_gap_loss"])
        assert D(a["prospective_notional_upper"]) <= D(6) * (D(a["native_equity"]) - reserve)
    reasons = {}
    for a in zero:
        reason = a.get("reason", "NO_ROOM_OR_BELOW_NATIVE_STEP")
        reasons[reason] = reasons.get(reason, 0) + 1
    return {"attempts": len(attempts), "positive_admissions": len(positive), "positive_clamps": len(capped),
            "zero_admissions": len(zero), "zero_reasons": reasons,
            "first_positive_clamp": {**capped[0], "utc": utc(capped[0]["timestamp_ns"])} if capped else None,
            "admission_bound_verified_all_positive": True,
            "basis": "ADMISSION_ATTEMPTS_NOT_UNIQUE_FILLED_ORDERS; EXISTING_EXPOSURE_IS_NOT_FORCED_DOWN"}

def protection_stats(report):
    events = report.get("research_protection_audit", [])
    breaches = [a for a in events if a["event"] == "BREACH"]
    exits = [a for a in report["fill_audit"] if a["reason"] == "RESEARCH_PORTFOLIO_45"]
    detailed = []
    for i, event in enumerate(breaches):
        start = int(event["timestamp_ns"])
        end = int(breaches[i+1]["timestamp_ns"]) if i+1 < len(breaches) else 10**30
        fills = [f for f in exits if start <= int(f["fill_ns"]) < end]
        detailed.append({**event, "utc": utc(start),
                         "native_exit_fill_count": len(fills),
                         "native_exit_notional": str(sum((D(f["notional"]) for f in fills), D(0))),
                         "native_exit_fees": str(sum((D(f["commission"]) for f in fills), D(0))),
                         "first_exit_utc": utc(fills[0]["fill_ns"]) if fills else None,
                         "last_exit_utc": utc(fills[-1]["fill_ns"]) if fills else None,
                         "first_fill_latency_ns": str(int(fills[0]["fill_ns"]) - start) if fills else None,
                         "last_fill_latency_ns": str(int(fills[-1]["fill_ns"]) - start) if fills else None,
                         "latency_basis": "LAST_FILL_IS_NOT_AN_ATOMIC_NATIVE_FLAT_ACK"})
    return {"breaches": len(breaches), "rearms": sum(a["event"] == "REARM_NEXT_EPISODE" for a in events),
            "events": [{**a, "utc": utc(a["timestamp_ns"])} for a in events], "breach_exit_fills": detailed,
            "protective_epoch_reset_is_not_global_dd_reset": True}

def trace_pass(path, summary):
    close = summary["curves"]["all_native_close_samples"]
    targets = {(p["timestamp_ns"], D(p["equity"])) for episode in close["top3_distinct_excursions"]
               for p in (episode["peak"], episode["trough"], episode["recovery"]) if p}
    targets.add((close["minimum"]["timestamp_ns"], D(close["minimum"]["equity"])))
    snapshots = {}
    running_upper = None
    worst = None
    min_buffer = None
    rows = prequotes = exposed = 0
    with gzip.open(path, "rt", newline="") as stream:
        for row in csv.DictReader(stream):
            rows += 1
            key = (row["close_available_ns"], D(row["paired_close_equity"]))
            if key in targets and key not in snapshots and not row["phase"].startswith("post_boundary_"):
                snapshots[key] = {**row, "utc": utc(key[0]),
                                  "native_positions_and_mark_ohlc_json": json.loads(row["native_positions_and_mark_ohlc_json"])}
            if row["phase"] != "pre_quote_paired_close":
                continue
            prequotes += 1
            upper, lower = D(row["conditional_favorable_equity"]), D(row["conditional_adverse_equity"])
            point = {"timestamp_ns": row["close_available_ns"], "bar_open_ms": row["bar_open_ms"], "utc": utc(row["close_available_ns"])}
            if running_upper is None or upper > running_upper["equity"]:
                running_upper = {**point, "equity": upper}
            if running_upper["equity"] > 0:
                amount = running_upper["equity"] - lower
                percent = amount / running_upper["equity"] * 100
                if worst is None or percent > worst["maximum_percent"]:
                    worst = {"maximum_percent": percent, "amount_usdt": amount, "peak": dict(running_upper),
                             "trough": {**point, "equity": lower},
                             "same_bar_extreme_order_unknown": running_upper["timestamp_ns"] == point["timestamp_ns"]}
            if row["native_positions_and_mark_ohlc_json"] != "[]":
                exposed += 1
                buffer = lower - D(row["conditional_high_mark_mm_upper"])
                if min_buffer is None or buffer < min_buffer["buffer_usdt"]:
                    min_buffer = {**point, "buffer_usdt": buffer, "lower_equity": lower,
                                  "maintenance_upper": D(row["conditional_high_mark_mm_upper"])}
    assert rows == summary["rows"] == 3 * prequotes
    assert len(snapshots) == len(targets)
    return {"trace_rows": rows, "paired_prequote_minutes": prequotes, "exposed_minutes": exposed,
            "global_conditional_favorable_peak_to_later_adverse_bound": worst,
            "minimum_conditional_exposed_margin_buffer": min_buffer,
            "native_landmark_snapshots": list(snapshots.values()),
            "interpretation": "OHLC upper-to-lower is a conditional conservative path bound; joint asset extrema/order unknown, not actual historical DD"}

def native_cash_decomposition(item):
    snapshots = item["native_landmark_snapshots"]
    rows = []
    for rank, episode in enumerate(item["global_native_curve"]["top3_distinct_excursions"], 1):
        matched = []
        for phase in ("peak", "trough"):
            p = episode[phase]
            snap = next(s for s in snapshots if s["close_available_ns"] == p["timestamp_ns"]
                        and D(s["paired_close_equity"]) == D(p["equity"]))
            matched.append({"phase": snap["phase"], "utc": p["utc"], "cash": D(snap["cash"]),
                            "unrealized": D(p["equity"])-D(snap["cash"]),
                            "native_positions": snap["native_positions_and_mark_ohlc_json"]})
        peak, trough = matched
        cash_loss, unrealized_loss = peak["cash"]-trough["cash"], peak["unrealized"]-trough["unrealized"]
        assert cash_loss + unrealized_loss == D(episode["drawdown_amount"])
        rows.append({"rank": rank, "peak": peak, "trough": trough, "cash_loss_component": cash_loss,
                     "unrealized_loss_component": unrealized_loss,
                     "cash_loss_percent_of_drawdown": cash_loss/D(episode["drawdown_amount"])*100,
                     "unrealized_loss_percent_of_drawdown": unrealized_loss/D(episode["drawdown_amount"])*100,
                     "basis": "EXACT_NATIVE_CASH_ENDPOINT_DIFFERENCE_AND_NATIVE_MARKED_EQUITY_MINUS_CASH; CASH_INCLUDES_UNALLOCATED_FUNDING"})
    return rows

def write_readme(output):
    def fmt(value, places=2):
        return f"{D(value):,.{places}f}"
    lines = ["# Two isolated native risk comparisons",
        "",
        "Comparison reference is the reused audited selective-lifecycle30m winner TOTAL 5,146,884.957182 USDT. The original V0 artifact is only the immutable input-loader source, not the economic comparison baseline.",
        "",
        "Frozen source 498a8fe0d62cac5cea00e81660195f7e9c3e0131; independent narrow review GO; 116 relevant tests passed. Two mutually exclusive flags, one fresh native engine/funding journal per variant, identical Bybit inputs and all other economics. No control rerun, pilot action, or follow-up candidate.",
        "",
        "| Variant | TOTAL USDT | Change vs winner | ROI on 10,000 | Global native DD | Conditional upper-to-lower bound | Fees | Fills |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    control = output["control"]
    lines.append(f'| Reused control | {fmt(control["terminal_total"])} | — | {fmt(control["roi_percent"])}% | {fmt(control["native_curve"]["top3_distinct_excursions"][0]["drawdown_peak_percent"],4)}% | {fmt(control["conditional_upper_to_lower_bound"]["maximum_percent"],4)}% | {fmt(control["native_fees"])} | {control["fills"]} |')
    for name, item in output["variants"].items():
        dd = item["global_native_curve"]["top3_distinct_excursions"][0]["drawdown_peak_percent"]
        bound = item["global_conditional_favorable_peak_to_later_adverse_bound"]["maximum_percent"]
        lines.append(f'| {name} | {fmt(item["terminal_total"])} | {fmt(item["terminal_delta_vs_control"])} ({fmt(item["terminal_delta_vs_control_percent"])}%) | {fmt(item["roi_percent"])}% | {fmt(dd,4)}% | {fmt(bound,4)}% | {fmt(item["native_fees"])} | {item["fills"]} |')
    lines.extend(["", "Native DD uses the global 24-month pre/post callback-close sampled curve without any reset. It is not an exact intrabar trajectory. The final completed-bar prequote at end_exclusive is retained; terminal quote/fill settlement is separately exported and excluded from interval DD. TOTAL includes native terminal settlement.",
                  "", "| Variant | Minimum native equity / UTC | Loss below initial 10,000 | Conditional adverse minimum | Funding postings | Liquidations | Modeled conditional MM breaches |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: |"])
    for name, item in output["variants"].items():
        curve = item["global_native_curve"]
        lower = item["conditional_adverse_curve"]
        lines.append(f'| {name} | {fmt(curve["minimum"]["equity"])} / {curve["minimum"]["utc"]} | {fmt(curve["maximum_loss_below_seed_amount"])} ({fmt(curve["maximum_loss_below_seed_percent"],4)}%) | {fmt(lower["minimum"]["equity"])} / {lower["minimum"]["utc"]} | {item["funding_count"]} | {item["liquidation_count"]} | {item["conditional_modeled_margin_breaches"]} |')
    lines.extend(["", "Signed funding and per-trade native PnL attribution remain UNKNOWN; posting counts are not signed funding amounts. Fees and filled notional come directly from native fills and reconcile to native totals. A change in final TOTAL cannot be attributed solely to the fee difference because subsequent exposure and compounding differ.",
                  "", "## Global native TOP3 distinct peak-to-recovery excursions", "",
                  "| Variant/rank | Peak UTC / equity | Trough UTC / equity | Recovery UTC | Loss USDT | DD |",
                  "| --- | --- | --- | --- | ---: | ---: |"])
    for name, item in output["variants"].items():
        for rank, e in enumerate(item["global_native_curve"]["top3_distinct_excursions"],1):
            recovery = e["recovery"]["utc"] if e["recovery"] else "UNRECOVERED"
            lines.append(f'| {name}/{rank} | {e["peak"]["utc"]} / {fmt(e["peak"]["equity"])} | {e["trough"]["utc"]} / {fmt(e["trough"]["equity"])} | {recovery} | {fmt(e["drawdown_amount"])} | {fmt(e["drawdown_peak_percent"],4)}% |')
    lines.extend(["", "Conditional adverse lower-series TOP3 are in drawdown-top3.csv and the JSON. These lower-to-lower excursions are not the conservative maximum intrabar-DD bound. The separate favorable running-upper to later adverse-lower maximum permits unfavorable same-bar ordering; BTC/SOL extrema are not synchronized and historical path/order is unknown.",
                  "", "## Measured mechanism and native economic divergence", ""])
    for name, item in output["variants"].items():
        divergence = item["first_native_fill_divergence"]
        lines.append(f'**{name}:** {divergence["identical_preceding_native_fill_rows"]} preceding native monetary fill rows match the control before the first divergence.')
        for label in ("control","variant"):
            row = divergence[label]
            if row:
                lines.append(f'- First {label} row: {utc(row["fill_ns"])} UTC, {row["instrument"]}, {row["action"]}/{row["reason"]}, qty {row["qty"]}, price {row["px"]}, notional {row["notional"]}, commission {row["commission"]}.')
        lines.append("")
        if name == "solcap6":
            a = item["cap_admissions"]
            lines.append(f'SOL admission attempts {a["attempts"]}; positive admissions {a["positive_admissions"]}; positive clamps {a["positive_clamps"]}; zero admissions {a["zero_admissions"]}. All positive admission inequalities verify against native equity, aggregate held marked notional, gap/fee reserve and lot normalization. This is entry sizing only; held exposure can later exceed6x as prices/equity change. H/reference, BTC sizing, rights and exit rules stay unchanged.')
            if a["first_positive_clamp"]:
                c = a["first_positive_clamp"]
                lines.append(f'First clamp {c["utc"]}: desired {c["requested_quantity"]} SOL → admitted {c["admitted_quantity"]}; native equity {c["native_equity"]}; existing held SOL marked notional {c["held_sol_mark_notional"]}. Counts are admission attempts, not unique native fill orders.')
        else:
            a = item["protection"]
            fees = sum((D(e["native_exit_fees"]) for e in a["breach_exit_fills"]),D(0))
            fills = sum(e["native_exit_fill_count"] for e in a["breach_exit_fills"])
            lines.append(f'Protection breaches {a["breaches"]}; next-episode rearms {a["rearms"]}; actual protection-exit fills {fills}, exit commissions {fmt(fees)}. These RESEARCH_PORTFOLIO_45 exits are distinct from original TRAIL/REGIME and are not fixed price SL exits. Protective peak resets only after actual native flatness and the next fresh genuine BTC episode; global observer peaks never reset. Repeated epochs can still produce global DD above45% or50%.')
            if a["breach_exit_fills"]:
                e = a["breach_exit_fills"][0]
                lines.append(f'First breach {e["utc"]}: native equity {e["native_equity"]} versus protective peak {e["protective_peak"]}; old episode {e["old_episode_id"]}; first/last exit fill latency {e["first_fill_latency_ns"]}/{e["last_fill_latency_ns"]}ns. Last fill is not a separate atomic native-flat acknowledgement.')
        lines.append("")
        for asset, values in item["native_fills_by_asset"].items():
            lines.append(f'- {asset}: native fills {values["fills"]}, filled turnover {fmt(values["notional"])} USDT, native commissions {fmt(values["fees"])}.')
        lines.append("")
    qualified = [(name,item) for name,item in output["variants"].items() if item["global_native_dd_at_most_50"]]
    if qualified:
        name,item = max(qualified,key=lambda pair:D(pair[1]["terminal_total"]))
        lines.append(f'Recommendation: {name} has the highest TOTAL among these two variants meeting the sampled global native ≤50% target. Its conditional OHLC bound is reported separately; this does not establish exact intrabar or live viability.')
    else:
        lines.append("Recommendation: neither comparison meets the sampled global native ≤50% target, so this bounded comparison has no qualifying winner. Preserve the control as the ROI reference; no next candidate or deployment is authorized by this report.")
    lines.extend(["", "## Evidence and limits", "",
        "comparison.json contains exact values, global TOP3, native prequote/postquote landmark snapshots, conditional bound endpoints, minimum exposed modeled MM buffer, cap admissions/protection events, sole config delta, native fill attribution and immutable trace paths/SHA-256. comparison.csv and drawdown-top3.csv are compact tables; both minute-risk-summary.json files and the independent review are retained. Large minute traces remain in immutable jobs and are not committed.",
        "",
        "Execution is the existing synthetic zero-spread, size1000 quote policy from Bybit1m closes. Protection cancellation acknowledgement can invoke existing native market_exit against the previous cached book; pre-action marked loss and completed-bar OHLC exposure are captured first. Such fills are diagnostic and cannot be treated as venue stop execution. Funding/execution marks, historical venue fee applicability and synchronized ticks remain unvalidated.",
        "",
        "Modeled maintenance uses existing native-equity≤tierMM only, without extra liquidation-fee reserve. Zero conditional modeled breaches is conditional model evidence, not actual venue liquidation safety. Quantity gap/fee reserve is admission evidence and does not force later SOL deleveraging.",
        ""])
    (HERE/"README.md").write_text("\n".join(lines))

def main():
    with gzip.open(AUDIT/"native-observer-result.json.gz", "rt") as stream:
        control = json.load(stream)
    control_summary = load(AUDIT/"minute-risk-summary.json")
    control_bound = load(AUDIT/"conditional-upper-to-lower-bound.json")
    assert D(control["terminal_total"]) == D("5146884.95718200")
    output = {"control": {"terminal_total": control["terminal_total"], "roi_percent": str((D(control["terminal_total"])/10000-1)*100),
                          "native_fees": control["native_fees"], "fills": control["fills"],
                          "funding_count": control["funding"]["count"], "native_fills_by_asset": aggregate_fills(control),
                          "native_curve": curve_summary(control_summary["curves"]["all_native_close_samples"]),
                          "conditional_upper_to_lower_bound": control_bound},
              "variants": {}, "money_basis": "NATIVE_ACCOUNT_AND_NATIVE_FILLS_ONLY; NO_SECOND_PNL_ENGINE; SIGNED_FUNDING_UNKNOWN"}
    output["control"]["provenance"] = {
        "result_gzip_path": str(AUDIT/"native-observer-result.json.gz"),
        "result_gzip_sha256": sha(AUDIT/"native-observer-result.json.gz"),
        "summary_path": str(AUDIT/"minute-risk-summary.json"),
        "summary_sha256": sha(AUDIT/"minute-risk-summary.json"),
        "receipt_path": str(AUDIT/"native-observer-receipt.json"),
        "receipt_sha256": sha(AUDIT/"native-observer-receipt.json"),
        "reference": "REUSED_AUDITED_SELECTIVE_LIFECYCLE_30M_WINNER_NOT_ORIGINAL_V0_LOADER"}
    for name, jobname in VARIANTS.items():
        folder = JOBS/jobname/"result"
        result_path = folder/f"v0-selective-lifecycle-cap30m-{name}.json"
        cache = HERE/f"{name}-analysis.json"
        if cache.exists():
            saved = load(cache)
            assert saved["provenance"]["result_sha256"] == sha(result_path)
            output["variants"][name] = saved
            continue
        if not result_path.exists():
            continue  # Run only after ops confirms completion; never read partial trace.
        report, summary = load(result_path), load(folder/"minute-risk-summary.json")
        trace = folder/"minute-native-risk.csv.gz"
        config_delta = {k: {"control": control["config"].get(k), "variant": report["config"].get(k)}
                        for k in set(control["config"]) | set(report["config"])
                        if control["config"].get(k) != report["config"].get(k)}
        expected_key = "research_sol_notional_cap_multiple" if name == "solcap6" else "research_portfolio_protect_45"
        assert set(config_delta) == {expected_key}, config_delta
        assert report["data_hash"] == control["data_hash"] and report["policy_hash"] == control["policy_hash"]
        scans = trace_pass(trace, summary)
        native = curve_summary(summary["curves"]["all_native_close_samples"])
        max_dd = D(native["top3_distinct_excursions"][0]["drawdown_peak_percent"])
        total = D(report["terminal_total"])
        output["variants"][name] = {"terminal_total": str(total), "roi_percent": str((total/10000-1)*100),
            "terminal_delta_vs_control": str(total-D(control["terminal_total"])),
            "terminal_delta_vs_control_percent": str((total/D(control["terminal_total"])-1)*100),
            "native_fees": report["native_fees"], "fee_delta_vs_control": str(D(report["native_fees"])-D(control["native_fees"])),
            "fills": report["fills"], "funding_count": report["funding"]["count"], "signed_funding": "UNKNOWN",
            "liquidation_count": report["liquidation_count"], "terminal_open_positions": report["terminal_open_positions"],
            "native_fills_by_asset": aggregate_fills(report), "first_native_fill_divergence": first_fill_divergence(control, report),
            "global_native_curve": native, "global_native_dd_at_most_50": max_dd <= 50,
            "conditional_adverse_curve": curve_summary(summary["curves"]["conditional_ohlc_adverse"]),
            "conditional_modeled_margin_breaches": summary["potential_conditional_intrabar_margin_breach_count"],
            "cap_admissions": cap_stats(report) if name == "solcap6" else None,
            "protection": protection_stats(report) if name == "portfolio45" else None,
            "config_delta": config_delta, **scans,
            "provenance": {"result_path": str(result_path), "result_sha256": sha(result_path), "trace_path": str(trace),
                           "trace_sha256": sha(trace), "summary_path": str(folder/"minute-risk-summary.json"),
                           "summary_sha256": sha(folder/"minute-risk-summary.json"), "execution_artifacts": report["execution_artifacts"]}}
        (HERE/f"{name}-minute-risk-summary.json").write_text(json.dumps(summary, indent=2)+"\n")
        cache.write_text(json.dumps(output["variants"][name], indent=2, default=str)+"\n")
        print(json.dumps({"completed_analysis": name, "total": str(total), "native_dd_percent": str(max_dd),
                          "conditional_bound_percent": str(scans["global_conditional_favorable_peak_to_later_adverse_bound"]["maximum_percent"])},
                         default=str), flush=True)
    for name, item in output["variants"].items():
        report = load(JOBS/VARIANTS[name]/"result"/f"v0-selective-lifecycle-cap30m-{name}.json")
        item["native_fills_by_asset"] = aggregate_fills(report)
        item["native_drawdown_cash_decomposition"] = native_cash_decomposition(item)
        (HERE/f"{name}-analysis.json").write_text(json.dumps(item, indent=2, default=str)+"\n")
    (HERE/"comparison.json").write_text(json.dumps(output, indent=2, default=str)+"\n")
    fields = ["variant","terminal_total","roi_percent","terminal_delta_usdt","terminal_delta_percent","native_dd_percent","native_seed_minimum","conditional_upper_lower_percent","fees","fills","funding_count","liquidations"]
    with (HERE/"comparison.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n"); writer.writeheader()
        for name, item in output["variants"].items():
            writer.writerow({"variant": name,"terminal_total":item["terminal_total"],"roi_percent":item["roi_percent"],
                "terminal_delta_usdt":item["terminal_delta_vs_control"],"terminal_delta_percent":item["terminal_delta_vs_control_percent"],
                "native_dd_percent":item["global_native_curve"]["top3_distinct_excursions"][0]["drawdown_peak_percent"],
                "native_seed_minimum":item["global_native_curve"]["minimum"]["equity"],
                "conditional_upper_lower_percent":item["global_conditional_favorable_peak_to_later_adverse_bound"]["maximum_percent"],
                "fees":item["native_fees"],"fills":item["fills"],"funding_count":item["funding_count"],"liquidations":item["liquidation_count"]})
    with (HERE/"drawdown-top3.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["variant","curve","rank","peak_utc","peak_equity","trough_utc","trough_equity","recovery_utc","drawdown_usdt","drawdown_percent"])
        for name, item in output["variants"].items():
            for label, key in (("native_callback_close","global_native_curve"),("conditional_adverse_lower_series","conditional_adverse_curve")):
                for rank, episode in enumerate(item[key]["top3_distinct_excursions"],1):
                    writer.writerow([name,label,rank,episode["peak"]["utc"],episode["peak"]["equity"],episode["trough"]["utc"],
                        episode["trough"]["equity"],episode["recovery"]["utc"] if episode["recovery"] else "UNRECOVERED",
                        episode["drawdown_amount"],episode["drawdown_peak_percent"]])
    if set(output["variants"]) == set(VARIANTS):
        write_readme(output)
    print(json.dumps({name:{k:v[k] for k in ("terminal_total","terminal_delta_vs_control","global_native_dd_at_most_50","fills")} for name,v in output["variants"].items()},indent=2))

if __name__ == "__main__":
    main()
