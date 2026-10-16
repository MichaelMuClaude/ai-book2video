import json
import tempfile
import unittest
import wave
from pathlib import Path

from tests import helpers  # noqa: F401
from ai_book2video import script, sfx

CUES = [[0.0, 2.0, "One.", "一。"], [2.0, 4.5, "Two.", "二。"], [4.5, 6.0, "Three.", "三。"]]


def stage_scene(stage: dict):
    raw = {"title": "T", "scenes": [{"kind": "stage", "narration": "One. Two. Three.", "narration_zh": "一。二。三。", "stage": stage}]}
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "s.json"
        path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        return script.load(path).scenes[0]


class BurstKindTests(unittest.TestCase):
    def test_words_choose_the_sound(self):
        self.assertEqual(sfx.burst_kind("BANG!"), "impact")
        self.assertEqual(sfx.burst_kind("FAIL"), "sad")
        self.assertEqual(sfx.burst_kind("BRAVO!"), "chime")
        self.assertEqual(sfx.burst_kind("?"), "question")
        self.assertEqual(sfx.burst_kind("1886"), "pop")


class EventTests(unittest.TestCase):
    def test_events_follow_the_action(self):
        scene = stage_scene({
            "actors": [{"x": 900, "action": "fall", "at": "s2"},
                       {"x": 300, "action": "walk", "to": 900, "at": 0, "dur": 2, "say": [{"text": "Hi", "at": "s3"}]}],
            "props": [{"type": "burst", "x": 500, "y": 500, "at": "s2", "text": "BANG!"},
                      {"type": "train", "x": -400, "to": 2400, "at": "s1", "dur": 2}],
        })
        events = sfx.scene_events(scene, CUES, 6.0)
        names = [name for _, name, _ in events]
        self.assertIn((2.0, "impact", {}), events)
        self.assertIn((2.4, "thud", {}), [(t, n, o) for t, n, o in events if n == "thud"])
        self.assertIn("whistle", names)
        self.assertGreater(names.count("chug"), 4)
        self.assertGreater(names.count("step"), 2)
        self.assertIn((4.5, "pop", {"gain": 0.6}), events)
        self.assertIn("whoosh", names)

    def test_last_scene_has_no_wipe_and_none_silences(self):
        scene = stage_scene({"props": [{"type": "burst", "x": 500, "y": 500, "at": 1, "text": "BANG!", "sfx": "none"}]})
        self.assertEqual(sfx.scene_events(scene, CUES, 6.0, last=True), [])

    def test_every_sound_has_a_level(self):
        self.assertEqual(set(sfx.SOUNDS) | {"engine"}, set(sfx.LEVELS))


class RenderTests(unittest.TestCase):
    def test_track_has_scene_length_and_stays_under_the_voice(self):
        with tempfile.TemporaryDirectory() as folder:
            out = sfx.render([(0.5, "impact", {}), (1.0, "chime", {}), (1.5, "chug", {})], 3.0, Path(folder) / "fx.wav")
            with wave.open(str(out)) as handle:
                self.assertEqual(handle.getframerate(), sfx.RATE)
                self.assertAlmostEqual(handle.getnframes() / sfx.RATE, 3.0, places=2)
                frames = handle.readframes(handle.getnframes())
            peak = max(abs(int.from_bytes(frames[i:i + 2], "little", signed=True)) for i in range(0, len(frames), 2)) / 32767
            self.assertLess(peak, 10 ** (-9 / 20))  # loudest effect is -10 dB, under narration peaks


if __name__ == "__main__":
    unittest.main()
