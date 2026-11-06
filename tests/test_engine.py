import concurrent.futures
from contextlib import closing
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from server.engine import (
    ActionLocked,
    MatchEngine,
    MatchNotReady,
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

    def start(self, count=3):
        code, tokens = self.create_ready_room(count)
        state = self.engine.start_match(code, self.store.get_session(tokens[0])["player_id"])
        return code, tokens, state

    def test_three_players_can_start_a_match(self):
        _code, _tokens, state = self.start(3)
        self.assertEqual(state["status"], "active")
        self.assertEqual(state["phase"], "actions")
        self.assertEqual(state["player_count"], 3)
        self.assertEqual([p["coins"] for p in state["players"]], [10, 10, 10])

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
                self.assertEqual(state["phase"], "actions")
                self.assertEqual(state["round"], round_no + 1)
            else:
                self.assertEqual(state["phase"], "finished")
                self.assertEqual(state["status"], "finished")
                self.assertEqual(len(state["ranking"]), 3)
                self.assertEqual(state["ranking"][0]["coins"], 10)


if __name__ == "__main__":
    unittest.main()
