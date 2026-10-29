"""Current account-effective primitive fractions; referral is already included."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class EffectiveFeeRates:
    maker: Decimal = Decimal("0.000144")
    taker: Decimal = Decimal("0.000432")
    source: str = "OWNER_VERIFIED_USERFEES_REFERRAL_ALREADY_APPLIED"

    def __post_init__(self):
        if any(not v.is_finite() or v < 0 or v >= 1 for v in (self.maker,self.taker)):
            raise ValueError("INVALID_EFFECTIVE_FEE_FRACTION")

    def reserve_taker(self, buffer):
        buffer=Decimal(buffer)
        if not buffer.is_finite() or buffer < 0:
            raise ValueError("INVALID_FEE_RESERVE_BUFFER")
        return max(self.taker,buffer)


CURRENT_HL_FEES=EffectiveFeeRates()
HL_FEE_RESERVE_BUFFER=Decimal("0.0005")


def effective_instrument_dict(values, rates=CURRENT_HL_FEES):
    result=dict(values)
    result.update(maker_fee=str(rates.maker),taker_fee=str(rates.taker))
    return result
