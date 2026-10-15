"""Subtitle cues: split each narration into lines and time them across the audio."""

from __future__ import annotations

import re
from dataclasses import dataclass
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
