# Compatibility Probe — اختبار توافق الأجهزة والاتصال

This temporary page checks:
- Access from the laptop, two Android phones, and iPhone 4S Safari.
- JSON request/response using XMLHttpRequest (no Fetch API).
- Arabic/RTL text rendering.
- Responsive page width and horizontal overflow.
- Touch response and viewport measurements.

The Python server uses only the standard library. The public test URL is created by Cloudflare Quick Tunnel. No router configuration or Wi-Fi hotspot is required.

## 1. Check requirements

On Linux Mint:

```bash
python3 --version
cloudflared --version
```

If `cloudflared` is missing, install the package for your Linux distribution using the [official Cloudflare download guide](https://developers.cloudflare.com/tunnel/downloads/).

## 2. Start the server and tunnel

From the repository root:

```bash
bash start_chaos.sh
```

The launcher:
1. Starts the Python server on `127.0.0.1:8765` only.
2. Waits for the local server to become ready.
3. Starts `cloudflared tunnel --url http://127.0.0.1:8765`.
4. Extracts and displays the temporary `trycloudflare.com` URL.
5. Keeps both processes running until you press Ctrl+C.

It does not create a hotspot, change NetworkManager, modify UFW, change Proton VPN settings, or add router port-forwarding rules.

The old command `bash start_chaos_lan.sh` is retained as an alias to this Cloudflare launcher. It no longer starts a laptop hotspot.

## 3. Open the same public URL on all devices

- Linux Mint laptop: player 1 and local server host.
- Android phone 1: open the printed HTTPS URL.
- Android phone 2: open the same HTTPS URL.
- iPhone 4S / iOS 9.3.6: open the same HTTPS URL in Safari.

Use the exact URL printed by the script. The hostname changes when a new Quick Tunnel is created. The laptop player should also use that public URL so all players use the same browser origin.

The laptop and each phone need an internet connection. They do not need to be on the same Wi-Fi network.

## 4. What to test

On each device:
- Does the page open using the temporary HTTPS URL?
- Does the server status show connected?
- Does the tap counter increase after each press?
- Does sending a test message return a successful echo?
- Does the page avoid horizontal scrolling?
- Record viewport width and height.
- Rotate the phone and repeat the layout check.

On iPhone 4S, verify Safari 9.3.6 in portrait and landscape. A successful network load does not by itself mean the layout has passed.

## 5. Stop the test

Press Ctrl+C in the terminal running `start_chaos.sh`. The launcher stops both the cloudflared process and the local Python server.

The temporary URL stops working when the cloudflared process stops.

## 6. VPN behavior

The launcher does not alter Proton VPN, its Kill Switch, DNS settings, routes, or firewall policy. The cloudflared process uses the laptop's existing network routing. If the VPN policy blocks the outbound connection, diagnose the VPN/network configuration; do not disable the Kill Switch just to make this script work.

## 7. Security boundary

A Quick Tunnel URL is public: anyone who has the URL can access the exposed compatibility service while the tunnel is running. A random hostname is not authentication. The probe contains no private match data, but stop it immediately after testing and do not leave it running unnecessarily.

Before tunneling the full game, implement a room invite code, per-player session tokens, strict server-side validation, a four-seat limit, rate limits, and privacy boundaries between each player's private state.

Quick Tunnels are for testing and development, not a production availability guarantee. They support up to 200 in-flight requests and do not support SSE. This project uses XMLHttpRequest polling instead of SSE.
