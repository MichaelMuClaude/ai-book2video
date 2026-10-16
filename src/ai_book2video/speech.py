"""Narration: turn text into a WAV file with a local text-to-speech engine."""

from __future__ import annotations

import json
import math
import os
import shlex
import shutil
import struct
import subprocess
import wave
from pathlib import Path

from ai_book2video.errors import Book2VideoError

ENVELOPE_RATE = 24  # samples a second: enough to move a mouth, small enough to embed in the page

BACKENDS = ("kokoro", "espeak", "command")
KOKORO_PYTHON = os.environ.get("KOKORO_PYTHON", str(Path.home() / ".venvs" / "kokoro" / "bin" / "python"))
KOKORO_SCRIPT = Path(__file__).resolve().parent / "tts_kokoro.py"


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


def kokoro_batch(jobs: list[tuple[str, Path]], voice: str = "af_heart", speed: float = 1.0) -> None:
    """Render every narration with one Kokoro model load. jobs: (text, wav path) pairs."""
    if not Path(KOKORO_PYTHON).exists():
        raise Book2VideoError(f"Kokoro is not installed at {KOKORO_PYTHON}; set KOKORO_PYTHON or use --tts espeak")
    for _, out in jobs:
        out.parent.mkdir(parents=True, exist_ok=True)
    jobs_file = jobs[0][1].parent / "kokoro-jobs.json"
    jobs_file.write_text(json.dumps([{"text": text, "out": str(out)} for text, out in jobs], ensure_ascii=False), encoding="utf-8")
    result = subprocess.run([KOKORO_PYTHON, str(KOKORO_SCRIPT), str(jobs_file), voice, str(speed)], capture_output=True, text=True, timeout=60 * 60)
    jobs_file.unlink(missing_ok=True)
    if result.returncode != 0 or any(not out.exists() for _, out in jobs):
        raise Book2VideoError(f"Kokoro failed: {(result.stderr or result.stdout).strip()[-600:]}")


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


def amplitude_envelope(wav: Path, rate: int = ENVELOPE_RATE) -> list[float]:
    """Loudness of `wav` over time, one 0-1 value per 1/rate seconds (root-mean-square per window,
    normalised to its own peak, light smoothing, silence floors to 0). Used to open a talking
    actor's mouth in proportion to how loud the narration actually is at that instant, instead of a
    fixed flap. Mono or stereo 16-bit PCM; anything else returns an empty envelope (the caller falls
    back to the old flap)."""
    try:
        with wave.open(str(wav), "rb") as handle:
            if handle.getsampwidth() != 2:
                return []
            channels = handle.getnchannels()
            framerate = handle.getframerate()
            raw = handle.readframes(handle.getnframes())
    except (OSError, wave.Error):
        return []
    if not raw:
        return []
    samples = struct.unpack(f"<{len(raw) // 2}h", raw)
    window = max(1, int(framerate / rate))
    levels = []
    for start in range(0, len(samples), window * channels):
        chunk = samples[start : start + window * channels]
        if not chunk:
            break
        levels.append(math.sqrt(sum(v * v for v in chunk) / len(chunk)) / 32768)
    peak = max(levels, default=0.0) or 1.0
    levels = [v / peak for v in levels]
    smoothed = []  # a short rise/fall rather than a jittery bar, closer to how a mouth actually moves
    for i, v in enumerate(levels):
        window_vals = levels[max(0, i - 1) : i + 2]
        smoothed.append(sum(window_vals) / len(window_vals))
    return [round(v, 3) for v in smoothed]
