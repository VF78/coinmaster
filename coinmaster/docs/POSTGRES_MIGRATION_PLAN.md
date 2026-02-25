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

### Phase 2 — Dual-Write / Shadow + Reconciliation
- [x] `DualWriteStore` class — wraps lowdb (primary) + postgres (shadow)
- [x] `getData()` always returns primary (lowdb) snapshot
- [x] `flush()` writes primary first, then best-effort shadow (errors logged, never fatal)
- [x] Activated via `PERSISTENCE_DUAL_WRITE=true` when `PERSISTENCE_BACKEND=lowdb`
- [x] `scripts/persistence-seed-postgres.ts` — one-shot copy lowdb → postgres snapshot
- [x] `scripts/persistence-reconcile.ts` — compares lowdb vs postgres (settings, counts, key IDs); exit 0=ok, 1=diff, 2=error
- [x] npm scripts: `persistence:seed-pg`, `persistence:reconcile`

**How to activate:**
```bash
# 1. Seed postgres with current lowdb data
DATABASE_URL=postgresql://user:pass@localhost:5432/coinmaster \
  npm run persistence:seed-pg

# 2. Enable dual-write shadow mode
PERSISTENCE_BACKEND=lowdb \
PERSISTENCE_DUAL_WRITE=true \
DATABASE_URL=postgresql://user:pass@localhost:5432/coinmaster \
  npm run start

# 3. After running for a while, verify data consistency
DATABASE_URL=postgresql://user:pass@localhost:5432/coinmaster \
  npm run persistence:reconcile
```

**Validation criteria:**
- Run dual-write in staging for 48–72h
- `persistence:reconcile` returns exit code 0 (no differences)
- No `[dual-write] Shadow flush failed` errors in logs

### Phase 3 — Cutover / Rollback Automation

**Automated verification scripts** (added in Phase 3):

| npm script | What it does |
|---|---|
| `npm run persistence:cutover-check` | Full cutover dry-run: docker PG → migrations → seed → reconcile → app health |
| `npm run persistence:rollback-check` | Cutover + rollback: verifies return to lowdb works after postgres run |

**Cutover check (`scripts/persistence-cutover-check.sh`):**
```bash
npm run persistence:cutover-check
```
Steps performed automatically:
1. Starts temporary PostgreSQL container (port 55432, configurable via `CUTOVER_PG_PORT`)
2. Applies `migrations/001_initial_schema.sql` + `002_state_snapshot.sql`
3. Runs `npm run persistence:seed-pg` (copies lowdb → postgres)
4. Runs `npm run persistence:reconcile` (compares lowdb ↔ postgres, must exit 0)
5. Starts app with `PERSISTENCE_BACKEND=postgres`, verifies `/api/health` and `/api/health/perf`
6. Stops app and removes docker container

Expected output (success):
```
[1] Pre-flight checks
  ✓ Required tools available (docker, psql, curl)
  ✓ Migration files present
[2] Starting temporary PostgreSQL (port 55432)
  ✓ PostgreSQL is running
[3] Running migrations
  ✓ Migration 001 applied
  ✓ Migration 002 applied
  ✓ Tables created: N public tables
[4] Seeding PostgreSQL from lowdb snapshot
  ✓ Seed completed
[5] Running reconciliation (lowdb ↔ postgres)
  ✓ Reconciliation passed (exit 0)
[6] Starting app with PERSISTENCE_BACKEND=postgres (port 18787)
  ✓ App healthy on postgres backend
[7] Verifying /api/health
  ✓ /api/health → ok: true
[8] Verifying /api/health/perf
  ✓ /api/health/perf → ok: true
[9] Stopping app
  ✓ App stopped

  Cutover check: 11 passed, 0 failed
  CUTOVER CHECK PASSED — safe to proceed with cutover.
```

**Rollback check (`scripts/persistence-rollback-check.sh`):**
```bash
npm run persistence:rollback-check
```
Steps performed automatically:
1. Backs up current lowdb file
2. Starts temporary PostgreSQL, applies migrations, seeds data
3. Starts app with `PERSISTENCE_BACKEND=postgres`, verifies health
4. Stops app, restarts with `PERSISTENCE_BACKEND=lowdb` (rollback)
5. Verifies health on lowdb backend
6. Restores lowdb backup
7. Prints production rollback instructions for reference

