#!/usr/bin/env bash
# Invoked over SSH by deploy_native_gui.sh. Never touches paper or trader units.
set -euo pipefail
ACTION="${1:-}"; COMMIT="${2:-}"; ARCHIVE_SHA="${3:-none}"
[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo 'invalid release SHA' >&2; exit 2; }
case "$ACTION" in plan|stage|activate-api|rollback) ;; *) exit 2;; esac
[[ "$(id -u)" == 0 ]] || { echo 'root is required for isolated unit provisioning' >&2; exit 2; }
BASE=/srv/coinmaster-native-gui
RELEASE="$BASE/releases/$COMMIT"
CURRENT="$BASE/current"
STATE=/var/lib/coinmaster-native-gui
BACKUPS=/var/lib/coinmaster-native-gui-deploy
ENV_FILE=/etc/coinmaster-native-gui.env
UNIT=/etc/systemd/system/coinmaster-runtime.service
OLD_DB=/var/lib/coinmaster-runtime/control.sqlite
ARCHIVE="/var/tmp/coinmaster-native-gui-$COMMIT.tar.gz"
PAPER=coinmaster-paper.service
TRADER=coinmaster-hl-stageg-testnet.service
RUNTIME=coinmaster-runtime.service

pid() { systemctl show -P MainPID "$1"; }
active() { [[ "$(systemctl show -P ActiveState "$1")" == active ]]; }
assert_peers() { active "$PAPER" && active "$TRADER" && [[ "$(pid "$PAPER")" == "$1" ]] && [[ "$(pid "$TRADER")" == "$2" ]]; }
source_db() { if [[ -L "$CURRENT" ]]; then printf '%s\n' "$STATE/control.sqlite"; else printf '%s\n' "$OLD_DB"; fi; }
check_no_jobs() {
  python3 - "$1" <<'PY'
import sqlite3, sys
from pathlib import Path
path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit('control DB missing')
db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
if 'research_leases' in tables and db.execute('SELECT count(*) FROM research_leases').fetchone()[0]:
    raise SystemExit('active research lease blocks deploy')
if 'runs' in tables and db.execute("SELECT count(*) FROM runs WHERE kind='research' AND status IN ('STARTING','RUNNING','CANCEL_REQUESTED')").fetchone()[0]:
    raise SystemExit('active research run blocks deploy')
PY
}
backup_db() {
  python3 - "$1" "$2" <<'PY'
import sqlite3, sys
src = sqlite3.connect(f'file:{sys.argv[1]}?mode=ro', uri=True)
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
assert dst.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
dst.close(); src.close()
PY
}
token_from_paper_env() {
  python3 - <<'PY'
import re
from pathlib import Path
lines = [line for line in Path('/etc/coinmaster-paper.env').read_text().splitlines() if line.startswith('COINMASTER_RUNTIME_API_TOKEN=')]
if len(lines) != 1:
    raise SystemExit('exactly one operator token is required in the existing env')
token = lines[0].split('=', 1)[1].strip().strip('"\'')
if not re.fullmatch(r'[A-Za-z0-9._~+\-]{16,256}', token):
    raise SystemExit('operator token is missing or uses unsupported quoting')
print(token)
PY
}
api_smoke() {
  local port="$1" db="$2"
  GUI_SMOKE_PORT="$port" GUI_SMOKE_DB="$db" COINMASTER_RUNTIME_API_TOKEN="$TOKEN" python3 - <<'PY'
import json, os, sqlite3, urllib.error, urllib.request
base = f"http://127.0.0.1:{os.environ['GUI_SMOKE_PORT']}"
token = os.environ['COINMASTER_RUNTIME_API_TOKEN']
def get(path, authorized=True, method='GET'):
    headers = {'Authorization': f'Bearer {token}'} if authorized else {}
    req = urllib.request.Request(base + path, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
assert get('/api/v1/instances/hl-stageg-testnet/controls', False)[0] == 401
status, raw = get('/api/v1/instances/hl-stageg-testnet/controls')
assert status == 200
controls = json.loads(raw)
assert controls['instance_id'] == 'hl-stageg-testnet' and controls['projection_state'] == 'UNAVAILABLE'
assert all(not controls[name]['enabled'] for name in ('pause','resume','flatten','promotion'))
assert json.loads(get('/api/v1/instances/hl-stageg-testnet')[1])['projection_state'] == 'UNAVAILABLE'
spec = json.loads(get('/api/v1/openapi.json')[1])
assert '/api/v1/runtime/commands/{command}' not in spec['paths']
assert '/api/v1/research/capabilities' in spec['paths']
assert get('/api/v1/research/capabilities')[0] == 200
assert get('/api/v1/instances/hl-stageg-testnet/controls', method='POST')[0] == 405
assert get('/api/v1/auth/session', False)[0] == 401
assert b'Operator sign in' in get('/', False)[1]
assert get('/', True)[0] == 200
db = sqlite3.connect(f"file:{os.environ['GUI_SMOKE_DB']}?mode=ro", uri=True)
assert db.execute('SELECT count(*) FROM research_leases').fetchone()[0] == 0
print('API_SMOKE_OK: auth, SPA, HL unavailable/disabled, no paper command route, research lease clear')
PY
}
wait_api_ready() {
  local deadline=$((SECONDS + 30))
  while (( SECONDS < deadline )); do
    if python3 - <<'PY' >/dev/null 2>&1
import urllib.error, urllib.request
try:
    urllib.request.urlopen('http://127.0.0.1:18182/api/v1/health', timeout=1)
except urllib.error.HTTPError as error:
    raise SystemExit(0 if error.code == 401 else 1)
except Exception:
    raise SystemExit(1)
raise SystemExit(1)
PY
    then return 0; fi
    sleep 1
  done
  echo 'runtime API did not become ready within 30 seconds' >&2
  return 1
}
if [[ "$ACTION" == plan ]]; then
  active "$PAPER" && active "$TRADER" && active "$RUNTIME" || { echo 'required service is inactive' >&2; exit 1; }
  check_no_jobs "$(source_db)"
  token_from_paper_env >/dev/null
  [[ -x /root/.local/bin/uv ]] || { echo 'pinned Linux uv runtime unavailable' >&2; exit 1; }
  [[ -e "$UNIT" ]] || { echo 'current runtime unit missing' >&2; exit 1; }
  echo "PLAN_OK commit=$COMMIT runtime_pid=$(pid "$RUNTIME") paper_pid=$(pid "$PAPER") trader_pid=$(pid "$TRADER") current=$(readlink "$CURRENT" 2>/dev/null || echo none)"
  exit
fi

exec 9>/run/coinmaster-native-gui-deploy.lock
flock -n 9 || { echo 'another native GUI deploy holds the lock' >&2; exit 1; }
if [[ "$ACTION" == stage ]]; then
  [[ "$ARCHIVE_SHA" =~ ^[0-9a-f]{64}$ ]] || { echo 'invalid archive digest' >&2; exit 2; }
  [[ -f "$ARCHIVE" && ! -e "$RELEASE" && ! -e "$RELEASE.incoming" ]] || { echo 'release/archive already exists or is missing' >&2; exit 1; }
  [[ "$(sha256sum "$ARCHIVE" | cut -d ' ' -f1)" == "$ARCHIVE_SHA" ]] || { echo 'archive digest mismatch' >&2; exit 1; }
  active "$PAPER" && active "$TRADER" && active "$RUNTIME" || { echo 'required service inactive' >&2; exit 1; }
  check_no_jobs "$(source_db)"
  PAPER_BEFORE="$(pid "$PAPER")"; TRADER_BEFORE="$(pid "$TRADER")"
  TOKEN="$(token_from_paper_env)"
  GUI_AUTH_RAW="$(python3 - "$ENV_FILE" "$TOKEN" <<'PY'
import os, re, sys
from pathlib import Path
path = Path(sys.argv[1])
stat = path.stat()
if stat.st_uid != 0 or stat.st_mode & 0o077:
    raise SystemExit('GUI environment must be root-owned mode 0600')
entries = dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line)
if entries.get('COINMASTER_RUNTIME_API_TOKEN') != sys.argv[2]:
    raise SystemExit('GUI automation token differs from current operator token')
