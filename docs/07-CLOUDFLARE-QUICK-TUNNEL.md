# Cloudflare Quick Tunnel — Network Decision and Operations

## Decision

Cloudflare Quick Tunnel is the selected remote access path for family testing after direct LAN/hotspot access failed on the physical devices. The owner confirmed that the temporary Cloudflare URL opened successfully in iPhone 4S Safari 9.3.6.

The game server and SQLite database stay on the Linux Mint laptop. Cloudflare provides a temporary HTTPS path to that one local server; it does not host game logic or store the match.

## Topology

```text
Linux Mint laptop
  Python game server: 127.0.0.1:8765
  SQLite database: local disk
  cloudflared process
        |
        | outbound encrypted tunnel
        v
Cloudflare edge
  temporary HTTPS URL: https://....trycloudflare.com
        |
        +---- laptop player browser
        +---- Android player 2
        +---- Android player 3
        +---- iPhone 4S player 4
```

All four players open the same URL. Player browsers do not connect directly to each other. The single server is authoritative for every action and balance.

## Why this path

- The laptop does not need to accept unsolicited inbound connections.
- No router port-forwarding or public IP configuration is required.
- No local Wi-Fi hotspot or special AP-mode support is required.
- Players can use different internet connections.
- The player devices do not need to be on the same LAN.
- Quick Tunnels do not require a Cloudflare account or custom domain.

This path does require internet access on the laptop and each player device during the session.

## Install cloudflared

Install the package matching the laptop's Linux architecture and distribution by following the [official Cloudflare download instructions](https://developers.cloudflare.com/tunnel/downloads/).

Verify:

```bash
cloudflared --version
```

The project launcher does not install or update cloudflared automatically.

## Start

From the repository root:

```bash
bash start_chaos.sh
```

The launcher starts the local server and then runs the equivalent of:

```bash
cloudflared tunnel --url http://127.0.0.1:8765
```

It extracts and prints the generated HTTPS URL. Share the exact URL with the three other players. The laptop player should open that same URL in the laptop browser.

Keep the terminal open for the entire session. Press Ctrl+C to stop both the tunnel and the local server.

The old command:

```bash
bash start_chaos_lan.sh
```

is retained as a backward-compatible alias and now invokes the Quick Tunnel launcher. It does not start a Wi-Fi access point.

## Proton VPN

The project launcher does not modify Proton VPN, its Kill Switch, DNS settings, firewall, or routing table. cloudflared uses the existing operating-system network path. The owner has tested the tunnel while Proton VPN was in use.

If the VPN or Kill Switch blocks the outbound connection, diagnose that policy normally. Do not disable the Kill Switch or add a bypass just to make the game work. The launcher reports a startup failure rather than changing VPN protection.

## Important Quick Tunnel limitations

Quick Tunnels are intended for testing and development:
- The hostname is randomly generated and changes when a new tunnel is created.
- The URL stops working when the cloudflared process stops.
- There is no uptime guarantee.
- Each Quick Tunnel supports up to 200 in-flight requests.
- Server-Sent Events (SSE) are not supported.

The client synchronization plan therefore uses XMLHttpRequest polling, not SSE. A future permanent/public deployment needs a separately reviewed named-tunnel or hosting design.

## Security

Anyone who obtains a Quick Tunnel URL can access the service exposed through it while the tunnel is running. The random URL is not authentication. Do not expose the full game until the application has:
- A high-entropy room invite code with expiry and attempt limits.
- Exactly four seats per room.
- Separate high-entropy sessions for each player.
- Server-side ownership checks on every action and state request.
- Player-specific private state and delayed public reveal.
- Request-size and rate limits.
- No debug, admin, or filesystem endpoints reachable by players.

The compatibility probe currently has no private match information. Stop its tunnel promptly after testing.

Browser-to-Cloudflare traffic uses HTTPS. cloudflared maintains an encrypted outbound tunnel to the laptop. This should not be described as end-to-end encryption that prevents Cloudflare's edge from processing requests.

## Runtime data

The tunnel URL, logs, tokens, match state, and SQLite database must not be committed. The launcher creates a permission-restricted temporary directory for its logs and removes it when it exits. Store the eventual game database outside the repository and retain only safe example configuration in Git.

## Verification

- [x] Quick Tunnel opened the compatibility page on iPhone 4S Safari 9.3.6 (owner-confirmed).
- [ ] Open the same tunnel URL on both Android phones.
- [ ] Verify GET ping and POST echo from each device.
- [ ] Test reconnect after briefly disconnecting one phone.
- [ ] Test that Ctrl+C stops the Python server and cloudflared process.
- [ ] Repeat Safari portrait/landscape layout checks after the game UI exists.

## Official references

- [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)
- [cloudflared downloads](https://developers.cloudflare.com/tunnel/downloads/)
