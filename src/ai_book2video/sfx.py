"""Sound effects made from code: no downloaded samples, so there is nothing to license.

Every effect is synthesised from sine waves and filtered noise in plain Python. A scene's
effects are placed on their own track at the moment the matching thing happens on screen
(a burst pops, someone falls, a train passes, a speech bubble appears, the scene wipes away),
and the track is mixed quietly under the narration when the scene is encoded.

Any prop or actor can choose or silence its sound with "sfx": "impact" | "chime" | "sad" |
"question" | "pop" | "none".
"""

from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

from ai_book2video.script import Scene
from ai_book2video.svgstage import burst_kind, when  # noqa: F401  (burst_kind is part of this module's API)

RATE = 24000
STEP_EVERY = 0.55  # matches the walking leg swing (1.1 s per stride, two steps)

KINDS = ("impact", "chime", "sad", "question", "pop", "none")
LEAD = 1 / 30  # one video frame
WHOOSH_SECONDS = 0.55


# --- synthesis -------------------------------------------------------------------------------

def _n(seconds: float) -> int:
    return max(1, int(seconds * RATE))


def _tone(freq_start: float, freq_end: float, seconds: float, decay: float, amp: float, shape: str = "sine") -> list[float]:
    out, phase = [], 0.0
    count = _n(seconds)
    for i in range(count):
        p = i / count
        freq = freq_start * (freq_end / freq_start) ** p
        phase += 2 * math.pi * freq / RATE
        if shape == "triangle":
            value = 2 / math.pi * math.asin(math.sin(phase))
        else:
            value = math.sin(phase)
        attack = min(1.0, i / (0.004 * RATE))
        out.append(amp * attack * value * math.exp(-decay * i / RATE))
    return out


def _noise(seconds: float, amp: float, low: float, high: float, envelope, seed: int) -> list[float]:
    """Band-limited noise: a one-pole high-pass and low-pass around white noise, shaped by envelope(p)."""
    rng = random.Random(seed)
    out = []
    count = _n(seconds)
    lp = hp_in = hp_out = 0.0
    for i in range(count):
        p = i / count
        hi = high(p) if callable(high) else high
        lo = low(p) if callable(low) else low
        a_lp = 1 - math.exp(-2 * math.pi * hi / RATE)
        a_hp = math.exp(-2 * math.pi * lo / RATE)
        x = rng.uniform(-1, 1)
        lp += a_lp * (x - lp)
        hp_out = a_hp * (hp_out + lp - hp_in)
        hp_in = lp
        out.append(amp * envelope(p) * hp_out)
    return out


def _add(*layers: list[float]) -> list[float]:
    out = [0.0] * max(len(layer) for layer in layers)
    for layer in layers:
        for i, value in enumerate(layer):
            out[i] += value
    return out


def pop(seed: int = 0) -> list[float]:
    return _tone(950, 320, 0.10, 28, 0.45)


def impact(seed: int = 0) -> list[float]:
    body = _tone(120, 42, 0.55, 7, 0.85)
    crack = _noise(0.25, 1.4, 200, 5000, lambda p: math.exp(-14 * p), seed)
    return _add(body, crack)


def thud(seed: int = 0) -> list[float]:
    return _add(_tone(95, 40, 0.32, 13, 0.75), _noise(0.12, 0.8, 80, 900, lambda p: math.exp(-10 * p), seed))


def chime(seed: int = 0) -> list[float]:
    first = _add(_tone(1046.5, 1046.5, 0.9, 4.5, 0.32), _tone(2093, 2093, 0.9, 7, 0.10))
    second = _add(_tone(1568, 1568, 0.9, 4.5, 0.28), _tone(3136, 3136, 0.9, 7, 0.08))
    return _add(first, [0.0] * _n(0.09) + second)


def sad(seed: int = 0) -> list[float]:
    notes = [(392, 0.22), (370, 0.22), (349, 0.22), (330, 0.55)]
    out: list[float] = []
    for freq, seconds in notes:
        out += _tone(freq, freq * 0.985, seconds, 3, 0.30, "triangle")
    return out


def question(seed: int = 0) -> list[float]:
    return _tone(520, 520, 0.09, 20, 0.35) + [0.0] * _n(0.05) + _tone(700, 940, 0.16, 12, 0.35)


def whoosh(seed: int = 0, seconds: float = WHOOSH_SECONDS) -> list[float]:
    centre = lambda p: 500 + 2500 * math.sin(math.pi * p)  # noqa: E731
    return _noise(seconds, 1.6, lambda p: centre(p) * 0.6, centre, lambda p: math.sin(math.pi * p) ** 2, seed)


def swish(seed: int = 0) -> list[float]:
    return _noise(0.25, 0.9, 1800, 7000, lambda p: math.sin(math.pi * p), seed)


def step(seed: int = 0) -> list[float]:
    return _noise(0.07, 0.9, 60, 700, lambda p: math.exp(-9 * p), seed)


def tick(seed: int = 0) -> list[float]:
    return _tone(2200, 2200, 0.03, 120, 0.18)


def whistle(seed: int = 0) -> list[float]:
    return _add(_tone(587, 600, 0.7, 2.2, 0.16), _tone(740, 755, 0.7, 2.2, 0.12))


