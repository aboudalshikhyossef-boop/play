# Compatibility Test Record

This file distinguishes owner-confirmed physical-device results from automated tests. Owner feedback is recorded as reported; it is not presented as an independent test by the development environment.

## Environment

- Host: Linux Mint 22.3.
- Python 3: installed; exact laptop version is not yet recorded.
- Access path: Cloudflare Quick Tunnel to a localhost-only Python server.
- Client devices: two Android phones and iPhone 4S / iOS 9.3.6 Safari.
- Current application: room/lobby foundation, eight-round engine, generated no-repeat challenge system with quiz, bluff, prediction, and four-player rotating duel modes, beginner rules and round roadmap, and five event-card effects. The larger event catalogue and full visual/audio systems remain in progress.

## Network history

### Direct home-router/LAN test

The original compatibility page opened on the laptop but did not load from the Android phones or iPhone using the direct LAN address. This was a network-reachability failure on that network path, not a browser rendering result.

### Laptop-hosted hotspot experiment

The Android devices could join the laptop hotspot, but the page still did not load from them. The hotspot workflow has been superseded and is no longer part of normal startup.

### Cloudflare Quick Tunnel

The owner confirmed that the basic connection, room creation, room joining, and lobby flows work through the temporary HTTPS Quick Tunnel URL. On 2026-11-06 the owner additionally reported that the current game interface and match controls work across the connected phones, and that the iPhone 4S / Safari 9.3.6 runs the game correctly.

This is owner-reported physical-device feedback for the lobby and match arena as they existed before the timed quiz expansion. The new challenge panel and answer-reveal screen were added afterward and have not yet been confirmed on physical devices. It also does not independently verify every orientation, narrow viewport, disconnect/reconnect case, or a complete eight-round run.

## Diagnostic message behavior

The previous echo endpoint returned the submitted message only to the same phone. It did not publish the message to a shared feed or show it on the laptop page.

The current diagnostic page posts to the server's in-memory message feed. Each open diagnostic page polls the feed, so a message sent from a phone appears on the laptop when the laptop also has /compatibility open. The server terminal logs the received diagnostic message.

## Current verification matrix

| Device | Browser | Tunnel page load | Current lobby | Shared message feed | Viewport/layout |
|---|---|---|---|---|---|
| Linux Mint laptop | Firefox (screenshot) | Owner confirms current app | Owner confirms match UI works | Not rechecked in this session | Detailed viewport pending |
| Android phone 1 | Browser not recorded | Owner confirms current app | Owner confirms match UI works | Not rechecked in this session | Detailed viewport pending |
| Android phone 2 | Browser not recorded | Owner confirms current app | Owner confirms match UI works | Not rechecked in this session | Detailed viewport pending |
| iPhone 4S / iOS 9.3.6 | Safari | Owner confirms current app | Owner confirms match UI works correctly | Not rechecked in this session | Orientation details pending |
| iPhone 4S / iOS 9.3.6 | Safari landscape | Not separately recorded | Not separately recorded | Not separately recorded | Pending |

## Automated checks run during development

The repository test suite now contains 63 tests across room storage, concurrent seat allocation, HTTP APIs, UI/legacy-browser contracts, generated challenge diversity, permanent no-repeat history across matches and engine restarts, legacy question migration, bluff answer validation, hidden-dice prediction, four-player duel scoring and pair rotation, duel reveal privacy, private timed challenge scoring, match actions, revenge, five round-event mechanics and persistence, deadlines, and a complete eight-round lifecycle. The latest fully verified GitHub Actions run passed: [run 130 — all 63 tests and source checks successful](https://github.com/aboudalshikhyossef-boop/play/actions/runs/42269019817).

Local checks also include:
- Python compileall.
- Node syntax check for the browser JavaScript.
- Bash syntax check for startup scripts.

These checks were run in the development container. They are not a substitute for the actual Linux Mint laptop or the physical iPhone and Android tests.

## Match-engine verification status

The committed test suite includes server-side tests for 3-player and 4-player starts, room locking after match start, generated challenge families and valid answer keys, no repeated question fingerprints across separate matches and engine restarts, migration of previously used legacy questions, bluff and prediction correctness, rotating duel pairs, duel score settlement and reveal privacy, private challenge answers and scoring, challenge timeouts and no-penalty behavior, answer idempotency, action idempotency, guard, steal, wager, revenge limits, five persisted round events and their effects, timeout passes, and the complete eight-round lifecycle. The owner reports that the original match arena and controls worked across the connected phones, including the iPhone 4S. The generated challenge panel, bluff/prediction modes, duel opponent banner, answer-reveal screen, and five-step round roadmap are newer and remain pending physical acceptance.

## Required acceptance criteria

- Three or four devices open the same temporary HTTPS URL.
- The room supports three active players without a fake fourth seat; a fourth may join before match start.
- A fifth browser is rejected.
- All active players see the same player list and readiness states.
- Refreshing a browser restores the same seat.
- A phone message appears in the laptop's open diagnostic feed.
- No horizontal overflow at 320 CSS px.
- No clipped controls, overlapping text, or hidden actions.
- iPhone portrait and landscape remain usable.
- Ctrl+C stops the local server and Cloudflare process.

