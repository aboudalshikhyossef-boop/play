# Superseded Network Decision: Laptop-Hosted Wi-Fi Hotspot

> **Status: Superseded.** The project now uses Cloudflare Quick Tunnel for device access. The hotspot scripts are no longer part of the normal startup flow.

## Historical experiment

An earlier design proposed making the Linux Mint laptop a 2.4 GHz WPA2 Wi-Fi access point using NetworkManager, with the laptop at `10.42.0.1/24`. The compatibility page opened on the laptop, and Android devices could join the hotspot, but the page still did not load from the phones. The owner then tested Cloudflare Quick Tunnel and confirmed successful page loading in iPhone 4S Safari 9.3.6.

## Current decision

Use the Cloudflare Quick Tunnel documented in [07-CLOUDFLARE-QUICK-TUNNEL.md](07-CLOUDFLARE-QUICK-TUNNEL.md).

The Python origin listens on `127.0.0.1:8765`. cloudflared creates an outbound tunnel and prints a temporary HTTPS URL. All four player browsers open that same URL. The laptop remains player 1 and retains the authoritative game server and SQLite database.

## What this means

- Do not create a CHAOS Wi-Fi hotspot as part of normal startup.
- Do not change NetworkManager Wi-Fi profiles for the game.
- Do not add router port forwarding.
- Do not open an inbound UFW rule for the game origin.
- Do not disable Proton VPN or its Kill Switch to start the tunnel.
- Internet access is required on the laptop and all player devices while the Quick Tunnel is used.
- The old `start_chaos_lan.sh` command is retained only as an alias to the Cloudflare launcher.

## Historical configuration

The former SSID, WPA2 passphrase generation, AP-mode checks, and `10.42.0.1` address are no longer active project requirements. If a NetworkManager profile named `chaos-family-hotspot` remains on the laptop, it is not activated by the current launcher. The owner may remove the old profile manually later if desired.

## Verification state

- [x] Quick Tunnel tested by the owner.
- [x] iPhone 4S / Safari 9.3.6 successfully opened the compatibility page through the Quick Tunnel.
- [ ] Confirm both Android phones using the same Quick Tunnel URL.
- [ ] Record viewport and layout results on all phones.
