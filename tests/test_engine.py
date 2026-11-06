import concurrent.futures
import json
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

    def start(self, count=3):
        code, tokens = self.create_ready_room(count)
        state = self.engine.start_match(code, self.store.get_session(tokens[0])["player_id"])
        return code, tokens, state

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

if __name__ == "__main__":
    unittest.main()
