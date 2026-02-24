# PostgreSQL Migration Plan

Migrate persistence from lowdb (JSON file) to PostgreSQL without production downtime.

## Current State

- Single `data/db.json` file via lowdb `JSONFilePreset`
- All reads/writes go through `getDb()` → `db.data.*` mutation → `db.write()`
- Core logic (`simulation.ts`, `services.ts`, `replay.ts`) operates on `DBShape` in-memory object
- Server (`index.ts`) is the sole consumer of `getDb()`

## Architecture

```
PERSISTENCE_BACKEND env var
        │
        ▼
┌─────────────────┐
│ PersistenceStore │  ← interface (src/core/persistence/types.ts)
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
LowdbStore  PostgresStore
(default)   (opt-in)
```

## Phases

### Phase 0 — Baseline (this PR)
- [x] SQL schema file `migrations/001_initial_schema.sql`
- [x] `PersistenceStore` interface with operations used by the server
- [x] `LowdbStore` adapter wrapping existing lowdb through the interface
- [x] `PostgresStore` skeleton with `init()` and `healthCheck()`
- [x] `PERSISTENCE_BACKEND=lowdb|postgres` env switch (default: `lowdb`)
- [x] Zero changes to trading logic, risk gates, or API contracts

### Phase 1 — Snapshot Bridge (this PR)
- [x] `migrations/002_state_snapshot.sql` — `state_snapshot` table (`key TEXT PK`, `data JSONB`, `updated_at`)
- [x] `PostgresStore.init()` — creates snapshot table (idempotent), loads existing snapshot into `this.data`
- [x] `PostgresStore.flush()` — upserts full `DBShape` as a single JSONB row in a transaction
- [x] `pg` added as runtime dependency
- [x] Zero changes to trading logic, risk gates, or API contracts
- Strategy: snapshot-table acts as a safe bridge — the entire `DBShape` is stored as one JSONB document, so all existing in-memory mutation patterns work unchanged. Phase 2 will migrate reads/writes to the normalised tables from `001_initial_schema.sql`.

### Phase 2 — Dual-Write
- Enable dual-write mode: lowdb primary + postgres shadow writes
- Add reconciliation script comparing JSON ↔ PG row counts
- Begin writing to normalised tables (001 schema) alongside snapshot
- Validate in staging for 48–72h

### Phase 3 — Read Migration
- Switch reads to PostgreSQL (normalised tables) while keeping lowdb writes as backup
- Compare response payloads (lowdb vs PG) in shadow mode
- Monitor latency / error rates

### Phase 4 — Cutover
- Set `PERSISTENCE_BACKEND=postgres` as default
- Keep lowdb adapter available but unused
- Run for 1 week with rollback ready

### Phase 5 — Cleanup
- Remove lowdb dependency and `data/db.json` path
- Archive migration code
- Drop `PERSISTENCE_BACKEND` env switch

## Rollback Procedure

At any phase, rollback is:

1. Set `PERSISTENCE_BACKEND=lowdb` (or remove the env var)
2. Restart the process
3. The system immediately reverts to JSON file persistence

No data loss risk: lowdb remains the source of truth until Phase 3 cutover.

## Environment Variables

| Variable | Values | Default | Description |
|---|---|---|---|
| `PERSISTENCE_BACKEND` | `lowdb`, `postgres` | `lowdb` | Active persistence backend |
| `DATABASE_URL` | PostgreSQL connection string | — | Required when backend=postgres |
| `COINMASTER_DB_FILE` | File path | `data/db.json` | lowdb JSON file path |

## Risk Mitigation

- **No trading logic changes**: `DBShape` in-memory contract unchanged
- **Default is lowdb**: existing deployments unaffected
- **Health probe**: PostgresStore exposes `healthCheck()` for readiness gates
- **Gradual rollout**: each phase is independently deployable and reversible
