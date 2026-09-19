"""Explicit venue-mark data routed outside Nautilus matching.

Nautilus 1.231's backtest engine does not accept ``PriceType.MARK`` bars.
Marks are therefore modelled as ``CustomData``: they are available to a
strategy and risk modules, but cannot update the simulated order book or
produce fills.  Execution prices remain quote/trade data only.
"""
from __future__ import annotations

from decimal import Decimal

from nautilus_trader.core.data import Data
from nautilus_trader.model.data import CustomData, DataType
from nautilus_trader.model.identifiers import InstrumentId


class VenueMark(Data):
    """A captured venue mark, with event and availability timestamps in ns."""

    def __init__(self, instrument_id: InstrumentId, price: Decimal, ts_event: int, ts_init: int | None = None) -> None:
        self.instrument_id = instrument_id
        self.price = Decimal(price)
        self._ts_event = ts_event
        self._ts_init = ts_event if ts_init is None else ts_init

    @property
    def ts_event(self) -> int:
        return self._ts_event

    @property
    def ts_init(self) -> int:
        return self._ts_init


def venue_mark_data_type(instrument_id: InstrumentId) -> DataType:
    """Return the stable subscription key for one instrument's mark stream."""
    return DataType(VenueMark, {"instrument_id": str(instrument_id)})


def venue_mark(instrument_id: InstrumentId, price: Decimal, ts_event: int, ts_init: int | None = None) -> CustomData:
    """Wrap a mark as native ``CustomData`` for engine delivery."""
    return CustomData(
        venue_mark_data_type(instrument_id),
        VenueMark(instrument_id, price, ts_event, ts_init),
    )
