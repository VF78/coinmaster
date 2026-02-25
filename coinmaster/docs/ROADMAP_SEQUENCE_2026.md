# Roadmap Sequence 2026

> **Parent issue:** #21 P1 — Target architecture for 24/7 realtime trading engine
> **Backlog:** [IMPLEMENTATION_BACKLOG_2026.md](IMPLEMENTATION_BACKLOG_2026.md)
> **Created:** 2026-02-25
> **Status:** Active

---

## Phase Sequence & Dependencies

```
Phase A (Weeks 1–2)          Phase B (Weeks 3–4)
┌─────────┐ ┌─────────┐     ┌─────────┐
│   E1    │ │   E2    │────►│   E3    │
│Observ.  │ │Process  │     │PG Cutov.│
│3–4 days │ │3–4 days │     │5–7 days │
└─────────┘ └────┬────┘     └────┬────┘
  (parallel)     │               │
                 │               ▼
            Phase C (Weeks 5–8)
            ┌─────────┐     ┌─────────┐
            │   E4    │────►│   E5    │
            │Runtime  │     │Reliab.  │
            │Separatn.│     │Patterns │
            │8–10 days│     │5–7 days │
            └─────────┘     └────┬────┘
                                 │
                                 ▼
            Phase D (Weeks 9–11)
            ┌─────────┐     ┌─────────┐
            │   E6    │     │   E7    │
            │Outbox/  │     │Feed     │
            │Risk     │     │Resil.   │
            │5–7 days │     │3–4 days │
            └─────────┘     └─────────┘
              (parallel)
                 │               │
                 ▼               ▼
            Phase E (Weeks 12–15)
            ┌──────────────────────┐
            │        E8           │
            │Multi-Exchange & Horiz│
            │8–12 days            │
            └──────────────────────┘
```

---

## Dependency Matrix

| Epic | Hard Dependencies | Soft Dependencies | Can Parallel With |
|------|-------------------|-------------------|-------------------|
| E1 (Observability) | None | — | E2 |
| E2 (Process Hardening) | None | E1 (logging helps debugging) | E1 |
| E3 (PG Cutover) | E2 (graceful shutdown needed for safe cutover) | E1 (structured logs help validation) | — |
| E4 (Runtime Separation) | E3 (PG primary simplifies persistence in modules) | E1 (structured logs in new modules) | — |
| E5 (Reliability Patterns) | E4 (circuit breakers wrap extracted modules) | E3 (PG for idempotency persistence) | — |
| E6 (Outbox/Risk) | E5 (circuit breakers), E3 (PG for outbox table) | E4 (clean module boundaries) | E7 |
| E7 (Feed Resilience) | E5 (circuit breakers for WS/REST) | E1 (alerting for staleness) | E6 |
| E8 (Multi-Exchange) | E3 (PG primary), E4 (plane separation), E5 (reliability) | E6, E7 | — |

---

## Critical Path

```
E2 → E3 → E4 → E5 → E6/E7 → E8
```

**Critical path duration:** ~35–47 days (assuming sequential execution on critical items)

**Slack (non-critical):**
- E1 has ~1 week slack (can start any time during Phase A, not on critical path)
- E7 has ~1 week slack (can run in parallel with E6)

---

## Phase Details

### Phase A — Observability & Process Hardening (Weeks 1–2)

**Objective:** Make the system observable and crash-resilient before any architectural changes.

**Epics:** E1 + E2 (run in parallel)

**Go criteria (to start):**
- Current `main` branch is green (`npm run check && npm run build`)
- VPS access confirmed for systemd deployment

**Go/No-Go gate (to exit Phase A):**
- [ ] All console.log replaced with pino
- [ ] systemd unit deployed and tested (kill -9 → restart <5s)
- [ ] Graceful shutdown verified
- [ ] WS backoff verified
- [ ] `/api/health/perf` baseline captured and documented
- [ ] No trading logic regressions

**Stop conditions:**
- Performance baseline shows regression >20% in any SLO metric → investigate before proceeding
- Graceful shutdown fails to drain connections → fix before PG cutover

---

### Phase B — PostgreSQL Primary Cutover (Weeks 3–4)

**Objective:** PostgreSQL becomes the single source of truth; lowdb deprecated.

**Epics:** E3

**Go criteria (to start):**
- Phase A complete (graceful shutdown is critical for safe cutover)
- Dual-write has been running in production/staging

**Go/No-Go gate (to exit Phase B):**
- [ ] `npm run persistence:cutover-check` exits 0
- [ ] `npm run persistence:rollback-check` exits 0
- [ ] 48h zero-diff reconciliation verified
- [ ] Daily backup cron operational and restore tested
- [ ] 1-week PG-primary stability confirmed (no flush errors, latency within SLO)

**Stop conditions:**
- Reconciliation shows persistent diffs → do NOT cutover; debug divergence
- PG flush latency >50ms p95 → investigate before proceeding
- Any data loss during testing → halt and restore from backup

---

### Phase C — Runtime Separation & Reliability (Weeks 5–8)

**Objective:** Decompose monolith into testable planes; add reliability patterns.

**Epics:** E4 → E5 (sequential — E5 wraps E4 modules)

