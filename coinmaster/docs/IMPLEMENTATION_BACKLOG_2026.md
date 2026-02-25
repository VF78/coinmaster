# Implementation Backlog 2026

> **Parent issue:** #21 P1 — Target architecture for 24/7 realtime trading engine
> **Source docs:** TARGET_ARCHITECTURE_2026.md, ADR-001, ADR-002, AUDIT_P1_10_BASELINE.md
> **Created:** 2026-02-25
> **Status:** Active

---

## Epic Overview

| Epic | Name | Phase | Est. (SP) | Est. (days) | Owner Role |
|------|------|-------|-----------|-------------|------------|
| E1 | Observability Foundation | A | 8 | 3–4 | Backend Dev |
| E2 | Process Hardening | A | 8 | 3–4 | Backend Dev / DevOps |
| E3 | PostgreSQL Primary Cutover | B | 13 | 5–7 | Backend Dev |
| E4 | Runtime Separation (Planes) | C | 21 | 8–10 | Backend Dev |
| E5 | Reliability Patterns | C | 13 | 5–7 | Backend Dev |
| E6 | Advanced Risk & Outbox | D | 13 | 5–7 | Backend Dev |
| E7 | Feed Resilience & Degradation | D | 8 | 3–4 | Backend Dev |
| E8 | Multi-Exchange & Horizontal Prep | E | 21 | 8–12 | Backend Dev / Architect |

**Total:** ~105 SP / ~40–55 days

---

## E1 — Observability Foundation

**Goal:** Replace ad-hoc logging with structured JSON, add latency instrumentation, and establish heartbeat-based alerting.

**Scope:**
- Replace `console.log` → pino structured JSON logger (task A1)
- Instrument flush latency + risk gate latency → `/api/health/perf` (task A3)
- Replace silent `.catch(() => undefined)` with `.catch(log.warn)` (task A6)
- Add correlation IDs to order lifecycle logs
- 15-min heartbeat SLA alerting (task A7)

**Out-of-scope:**
- Prometheus/Grafana dashboards (future)
- External alerting integrations (PagerDuty, Slack)

**Definition of Done (DoD):**
- [ ] `grep -r "console.log" src/` returns 0 hits (only pino)
- [ ] `/api/health/perf` includes `flushLatencyMs` and `riskGateLatencyMs` p95
- [ ] All `.catch(() => undefined)` replaced (0 hits in `grep`)
- [ ] Order lifecycle logs include `correlationId` field
- [ ] Missing heartbeat triggers alert within 15 min
- [ ] `npm run check && npm run build` pass
- [ ] No trading logic changes

**Rollback:**
- Revert pino imports → re-add console.log (no data loss)
- Remove instrumentation code (no side effects)
- Disable heartbeat alerting

**Risks:**
- Pino formatter change may break existing log parsers/grep scripts → document format change in CHANGELOG
- Correlation ID propagation may miss edge paths → verify with integration test

**Owner role:** Backend Dev
**Estimate:** 8 SP / 3–4 days

---

## E2 — Process Hardening

**Goal:** Ensure the process survives crashes, restarts automatically, and handles edge cases in WS/adapter lifecycle.

**Scope:**
- systemd unit file `coinmaster.service` with `Restart=always` (task A2)
- `process.on('SIGTERM'/'SIGINT')` graceful shutdown: clear timers, close WS, drain DB pool (AUDIT C1, C2)
- `process.on('uncaughtException'/'unhandledRejection')` with structured logging (AUDIT C1)
- WS reconnect exponential backoff 1s → 60s cap (task A4, AUDIT H3)
- Adapter lazy-init failure retry/reset (task A5, AUDIT H5)
- Cap idempotency cache (LRU 1000) + `.unref()` risk audit interval (AUDIT H1, H2)
- Express error middleware (4-arg handler)
- Rate-limit middleware on public endpoints (task C6, AUDIT M3)

**Out-of-scope:**
- Node.js clustering / multi-process (Phase E)
- Memory/file-descriptor resource limits (ops runbook item)

