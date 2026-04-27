#!/usr/bin/env python3
"""Invariant checks for CoinMasterStrategy Freqtrade-native Radar policy bridge."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pandas as pd

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

print("\n── Strategy logic invariants ──")

fvg_df = pd.DataFrame([
    {"open": 96, "high": 100, "low": 95, "close": 98},
    {"open": 101, "high": 106, "low": 99, "close": 105},
    {"open": 112, "high": 116, "low": 110, "close": 114},
    {"open": 113, "high": 112, "low": 104, "close": 112},  # wick touches retrace band, close remains above
])
annotated = CoinMasterStrategy._annotate_fvg(
    fvg_df.copy(),
    lookback=5,
    retrace_pct=50,
    min_width_pct=1,
    require_sweep=False,
    sweep_lookback=3,
    require_first_touch=False,
    max_zone_age=10,
)
assert_true(int(annotated.loc[3, "fvg_dir"]) == 1, "FVG retrace accepts wick/range touch, not close-only")

with TemporaryDirectory() as tmpdir:
    path = Path(tmpdir) / "radar_policy.json"
    stake_strategy = strategy_with_policy(path)
    stake_strategy.wallets = SimpleNamespace(get_total_stake_amount=lambda: 1000.0)
    stake_strategy._runtime_strategy_params = {
        "coin_allocations": {"BTC/USDC:USDC": {"symbol": "BTC", "pct": 50}},
        "portfolio_gross_cap_enabled": True,
        "portfolio_gross_cap": 100,
        "risk_per_trade_enabled": False,
        "max_leverage_value": 2,
        "sl_pct": 2,
    }
    stake_strategy._open_gross_notional = lambda: 800.0
    stake = stake_strategy.custom_stake_amount(
        pair="BTC/USDC:USDC",
        current_time=datetime.now(timezone.utc),
        current_rate=100.0,
        proposed_stake=500.0,
        min_stake=None,
        max_stake=1000.0,
        leverage=2.0,
        entry_tag=None,
        side="long",
    )
    assert_true(abs(stake - 100.0) < 1e-9, "portfolio gross cap subtracts existing open notional before sizing new stake")

    time_strategy = strategy_with_policy(path)
    time_strategy._runtime_strategy_params = {
        "time_stop_enabled": True,
        "time_stop_bars": 2,
        "entry_timeframes": ["5m", "1h"],
    }
    opened = datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc)
    trade = SimpleNamespace(open_date_utc=opened, is_short=False)
    assert_true(time_strategy.custom_exit("BTC/USDC:USDC", trade, opened + timedelta(minutes=30), 100, -0.01) is None, "time stop uses selected primary entry timeframe, not hardcoded 5m")
    assert_true(time_strategy.custom_exit("BTC/USDC:USDC", trade, opened + timedelta(minutes=121), 100, -0.01) == "time_stop_no_follow_through", "time stop exits after configured higher-timeframe bars")

    bias_strategy = strategy_with_policy(path)
    bias_strategy._runtime_strategy_params = {"bias_policy": {"defaultBias": "long", "symbolOverrides": {"ETH": {"mode": "symbol", "bias": "short"}}}}
    assert_true(bias_strategy._side_enabled("BTC/USDC:USDC", "long") is True and bias_strategy._side_enabled("BTC/USDC:USDC", "short") is False, "default trading bias gates sides")
    assert_true(bias_strategy._side_enabled("ETH/USDC:USDC", "short") is True and bias_strategy._side_enabled("ETH/USDC:USDC", "long") is False, "symbol trading bias override gates sides")
    bias_strategy._runtime_strategy_params = {"bias_policy": {"defaultBias": "off", "symbolOverrides": {}}}
    assert_true(bias_strategy._side_enabled("BTC/USDC:USDC", "long") is False and bias_strategy._side_enabled("BTC/USDC:USDC", "short") is False, "off trading bias blocks both sides")

print(f"\nTOTAL: {passed + failed} | PASSED: {passed} | FAILED: {failed}")
if failed:
    raise SystemExit(1)
