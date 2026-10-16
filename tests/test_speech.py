import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from tests import helpers  # noqa: F401
from ai_book2video import speech


def tone_wav(path: Path, pattern: list[tuple[float, float]], rate: int = 24000) -> None:
    """Write a mono 16-bit WAV: a list of (seconds, amplitude 0-1) blocks of a 200 Hz tone."""
    frames = []
    t = 0.0
    for seconds, amp in pattern:
        n = int(seconds * rate)
        for i in range(n):
            frames.append(int(amp * 32767 * math.sin(2 * math.pi * 200 * (t + i / rate))))
        t += seconds
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(struct.pack(f"<{len(frames)}h", *frames))


class AmplitudeEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.folder)

    def test_loud_and_quiet_sections_are_told_apart(self):
        wav = self.folder / "t.wav"
        tone_wav(wav, [(0.5, 0.9), (0.5, 0.02), (0.5, 0.9)])
        env = speech.amplitude_envelope(wav)
        n = len(env)
        self.assertGreater(n, 20)
        loud_start = env[: n // 6]
        quiet_middle = env[n // 2 - n // 8 : n // 2 + n // 8]
        loud_end = env[-n // 6 :]
        self.assertGreater(min(loud_start), 0.5)
        self.assertLess(max(quiet_middle), 0.3)
        self.assertGreater(min(loud_end), 0.5)

    def test_values_stay_in_zero_to_one(self):
        wav = self.folder / "t.wav"
        tone_wav(wav, [(1.0, 1.0)])
        env = speech.amplitude_envelope(wav)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in env))

    def test_silence_is_near_zero_throughout(self):
        wav = self.folder / "s.wav"
        tone_wav(wav, [(1.0, 0.0)])
        env = speech.amplitude_envelope(wav)
        self.assertTrue(all(v < 0.05 for v in env))

    def test_missing_file_returns_empty(self):
        self.assertEqual(speech.amplitude_envelope(self.folder / "nope.wav"), [])


if __name__ == "__main__":
    unittest.main()
