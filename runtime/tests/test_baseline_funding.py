from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from coinmaster.research.native_baseline import funding_with_prior_minute_marks


def write(table, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(table), path)


def test_funding_wiring_requires_the_prior_closed_minute_mark(tmp_path) -> None:
    root = tmp_path / "data"
    for symbol in ("BTCUSDT", "SOLUSDT"):
        write([{"open_time_ms": 60_000, "close": "100"}], root / "normalized" / f"bybit-{symbol}-mark-1m.parquet")
        write([{"funding_time_ms": 120_000, "funding_rate": "0.01"}], root / "normalized" / f"bybit-{symbol}-funding.parquet")
    events = funding_with_prior_minute_marks(root)
    assert len(events) == 2 and all(event.basis == "venue_mark_prior_minute" for event in events)
    (root / "normalized" / "bybit-SOLUSDT-mark-1m.parquet").unlink()
    with pytest.raises(FileNotFoundError):
        funding_with_prior_minute_marks(root)
