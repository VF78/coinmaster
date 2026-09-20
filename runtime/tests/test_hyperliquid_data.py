import json

from coinmaster.research.hyperliquid_data import DAY_MS, HOUR_MS, _save, normalize_candles, normalize_funding, write_raw


def test_normalization_keeps_nontrading_prices_and_never_invents_funding(tmp_path) -> None:
    root, symbol = tmp_path, "BTC"
    candle_start, candle_end = 0, 2 * DAY_MS
    candle_raw = write_raw(root / "hyperliquid" / symbol, "candle", {"type": "candleSnapshot"}, [
        {"t": 0, "T": DAY_MS - 1, "o": "1", "h": "2", "l": "1", "c": "2", "v": "0", "n": 0},
        {"t": DAY_MS, "T": 2 * DAY_MS - 1, "o": "2", "h": "3", "l": "2", "c": "3", "v": "4", "n": 7},
    ])
    _save(root / "hyperliquid" / symbol / "candle-1d.progress.json", {"stream": "candleSnapshot_1d", "start_ms": candle_start, "end_ms": candle_end, "next_start_ms": candle_end, "raw": [{**candle_raw, "rows": 2}], "completed": True})
    daily = normalize_candles(symbol, root)
    assert daily["rows"] == daily["expected"] == 2
    assert daily["missing_count"] == daily["duplicate_count"] == 0
    assert daily["proxy_prices_nontrading_count"] == 1

    funding_start, funding_end = 0, 3 * HOUR_MS
    funding_raw = write_raw(root / "hyperliquid" / symbol, "funding", {"type": "fundingHistory"}, [
        {"time": 12, "fundingRate": "0.001", "premium": "0.002"},
        {"time": HOUR_MS + 12, "fundingRate": "0.003", "premium": "0.004"},
    ])
    _save(root / "hyperliquid" / symbol / "funding.progress.json", {"stream": "fundingHistory", "start_ms": funding_start, "end_ms": funding_end, "next_start_ms": funding_end, "raw": [{**funding_raw, "rows": 2}], "completed": True})
    funding = normalize_funding(symbol, root)
    assert funding["rows"] == 2
    assert funding["missing_count"] == 1
    assert funding["settlement_oracle"] == "UNKNOWN_FREE_REST_HAS_NO_SETTLEMENT_ORACLE"
    rows = json.loads(json.dumps(funding))
    assert rows["rows"] != rows["expected_hourly"]  # no synthetic zero-rate row
