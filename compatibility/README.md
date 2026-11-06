# Compatibility Probe — مرحلة اختبار الاتصال والشاشات

This is a temporary compatibility test page, not the final game UI. It checks:
- LAN reachability from each device.
- Basic JSON request/response using XMLHttpRequest (no Fetch API).
- Arabic/RTL text rendering.
- Responsive page width and horizontal overflow.
- Touch button response and viewport measurements.

The server uses only the Python standard library. No pip install is required.

## 1. Check Python on Linux Mint

Open Terminal and run:

```bash
python3 --version
```

Python 3 should print its installed version.

## 2. Start the probe

From the project root directory:

```bash
python3 compatibility/probe_server.py
```

The script tries to select the laptop's LAN IPv4 address and prints a URL such as:

`http://192.168.1.50:8765/`

The example address is illustrative; use the exact URL printed by your laptop.

Keep the terminal open during the test. Stop the server with Ctrl+C.

If automatic address detection fails, run `hostname -I`, identify the laptop's home-network IPv4 address, then start with:

```bash
python3 compatibility/probe_server.py --host 192.168.1.50
```

Replace the example IP with the actual address.

## 3. Open on all four devices

Make sure all devices are connected to the same trusted home Wi-Fi/LAN. Open the printed URL on:
1. Linux Mint laptop (player 1).
2. Android phone (player 2).
3. Android phone (player 3).
4. iPhone 4S Safari (player 4).

Do not use mobile data for this test. Do not configure router port forwarding, public tunnels, or public hosting.

If the laptop can open the page but phones cannot, check the local firewall and router client-isolation settings. Do not disable the firewall globally. Add only a temporary, narrowly scoped LAN rule if required, and remove it after testing.

## 4. What to test

On each device:
- Does the Arabic text appear connected and readable?
- Are all panels and buttons visible without clipping?
- Does the page avoid horizontal scrolling?
- Does the tap counter increase each time?
- Does sending the test message show a successful reply?
- Record the displayed viewport width and height.
- Rotate the phone and repeat the layout check.

On iPhone 4S, confirm that the displayed viewport width is close to 320 CSS px in portrait. Take screenshots of the top, middle, and bottom of the page if possible.

## 5. Report results

Record the device, browser, orientation, viewport width/height, whether the server connected, whether the echo test passed, and any visual problem. Do not share private session data; this probe does not create game sessions.

## Security boundary

This test server binds to one selected LAN interface by default, not all interfaces. HTTP traffic on the home LAN is not encrypted. Use it only on a trusted local network. Never expose it through router port forwarding or a public tunnel.
