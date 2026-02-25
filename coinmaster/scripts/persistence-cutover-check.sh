#!/usr/bin/env bash
# persistence-cutover-check.sh
#
# End-to-end cutover verification for the PostgreSQL migration (Issue #3, Phase 3).
#
# What it does:
#   1. Starts a temporary PostgreSQL container on port 55432
#   2. Runs migrations 001 + 002
#   3. Seeds postgres from current lowdb snapshot
#   4. Runs reconciliation (lowdb ↔ postgres)
#   5. Starts the app with PERSISTENCE_BACKEND=postgres, checks /api/health + /api/health/perf
#   6. Tears everything down
#
# Prerequisites: docker, psql (postgresql-client), node/npm, built project (npm run build)
#
# Usage:
#   bash scripts/persistence-cutover-check.sh
#   npm run persistence:cutover-check

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# ── Configuration ─────────────────────────────────────────────────────
PG_CONTAINER="coinmaster_cutover_check_$$"
PG_PORT="${CUTOVER_PG_PORT:-55432}"
PG_USER="coinmaster_test"
PG_PASS="cutover_test_pass"
PG_DB="coinmaster_cutover"
DATABASE_URL="postgresql://${PG_USER}:${PG_PASS}@localhost:${PG_PORT}/${PG_DB}"
APP_PORT="${CUTOVER_APP_PORT:-18787}"
HEALTH_TIMEOUT=30  # seconds to wait for app to become healthy

# ── Colours (if terminal supports them) ───────────────────────────────
if [ -t 1 ]; then
  GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; NC='\033[0m'
else
  GREEN=''; RED=''; YELLOW=''; NC=''
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

# ── Pre-flight checks ────────────────────────────────────────────────
log_step "Pre-flight checks"

command -v docker >/dev/null 2>&1 || { log_fail "docker not found"; exit 1; }
command -v psql >/dev/null 2>&1   || { log_fail "psql not found (install postgresql-client)"; exit 1; }
command -v curl >/dev/null 2>&1   || { log_fail "curl not found"; exit 1; }
log_ok "Required tools available (docker, psql, curl)"

[ -f "$PROJECT_DIR/migrations/001_initial_schema.sql" ] || { log_fail "migrations/001 not found"; exit 1; }
[ -f "$PROJECT_DIR/migrations/002_state_snapshot.sql" ]  || { log_fail "migrations/002 not found"; exit 1; }
log_ok "Migration files present"

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

# Wait for postgres to be ready
echo "  Waiting for PostgreSQL to accept connections..."
for i in $(seq 1 30); do
  if PGPASSWORD="$PG_PASS" psql -h localhost -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -c "SELECT 1" >/dev/null 2>&1; then
    break
  fi
  if [ "$i" -eq 30 ]; then
    log_fail "PostgreSQL did not start within 30s"
    exit 1
  fi
  sleep 1
done
log_ok "PostgreSQL is running"

# ── Run migrations ────────────────────────────────────────────────────
log_step "Running migrations"

PGPASSWORD="$PG_PASS" psql -h localhost -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
  -f "$PROJECT_DIR/migrations/001_initial_schema.sql" -q 2>&1 | tail -1
log_ok "Migration 001 applied"

PGPASSWORD="$PG_PASS" psql -h localhost -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
  -f "$PROJECT_DIR/migrations/002_state_snapshot.sql" -q 2>&1 | tail -1
log_ok "Migration 002 applied"

# Verify tables exist
TABLE_COUNT=$(PGPASSWORD="$PG_PASS" psql -h localhost -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
  -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" | tr -d ' ')
log_ok "Tables created: $TABLE_COUNT public tables"

# ── Seed postgres from lowdb ─────────────────────────────────────────
log_step "Seeding PostgreSQL from lowdb snapshot"

DATABASE_URL="$DATABASE_URL" npx tsx "$PROJECT_DIR/scripts/persistence-seed-postgres.ts" 2>&1 | while IFS= read -r line; do
  echo "  $line"
done
log_ok "Seed completed"

# ── Reconciliation ────────────────────────────────────────────────────
log_step "Running reconciliation (lowdb ↔ postgres)"

set +e
DATABASE_URL="$DATABASE_URL" npx tsx "$PROJECT_DIR/scripts/persistence-reconcile.ts" 2>&1 | while IFS= read -r line; do
  echo "  $line"
done
RECONCILE_EXIT=${PIPESTATUS[0]}
set -e

if [ "$RECONCILE_EXIT" -eq 0 ]; then
  log_ok "Reconciliation passed (exit 0)"
else
  log_fail "Reconciliation failed (exit $RECONCILE_EXIT)"
fi

# ── Start app with PERSISTENCE_BACKEND=postgres ──────────────────────
log_step "Starting app with PERSISTENCE_BACKEND=postgres (port $APP_PORT)"

PERSISTENCE_BACKEND=postgres \
DATABASE_URL="$DATABASE_URL" \
PORT="$APP_PORT" \
HOST="127.0.0.1" \
  npx tsx "$PROJECT_DIR/src/server/index.ts" &
APP_PID=$!

echo "  App PID: $APP_PID"

# Wait for health endpoint
echo "  Waiting for /api/health..."
HEALTHY=false
for i in $(seq 1 "$HEALTH_TIMEOUT"); do
  if curl -sf "http://127.0.0.1:${APP_PORT}/api/health" >/dev/null 2>&1; then
    HEALTHY=true
    break
  fi
  sleep 1
done

if [ "$HEALTHY" = true ]; then
  log_ok "/api/health responded"
else
  log_fail "/api/health did not respond within ${HEALTH_TIMEOUT}s"
fi

# ── Check /api/health ────────────────────────────────────────────────
log_step "Verifying /api/health"

HEALTH_RESP=$(curl -sf "http://127.0.0.1:${APP_PORT}/api/health" 2>/dev/null || echo '{}')
echo "  Response: $HEALTH_RESP"

if echo "$HEALTH_RESP" | grep -q '"ok":true'; then
  log_ok "/api/health → ok: true"
else
  log_fail "/api/health → unexpected response"
fi

# ── Check /api/health/perf ───────────────────────────────────────────
log_step "Verifying /api/health/perf"

PERF_RESP=$(curl -sf "http://127.0.0.1:${APP_PORT}/api/health/perf" 2>/dev/null || echo '{}')
echo "  Response: $PERF_RESP"

if echo "$PERF_RESP" | grep -q '"ok":true'; then
  log_ok "/api/health/perf → ok: true"
else
  log_fail "/api/health/perf → unexpected response"
fi

# ── Stop app ──────────────────────────────────────────────────────────
log_step "Stopping app"

kill "$APP_PID" 2>/dev/null || true
wait "$APP_PID" 2>/dev/null || true
APP_PID=""
log_ok "App stopped"

# ── Summary ───────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo -e "  Cutover check: ${GREEN}${pass_count} passed${NC}, ${RED}${fail_count} failed${NC}"
echo "═══════════════════════════════════════════════════════════════════"

if [ "$fail_count" -gt 0 ]; then
  echo -e "${RED}CUTOVER CHECK FAILED${NC} — review errors above before proceeding."
  exit 1
else
  echo -e "${GREEN}CUTOVER CHECK PASSED${NC} — safe to proceed with cutover."
  exit 0
fi
