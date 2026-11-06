# Compatibility Test Record

This file records results from physical-device testing. A device is marked passed only for the exact test that was actually performed.

## Environment

- Linux Mint: 22.3.
- Python: installed; exact version not yet recorded.
- Host: Linux Mint laptop; player 1 and authoritative server.
- Remote access: Cloudflare Quick Tunnel to a localhost-only Python origin.
- Local origin: `http://127.0.0.1:8765/`.
- Client devices: two Android phones and iPhone 4S / iOS 9.3.6.

## Network history

### Direct home-router/LAN test

The compatibility page opened on the laptop but did not load from the Android phones or iPhone over the previous direct LAN address. This was recorded as an inbound network reachability issue, not as a proven browser rendering failure.

### Laptop-hosted Wi-Fi hotspot experiment

The laptop hotspot was added to the repository as an experiment. The Android phones could join the hotspot, but the local page still did not load from the phones. The hotspot is no longer the selected network path and is not part of the current launcher.

### Cloudflare Quick Tunnel test

The project owner reports that a Cloudflare Quick Tunnel was tested and the compatibility page finally opened successfully in iPhone 4S Safari 9.3.6.

This confirms a successful page load through the temporary HTTPS URL on the physical iPhone. It does not yet confirm every layout criterion or every game interaction.

## Device verification matrix

| Device | Browser | Network page load | JSON ping/echo | Viewport and layout | Status |
|---|---|---|---|---|---|
| Linux Mint laptop | Desktop browser | Confirmed locally | Pending record | Pending | Partial |
| Android phone 1 | Browser not recorded | Pending via Quick Tunnel | Pending | Pending | Not yet verified through tunnel |
| Android phone 2 | Browser not recorded | Pending via Quick Tunnel | Pending | Pending | Not yet verified through tunnel |
| iPhone 4S / iOS 9.3.6 | Safari | Confirmed via Quick Tunnel | Pending record | Pending | Network load confirmed |
| iPhone 4S / iOS 9.3.6 | Safari, landscape | Not recorded | Pending | Pending | Pending |

## Pass criteria

- The same temporary HTTPS URL opens on all four devices.
- GET `/api/ping` succeeds.
- POST `/api/echo` returns the exact Arabic test message.
- No horizontal overflow at the 320 CSS px iPhone baseline.
- No clipped text, controls, or overlapping elements.
- Touch controls respond consistently.
- Portrait and landscape remain usable.
- Actual iPhone Safari 9.3.6 is tested, not only an emulator.
- The launcher stops both cloudflared and Python cleanly after Ctrl+C.

## Known limitations

- Only the iPhone Quick Tunnel page load has been explicitly confirmed by the owner.
- Android page loads via the Quick Tunnel still need to be recorded.
- iPhone viewport measurements, JSON echo, touch checks, and layout checks remain pending.
- The compatibility probe is not the game server and does not implement matchmaking or gameplay.
- Quick Tunnels are temporary development tunnels and do not provide an uptime guarantee.
