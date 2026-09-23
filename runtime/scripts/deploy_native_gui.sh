#!/usr/bin/env bash
# Local driver. Host-side gates and rollback live in native_gui_host.sh.
set -euo pipefail

ACTION="${1:-}"
case "$ACTION" in plan|stage|activate-api|rollback) ;; *) echo 'usage: GUI_DEPLOY_HOST=root@host deploy_native_gui.sh plan|stage|activate-api|rollback' >&2; exit 2;; esac
HOST="${GUI_DEPLOY_HOST:?set GUI_DEPLOY_HOST to the verified SSH target}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GIT=/Library/Developer/CommandLineTools/usr/bin/git
[[ -x "$GIT" ]] || GIT=git
COMMIT="$("$GIT" -C "$ROOT" rev-parse HEAD)"
[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo 'invalid commit' >&2; exit 2; }
HELPER="$ROOT/runtime/scripts/native_gui_host.sh"
SSH=(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=8 "$HOST")

run_host() { "${SSH[@]}" "bash -s -- '$1' '$COMMIT' '${2:-none}'" < "$HELPER"; }
if [[ "$ACTION" == plan ]]; then run_host plan; exit; fi
if [[ "$ACTION" == rollback || "$ACTION" == activate-api ]]; then run_host "$ACTION"; exit; fi

[[ -z "$("$GIT" -C "$ROOT" status --porcelain)" ]] || { echo 'commit the exact source before staging' >&2; exit 2; }
command -v npm >/dev/null
command -v rsync >/dev/null
command -v scp >/dev/null
run_host plan
npm --prefix "$ROOT/coinmaster" run check
npm --prefix "$ROOT/coinmaster" run build
TEMP="$(mktemp -d /private/tmp/coinmaster-native-gui.XXXXXX)"
trap 'rm -rf -- "$TEMP"' EXIT
mkdir -p "$TEMP/release/web"
"$GIT" -C "$ROOT" archive "$COMMIT" runtime | tar -x -C "$TEMP/release"
rsync -a "$ROOT/coinmaster/dist/" "$TEMP/release/web/"
tar -C "$TEMP/release" -czf "$TEMP/release.tar.gz" runtime web
DIGEST="$(shasum -a 256 "$TEMP/release.tar.gz" | cut -d ' ' -f1)"
scp -q "$TEMP/release.tar.gz" "$HOST:/var/tmp/coinmaster-native-gui-$COMMIT.tar.gz"
run_host stage "$DIGEST"
