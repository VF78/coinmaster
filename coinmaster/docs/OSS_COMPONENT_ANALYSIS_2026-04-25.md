# CoinMaster OSS Component Analysis — 2026-04-25

Status: draft analysis for owner approval. Do not update GitHub Project tasks from this document until owner explicitly confirms the chosen components.

Related architecture note: `coinmaster/docs/TARGET_ARCHITECTURE_OWNER_DIRECTION_2026-04-25.md`.

## 1. Current codebase fit

CoinMaster is already closer to a modular event-driven monolith than to a framework-driven external trading bot.

Current evidence in code:

- Shared DTO/schema boundary: `src/shared/dto.ts`.
- Shared mutable persistence shape: `src/core/types.ts:21` (`DBShape`).
- LowDB/Postgres snapshot persistence bridge: `src/core/persistence/*`.
- Trading Rules evaluators are already isolated from execution:
  - `src/core/engulfingEvaluator.ts:162` (`evaluateTimeframe`);
  - `src/core/fvgEvaluator.ts:70` (`detectFvgZones`).
- Execution handoff is already unified for engulfing/FVG/Radar:
  - `src/server/index.ts:4253` (`handoffStrategyEntrySignal`).
- Radar has source and execution planes documented and implemented:
  - `src/server/index.ts:1414` (`startAlphaRadarMonitoringPlane`);
  - `src/server/index.ts:7013` (`ingestRadarSignal`).
- Backtest/optimizer already exist as detached compute work:
  - `src/core/backtestEngine.ts:172` (`runBacktestEngine`);
  - `src/core/computeJobProcess.ts:15`;
  - `src/core/optimizerWorker.ts:44` (`MAX_CANDIDATES`).

This argues for **incremental adoption of libraries**, not replacement of the application with an external trading engine.

## 2. Replace Trading Rules engine or extend it?

Recommendation: **extend the current Trading Rules engine; do not replace it now.**

Reasons:

1. The current engine already implements the business-specific entry core: engulfing + sweep and FVG retrace/confirmation.
2. Backtest already uses the same core evaluators as live, which is valuable parity.
3. Execution/risk path is already CoinMaster-specific: manual confirmation, sizing, risk gates, pending confirmations, TP/SL best effort, Telegram notifications, exchange adapter.
4. Replacing with LEAN/Nautilus/Freqtrade/Hummingbot would move execution ownership and state model outside CoinMaster before the durable domain model (`SignalCandidate`, `ExecutionIntent`, `Order`, `Fill`, `Exposure`) is ready.
5. The target gaps are narrow and local: `SignalQualityContext`, regime/ATR/ADX filters, RR gate, time/no-follow exits, fail-safe `engulfingGate`, and FVG lag fix.

Where to extend:

- Add `SignalQualityContext` in `src/core/signalQualityContext.ts`.
- Extend `TradingRulesSettings` and normalization in `src/shared/dto.ts` and `src/shared/tradingRules.ts`.
- Use the quality context in:
  - `src/core/engulfingEvaluator.ts`;
  - `src/core/fvgEvaluator.ts`;
  - `src/server/index.ts::runEngulfingMonitorTick`;
  - `src/server/index.ts::runFvgMonitorTick`;
  - `src/server/index.ts::engulfingGate`;
  - `src/core/backtestEngine.ts`.

## 3. Replace Radar or extend it?

Recommendation: **rebuild Radar internals as context/evidence controller; do not replace Radar with a ready-made engine.**

Reasons:

1. Radar already has useful repo-owned concepts: observations, ideas, source health, freshness, connectors, handoff history.
2. Existing docs already separate Source Radar and Execution Radar, and execution goes through the unified handoff path.
3. The target role is not “find and execute trades independently”; it is `RadarContextPolicy` controlling whether local Trading Rules patterns may enter.
4. No candidate listed provides this exact role out of the box. The needed capabilities are ingestion/NLP/dedupe/scoring components, not a replacement trading engine.

Where to extend:

- Replace regex RSS parser:
  - `src/server/alphaRadar.ts:1297` (`extractRssItems`).
- Add provenance fields to DTOs:
  - `AlphaRadarProvenance` / `AlphaRadarObservation` in `src/shared/dto.ts`.
- Add durable objects:
  - `EvidenceBundle`;
  - `SignalCandidate`;
  - `RadarContextPolicy`;
  - `ExecutionIntent`.
