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

1. **Family challenge — 25 seconds.** All players receive the same generated challenge and submit one answer privately. Correct answers earn their mode-specific reward; wrong or missing answers never deduct coins. The server reveals all answers together when everyone has answered or the deadline expires.
2. **Chaos event decision — 20 seconds when required.** Black Box, Bomb, Secret Auction, and Court ask each player for one secret decision. Temporary King is applied automatically after the challenge; standard modifier cards are applied during action resolution. The server applies safe defaults to missing interactive decisions when the deadline expires. Event choices remain hidden until everyone submits or the deadline expires.
3. **Secret actions — 60 seconds.** Each player chooses exactly one action after the challenge and any interactive event have resolved. The chosen action, target, and wager amount are private until action reveal. The server locks the first accepted choice. The same request ID and same payload can safely be retried; a different second choice is rejected.
4. **Reveal and resolution.** Once all current players submit, the server reveals all action choices together and resolves them in seat order using a deterministic rule order. If time expires, missing choices become pass.
5. **Revenge — 15 seconds, only when an actual theft succeeded.** Each player who lost coins to a successful thief may choose one eligible thief or pass. The action is limited by the player's remaining revenge charges. Missing revenge choices become pass when the deadline expires.
6. **Round result — 10 seconds.** All players see the same public result and updated balances. The server begins the next round when the result deadline elapses.
7. **Match finished.** After the eighth result window, the server finalizes the ranking. The room may start a new match when three or four players are again present, connected, and ready.

The browser displays the server-provided remaining time. Client clocks never decide whether an action is accepted. A visible six-step roadmap marks the challenge, optional event decision, secret action, reveal, conditional revenge, and result. Events that resolve automatically or do not need an interactive choice are marked complete or skipped rather than showing a false waiting step.

## Generated family challenge system

Every round starts with a freshly generated Arabic challenge. The generator can choose a standard quiz, **Bluff**, **Prediction**, or (with four players only) **Duel** mode. Standard quiz prompts use addition, subtraction, multiplication, number sequences, elapsed time, short-term word memory, odd-one-out, and comparing sums. Numbers, words, sequences, dice results, and answer choices are randomized; the challenge content is not a fixed deck.

- 25 seconds per challenge.
- Correct answer: +2 coins, recorded in the coin ledger as `challenge_reward`.
- Wrong answer or no answer before the deadline: 0 coins; there is no deduction.
- No speed bonus in quiz, bluff, or prediction: all correct players receive the same reward.
- Bluff: three arithmetic statements are shown; exactly one is false. Identify that statement for +2 coins.
- Prediction: the server privately generates two die results before answers are submitted. Guess their sum; a correct prediction earns +2 coins. This is explicitly a luck mode, not a skill question.
- Duel: available only with four players. The server pairs the four seats into two head-to-head matches and rotates through all three possible pair layouts over successive rounds. A player who alone answers correctly in their pair earns +3 coins; if both answer correctly, each earns +2; if neither answers correctly, neither earns coins. Wrong or missing answers never deduct coins.
- One answer per player; the first accepted answer is locked. A matching request ID and payload can be retried safely.
- The next question is checked against the complete prior question fingerprint, including its option set. Reordering the same options does not make a used question new.
- The browser receives only the prompt and options before reveal, never the correct index or other players' answers.

### Permanent no-repeat history

The `challenge_history` table stores a SHA-256 fingerprint of the normalized prompt and sorted answer-option set. Its primary key prevents two concurrent matches from claiming the same question. The row is reserved in the same SQLite transaction that creates the match round, so a crash cannot leave an assigned question unrecorded. The table deliberately has no foreign key to match records: deleting an old match or starting a rematch does not delete its question history.

On engine upgrade, prompts already stored in old `match_rounds.challenge_json` records are imported into the history before new rounds are selected. The no-repeat guarantee therefore covers old fixed-deck questions too.

The history lasts as long as the same SQLite database is kept. Removing or replacing `~/.local/share/chaos-family/chaos.sqlite3` resets that history. The generator has a very large practical variation space, but no finite software system can promise literally infinite unique content; if it cannot claim an unused fingerprint after its bounded retry window, it fails closed instead of repeating a known question.

Before each duel, the server sends each player only their own opponent's display name; it does not publish the pair list or the answer key. The final reveal shows the winner and reward without including internal duel seat IDs.

The challenge generator and fingerprint rules live in `server/challenges.py`; the authoritative engine reserves and scores questions in `server/engine.py`.

## Round event cards

Round one is intentionally a teaching round with the base rules. Starting in round two, the server selects one event card for each round. The card is stored as JSON in the matching SQLite round record; all browsers receive the same card, including after refresh or reconnect. The next card is selected so it does not repeat the immediately previous card.

