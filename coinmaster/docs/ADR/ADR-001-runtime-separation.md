# ADR-001: Runtime Separation into Logical Planes

| Field | Value |
|-------|-------|
| **Status** | Proposed |
| **Date** | 2026-02-25 |
| **Driver** | Issue #21 — Target architecture for 24/7 realtime trading engine |
| **Deciders** | Core team |

## Context

The current Coinmaster codebase is a monolith centered on `src/server/index.ts` (1175 LOC). This single file contains:

- Express API routes and middleware
- Drawdown watchdog (5s timer loop)
- Risk gate evaluation (2 exchange API calls per order)
- Order execution pipeline (validation → gating → submission → TP/SL)
- WebSocket lifecycle management
- Paper engine orchestration
- Persistence flush triggers (13 `db.write()` call sites)
- Idempotency cache management
- Risk audit buffer and flush timer

This coupling creates several problems:

1. **Testability** — Risk gates, execution pipeline, and watchdog cannot be unit-tested in isolation without starting the full Express server.
2. **Cognitive load** — A 1175-line file with interleaved concerns is hard to navigate and modify safely.
3. **Reliability** — A bug in the dashboard aggregation code can block the risk watchdog because they share the same event loop priority.
4. **Evolution** — Adding circuit breakers, caching, or outbox patterns requires touching the monolith, increasing merge conflict risk.

## Decision

Split the monolith into **five logical planes** implemented as separate TypeScript modules within the same Node.js process:

```
src/
├── control/          # Control Plane — API routes, middleware, config
│   ├── routes/       # Express route handlers
│   ├── middleware/    # Auth, rate-limit, error handling
│   └── index.ts      # Express app setup
│
├── execution/        # Execution Plane — order pipeline
│   ├── pipeline.ts   # validate → risk → alloc → submit → post-trade
│   ├── idempotency.ts
│   └── tpsl.ts       # TP/SL resolution and placement
│
├── risk/             # Risk Plane — watchdog, gates, circuit breakers
│   ├── watchdog.ts   # Drawdown watchdog loop
│   ├── gates.ts      # Risk gate + symbol allocation evaluation
│   ├── cache.ts      # Cached account state (TTL)
│   └── circuit.ts    # Circuit breaker state machine
│
├── data/             # Data Plane — persistence, exchange, events
│   ├── exchange/     # (existing src/exchange/)
│   ├── persistence/  # (existing src/core/persistence/)
│   └── events/       # Trade event journal
│
├── observability/    # Observability Plane — logging, metrics, health
│   ├── logger.ts     # pino structured logger
│   ├── metrics.ts    # Latency histograms, counters
│   └── health.ts     # Health probe endpoints
│
├── core/             # (existing) Domain types, strategy, simulation
└── server/
    └── index.ts      # Slim bootstrap: wire planes together, start server
```

### Key Constraints

1. **Same process** — All planes run in one Node.js process (Phase A–D). Separation is at the module level, not the process level.
2. **Dependency direction** — Control → Execution → Risk → Data → Core. No circular dependencies. Observability is cross-cutting (imported by all).
3. **Interface-first** — Planes communicate via typed interfaces, not direct function calls to internal state. This makes future process separation possible.
4. **Incremental** — Migration is file-by-file. Each extraction is a standalone PR that can be reverted.

## Consequences

### Positive

- `index.ts` shrinks from 1175 LOC to ~200 LOC (bootstrap + wiring)
- Risk watchdog is testable without Express; execution pipeline is testable without watchdog
- Circuit breakers and caching can be added to the risk plane without touching execution code
- Clear ownership boundaries make code review faster
- Prepares for future process-level separation (Phase E) without rewriting

### Negative

- More files and directories to navigate
- Import paths become deeper (`src/execution/pipeline` vs `src/server/index`)
- Internal interfaces add a small amount of boilerplate
- Migration period has partial extraction (some logic in index.ts, some in new modules)

### Risks

- **Partial extraction stalls** — If extraction is not completed within Phase C, the codebase is split between old and new patterns. Mitigation: each extraction is a standalone PR with tests; roadmap has explicit done criteria.
- **Over-abstraction** — Risk of creating unnecessary interfaces for single-implementation cases. Mitigation: use concrete classes initially; extract interfaces only when needed for testing or multi-implementation.

## Alternatives Considered

### 1. Microservices (separate processes per plane)

Rejected for Phase A–D because:
- Adds operational complexity (IPC, service discovery, deployment orchestration)
- Single VPS doesn't benefit from process isolation
- Not warranted for single-operator, single-exchange use case

### 2. Keep monolith, add tests with dependency injection

Rejected because:
- DI in a 1175-line file still requires understanding the full file
- Doesn't address cognitive load or merge conflict risk
- Doesn't prepare for future scaling

### 3. Event bus between components (in-process pub/sub)

Deferred — adds indirection that isn't needed for same-process communication. May be introduced in Phase E for cross-process communication.

## Implementation Plan

See [TARGET_ARCHITECTURE_2026.md](../TARGET_ARCHITECTURE_2026.md), Phase C (tasks C1, C2).

## References

- [TARGET_ARCHITECTURE_2026.md](../TARGET_ARCHITECTURE_2026.md) — Target architecture document
- [ARCHITECTURE.md](../ARCHITECTURE.md) — Current MVP architecture
