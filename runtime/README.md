# CoinMaster Nautilus runtime

This package is the active Nautilus paper-first runtime. Legacy Freqtrade, JS
execution, and `backtest_v1` are historical references and intentionally not
imported.

P0 pins CPython 3.12 and NautilusTrader 1.231.0. `var/raw/venues/` contains
immutable public REST payloads with source and real UTC capture timestamps;
`var/venue-manifest.json` records their hashes, boundary probes, and explicit
gaps. They are current public snapshots, not complete historical or account
evidence.

```sh
uv sync --group dev
uv run pytest
```

The deployed paper worker uses public Bybit/Hyperliquid data and exactly one
native `SandboxExecutionClient`; `live_order_capability=false` is invariant.
Runtime operations are documented in [`ops/PAPER_RUNBOOK.md`](ops/PAPER_RUNBOOK.md).
The SQLite doctor is read-only and its successful result is not live approval:

```sh
.venv/bin/python scripts/paper_doctor.py /var/lib/coinmaster-paper/paper.sqlite
```

Export the frontend contract deterministically (without binding a port):

```sh
.venv/bin/python scripts/export_openapi.py
```
