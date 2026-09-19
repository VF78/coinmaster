# Nautilus MVP — coordinator checkpoint

Current: P0 complete locally; P1 native accounting is next.
Decision: new isolated `runtime/` package, CPython >=3.12,<3.13, `nautilus_trader==1.231.0`; legacy execution is not imported.
Implemented: immutable public Bybit BTCUSDT/SOLUSDT and Hyperliquid meta snapshots, SHA-256 manifest, explicit account/historical-data unknowns, and hash-validation test.
Evidence: `runtime/var/venue-manifest.json`; raw payloads collected read-only 2026-09-19 UTC. Bybit has 8h funding interval; HL payload establishes BTC 40x/SOL 20x public maxima only.
Tested: `uv lock --check`; `uv sync --group dev`; CPython 3.12.13; `nautilus=1.231.0`; both adapters expose funding plus `QueryAccount`/`AccountState`; `.venv/bin/python -m pytest -q` (1 passed).
Assumed: snapshot collection timestamp is the task date because exchange payloads do not provide a collection timestamp; public maxima are not margin tiers or account eligibility.
VPS read-only inventory: `coinmaster.service` inactive; Docker active with unrelated gateway/postgres/VPN containers; no production action taken.
Blockers: account fee/margin/risk tiers, limits, actual funding/mark historical coverage and USDT↔USDC conversion cannot be verified without further data collection/account evidence; no keys were requested or read.
Correction used: declared Hatch wheel package explicitly after editable build initially could not discover `coinmaster/`.
Next: P1 native BacktestEngine BTC+SOL manual-money fixture using one Nautilus lifecycle; first prove native funding/account events or document a minimal supported SimulationModule.
Safety: no legacy engines, deployments, VPS changes, orders, transfers, or live activation were run.