| Event | Effect |
|---|---|
| سوق السرقة المفتوح | Each successful steal can transfer up to 3 coins instead of 2. |
| درع مجاني للجميع | Guard costs 0 coins for the round and can be used even at a zero balance. It still blocks all steals against its user. |
| مكافأة على الجرأة | Each successful thief receives 1 extra coin from the game bank. The victim loses only the normal stolen amount. The bonus is written to the coin ledger. |
| ردّ الصاع مضاعفًا | A successful counterstrike transfers up to 2 coins instead of 1, but still consumes only one of the player's two match-long revenge charges. |
| رهان عالي المخاطرة | The chance remains 50/50. A winning wager gives net profit of twice the stake; a losing wager still removes only the original stake. |
| الصندوق الأسود | Each player secretly chooses box 1, 2, or 3. The three hidden contents are one +2 coin bonus, one free shield against all steals this round, and one trap that removes 1 coin (or no coins from a zero balance). A player may also skip. |
| القنبلة المتنقلة | The server selects a starting carrier. All players privately choose keep or pass to another player. The server follows the chain from the starting carrier; the last holder loses up to 2 coins. If a pass returns to a player already visited, the bomb explodes with the last holder before the loop. |
| الملك المؤقت | After challenge rewards are applied, the player with the lowest balance is crowned; rotating seat priority breaks ties. The king gains +1 coin from the game bank, is protected for the round at no cost, and may steal up to 3 coins. The crown expires after this round. |
| المزاد السري | Each player bids 0–3 coins, limited by their balance. The highest positive bid wins a free shield and is transferred to the game bank. Rotating seat priority breaks ties; all-zero bids mean no winner. |
| المحكمة | Each player secretly votes for another player or abstains. A player needs more than half of all players' votes to be convicted and lose 1 coin to the game bank. Self-votes are invalid; a tie or lack of an absolute majority dismisses the case. |

All event choices are stored in `event_actions` and resolved by the server. The browser receives only the public event instructions and its own submitted flag before reveal. Hidden box contents, individual bids, votes, and bomb decisions are not exposed until the shared event result is stored. Event outcomes and all coin changes are persisted in the match-round record and coin ledger.

## Secret actions in the current engine

| Action | Rule |
|---|---|
| Steal | Choose one other player. Attempt to transfer up to 2 coins from that player to yourself (up to 3 during Market Rush or when you are the Temporary King). |
| Guard | Pay 1 coin. All theft attempts targeting you in the current round are blocked (free during Free Guard or when you are the Temporary King). |
| Wager | Stake 1, 2, or 3 coins. The server uses a cryptographically secure 50/50 result. A win gives net profit equal to the stake (twice the stake during High Stakes); a loss removes the stake. |
| Pass | Submit no action for the round. |

All balances are resolved on the server. The engine never accepts a balance or claimed result from a browser. Coin balances cannot become negative.

If multiple players target the same unguarded player, theft attempts resolve in ascending attacker seat order. Each attempt can take up to 2 coins (or 3 during Market Rush or when the attacker is the Temporary King), limited by the target's remaining balance. A guard blocks every theft attempt against that player for the round; it costs one coin even when nobody attacks unless the Free Guard event is active or the guarding player is the Temporary King. Free shields from Black Box and Secret Auction, plus the Temporary King's crown protection, are applied before attack resolution and do not require a paid Guard action. A successful theft during the Bounty event also grants the thief one ledger-recorded bonus coin from the game bank.

## Revenge

- A revenge opportunity exists only for a player who actually lost at least one coin to a successful theft that round.
- That player may counterstrike one of the players who successfully stole from them in that same round.
- A successful counterstrike transfers exactly 1 coin from the selected thief to the victim, or up to 2 during the Double Revenge event.
- Each player has two revenge charges for the whole match.
- A player can submit at most one revenge decision in a round.
- A counterstrike cannot create another revenge opportunity. No revenge chain is possible.
- If the selected thief has no coins left by resolution time, the counterstrike fails and does not consume a charge.
- Passing does not consume a charge.

## Resolution order

1. Apply the current event's guard cost (0 during Free Guard) and mark protected players.
2. Resolve wagers using server-side randomness and the current event's payout rule.
3. Resolve steals in attacker seat order, respecting guards, the current event's steal limit, and remaining victim balance.
4. Apply any event bounty and store the public reveal; determine eligible revenge victims.
5. Resolve counterstrikes in victim seat order using the current event's revenge amount.
6. Store the settled result and start the result window.

Every balance change has a corresponding row in the coin ledger, including both sides of transfers.

## Ranking and tie-breakers

Final ranking is:
1. Highest remaining coin balance.
2. Highest cumulative coins successfully stolen during the match.
3. Lowest seat number.

Players are not eliminated at zero coins. They can continue to choose actions and can potentially recover.

## Privacy contract

During the challenge phase, each player receives the same newly generated prompt and options, plus only their own answer-submitted flag. The correct answer and other players' answers remain hidden until the challenge resolves.

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

The engine now supports eight rounds, dynamically generated challenges from eight question formats and four challenge modes, permanent no-repeat history across matches and server restarts, private challenge submissions, all ten round modifiers/events (five passive modifiers and five large events), server-resolved Black Box/Bomb/Temporary King/Auction/Court mechanics, private event choices, event timeouts/defaults, secret actions, revenge, a persistent coin ledger, three-or-four-player matches, and final ranking. The client includes a plain-language rules guide and a six-step roadmap that shows the optional event decision phase and its timing.

Remaining work includes additional mini-game formats beyond the implemented challenges, the larger Chaos event concept, comeback balancing, final match statistics, and the polished sound/effects layer. These will be integrated into the same server-authoritative state machine.
