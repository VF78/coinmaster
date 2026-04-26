# Coinmaster Target Architecture 2026

> **2026-04-27 update:** The target implementation path is now autonomous native Freqtrade. This older document remains useful as AS-IS/reference material, but custom CoinMaster execution/backtest/optimizer/Radar runtime should not be treated as the future runtime. See `docs/FREQTRADE_MIGRATION_2026-04-27.md`.


> **Issue:** #21 P1 — Target architecture for 24/7 realtime trading engine
> **Status:** Draft
> **Date:** 2026-02-25
> **Supersedes:** docs/ARCHITECTURE.md (MVP evolution path)

---

## Table of Contents

1. [AS-IS Architecture](#1-as-is-architecture)
2. [TO-BE Architecture](#2-to-be-architecture)
3. [Reliability Patterns](#3-reliability-patterns)
4. [Latency & SLO/SLA Targets](#4-latency--slosla-targets)
5. [RTO/RPO Targets](#5-rtorpo-targets)
6. [Roadmap (Phase A–E)](#6-roadmap-phase-ae)
7. [Migration on Current VPS](#7-migration-on-current-vps)
8. [Future Horizontal Scaling Path](#8-future-horizontal-scaling-path)

---

## 1. AS-IS Architecture

### 1.1 Topology

```
 Browser (React SPA)
        │ REST API
        ▼
┌─────────────────────────────────────────────────┐
│           Single Node.js Process (index.ts)     │
│                                                 │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐ │
│  │ Express  │  │ Paper     │  │ Drawdown     │ │
│  │ API +    │  │ Engine    │  │ Watchdog     │ │
│  │ Static   │  │ (5m/15m)  │  │ (5s loop)    │ │
│  └──────────┘  └───────────┘  └──────────────┘ │
│                                                 │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐ │
│  │ Risk     │  │ Runtime   │  │ Idempotency  │ │
│  │ Gates    │  │ Rules     │  │ Cache        │ │
│  │ (2 API   │  │ Cache     │  │ (in-memory)  │ │
│  │  calls)  │  │ (5s TTL)  │  │              │ │
│  └──────────┘  └───────────┘  └──────────────┘ │
│                                                 │
│  ┌──────────────────────────────────────────┐   │
│  │ HyperliquidAdapter (WS + REST)           │   │
│  │ - subscribeMids() → price feed           │   │
│  │ - placeOrder / cancelOrder / TP-SL       │   │
│  │ - REST fallback (60s polling)            │   │
│  └──────────────────────────────────────────┘   │
│                                                 │
│  ┌──────────────────────────────────────────┐   │
│  │ Persistence (lowdb default / PG Phase 1) │   │
│  │ - lowdb: synchronous JSON file writes    │   │
│  │ - PG: full JSONB snapshot upsert         │   │
│  │ - Dual-write shadow mode available       │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
        │                    │
        ▼                    ▼
   ┌──────────┐      ┌──────────────┐
   │ lowdb    │      │ PostgreSQL   │
   │ db.json  │      │ (snapshot)   │
   └──────────┘      └──────────────┘
```

### 1.2 Key Properties

| Property | Current State |
|----------|--------------|
| Process model | Single Node.js process, single event loop |
| Exchange | Hyperliquid only (adapter pattern ready for Bybit/Binance) |
| Persistence | lowdb (sync JSON) primary; PG snapshot bridge (Phase 1) |
| Strategy | 5m/15m engulfing + sweep detection; paper + live |
| Risk controls | Daily DD stop (20%), leverage cap (10x), per-symbol allocation, kill-switch |
| Supervision | None (no systemd/PM2); manual restart on crash |
| Observability | `/api/health/perf` endpoint; console.log; no structured logging |
| Auth | Bearer token + HMAC; single-operator |

### 1.3 Bottlenecks & Risks

| ID | Severity | Description | Impact |
|----|----------|-------------|--------|
| C1 | CRITICAL | lowdb `db.write()` blocks event loop (13 call sites) | Latency spikes O(n) with data size |
| C2 | CRITICAL | No process supervisor | Crash = manual restart = downtime |
| H1 | HIGH | WS reconnect fixed 3s delay, no exponential backoff | Exchange outage → reconnect storm → rate-limit ban |
| H2 | HIGH | HyperliquidAdapter lazy-init failure is sticky | Permanent exchange disconnect until restart |
| H3 | HIGH | PG snapshot = full JSONB upsert per flush | O(n) write cost, grows with data |
| H4 | HIGH | Risk gate evaluates 2 exchange API calls per order | Added latency on every trade |
| M1 | MEDIUM | Silent `.catch(() => undefined)` in 4+ locations | Hidden failures, delayed diagnosis |
| M2 | MEDIUM | In-memory caches lost on restart | Idempotency gaps during restart window |
| M3 | MEDIUM | tradeEvents/marketTicks arrays unbounded | Memory growth over weeks/months |
| M4 | MEDIUM | No rate-limit middleware on public endpoints | DoS vector |
| M5 | MEDIUM | Single CPU core, no clustering | CPU-bound tasks block everything |

---

## 2. TO-BE Architecture

### 2.1 Design Principles

1. **Fail-safe by default** — any component failure degrades gracefully, never corrupts state
2. **Crash-only design** — every process can be killed and restarted at any time
3. **Separation of concerns** — split monolith into logical planes (same process initially, separate later)
4. **Event-driven** — state changes flow through append-only event journal
5. **Observable** — structured logs, metrics, health probes at every boundary

### 2.2 Five-Plane Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY PLANE                       │
│  Structured JSON logs (pino) │ Health probes │ Metrics       │
│  Correlation IDs │ Alerting (heartbeat SLA) │ Dashboards     │
└─────────────────────────────────────────────────────────────┘

┌───────────────────────┐  ┌──────────────────────────────────┐
│    CONTROL PLANE      │  │        EXECUTION PLANE           │
│                       │  │                                  │
│ ▸ Express API server  │  │ ▸ Order execution pipeline       │
│ ▸ Runtime rules cache │  │   - validate → risk-gate →       │
│ ▸ UI (React SPA)      │  │     alloc-gate → submit →        │
│ ▸ Config management   │  │     TP/SL → ack/reject           │
│ ▸ Admin endpoints     │  │ ▸ Idempotency cache (bounded)    │
│                       │  │ ▸ TP/SL auto-apply               │
│                       │  │ ▸ Emergency close procedure       │
└───────────────────────┘  └──────────────────────────────────┘

┌───────────────────────┐  ┌──────────────────────────────────┐
│     RISK PLANE        │  │          DATA PLANE              │
│                       │  │                                  │
│ ▸ Drawdown watchdog   │  │ ▸ Market data ingest (WS + REST) │
│   (5s interval)       │  │ ▸ Account state cache (TTL)       │
│ ▸ Daily DD evaluator  │  │ ▸ Position snapshot cache          │
│ ▸ Leverage guard      │  │ ▸ Trade event journal (append)     │
│ ▸ Symbol allocation   │  │ ▸ PostgreSQL (normalized, Phase 4) │
│   guard               │  │ ▸ Exchange adapter (Hyperliquid)   │
│ ▸ Kill-switch         │  │   - WS with exp. backoff           │
│ ▸ Audit log buffer    │  │   - REST fallback                  │
│                       │  │   - Init retry on failure           │
└───────────────────────┘  └──────────────────────────────────┘
```

### 2.3 Plane Responsibilities

#### Control Plane
- **Owner:** Express API + React SPA
- **Responsibility:** User-facing operations, configuration, dashboard
- **Key change:** Delegates all trading logic to Execution Plane via internal call; never directly touches exchange

#### Execution Plane
- **Owner:** Order execution pipeline
- **Responsibility:** Validate, gate, submit, track orders end-to-end
- **Key change:** Pipeline stages become explicit (validate → risk → alloc → submit → post-trade); each stage emits a trade event

#### Risk Plane
- **Owner:** Drawdown watchdog + risk evaluators
- **Responsibility:** Continuous risk monitoring, circuit-breaking, emergency close
- **Key change:** Risk evaluation result is cached (TTL 1–5s) instead of calling exchange on every order; watchdog can trigger circuit breaker independent of API

#### Data Plane
- **Owner:** Exchange adapter + persistence
- **Responsibility:** Market data ingest, state persistence, event journal
- **Key change:** WS reconnect with exponential backoff (cap 60s); adapter init retry; account state cache with TTL; PG normalized tables

#### Observability Plane
- **Owner:** Logging + metrics + alerting
- **Responsibility:** Structured JSON logs, health probes, heartbeat SLA (15-min), correlation IDs
- **Key change:** Replace console.log with pino; add `/metrics` endpoint for Prometheus scraping; alerting on heartbeat miss

### 2.4 Component Interaction (TO-BE)

```
User ──► Control Plane ──► Execution Plane ──► Data Plane (exchange)
              │                    │                   │
              │                    ▼                   │
              │              Risk Plane ◄──────────────┘
              │                    │          (cached account state)
              ▼                    ▼
         Observability Plane (logs, metrics, alerts)
              │
              ▼
         Data Plane (PostgreSQL, event journal)
```

---

## 3. Reliability Patterns

### 3.1 Idempotency

| Concern | Pattern |
|---------|---------|
| Order submission | `clientOrderId` → MD5-based CLOID; exchange-level dedup + in-memory cache (30min TTL, max 1000) |
| TP/SL placement | Tied to parent order `clientOrderId`; skip if already exists |
| DB writes | PostgreSQL UPSERT on `singleton_key`; no duplicate rows |
| Event journal | Sequential `seq` + `prevHash` chain; duplicates detectable |

**TO-BE improvement:** Persist idempotency cache to PostgreSQL table; survives restarts.

### 3.2 Outbox Pattern

Current state has no outbox. TO-BE introduces:

```
┌──────────────────────────────────────────────────┐
│ Transaction:                                     │
│   1. Write trade_event to events table           │
│   2. Write outbox entry (pending) in same txn    │
│ Outbox worker:                                   │
│   - Poll pending entries every 1s                │
│   - Execute side-effect (TP/SL, notification)    │
│   - Mark entry as processed                      │
│   - Retry on failure (max 3, then dead-letter)   │
└──────────────────────────────────────────────────┘
```

This ensures TP/SL orders are never lost even if the process crashes between parent order ack and TP/SL submission.

### 3.3 Retry Policy

| Operation | Strategy | Max Retries | Backoff | Timeout |
|-----------|----------|-------------|---------|---------|
| WS reconnect | Exponential + jitter | ∞ | 1s → 60s cap | — |
| Exchange REST call | Linear | 3 | 500ms | 10s |
| Emergency close | Aggressive retry | 5 | 400ms | 30s total |
| DB write (PG) | Exponential | 3 | 100ms → 1s | 5s |
| Adapter init | Exponential | 5 | 2s → 30s | 60s total |
| Outbox delivery | Fixed | 3 | 1s | 5s |

### 3.4 Circuit Breakers

| Circuit | Trip Condition | Open Duration | Half-Open | Fallback |
|---------|---------------|---------------|-----------|----------|
| Exchange REST | 5 consecutive failures or 3 timeouts in 30s | 30s | 1 probe call | Return cached data + log warning |
| WS feed | 3 disconnects in 5 min | 60s | Reconnect attempt | REST polling fallback (already exists) |
| DB write | 3 consecutive PG failures | 15s | 1 probe write | Buffer in-memory, flush on recovery |
| Risk evaluation | Exchange call timeout | 10s | 1 probe | Use last-known-good cached values; block new orders if cache >30s stale |

### 3.5 Fail-Safe Behaviors

| Scenario | Behavior |
|----------|----------|
| Exchange WS disconnected | REST polling fallback; log warning; circuit breaker tracks |
| PostgreSQL unreachable | Buffer writes in-memory (bounded); alert; degrade to read-only for new trades |
| Risk gate timeout | Block new orders; watchdog continues with last-known state |
| Adapter init failure | Retry with backoff; expose `unhealthy` status; block trading until recovered |
| Uncaught exception | Log full stack; flush audit buffer; close positions if `fail_safe_close=true`; restart via systemd |
| OOM / SIGKILL | systemd restarts; PG has last flushed state; event journal allows replay |
| Drawdown breach | Emergency close all; set kill-switch; require manual re-enable |

---

## 4. Latency & SLO/SLA Targets

### 4.1 Internal SLOs (self-imposed)

| Metric | SLO | Measurement |
|--------|-----|-------------|
| API response p50 | < 50ms | Express middleware timer |
| API response p95 | < 200ms | Express middleware timer |
| API response p99 | < 500ms | Express middleware timer |
| Event loop lag | < 20ms sustained | `setImmediate` probe |
| DB write (PG) latency p95 | < 20ms | Instrumented flush |
| Order round-trip (submit → ack) | < 500ms | Trade event timestamps |
| Risk gate evaluation | < 50ms (cached) | Middleware timer |
| WS price tick → ingest | < 10ms | Timestamp delta |
| Heartbeat interval | ≤ 15 min | Health probe |
| Price feed gap | < 120s before alert | WS last-tick timer |

### 4.2 Availability SLAs

| Component | Target | Measurement |
|-----------|--------|-------------|
| Trading API uptime | 99.5% monthly (≤ 3.6h downtime) | Health probe |
| Price feed availability | 99.0% monthly | WS + REST combined |
| Risk watchdog uptime | 99.9% (≤ 43min downtime/month) | Watchdog heartbeat |
| Dashboard availability | 99.0% | HTTP health check |

### 4.3 Data Freshness

| Data | Staleness Threshold | Action on Breach |
|------|-------------------|------------------|
| Mid prices | > 120s | Alert + degrade strategy signals |
| Account state | > 30s | Block new orders |
| Open positions | > 30s | Block new orders |
| Runtime rules | > 15s (current: 5s refresh) | Use last-known-good |

---

## 5. RTO/RPO Targets

### 5.1 Recovery Targets by Scenario

| Scenario | RTO | RPO | Recovery Method |
|----------|-----|-----|-----------------|
| Process crash (OOM/panic) | < 30s | 0 (event journal) | systemd `Restart=always` + `RestartSec=3` |
| VPS reboot (planned) | < 2 min | 0 | systemd auto-start; PG auto-start |
| VPS hardware failure | < 30 min | < 5 min | Re-provision from backup; PG WAL replay |
| PostgreSQL crash | < 1 min | < 30s | PG auto-restart; WAL recovery |
| Exchange API outage | N/A (external) | 0 | Circuit breaker + REST fallback; resume on recovery |
| Corrupted state | < 15 min | < 1 min | Restore from PG snapshot; replay event journal |
| DNS/network partition | < 5 min | 0 | VPS provider failover; cached state preserved |

### 5.2 Backup Strategy

| Asset | Frequency | Retention | Method |
|-------|-----------|-----------|--------|
| PostgreSQL full | Daily 03:00 UTC | 30 days | `pg_dump` → compressed → off-site |
| PostgreSQL WAL | Continuous | 7 days | WAL archiving to local + off-site |
| Event journal | Continuous (append-only) | Permanent | Part of PG backup |
| Configuration (.env) | On change | 10 versions | Encrypted backup |
| lowdb (db.json) | Deprecated after PG cutover | — | — |

---

## 6. Roadmap (Phase A–E)

### Phase Overview

| Phase | Name | Duration | Prerequisites |
|-------|------|----------|---------------|
| A | Observability & Process Hardening | 1–2 weeks | None |
| B | Persistence Cutover (PG primary) | 1–2 weeks | Phase A |
| C | Runtime Separation & Reliability | 2–3 weeks | Phase B |
| D | Advanced Risk & Feed Resilience | 1–2 weeks | Phase C |
| E | Multi-Exchange & Horizontal Prep | 2–4 weeks | Phase D |

### Phase A — Observability & Process Hardening

| # | Task | Done Criteria | Rollback |
|---|------|---------------|----------|
| A1 | Replace `console.log` with pino JSON logger | All log output is structured JSON; `grep console.log src/` returns 0 hits | Revert logger import; no data loss |
| A2 | Add systemd unit (`coinmaster.service`) | `systemctl status coinmaster` shows active; auto-restarts within 5s of `kill -9` | `systemctl disable coinmaster`; revert to manual start |
| A3 | Instrument flush latency + risk gate latency | `/api/health/perf` includes `flushLatencyMs` and `riskGateLatencyMs` p95 values | Remove instrumentation code; no side effects |
| A4 | WS reconnect exponential backoff (1s → 60s cap) | 10 rapid disconnects produce delays: 1, 2, 4, 8, 16, 32, 60, 60, 60, 60 | Revert to fixed 3s delay |
| A5 | Fix adapter lazy-init failure (add retry/reset) | Simulated init failure recovers within 30s without restart | Revert to current sticky behavior |
| A6 | Replace silent `.catch(() => undefined)` | All catch blocks log via `log.warn` with context | Revert catch blocks |
| A7 | Add 15-min heartbeat SLA alerting | Missing heartbeat triggers alert within 15 min | Disable alert; no side effects |

### Phase B — Persistence Cutover (PostgreSQL Primary)

| # | Task | Done Criteria | Rollback |
|---|------|---------------|----------|
| B1 | Validate dual-write reconciliation (0 diffs over 48h) | `npm run persistence:reconcile` reports 0 mismatches for 48 consecutive hours | Continue dual-write; no data loss |
| B2 | Switch `PERSISTENCE_BACKEND=postgres` (PG primary) | Server starts with PG primary; all CRUD operations verified via smoke tests | Set `PERSISTENCE_BACKEND=lowdb`; data preserved in both stores |
| B3 | Implement bounded event/tick arrays in PG | `tradeEvents` and `marketTicks` pruned to configurable max (default 50K); archived rows moved to `_archive` table | Remove pruning; data preserved |
| B4 | Add `pg_dump` daily backup cron | Backup file created daily at 03:00 UTC; restore tested monthly | Remove cron entry |
| B5 | Deprecate lowdb writes | `PERSISTENCE_DUAL_WRITE=false`; lowdb file no longer updated | Re-enable dual-write |

### Phase C — Runtime Separation & Reliability

| # | Task | Done Criteria | Rollback |
|---|------|---------------|----------|
| C1 | Extract execution pipeline into module (`src/execution/`) | Order flow passes through explicit stages; each stage emits trade event; `index.ts` < 800 LOC | Inline pipeline back into index.ts |
| C2 | Extract risk plane into module (`src/risk/`) | Watchdog, DD evaluator, risk gates in dedicated module; testable in isolation | Inline back into index.ts |
| C3 | Cache risk evaluation result (1–5s TTL) | Risk gate uses cached account state; exchange calls reduced by 80%+ | Revert to per-request exchange calls |
| C4 | Implement circuit breakers (exchange REST, WS, DB) | Circuit state visible via `/api/health/circuits`; trips verified by fault injection | Remove circuit breaker wrappers |
| C5 | Persist idempotency cache to PostgreSQL | Cache survives restart; tested by: submit order → restart → re-submit same `clientOrderId` → dedup | Revert to in-memory-only cache |
| C6 | Add rate-limit middleware | Public endpoints throttled to 60 req/min per IP; trading endpoints to 10 req/s | Remove middleware |

### Phase D — Advanced Risk & Feed Resilience

| # | Task | Done Criteria | Rollback |
|---|------|---------------|----------|
| D1 | Outbox pattern for TP/SL delivery | TP/SL survives process crash between parent ack and TP/SL submit; verified by fault injection | Remove outbox; revert to inline TP/SL |
| D2 | Feed staleness detection + strategy degradation | Price gap > 120s triggers `strategy_degraded` state; no new signals generated; alert fired | Remove staleness check; strategy always active |
| D3 | Account state TTL cache with invalidation on fills | Account snapshot cached; invalidated on fill events; cache miss triggers fresh fetch | Revert to per-request fetch |
| D4 | Dead-letter queue for failed outbox entries | Failed deliveries after 3 retries moved to DLQ; `/api/admin/dlq` endpoint to inspect/retry | Remove DLQ; failed deliveries logged only |
| D5 | Graceful degradation on PG unavailability | In-memory buffer (max 100 events); auto-flush on PG recovery; alert on buffer >50% | Revert to immediate write (fail on PG down) |

### Phase E — Multi-Exchange & Horizontal Prep

| # | Task | Done Criteria | Rollback |
|---|------|---------------|----------|
| E1 | Normalize PostgreSQL schema (Phase 4 from migration plan) | All entities in dedicated tables; `001_initial_schema.sql` applied; queries use SQL not JSONB | Revert to JSONB snapshot mode |
| E2 | Implement BybitAdapter | Adapter passes same integration tests as HyperliquidAdapter; capability flags declared | Remove adapter; single-exchange mode |
| E3 | Extract exchange connection manager | Multiple adapters managed by connection registry; health per exchange; failover between exchanges for same asset | Inline single adapter |
| E4 | Prepare clustering (Node.js cluster or separate processes) | State shared via PG; no in-memory singletons; session affinity not required | Revert to single process |
| E5 | Document horizontal scaling architecture | Architecture doc for multi-VPS deployment; load balancer, shared PG, WS fan-out | No code change; doc-only |

---

## 7. Migration on Current VPS

All phases A–D are designed to run on a **single VPS** (current Hetzner instance).

### 7.1 Resource Requirements

| Phase | CPU | RAM | Disk | PostgreSQL |
|-------|-----|-----|------|-----------|
| A (current) | 1 vCPU | 1 GB | 10 GB | Existing (snapshot mode) |
| B | 1 vCPU | 1 GB | 20 GB | Primary (JSONB + WAL) |
| C | 1 vCPU | 2 GB | 20 GB | Primary (JSONB + idempotency table) |
| D | 2 vCPU | 2 GB | 30 GB | Primary (JSONB + outbox + DLQ) |
| E | 2 vCPU | 4 GB | 50 GB | Primary (normalized schema) |

### 7.2 VPS Migration Strategy

```
Phase A–C: Single VPS, single process
  ┌──────────────────────────────┐
  │ VPS (Hetzner)                │
  │ ┌──────────┐ ┌────────────┐ │
  │ │ Node.js  │ │ PostgreSQL │ │
  │ │ coinmaster│ │ (local)    │ │
  │ └──────────┘ └────────────┘ │
  │ systemd supervised           │
  │ pino → journald              │
  └──────────────────────────────┘

Phase D: Single VPS, more capable
  ┌──────────────────────────────┐
  │ VPS (Hetzner, upgraded)      │
  │ ┌──────────┐ ┌────────────┐ │
  │ │ Node.js  │ │ PostgreSQL │ │
  │ │ coinmaster│ │ + WAL      │ │
  │ │ + outbox  │ │ + backups  │ │
  │ └──────────┘ └────────────┘ │
  │ systemd + cron (backups)     │
  │ pino → journald → alerts     │
  └──────────────────────────────┘
```

### 7.3 Zero-Downtime Deployment

For Phases A–D (single VPS), deployment follows:

1. `git pull` latest release
2. `npm run build` (build SPA + TypeScript)
3. `npm run check` (type-check)
4. `systemctl restart coinmaster` (graceful shutdown → restart)
5. `npm run ops:smoke` (verify health)

Expected downtime per deploy: **< 10 seconds** (graceful shutdown + cold start).

### 7.4 Rollback Procedure

1. `git checkout <previous-tag>`
2. `npm run build`
3. `systemctl restart coinmaster`
4. If DB schema changed: run reverse migration SQL
5. `npm run ops:smoke`

---

## 8. Future Horizontal Scaling Path

Phase E prepares for horizontal scaling. This section describes the **future** architecture (not implemented in Phases A–D).

### 8.1 Target Topology

```
                    ┌─────────────────┐
                    │  Load Balancer  │
                    │  (nginx/HAProxy)│
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
        │ Node.js   │ │ Node.js   │ │ Node.js   │
        │ API (1)   │ │ API (2)   │ │ Worker(1) │
        │ stateless │ │ stateless │ │ watchdog  │
        └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────▼────────┐
                    │  PostgreSQL     │
                    │  (managed/HA)   │
                    │  + pgbouncer    │
                    └─────────────────┘
```

### 8.2 Scaling Constraints

| Concern | Solution |
|---------|----------|
| In-memory caches | Move to PostgreSQL (idempotency, risk cache) |
| Watchdog singleton | Leader election via PG advisory lock |
| WS feed | Dedicated feed process; API processes subscribe via PG NOTIFY or Redis pub/sub |
| Session state | Stateless API; all state in PG |
| File-based persistence | Eliminated (PG only) |

### 8.3 When to Scale Horizontally

Horizontal scaling is warranted when:
- Single Node.js process CPU > 70% sustained
- Multiple exchanges require dedicated connections
- Multi-operator/SaaS mode required
- RTO requirement drops below 10s (active-passive failover)

Until these conditions are met, **vertical scaling on a single VPS is sufficient and simpler**.

---

## Related Documents

- [ADR-001: Runtime Separation](ADR/ADR-001-runtime-separation.md)
- [ADR-002: Persistence and Eventing](ADR/ADR-002-persistence-and-eventing.md)
- [ARCHITECTURE.md](ARCHITECTURE.md) — MVP evolution path (predecessor)
- [AUDIT_P1_10_BASELINE.md](AUDIT_P1_10_BASELINE.md) — Risk registry & performance baseline
- [POSTGRES_MIGRATION_PLAN.md](POSTGRES_MIGRATION_PLAN.md) — 5-phase PostgreSQL migration
- [SECURITY_REQUIREMENTS.md](SECURITY_REQUIREMENTS.md) — Trading security requirements
