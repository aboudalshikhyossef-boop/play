import re
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class IdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.html_attrs = None
        self.viewport_found = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.append(values["id"])
        if tag == "html":
            self.html_attrs = values
        if tag == "meta" and values.get("name", "").lower() == "viewport":
            self.viewport_found = "width=device-width" in values.get("content", "")


class LegacyUIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        cls.css = (ROOT / "web" / "css" / "main.css").read_text(encoding="utf-8")
        cls.js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        cls.engine = (ROOT / "server" / "engine.py").read_text(encoding="utf-8")
        cls.challenge_source = (ROOT / "server" / "challenges.py").read_text(encoding="utf-8")
        cls.app = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
        cls.parser = IdParser()
        cls.parser.feed(cls.html)

    def test_document_is_arabic_rtl_with_device_viewport(self):
        self.assertEqual(self.parser.html_attrs.get("lang"), "ar")
        self.assertEqual(self.parser.html_attrs.get("dir"), "rtl")
        self.assertTrue(self.parser.viewport_found)

    def test_javascript_references_only_existing_unique_element_ids(self):
        html_ids = set(self.parser.ids)
        referenced_ids = set(re.findall(r'byId\("([^"]+)"\)', self.js))
        self.assertTrue(referenced_ids)
        self.assertEqual(referenced_ids - html_ids, set())
        counts = Counter(self.parser.ids)
        self.assertEqual([item for item, count in counts.items() if count > 1], [])

    def test_legacy_browser_transport_contract(self):
        self.assertIn("XMLHttpRequest", self.js)
        self.assertNotRegex(self.js, r"\bfetch\s*\(")
        self.assertNotIn("=>", self.js)
        self.assertNotRegex(self.css, r"display\s*:\s*grid")

    def test_mobile_touch_targets_and_text_wrapping_are_present(self):
        self.assertRegex(self.css, r"\.button\s*\{[^}]*min-height\s*:\s*49px")
        self.assertRegex(self.css, r"\.text-input[^}]*min-height\s*:\s*48px")
        self.assertIn("word-wrap: break-word", self.css)
        self.assertNotIn("overflow-x: hidden", self.css)


    def test_three_or_four_player_game_arena_is_present(self):
        html_ids = set(self.parser.ids)
        required = {
            "startMatchButton", "gameScreen", "actionPanel", "revengePanel",
            "resultPanel", "finalPanel", "stealAction", "guardAction",
            "wagerAction", "passAction", "counterstrikeAction", "rematchButton",
            "rulesToggle", "rulesPanel", "roundEventCard", "roundEventTitle",
            "roundEventDescription", "roundEventEffect", "challengePanel",
            "challengeTitle", "challengeFamily", "challengePrompt", "challengeAnswer",
            "challengeSubmit", "challengeStatus", "challengeSummary",
            "challengeCorrectAnswer", "challengeExplanation", "challengeResults"
        }
        self.assertTrue(required.issubset(html_ids))
        self.assertIn("MIN_PLAYERS = 3", self.engine)
        self.assertIn("MAX_PLAYERS = 4", self.engine)

    def test_beginner_rules_and_round_event_ui_are_wired(self):
        self.assertIn("كل عملة تساوي نقطة", self.html)
        self.assertIn("فرصة الفوز 50٪", self.html)
        self.assertIn("اختيارات الجميع تبقى سرية", self.html)
        self.assertIn("function renderRoundEvent(event)", self.js)
        self.assertIn('byId("rulesToggle").onclick = toggleRules', self.js)
        self.assertIn('var isHidden = /\\bhidden\\b/', self.js)
        for event_id in ("market_rush", "free_guard", "bounty", "double_revenge", "high_stakes"):
            self.assertIn(event_id, self.engine)

    def test_round_challenge_is_a_private_server_scored_stage(self):
        self.assertIn("function renderChallenge(challenge, result, state)", self.js)
        self.assertIn("function submitChallenge()", self.js)
        self.assertIn("/match/challenge", self.app)
        self.assertIn("CHALLENGE_SECONDS = 25", self.challenge_source)
        self.assertIn("CHALLENGE_REWARD = 2", self.challenge_source)
        self.assertIn("answer_index", self.engine)
        self.assertIn("challenge_result_json", self.engine)
        self.assertIn("correct_index", self.challenge_source)
        self.assertIn("challenge_submitted", self.engine)


if __name__ == "__main__":
    unittest.main()
