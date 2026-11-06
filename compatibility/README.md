# Compatibility Probe — اختبار نقطة الاتصال والشاشات

This temporary page checks:
- Laptop-hosted Wi-Fi hotspot reachability from the three phones.
- JSON request/response using XMLHttpRequest (no Fetch API).
- Arabic/RTL text rendering.
- Responsive page width and horizontal overflow.
- Touch response and viewport measurements.

The scripts use NetworkManager and the Python standard library. No pip installation is required.

## 1. Check Python and tools

On Linux Mint, run:

```bash
python3 --version
nmcli --version
iw --version
```

If `iw` is missing:

```bash
sudo apt install iw
```

## 2. Start hotspot and test server together

From the repository root:

```bash
bash start_chaos_lan.sh
```

The startup script:
- Checks that the Wi-Fi adapter and driver support AP mode.
- Creates or reuses the `CHAOS-FAMILY` network on 2.4 GHz.
- Uses WPA2-Personal security.
- Generates a random password once and stores it locally under `~/.config/chaos-family/hotspot-password` with restrictive permissions.
- Starts the hotspot at `10.42.0.1/24`.
- Starts the test page at `http://10.42.0.1:8765/`.

The terminal displays the Wi-Fi password. Share it only with the three players. It is not committed to Git. The saved password means the phones can remember this Wi-Fi network and reconnect automatically after the first successful join.

The laptop may disconnect from the home Wi-Fi while its adapter operates as an access point. This is expected. No home-router changes, port forwarding, public tunnel, or internet connection are needed.

## 3. Connect all four devices

- Linux Mint laptop: local player 1 and web server.
- Android phone 1: join `CHAOS-FAMILY`.
- Android phone 2: join `CHAOS-FAMILY`.
- iPhone 4S: open Settings > Wi-Fi and join `CHAOS-FAMILY`.

On all phones, open:

`http://10.42.0.1:8765/`

Use the actual URL displayed by the script if it changes in a later configuration.

## 4. Firewall

Do not disable UFW.

Check:

```bash
sudo ufw status verbose
```

If UFW reports `Status: active`, first identify the hotspot Wi-Fi interface printed or selected by NetworkManager (for example `wlp2s0`). Then allow only the test server port from the hotspot subnet, replacing the interface name:

```bash
sudo ufw allow in on wlp2s0 from 10.42.0.0/24 to any port 8765 proto tcp
```

After testing, remove that temporary rule:

```bash
sudo ufw delete allow in on wlp2s0 from 10.42.0.0/24 to any port 8765 proto tcp
```

If UFW is inactive, do not add a rule just for the sake of it.

## 5. Stop the test

Press Ctrl+C in the server terminal, then in another terminal run:

```bash
bash scripts/stop_chaos_hotspot.sh
```

This deactivates the hotspot but preserves its profile and locally stored password.

## 6. What to test

On each device:
- Does the Wi-Fi network appear and allow joining?
- Does the Arabic test page open?
- Does the server status show connected?
- Does the tap counter increase on each press?
- Does sending a test message show a successful echo?
- Does the page avoid horizontal scrolling?
- Record viewport width/height.
- Rotate the phone and repeat the layout check.

On iPhone 4S, confirm that portrait viewport width is close to 320 CSS px. Test Safari 9.3.6 in portrait and landscape.

## 7. If hotspot creation fails

The script checks AP mode before creating or activating the profile. If it reports that AP mode is unsupported, do not keep retrying or disable security. Send the exact terminal error and the output of:

```bash
nmcli device status
iw list
```

A compatible USB Wi-Fi adapter may be needed.

If the hotspot starts but phones cannot open the page, check UFW and confirm that the phone actually joined `CHAOS-FAMILY`.

## Security boundary

WPA2 protects access to the private Wi-Fi network. HTTP traffic from a joined device to the laptop is still unencrypted. Any device with the Wi-Fi password is on the trusted game network. The server must validate sessions and actions. Never expose this test server through router port forwarding or a public tunnel.
