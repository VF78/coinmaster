#!/usr/bin/env bash
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo "root required" >&2; exit 2; }
SOURCE="$(cd "$(dirname "$0")/.." && pwd)/ops/coinmaster-stageg.needrestart.conf"
TARGET=/etc/needrestart/conf.d/coinmaster-stageg.conf
[[ -f /etc/needrestart/needrestart.conf && -d /etc/needrestart/conf.d ]] || { echo "needrestart not installed" >&2; exit 1; }
perl -c "$SOURCE" >/dev/null
if [[ "${1:-}" == --check ]]; then
  cmp "$SOURCE" "$TARGET"
  exit
fi
[[ "${1:-}" == --install ]] || { echo "use --check or --install" >&2; exit 2; }
TEMP="$(mktemp /etc/needrestart/conf.d/.coinmaster-stageg.XXXXXX)"
trap 'rm -f "$TEMP"' EXIT
install -m 0644 "$SOURCE" "$TEMP"
perl -c "$TEMP" >/dev/null
mv -f "$TEMP" "$TARGET"
trap - EXIT
cmp "$SOURCE" "$TARGET"
