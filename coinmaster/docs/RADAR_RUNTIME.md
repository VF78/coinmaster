# Radar Runtime

This document describes the **actual** implemented Radar runtime — not aspirational
connector infrastructure. If Radar behavior here disagrees with code, treat the code
as authoritative and file a doc fix.

## Scope

Radar is an **owner-only, upstream-only signal intake**. It accepts pre-computed
trade candidates (symbol, side, price, reason) from external sources the owner
chooses to run — Telegram scrapers, GPTs, third-party alert feeds, custom
notebooks — and hands each accepted signal to the **single unified trading
engine** for sizing, risk gating, and order placement. Radar does **not** run
its own market-data connectors, indicator logic, or a second execution path.

What Radar does:

- Accept `RadarSignalIngestPayload` via `POST /api/radar/signals` (single) and
  `POST /api/radar/signals/batch` (≤ 50 items).
- Deduplicate within a 5-minute window (see `RADAR_SIGNAL_DEDUP_MS`).
- Enforce monitored-symbol scope using **Trading Rules enabled coins** only.
- Hand off accepted signals to `handoffStrategyEntrySignal` with
  `strategy='radar'`, exactly like the engulfing and FVG monitors.
- Score and classify signals deterministically for diagnostics and dashboards.
- Return enriched signals plus summary rollups from `GET /api/radar/signals`.

What Radar does **not** do:

- No internal upstream connectors (no internal WebSocket clients, no scheduled
  scrapers, no reconnect/backoff loops for external feeds). The ingest surface
  is exclusively the two POST endpoints above.
- No separate execution engine. Orders flow through the same
  `handoffStrategyEntrySignal` → risk gates → `exchange.placeLimitOrder` path
  used by the other strategies.
- No new persistence. Signals are stored in the shared lowdb `radarSignals`
  array (see `RADAR_SIGNAL_HISTORY_LIMIT`).
- No asset-class gating of monitored symbols. Asset class influences **verdict
  thresholds only** (see below).

## Ingest

### Endpoints

| Method | Path                          | Auth        | Body                                    |
| ------ | ----------------------------- | ----------- | --------------------------------------- |
| POST   | `/api/radar/signals`          | `ownerAuth` | `RadarSignalIngestPayload`              |
| POST   | `/api/radar/signals/batch`    | `ownerAuth` | `{ signals: RadarSignalIngestPayload[] }` (max 50) |
| GET    | `/api/radar/signals`          | `ownerAuth` | query: `limit`, `status`, `symbol`, `connector`, `kind`, `channel`, `source` |

Payload fields: `symbol`, `side` (`buy`/`sell`), `price` (> 0), `reason`
(required, ≤ 280 chars), `timeframe` (optional — falls back to `15m`),
`source` (free-form label), optional `sourceMeta` with `connector`, `kind`,
`channel`, `externalId`, `messageTs`.

Any payload missing `symbol`, `side`, `source`, `reason`, or a finite positive
`price` is rejected with `400 invalid_radar_signal_payload` before hitting the
engine.

### Deduplication

A signal is considered a duplicate if it matches an existing record by the
dedupe key (`symbol|side|timeframe|source|reason|sourceMeta`) and the older
record is within `RADAR_SIGNAL_DEDUP_MS` (5 min). Duplicates are persisted
with `status='ignored'`, `error='duplicate_signal'`, and a `duplicateOf` back-
reference. No handoff runs for duplicates.

### Monitored-symbol scope

Before handoff, `isSymbolMonitored(effectiveRules.raw, symbol)` enforces that
the incoming symbol is in the **enabled coins list** of the current Trading
Rules snapshot. Signals for symbols outside that set are rejected with
`status='rejected'`, `error='symbol_not_monitored'`. The enabled set is
authoritative — asset class is not used here.

### Handoff to the unified engine

Accepted signals call `handoffStrategyEntrySignal` with `strategy='radar'`
and `component='radar-ingest'`. Manual vs. auto-confirm is taken from
`effectiveRules.raw?.autoConfirm`:

- **Manual** → signal queued via `queuePendingConfirmation` → owner confirms in
  the dashboard → same pending-confirmation flow shared with engulfing/FVG.
- **Auto-confirm** → sizing computed via `computeAllocationSize`, risk gates
  re-evaluated via `evaluateRiskGates`, `exchange.placeLimitOrder` invoked,
  TP/SL trigger orders placed best-effort, Telegram trade-open notify sent.

Outcome is written back to the `RadarSignalRecord` as one of:

| status                  | meaning                                                     |
| ----------------------- | ----------------------------------------------------------- |
| `pending_confirmation`  | queued for owner confirmation                               |
| `auto_order_placed`     | auto-confirm order accepted by exchange                     |
| `rejected`              | blocked by sizing, risk gate, monitored-symbol scope, etc.  |
| `ignored`               | invalid sizing, duplicate, or monitor-path skip             |

## Scoring, verdicts, and summaries

`src/server/radarReadModel.ts` is pure-function deterministic logic:
`enrichRadarSignal` computes `candidateScore` and `verdict` for each record;
`buildRadarSignalsSummary` produces the rollup returned alongside the list.

### Candidate score (0–100)

```
score = statusWeight + freshnessScore + sourceMetaRichness − duplicatePenalty
clamp(score, 0, 100)
```

- **statusWeight:** `auto_order_placed=40`, `pending_confirmation=30`,
  `ignored=10`, `rejected=5`.
