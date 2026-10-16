"""Check a finished video with numbers before anyone watches it: `ai-book2video check out.mp4`.

Looking at a few still frames cannot show whether a film moves, flickers or goes quiet. This
measures it, scene by scene (scene boundaries come from the build's manifest.json):

- motion: how much of the picture changes inside each scene. A scene that hardly moves reads as
  a slide, not an animation.
- frozen stretches: the longest run with no visible change.
- jumps: a sudden whole-picture change in the middle of a scene, which is usually a glitch
  (scene changes and camera cuts on sentence starts are expected and not counted).
- blank frames: nearly one flat colour.
- sound: scenes with no narration, the overall loudness and the peak.

Red means fix before delivering; yellow means look at it at normal speed.
"""

from __future__ import annotations

import json
import re
import statistics
import subprocess
from pathlib import Path

from ai_book2video.errors import Book2VideoError
from ai_book2video.reference import _ffmpeg, cuts, probe

W, H = 90, 160  # analysis size (portrait); small enough to be quick, big enough to see a stick figure move
FPS = 10
CHANGE = 12  # a pixel "moved" when its grey level changes by more than this
STILL_MOTION = 0.004  # under 0.4% of the picture moving: a still frame pair
SLIDE_MOTION = 0.006  # a scene whose average motion is under this reads as a slide
JUMP = 0.55  # more than 55% of the picture changing between two frames is a jump