user, verifier = entries.get('COINMASTER_GUI_USERNAME', ''), entries.get('COINMASTER_GUI_PASSWORD_HASH', '')
if not re.fullmatch(r'[A-Za-z0-9_-]{3,32}', user) or not re.fullmatch(r'scrypt\$15\$8\$1\$[0-9a-f]{64}\$[0-9a-f]{128}', verifier):
    raise SystemExit('one GUI operator and a strong password verifier are required')
print(user); print(verifier)
PY
)"
  GUI_USERNAME="${GUI_AUTH_RAW%%$'\n'*}"; GUI_PASSWORD_HASH="${GUI_AUTH_RAW#*$'\n'}"
  if ! id coinmaster-research >/dev/null 2>&1; then
    useradd --system --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin coinmaster-research
  fi
  [[ "$(id -g coinmaster-research)" != "$(id -g coinmaster-hl)" ]] || { echo 'research and trader groups overlap' >&2; exit 1; }
  install -d -m 0755 "$BASE" "$BASE/releases"
  install -d -m 0700 -o coinmaster-research -g coinmaster-research "$STATE" "$STATE/data"
  install -d -m 0700 "$BACKUPS"
  umask 077
  mkdir "$RELEASE.incoming"
  tar -xzf "$ARCHIVE" -C "$RELEASE.incoming" --no-same-owner
  [[ -f "$RELEASE.incoming/runtime/uv.lock" && -f "$RELEASE.incoming/runtime/ops/coinmaster-native-gui.service" && -f "$RELEASE.incoming/web/index.html" ]] || { echo 'incomplete release' >&2; exit 1; }
  (cd "$RELEASE.incoming/runtime" && /root/.local/bin/uv sync --frozen --no-dev --no-install-project)
  chmod -R a+rX "$RELEASE.incoming"
  SMOKE="$STATE/smoke-$COMMIT"
  install -d -m 0700 -o coinmaster-research -g coinmaster-research "$SMOKE" "$SMOKE/data"
  backup_db "$(source_db)" "$SMOKE/control.sqlite"
  chown coinmaster-research:coinmaster-research "$SMOKE/control.sqlite"
  [[ -z "$(ss -ltn '( sport = :18184 )' | tail -n +2)" ]] || { echo 'smoke port is already occupied' >&2; exit 1; }
  (cd "$RELEASE.incoming/runtime" && runuser -u coinmaster-research -- env -i PATH=/usr/bin:/bin \
    COINMASTER_RUNTIME_API_TOKEN="$TOKEN" COINMASTER_GUI_USERNAME="$GUI_USERNAME" COINMASTER_GUI_PASSWORD_HASH="$GUI_PASSWORD_HASH" \
    COINMASTER_GUI_ORIGIN=https://coinmaster24.com COINMASTER_GUI_SESSION_DB="$SMOKE/auth.sqlite" \
    COINMASTER_RUNTIME_CONTROL_DB="$SMOKE/control.sqlite" COINMASTER_CONTROL_DB="$SMOKE/legacy-control.sqlite" \
    COINMASTER_RESEARCH_DATA_ROOT="$SMOKE/data" COINMASTER_RUNTIME_DIST="$RELEASE.incoming/web" \
    COINMASTER_HL_STAGEG_STATUS_URL=http://127.0.0.1:18183 COINMASTER_PAPER_DB="$SMOKE/no-paper.sqlite" \
    PYTHONPATH="$RELEASE.incoming/runtime" PYTHONDONTWRITEBYTECODE=1 GUI_SMOKE_PIDFILE="$SMOKE/uvicorn.pid" GUI_PYTHON="$RELEASE.incoming/runtime/.venv/bin/python" \
    sh -c 'echo $$ > "$GUI_SMOKE_PIDFILE"; exec "$GUI_PYTHON" -m uvicorn coinmaster.api.runtime_sidecar:app --host 127.0.0.1 --port 18184' >/dev/null 2>&1) &
  SMOKE_PARENT=$!
  trap 'if [[ -f "$SMOKE/uvicorn.pid" ]]; then kill "$(cat "$SMOKE/uvicorn.pid")" 2>/dev/null || true; fi; kill "$SMOKE_PARENT" 2>/dev/null || true; wait "$SMOKE_PARENT" 2>/dev/null || true' EXIT
  for _ in {1..30}; do
    if GUI_SMOKE_PORT=18184 COINMASTER_RUNTIME_API_TOKEN="$TOKEN" python3 - <<'PY' >/dev/null 2>&1
