# ADR-002: Persistence and Eventing Strategy

| Field | Value |
|-------|-------|
| **Status** | Proposed |
| **Date** | 2026-02-25 |
| **Driver** | Issue #21 — Target architecture for 24/7 realtime trading engine |
| **Deciders** | Core team |

## Context

Coinmaster currently has a three-layer persistence stack:

1. **lowdb (default)** — Synchronous JSON file writes. Blocks event loop on every `db.write()` (13 call sites). O(n) cost grows with data.
2. **PostgreSQL snapshot bridge (Phase 1)** — Full `DBShape` serialized as single JSONB row via UPSERT. Same O(n) cost, but non-blocking I/O.
3. **Dual-write shadow mode** — lowdb primary + PG shadow. Best-effort; PG failure never blocks primary path.

The persistence roadmap in `POSTGRES_MIGRATION_PLAN.md` defines 5 phases:
- Phase 1: Snapshot bridge (done)
- Phase 2: Dual-write validation (in progress)
- Phase 3: PG primary cutover
- Phase 4: Normalized schema
- Phase 5: lowdb removal

Additionally, the trade event journal (`tradeEvents.ts`) is an append-only hash-chain log, but it is stored inside the same `DBShape` blob — meaning every event append triggers a full state flush.

### Problems

1. **Event loop blocking** — lowdb `db.write()` is synchronous; 13 call sites cause latency spikes.
2. **O(n) writes** — Both lowdb and PG snapshot mode serialize the entire state on every write.
3. **No atomicity between events and side-effects** — TP/SL orders are placed after the parent order ack, outside any transaction. Process crash between ack and TP/SL = lost TP/SL.
4. **Unbounded arrays** — `tradeEvents[]` and `marketTicks[]` grow without limit; no archival.
5. **No event-driven side-effects** — Side-effects (TP/SL, notifications) are inline in the order handler, not triggered by events.

## Decision

### 2.1 PostgreSQL as Single Source of Truth

After dual-write validation (Phase B), PostgreSQL becomes the **sole persistence backend**:

- `PERSISTENCE_BACKEND=postgres` is the default
- lowdb is deprecated and removed
- All writes go through the `PersistenceStore` interface

### 2.2 Incremental Migration to Normalized Schema

Instead of a single big-bang migration from JSONB to normalized tables, adopt an incremental approach:

```
Phase B:  PG primary (JSONB snapshot — current postgresStore.ts)
Phase C:  Extract high-write tables (trade_events, risk_audit)
Phase D:  Extract outbox table
Phase E:  Full normalization (positions, orders, market_ticks, etc.)
```

At each phase, the `PersistenceStore` interface remains stable. Only the implementation changes.

### 2.3 Trade Events as First-Class Table

Extract `tradeEvents` from the JSONB blob into a dedicated `trade_events` table:

```sql
CREATE TABLE trade_events (
    id          BIGSERIAL PRIMARY KEY,
    seq         INTEGER NOT NULL,
    type        TEXT NOT NULL,           -- 'order_submitted', 'order_filled', etc.
    source      TEXT NOT NULL,           -- 'live', 'paper', 'replay'
    symbol      TEXT,
    side        TEXT,
    payload     JSONB NOT NULL,          -- Event-specific data
    correlation_id TEXT,
    prev_hash   TEXT,
    hash        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_trade_events_type ON trade_events(type);
CREATE INDEX idx_trade_events_symbol ON trade_events(symbol);
CREATE INDEX idx_trade_events_correlation ON trade_events(correlation_id);
CREATE INDEX idx_trade_events_created ON trade_events(created_at);
```

Benefits:
- Append is O(1), not O(n)
- SQL queries for audit, P&L reconciliation, debugging
- Index-based filtering by type, symbol, time range
- Natural partition point for archival (by `created_at`)

### 2.4 Outbox Pattern for Reliable Side-Effects

Introduce an outbox table for side-effects that must survive process crash:

```sql
CREATE TABLE outbox (
    id          BIGSERIAL PRIMARY KEY,
    event_id    BIGINT REFERENCES trade_events(id),
    action      TEXT NOT NULL,           -- 'place_tp_sl', 'send_alert', etc.
    payload     JSONB NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending, processing, done, failed, dead
    attempts    INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    next_retry_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX idx_outbox_pending ON outbox(status, next_retry_at)
    WHERE status IN ('pending', 'failed');
```

