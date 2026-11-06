# Architecture and Network Security

## 1. Deployment model

The Linux Mint 22.3 laptop runs one authoritative Python game server and one SQLite database. The same laptop is also player 1 using the ordinary player interface; it has no referee role or privileged game information.

Three other clients join from two Android phones and the iPhone 4S / iOS 9.3.6. All four browsers connect to the same game server. There is no per-device game database and no client is responsible for calculating authoritative balances or outcomes.

## 2. Network topology — Cloudflare Quick Tunnel

The selected connection path is:

1. Python listens only on `127.0.0.1:8765` on the laptop.
2. `cloudflared` opens an outbound connection from the laptop to Cloudflare.
3. Cloudflare assigns a temporary random `trycloudflare.com` HTTPS address.
4. All four players open the same URL in their browsers.
5. Requests travel through the tunnel to the single local Python process.

The game server is not bound to `0.0.0.0` or a LAN address by default. The laptop does not accept direct inbound connections from the home router or the public internet. No router port forwarding, public IP, local Wi-Fi hotspot, or UFW inbound exception is required for the tunnel path.

All player devices and the laptop need internet connectivity while using the Quick Tunnel. The devices do not need to be connected to the same Wi-Fi network.

## 3. One source of truth and synchronization

- One Python process owns the match state.
- One SQLite database on the laptop persists match state, coin ledger, actions, and minimal reconnect/session information.
- Every client communicates with that same process through same-origin HTTP endpoints.
- Clients submit intentions; the server validates and resolves actions.
- The server publishes public match state and only the requesting player's private state.
- No Cloudflare database or client-side database synchronization is involved.

Each action must include a unique request identifier so retries after network interruption cannot apply the same action twice. State updates carry a monotonically increasing revision or sequence number so clients can detect stale state. Reconnect restores the existing seat and session without duplicating a player.

## 4. Proposed application stack

Initial choices, subject to compatibility verification:
- Front end: semantic HTML, CSS, and conservative JavaScript compatible with iOS 9 Safari.
- Local server: Python 3 with a small HTTP application; Flask is the current proposal.
- Serving: a WSGI server compatible with the selected Python environment; Waitress is the current proposal.
- Storage: SQLite stored on the laptop only.
- Client/server messages: JSON over same-origin HTTP requests using XMLHttpRequest.
- Synchronization: short-interval polling initially; do not depend on Server-Sent Events because Quick Tunnels do not support SSE.
- Assets: bundled locally; no external CDN dependency for the game UI.

Pin and document tested dependency versions after checking the actual Linux Mint and Python versions. Do not assume newest package releases support the installed environment.

## 5. Quick Tunnel lifecycle

The command `bash start_chaos.sh`:
- Starts the compatibility/game HTTP origin at `127.0.0.1:8765`.
- Starts `cloudflared tunnel --url http://127.0.0.1:8765`.
- Extracts and prints the temporary HTTPS URL.
- Keeps both processes alive in the foreground.
- Stops both children when the user presses Ctrl+C or the launcher exits.

The old command `bash start_chaos_lan.sh` is a backward-compatible alias to the same Quick Tunnel launcher. It does not start a Wi-Fi access point.

Quick Tunnel hostnames are temporary and change when a new tunnel is created. The tunnel only exists while the cloudflared process is running. Quick Tunnels have no uptime guarantee, support up to 200 in-flight requests, and do not support SSE. They are intended for testing and development. A permanent or production deployment would require a different reviewed design, such as a named Cloudflare Tunnel.

## 6. Proton VPN interaction

The launcher does not modify Proton VPN, its Kill Switch, DNS, routing table, or firewall. cloudflared uses the operating system's existing network route. If the VPN or Kill Switch blocks the outbound tunnel, the launcher reports the failure; it must not disable protections or attempt to bypass the VPN.

## 7. Security boundaries

- A Quick Tunnel URL is public. Anyone who obtains the URL can reach the exposed service while the tunnel is active.
- The random URL is not authentication and must not be treated as a secret room password.
- The current compatibility probe contains no private game state; stop its tunnel after testing.
- Before exposing the full game, require a room invite code with adequate entropy and expiry, limit each room to four seats, issue separate high-entropy player session tokens, validate session ownership on every request, rate-limit join/action endpoints, and make private state player-specific.
- Never expose a debug console, filesystem browser, admin endpoint, or raw database through the tunnel.
- Use request-size limits and safe error responses.
- Do not put session tokens, real invite codes, tunnel URLs, database files, or player data into Git or logs.

The public browser-to-Cloudflare leg uses HTTPS. cloudflared uses an encrypted outbound tunnel back to the laptop. This is not end-to-end encryption that prevents Cloudflare's edge from processing the browser request; do not describe it as such.

Quick Tunnel can be accessed without a Cloudflare account. It is a temporary development ingress, not a substitute for application authentication or a production access policy.

## 8. SQLite storage and recovery

SQLite remains on the laptop. Store it in an OS-appropriate local data directory outside the repository. Keep backups and logs out of Git. Persist enough state to recover from browser refresh or a temporary client disconnect. The server decides whether a deadline elapsed while a client was disconnected. Define graceful host shutdown and deliberate match reset behavior.

## 9. Public repository hygiene

The repository is public. Never commit secrets, tunnel URLs, player session tokens, room invite codes, local database files, player history, or local configuration. Use `.gitignore` for runtime data and local settings. The launcher stores its temporary logs under a private temporary directory and deletes them on exit.

## 10. Operational checklist

Before each test/play session:
- Confirm Python 3 and cloudflared are installed.
- Confirm the laptop and player devices have internet access.
- Run `bash start_chaos.sh`.
- Share the generated HTTPS URL with the other three players.
- Open that same URL on the laptop and all phones.
- Keep the launcher terminal open for the entire session.
- Stop with Ctrl+C when finished.
- Confirm no tunnel or local server process remains after stopping.
