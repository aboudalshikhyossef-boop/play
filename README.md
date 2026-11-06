# CHAOS FAMILY BATTLE

A fast, chaotic browser-based family game for three or four players.

> Trust no one. Revenge everyone.

## Current project status

The owner reports that the game now runs across the connected laptop and phones, including the iPhone 4S / iOS 9.3.6 Safari. The current match arena has been used successfully on those devices; detailed orientation and edge-case acceptance remains tracked separately.

The first real application foundation is now in the repository:
- One authoritative Python server on the Linux Mint laptop.
- One SQLite database on that laptop.
- Three-or-four-player room creation and joining.
- Separate browser sessions and recovery after refresh.
- Lobby polling and synchronized player/ready states.
- A responsive Arabic RTL lobby interface built with conservative JavaScript and CSS.
- Automated tests for room capacity, sessions, security checks, and concurrent joins.

**The eight-round match engine now includes a real challenge phase and the first chaos expansion.** Each round opens with one of eight Arabic family-friendly multiple-choice challenges (25 seconds; +2 coins for a correct answer, no penalty for a wrong or missing answer). Answers remain private until everyone answers or time expires. The round then proceeds to secret steal, guard, wager, or pass choices, followed by reveal and bounded revenge. Five server-selected event cards also modify later rounds. Remaining work includes bluff/trap actions, the larger event catalogue (Black Box, Bomb, Temporary King, Auction, Court), broader challenge families, comeback tuning, match statistics, and the final visual/audio layer.

## Fixed product requirements

- Three or four human players; four is the maximum and three is enough to start.
- Linux Mint laptop is player 1 and the authoritative server, not a referee or privileged player.
- Two Android phones and one iPhone 4S running iOS 9.3.6.
- Arabic-first interface with right-to-left layout.
- Minimum supported width: 320 CSS pixels.
- No clipped text, overlapping elements, hidden controls, or horizontal overflow.
- Legacy client code uses XMLHttpRequest and avoids Fetch API and CSS Grid.
- Internal development milestones are quality gates, not separate public game releases.

## Network and data model

The Python server binds to 127.0.0.1:8765. Cloudflare Quick Tunnel publishes a temporary HTTPS URL for the players. All four browsers open that same URL.

Cloudflare is only a transport path. The game rules, room data, sessions, and SQLite database remain on the laptop. There is one shared database, not a separate game copy on every phone.

The default database path is outside the repository:

    ~/.local/share/chaos-family/chaos.sqlite3

No router port forwarding, Wi-Fi hotspot, or public game hosting is required. The laptop and phones need internet access while a Quick Tunnel is active.

## Quick start on Linux Mint

Requirements:
- Python 3.
- cloudflared installed and available on PATH.
- Internet access for the laptop and player devices.

From the repository directory:

    git pull --ff-only
    python3 --version
    cloudflared --version
    bash run_tests.sh
    bash start_chaos.sh

The launcher starts the local Python server and Cloudflare Quick Tunnel, then prints a temporary URL similar to:

    https://random-words.trycloudflare.com

Keep the terminal open. Open that same URL on the laptop and all three phones.

The first player enters a name and creates a room. The page shows a 10-character room code and a shareable invitation link. Two or three more players can join. The match starts when all three or four participants are connected and ready; a fourth player is optional.

Press Ctrl+C in the launcher terminal to stop both the tunnel and the local server.

The older command bash start_chaos_lan.sh remains as a compatibility alias. It no longer creates a Wi-Fi hotspot; it launches the same Cloudflare flow.

## Compatibility diagnostics

Open /compatibility on the same temporary URL to test:
- Screen width and height.
- Arabic/RTL layout and horizontal overflow.
- Touch input.
- A shared message feed.

The old echo test returned a message only to the phone that sent it. The corrected test stores the message in the server's temporary in-memory feed. Open /compatibility on the laptop too; messages submitted from a phone then appear in the laptop's feed and in the server terminal.

The diagnostic feed is not chat and is not stored in the game database.

## Tests

Run the automated suite with:

    bash run_tests.sh

The suite covers:
- Creating a room and assigning the first seat.
- Three-player and four-player match starts, four distinct seats, and rejection of a fifth player.
- Duplicate and invalid names.
- Ready-state aggregation.
- Session recovery and revocation on leave.
- Concurrent join attempts.
- Shared diagnostic message delivery through the server feed.
- Three/four-player match start, ready validation, and active-room membership lock.
- Private challenge answers, challenge rewards and timeouts, secret action privacy, action locking, guard, steal, wager, counterstrike revenge, round-event effects and persistence, deadlines, and full eight-round lifecycle.
- HTTP API, cookie flags, origin rejection, and rate limits.
- Static file and health endpoints.

The current suite contains **52 automated tests**. The latest GitHub Actions run passed: [run 75 — 52 tests and all source checks successful](https://github.com/aboudalshikhyossef-boop/play/actions/runs/42264655578). The workflow also checks Python compilation, shell syntax, and legacy-compatible JavaScript syntax.

Automated checks do not replace physical testing. The owner reports that the current game and match controls work across the connected phones, including iPhone 4S Safari 9.3.6. A separate acceptance pass is still useful for 320 CSS px, portrait/landscape, disconnect/reconnect, and completing all eight rounds on three and four devices.

## Security notes

The repository is public. Never commit the SQLite database, session cookies/tokens, real room codes, tunnel URLs, logs, or personal player data.

The Quick Tunnel URL is public while active. Anyone who obtains it can reach the exposed service, so the random URL is not authentication. The lobby uses room invite codes and separate Secure, HttpOnly browser sessions. The compatibility message endpoint is a temporary unauthenticated diagnostic route and must not carry private game information.

Quick Tunnels are intended for testing/development and do not provide an uptime guarantee. A long-term deployment needs a separately reviewed hosting/tunnel plan.

## Documentation

- Game specification: docs/01-GAME-SPEC.md
- Responsive UX and visual quality: docs/02-RESPONSIVE-UX.md
- Architecture and security: docs/03-ARCHITECTURE-SECURITY.md
- Internal build plan: docs/04-BUILD-PLAN.md
- Physical-device test record: docs/05-COMPATIBILITY-RESULTS.md
- Superseded hotspot experiment: docs/06-HOTSPOT-DECISION.md
- Cloudflare Quick Tunnel: docs/07-CLOUDFLARE-QUICK-TUNNEL.md
- Room and lobby foundation: docs/08-ROOM-LOBBY-FOUNDATION.md
- Match engine rules and phase sequence: docs/09-MATCH-ENGINE-RULES.md
