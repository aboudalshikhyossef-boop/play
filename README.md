# CHAOS FAMILY BATTLE

A local-network family party game for exactly four players.

> Trust no one. Revenge everyone.

## Project status
Planning and specification. Implementation has not started.

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

## Target environment
- Host: Linux Mint laptop
- Clients: two Android devices and one iPhone 4S running iOS 9.3.6
- Network: trusted home LAN

## Security
The repository is public. Never commit passwords, private session tokens, real invite codes, local IP details, database files, player data, or other secrets. The game server must not be exposed through router port forwarding or a public tunnel.

## Next step
Complete and review the product, interface, architecture, and test specifications before implementation.
