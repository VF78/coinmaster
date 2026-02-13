#!/usr/bin/env bash
set -euo pipefail

LOCAL_PORT="${LOCAL_PORT:-8787}"
SERVER_HOST="${SERVER_HOST:-127.0.0.1}"
SUBDOMAIN="${1:-}"

if ! nc -z "$SERVER_HOST" "$LOCAL_PORT" >/dev/null 2>&1; then
  echo "[ERR] local server is not reachable at ${SERVER_HOST}:${LOCAL_PORT}"
  echo "Start API first: npm run start"
  exit 1
fi

SSH_OPTS=(
  -o ServerAliveInterval=60
  -o ServerAliveCountMax=3
  -o ExitOnForwardFailure=yes
)

if [[ -n "$SUBDOMAIN" ]]; then
  echo "[INFO] requesting fixed subdomain: ${SUBDOMAIN}"
  echo "[INFO] requires key linked in https://admin.localhost.run and plan@ user"
  exec ssh "${SSH_OPTS[@]}" -N -R "${SUBDOMAIN}:80:localhost:${LOCAL_PORT}" plan@localhost.run
else
  echo "[INFO] starting free tunnel (URL may rotate)"
  exec ssh "${SSH_OPTS[@]}" -N -R "80:localhost:${LOCAL_PORT}" localhost.run
fi
