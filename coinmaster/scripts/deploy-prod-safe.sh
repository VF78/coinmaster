#!/usr/bin/env bash
set -euo pipefail

# Safe production deploy for Coinmaster.
# - Never rsync/delete into /opt/coinmaster root directly
# - Sync only src/ and dist/ trees
# - Keep backup + rollback on failed smoke checks

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${TARGET_DIR:-/opt/coinmaster}"
SERVICE="${SERVICE:-coinmaster.service}"
OWNER_USER="${OWNER_USER:-coinmaster}"
OWNER_GROUP="${OWNER_GROUP:-coinmaster}"

BACKUP_ROOT="$TARGET_DIR/.deploy-backups"
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$TS"

log() { printf '[deploy-safe] %s\n' "$*"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

for cmd in npm rsync curl systemctl cmp; do
  require_cmd "$cmd"
done

log "Running typecheck gate"
cd "$APP_DIR"
SOURCE_COMMIT="$(git rev-parse HEAD)"
npm run check >/tmp/coinmaster-deploy-check.log 2>&1 || {
  cat /tmp/coinmaster-deploy-check.log >&2
  exit 1
}

log "Building web assets"
npm run build >/tmp/coinmaster-deploy-build.log 2>&1 || {
  cat /tmp/coinmaster-deploy-build.log >&2
  exit 1
}

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
    echo "Dependency drift detected between workspace and production target; run npm install / npm ci in workspace, then redeploy." >&2
    exit 1
  fi
fi

log "Preparing backup at $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
if [[ -d "$TARGET_DIR/src" ]]; then rsync -a "$TARGET_DIR/src/" "$BACKUP_DIR/src/"; fi
if [[ -d "$TARGET_DIR/dist" ]]; then rsync -a "$TARGET_DIR/dist/" "$BACKUP_DIR/dist/"; fi
if [[ -f "$TARGET_DIR/package.json" ]]; then cp "$TARGET_DIR/package.json" "$BACKUP_DIR/package.json"; fi
if [[ -f "$TARGET_DIR/package-lock.json" ]]; then cp "$TARGET_DIR/package-lock.json" "$BACKUP_DIR/package-lock.json"; fi

log "Syncing staged trees"
rm -rf "$TARGET_DIR/src.new" "$TARGET_DIR/dist.new"
mkdir -p "$TARGET_DIR/src.new" "$TARGET_DIR/dist.new"
rsync -a --delete "$APP_DIR/src/" "$TARGET_DIR/src.new/"
rsync -a --delete "$APP_DIR/dist/" "$TARGET_DIR/dist.new/"
install -o "$OWNER_USER" -g "$OWNER_GROUP" -m 0644 "$APP_DIR/package.json" "$TARGET_DIR/package.json"
install -o "$OWNER_USER" -g "$OWNER_GROUP" -m 0644 "$APP_DIR/package-lock.json" "$TARGET_DIR/package-lock.json"
chown -R "$OWNER_USER:$OWNER_GROUP" "$TARGET_DIR/src.new" "$TARGET_DIR/dist.new"

if [[ ! -f "$TARGET_DIR/dist.new/index.html" ]]; then
  echo "dist.new/index.html missing after build/sync" >&2
  exit 1
fi

log "Atomic swap src + dist"
rm -rf "$TARGET_DIR/src.prev" "$TARGET_DIR/dist.prev"
if [[ -d "$TARGET_DIR/src" ]]; then mv "$TARGET_DIR/src" "$TARGET_DIR/src.prev"; fi
if [[ -d "$TARGET_DIR/dist" ]]; then mv "$TARGET_DIR/dist" "$TARGET_DIR/dist.prev"; fi
mv "$TARGET_DIR/src.new" "$TARGET_DIR/src"
mv "$TARGET_DIR/dist.new" "$TARGET_DIR/dist"

log "Restarting $SERVICE"
systemctl restart "$SERVICE"

log "Waiting for active state"
for i in {1..20}; do
  state="$(systemctl is-active "$SERVICE" || true)"
  [[ "$state" == "active" ]] && break
  sleep 1
done

if [[ "$(systemctl is-active "$SERVICE" || true)" != "active" ]]; then
  echo "Service failed to become active, rolling back" >&2
  rm -rf "$TARGET_DIR/src" "$TARGET_DIR/dist"
  if [[ -d "$BACKUP_DIR/src" ]]; then rsync -a "$BACKUP_DIR/src/" "$TARGET_DIR/src/"; fi
  if [[ -d "$BACKUP_DIR/dist" ]]; then rsync -a "$BACKUP_DIR/dist/" "$TARGET_DIR/dist/"; fi
  if [[ -f "$BACKUP_DIR/package.json" ]]; then install -o "$OWNER_USER" -g "$OWNER_GROUP" -m 0644 "$BACKUP_DIR/package.json" "$TARGET_DIR/package.json"; fi
  if [[ -f "$BACKUP_DIR/package-lock.json" ]]; then install -o "$OWNER_USER" -g "$OWNER_GROUP" -m 0644 "$BACKUP_DIR/package-lock.json" "$TARGET_DIR/package-lock.json"; fi
  chown -R "$OWNER_USER:$OWNER_GROUP" "$TARGET_DIR/src" "$TARGET_DIR/dist" || true
  systemctl restart "$SERVICE" || true
  exit 1
fi

log "Running smoke checks"
SMOKE_OK=0
for i in {1..25}; do
  HEALTH="$(curl -fsS --max-time 2 http://127.0.0.1:8787/api/health || true)"
  ROOT_HTML="$(curl -fsS --max-time 2 http://127.0.0.1:8787/ || true)"
  if [[ "$HEALTH" == *'"ok":true'* ]] && [[ "$ROOT_HTML" == *'<div id="root"></div>'* ]]; then
    SMOKE_OK=1
    break
  fi
  sleep 1
done

if [[ "$SMOKE_OK" -ne 1 ]]; then
  echo "Smoke checks failed, rolling back" >&2
  rm -rf "$TARGET_DIR/src" "$TARGET_DIR/dist"
  if [[ -d "$BACKUP_DIR/src" ]]; then rsync -a "$BACKUP_DIR/src/" "$TARGET_DIR/src/"; fi
  if [[ -d "$BACKUP_DIR/dist" ]]; then rsync -a "$BACKUP_DIR/dist/" "$TARGET_DIR/dist/"; fi
  if [[ -f "$BACKUP_DIR/package.json" ]]; then install -o "$OWNER_USER" -g "$OWNER_GROUP" -m 0644 "$BACKUP_DIR/package.json" "$TARGET_DIR/package.json"; fi
  if [[ -f "$BACKUP_DIR/package-lock.json" ]]; then install -o "$OWNER_USER" -g "$OWNER_GROUP" -m 0644 "$BACKUP_DIR/package-lock.json" "$TARGET_DIR/package-lock.json"; fi
  chown -R "$OWNER_USER:$OWNER_GROUP" "$TARGET_DIR/src" "$TARGET_DIR/dist" || true
  systemctl restart "$SERVICE" || true
  exit 1
fi

printf '%s\n' "$SOURCE_COMMIT" > "$TARGET_DIR/.deploy-source-commit.new"
chown "$OWNER_USER:$OWNER_GROUP" "$TARGET_DIR/.deploy-source-commit.new"
mv "$TARGET_DIR/.deploy-source-commit.new" "$TARGET_DIR/.deploy-source-commit"

log "Deploy successful"