import urllib.error, urllib.request
try: urllib.request.urlopen('http://127.0.0.1:18184/api/v1/health', timeout=.5)
except urllib.error.HTTPError as error: raise SystemExit(0 if error.code == 401 else 1)
except Exception: raise SystemExit(1)
PY
    then break; fi
    sleep 1
  done
  [[ -f "$SMOKE/uvicorn.pid" ]] && kill -0 "$(cat "$SMOKE/uvicorn.pid")" || { echo 'smoke process died before validation' >&2; exit 1; }
  api_smoke 18184 "$SMOKE/control.sqlite"
  kill "$(cat "$SMOKE/uvicorn.pid")" 2>/dev/null || true
  kill "$SMOKE_PARENT" 2>/dev/null || true
  wait "$SMOKE_PARENT" 2>/dev/null || true
  trap - EXIT
  assert_peers "$PAPER_BEFORE" "$TRADER_BEFORE" || { echo 'peer PID changed during stage' >&2; exit 1; }
  printf 'archive_sha256=%s\npaper_pid=%s\ntrader_pid=%s\n' "$ARCHIVE_SHA" "$PAPER_BEFORE" "$TRADER_BEFORE" > "$RELEASE.incoming/stage.receipt"
  chmod -R a-w "$RELEASE.incoming"
  mv "$RELEASE.incoming" "$RELEASE"
  "$RELEASE/runtime/.venv/bin/python" -m uvicorn --version >/dev/null
  rm -f -- "$ARCHIVE"
  echo "STAGED_OK commit=$COMMIT archive_sha256=$ARCHIVE_SHA"
  exit
