#!/usr/bin/env bash
# Stop the CHAOS access point. This does not delete its saved local password.
set -Eeuo pipefail
PROFILE="chaos-family-hotspot"
if ! command -v nmcli >/dev/null 2>&1; then
  echo "nmcli is not installed." >&2
  exit 1
fi
if nmcli -t -f NAME connection show --active | grep -Fxq "$PROFILE"; then
  nmcli connection down "$PROFILE"
  echo "CHAOS hotspot stopped."
else
  echo "CHAOS hotspot is not currently active."
fi