**Definition of Done (DoD):**
- [ ] `systemctl status coinmaster` shows active; `kill -9` → restart within 5s
- [ ] `kill -TERM <pid>` exits cleanly within 5s (timers cleared, WS closed, DB drained)
- [ ] Uncaught errors logged as structured JSON (not silent crash)
- [ ] 10 rapid WS disconnects produce backoff: 1,2,4,8,16,32,60,60,60,60
- [ ] Simulated adapter init failure recovers within 30s
- [ ] Idempotency cache capped at 1000 entries
- [ ] Public endpoints return 429 at >60 req/min/IP
- [ ] `npm run check && npm run build` pass

**Rollback:**
- `systemctl disable coinmaster` → manual start
- Revert WS backoff → fixed 3s delay
- Revert adapter retry → sticky failure
- Remove rate-limit middleware

**Risks:**
- systemd unit requires root/sudo on VPS → provide deployment instructions
- Rate-limiting may block legitimate bursts from dashboard polling → tune thresholds

**Owner role:** Backend Dev / DevOps
**Estimate:** 8 SP / 3–4 days

---

## E3 — PostgreSQL Primary Cutover

**Goal:** Complete PG migration: validate dual-write, switch to PG primary, set up backups, deprecate lowdb.

**Scope:**
- Validate dual-write reconciliation 0 diffs over 48h (task B1)
- Switch `PERSISTENCE_BACKEND=postgres` (task B2)
- Bounded event/tick arrays in PG with archival (task B3, AUDIT M7)
- `pg_dump` daily backup cron (task B4)
- Deprecate lowdb writes (task B5)
- Run cutover-check and rollback-check scripts (Phase 3 of PG migration plan)

**Out-of-scope:**
- Normalized PG schema (Phase E, task E1)
- WAL archiving to off-site (ops hardening)
- lowdb dependency removal (cleanup after stabilization)

**Definition of Done (DoD):**
- [ ] `npm run persistence:reconcile` reports 0 mismatches for 48 consecutive hours
- [ ] `npm run persistence:cutover-check` exits 0
- [ ] `npm run persistence:rollback-check` exits 0
- [ ] Server runs with `PERSISTENCE_BACKEND=postgres`; all CRUD verified via smoke tests
- [ ] `tradeEvents` pruned to configurable max (default 50K); archive table exists
- [ ] `pg_dump` cron fires daily at 03:00 UTC; restore tested at least once
- [ ] `PERSISTENCE_DUAL_WRITE=false` — lowdb no longer updated
- [ ] `npm run check && npm run build` pass

**Rollback:**
- Set `PERSISTENCE_BACKEND=lowdb` → restart → immediate revert
- Restore `data/db.json.pre_cutover` if lowdb data is stale
- Re-enable dual-write for retry

**Risks:**
- PG becomes hard dependency — PG crash = downtime until restart → mitigate with E6/D5 (in-memory buffer)
- Dual-write divergence during validation → reconcile script catches; extend window if needed
- Backup restore never tested → add monthly restore drill to ops runbook

**Owner role:** Backend Dev
**Estimate:** 13 SP / 5–7 days

---

## E4 — Runtime Separation (Planes)

**Goal:** Extract monolith `index.ts` (1175 LOC) into five logical planes per ADR-001, making each testable in isolation.

**Scope:**
- Extract Execution Plane → `src/execution/` (pipeline, idempotency, tpsl) (task C1)
- Extract Risk Plane → `src/risk/` (watchdog, gates, cache) (task C2)
- Establish plane interfaces (typed, no circular deps)
- Slim `index.ts` to ~200 LOC bootstrap + wiring
- Unit tests for extracted modules (risk gates, pipeline stages)

**Out-of-scope:**
- Control Plane extraction (Express routes stay in `src/server/` for now)
- Data Plane extraction (exchange adapter stays in `src/exchange/`)
- Observability Plane extraction (logger stays cross-cutting)
- Process-level separation (Phase E)

**Definition of Done (DoD):**
- [ ] `src/execution/` exists with pipeline.ts, idempotency.ts, tpsl.ts
- [ ] `src/risk/` exists with watchdog.ts, gates.ts, cache.ts
- [ ] `src/server/index.ts` < 400 LOC (target: ~200)
- [ ] Order flow passes through explicit stages; each stage emits trade event
- [ ] Dependency direction: Control → Execution → Risk → Data → Core (no cycles)
- [ ] Risk watchdog testable without Express server
- [ ] Execution pipeline testable without watchdog
- [ ] All existing tests pass + new unit tests for extracted modules
- [ ] `npm run check && npm run build` pass

