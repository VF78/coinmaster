# P1-10 Codebase Audit Baseline

**Date**: 2026-02-24
**Commit**: c783d03
**Scope**: Full architecture + performance audit for production-readiness and VPS migration

---

## 1. Current Architecture Summary

```
                    ┌──────────┐
     Browser ──────►│  Vite    │ (dev) / static dist (prod)
                    │  React   │
                    └────┬─────┘
                         │ REST
                    ┌────▼─────────────────────────────┐
                    │  Express server  (index.ts 1175L) │
                    │  ├─ ownerAuth middleware           │
                    │  ├─ riskGateMiddleware             │
                    │  ├─ 19 API endpoints               │
                    │  ├─ ingestPrice loop (WS+REST)     │
                    │  └─ paper engine (opt-in)          │
                    └────┬─────────────┬───────────────┘
                         │             │
               ┌─────────▼──┐   ┌─────▼──────────┐
               │ Persistence │   │ HyperliquidAdpt│
               │ lowdb / PG  │   │  REST + WS     │
               └─────────────┘   └────────────────┘
```

**Key properties**:
- Single Node.js process, single-operator, single exchange
- Express + React SPA served from same process
- Persistence: lowdb (default) or PostgreSQL snapshot bridge (Phase 1)
- Exchange: Hyperliquid only via REST + WebSocket
- Strategy: 5m/15m engulfing + sweep detection, paper/live capable
- Risk: daily drawdown stop (20%), leverage cap (10x), kill-switch

---

## 2. Risk Registry

### CRITICAL

| ID | Finding | File:Line | Impact |
|----|---------|-----------|--------|
| C1 | **No global error handler** — no `process.on('uncaughtException'/'unhandledRejection')`. Unhandled promise rejection crashes server silently. | server/index.ts (global) | Production outage without diagnostics |
| C2 | **No graceful shutdown** — no SIGTERM/SIGINT handler. Timers, DB pool, WS connections not drained. | server/index.ts (global) | Data loss on deploy, orphaned connections |
| C3 | **lowdb blocks event loop** — `db.write()` serializes entire DBShape synchronously to disk. 13 call sites in index.ts. | server/index.ts:108,129,313,478,… | API latency spikes proportional to data size |

### HIGH

| ID | Finding | File:Line | Impact |
|----|---------|-----------|--------|
| H1 | **Idempotency cache unbounded** — `Map<string,…>` pruned only on requests, no max-size cap. | server/index.ts:892 | Memory leak on long-running server |
| H2 | **Risk audit flush interval never cleared** — `setInterval(30s)` without `.unref()` or `clearInterval`. | server/index.ts:112 | Prevents clean shutdown, keeps process alive |
| H3 | **WS reconnect no max backoff** — 3s/5s fixed delay, no exponential cap. Exchange outage → reconnect storm. | server/index.ts:345-349 | Rate-limit bans, amplified outage |
| H4 | **PostgreSQL snapshot = full JSONB upsert** — entire DBShape serialized per flush. No incremental writes. | persistence/postgresStore.ts:117-121 | O(n) write cost grows with data |
| H5 | **Exchange adapter lazy-init failure sticky** — if first `getTradingClient()` fails, cached `null` blocks all future calls. | hyperliquidAdapter.ts:556-583 | Permanent exchange disconnection until restart |

### MEDIUM

| ID | Finding | File:Line | Impact |
|----|---------|-----------|--------|
| M1 | **Silent error swallowing** — `.catch(() => undefined)` on timer callbacks hides real failures. | server/index.ts:112,338,369,1172 | Invisible degradation |
| M2 | **Risk gate calls exchange on every order** — `evaluateRiskGates()` makes 2 API calls (account state + positions). | server/index.ts:143-190 | Added latency per trading request |
| M3 | **No rate-limit middleware** — public endpoints (/api/dashboard, /api/health) have no throttling. | server/index.ts:388-391 | DoS vector |
| M4 | **CORS wide open** — `cors()` with default config allows any origin. | server/index.ts:388 | Acceptable for single-operator, risk for SaaS |
| M5 | **No process manager** — no PM2/systemd unit. Crash = manual restart. | deployment | Downtime until manual intervention |
| M6 | **Single CPU core** — no clustering, single event loop. | architecture | CPU-bound tasks block everything |
| M7 | **tradeEvents / marketTicks unbounded** — no archival or rotation strategy. | core/types.ts, simulation.ts | DB growth, query degradation |