- Add collections to `DBShape` and persistence defaults.
- Split heavy Radar logic into dedicated modules:
  - `src/server/alphaRadarDedupe.ts`;
  - `src/server/alphaRadarNlp.ts`;
  - `src/server/alphaRadarScoring.ts`;
  - `src/server/radarContextPolicy.ts`.

## 4. Component-by-component assessment

### Architecture / trading frameworks

#### LEAN

Use: reference only, not replacement.

Pros:
- Mature event-driven quant engine.
- Strong portfolio/risk/accounting/backtest concepts.
- Broad multi-asset support.

Cons for CoinMaster now:
- Large C#/Python ecosystem; heavy migration from current TS monolith.
- Would duplicate/replace current execution/risk state instead of improving it.
- Overkill before durable CoinMaster objects are normalized.

Decision: **avoid as runtime replacement; use as architectural reference.**

#### NautilusTrader

Use: later research benchmark, not runtime replacement now.

Pros:
- Production-grade event-driven architecture.
- Strong research/live parity model.
- Multi-asset/multi-venue design.

Cons:
- Rust/Python engine ownership would compete with CoinMaster’s TS execution/risk path.
- Integration cost is high before CoinMaster’s own domain objects are durable.

Decision: **do not embed now; study patterns and possibly use later as isolated benchmark/lab.**

#### Freqtrade

Use: reference for crypto strategy/backtesting/hyperopt patterns, not replacement.

Pros:
- Python crypto bot with backtesting, plotting, money management, hyperoptimization.
- Useful comparison for dry-run/live workflow and strategy lifecycle.

Cons:
- Opinionated bot architecture; would become a second system.
- Replacing CoinMaster with Freqtrade would discard current unified handoff/risk/governance work.

Decision: **do not replace Trading Rules with Freqtrade; borrow ideas only.**

#### Hummingbot

Use: reference/connectors/market-making ideas only.

Pros:
- Strong exchange connector ecosystem and market-making orientation.
- Useful conceptual reference for crypto connectivity.

Cons:
- Primary fit is market making / liquidity / arbitrage frameworks, not CoinMaster’s pattern + Radar context pipeline.
- Would introduce external execution ownership.

Decision: **avoid as core replacement.**

### Market ingestion

#### cryptofeed

Use: evaluate for later multi-exchange market-data ingestion.

Pros:
- Normalized/standardized crypto exchange feeds.
- Designed for trades, book updates, ticker updates, websocket-first with REST fallback.
- This is infrastructure CoinMaster should not rewrite once multi-exchange depth/trade feeds matter.

Cons:
- Python runtime; current live path is TypeScript with Hyperliquid adapter.
- Needs a clean bridge into durable market events / collector worker.
- Not necessary for immediate Trading Rules quality filters if current candle/tick source is enough.

Decision: **adopt later for collector worker if/when multi-exchange normalized feeds are required. Not first task.**

### Research / optimization

#### vectorbt

Use: Python research sidecar, not live/backtest source of truth.

Pros:
- Very fast vectorized research sweeps.
- Good for hypothesis exploration across symbols/parameters/windows.

Cons:
- Different execution semantics from current live/backtest engine.
- Can create research/live drift if used as canonical backtester.

Decision: **adopt later as research accelerator; keep CoinMaster backtest engine canonical for promotion.**

#### Optuna

Use: primary optimizer component.

Pros:
- Strong hyperparameter optimization framework.
- Supports pruning unpromising trials and parallelization.
- `RDBStorage` fits the Postgres direction.
- Optuna Dashboard supports operator inspection.

Cons:
- Requires Python worker/sidecar or TS/Python bridge.
- Must write versioned trial records and avoid drifting from live engine.

Decision: **adopt for optimizer worker.**

#### Qlib

Use: not now.

Pros:
- AI-oriented quantitative research platform.
- Strong data/model workflow concepts.

Cons:
- Heavy ML/research platform, more equity/AI-workflow oriented.
- Premature for current need: improve deterministic TR + Radar context first.

Decision: **defer/avoid for now.**

### Radar ingestion / NLP / dedupe

#### feedparser

Use: immediate replacement for regex RSS/XML parser.

Pros:
- Handles RSS/Atom variants, dates, normalization, ETag/Last-Modified HTTP features.
- Directly matches target provenance requirements.

Cons:
- Python package; if Node-only implementation is preferred, choose a Node feed parser with equivalent features. The owner specifically listed `feedparser`, so Python sidecar is acceptable if scoped.

Decision: **adopt now for feed parsing, either via small Python collector sidecar or a Node-equivalent only if we choose to avoid Python in collector.**

#### spaCy

Use: NER / alias resolution.

