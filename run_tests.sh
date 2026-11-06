#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "[1/4] Compile Python modules"
python3 -m compileall -q server tests

echo "[2/4] Run unit and HTTP API tests"
python3 -m unittest discover -s tests -v

echo "[3/4] Check shell scripts"
bash -n start_chaos.sh start_chaos_lan.sh start_compatibility.sh scripts/start_chaos_tunnel.sh

echo "[4/4] Check JavaScript syntax"
if command -v node >/dev/null 2>&1; then
  node --check web/js/app.js
else
  echo "Node.js not installed; JavaScript syntax check skipped."
fi

echo "All available CHAOS checks passed."
