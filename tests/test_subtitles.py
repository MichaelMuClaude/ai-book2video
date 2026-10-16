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

class TimedCueTests(unittest.TestCase):
    SPOKEN = [["The", 0.25, 0.33], ["classmate", 0.33, 0.88], ["pulls", 0.88, 1.11], ["out", 1.11, 1.24], ["a", 1.24, 1.30],
              ["pocket", 1.30, 1.64], ["knife", 1.64, 2.18], [".", 2.18, 2.28], ["Then", 2.28, 2.44], ["it", 2.44, 2.53],
              ["hits", 2.53, 2.76], ["him", 2.76, 3.28], [".", 3.28, 3.43]]

    def test_sentences_start_when_spoken(self):
        cues = subtitles.timed_cues(["The classmate pulls out a pocket knife.", "Then it hits him."], ["一。", "二。"],
                                    self.SPOKEN, 0.0, 3.43)
        self.assertEqual(cues[0].start, 0.0)
        self.assertAlmostEqual(cues[1].start, 2.23, places=2)  # "Then" at 2.28, shown 0.05 s early
        self.assertEqual(cues[0].end, cues[1].start)
        self.assertEqual(cues[1].end, 3.43)
        self.assertIn(["knife", 1.64], cues[0].words)

    def test_unmatched_sentence_falls_back_to_a_share(self):
        cues = subtitles.timed_cues(["The classmate pulls out a pocket knife.", "Zzz.", "Then it hits him."], ["一。", "二。", "三。"],
                                    self.SPOKEN, 0.0, 3.43)
        self.assertLess(cues[0].start, cues[1].start)
        self.assertLess(cues[1].start, cues[2].start)
        self.assertTrue(cues[1].words)  # estimated

    def test_hyphens_and_numbers_still_align(self):
        spoken = [["A", 0.1, 0.2], ["ten", 0.2, 0.4], ["-", 0.4, 0.4], ["year", 0.4, 0.6], ["-", 0.6, 0.6], ["old", 0.6, 0.8],
                  [".", 0.8, 0.9], ["In", 1.0, 1.1], ["1884", 1.1, 1.9], [".", 1.9, 2.0]]
        cues = subtitles.timed_cues(["A ten-year-old.", "In 1884."], ["一。", "二。"], spoken, 0.0, 2.0)
        self.assertAlmostEqual(cues[1].start, 0.95, places=2)
        self.assertIn(["1884", 1.1], cues[1].words)


if __name__ == "__main__":
    unittest.main()
