#!/usr/bin/env bash
# Main CHAOS launcher: local Python server + temporary Cloudflare Quick Tunnel.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec bash "$ROOT/scripts/start_chaos_tunnel.sh" "$@"
