import unittest

from tests import helpers  # noqa: F401
from ai_book2video import subtitles


class SubtitleTests(unittest.TestCase):
    def test_timestamp_format(self):
        self.assertEqual(subtitles.timestamp(0), "00:00:00,000")
        self.assertEqual(subtitles.timestamp(3.5), "00:00:03,500")
        self.assertEqual(subtitles.timestamp(3725.25), "01:02:05,250")

    def test_cues_cover_the_span_without_gaps_at_the_end(self):
        text = "First sentence here. Second sentence is a little longer than the first one. Third."
        cues = subtitles.cues_for(text, 10.0, 16.0)
        self.assertAlmostEqual(cues[0].start, 10.0)
        self.assertAlmostEqual(cues[-1].end, 16.0)
        for earlier, later in zip(cues, cues[1:]):
            self.assertLessEqual(earlier.start, later.start)

    def test_wrap_breaks_long_lines(self):
        lines = subtitles.wrap("one two three four five six seven eight nine ten eleven twelve", width=20)
        self.assertTrue(all(len(line) <= 20 for line in lines))
        self.assertGreater(len(lines), 1)

    def test_unspaced_text_is_chunked(self):
        lines = subtitles.wrap("字" * 100, width=42)
        self.assertEqual(len(lines), 3)


if __name__ == "__main__":
    unittest.main()
