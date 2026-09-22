import json
from decimal import Decimal
from pathlib import Path

import pytest
from nautilus_trader.adapters.hyperliquid.config import HyperliquidDataClientConfig
from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.model.identifiers import InstrumentId

from coinmaster.venues.hyperliquid_profile import (
    ACCOUNT_CURRENCY,
    BTC_PERP_ID,
    COLLATERAL_CURRENCY,
    SOL_PERP_ID,
    HyperliquidFeeSchedule,
    HyperliquidProfileEnvironment,
    HyperliquidVenueProfile,
    normalize_funding_event,
)


ROOT = Path(__file__).resolve().parents[1]


def test_profile_is_evidence_bound_usdc_btc_sol_and_fee_configurable() -> None:
    profile = HyperliquidVenueProfile.from_snapshot(ROOT, environment=HyperliquidProfileEnvironment.MAINNET, fees=HyperliquidFeeSchedule(Decimal("0.00011"), Decimal("0.00031")))
    assert (COLLATERAL_CURRENCY, ACCOUNT_CURRENCY) == ("USDC", "USDC")
    assert profile.evidence.collected_at == "2026-09-21T23:33:17Z"
    assert len(profile.evidence.sha256) == 64
    assert profile.fees == HyperliquidFeeSchedule(Decimal("0.00011"), Decimal("0.00031"))
    assert profile.instruments[BTC_PERP_ID].quantity_increment == Decimal("0.00001")
    assert profile.instruments[SOL_PERP_ID].quantity_increment == Decimal("0.01")
    assert any("24-month Hyperliquid BBO/L2" in item for item in profile.unknowns)


@pytest.mark.parametrize(
    ("instrument_id", "price", "quantity", "leverage", "reason"),
    [
        (BTC_PERP_ID, "100000.0", "0.00010", "10", None),
        (BTC_PERP_ID, "100000.0", "0.00001", "10", "MIN_NOTIONAL"),
        (BTC_PERP_ID, "100000.0", "0.000011", "10", "QUANTITY_INCREMENT"),
        (BTC_PERP_ID, "100000.01", "0.00010", "10", "PRICE_DECIMALS"),
        (SOL_PERP_ID, "2.0123", "5.00", "10", None),
        (SOL_PERP_ID, "2.01234", "5.00", "10", "PRICE_DECIMALS"),
        (SOL_PERP_ID, "2.0", "0.01", "10", "MIN_NOTIONAL"),
    ],
)
def test_quantity_notional_and_price_boundaries(instrument_id, price, quantity, leverage, reason) -> None:
    profile = HyperliquidVenueProfile.from_snapshot(ROOT, environment=HyperliquidProfileEnvironment.MAINNET)
    result = profile.preflight.evaluate(
        instrument_id=instrument_id, price=Decimal(price), quantity=Decimal(quantity), selected_leverage=Decimal(leverage),
        order_type="market", available_collateral=Decimal("100000"),
    )
    assert result.reason == reason
    assert result.allowed is (reason is None)


def test_margin_preflight_uses_hyperliquid_tiers_and_never_assumes_account_state() -> None:
    profile = HyperliquidVenueProfile.from_snapshot(ROOT, environment=HyperliquidProfileEnvironment.MAINNET)
    no_account = profile.preflight.evaluate(
        instrument_id=BTC_PERP_ID, price=Decimal("100000"), quantity=Decimal("1"), selected_leverage=Decimal("20"), order_type="market",
    )
    assert no_account.reason == "ACCOUNT_COLLATERAL_UNKNOWN"
    tier_boundary = profile.preflight.evaluate(
        instrument_id=BTC_PERP_ID, price=Decimal("100000"), quantity=Decimal("1501"), selected_leverage=Decimal("40"), order_type="limit",
        available_collateral=Decimal("10000000"),
    )
    assert tier_boundary.reason == "LEVERAGE_EXCEEDS_MARGIN_TIER"
    sol = profile.preflight.evaluate(
        instrument_id=SOL_PERP_ID, price=Decimal("200"), quantity=Decimal("100"), selected_leverage=Decimal("20"), order_type="market",
        available_collateral=Decimal("2000"),
    )
    assert sol.allowed and sol.required_initial_margin == Decimal("1000") and sol.maintenance_margin == Decimal("500")


def test_normalized_hyperliquid_funding_identity_is_stable_and_requires_venue_mark() -> None:
    event = normalize_funding_event(
        environment=HyperliquidProfileEnvironment.MAINNET, instrument_id=BTC_PERP_ID, settlement_ns=1_700_000_000_000_000_000,
        rate=Decimal("0.0000125"), settlement_mark=Decimal("100000"),
    )
    assert event.event_id == f"hyperliquid:mainnet:{BTC_PERP_ID}:1700000000000000000"
    with pytest.raises(ValueError, match="UNCONFIRMED_HYPERLIQUID_SETTLEMENT_MARK"):
        normalize_funding_event(environment=HyperliquidProfileEnvironment.MAINNET, instrument_id=BTC_PERP_ID, settlement_ns=1, rate=Decimal("0"), settlement_mark=None)


