import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import helpers  # noqa: F401
from ai_book2video import motion, script


def scene_from(raw: dict):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "s.json"
        path.write_text(json.dumps({"title": "Demo & <Co>", "scenes": [raw]}), encoding="utf-8")
        return script.load(path).scenes[0], "Demo & <Co>"


SCENES = {
    "title": {"kind": "title", "heading": "Europe in Danger", "body": "A short tour.", "narration": "n"},
    "text": {"kind": "text", "heading": "Two men", "body": "One sentence. Two sentences.", "narration": "n"},
    "bullets": {"kind": "bullets", "heading": "Parts", "items": ["one", "two", "three"], "narration": "n"},
    "quote": {"kind": "quote", "body": "the right to tell people", "source": "Orwell", "narration": "n"},
    "stat": {"kind": "stat", "value": 2, "suffix": " survivors", "heading": "both lived", "narration": "n"},
}


class MotionPageTests(unittest.TestCase):
    def test_every_kind_renders_a_page_with_a_timeline(self):
        for kind, raw in SCENES.items():
            scene, title = scene_from(raw)
            page = motion.scene_page(scene, 1, title, 6.0)
            self.assertIn("window.setT", page, kind)
            self.assertIn("const ANIMS", page, kind)
            self.assertIn('data-id="wipe-out"', page, kind)
            self.assertIn('data-id="wipe-in"', page, kind)

    def test_every_animated_id_is_an_element(self):
        for kind, raw in SCENES.items():
            scene, title = scene_from(raw)
            page = motion.scene_page(scene, 2, title, 7.0)
            elements = set(re.findall(r'data-id="([^"]+)"', page))
            anims = json.loads(re.search(r"const ANIMS = (\[.*?\]); const INIT", page, re.S).group(1))
            self.assertEqual({a["id"] for a in anims} - elements, set(), kind)

    def test_slide_text_is_escaped(self):
        scene, title = scene_from(SCENES["title"])
        page = motion.scene_page(scene, 1, title, 6.0)
        self.assertIn("Demo &amp; &lt;Co&gt;", page)
        self.assertNotIn("Demo & <Co>", page)

    def test_stat_counts_to_the_value(self):
        scene, title = scene_from(SCENES["stat"])
        page = motion.scene_page(scene, 1, title, 6.0)
        anims = json.loads(re.search(r"const ANIMS = (\[.*?\]); const INIT", page, re.S).group(1))
        counts = [a for a in anims if a["p"] == "count"]
        self.assertEqual(counts[0]["to"], 2.0)

    @unittest.skipUnless(shutil.which("node"), "node is needed to check the engine script")
    def test_engine_script_parses(self):
        scene, title = scene_from(SCENES["text"])
        page = motion.scene_page(scene, 1, title, 6.0)
        code = re.search(r"<script>(.*)</script>", page, re.S).group(1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "engine.js"
            path.write_text(code, encoding="utf-8")
            result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
