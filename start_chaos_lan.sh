#!/usr/bin/env bash
# Start the CHAOS hotspot and compatibility server; stop the hotspot on exit.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
  bash "$ROOT/scripts/stop_chaos_hotspot.sh" || true
}
trap cleanup EXIT INT TERM

if [[ $# -gt 0 ]]; then
  bash "$ROOT/scripts/start_chaos_hotspot.sh" "$1"
else
  bash "$ROOT/scripts/start_chaos_hotspot.sh"
fi

python3 "$ROOT/compatibility/probe_server.py" --host 10.42.0.1
