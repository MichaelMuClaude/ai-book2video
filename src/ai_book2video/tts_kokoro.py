"""Render narration with Kokoro (open model, local GPU). Runs under its own Python environment.

usage: python tts_kokoro.py <jobs.json> <voice> <speed>
jobs.json is a list of {"text": "...", "out": "/path/file.wav"}. The model loads once for all jobs.
"""

import json
import sys

import numpy as np
import soundfile as sf
import torch
from kokoro import KPipeline

SAMPLE_RATE = 24000


def main() -> None:
    jobs = json.load(open(sys.argv[1], encoding="utf-8"))
    voice = sys.argv[2] if len(sys.argv) > 2 else "af_heart"
    speed = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    device = "cuda" if torch.cuda.is_available() else "cpu"
    pipe = KPipeline(lang_code="a", device=device)
    for job in jobs:
        chunks = [audio for _, _, audio in pipe(job["text"], voice=voice, speed=speed)]
        wav = np.concatenate(chunks) if chunks else np.zeros(SAMPLE_RATE // 2, dtype=np.float32)
        sf.write(job["out"], wav, SAMPLE_RATE)
    print(f"kokoro rendered {len(jobs)} narrations on {device}")


if __name__ == "__main__":
    main()
