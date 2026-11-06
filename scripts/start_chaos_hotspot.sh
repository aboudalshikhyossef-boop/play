#!/usr/bin/env bash
# Create/start the private CHAOS Wi-Fi access point through NetworkManager.
# Safe preflight: does not replace or delete existing Wi-Fi profiles.
set -Eeuo pipefail

SSID="CHAOS-FAMILY"
PROFILE="chaos-family-hotspot"
HOTSPOT_IP="10.42.0.1"
PASS_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/chaos-family"
PASS_FILE="$PASS_DIR/hotspot-password"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

for tool in nmcli iw ip python3; do
  command -v "$tool" >/dev/null 2>&1 || fail "Required command '$tool' not found. Install it first (for iw: sudo apt install iw)."
done

IFACE="${1:-}"
if [[ -z "$IFACE" ]]; then
  IFACE="$(nmcli -t -f DEVICE,TYPE device status | awk -F: '$2 == "wifi" { print $1; exit }')"
fi
[[ -n "$IFACE" ]] || fail "No Wi-Fi interface found. Check that the laptop Wi-Fi adapter is enabled."

if ! nmcli -t -f DEVICE device status | grep -Fxq "$IFACE"; then
  fail "Interface '$IFACE' is not listed by NetworkManager."
fi

nmcli radio wifi on

PHY_ID="$(iw dev "$IFACE" info 2>/dev/null | awk '$1 == "wiphy" { print $2; exit }')"
[[ -n "$PHY_ID" ]] || fail "Could not identify the wireless hardware for '$IFACE'."

PHY_INFO="$(iw phy "phy$PHY_ID" info 2>/dev/null)" || fail "Could not inspect Wi-Fi capabilities for phy$PHY_ID."
if ! printf '%s\n' "$PHY_INFO" | awk '
  /Supported interface modes:/ { in_modes=1; next }
  in_modes && /^Band / { in_modes=0 }
  in_modes && $1 == "*" && $2 == "AP" { found=1 }
  END { exit !found }
'; then
  fail "This Wi-Fi adapter/driver does not advertise Access Point (AP) mode. No hotspot profile was activated. A compatible USB Wi-Fi adapter may be needed."
fi

umask 077
mkdir -p "$PASS_DIR"
chmod 700 "$PASS_DIR"
if [[ ! -s "$PASS_FILE" ]]; then
  python3 -c 'import secrets,string; a=string.ascii_letters+string.digits; print("".join(secrets.choice(a) for _ in range(24)))' > "$PASS_FILE"
fi
chmod 600 "$PASS_FILE"
PASSWORD="$(cat "$PASS_FILE")"

if ! nmcli -t -f NAME connection show | grep -Fxq "$PROFILE"; then
  nmcli connection add type wifi ifname "$IFACE" con-name "$PROFILE" ssid "$SSID" >/dev/null
fi

nmcli connection modify "$PROFILE" \
  connection.interface-name "$IFACE" \
  connection.autoconnect no \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  802-11-wireless.channel 6 \
  ipv4.method shared \
  ipv4.addresses "$HOTSPOT_IP/24" \
  ipv6.method disabled \
  802-11-wireless-security.key-mgmt wpa-psk \
  802-11-wireless-security.proto rsn \
  802-11-wireless-security.pairwise ccmp \
  802-11-wireless-security.group ccmp \
  802-11-wireless-security.psk "$PASSWORD"

echo "Starting the CHAOS hotspot on $IFACE..."
echo "Note: this Wi-Fi adapter may disconnect from the home Wi-Fi while operating as an access point."
nmcli connection up "$PROFILE" ifname "$IFACE"

READY=0
for attempt in $(seq 1 12); do
  if ip -4 -o address show dev "$IFACE" | grep -q "$HOTSPOT_IP/24"; then
    READY=1
    break
  fi
  sleep 1
done

[[ "$READY" -eq 1 ]] || fail "The hotspot profile activated, but $HOTSPOT_IP/24 was not assigned to $IFACE. Inspect: nmcli connection show '$PROFILE'."

echo ""
echo "CHAOS hotspot is active."
echo "Wi-Fi interface:   $IFACE"
echo "Wi-Fi name (SSID): $SSID"
echo "Wi-Fi password:    $PASSWORD"
echo "Local game URL:    http://$HOTSPOT_IP:8765/"
echo ""
echo "The password is stored locally at: $PASS_FILE"
echo "It is not written into the Git repository."
echo "Connect all three phones to this Wi-Fi network, then open the URL above."
