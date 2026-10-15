import json
import re
import tempfile
import unittest
from pathlib import Path

from tests import helpers  # noqa: F401
from ai_book2video import motion, script, svgstage, subtitles


def stage_scene(stage: dict, narration: str = "One. Two. Three.", zh: str = "一。二。三。"):
    raw = {"title": "T", "scenes": [{"kind": "stage", "narration": narration, "narration_zh": zh, "stage": stage}]}
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "s.json"
        path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        return script.load(path).scenes[0]


CUES = [[0.0, 2.0, "One.", "一。"], [2.0, 4.5, "Two.", "二。"], [4.5, 6.0, "Three.", "三。"]]


class WhenTests(unittest.TestCase):
    def test_numbers_pass_through(self):
        self.assertEqual(svgstage.when(1.5, CUES), 1.5)

    def test_sentence_references(self):
        self.assertEqual(svgstage.when("s2", CUES), 2.0)
        self.assertEqual(svgstage.when("s2+0.5", CUES), 2.5)
        self.assertEqual(svgstage.when("s3-1", CUES), 3.5)

    def test_out_of_range_sentence_uses_the_last(self):
        self.assertEqual(svgstage.when("s9", CUES), 4.5)


class StagePageTests(unittest.TestCase):
    def page(self, stage):
        scene = stage_scene(stage)
        return motion.scene_page(scene, 1, "T", 6.0, CUES)

    def test_stage_is_svg_with_camera(self):
        page = self.page({"background": "street", "actors": [{"label": "A", "x": 500, "action": "walk", "to": 900, "at": "s1", "dur": 3}]})
        self.assertIn('<svg class="stage-svg"', page)
        self.assertIn('data-id="cam"', page)
        self.assertIn('data-id="sa0"', page)

    def test_every_animated_id_exists(self):
        stage = {
            "background": "field",
            "actors": [
                {"label": "A", "x": 600, "action": "fall", "at": "s2", "faces": [{"at": "s1", "face": "surprised"}],
                 "say": [{"text": "Hi!", "at": "s1", "dur": 1}]},
                {"label": "B", "x": 1300, "action": "talk"},
            ],
            "props": [{"type": "car", "x": -300, "to": 2200, "at": "s2-1", "dur": 2},
                      {"type": "burst", "x": 600, "y": 600, "at": "s2", "text": "BANG!"}],
        }
        page = self.page(stage)
        elements = set(re.findall(r'data-id="([^"]+)"', page))
        anims = json.loads(re.search(r"const ANIMS = (\[.*?\]); const INIT", page, re.S).group(1))
        self.assertEqual({a["id"] for a in anims} - elements, set())

    def test_fall_lands_on_its_sentence(self):
        page = self.page({"actors": [{"x": 900, "action": "fall", "at": "s2"}]})
        anims = json.loads(re.search(r"const ANIMS = (\[.*?\]); const INIT", page, re.S).group(1))
        falls = [a for a in anims if a["id"] == "sa0-f" and a["p"] == "r"]
        self.assertEqual(falls[0]["at"], 2.0)

    def test_bubble_flips_where_a_walker_ends_up(self):
        walker = {"x": 100, "action": "walk", "to": 1800, "at": 0, "dur": 2, "say": [{"text": "Made it!", "at": "s2"}]}
        flipped = re.compile(r"translate\(-\d+ -470\)")
        self.assertRegex(self.page({"actors": [walker]}), flipped)
        stander = {"x": 100, "action": "stand", "say": [{"text": "Made it!", "at": "s2"}]}
        self.assertNotRegex(self.page({"actors": [stander]}), flipped)

    def test_camera_never_shows_an_edge(self):
        page = self.page({"actors": [{"x": 0, "action": "stand"}, {"x": 1920, "action": "stand"}]})
        anims = json.loads(re.search(r"const ANIMS = (\[.*?\]); const INIT", page, re.S).group(1))
        zooms = {}
        for a in anims:
            if a["id"] == "cam" and a["p"] in ("s", "x", "y"):
                zooms.setdefault(a["at"], {})[a["p"]] = a["to"]
        for values in zooms.values():
            if "x" in values and "s" in values:
                limit = svgstage.WIDTH / 2 * (values["s"] - 1) + 0.01
                self.assertLessEqual(abs(values["x"]), limit)


class PairTests(unittest.TestCase):
    def test_pairs_share_time_by_english_length(self):
        cues = subtitles.pair_cues(["One two three.", "Four."], ["一二三。", "四。"], 0.0, 4.0)
        self.assertEqual([c.zh for c in cues], ["一二三。", "四。"])
        self.assertAlmostEqual(cues[0].end, 3.0)
        self.assertAlmostEqual(cues[-1].end, 4.0)


if __name__ == "__main__":
    unittest.main()
