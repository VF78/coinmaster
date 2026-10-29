"""Shared, fail-closed public-candle slice of the VPS Hyperliquid IP budget.

All API workers use the existing GUI state directory. A first-use/recreated
bucket starts full for 60s so a restart/deletion cannot mint request capacity.
Persisted monotonic timestamps survive process restarts on the same host boot;
a backwards clock (including an OS reboot) fails closed for manual review.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from coinmaster.api.hl_public_candles import INTERVAL_MS, MAX_CANDLES, _post, public_candles

CAPACITY = 150
WINDOW_NS = 60_000_000_000
CACHE_TTL_NS = 5_000_000_000
LEASE_NS = 30_000_000_000
MAX_CACHE_ENTRIES = 12
MAX_STATE_BYTES = 4 * 1024 * 1024


def candle_weight(rows: int) -> int:
    return 20 + math.ceil(rows / 60)


class CandleBudgetUnavailable(Exception):
    pass


def _boot_identity() -> str:
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


class PublicCandleBudget:
    def __init__(self, state_dir: Path, *, post: Callable[[dict[str, Any]], Any] = _post,
                 clock: Callable[[], int] = time.monotonic_ns,
                 wall_clock: Callable[[], int] = lambda: time.time_ns() // 1_000_000,
                 boot_id: Callable[[], str] = _boot_identity) -> None:
        self.path = Path(state_dir) / "hl-public-candles.json"
        self.lock_path = Path(state_dir) / "hl-public-candles.lock"
        self.post, self.clock, self.wall_clock, self.boot_id = post, clock, wall_clock, boot_id

    @contextmanager
    def _locked(self):
        # Separate stable lock inode: replacing the JSON must not replace a lock.
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)

    def _read(self, now: int) -> dict[str, Any]:
        boot_id = self.boot_id()
        if not isinstance(boot_id, str) or not 1 <= len(boot_id) <= 128:
            raise CandleBudgetUnavailable("CANDLE_BUDGET_BOOT_ID_UNAVAILABLE")
        if not self.path.exists():
            state = {"version": 2, "boot_id": boot_id, "fault": None, "last_ns": now,
                     "charges": [{"id": "INITIAL_CONSERVATIVE_HOLD", "at_ns": now, "weight": CAPACITY}],
                     "pending": {}, "cache": {}}
            self._write(state)
            return state
        if self.path.is_symlink() or self.path.stat().st_size > MAX_STATE_BYTES:
            raise CandleBudgetUnavailable("CANDLE_BUDGET_STATE_INVALID")
        state = json.loads(self.path.read_text(), parse_constant=lambda _v: (_ for _ in ()).throw(ValueError()))
        if not isinstance(state, dict):
            raise CandleBudgetUnavailable("CANDLE_BUDGET_STATE_INVALID")
        digest = state.pop("sha256", None)
        canonical = json.dumps(state, separators=(",", ":"), sort_keys=True, allow_nan=False).encode()
        if not isinstance(digest, str) or hashlib.sha256(canonical).hexdigest() != digest:
            raise CandleBudgetUnavailable("CANDLE_BUDGET_STATE_CHECKSUM_INVALID")
        if (set(state) != {"version", "boot_id", "fault", "last_ns", "charges", "pending", "cache"}
                or type(state["version"]) is not int or state["version"] != 2 or type(state["last_ns"]) is not int
                or state["boot_id"] != boot_id or state["fault"] is not None
                or state["last_ns"] < 0 or not isinstance(state["charges"], list)
                or len(state["charges"]) > CAPACITY or not isinstance(state["pending"], dict)
                or len(state["pending"]) > MAX_CACHE_ENTRIES or not isinstance(state["cache"], dict)
                or len(state["cache"]) > MAX_CACHE_ENTRIES):
            raise CandleBudgetUnavailable("CANDLE_BUDGET_STATE_INVALID")
        if state["last_ns"] > now:
            state["fault"] = "CANDLE_BUDGET_CLOCK_REVERSED"
            self._write(state)
            raise CandleBudgetUnavailable("CANDLE_BUDGET_CLOCK_REVERSED")
        for charge in state["charges"]:
            if (not isinstance(charge, dict) or set(charge) != {"id", "at_ns", "weight"}
                    or not isinstance(charge["id"], str) or type(charge["at_ns"]) is not int
                    or not 0 <= charge["at_ns"] <= now or type(charge["weight"]) is not int
                    or not 20 <= charge["weight"] <= CAPACITY):
                raise CandleBudgetUnavailable("CANDLE_BUDGET_STATE_INVALID")
        for value in state["pending"].values():
            if (not isinstance(value, dict) or set(value) != {"id", "expires_ns"}
                    or not isinstance(value["id"], str) or type(value["expires_ns"]) is not int):
                raise CandleBudgetUnavailable("CANDLE_BUDGET_STATE_INVALID")
        for key, value in state["cache"].items():
            if (not isinstance(key, str) or not isinstance(value, dict) or set(value) != {"at_ns", "payload"}
                    or type(value["at_ns"]) is not int or not 0 <= value["at_ns"] <= now
                    or not isinstance(value["payload"], dict)
                    or value["payload"].get("quote_currency") != "USDC"
                    or not isinstance(value["payload"].get("candles"), list)
                    or len(value["payload"]["candles"]) > MAX_CANDLES):
                raise CandleBudgetUnavailable("CANDLE_BUDGET_STATE_INVALID")
        state["charges"] = [entry for entry in state["charges"] if now - entry["at_ns"] < WINDOW_NS]
        state["pending"] = {key: value for key, value in state["pending"].items() if value["expires_ns"] > now}
        state["last_ns"] = now
        return state

    def _write(self, state: dict[str, Any]) -> None:
        canonical = json.dumps(state, separators=(",", ":"), sort_keys=True, allow_nan=False).encode()
        data = json.dumps({**state, "sha256": hashlib.sha256(canonical).hexdigest()},
                          separators=(",", ":"), sort_keys=True, allow_nan=False).encode()
        if len(data) > MAX_STATE_BYTES:
            raise CandleBudgetUnavailable("CANDLE_BUDGET_STATE_TOO_LARGE")
        fd, name = tempfile.mkstemp(prefix=".hl-candles-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(name, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    @staticmethod
    def _unavailable(coin: str, interval: str, reason: str, cached: dict | None = None) -> dict:
        if cached and cached["payload"].get("candles"):
            return {**cached["payload"], "state": "STALE", "reason": reason}
        return {"version": "hl-public-candles-v1", "venue": "HYPERLIQUID",
                "environment": "mainnet-public", "source": "OFFICIAL_INFO_CANDLE_SNAPSHOT",
                "execution_evidence": False, "coin": coin, "quote_currency": "USDC", "interval": interval,
                "state": "UNAVAILABLE", "observed_at_ms": None, "latest_closed_at_ms": None,
                "candles": [], "reason": reason}

    def request(self, coin: str, interval: str, limit: int) -> dict[str, Any]:
        if coin not in {"BTC", "SOL"} or interval not in INTERVAL_MS or type(limit) is not int or not 1 <= limit <= MAX_CANDLES:
            raise ValueError("CANDLE_REQUEST_SCOPE_INVALID")
        key = f"{coin}:{interval}:{limit}"
        token = uuid.uuid4().hex
        cache = None
        try:
            now = self.clock()
            if type(now) is not int or now < 0:
                raise CandleBudgetUnavailable("CANDLE_BUDGET_CLOCK_INVALID")
            with self._locked():
                state = self._read(now)
                cache = state["cache"].get(key)
                if cache and now - cache["at_ns"] < CACHE_TTL_NS:
                    return cache["payload"]
                if key in state["pending"]:
                    return self._unavailable(coin, interval, "PUBLIC_CANDLES_REQUEST_IN_FLIGHT", cache)
                # The exact closed-time request spans limit rows inclusively.
                # Verify this from its actual body again before calling HTTP.
                reserve = candle_weight(limit)
                if sum(entry["weight"] for entry in state["charges"]) + reserve > CAPACITY:
                    self._write(state)
                    return self._unavailable(coin, interval, "PUBLIC_CANDLE_BUDGET_EXHAUSTED", cache)
                state["charges"].append({"id": token, "at_ns": now, "weight": reserve})
                state["pending"][key] = {"id": token, "expires_ns": now + LEASE_NS}
                self._write(state)
        except (OSError, ValueError, TypeError, KeyError, CandleBudgetUnavailable):
            return self._unavailable(coin, interval, "PUBLIC_CANDLE_BUDGET_UNAVAILABLE")

        raw_rows = None
        posted = False
        def prepaid_post(body):
            nonlocal raw_rows, posted
            if posted:
                raise ValueError("CANDLE_REPEATED_POST_FORBIDDEN")
            request = body["req"]
            inclusive_rows = (request["endTime"] - request["startTime"]) // INTERVAL_MS[interval] + 1
            if inclusive_rows != limit or candle_weight(inclusive_rows) > reserve:
                raise ValueError("CANDLE_REQUEST_RESERVATION_MISMATCH")
            # Rebind the durable debit immediately before the actual POST;
            # time spent waiting/suspended after admission must not age it out.
            started = self.clock()
            with self._locked():
                state = self._read(started)
                pending = state["pending"].get(key)
                charge = next((entry for entry in state["charges"] if entry["id"] == token), None)
                if not pending or pending["id"] != token or charge is None:
                    raise ValueError("CANDLE_RESERVATION_EXPIRED")
                charge["at_ns"] = started
                self._write(state)
            posted = True
            raw = self.post(body)  # No file lock is held across this HTTP.
            if isinstance(raw, list):
                raw_rows = len(raw)  # Count raw rows before any filtering/slicing.
            return raw

        try:
            result = public_candles(coin, interval, limit, now_ms=self.wall_clock(), post=prepaid_post)
        except Exception:
            result = self._unavailable(coin, interval, "PUBLIC_INFO_UNAVAILABLE")
        try:
            now = self.clock()
            with self._locked():
                state = self._read(now)
                # Refund only a successfully parsed, validated response (including
                # a known empty list). Malformed/HTTP failures keep all prepaid weight.
                valid = result["state"] in {"READY", "STALE"} or result.get("reason") == "NO_PUBLIC_CANDLES"
                if valid and raw_rows is not None and raw_rows <= limit:
                    for entry in state["charges"]:
                        if entry["id"] == token:
                            entry["weight"] = candle_weight(raw_rows)
                pending = state["pending"].get(key)
                if pending and pending["id"] == token:
                    del state["pending"][key]
                    if valid:
                        state["cache"][key] = {"at_ns": now, "payload": result}
                        while len(state["cache"]) > MAX_CACHE_ENTRIES:
                            del state["cache"][min(state["cache"], key=lambda item: state["cache"][item]["at_ns"])]
                self._write(state)
        except (OSError, ValueError, TypeError, KeyError, CandleBudgetUnavailable):
            # Reservation is already durable. Failure to settle cannot mint a refund.
            return self._unavailable(coin, interval, "PUBLIC_CANDLE_BUDGET_UNAVAILABLE")
        if result["state"] not in {"READY", "STALE"} and cache:
            return self._unavailable(coin, interval, result["reason"], cache)
        return result
