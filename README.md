# CHAOS FAMILY BATTLE

A local-network family party game for exactly four players.

> Trust no one. Revenge everyone.

## Project status

The project is in the real-device compatibility and LAN feasibility stage. The compatibility probe has been added; physical-device test results are still pending.

## Product principles

- Exactly four human players. The Linux Mint laptop is both the local host and one ordinary player; it has no gameplay or information advantage.
- One browser-based application for laptop, Android phones, and iPhone 4S (iOS 9.3.6).
- Local-network play only. The laptop hosts the game; the home router connects devices on the LAN.
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

## Compatibility probe

The first test server uses only the Python standard library. No pip installation is required.

From the repository root on Linux Mint:

```bash
python3 --version
python3 compatibility/probe_server.py
```

Open the exact LAN URL printed by the terminal on the laptop, both Android phones, and iPhone 4S Safari. Full instructions are in [compatibility/README.md](compatibility/README.md).

The probe checks basic LAN access, JSON requests using XMLHttpRequest, Arabic/RTL rendering, viewport measurements, horizontal overflow, and touch response. It is a test harness, not the final game.

## Target environment

- Host: Linux Mint 22.3 laptop (reported by project owner)
- Runtime: Python 3 (installed; exact version to be recorded)
- Clients: two Android phones and one iPhone 4S running iOS 9.3.6
- Network: trusted home LAN

## Security

The repository is public. Never commit passwords, private session tokens, real invite codes, local IP details, database files, player data, or other secrets. The probe binds to one selected LAN interface by default. Do not expose it through router port forwarding or a public tunnel. HTTP traffic on the LAN is not encrypted.

## Current gate

Do not start the full game UI and match engine until LAN access and the actual iPhone 4S Safari test have been checked. Record results in [docs/05-COMPATIBILITY-RESULTS.md](docs/05-COMPATIBILITY-RESULTS.md).
