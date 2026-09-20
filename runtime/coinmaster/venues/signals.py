"""Non-matching captured daily signal bars for native research execution."""
from __future__ import annotations

from decimal import Decimal

from nautilus_trader.core.data import Data
from nautilus_trader.model.data import CustomData, DataType
from nautilus_trader.model.identifiers import InstrumentId


class DailySignalBar(Data):
    """Daily OHLC signal input; it never enters the simulated matching book."""
    def __init__(self, instrument_id: InstrumentId, open_: Decimal, high: Decimal, low: Decimal, close: Decimal, ts_event: int, ts_init: int | None = None) -> None:
        self.instrument_id, self.open, self.high, self.low, self.close = instrument_id, Decimal(open_), Decimal(high), Decimal(low), Decimal(close)
        self._ts_event, self._ts_init = ts_event, ts_event if ts_init is None else ts_init

    @property
    def ts_event(self) -> int:
        return self._ts_event

    @property
    def ts_init(self) -> int:
        return self._ts_init


def daily_signal_data_type(instrument_id: InstrumentId) -> DataType:
    return DataType(DailySignalBar, {"instrument_id": str(instrument_id)})


def daily_signal(instrument_id: InstrumentId, open_: Decimal, high: Decimal, low: Decimal, close: Decimal, ts_event: int, ts_init: int | None = None) -> CustomData:
    return CustomData(daily_signal_data_type(instrument_id), DailySignalBar(instrument_id, open_, high, low, close, ts_event, ts_init))
