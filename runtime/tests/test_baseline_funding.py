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


def test_funding_warmup_rows_are_excluded_before_captured_mark_window(tmp_path) -> None:
    root = tmp_path / "data"
    for symbol in ("BTCUSDT", "SOLUSDT"):
        write([{"open_time_ms": 60_000, "close": "100"}], root / "normalized" / f"bybit-{symbol}-mark-1m.parquet")
        write([{"funding_time_ms": 0, "funding_rate": "0.01"}, {"funding_time_ms": 120_000, "funding_rate": "0.01"}], root / "normalized" / f"bybit-{symbol}-funding.parquet")
    events = funding_with_prior_minute_marks(root, start_settlement_ms=0, end_settlement_ms=180_000)
    assert len(events) == 2


def test_funding_short_window_streams_full_source_without_full_mark_table(tmp_path, monkeypatch) -> None:
    from coinmaster.research import native_baseline

    root = tmp_path / "data"
    for symbol in ("BTCUSDT", "SOLUSDT"):
        write([{"open_time_ms": minute * 60_000, "close": str(100 + minute)} for minute in range(10)], root / "normalized" / f"bybit-{symbol}-mark-1m.parquet")
        write([{"funding_time_ms": minute * 60_000, "funding_rate": "0.01"} for minute in (2, 3)], root / "normalized" / f"bybit-{symbol}-funding.parquet")

    original_read = pq.read_table
    def guarded_read(path, *args, **kwargs):
        assert "-mark-1m.parquet" not in str(path), "full mark table must not be materialized"
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(pq, "read_table", guarded_read)

    cursors = []
    original_cursor = native_baseline.ParquetMinuteCursor
    class CapturingCursor(original_cursor):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            cursors.append(self)
    monkeypatch.setattr(native_baseline, "ParquetMinuteCursor", CapturingCursor)

    events = funding_with_prior_minute_marks(root, start_settlement_ms=60_000, end_settlement_ms=240_000)
    assert len(events) == 4
    assert sorted(str(event.settlement_mark) for event in events) == ["101", "101", "102", "102"]
    assert all(cursor.rows_seen == 3 and cursor.peak_buffer_rows <= 3 for cursor in cursors)
