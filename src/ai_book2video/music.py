"""Background music made in code: a quiet bed under the narration, with no sound files to license.

A mood picks a key, a tempo and a four-chord progression. The bed is a warm pad (two slightly
detuned voices per chord tone), a soft bass on each bar, and a plucked arpeggio (Karplus-Strong)
that moves on eighth or quarter notes. Sixteen bars are rendered once as a seamless loop: anything
that rings past the end wraps round to the start, so the loop tiles with no click or gap. The build
lays the loop under the whole film, fades it in and out, keeps it well below the voice and lowers
it further whenever the narrator speaks (sidechain ducking), so it fills pauses without competing.

Everything is seeded, so the same mood always renders the same music.
"""

from __future__ import annotations

import math
import random
import struct
import wave
from array import array
from pathlib import Path

RATE = 24000

# key (MIDI note of the tonic), tempo, chords as (semitones above the tonic, "maj" | "min"),
# arpeggio note length in beats and two patterns (indexes into the chord's tones).
MOODS = {
    "calm": {"tonic": 60, "bpm": 72, "chords": [(0, "maj"), (9, "min"), (5, "maj"), (7, "maj")],
             "step": 0.5, "patterns": ([0, 1, 2, 3, 2, 1, 2, 3], [0, 2, 1, 3, 0, 2, 3, 2])},
    "reflective": {"tonic": 57, "bpm": 66, "chords": [(0, "min"), (8, "maj"), (3, "maj"), (10, "maj")],
                   "step": 0.5, "patterns": ([0, 2, 1, 2, 3, 2, 1, 2], [0, 1, 2, 3, 1, 2, 3, 2])},
    "tense": {"tonic": 50, "bpm": 80, "chords": [(0, "min"), (1, "maj"), (0, "min"), (10, "maj")],
              "step": 1.0, "patterns": ([0, 2, 0, 1], [0, 3, 1, 2])},
}
TRIADS = {"maj": (0, 4, 7), "min": (0, 3, 7)}
BARS = 16  # two passes of the progression, two bars a chord; the second pass varies the arpeggio


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _chord_tones(tonic: int, offset: int, quality: str) -> list[int]:
    """Root, third, fifth and octave, kept between G3 and C5 so the chords move smoothly."""
    tones = []
    for interval in TRIADS[quality] + (12,):
        midi = tonic + offset + interval
        while midi > 72:
            midi -= 12
        while midi < 55:
            midi += 12
        tones.append(midi)
    return sorted(tones)


def _add(track: array, start: int, samples) -> None:
    """Mix samples into the loop from `start`, wrapping past the end back to the beginning."""
    length = len(track)
    for i, value in enumerate(samples):
        track[(start + i) % length] += value


def _pad(freq: float, seconds: float, amp: float) -> list[float]:
    attack, release = 1.0, 1.4
    total = int((seconds + release) * RATE)
    out = []
    for i in range(total):
        t = i / RATE
        env = min(1.0, t / attack) if t < seconds else max(0.0, 1 - (t - seconds) / release)
        phase = 2 * math.pi * freq * t
        value = (math.sin(phase * 0.9985) + math.sin(phase * 1.0015)) * 0.5
        value += 0.25 * math.sin(2 * phase) + 0.08 * math.sin(3 * phase)
        out.append(amp * env * value)
    return out


def _bass(freq: float, seconds: float, amp: float) -> list[float]:
    total = int(seconds * RATE)
    return [amp * min(1.0, i / (0.03 * RATE)) * math.exp(-1.6 * i / RATE) * math.sin(2 * math.pi * freq * i / RATE)
            for i in range(total)]


def _pluck(freq: float, seconds: float, amp: float, rng: random.Random) -> list[float]:
    """Karplus-Strong: a burst of filtered noise in a delay line, averaged as it circulates."""
    period = max(2, int(RATE / freq))
    noise = [rng.uniform(-1, 1) for _ in range(period)]
    line = [(noise[i] + noise[i - 1]) * 0.5 for i in range(period)]  # soften the attack
    total = int(seconds * RATE)
    out = []
    for i in range(total):
        j = i % period
        value = line[j]
        line[j] = 0.5 * (value + line[(j + 1) % period]) * 0.995
        fade = min(1.0, (total - i) / (0.05 * RATE))
        out.append(amp * fade * value)
    return out


def render_loop(mood: str, out: Path, seed: int = 7) -> Path:
    """Write the mood's sixteen-bar loop as a 16-bit mono WAV that tiles seamlessly."""
    spec = MOODS[mood]
    rng = random.Random(seed)
    beat = 60.0 / spec["bpm"]
    bar = 4 * beat
    track = array("f", [0.0]) * int(BARS * bar * RATE)
    chords = spec["chords"]
    for number in range(BARS // 2):  # one chord every two bars
        offset, quality = chords[number % len(chords)]
        tones = _chord_tones(spec["tonic"], offset, quality)
        start = number * 2 * bar
        for tone in tones:
            _add(track, int(start * RATE), _pad(hz(tone), 2 * bar, 0.06))
        root = spec["tonic"] + offset - 24
        while root > 48:
            root -= 12
        for b in range(2):
            _add(track, int((start + b * bar) * RATE), _bass(hz(root), bar, 0.18))
        pattern = spec["patterns"][0 if number < len(chords) else 1]
        step = spec["step"] * beat
        steps = int(2 * bar / step)
        for k in range(steps):
            tone = tones[pattern[k % len(pattern)] % len(tones)] + 12
            velocity = 0.11 * (0.75 + 0.25 * rng.random()) * (1.15 if k % len(pattern) == 0 else 1.0)
            _add(track, int((start + k * step) * RATE), _pluck(hz(tone), min(1.4, 3 * step), velocity, rng))
    peak = max(abs(v) for v in track) or 1.0
    scale = 0.5 / peak
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(b"".join(struct.pack("<h", int(32767 * v * scale)) for v in track))
    return out


def loop_seconds(mood: str) -> float:
    return BARS * 4 * 60.0 / MOODS[mood]["bpm"]