**Go criteria (to start):**
- Phase B complete (PG primary stable; no dual-write complications)
- index.ts baseline LOC measured

**Go/No-Go gate (to exit Phase C):**
- [ ] `src/execution/` and `src/risk/` exist with unit tests
- [ ] `index.ts` < 400 LOC
- [ ] Circuit breakers operational on all 4 circuits
- [ ] Risk gate exchange calls reduced ≥80% (verified by logs)
- [ ] Idempotency dedup survives restart
- [ ] Full order flow integration test passes

**Stop conditions:**
- Partial extraction breaks trading flow → revert problematic PR; stabilize before continuing
- Circuit breaker false-positives in production → tune thresholds; extend Phase C if needed
- index.ts LOC doesn't decrease meaningfully → reassess extraction approach

---

### Phase D — Advanced Risk & Feed Resilience (Weeks 9–11)

**Objective:** Guarantee side-effect delivery; handle exchange and DB failures gracefully.

**Epics:** E6 + E7 (run in parallel)

**Go criteria (to start):**
- Phase C complete (reliable modules to wrap with outbox/degradation)

**Go/No-Go gate (to exit Phase D):**
- [ ] TP/SL delivery survives fault injection (process kill between ack and TP/SL)
- [ ] DLQ admin endpoint functional
- [ ] Price staleness detection working (120s threshold)
- [ ] PG unavailability → graceful buffer → recovery flush verified
- [ ] Strategy degradation mode verified (no signals in degraded state)

**Stop conditions:**
- Outbox introduces >2s latency to TP/SL placement → optimize poll interval
- In-memory buffer fills up in <10 min of PG outage → increase buffer or add alerts
- Feed staleness false-positives during normal market hours → raise threshold

---

### Phase E — Multi-Exchange & Horizontal Prep (Weeks 12–15)

**Objective:** Prepare for multi-exchange trading and future multi-process deployment.

**Epics:** E8

**Go criteria (to start):**
- Phases A–D complete and stable for ≥2 weeks in production
- BybitAdapter API research complete; capability mapping documented

**Go/No-Go gate (to exit Phase E):**
- [ ] Normalized PG schema operational; no JSONB blob queries
- [ ] BybitAdapter passes integration tests
- [ ] Connection manager handles multi-adapter lifecycle
- [ ] No in-memory singletons remain
- [ ] Horizontal scaling architecture documented

**Stop conditions:**
- Normalized schema migration causes data loss → rollback; investigate
- BybitAdapter API breaks assumptions → reassess adapter interface
- Single-VPS performance degrades with normalized schema → optimize queries before scaling

---

## What Can Run in Parallel

| Parallelism | Epics | Condition |
|-------------|-------|-----------|
| Phase A | E1 + E2 | Independent; different code areas |
| Phase D | E6 + E7 | Independent; different subsystems |
| Within E4 | Execution extraction + Risk extraction | Can be 2 PRs by different devs if both understand index.ts |
| Within E8 | Schema normalization + BybitAdapter | Different code areas; different skills |

---

## Sprint Candidates (Next Sprint)

Based on dependency order and immediate value, **Sprint 1 candidates** are:

### Must-have (Phase A):
1. **E1: Structured logging** — foundational for all debugging going forward
2. **E2: Graceful shutdown + error handlers** — CRITICAL audit findings C1, C2
3. **E2: systemd unit file** — eliminates manual restart risk
4. **E2: WS exponential backoff** — prevents reconnect storms

### Nice-to-have (Phase A stretch):
5. **E2: Rate-limit middleware** — low effort, addresses AUDIT M3
6. **E1: Heartbeat SLA alerting** — builds on existing heartbeat logic

---

## Risk Summary

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Partial extraction stalls (E4) | Medium | High | One module per PR; block merging until self-contained |
| PG cutover data inconsistency (E3) | Low | Critical | 48h reconciliation; automated cutover/rollback checks |
| Circuit breaker false-positives (E5) | Medium | Medium | Conservative thresholds; half-open probes; tune in production |
| Outbox poison pill (E6) | Low | Medium | max_attempts + dead-letter + admin API |
| Normalized schema data loss (E8) | Low | Critical | Transaction-wrapped migrations; backup before each run |
| Scope creep across epics | Medium | Medium | Strict out-of-scope definitions; time-box each epic |
| Single developer bottleneck | High | High | Phases A & D have parallel epics; document well for onboarding |

---

## Timeline Summary

| Week | Phase | Epics | Milestone |
|------|-------|-------|-----------|
| 1–2 | A | E1 + E2 | Observable, crash-resilient process |
| 3–4 | B | E3 | PostgreSQL primary; lowdb deprecated |
| 5–7 | C (part 1) | E4 | Modular codebase; index.ts <400 LOC |
| 7–8 | C (part 2) | E5 | Circuit breakers; cached risk; persistent idempotency |
| 9–10 | D | E6 + E7 | Outbox TP/SL; feed resilience |
| 11 | D | — | Stabilization & production soak |
| 12–15 | E | E8 | Multi-exchange ready; normalized schema |

**Total estimated duration:** 12–15 weeks (single developer, sequential phases)
**With 2 developers and parallelism:** 9–11 weeks
