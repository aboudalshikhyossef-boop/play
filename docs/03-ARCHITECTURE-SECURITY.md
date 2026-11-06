# Architecture and Network Security

## 1. Deployment model

The Linux Mint 22.3 laptop runs one authoritative Python application server and one SQLite database. The laptop owner also plays from an ordinary browser session as player 1; creating a room does not grant match powers or access to other players' private information.

Three additional clients join from two Android phones and an iPhone 4S / iOS 9.3.6. All four browsers communicate with the same server and the same database. There are no per-device game databases and no client-side authority for balances or outcomes.

## 2. Network topology — Cloudflare Quick Tunnel

1. Python binds only to 127.0.0.1:8765 on the laptop.
2. cloudflared opens an outbound tunnel connection to Cloudflare.
3. Cloudflare provides a temporary random trycloudflare.com HTTPS URL.
4. All four player browsers open that same URL.
5. Requests travel through the tunnel to the single local Python process.

The server does not bind to 0.0.0.0 or a LAN address. No router port forwarding, public IP configuration, local laptop hotspot, or inbound UFW exception is required for this tunnel path. All devices require internet access during the session.

## 3. Application stack

- Python 3 standard library HTTP server using ThreadingHTTPServer.
- SQLite from Python's standard library.
- Browser UI: semantic HTML, locally bundled CSS, and conservative JavaScript.
- Browser requests: same-origin XMLHttpRequest.
- Lobby synchronization: short polling, currently about 1.6 seconds per active browser.
- No third-party Python package or remote CDN is required for the current foundation.

This keeps the first implementation dependency-light and compatible with the installed Linux Mint Python environment. Any future package addition must be pinned and tested against the actual Python version.

## 4. One source of truth

- One Python process owns room membership, seat assignments, player readiness, session identity, and all future match state.
- One SQLite database stores room, player, and hashed session records.
- Clients submit intents; the server validates them.
- Public lobby state is the same for everyone, while session ownership identifies the current player.
- The future match API must return each player only their permitted private state.
- Future action requests need unique request IDs so retries after interruption cannot apply one action twice.
- Future match updates need monotonic revisions so browsers can detect stale state.

## 5. Room and player foundation

- Room codes are generated randomly and contain 10 characters from a 32-character alphabet.
- A room has exactly four seats.
- The room creator occupies seat 1 but has no extra game authority.
- Each browser receives a separate high-entropy session token in a Secure, HttpOnly, SameSite cookie.
- The raw token is not returned in JSON and is not stored in SQLite; only its SHA-256 hash is stored.
- A browser refresh recovers its existing player seat through the session endpoint.
- A fifth player is rejected.
- Duplicate names in the same room are rejected case-insensitively.
- Room membership and seat allocation use SQLite immediate transactions to avoid concurrent overbooking.
- Rooms expire after 24 hours; a player who disconnects temporarily retains their seat.

## 6. API and validation

The initial API supports health, room creation, joining, current-session recovery, room-state retrieval, ready-state changes, and leave/revocation. Room reads and mutations require the session cookie.

- JSON request bodies are capped at 8 KiB.
- Names are normalized and limited to 18 characters.
- Player names are rendered as text, never interpreted as HTML.
- Mutating requests are rejected when a supplied Origin does not match the request host.
- No CORS access is enabled.
- Room creation is rate-limited to five attempts per ten minutes; room joins to fifteen attempts per minute per client address.
- The rate limiter uses the Cloudflare connecting-IP header when present; arbitrary X-Forwarded-For values are not trusted.

The /compatibility diagnostic feed is intentionally unauthenticated and ephemeral. It is for network testing only, has no private match information, and must be removed or disabled before broader public exposure.

## 7. Proton VPN interaction

The launcher does not modify Proton VPN, its Kill Switch, DNS, routing table, or firewall. cloudflared uses the operating system's existing network route. If VPN policy blocks the outbound tunnel, the launcher reports a failure; it must not disable protections or attempt to bypass them.

## 8. Security boundaries

- A Quick Tunnel URL is public. Anyone who obtains the URL can reach the exposed service while the tunnel is active.
- The random URL is not authentication.
- The room invite code is separate from each player's browser session.
- Never expose debug consoles, admin operations, file browsing, or raw database downloads through the tunnel.
- The browser-to-Cloudflare leg uses HTTPS, and cloudflared maintains an encrypted outbound tunnel to the laptop. This is not end-to-end encryption that prevents Cloudflare's edge from processing requests.
- Do not commit cookies, tokens, invite codes, tunnel URLs, logs, databases, or player data.

Before the full game is used with private match information, finish the complete authorization/privacy review for all game endpoints.

## 9. SQLite storage and recovery

The database is stored outside the repository by default:

    ~/.local/share/chaos-family/chaos.sqlite3

The application creates its own data directory with restrictive permissions and attempts to set the database file to owner-only permissions. A custom database path does not cause permissions on its parent folder to be modified.

SQLite uses foreign keys, a busy timeout, and WAL journaling. Each request uses a separate connection. Seat allocation is transactional. The game engine will extend this schema in a later stage for match state, actions, coin ledger, events, and challenge outcomes.

## 10. Operational checklist

- Confirm Python 3 and cloudflared are installed.
- Run bash run_tests.sh.
- Run bash start_chaos.sh.
- Share the printed HTTPS URL with all four devices.
- Create one room and share its invite link/code.
- Keep the terminal open during the session.
- Press Ctrl+C to stop the tunnel and server.
- Never commit runtime data or secrets.

