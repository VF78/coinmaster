# Radar Runtime

This document describes the implemented Radar runtime. If code and this document diverge, treat code as authoritative and fix the doc in the same change.

## End-to-end flow

```text
source connectors / feeds / market monitors
  -> Alpha Radar observations
  -> dedupe + source health + freshness state
  -> idea promotion / watch-only classification
  -> confirmed tradable candidate
  -> POST /api/radar/signals or internal Radar handoff surface
  -> unified entry handoff (`handoffStrategyEntrySignal`)
  -> pending confirmation or auto-order via the single trading engine
```

There are two deliberately separate planes:

- **Source Radar / Alpha Radar** collects observations broadly from market snapshots, configured feeds, and social/connectors. It owns source health, freshness, live ideas, and monitoring-only context.
- **Execution Radar ingest** accepts only concrete trade candidates and hands them to the existing unified trade flow. It does not size, risk-gate, or place orders itself.

The handoff boundary is strict: Source Radar may display broad context, but only enabled Trading Rules symbols can become tradable handoff signals.

## Source plane

Source collection is repo-owned and starts from `startAlphaRadarMonitoringPlane()` during server boot. It currently has two collector loops:

- **Market snapshot**: builds observations from live market ticks plus configured macro/proxy/equity monitoring assets.
- **External feeds/connectors**: polls configured RSS/JSON/GDELT feeds and connector-backed social sources where configured/authenticated.

Runtime state is exposed through:

- `GET /api/settings/alpha-radar`
- `PUT /api/settings/alpha-radar`
- `GET /api/alpha-radar/live`
- `GET /api/alpha-radar/observations`
- `GET /api/alpha-radar/ideas`
- `POST /api/alpha-radar/collect/market-snapshot`
- `POST /api/alpha-radar/collect/external-feeds`

Health/freshness surface includes collector status, last run, last success/error, expected source health, stale/inactive/fresh state, and connector state. A stalled source plane should be visible from the Radar page without log diving.

## Execution ingest and handoff

Execution handoff is exposed through:

- `POST /api/radar/signals`
- `POST /api/radar/signals/batch` (≤ 50 items)
- `GET /api/radar/signals`
- `GET/PUT /api/settings/radar`

A `RadarSignalIngestPayload` must include `symbol`, `side`, `price`, `reason`, and `source`/source metadata. Invalid payloads are rejected before handoff.

Accepted signals follow this sequence:

1. Normalize payload and create a `RadarSignalRecord`.
2. Deduplicate within `RADAR_SIGNAL_DEDUP_MS` (5 minutes).
3. Enforce monitored-symbol scope via Trading Rules enabled coins.
4. Call `handoffStrategyEntrySignal({ strategy: 'radar', component: 'radar-ingest', ... })`.
5. Persist outcome: `pending_confirmation`, `auto_order_placed`, `rejected`, or `ignored`.

Manual vs auto confirm is controlled by Radar runtime settings:

- **Manual**: queue pending confirmation; owner confirms through the shared dashboard pending-confirm flow.
- **Auto**: use the same sizing, risk gates, exchange order path, and TP/SL best-effort placement as other strategies.

Radar never creates a second execution engine and never bypasses the unified handoff path.

## Tradable vs monitoring-only policy

Policy:

- Observe broadly.
- Display non-tradable but relevant live ideas as monitoring-only context.
- Only confirmed candidates for symbols enabled in Trading Rules may be handed off.
- Non-tradable observations must not appear as trade-ready.

Implementation anchors:

- Source Radar can include monitoring-only macro/proxy/equity assets in `AlphaRadarObservation` and UI sections.
- Execution Radar rejects any handoff symbol not returned by `getMonitoredSymbols(normalizeTradingRules(settings.tradingRules))` with `symbol_not_monitored`.
- Asset class affects verdict labels/diagnostics only; it does not expand the tradable universe.

## Candidate-generation audit

The current retained candidate logic is intentionally simple and explainable.

### Retained rules

- **Freshness**: recent observations/signals rank higher; stale sources are clearly marked. Rationale: live trading ideas decay quickly.
- **Source independence**: confirmation improves when sources span different source types/classes/layers. Rationale: reduces single-feed noise.
- **Primary-source presence**: ideas prefer at least one primary source or validated market source. Rationale: narrative-only signals are weak.
- **Market structure readiness**: watch/idea split uses compression, breakout/follow-through, relative strength, trigger/invalidation/target availability. Rationale: observation quality alone is not enough for execution.
- **Trading Rules handoff gate**: only enabled symbols can become execution candidates. Rationale: keeps monitoring breadth separate from capital deployment.
- **Duplicate suppression**: repeated identical handoff signals are persisted as ignored duplicates. Rationale: protects from connector spam and repeated alerts.
- **Outcome reconciliation**: pending/order/rejected outcomes are written back to the source record. Rationale: the operator can inspect what happened after handoff.

### Removed or simplified rules

- No separate Radar execution engine.
- No hidden runtime outside repo boot/startup code.
- No asset-class expansion of tradable symbols.
- No opaque multi-engine scoring path; scoring stays deterministic and surfaced through DTO/read-model fields.
- No automatic execution for monitoring-only macro/proxy/equity observations.

### Promotion criteria

- **Ignored**: invalid payload, duplicate handoff, Radar disabled, insufficient sizing, or candidate below useful watch/actionability thresholds.
- **Watch/live idea**: fresh observation set with useful context or early structure, but not enough execution readiness/cross-confirmation for handoff.
- **Confirmed tradable candidate**: symbol is enabled in Trading Rules, direction/price/reason are explicit, duplicate check passes, and the candidate reaches the Radar handoff API or internal handoff surface.
- **Rejected at handoff**: candidate reached the handoff gate but failed Trading Rules scope, risk gates, sizing, or exchange acceptance. The rejection reason must be visible in handoff history.

## Operator UI requirements

The Radar page must keep these concepts visually separate:

- **Radar health/status**: collectors, connectors, freshness/stale state, and runtime switches.
- **Live feed**: recent observations and active ideas.
- **Tradable now**: only pending-confirmation or auto-placed handoff signals.
- **Funnel counters**: collected, deduped/merged, promoted, handed off, rejected at handoff.
- **Handoff history**: recent pending/placed/rejected/ignored signals with reason/error.

This prevents conflating source monitoring with execution ingest history.

## Scoring and verdicts

`src/server/radarReadModel.ts` is deterministic read-model logic. It enriches `RadarSignalRecord` rows with candidate score and verdict:

```text
score = statusWeight + freshnessScore + sourceMetaRichness - duplicatePenalty
```

Verdict thresholds are diagnostics only:

| asset class | actionable | bias | watch |
| --- | ---: | ---: | ---: |
| crypto | 70 | 45 | 20 |
| commodity | 80 | 55 | 30 |

Rejected and duplicate signals always return `ignore`. `auto_order_placed` is always actionable.

## Persistence and history cap

- Source observations live in shared persistence as `alphaRadarObservations` and are pruned/compacted.
- Execution handoff records live in shared persistence as `radarSignals`.
- Radar signal history is capped by `RADAR_SIGNAL_HISTORY_LIMIT` (500).

## Invariants

Run before shipping Radar-adjacent changes:

```bash
npm run check
npm run build
npm run invariants:radar-handoff
```

`invariants-radar-handoff` asserts that manual/auto handoff reuse the unified entry flow, duplicate signals are ignored, Trading Rules scope is enforced, and outcomes reconcile back to Radar records.
