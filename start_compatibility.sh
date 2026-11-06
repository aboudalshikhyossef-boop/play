#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec python3 compatibility/probe_server.py "$@"
