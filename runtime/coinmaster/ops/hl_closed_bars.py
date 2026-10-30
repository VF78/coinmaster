"""Normalize stock 1.231.0 HL OPEN-stamped bars at the native input boundary.

WS emits the previous closed candle on period change; ts_init is its native
receipt. HTTP stamps both fields OPEN, so retain our actual response receipt.
No engine, transport, feature formula, or clock arithmetic is replaced.
"""
from nautilus_trader.adapters.hyperliquid.data import HyperliquidDataClient
from nautilus_trader.adapters.hyperliquid.factories import (
    get_cached_hyperliquid_http_client, get_cached_hyperliquid_instrument_provider,
    _resolve_environment, _resolve_product_types,
)
from nautilus_trader.live.factories import LiveDataClientFactory
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import BarAggregation
from coinmaster.ops.venue_data import binding_for_execution


def normalize_hl_bar(bar, *, received_ns, historical=False):
    if not isinstance(bar, Bar):
        return bar
    if str(bar.bar_type.instrument_id.venue) != "HYPERLIQUID":
        raise ValueError("HL_BAR_SOURCE_MISMATCH")
    spec = bar.bar_type.spec
    units = {BarAggregation.MINUTE: 60_000_000_000, BarAggregation.DAY: 86_400_000_000_000}
    if spec.step != 1 or spec.aggregation not in units:
        raise ValueError("HL_BAR_INTERVAL_UNSUPPORTED")
    span = units[spec.aggregation]
    close = bar.ts_event + span
    init = received_ns if historical else bar.ts_init
    if bar.ts_event % span or not close <= init <= received_ns:
        raise ValueError("HL_BAR_UNCLOSED_OR_RECEIPT_INVALID")
    return Bar(bar.bar_type, bar.open, bar.high, bar.low, bar.close, bar.volume, close, init)


class ClosedHyperliquidDataClient(HyperliquidDataClient):
    def _handle_data(self, data):
        if isinstance(data, Bar):
            data = normalize_hl_bar(data, received_ns=self._clock.timestamp_ns())
        return super()._handle_data(data)

    def _handle_bars(self, bar_type, bars, correlation_id, start, end, params):
        received = self._clock.timestamp_ns()
        bars = [normalize_hl_bar(bar, received_ns=received, historical=True) for bar in bars]
        return super()._handle_bars(bar_type, bars, correlation_id, start, end, params)


class ClosedHyperliquidDataClientFactory(LiveDataClientFactory):
    unified = False

    @classmethod
    def create(cls, loop, name, config, msgbus, cache, clock):
        client = get_cached_hyperliquid_http_client(timeout_secs=config.http_timeout_secs,
            environment=_resolve_environment(config.environment), proxy_url=config.proxy_url)
        products = _resolve_product_types(config.product_types)
        if cls.unified:
            from coinmaster.ops.hl_unified_instruments import get_unified_instrument_provider
            provider = get_unified_instrument_provider(client, config.instrument_provider, products)
        else:
            provider = get_cached_hyperliquid_instrument_provider(client, config.instrument_provider, products)
        binding_for_execution(tuple(sorted(config.instrument_provider.load_ids, key=str)))
        return ClosedHyperliquidDataClient(loop=loop, client=client, msgbus=msgbus, cache=cache,
            clock=clock, instrument_provider=provider, config=config, name=name)


class ClosedUnifiedHyperliquidDataClientFactory(ClosedHyperliquidDataClientFactory):
    unified = True
