# Architecture and Local-Network Security

## 1. Deployment model
The Linux Mint laptop runs the game server and also opens the ordinary player interface for its owner. Three other clients join from two Android phones and the iPhone 4S.

The router provides local network connectivity only. The game does not require public hosting, cloud services, or internet access during a match.

## 2. Proposed stack
Initial choices, subject to compatibility verification:
- Front end: semantic HTML, CSS, and conservative JavaScript compatible with iOS 9 Safari.
- Local server: Python 3 with a small HTTP application; Flask is the current proposal.
- Serving: a WSGI server compatible with the selected Python environment; Waitress is the current proposal.
- Storage: SQLite.
- Client/server messages: JSON over same-origin HTTP requests using XMLHttpRequest.
- Synchronization: short-interval polling initially; consider WebSocket only if real-device testing demonstrates a need.
- Assets: bundled locally; no external CDN dependency.

Pin and document tested dependency versions after checking the actual Linux Mint and Python versions. Do not assume newest package releases support the installed environment.

## 3. Server-authoritative model
The server is the single source of truth for player seats and sessions, match and round state, timers and deadlines, secret action submissions, random event selection, coin balances, action eligibility and costs, revenge charges and outcomes, and public/private information.

Clients submit requested actions, not claimed outcomes or balances. The server validates every request and calculates all results.

Each action should include a unique request identifier so retries after network interruption do not apply the same action twice. State updates should carry a monotonically increasing revision or sequence number so clients can detect stale state.

## 4. Local invitation flow
1. Host starts the local server.
2. Server binds only to the laptop's selected LAN IPv4 address, not all interfaces by default.
3. Host creates a match and receives a random, short-lived invite code.
4. Application creates a LAN URL containing the host LAN address, port, and invite code.
5. Other players open the link while connected to the same home LAN.
6. Each player claims one available seat and receives a private session token.
7. Four players join and ready up; only then can the match begin.

The invite URL is a convenience, not a security boundary. Rate-limit attempts, expire unused invitations, and validate seat/session ownership.

## 5. Network boundary and firewall
- Do not configure router port forwarding for the game.
- Do not use public tunnels or reverse proxies.
- Bind the server to the intended private LAN interface/address.
- Configure UFW to allow the game port only from the trusted home subnet/interface as appropriate.
- Do not expose a general-purpose admin endpoint to player clients.
- Use a stable DHCP reservation for the laptop if desired.
- Confirm Wi-Fi client isolation is disabled on the trusted home network.
- Do not assume the same SSID guarantees peer-to-peer connectivity.

A LAN-only HTTP service is not encrypted. Use it only on a trusted home network. Do not put passwords or sensitive personal data in game requests. Reassess transport security if the threat model changes.

## 6. Session and input safety
- Generate high-entropy session tokens on the server.
- Keep tokens out of public lobby state, logs, screenshots, and repository files.
- Use appropriate cookie flags where supported and validate session ownership on every action.
- Validate all input server-side: player name length, action, target, amount, phase, deadline, and request ID.
- Escape player-supplied names and text before rendering; prevent HTML/script injection.
- Apply request size limits and rate limits.
- Do not trust client clocks.
- Avoid storing unnecessary personal information.
- Provide a clear way to reset local match data.

## 7. Data storage
SQLite stores only what the game needs: match state/history, player display names and selected avatars/colors, coin ledger and action results, event/challenge references, and minimal session data required for reconnect.

Do not commit database files, real player history, session tokens, invite codes, or local configuration to Git.

## 8. Public repository hygiene
The repository is public at the time of writing. Never commit secrets or real local network addresses. Include .gitignore before implementation. Keep runtime database and logs outside tracked source files. Use example configuration with placeholders only. Review changes before pushing. Do not put personal details in test fixtures.

## 9. Recovery and lifecycle
Persist enough state to recover from browser refresh or temporary Wi-Fi interruption. Reconnect must restore the correct player seat without duplicating the player. The server decides whether a deadline elapsed while a client was disconnected. Define host shutdown and graceful match termination. Do not silently resume a stale match after deliberate reset.

## 10. Operational checks
Before each play session:
- Confirm laptop is on the trusted home LAN.
- Confirm server is bound to the expected LAN address.
- Confirm firewall rule scope.
- Confirm no router port-forwarding rule exists for the game.
- Confirm four devices can reach the local page.
- Confirm laptop local IP and invite link are current.
