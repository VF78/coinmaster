from pathlib import Path
from decimal import Decimal

from coinmaster.venues.profiles import load_manifest
from coinmaster.venues.bybit_profile import BybitVenueProfile


ROOT = Path(__file__).resolve().parents[1]


def test_public_snapshots_are_immutable_and_gaps_explicit() -> None:
    manifest = load_manifest(ROOT)
    assert {item["venue"] for item in manifest["profiles"]} == {"bybit", "hyperliquid"}
    assert all(profile["unknowns"] for profile in manifest["profiles"])
    bybit = next(item for item in manifest["profiles"] if item["venue"] == "bybit")
    assert {instrument["symbol"] for instrument in bybit["instruments"]} == {"BTCUSDT", "SOLUSDT"}


def test_captured_bybit_profile_loads_full_btc_and_sol_tiers() -> None:
    profile = BybitVenueProfile.from_raw(ROOT)
    assert len(profile.tiers["BTCUSDT"]) == len(profile.tiers["SOLUSDT"]) == 35
    assert profile.tier_for("BTCUSDT",  Decimal("300000")).im == Decimal("0.0066")
    assert profile.tier_for("SOLUSDT", Decimal("50000")).im == Decimal("0.01")
