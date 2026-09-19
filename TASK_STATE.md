# Nautilus MVP — coordinator checkpoint

Current: P0 partial (P0.1 verified/closed; P0.2 open). P1 native fixture has fills/funding/basic margin gate; durable ledger/reconciliation and tier deductions remain open.
Decision: new isolated `runtime/` package, CPython >=3.12,<3.13, `nautilus_trader==1.231.0`; legacy execution is not imported.
Implemented: immutable public Bybit BTCUSDT/SOLUSDT and Hyperliquid meta snapshots, SHA-256 manifest, explicit account/historical-data unknowns, and hash-validation test.
Evidence: `runtime/var/venue-manifest.json`; raw payloads have real UTC capture timestamps. Bybit has 8h funding interval and public tiers; HL payload establishes BTC 40x/SOL 20x public maxima only.
P1 evidence: `runtime/coinmaster/research/native_fixture.py` uses one native BacktestEngine with BTC/SOL perpetuals; 5 native fills, partial BTC reduce, SOL add and final closes reconcile to hand-calculated `15632.05 USDT` after fees.
Margin: native model gives BTC 80k/40 + SOL 80k/20 = 6k IM; an 1,100-SOL increase is fail-closed pre-submit against native free account balance. Reservations retain parent IM through partial fill until confirmed cancel.
Funding: a native FundingRateUpdate alone does not change account money in this pin. `PerpetualFundingModule` is a small supported SimulationModule using only `exchange.adjust_account`; signed, timed, duplicate-ID fixture posts `14346.303 USDT` and production events fail closed without confirmed venue settlement mark.
Tested: `uv lock --check`; `uv sync --group dev`; CPython 3.12.13; `nautilus=1.231.0`; adapters expose funding plus `QueryAccount`/`AccountState`; `.venv/bin/python -m pytest -q` (7 passed; Pandas deprecation warnings).
Assumed: public maxima are not account eligibility; real importer must normalize a stable venue funding ID and confirmed settlement mark.
VPS read-only inventory: `coinmaster.service` inactive; Docker active with unrelated gateway/postgres/VPN containers; no production action taken.
Coverage: required interval is [2024-09-01, 2026-09-01), warmup starts 2022-09-02. Bybit boundary probes exist for BTC/SOL mark+funding, but gap-free coverage is UNVERIFIED. HL has funding and nonzero-volume candles at research start; its warmup funding is empty and candle provenance remains unverified, not a standalone funding blocker while flat.
Blockers: account fee/margin/risk tiers, limits, complete price/funding history and USDT↔USDC conversion cannot be verified without further data collection/account evidence; no keys were requested or read.
Correction used: declared Hatch wheel package explicitly after editable build initially could not discover `coinmaster/`.
Next: implement durable native-event journal/restart reconciliation and tier deductions before closing P1; P2 is still blocked on that money gate.
Safety: no legacy engines, deployments, VPS changes, orders, transfers, or live activation were run.
