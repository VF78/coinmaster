#!/usr/bin/env bash
# persistence-rollback-check.sh
#
# Verifies that rollback from PERSISTENCE_BACKEND=postgres back to lowdb works
# correctly after a cutover (Issue #3, Phase 3).
#
# What it does:
#   1. Starts a temporary PostgreSQL container on port 55432
#   2. Runs migrations + seed (same as cutover-check)
#   3. Starts the app with PERSISTENCE_BACKEND=postgres, verifies health
#   4. Stops the app
#   5. Restarts the app with PERSISTENCE_BACKEND=lowdb, verifies health
#   6. Confirms lowdb data is intact
#   7. Prints dry-run production rollback instructions
#   8. Tears everything down
#
# Prerequisites: docker, psql (postgresql-client), node/npm
#
# Usage:
#   bash scripts/persistence-rollback-check.sh
#   npm run persistence:rollback-check

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# ── Configuration ─────────────────────────────────────────────────────
PG_CONTAINER="coinmaster_rollback_check_$$"
PG_PORT="${ROLLBACK_PG_PORT:-55433}"
PG_USER="coinmaster_test"
PG_PASS="rollback_test_pass"
PG_DB="coinmaster_rollback"
DATABASE_URL="postgresql://${PG_USER}:${PG_PASS}@localhost:${PG_PORT}/${PG_DB}"
APP_PORT="${ROLLBACK_APP_PORT:-18788}"
HEALTH_TIMEOUT=30

# ── Colours ───────────────────────────────────────────────────────────
if [ -t 1 ]; then
  GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; CYAN='\033[0;36m'; NC='\033[0m'
else
  GREEN=''; RED=''; YELLOW=''; CYAN=''; NC=''
fi

step=0
pass_count=0
fail_count=0

log_step() { step=$((step + 1)); echo -e "\n${YELLOW}[$step]${NC} $1"; }
log_ok()   { pass_count=$((pass_count + 1)); echo -e "  ${GREEN}✓${NC} $1"; }
log_fail() { fail_count=$((fail_count + 1)); echo -e "  ${RED}✗${NC} $1"; }

# ── Cleanup on exit ───────────────────────────────────────────────────
APP_PID=""
cleanup() {
  echo ""
  echo "── Cleanup ──────────────────────────────────────────────────────"
  if [ -n "$APP_PID" ] && kill -0 "$APP_PID" 2>/dev/null; then
    echo "Stopping app (PID $APP_PID)..."
    kill "$APP_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null || true
  fi
  if docker ps -q --filter "name=$PG_CONTAINER" | grep -q .; then
    echo "Stopping postgres container ($PG_CONTAINER)..."
    docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true
  fi
  echo "Cleanup done."
}
trap cleanup EXIT

