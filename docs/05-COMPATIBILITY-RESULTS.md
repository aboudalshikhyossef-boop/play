# Compatibility Test Record

This file records results from physical-device testing. Do not mark a device as passed until it has been tested on the actual device/browser.

## Environment

- Linux Mint: 22.3 (reported by project owner)
- Python: installed; exact version pending `python3 --version`
- Network model: laptop-hosted private Wi-Fi hotspot (new test path)
- Hotspot SSID: `CHAOS-FAMILY`
- Hotspot subnet: `10.42.0.0/24`
- Laptop hotspot address: `10.42.0.1`
- Radio: 2.4 GHz, WPA2-Personal
- Probe port: TCP 8765

## Previous home-router test

The compatibility page opened successfully on the laptop but did not load on either Android phone or the iPhone 4S. This is recorded as a network-reachability failure on the previous home Wi-Fi path, not as a browser rendering failure.

## New laptop-hotspot test

The new hotspot scripts have been committed, but the laptop's physical Wi-Fi AP capability and the new network have not yet been tested.

| Device | Browser | Orientation | Viewport width × height | Joined hotspot | Page opened | JSON echo | Layout | Notes |
|---|---|---|---|---|---|---|---|---|
| Linux Mint laptop | Pending | Landscape | Pending | N/A | Pending | Pending | Pending | Player 1 and server |
| Android phone 1 | Pending | Portrait | Pending | Pending | Pending | Pending | Pending | |
| Android phone 2 | Pending | Portrait | Pending | Pending | Pending | Pending | Pending | |
| iPhone 4S / iOS 9.3.6 | Safari | Portrait | Pending | Pending | Pending | Pending | Pending | |
| iPhone 4S / iOS 9.3.6 | Safari | Landscape | Pending | Pending | Pending | Pending | Pending | |

## Pass criteria

- Laptop Wi-Fi adapter advertises AP mode.
- Hotspot starts and assigns `10.42.0.1/24`.
- All three phones can join the WPA2 2.4 GHz network.
- Page opens at `http://10.42.0.1:8765/` on each device.
- GET health request succeeds.
- POST echo returns the exact Arabic test message.
- No horizontal overflow at the 320 CSS px iPhone baseline.
- No clipped text or controls.
- Touch control responds consistently.
- Portrait and landscape remain usable.
- Actual iPhone Safari 9.3.6 has been tested.

## Known limitations

- New physical-device hotspot test is pending.
- This probe is not the game server and does not implement matchmaking or gameplay.
- HTTP inside the private hotspot is unencrypted.
- A Wi-Fi adapter without AP mode will need a compatible USB Wi-Fi adapter or a router-based fallback.
