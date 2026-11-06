# Compatibility Test Record

This file records results from physical-device testing. Do not mark a device as passed until it has been tested on the actual device/browser.

## Environment

- Linux Mint: 22.3 (reported by project owner)
- Python: pending confirmation from `python3 --version`
- Probe port: 8765
- Network: trusted home LAN

## Device results

| Device | Browser | Orientation | Viewport width × height | LAN page | JSON echo | Layout | Notes |
|---|---|---|---|---|---|---|---|
| Linux Mint laptop | Pending | Landscape | Pending | Pending | Pending | Pending | |
| Android phone 1 | Pending | Portrait | Pending | Pending | Pending | Pending | |
| Android phone 2 | Pending | Portrait | Pending | Pending | Pending | Pending | |
| iPhone 4S / iOS 9.3.6 | Safari | Portrait | Pending | Pending | Pending | Pending | |
| iPhone 4S / iOS 9.3.6 | Safari | Landscape | Pending | Pending | Pending | Pending | |

## Pass criteria

- Page opens from each device using the laptop LAN address.
- GET health request succeeds.
- POST echo returns the exact Arabic test message.
- No horizontal overflow at the 320 CSS px iPhone baseline.
- No clipped text or controls.
- Touch control responds consistently.
- Portrait and landscape remain usable.
- Actual iPhone Safari 9.3.6 has been tested.

## Known limitations

- No real-device result has been recorded yet.
- This probe is not the game server and does not implement matchmaking or gameplay.
- HTTP on the LAN is unencrypted.
