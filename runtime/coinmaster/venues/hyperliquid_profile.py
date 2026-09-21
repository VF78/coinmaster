"""Production-facing, evidence-bound Hyperliquid BTC/SOL perpetual profile.

The profile is intentionally independent from research/native_fixture and the
Bybit tier module.  It is a fail-closed input to a future production adapter,
not authorization to construct a node, connect a wallet, or submit orders.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from coinmaster.venues.production_preflight import MarginTier, ProductionInstrument, ProductionVenuePreflight


VENUE = "HYPERLIQUID"
COLLATERAL_CURRENCY = "USDC"
ACCOUNT_CURRENCY = "USDC"
BTC_PERP_ID = "BTC-USD-PERP.HYPERLIQUID"
SOL_PERP_ID = "SOL-USD-PERP.HYPERLIQUID"


@dataclass(frozen=True)
class HyperliquidFeeSchedule:
    """Configured account rates; public base rates are defaults, not assumed facts."""
    maker: Decimal = Decimal("0.00015")
    taker: Decimal = Decimal("0.00045")

    def __post_init__(self) -> None:
        if self.maker < Decimal("-1") or self.taker < 0:
            raise ValueError("INVALID_HYPERLIQUID_FEE_RATE")


@dataclass(frozen=True)
class Evidence:
    source: str
    collected_at: str
    sha256: str


@dataclass(frozen=True)
class NormalizedFundingEvent:
    event_id: str
    instrument_id: str
    settlement_ns: int
    rate: Decimal
    settlement_mark: Decimal


def normalize_funding_event(*, instrument_id: str, settlement_ns: int, rate: Decimal, settlement_mark: Decimal | None) -> NormalizedFundingEvent:
    """Return a rate-independent, venue-native settlement identity.

    Hyperliquid pays funding hourly.  A rate alone is never a settlement cash
    event, therefore missing causal mark evidence is rejected rather than
    borrowing a Bybit mark or manufacturing an event.
    """
    if instrument_id not in {BTC_PERP_ID, SOL_PERP_ID}:
        raise ValueError("UNKNOWN_HYPERLIQUID_INSTRUMENT")
    if settlement_ns <= 0 or settlement_mark is None or settlement_mark <= 0:
        raise ValueError("UNCONFIRMED_HYPERLIQUID_SETTLEMENT_MARK")
    return NormalizedFundingEvent(
        event_id=f"hyperliquid:{instrument_id}:{settlement_ns}",
        instrument_id=instrument_id,
        settlement_ns=settlement_ns,
        rate=Decimal(rate),
        settlement_mark=Decimal(settlement_mark),
    )


class HyperliquidVenueProfile:
    """Current public metadata plus explicit facts that public metadata omits."""

    def __init__(self, *, evidence: Evidence, fees: HyperliquidFeeSchedule = HyperliquidFeeSchedule()) -> None:
        self.evidence = evidence
        self.fees = fees
        self.instruments = {
            BTC_PERP_ID: ProductionInstrument(
                BTC_PERP_ID, Decimal("0.00001"), Decimal("0.00001"), Decimal("10"), 1, 5,
                Decimal("30000000"), Decimal("300000000"),
                (MarginTier(Decimal("0"), Decimal("40")), MarginTier(Decimal("150000000"), Decimal("20"))),
            ),
            SOL_PERP_ID: ProductionInstrument(
                SOL_PERP_ID, Decimal("0.01"), Decimal("0.01"), Decimal("10"), 4, 5,
                Decimal("5000000"), Decimal("50000000"),
                (MarginTier(Decimal("0"), Decimal("20")), MarginTier(Decimal("70000000"), Decimal("10"))),
            ),
        }
        self.preflight = ProductionVenuePreflight(self.instruments)
        self.unknowns = (
            "Account-selected leverage, cross/isolated mode, collateral and open positions require authenticated account evidence.",
            "Effective maker/taker fee tier, referral, staking, and market-maker rebate require userFees evidence.",
            "Public meta is current-only; it does not establish historical applicability.",
            "No verified 24-month Hyperliquid BBO/L2 history is available here; do not substitute Bybit data.",
        )

    @classmethod
    def from_snapshot(cls, root: Path, *, fees: HyperliquidFeeSchedule = HyperliquidFeeSchedule()) -> "HyperliquidVenueProfile":
        path = root / "var/raw/venues/hyperliquid-production-meta-2026-09-21.json"
        raw = path.read_bytes()
        snapshot = json.loads(raw)
        evidence = Evidence(snapshot["source"], snapshot["collected_at"], hashlib.sha256(raw).hexdigest())
        profile = cls(evidence=evidence, fees=fees)
        expected = {
            "BTC": (5, Decimal("40"), 56),
            "SOL": (2, Decimal("20"), 54),
        }
        observed = {row["name"]: (row["szDecimals"], Decimal(str(row["maxLeverage"])), row["marginTableId"]) for row in snapshot["response"]["universe"] if row["name"] in expected}
        expected_tiers = {
            54: ((Decimal("0"), Decimal("20")), (Decimal("70000000"), Decimal("10"))),
            56: ((Decimal("0"), Decimal("40")), (Decimal("150000000"), Decimal("20"))),
        }
        observed_tiers = {
            int(table_id): tuple((Decimal(str(tier["lowerBound"])), Decimal(str(tier["maxLeverage"]))) for tier in table["marginTiers"])
            for table_id, table in snapshot["response"]["marginTables"]
            if int(table_id) in expected_tiers
        }
        if observed != expected or observed_tiers != expected_tiers or snapshot["response"].get("collateralToken") != 0:
            raise ValueError("HYPERLIQUID_PROFILE_SNAPSHOT_MISMATCH")
        return profile
