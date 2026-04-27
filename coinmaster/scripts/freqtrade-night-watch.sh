#!/usr/bin/env bash
set -euo pipefail

# CoinMaster 24/7 stack watch
# Goal: keep the native Freqtrade dry-run stack observable and self-healing.
# This never switches live trading on; it only:
# - verifies/restarts the CoinMaster companion app if /api/health is down;
# - verifies/restarts the Freqtrade dry-run service if container/API is down;
# - starts the Freqtrade trader only when config/API confirm dry_run=true;
# - checks Radar policy freshness/exporter health;
# - records evidence to /var/log/coinmaster/freqtrade-night-watch-status.json.

APP_DIR="${APP_DIR:-/opt/coinmaster}"
FREQTRADE_DIR="$APP_DIR/freqtrade"
LOG_DIR="${LOG_DIR:-/var/log/coinmaster}"
LOG_FILE="$LOG_DIR/freqtrade-night-watch.log"
STATUS_FILE="$LOG_DIR/freqtrade-night-watch-status.json"
APP_HEALTH_URL="${APP_HEALTH_URL:-http://127.0.0.1:8787/api/health}"
APP_RADAR_URL="${APP_RADAR_URL:-http://127.0.0.1:8787/api/freqtrade/radar-policy}"
APP_SERVICE="${APP_SERVICE:-coinmaster.service}"
FREQTRADE_SERVICE="${FREQTRADE_SERVICE:-coinmaster-freqtrade.service}"
RADAR_POLICY_MAX_STALE_SEC="${RADAR_POLICY_MAX_STALE_SEC:-900}"
mkdir -p "$LOG_DIR"

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*" | tee -a "$LOG_FILE"
}

wait_for_http() {
  local url="$1"
  local attempts="${2:-20}"
  local delay="${3:-2}"
  local i
  for ((i=1; i<=attempts; i++)); do
    if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

if ! wait_for_http "$APP_HEALTH_URL" 2 1; then
  log "CoinMaster app health is down; restarting $APP_SERVICE"
  systemctl restart "$APP_SERVICE" || true
  wait_for_http "$APP_HEALTH_URL" 20 2 || true
fi

cd "$FREQTRADE_DIR"

if ! docker compose -f docker-compose.yml -f docker-compose.prod.yml ps --status running freqtrade >/dev/null 2>&1; then
  log "Freqtrade container not running; restarting $FREQTRADE_SERVICE dry-run service"
  systemctl restart "$FREQTRADE_SERVICE" || true
  sleep 10
fi

python3 - <<'PY' >>"/var/log/coinmaster/freqtrade-night-watch.log" 2>&1
import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

base = 'http://127.0.0.1:8080/api/v1'
app_health_url = os.environ.get('APP_HEALTH_URL', 'http://127.0.0.1:8787/api/health')
app_radar_url = os.environ.get('APP_RADAR_URL', 'http://127.0.0.1:8787/api/freqtrade/radar-policy')
radar_policy_max_stale_sec = int(os.environ.get('RADAR_POLICY_MAX_STALE_SEC', '900'))
status_path = Path('/var/log/coinmaster/freqtrade-night-watch-status.json')
config_dir = Path('/opt/coinmaster/freqtrade/user_data')
radar_policy_path = Path('/var/lib/coinmaster/freqtrade/radar_policy.json')
result = {
    'ts': datetime.now(timezone.utc).isoformat(),
    'ok': False,
    'app_health': None,
    'radar_policy': None,
    'radar_policy_age_sec': None,
    'radar_policy_valid_until': None,
    'dry_run': None,
    'state': None,
    'open_trades': None,
    'locks': None,
    'actions': [],
    'errors': [],
}

def merge(left, right):
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(left.get(key), dict):
            merge(left[key], value)
        else:
            left[key] = value

def load_config():
    cfg = {}
    for name in ('config.example.json', 'config.private.json'):
        path = config_dir / name
        if path.exists():
            merge(cfg, json.loads(path.read_text()))
    return cfg

def http_json(url, timeout=8):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode())

def req(path, method='GET', token=None, basic=None, timeout=10):
    r = urllib.request.Request(base + path, method=method)
    if token:
        r.add_header('Authorization', 'Bearer ' + token)
    if basic:
        r.add_header('Authorization', 'Basic ' + basic)
    return urllib.request.urlopen(r, timeout=timeout).read().decode()

