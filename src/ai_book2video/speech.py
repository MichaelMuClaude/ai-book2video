"""Narration: turn text into a WAV file with a local text-to-speech engine."""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from pathlib import Path

from ai_book2video.errors import Book2VideoError

BACKENDS = ("espeak", "command")


def require(tool: str) -> str:
    found = shutil.which(tool)
    if not found:
        raise Book2VideoError(f"{tool} is not installed or not on PATH")
    return found


def synthesize(text: str, out: Path, backend: str = "espeak", voice: str = "en-us", rate: int = 165, command: str = "") -> None:
    """Write `text` to `out` (WAV). `command` may use {text} (a file with the text) and {out}."""
    out.parent.mkdir(parents=True, exist_ok=True)
    text_file = out.with_suffix(".txt")
    text_file.write_text(text, encoding="utf-8")
    if backend == "espeak":
        result = subprocess.run(
            [require("espeak-ng"), "-v", voice, "-s", str(rate), "-f", str(text_file), "-w", str(out)],
            capture_output=True,
            text=True,
        )
    elif backend == "command":
        if not command:
            raise Book2VideoError("--tts command needs --tts-command with {text} and {out} placeholders")
        pieces = shlex.split(command.format(text=str(text_file), out=str(out)))
        result = subprocess.run(pieces, capture_output=True, text=True)
    else:
        raise Book2VideoError(f"unknown TTS backend {backend!r}; use one of {', '.join(BACKENDS)}")
    if result.returncode != 0 or not out.exists():
        raise Book2VideoError(f"speech synthesis failed: {result.stderr.strip() or result.stdout.strip()}")


def duration(path: Path) -> float:
    """Length of a media file in seconds, from ffprobe."""
    probe = subprocess.run(
        [require("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        raise Book2VideoError(f"ffprobe failed on {path}: {probe.stderr.strip()}")
    return float(json.loads(probe.stdout)["format"]["duration"])