- **freshnessScore:** `≤15m→30`, `≤1h→20`, `≤4h→10`, else `0` — based on
  `updatedAt ?? createdAt`.
- **sourceMetaRichness:** 2 points per populated meta field (connector, kind,
  channel, externalId, messageTs), capped at 10.
- **duplicatePenalty:** 20 if the record is marked `duplicate_signal` or has a
  `duplicateOf` back-reference.

### Asset-class verdict thresholds (diagnostics only)

Verdict is derived from the score and the inferred asset class of the symbol
(`inferAssetClassFromSymbol`). Thresholds are:

| asset class  | actionable | bias | watch |
| ------------ | ---------- | ---- | ----- |
| crypto       | 70         | 45   | 20    |
| commodity    | 80         | 55   | 30    |
| other        | falls back to crypto defaults            |

**Important:** these thresholds shape the **verdict label and diagnostic
summary rollups only**. They do **not** gate which symbols are monitored or
which signals get handed to the engine — that is controlled exclusively by
Trading Rules enabled coins.

Duplicate, rejected records, or scores below the `watch` threshold return
verdict `ignore`. `auto_order_placed` short-circuits to `actionable`.

### Summary rollups

`buildRadarSignalsSummary` groups the enriched records into:

- `bySource`, `byConnector`, `byKind`, `byChannel` — raw counts.
- `qualityBySource`, `qualityByConnector`, `qualityByAsset`,
  `qualityByVerdict`, `qualityByFamily` — outcome buckets
  (`pendingConfirmation`, `autoOrderPlaced`, `rejected`, `ignored`,
  `duplicates`, `lastSeenAt`).
- `candidateGroups` — top symbols×side ranked by best score, used to drive the
  Radar dashboard view.

## Persistence and history cap

Radar signals live in the shared lowdb store under `radarSignals`. After every
mutation the list is passed through `compactRadarSignals`, which sorts by
`updatedAt` descending and truncates to `RADAR_SIGNAL_HISTORY_LIMIT` (500).
No migration or separate table is involved; adding persistence beyond this is
out of scope for the current runtime baseline.

## Upstream read pressure and shared coordinator

Radar itself does not call Hyperliquid, but the unified engine that Radar
hands off to does, alongside the drawdown watchdog, engulfing monitor, FVG
monitor, TP-fill monitor, REST fallback ingest, and live dashboard warmup.

All **idempotent `info` POST reads** go through a single shared coordinator,
`HyperliquidInfoClient` (`src/exchange/hyperliquidInfoClient.ts`), wired into
`HyperliquidAdapter` via `requestInfo`:

- **In-flight dedupe:** simultaneous identical payloads share one fetch
  (keyed by stable-stringified payload).
- **Bounded concurrency:** hard cap (`HYPERLIQUID_INFO_MAX_CONCURRENCY`,
  default 4) with a FIFO queue.
- **Retry + backoff:** transient `429` and `5xx` retry with jittered
  exponential backoff (`HYPERLIQUID_INFO_BASE_BACKOFF_MS`→
  `HYPERLIQUID_INFO_MAX_BACKOFF_MS`, defaults 250ms → 5000ms), honoring
  `Retry-After` when present. Network errors retry identically.
- **Scope:** `info` reads only. Order placement goes through the SDK directly
  and is **not** wrapped.

Monitor first-tick warmups are additionally staggered at boot
(`MONITOR_STARTUP_STAGGER_MS`, default 750ms) so the drawdown watchdog, FVG
monitor, and engulfing monitor do not fire their initial fetches in the same
event-loop turn.

Observability: coordinator counters (`totalRequests`, `dedupedRequests`,
`retries`, `failures`, `activeCount`, `queueLength`, `inFlightCount`) are
surfaced at `GET /api/health/perf` under `hyperliquidInfo`.

## Environment variables

| Variable                              | Default | Purpose                                              |
| ------------------------------------- | ------- | ---------------------------------------------------- |
| `HYPERLIQUID_INFO_MAX_CONCURRENCY`    | 4       | Max concurrent `info` upstream calls                 |
| `HYPERLIQUID_INFO_MAX_RETRIES`        | 3       | Retry attempts on 429/5xx/network errors             |
| `HYPERLIQUID_INFO_BASE_BACKOFF_MS`    | 250     | Base backoff for jittered exponential retry          |
| `HYPERLIQUID_INFO_MAX_BACKOFF_MS`     | 5000    | Cap for the computed backoff                         |
| `MONITOR_STARTUP_STAGGER_MS`          | 750     | Spacing between monitor first-tick warmups at boot   |

The `RADAR_SIGNAL_DEDUP_MS` (5 min) and `RADAR_SIGNAL_HISTORY_LIMIT` (500)
constants are currently hard-coded — change them in `src/server/index.ts` if
required.

## Invariants

`scripts/invariants-radar-handoff.ts` (runnable via
`npm run invariants:radar-handoff`) asserts:

- Radar handoff reuses the unified entry flow (manual + auto).
- Duplicates are ignored without side effects.
- Monitored-symbol scope is enforced via Trading Rules enabled coins.
- Outcome reconciliation writes back correct `pendingId`/`orderId`/`status`.
- Summary rollups and verdict thresholds remain deterministic.

Run it alongside `npm run check` before shipping Radar-adjacent changes.
