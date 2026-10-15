"""Turn a book or document into an ordered list of sections."""

from __future__ import annotations

import re
from pathlib import Path

from ai_book2video.errors import Book2VideoError
from ai_book2video.text import count_words, slice_words

INPUT_SUFFIXES = {".md", ".markdown", ".txt"}

HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)
CHAPTER_LINE = re.compile(r"^[ \t]*((Chapter|Part|Section|Lesson|Unit)[ \t]+(\d+|[IVXLC]+)\b[^\n]{0,80})[ \t]*$", re.MULTILINE)
CHUNK_WORDS = 1200


def read_text(path: Path) -> str:
    """Return the document text. Only Markdown and plain text are read; convert other formats first."""
    suffix = path.suffix.lower()
    if suffix not in INPUT_SUFFIXES:
        raise Book2VideoError(
            f"unsupported input {suffix or '(no extension)'}: ai-book2video reads Markdown (.md) or plain text (.txt). "
            "Convert the document to Markdown first."
        )
    return path.read_text(encoding="utf-8", errors="replace")


def guess_title(text: str, fallback: str) -> str:
    match = HEADING.search(text)
    if match and len(match.group(1)) == 1:
        return match.group(2).strip()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return fallback


def word_count(text: str) -> int:
    return count_words(text)


def _clean(text: str) -> str:
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_markdown(text: str) -> list[tuple[str, str]]:
    """Split on Markdown headings. Returns (title, body) pairs."""
    matches = list(HEADING.finditer(text))
    if not matches:
        return []
    sections: list[tuple[str, str]] = []
    preface = text[: matches[0].start()].strip()
    if word_count(preface) > 30:
        sections.append(("Introduction", preface))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(2).strip(), text[match.end() : end].strip()))
    return sections


def split_chapters(text: str) -> list[tuple[str, str]]:
    """Split on lines such as 'Chapter 3: Title' or 'Part II'."""
    matches = list(CHAPTER_LINE.finditer(text))
    if len(matches) < 2:
        return []
    sections: list[tuple[str, str]] = []
    preface = text[: matches[0].start()].strip()
    if word_count(preface) > 30:
        sections.append(("Front matter", preface))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip()[:120], text[match.end() : end].strip()))
    return sections


def split_by_size(text: str, target: int = CHUNK_WORDS) -> list[tuple[str, str]]:
    """Fallback: group paragraphs into parts of about `target` words."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    parts: list[tuple[str, str]] = []
    current: list[str] = []
    count = 0
    for paragraph in paragraphs:
        current.append(paragraph)
        count += word_count(paragraph)
        if count >= target:
            parts.append((f"Part {len(parts) + 1}", "\n\n".join(current)))
            current, count = [], 0
    if current:
        parts.append((f"Part {len(parts) + 1}", "\n\n".join(current)))
    return parts


def split_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (method, sections). Tries headings, then chapter lines, then size."""
    for method, splitter in (("headings", split_markdown), ("chapters", split_chapters)):
        sections = splitter(text)
        if sections:
            return method, sections
    return "size", split_by_size(text)


def ingest(path: Path, title: str | None = None) -> dict:
    """Read a document and return the book structure used by the other commands."""
    if not path.exists():
        raise Book2VideoError(f"file not found: {path}")
    raw = _clean(read_text(path))
    if word_count(raw) < 50:
        raise Book2VideoError("the document has fewer than 50 words; nothing to make a video from")
    method, pairs = split_sections(raw)
    sections = []
    for section_title, body in pairs:
        body = _clean(body)
        if not body:
            continue
        sections.append(
            {
                "id": f"s{len(sections) + 1:02d}",
                "title": section_title,
                "words": word_count(body),
                "text": body,
            }
        )
    if not sections:
        raise Book2VideoError("no readable text found")
    return {
        "title": title or guess_title(raw, path.stem),
        "source": str(path),
        "split": method,
        "words": sum(section["words"] for section in sections),
        "sections": sections,
    }


def find_section(book: dict, section_id: str) -> dict:
    for section in book["sections"]:
        if section["id"] == section_id:
            return section
    raise Book2VideoError(f"no section {section_id!r}; run 'outline' to see the ids")


def section_part(section: dict, part: int, max_words: int) -> tuple[int, str]:
    """Return (parts_total, text) for one piece of a long section."""
    total_words = word_count(section["text"])
    if max_words <= 0 or total_words <= max_words:
        return 1, section["text"]
    total = -(-total_words // max_words)
    if not 1 <= part <= total:
        raise Book2VideoError(f"part must be between 1 and {total} for this section")
    start = (part - 1) * max_words
    return total, slice_words(section["text"], start, start + max_words)
