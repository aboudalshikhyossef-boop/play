# Network Decision: Laptop-Hosted CHAOS Wi-Fi

## Decision

Replace the home router as the player-to-player access network during a CHAOS match with a private Wi-Fi access point hosted by the Linux Mint laptop.

The laptop continues to be player 1 and the authoritative local game server. It does not gain extra game information or powers.

## Topology

- Laptop Wi-Fi adapter operates in Access Point (AP) mode.
- SSID: `CHAOS-FAMILY`.
- Radio band: 2.4 GHz (NetworkManager `bg` band), selected for compatibility with the iPhone 4S.
- Security: WPA2-Personal / WPA-PSK with RSN and CCMP where supported.
- Hotspot IPv4 address: `10.42.0.1/24`.
- NetworkManager shared mode supplies DHCP and DNS to connected clients.
- Compatibility/game server listens specifically on `10.42.0.1`.
- No router port forwarding, public hosting, tunnel, or external matchmaking.

NetworkManager's shared IPv4 method assigns a 10.42.x.1/24 address when one is not specified and starts DHCP/DNS services for clients. The nmcli hotspot command supports selecting a Wi-Fi interface, SSID, band, channel, and password. See the official NetworkManager references linked below.

## Automatic startup

The local command `bash start_chaos_lan.sh`:
1. Checks that nmcli, iw, ip, and Python 3 are installed.
2. Checks that the selected Wi-Fi device advertises AP mode before changing its connection profile.
3. Creates or reuses a NetworkManager profile called `chaos-family-hotspot`.
4. Generates a random 24-character alphanumeric WPA2 passphrase once and saves it under the user's local `~/.config/chaos-family/` directory with restrictive permissions.
5. Starts the 2.4 GHz hotspot and requests the 10.42.0.1/24 address.
6. Starts the compatibility web server on that address.

The password is not committed to Git. It remains stable so the phones can remember the network and reconnect on future sessions. The phones still need to join the network once and save it.

Stop the test hotspot with `bash scripts/stop_chaos_hotspot.sh`. Stopping the hotspot does not delete its saved profile or passphrase.

## Hardware requirement

The laptop's Wi-Fi adapter and Linux driver must support AP mode. The startup script checks this using `iw` before activating the hotspot. If unsupported, use a compatible USB Wi-Fi adapter or retain the existing router-based LAN. Do not assume that every laptop adapter supports AP mode.

Using the same Wi-Fi adapter as both a client and AP may disconnect it from the home Wi-Fi while the hotspot is active. This is expected for this offline local-play design. A separate Ethernet uplink is optional and not required.

## Firewall

Do not disable UFW. If UFW is active, permit only TCP port 8765 from the hotspot subnet on the hotspot Wi-Fi interface. Example, replacing `wlp2s0` with the actual interface:

```bash
sudo ufw allow in on wlp2s0 from 10.42.0.0/24 to any port 8765 proto tcp
```

Remove this temporary probe rule after testing:

```bash
sudo ufw delete allow in on wlp2s0 from 10.42.0.0/24 to any port 8765 proto tcp
```

The final game port and firewall rule will be recorded in the final deployment guide.

## Security boundaries

This design reduces dependence on the home router and avoids guest/client-isolation settings on that router. WPA2 protects access to the Wi-Fi network, but does not encrypt the HTTP session between a joined phone and the local server. Any device given the hotspot password is on the trusted game network and may attempt to reach the laptop's permitted local services. The server must validate sessions and actions, bind only to the hotspot address, and expose only the required port through the firewall.

This is not a guarantee against a compromised connected device or a hostile person who has the Wi-Fi password.

## Verification gates

- AP capability check passes on the laptop's physical Wi-Fi adapter.
- Hotspot starts and has 10.42.0.1/24.
- Android devices and iPhone 4S can join the 2.4 GHz WPA2 network.
- All devices can open `http://10.42.0.1:8765/`.
- JSON ping and echo succeed.
- The laptop remains an ordinary player using the same server URL.
- UFW is not disabled and no router port forwarding is configured.

## Official references

- NetworkManager nmcli reference: https://networkmanager.pages.freedesktop.org/NetworkManager/NetworkManager/nmcli.html
- NetworkManager IP settings reference: https://networkmanager.pages.freedesktop.org/NetworkManager/NetworkManager/nm-settings-nmcli.html
