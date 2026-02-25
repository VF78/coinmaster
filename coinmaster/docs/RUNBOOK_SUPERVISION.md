# Runbook: Process Supervision Checks

Baseline checks for verifying coinmaster process supervision (systemd or equivalent).

## Prerequisites

The service unit is assumed to be named `coinmaster.service`.
Adjust the unit name if your deployment differs.

## 1. Service Status

```bash
# Check if the service is running
systemctl is-active coinmaster.service

# Full status with recent logs
systemctl status coinmaster.service

# Verify the service is enabled for auto-start on boot
systemctl is-enabled coinmaster.service
```

Expected: `active` / `enabled`.

## 2. Restart Latency

```bash
# Measure restart wall-clock time
time systemctl restart coinmaster.service

# Confirm service is active after restart
systemctl is-active coinmaster.service

# Tail logs to verify the server started listening
journalctl -u coinmaster.service -n 20 --no-pager | grep 'server listening'
```

Expected: restart completes in < 5 s; `server listening` log appears.

## 3. Graceful Shutdown (SIGTERM)

The process handles SIGTERM with a graceful shutdown sequence:
timers cleared, WS streams closed, risk audit flushed, persistence store closed.

```bash
# Find the main process PID
PID=$(systemctl show -p MainPID --value coinmaster.service)

# Send SIGTERM
kill -TERM "$PID"

# Watch the journal for the shutdown sequence
journalctl -u coinmaster.service -f --no-pager | grep -E 'shutdown|cleanup|closed|exiting'
```

Expected log sequence:
1. `received signal, shutting down gracefully` (signal=SIGTERM)
2. `HTTP server closed`
3. `persistence store closed`
4. `cleanup complete, exiting`

After exit, systemd should auto-restart the service (if `Restart=always`).

```bash
# Confirm auto-restart happened
sleep 5 && systemctl is-active coinmaster.service
```

## 4. Forced Kill Recovery (SIGKILL / kill -9)

```bash
PID=$(systemctl show -p MainPID --value coinmaster.service)

# Force kill — no graceful shutdown
kill -9 "$PID"

# Verify systemd restarts the process
sleep 5 && systemctl is-active coinmaster.service

# Confirm a new PID was assigned
NEW_PID=$(systemctl show -p MainPID --value coinmaster.service)
[ "$PID" != "$NEW_PID" ] && echo "OK: restarted with PID $NEW_PID" || echo "FAIL: same PID or not running"
```

Expected: service returns to `active` within the configured `RestartSec` window.

## 5. Health Endpoint Verification

After any restart, confirm the application is healthy:

```bash
curl -sf http://localhost:8787/api/health | jq .
```

Expected: HTTP 200 with status fields.

## 6. Log Verification After Restart

Confirm that runtime-critical subsystems initialized:

```bash
journalctl -u coinmaster.service --since "1 min ago" --no-pager | grep -E 'server listening|drawdown watchdog started|WS connected|rules refresh'
```

All four components should appear in the logs shortly after startup.


## 7. WS Backoff Verification

Verify exponential reconnect schedule (1s → 2s → 4s ... cap 60s) from logs.

```bash
# 1) Tail reconnect logs
journalctl -u coinmaster.service -f --no-pager | grep -E 'WS disconnected|scheduling WS reconnect'

# 2) Temporarily block outbound WS connectivity (example), wait ~30s, then unblock
# NOTE: adapt to your firewall tooling/environment.
# sudo iptables -I OUTPUT -p tcp --dport 443 -j REJECT
# sleep 30
# sudo iptables -D OUTPUT -p tcp --dport 443 -j REJECT

# 3) Confirm delay values increase and then reset to 1s after reconnect
curl -sS -u 'vladimir:***' https://coinmaster24.com/api/health/perf | jq '.ws'
```

Expected:
- `reconnectAttempts` increases during disconnect period.
- `lastReconnectDelayMs` grows exponentially up to 60000.
- After successful reconnect, backoff resets and `connected=true`.
