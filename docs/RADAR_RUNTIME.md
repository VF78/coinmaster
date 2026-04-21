# RADAR_RUNTIME.md

**Date:** 2026-04-21
**Purpose:** Runtime behavior and source-class policy for Radar signal ingestion.

## Overview

Radar is an **upstream signal layer** that ingests trade signals from external sources (connected channels, feeds, webhooks) and hands them off to the unified trading engine via the existing `handoffStrategyEntrySignal` flow.

**Architectural constraints:**
- Radar is read-only from the trading engine's perspective
- No second execution engine
- Handoff into existing confirm/auto-open flow (same as engulfing/FVG)
- No admin UI required — signals visible in `/api/radar/signals` endpoint

## Source Classes

Radar signals are categorized by **source class** based on connector type and ingestion freshness requirements.

### 1. **Connected Channels** (push-based, near-real-time)

**Examples:** Telegram, Discord, Slack bots listening to trade signal channels.

**Runtime behavior:**
- **Freshness:** < 1 minute from external message timestamp to ingestion
- **Transport:** WebSocket / long-polling / webhook push
- **Reconnect policy:** Auto-reconnect on disconnect with exponential backoff (2s → 30s max)
- **Dedupe window:** 5 minutes (configurable via `RADAR_SIGNAL_DEDUP_MS`)
- **Metadata required:**
  - `connector` (e.g., "telegram", "discord")
  - `kind` (e.g., "channel-message", "webhook")
  - `channel` (e.g., channel ID or name)
  - `externalId` (message ID for idempotency)
  - `messageTs` (optional, for ordering/freshness)

**Implementation notes:**
- Use existing connector libraries (e.g., `node-telegram-bot-api`, `discord.js`)
- Store connection state outside DB (in-memory or stateful connector service)
- No canonical engine state — Radar is purely upstream

### 2. **External Feeds** (poll-based, bounded-freshness)

**Examples:** REST API endpoints, RSS feeds, external signal providers.

**Runtime behavior:**
- **Freshness:** 1–15 minutes (poll interval configurable per feed)
- **Transport:** HTTP GET/POST polling
- **Retry policy:** Up to 3 retries on failure with 5s–30s backoff
- **Dedupe window:** Same as connected channels (5 minutes)
- **Metadata required:**
  - `connector` (e.g., "rest-api", "rss")
  - `kind` (e.g., "feed-poll", "webhook")
  - `externalId` (feed item ID for idempotency)

**Implementation notes:**
- Use simple `setInterval` for periodic polling
- No persistent queue — if a poll fails, next interval will retry
- Log poll failures but do not block ingestion

### 3. **Manual/Webhook Ingestion** (on-demand)

**Examples:** Owner API (`POST /api/radar/signals`), external webhook payloads.

**Runtime behavior:**
- **Freshness:** Immediate (no buffering)
- **Transport:** HTTP POST to `/api/radar/signals` or `/api/radar/signals/batch`
- **Dedupe window:** Same as above (5 minutes)
- **Metadata required:**
  - `source` label (free-form, identifies the originating system)
  - Optional: `sourceMeta` for richer context

**Implementation notes:**
- Already implemented in `src/server/index.ts:6070-6115`
- Batch endpoint supports up to 100 signals per request
- No authentication for owner-only endpoints (protected by `ownerAuth` middleware)

## Ingestion Flow

1. **Receive signal** from connector/feed/API
2. **Normalize payload** → `RadarSignalIngestPayload`
3. **Dedupe check** using `dedupeKey` or symbol/side/source/reason tuple
4. **Store record** with `status='ignored'` initially
5. **Handoff to trading engine** via `handoffStrategyEntrySignal`
6. **Update status** based on handoff result:
   - `pending_confirmation` → queued for manual confirm
   - `auto_order_placed` → order submitted successfully
   - `rejected` → blocked by risk gates / allocation / bias
   - `ignored` → duplicate or invalid

7. **Reconcile outcome** after pending confirmation or order fill

## Deduplication Policy

**Dedupe key construction** (if all metadata available):
```
connector|kind|channel|externalId|messageTs|symbol|side|timeframe
```

**Fallback** (if metadata incomplete):
```
symbol|side|timeframe|source|reason
```

**Dedupe window:** 5 minutes (`RADAR_SIGNAL_DEDUP_MS`)

**Duplicate handling:**
- Set `duplicateOf` to original signal ID
- Set `error='duplicate_signal'`
- Do NOT trigger handoff (no order placement or pending confirmation)
- Include in history for audit/debugging

## Source Quality Tracking

Radar tracks **source quality rollups** by:
- Source label
- Connector type
- Asset class
- Verdict (actionable/bias/watch/ignore)

**Metrics per source:**
- Total signals
- Pending confirmations
- Auto-orders placed
- Rejected signals
- Ignored signals
- Duplicates
- Last seen timestamp

**View:** `GET /api/radar/signals` → `summary.qualityBySource`, `qualityByConnector`, etc.

## Configuration

**Environment variables:**

```bash
# Radar signal history retention limit (default: 500)
# Note: Signals are compacted on every write, keeping only the N most recent.
RADAR_SIGNAL_HISTORY_LIMIT=500

# Dedupe window in milliseconds (default: 5 minutes)
RADAR_SIGNAL_DEDUP_MS=300000
```

**No external config files required.** All connector setup (API keys, channel IDs, webhook URLs) should be managed by the operator outside the Coinmaster codebase (e.g., environment variables, Kubernetes secrets, `.env` files).

## Bootstrap Procedure

**On server startup:**
1. Load existing Radar signals from DB (`db.data.radarSignals`)
2. Compact to history limit (`compactRadarSignals`)
3. No automatic reconnection to external connectors — operator must start connector services separately

**No persistent connection state in DB.** Connectors should handle their own reconnection logic (e.g., Telegram bot auto-reconnects on network failure).

## Operational Checklist

- [ ] Confirm `/api/radar/signals` endpoint returns valid summary
- [ ] Test manual signal ingestion via `POST /api/radar/signals`
- [ ] Verify duplicate signals are correctly marked and skipped
- [ ] Confirm handoff to `pending_confirmation` in manual mode
- [ ] Confirm handoff to `auto_order_placed` in auto mode
- [ ] Run `npm run invariants:radar-handoff` to verify regression coverage

## Future Extensions (NOT in deterministic baseline)

- [ ] Optional AI second pass (issue #47) — explicitly deferred
- [ ] Admin UI for source management — not planned
- [ ] Persistent connector state in DB — not needed (use external services)
- [ ] Advanced routing/filtering rules — not needed (keep simple)

## Related Files

- `src/server/radarReadModel.ts` — Scoring, verdict policy, enrichment
- `src/server/index.ts` — Ingest logic, handoff, reconciliation
- `scripts/invariants-radar-handoff.ts` — Regression-safe handoff coverage
- `src/shared/dto.ts` — Radar signal types

## References

- Issue #41: Radar epic
- Issue #42: Near-real-time ingress and runtime
- Issue #43: Simplified monitoring, scoring, and trade-candidate selection
- Issue #44: Asset-class verdict policy
- Issue #45: Regression-safe handoff into existing confirm/auto-open flow
- Issue #46: Source-quality feedback
