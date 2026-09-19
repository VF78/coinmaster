from pathlib import Path

from coinmaster.venues.profiles import load_manifest


ROOT = Path(__file__).resolve().parents[1]


def test_public_snapshots_are_immutable_and_gaps_explicit() -> None:
    manifest = load_manifest(ROOT)
    assert {item["venue"] for item in manifest["profiles"]} == {"bybit", "hyperliquid"}
    assert all(profile["unknowns"] for profile in manifest["profiles"])
    bybit = next(item for item in manifest["profiles"] if item["venue"] == "bybit")
    assert {instrument["symbol"] for instrument in bybit["instruments"]} == {"BTCUSDT", "SOLUSDT"}