def test_testnet_profile_uses_public_testnet_tiers_and_pinned_nautilus_ids() -> None:
    profile = HyperliquidVenueProfile.from_snapshot(ROOT, environment=HyperliquidProfileEnvironment.TESTNET)
    assert profile.environment is HyperliquidProfileEnvironment.TESTNET
    assert profile.evidence.collected_at == "2026-09-22T21:01:26Z"
    assert tuple(item.max_leverage for item in profile.instruments[BTC_PERP_ID].margin_tiers) == (Decimal("40"), Decimal("25"), Decimal("10"))
    assert tuple(item.max_leverage for item in profile.instruments[SOL_PERP_ID].margin_tiers) == (Decimal("10"),)
    assert HyperliquidDataClientConfig(environment=nautilus_pyo3.HyperliquidEnvironment.TESTNET).environment is nautilus_pyo3.HyperliquidEnvironment.TESTNET
    assert tuple(str(InstrumentId.from_str(item)) for item in (BTC_PERP_ID, SOL_PERP_ID)) == (BTC_PERP_ID, SOL_PERP_ID)


def test_testnet_preflight_obeys_testnet_margin_boundaries_and_order_limits() -> None:
    profile = HyperliquidVenueProfile.from_snapshot(ROOT, environment=HyperliquidProfileEnvironment.TESTNET)
    below_btc_boundary = profile.preflight.evaluate(
        instrument_id=BTC_PERP_ID, price=Decimal("100000"), quantity=Decimal("0.09999"), selected_leverage=Decimal("40"), order_type="market", available_collateral=Decimal("1000"),
    )
    assert below_btc_boundary.allowed
    at_btc_boundary = profile.preflight.evaluate(
        instrument_id=BTC_PERP_ID, price=Decimal("100000"), quantity=Decimal("0.0001"), position_notional_before=Decimal("9990"), selected_leverage=Decimal("40"), order_type="market", available_collateral=Decimal("1000"),
    )
    assert at_btc_boundary.reason == "LEVERAGE_EXCEEDS_MARGIN_TIER"
    sol = profile.preflight.evaluate(
        instrument_id=SOL_PERP_ID, price=Decimal("200"), quantity=Decimal("1"), selected_leverage=Decimal("20"), order_type="market", available_collateral=Decimal("1000"),
    )
    assert sol.reason == "LEVERAGE_EXCEEDS_MARGIN_TIER"
    over_limit = profile.preflight.evaluate(
        instrument_id=SOL_PERP_ID, price=Decimal("2000000"), quantity=Decimal("1.01"), selected_leverage=Decimal("10"), order_type="market", available_collateral=Decimal("10000000"),
    )
    assert over_limit.reason == "MAX_ORDER_NOTIONAL"


def test_profile_rejects_snapshot_environment_mismatch(tmp_path) -> None:
    target = tmp_path / "var/raw/venues"
    target.mkdir(parents=True)
    source = ROOT / "var/raw/venues/hyperliquid-testnet-production-meta-2026-09-22.json"
    payload = json.loads(source.read_text())
    payload["environment"] = "mainnet"
    (target / source.name).write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="HYPERLIQUID_PROFILE_SNAPSHOT_MISMATCH"):
        HyperliquidVenueProfile.from_snapshot(tmp_path, environment=HyperliquidProfileEnvironment.TESTNET)


def test_testnet_profile_rejects_invented_low_id_raw_margin_table(tmp_path) -> None:
    target = tmp_path / "var/raw/venues"
    target.mkdir(parents=True)
    source = ROOT / "var/raw/venues/hyperliquid-testnet-production-meta-2026-09-22.json"
    payload = json.loads(source.read_text())
    payload["response"]["marginTables"].append(
        [10, {"description": "fabricated", "marginTiers": [{"lowerBound": "0.0", "maxLeverage": 10}]}]
    )
    (target / source.name).write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="HYPERLIQUID_PROFILE_SYNTHESIZED_MARGIN_TABLE"):
        HyperliquidVenueProfile.from_snapshot(tmp_path, environment=HyperliquidProfileEnvironment.TESTNET)


def test_production_profile_does_not_import_research_fixture_or_bybit_policy() -> None:
    source = (ROOT / "coinmaster/venues/hyperliquid_profile.py").read_text() + (ROOT / "coinmaster/venues/production_preflight.py").read_text()
    assert "research.native_fixture" not in source
    assert "BybitTierMarginModule" not in source
    assert "bybit_profile" not in source
