import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import helpers  # noqa: F401
from ai_book2video import check


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
class CheckTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder)

    def clip(self, name: str, video: str, audio: str | None) -> Path:
        out = self.folder / name
        inputs = ["-f", "lavfi", "-i", video]
        if audio:
            inputs += ["-f", "lavfi", "-i", audio]
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-t", "6", "-pix_fmt", "yuv420p", *(["-shortest"] if audio else []), str(out)], check=True)
        return out

    def test_a_still_silent_film_fails(self):
        report = check.check(self.clip("still.mp4", "color=c=0x0f172a:s=270x480:r=30:d=6", None))
        self.assertFalse(report["passed"])
        self.assertTrue(any("hardly moves" in item for item in report["red"]))
        self.assertTrue(any("no sound" in item for item in report["red"]))

    def test_a_moving_film_with_sound_passes(self):
        report = check.check(self.clip("moving.mp4", "testsrc2=s=270x480:r=30:d=6", "sine=f=220:d=6"))
        self.assertTrue(report["passed"], report["red"])
        self.assertGreater(report["scenes"][0]["motion"], check.SLIDE_MOTION)

    def test_manifest_scenes_are_checked_one_by_one(self):
        video = self.clip("moving.mp4", "testsrc2=s=270x480:r=30:d=6", "sine=f=220:d=6")
        manifest = {"seconds": 6.0, "scenes": [{"index": 1, "start": 0.0, "clip_seconds": 3.0},
                                               {"index": 2, "start": 3.0, "clip_seconds": 3.0}]}
        report = check.check(video, manifest)
        self.assertEqual([s["scene"] for s in report["scenes"]], [1, 2])


if __name__ == "__main__":
    unittest.main()