def chug(seed: int = 0) -> list[float]:
    return _noise(0.16, 1.1, 60, 1200, lambda p: math.exp(-7 * p), seed)


def engine(seconds: float, seed: int = 0) -> list[float]:
    rumble = _tone(55, 75, seconds, 0, 0.16, "triangle")
    fade = _n(seconds)
    return [v * min(1.0, i / (0.3 * RATE), (fade - i) / (0.4 * RATE)) for i, v in enumerate(rumble)]


# Peak level of each sound in dBFS, set against Kokoro narration (peaks near -7 dB, average near -25 dB):
# one-off hits sit just under the voice, continuous sounds (chugging, steps, ticks) well below it.
LEVELS = {"impact": -10, "thud": -13, "chime": -17, "sad": -17, "question": -18, "pop": -18, "whoosh": -19,
          "swish": -22, "whistle": -20, "chug": -25, "step": -28, "tick": -27, "engine": -25}


def _level(samples: list[float], peak_db: float) -> list[float]:
    peak = max((abs(v) for v in samples), default=0.0)
    if peak == 0:
        return samples
    scale = 10 ** (peak_db / 20) / peak
    return [v * scale for v in samples]


SOUNDS = {"pop": pop, "impact": impact, "thud": thud, "chime": chime, "sad": sad, "question": question,
          "whoosh": whoosh, "swish": swish, "step": step, "tick": tick, "whistle": whistle, "chug": chug}


# --- events ----------------------------------------------------------------------------------

def scene_events(scene: Scene, cues: list, duration: float, last: bool = False) -> list[tuple[float, str, dict]]:
    """(time, sound, options) for everything in a scene that should make a noise."""
    events: list[tuple[float, str, dict]] = []
    if not last:
        # The wipe into the next scene crosses the middle of the frame about 0.4 s before the end;
        # a whoosh peaks halfway through itself, so start it half its length before that.
        events.append((max(0.0, duration - 0.4 - WHOOSH_SECONDS / 2), "whoosh", {}))
    if scene.kind == "title":
        events.append((0.4, "chime", {}))
    if scene.kind != "stage" or not scene.stage:
        return events
    for item in scene.stage.get("props", []):
        choice = item.get("sfx")
        if choice == "none":
            continue
        kind = item.get("type")
        if kind == "burst":
            at = when(item.get("at"), cues, 1.0)
            events.append((at, choice or burst_kind(str(item.get("text", "!"))), {}))
        elif kind in ("car", "train") and item.get("to") is not None:
            at = when(item.get("at"), cues)
            dur = float(item.get("dur", 3))
            if kind == "train":
                events.append((at, "whistle", {}))
                t = at + 0.1
                while t < at + dur - 0.1:
                    events.append((t, "chug", {"gain": 0.8 if int((t - at) / 0.24) % 2 else 1.0}))
                    t += 0.24
            else:
                events.append((at, "engine", {"seconds": dur}))
                events.append((at + dur / 2 - 0.3, "whoosh", {"gain": 1.2}))
        elif kind == "letter" and item.get("to") is not None:
            events.append((when(item.get("at"), cues), "swish", {}))
        elif kind == "clock" and float(item.get("spin", 1)) > 0:
            at = when(item.get("at"), cues)
            dur = float(item.get("dur", 6))
            t = at
            while t < min(at + dur, duration - 0.8):
                events.append((t, "tick", {}))
                t += 0.5
        elif choice in KINDS:
            events.append((when(item.get("at"), cues, 1.0), choice, {}))
    for item in scene.stage.get("actors", []):
        choice = item.get("sfx")
        if choice == "none":
            continue
        action = item.get("action", "stand")
        at = when(item.get("at"), cues)
        if action == "fall":
            events.append((at + 0.4, choice or "thud", {}))
        elif action == "walk" and item.get("to") is not None:
            dur = float(item.get("dur", 3))
            t = at + 0.15
            while t < at + dur:
                events.append((t, "step", {"gain": 0.55}))
                t += STEP_EVERY
        for line in item.get("say", []):
            events.append((when(line.get("at"), cues, 0.5), "pop", {"gain": 0.6}))
    # A hit's transient is its first instant, and a sound placed on the hit frame is heard as late;
    # one frame early it reads on the frame (a habit from anything2video's audio engine).
    early = {"impact", "thud", "pop", "chime", "sad", "question", "tick", "step", "chug"}
    events = [(max(0.0, t - LEAD) if name in early else t, name, opts) for t, name, opts in events]
    return sorted((round(t, 3), name, opts) for t, name, opts in events if t < duration)


def render(events: list[tuple[float, str, dict]], duration: float, out: Path) -> Path:
    """Mix the events into one 16-bit mono WAV the length of the scene."""
    track = [0.0] * _n(duration)
    for number, (at, name, opts) in enumerate(events):
        if name == "engine":
            samples = engine(float(opts.get("seconds", 3)), seed=number)
        else:
            samples = SOUNDS[name](seed=number)
        samples = _level(samples, LEVELS[name])
        gain = float(opts.get("gain", 1.0))
        start = int(at * RATE)
        for i, value in enumerate(samples):
            j = start + i
            if j >= len(track):
                break
            track[j] += gain * value
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(b"".join(struct.pack("<h", int(32767 * math.tanh(v))) for v in track))
    return out