---

## 3. Performance Baseline — What to Measure

These metrics should be collected before and after each refactor phase.

| Metric | How to collect | Target |
|--------|---------------|--------|
| **API latency p50/p95** (ms) | `GET /api/health/perf` → `uptimeSeconds`, external: `time curl /api/dashboard` | p95 < 200ms |
| **Event loop lag** (ms) | `GET /api/health/perf` → `eventLoopLagMs` | < 50ms sustained |
| **Memory RSS** (MB) | `GET /api/health/perf` → `memory.rss` | < 300MB |
| **Heap used / total** (MB) | `GET /api/health/perf` → `memory.heapUsed/heapTotal` | heapUsed < 80% of heapTotal |
| **DB write latency** (ms) | Instrument `flush()` — Phase 2 | lowdb < 50ms, PG < 20ms |
| **WS reconnect count** (per hour) | Log grep: `scheduleWsReconnect` | < 3/hour |
| **Order round-trip** (ms) | Timestamp diff: submit → ACK event | < 500ms |
| **Risk gate eval time** (ms) | Instrument `evaluateRiskGates()` — Phase 2 | < 100ms |

### Baseline collection command

```bash
# Snapshot after 1h uptime
curl -sS http://HOST:PORT/api/health/perf | jq .
```

---

## 4. Refactor Roadmap

### Phase 0 — Observability & Safety (this PR)

**Scope**: Non-invasive, no trading logic changes.

- [x] Add `GET /api/health/perf` endpoint (RSS, heap, uptime, event loop lag)
- [x] Create this audit document
- [x] Create RUNBOOK_COMMANDS.md with audit check commands

**Done-criteria**: `npm run check && npm run build && npm run ops:smoke` pass. `/api/health/perf` returns valid JSON.

### Phase 1 — Graceful Shutdown + Error Boundaries

**Scope**: Process lifecycle hardening.

- [ ] Add `process.on('SIGTERM'/'SIGINT')` handler: clear timers, close WS, drain DB pool
- [ ] Add `process.on('uncaughtException'/'unhandledRejection')` with structured logging
- [ ] Add Express error middleware (4-arg handler)
- [ ] Cap idempotency cache size (e.g., LRU 1000 entries)
- [ ] Add `.unref()` to risk audit flush interval

**Done-criteria**: `kill -TERM <pid>` exits cleanly within 5s. Uncaught errors logged, not silent.

### Phase 2 — Structured Logging + DB Write Instrumentation

**Scope**: Replace console.log with JSON logger, instrument hot paths.

- [ ] Add lightweight JSON logger (pino or custom)
- [ ] Instrument `flush()` with timing
- [ ] Instrument `evaluateRiskGates()` with timing
- [ ] Add correlation IDs to order lifecycle logs
- [ ] Replace `.catch(() => undefined)` with `.catch(log.warn)`

**Done-criteria**: All logs are JSON. Flush and risk-gate latency visible in `/api/health/perf`.

### Phase 3 — PostgreSQL Migration (Phase 2-4 of POSTGRES_MIGRATION_PLAN.md)

**Scope**: Complete migration from lowdb to normalized PG schema.

- [ ] Dual-write mode (lowdb primary + PG shadow)
- [ ] Reconciliation script
- [ ] Read migration to PG
- [ ] Cutover to `PERSISTENCE_BACKEND=postgres`

**Done-criteria**: 72h dual-write with zero reconciliation diffs. PG as sole backend.

