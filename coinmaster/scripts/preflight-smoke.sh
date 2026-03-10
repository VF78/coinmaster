#!/usr/bin/env bash
set -euo pipefail

# ── Preflight / Smoke-check for coinmaster API ──────────────────────
# Usage:  API_BASE_URL=http://127.0.0.1:8787 bash ./scripts/preflight-smoke.sh
# Exit 0 = all checks passed, non-zero = at least one failed.

BASE="${API_BASE_URL:-http://127.0.0.1:8787}"
PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  PASS  $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL  $1  — $2"; }

echo "=== coinmaster preflight smoke-check ==="
echo "    target: ${BASE}"
echo ""

# ── 1. /api/health ──────────────────────────────────────────────────
EP="/api/health"
HTTP=$(curl -s -o /tmp/cm_smoke_health.json -w '%{http_code}' "${BASE}${EP}" 2>/dev/null || true)
if [[ "$HTTP" == "200" ]] && grep -q '"ok":true' /tmp/cm_smoke_health.json 2>/dev/null; then
  pass "$EP  (HTTP ${HTTP}, ok=true)"
else
  fail "$EP" "HTTP ${HTTP:-no_response}"
fi

# ── 2. /api/dashboard ──────────────────────────────────────────────
EP="/api/dashboard"
HTTP=$(curl -s -o /tmp/cm_smoke_dashboard.json -w '%{http_code}' "${BASE}${EP}" 2>/dev/null || true)
if [[ "$HTTP" == "200" ]] && python3 -c "import json,sys; json.load(sys.stdin)" < /tmp/cm_smoke_dashboard.json 2>/dev/null; then
  pass "$EP  (HTTP ${HTTP}, valid JSON)"
else
  fail "$EP" "HTTP ${HTTP:-no_response} or invalid JSON"
fi

# ── 3. /api/live/status ────────────────────────────────────────────
EP="/api/live/status"
HTTP=$(curl -s -o /tmp/cm_smoke_status.json -w '%{http_code}' "${BASE}${EP}" 2>/dev/null || true)
if [[ "$HTTP" == "200" ]] && python3 -c "import json,sys; json.load(sys.stdin)" < /tmp/cm_smoke_status.json 2>/dev/null; then
  # ok=false is acceptable (exchange keys may not be configured)
  pass "$EP  (HTTP ${HTTP}, valid JSON)"
else
  fail "$EP" "HTTP ${HTTP:-no_response} or invalid JSON"
fi

# ── 4. Secured owner endpoints (optional) ───────────────────────────
if [[ -n "${OWNER_AUTH_TOKEN:-}" ]]; then
  AUTH=(-H "Authorization: Bearer ${OWNER_AUTH_TOKEN}")

  EP="/api/settings/read-only-exchanges"
  HTTP=$(curl -s "${AUTH[@]}" -o /tmp/cm_smoke_ro_settings.json -w '%{http_code}' "${BASE}${EP}" 2>/dev/null || true)
  if [[ "$HTTP" == "200" ]] && python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('ok') is True and 'exchanges' in d" < /tmp/cm_smoke_ro_settings.json 2>/dev/null; then
    pass "$EP  (HTTP ${HTTP}, ok=true, exchanges present)"
  else
    fail "$EP" "HTTP ${HTTP:-no_response} or invalid JSON"
  fi

  EP="/api/settings/read-only-exchanges/bybit/test"
  HTTP=$(curl -s "${AUTH[@]}" -X POST -o /tmp/cm_smoke_bybit_test.json -w '%{http_code}' "${BASE}${EP}" 2>/dev/null || true)
  if [[ "$HTTP" == "200" ]] && python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('ok') is True and 'status' in d" < /tmp/cm_smoke_bybit_test.json 2>/dev/null; then
    pass "$EP  (HTTP ${HTTP}, ok=true, status present)"
  else
    fail "$EP" "HTTP ${HTTP:-no_response} or invalid JSON"
  fi

  EP="/api/ai-master/snapshot?limit=5"
  HTTP=$(curl -s "${AUTH[@]}" -o /tmp/cm_smoke_ai_master.json -w '%{http_code}' "${BASE}${EP}" 2>/dev/null || true)
  if [[ "$HTTP" == "200" ]] && python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('ok') is True and 'insights' in d and 'qa' in d" < /tmp/cm_smoke_ai_master.json 2>/dev/null; then
    pass "$EP  (HTTP ${HTTP}, ok=true, insights+qa present)"
  else
    fail "$EP" "HTTP ${HTTP:-no_response} or invalid JSON"
  fi
else
  echo "  SKIP  secured owner endpoints (OWNER_AUTH_TOKEN not set)"
fi

# ── Summary ─────────────────────────────────────────────────────────
echo ""
echo "=== Results: ${PASS} passed, ${FAIL} failed ==="

if [[ "$FAIL" -gt 0 ]]; then
  echo "SMOKE CHECK FAILED"
  exit 1
fi

echo "ALL CHECKS PASSED"
exit 0
