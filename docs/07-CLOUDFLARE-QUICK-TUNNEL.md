# Cloudflare Quick Tunnel — Network Decision and Operations

## Decision

Cloudflare Quick Tunnel is the current remote access path for family testing. The owner confirmed that the test page opened on iPhone 4S Safari 9.3.6 through a temporary Quick Tunnel.

The Python game server and SQLite database remain on the Linux Mint laptop. Cloudflare is a transport path to that one local process; it does not host the game engine or store match state.

## Topology

    Linux Mint laptop
      Python application: 127.0.0.1:8765
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

All four players open the same URL. They do not communicate directly with one another. The single server is authoritative for room state and future game actions.

## Why this path

- The laptop does not need to accept unsolicited inbound connections.
- No router port forwarding or public IP configuration is required.
- No local Wi-Fi hotspot or AP-mode support is required.
- Players can use different internet connections.
- Quick Tunnels do not require a Cloudflare account or custom domain.
- The one local SQLite database remains the source of truth.

This path requires internet access on the laptop and each player device during the session.

## Install cloudflared

Install the package that matches the laptop's Linux architecture and distribution using the official Cloudflare download instructions:

https://developers.cloudflare.com/tunnel/downloads/

Verify:

    cloudflared --version

The project launcher does not install or update cloudflared automatically.

## Start the application and tunnel

From the repository root:

    git pull --ff-only
    bash run_tests.sh
    bash start_chaos.sh

The launcher starts the local application and then runs the equivalent of:

    cloudflared tunnel --url http://127.0.0.1:8765

It extracts and prints the generated HTTPS URL. Share that exact URL with the three other players. The laptop player should open the same public URL in the laptop browser.

The first player creates a room. The app assigns seat 1, creates a 10-character room code, and displays an invitation link. The other players use that code/link to occupy seats 2–4. Room membership and player sessions are stored locally on the laptop.

Keep the terminal open for the entire session. Press Ctrl+C to stop both the tunnel and the local server.

The old command bash start_chaos_lan.sh is retained as a backward-compatible alias and now launches the same Cloudflare path. It does not start a Wi-Fi access point.

## Proton VPN

The project launcher does not modify Proton VPN, its Kill Switch, DNS settings, firewall, or routing table. cloudflared uses the existing operating-system network path. The owner has confirmed that their manual Quick Tunnel test worked while using their VPN setup.

If VPN or Kill Switch policy blocks the outbound tunnel, diagnose that normally. Do not disable the Kill Switch or add a bypass just to make the game work.

## Quick Tunnel limitations

Quick Tunnels are intended for testing and development:
- The hostname is randomly generated and changes when a new tunnel is created.
- The URL stops working when the cloudflared process stops.
- There is no uptime guarantee.
- Each Quick Tunnel supports up to 200 in-flight requests.
- Server-Sent Events (SSE) are not supported.

The lobby therefore uses XMLHttpRequest polling rather than SSE. Current polling is approximately every 1.6 seconds per active client. A permanent/public deployment needs a separately reviewed named-tunnel or hosting design.

## Security

Anyone who obtains a Quick Tunnel URL can access the service exposed through it while the tunnel is active. The random URL is not authentication.

The current lobby adds:
- A random room invite code separate from player sessions.
- Exactly four seats per room.
- Separate high-entropy player sessions.
- Secure, HttpOnly, SameSite cookies for HTTPS browsers.
- Session ownership checks on room state and mutations.
- Request-size validation, Origin checks, and basic rate limits.

The /compatibility page and its diagnostic message feed are intentionally unauthenticated and must not be used for private game data. Disable/remove that diagnostic endpoint before broader exposure.

Browser-to-Cloudflare traffic uses HTTPS. cloudflared maintains an encrypted outbound tunnel to the laptop. This should not be described as end-to-end encryption that prevents Cloudflare's edge from processing requests.

## Runtime data

The database is stored outside the repository by default in the user's local application data directory. The tunnel URL, session cookies/tokens, room invite codes, logs, and player data must not be committed. The repository is public.

## Verification

- [x] Owner-confirmed Quick Tunnel page load on iPhone 4S Safari 9.3.6.
- [x] Local API and room-store test suite passed in the development container.
- [ ] Run the updated project on the Linux Mint laptop.
- [ ] Open the same Quick Tunnel URL on both Android phones and the iPhone.
- [ ] Verify room creation, all four seats, readiness polling, refresh recovery, and leave.
- [ ] Verify that a phone's diagnostic message appears on the laptop's /compatibility page.
- [ ] Recheck iPhone 4S portrait and landscape layout.

## Official references

- Cloudflare Quick Tunnels: https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/
- cloudflared downloads: https://developers.cloudflare.com/tunnel/downloads/