Pros:
- Mature NLP pipeline for entity extraction.
- EntityRuler/custom patterns can handle tickers, issuers, regulators, macro entities.

Cons:
- Model install and memory footprint.
- Finance-specific entities require custom rules, not just default NER.

Decision: **adopt for Radar NLP sidecar, with custom EntityRuler first.**

#### FinBERT

Use: finance sentiment sidecar.

Pros:
- Finance-domain sentiment model, better aligned than generic sentiment.
- Outputs positive/negative/neutral probabilities.

Cons:
- Heavier inference; needs batching/cache/timeouts.
- Should be a subfeature, not a hard gate by itself.

Decision: **adopt for finance sentiment, async/non-critical with fallback.**

#### RapidFuzz

Use: immediate fuzzy dedupe.

Pros:
- Fast fuzzy string matching with C++ implementations and Python fallback.
- Good fit for URL/title/source duplicate suppression.

Cons:
- Requires thresholds and auditability to avoid hiding genuinely new events.

Decision: **adopt now for dedupe layer 1.**

#### SentenceTransformers

Use: second-stage semantic dedupe after provenance + RapidFuzz.

Pros:
- Strong text embeddings/similarity ecosystem.
- Useful for near-duplicate news across sources/languages/titles.

Cons:
- Needs embedding storage/cache and model management.
- More CPU/RAM than fuzzy dedupe.

Decision: **adopt after durable EvidenceBundle/provenance is in place.**

### Indicators / performance analytics

#### TA-Lib

Use: optional; prefer simple in-process TS indicators first for live path.

Pros:
- Stable technical analysis library with ADX/ATR/EMA and many indicators.
- Good for Python research/backtest parity checks.

Cons:
- C/C++ dependency can complicate VPS build/deploy.
- Calling Python/TA-Lib in live critical path adds operational risk.

Decision: **for live Trading Rules: implement minimal EMA/ATR/ADX in TypeScript first. For research/validation: use TA-Lib optionally in Python sidecar.**

#### QuantStats

Use: performance/risk reporting for backtest/live deltas.

Pros:
- Good fit for tearsheets and risk/performance summaries.
- Complements current simple BacktestRunSummary.

Cons:
- Python report generation must be async/non-critical.

Decision: **adopt for reporting/tearsheets, not live decision path.**

### Macro/calendar/regulatory data

#### OpenBB

Use: later for macro/calendar/regulatory/reference data ingestion.

Pros:
- Unified Python API/data platform with connectors and extensions.
- Good fit for Radar context enrichment.

Cons:
- Provider coverage/licensing/API keys vary by dataset.
- Too broad for first implementation; could add dependency bulk before schema is ready.

Decision: **defer until Radar provenance/EvidenceBundle/RadarContextPolicy exist.**

## 5. Recommended approval package

### Approve now

1. `feedparser` — RSS/Atom parsing + provenance.
2. `RapidFuzz` — first-layer fuzzy dedupe.
3. `spaCy` — NER/alias resolution with custom patterns.
4. `FinBERT` — finance sentiment as async subfeature.
5. `Optuna` — optimizer worker with Postgres `RDBStorage` and pruners.
6. `QuantStats` — backtest/live performance reports.

### Approve with constraint

7. `TA-Lib` — use for Python research/validation only at first; live Node path uses minimal TS EMA/ATR/ADX to avoid C dependency in live execution.
8. `SentenceTransformers` — add only after provenance/EvidenceBundle and storage/cache are ready.
9. `vectorbt` — use for research sweeps only, not canonical live/backtest parity.
10. `cryptofeed` — add later when multi-exchange normalized trades/books/tickers are needed.
11. `OpenBB` — add later for macro/calendar/regulatory enrichment.

### Do not approve as replacements

12. LEAN — reference only.
13. NautilusTrader — reference/later benchmark only.
14. Freqtrade — reference only, no replacement.
15. Hummingbot — reference/connectivity ideas only, no replacement.
16. Qlib — defer/avoid for now.

## 6. Implementation principles if approved

- Keep live execution/risk ownership in CoinMaster.
- Do not put Python NLP/model sidecars in the live critical path without timeout and fallback.
- All sidecar outputs must write durable records (`EvidenceBundle`, `SignalCandidate`, `RadarContextPolicy`, `Experiment`, `ChampionConfig`) before being used.
- Version schemas between TypeScript and Python.
- Start with deterministic, auditable gates before ML-heavy scoring.
- Keep UI first-stage parameters capped to the owner-approved eight fields.
