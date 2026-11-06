# CHAOS FAMILY BATTLE

A local-network family party game for exactly four players.

> Trust no one. Revenge everyone.

## Project status

The project is in the physical-device compatibility and local-network feasibility stage. The laptop-hosted Wi-Fi hotspot workflow is now prepared; actual adapter and phone compatibility tests are pending.

## Product principles

- Exactly four human players. The Linux Mint laptop is both the local host and one ordinary player; it has no gameplay or information advantage.
- One browser-based application for laptop, Android phones, and iPhone 4S (iOS 9.3.6).
- The laptop creates a private 2.4 GHz Wi-Fi network and hosts the game locally.
- Arabic-first interface with right-to-left layout.
- Responsive design is a core requirement. The smallest target is 320 CSS pixels wide.
- The complete game scope is planned before implementation. Development milestones are internal quality gates, not separate public releases.
- The server is authoritative for actions, timers, randomness, scoring, and outcomes.

## Documentation

- [Game specification](docs/01-GAME-SPEC.md)
- [Responsive UX and visual quality](docs/02-RESPONSIVE-UX.md)
- [Architecture and local-network security](docs/03-ARCHITECTURE-SECURITY.md)
- [Build and verification plan](docs/04-BUILD-PLAN.md)
- [Compatibility test record](docs/05-COMPATIBILITY-RESULTS.md)
- [Laptop hotspot network decision](docs/06-HOTSPOT-DECISION.md)

## Start the local compatibility test

The laptop hotspot and test server use only Linux NetworkManager tools and the Python standard library. No pip installation is required.

From the repository root on Linux Mint:

```bash
python3 --version
bash start_chaos_lan.sh
```

The script checks whether the laptop Wi-Fi adapter supports Access Point (AP) mode, creates or reuses the private `CHAOS-FAMILY` 2.4 GHz WPA2 hotspot, saves a randomly generated password locally, and starts the compatibility page at:

`http://10.42.0.1:8765/`

Connect both Android phones and the iPhone 4S to the displayed Wi-Fi name and password, then open that URL. The phones need to save the network once; they should then be able to reconnect to the same SSID on future sessions.

To stop the hotspot after testing, open another terminal in the project directory and run:

```bash
bash scripts/stop_chaos_hotspot.sh
```

Full instructions and firewall guidance are in [the hotspot decision](docs/06-HOTSPOT-DECISION.md) and [compatibility guide](compatibility/README.md).

## Target environment

- Host: Linux Mint 22.3 laptop (reported by project owner)
- Runtime: Python 3 (installed; exact version to be recorded)
- Clients: two Android phones and one iPhone 4S running iOS 9.3.6
- Network: laptop-hosted private Wi-Fi access point

## Security

The repository is public. Never commit passwords, private session tokens, real invite codes, local IP details, database files, player data, or other secrets. The hotspot password is stored only in the local user configuration directory and is not written into Git. Do not expose the server through router port forwarding or a public tunnel. HTTP traffic on the local hotspot is not encrypted. Do not disable UFW; use only the narrow port rule documented for the hotspot interface if required.

## Current gate

Do not start the full game UI and match engine until the laptop's AP capability and actual iPhone 4S Safari connection have been checked. Record results in [docs/05-COMPATIBILITY-RESULTS.md](docs/05-COMPATIBILITY-RESULTS.md).
