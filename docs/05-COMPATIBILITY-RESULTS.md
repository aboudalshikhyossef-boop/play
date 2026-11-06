# Compatibility Test Record

This file distinguishes owner-confirmed physical-device results from automated tests. A device is not marked fully passed until the current application has been tested on that exact device/browser.

## Environment

- Host: Linux Mint 22.3.
- Python 3: installed; exact laptop version is not yet recorded.
- Access path: Cloudflare Quick Tunnel to a localhost-only Python server.
- Client devices: two Android phones and iPhone 4S / iOS 9.3.6 Safari.
- Current application: four-seat room/lobby foundation; full match engine is not yet implemented.

## Network history

### Direct home-router/LAN test

The original compatibility page opened on the laptop but did not load from the Android phones or iPhone using the direct LAN address. This was a network-reachability failure on that network path, not a browser rendering result.

### Laptop-hosted hotspot experiment

The Android devices could join the laptop hotspot, but the page still did not load from them. The hotspot workflow has been superseded and is no longer part of normal startup.

### Cloudflare Quick Tunnel

The owner confirmed that the compatibility page opened successfully on the physical iPhone 4S using Safari 9.3.6 through a temporary HTTPS Quick Tunnel URL.

This confirms a network page load through the tunnel. It does not by itself confirm all touch, layout, orientation, or current lobby behavior.

## Diagnostic message behavior

The previous echo endpoint returned the submitted message only to the same phone. It did not publish the message to a shared feed or show it on the laptop page.

The current diagnostic page posts to the server's in-memory message feed. Each open diagnostic page polls the feed, so a message sent from a phone should appear on the laptop when the laptop also has /compatibility open. The server terminal logs the received diagnostic message. This needs a new physical-device test after pulling the updated application.

## Current verification matrix

| Device | Browser | Tunnel page load | Current lobby | Shared message feed | Viewport/layout |
|---|---|---|---|---|---|
| Linux Mint laptop | Desktop browser | Owner confirmed local page | Pending physical use | Pending physical check | Pending |
| Android phone 1 | Browser not recorded | Pending on tunnel | Pending | Pending | Pending |
| Android phone 2 | Browser not recorded | Pending on tunnel | Pending | Pending | Pending |
| iPhone 4S / iOS 9.3.6 | Safari | Owner confirmed compatibility page | Pending new app test | Pending new app test | Pending |
| iPhone 4S / iOS 9.3.6 | Safari landscape | Not recorded | Pending | Pending | Pending |

## Automated checks run during development

The local test suite currently includes 21 tests covering the room store, concurrency, HTTP API, cookie flags, rate limits, origin checks, and shared diagnostic messages.

Local checks also include:
- Python compileall.
- Node syntax check for the browser JavaScript.
- Bash syntax check for startup scripts.

These checks were run in the development container. They are not a substitute for the actual Linux Mint laptop or the physical iPhone and Android tests.

## Required acceptance criteria

- All four devices open the same temporary HTTPS URL.
- The laptop can create a room and occupy seat 1.
- Three phones join seats 2–4.
- A fifth browser is rejected.
- All four see the same player list and readiness states.
- Refreshing a browser restores the same seat.
- A phone message appears in the laptop's open diagnostic feed.
- No horizontal overflow at 320 CSS px.
- No clipped controls, overlapping text, or hidden actions.
- iPhone portrait and landscape remain usable.
- Ctrl+C stops the local server and Cloudflare process.

