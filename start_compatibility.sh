#!/usr/bin/env sh
# Run the application locally for diagnostics; the main launcher adds Cloudflare.
set -eu
cd "$(dirname "$0")"
exec python3 -m server.app "$@"
