#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures as cf
import io
import json
import math
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import error, parse, request

try:
    from pyarrow import feather  # type: ignore
except Exception as exc:  # pragma: no cover - local bootstrap path
    feather = None
    _PYARROW_IMPORT_ERROR = exc
else:
    _PYARROW_IMPORT_ERROR = None

MINUTE_MS = 60_000
BYBIT_BASE = "https://api.bybit.com"
HL_INFO_URL = "https://api.hyperliquid.xyz/info"

HL_HISTORICAL_URLS = {
    "BTC": "https://raw.githubusercontent.com/guibvieira/freqtrade-hyperliquid-data/main/user_data/data/hyperliquid/futures/BTC_USDC_USDC-1m-futures.feather",
    "SOL": "https://raw.githubusercontent.com/guibvieira/freqtrade-hyperliquid-data/main/user_data/data/hyperliquid/futures/SOL_USDC_USDC-1m-futures.feather",
    "HYPE": "https://raw.githubusercontent.com/trmaphi/freqtrade_download_hyperliquid_data/main/user_data/data/hyperliquid/HYPE_USDC-1m.feather",
    "ZEC": "https://raw.githubusercontent.com/guibvieira/freqtrade-hyperliquid-data/main/user_data/data/hyperliquid/futures/ZEC_USDC_USDC-1m-futures.feather",
}

# Bybit USDC perpetuals for the requested assets.
# ZEC has no USDC perp on Bybit at the time of analysis, so we use ZECUSDT
# as the nearest liquid perpetual and explicitly flag that in the report.
BYBIT_SYMBOLS = {
    "BTC": "BTCPERP",
    "SOL": "SOLPERP",
    "HYPE": "HYPEPERP",
    "ZEC": "ZECUSDT",
}

HL_COINS = {
    "BTC": "BTC",
    "SOL": "SOL",
    "HYPE": "HYPE",
    "ZEC": "ZEC",
}


@dataclass
class Series:
    rows: list[dict[str, Any]]
    meta: dict[str, Any]


class FetchError(RuntimeError):
    pass


