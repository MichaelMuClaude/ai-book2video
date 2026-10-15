"""Command-line interface: ai-book2video <command> ..."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from ai_book2video import __version__, browser, ingest, motion, script as scripts, speech, video
from ai_book2video.errors import Book2VideoError


def parse_scenes(text: str | None) -> set[int] | None:
    """'1,3,5-7' -> {1, 3, 5, 6, 7}. None means every scene."""
    if not text:
        return None
    chosen: set[int] = set()
    for part in text.split(","):
        if "-" in part:
            low, high = part.split("-", 1)
            chosen.update(range(int(low), int(high) + 1))
        else:
            chosen.add(int(part))
    return chosen


def cmd_ingest(args: argparse.Namespace) -> int:
    book = ingest.ingest(Path(args.file), title=args.title)
    out = Path(args.output or Path(args.file).with_suffix(".book.json"))
    out.write_text(json.dumps(book, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out}: {len(book['sections'])} sections, {book['words']} words (split by {book['split']})")
    return 0


def _load_book(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise Book2VideoError(f"book file not found: {path} (run 'ingest' first)") from error


def cmd_outline(args: argparse.Namespace) -> int:
    book = _load_book(args.book)
    print(f"{book['title']}  ({book['words']} words, split by {book['split']})")
    for section in book["sections"]:
        print(f"  {section['id']}  {section['words']:>6} words  {section['title']}")
    return 0


def cmd_section(args: argparse.Namespace) -> int:
    book = _load_book(args.book)
    section = ingest.find_section(book, args.id)
    total, text = ingest.section_part(section, args.part, args.max_words)
    header = f"# {section['title']}  ({section['id']}"
    header += f", part {args.part} of {total})" if total > 1 else ")"
    print(header)
    print()
    print(text)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.script)
    raw = json.loads(path.read_text(encoding="utf-8"))
    errors, warnings = scripts.check(raw)
    for warning in warnings:
        print(f"warning: {warning}")
    if errors:
        for error in errors:
            print(f"error: {error}")
        print(f"{len(errors)} error(s); fix the script before building")
        return 1
    script = scripts.load(path)
    print(
        f"ok: {len(script.scenes)} scenes, about {script.seconds_estimate / 60:.1f} min of narration "
        f"({len(warnings)} warning(s))"
    )
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    script = scripts.load(Path(args.script))
    out = Path(args.output)
    frames = video.preview(script, out, only=parse_scenes(args.scenes))
    print(f"wrote {len(frames)} preview frames to {out}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    script = scripts.load(Path(args.script))
    for warning in script.warnings:
        print(f"warning: {warning}")
    out = Path(args.output)
    workdir = Path(args.work) if args.work else out.with_suffix("")
    voice = args.voice or ("af_heart" if args.tts == "kokoro" else "en-us")
    manifest = video.build(
        script,
        out,
        workdir,
        tts=args.tts,
        voice=voice,
        rate=args.rate,
        tts_command=args.tts_command,
        only=parse_scenes(args.scenes),
        subtitles_file=not args.no_subtitles,
        keep_frames=args.keep_frames,
        jobs=args.jobs,
        encoder=args.encoder,
    )
    minutes, seconds = divmod(manifest["seconds"], 60)
    print(f"wrote {out}  ({int(minutes)} min {seconds:04.1f} s, {len(manifest['scenes'])} scenes)")
    if manifest["subtitles"]:
        print(f"subtitles: {manifest['subtitles']}")
    print(f"working files: {workdir}")
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    checks = {
        "ffmpeg": shutil.which("ffmpeg"),
        "ffprobe": shutil.which("ffprobe"),
        "espeak-ng (narration)": shutil.which("espeak-ng"),
    }
    try:
        checks["Chrome (frame capture)"] = browser.find_chrome()
    except Book2VideoError:
        checks["Chrome (frame capture)"] = None
    checks["node (frame capture)"] = shutil.which("node")
    kokoro = Path(speech.KOKORO_PYTHON)
    if kokoro.exists():
        probe = subprocess.run([str(kokoro), "-c", "import kokoro, torch; print(torch.cuda.is_available())"], capture_output=True, text=True)
        checks["Kokoro voice (default narration)"] = f"{kokoro} (GPU: {probe.stdout.strip()})" if probe.returncode == 0 else None
    else:
        checks["Kokoro voice (default narration)"] = None
    missing = 0
    for name, found in checks.items():
        print(f"{'ok ' if found else 'MISSING'}  {name}  {found or ''}")
        if not found and name.split(" ")[0] in ("ffmpeg", "Chrome", "node"):
            missing += 1
    return 1 if missing else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-book2video", description="Turn a book or document into a narrated MP4.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest", help="split a Markdown or text document into sections")
    p.add_argument("file")
    p.add_argument("-o", "--output", help="book JSON path (default: next to the input)")
    p.add_argument("--title", help="book title (default: the first heading)")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("outline", help="list the sections of an ingested book")
    p.add_argument("book")
    p.set_defaults(func=cmd_outline)

    p = sub.add_parser("section", help="print one section, so a writer can read it")
    p.add_argument("book")
    p.add_argument("id", help="section id from 'outline', e.g. s03")
    p.add_argument("--part", type=int, default=1, help="which piece, for long sections")
    p.add_argument("--max-words", type=int, default=1200, help="split sections longer than this (0 = never)")
    p.set_defaults(func=cmd_section)

    p = sub.add_parser("validate", help="check a scene script before rendering")
    p.add_argument("script")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("preview", help="render three key frames per scene, to check the motion and layout")
    p.add_argument("script")
    p.add_argument("-o", "--output", default="preview")
    p.add_argument("--scenes", help="e.g. 1,3,5-7")
    p.set_defaults(func=cmd_preview)

    p = sub.add_parser("build", help="render the narrated MP4 (and an SRT file)")
    p.add_argument("script")
    p.add_argument("-o", "--output", required=True, help="output .mp4")
    p.add_argument("--work", help="working folder (default: the output name without .mp4)")
    p.add_argument("--keep-frames", action="store_true", help="keep the captured frame images in the working folder")
    p.add_argument("--encoder", choices=video.ENCODERS, default="cpu",
                   help="video encoder: cpu (libx264) or nvenc (NVIDIA GPU, frees the CPU for frame capture)")
    p.add_argument("--jobs", type=int, default=video.DEFAULT_JOBS,
                   help=f"scenes to render at the same time (default {video.DEFAULT_JOBS} on this machine)")
    p.add_argument("--tts", default="kokoro", choices=speech.BACKENDS, help="narration engine (kokoro is the default)")
    p.add_argument("--voice", default=None, help="voice: af_heart (Kokoro, default), or an espeak voice such as en-us")
    p.add_argument("--rate", type=int, default=165, help="espeak words per minute")
    p.add_argument("--tts-command", default="", help="for --tts command: e.g. 'mytts --in {text} --out {out}'")
    p.add_argument("--scenes", help="render only these scenes, e.g. 1-3 (for a quick preview)")
    p.add_argument("--no-subtitles", action="store_true")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("doctor", help="check the tools this needs")
    p.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Book2VideoError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as error:
        print(f"error: not valid JSON: {error}", file=sys.stderr)
        return 2
