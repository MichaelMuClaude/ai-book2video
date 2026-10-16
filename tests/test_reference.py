import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import helpers  # noqa: F401
from ai_book2video import reference


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
class AnalyzeTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder)

    def make_clip(self) -> Path:
        clip = self.folder / "clip.mp4"
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", "color=c=0xff5a5f:s=180x320:d=2:r=10",
             "-f", "lavfi", "-i", "color=c=0x1b1b3a:s=180x320:d=1.5:r=10",
             "-f", "lavfi", "-i", "color=c=0x22d3ee:s=180x320:d=2:r=10",
             "-filter_complex", "[0][1][2]concat=n=3:v=1[v]", "-map", "[v]", str(clip)],
            check=True,
        )
        return clip

    def test_cuts_shots_and_colours(self):
        report = reference.analyze(self.make_clip(), self.folder / "ref")
        self.assertEqual(report["aspect"], "portrait")
        self.assertEqual(len(report["cuts"]), 2)
        self.assertAlmostEqual(report["cuts"][0], 2.0, delta=0.15)
        self.assertAlmostEqual(report["cuts"][1], 3.5, delta=0.15)
        self.assertEqual(report["shots"], 3)
        self.assertEqual(report["motion"]["level"], "calm")
        tops = [c["hex"] for c in report["colours"][:3]]
        for want in ("ff5a5f", "1b1b3a", "22d3ee"):
            self.assertTrue(any(sum((int(t[i:i + 2], 16) - int(want[i - 1:i + 1], 16)) ** 2 for i in (1, 3, 5)) < 30 ** 2
                                for t in tops), f"{want} not among {tops}")
        self.assertEqual(set(report["suggested_palettes"][0]), {"bg", "accent", "card"})
        self.assertTrue((self.folder / "ref" / "reference.md").exists())
        self.assertTrue(Path(report["contact_sheet"]).exists())

    def test_a_picture_has_colours_but_no_cuts(self):
        picture = self.folder / "look.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=0x06d6a0:s=200x200",
                        "-frames:v", "1", str(picture)], check=True)
        report = reference.analyze(picture, self.folder / "pic")
        self.assertEqual(report["cuts"], [])
        self.assertEqual(report["shots"], 0)
        self.assertEqual(report["colours"][0]["share"], 1.0)


if __name__ == "__main__":
    unittest.main()
