# Coinmaster Runbook Commands

Quick-reference commands for operating and troubleshooting the Coinmaster instance.

## Startup

```bash
# Development (hot-reload API + Vite dev server)
npm run dev

# Production build + start
npm run build
PORT=8787 HOST=0.0.0.0 npm run start
```

## Health & Smoke Checks

```bash
# Basic health
curl -sS http://127.0.0.1:8787/api/health | jq .

# Full smoke suite
API_BASE_URL=http://127.0.0.1:8787 npm run ops:smoke

# Dashboard state
curl -sS http://127.0.0.1:8787/api/dashboard | jq '.symbol, .liveMode'

# Live connection status
curl -sS http://127.0.0.1:8787/api/live/status | jq .
```

## P1-10 Audit Checks

Performance and observability commands added as part of Issue #18.

### Performance snapshot

```bash
# Collect performance metrics (RSS, heap, event-loop lag, uptime)
curl -sS http://127.0.0.1:8787/api/health/perf | jq .

# Expected output shape:
# {
#   "ok": true,
#   "uptimeSeconds": 3600,
#   "memory": { "rss": 85.2, "heapTotal": 60.1, "heapUsed": 45.3, "external": 1.2 },
#   "eventLoopLagMs": 0.42,
#   "timestamp": "2026-02-24T12:00:00.000Z"
# }
```

### Baseline collection (run after 1h uptime)

```bash
# Save baseline snapshot
curl -sS http://127.0.0.1:8787/api/health/perf | jq . > /tmp/perf_baseline_$(date +%Y%m%d_%H%M).json

# Compare two snapshots
diff <(jq '.memory' /tmp/perf_baseline_old.json) <(jq '.memory' /tmp/perf_baseline_new.json)
```

### Memory growth check

```bash
# Watch memory every 60s for 10 iterations
for i in $(seq 1 10); do
  echo "--- $(date) ---"
  curl -sS http://127.0.0.1:8787/api/health/perf | jq '{rss: .memory.rss, heap: .memory.heapUsed, lag: .eventLoopLagMs}'
  sleep 60
done
```

### Process-level checks (on VPS)

```bash
# Node.js process info
ps aux | grep 'tsx.*server/index' | grep -v grep

# Open file descriptors
ls /proc/$(pgrep -f 'tsx.*server/index')/fd | wc -l

# Network connections
ss -tnp | grep :8787
```

### TypeScript & build verification

```bash
# Type check (no emit)
npm run check

# Production build
npm run build

# Full verification sequence
npm run check && npm run build && PORT=8878 HOST=127.0.0.1 npm run start &
sleep 3
API_BASE_URL=http://127.0.0.1:8878 npm run ops:smoke
curl -sS http://127.0.0.1:8878/api/health/perf | jq .
kill %1
```

## Trading Rules Invariant Checks