**Outbox worker** (in-process, same Node.js):
1. Poll `pending` or `failed` entries every 1s
2. Execute action (e.g., place TP/SL orders)
3. On success: mark `done`
4. On failure: increment `attempts`; if < `max_attempts`, set `next_retry_at`; else mark `dead`
5. Dead entries visible via admin API for manual intervention

**Transaction boundary:**
```typescript
await db.transaction(async (tx) => {
    // 1. Write trade event
    const event = await tx.insertTradeEvent(orderAckEvent);
    // 2. Write outbox entry (same transaction)
    await tx.insertOutbox({
        eventId: event.id,
        action: 'place_tp_sl',
        payload: { symbol, side, tpPrice, slPrice }
    });
});
// Outbox worker picks up the entry asynchronously
```

This guarantees: if the trade event is recorded, the TP/SL intent is also recorded. Process crash after commit → outbox worker retries on restart.

### 2.5 Event Archival

| Table | Hot retention | Archive strategy |
|-------|--------------|-----------------|
| `trade_events` | 90 days | Move to `trade_events_archive` partitioned by month |
| `risk_audit` | 30 days | Move to `risk_audit_archive` |
| `market_ticks` | 7 days | Move to `market_ticks_archive` or drop |
| `outbox` | Until processed + 7 days | Delete `done` entries older than 7 days |

Archival runs as a nightly cron job (03:30 UTC, after backup).

## Consequences

### Positive

- **No more event loop blocking** — All PG writes are async
- **O(1) event appends** — Dedicated table, not full state re-serialization
- **Reliable TP/SL delivery** — Outbox pattern guarantees delivery through process crashes
- **Queryable audit trail** — SQL queries on trade events for P&L, debugging, compliance
- **Bounded data growth** — Archival strategy prevents unbounded array growth
- **Incremental migration** — Each phase is independently deployable and reversible

### Negative

- **PostgreSQL dependency** — PG becomes a hard dependency (vs. optional in current state)
- **Outbox worker complexity** — New component to monitor and debug
- **Migration effort** — Each table extraction requires code changes + migration SQL
- **Backup importance increases** — PG is now the only data store; backup failure = data loss risk

### Risks

- **Dual-write inconsistency** — During transition, lowdb and PG may diverge. Mitigation: reconciliation script runs continuously; 48h validation window before cutover.
- **Outbox poison pill** — A consistently failing outbox entry blocks the queue. Mitigation: max_attempts + dead-letter status; admin API for manual retry/discard.
- **Migration data loss** — Incorrect migration SQL could drop data. Mitigation: all migrations run in transactions; backup taken before each migration; rollback SQL provided.

## Alternatives Considered

### 1. Keep lowdb, add async writes

Rejected because:
- lowdb's synchronous API is fundamental to its design
- Wrapping in `setTimeout` introduces write ordering issues
- Doesn't solve O(n) growth or queryability

### 2. Redis for caching + PostgreSQL for persistence

Deferred — adds operational complexity (another service to manage). For single-VPS deployment, in-process caching with PG persistence is simpler. Redis may be introduced in Phase E for pub/sub between clustered processes.

### 3. Event sourcing (full CQRS)

Rejected for current scale because:
- trade_events journal already provides event-level audit
- Full CQRS adds projection/snapshot complexity not warranted for single-operator
- Can be evolved toward if multi-operator/SaaS requires it

### 4. SQLite instead of PostgreSQL

Rejected because:
- PostgreSQL is already deployed and working (Phase 1)
- PG offers WAL, replication, NOTIFY, advisory locks — needed for Phase E scaling
- SQLite has write contention issues under concurrent access

## Implementation Plan

See [TARGET_ARCHITECTURE_2026.md](../TARGET_ARCHITECTURE_2026.md):
- Phase B: PG primary cutover (tasks B1–B5)
- Phase C: Idempotency cache in PG (task C5)
- Phase D: Outbox pattern (tasks D1, D4, D5)
- Phase E: Full normalization (task E1)

## References

- [TARGET_ARCHITECTURE_2026.md](../TARGET_ARCHITECTURE_2026.md) — Target architecture document
- [POSTGRES_MIGRATION_PLAN.md](../POSTGRES_MIGRATION_PLAN.md) — Current 5-phase migration plan
- [ADR-001: Runtime Separation](ADR-001-runtime-separation.md) — Companion ADR