### Phase 4 — Process Hardening for VPS

**Scope**: Production deployment infrastructure.

- [ ] systemd unit file with `Restart=always`
- [ ] Rate-limit middleware on public endpoints
- [ ] WS reconnect exponential backoff with max 60s cap
- [ ] Exchange adapter retry/reset on init failure
- [ ] Resource limits (memory, file descriptors)

**Done-criteria**: Server survives `kill -9`, restarts within 5s. Rate-limited endpoints return 429.

---

## 5. VPS Migration Plan — 46.225.133.161

### Pre-migration checklist

```
[ ] Node.js 20+ installed on target VPS
[ ] PostgreSQL 15+ installed (if using PG backend)
[ ] .env file prepared with production secrets (600 perms)
[ ] data/db.json backed up from current host
[ ] DNS / firewall rules configured (port 8787 or reverse proxy)
[ ] systemd unit file deployed
[ ] TLS termination configured (nginx/caddy reverse proxy)
```

### Cutover sequence

```
1. FREEZE  — Set bias=off, cancel open orders on current host
2. BACKUP  — Copy data/db.json + .env from current host
3. DEPLOY  — Clone repo, npm install, npm run build on 46.225.133.161
4. CONFIG  — Place .env (chmod 600), place db.json in data/
5. SMOKE   — PORT=8787 npm run start → npm run ops:smoke
6. VERIFY  — curl /api/health/perf → check metrics baseline
7. SWITCH  — Update DNS/proxy to point to new VPS
8. MONITOR — Watch logs for 30 min, verify WS connection stable
9. CONFIRM — Place test order (paper mode), verify round-trip
```

### Rollback procedure

```
1. Revert DNS/proxy to old host
2. Restart old host process (data/db.json was preserved)
3. Verify /api/health on old host
4. Investigate failure on new VPS
```

**RTO target**: < 5 min (DNS TTL permitting)
**RPO target**: Zero — append-only trade log preserved on both hosts

### Post-migration validation

```bash
# On new VPS
curl -sS http://127.0.0.1:8787/api/health/perf | jq .
curl -sS http://127.0.0.1:8787/api/dashboard | jq '.symbol, .liveMode'
curl -sS http://127.0.0.1:8787/api/live/status | jq .
# Compare with old host outputs
```

---

## 6. Dependency Summary

| Package | Version | Role | Risk |
|---------|---------|------|------|
| express | ^4.19.2 | HTTP server | Stable, no CVEs |
| hyperliquid | ^1.7.7 | Exchange SDK | Vendor lock-in, sole data source |
| lowdb | ^7.0.1 | File persistence | Sync I/O bottleneck (C3) |
| pg | ^8.13.1 | PostgreSQL driver | Phase 1 only, optional |
| nanoid | ^5.0.7 | ID generation | Minimal risk |
| cors | ^2.8.5 | CORS middleware | Wide-open config (M4) |

---

## Appendix: File Criticality Map

| File | LOC | Criticality | Key Risks |
|------|-----|-------------|-----------|
| src/server/index.ts | 1175 | **CRITICAL** | Global state, timers, error handling |
| src/exchange/hyperliquidAdapter.ts | 598 | **CRITICAL** | Singleton, lazy init, WS lifecycle |
| src/core/simulation.ts | 353 | HIGH | Strategy engine, position lifecycle |
| src/core/persistence/postgresStore.ts | 157 | HIGH | JSONB serialization bottleneck |
| src/server/liveSnapshot.ts | 240 | MEDIUM | State aggregation |
| src/core/replay.ts | 135 | MEDIUM | Backtest engine |
| src/core/services.ts | 75 | MEDIUM | Bias + stats |
| src/core/persistence/lowdbStore.ts | 62 | MEDIUM | File I/O default backend |
| src/core/tradeEvents.ts | 63 | LOW | Append-only, hash chain |
| src/core/strategyAdapter.ts | 124 | LOW | Signal evaluation |
