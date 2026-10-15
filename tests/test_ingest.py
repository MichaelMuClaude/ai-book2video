import unittest

from tests import helpers  # noqa: F401  (sets sys.path)
from ai_book2video import ingest
from ai_book2video.errors import Book2VideoError


class SplitTests(unittest.TestCase):
    def test_markdown_headings_become_sections(self):
        text = "# Book\n\n" + " ".join(["word"] * 40) + "\n\n## First\n\nAlpha beta.\n\n## Second\n\nGamma delta."
        method, sections = ingest.split_sections(text)
        self.assertEqual(method, "headings")
        titles = [title for title, _ in sections]
        self.assertIn("First", titles)
        self.assertIn("Second", titles)
        self.assertIn("Alpha beta.", dict(sections)["First"])

    def test_chapter_lines_when_no_headings(self):
        filler = " ".join(["filler"] * 40)
        text = f"Chapter 1: Start\n{filler}\nChapter 2: Middle\n{filler}\nChapter 3: End\n{filler}"
        method, sections = ingest.split_sections(text)
        self.assertEqual(method, "chapters")
        self.assertEqual([title for title, _ in sections], ["Chapter 1: Start", "Chapter 2: Middle", "Chapter 3: End"])

    def test_sentences_that_start_with_chapter_are_not_headings(self):
        filler = " ".join(["filler"] * 40)
        text = f"Chapter 1: Start\n{filler}\nchapter explains how the parts fit.\n{filler}\nChapter 2: End\n{filler}"
        method, sections = ingest.split_sections(text)
        self.assertEqual(method, "chapters")
        self.assertEqual([title for title, _ in sections], ["Chapter 1: Start", "Chapter 2: End"])
        self.assertIn("chapter explains how the parts fit.", dict(sections)["Chapter 1: Start"])

    def test_size_split_for_plain_text(self):
        paragraph = " ".join(["word"] * 500)
        text = "\n\n".join([paragraph] * 5)
        method, sections = ingest.split_sections(text)
        self.assertEqual(method, "size")
        self.assertGreaterEqual(len(sections), 2)
        self.assertEqual(sections[0][0], "Part 1")


class CjkCountTests(unittest.TestCase):
    def test_each_cjk_character_counts_as_a_word(self):
        from ai_book2video.text import count_words

        self.assertEqual(count_words("中文字符"), 4)
        self.assertEqual(count_words("Hello 世界"), 3)

    def test_chinese_document_is_not_refused_as_too_short(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "chapter.md"
            path.write_text("# 第一章\n\n" + "这是一段很长的中文文本，用来测试字数统计。" * 8, encoding="utf-8")
            book = ingest.ingest(path)
            self.assertGreater(book["words"], 50)


class PartTests(unittest.TestCase):
    def test_section_part_splits_long_sections(self):
        section = {"text": " ".join(f"w{i}" for i in range(10))}
        total, part = ingest.section_part(section, 2, 4)
        self.assertEqual(total, 3)
        self.assertEqual(part, "w4 w5 w6 w7")

    def test_section_part_rejects_out_of_range(self):
        with self.assertRaises(Book2VideoError):
            ingest.section_part({"text": "a b c"}, 5, 2)

    def test_other_formats_are_refused_with_a_hint(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "book.pdf"
            path.write_bytes(b"%PDF-1.4")
            with self.assertRaises(Book2VideoError) as context:
                ingest.ingest(path)
            self.assertIn("Convert the document to Markdown first", str(context.exception))

    def test_short_documents_are_refused(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tiny.md"
            path.write_text("just a few words here", encoding="utf-8")
            with self.assertRaises(Book2VideoError):
                ingest.ingest(path)


if __name__ == "__main__":
    unittest.main()