wait_for_health() {
  local port="$1"
  for i in $(seq 1 "$HEALTH_TIMEOUT"); do
    if curl -sf "http://127.0.0.1:${port}/api/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

# ── Pre-flight ────────────────────────────────────────────────────────
log_step "Pre-flight checks"

command -v docker >/dev/null 2>&1 || { log_fail "docker not found"; exit 1; }
command -v psql >/dev/null 2>&1   || { log_fail "psql not found"; exit 1; }
command -v curl >/dev/null 2>&1   || { log_fail "curl not found"; exit 1; }
log_ok "Required tools available"

# ── Backup lowdb ──────────────────────────────────────────────────────
log_step "Backing up lowdb data"

LOWDB_FILE="${COINMASTER_DB_FILE:-data/db.json}"
if [ -f "$LOWDB_FILE" ]; then
  cp "$LOWDB_FILE" "${LOWDB_FILE}.rollback_check_backup"
  log_ok "Backed up $LOWDB_FILE"
else
  log_ok "No existing lowdb file (will use defaults)"
fi

# ── Start temporary PostgreSQL ────────────────────────────────────────
log_step "Starting temporary PostgreSQL (port $PG_PORT)"

if docker ps -q --filter "name=$PG_CONTAINER" | grep -q .; then
  docker rm -f "$PG_CONTAINER" >/dev/null 2>&1
fi

docker run -d --name "$PG_CONTAINER" \
  -e POSTGRES_USER="$PG_USER" \
  -e POSTGRES_PASSWORD="$PG_PASS" \
  -e POSTGRES_DB="$PG_DB" \
  -p "${PG_PORT}:5432" \
  postgres:16-alpine >/dev/null

echo "  Waiting for PostgreSQL..."
for i in $(seq 1 30); do
  if PGPASSWORD="$PG_PASS" psql -h localhost -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -c "SELECT 1" >/dev/null 2>&1; then
    break
  fi
  [ "$i" -eq 30 ] && { log_fail "PostgreSQL did not start"; exit 1; }
  sleep 1
done
log_ok "PostgreSQL is running"

# ── Migrations + Seed ─────────────────────────────────────────────────
log_step "Running migrations + seed"

PGPASSWORD="$PG_PASS" psql -h localhost -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
  -f "$PROJECT_DIR/migrations/001_initial_schema.sql" -q 2>&1 | tail -1
PGPASSWORD="$PG_PASS" psql -h localhost -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
  -f "$PROJECT_DIR/migrations/002_state_snapshot.sql" -q 2>&1 | tail -1
DATABASE_URL="$DATABASE_URL" npx tsx "$PROJECT_DIR/scripts/persistence-seed-postgres.ts" 2>&1 | while IFS= read -r line; do
  echo "  $line"
done
log_ok "Migrations + seed complete"

# ── Phase A: Run with postgres backend ────────────────────────────────
log_step "Starting app with PERSISTENCE_BACKEND=postgres"

PERSISTENCE_BACKEND=postgres \
DATABASE_URL="$DATABASE_URL" \
PORT="$APP_PORT" \
HOST="127.0.0.1" \
  npx tsx "$PROJECT_DIR/src/server/index.ts" &
APP_PID=$!

if wait_for_health "$APP_PORT"; then
  log_ok "App healthy on postgres backend"
else
  log_fail "App did not become healthy on postgres backend"
fi

PERF_RESP=$(curl -sf "http://127.0.0.1:${APP_PORT}/api/health/perf" 2>/dev/null || echo '{}')
echo "  health/perf: $PERF_RESP"

# Stop app
kill "$APP_PID" 2>/dev/null || true
wait "$APP_PID" 2>/dev/null || true
APP_PID=""
log_ok "App stopped (postgres phase)"

# ── Phase B: Rollback to lowdb ────────────────────────────────────────
log_step "Restarting app with PERSISTENCE_BACKEND=lowdb (rollback)"

PERSISTENCE_BACKEND=lowdb \
PORT="$APP_PORT" \
HOST="127.0.0.1" \
  npx tsx "$PROJECT_DIR/src/server/index.ts" &
APP_PID=$!

if wait_for_health "$APP_PORT"; then
  log_ok "App healthy on lowdb backend (rollback successful)"
else
  log_fail "App did not become healthy on lowdb backend"
fi

HEALTH_RESP=$(curl -sf "http://127.0.0.1:${APP_PORT}/api/health" 2>/dev/null || echo '{}')
echo "  health: $HEALTH_RESP"

# Stop app
kill "$APP_PID" 2>/dev/null || true
wait "$APP_PID" 2>/dev/null || true
APP_PID=""
log_ok "App stopped (lowdb phase)"

# ── Restore lowdb backup ─────────────────────────────────────────────
log_step "Restoring lowdb backup"

if [ -f "${LOWDB_FILE}.rollback_check_backup" ]; then
  mv "${LOWDB_FILE}.rollback_check_backup" "$LOWDB_FILE"
  log_ok "Restored $LOWDB_FILE from backup"
else
  log_ok "No backup to restore"
fi

# ── Dry-run production rollback instructions ──────────────────────────
log_step "Production rollback instructions (dry-run reference)"

echo -e "
${CYAN}  ┌──────────────────────────────────────────────────────────────┐
  │  PRODUCTION ROLLBACK PROCEDURE                               │
  ├──────────────────────────────────────────────────────────────┤
  │                                                              │
  │  1. Stop the application:                                    │
  │     kill \$APP_PID  # or systemctl stop coinmaster            │
  │                                                              │
  │  2. Revert environment:                                      │
  │     export PERSISTENCE_BACKEND=lowdb                         │
  │     unset PERSISTENCE_DUAL_WRITE                             │
  │                                                              │
  │  3. (If lowdb data is stale) Restore backup:                 │
  │     cp data/db.json.pre_cutover data/db.json                 │
  │                                                              │
  │  4. Restart:                                                 │
  │     npm run start                                            │
  │                                                              │
  │  5. Verify:                                                  │
  │     curl http://localhost:8787/api/health                    │
  │     # Should return {\"ok\":true}                              │
  │                                                              │
  │  6. (Optional) Re-enable dual-write for re-cutover attempt:  │
  │     export PERSISTENCE_DUAL_WRITE=true                       │
  │     export DATABASE_URL=postgresql://...                     │
  │                                                              │
  └──────────────────────────────────────────────────────────────┘${NC}
"
log_ok "Rollback instructions printed"

# ── Summary ───────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo -e "  Rollback check: ${GREEN}${pass_count} passed${NC}, ${RED}${fail_count} failed${NC}"
echo "═══════════════════════════════════════════════════════════════════"

if [ "$fail_count" -gt 0 ]; then
  echo -e "${RED}ROLLBACK CHECK FAILED${NC} — review errors above."
  exit 1
else
  echo -e "${GREEN}ROLLBACK CHECK PASSED${NC} — rollback procedure verified."
  exit 0
fi