**Rollback:**
- Inline modules back into index.ts (git revert per PR)
- Each extraction is a standalone PR — revert individually

**Risks:**
- Partial extraction stalls → enforce "one module per PR" rule; block merging until module is self-contained
- Import path changes break consumers → update all imports in same PR; use barrel exports
- Behavioral regression in wiring → integration test covering full order flow

**Owner role:** Backend Dev
**Estimate:** 21 SP / 8–10 days

---

## E5 — Reliability Patterns

**Goal:** Add circuit breakers, cached risk evaluation, persistent idempotency, and bounded caches.

**Scope:**
- Circuit breakers: exchange REST, WS feed, DB write, risk eval (task C4)
- Cache risk evaluation result 1–5s TTL (task C3, AUDIT M2)
- Persist idempotency cache to PostgreSQL (task C5)
- Circuit state visible via `/api/health/circuits`
- Bounded in-memory caches (tradeEvents in-memory, marketTicks)

**Out-of-scope:**
- Outbox pattern (E6)
- Feed staleness detection (E7)
- External circuit breaker libraries (use simple state machine)

**Definition of Done (DoD):**
- [ ] Circuit breaker states: closed/open/half-open for each circuit
- [ ] `/api/health/circuits` returns state of all 4 circuits
- [ ] Risk gate uses cached account state; exchange API calls reduced by ≥80%
- [ ] Fault injection: 5 consecutive REST failures → circuit opens → 30s open → half-open probe
- [ ] Idempotency cache in PG: submit order → restart → re-submit same `clientOrderId` → dedup
- [ ] `npm run check && npm run build` pass

**Rollback:**
- Remove circuit breaker wrappers → direct calls
- Revert risk cache → per-request exchange calls
- Revert idempotency → in-memory only

**Risks:**
- Circuit breaker false-positive trips during normal exchange latency → tune thresholds carefully
- Cached risk data staleness → enforce max 5s TTL; block orders if cache >30s stale
- PG idempotency table growth → add TTL-based cleanup (30 min retention)

**Owner role:** Backend Dev
**Estimate:** 13 SP / 5–7 days

---

## E6 — Advanced Risk & Outbox

**Goal:** Guarantee TP/SL delivery through crashes via outbox pattern; add dead-letter queue and PG degradation handling.

**Scope:**
- Outbox pattern for TP/SL delivery (task D1)
- Dead-letter queue for failed outbox entries (task D4)
- Graceful degradation on PG unavailability — in-memory buffer (task D5)
- Admin API: `/api/admin/dlq` inspect/retry
- SQL migrations: `outbox` table, DLQ status

**Out-of-scope:**
- Outbox for notifications / alerts (future)
- Multi-exchange outbox routing
- External message broker (RabbitMQ, etc.)

**Definition of Done (DoD):**
- [ ] TP/SL survives process crash between parent ack and TP/SL submit (fault injection verified)
- [ ] Outbox worker polls every 1s; retries up to 3 times; dead-letters on exhaustion
- [ ] `/api/admin/dlq` returns dead-lettered entries; supports retry/discard
- [ ] PG down → in-memory buffer (max 100 events); auto-flush on recovery; alert on buffer >50%
- [ ] Transaction boundary: trade_event + outbox entry in same PG transaction
- [ ] `npm run check && npm run build` pass

**Rollback:**
- Remove outbox → revert to inline TP/SL placement
- Remove DLQ → failed deliveries logged only
- Remove PG buffer → immediate write (fail on PG down)

**Risks:**
- Outbox poison pill (consistently failing entry) → max_attempts + dead-letter prevents queue blocking
- In-memory buffer overflow on extended PG outage → bounded at 100; alert at 50; manual intervention required
- Outbox worker adds latency to TP/SL placement → 1s poll interval acceptable for trading timeframe (5m/15m)

**Owner role:** Backend Dev
**Estimate:** 13 SP / 5–7 days

---

## E7 — Feed Resilience & Degradation

**Goal:** Detect stale price feeds and degrade strategy signals; cache account state with fill-based invalidation.

**Scope:**
- Feed staleness detection: price gap >120s → `strategy_degraded` state (task D2)
- Account state TTL cache with invalidation on fill events (task D3)
- Alert on feed staleness
- Strategy signal suppression in degraded state

