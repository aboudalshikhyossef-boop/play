# Room and Lobby Foundation

## Status

The first real application foundation is implemented. It replaces the one-way echo demonstration with a central room service and a synchronized three-or-four-player lobby. The first authoritative eight-round match engine is now implemented in addition to the lobby. The complete challenge library and event catalogue remain later work.

## One server, one database

- One Python process runs on the Linux Mint laptop.
- One SQLite database stores rooms, players, readiness, and session hashes.
- Every browser talks to that same process through the Cloudflare Quick Tunnel.
- The laptop's player is simply seat 1. Creating the room grants no gameplay power or special information.
- The database is stored outside the repository in the user's local application-data directory.

Default database location:

    ~/.local/share/chaos-family/chaos.sqlite3

The application creates its own data folder with restricted permissions and attempts to keep the database file readable only by its owner. A custom database path does not cause permissions on the caller's parent directory to be changed.

## Room rules

- A room has a maximum of up to four seats; three or four players may start a match.
- The creator automatically occupies one seat.
- Invite codes contain 10 characters from an alphabet that avoids visually ambiguous characters.
- Duplicate player names are rejected within a room, ignoring case.
- A fifth player receives a room-full response.
- The lobby becomes startable when three or four occupied players are all connected and ready.
- A room is considered available for 24 hours from creation.
- A player who leaves releases their seat; the room code remains usable until expiry.
- Disconnected players retain their seat so a temporary network interruption does not create a duplicate player.
- The connection indicator is based on recent server activity, not a client-side claim.
- All three or four occupied players must be recently connected and ready before the lobby reports all-ready.

The authenticated start-match endpoint is available when three or four players are connected and ready. The match engine freezes room membership until the match finishes.

## Session model

On room creation or successful join, the server generates a high-entropy random session token. It is issued to the browser in a Secure, HttpOnly, SameSite cookie. The raw token is not returned in the JSON response and is not stored in SQLite; only its SHA-256 hash is stored.

The cookie is automatically sent by the browser on same-origin requests. Refreshing the page calls the session-recovery endpoint and restores the same player seat. The session cookie is scoped to the temporary HTTPS origin and expires after seven days. A deliberate leave revokes the session and clears the cookie.

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | /api/health | Server health and Python version |
| POST | /api/rooms | Create a room and occupy seat 1 |
| POST | /api/rooms/CODE/join | Join a room and reserve one seat |
| GET | /api/me | Restore the current browser session |
| GET | /api/rooms/CODE | Read authenticated lobby state |
| POST | /api/rooms/CODE/ready | Set the current player's ready state |
| POST | /api/rooms/CODE/leave | Release the seat and revoke the session (blocked during an active match) |
| POST | /api/rooms/CODE/start | Start an 8-round match with 3 or 4 ready players |
| GET | /api/rooms/CODE/match | Read the authenticated match state |
| POST | /api/rooms/CODE/match/action | Submit one private round action |
| POST | /api/rooms/CODE/match/revenge | Submit one eligible revenge decision |

Room endpoints require the session cookie. The room response includes public player names, seat numbers, colors, avatars, ready state, and connection state. It does not contain session tokens.

## Synchronization

- The browser uses XMLHttpRequest, not Fetch, so it remains compatible with the legacy Safari target.
- Each active lobby polls its room state approximately every 1.6 seconds.
- Once a match starts, lobby clients detect the match automatically and switch to the match arena.
- Match clients poll the current match state approximately every 1.4 seconds.
- Requests update the server-side last-seen time for the authenticated player.
- SQLite transactions use an immediate write lock when assigning seats, preventing concurrent joins from reserving the same seat or exceeding four players.
- Player names are rendered with text nodes, not interpreted as HTML.
- Room creation and join attempts are rate-limited.

## Compatibility message probe

The temporary page at /compatibility is a diagnostic tool, not part of the final game UI. The old echo request merely returned a message to the device that sent it. The replacement diagnostic flow publishes a message into the server's in-memory feed. Each open diagnostic page polls that feed, so a phone's message appears on the laptop when the laptop also has the diagnostic page open. The server terminal also prints a short received-message line.

This test feed is intentionally ephemeral and is cleared when the server process stops. It is not game chat and is not stored in SQLite. The diagnostic message endpoint is not authenticated; do not use it for private game content, and disable or remove it before a broader public deployment.

## Security boundaries

- The server binds only to loopback by default.
- Cloudflare Quick Tunnel is the only remote ingress in the current setup.
- The random Cloudflare URL is not authentication.
- Room invite codes are separate from per-player sessions.
- Cross-origin mutation requests with a mismatched Origin are rejected when the browser sends that header.
- JSON request bodies are limited to 8 KiB.
- Room creation is limited to five attempts per ten minutes per client address; joins are limited to fifteen attempts per minute.
- The client IP key uses Cloudflare's connecting-IP header when present and does not trust arbitrary X-Forwarded-For values.
- No CORS access is enabled.
- Do not commit the SQLite database, session tokens, real invite codes, logs, or tunnel URL.

## Verification

The initial match engine is documented in [09-MATCH-ENGINE-RULES.md](09-MATCH-ENGINE-RULES.md).

Automated tests cover server health and static routes, shared diagnostic messages, room creation, cookie flags, session recovery, four distinct seats, rejection of a fifth player, the three-player start threshold, readiness, leave/rejoin, duplicate names, invalid inputs, cross-origin rejection, rate limiting, and concurrent seat allocation.

Run:

    bash run_tests.sh

Physical testing is still required on the actual iPhone 4S Safari 9.3.6 and both Android phones. Automated tests cannot prove legacy-browser layout or Cloudflare behavior on the owner's devices.
