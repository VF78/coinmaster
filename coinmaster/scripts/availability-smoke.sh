#!/usr/bin/env bash
set -euo pipefail

# CoinMaster availability/autorecovery smoke check.
# Read-only by default: verifies supervision layers, app health, Freqtrade dry-run
# state, Radar policy freshness, Docker restart policy, and watchdog evidence.

APP_DIR="${APP_DIR:-/opt/coinmaster}"
FREQTRADE_DIR="$APP_DIR/freqtrade"
APP_SERVICE="${APP_SERVICE:-coinmaster.service}"
FREQTRADE_SERVICE="${FREQTRADE_SERVICE:-coinmaster-freqtrade.service}"
DATASET_TIMER="${DATASET_TIMER:-coinmaster-freqtrade-dataset-sync.timer}"
APP_HEALTH_URL="${APP_HEALTH_URL:-http://127.0.0.1:8787/api/health}"
RADAR_POLICY_URL="${RADAR_POLICY_URL:-http://127.0.0.1:8787/api/freqtrade/radar-policy}"
WATCH_STATUS="${WATCH_STATUS:-/var/log/coinmaster/freqtrade-night-watch-status.json}"
MAX_WATCH_AGE_SEC="${MAX_WATCH_AGE_SEC:-900}"
MAX_RADAR_AGE_SEC="${MAX_RADAR_AGE_SEC:-900}"

pass=0
fail=0

ok() { pass=$((pass + 1)); printf '  ✓ %s\n' "$*"; }
bad() { fail=$((fail + 1)); printf '  ✗ %s\n' "$*" >&2; }

json_field() {
  python3 - "$1" "$2" <<'PY'
import json, sys
path = sys.argv[1].split('.')
data = json.loads(sys.argv[2])
for part in path:
    if isinstance(data, dict):
        data = data.get(part)
    else:
        data = None
print('' if data is None else data)
PY
}

printf '\n── CoinMaster availability smoke ──\n'

for unit in "$APP_SERVICE" "$FREQTRADE_SERVICE" "$DATASET_TIMER"; do
  if systemctl is-enabled "$unit" >/dev/null 2>&1; then ok "$unit enabled"; else bad "$unit not enabled"; fi
  if systemctl is-active "$unit" >/dev/null 2>&1; then ok "$unit active"; else bad "$unit not active"; fi
done

restart_policy="$(docker inspect coinmaster-freqtrade --format '{{.HostConfig.RestartPolicy.Name}}' 2>/dev/null || true)"
if [[ "$restart_policy" == "unless-stopped" || "$restart_policy" == "always" ]]; then
  ok "coinmaster-freqtrade Docker restart policy = $restart_policy"
else
  bad "coinmaster-freqtrade Docker restart policy is '$restart_policy'"
fi

if curl -fsS --max-time 5 "$APP_HEALTH_URL" | grep -q '"ok":true'; then
  ok "CoinMaster app /api/health ok"
else
  bad "CoinMaster app /api/health failed"
fi

python3 - <<'PY'
import base64, json, sys, urllib.request
from pathlib import Path
cfg = {}
def merge(left, right):
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(left.get(key), dict):
            merge(left[key], value)
        else:
            left[key] = value
root = Path('/opt/coinmaster/freqtrade/user_data')
for name in ('config.example.json', 'config.private.json'):
    path = root / name
    if path.exists():
        merge(cfg, json.loads(path.read_text()))
api = cfg.get('api_server', {})
headers = {}
if api.get('username') or api.get('password'):
    headers['Authorization'] = 'Basic ' + base64.b64encode(f"{api.get('username','')}:{api.get('password','')}".encode()).decode()

def req(ep):
    r = urllib.request.Request('http://127.0.0.1:8080/api/v1' + ep, headers=headers)
    with urllib.request.urlopen(r, timeout=8) as response:
        return json.load(response)
show = req('/show_config')
locks = req('/locks')
status = req('/status')
print(json.dumps({
    'dry_run': show.get('dry_run'),
    'state': show.get('state'),
    'runmode': show.get('runmode'),
    'exchange': show.get('exchange'),
    'strategy': show.get('strategy'),
    'open_trades': len(status) if isinstance(status, list) else None,
    'locks': locks.get('lock_count'),
}))
if show.get('dry_run') is not True or show.get('state') != 'running':
    sys.exit(1)
PY
if [[ "$?" -eq 0 ]]; then ok "Freqtrade API dry_run/running ok"; else bad "Freqtrade API dry_run/running failed"; fi

radar_json="$(curl -fsS --max-time 8 "$RADAR_POLICY_URL" || true)"
if [[ -n "$radar_json" ]]; then
  if RADAR_JSON="$radar_json" MAX_RADAR_AGE_SEC="$MAX_RADAR_AGE_SEC" python3 - <<'PY'
import json, os, sys
from datetime import datetime, timezone
payload = json.loads(os.environ['RADAR_JSON'])
disk = payload.get('disk') or {}
updated = disk.get('updated_at')
valid_until = disk.get('valid_until')
if not updated or not valid_until:
    sys.exit(1)
updated_dt = datetime.fromisoformat(updated.replace('Z', '+00:00')).astimezone(timezone.utc)
valid_dt = datetime.fromisoformat(valid_until.replace('Z', '+00:00')).astimezone(timezone.utc)
age = (datetime.now(timezone.utc) - updated_dt).total_seconds()
print(json.dumps({'age_sec': round(age, 1), 'valid_until': valid_until, 'pairs': len(disk.get('pairs') or {})}))
if age > int(os.environ['MAX_RADAR_AGE_SEC']) or valid_dt <= datetime.now(timezone.utc):
    sys.exit(1)
PY
  then ok "Radar policy fresh"; else bad "Radar policy stale/invalid"; fi
else
  bad "Radar policy endpoint failed"
fi

if [[ -f "$WATCH_STATUS" ]]; then
  if WATCH_STATUS="$WATCH_STATUS" MAX_WATCH_AGE_SEC="$MAX_WATCH_AGE_SEC" python3 - <<'PY'
import json, os, sys
from datetime import datetime, timezone
p = os.environ['WATCH_STATUS']
data = json.load(open(p))
ts = datetime.fromisoformat(data['ts'].replace('Z', '+00:00')).astimezone(timezone.utc)
age = (datetime.now(timezone.utc) - ts).total_seconds()
print(json.dumps({'watch_age_sec': round(age, 1), 'ok': data.get('ok'), 'actions': data.get('actions'), 'errors': data.get('errors')}))
if age > int(os.environ['MAX_WATCH_AGE_SEC']) or data.get('ok') is not True:
    sys.exit(1)
PY
  then ok "watchdog status fresh/ok"; else bad "watchdog status stale/not ok"; fi
else
  bad "watchdog status file missing"
fi

printf '\nTOTAL: %d | PASSED: %d | FAILED: %d\n' "$((pass + fail))" "$pass" "$fail"
if [[ "$fail" -gt 0 ]]; then exit 1; fi
