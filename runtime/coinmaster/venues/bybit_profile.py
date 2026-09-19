"""Immutable validated profile from captured public Bybit risk-limit payloads."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class Tier:
    cap: Decimal
    im: Decimal
    mm: Decimal
    deduction: Decimal
    max_leverage: Decimal


@dataclass(frozen=True)
class BybitVenueProfile:
    tiers: dict[str, tuple[Tier, ...]]
    hashes: dict[str, str]

    @classmethod
    def from_raw(cls, root: Path) -> "BybitVenueProfile":
        tiers: dict[str, tuple[Tier, ...]] = {}
        hashes: dict[str, str] = {}
        manifest = json.loads((root / "var/venue-manifest.json").read_text())
        expected_hashes = {
            Path(item["path"]).name: item["sha256"]
            for item in manifest["snapshots"]
            if item["path"].endswith("-risk-limit.json")
        }
        for symbol in ("BTCUSDT", "SOLUSDT"):
            path = root / "var/raw/venues" / f"bybit-{symbol}-risk-limit.json"
            raw = path.read_bytes()
            hashes[symbol] = hashlib.sha256(raw).hexdigest()
            if hashes[symbol] != expected_hashes.get(path.name):
                raise ValueError(f"raw profile hash is not manifest-validated: {symbol}")
            rows = json.loads(raw)["result"]["list"]
            try:
                parsed = tuple(
                    Tier(
                        Decimal(row["riskLimitValue"]), Decimal(row["initialMargin"]),
                        Decimal(row["maintenanceMargin"]), Decimal(row["mmDeduction"] or "0"),
                        Decimal(row["maxLeverage"]),
                    )
                    for row in rows
                )
            except (KeyError, ValueError) as error:
                raise ValueError(f"invalid tier fields: {symbol}") from error
            if (
                len(parsed) != 35
                or any(row.get("symbol") != symbol for row in rows)
                or any(
                    tier.cap <= 0 or tier.im <= 0 or tier.mm < 0 or tier.deduction < 0
                    or tier.max_leverage <= 0 or tier.mm > tier.im
                    for tier in parsed
                )
                or any(a.cap >= b.cap for a, b in zip(parsed, parsed[1:]))
            ):
                raise ValueError(f"invalid ordered tiers: {symbol}")
            tiers[symbol] = parsed
        return cls(tiers, hashes)

    def tier_for(self, symbol: str, notional: Decimal) -> Tier:
        for tier in self.tiers.get(symbol, ()):
            if notional <= tier.cap:
                return tier
        raise ValueError(f"unknown or out-of-range tier: {symbol}")