Offline verification of runtime trading-rules precedence logic (Issue #20, Subtask 6).
No server or exchange connection required — tests pure functions only.

```bash
# Run all invariant checks
npm run invariants:trading-rules

# What it verifies:
# 1. Explicit TP/SL overrides runtime defaults (precedence)
# 2. Runtime defaults auto-applied when explicit values missing
# 3. Disabled symbol → order blocked (isSymbolEnabled)
# 4. Allocation cap exceeded → order blocked (maxNotionalForSymbol)
# 5. Env fallback (no DB) → all symbols blocked, no TP/SL defaults

# Exit code: 0 = all pass, 1 = failures found
```

Include in pre-deploy or CI verification:

```bash
npm run check && npm run invariants:trading-rules && npm run build
```

## Allocation Sizing Invariant Checks

Deterministic verification of `computeAllocationSize()` — the pure function that
derives position size from equity, available margin, per-symbol allocation % and
leverage (Issue #24, Subtask B). No server or exchange connection required.

```bash
# Run allocation sizing invariants
npm run invariants:allocation-sizing

# What it verifies:
# Case 1: BTC happy-path — equity=100, available=100, BTC 50%, lev=10
#          → margin=50, notional=500, size=0.01
# Case 2: Sequential allocation — after BTC consumed $50 margin,
#          SOL 20%, lev=10 → margin=20, notional=200, size=2.0
# Case 3: Insufficient available margin (available < targetMargin)
#          → reason='insufficient_available_margin'
# Case 4: Disabled symbol / unknown symbol / env_fallback
#          → reason='symbol_not_enabled'

# Exit code: 0 = all pass, 1 = failures found
```

Include in pre-deploy verification:

```bash
npm run check && npm run invariants:trading-rules && npm run invariants:allocation-sizing && npm run build
```

## Rate Limit & Request Protection (Issue #18 S3)

The API has in-memory rate limiting on all `/api/*` endpoints except `/api/health` and `/api/health/perf`.

- **Default**: 120 req/min per IP (env `API_RATE_LIMIT_RPM`)
- **JSON body limit**: 256kb (env `API_JSON_LIMIT`)
- **Exceeded**: HTTP 429 `{ "ok": false, "error": "rate_limited" }`

### Verify rate limiting works

```bash
# Flood test: send 130 rapid requests to /api/dashboard (limit is 120/min)
for i in $(seq 1 130); do
  HTTP=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8787/api/dashboard)
  echo "req $i → HTTP $HTTP"
done
# Expected: requests 1-120 return 200, requests 121+ return 429

# Verify health endpoints are NOT rate-limited
for i in $(seq 1 130); do
  HTTP=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8787/api/health)
  echo "req $i → HTTP $HTTP"
done
# Expected: all 130 return 200

# Verify oversized body is rejected (413)
python3 -c "print('{\"x\":\"' + 'A'*300000 + '\"}')" | \
  curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' \
  --data-binary @- http://127.0.0.1:8787/api/bias
# Expected: HTTP 413
```

### Tuning

```bash
# Raise limit to 200 req/min and 1MB body
API_RATE_LIMIT_RPM=200 API_JSON_LIMIT=1mb npm run start
```

## VPS Migration (46.225.133.161)

```bash
# Pre-migration: backup current state
scp user@current-host:~/coinmaster/data/db.json ./db_backup_$(date +%Y%m%d).json

# On new VPS: deploy
git clone <repo> coinmaster && cd coinmaster
npm install && npm run build
cp /path/to/.env .env && chmod 600 .env
mkdir -p data && cp /path/to/db.json data/

# Smoke test on new VPS
PORT=8787 HOST=127.0.0.1 npm run start &
sleep 3
API_BASE_URL=http://127.0.0.1:8787 npm run ops:smoke
curl -sS http://127.0.0.1:8787/api/health/perf | jq .
kill %1
```

## Freqtrade Stage 1 Deployment Protocol

Current production deployment is split into two surfaces:

1. **CoinMaster companion app** on `127.0.0.1:8787` (`coinmaster.service`) for custom/reference UI and rules export.
2. **Native Freqtrade** on `127.0.0.1:8080` (`coinmaster-freqtrade` container/service) for dry-run/live execution, FreqUI/API, backtests, protections, orders, and positions.

### Pre-deploy gates

```bash
npm run invariants:trading-rules
npm run invariants:signal-quality
npm run check
npm run build
python3 -m py_compile freqtrade/user_data/strategies/CoinMasterStrategy.py
```

### Safe deploy

Use the safe deploy script from the repo root:

```bash
TARGET_DIR=/opt/coinmaster SERVICE=coinmaster.service ./scripts/deploy-prod-safe.sh
```

The deploy script syncs only known app/runtime trees and preserves Freqtrade private/runtime state:

- preserved: `freqtrade/user_data/config.private.json`, `data/`, `runtime/`, `backtest_results/`, `hyperopt_results/`, sqlite DBs;
- synced: `src`, `dist`, `dist-custom`, `docs`, `scripts`, `freqtrade` code/config/systemd/runbooks.

### Freqtrade dry-run deploy/restart check

```bash
cd /opt/coinmaster/freqtrade
sudo systemctl daemon-reload
sudo systemctl enable coinmaster-freqtrade || true
sudo systemctl restart coinmaster-freqtrade || docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans

docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=250 freqtrade
curl -fsS http://127.0.0.1:8080/api/v1/ping
```

If `initial_state` is `stopped`, start dry-run through FreqUI/API only after config/log checks:

```bash
# Use Freqtrade API credentials from ignored config.private.json.
curl -fsS http://127.0.0.1:8080/api/v1/ping
```

### Post-deploy audit

Check all of the following before calling the deploy healthy:

- `coinmaster.service` active and `/api/health` returns `{"ok":true}`.
- Freqtrade API `/show_config` shows `dry_run=true`, `state=running`, expected whitelist and `timeframe=5m`.
- Freqtrade logs have no material `ERROR`, `Traceback`, exchange failures, non-tradable pair warnings, or repeated timeouts.
- `/api/v1/status`, `/api/v1/balance`, `/api/v1/locks`, and `/api/v1/performance` respond.
- No old CoinMaster live execution monitors are active against the same account.

### Current dry-run candidate

As of the 2026-04-27 overnight run, the selected candidate is ETH/HYPE both sides with 42 trades and +39.36% on 2026-01-01..2026-04-26. Evidence lives under `reports/freqtrade-nightly-20260427/` in the working repo; do not promote to live without owner approval.
