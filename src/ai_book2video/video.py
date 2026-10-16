"""Assemble the MP4: each scene is an animated page, captured frame by frame, with its narration."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from ai_book2video import motion, music, sfx, speech, subtitles
from ai_book2video.browser import find_chrome, find_node
from ai_book2video.errors import Book2VideoError
from ai_book2video.script import Script, Scene

HERE = Path(__file__).resolve().parent
CAPTURE = HERE / "capture.mjs"
FPS = 30
MIN_SCENE_SECONDS = 4.0
TAIL_SECONDS = 0.8
LOUDNESS = -16.0  # LUFS for the finished film: about what phone video apps play at
SFX_VOLUME = 1.0
MUSIC_LEVEL = -14.0  # dB of the music bed relative to the film's loudness (before ducking)
MUSIC_DUCK = 8.0  # dB the bed drops while the narrator speaks  # multiplies the built-in sound effect levels (sfx.LEVELS)
DEFAULT_JOBS = max(1, min(4, (os.cpu_count() or 4) // 8))  # scenes rendered at the same time; kept low so the CPU stays cool


@dataclass
class SceneTiming:
    index: int
    narration_seconds: float
    clip_seconds: float
    start: float


def has_talker(scene: Scene) -> bool:
    """True when a "talk" actor is on stage, so it is worth reading a voice envelope for the mouth."""
    stage = scene.stage if isinstance(scene.stage, dict) else {}
    return any(isinstance(a, dict) and a.get("action") == "talk" for a in stage.get("actors", []))


def scene_cues(scene: Scene, start: float, end: float, spoken: list | None = None) -> list[subtitles.Cue]:
    """Subtitles for one scene: English narration with its Chinese pair when given.
    With `spoken` word timings (from Kokoro) each sentence starts exactly when it is said;
    without them, time is shared out by sentence length."""
    english = subtitles.sentences(scene.narration) or [scene.narration]
    chinese = subtitles.sentences(scene.narration_zh) if scene.narration_zh else []
    if spoken:
        return subtitles.timed_cues(english, chinese, spoken, start, end)
    if scene.narration_zh:
        cues = subtitles.pair_cues(english, chinese, start, end)
    else:
        cues = subtitles.cues_for(scene.narration, start, end)
    for cue in cues:
        subtitles.estimate_words(cue)
    return cues


def spoken_words(wav: Path) -> list:
    """Word timings Kokoro wrote next to the narration, or [] when there are none."""
    path = wav.with_suffix(".words.json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def cue_rows(cues: list[subtitles.Cue]) -> list[list]:
    """[start, end, english, chinese, words, captions] per cue. `words` are [[word, start], ...] for
    "w:" cues; `captions` are [[token, start], ...], one per displayed word, for the caption highlight."""
    return [[round(c.start, 3), round(c.end, 3), c.text, c.zh, c.words, c.captions] for c in cues]


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


ENCODERS = ("cpu", "nvenc")
VIDEO_ARGS = {
    # libx264 on the CPU: small files, but it competes with Chrome for the cores.
    "cpu": ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-maxrate", "10M", "-bufsize", "20M"],
    # NVIDIA hardware encoder: frees the CPU for frame capture. Constant quality 23, same bitrate cap.
    "nvenc": ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "23", "-b:v", "0", "-maxrate", "10M", "-bufsize", "20M"],
}


def nvenc_available() -> bool:
    """True when ffmpeg has h264_nvenc and an NVIDIA GPU accepts a tiny test encode."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    probe = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=size=256x256:duration=0.1",
         "-c:v", "h264_nvenc", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0


