#!/usr/bin/env bash
set -euo pipefail

# Safe production deploy for Coinmaster + native Freqtrade Stage 1.
# - Never rsync/delete into /opt/coinmaster root directly
# - Sync only known application/runtime trees
# - Preserve Freqtrade secrets, runtime data, backtest/hyperopt artifacts, DBs
# - Keep backup + rollback on failed smoke checks

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${TARGET_DIR:-/opt/coinmaster}"
SERVICE="${SERVICE:-coinmaster.service}"
FREQTRADE_SERVICE="${FREQTRADE_SERVICE:-coinmaster-freqtrade.service}"
OWNER_USER="${OWNER_USER:-coinmaster}"
OWNER_GROUP="${OWNER_GROUP:-coinmaster}"
APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-8787}"
DEPLOY_LOCK="${DEPLOY_LOCK:-/run/coinmaster-deploy.lock}"

BACKUP_ROOT="$TARGET_DIR/.deploy-backups"
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$TS"

log() { printf '[deploy-safe] %s\n' "$*"; }
cleanup_deploy_lock() { rm -f "$DEPLOY_LOCK"; }
mkdir -p "$(dirname "$DEPLOY_LOCK")"
printf '%s\n' "$(date -Is) pid=$$" > "$DEPLOY_LOCK"
trap cleanup_deploy_lock EXIT

