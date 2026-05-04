#!/usr/bin/env python3
"""Synthetic invariant check for the research-only Wave Engine prototype."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from freqtrade.wave_engine.engine import run_matrix_research, run_single_research


def candle(ts: datetime, o: float, h: float, l: float, c: float) -> dict:
    return {"timestamp": ts.isoformat(), "open": o, "high": h, "low": l, "close": c, "volume": 1.0}


def build_dataset() -> dict:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles_4h = []
    price = 100.0
    for step in range(18):
        ts = start + timedelta(hours=4 * step)
        if step < 4:
            close = price + 1.0
        elif step < 8:
            close = price - 1.8
        elif step < 12:
            close = price + 2.5
        else:
            close = price + 1.0
        high = max(price, close) + 0.8
        low = min(price, close) - 0.8
        candles_4h.append(candle(ts, price, high, low, close))
        price = close

    candles_1h = []
    start_1h = start
    price = 100.0
    pattern = [0.4, 0.6, -0.2, -0.5, 0.7, 0.9, -0.3, -0.6, 1.1, -0.4, 0.5, 0.8]
    for step in range(72):
        ts = start_1h + timedelta(hours=step)
        delta = pattern[step % len(pattern)]
        close = price + delta
        high = max(price, close) + 0.35
        low = min(price, close) - 0.35
        candles_1h.append(candle(ts, price, high, low, close))
        price = close

    def down_up_sequence(ts: datetime, price: float) -> tuple[list[dict], float]:
        out = []
        steps = [-0.6, -0.4, 1.2, 0.7]
        current = price
        for move in steps:
            close = current + move
            out.append(candle(ts, current, max(current, close) + 0.15, min(current, close) - 0.15, close))
            current = close
            ts += timedelta(minutes=15)
        return out, current

    candles_15m = []
    current = 100.0
    ts = start
    for _ in range(96):
        block, current = down_up_sequence(ts, current)
        candles_15m.extend(block)
        ts = block[-1]["timestamp"]
        ts = datetime.fromisoformat(ts).astimezone(UTC) + timedelta(minutes=15)

    candles_5m = []
    current = 100.0
    ts = start
    for step in range(288):
        move = [-0.2, -0.15, 0.45, 0.25][step % 4]
        close = current + move
        candles_5m.append(candle(ts, current, max(current, close) + 0.08, min(current, close) - 0.08, close))
        current = close
        ts += timedelta(minutes=5)

    return {"candles": {"4h": candles_4h, "1h": candles_1h, "15m": candles_15m, "5m": candles_5m}}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="wave-engine-check-") as tmpdir:
        tmp = Path(tmpdir)
        dataset_path = tmp / "dataset.json"
        dataset_path.write_text(json.dumps(build_dataset(), indent=2) + "\n", encoding="utf-8")

        single = run_single_research(
            dataset_path,
            {"entry_timeframes": ["15m"], "wave_engine": "pct_zigzag", "pct_move": 0.02, "break_basis": "wick"},
            tmp / "runs-single",
            run_id="single-check",
        )
        metrics = single["metrics"]
        assert metrics["trades"] >= 1, metrics
        assert "run_dir" in single and Path(single["run_dir"]).exists()

        matrix = run_matrix_research(
            dataset_path,
            {"entry_timeframes": ["15m"]},
            tmp / "runs-matrix",
            mode="quick",
            max_candidates=3,
            sampling="random",
            seed=73,
            run_id="matrix-check",
        )
        assert matrix["leaderboard_size"] == 3, matrix
        assert matrix["best"] is not None, matrix
        print(json.dumps({"single": single, "matrix": matrix}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
