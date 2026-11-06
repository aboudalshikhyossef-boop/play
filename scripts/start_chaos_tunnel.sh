#!/usr/bin/env bash
# Start the local CHAOS compatibility server and publish it through a
# temporary Cloudflare Quick Tunnel. Does not configure Wi-Fi, UFW, routes,
# Proton VPN, or router settings.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="127.0.0.1"
PORT="${CHAOS_PORT:-8765}"
CLOUDFLARED_BIN="${CLOUDFLARED_BIN:-cloudflared}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

[[ "$PORT" =~ ^[0-9]+$ ]] || fail "CHAOS_PORT must be a number."
(( PORT >= 1024 && PORT <= 65535 )) || fail "CHAOS_PORT must be between 1024 and 65535."
command -v python3 >/dev/null 2>&1 || fail "Python 3 is required."
command -v "$CLOUDFLARED_BIN" >/dev/null 2>&1 || {
  echo "cloudflared was not found." >&2
  echo "Install it from: https://developers.cloudflare.com/tunnel/downloads/" >&2
  exit 1
}

RUN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/chaos-quick-tunnel.XXXXXX")"
chmod 700 "$RUN_DIR"
SERVER_LOG="$RUN_DIR/server.log"
TUNNEL_LOG="$RUN_DIR/tunnel.log"
SERVER_PID=""
TUNNEL_PID=""

stop_child() {
  local child_pid="$1"
  [[ -n "$child_pid" ]] || return 0
  if kill -0 "$child_pid" 2>/dev/null; then
    kill -TERM "$child_pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      kill -0 "$child_pid" 2>/dev/null || break
      sleep 0.2
    done
    kill -KILL "$child_pid" 2>/dev/null || true
  fi
  wait "$child_pid" 2>/dev/null || true
}

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  echo
  echo "Stopping CHAOS local server and Cloudflare tunnel..."
  stop_child "$TUNNEL_PID"
  stop_child "$SERVER_PID"
  rm -rf "$RUN_DIR"
  echo "CHAOS tunnel session stopped."
  exit "$exit_code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "Starting CHAOS compatibility server on http://$HOST:$PORT/ ..."
python3 "$ROOT/compatibility/probe_server.py" --host "$HOST" --port "$PORT" >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

SERVER_READY=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if python3 - "$HOST" "$PORT" <<'PY' >/dev/null 2>&1
import socket
import sys

connection = socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=1)
connection.close()
PY
  then
    SERVER_READY=1
    break
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "The local Python server stopped unexpectedly:" >&2
    cat "$SERVER_LOG" >&2 || true
    exit 1
  fi
  sleep 0.5
done

[[ "$SERVER_READY" -eq 1 ]] || {
  echo "The local Python server did not become ready:" >&2
  cat "$SERVER_LOG" >&2 || true
  exit 1
}

echo "Starting Cloudflare Quick Tunnel. Proton VPN settings are not changed."
"$CLOUDFLARED_BIN" tunnel --url "http://$HOST:$PORT" >"$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!

PUBLIC_URL=""
for _ in $(seq 1 90); do
  PUBLIC_URL="$(grep -Eo 'https://[[:alnum:]-]+\.trycloudflare\.com' "$TUNNEL_LOG" | head -n 1 || true)"
  [[ -n "$PUBLIC_URL" ]] && break

  if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
    echo "cloudflared exited before creating a Quick Tunnel:" >&2
    cat "$TUNNEL_LOG" >&2 || true
    exit 1
  fi
  sleep 1
done

if [[ -z "$PUBLIC_URL" ]]; then
  echo "No trycloudflare.com URL appeared within 90 seconds." >&2
  echo "cloudflared output:" >&2
  tail -n 40 "$TUNNEL_LOG" >&2 || true
  echo "Check internet access and Proton VPN/Kill Switch policy; this script does not bypass them." >&2
  exit 1
fi

echo
echo "============================================================"
echo " CHAOS compatibility test is ready"
echo
echo " Share this temporary URL with the other players:"
echo " $PUBLIC_URL"
echo
echo " Local origin: http://$HOST:$PORT/"
echo " The laptop player should open the same public URL."
echo " Keep this terminal open while testing or playing."
echo " Press Ctrl+C to stop both the tunnel and local server."
echo "============================================================"
echo
echo "Security: anyone who obtains this URL can reach the compatibility probe."
echo "Do not use this probe to expose private game data. The full game must"
echo "require a room invite code and a separate player session."
echo

wait "$TUNNEL_PID"
