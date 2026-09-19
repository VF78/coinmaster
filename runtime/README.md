# CoinMaster Nautilus runtime

This package is the paper-first replacement runtime.  Legacy Freqtrade, JS
execution, and `backtest_v1` are intentionally not imported.

P0 pins CPython 3.12 and NautilusTrader 1.231.0. `var/raw/venues/` contains
immutable public REST payloads collected on 2026-09-19 UTC; `var/venue-manifest.json`
records their hashes and explicit gaps.  They are current public snapshots, not
historical fee, margin-tier, or account evidence.

```sh
uv sync --group dev
uv run pytest
```

The next slice must use Nautilus native account/events as the only source of
trading money. Do not use this module as an order-execution adapter yet.
