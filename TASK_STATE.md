# Nautilus MVP — coordinator checkpoint

Current: P0 partial: P0.1 verified/closed; P0.2 data completeness remains open. P1 native accounting may proceed only with manual fixtures.
Decision: new isolated `runtime/` package, CPython >=3.12,<3.13, `nautilus_trader==1.231.0`; legacy execution is not imported.
Implemented: immutable public Bybit BTCUSDT/SOLUSDT and Hyperliquid meta snapshots, SHA-256 manifest, explicit account/historical-data unknowns, and hash-validation test.
Evidence: `runtime/var/venue-manifest.json`; raw payloads have real UTC capture timestamps. Bybit has 8h funding interval and public tiers; HL payload establishes BTC 40x/SOL 20x public maxima only.
Tested: `uv lock --check`; `uv sync --group dev`; CPython 3.12.13; `nautilus=1.231.0`; both adapters expose funding plus `QueryAccount`/`AccountState`; `.venv/bin/python -m pytest -q` (1 passed).
Assumed: public maxima are not account eligibility; native event behavior still needs a P1 execution fixture.
VPS read-only inventory: `coinmaster.service` inactive; Docker active with unrelated gateway/postgres/VPN containers; no production action taken.
Coverage: required interval is [2024-09-01, 2026-09-01), warmup starts 2022-09-02. Bybit boundary probes exist for BTC/SOL mark+funding, but gap-free coverage is UNVERIFIED. HL has funding and nonzero-volume candles at research start; its warmup funding is empty and candle provenance remains unverified, not a standalone funding blocker while flat.
Blockers: account fee/margin/risk tiers, limits, complete price/funding history and USDT↔USDC conversion cannot be verified without further data collection/account evidence; no keys were requested or read.
Correction used: declared Hatch wheel package explicitly after editable build initially could not discover `coinmaster/`.
Next: P1 native BacktestEngine BTC+SOL manual-money fixture using one Nautilus lifecycle; first prove native funding/account events or document a minimal supported SimulationModule.
Safety: no legacy engines, deployments, VPS changes, orders, transfers, or live activation were run.