def _stats(video: Path, chain: str, key: str) -> list[float]:
    """One signalstats value per analysed frame, computed inside ffmpeg (fast, no frames in Python)."""
    result = subprocess.run(
        [_ffmpeg(), "-hide_banner", "-loglevel", "error", "-i", str(video), "-an", "-vf",
         f"fps={FPS},scale={W}:{H}:flags=area,format=yuv420p,{chain}signalstats,"
         f"metadata=print:key=lavfi.signalstats.{key}:file=-", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise Book2VideoError(f"cannot analyse {video}: {result.stderr[-300:]}")
    return [float(v) for v in re.findall(rf"lavfi\.signalstats\.{key}=([0-9.]+)", result.stdout)]


def motion_series(video: Path) -> list[float]:
    """Share of the picture that changed since the previous analysed frame, per frame."""
    diff = f"tblend=all_mode=difference,lutyuv=y='if(gt(val\\,{CHANGE})\\,255\\,0)',"
    return [v / 255 for v in _stats(video, diff, "YAVG")]


def flat_series(video: Path) -> list[bool]:
    """True where a frame is nearly one flat colour (the 10th and 90th percentile grey are equal)."""
    lows = _stats(video, "", "YLOW")
    highs = _stats(video, "", "YHIGH")
    return [h - l < 3 for l, h in zip(lows, highs)]


def _sound(video: Path) -> dict:
    """Overall loudness (LUFS), true peak, and quiet stretches (silencedetect)."""
    result = subprocess.run(
        [_ffmpeg(), "-hide_banner", "-nostats", "-i", str(video), "-vn",
         "-af", "silencedetect=noise=-45dB:d=2.5,ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    text = result.stderr
    lufs = re.findall(r"I:\s+(-?[0-9.]+) LUFS", text)
    peak = re.findall(r"Peak:\s+(-?[0-9.]+|-inf) dBFS", text)
    starts = [float(t) for t in re.findall(r"silence_start: (-?[0-9.]+)", text)]
    ends = [float(t) for t in re.findall(r"silence_end: ([0-9.]+)", text)]
    quiet = list(zip(starts, ends + [None] * (len(starts) - len(ends))))
    return {"lufs": float(lufs[-1]) if lufs else None,
            "peak": float(peak[-1]) if peak and peak[-1] != "-inf" else None,
            "quiet": [(round(a, 2), round(b, 2) if b is not None else None) for a, b in quiet]}


def _manifest_for(video: Path) -> dict | None:
    candidates = [video.with_suffix("") / "manifest.json", video.parent / (video.stem + ".manifest.json")]
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def _scenes_from_cuts(video: Path, duration: float) -> list[dict]:
    """Without a manifest, find the scenes in the video: hard picture changes, ignoring the short
    pieces a wipe between scenes leaves behind."""
    bounds = [0.0] + [t for t in cuts(video, 0.3) if 0 < t < duration] + [duration]
    scenes, start = [], 0.0
    for t in bounds[1:]:
        if t - start >= 2.0:
            scenes.append({"index": len(scenes) + 1, "start": start, "clip_seconds": t - start})
            start = t
    if not scenes:
        scenes = [{"index": 1, "start": 0.0, "clip_seconds": duration}]
    elif start < duration:
        scenes[-1]["clip_seconds"] = duration - scenes[-1]["start"]
    return scenes


def check(video: Path, manifest: dict | None = None) -> dict:
    if not video.exists():
        raise Book2VideoError(f"video not found: {video}")
    info = probe(video)
    manifest = manifest or _manifest_for(video)
    moved = motion_series(video)
    flat = flat_series(video)
    duration = info["duration"] or len(moved) / FPS
    scenes = (manifest or {}).get("scenes") or _scenes_from_cuts(video, duration)
    cut_times = [float(s["start"]) for s in scenes]
    sound = _sound(video)
    report_scenes, red, yellow = [], [], []
    for scene in scenes:
        a = float(scene["start"])
        b = a + float(scene.get("clip_seconds", duration - a))
        lo, hi = int(a * FPS), min(len(moved), int(b * FPS))
        inner = moved[lo + 8:hi - 8] if hi - lo > 20 else moved[lo:hi]  # leave out the wipes at both ends
        if not inner:
            continue
        mean_motion = statistics.mean(inner)
        run = longest = 0
        for value in inner:
            run = run + 1 if value < STILL_MOTION else 0
            longest = max(longest, run)
        jumps = [round((lo + 8 + i) / FPS, 1) for i, value in enumerate(inner) if value > JUMP]
        blank = sum(1 for f in flat[lo + 8:hi - 8] if f)
        talk = b - a - sum(min(e if e is not None else b, b) - max(s, a) for s, e in sound["quiet"] if s < b and (e is None or e > a))
        entry = {"scene": scene["index"], "start": round(a, 1), "seconds": round(b - a, 1), "motion": round(mean_motion, 4),
                 "longest_still": round(longest / FPS, 1), "jumps": jumps, "blank_frames": blank, "sound_seconds": round(max(0.0, talk), 1)}
        report_scenes.append(entry)
        where = f"scene {scene['index']} ({a:.0f}s)"
        if mean_motion < SLIDE_MOTION:
            red.append(f"{where}: hardly moves (motion {mean_motion:.2%}); it will read as a slide")
        if longest / FPS > 6:
            yellow.append(f"{where}: frozen for {longest / FPS:.1f}s; fine for a pause, check it at normal speed")
        if jumps:
            red.append(f"{where}: whole picture jumps at {', '.join(map(str, jumps[:5]))}s")
        if blank > FPS:
            red.append(f"{where}: {blank} nearly blank frames")
        if b - a > 3 and talk < 1.0:
            red.append(f"{where}: no narration heard")
    if sound["lufs"] is None:
        red.append("no sound track")
    elif not -24 <= sound["lufs"] <= -12:
        yellow.append(f"overall loudness {sound['lufs']} LUFS; short-video apps expect about -16 to -14")
    if sound["peak"] is not None and sound["peak"] > -1.0:
        yellow.append(f"peak {sound['peak']} dBFS; leave at least 1 dB of headroom")
    if manifest and abs(float(manifest.get("seconds", duration)) - duration) > 0.5:
        red.append(f"video is {duration}s but the manifest says {manifest['seconds']}s")
    return {"video": str(video), "seconds": duration, "scenes": report_scenes, "sound": sound,
            "cuts": cut_times, "red": red, "yellow": yellow, "passed": not red}


def summary(report: dict) -> str:
    lines = [f"{Path(report['video']).name}: {report['seconds']}s, {len(report['scenes'])} scenes"]
    sound = report["sound"]
    lines.append(f"  loudness {sound['lufs']} LUFS, peak {sound['peak']} dBFS")
    motions = [s["motion"] for s in report["scenes"]]
    if motions:
        calm = min(report["scenes"], key=lambda s: s["motion"])
        lines.append(f"  motion per scene {min(motions):.2%}–{max(motions):.2%} (calmest: scene {calm['scene']})")
    for item in report["red"]:
        lines.append(f"  RED     {item}")
    for item in report["yellow"]:
        lines.append(f"  YELLOW  {item}")
    lines.append("  passed" if report["passed"] else "  FAILED: fix the red items before delivering")
    return "\n".join(lines)
