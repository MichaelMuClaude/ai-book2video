import json
import re
import tempfile
import unittest
from pathlib import Path

from tests import helpers  # noqa: F401
from ai_book2video import collage, motion, script, svgstage

CUES = [[0.0, 2.0, "One.", "一。"], [2.0, 4.5, "Two.", "二。"], [4.5, 6.0, "Three.", "三。"]]
PALETTE = {"bg": "#f3e6c8", "accent": "#ead9b3", "card": "#1b1b3a", "ink": "#111111", "card_ink": "#ffffff"}


def stage_scene(stage: dict, style: str = "collage"):
    raw = {"title": "T", "style": style,
           "scenes": [{"kind": "stage", "narration": "One. Two. Three.", "narration_zh": "一。二。三。", "stage": stage}]}
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "s.json"
        path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        return script.load(path)


def no_transform_on_animated_elements(page: str) -> list[str]:
    """Every element with a data-id must not also carry a static `transform=` attribute: the engine
    writes el.style.transform every frame (identity or not), which silently replaces an SVG
    `transform` attribute on the same element and strips its position. Returns the offending ids."""
    offenders = []
    for tag in re.findall(r"<[a-zA-Z]+\b[^>]*>", page):
        if "data-id=" in tag and " transform=" in tag:
            gid = re.search(r'data-id="([^"]*)"', tag)
            offenders.append(gid.group(1) if gid else tag[:60])
    return offenders


class TransformAttributeRegressionTests(unittest.TestCase):
    """The exact bug found and fixed while building collage.py (see LESSONS.md): a data-id element's
    own SVG transform attribute gets silently overridden by the engine. Checked on both renderers so
    neither can reintroduce it."""

    STAGE = {"actors": [{"label": "A", "x": 500, "action": "talk", "say": [{"text": "Hi", "at": "s1"}]},
                        {"label": "B", "x": 1300, "action": "walk", "to": 1500, "at": 0, "dur": 2}],
             "props": [{"type": "letter", "x": 800}, {"type": "burst", "x": 900, "y": 500, "text": "BANG!", "at": "s2"},
                       {"type": "clock", "x": 600, "spin": 1, "at": 0, "dur": 4}]}

    def test_collage_has_no_offending_transforms(self):
        tl = __import__("ai_book2video.motion", fromlist=["Timeline"]).Timeline()
        page = collage.stage(stage_scene(self.STAGE).scenes[0], PALETTE, tl, CUES, 6.0)
        self.assertEqual(no_transform_on_animated_elements(page), [])

    def test_svgstage_has_no_offending_transforms(self):
        tl = __import__("ai_book2video.motion", fromlist=["Timeline"]).Timeline()
        page = svgstage.stage(stage_scene(self.STAGE, "stick").scenes[0], PALETTE, tl, CUES, 6.0)
        self.assertEqual(no_transform_on_animated_elements(page), [])


class CollageStageTests(unittest.TestCase):
    def page(self, stage):
        loaded = stage_scene(stage)
        return motion.scene_page(loaded.scenes[0], 1, "T", 6.0, CUES, style=loaded.style)

    def test_renders_svg_with_camera(self):
        page = self.page({"actors": [{"label": "A", "x": 500, "action": "stand"}]})
        self.assertIn('<svg class="stage-svg"', page)
        self.assertIn('data-id="cam"', page)
        self.assertIn('data-id="ca0"', page)

    def test_every_animated_id_exists(self):
        stage = {
            "actors": [{"label": "A", "x": 600, "action": "fall", "faces": [{"at": "s1", "face": "surprised"}],
                       "say": [{"text": "Hi!", "at": "s1", "dur": 1}]},
                      {"label": "B", "x": 1300, "action": "talk"}],
            "props": [{"type": "letter", "x": 800, "to": 1200, "at": "s1", "dur": 2},
                      {"type": "burst", "x": 600, "y": 600, "at": "s2", "text": "BANG!"},
                      {"type": "clock", "x": 400, "spin": 2, "at": 0, "dur": 5}],
        }
        page = self.page(stage)
        elements = set(re.findall(r'data-id="([^"]+)"', page))
        anims = json.loads(re.search(r"const ANIMS = (\[.*?\]); const INIT", page, re.S).group(1))
        self.assertEqual({a["id"] for a in anims} - elements, set())

    def test_letters_and_headlines_render(self):
        page = self.page({"props": [{"type": "letter", "x": 500}, {"type": "burst", "x": 900, "y": 500, "text": "URGENT"}]})
        self.assertIn("URGENT", page.upper())

    def test_speech_becomes_a_note(self):
        page = self.page({"actors": [{"label": "A", "x": 500, "action": "stand", "say": [{"text": "Hello there", "at": 0.2}]}]})
        self.assertIn("Hello there", page)


class StyleSelectionTests(unittest.TestCase):
    def test_default_style_is_stick(self):
        raw = {"title": "T", "scenes": [{"kind": "stage", "narration": "Hi.", "stage": {}}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "s.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            loaded = script.load(path)
        self.assertEqual(loaded.style, "stick")

    def test_bad_style_is_rejected(self):
        raw = {"title": "T", "style": "watercolour", "scenes": [{"kind": "stage", "narration": "Hi.", "stage": {}}]}
        errors, _ = script.check(raw)
        self.assertTrue(any("style" in e for e in errors))

    def test_stick_and_collage_render_differently_for_the_same_scene(self):
        loaded = stage_scene({"actors": [{"label": "A", "x": 500, "action": "stand"}]}, style="collage")
        collage_page = motion.scene_page(loaded.scenes[0], 1, "T", 6.0, CUES, style="collage")
        stick_page = motion.scene_page(loaded.scenes[0], 1, "T", 6.0, CUES, style="stick")
        self.assertNotEqual(collage_page, stick_page)
        self.assertIn("paper-grain", collage_page)
        self.assertNotIn("paper-grain", stick_page)


if __name__ == "__main__":
    unittest.main()
