"""Subtitle cues: split each narration into lines and time them across the audio."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

LINE_CHARS = 42
CJK_LINE_CHARS = 24
MAX_LINES = 2
CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


@dataclass
class Cue:
    start: float
    end: float
    text: str
    zh: str = ""
    words: list = field(default_factory=list)  # [[word, seconds], ...]: when each word starts


def norm(text: str) -> str:
    """Letters and digits only, lower case: the form words are matched in."""
    return re.sub(r"[^0-9a-z]", "", text.lower())


def sentences(text: str) -> list[str]:
    """Split after sentence ends. Chinese sentences end with 。！？ and have no space after them."""
    parts = re.split(r"(?<=[。！？])\s*|(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part and part.strip()]


def wrap(text: str, width: int | None = None) -> list[str]:
    """Wrap to lines of about `width` characters. Works for text with or without spaces."""
    if width is None:
        width = CJK_LINE_CHARS if CJK.search(text) else LINE_CHARS
    if " " not in text:
        return [text[i : i + width] for i in range(0, len(text), width)]
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if len(candidate) > width and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def cues_for(text: str, start: float, end: float) -> list[Cue]:
    """Split one narration over [start, end], giving each sentence a share of the time by length."""
    pieces = sentences(text) or [text]
    total = sum(len(piece) for piece in pieces) or 1
    cues: list[Cue] = []
    cursor = start
    for piece in pieces:
        share = (end - start) * len(piece) / total
        lines = wrap(piece)
        joiner = "" if CJK.search(piece) else "\n"
        for block in range(0, len(lines), MAX_LINES):
            chunk = lines[block : block + MAX_LINES]
            part_share = share * len(" ".join(chunk)) / max(len(piece), 1)
            cues.append(Cue(cursor, min(end, cursor + part_share), joiner.join(chunk)))
            cursor += part_share
    if cues:
        cues[-1].end = end
    return cues


def pair_cues(english: list[str], chinese: list[str], start: float, end: float) -> list[Cue]:
    """One cue per sentence pair. Each pair gets time in proportion to its English length."""
    weights = [max(1, len(sentence.split())) for sentence in english]
    total = sum(weights) or 1
    cues: list[Cue] = []
    cursor = start
    for index, sentence in enumerate(english):
        share = (end - start) * weights[index] / total
        zh = chinese[index] if index < len(chinese) else ""
        cues.append(Cue(cursor, min(end, cursor + share), sentence, zh))
        cursor += share
    if cues:
        cues[-1].end = end
    return cues


def estimate_words(cue: Cue) -> None:
    """Without real timings, spread a cue's words across it by length."""
    tokens = [t for t in cue.text.split() if norm(t)]
    total = sum(len(t) + 1 for t in tokens) or 1
    cursor, span = cue.start, cue.end - cue.start
    cue.words = []
    for token in tokens:
        cue.words.append([norm(token), round(cursor, 3)])
        cursor += span * (len(token) + 1) / total


def align(sentence_list: list[str], spoken: list) -> list[list]:
    """Match spoken word timings [[word, start, end], ...] to the sentences, letter by letter.

    Returns, per sentence, [[word, start, end], ...] for the words found in it (may be empty).
    Matching on letters and digits only makes it robust to how the speech engine splits
    hyphens, contractions and punctuation."""
    bounds, position = [], 0
    for sentence in sentence_list:
        length = len(norm(sentence))
        bounds.append((position, position + length))
        position += length
    full = "".join(norm(sentence) for sentence in sentence_list)
    placed, cursor = [], 0
    for text, start, end in spoken:
        key = norm(str(text))
        if not key:
            continue
        found = full.find(key, cursor)
        if found < 0 or found - cursor > 40:
            continue
        placed.append((found, found + len(key), key, float(start), float(end)))
        cursor = found + len(key)
    return [[[key, start, end] for a, b, key, start, end in placed if a >= lo and b <= hi] for lo, hi in bounds]


def timed_cues(english: list[str], chinese: list[str], spoken: list, start: float, end: float) -> list[Cue]:
    """One cue per sentence pair, timed from the speech engine's word timings.

    A cue starts when its first word is spoken (the first cue at `start`) and lasts until the
    next cue, so subtitles never blink off between sentences. Sentences with no matched words
    fall back to an even share of the gap around them."""
    found = align(english, spoken)
    starts: list[float | None] = [words[0][1] if words else None for words in found]
    starts[0] = start
    for index in range(1, len(starts)):
        if starts[index] is None:
            later = next((s for s in starts[index + 1:] if s is not None), end)
            earlier = starts[index - 1]
            missing = sum(1 for s in starts[index:] if s is None) if later == end else 1
            starts[index] = earlier + (later - earlier) / (missing + 1)
    shown = [start] + [max(start, s - 0.05) for s in starts[1:]]  # show a line just before it is said
    cues = []
    for index, sentence in enumerate(english):
        cue_end = shown[index + 1] if index + 1 < len(shown) else end
        cue = Cue(shown[index], cue_end, sentence, chinese[index] if index < len(chinese) else "")
        cue.words = [[key, round(t0, 3)] for key, t0, _ in found[index]]
        if not cue.words:
            estimate_words(cue)
        cues.append(cue)
    return cues


def timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def write_srt(cues: list[Cue], path: Path) -> None:
    blocks = []
    for number, cue in enumerate(cues, start=1):
        text = cue.text + ("\n" + cue.zh if cue.zh else "")
        blocks.append(f"{number}\n{timestamp(cue.start)} --> {timestamp(cue.end)}\n{text}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")
