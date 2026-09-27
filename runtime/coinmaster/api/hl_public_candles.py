"""Bounded public Hyperliquid candles for read-only operator market context."""
from __future__ import annotations

import json
import time
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

INFO_URL = "https://api.hyperliquid.xyz/info"
INTERVAL_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000,
               "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
MAX_CANDLES = 500
MAX_BODY = 350_000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _post(body: dict[str, Any]) -> Any:
    request = urllib.request.Request(
        INFO_URL, data=json.dumps(body, separators=(",", ":")).encode(), method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.build_opener(_NoRedirect).open(request, timeout=3) as response:
        if response.status != 200 or "application/json" not in response.headers.get("Content-Type", ""):
            raise ValueError("CANDLE_HTTP_RESPONSE_INVALID")
        raw = response.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY:
            raise ValueError("CANDLE_BODY_TOO_LARGE")
    return json.loads(raw)


def _decimal(value: object, *, positive: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError("CANDLE_DECIMAL_INVALID")
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("CANDLE_DECIMAL_INVALID") from error
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise ValueError("CANDLE_DECIMAL_INVALID")
    return value


def public_candles(
    coin: str, interval: str, limit: int, *,
    now_ms: int | None = None, post: Callable[[dict[str, Any]], Any] = _post,
) -> dict[str, Any]:
    """Return completed official Info candles, never inferred venue executions."""
    if coin not in {"BTC", "SOL"} or interval not in INTERVAL_MS or type(limit) is not int or not 1 <= limit <= MAX_CANDLES:
        raise ValueError("CANDLE_REQUEST_SCOPE_INVALID")
    now_ms = time.time_ns() // 1_000_000 if now_ms is None else now_ms
    if type(now_ms) is not int or now_ms < 0:
        raise ValueError("CANDLE_CLOCK_INVALID")
    duration = INTERVAL_MS[interval]
    last_end = now_ms // duration * duration - 1
    start = last_end + 1 - limit * duration
    result = {
        "version": "hl-public-candles-v1", "venue": "HYPERLIQUID",
        "environment": "mainnet-public", "source": "OFFICIAL_INFO_CANDLE_SNAPSHOT",
        "execution_evidence": False, "coin": coin, "interval": interval,
        "state": "UNAVAILABLE", "observed_at_ms": None, "latest_closed_at_ms": None,
        "candles": [], "reason": "NO_PUBLIC_CANDLES",
    }
    if start < 0:
        return result
    body = {"type": "candleSnapshot", "req": {
        "coin": coin, "interval": interval, "startTime": start, "endTime": last_end,
    }}
    try:
        raw = post(body)
    except (OSError, TimeoutError):
        return {**result, "reason": "PUBLIC_INFO_UNAVAILABLE"}
    except (ValueError, TypeError):
        return {**result, "state": "INVALID", "reason": "PUBLIC_INFO_INVALID"}
    if not isinstance(raw, list) or len(raw) > limit:
        return {**result, "state": "INVALID", "reason": "CANDLE_RESPONSE_INVALID"}
    candles = []
    prior_t = -1
    try:
        for row in raw:
            if not isinstance(row, dict) or set(row) != {"T", "c", "h", "i", "l", "n", "o", "s", "t", "v"}:
                raise ValueError("CANDLE_ROW_SHAPE_INVALID")
            opened, closed = row["t"], row["T"]
            if (type(opened) is not int or type(closed) is not int or type(row["n"]) is not int
                    or row["n"] < 0 or row["s"] != coin or row["i"] != interval
                    or opened < start or closed > last_end or opened % duration
                    or closed != opened + duration - 1 or opened <= prior_t):
                raise ValueError("CANDLE_ROW_TIME_OR_IDENTITY_INVALID")
            prices = {field: Decimal(_decimal(row[field], positive=True)) for field in ("o", "h", "l", "c")}
            _decimal(row["v"])
            if prices["h"] < max(prices["o"], prices["c"]) or prices["l"] > min(prices["o"], prices["c"]) or prices["l"] > prices["h"]:
                raise ValueError("CANDLE_OHLC_INVALID")
            candles.append({
                "open_time_ms": opened, "close_time_ms": closed, "open": row["o"],
                "high": row["h"], "low": row["l"], "close": row["c"],
                "volume": row["v"], "trades": row["n"],
            })
            prior_t = opened
    except (ValueError, TypeError, KeyError):
        return {**result, "state": "INVALID", "reason": "CANDLE_RESPONSE_INVALID"}
    if not candles:
        return result
    latest = candles[-1]["close_time_ms"]
    fresh = last_end - latest < 2 * duration
    return {
        **result, "state": "READY" if fresh else "STALE",
        "observed_at_ms": now_ms, "latest_closed_at_ms": latest,
        "candles": candles, "reason": None if fresh else "PUBLIC_CANDLES_STALE",
    }
