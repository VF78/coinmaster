# CoinMaster Target Architecture — Owner Direction 2026-04-25

Status: owner-approved direction captured from Telegram discussion on 2026-04-25. This file is intended to survive OpenClaw/session restarts and to provide stable context for future GitHub Project tasks.

This document complements the older target architecture materials in `coinmaster/docs/TARGET_ARCHITECTURE_2026.md`, `coinmaster/docs/COINMASTER_SYSTEM_AND_SIGNAL_FLOW.md`, and `coinmaster/docs/RADAR_RUNTIME.md`.

## 1. Architecture for the next year

CoinMaster should evolve as a **modular event-driven monolith**, not a microservice mesh.

Keep:

- one repository;
- one shared data schema;
- one deployable application boundary;
- explicit internal module boundaries;
- durable state transitions and audit trail.

Target runtime workers:

1. **Collector worker** — market/news/social/feed ingestion and normalization.
2. **Strategy worker** — Trading Rules evaluation, pattern detection, signal quality, and Radar context checks.
3. **Execution / risk worker** — handoff, order intent, hard gates, order/fill/exposure reconciliation.
4. **Optimizer worker** — rolling-window backtests, optimization trials, candidate/champion governance.

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

Radar must stop acting as a second independent source of trade candidates. Radar becomes the **main context controller** for the Trading Rules engine.

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

The Trading Rules engine must not open a new local-pattern trade unless that pattern is allowed by the active `RadarContextPolicy`.

This is the intended compromise between the current CoinMaster design and the industry alpha -> portfolio/risk -> execution model: Radar stops being “a second trader”, but materially controls entry quality.

### ExecutionIntent, Order, Fill, Exposure

`ExecutionIntent` records exactly what was sent to handoff/execution after all strategy, Radar-context, and risk gates.

Downstream execution state should be represented by:

- `Order`;
- `Fill`;
- `Exposure`.

These objects support reconciliation, risk accounting, and post-trade analysis.

### Experiment and ChampionConfig

Use `Experiment` and `ChampionConfig` for research-to-live governance:

- store optimizer/backtest trials;
- compare candidate configs to current champion;
- promote only with explicit evidence;
- preserve audit trail from research to live behavior.

## 3. Trading Rules engine target

Keep the current engulfing and FVG detectors as the entry core. Do **not** replace them wholesale with an external trading engine unless later evidence proves replacement is cheaper and safer.

Add a thin `SignalQualityContext` layer per symbol/timeframe. It should contain only filters that statistically separate “pattern on noise” from “pattern in regime”.

Target scope:

1. Add a 1h/4h regime filter using EMA slope plus ADX/ATR so long/short signals on lower timeframes agree with higher-timeframe directional regime.
2. Add displacement-quality filters for engulfing and FVG:
   - candle/impulse body or range must be at least a configured fraction of ATR;
   - close must be in the upper quartile for long and lower quartile for short.
3. Add `minExpectedRr` as a hard reject gate before handoff.
4. Add time stop and no-follow-through exit so bad entries die quickly even without reverse engulfing.
5. Change `engulfingGate` from fail-open to fail-safe for new non-reduce-only entry orders, with explicit operator override.
6. Fix FVG latest-closed-candle lag.
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

Radar becomes a context/evidence controller.

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
3. Add `EvidenceBundle` and durable `SignalCandidate` records.
4. Make `AlphaRadarIdea` create candidate/context records rather than only UI objects.
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
10. Trading Rules engine must read `RadarContextPolicy` before every new entry.

## 5. Backtest / optimizer target

For continuous 24/7 optimization, add an optimizer worker that:

1. cycles rolling-window backtest jobs;
2. writes trials to Postgres;
3. uses Optuna with `RDBStorage`;
4. uses pruners for early termination of poor trials;
5. supports visual inspection with Optuna Dashboard;
6. compares live/backtest deltas and risk/performance tearsheets;
7. supports research-to-live governance through `Experiment` and `ChampionConfig`.

## 6. Candidate open-source components

Open-source components to evaluate and possibly adopt:

- architecture / event-driven parity: LEAN, NautilusTrader, Freqtrade, Hummingbot;
- crypto market ingestion: cryptofeed;
- research / optimization: vectorbt, Optuna, Qlib;
- Radar: feedparser, FinBERT, spaCy, RapidFuzz, SentenceTransformers;
- indicators / analytics: TA-Lib, QuantStats;
- macro/calendar/regulatory data: OpenBB.

## 7. Implementation bias

Prefer the simplest implementation that moves CoinMaster toward the target architecture:

- do not replace the working monolith with a service mesh;
- do not replace the current Trading Rules engine unless evidence later proves it is better;
- do not make Radar a second trader;
- avoid large migrations that block production fixes;
- add durable state and clear interfaces first;
- add open-source libraries where they reduce custom infrastructure or improve signal quality;
- keep live execution/risk ownership inside CoinMaster.