def encode_scene(frames_dir: Path, wav: Path, seconds: float, out: Path, encoder: str = "cpu",
                 effects: Path | None = None, effects_volume: float = SFX_VOLUME) -> None:
    audio_inputs = ["-i", str(wav)]
    mix = "[1:a]apad,atrim=0:" + f"{seconds:.3f}" + "[a]"
    if effects is not None:
        # Narration on top, code-made sound effects quietly underneath.
        audio_inputs += ["-i", str(effects)]
        mix = (f"[1:a]apad,atrim=0:{seconds:.3f}[n];[2:a]apad,atrim=0:{seconds:.3f},volume={effects_volume:.3f}[s];"
               "[n][s]amix=inputs=2:duration=first:normalize=0[a]")
    result = subprocess.run(
        [
            require_ffmpeg(), "-y", "-loglevel", "error",
            "-framerate", str(FPS), "-i", str(frames_dir / "f%05d.jpg"),
            *audio_inputs,
            "-filter_complex", mix,
            "-map", "0:v", "-map", "[a]",
            "-t", f"{seconds:.3f}",
            "-vf", "format=yuv420p",
            *VIDEO_ARGS[encoder],
            "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Book2VideoError(f"ffmpeg failed on {out.name}: {result.stderr.strip()[-400:]}")


def level_loudness(source: Path, out: Path, loudness: float = LOUDNESS) -> dict:
    """Bring `source`'s sound to `loudness` LUFS and write the result to `out`. Two-pass loudnorm,
    measured over the whole file first, so phones play it as loud as other videos: a plain gain when
    the peaks allow, otherwise loudnorm gently limits the loudest peaks to keep 1.5 dB of headroom.
    The picture is copied, not re-encoded, and `out` may equal `source` (a temp file is used)."""
    target = f"I={loudness}:TP=-1.5:LRA=11"
    measure = subprocess.run(
        [require_ffmpeg(), "-hide_banner", "-nostats", "-i", str(source), "-vn", "-af", f"loudnorm={target}:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    found = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", measure.stderr)
    if measure.returncode != 0 or not found:
        raise Book2VideoError(f"measuring loudness failed: {measure.stderr.strip()[-400:]}")
    m = json.loads(found.group(0))
    apply = (f"loudnorm={target}:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
             f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
    dest = out
    if out.resolve() == source.resolve():
        dest = out.with_suffix(".leveled" + out.suffix)
    result = subprocess.run(
        [require_ffmpeg(), "-y", "-loglevel", "error", "-i", str(source), "-c:v", "copy", "-af", apply, "-ar", "48000",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(dest)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise Book2VideoError(f"loudness step failed: {result.stderr.strip()[-400:]}")
    if dest != out:
        dest.replace(out)
    return {"target_lufs": loudness, "measured_lufs": float(m["input_i"]), "measured_peak": float(m["input_tp"])}


def _integrated_lufs(path: Path) -> float:
    result = subprocess.run([require_ffmpeg(), "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "ebur128", "-f", "null", "-"],
                            capture_output=True, text=True)
    found = re.findall(r"I:\s+(-?[0-9.]+) LUFS", result.stderr)
    if not found:
        raise Book2VideoError(f"measuring loudness of {path.name} failed: {result.stderr.strip()[-300:]}")
    return float(found[-1])


def add_music(film: Path, loop: Path, out: Path, level: float = MUSIC_LEVEL, duck: float = MUSIC_DUCK) -> dict:
    """Lay a seamless music loop under the whole film: `level` dB relative to the film's own loudness,
    faded in over 2 s and out over 4 s, and lowered by up to about `duck` dB whenever the narration
    is speaking (sidechain compression keyed by the film's own sound). The picture is copied."""
    seconds = speech.duration(film)
    film_lufs = _integrated_lufs(film)
    loop_lufs = _integrated_lufs(loop)
    gain = film_lufs + level - loop_lufs
    ratio = max(1.5, 10 ** (duck / 20) * 1.5)
    graph = (
        f"[1:a]aformat=sample_rates=48000:channel_layouts=mono,atrim=0:{seconds:.3f},asetpts=N/SR/TB,volume={gain:.2f}dB,"
        f"afade=t=in:st=0:d=2,afade=t=out:st={max(0.0, seconds - 4):.3f}:d=4[m];"
        "[0:a]aformat=sample_rates=48000:channel_layouts=mono,asplit=2[v][key];"
        f"[m][key]sidechaincompress=threshold=0.02:ratio={ratio:.1f}:attack=40:release=600[md];"
        "[v][md]amix=inputs=2:duration=first:normalize=0[a]"
    )
    result = subprocess.run(
        [require_ffmpeg(), "-y", "-loglevel", "error", "-i", str(film), "-stream_loop", "-1", "-i", str(loop),
         "-filter_complex", graph, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-t", f"{seconds:.3f}", "-movflags", "+faststart", str(out)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise Book2VideoError(f"adding music failed: {result.stderr.strip()[-400:]}")
    return {"film_lufs": film_lufs, "music_gain_db": round(gain, 2), "level_db": level, "duck_db": duck}


def join_clips(clips: list[Path], out: Path, workdir: Path, loudness: float | None = LOUDNESS,
               music_loop: Path | None = None, music_level: float | None = None) -> dict | None:
    """Join the scene clips in order. With `music_loop`, lay it under the film (see `add_music`).
    With `loudness` (LUFS), bring the sound to that level (see `level_loudness`). The picture is
    copied, not re-encoded."""
    listing = workdir / "clips.txt"
    listing.write_text("".join(f"file '{clip.resolve()}'\n" for clip in clips), encoding="utf-8")
    joined = out if loudness is None else workdir / "joined.mp4"
    result = subprocess.run(
        [require_ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(joined)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Book2VideoError(f"joining clips failed: {result.stderr.strip()[-400:]}")
    info: dict = {}
    if music_loop is not None:
        scored = workdir / "with-music.mp4"
        target = scored if loudness is not None else out
        if loudness is None and joined == out:
            joined = out.with_suffix(".nomusic" + out.suffix)
            out.replace(joined)
        info["music"] = add_music(joined, music_loop, target, MUSIC_LEVEL if music_level is None else music_level)
        joined = scored if loudness is not None else out
    if loudness is None:
        return info or None
    info.update(level_loudness(joined, out, loudness))
    return info


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
    encoder: str = "cpu",
    effects: bool = False,
    effects_volume: float = SFX_VOLUME,
    camera: str | None = None,
    loudness: float | None = LOUDNESS,
    music_mood: str | None = None,
    music_level: float = MUSIC_LEVEL,
) -> dict:
    """Render the video. Returns the manifest (also written to workdir/manifest.json)."""
    require_ffmpeg()
    find_node()
    find_chrome()
    if encoder not in ENCODERS:
        raise Book2VideoError(f"encoder must be one of {', '.join(ENCODERS)}")
    if encoder == "nvenc" and not nvenc_available():
        raise Book2VideoError("the nvenc encoder needs ffmpeg with h264_nvenc and an NVIDIA GPU; use --encoder cpu")
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
            wav.with_suffix(".words.json").unlink(missing_ok=True)  # no stale timings from an earlier Kokoro run
            speech.synthesize(scene.narration, wav, backend=tts, voice=voice, rate=rate, command=tts_command)
        spoken = speech.duration(wav)
        seconds = max(MIN_SCENE_SECONDS, spoken + TAIL_SECONDS)
        page = pages_dir / f"scene{scene.index:03d}.html"
        local_cues = scene_cues(scene, 0.0, spoken, spoken_words(wav))
        voice_env = speech.amplitude_envelope(wav) if has_talker(scene) else None
        page.write_text(
            motion.scene_page(scene, scene.index, script.title, seconds, cue_rows(local_cues), script.book, script.chapter,
                              script.palettes, camera or script.camera, voice_env, speech.ENVELOPE_RATE),
            encoding="utf-8",
        )
        clip = clips_dir / f"scene{scene.index:03d}.mp4"
        effects_wav = None
        if effects:
            events = sfx.scene_events(scene, cue_rows(local_cues), seconds, last=scene is scenes[-1])
            if events:
                effects_wav = sfx.render(events, seconds, audio_dir / f"scene{scene.index:03d}.sfx.wav")
        jobs_list.append((scene, page, wav, seconds, clip, effects_wav))
        clip_paths.append(clip)
        timings.append(SceneTiming(scene.index, round(spoken, 2), round(seconds, 2), round(cursor, 2)))
        cues.extend(subtitles.Cue(cue.start + cursor, cue.end + cursor, cue.text, cue.zh) for cue in local_cues)
        cursor += seconds

    def render(job) -> None:
        scene, page, wav, seconds, clip, effects_wav = job
        frames_dir = workdir / "frames" / f"scene{scene.index:03d}"
        if frames_dir.exists():
            shutil.rmtree(frames_dir)
        times = [i / FPS for i in range(max(1, round(seconds * FPS)))]
        capture_frames(page, frames_dir, times)
        encode_scene(frames_dir, wav, seconds, clip, encoder, effects_wav, effects_volume)
        if not keep_frames:
            shutil.rmtree(frames_dir, ignore_errors=True)

    # Each scene is captured by its own headless Chrome (own profile, own port), so scenes render in parallel.
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        for future in [pool.submit(render, job) for job in jobs_list]:
            future.result()
    out.parent.mkdir(parents=True, exist_ok=True)
    mood = music_mood or script.music or None
    loop = music.render_loop(mood, workdir / f"music-{mood}.wav") if mood else None
    levels = join_clips(clip_paths, out, workdir, loudness, loop, music_level)
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
        "encoder": encoder,
        "sound_effects": effects,
        "camera": camera or script.camera,
        "loudness": levels,
        "music": mood,
        "scenes": [timing.__dict__ for timing in timings],
    }
    (workdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def preview(script: Script, outdir: Path, only: set[int] | None = None, camera: str | None = None) -> list[Path]:
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
            motion.scene_page(scene, scene.index, script.title, seconds, cue_rows(cues), script.book, script.chapter,
                              script.palettes, camera or script.camera),
            encoding="utf-8",
        )
        frames = outdir / f"scene{scene.index:03d}"
        capture_frames(page, frames, [0.6, seconds * 0.5, seconds - 0.4])
        written.extend(sorted(frames.glob("*.jpg")))
    return written
