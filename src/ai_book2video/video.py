"""Assemble the MP4: each scene is an animated page, captured frame by frame, with its narration."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from ai_book2video import motion, speech, subtitles
from ai_book2video.browser import find_chrome, find_node
from ai_book2video.errors import Book2VideoError
from ai_book2video.script import Script, Scene

HERE = Path(__file__).resolve().parent
CAPTURE = HERE / "capture.mjs"
FPS = 30
MIN_SCENE_SECONDS = 4.0
TAIL_SECONDS = 0.8
DEFAULT_JOBS = max(1, min(8, (os.cpu_count() or 4) // 4))  # scenes rendered at the same time


@dataclass
class SceneTiming:
    index: int
    narration_seconds: float
    clip_seconds: float
    start: float


def scene_cues(scene: Scene, start: float, end: float) -> list[subtitles.Cue]:
    """Subtitles for one scene: English narration with its Chinese pair when given."""
    english = subtitles.sentences(scene.narration) or [scene.narration]
    if scene.narration_zh:
        return subtitles.pair_cues(english, subtitles.sentences(scene.narration_zh), start, end)
    return subtitles.cues_for(scene.narration, start, end)


def cue_rows(cues: list[subtitles.Cue]) -> list[list]:
    return [[round(c.start, 3), round(c.end, 3), c.text, c.zh] for c in cues]


def require_ffmpeg() -> str:
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise Book2VideoError(f"{tool} is not installed or not on PATH")
    return shutil.which("ffmpeg")


def capture_frames(page: Path, frames_dir: Path, times: list[float]) -> None:
    """Render the page at each time (seconds) into frames_dir as JPEG files."""
    frames_dir.mkdir(parents=True, exist_ok=True)
    times_file = frames_dir.with_suffix(".times.json")
    times_file.write_text(json.dumps([round(t, 4) for t in times]), encoding="utf-8")
    result = subprocess.run(
        [find_node(), str(CAPTURE), str(page), str(frames_dir), str(motion.WIDTH), str(motion.HEIGHT), find_chrome(), str(times_file)],
        capture_output=True,
        text=True,
        timeout=60 * 30,
    )
    times_file.unlink(missing_ok=True)
    if result.returncode != 0 or "captured" not in result.stdout:
        raise Book2VideoError(f"frame capture failed for {page.name}: {(result.stderr or result.stdout).strip()[-600:]}")


def encode_scene(frames_dir: Path, wav: Path, seconds: float, out: Path) -> None:
    result = subprocess.run(
        [
            require_ffmpeg(), "-y", "-loglevel", "error",
            "-framerate", str(FPS), "-i", str(frames_dir / "f%05d.jpg"),
            "-i", str(wav),
            "-filter_complex", "[1:a]apad,atrim=0:" + f"{seconds:.3f}" + "[a]",
            "-map", "0:v", "-map", "[a]",
            "-t", f"{seconds:.3f}",
            "-vf", "format=yuv420p",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-maxrate", "10M", "-bufsize", "20M",
            "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Book2VideoError(f"ffmpeg failed on {out.name}: {result.stderr.strip()[-400:]}")


def join_clips(clips: list[Path], out: Path, workdir: Path) -> None:
    listing = workdir / "clips.txt"
    listing.write_text("".join(f"file '{clip.resolve()}'\n" for clip in clips), encoding="utf-8")
    result = subprocess.run(
        [require_ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(out)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Book2VideoError(f"joining clips failed: {result.stderr.strip()[-400:]}")


def build(
    script: Script,
    out: Path,
    workdir: Path,
    tts: str = "espeak",
    voice: str = "en-us",
    rate: int = 165,
    tts_command: str = "",
    only: set[int] | None = None,
    subtitles_file: bool = True,
    keep_frames: bool = False,
    jobs: int = DEFAULT_JOBS,
) -> dict:
    """Render the video. Returns the manifest (also written to workdir/manifest.json)."""
    require_ffmpeg()
    find_node()
    find_chrome()
    workdir.mkdir(parents=True, exist_ok=True)
    scenes = [scene for scene in script.scenes if only is None or scene.index in only]
    if not scenes:
        raise Book2VideoError("no scenes selected")
    pages_dir = workdir / "pages"
    audio_dir = workdir / "audio"
    clips_dir = workdir / "clips"
    for folder in (pages_dir, audio_dir, clips_dir):
        folder.mkdir(exist_ok=True)
    clip_paths: list[Path] = []
    timings: list[SceneTiming] = []
    cues: list[subtitles.Cue] = []
    cursor = 0.0
    if tts == "kokoro":
        speech.kokoro_batch([(scene.narration, audio_dir / f"scene{scene.index:03d}.wav") for scene in scenes], voice=voice)
    jobs_list = []
    for scene in scenes:
        wav = audio_dir / f"scene{scene.index:03d}.wav"
        if tts != "kokoro":
            speech.synthesize(scene.narration, wav, backend=tts, voice=voice, rate=rate, command=tts_command)
        spoken = speech.duration(wav)
        seconds = max(MIN_SCENE_SECONDS, spoken + TAIL_SECONDS)
        page = pages_dir / f"scene{scene.index:03d}.html"
        local_cues = scene_cues(scene, 0.0, spoken)
        page.write_text(
            motion.scene_page(scene, scene.index, script.title, seconds, cue_rows(local_cues), script.book, script.chapter),
            encoding="utf-8",
        )
        clip = clips_dir / f"scene{scene.index:03d}.mp4"
        jobs_list.append((scene, page, wav, seconds, clip))
        clip_paths.append(clip)
        timings.append(SceneTiming(scene.index, round(spoken, 2), round(seconds, 2), round(cursor, 2)))
        cues.extend(subtitles.Cue(cue.start + cursor, cue.end + cursor, cue.text, cue.zh) for cue in local_cues)
        cursor += seconds

    def render(job) -> None:
        scene, page, wav, seconds, clip = job
        frames_dir = workdir / "frames" / f"scene{scene.index:03d}"
        if frames_dir.exists():
            shutil.rmtree(frames_dir)
        times = [i / FPS for i in range(max(1, round(seconds * FPS)))]
        capture_frames(page, frames_dir, times)
        encode_scene(frames_dir, wav, seconds, clip)
        if not keep_frames:
            shutil.rmtree(frames_dir, ignore_errors=True)

    # Each scene is captured by its own headless Chrome (own profile, own port), so scenes render in parallel.
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        for future in [pool.submit(render, job) for job in jobs_list]:
            future.result()
    out.parent.mkdir(parents=True, exist_ok=True)
    join_clips(clip_paths, out, workdir)
    srt = out.with_suffix(".srt")
    if subtitles_file:
        subtitles.write_srt(cues, srt)
    manifest = {
        "title": script.title,
        "video": str(out),
        "subtitles": str(srt) if subtitles_file else None,
        "seconds": round(cursor, 2),
        "fps": FPS,
        "voice": voice if tts in ("espeak", "kokoro") else "custom command",
        "tts": tts,
        "orientation": "portrait 1080x1920",
        "scenes": [timing.__dict__ for timing in timings],
    }
    (workdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def preview(script: Script, outdir: Path, only: set[int] | None = None) -> list[Path]:
    """Render three key frames per scene (early, middle, late) as JPEG files, for a quick look."""
    find_node()
    find_chrome()
    outdir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for scene in script.scenes:
        if only is not None and scene.index not in only:
            continue
        seconds = max(MIN_SCENE_SECONDS, scene.seconds_estimate + TAIL_SECONDS)
        page = outdir / f"scene{scene.index:03d}.html"
        cues = scene_cues(scene, 0.0, max(1.0, seconds - TAIL_SECONDS))
        page.write_text(
            motion.scene_page(scene, scene.index, script.title, seconds, cue_rows(cues), script.book, script.chapter),
            encoding="utf-8",
        )
        frames = outdir / f"scene{scene.index:03d}"
        capture_frames(page, frames, [0.6, seconds * 0.5, seconds - 0.4])
        written.extend(sorted(frames.glob("*.jpg")))
    return written
