#!/usr/bin/env bash
# Backward-compatible command name. This no longer creates a Wi-Fi hotspot.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec bash "$ROOT/start_chaos.sh" "$@"