move_freqtrade_sqlite_files() {
  local source_dir="$1"
  local dest_dir="$2"
  mkdir -p "$dest_dir"
  shopt -s nullglob
  local sqlite_file
  for sqlite_file in "$source_dir"/*.sqlite "$source_dir"/*.sqlite-*; do
    [[ -e "$sqlite_file" ]] || continue
    mv "$sqlite_file" "$dest_dir/$(basename "$sqlite_file")"
  done
  shopt -u nullglob
}

preserve_freqtrade_runtime() {
  local preserve_dir="$1"
  rm -rf "$preserve_dir"
  mkdir -p "$preserve_dir"
  if [[ -d "$TARGET_DIR/freqtrade/user_data" ]]; then
    for item in config.private.json data runtime backtest_results hyperopt_results; do
      if [[ -e "$TARGET_DIR/freqtrade/user_data/$item" ]]; then
        mkdir -p "$preserve_dir/user_data"
        mv "$TARGET_DIR/freqtrade/user_data/$item" "$preserve_dir/user_data/$item"
      fi
    done
    move_freqtrade_sqlite_files "$TARGET_DIR/freqtrade/user_data" "$preserve_dir/user_data"
  fi
}

restore_freqtrade_runtime() {
  local preserve_dir="$1"
  if [[ -d "$preserve_dir/user_data" ]]; then
    mkdir -p "$TARGET_DIR/freqtrade/user_data"
    for item in config.private.json data runtime backtest_results hyperopt_results; do
      if [[ -e "$preserve_dir/user_data/$item" && ! -e "$TARGET_DIR/freqtrade/user_data/$item" ]]; then
        mv "$preserve_dir/user_data/$item" "$TARGET_DIR/freqtrade/user_data/$item"
      fi
    done
    move_freqtrade_sqlite_files "$preserve_dir/user_data" "$TARGET_DIR/freqtrade/user_data"
  fi
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

for cmd in npm rsync curl systemctl cmp ss diff; do
  require_cmd "$cmd"
done

log "Running typecheck gate"
cd "$APP_DIR"
SOURCE_COMMIT="$(git rev-parse HEAD)"
GIT_ROOT="$(git rev-parse --show-toplevel)"
APP_REL="$(realpath --relative-to="$GIT_ROOT" "$APP_DIR")"
PREVIOUS_COMMIT="$(cat "$TARGET_DIR/.deploy-source-commit" 2>/dev/null || true)"
FREQTRADE_TREE_CHANGED=1
if [[ -n "$PREVIOUS_COMMIT" ]] && git cat-file -e "$PREVIOUS_COMMIT^{commit}" 2>/dev/null; then
  if git diff --quiet "$PREVIOUS_COMMIT" "$SOURCE_COMMIT" -- "$APP_REL/freqtrade"; then
    FREQTRADE_TREE_CHANGED=0
  fi
fi
npm run check >/tmp/coinmaster-deploy-check.log 2>&1 || {
  cat /tmp/coinmaster-deploy-check.log >&2
  exit 1
}

log "Building web assets"
npm run build >/tmp/coinmaster-deploy-build.log 2>&1 || {
  cat /tmp/coinmaster-deploy-build.log >&2
  exit 1
}

DEPENDENCY_DRIFT=0
if [[ -f "$TARGET_DIR/package-lock.json" ]]; then
  if ! LOCK_SRC="$APP_DIR/package-lock.json" LOCK_TGT="$TARGET_DIR/package-lock.json" python3 - <<'PY'
import json, sys, os
try:
    with open(os.environ["LOCK_SRC"]) as f: src = json.load(f)
    with open(os.environ["LOCK_TGT"]) as f: tgt = json.load(f)
    src_root = src.get("packages", {}).get("", {})
    tgt_root = tgt.get("packages", {}).get("", {})
    if src_root.get("dependencies") != tgt_root.get("dependencies") or src_root.get("devDependencies") != tgt_root.get("devDependencies"):
        print("DEPENDENCY_DRIFT", file=sys.stderr)
        sys.exit(1)
except Exception as e:
    print(f"lockfile_parse_error: {e}", file=sys.stderr)
    sys.exit(1)
PY
  then
    DEPENDENCY_DRIFT=1
    log "Dependency drift detected; production npm install will run after package files are staged"
  fi
fi

log "Preparing backup at $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
if [[ -d "$TARGET_DIR/src" ]]; then rsync -a "$TARGET_DIR/src/" "$BACKUP_DIR/src/"; fi
if [[ -d "$TARGET_DIR/dist" ]]; then rsync -a "$TARGET_DIR/dist/" "$BACKUP_DIR/dist/"; fi
if [[ -d "$TARGET_DIR/dist-custom" ]]; then rsync -a "$TARGET_DIR/dist-custom/" "$BACKUP_DIR/dist-custom/"; fi
if [[ -d "$TARGET_DIR/docs" ]]; then rsync -a "$TARGET_DIR/docs/" "$BACKUP_DIR/docs/"; fi
if [[ -d "$TARGET_DIR/scripts" ]]; then rsync -a "$TARGET_DIR/scripts/" "$BACKUP_DIR/scripts/"; fi
if [[ -d "$TARGET_DIR/freqtrade" ]]; then
  rsync -a \
    --exclude 'user_data/config.private.json' \
    --exclude 'user_data/data/' \
    --exclude 'user_data/runtime/' \
    --exclude 'user_data/backtest_results/' \
    --exclude 'user_data/hyperopt_results/' \
    --exclude 'user_data/*.sqlite' \
    --exclude 'user_data/*.sqlite-*' \
    --exclude 'user_data/strategies/__pycache__/' \
    "$TARGET_DIR/freqtrade/" "$BACKUP_DIR/freqtrade/"
fi
if [[ -f "$TARGET_DIR/package.json" ]]; then cp "$TARGET_DIR/package.json" "$BACKUP_DIR/package.json"; fi
if [[ -f "$TARGET_DIR/package-lock.json" ]]; then cp "$TARGET_DIR/package-lock.json" "$BACKUP_DIR/package-lock.json"; fi

log "Syncing staged trees"
rm -rf "$TARGET_DIR/src.new" "$TARGET_DIR/dist.new" "$TARGET_DIR/dist-custom.new" "$TARGET_DIR/docs.new" "$TARGET_DIR/scripts.new" "$TARGET_DIR/freqtrade.new"
mkdir -p "$TARGET_DIR/src.new" "$TARGET_DIR/dist.new" "$TARGET_DIR/dist-custom.new" "$TARGET_DIR/docs.new" "$TARGET_DIR/scripts.new" "$TARGET_DIR/freqtrade.new"
rsync -a --delete "$APP_DIR/src/" "$TARGET_DIR/src.new/"
rsync -a --delete "$APP_DIR/dist/" "$TARGET_DIR/dist.new/"
rsync -a --delete "$APP_DIR/dist-custom/" "$TARGET_DIR/dist-custom.new/"
rsync -a --delete "$APP_DIR/docs/" "$TARGET_DIR/docs.new/"
rsync -a --delete "$APP_DIR/scripts/" "$TARGET_DIR/scripts.new/"
rsync -a --delete \
  --exclude 'user_data/config.private.json' \
  --exclude 'user_data/data/' \
  --exclude 'user_data/runtime/' \
  --exclude 'user_data/backtest_results/' \
  --exclude 'user_data/hyperopt_results/' \
  --exclude 'user_data/*.sqlite' \
  --exclude 'user_data/*.sqlite-*' \
  --exclude 'user_data/strategies/__pycache__/' \
  "$APP_DIR/freqtrade/" "$TARGET_DIR/freqtrade.new/"
FREQTRADE_DEPLOY_TREE_CHANGED="$FREQTRADE_TREE_CHANGED"
if [[ -d "$TARGET_DIR/freqtrade" ]]; then
  if ! diff -qr \
    --exclude 'config.private.json' \
    --exclude 'data' \
    --exclude 'runtime' \
    --exclude 'backtest_results' \
    --exclude 'hyperopt_results' \
    --exclude '*.sqlite' \
    --exclude '*.sqlite-*' \
    --exclude '__pycache__' \
    "$TARGET_DIR/freqtrade" "$TARGET_DIR/freqtrade.new" >/dev/null; then
    FREQTRADE_DEPLOY_TREE_CHANGED=1
  fi
else
  FREQTRADE_DEPLOY_TREE_CHANGED=1
fi
install -o "$OWNER_USER" -g "$OWNER_GROUP" -m 0644 "$APP_DIR/package.json" "$TARGET_DIR/package.json"
install -o "$OWNER_USER" -g "$OWNER_GROUP" -m 0644 "$APP_DIR/package-lock.json" "$TARGET_DIR/package-lock.json"
chown -R "$OWNER_USER:$OWNER_GROUP" "$TARGET_DIR/src.new" "$TARGET_DIR/dist.new" "$TARGET_DIR/dist-custom.new" "$TARGET_DIR/docs.new" "$TARGET_DIR/scripts.new" "$TARGET_DIR/freqtrade.new"

if [[ "$DEPENDENCY_DRIFT" -eq 1 ]]; then
  log "Installing production dependencies from staged lockfile"
  if ! npm install --prefix "$TARGET_DIR" --no-audit --no-fund >/tmp/coinmaster-deploy-npm-install.log 2>&1; then
    cat /tmp/coinmaster-deploy-npm-install.log >&2
    if [[ -f "$BACKUP_DIR/package.json" ]]; then install -o "$OWNER_USER" -g "$OWNER_GROUP" -m 0644 "$BACKUP_DIR/package.json" "$TARGET_DIR/package.json"; fi
    if [[ -f "$BACKUP_DIR/package-lock.json" ]]; then install -o "$OWNER_USER" -g "$OWNER_GROUP" -m 0644 "$BACKUP_DIR/package-lock.json" "$TARGET_DIR/package-lock.json"; fi
    exit 1
  fi
  chown -R "$OWNER_USER:$OWNER_GROUP" "$TARGET_DIR/node_modules" "$TARGET_DIR/package-lock.json" "$TARGET_DIR/package.json"
fi

if [[ ! -f "$TARGET_DIR/dist.new/index.html" ]]; then
  echo "dist.new/index.html missing after build/sync" >&2
  exit 1
fi

log "Atomic swap application + Freqtrade deploy trees"
rm -rf "$TARGET_DIR/src.prev" "$TARGET_DIR/dist.prev" "$TARGET_DIR/dist-custom.prev" "$TARGET_DIR/docs.prev" "$TARGET_DIR/scripts.prev" "$TARGET_DIR/freqtrade.prev"
if [[ -d "$TARGET_DIR/src" ]]; then mv "$TARGET_DIR/src" "$TARGET_DIR/src.prev"; fi
if [[ -d "$TARGET_DIR/dist" ]]; then mv "$TARGET_DIR/dist" "$TARGET_DIR/dist.prev"; fi
if [[ -d "$TARGET_DIR/dist-custom" ]]; then mv "$TARGET_DIR/dist-custom" "$TARGET_DIR/dist-custom.prev"; fi
if [[ -d "$TARGET_DIR/docs" ]]; then mv "$TARGET_DIR/docs" "$TARGET_DIR/docs.prev"; fi
if [[ -d "$TARGET_DIR/scripts" ]]; then mv "$TARGET_DIR/scripts" "$TARGET_DIR/scripts.prev"; fi
if [[ -d "$TARGET_DIR/freqtrade" ]]; then mv "$TARGET_DIR/freqtrade" "$TARGET_DIR/freqtrade.prev"; fi
mv "$TARGET_DIR/src.new" "$TARGET_DIR/src"
mv "$TARGET_DIR/dist.new" "$TARGET_DIR/dist"
mv "$TARGET_DIR/dist-custom.new" "$TARGET_DIR/dist-custom"
mv "$TARGET_DIR/docs.new" "$TARGET_DIR/docs"
mv "$TARGET_DIR/scripts.new" "$TARGET_DIR/scripts"
mv "$TARGET_DIR/freqtrade.new" "$TARGET_DIR/freqtrade"

if [[ -d "$TARGET_DIR/freqtrade.prev/user_data" ]]; then
  log "Restoring protected Freqtrade runtime files"
  mkdir -p "$TARGET_DIR/freqtrade/user_data"
  for item in config.private.json data runtime backtest_results hyperopt_results; do
    if [[ -e "$TARGET_DIR/freqtrade.prev/user_data/$item" && ! -e "$TARGET_DIR/freqtrade/user_data/$item" ]]; then
      mv "$TARGET_DIR/freqtrade.prev/user_data/$item" "$TARGET_DIR/freqtrade/user_data/$item"
    fi
  done
  move_freqtrade_sqlite_files "$TARGET_DIR/freqtrade.prev/user_data" "$TARGET_DIR/freqtrade/user_data"
fi

log "Stopping $SERVICE for clean port handoff"
systemctl stop "$SERVICE"

if ss -ltnp "( sport = :$APP_PORT )" | tail -n +2 | grep -q LISTEN; then
  echo "Port $APP_PORT is still busy after stopping $SERVICE; refusing deploy." >&2
  ss -ltnp "( sport = :$APP_PORT )" >&2 || true
  exit 1
fi

log "Starting $SERVICE"
systemctl start "$SERVICE"

log "Waiting for active state"
for i in {1..20}; do
  state="$(systemctl is-active "$SERVICE" || true)"
  [[ "$state" == "active" ]] && break
  sleep 1
done

if [[ "$(systemctl is-active "$SERVICE" || true)" != "active" ]]; then
  echo "Service failed to become active, rolling back" >&2
  FREQTRADE_PRESERVE="$BACKUP_DIR/freqtrade-runtime-preserve-service-fail"
  preserve_freqtrade_runtime "$FREQTRADE_PRESERVE"
  rm -rf "$TARGET_DIR/src" "$TARGET_DIR/dist"
  rm -rf "$TARGET_DIR/dist-custom" "$TARGET_DIR/docs" "$TARGET_DIR/scripts" "$TARGET_DIR/freqtrade"
  if [[ -d "$BACKUP_DIR/src" ]]; then rsync -a "$BACKUP_DIR/src/" "$TARGET_DIR/src/"; fi
  if [[ -d "$BACKUP_DIR/dist" ]]; then rsync -a "$BACKUP_DIR/dist/" "$TARGET_DIR/dist/"; fi
  if [[ -d "$BACKUP_DIR/dist-custom" ]]; then rsync -a "$BACKUP_DIR/dist-custom/" "$TARGET_DIR/dist-custom/"; fi
  if [[ -d "$BACKUP_DIR/docs" ]]; then rsync -a "$BACKUP_DIR/docs/" "$TARGET_DIR/docs/"; fi
  if [[ -d "$BACKUP_DIR/scripts" ]]; then rsync -a "$BACKUP_DIR/scripts/" "$TARGET_DIR/scripts/"; fi
  if [[ -d "$BACKUP_DIR/freqtrade" ]]; then rsync -a "$BACKUP_DIR/freqtrade/" "$TARGET_DIR/freqtrade/"; fi
  restore_freqtrade_runtime "$FREQTRADE_PRESERVE"
  if [[ -f "$BACKUP_DIR/package.json" ]]; then install -o "$OWNER_USER" -g "$OWNER_GROUP" -m 0644 "$BACKUP_DIR/package.json" "$TARGET_DIR/package.json"; fi
  if [[ -f "$BACKUP_DIR/package-lock.json" ]]; then install -o "$OWNER_USER" -g "$OWNER_GROUP" -m 0644 "$BACKUP_DIR/package-lock.json" "$TARGET_DIR/package-lock.json"; fi
  chown -R "$OWNER_USER:$OWNER_GROUP" "$TARGET_DIR/src" "$TARGET_DIR/dist" "$TARGET_DIR/dist-custom" "$TARGET_DIR/docs" "$TARGET_DIR/scripts" "$TARGET_DIR/freqtrade" || true
  systemctl restart "$SERVICE" || true
  exit 1
fi

log "Running smoke checks"
SMOKE_OK=0
for i in {1..25}; do
  HEALTH="$(curl -fsS --max-time 2 http://$APP_HOST:$APP_PORT/api/health || true)"
  ROOT_HTML="$(curl -fsS --max-time 2 http://$APP_HOST:$APP_PORT/ || true)"
  if [[ "$HEALTH" == *'"ok":true'* ]] && [[ "$ROOT_HTML" == *'<div id="root"></div>'* ]]; then
    SMOKE_OK=1
    break
  fi
  sleep 1
done

if [[ "$SMOKE_OK" -ne 1 ]]; then
  echo "Smoke checks failed, rolling back" >&2
  FREQTRADE_PRESERVE="$BACKUP_DIR/freqtrade-runtime-preserve-smoke-fail"
  preserve_freqtrade_runtime "$FREQTRADE_PRESERVE"
  rm -rf "$TARGET_DIR/src" "$TARGET_DIR/dist"
  rm -rf "$TARGET_DIR/dist-custom" "$TARGET_DIR/docs" "$TARGET_DIR/scripts" "$TARGET_DIR/freqtrade"
  if [[ -d "$BACKUP_DIR/src" ]]; then rsync -a "$BACKUP_DIR/src/" "$TARGET_DIR/src/"; fi
  if [[ -d "$BACKUP_DIR/dist" ]]; then rsync -a "$BACKUP_DIR/dist/" "$TARGET_DIR/dist/"; fi
  if [[ -d "$BACKUP_DIR/dist-custom" ]]; then rsync -a "$BACKUP_DIR/dist-custom/" "$TARGET_DIR/dist-custom/"; fi
  if [[ -d "$BACKUP_DIR/docs" ]]; then rsync -a "$BACKUP_DIR/docs/" "$TARGET_DIR/docs/"; fi
  if [[ -d "$BACKUP_DIR/scripts" ]]; then rsync -a "$BACKUP_DIR/scripts/" "$TARGET_DIR/scripts/"; fi
  if [[ -d "$BACKUP_DIR/freqtrade" ]]; then rsync -a "$BACKUP_DIR/freqtrade/" "$TARGET_DIR/freqtrade/"; fi
  restore_freqtrade_runtime "$FREQTRADE_PRESERVE"
  if [[ -f "$BACKUP_DIR/package.json" ]]; then install -o "$OWNER_USER" -g "$OWNER_GROUP" -m 0644 "$BACKUP_DIR/package.json" "$TARGET_DIR/package.json"; fi
  if [[ -f "$BACKUP_DIR/package-lock.json" ]]; then install -o "$OWNER_USER" -g "$OWNER_GROUP" -m 0644 "$BACKUP_DIR/package-lock.json" "$TARGET_DIR/package-lock.json"; fi
  chown -R "$OWNER_USER:$OWNER_GROUP" "$TARGET_DIR/src" "$TARGET_DIR/dist" "$TARGET_DIR/dist-custom" "$TARGET_DIR/docs" "$TARGET_DIR/scripts" "$TARGET_DIR/freqtrade" || true
  systemctl restart "$SERVICE" || true
  exit 1
fi

if [[ -d /etc/cron.d && -x "$TARGET_DIR/scripts/freqtrade-night-watch.sh" ]]; then
  log "Installing CoinMaster 24/7 stack watchdog cron"
  cat >/etc/cron.d/coinmaster-freqtrade-night-watch <<'EOF'
# CoinMaster 24/7 stack watch
# Every 5 minutes verify/recover companion app health, native Freqtrade dry-run
# API/container, dry_run/running state, locks/open trades, and Radar policy
# freshness. This watchdog never enables live trading; it refuses trading actions
# unless Freqtrade config/API confirm dry_run=true.
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
*/5 * * * * root /opt/coinmaster/scripts/freqtrade-night-watch.sh >/dev/null 2>&1
EOF
  chmod 0644 /etc/cron.d/coinmaster-freqtrade-night-watch
fi

if [[ "$FREQTRADE_DEPLOY_TREE_CHANGED" -eq 1 ]] && systemctl list-unit-files "$FREQTRADE_SERVICE" >/dev/null 2>&1; then
  log "Freqtrade tree changed; restarting $FREQTRADE_SERVICE so strategy/config code is loaded"
  systemctl restart "$FREQTRADE_SERVICE"
  log "Waiting for Freqtrade API after restart"
  FREQTRADE_API_OK=0
  for i in {1..90}; do
    if curl -fsS --max-time 3 http://127.0.0.1:8080/api/v1/ping >/dev/null 2>&1; then
      FREQTRADE_API_OK=1
      break
    fi
    sleep 1
  done
  if [[ "$FREQTRADE_API_OK" -ne 1 ]]; then
    echo "Freqtrade API did not become reachable after $FREQTRADE_SERVICE restart" >&2
    exit 1
  fi
  TARGET_DIR="$TARGET_DIR" python3 - <<'PY'
import base64, json, os, urllib.request
from pathlib import Path
config = {}
def merge(left, right):
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(left.get(key), dict):
            merge(left[key], value)
        else:
            left[key] = value
root = Path(os.environ['TARGET_DIR']) / 'freqtrade' / 'user_data'
for name in ('config.example.json', 'config.private.json'):
    path = root / name
    if path.exists():
        with path.open() as handle:
            merge(config, json.load(handle))
api = config.get('api_server', {})
headers = {}
if api.get('username') or api.get('password'):
    token = base64.b64encode(f"{api.get('username','')}:{api.get('password','')}".encode()).decode()
    headers['Authorization'] = f'Basic {token}'
base = 'http://127.0.0.1:8080/api/v1'
def request(endpoint, method='GET'):
    req = urllib.request.Request(f'{base}{endpoint}', headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.load(response)
show = request('/show_config')
if show.get('dry_run') is True and show.get('state') != 'running':
    request('/start', method='POST')
    show = request('/show_config')
if show.get('dry_run') is not True or show.get('state') != 'running':
    raise SystemExit(f"unexpected Freqtrade post-restart state: dry_run={show.get('dry_run')} state={show.get('state')}")
PY
fi

if systemctl list-unit-files "$FREQTRADE_SERVICE" >/dev/null 2>&1; then
  log "Verifying Freqtrade dry-run trader state"
  FREQTRADE_API_OK=0
  for i in {1..90}; do
    if curl -fsS --max-time 3 http://127.0.0.1:8080/api/v1/ping >/dev/null 2>&1; then
      FREQTRADE_API_OK=1
      break
    fi
    sleep 1
  done
  if [[ "$FREQTRADE_API_OK" -ne 1 ]]; then
    echo "Freqtrade API did not become reachable for final state check" >&2
    exit 1
  fi
  TARGET_DIR="$TARGET_DIR" python3 - <<'PY'
import base64, json, os, time, urllib.request
from pathlib import Path
config = {}
def merge(left, right):
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(left.get(key), dict):
            merge(left[key], value)
        else:
            left[key] = value
root = Path(os.environ['TARGET_DIR']) / 'freqtrade' / 'user_data'
for name in ('config.example.json', 'config.private.json'):
    path = root / name
    if path.exists():
        with path.open() as handle:
            merge(config, json.load(handle))
api = config.get('api_server', {})
headers = {}
if api.get('username') or api.get('password'):
    token = base64.b64encode(f"{api.get('username','')}:{api.get('password','')}".encode()).decode()
    headers['Authorization'] = f'Basic {token}'
base = 'http://127.0.0.1:8080/api/v1'
def request(endpoint, method='GET'):
    req = urllib.request.Request(f'{base}{endpoint}', headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=8) as response:
        return json.load(response)
show = request('/show_config')
if show.get('dry_run') is True and show.get('state') != 'running':
    request('/start', method='POST')
    time.sleep(2)
    show = request('/show_config')
if show.get('dry_run') is not True or show.get('state') != 'running':
    raise SystemExit(f"unexpected Freqtrade final state: dry_run={show.get('dry_run')} state={show.get('state')}")
PY
fi

printf '%s\n' "$SOURCE_COMMIT" > "$TARGET_DIR/.deploy-source-commit.new"
chown "$OWNER_USER:$OWNER_GROUP" "$TARGET_DIR/.deploy-source-commit.new"
mv "$TARGET_DIR/.deploy-source-commit.new" "$TARGET_DIR/.deploy-source-commit"

log "Deploy successful"