try:
    try:
        health = http_json(app_health_url)
        result['app_health'] = 'ok' if health.get('ok') is True else 'bad_response'
    except Exception as exc:
        result['app_health'] = 'down'
        result['errors'].append(f'app_health_failed: {exc!r}')

    try:
        radar_response = http_json(app_radar_url)
        disk = radar_response.get('disk') if isinstance(radar_response, dict) else None
        if not isinstance(disk, dict) and radar_policy_path.exists():
            disk = json.loads(radar_policy_path.read_text())
        if isinstance(disk, dict):
            updated = disk.get('updated_at')
            valid_until = disk.get('valid_until')
            result['radar_policy_valid_until'] = valid_until
            updated_dt = datetime.fromisoformat(str(updated).replace('Z', '+00:00')) if updated else None
            age = (datetime.now(timezone.utc) - updated_dt.astimezone(timezone.utc)).total_seconds() if updated_dt else None
            result['radar_policy_age_sec'] = round(age, 1) if age is not None else None
            valid_dt = datetime.fromisoformat(str(valid_until).replace('Z', '+00:00')) if valid_until else None
            if age is not None and age <= radar_policy_max_stale_sec and valid_dt and valid_dt.astimezone(timezone.utc) > datetime.now(timezone.utc):
                result['radar_policy'] = 'fresh'
            else:
                result['radar_policy'] = 'stale'
                result['errors'].append('radar_policy_stale_or_expired')
        else:
            result['radar_policy'] = 'missing'
            result['errors'].append('radar_policy_missing')
    except Exception as exc:
        result['radar_policy'] = 'error'
        result['errors'].append(f'radar_policy_check_failed: {exc!r}')

    cfg = load_config()
    api = cfg.get('api_server', {})
    user = api.get('username')
    pwd = api.get('password')
    if not user or not pwd:
        raise RuntimeError('api_credentials_missing')
    basic = base64.b64encode(f'{user}:{pwd}'.encode()).decode()

    token = None
    last = None
    for _ in range(10):
        try:
            token = json.loads(req('/token/login', method='POST', basic=basic, timeout=5))['access_token']
            break
        except Exception as exc:
            last = exc
            time.sleep(3)
    if not token:
        subprocess.run(['systemctl', 'restart', os.environ.get('FREQTRADE_SERVICE', 'coinmaster-freqtrade.service')], timeout=30)
        result['actions'].append('freqtrade_service_restart_api_login_failed')
        time.sleep(10)
        for _ in range(10):
            try:
                token = json.loads(req('/token/login', method='POST', basic=basic, timeout=5))['access_token']
                break
            except Exception as exc:
                last = exc
                time.sleep(3)
    if not token:
        raise RuntimeError(f'api_login_failed: {last!r}')

    show = json.loads(req('/show_config', token=token))
    result['dry_run'] = show.get('dry_run')
    result['state'] = show.get('state')

    if show.get('dry_run') is not True:
        raise RuntimeError('refusing action: Freqtrade is not in dry_run mode')

    if show.get('state') != 'running':
        result['actions'].append('freqtrade_api_start')
        req('/start', method='POST', token=token)
        time.sleep(5)
        show = json.loads(req('/show_config', token=token))
        result['state'] = show.get('state')

    status = json.loads(req('/status', token=token))
    locks = json.loads(req('/locks', token=token))
    result['open_trades'] = len(status) if isinstance(status, list) else None
    result['locks'] = locks.get('lock_count')

    logs = subprocess.run(
        ['docker', 'compose', '-f', 'docker-compose.yml', '-f', 'docker-compose.prod.yml', 'logs', '--since=10m', 'freqtrade'],
        cwd='/opt/coinmaster/freqtrade', text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30,
    ).stdout
    bad_lines = []
    for line in logs.splitlines():
        lower = line.lower()
        if any(x in lower for x in ['traceback', 'exception', 'not tradable', 'config file', 'failed with', 'timeout']):
            if 'unfilledtimeout' in lower or 'exit_timeout_count' in lower or 'uvicorn.error - info' in lower:
                continue
            bad_lines.append(line[-500:])
    if bad_lines:
        result['errors'].extend(bad_lines[-20:])

    result['ok'] = (
        result['app_health'] == 'ok'
        and result['dry_run'] is True
        and result['state'] == 'running'
        and result['radar_policy'] in {'fresh', 'missing'}
        and not [e for e in result['errors'] if not str(e).startswith('radar_policy_missing')]
    )

except Exception as exc:
    result['errors'].append(repr(exc))

status_path.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
PY

log "stack watch completed: $(cat "$STATUS_FILE" | tr '\n' ' ' | cut -c1-900)"
