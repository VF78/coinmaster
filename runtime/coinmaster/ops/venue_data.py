"""Execution-derived LIVE data contract. Research Bybit artifacts remain separate.

No account APIs: HL history is the public candleSnapshot, not mark/funding or
execution history. Only the leading pre-activity zero-volume/zero-trade prefix
is excluded, jointly across BTC/SOL. Interior zero-trade days are retained.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import uuid
import fcntl
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from nautilus_trader.model.data import BarType, BarSpecification
from nautilus_trader.model.enums import AggregationSource, BarAggregation, PriceType
from nautilus_trader.model.identifiers import InstrumentId

DAY_MS = 86_400_000
HL_SCHEMA = "coinmaster-hyperliquid-candle-warmup-v1"
HL_ENDPOINT = "https://api.hyperliquid.xyz/info"


def _hash(data):
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class VenueDataBinding:
    venue: str
    signal_ids: tuple
    timestamp_basis: str

    @property
    def policy(self):
        return f"LIVE_{self.venue}_TRADE_D1_M1_CLOSE_UTC_H4_H1_ACTUAL_AVAILABILITY_V2"

    @property
    def identity(self):
        return _hash(json.dumps(dict(venue=self.venue, ids=list(map(str, self.signal_ids)),
            timestamp_basis=self.timestamp_basis, policy=self.policy), sort_keys=True).encode())

    def bar_type(self, index, *, minute=False):
        return BarType(self.signal_ids[index], BarSpecification(1,
            BarAggregation.MINUTE if minute else BarAggregation.DAY, PriceType.LAST), AggregationSource.EXTERNAL)

    def load(self, path, *, now_ms=None):
        if self.venue == "HYPERLIQUID":
            return load_hl_warmup(path, binding=self, now_ms=now_ms)
        from coinmaster.ops.stage_g_warmup import load_stageg_bybit_warmup
        return load_stageg_bybit_warmup(path, now_ms=now_ms)

    def refresh(self, root, *, now_ms=None):
        if self.venue == "HYPERLIQUID":
            return refresh_hl_warmup(root, binding=self, now_ms=now_ms)
        from coinmaster.ops.stage_g_refresh import refresh_stageg_warmup
        return refresh_stageg_warmup(root, now_ms=now_ms)


def binding_for_execution(ids):
    ids = tuple(ids)
    if len(ids) != 2 or len({str(i.venue) for i in ids}) != 1:
        raise ValueError("LIVE_EXECUTION_DATA_VENUE_INCONSISTENT")
    venue = str(ids[0].venue)
    expected = {
        "HYPERLIQUID": ("BTC-USD-PERP.HYPERLIQUID", "SOL-USD-PERP.HYPERLIQUID"),
        "BYBIT": ("BTCUSDT-LINEAR.BYBIT", "SOLUSDT-LINEAR.BYBIT"),
    }
    if venue not in expected or tuple(map(str, ids)) != expected[venue]:
        raise ValueError("LIVE_EXECUTION_DATA_VENUE_UNSUPPORTED")
    return VenueDataBinding(venue, ids, "OPEN" if venue == "HYPERLIQUID" else "CLOSE")


def public_hl_candles(coin, interval, start_ms, end_ms):
    body = json.dumps({"type": "candleSnapshot", "req": {"coin": coin,
        "interval": interval, "startTime": start_ms, "endTime": end_ms}}).encode()
    request = Request(HL_ENDPOINT, data=body, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=30) as response:
        raw = response.read()
    received_ms = int(datetime.now(UTC).timestamp() * 1000)
    rows = json.loads(raw)
    if not isinstance(rows, list) or not rows:
        raise ValueError("HL_CANDLE_HISTORY_EMPTY")
    return raw, received_ms


def _daily_rows(raw, coin, today_ms):
    payload = json.loads(raw)
    if not isinstance(payload, list) or not payload:
        raise ValueError("HL_CANDLE_HISTORY_EMPTY")
    rows = []
    previous = None
    active = False
    for item in payload:
        t = int(item["t"])
        if item["s"] != coin or item["i"] != "1d" or t % DAY_MS:
            raise ValueError("HL_DAILY_SOURCE_INVALID")
        if previous is not None and t != previous + DAY_MS:
            raise ValueError("HL_DAILY_GAP_DUPLICATE_OR_REORDER")
        previous = t
        if int(item["T"]) != t + DAY_MS - 1:
            raise ValueError("HL_DAILY_END_INVALID")
        values = tuple(float(item[k]) for k in ("o", "h", "l", "c", "v"))
        o, h, l, c, v = values
        n = int(item["n"])
        if (any(not math.isfinite(x) for x in values) or not 0 < l <= min(o,c) <= max(o,c) <= h
            or v < 0 or n < 0):
            raise ValueError("HL_DAILY_VALUES_INVALID")
        if t >= today_ms:
            continue  # Public API can include the current incomplete day.
        active = active or v > 0 or n > 0
        if active:
            rows.append(dict(open_time_ms=t, open=item["o"], high=item["h"], low=item["l"],
                close=item["c"], volume=item["v"], trades=n))
    if len(rows) < 730 or int(rows[-1]["open_time_ms"]) + DAY_MS != today_ms:
        raise ValueError("HL_DAILY_INSUFFICIENT_OR_STALE")
    return rows


def _paired_rows(raws, today_ms):
    rows = {coin: _daily_rows(raws[coin], coin, today_ms) for coin in ("BTC", "SOL")}
    start = max(int(rows[coin][0]["open_time_ms"]) for coin in rows)
    rows = {coin: tuple(r for r in values if r["open_time_ms"] >= start) for coin, values in rows.items()}
    if len(rows["BTC"]) < 730 or [r["open_time_ms"] for r in rows["BTC"]] != [r["open_time_ms"] for r in rows["SOL"]]:
        raise ValueError("HL_DAILY_PAIRED_COVERAGE_INVALID")
    return rows


def load_hl_warmup(path, *, binding, now_ms=None):
    try:
        now_ms = int(datetime.now(UTC).timestamp() * 1000) if now_ms is None else now_ms
        today = now_ms // DAY_MS * DAY_MS
        manifest = json.loads(path.read_bytes())
        if (manifest["schema"] != HL_SCHEMA or manifest["venue"] != binding.venue
            or manifest["binding_sha256"] != binding.identity or manifest["source_policy"] != binding.policy
            or manifest["endpoint"] != HL_ENDPOINT or manifest["warmup_end_exclusive_ms"] != today):
            raise ValueError("HL_WARMUP_IDENTITY_OR_SESSION_MISMATCH")
        raws = {}
        for coin in ("BTC", "SOL"):
            item = manifest["raw"][coin]
            if item["path"] != coin + "-1d.json" or item["received_ms"] < today or item["received_ms"] > now_ms:
                raise ValueError("HL_WARMUP_PROVENANCE_INVALID")
            raw = (path.parent / item["path"]).read_bytes()
            if _hash(raw) != item["sha256"]:
                raise ValueError("HL_WARMUP_RAW_HASH_MISMATCH")
            raws[coin] = raw
        rows = _paired_rows(raws, today)
        if manifest["warmup_start_ms"] != rows["BTC"][0]["open_time_ms"] or manifest["completed_sessions"] != len(rows["BTC"]):
            raise ValueError("HL_WARMUP_COVERAGE_MISMATCH")
        # Internal feature adapter keys retain established BTC/SOL slot names;
        # source identities are exclusively in the binding and raw manifest.
        return {"BTCUSDT": rows["BTC"], "SOLUSDT": rows["SOL"]}, "READY"
    except (OSError, KeyError, TypeError, ValueError):
        return {}, "MISSING_OR_INVALID_HYPERLIQUID_WARMUP"


def refresh_hl_warmup(root, *, binding, now_ms=None, fetch=public_hl_candles):
    root = Path(root)
    if root.name != "hyperliquid":
        raise ValueError("HL_WARMUP_SOURCE_SPECIFIC_ROOT_REQUIRED")
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve(strict=True)
    now_ms = int(datetime.now(UTC).timestamp() * 1000) if now_ms is None else now_ms
    today = now_ms // DAY_MS * DAY_MS
    with (root / ".refresh.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        pointer = root / "current"
        if pointer.exists():
            current = (pointer / "manifest.json").resolve(strict=True)
            if current.parent.parent != root:
                raise ValueError("HL_WARMUP_POINTER_OUTSIDE_ROOT")
            if load_hl_warmup(current, binding=binding, now_ms=now_ms)[1] == "READY":
                return pointer / "manifest.json"
        raw, provenance = {}, {}
        for coin in ("BTC", "SOL"):
            raw[coin], received = fetch(coin, "1d", 0, today - 1)
            provenance[coin] = dict(path=coin + "-1d.json", sha256=_hash(raw[coin]), received_ms=received)
        paired = _paired_rows(raw, today)
        manifest = dict(schema=HL_SCHEMA, venue=binding.venue, binding_sha256=binding.identity,
            source_policy=binding.policy, endpoint=HL_ENDPOINT, raw=provenance,
            warmup_start_ms=paired["BTC"][0]["open_time_ms"], warmup_end_exclusive_ms=today,
            completed_sessions=len(paired["BTC"]), leading_pre_activity_policy="PAIRED_MAX_FIRST_ACTIVE_ONLY",
            timestamp_basis="OPEN_PLUS_INTERVAL_CLOSE;ACTUAL_HTTP_RECEIPT",
            usage="LIVE_FEATURE_ONLY_NOT_EXECUTION_MARK_OR_FUNDING_HISTORY")
        content = json.dumps(manifest, sort_keys=True, indent=2).encode() + b"\n"
        destination = root / ("hl-daily-" + str(today) + "-" + _hash(content)[:16])
        staging = root / (".staging-" + uuid.uuid4().hex)
        staging.mkdir()
        for coin in raw:
            (staging / provenance[coin]["path"]).write_bytes(raw[coin])
        (staging / "manifest.json").write_bytes(content)
        # Validate against actual receipt as well as caller's cutoff. A delayed
        # response across midnight cannot promote stale history.
        validated_now = max(now_ms, *(i["received_ms"] for i in provenance.values()))
        if load_hl_warmup(staging / "manifest.json", binding=binding, now_ms=validated_now)[1] != "READY":
            raise ValueError("HL_WARMUP_SUCCESSOR_INVALID")
        staging.rename(destination)
        temporary = root / (".current-" + uuid.uuid4().hex)
        temporary.symlink_to(destination.name, target_is_directory=True)
        os.replace(temporary, pointer)
        return pointer / "manifest.json"
