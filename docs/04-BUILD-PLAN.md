# Build Plan and Quality Gates

## 1. Delivery policy

The goal is one complete game, not a sequence of reduced public releases. Plan and implement the full agreed feature set before calling the game complete.

Development is divided into internal milestones. These are dependency and quality gates, not separate player-facing editions. Do not remove agreed features merely to reach an early demo. If scope changes, update the specification explicitly.

## 2. Internal work sequence

### Milestone A — Product and UX specification
- Confirm game rules, economy, revenge constraints, event catalogue, challenge families, and tie-breakers.
- Define all screens and user flows.
- Define responsive behavior and the 320 CSS px baseline.
- Define browser compatibility and visual verification criteria.

Exit criteria: specifications reviewed and no unresolved contradiction in core rules.

### Milestone B — Legacy browser and remote-connection feasibility
- Inspect Linux Mint version and Python runtime.
- Create a minimal static page and local server bound to localhost.
- Expose the local server through a temporary Cloudflare Quick Tunnel.
- Test the generated HTTPS URL on Android and iPhone 4S Safari 9.3.6.
- Verify form submission, JSON response, refresh behavior, and the laptop's ordinary player view.
- Keep Proton VPN settings unchanged during the test.

Exit criteria: the same tunnel URL is usable by all four devices; actual iPhone Safari test passes.

### Milestone C — Foundation and security
- Establish application structure and dependency pinning.
- Add local run scripts and runtime-data exclusions.
- Implement temporary tunnel startup/shutdown, local origin binding, invite code lifecycle, and session model.
- Implement persistent SQLite storage and safe reset behavior.
- Ensure the public tunnel cannot expose debug/admin or filesystem endpoints.

Exit criteria: one authoritative local server is reachable through the tunnel and no secrets/runtime data are tracked.

### Milestone D — Identity, lobby, and responsive design system
- Build reusable typography, spacing, colors, buttons, cards, dialogs, status indicators, and navigation.
- Build registration, avatar/color selection, four-seat lobby, readiness, and reconnect.
- Verify every screen at 320 CSS px before expanding to larger screens.

Exit criteria: four distinct players can join and remain correctly identified through refresh/reconnect.

### Milestone E — Authoritative match engine
- Implement match state machine and round lifecycle.
- Implement deadlines, action locking, reveal, resolution, settlement, and sequence numbers.
- Implement coin ledger and deterministic resolution order.
- Implement server-side validation and idempotent action requests.

Exit criteria: a complete scripted match resolves correctly in automated tests.

### Milestone F — Full gameplay systems
- Implement all agreed secret actions.
- Implement bounded revenge and anti-chain protections.
- Implement event engine and complete agreed event catalogue.
- Implement challenge families and content loading.
- Implement comeback balancing and anti-repetition logic.
- Implement match-end ranking and statistics.

Exit criteria: every mechanic has rules, UI states, server validation, and automated tests.

### Milestone G — Full visual/audio experience
- Complete every screen and responsive state.
- Add local sound assets and user controls.
- Add lightweight visual effects and clear motion states.
- Add reduced-motion/effects-off behavior.
- Verify no effect blocks interaction or obscures essential information.

Exit criteria: visual and audio systems work without breaking the legacy phone experience.

### Milestone H — Integrated verification and completion
- Test full matches with all four physical devices using the same tunnel URL.
- Test disconnect, refresh, duplicate requests, timeout, tunnel interruption, and host shutdown.
- Test portrait and landscape, long Arabic names, mixed-direction text, and keyboard-open states.
- Run automated tests and manual device checklist.
- Review repository for secrets and runtime data.
- Complete README setup and recovery instructions.

Exit criteria: all critical tests pass and the full game is playable start to finish.

## 3. Test strategy

### Automated tests
- Coin ledger and no-negative-balance rules.
- Action eligibility, costs, and target validation.
- Revenge charge limits and no infinite chains.
- Round transition and timeout handling.
- Event and challenge selection constraints.
- Duplicate request idempotency.
- Session ownership and seat limits.
- Reconnect and stale-state handling.

### Manual device tests
- iPhone 4S / iOS 9.3.6 / Safari.
- Two Android devices and their actual browsers.
- Linux Mint laptop browser.
- Same temporary HTTPS URL on all devices.
- Portrait and landscape.
- 320 CSS px width and larger widths.
- Touch target, text legibility, overflow, overlap, and keyboard behavior.
- Tunnel disconnect/reconnect and Proton VPN behavior.

### Per-screen acceptance checklist
- No horizontal overflow.
- No clipped text or controls.
- No overlapping interactive elements.
- Primary touch targets are comfortably tappable.
- Body text is legible.
- RTL and mixed-direction text are correct.
- Important actions remain reachable with keyboard open.
- Loading, empty, error, disabled, and disconnected states exist.
- Screen passes on actual iPhone Safari 9.3.6.

## 4. Project governance
- Keep product decisions in docs/.
- Update specifications before changing behavior.
- Use focused commits with clear messages.
- Do not commit generated runtime data.
- Do not label internal milestones as public game releases.
- Maintain a known-issues list until critical items are closed.
