#!/usr/bin/env bash
# Start the CHAOS hotspot and then serve the compatibility probe on it.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ $# -gt 0 ]]; then
  bash "$ROOT/scripts/start_chaos_hotspot.sh" "$1"
else
  bash "$ROOT/scripts/start_chaos_hotspot.sh"
fi
exec python3 "$ROOT/compatibility/probe_server.py" --host 10.42.0.1