Expected output (success):
```
  Rollback check: N passed, 0 failed
  ROLLBACK CHECK PASSED — rollback procedure verified.
```

---

**Pre-cutover checklist:**
- [ ] `npm run persistence:cutover-check` passes (exit 0)
- [ ] `npm run persistence:rollback-check` passes (exit 0)
- [ ] Dual-write has been running for ≥48h with zero shadow errors
- [ ] `npm run persistence:reconcile` returns exit 0 against production PG
- [ ] PostgreSQL backup taken: `pg_dump -Fc coinmaster > pre_cutover.dump`
- [ ] lowdb backup taken: `cp data/db.json data/db.json.pre_cutover`

**Production cutover steps:**
```bash
# 1. Run automated cutover check (uses temporary docker PG)
npm run persistence:cutover-check
# Must exit 0

# 2. Final reconcile against production PG
DATABASE_URL=postgresql://... npm run persistence:reconcile
# Must exit 0

# 3. Stop the application
kill $APP_PID  # or systemctl stop coinmaster

# 4. Switch backend
export PERSISTENCE_BACKEND=postgres
export PERSISTENCE_DUAL_WRITE=   # disable dual-write
export DATABASE_URL=postgresql://...

# 5. Start with postgres as primary
npm run start

# 6. Verify health
curl http://localhost:8787/api/health
# Expected: {"ok":true}
curl http://localhost:8787/api/health/perf
# Expected: {"ok":true,"uptimeSeconds":...,"memory":{...},...}
```

**Production rollback (if issues found):**
```bash
# 1. Stop the application
kill $APP_PID

# 2. Revert to lowdb
export PERSISTENCE_BACKEND=lowdb
unset PERSISTENCE_DUAL_WRITE
# (DATABASE_URL can stay — it is ignored when backend=lowdb)

# 3. If lowdb data is stale, restore backup
cp data/db.json.pre_cutover data/db.json

# 4. Restart
npm run start

# 5. Verify
curl http://localhost:8787/api/health
# Expected: {"ok":true}

# 6. (Optional) Re-enable dual-write for re-cutover attempt
export PERSISTENCE_DUAL_WRITE=true
export DATABASE_URL=postgresql://...
npm run start
```

**Post-cutover monitoring (1 week):**
- Watch `healthCheck()` responses for `ok: true`
- Monitor flush latency (postgres is slightly slower than file I/O)
- Keep `data/db.json.pre_cutover` available for emergency rollback

### Phase 4 — Normalised Tables (future)
- Migrate from snapshot-bridge (`state_snapshot` JSONB) to normalised tables (`001_initial_schema.sql`)
- PostgresStore reads/writes individual tables instead of single JSONB document
- Enables SQL queries, indexing, and partial updates

### Phase 5 — Cleanup
- Remove lowdb dependency and `data/db.json` path
- Remove `DualWriteStore` and dual-write env flag
- Archive migration scripts
- Drop `PERSISTENCE_BACKEND` env switch

## Rollback Procedure

At any phase, rollback is:

1. Set `PERSISTENCE_BACKEND=lowdb` (or remove the env var)
2. Unset `PERSISTENCE_DUAL_WRITE`
3. Restart the process
4. The system immediately reverts to JSON file persistence

No data loss risk: lowdb remains the source of truth until Phase 3 cutover.

## Environment Variables

| Variable | Values | Default | Description |
|---|---|---|---|
| `PERSISTENCE_BACKEND` | `lowdb`, `postgres` | `lowdb` | Active persistence backend |
| `PERSISTENCE_DUAL_WRITE` | `true`, `1` | _(off)_ | Enable shadow writes to postgres (only when backend=lowdb) |
| `DATABASE_URL` | PostgreSQL connection string | — | Required when backend=postgres or dual-write=true |
| `COINMASTER_DB_FILE` | File path | `data/db.json` | lowdb JSON file path |

## Risk Mitigation

- **No trading logic changes**: `DBShape` in-memory contract unchanged
- **Default is lowdb**: existing deployments unaffected
- **Health probe**: PostgresStore exposes `healthCheck()` for readiness gates
- **Gradual rollout**: each phase is independently deployable and reversible
- **Shadow writes are non-fatal**: dual-write mode never breaks the primary lowdb path
- **Reconciliation script**: automated verification before cutover
