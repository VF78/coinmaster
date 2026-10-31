"""Frozen current HL rules on historical proxy prices; no network or account access."""
from dataclasses import dataclass,replace
from decimal import Decimal
import hashlib,json
from pathlib import Path
from nautilus_trader.model.instruments import CryptoPerpetual
from nautilus_trader.model.identifiers import InstrumentId
from coinmaster.ops.hl_unified_instruments import normalize_unified_legacy_instrument,TARGET_IDS
from coinmaster.venues.effective_fees import CURRENT_HL_FEES,effective_instrument_dict
from coinmaster.venues.hyperliquid_profile import HyperliquidVenueProfile,HyperliquidProfileEnvironment,Evidence,HyperliquidFeeSchedule
from coinmaster.venues.margin_policy import HyperliquidSandboxMarginPolicy

D=Decimal

@dataclass(frozen=True)
class CurrentHLDiagnostic:
    instruments: tuple
    profile: object
    selected_leverage: tuple
    evidence: dict

    def margin_policy(self,max_age_ns):
        return HyperliquidSandboxMarginPolicy(self.profile,dict(self.selected_leverage),max_age_ns)


def load_current_hl_diagnostic(inputs):
    inputs=Path(inputs)
    names=("native-btc-sol-raw.json","hyperliquid-meta-BTC-SOL-20261029.json","execution-profile-inputs.json")
    raw={name:(inputs/name).read_bytes() for name in names}
    hashes={name:hashlib.sha256(value).hexdigest() for name,value in raw.items()}
    meta=json.loads(raw[names[1]]);config=json.loads(raw[names[2]])
    if (config["accounting_currency"]!="USDC" or config["fee_rates"]!={"maker":str(CURRENT_HL_FEES.maker),"taker":str(CURRENT_HL_FEES.taker)}
        or config["selected_leverage"]!={"BTC":"40","SOL":"20"} or not config["referral_discount_already_applied"]):
        raise ValueError("CURRENT_HL_PROFILE_CONFIG_MISMATCH")
    rows={r["name"]:r for r in meta["universe"] if r["name"] in ("BTC","SOL")}
    expected={"BTC":(5,40,56),"SOL":(2,20,54)}
    if {k:(r["szDecimals"],r["maxLeverage"],r["marginTableId"]) for k,r in rows.items()}!=expected:
        raise ValueError("CURRENT_HL_META_CONSTRAINT_MISMATCH")
    tables={int(k):v for k,v in meta["marginTables"]}
    actual={key:tuple((D(str(t["lowerBound"])),D(str(t["maxLeverage"]))) for t in tables[key]["marginTiers"]) for key in (54,56)}
    if actual!={54:((D(0),D(20)),(D(70000000),D(10))),56:((D(0),D(40)),(D(150000000),D(20)))}:
        raise ValueError("CURRENT_HL_META_TIER_MISMATCH")
    evidence=Evidence("FROZEN_PUBLIC_MAINNET_META_20261029","2026-10-29T19:31:53Z",hashes[names[1]])
    profile=HyperliquidVenueProfile(environment=HyperliquidProfileEnvironment.MAINNET,evidence=evidence,fees=HyperliquidFeeSchedule(CURRENT_HL_FEES.maker,CURRENT_HL_FEES.taker))
    native=json.loads(raw[names[0]])
    if set(native)!=TARGET_IDS:raise ValueError("CURRENT_HL_NATIVE_INSTRUMENT_SET_MISMATCH")
    instruments=[]
    for coin in ("BTC","SOL"):
        key=coin+"-USD-PERP.HYPERLIQUID"
        base=normalize_unified_legacy_instrument(CryptoPerpetual.from_dict(native[key]))
        instrument=CryptoPerpetual.from_dict(effective_instrument_dict(CryptoPerpetual.to_dict(base)))
        if (str(instrument.quote_currency)!="USDC" or str(instrument.settlement_currency)!="USDC"
            or instrument.size_precision!=expected[coin][0] or instrument.min_notional.as_decimal()!=10):
            raise ValueError("CURRENT_HL_NATIVE_CONSTRAINT_MISMATCH")
        instruments.append(instrument)
    leverage=tuple((i.id,D(config["selected_leverage"][i.base_currency.code])) for i in instruments)
    return CurrentHLDiagnostic(tuple(instruments),profile,leverage,dict(input_sha256=hashes,configuration=config,
        economic_assumption="CURRENT_HL_USDC_RULES_ON_PINNED_BYBIT_PRICE_AND_FUNDING_PROXY",real_historical_hl_execution_proven=False))
