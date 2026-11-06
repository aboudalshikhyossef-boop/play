import concurrent.futures
import json
import re
from contextlib import closing
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from server.challenges import (
    ROUND_CHALLENGES,
    challenge_fingerprint,
    generate_challenge,
)
from server.engine import (
    ActionLocked,
    MatchEngine,
    MatchNotActive,
    MatchNotReady,
    ROUND_EVENTS,
)
from server.store import GameStore, InvalidInput, RoomNotOpen


class MatchEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp.name) / "engine.sqlite3")
        self.store = GameStore(db_path)
        self.engine = MatchEngine(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def create_ready_room(self, count=3):
        created = self.store.create_room("Player 1")
        tokens = [created["session_token"]]
        for index in range(2, count + 1):
            joined = self.store.join_room(created["invite_code"], "Player %s" % index)
            tokens.append(joined["session_token"])
        for token in tokens:
            self.store.set_ready(created["invite_code"], token, True)
        return created["invite_code"], tokens

    def answer_challenge_for_all(self, code, state, resolve_event=True):
        with closing(self.store._connect()) as db:
            row = db.execute(
                "SELECT challenge_json FROM match_rounds WHERE match_id = ? AND round_no = ?",
                (state["match_id"], state["round"]),
            ).fetchone()
        challenge = json.loads(row["challenge_json"])
        wrong_index = (challenge["correct_index"] + 1) % len(challenge["options"])
        player_ids = [player["id"] for player in state["players"]]
        for index, player_id in enumerate(player_ids):
            state = self.engine.submit_challenge(
                code,
                player_id,
                "auto-challenge-r%02d-p%d" % (state["round"], index + 1),
                wrong_index,
            )
        if resolve_event and state["phase"] == "event":
            event_id = state["round_event"]["id"]
            for index, player_id in enumerate(player_ids):
                if event_id == "black_box":
                    state = self.engine.submit_event(
                        code, player_id, "auto-box-%02d-p%d" % (state["round"], index),
                        "skip",
                    )
                elif event_id == "bomb":
                    state = self.engine.submit_event(
                        code, player_id, "auto-bomb-%02d-p%d" % (state["round"], index),
                        "keep",
                    )
                elif event_id == "secret_auction":
                    state = self.engine.submit_event(
                        code, player_id, "auto-bid-%02d-p%d" % (state["round"], index),
                        "bid", amount=0,
                    )
                elif event_id == "court":
                    state = self.engine.submit_event(
                        code, player_id, "auto-court-%02d-p%d" % (state["round"], index),
                        "abstain",
                    )
        return state

    def start(self, count=3):
        code, tokens = self.create_ready_room(count)
        player_id = self.store.get_session(tokens[0])["player_id"]
        state = self.engine.start_match(code, player_id)
        state = self.answer_challenge_for_all(code, state)
        return code, tokens, state

    def set_round_event_payload(self, match_id, round_no, event):
        with closing(self.store._connect()) as db:
            db.execute(
                "UPDATE match_rounds SET event_json = ? WHERE match_id = ? AND round_no = ?",
                (json.dumps(event, ensure_ascii=False), match_id, round_no),
            )

    def start_with_event(self, count, event):
        code, tokens = self.create_ready_room(count)
        player_ids = [self.store.get_session(token)["player_id"] for token in tokens]
        state = self.engine.start_match(code, player_ids[0])
        self.set_round_event_payload(state["match_id"], state["round"], event)
        state = self.answer_challenge_for_all(code, state, resolve_event=False)
        return code, tokens, player_ids, state

    def set_round_event(self, match_id, round_no, event_id):
        with closing(self.store._connect()) as db:
            db.execute(
                "UPDATE match_rounds SET event_json = ? WHERE match_id = ? AND round_no = ?",
                (json.dumps(ROUND_EVENTS[event_id], ensure_ascii=False), match_id, round_no),
            )

    def test_three_players_can_start_a_match(self):
        _code, _tokens, state = self.start(3)
        self.assertEqual(state["status"], "active")
        self.assertEqual(state["phase"], "actions")
        self.assertEqual(state["player_count"], 3)
        self.assertEqual([p["coins"] for p in state["players"]], [10, 10, 10])
        self.assertNotEqual(state["challenge"]["mode"], "duel")

    def test_four_players_can_start_a_match(self):
        _code, _tokens, state = self.start(4)
        self.assertEqual(state["player_count"], 4)
        self.assertEqual(state["action_total"], 4)

    def test_two_players_cannot_start_a_match(self):
        code, tokens = self.create_ready_room(2)
        player_id = self.store.get_session(tokens[0])["player_id"]
        with self.assertRaises(MatchNotReady):
            self.engine.start_match(code, player_id)

    def test_three_players_must_all_be_ready(self):
        created = self.store.create_room("A")
        second = self.store.join_room(created["invite_code"], "B")
        self.store.join_room(created["invite_code"], "C")
        self.store.set_ready(created["invite_code"], created["session_token"], True)
        self.store.set_ready(created["invite_code"], second["session_token"], True)
        player_id = self.store.get_session(created["session_token"])["player_id"]
        with self.assertRaises(MatchNotReady):
            self.engine.start_match(created["invite_code"], player_id)

    def test_concurrent_start_requests_create_only_one_match(self):
        code, tokens = self.create_ready_room(3)
        player_ids = [self.store.get_session(token)["player_id"] for token in tokens]

        def start(player_id):
            return self.engine.start_match(code, player_id)["match_id"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            match_ids = list(pool.map(start, player_ids))
        self.assertEqual(len(set(match_ids)), 1)

    def test_choices_remain_private_until_all_players_submit(self):
        code, tokens, state = self.start(3)
        ids = [p["id"] for p in state["players"]]
        first = self.engine.submit_action(code, ids[0], "req-steal-0001", "steal", ids[1], 0)
        self.assertEqual(first["phase"], "actions")
        self.assertIsNone(first["result"])
        self.assertTrue(first["private"]["action_submitted"])

        second = self.engine.get_state(code, ids[1])
        self.assertFalse(second["private"]["action_submitted"])
        self.assertIsNone(second["result"])
        self.assertEqual([p["coins"] for p in second["players"]], [10, 10, 10])

    def test_guard_blocks_theft_and_costs_one_coin(self):
        code, tokens, state = self.start(3)
        ids = [p["id"] for p in state["players"]]
        self.engine.submit_action(code, ids[0], "req-steal-0002", "steal", ids[1], 0)
        self.engine.submit_action(code, ids[1], "req-guard-0002", "guard")
        result = self.engine.submit_action(code, ids[2], "req-pass-0002", "pass")
        self.assertEqual(result["phase"], "result")
        self.assertEqual([p["coins"] for p in result["players"]], [10, 9, 10])
        self.assertEqual(result["result"]["blocked_attacks"][0]["reason"], "guarded")

    def test_successful_theft_opens_bounded_revenge_and_counterstrike(self):
        code, tokens, state = self.start(3)
        ids = [p["id"] for p in state["players"]]
        self.engine.submit_action(code, ids[0], "req-steal-0003", "steal", ids[1], 0)
        self.engine.submit_action(code, ids[1], "req-pass-0003", "pass")
        result = self.engine.submit_action(code, ids[2], "req-pass-0004", "pass")
        self.assertEqual(result["phase"], "revenge")

        victim_state = self.engine.get_state(code, ids[1])
        attacker_state = self.engine.get_state(code, ids[0])
        self.assertEqual(victim_state["private"]["revenge_targets"], [ids[0]])
        self.assertEqual(victim_state["private"]["revenge_charges"], 2)
        self.assertEqual(attacker_state["private"]["revenge_targets"], [])

        settled = self.engine.submit_revenge(code, ids[1], "req-revenge-0001", "counterstrike", ids[0])
        self.assertEqual(settled["phase"], "result")
        balances = {p["id"]: p["coins"] for p in settled["players"]}
        self.assertEqual(balances[ids[0]], 11)
        self.assertEqual(balances[ids[1]], 9)
        self.assertEqual(settled["private"]["revenge_charges"], 1)
        self.assertEqual(len(settled["result"]["revenge_results"]), 1)

    def test_revenge_cannot_target_a_player_who_did_not_steal_from_you(self):
        code, tokens, state = self.start(3)
        ids = [p["id"] for p in state["players"]]
        self.engine.submit_action(code, ids[0], "req-steal-0005", "steal", ids[1], 0)
        self.engine.submit_action(code, ids[1], "req-pass-0005", "pass")
        self.engine.submit_action(code, ids[2], "req-pass-0006", "pass")
        with self.assertRaises(InvalidInput):
            self.engine.submit_revenge(code, ids[1], "req-revenge-0002", "counterstrike", ids[2])

    def test_duplicate_final_action_retry_is_idempotent_after_reveal(self):
        code, tokens, state = self.start(3)
        ids = [p["id"] for p in state["players"]]
        self.engine.submit_action(code, ids[0], "req-pass-0010", "pass")
        self.engine.submit_action(code, ids[1], "req-pass-0011", "pass")
        final = self.engine.submit_action(code, ids[2], "req-pass-0012", "pass")
        self.assertEqual(final["phase"], "result")
        retry = self.engine.submit_action(code, ids[2], "req-pass-0012", "pass")
        self.assertEqual(retry["phase"], "result")
        self.assertEqual([p["coins"] for p in retry["players"]], [10, 10, 10])

    def test_wager_win_credits_the_net_profit_without_negative_balances(self):
        code, tokens, state = self.start(3)
        ids = [p["id"] for p in state["players"]]
        with patch("server.engine.secrets.randbelow", return_value=1):
            self.engine.submit_action(code, ids[0], "req-wager-0001", "wager", None, 3)
            self.engine.submit_action(code, ids[1], "req-pass-0021", "pass")
            result = self.engine.submit_action(code, ids[2], "req-pass-0022", "pass")
        balances = {p["id"]: p["coins"] for p in result["players"]}
        self.assertEqual(balances[ids[0]], 13)
        self.assertTrue(result["result"]["wagers"][0]["won"])
        self.assertTrue(all(value >= 0 for value in balances.values()))

    def test_wager_cannot_exceed_current_balance_or_rules_cap(self):
        code, tokens, state = self.start(3)
        ids = [p["id"] for p in state["players"]]
        with self.assertRaises(InvalidInput):
            self.engine.submit_action(code, ids[0], "req-wager-0003", "wager", None, 4)
        with self.assertRaises(InvalidInput):
            self.engine.submit_action(code, ids[0], "req-wager-0004", "wager", None, 0)

    def test_player_cannot_change_a_locked_choice(self):
        code, tokens, state = self.start(3)
        ids = [p["id"] for p in state["players"]]
        self.engine.submit_action(code, ids[0], "req-pass-0031", "pass")
        with self.assertRaises(ActionLocked):
            self.engine.submit_action(code, ids[0], "req-pass-0032", "steal", ids[1], 0)

    def test_room_is_locked_during_an_active_match(self):
        code, tokens, state = self.start(3)
        with self.assertRaises(RoomNotOpen):
            self.store.join_room(code, "Late Player")
        with self.assertRaises(RoomNotOpen):
            self.store.leave_room(code, tokens[0])

    def test_action_deadline_resolves_missing_choices_as_pass(self):
        code, tokens, state = self.start(3)
        ids = [p["id"] for p in state["players"]]
        self.engine.submit_action(code, ids[0], "req-pass-0041", "pass")
        with closing(self.store._connect()) as db:
            db.execute(
                "UPDATE matches SET deadline_at = ? WHERE id = ?",
                (int(time.time()) - 1, state["match_id"]),
            )
        advanced = self.engine.get_state(code, ids[1])
        self.assertEqual(advanced["phase"], "result")
        self.assertEqual(len(advanced["result"]["actions"]), 3)
        self.assertEqual([p["coins"] for p in advanced["players"]], [10, 10, 10])


    def test_full_eight_round_match_transitions_and_finishes(self):
        code, tokens, state = self.start(3)
        player_ids = [player["id"] for player in state["players"]]
        previous_challenge_id = state["challenge"]["id"]
        used_questions = {
            challenge_fingerprint(
                state["challenge"]["prompt"], state["challenge"]["options"]
            )
        }

        for round_no in range(1, 9):
            for index, player_id in enumerate(player_ids):
                request_id = "full-r%02d-p%d" % (round_no, index + 1)
                state = self.engine.submit_action(
                    code, player_id, request_id, "pass", None, 0
                )
            self.assertEqual(state["phase"], "result")
            self.assertEqual(state["round"], round_no)

            with closing(self.store._connect()) as db:
                db.execute(
                    "UPDATE matches SET deadline_at = ? WHERE id = ?",
                    (int(time.time()) - 1, state["match_id"]),
                )
            state = self.engine.get_state(code, player_ids[0])

            if round_no < 8:
                self.assertEqual(state["phase"], "challenge")
                self.assertEqual(state["round"], round_no + 1)
                self.assertNotEqual(state["challenge"]["id"], previous_challenge_id)
                fingerprint = challenge_fingerprint(
                    state["challenge"]["prompt"], state["challenge"]["options"]
                )
                self.assertNotIn(fingerprint, used_questions)
                used_questions.add(fingerprint)
                previous_challenge_id = state["challenge"]["id"]
                state = self.answer_challenge_for_all(code, state)
                self.assertEqual(state["phase"], "actions")
            else:
                self.assertEqual(state["phase"], "finished")
                self.assertEqual(state["status"], "finished")
                self.assertEqual(len(state["ranking"]), 3)
                self.assertTrue(all(player["coins"] >= 0 for player in state["ranking"]))
                self.assertEqual(
                    [player["coins"] for player in state["ranking"]],
                    sorted([player["coins"] for player in state["ranking"]], reverse=True),
                )



    def test_round_events_are_shared_persisted_and_do_not_repeat_back_to_back(self):
        code, tokens, state = self.start(3)
        ids = [p["id"] for p in state["players"]]
        self.assertEqual(state["round_event"]["id"], "opening")

        for index, player_id in enumerate(ids):
            state = self.engine.submit_action(
                code, player_id, "opening-pass-%02d" % index, "pass"
            )
        self.assertEqual(state["phase"], "result")

        with closing(self.store._connect()) as db:
            db.execute(
                "UPDATE matches SET deadline_at = ? WHERE id = ?",
                (int(time.time()) - 1, state["match_id"]),
            )
        round_two = self.engine.get_state(code, ids[0])
        same_card = self.engine.get_state(code, ids[2])
        self.assertEqual(round_two["round"], 2)
        self.assertIn(round_two["round_event"]["id"], ROUND_EVENTS)
        self.assertNotEqual(round_two["round_event"]["id"], "opening")
        self.assertEqual(round_two["round_event"], same_card["round_event"])
        self.assertEqual(round_two["phase"], "challenge")
        self.assertEqual(round_two["challenge"], same_card["challenge"])
        round_two = self.answer_challenge_for_all(code, round_two)

        for index, player_id in enumerate(ids):
            state = self.engine.submit_action(
                code, player_id, "second-pass-%02d" % index, "pass"
            )
        with closing(self.store._connect()) as db:
            db.execute(
                "UPDATE matches SET deadline_at = ? WHERE id = ?",
                (int(time.time()) - 1, state["match_id"]),
            )
        round_three = self.engine.get_state(code, ids[0])
        self.assertNotEqual(
            round_three["round_event"]["id"], round_two["round_event"]["id"]
        )
        self.assertEqual(round_three["phase"], "challenge")
        self.assertNotEqual(
            round_three["challenge"]["id"], round_two["challenge"]["id"]
        )

    def test_market_rush_increases_successful_steal_limit_to_three(self):
        code, tokens, state = self.start(3)
        ids = [p["id"] for p in state["players"]]
        self.set_round_event(state["match_id"], 1, "market_rush")
        self.engine.submit_action(code, ids[0], "market-steal-0001", "steal", ids[1], 0)
        self.engine.submit_action(code, ids[1], "market-pass-0001", "pass")
        result = self.engine.submit_action(code, ids[2], "market-pass-0002", "pass")
        balances = {p["id"]: p["coins"] for p in result["players"]}
        self.assertEqual(balances[ids[0]], 13)
        self.assertEqual(balances[ids[1]], 7)
        self.assertEqual(result["result"]["thefts"][0]["amount"], 3)

    def test_free_guard_blocks_theft_even_with_zero_coins(self):
        code, tokens, state = self.start(3)
        ids = [p["id"] for p in state["players"]]
        self.set_round_event(state["match_id"], 1, "free_guard")
        with closing(self.store._connect()) as db:
            db.execute(
                "UPDATE match_players SET coins = 0 WHERE match_id = ? AND player_id = ?",
                (state["match_id"], ids[1]),
            )
        self.engine.submit_action(code, ids[0], "free-guard-steal-01", "steal", ids[1], 0)
        self.engine.submit_action(code, ids[1], "free-guard-guard-01", "guard")
        result = self.engine.submit_action(code, ids[2], "free-guard-pass-01", "pass")
        balances = {p["id"]: p["coins"] for p in result["players"]}
        self.assertEqual(balances[ids[1]], 0)
        self.assertEqual(result["result"]["blocked_attacks"][0]["reason"], "guarded")

    def test_bounty_event_records_bonus_in_ledger_and_public_result(self):
        code, tokens, state = self.start(3)
        ids = [p["id"] for p in state["players"]]
        self.set_round_event(state["match_id"], 1, "bounty")
        self.engine.submit_action(code, ids[0], "bounty-steal-0001", "steal", ids[1], 0)
        self.engine.submit_action(code, ids[1], "bounty-pass-0001", "pass")
        result = self.engine.submit_action(code, ids[2], "bounty-pass-0002", "pass")
        balances = {p["id"]: p["coins"] for p in result["players"]}
        self.assertEqual(balances[ids[0]], 13)
        self.assertEqual(result["result"]["thefts"][0]["bonus"], 1)
        with closing(self.store._connect()) as db:
            bonus = db.execute(
                "SELECT delta FROM coin_ledger WHERE match_id = ? AND player_id = ? AND reason = 'event_bounty'",
                (state["match_id"], ids[0]),
            ).fetchone()
        self.assertEqual(bonus["delta"], 1)

    def test_double_revenge_event_transfers_up_to_two_coins_once(self):
        code, tokens, state = self.start(3)
        ids = [p["id"] for p in state["players"]]
        self.set_round_event(state["match_id"], 1, "double_revenge")
        self.engine.submit_action(code, ids[0], "double-revenge-steal1", "steal", ids[1], 0)
        self.engine.submit_action(code, ids[1], "double-revenge-pass1", "pass")
        state = self.engine.submit_action(code, ids[2], "double-revenge-pass2", "pass")
        self.assertEqual(state["phase"], "revenge")
        settled = self.engine.submit_revenge(
            code, ids[1], "double-revenge-hit1", "counterstrike", ids[0]
        )
        balances = {p["id"]: p["coins"] for p in settled["players"]}
        self.assertEqual(balances[ids[0]], 10)
        self.assertEqual(balances[ids[1]], 10)
        self.assertEqual(settled["result"]["revenge_results"][0]["amount"], 2)
        self.assertEqual(settled["private"]["revenge_charges"], 1)

    def test_high_stakes_event_doubles_net_winnings_but_not_losses(self):
        code, tokens, state = self.start(3)
        ids = [p["id"] for p in state["players"]]
        self.set_round_event(state["match_id"], 1, "high_stakes")
        with patch("server.engine.secrets.randbelow", return_value=1):
            self.engine.submit_action(code, ids[0], "high-stakes-win-001", "wager", None, 3)
            self.engine.submit_action(code, ids[1], "high-stakes-pass-001", "pass")
            result = self.engine.submit_action(code, ids[2], "high-stakes-pass-002", "pass")
        balances = {p["id"]: p["coins"] for p in result["players"]}
        self.assertEqual(balances[ids[0]], 16)
        self.assertEqual(result["result"]["wagers"][0]["delta"], 6)


    def test_challenge_answers_are_private_until_everyone_submits_and_score_correct_answers(self):
        code, tokens = self.create_ready_room(3)
        player_ids = [self.store.get_session(token)["player_id"] for token in tokens]
        state = self.engine.start_match(code, player_ids[0])
        self.assertEqual(state["phase"], "challenge")
        self.assertIsNone(state["challenge_result"])
        self.assertNotIn("correct_index", state["challenge"])

        with closing(self.store._connect()) as db:
            row = db.execute(
                "SELECT challenge_json FROM match_rounds WHERE match_id = ? AND round_no = ?",
                (state["match_id"], state["round"]),
            ).fetchone()
        challenge = json.loads(row["challenge_json"])
        correct = challenge["correct_index"]
        wrong = (correct + 1) % len(challenge["options"])
        first = self.engine.submit_challenge(code, player_ids[0], "quiz-answer-0001", correct)
        self.assertEqual(first["phase"], "challenge")
        self.assertTrue(first["private"]["challenge_submitted"])
        self.assertIsNone(first["challenge_result"])

        second_view = self.engine.get_state(code, player_ids[1])
        self.assertFalse(second_view["private"]["challenge_submitted"])
        self.assertIsNone(second_view["challenge_result"])
        self.assertEqual([p["coins"] for p in second_view["players"]], [10, 10, 10])

        self.engine.submit_challenge(code, player_ids[1], "quiz-answer-0002", wrong)
        final = self.engine.submit_challenge(code, player_ids[2], "quiz-answer-0003", correct)
        self.assertEqual(final["phase"], "actions")
        self.assertEqual([p["coins"] for p in final["players"]], [12, 10, 12])
        self.assertEqual(final["challenge_result"]["correct_answer"], challenge["options"][correct])
        self.assertEqual(
            [row["correct"] for row in final["challenge_result"]["answers"]],
            [True, False, True],
        )

    def test_challenge_answer_is_idempotent_and_locked_after_first_submission(self):
        code, tokens = self.create_ready_room(3)
        player_id = self.store.get_session(tokens[0])["player_id"]
        state = self.engine.start_match(code, player_id)
        answer = 0
        first = self.engine.submit_challenge(code, player_id, "quiz-retry-0001", answer)
        again = self.engine.submit_challenge(code, player_id, "quiz-retry-0001", answer)
        self.assertEqual(first["phase"], "challenge")
        self.assertTrue(again["private"]["challenge_submitted"])
        with self.assertRaises(ActionLocked):
            self.engine.submit_challenge(code, player_id, "quiz-retry-0002", (answer + 1) % 3)

    def test_actions_cannot_start_before_challenge_and_timeout_answers_are_no_penalty(self):
        code, tokens = self.create_ready_room(3)
        player_ids = [self.store.get_session(token)["player_id"] for token in tokens]
        state = self.engine.start_match(code, player_ids[0])
        with self.assertRaises(MatchNotActive):
            self.engine.submit_action(code, player_ids[0], "quiz-gate-pass-01", "pass")

        with closing(self.store._connect()) as db:
            db.execute(
                "UPDATE matches SET deadline_at = ? WHERE id = ?",
                (int(time.time()) - 1, state["match_id"]),
            )
        with self.assertRaises(MatchNotActive):
            self.engine.submit_action(code, player_ids[0], "quiz-late-pass-0001", "pass")

        advanced = self.engine.get_state(code, player_ids[0])
        self.assertEqual(advanced["phase"], "actions")
        self.assertFalse(advanced["private"]["action_submitted"])
        self.assertTrue(all(not item["answered"] for item in advanced["challenge_result"]["answers"]))
        self.assertEqual([p["coins"] for p in advanced["players"]], [10, 10, 10])


    def test_questions_never_repeat_across_matches_or_engine_restart(self):
        code1, tokens1 = self.create_ready_room(3)
        id1 = self.store.get_session(tokens1[0])["player_id"]
        first = self.engine.start_match(code1, id1)
        fingerprint1 = challenge_fingerprint(
            first["challenge"]["prompt"], first["challenge"]["options"]
        )

        code2, tokens2 = self.create_ready_room(3)
        id2 = self.store.get_session(tokens2[0])["player_id"]
        second = self.engine.start_match(code2, id2)
        fingerprint2 = challenge_fingerprint(
            second["challenge"]["prompt"], second["challenge"]["options"]
        )
        self.assertNotEqual(fingerprint1, fingerprint2)

        restarted_engine = MatchEngine(self.store)
        code3, tokens3 = self.create_ready_room(3)
        id3 = self.store.get_session(tokens3[0])["player_id"]
        third = restarted_engine.start_match(code3, id3)
        fingerprint3 = challenge_fingerprint(
            third["challenge"]["prompt"], third["challenge"]["options"]
        )
        self.assertNotIn(fingerprint3, {fingerprint1, fingerprint2})

        with closing(self.store._connect()) as db:
            used = db.execute("SELECT COUNT(*) AS count FROM challenge_history").fetchone()["count"]
        self.assertGreaterEqual(used, 3)

    def test_legacy_questions_are_backfilled_and_rejected_by_unique_claim(self):
        code, tokens = self.create_ready_room(3)
        player_id = self.store.get_session(tokens[0])["player_id"]
        state = self.engine.start_match(code, player_id)
        legacy = dict(ROUND_CHALLENGES[0])
        fingerprint = challenge_fingerprint(legacy["prompt"], legacy["options"])

        with closing(self.store._connect()) as db:
            db.execute(
                "UPDATE match_rounds SET challenge_json = ? WHERE match_id = ? AND round_no = 1",
                (json.dumps(legacy, ensure_ascii=False), state["match_id"]),
            )
            db.execute(
                "DELETE FROM challenge_history WHERE fingerprint = ?",
                (fingerprint,),
            )

        migrated_engine = MatchEngine(self.store)
        with closing(self.store._connect()) as db:
            migrated = db.execute(
                "SELECT prompt FROM challenge_history WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        self.assertIsNotNone(migrated)
        self.assertEqual(migrated["prompt"], legacy["prompt"])

        fresh = {
            "id": "fresh-test-question",
            "family": "اختبار",
            "title": "سؤال جديد",
            "prompt": "هذا سؤال اختباري فريد لم يسبق استخدامه 73921؟",
            "options": ["أ", "ب", "ج"],
            "correct_index": 0,
            "explanation": "إجابة الاختبار.",
        }
        with closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            with patch(
                "server.engine.generate_challenge",
                side_effect=[legacy, fresh],
            ):
                selected = migrated_engine._claim_unique_challenge(
                    db, state["match_id"], 2
                )
            db.commit()
        self.assertEqual(selected["id"], "fresh-test-question")

    def test_generated_challenges_cover_multiple_families_and_valid_answer_keys(self):
        generated = [generate_challenge() for _ in range(120)]
        families = {challenge["family"] for challenge in generated}
        self.assertGreaterEqual(len(families), 6)
        for challenge in generated:
            self.assertGreaterEqual(len(challenge["options"]), 3)
            self.assertEqual(len(set(challenge["options"])), len(challenge["options"]))
            self.assertGreaterEqual(challenge["correct_index"], 0)
            self.assertLess(challenge["correct_index"], len(challenge["options"]))
            self.assertTrue(challenge["explanation"])

    def test_same_question_with_reordered_choices_has_same_fingerprint(self):
        prompt = "احسب بسرعة: 23 + 14 = ؟"
        first = challenge_fingerprint(prompt, ["37", "36", "38"])
        reordered = challenge_fingerprint(prompt, ["38", "37", "36"])
        different = challenge_fingerprint(prompt, ["37", "35", "38"])
        self.assertEqual(first, reordered)
        self.assertNotEqual(first, different)

    def test_bluff_challenge_has_exactly_one_false_equation(self):
        challenge = generate_challenge(mode="bluff")
        equations = challenge["prompt"].splitlines()[1:]
        self.assertEqual(challenge["mode"], "bluff")
        self.assertEqual(len(equations), 3)
        false_indexes = []
        for index, line in enumerate(equations):
            expression = line.split(") ", 1)[1]
            left, shown = expression.split(" = ")
            first, second = [int(value.strip()) for value in left.split(" + ")]
            if first + second != int(shown):
                false_indexes.append(index)
        self.assertEqual(false_indexes, [challenge["correct_index"]])
        self.assertEqual(len(false_indexes), 1)

    def test_prediction_challenge_reveals_valid_server_generated_dice_sum(self):
        challenge = generate_challenge(mode="prediction")
        roll = re.search(r"كانت النردتان (\d+) و(\d+)", challenge["explanation"])
        self.assertIsNotNone(roll)
        dice_sum = int(roll.group(1)) + int(roll.group(2))
        self.assertEqual(challenge["mode"], "prediction")
        self.assertEqual(challenge["options"][challenge["correct_index"]], str(dice_sum))
        self.assertTrue(1 <= int(roll.group(1)) <= 6)
        self.assertTrue(1 <= int(roll.group(2)) <= 6)

    def test_duel_mode_is_only_generated_for_four_human_players(self):
        with self.assertRaises(ValueError):
            generate_challenge(player_count=3, mode="duel")
        challenge = generate_challenge(player_count=4, mode="duel")
        self.assertEqual(challenge["mode"], "duel")
        for _ in range(80):
            self.assertNotEqual(generate_challenge(player_count=3)["mode"], "duel")

    def test_four_player_duel_scores_winner_draw_and_rotates_pairs(self):
        code, tokens = self.create_ready_room(4)
        player_ids = [self.store.get_session(token)["player_id"] for token in tokens]
        first_challenge = generate_challenge(player_count=4, mode="duel")
        second_challenge = generate_challenge(player_count=4, mode="duel")
        while challenge_fingerprint(
            second_challenge["prompt"], second_challenge["options"]
        ) == challenge_fingerprint(first_challenge["prompt"], first_challenge["options"]):
            second_challenge = generate_challenge(player_count=4, mode="duel")

        with patch(
            "server.engine.generate_challenge",
            side_effect=[first_challenge, second_challenge],
        ):
            state = self.engine.start_match(code, player_ids[0])
            self.assertEqual(state["phase"], "challenge")
            self.assertEqual(state["challenge"]["mode"], "duel")
            self.assertNotIn("duel_pairs", state["challenge"])
            self.assertNotIn("correct_index", state["challenge"])

            views = [self.engine.get_state(code, player_id) for player_id in player_ids]
            self.assertEqual(
                [view["challenge"]["duel_opponent"] for view in views],
                ["Player 2", "Player 1", "Player 4", "Player 3"],
            )
            correct = first_challenge["correct_index"]
            wrong = (correct + 1) % len(first_challenge["options"])
            answers = [correct, wrong, correct, correct]
            for index, player_id in enumerate(player_ids):
                state = self.engine.submit_challenge(
                    code, player_id, "duel-answer-%02d" % index, answers[index]
                )

            self.assertEqual(state["phase"], "actions")
            self.assertEqual([player["coins"] for player in state["players"]], [13, 10, 12, 12])
            self.assertEqual(
                [duel["outcome"] for duel in state["challenge_result"]["duel_results"]],
                ["first_won", "both_correct"],
            )
            self.assertEqual(state["challenge_result"]["duel_results"][0]["winner_name"], "Player 1")
            self.assertEqual(state["challenge_result"]["duel_results"][0]["reward"], 3)
            self.assertEqual(state["challenge_result"]["answers"][0]["reward"], 3)
            self.assertEqual(state["challenge_result"]["answers"][2]["reward"], 2)
            for duel_result in state["challenge_result"]["duel_results"]:
                self.assertNotIn("player_ids", duel_result)
                self.assertNotIn("winner_id", duel_result)

            for index, player_id in enumerate(player_ids):
                state = self.engine.submit_action(
                    code, player_id, "duel-pass-%02d" % index, "pass"
                )
            with closing(self.store._connect()) as db:
                db.execute(
                    "UPDATE matches SET deadline_at = ? WHERE id = ?",
                    (int(time.time()) - 1, state["match_id"]),
                )
            next_round = self.engine.get_state(code, player_ids[0])
            self.assertEqual(next_round["phase"], "challenge")
            self.assertEqual(next_round["round"], 2)
            self.assertEqual(next_round["challenge"]["mode"], "duel")
            next_views = [
                self.engine.get_state(code, player_id) for player_id in player_ids
            ]
            self.assertEqual(
                [view["challenge"]["duel_opponent"] for view in next_views],
                ["Player 3", "Player 4", "Player 1", "Player 2"],
            )


    def test_black_box_choices_are_private_scored_and_shield_blocks_theft(self):
        event = dict(
            ROUND_EVENTS["black_box"],
            box_contents=["bonus", "shield", "trap"],
        )
        code, tokens, ids, state = self.start_with_event(3, event)
        self.assertEqual(state["phase"], "event")
        self.assertNotIn("box_contents", state["round_event"])
        self.assertIsNone(state["event_result"])

        second_view = self.engine.get_state(code, ids[1])
        self.assertFalse(second_view["private"]["event_submitted"])
        self.assertIsNone(second_view["event_result"])

        choices = [0, 1, 2]
        request_ids = ["black-box-%02d" % index for index in range(3)]
        for index, player_id in enumerate(ids):
            state = self.engine.submit_event(
                code, player_id, request_ids[index],
                "box", amount=0, choice_value=choices[index],
            )
        self.assertEqual(state["phase"], "actions")
        retry = self.engine.submit_event(
            code, ids[0], request_ids[0], "box", amount=0, choice_value=choices[0]
        )
        self.assertEqual(retry["phase"], "actions")
        with self.assertRaises(ActionLocked):
            self.engine.submit_event(
                code, ids[0], "black-box-different", "skip"
            )
        with closing(self.store._connect()) as db:
            event_choice_count = db.execute(
                "SELECT COUNT(*) AS count FROM event_actions "
                "WHERE match_id = ? AND round_no = 1",
                (state["match_id"],),
            ).fetchone()["count"]
        self.assertEqual(event_choice_count, 3)
        self.assertEqual([p["coins"] for p in state["players"]], [12, 10, 9])
        self.assertEqual(state["event_result"]["shield_names"], ["Player 2"])
        self.assertNotIn("shield_player_ids", state["event_result"])
        self.assertEqual(
            [row["outcome"] for row in state["event_result"]["entries"]],
            ["bonus", "shield", "trap"],
        )

        state = self.engine.submit_action(code, ids[0], "black-theft-001", "steal", ids[1])
        state = self.engine.submit_action(code, ids[1], "black-pass-001", "pass")
        state = self.engine.submit_action(code, ids[2], "black-pass-002", "pass")
        self.assertEqual(state["phase"], "result")
        self.assertEqual(state["players"][1]["coins"], 10)
        self.assertTrue(any(row["reason"] == "guarded" for row in state["result"]["blocked_attacks"]))
        with closing(self.store._connect()) as db:
            reasons = [
                row["reason"] for row in db.execute(
                    "SELECT reason FROM coin_ledger WHERE match_id = ? AND round_no = 1",
                    (state["match_id"],),
                ).fetchall()
            ]
        self.assertIn("black_box_bonus", reasons)
        self.assertIn("black_box_trap", reasons)

    def test_bomb_pass_chain_hits_last_carrier_and_records_penalty(self):
        event = dict(ROUND_EVENTS["bomb"])
        code, tokens, ids, state = self.start_with_event(3, event)
        event["bomb_holder_id"] = ids[0]
        self.set_round_event_payload(state["match_id"], 1, event)
        state = self.engine.get_state(code, ids[0])
        self.assertEqual(state["phase"], "event")
        self.assertEqual(state["round_event"]["bomb_starter_name"], "Player 1")

        state = self.engine.submit_event(
            code, ids[0], "bomb-pass-0001", "pass", target_player_id=ids[1]
        )
        state = self.engine.submit_event(
            code, ids[1], "bomb-pass-0002", "pass", target_player_id=ids[2]
        )
        state = self.engine.submit_event(code, ids[2], "bomb-keep-0003", "keep")
        self.assertEqual(state["phase"], "actions")
        self.assertEqual(state["event_result"]["path_names"], ["Player 1", "Player 2", "Player 3"])
        self.assertEqual(state["event_result"]["final_holder_name"], "Player 3")
        self.assertEqual(state["event_result"]["damage"], 2)
        self.assertEqual(state["players"][2]["coins"], 8)
        with closing(self.store._connect()) as db:
            row = db.execute(
                "SELECT delta FROM coin_ledger WHERE match_id = ? AND reason = 'bomb_penalty'",
                (state["match_id"],),
            ).fetchone()
        self.assertEqual(row["delta"], -2)

    def test_bomb_cycle_explodes_on_last_player_who_attempted_to_pass(self):
        event = dict(ROUND_EVENTS["bomb"])
        code, tokens, ids, state = self.start_with_event(3, event)
        event["bomb_holder_id"] = ids[0]
        self.set_round_event_payload(state["match_id"], 1, event)
        self.engine.get_state(code, ids[0])
        self.engine.submit_event(
            code, ids[0], "bomb-loop-0001", "pass", target_player_id=ids[1]
        )
        state = self.engine.submit_event(
            code, ids[1], "bomb-loop-0002", "pass", target_player_id=ids[0]
        )
        state = self.engine.submit_event(code, ids[2], "bomb-loop-keep3", "keep")
        self.assertEqual(state["event_result"]["final_holder_name"], "Player 2")
        self.assertEqual(state["players"][1]["coins"], 8)
        self.assertEqual(state["players"][0]["coins"], 10)

    def test_secret_auction_tie_rotates_winner_and_grants_free_shield(self):
        event = dict(ROUND_EVENTS["secret_auction"])
        code, tokens, ids, state = self.start_with_event(3, event)
        self.assertEqual(state["phase"], "event")
        bids = [3, 3, 1]
        for index, player_id in enumerate(ids):
            state = self.engine.submit_event(
                code, player_id, "auction-bid-%02d" % index, "bid", amount=bids[index]
            )
        self.assertEqual(state["phase"], "actions")
        self.assertEqual(state["event_result"]["winner_name"], "Player 1")
        self.assertEqual(state["event_result"]["winning_bid"], 3)
        self.assertEqual(state["event_result"]["shield_names"], ["Player 1"])
        self.assertEqual(state["players"][0]["coins"], 7)

        state = self.engine.submit_action(code, ids[0], "auction-pass-001", "pass")
        state = self.engine.submit_action(code, ids[1], "auction-steal-01", "steal", ids[0])
        state = self.engine.submit_action(code, ids[2], "auction-pass-002", "pass")
        self.assertEqual(state["phase"], "result")
        self.assertEqual(state["players"][0]["coins"], 7)
        self.assertTrue(any(
            row["reason"] == "guarded" for row in state["result"]["blocked_attacks"]
        ))

    def test_secret_auction_rejects_bid_above_balance_and_locks_after_submit(self):
        event = dict(ROUND_EVENTS["secret_auction"])
        code, tokens, ids, state = self.start_with_event(3, event)
        with self.assertRaises(InvalidInput):
            self.engine.submit_event(code, ids[0], "auction-invalid-01", "bid", amount=11)
        first = self.engine.submit_event(
            code, ids[0], "auction-valid-001", "bid", amount=2
        )
        self.assertTrue(first["private"]["event_submitted"])
        with self.assertRaises(ActionLocked):
            self.engine.submit_event(
                code, ids[0], "auction-valid-002", "bid", amount=1
            )

    def test_court_needs_absolute_majority_and_cannot_vote_for_self(self):
        event = dict(ROUND_EVENTS["court"])
        code, tokens, ids, state = self.start_with_event(3, event)
        with self.assertRaises(InvalidInput):
            self.engine.submit_event(
                code, ids[0], "court-self-0001", "vote", target_player_id=ids[0]
            )
        state = self.engine.submit_event(
            code, ids[0], "court-vote-0001", "vote", target_player_id=ids[2]
        )
        state = self.engine.submit_event(
            code, ids[1], "court-vote-0002", "vote", target_player_id=ids[2]
        )
        state = self.engine.submit_event(code, ids[2], "court-abstain-01", "abstain")
        self.assertEqual(state["phase"], "actions")
        self.assertTrue(state["event_result"]["majority"])
        self.assertEqual(state["event_result"]["target_name"], "Player 3")
        self.assertEqual(state["event_result"]["penalty"], 1)
        self.assertEqual(state["players"][2]["coins"], 9)

    def test_temporary_king_gets_crown_bonus_free_guard_and_extra_steal(self):
        event = dict(ROUND_EVENTS["temporary_king"])
        code, tokens = self.create_ready_room(3)
        ids = [self.store.get_session(token)["player_id"] for token in tokens]
        state = self.engine.start_match(code, ids[0])
        with closing(self.store._connect()) as db:
            db.execute(
                "UPDATE match_players SET coins = CASE player_id "
                "WHEN ? THEN 10 WHEN ? THEN 3 ELSE 7 END WHERE match_id = ?",
                (ids[0], ids[1], state["match_id"]),
            )
        event["king_player_id"] = ids[1]
        self.set_round_event_payload(state["match_id"], 1, event)
        state = self.answer_challenge_for_all(code, state)
        self.assertEqual(state["phase"], "actions")
        self.assertEqual(state["event_result"]["king_name"], "Player 2")
        self.assertEqual(state["players"][1]["coins"], 4)
        king_view = self.engine.get_state(code, ids[1])
        self.assertTrue(king_view["private"]["is_temporary_king"])
        self.assertFalse(self.engine.get_state(code, ids[0])["private"]["is_temporary_king"])

        state = self.engine.submit_action(code, ids[0], "king-target-001", "steal", ids[1])
        state = self.engine.submit_action(code, ids[1], "king-steal-0001", "steal", ids[0])
        state = self.engine.submit_action(code, ids[2], "king-pass-0001", "pass")
        self.assertEqual(state["phase"], "revenge")
        self.assertEqual(state["players"][0]["coins"], 7)
        self.assertEqual(state["players"][1]["coins"], 7)
        self.assertTrue(any(
            row["reason"] == "guarded" for row in state["result"]["blocked_attacks"]
        ))
        self.assertEqual(state["result"]["thefts"][0]["amount"], 3)

    def test_temporary_king_selection_uses_lowest_balance_and_rotates_ties(self):
        players = [
            {"player_id": "seat-1", "seat": 1, "coins": 2},
            {"player_id": "seat-2", "seat": 2, "coins": 2},
            {"player_id": "seat-3", "seat": 3, "coins": 5},
        ]
        first = self.engine._select_temporary_king(players, 2)
        second = self.engine._select_temporary_king(players, 3)
        self.assertEqual(first["player_id"], "seat-1")
        self.assertEqual(second["player_id"], "seat-2")

        players[2]["coins"] = 1
        leader = self.engine._select_temporary_king(players, 4)
        self.assertEqual(leader["player_id"], "seat-3")

    def test_event_timeout_uses_safe_defaults_and_opens_actions(self):
        event = dict(
            ROUND_EVENTS["black_box"],
            box_contents=["bonus", "shield", "trap"],
        )
        code, tokens, ids, state = self.start_with_event(3, event)
        with closing(self.store._connect()) as db:
            db.execute(
                "UPDATE matches SET deadline_at = ? WHERE id = ?",
                (int(time.time()) - 1, state["match_id"]),
            )
        timed_out = self.engine.get_state(code, ids[0])
        self.assertEqual(timed_out["phase"], "actions")
        self.assertEqual(timed_out["players"][0]["coins"], 10)
        self.assertEqual(timed_out["players"][1]["coins"], 10)
        self.assertEqual(timed_out["players"][2]["coins"], 10)
        self.assertEqual(
            [entry["outcome"] for entry in timed_out["event_result"]["entries"]],
            ["لم يختر صندوقًا", "لم يختر صندوقًا", "لم يختر صندوقًا"],
        )


    def test_court_with_four_players_requires_three_votes_for_absolute_majority(self):
        event = dict(ROUND_EVENTS["court"])
        code, tokens, ids, state = self.start_with_event(4, event)
        state = self.engine.submit_event(
            code, ids[0], "court-four-vote-01", "vote", target_player_id=ids[3]
        )
        state = self.engine.submit_event(
            code, ids[1], "court-four-vote-02", "vote", target_player_id=ids[3]
        )
        state = self.engine.submit_event(
            code, ids[2], "court-four-abstain", "abstain"
        )
        state = self.engine.submit_event(
            code, ids[3], "court-four-abstain2", "abstain"
        )
        self.assertEqual(state["phase"], "actions")
        self.assertFalse(state["event_result"]["majority"])
        self.assertIsNone(state["event_result"]["target_name"])
        self.assertEqual(state["event_result"]["penalty"], 0)
        self.assertEqual(state["players"][3]["coins"], 10)

if __name__ == "__main__":
    unittest.main()
