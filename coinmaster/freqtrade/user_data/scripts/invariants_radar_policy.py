#!/usr/bin/env python3
"""Invariant checks for CoinMasterStrategy Freqtrade-native Radar policy bridge."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, "/freqtrade/user_data")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from strategies.CoinMasterStrategy import CoinMasterStrategy

passed = 0
failed = 0


def assert_true(condition: bool, label: str) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ {label}")
    else:
        failed += 1
        print(f"  ✗ FAIL: {label}", file=sys.stderr)


def write_policy(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)


def future(minutes: int = 15) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def past(minutes: int = 15) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def strategy_with_policy(path: Path) -> CoinMasterStrategy:
    CoinMasterStrategy.radar_policy_path = path
    CoinMasterStrategy.fallback_radar_policy_path = path.with_name("missing-fallback.json")
    strategy = CoinMasterStrategy({"timeframe": "5m", "stake_currency": "USDC"})
    strategy._refresh_radar_policy(force=True)
    return strategy


print("\n── Radar policy invariants ──")

with TemporaryDirectory() as tmpdir:
    path = Path(tmpdir) / "radar_policy.json"

    missing = strategy_with_policy(path)
    assert_true(missing._radar_effective_policy("BTC/USDC:USDC", "long")["allowed"] is True, "missing policy is neutral/allowed")
    assert_true(missing._radar_effective_policy("BTC/USDC:USDC", "long")["risk_multiplier"] == 1.0, "missing policy multiplier is 1.0")

    write_policy(path, {"schema_version": 1, "valid_until": past(), "global": {"enabled": True, "mode": "off"}})
    stale = strategy_with_policy(path)
    assert_true(stale._radar_effective_policy("BTC/USDC:USDC", "long")["allowed"] is True, "stale policy is ignored/neutral")

    write_policy(path, {"schema_version": 999, "valid_until": future(), "global": {"enabled": True, "mode": "off"}})
    invalid = strategy_with_policy(path)
    assert_true(invalid._radar_effective_policy("BTC/USDC:USDC", "long")["allowed"] is True, "invalid policy is ignored/neutral")

    write_policy(path, {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "valid_until": future(),
        "global": {"enabled": True, "mode": "both", "risk_multiplier": 1.0, "lock_new_entries": True, "reason": "kill_switch"},
        "pairs": {},
    })
    blocked_global = strategy_with_policy(path)
    eff = blocked_global._radar_effective_policy("BTC/USDC:USDC", "long")
    assert_true(eff["allowed"] is False and eff["code"] == "radar_block_global", "global lock blocks entries")

    write_policy(path, {
        "schema_version": 1,
        "valid_until": future(),
        "global": {"enabled": True, "mode": "both", "risk_multiplier": 1.0, "reason": "normal"},
        "pairs": {"BTC/USDC:USDC": {"mode": "off", "risk_multiplier": 0, "reason": "pair_off"}},
    })
    blocked_pair = strategy_with_policy(path)
    eff = blocked_pair._radar_effective_policy("BTC/USDC:USDC", "long")
    assert_true(eff["allowed"] is False and eff["code"] == "radar_block_pair", "pair mode=off blocks entries")

    write_policy(path, {
        "schema_version": 1,
        "valid_until": future(),
        "global": {"enabled": True, "mode": "long_only", "risk_multiplier": 1.0, "reason": "bullish"},
        "pairs": {},
    })
    direction = strategy_with_policy(path)
    assert_true(direction._radar_effective_policy("ETH/USDC:USDC", "long")["allowed"] is True, "long_only allows long")
    eff = direction._radar_effective_policy("ETH/USDC:USDC", "short")
    assert_true(eff["allowed"] is False and eff["code"] == "radar_direction_mismatch", "long_only blocks short")

    write_policy(path, {
        "schema_version": 1,
        "valid_until": future(),
        "global": {"enabled": True, "mode": "both", "risk_multiplier": 1.2, "reason": "clamped"},
        "pairs": {"HYPE/USDC:USDC": {"mode": "both", "risk_multiplier": 0.5, "reason": "mixed"}},
    })
    multiplier = strategy_with_policy(path)
    eff = multiplier._radar_effective_policy("HYPE/USDC:USDC", "long")
    assert_true(eff["allowed"] is True and eff["risk_multiplier"] == 0.5, "risk multiplier reduces stake and clamps global >1")

print(f"\nTOTAL: {passed + failed} | PASSED: {passed} | FAILED: {failed}")
if failed:
    raise SystemExit(1)
