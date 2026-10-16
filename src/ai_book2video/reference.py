"""Measure a reference video (or picture) so its style can be copied on purpose, not by eye.

`ai-book2video analyze-ref clip.mp4` writes, next to a contact sheet with one frame per shot:
- pacing: where the cuts are, how long shots last, cuts per minute,
- colour: the dominant colours, how bright and how saturated the picture is,
- motion: how much changes from second to second (calm, lively or busy),
- a starter "palettes" list that can be pasted into a script.

Everything comes from ffmpeg; nothing is uploaded or downloaded.
"""

from __future__ import annotations

import colorsys
import json
import re
import shutil
import statistics
import subprocess
from pathlib import Path

from ai_book2video.errors import Book2VideoError

SAMPLE = 48  # frames are shrunk to SAMPLE x SAMPLE pixels for colour and motion statistics
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


def _ffmpeg() -> str:
    tool = shutil.which("ffmpeg")
    if not tool or not shutil.which("ffprobe"):
        raise Book2VideoError("ffmpeg and ffprobe are needed to analyse a reference")
    return tool


def probe(path: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,avg_frame_rate:format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise Book2VideoError(f"cannot read {path}: {result.stderr.strip()[-300:]}")
    data = json.loads(result.stdout)
    stream = (data.get("streams") or [{}])[0]
    num, _, den = str(stream.get("avg_frame_rate", "0/1")).partition("/")
    fps = float(num) / float(den) if den and float(den) else 0.0
    duration = float(data.get("format", {}).get("duration") or 0.0)
    if path.suffix.lower() in IMAGE_SUFFIXES:
        duration, fps = 0.0, 0.0
    return {"width": int(stream.get("width", 0)), "height": int(stream.get("height", 0)), "fps": round(fps, 2), "duration": round(duration, 2)}


def cuts(path: Path, threshold: float = 0.3) -> list[float]:
    """Times (seconds) where the picture changes enough to count as a new shot."""
    result = subprocess.run(
        [_ffmpeg(), "-hide_banner", "-i", str(path), "-an", "-vf", f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    return [round(float(t), 2) for t in re.findall(r"pts_time:([0-9.]+)", result.stderr)]


def frames(path: Path, per_second: float = 2.0) -> list[bytes]:
    """Small RGB frames (SAMPLE x SAMPLE) taken per_second times a second, or the one picture."""
    rate = [] if path.suffix.lower() in IMAGE_SUFFIXES else ["-vf", f"fps={per_second},scale={SAMPLE}:{SAMPLE}:flags=area"]
    if not rate:
        rate = ["-vf", f"scale={SAMPLE}:{SAMPLE}:flags=area"]
    result = subprocess.run(
        [_ffmpeg(), "-hide_banner", "-loglevel", "error", "-i", str(path), *rate, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True,
    )
    if result.returncode != 0:
        raise Book2VideoError(f"cannot decode {path}: {result.stderr.decode(errors='replace')[-300:]}")
    size = SAMPLE * SAMPLE * 3
    data = result.stdout
    return [data[i:i + size] for i in range(0, len(data) - size + 1, size)]


def palette(samples: list[bytes], count: int = 6) -> list[dict]:
    """Dominant colours: pixels grouped into coarse colour bins, nearby bins merged, biggest first."""
    bins: dict[tuple, list[int]] = {}
    total = 0
    for frame in samples:
        for i in range(0, len(frame), 3):
            r, g, b = frame[i], frame[i + 1], frame[i + 2]
            key = (r >> 5, g >> 5, b >> 5)
            entry = bins.setdefault(key, [0, 0, 0, 0])
            entry[0] += r
            entry[1] += g
            entry[2] += b
            entry[3] += 1
            total += 1
    colours = sorted(([e[0] / e[3], e[1] / e[3], e[2] / e[3], e[3]] for e in bins.values()), key=lambda c: -c[3])
    merged: list[list[float]] = []
    for c in colours:
        for m in merged:
            if sum((c[k] - m[k]) ** 2 for k in range(3)) < 45 ** 2:
                weight = m[3] + c[3]
                for k in range(3):
                    m[k] = (m[k] * m[3] + c[k] * c[3]) / weight
                m[3] = weight
                break
        else:
            merged.append(list(c))
    merged.sort(key=lambda c: -c[3])
    out = []
    for r, g, b, n in merged[:count]:
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        out.append({"hex": f"#{int(r):02x}{int(g):02x}{int(b):02x}", "share": round(n / max(total, 1), 3),
                    "lightness": round(l, 2), "saturation": round(s, 2)})
    return out


def motion_level(samples: list[bytes]) -> tuple[float, str]:
    """Average change between consecutive samples, 0-255, and a word for it."""
    if len(samples) < 2:
        return 0.0, "still"
    diffs = [sum(abs(a - b) for a, b in zip(x, y)) / len(x) for x, y in zip(samples, samples[1:])]
    within = [d for d in diffs if d < 45] or diffs  # a jump this big is a cut, not movement inside a shot
    value = round(statistics.mean(within), 1)
    word = "calm" if value < 6 else "lively" if value < 18 else "busy"
    return value, word


def suggest_palettes(colours: list[dict]) -> list[dict]:
    """A starter "palettes" list for a script: the main colour as background, the most saturated
    other colour as accent, and the strongest contrast to the background as the card colour."""
    if not colours:
        return []
    bg = colours[0]
    rest = colours[1:] or colours
    accent = max(rest, key=lambda c: c["saturation"] * (0.5 + c["share"]))
    card = max(rest, key=lambda c: abs(c["lightness"] - bg["lightness"]))
    first = {"bg": bg["hex"], "accent": accent["hex"], "card": card["hex"]}
    second = {"bg": card["hex"], "accent": accent["hex"], "card": bg["hex"]} if card is not bg else dict(first)
    return [first, second]


def contact_sheet(path: Path, times: list[float], out: Path) -> Path | None:
    """One frame from the middle of each shot, tiled four across."""
    if not times:
        return None
    work = out.parent / "shots"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    for number, t in enumerate(times[:24], start=1):
        subprocess.run([_ffmpeg(), "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
                        "-vf", "scale=270:-2", str(work / f"shot{number:02d}.jpg")], capture_output=True)
    shots = sorted(work.glob("shot*.jpg"))
    if not shots:
        return None
    rows = (len(shots) + 3) // 4
    subprocess.run([_ffmpeg(), "-loglevel", "error", "-y", "-framerate", "1", "-i", str(work / "shot%02d.jpg"),
                    "-vf", f"tile=4x{rows}:padding=6:margin=6:color=white", "-frames:v", "1", str(out)], capture_output=True)
    return out if out.exists() else None


def analyze(path: Path, outdir: Path, threshold: float = 0.3) -> dict:
    if not path.exists():
        raise Book2VideoError(f"reference not found: {path}")
    outdir.mkdir(parents=True, exist_ok=True)
    info = probe(path)
    is_image = info["duration"] == 0.0
    cut_times = [] if is_image else cuts(path, threshold)
    bounds = [0.0, *cut_times, info["duration"]] if not is_image else []
    shots = [round(b - a, 2) for a, b in zip(bounds, bounds[1:]) if b - a > 0.05]
    samples = frames(path)
    colours = palette(samples)
    motion_value, motion_word = motion_level(samples)
    middles = [round((a + b) / 2, 2) for a, b in zip(bounds, bounds[1:]) if b - a > 0.05] if not is_image else []
    sheet = contact_sheet(path, middles, outdir / "contact-sheet.jpg") if middles else None
    if is_image:
        sheet = None
    mean_light = statistics.mean(c["lightness"] for c in colours) if colours else 0
    mean_sat = statistics.mean(c["saturation"] for c in colours) if colours else 0
    report = {
        "source": str(path),
        **info,
        "aspect": "portrait" if info["height"] > info["width"] else "landscape" if info["width"] > info["height"] else "square",
        "cuts": cut_times,
        "shots": len(shots),
        "shot_seconds": {
            "average": round(statistics.mean(shots), 2) if shots else None,
            "median": round(statistics.median(shots), 2) if shots else None,
            "shortest": min(shots) if shots else None,
            "longest": max(shots) if shots else None,
        },
        "cuts_per_minute": round(len(cut_times) / info["duration"] * 60, 1) if info["duration"] else None,
        "colours": colours,
        "brightness": "dark" if mean_light < 0.35 else "bright" if mean_light > 0.65 else "mid",
        "saturation": "muted" if mean_sat < 0.3 else "vivid" if mean_sat > 0.6 else "moderate",
        "motion": {"value": motion_value, "level": motion_word},
        "suggested_palettes": suggest_palettes(colours),
        "contact_sheet": str(sheet) if sheet else None,
    }
    (outdir / "reference.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (outdir / "reference.md").write_text(_markdown(report), encoding="utf-8")
    return report


def _markdown(r: dict) -> str:
    lines = [f"# Reference: {Path(r['source']).name}", ""]
    lines.append(f"- Frame: {r['width']}x{r['height']} ({r['aspect']}), {r['fps']} fps, {r['duration']} s")
    if r["shots"]:
        s = r["shot_seconds"]
        lines.append(f"- Pacing: {r['shots']} shots, {r['cuts_per_minute']} cuts a minute; shots last {s['average']} s on average "
                     f"(median {s['median']}, {s['shortest']}–{s['longest']} s)")
        lines.append(f"- Cuts at: {', '.join(str(t) for t in r['cuts'][:40])}{' …' if len(r['cuts']) > 40 else ''}")
    lines.append(f"- Look: {r['brightness']}, {r['saturation']} colour; motion {r['motion']['level']} ({r['motion']['value']})")
    lines.append("- Colours: " + ", ".join(f"{c['hex']} ({c['share']:.0%})" for c in r["colours"]))
    lines.append("")
    lines.append("Starter palettes for the script (check them against the contact sheet and adjust):")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps({"palettes": r["suggested_palettes"]}, indent=2))
    lines.append("```")
    if r["contact_sheet"]:
        lines += ["", f"Contact sheet (one frame per shot): {r['contact_sheet']}"]
    return "\n".join(lines) + "\n"
