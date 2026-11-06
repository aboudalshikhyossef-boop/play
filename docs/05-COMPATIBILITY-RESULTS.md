# Compatibility Test Record

This file distinguishes owner-confirmed physical-device results from automated tests. A device is not marked fully passed until the current application has been tested on that exact device/browser.

## Environment

- Host: Linux Mint 22.3.
- Python 3: installed; exact laptop version is not yet recorded.
- Access path: Cloudflare Quick Tunnel to a localhost-only Python server.
- Client devices: two Android phones and iPhone 4S / iOS 9.3.6 Safari.
- Current application: room/lobby foundation plus the eight-round core match engine. The challenge/event catalogue and full visual/audio systems remain in progress.

## Network history

### Direct home-router/LAN test

The original compatibility page opened on the laptop but did not load from the Android phones or iPhone using the direct LAN address. This was a network-reachability failure on that network path, not a browser rendering result.

### Laptop-hosted hotspot experiment

The Android devices could join the laptop hotspot, but the page still did not load from them. The hotspot workflow has been superseded and is no longer part of normal startup.

### Cloudflare Quick Tunnel

The owner confirmed that the basic connection, room creation, and room joining flows work, and specifically confirmed the page/lobby connection on the physical iPhone 4S using Safari 9.3.6 through a temporary HTTPS Quick Tunnel URL.

This confirms a network page load through the tunnel. It does not by itself confirm all touch, layout, orientation, or current lobby behavior.

## Diagnostic message behavior

The previous echo endpoint returned the submitted message only to the same phone. It did not publish the message to a shared feed or show it on the laptop page.

The current diagnostic page posts to the server's in-memory message feed. Each open diagnostic page polls the feed, so a message sent from a phone appears on the laptop when the laptop also has /compatibility open. The server terminal logs the received diagnostic message.

## Current verification matrix

| Device | Browser | Tunnel page load | Current lobby | Shared message feed | Viewport/layout |
|---|---|---|---|---|---|
| Linux Mint laptop | Desktop browser | Owner confirmed local page | Pending physical use | Pending physical check | Pending |
| Android phone 1 | Browser not recorded | Owner confirmed basic connection/join flow | Lobby confirmed | Match arena pending | Detailed viewport pending |
| Android phone 2 | Browser not recorded | Owner confirmed basic connection/join flow | Lobby confirmed | Match arena pending | Detailed viewport pending |
| iPhone 4S / iOS 9.3.6 | Safari | Owner confirmed compatibility page | Lobby confirmed | Match arena pending | Portrait/landscape details pending |
| iPhone 4S / iOS 9.3.6 | Safari landscape | Not recorded | Pending | Pending | Pending |

## Automated checks run during development

The repository test suite currently contains 40 tests across room storage, concurrent seat allocation, HTTP APIs, UI/legacy-browser contracts, match actions, revenge, deadlines, and a complete eight-round lifecycle. The test suite is committed; its latest GitHub Actions run must be checked before claiming a green CI result.

Local checks also include:
- Python compileall.
- Node syntax check for the browser JavaScript.
- Bash syntax check for startup scripts.

These checks were run in the development container. They are not a substitute for the actual Linux Mint laptop or the physical iPhone and Android tests.

## Match-engine verification status

The committed test suite includes server-side tests for 3-player and 4-player starts, room locking after match start, private selections, action idempotency, guard, steal, wager, revenge limits, timeout passes, and the complete eight-round lifecycle. The newly added game arena has not yet been visually tested on the physical iPhone or Android devices.

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