fi

[[ -d "$RELEASE" && -f "$RELEASE/stage.receipt" ]] || { echo 'release has no verified stage receipt' >&2; exit 1; }
TOKEN="$(token_from_paper_env)"
if [[ "$ACTION" == activate-api ]]; then
  check_no_jobs "$(source_db)"
  [[ "$(pid "$PAPER")" == "$(sed -n 's/^paper_pid=//p' "$RELEASE/stage.receipt")" && "$(pid "$TRADER")" == "$(sed -n 's/^trader_pid=//p' "$RELEASE/stage.receipt")" ]] || { echo 'peer PID changed since stage' >&2; exit 1; }
  [[ "$(basename "$RELEASE")" == "$COMMIT" && "$(sed -n 's/^archive_sha256=//p' "$RELEASE/stage.receipt")" =~ ^[0-9a-f]{64}$ ]] || { echo 'staged release identity or receipt digest is invalid' >&2; exit 1; }
  if [[ -d "$BACKUPS/$COMMIT" ]]; then
    [[ -f "$BACKUPS/$COMMIT/prior.unit" && -f "$BACKUPS/$COMMIT/prior.release" && -f "$BACKUPS/$COMMIT/prior.pids" ]] || { echo 'incomplete prior activation backup; refusing retry' >&2; exit 1; }
    cmp -s "$UNIT" "$BACKUPS/$COMMIT/prior.unit" && active "$RUNTIME" || { echo 'runtime no longer matches the saved pre-activation state' >&2; exit 1; }
    PREVIOUS="$(cat "$BACKUPS/$COMMIT/prior.release")"
    if [[ "$PREVIOUS" == none ]]; then [[ ! -L "$CURRENT" ]] || { echo 'release pointer changed since rollback' >&2; exit 1; }
    else [[ "$(readlink "$CURRENT" 2>/dev/null || true)" == "$PREVIOUS" ]] || { echo 'release pointer changed since rollback' >&2; exit 1; }; fi
    assert_peers "$(sed -n 's/^paper_pid=//p' "$BACKUPS/$COMMIT/prior.pids")" "$(sed -n 's/^trader_pid=//p' "$BACKUPS/$COMMIT/prior.pids")" || { echo 'paper/trader PID differs from activation backup' >&2; exit 1; }
  else
    install -d -m 0700 "$BACKUPS/$COMMIT"
    cp "$UNIT" "$BACKUPS/$COMMIT/prior.unit"
    systemctl show -P EnvironmentFiles "$RUNTIME" > "$BACKUPS/$COMMIT/prior.env-ref"
    sha256sum /etc/coinmaster-paper.env > "$BACKUPS/$COMMIT/prior.env-sha256"
    readlink "$CURRENT" > "$BACKUPS/$COMMIT/prior.release" 2>/dev/null || printf 'none\n' > "$BACKUPS/$COMMIT/prior.release"
    printf 'runtime_pid=%s\npaper_pid=%s\ntrader_pid=%s\n' "$(pid "$RUNTIME")" "$(pid "$PAPER")" "$(pid "$TRADER")" > "$BACKUPS/$COMMIT/prior.pids"
  fi
  systemctl stop "$RUNTIME"
  if [[ ! -L "$CURRENT" ]]; then
    backup_db "$OLD_DB" "$STATE/control.sqlite"
    chown coinmaster-research:coinmaster-research "$STATE/control.sqlite"
  fi
  cp "$RELEASE/runtime/ops/coinmaster-native-gui.service" "$UNIT"
  ln -s "$RELEASE" "$CURRENT.next"
  mv -Tf "$CURRENT.next" "$CURRENT"
  systemctl daemon-reload
  if ! systemctl start "$RUNTIME" || ! wait_api_ready || ! active "$RUNTIME" || ! assert_peers "$(sed -n 's/^paper_pid=//p' "$BACKUPS/$COMMIT/prior.pids")" "$(sed -n 's/^trader_pid=//p' "$BACKUPS/$COMMIT/prior.pids")" || ! api_smoke 18182 "$STATE/control.sqlite"; then
    echo 'activation failed; restoring the prior runtime unit' >&2
    systemctl stop "$RUNTIME" || true
    cp "$BACKUPS/$COMMIT/prior.unit" "$UNIT"
    PREVIOUS="$(cat "$BACKUPS/$COMMIT/prior.release")"
    if [[ "$PREVIOUS" == none ]]; then rm -f -- "$CURRENT"; else ln -s "$PREVIOUS" "$CURRENT.rollback"; mv -Tf "$CURRENT.rollback" "$CURRENT"; fi
    systemctl daemon-reload
    systemctl start "$RUNTIME"
    wait_api_ready && active "$RUNTIME" && assert_peers "$(sed -n 's/^paper_pid=//p' "$BACKUPS/$COMMIT/prior.pids")" "$(sed -n 's/^trader_pid=//p' "$BACKUPS/$COMMIT/prior.pids")" || { echo 'automatic rollback did not pass readiness/PID checks' >&2; exit 2; }
    exit 1
  fi
  echo "ACTIVE_OK commit=$COMMIT runtime_pid=$(pid "$RUNTIME") paper_pid=$(pid "$PAPER") trader_pid=$(pid "$TRADER")"
  exit
fi

[[ -f "$BACKUPS/$COMMIT/prior.unit" && "$(readlink "$CURRENT")" == "$RELEASE" ]] || { echo 'rollback target does not match current release' >&2; exit 1; }
check_no_jobs "$STATE/control.sqlite"
PAPER_BEFORE="$(pid "$PAPER")"; TRADER_BEFORE="$(pid "$TRADER")"
systemctl stop "$RUNTIME"
cp "$BACKUPS/$COMMIT/prior.unit" "$UNIT"
PREVIOUS="$(cat "$BACKUPS/$COMMIT/prior.release")"
if [[ "$PREVIOUS" == none ]]; then rm -f -- "$CURRENT"; else ln -s "$PREVIOUS" "$CURRENT.rollback"; mv -Tf "$CURRENT.rollback" "$CURRENT"; fi
systemctl daemon-reload
systemctl start "$RUNTIME"
wait_api_ready && active "$RUNTIME" && assert_peers "$PAPER_BEFORE" "$TRADER_BEFORE" || { echo 'rollback needs operator attention' >&2; exit 1; }
echo "ROLLBACK_OK runtime_pid=$(pid "$RUNTIME") paper_pid=$PAPER_BEFORE trader_pid=$TRADER_BEFORE"
