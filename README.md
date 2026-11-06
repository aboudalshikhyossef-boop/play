# CHAOS FAMILY BATTLE

A high-energy browser-based family party game for exactly four players.

> Trust no one. Revenge everyone.

## Project status

The project is in the compatibility and network-foundation stage. The owner has confirmed that a Cloudflare Quick Tunnel URL successfully opened the compatibility page in iPhone 4S Safari 9.3.6. Actual layout measurements and complete four-device checks are still being recorded.

## Product principles

- Exactly four human players. The Linux Mint laptop is both the authoritative local game host and an ordinary player; it has no gameplay or information advantage.
- One browser-based application for the laptop, two Android phones, and iPhone 4S (iOS 9.3.6).
- The game server and SQLite database stay on the Linux Mint laptop.
- Remote browser access for family sessions uses a temporary Cloudflare Quick Tunnel URL. No Cloudflare account or custom domain is required for Quick Tunnels.
- The tunnel is a transport path only; it does not host game rules, match state, player balances, or the database.
- Arabic-first interface with right-to-left layout.
- Responsive design is a core requirement. The smallest target is 320 CSS pixels wide.
- The complete game scope is planned before implementation. Internal milestones are quality gates, not separate public releases.
- The server is authoritative for actions, timers, randomness, scoring, and outcomes.

## Documentation

- [Game specification](docs/01-GAME-SPEC.md)
- [Responsive UX and visual quality](docs/02-RESPONSIVE-UX.md)
- [Architecture and security](docs/03-ARCHITECTURE-SECURITY.md)
- [Build and verification plan](docs/04-BUILD-PLAN.md)
- [Physical-device compatibility results](docs/05-COMPATIBILITY-RESULTS.md)
- [Superseded hotspot decision](docs/06-HOTSPOT-DECISION.md)
- [Cloudflare Quick Tunnel decision and operation](docs/07-CLOUDFLARE-QUICK-TUNNEL.md)

## Start the compatibility test

Requirements:
- Linux Mint 22.3 (the current host environment).
- Python 3.
- `cloudflared` installed and available on PATH.
- An internet connection on the laptop and player devices.

From the repository root:

```bash
python3 --version
cloudflared --version
bash start_chaos.sh
```

The launcher starts the Python compatibility server on `127.0.0.1:8765`, then starts:

```bash
cloudflared tunnel --url http://127.0.0.1:8765
```

It detects and prints the temporary `https://....trycloudflare.com` URL. Share that same URL with all three other players. The laptop player should open the same public URL in the laptop browser so every device uses the same origin.

Keep the terminal open while the tunnel is in use. Press Ctrl+C to stop both the tunnel and the Python server. The launcher does not create or change a Wi-Fi hotspot, router setting, UFW rule, VPN setting, or port-forwarding rule.

The old command name `bash start_chaos_lan.sh` remains as a compatibility alias and now starts the Cloudflare workflow; it no longer creates a laptop Wi-Fi hotspot.

See [the Cloudflare tunnel guide](docs/07-CLOUDFLARE-QUICK-TUNNEL.md) for setup, limitations, and security notes.

## Target environment

- Host: Linux Mint 22.3 laptop.
- Runtime: Python 3 (installed; record exact version with `python3 --version`).
- Clients: two Android phones and one iPhone 4S running iOS 9.3.6.
- Access: Cloudflare Quick Tunnel to a localhost-only origin.
- Local origin: `http://127.0.0.1:8765/`.
- Compatibility probe: TCP port 8765.

## Important network and security notes

Quick Tunnels create a public URL. Anyone who obtains the URL can access the exposed local service until the tunnel stops. The random URL is not a substitute for authentication. The current compatibility page contains no private game data; stop the tunnel after testing. Before exposing the full game, implement room invite validation, four-seat limits, high-entropy per-player sessions, server-side action validation, request limits, and reconnect controls.

The game server and SQLite database remain on the laptop. The tunnel does not create a cloud database or synchronize multiple copies of the game. The connection from player browsers to Cloudflare uses HTTPS; cloudflared connects back to the local origin through its outbound tunnel. Do not describe this as end-to-end encryption from the browser to the Python process.

Proton VPN is not changed by the launcher. It does not turn off the VPN or bypass its Kill Switch. If the VPN/Kill Switch prevents cloudflared from reaching Cloudflare, the tunnel will fail rather than changing the VPN configuration.

Quick Tunnels are intended for testing and development, have no uptime guarantee, support up to 200 in-flight requests, and do not support Server-Sent Events (SSE). The planned client synchronization uses XMLHttpRequest polling, not SSE. See the official [Cloudflare Quick Tunnel documentation](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

Never commit temporary tunnel URLs, passwords, real invite codes, player session tokens, database files, or personal player data. The repository is currently public.

## Current gate

- [x] Compatibility page opened on the laptop.
- [x] Owner confirmed the Cloudflare Quick Tunnel page opened in iPhone 4S Safari 9.3.6.
- [ ] Confirm the same Quick Tunnel URL on both Android phones.
- [ ] Record viewport dimensions and check portrait/landscape layout on all phones.
- [ ] Verify Arabic text, no horizontal overflow, readable controls, and touch response.
- [ ] Continue with the full game foundation only after the remaining critical compatibility checks are recorded.
