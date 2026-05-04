#!/usr/bin/env python3
"""Fast in-memory Wave Engine challenger search with split/stress scoring.

Unlike run_wave_engine_research.py, this does not write every candidate's full
trades/signals artifacts. It is intended for broad research sweeps and produces a
compact JSON summary. Research-only; no runtime mutation.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine import (
    _candidate_profiles,
    _normalize_profile,
    build_regime,
    compute_metrics,
    detect_pivots,
    generate_entry_signals,
    load_dataset,
    profile_to_dict,
    simulate_trades,
)


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _filter_trades(trades: list[Any], start: datetime | None, end: datetime | None) -> list[Any]:
    out = []
    for trade in trades:
        if start and trade.entry_time < start:
            continue
        if end and trade.entry_time >= end:
            continue
        out.append(trade)
    return out


def _metric_dict(trades: list[Any]) -> dict[str, Any]:
    metrics = asdict(compute_metrics(trades))
    by_side: dict[str, float] = {}
    by_exit: dict[str, float] = {}
    for trade in trades:
        by_side[trade.side] = round(by_side.get(trade.side, 0.0) + trade.profit_abs, 8)
        by_exit[trade.exit_reason] = round(by_exit.get(trade.exit_reason, 0.0) + trade.profit_abs, 8)
    metrics["by_side_profit_abs"] = by_side
    metrics["by_exit_profit_abs"] = by_exit
    return metrics


def _evaluate(candles_by_tf: dict[str, list[Any]], raw_profile: dict[str, Any]) -> dict[str, Any]:
    profile = _normalize_profile(raw_profile)
    pivots = detect_pivots(candles_by_tf["4h"], profile)
    regimes = build_regime(candles_by_tf["4h"], pivots, profile.break_basis)
    signals = generate_entry_signals(profile.symbol, profile, candles_by_tf, regimes)
    trades = simulate_trades(profile, candles_by_tf, signals)
    splits = {
        "full_jan_may": (None, None),
        "train_jan_mar": (_ts("2026-01-01T00:00:00+00:00"), _ts("2026-04-01T00:00:00+00:00")),
        "oos_apr_may": (_ts("2026-04-01T00:00:00+00:00"), None),
        "recent_mar_may": (_ts("2026-03-01T00:00:00+00:00"), None),
    }
    split_metrics = {name: _metric_dict(_filter_trades(trades, start, end)) for name, (start, end) in splits.items()}
    return {
        "profile": profile_to_dict(profile),
        "pivot_count": len(pivots),
        "signal_count": len(signals),
        "metrics": split_metrics,
        "latest_regime": asdict(regimes[-1]) if regimes else None,
    }


def _score(result: dict[str, Any]) -> float:
    full = result["metrics"]["full_jan_may"]
    oos = result["metrics"]["oos_apr_may"]
    recent = result["metrics"]["recent_mar_may"]
    train = result["metrics"]["train_jan_mar"]
    pf = lambda m: float(m["profit_factor"] or 0.0)
    # Hard-ish penalties: we prefer candidates that work recently, not only in Jan.
    score = 0.0
    score += float(oos["roi_pct"]) * 3.0
    score += float(recent["roi_pct"]) * 2.0
    score += float(full["roi_pct"]) * 1.0
    score += min(pf(oos), 5.0) * 10.0
    score += min(pf(recent), 5.0) * 6.0
    score -= float(full["max_drawdown_pct"]) * 4.0
    score -= float(recent["max_drawdown_pct"]) * 3.0
    if int(full["trades"]) < 10:
        score -= 100.0
    if int(oos["trades"]) < 3:
        score -= 80.0
    if float(oos["profit_abs"]) <= 0:
        score -= 120.0
    if float(recent["profit_abs"]) <= 0:
        score -= 80.0
    if float(train["profit_abs"]) <= 0:
        score -= 40.0
    stress = float(full.get("top_trade_stress_abs") or 0.0)
    if float(full["profit_abs"]) > 0 and stress <= 0:
        score -= 60.0
    return round(score, 8)


def _candidate_pool(mode: str, count: int, seed: int) -> list[dict[str, Any]]:
    candidates = _candidate_profiles(mode, max_candidates=count, sampling="random", seed=seed)
    # Add deliberately looser variants to test the "too strict" hypothesis.
    randomizer = random.Random(seed + 909)
    for _ in range(max(24, count // 8)):
        candidates.append(
            {
                "wave_engine": randomizer.choice(["atr_zigzag", "pct_zigzag"]),
                "atr_mult": randomizer.choice([1.5, 2.0, 2.5]),
                "pct_move": randomizer.choice([0.02, 0.025, 0.03]),
                "break_basis": randomizer.choice(["wick", "close"]),
                "entry_timeframes": (randomizer.choice(["5m", "15m", "1h"]),),
                "flat_extreme_lookback_hours": randomizer.choice([60, 90, 120, 150]),
                "pullback_ratio": randomizer.choice([0.4, 0.45, 0.5, 0.55, 0.6]),
                "max_sl_pct": randomizer.choice([0.02, 0.025, 0.03, 0.035, 0.04]),
                "tp2_pct": randomizer.choice([0.02, 0.025, 0.03, 0.035, 0.04]),
                "tp3_pct": randomizer.choice([0.04, 0.05, 0.06, 0.07, 0.08]),
                "time_stop_hours": randomizer.choice([4, 6, 8, 10, 12, 16]),
            }
        )
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Fast Wave Engine challenger search.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=["quick", "deep"], default="deep")
    parser.add_argument("--candidates", type=int, default=512)
    parser.add_argument("--seed", type=int, default=7303)
    parser.add_argument("--selected-profile", help="Optional Wave Engine profile snapshot to include as baseline.")
    args = parser.parse_args()

    base = {"symbol": args.symbol}
    candidates = _candidate_pool(args.mode, args.candidates, args.seed)
    evaluated: list[dict[str, Any]] = []
    baseline: dict[str, Any] | None = None

    candles_by_tf = load_dataset(args.dataset)

    if args.selected_profile:
        snapshot = json.loads(Path(args.selected_profile).read_text(encoding="utf-8"))
        raw = (snapshot.get("pairs") or {}).get(args.symbol)
        if isinstance(raw, dict):
            baseline = _evaluate(candles_by_tf, raw)
            baseline["score"] = _score(baseline)
            baseline["candidate_id"] = "current_selected"

    for index, candidate in enumerate(candidates, start=1):
        raw = dict(base)
        raw.update(candidate)
        result = _evaluate(candles_by_tf, raw)
        result["score"] = _score(result)
        result["candidate_id"] = f"candidate-{index:04d}"
        evaluated.append(result)

    evaluated.sort(key=lambda row: row["score"], reverse=True)
    payload = {
        "ok": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": args.dataset,
        "symbol": args.symbol,
        "mode": args.mode,
        "candidate_count": len(evaluated),
        "baseline": baseline,
        "top": evaluated[:25],
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": args.output, "symbol": args.symbol, "best_score": evaluated[0]["score"] if evaluated else None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
