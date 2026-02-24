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
