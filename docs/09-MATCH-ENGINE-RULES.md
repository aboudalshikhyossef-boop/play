# Match Engine — Core Rules and State Machine

## Player count

A match requires at least three and accepts at most four players. Three people can play without reserving a fake fourth seat. A fourth person may join the lobby before the match starts. Once a match starts, membership is frozen until the match finishes.

Every player is equal. Creating the room does not grant a host role, extra powers, private information, or control over another player's actions.

## Match setup

- Eight rounds per match.
- Every player starts with 10 coins.
- Every player starts with two revenge charges for the entire match.
- The server chooses deadlines and resolves all actions.
- The match state and coin ledger are stored in the same SQLite database on the laptop.
- A rematch creates a new match record; it does not overwrite the previous match.

## Round phases

1. **Secret actions — 60 seconds.** Each player chooses exactly one action. The chosen action, target, and wager amount are private until reveal. The server locks the first accepted choice. The same request ID and same payload can safely be retried; a different second choice is rejected.
2. **Reveal and resolution.** Once all current players submit, the server reveals all choices together and resolves them in seat order using a deterministic rule order. If time expires, missing choices become pass.
3. **Revenge — 15 seconds, only when an actual theft succeeded.** Each player who lost coins to a successful thief may choose one eligible thief or pass. The action is limited by the player's remaining revenge charges. Missing revenge choices become pass when the deadline expires.
4. **Round result — 10 seconds.** All players see the same public result and updated balances. The server begins the next round when the result deadline elapses.
5. **Match finished.** After the eighth result window, the server finalizes the ranking. The room may start a new match when three or four players are again present, connected, and ready.

The browser displays the server-provided remaining time. Client clocks never decide whether an action is accepted.

## Secret actions in the current engine

| Action | Rule |
|---|---|
| Steal | Choose one other player. Attempt to transfer up to 2 coins from that player to yourself. |
| Guard | Pay 1 coin. All theft attempts targeting you in the current round are blocked. |
| Wager | Stake 1, 2, or 3 coins. The server uses a cryptographically secure 50/50 result. A win gives net profit equal to the stake; a loss removes the stake. |
| Pass | Submit no action for the round. |

All balances are resolved on the server. The engine never accepts a balance or claimed result from a browser. Coin balances cannot become negative.

If multiple players target the same unguarded player, theft attempts resolve in ascending attacker seat order. Each attempt can take up to 2 coins, limited by the target's remaining balance. A guard blocks every theft attempt against that player for the round; the guard costs one coin even when nobody attacks.

## Revenge

- A revenge opportunity exists only for a player who actually lost at least one coin to a successful theft that round.
- That player may counterstrike one of the players who successfully stole from them in that same round.
- A successful counterstrike transfers exactly 1 coin from the selected thief to the victim.
- Each player has two revenge charges for the whole match.
- A player can submit at most one revenge decision in a round.
- A counterstrike cannot create another revenge opportunity. No revenge chain is possible.
- If the selected thief has no coins left by resolution time, the counterstrike fails and does not consume a charge.
- Passing does not consume a charge.

## Resolution order

1. Apply one-coin guard costs and mark protected players.
2. Resolve wagers using server-side randomness.
3. Resolve steals in attacker seat order, respecting guards and remaining victim balance.
4. Store the public reveal and determine eligible revenge victims.
5. Resolve counterstrikes in victim seat order after all eligible victims submit or the revenge timer expires.
6. Store the settled result and start the result window.

Every balance change has a corresponding row in the coin ledger, including both sides of transfers.

## Ranking and tie-breakers

Final ranking is:
1. Highest remaining coin balance.
2. Highest cumulative coins successfully stolen during the match.
3. Lowest seat number.

Players are not eliminated at zero coins. They can continue to choose actions and can potentially recover.

## Privacy contract

During the secret-action phase, each player receives:
- Public player names, seats, colors, connection state, and balances.
- Their own action-submitted flag.
- Their own revenge charges.

They do not receive another player's action, target, or wager. The full action reveal is returned only after all players have submitted or the server deadline has elapsed.

During revenge, the public theft results are visible, but each player's pending revenge selection remains private until the revenge phase resolves.

## Persistence and reconnection

The server stores the match, match-player snapshots, round actions, revenge actions, round reveal JSON, and coin ledger in SQLite. A browser refresh restores the same session and reads the current match state from the server. A disconnected player retains their match seat; their missing action is treated as pass only when that phase's server deadline expires.

A completed match remains recorded. Starting a rematch creates a new match ID and resets each participant to 10 coins and two revenge charges.

## Implemented scope and remaining game design

The base engine now supports eight rounds, the four core actions above, private submission, reveal, wagers, guarding, theft, counterstrike revenge, deadlines, timeout passes, persistent coin ledger, three-or-four-player matches, and final ranking.

The complete game scope still includes the designed challenge library, additional bluff/trap/event systems, random events such as Black Box/Bomb/Temporary King/Auction/Court, richer revenge cards and their balancing, final match statistics, and the polished sound/effects layer. Those systems will be integrated into this same state machine rather than bolted on as a separate game.
