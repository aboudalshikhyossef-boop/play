# CHAOS FAMILY BATTLE — Game Specification

## 1. Product vision
CHAOS is a fast, social, unpredictable family competition built around bluffing, tactical choices, temporary alliances, theft, revenge, risk, and rotating mini-challenges. Players do not need technical or hacking knowledge.

The goal is not simply to answer the most riddles. Players earn and lose in-game currency through challenge outcomes, secret actions, strategic decisions, random events, and counterplay.

## 2. Fixed player model
A match accepts three or four human players. Four is the maximum; three is the minimum. No fourth seat is fabricated when only three people are available.

| Seat | Device | Role |
|---|---|---|
| 1 | Linux Mint laptop | Player and authoritative local host |
| 2 | Android phone | Player |
| 3 | Android phone | Player |
| 4 (optional) | iPhone 4S / iOS 9.3.6 or another supported browser | Optional fourth player |

The laptop host is not a referee and receives no privileged gameplay information. Its player uses the same rules and information boundaries as everyone else. Host/server processes run separately from the laptop player's browser interface.

A match can start when three or four players are present, connected, and ready. The optional fourth seat may remain empty.

## 3. Player identity and lobby
Each player joins with a display name, built-in avatar, distinct player color, and private session identity issued by the server.

Names must be validated for length and safe display. Names are presentation labels, not authentication secrets. Duplicate names should be disallowed within one match or clearly disambiguated.

The lobby displays up to four seats, connection state, readiness state, and the match invite code. Starting a match freezes membership until that match finishes. It must not reveal private session tokens.

## 4. Match economy
- Each player starts with 10 coins (initial balancing value; tune during playtesting).
- Coins are the primary match score and may be won, lost, stolen, wagered, or spent on permitted abilities.
- A player at zero coins remains in the match and can recover.
- No action may create a negative balance.
- Every balance change is calculated and recorded by the server with a reason and round reference.
- The final winner is the player with the highest valid coin balance after the final round and pending effects are resolved.

The rules must explain all costs, rewards, caps, and tie-breakers before a match begins.

## 5. Round lifecycle
1. Round setup: server selects a challenge and any modifier.
2. Challenge: all players receive a task, prompt, prediction, or mini-game.
3. Secret action selection: each player submits one permitted action privately.
4. Lock: choices are locked on submission or when the server deadline expires.
5. Reveal: eligible actions are revealed together.
6. Resolution: server resolves interactions in a documented deterministic order.
7. Revenge window: eligible affected players may use a limited counter-action.
8. Settlement: balances, effects, public events, and rankings are updated.
9. Transition: next round begins after clients receive the settled state.

A match contains eight rounds. Each round currently starts with a 25-second simultaneous multiple-choice challenge; a correct answer earns 2 coins, while an incorrect or missing answer earns nothing and costs nothing. Challenge answers remain private until the shared reveal. The secret action selection then lasts 60 seconds, an eligible revenge window lasts 15 seconds, and the result display lasts 10 seconds. These are initial implementation values and must be tuned through playtesting.

## 6. Secret actions
Initial action families:
- Attack: target another player under defined eligibility and cost rules.
- Guard: block or reduce a permitted incoming attack.
- Bluff: submit misleading information or influence a prediction mechanic.
- Wager: risk coins for a defined reward.
- Trap: create a delayed effect revealed at resolution.
- Revenge: use a limited counter-action after qualifying harm.

The server validates every action, target, cost, deadline, and remaining ability charge. Clients submit intent; they never submit authoritative balances or outcomes.

## 7. Revenge system
Revenge is a signature mechanic, but must be funny, understandable, reciprocal, and bounded.

Candidate revenge cards:
- Counterstrike: attempt to recover some coins from the attacker.
- Freeze: disable one eligible action for a limited future window.
- Duel: challenge the attacker to a short head-to-head task.
- Double-or-nothing: risk a limited amount for a larger possible recovery.

Fairness constraints:
- Revenge opportunities are limited per player and per match.
- No infinite revenge/counter-revenge chains.
- No repeated targeting loop that locks one player out of play.
- Every revenge action has a visible cost, eligibility rule, deadline, and maximum effect.
- A player at zero coins can still participate.
- Revenge rules are public; the selected revenge action stays private until its appropriate reveal.

Exact charges, costs, caps, and outcomes must be finalized in balancing documentation before implementation.

## 8. Random events
Candidate event deck:
- Black Box: a secret temporary ability.
- Bomb: a timed pass-along risk.
- Temporary King: a limited one-round privilege with counterplay.
- Chaos: a temporary change to action rules.
- Secret Auction: simultaneous hidden bids for a special ability.
- Court: a vote with a clear, bounded consequence.

The event engine must support adding and tuning events without rewriting the round manager. Each event needs eligibility, duration, effect, visibility, cancellation behavior, and tests.

## 9. Challenge library
The game must rotate among varied challenge families:
- Riddles and logic
- Bluffing and convincing false answers
- Prediction of another player's action
- Short-term memory
- Visual speed and difference spotting
- Risk/reward choices
- Head-to-head duels
- Luck and hidden-card choices

Correct answers are not the only path to winning. Challenges can award coins, temporary powers, protection, information, or tactical opportunities.

Content must be stored separately from game logic and support Arabic text. Avoid requiring specialist knowledge or obscure trivia. The current generator supports four modes: standard quiz from eight accessible formats, find-the-false-equation bluff, hidden two-dice prediction, and four-player head-to-head duel. Duel opponents rotate through three pair layouts; the only sole correct player in a pair earns 3 coins, a correct tie earns 2 coins each, and no answer never deducts coins. A persistent SQLite history records the normalized prompt and order-independent answer-option set, so an exact challenge is not reused across matches or server restarts while the same game database is retained. Legacy fixed-deck questions are imported during upgrade.

## 10. Anti-repetition and comeback
The variation system should avoid the same challenge family in consecutive rounds where possible, avoid recently used events until the pool requires reuse, vary order/targets/rewards/modifiers, and apply comeback opportunities carefully so they do not erase skill. Avoid long idle waits; use simultaneous or parallel decisions where practical.

Randomness is generated on the server. Tests should cover distribution and edge cases.

## 11. Match end and statistics
At match end, resolve pending effects, calculate final balances and ranking, apply documented tie-breakers, and show the winner and all four standings. Include fun statistics such as coins stolen, successful guards, revenge actions, duels won, and chaos events survived. Offer a rematch without forcing players to re-enter identity details.

## 12. Non-goals and hosting boundaries
- No hacking, cybersecurity, or technical knowledge required from players.
- No public matchmaking or public player directory.
- No cloud-hosted game engine or cloud game database; the authoritative server and SQLite file remain on the laptop.
- The temporary Cloudflare Quick Tunnel is only a network relay to the laptop, not the place where game state is stored or calculated.
- No player elimination before the match ends.
- No host-only gameplay powers.
