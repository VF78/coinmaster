"""Public provider normalization for default BTC/SOL USDC linear contracts.

Only denomination changes: IDs, numeric constraints, ticks, sizes, timestamps and
stockzero rates/fees remain. This is not an FX conversion or private cache patch.
"""
from decimal import Decimal
from functools import lru_cache
from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.model.instruments import CryptoPerpetual
from nautilus_trader.adapters.hyperliquid.providers import HyperliquidInstrumentProvider
from nautilus_trader.adapters.hyperliquid.data import HyperliquidDataClient
from nautilus_trader.adapters.hyperliquid.factories import get_cached_hyperliquid_http_client,_resolve_environment,_resolve_product_types
from nautilus_trader.live.factories import LiveDataClientFactory

TARGET_IDS=frozenset({'BTC-USD-PERP.HYPERLIQUID','SOL-USD-PERP.HYPERLIQUID'})
POLICY='HL_DEFAULT_BTC_SOL_LINEAR_USDC_DENOMINATION_V1'


def normalize_unified_instrument_dict(values):
    if values.get('id') not in TARGET_IDS:return dict(values)
    if (values.get('type')!='CryptoPerpetual' or values.get('settlement_currency')!='USDC'
        or values.get('quote_currency') not in ('USD','USDC') or values.get('is_inverse') is not False
        or values.get('base_currency') not in ('BTC','SOL')):
        raise ValueError('UNIFIED_INSTRUMENT_CONTRACT_UNSUPPORTED')
    if any(Decimal(str(values.get(key)))!=0 for key in ('margin_init','margin_maint','maker_fee','taker_fee')):
        raise ValueError('UNIFIED_STOCKZERO_RATES_REQUIRED')
    result=dict(values);result['quote_currency']='USDC'
    for name in ('min_notional','max_notional'):
        value=result.get(name)
        if value is None:continue
        if not isinstance(value,str):raise ValueError('UNIFIED_NOTIONAL_DENOMINATION_UNKNOWN')
        parts=value.rsplit(' ',1)
        if len(parts)!=2 or parts[1] not in ('USD','USDC'):raise ValueError('UNIFIED_NOTIONAL_CURRENCY_UNSUPPORTED')
        number=Decimal(parts[0])
        if not number.is_finite() or number<0:raise ValueError('UNIFIED_NOTIONAL_CONSTRAINT_INVALID')
        result[name]=parts[0]+' USDC'  # Same number, actual settlement denomination.
    return result


def normalize_unified_pyo3_instrument(instrument):
    values=instrument.to_dict()
    if values.get('id') not in TARGET_IDS:return instrument
    return nautilus_pyo3.CryptoPerpetual.from_dict(normalize_unified_instrument_dict(values))


def normalize_unified_legacy_instrument(instrument):
    values=CryptoPerpetual.to_dict(instrument) if isinstance(instrument,CryptoPerpetual) else None
    if values is None or values.get('id') not in TARGET_IDS:return instrument
    return CryptoPerpetual.from_dict(normalize_unified_instrument_dict(values))


class UnifiedHyperliquidInstrumentProvider(HyperliquidInstrumentProvider):
    """All public load/refresh paths rebuild both provider representations."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._unified_pyo3=[]

    async def _load_instruments(self):
        legacy=await super()._load_instruments()
        native=[normalize_unified_pyo3_instrument(item) for item in super().instruments_pyo3()]
        normalized=[normalize_unified_legacy_instrument(item) for item in legacy]
        self._unified_pyo3=native
        return normalized

    def instruments_pyo3(self):
        return list(self._unified_pyo3)


@lru_cache(maxsize=16)
def get_unified_instrument_provider(client,config,product_types):
    return UnifiedHyperliquidInstrumentProvider(client=client,config=config,product_types=product_types)


class UnifiedHyperliquidDataClientFactory(LiveDataClientFactory):
    @staticmethod
    def create(loop,name,config,msgbus,cache,clock):
        client=get_cached_hyperliquid_http_client(timeout_secs=config.http_timeout_secs,
            environment=_resolve_environment(config.environment),proxy_url=config.proxy_url)
        provider=get_unified_instrument_provider(client,config.instrument_provider,_resolve_product_types(config.product_types))
        return HyperliquidDataClient(loop=loop,client=client,msgbus=msgbus,cache=cache,clock=clock,
            instrument_provider=provider,config=config,name=name)
