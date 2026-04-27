#!/usr/bin/env bash
set -euo pipefail

# CoinMaster Freqtrade night watch
# Goal: keep the overnight dry-run/backtest deployment observable and prevent
# silent stalls. This never switches live trading on; it only verifies dry-run,
# restarts the Freqtrade dry-run service if the container/API is unavailable,
# starts the trader when config says dry_run=true, and records audit evidence.

APP_DIR="${APP_DIR:-/opt/coinmaster}"
FREQTRADE_DIR="$APP_DIR/freqtrade"
LOG_DIR="${LOG_DIR:-/var/log/coinmaster}"
LOG_FILE="$LOG_DIR/freqtrade-night-watch.log"
STATUS_FILE="$LOG_DIR/freqtrade-night-watch-status.json"
mkdir -p "$LOG_DIR"

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*" | tee -a "$LOG_FILE"
}

cd "$FREQTRADE_DIR"

if ! docker compose -f docker-compose.yml -f docker-compose.prod.yml ps --status running freqtrade >/dev/null 2>&1; then
  log "freqtrade container not running; restarting coinmaster-freqtrade dry-run service"
  systemctl restart coinmaster-freqtrade || true
  sleep 10
fi

python3 - <<'PY' >>"/var/log/coinmaster/freqtrade-night-watch.log" 2>&1
import base64
import json
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

base = 'http://127.0.0.1:8080/api/v1'
status_path = Path('/var/log/coinmaster/freqtrade-night-watch-status.json')
config_path = Path('/opt/coinmaster/freqtrade/user_data/config.private.json')
result = {
    'ts': datetime.now(timezone.utc).isoformat(),
    'ok': False,
    'dry_run': None,
    'state': None,
    'open_trades': None,
    'locks': None,
    'actions': [],
    'errors': [],
}

def req(path, method='GET', token=None, basic=None, timeout=10):
    r = urllib.request.Request(base + path, method=method)
    if token:
        r.add_header('Authorization', 'Bearer ' + token)
    if basic:
        r.add_header('Authorization', 'Basic ' + basic)
    return urllib.request.urlopen(r, timeout=timeout).read().decode()

try:
    cfg = json.loads(config_path.read_text())
    user = cfg['api_server']['username']
    pwd = cfg['api_server']['password']
    basic = base64.b64encode(f'{user}:{pwd}'.encode()).decode()

    token = None
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
        result['actions'].append('api_start')
        req('/start', method='POST', token=token)
        time.sleep(5)
        show = json.loads(req('/show_config', token=token))
        result['state'] = show.get('state')

    status = json.loads(req('/status', token=token))
    locks = json.loads(req('/locks', token=token))
    result['open_trades'] = len(status) if isinstance(status, list) else None
    result['locks'] = locks.get('lock_count')
    result['ok'] = result['dry_run'] is True and result['state'] == 'running'

    logs = subprocess.run(
        ['docker', 'compose', '-f', 'docker-compose.yml', '-f', 'docker-compose.prod.yml', 'logs', '--since=35m', 'freqtrade'],
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

except Exception as exc:
    result['errors'].append(repr(exc))

status_path.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
PY

log "night watch completed: $(cat "$STATUS_FILE" | tr '\n' ' ' | cut -c1-700)"
