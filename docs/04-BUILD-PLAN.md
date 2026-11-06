# Build Plan and Quality Gates

## 1. Delivery policy

The goal is one complete game, not a sequence of reduced public releases. Development milestones are internal quality gates, not player-facing editions. We will keep the agreed feature scope and test each dependency before building on it.

## 2. Completed specification and network decisions

- Three-or-four-player match model; a fourth player is optional.
- Laptop is player 1 and the single local server, without game privileges.
- Arabic-first RTL interface.
- iPhone 4S / iOS 9.3.6 is a first-class browser target.
- 320 CSS px is the smallest layout baseline.
- Cloudflare Quick Tunnel is the current access path after the owner confirmed the test page opens in iPhone Safari.
- The laptop retains the one SQLite database and authoritative game process.

## 3. Current implementation progress

### Foundation — implemented and automated

- Python application server binds to loopback only.
- SQLite store for rooms, players, and hashed sessions.
- Up to four lobby seats; three connected and ready players can start a match.
- Room invite codes and player-specific sessions.
- Secure, HttpOnly session cookie for HTTPS clients.
- Session restoration after refresh.
- Ready-state synchronization and leave/revoke.
- Concurrent seat allocation protection.
- Arabic RTL lobby page with mobile-first layout.
- Cloudflare launcher starts the main app server, not the old compatibility-only server.
- Cross-device diagnostic message feed now stores the message on the server and exposes it to all open diagnostic pages.
- Automated unit and HTTP API tests.
- GitHub Actions checks for Python, shell scripts, and JavaScript syntax.

### Physical compatibility — partially verified

- The owner confirmed the Quick Tunnel test page opens in iPhone 4S Safari 9.3.6.
- Earlier Android tests confirmed hotspot association but did not prove tunnel-based page access.
- Android tunnel loading and the new real lobby still need confirmation on both physical Android devices.
- New lobby layout still needs actual iPhone portrait/landscape verification.

## 4. Remaining implementation sequence

### Milestone D — Complete lobby UX and device acceptance
- Test room creation and joining from all four real devices.
- Verify seat display, readiness changes, reconnect after refresh, and leaving.
- Check 320 CSS px, Arabic line wrapping, touch targets, keyboard-open behavior, portrait, and landscape.
- Fix all clipping, overlap, and horizontal overflow.

Exit criteria: four physical devices remain in one room and all see the same lobby state.

### Milestone E — Core authoritative match engine — implemented in the current branch
- Added the eight-round match record and persistent match-player snapshots.
- Added three/four-player start eligibility and active-room membership lock.
- Added 60-second secret-action phase, 15-second revenge phase, and 10-second round-result phase.
- Added server-side steal, guard, wager, and pass actions.
- Added bounded counterstrike revenge with two charges per player and no revenge chains.
- Added timeout passes, deterministic resolution, idempotent request handling, and a persistent coin ledger.
- Added match arena UI, standings, reveal, final ranking, and rematch control.

Automated tests cover a full eight-round match and the critical concurrency/privacy rules. The physical game-arena test remains pending on the four devices.

Exit criteria: all match actions and phase transitions resolve correctly on all supported browsers and physical devices.

### Milestone F — Complete challenge and chaos systems
- Add the varied challenge library and server-validated challenge outcomes.
- Add bluff, trap, and the remaining agreed secret actions.
- Expand revenge cards beyond the current counterstrike foundation.
- Implement the complete random-event catalogue: Black Box, Bomb, Temporary King, Chaos, Secret Auction, and Court.
- Implement comeback balancing and anti-repetition.
- Add full match statistics and additional tie-break/play-balance tests.

Exit criteria: every mechanic has rules, player UI states, server validation, and tests.

### Milestone G — Complete visual/audio experience
- Complete every game screen and responsive state.
- Add local audio assets and user controls.
- Add lightweight visual effects, reduced-motion support, and explicit loading/error/disabled states.
- Ensure animation never hides information or delays an action.

Exit criteria: all screens work without breaking the legacy phone experience.

### Milestone H — Full integration and completion
- Test complete matches with three and four physical players on the supported devices.
- Test disconnect, refresh, duplicate actions, timeouts, and tunnel interruption.
- Test long Arabic names, mixed-direction text, and on-screen keyboard.
- Review all public endpoints and private-state boundaries.
- Review the repository for secrets and runtime data.
- Complete final setup, recovery, and maintenance documentation.

Exit criteria: a complete three-or-four-player game is playable start to finish and all critical tests pass.

## 5. Automated test coverage currently present

- Store: room creation, 3/4 readiness thresholds, distinct seats, fifth-player rejection, duplicate/invalid names, session recovery, leave/rejoin, active-room lock, and concurrent joins.
- Match engine: 3/4 player starts, concurrent start idempotency, secret actions, guard, theft, wager, revenge eligibility/charges, duplicate requests, deadlines, and a complete eight-round match.
- HTTP: health/static routes, cookies, session recovery, room/match APIs, active membership lock, cross-origin rejection, rate limiting, and shared diagnostic feed.

Run:

    bash run_tests.sh

## 6. Manual device acceptance checklist

- Linux Mint 22.3 laptop, desktop browser.
- Android phone 1, actual browser.
- Android phone 2, actual browser.
- iPhone 4S / iOS 9.3.6 / Safari.
- Same temporary HTTPS URL for all four devices.
- 320 CSS px and larger widths.
- Portrait and landscape.
- No horizontal overflow, clipped text, overlapping panels, or hidden controls.
- Primary touch targets at least 44 CSS px in each dimension.
- Refresh and reconnect retain the same player seat.
- Each player sees correct readiness and connection state.
- Laptop receives server-side messages from phones in the diagnostic feed.

Automated tests cannot mark a physical device as passed. Record the actual test result in docs/05-COMPATIBILITY-RESULTS.md.

