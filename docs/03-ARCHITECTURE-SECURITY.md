# Architecture and Local-Network Security

## 1. Deployment model

The Linux Mint laptop runs the game server, creates the private Wi-Fi access point, and also opens the ordinary player interface for its owner. Three other clients join from two Android phones and the iPhone 4S.

The home router is not part of the gameplay network. The laptop's Wi-Fi adapter provides the local access point and the laptop serves the web application. No public hosting, cloud services, or internet connection is required during a match.

## 2. Laptop-hosted hotspot

The intended network profile is:
- NetworkManager-managed Wi-Fi access point.
- SSID: `CHAOS-FAMILY`.
- 2.4 GHz band for compatibility with iPhone 4S.
- WPA2-Personal / WPA-PSK with RSN/CCMP.
- IPv4 shared mode, with the laptop at `10.42.0.1/24`.
- DHCP/DNS supplied by NetworkManager to joined devices.
- Game server bound only to `10.42.0.1`.

The startup script checks that the Wi-Fi hardware/driver advertises AP mode before activating the profile. Not every laptop adapter supports AP mode. If it does not, use a compatible USB Wi-Fi adapter or retain a router-based LAN as a fallback.

When one Wi-Fi adapter changes from client mode to AP mode, it may disconnect from the home Wi-Fi. That is expected; the match does not require internet access. A separate Ethernet uplink is optional.

See [the hotspot decision record](06-HOTSPOT-DECISION.md).

## 3. Proposed stack

Initial choices, subject to compatibility verification:
- Front end: semantic HTML, CSS, and conservative JavaScript compatible with iOS 9 Safari.
- Local server: Python 3 with a small HTTP application; Flask is the current proposal.
- Serving: a WSGI server compatible with the selected Python environment; Waitress is the current proposal.
- Storage: SQLite.
- Client/server messages: JSON over same-origin HTTP requests using XMLHttpRequest.
- Synchronization: short-interval polling initially; consider WebSocket only if real-device testing demonstrates a need.
- Assets: bundled locally; no external CDN dependency.

Pin and document tested dependency versions after checking the actual Linux Mint and Python versions. Do not assume newest package releases support the installed environment.

## 4. Server-authoritative model

The server is the single source of truth for player seats and sessions, match and round state, timers and deadlines, secret action submissions, random event selection, coin balances, action eligibility and costs, revenge charges and outcomes, and public/private information.

Clients submit requested actions, not claimed outcomes or balances. The server validates every request and calculates all results.

Each action should include a unique request identifier so retries after network interruption do not apply the same action twice. State updates should carry a monotonically increasing revision or sequence number so clients can detect stale state.

## 5. Local invitation flow

1. Host starts the local hotspot and server.
2. The server binds only to `10.42.0.1`.
3. Host creates a match and receives a random, short-lived invite code.
4. Application creates a LAN URL containing the hotspot address, port, and invite code.
5. Other players join the saved `CHAOS-FAMILY` network and open the invitation link.
6. Each player claims one available seat and receives a private session token.
7. Four players join and ready up; only then can the match begin.

The Wi-Fi password and game invite code are different things: the former joins the private network; the latter joins a game room. Neither is to be committed to Git. Rate-limit game invite attempts, expire unused invitations, and validate seat/session ownership.

## 6. Firewall and network boundary

- Do not configure router port forwarding.
- Do not use public tunnels or reverse proxies.
- Keep the server bound to `10.42.0.1`, not every interface.
- Do not disable UFW.
- If UFW is active, allow only the required TCP game port from `10.42.0.0/24` on the Wi-Fi AP interface.
- Do not expose a general-purpose admin endpoint to player clients.
- Stop the hotspot when the family session is finished.

NetworkManager shared mode supplies client addressing and may NAT traffic to a current default uplink if one exists. The game itself only needs local access to the server; internet sharing is not a game requirement.

HTTP on the hotspot is not encrypted. WPA2 protects access to the Wi-Fi network but does not encrypt HTTP requests after a device has joined. Only share the Wi-Fi password with trusted players.

## 7. Session and input safety

- Generate high-entropy session tokens on the server.
- Keep tokens out of public lobby state, logs, screenshots, and repository files.
- Use appropriate cookie flags where supported and validate session ownership on every action.
- Validate all input server-side: player name length, action, target, amount, phase, deadline, and request ID.
- Escape player-supplied names and text before rendering; prevent HTML/script injection.
- Apply request size limits and rate limits.
- Do not trust client clocks.
- Avoid storing unnecessary personal information.
- Provide a clear way to reset local match data.

## 8. Data storage

SQLite stores only what the game needs: match state/history, player display names and selected avatars/colors, coin ledger and action results, event/challenge references, and minimal session data required for reconnect.

Do not commit database files, real player history, session tokens, invite codes, hotspot passwords, or local configuration to Git.

## 9. Public repository hygiene

The repository is public at the time of writing. Never commit secrets or real local network addresses. Include .gitignore before implementation. Keep runtime database, logs, and local hotspot credentials outside tracked source files. Use example configuration with placeholders only. Review changes before pushing. Do not put personal details in test fixtures.

## 10. Recovery and lifecycle

Persist enough state to recover from browser refresh or temporary Wi-Fi interruption. Reconnect must restore the correct player seat without duplicating the player. The server decides whether a deadline elapsed while a client was disconnected. Define host shutdown and graceful match termination. Do not silently resume a stale match after deliberate reset.

The hotspot profile and locally generated Wi-Fi password persist between sessions so trusted devices can remember the network. The hotspot itself is activated only when the game startup command is run and is stopped explicitly after testing or playing.

## 11. Operational checks

Before each play session:
- Confirm the laptop Wi-Fi adapter supports AP mode.
- Start the CHAOS hotspot using the project startup script.
- Confirm the hotspot IP is `10.42.0.1/24`.
- Connect all three phones to `CHAOS-FAMILY`.
- Confirm the server is bound only to `10.42.0.1`.
- Confirm firewall scope and no router port-forwarding rule.
- Confirm all four devices can reach the local page.
