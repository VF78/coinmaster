# Wave Engine / Trading Rules 2 Architecture

This document defines the Slice 0 contract for GitHub issue #73. The goal is a simple research-first architecture that stays inside Freqtrade boundaries and does not disturb the currently running native dry-run bot.

## Boundaries

- Existing **Trading Rules** remain the current live/native rule surface.
- The new 4H wave engine uses a separate persisted namespace: `settings.tradingRulesV2`.
- Saving Trading Rules 2 must not export anything to the running Freqtrade config.
- The GUI edits configuration; Freqtrade/research runners execute backtests and validation.
- Promotion to any dry/live runtime is a separate action and requires explicit Vladimir approval. The current approval covers future dry-run replacement only after implementation and validation gates pass; it does not approve live trading.

## Shared contract

`src/shared/dto.ts` owns the DTOs:

- `WaveEngineRulesSettings`
- `WaveEngineSymbolSettings`
- `WaveEngineOptimizationSettings`
- `WaveEngineOptimizationRanges`

`src/shared/tradingRulesV2.ts` owns:

- `DEFAULT_WAVE_ENGINE_RULES`
- `WAVE_ENGINE_RANGE_LIMITS`
- `cloneWaveEngineRulesDefaults()`
- `normalizeWaveEngineRules()`

The normalizer is the source of truth for defaults, clamping, dedupe, and fixed values.

## Strategy settings captured

The contract captures Vladimir's agreed tunables:

- direction timeframe fixed to `4h`;
- entry timeframes: `5m`, `15m`, `1h`;
- wave engine: `atr_zigzag` or `pct_zigzag`;
- ATR ZigZag multiplier: `1.5..4.0`;
- percent ZigZag move: `2%..5%`;
- break basis: `wick` by default, configurable to `close`;
- flat extreme lookback: `60..150h`, default `100h`;
- pullback ratio: `40..80%`, default `50%`;
- body confirmation fixed to strict `body_engulfing`;
- SL buffer fixed to `0.33%` beyond impulse start;
- max SL cap: `2..4%`;
- TP1 cap fixed to `1.5%`;
- TP2: `2..4%`;
- TP3: `4..8%`;
- time stop: `4..16h`.

## API boundary

Slice 0 adds storage-only endpoints:

- `GET /api/settings/trading-rules-v2`
- `PUT /api/settings/trading-rules-v2`

These endpoints:

1. read the current `settings.tradingRulesV2` payload;
2. normalize absent/stale payloads;
3. persist only the normalized Trading Rules 2 payload;
4. return `{ ok: true, rules }`.

They intentionally do **not**:

- write `/opt/coinmaster/freqtrade` config;
- export `trading_rules.json`;
- refresh current runtime trading rules;
- restart any service;
- create orders.

## Future GUI: Trading Rules 2

The GUI should be a practical profile editor and research launcher:

- profile form for symbols, wave engine, break basis, entry TFs, and tunable ranges;
- save/load through the Trading Rules 2 API;
- buttons for baseline backtest, parameter matrix, and native validation;
- active/recent runs panel with metrics and artifact links;
- explicit research-only warning;
- no live apply button in the first implementation.

## Implemented web slice (2026-04-30)

The workspace now includes a dedicated `Wave Engine` page in the web GUI.

- Navigation: `src/web/App.tsx` and `src/web/CustomApp.tsx`
- Frontend page: `src/web/pages/WaveEnginePage.tsx`
- Shared DTO/API contract: `src/shared/dto.ts`, `src/web/lib/api.ts`
- Backend bridge: `src/server/waveEngineReplay.ts`
- Research-only replay exporter: `freqtrade/wave_engine/export_replay.py`

Current behavior:

1. `GET /api/settings/trading-rules-v2` / `PUT /api/settings/trading-rules-v2` remain the GUI settings source of truth.
2. `GET /api/wave-engine/profiles` returns the selected native Wave Engine snapshot from `freqtrade/wave_engine/wave_engine_profiles.selected.json`.
3. `GET /api/wave-engine/replay?pair=...&timeframe=...&start=2026-01-01&end=...` recomputes visualization data from backend engine output, not frontend annotations.
4. The replay JSON includes:
   - candles;
   - waves / pivot segments;
   - structural break markers;
   - regime-change markers;
   - trade entries/exits;
   - TP/SL/time-stop hit events;
   - horizontal trade level segments for SL / TP1 / TP2 / TP3.

The frontend only renders this schema with `lightweight-charts`; it does not embed Wave Engine decision logic.

## Runtime note

`export_replay.py` expects the local Freqtrade OHLCV feather store under `freqtrade/user_data/data/hyperliquid/futures` and is intended to run in the existing Freqtrade container/toolchain where `pandas` and `freqtrade` are available. This keeps the feature research-only and avoids touching the live/dry runtime config.

## Future research runner

The runner should create immutable, reproducible run artifacts under a dedicated root, for example:

`/var/lib/coinmaster/freqtrade/research/wave-engine/runs/<run_id>/`

Each run should write:

- `profile.json` — normalized GUI config snapshot;
- `resolved-params.json` — exact single candidate/optimized params used;
- `state.json` — current status/progress;
- `trades.csv` / `trades.json` — simulated/native trade events;
- `metrics.json` — ROI, PF, DD, winrate, top-trade stress;
- `SUMMARY.md` — human-readable result and rejection notes.

## Freqtrade boundary

The eventual strategy wrapper should be dedicated research code, e.g. `CoinMasterWaveEngineV1`:

- base timeframe equals selected entry TF;
- 4H regime is merged as informative data;
- 4H regime must be usable only after closed/confirmed candles;
- lower-TF entries must use already closed lower-TF candles;
- native Freqtrade backtest/hyperopt/lookahead checks are final validation gates.

The Wave Engine runner may prepare a temporary research config/profile for Freqtrade, but it must not mutate the running dry-run/live bot configuration.

## Slice 1-5 prototype status

Issue #73 now has a research-only prototype under `freqtrade/wave_engine/` plus `scripts/check-wave-engine-prototype.py`.

- The intended final home remains `freqtrade/user_data/scripts/wave_engine/` and `freqtrade/user_data/strategies/CoinMasterWaveEngineV1.py`.
- In this workspace snapshot, `freqtrade/user_data/*` is permission-locked, so the current safe implementation lives outside that tree.
- Exact commands and artifact contract are documented in [WAVE_ENGINE_RESEARCH_PROTOTYPE.md](./WAVE_ENGINE_RESEARCH_PROTOTYPE.md).
