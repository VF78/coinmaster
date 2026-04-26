# CoinMaster Target Architecture — Owner Direction 2026-04-25

Status: owner-approved direction captured from Telegram discussion on 2026-04-25. This file is intended to survive OpenClaw/session restarts and to provide stable context for future GitHub Project tasks.

This document complements the older target architecture materials in `coinmaster/docs/TARGET_ARCHITECTURE_2026.md`, `coinmaster/docs/COINMASTER_SYSTEM_AND_SIGNAL_FLOW.md`, and `coinmaster/docs/RADAR_RUNTIME.md`.

## 0. 2026-04-27 owner update — Freqtrade replaces the custom trading engine

Owner decision changed the implementation path: CoinMaster is migrating to an autonomous native Freqtrade core. Freqtrade replaces the custom CoinMaster execution/backtest/hyperopt/Telegram/FreqUI stack.

The architectural intent remains: one coherent trading system, clear state transitions, research-to-live governance, Radar as context/policy rather than a second trader. The implementation boundary changes:

- **Freqtrade owns Stage 1 trading runtime**: exchange integration, order/trade/fill/position lifecycle, dry-run/live execution, backtesting, hyperopt, native Telegram, and FreqUI.
- **Old CoinMaster trading engine becomes reference-only** until parity/cutover, then should be deletable/archivable.
- **No parallel engines**: old CoinMaster execution and Freqtrade live execution must not run together on the same Hyperliquid account.
- **No manual confirmation layer** in the target Freqtrade flow.
- **Stage 2 Radar is rebuilt from scratch** in a Freqtrade-native architecture; do not integrate the current CoinMaster Radar as a legacy runtime dependency.

Canonical migration details live in `coinmaster/docs/FREQTRADE_MIGRATION_2026-04-27.md`.

## 1. Architecture for the next year

CoinMaster should evolve into a **Freqtrade-native autonomous trading system**, not a microservice mesh and not a wrapper around the old CoinMaster runtime.

Keep:

- one repository for project-owned code and docs;
- one production trading runtime after cutover;
- explicit module boundaries;
- durable research-to-live governance;
- secrets outside git;
- a clean path to delete/archive the old CoinMaster trading engine.

Target runtime ownership:

1. **Freqtrade core** — exchange integration, strategy execution, risk/order/trade/fill/position lifecycle, dry-run/live, backtesting, hyperopt, Telegram, and FreqUI.
2. **CoinMasterStrategy** — project-owned Freqtrade `IStrategy` port of the current engulfing/FVG/risk logic.
3. **FreqAI / governance layer** — later research/model/champion workflow around native Freqtrade outputs.
4. **New Radar policy layer (Stage 2)** — context/policy/feature source built from scratch around Freqtrade, not a second execution engine.

## 2. Core durable domain objects

### SignalCandidate

`SignalCandidate` becomes a durable state-machine object, not a transient UI object.

Target states:

- `new`
- `validated`
- `actionable`
- `routed`
- `executed`
- `expired`
- `rejected`
- `postmortem_ready`

The same durable lifecycle should cover candidates originating from Trading Rules patterns and Radar evidence/context.

### RadarContextPolicy

Radar must not act as a second independent execution engine. In the new target it becomes a **Freqtrade-native context/policy layer** for the strategy. It is rebuilt from scratch in Stage 2 rather than integrated from the current CoinMaster Radar runtime.

Radar should calculate, per symbol / asset class:

- `directionMode` — long-only, short-only, both, blocked;
- `riskMultiplier`;
- `eventLockoutUntil` / `lockNewEntries`;
- `narrativeRegime`;
- `priorityScore`;
- `validUntil` / conviction TTL;
- `assetSpecificOverrides`;
- `reasonCodes`;
- `evidenceIds`.

The Freqtrade strategy must not open a new local-pattern trade unless that pattern is allowed by the active `RadarContextPolicy` once Stage 2 exists.

This is the intended compromise between the current CoinMaster design and the industry alpha -> portfolio/risk -> execution model: Radar stops being “a second trader”, but materially controls entry quality.

### Execution, Order, Fill, Exposure

In Stage 1, Freqtrade is the source of truth for execution state: trades, orders, fills, positions, and dry/live accounting.

Project-owned durable objects should not duplicate Freqtrade's execution database unless a later governance/Radar feature genuinely needs a small explanatory reference. The old `ExecutionIntent`/custom order/fill/exposure model is no longer the target execution backbone.

### Experiment and ChampionConfig

Use Freqtrade backtests/hyperopt/FreqAI outputs plus a lightweight `ChampionConfig` concept for research-to-live governance:

- store/identify candidate parameter sets or models;
- compare candidates to the current champion;
- promote only with explicit evidence;
- preserve enough audit trail to explain why live behavior changed.