def utc_floor_minute(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(second=0, microsecond=0)


def ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def dt_from_ms(v: int) -> datetime:
    return datetime.fromtimestamp(v / 1000, tz=timezone.utc)


def pct(v: float) -> float:
    return v * 100.0


def bps(v: float) -> float:
    return v * 10_000.0


def request_json(url: str, *, method: str = "GET", body: dict[str, Any] | None = None, timeout: int = 30, retries: int = 10) -> Any:
    payload = None if body is None else json.dumps(body).encode()
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"

    last_err: Exception | None = None
    for attempt in range(retries):
        req = request.Request(url, data=payload, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
            return json.loads(raw)
        except error.HTTPError as e:
            last_err = e
            if e.code in {429, 500, 502, 503, 504}:
                time.sleep(min(60, 2 ** attempt))
                continue
            raise
        except Exception as e:
            last_err = e
            time.sleep(min(60, 2 ** attempt))

    raise FetchError(f"failed request after {retries} attempts: {url}") from last_err


def fetch_bybit_symbol(symbol: str, start_ms: int, end_ms: int, interval: str = "1", limit: int = 1000) -> Series:
    rows: list[dict[str, Any]] = []
    calls = 0
    cursor_end = end_ms
    interval_ms = MINUTE_MS

    while cursor_end >= start_ms:
        q = parse.urlencode(
            {
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "start": start_ms,
                "end": cursor_end,
                "limit": limit,
            }
        )
        url = f"{BYBIT_BASE}/v5/market/kline?{q}"
        # Bybit often surfaces rate limits as JSON retCode=10006 rather than HTTP 429.
        # Retry the same page with a small backoff when that happens.
        last_data: dict[str, Any] | None = None
        for attempt in range(8):
            data = request_json(url)
            last_data = data
            if data.get("retCode") == 0:
                break
            if data.get("retCode") in {10006, 10018, 10019}:
                time.sleep(min(20.0, 1.5 ** attempt))
                continue
            raise FetchError(f"Bybit error for {symbol}: {data}")
        else:
            raise FetchError(f"Bybit rate-limit persisted for {symbol}: {last_data}")

        calls += 1
        lst = data.get("result", {}).get("list", [])
        if not lst:
            break

        batch = []
        tses = []
        for item in lst:
            # [startTime, open, high, low, close, volume, turnover]
            ts = int(item[0])
            if ts < start_ms or ts > end_ms:
                continue
            tses.append(ts)
            batch.append(
                {
                    "timestamp_ms": ts,
                    "timestamp": dt_from_ms(ts),
                    "open": float(item[1]),
                    "high": float(item[2]),
                    "low": float(item[3]),
                    "close": float(item[4]),
                    "volume": float(item[5]),
                    "turnover": float(item[6]),
                }
            )
        rows.extend(batch)

        if not tses:
            break
        oldest = min(tses)
        next_end = oldest - interval_ms
        if next_end >= cursor_end:
            break
        cursor_end = next_end

        # Gentle pacing keeps us well below Bybit's rolling limit.
        time.sleep(0.25)

        # Safety brake
        if calls > 10_000:
            break

    dedup = {r["timestamp_ms"]: r for r in rows}
    out = [dedup[k] for k in sorted(dedup)]
    meta = {
        "source": "bybit",
        "symbol": symbol,
        "count": len(out),
        "calls": calls,
        "requested_start": dt_from_ms(start_ms).isoformat(),
        "requested_end": dt_from_ms(end_ms).isoformat(),
    }
    if out:
        meta["actual_start"] = out[0]["timestamp"].isoformat()
        meta["actual_end"] = out[-1]["timestamp"].isoformat()
    return Series(out, meta)


def fetch_hyperliquid_symbol(coin: str, start_ms: int, end_ms: int, interval: str = "1m", chunk_minutes: int = 3000) -> Series:
    if feather is None:
        raise RuntimeError(
            "pyarrow is required to read Hyperliquid historical feather files. "
            f"Import error: {_PYARROW_IMPORT_ERROR}"
        )

    url = HL_HISTORICAL_URLS.get(coin)
    if not url:
        raise FetchError(f"No Hyperliquid historical URL for {coin}")

    raw = request_json_bytes(url)
    tbl = feather.read_table(io.BytesIO(raw))
    cols = tbl.to_pydict()
    dates = cols.get("date", [])
    opens = cols.get("open", [])
    highs = cols.get("high", [])
    lows = cols.get("low", [])
    closes = cols.get("close", [])
    volumes = cols.get("volume", [])

    rows: list[dict[str, Any]] = []
    for dt_obj, o, h, l, c, v in zip(dates, opens, highs, lows, closes, volumes):
        ts = int(dt_obj.timestamp() * 1000)
        if ts < start_ms or ts > end_ms:
            continue
        rows.append(
            {
                "timestamp_ms": ts,
                "timestamp": dt_from_ms(ts),
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "volume": float(v),
            }
        )

    dedup = {r["timestamp_ms"]: r for r in rows}
    out = [dedup[k] for k in sorted(dedup)]
    meta = {
        "source": "hyperliquid",
        "coin": coin,
        "count": len(out),
        "calls": 1,
        "requested_start": dt_from_ms(start_ms).isoformat(),
        "requested_end": dt_from_ms(end_ms).isoformat(),
    }
    if out:
        meta["actual_start"] = out[0]["timestamp"].isoformat()
        meta["actual_end"] = out[-1]["timestamp"].isoformat()
    return Series(out, meta)


def request_json_bytes(url: str, *, timeout: int = 60, retries: int = 6) -> bytes:
    last_err: Exception | None = None
    for attempt in range(retries):
        req = request.Request(url, headers={"Accept": "application/octet-stream", "User-Agent": "Mozilla/5.0"})
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except error.HTTPError as e:
            last_err = e
            if e.code in {429, 500, 502, 503, 504}:
                time.sleep(min(60, 2 ** attempt))
                continue
            raise
        except Exception as e:
            last_err = e
            time.sleep(min(60, 2 ** attempt))
    raise FetchError(f"failed request after {retries} attempts: {url}") from last_err


def hyperliquid_latest_end_ms(coin: str) -> int:
    if feather is None:
        raise RuntimeError(
            "pyarrow is required to read Hyperliquid historical feather files. "
            f"Import error: {_PYARROW_IMPORT_ERROR}"
        )
    url = HL_HISTORICAL_URLS.get(coin)
    if not url:
        raise FetchError(f"No Hyperliquid historical URL for {coin}")
    raw = request_json_bytes(url)
    tbl = feather.read_table(io.BytesIO(raw), columns=["date"])
    last = tbl.column("date")[-1].as_py()
    return int(last.timestamp() * 1000)


def interval_ms(interval: str) -> int:
    if interval in {"1m", "1"}:
        return MINUTE_MS
    raise ValueError(f"unsupported interval: {interval}")


def common_alignment(a: Series, b: Series) -> dict[str, Any]:
    da = {r["timestamp_ms"]: r for r in a.rows}
    db = {r["timestamp_ms"]: r for r in b.rows}
    common = sorted(set(da) & set(db))
    if not common:
        return {"common": [], "coverage_a": 0.0, "coverage_b": 0.0}
    start = common[0]
    end = common[-1]
    expected = int((end - start) / MINUTE_MS) + 1
    return {
        "common": common,
        "coverage_a": len(common) / max(1, len(a.rows)),
        "coverage_b": len(common) / max(1, len(b.rows)),
        "coverage_common_span": len(common) / max(1, expected),
    }


def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    if p <= 0:
        return sorted_vals[0]
    if p >= 1:
        return sorted_vals[-1]
    idx = (len(sorted_vals) - 1) * p
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return sorted_vals[int(idx)]
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def run_lengths(flags: list[bool]) -> list[int]:
    out: list[int] = []
    cur = 0
    for flag in flags:
        if flag:
            cur += 1
        elif cur:
            out.append(cur)
            cur = 0
    if cur:
        out.append(cur)
    return out


def stats_for_pair(bybit: Series, hl: Series, threshold_bps: list[float]) -> dict[str, Any]:
    aligned = common_alignment(bybit, hl)
    common = aligned["common"]
    da = {r["timestamp_ms"]: r for r in bybit.rows}
    db = {r["timestamp_ms"]: r for r in hl.rows}

    if not common:
        return {"error": "no_overlap", **aligned}

    signed_bps: list[float] = []
    abs_bps: list[float] = []
    spread_dollars: list[float] = []
    bybit_cheaper = 0
    hl_cheaper = 0

    for ts in common:
        a = da[ts]["close"]
        b = db[ts]["close"]
        mid = (a + b) / 2.0
        s = (b - a) / mid * 10_000.0  # positive => Hyperliquid more expensive
        signed_bps.append(s)
        abs_bps.append(abs(s))
        spread_dollars.append(b - a)
        if s > 0:
            bybit_cheaper += 1
        elif s < 0:
            hl_cheaper += 1

    sorted_signed = sorted(signed_bps)
    sorted_abs = sorted(abs_bps)
    mid_prices = [((da[ts]["close"] + db[ts]["close"]) / 2.0) for ts in common]

    # Conservative default fee assumptions for one round trip (open + close, taker/taker).
    # These are not used as trading advice; they are a benchmark for break-even analysis.
    fee_assumptions = {
        "bybit_taker_pct": 0.00055,
        "hyperliquid_taker_pct": 0.00045,
    }
    roundtrip_bps = 2.0 * (fee_assumptions["bybit_taker_pct"] + fee_assumptions["hyperliquid_taker_pct"]) * 10_000.0
    open_bps = (fee_assumptions["bybit_taker_pct"] + fee_assumptions["hyperliquid_taker_pct"]) * 10_000.0

    thresh_stats = {}
    for th in threshold_bps:
        flags = [x >= th for x in sorted_abs]
        lengths = run_lengths(flags)
        thresh_stats[str(th)] = {
            "share": sum(flags) / len(flags),
            "count": sum(flags),
            "max_run": max(lengths) if lengths else 0,
            "avg_run": (sum(lengths) / len(lengths)) if lengths else 0.0,
        }

    return {
        "aligned_count": len(common),
        "bybit_count": len(bybit.rows),
        "hyperliquid_count": len(hl.rows),
        **aligned,
        "signed_bps": {
            "mean": statistics.fmean(signed_bps),
            "median": statistics.median(signed_bps),
            "p05": percentile(sorted_signed, 0.05),
            "p25": percentile(sorted_signed, 0.25),
            "p75": percentile(sorted_signed, 0.75),
            "p95": percentile(sorted_signed, 0.95),
            "min": sorted_signed[0],
            "max": sorted_signed[-1],
            "stdev": statistics.pstdev(signed_bps),
        },
        "abs_bps": {
            "mean": statistics.fmean(abs_bps),
            "median": statistics.median(abs_bps),
            "p90": percentile(sorted_abs, 0.90),
            "p95": percentile(sorted_abs, 0.95),
            "p99": percentile(sorted_abs, 0.99),
            "max": sorted_abs[-1],
        },
        "direction": {
            "bybit_cheaper_share": bybit_cheaper / len(common),
            "hyperliquid_cheaper_share": hl_cheaper / len(common),
        },
        "thresholds": thresh_stats,
        "fee_benchmark": {
            "bybit_taker_pct": fee_assumptions["bybit_taker_pct"],
            "hyperliquid_taker_pct": fee_assumptions["hyperliquid_taker_pct"],
            "open_bps": open_bps,
            "roundtrip_bps": roundtrip_bps,
        },
        "sample_mid": {
            "first": mid_prices[0],
            "last": mid_prices[-1],
        },
    }


def fmt_pct(v: float, digits: int = 2) -> str:
    return f"{v * 100:.{digits}f}%"


def fmt_bps(v: float, digits: int = 2) -> str:
    return f"{v:.{digits}f} bps"


def summarize_coin(coin: str, bybit_symbol: str, bybit_series: Series, hl_series: Series, stats: dict[str, Any]) -> str:
    lines = []
    lines.append(f"## {coin}")
    lines.append(f"- Bybit symbol: `{bybit_symbol}`")
    lines.append(f"- Hyperliquid symbol: `{coin}`")
    lines.append(f"- Overlap: {stats['aligned_count']:,} aligned 1m candles")
    lines.append(f"- Bybit range: {bybit_series.meta.get('actual_start')} → {bybit_series.meta.get('actual_end')} ({bybit_series.meta['count']:,} candles)")
    lines.append(f"- Hyperliquid range: {hl_series.meta.get('actual_start')} → {hl_series.meta.get('actual_end')} ({hl_series.meta['count']:,} candles)")
    lines.append(f"- Coverage on common span: Bybit {pct(stats['coverage_a']):.1f}%, Hyperliquid {pct(stats['coverage_b']):.1f}%")
    lines.append(f"- Directional bias: Bybit cheaper {pct(stats['direction']['bybit_cheaper_share']):.1f}%, Hyperliquid cheaper {pct(stats['direction']['hyperliquid_cheaper_share']):.1f}%")
    lines.append(
        f"- Signed spread (HL - Bybit): mean {fmt_bps(stats['signed_bps']['mean'])}, median {fmt_bps(stats['signed_bps']['median'])}, p95 {fmt_bps(stats['signed_bps']['p95'])}, min {fmt_bps(stats['signed_bps']['min'])}, max {fmt_bps(stats['signed_bps']['max'])}"
    )
    lines.append(
        f"- Absolute spread: mean {fmt_bps(stats['abs_bps']['mean'])}, median {fmt_bps(stats['abs_bps']['median'])}, p95 {fmt_bps(stats['abs_bps']['p95'])}, p99 {fmt_bps(stats['abs_bps']['p99'])}, max {fmt_bps(stats['abs_bps']['max'])}"
    )
    lines.append(
        f"- Conservative fee benchmark: open ~{fmt_bps(stats['fee_benchmark']['open_bps'])} one-way, round-trip ~{fmt_bps(stats['fee_benchmark']['roundtrip_bps'])} (taker/taker assumption)"
    )
    for th, s in stats["thresholds"].items():
        lines.append(
            f"- |spread| ≥ {th} bps: {pct(s['share']):.2f}% of minutes, max run {s['max_run']} min, avg run {s['avg_run']:.1f} min"
        )
    return "\n".join(lines)


def build_report(results: list[dict[str, Any]], days: int, start: datetime, end: datetime) -> str:
    lines = []
    lines.append(f"# Bybit ↔ Hyperliquid arbitrage analysis")
    lines.append("")
    lines.append(f"- Window: {start.isoformat()} → {end.isoformat()} ({days} days requested)")
    lines.append("- Resolution: 1m close prices")
    lines.append("- Strategy tested: long cheaper exchange / short more expensive exchange")
    lines.append("- Costs modeled: fees only (no funding, no slippage, no transfer cost)")
    lines.append("- Notes: ZEC has no Bybit USDC perp; Bybit ZECUSDT was used as the closest liquid perpetual proxy.")
    lines.append("")
    lines.append("## Quick take")
    for r in results:
        thresholds = r["stats"].get("thresholds", {})
        s20 = thresholds.get("20.0")
        if s20:
            lines.append(
                f"- {r['coin']}: share above ~20 bps round-trip threshold = {pct(s20['share']):.2f}%, max run {s20['max_run']} min"
            )
        else:
            lines.append(f"- {r['coin']}: no valid overlap / threshold stats unavailable")
    lines.append("")
    for r in results:
        lines.append(summarize_coin(r["coin"], r["bybit_symbol"], r["bybit_series"], r["hl_series"], r["stats"]))
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Analyze Bybit vs Hyperliquid arb opportunities")
    ap.add_argument("--days", type=int, default=180, help="Lookback window in days (default: 180)")
    ap.add_argument("--output", default="reports/bybit_hyperliquid_arbitrage.md", help="Report output path")
    ap.add_argument("--json-output", default="reports/bybit_hyperliquid_arbitrage.json", help="JSON output path")
    ap.add_argument("--workers", type=int, default=1, help="Concurrent fetch workers")
    args = ap.parse_args()

    # Hyperliquid archival files are the limiting factor for overlap, so we anchor
    # the window to the latest timestamp common to all requested HL markets.
    hl_latest_end_ms = min(hyperliquid_latest_end_ms(coin) for coin in HL_COINS.values())
    end = datetime.fromtimestamp(hl_latest_end_ms / 1000, tz=timezone.utc)
    start = end - timedelta(days=args.days)
    start_ms = ms(start)
    end_ms = ms(end)

    tasks = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for coin, bybit_symbol in BYBIT_SYMBOLS.items():
            tasks.append(
                (
                    coin,
                    bybit_symbol,
                    ex.submit(fetch_bybit_symbol, bybit_symbol, start_ms, end_ms),
                    ex.submit(fetch_hyperliquid_symbol, HL_COINS[coin], start_ms, end_ms),
                )
            )

        results = []
        for coin, bybit_symbol, bybit_future, hl_future in tasks:
            bybit_series = bybit_future.result()
            hl_series = hl_future.result()
            stats = stats_for_pair(bybit_series, hl_series, threshold_bps=[5.0, 10.0, 15.0, 20.0, 25.0, 30.0])
            results.append(
                {
                    "coin": coin,
                    "bybit_symbol": bybit_symbol,
                    "bybit_series": bybit_series,
                    "hl_series": hl_series,
                    "stats": stats,
                }
            )

    report = build_report(results, args.days, start, end)
    payload = {
        "window": {"start": start.isoformat(), "end": end.isoformat(), "days": args.days},
        "results": [
            {
                "coin": r["coin"],
                "bybit_symbol": r["bybit_symbol"],
                "bybit_meta": r["bybit_series"].meta,
                "hl_meta": r["hl_series"].meta,
                "stats": r["stats"],
            }
            for r in results
        ],
    }

    # Write outputs.
    from pathlib import Path

    out_path = Path(args.output)
    out_json = Path(args.json_output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

    print(report)
    print(f"\nSaved report to {out_path}")
    print(f"Saved JSON to {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
