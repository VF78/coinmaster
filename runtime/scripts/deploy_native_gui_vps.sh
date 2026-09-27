#!/usr/bin/env bash
# VPS-local driver for the existing native_gui_host.sh stage/activation gates.
set -euo pipefail
ACTION="${1:-}"
case "$ACTION" in plan|stage|activate-api|rollback) ;; *) echo 'usage: deploy_native_gui_vps.sh plan|stage|activate-api|rollback' >&2; exit 2;; esac
[[ "$(id -u)" == 0 ]] || { echo 'root required' >&2; exit 2; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMMIT="${GUI_DEPLOY_RELEASE_SHA:-$(git -C "$ROOT" rev-parse HEAD)}"
[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo 'invalid commit' >&2; exit 2; }
if [[ "$ACTION" == stage ]]; then
  [[ "$COMMIT" == "$(git -C "$ROOT" rev-parse HEAD)" ]] || { echo 'stage requires exact HEAD' >&2; exit 2; }
fi
HOST="$ROOT/runtime/scripts/native_gui_host.sh"
if [[ "$ACTION" != stage ]]; then
  bash "$HOST" "$ACTION" "$COMMIT" none
  exit
fi
[[ -z "$(git -C "$ROOT" status --porcelain=v1 --untracked-files=all)" ]] || { echo 'commit exact source before staging' >&2; exit 2; }
command -v npm >/dev/null
command -v rsync >/dev/null
bash "$HOST" plan "$COMMIT" none
npm --prefix "$ROOT/coinmaster" run check
npm --prefix "$ROOT/coinmaster" run build
TEMP="$(mktemp -d /var/tmp/coinmaster-native-gui.XXXXXX)"
trap 'rm -rf -- "$TEMP"' EXIT
mkdir -p "$TEMP/release/web"
git -C "$ROOT" archive "$COMMIT" runtime | tar -x -C "$TEMP/release"
rsync -a "$ROOT/coinmaster/dist/" "$TEMP/release/web/"
python3 "$ROOT/runtime/scripts/release_manifest.py" generate \
  --source-root "$ROOT" --runtime-root "$TEMP/release/runtime" \
  --release-root "$TEMP/release" --component gui \
  --output "$TEMP/release/runtime/release-manifest.json"
python3 "$ROOT/runtime/scripts/release_manifest.py" verify \
  --runtime-root "$TEMP/release/runtime" --release-root "$TEMP/release" \
  --manifest "$TEMP/release/runtime/release-manifest.json" \
  --expected-commit "$COMMIT" --component gui
ARCHIVE="/var/tmp/coinmaster-native-gui-$COMMIT.tar.gz"
[[ ! -e "$ARCHIVE" ]] || { echo 'stale GUI archive exists' >&2; exit 1; }
tar -C "$TEMP/release" -czf "$TEMP/release.tar.gz" runtime web
DIGEST="$(sha256sum "$TEMP/release.tar.gz" | cut -d ' ' -f1)"
install -m 0600 "$TEMP/release.tar.gz" "$ARCHIVE"
bash "$HOST" stage "$COMMIT" "$DIGEST"
