import json
import tempfile
import unittest
from pathlib import Path

from tests import helpers  # noqa: F401
from ai_book2video import script
from ai_book2video.errors import Book2VideoError

GOOD = {
    "title": "Demo",
    "scenes": [
        {"kind": "title", "heading": "Demo", "body": "A tour", "narration": "Welcome to the demo."},
        {"kind": "bullets", "heading": "Three parts", "items": ["One", "Two"], "narration": "Three parts, two shown."},
        {"kind": "text", "heading": "Idea", "body": "Short words.", "narration": "The idea in full sentences."},
        {"kind": "quote", "body": "A quote.", "source": "Chapter 1", "narration": "The author says this."},
    ],
}


class CheckTests(unittest.TestCase):
    def test_good_script_has_no_errors(self):
        errors, warnings = script.check(GOOD)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_missing_narration_is_an_error(self):
        bad = json.loads(json.dumps(GOOD))
        del bad["scenes"][0]["narration"]
        errors, _ = script.check(bad)
        self.assertTrue(any("narration" in error for error in errors))

    def test_unknown_kind_and_missing_heading(self):
        bad = {"title": "X", "scenes": [{"kind": "video", "narration": "a"}, {"kind": "text", "narration": "b"}]}
        errors, _ = script.check(bad)
        self.assertTrue(any("kind must be one of" in error for error in errors))
        self.assertTrue(any("need a 'heading'" in error for error in errors))
        self.assertTrue(any("need a 'body'" in error for error in errors))

    def test_overlong_narration_is_an_error_and_long_slides_warn(self):
        long_narration = " ".join(["word"] * 300)
        bad = {"title": "X", "scenes": [{"kind": "text", "heading": "h", "body": " ".join(["x"] * 90), "narration": long_narration}]}
        errors, warnings = script.check(bad)
        self.assertTrue(any("split the scene" in error for error in errors))
        self.assertTrue(any("slide text has more" in warning for warning in warnings))

    def test_duplicate_ids_are_errors(self):
        bad = {"title": "X", "scenes": [
            {"kind": "text", "id": "a", "heading": "h", "body": "b", "narration": "one"},
            {"kind": "text", "id": "a", "heading": "h", "body": "b", "narration": "two"},
        ]}
        errors, _ = script.check(bad)
        self.assertTrue(any("duplicate id" in error for error in errors))

    def test_load_reports_problems_and_returns_scenes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "s.json"
            path.write_text(json.dumps(GOOD), encoding="utf-8")
            loaded = script.load(path)
            self.assertEqual(len(loaded.scenes), 4)
            self.assertEqual(loaded.scenes[1].items, ["One", "Two"])
            self.assertGreater(loaded.seconds_estimate, 0)
            path.write_text(json.dumps({"title": "", "scenes": []}), encoding="utf-8")
            with self.assertRaises(Book2VideoError):
                script.load(path)


if __name__ == "__main__":
    unittest.main()