**Out-of-scope:**
- Multi-exchange feed failover (Phase E)
- Historical data backfill on recovery
- Alternative data sources

**Definition of Done (DoD):**
- [ ] Price gap >120s triggers `strategy_degraded`; no new signals generated; alert fired
- [ ] Account snapshot cached; invalidated on fill events; cache miss triggers fresh fetch
- [ ] Degraded state visible in `/api/health` and dashboard
- [ ] Recovery: fresh tick → exit `strategy_degraded` → resume signal generation
- [ ] `npm run check && npm run build` pass

**Rollback:**
- Remove staleness check → strategy always active
- Revert account cache → per-request fetch

**Risks:**
- Overly aggressive staleness threshold → 120s is conservative for 5m/15m strategy; tune if needed
- Fill event missed → cache serves stale account state → TTL backup (30s max) prevents extended staleness

**Owner role:** Backend Dev
**Estimate:** 8 SP / 3–4 days

---

## E8 — Multi-Exchange & Horizontal Prep

**Goal:** Normalize PG schema, implement second exchange adapter, prepare for multi-process architecture.

**Scope:**
- Normalize PG schema: dedicated tables for positions, orders, ticks (task E1)
- Implement BybitAdapter (task E2)
- Exchange connection manager / registry (task E3)
- Eliminate in-memory singletons; all state via PG (task E4)
- Document horizontal scaling architecture (task E5)

**Out-of-scope:**
- Actual multi-VPS deployment
- Load balancer configuration
- Multi-operator / SaaS mode

**Definition of Done (DoD):**
- [ ] `001_initial_schema.sql` applied; queries use SQL, not JSONB
- [ ] BybitAdapter passes same integration test suite as HyperliquidAdapter
- [ ] Connection registry manages multiple adapters; health per exchange
- [ ] No in-memory singletons (idempotency, risk cache, caches all in PG)
- [ ] Horizontal scaling architecture documented
- [ ] `npm run check && npm run build` pass

**Rollback:**
- Revert PG schema → JSONB snapshot mode
- Remove BybitAdapter → single-exchange mode
- Inline single adapter → remove connection manager

**Risks:**
- Normalized schema migration is high-risk (data loss) → run in transaction; backup before; rollback SQL provided
- BybitAdapter API differences → abstract behind capability flags
- Removing in-memory singletons may increase PG load → benchmark before/after; add connection pooling

**Owner role:** Backend Dev / Architect
**Estimate:** 21 SP / 8–12 days

---

## Cross-Cutting Concerns (applied across all epics)

| Concern | Approach |
|---------|----------|
| Testing | Each epic adds unit tests for new modules; integration test for order flow |
| CI gate | `npm run check && npm run build` must pass before merge |
| Documentation | Update ARCHITECTURE.md and relevant ADRs on completion of each epic |
| Migration SQL | All schema changes via numbered migration files; rollback SQL included |
| Feature flags | Use env vars for gradual rollout where applicable |
| Monitoring | Each epic must not regress `/api/health/perf` baseline metrics |

---

## Traceability: AUDIT Findings → Epics

| Audit ID | Severity | Epic | Task |
|----------|----------|------|------|
| C1 | CRITICAL | E2 | Graceful shutdown + error handlers |
| C2 | CRITICAL | E2 | Graceful shutdown |
| C3 | CRITICAL | E3 | PG cutover (eliminates lowdb sync writes) |
| H1 | HIGH | E2 | Idempotency cache cap |
| H2 | HIGH | E2 | `.unref()` risk audit interval |
| H3 | HIGH | E2 | WS exponential backoff |
| H4 | HIGH | E3 | PG normalized writes (eventual) / E8 |
| H5 | HIGH | E2 | Adapter init retry |
| M1 | MEDIUM | E1 | Replace silent catches |
| M2 | MEDIUM | E5 | Cached risk evaluation |
| M3 | MEDIUM | E2 | Rate-limit middleware |
| M4 | MEDIUM | — | Acceptable for single-operator |
| M5 | MEDIUM | E8 | Clustering prep |
| M6 | MEDIUM | E8 | Clustering prep |
| M7 | MEDIUM | E3 | Bounded arrays + archival |
