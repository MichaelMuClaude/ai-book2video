import hashlib
import json
import tempfile
import unittest
import wave
from pathlib import Path

from tests import helpers  # noqa: F401
from ai_book2video import music, script


class MusicLoopTests(unittest.TestCase):
    def test_loop_has_the_promised_length_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as folder:
            first = music.render_loop("tense", Path(folder) / "a.wav")
            second = music.render_loop("tense", Path(folder) / "b.wav")
            with wave.open(str(first)) as handle:
                seconds = handle.getnframes() / handle.getframerate()
            self.assertAlmostEqual(seconds, music.loop_seconds("tense"), places=2)
            digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
            self.assertEqual(digest(first), digest(second), "same mood, same seed: identical music")

    def test_chords_stay_in_a_comfortable_range(self):
        for spec in music.MOODS.values():
            for offset, quality in spec["chords"]:
                tones = music._chord_tones(spec["tonic"], offset, quality)
                self.assertTrue(all(55 <= t <= 72 for t in tones), tones)

    def test_script_music_values(self):
        base = {"title": "T", "scenes": [{"kind": "title", "heading": "T", "narration": "Hello."}]}
        for value in ("calm", "reflective", "tense", "none"):
            errors, _ = script.check(dict(base, music=value))
            self.assertEqual(errors, [], value)
        errors, _ = script.check(dict(base, music="disco"))
        self.assertTrue(any("music" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