## 3. Freqtrade strategy target

Port the current engulfing and FVG strategy semantics into a native Freqtrade `IStrategy`. Freqtrade replaces the custom CoinMaster Trading Rules runtime, backtest engine, optimizer, execution path, Telegram flow, and primary UI/control plane.

Add/keep a thin signal-quality layer inside the Freqtrade strategy. It should contain only filters that statistically separate “pattern on noise” from “pattern in regime”.

Target scope:

1. Add a 1h/4h regime filter using EMA slope plus ADX/ATR so long/short signals on lower timeframes agree with higher-timeframe directional regime.
2. Add displacement-quality filters for engulfing and FVG:
   - candle/impulse body or range must be at least a configured fraction of ATR;
   - close must be in the upper quartile for long and lower quartile for short.
3. Add `minExpectedRr` as a hard reject gate before entry.
4. Add time stop and no-follow-through exit so bad entries die quickly even without reverse engulfing.
5. Use native Freqtrade callbacks/guards instead of the old `engulfingGate`/handoff/manual-confirm path.
6. Preserve the FVG latest-closed-candle fix in the Freqtrade dataframe implementation.
7. Add optional FVG-specific exit by invalidation and/or time stop.

### First-stage user-facing parameters

Do not turn the UI into a wall of toggles. Stage 1 should expose at most eight user-facing parameters:

1. `regimeTf`
2. `adxMin`
3. `minImpulseAtr`
4. `minExpectedRr`
5. `timeStopBars`
6. `riskPerTradePct`
7. `eventLockoutMinutes`
8. `portfolioGrossCap`

Everything else should be a closed constant or advanced setting.

## 4. Radar target

Radar becomes a new Freqtrade-native context/evidence/policy controller in Stage 2. It is built from scratch; the current CoinMaster Radar runtime is reference-only and should not become a dependency.

Target scope:

1. Replace regex-based RSS/XML parsing with `feedparser`.
2. Persist feed provenance:
   - raw payload;
   - canonical URL;
   - `published_at`;
   - `observed_at`;
   - `fetched_at`;
   - `http_etag`;
   - `last_modified`.
3. Add only the minimal evidence/policy records needed for explainability and FreqAI/features; avoid rebuilding a heavy parallel CoinMaster audit system.
4. New Radar observations/policies should feed Freqtrade strategy guards/features rather than create directly executable trades.
5. Add NER / alias resolution for assets, regulators, issuers, and macro entities via `spaCy`.
6. Use finance-specific sentiment, preferably FinBERT, instead of generic sentiment as the main finance-text model.
7. Add two-layer dedupe:
   - exact/fuzzy dedupe by hash + RapidFuzz;
   - semantic dedupe using SentenceTransformers embeddings.
8. Replace current score with factor scoring:
   - `relevance`;
   - `novelty`;
   - `sourceReliability`;
   - `eventSeverity`;
   - `timeDecay`;
   - `marketConfirmation`;
   - `executionability`;
   - current weighted sentiment may remain only as a subfeature.
9. Add `RadarContextPolicy` fields:
   - `directionMode`;
   - `riskMultiplier`;
   - `lockNewEntries`;
   - `validUntil`;
   - `reasonCodes`;
   - `evidenceIds`.
10. Freqtrade strategy must read/apply `RadarContextPolicy` before every new entry once Stage 2 is implemented.

## 5. Backtest / optimizer target

Freqtrade backtesting and hyperopt become the canonical Stage 1 research path. Do not continue the custom CoinMaster optimizer as the target engine.

Target scope:

1. use Freqtrade historical data and backtesting;
2. use Freqtrade hyperopt/search spaces for strategy parameters;
3. use FreqUI/backtest outputs where possible;
4. add lightweight champion governance around selected Freqtrade parameter sets;
5. add FreqAI in Stage 2 for advanced model/feature workflow.

## 6. Candidate open-source components

Open-source components to evaluate and possibly adopt:

- selected trading engine: Freqtrade;
- selected exchange abstraction inside Freqtrade: CCXT/Hyperliquid support;
- selected research path: Freqtrade backtesting/hyperopt, then FreqAI in Stage 2;
- possible Stage 2 Radar components: feedparser, FinBERT, spaCy, RapidFuzz, SentenceTransformers;
- possible macro/calendar/regulatory data: OpenBB.

## 7. Implementation bias

Prefer the simplest implementation that moves CoinMaster toward the target architecture:

- do not replace the working monolith with a service mesh;
- do replace the custom trading engine with autonomous native Freqtrade;
- do not make Radar a second trader;
- do not integrate the old Radar runtime into Stage 2; rebuild only the needed policy/feature layer;
- avoid parallel engines and duplicate control planes;
- use Freqtrade-native features before custom code;
- keep commits small, validated, and reversible until live cutover.
