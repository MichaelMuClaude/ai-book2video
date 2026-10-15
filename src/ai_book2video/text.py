"""Word counting and slicing that work for English and for CJK text (no spaces between words)."""

from __future__ import annotations

import re

CJK = "぀-ヿ㐀-䶿一-鿿豈-﫿가-힯"
TOKEN = re.compile(rf"[{CJK}]|[^\s{CJK}]+")


def spans(text: str) -> list[tuple[int, int]]:
    """Character spans of every word. Each CJK character is one word."""
    return [(match.start(), match.end()) for match in TOKEN.finditer(text)]


def count_words(text: str) -> int:
    return len(TOKEN.findall(text))


def slice_words(text: str, start: int, stop: int) -> str:
    """The original text from word `start` up to (not including) word `stop`."""
    found = spans(text)
    if not found or start >= len(found):
        return ""
    return text[found[start][0] : found[min(stop, len(found)) - 1][1]]
