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
            "wagerAction", "passAction", "counterstrikeAction", "rematchButton"
        }
        self.assertTrue(required.issubset(html_ids))
        self.assertIn("MIN_PLAYERS = 3", self.engine)
        self.assertIn("MAX_PLAYERS = 4", self.engine)


if __name__ == "__main__":
    unittest.main()
