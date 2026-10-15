# ai-book2video

Turn a Markdown document into a fun, animated, ad-style narrated MP4 video, with a voice and subtitles. Input is Markdown or plain text; convert other formats first.

The tool does the mechanical work: it splits a document into sections, renders each scene as an animated motion-graphics page (words pop in, bullets slide in, numbers count up), captures the frames with headless Chrome, makes the narration with espeak-ng (or a command you give), and joins the clips into an H.264 MP4 with an SRT file. The scene script (what each scene shows and what the narrator says) is written by Claude or by hand, as JSON.

## Use

```bash
ai-book2video doctor
ai-book2video ingest doc.md -o book.json
ai-book2video outline book.json
ai-book2video section book.json s02
ai-book2video validate examples/ai-paint-readme.script.json
ai-book2video preview examples/ai-paint-readme.script.json -o preview
ai-book2video build examples/ai-paint-readme.script.json -o how-it-works.mp4
```

`examples/ai-paint-readme.script.json` is a 9-scene script written from ai-paint's README. Building it gives a two-minute MP4 in about 15 seconds on this machine.

## Requirements

- Python 3.10+ (standard library only; no pip install)
- ffmpeg and ffprobe with libx264 and AAC
- espeak-ng (narration)
- Node.js 22+ (frame capture)
- Chrome or Chromium (frame capture; set `CHROME_PATH` if it is not on PATH)
- Input: Markdown (`.md`) or plain text (`.txt`)

## Tests

```bash
python3 -m unittest discover -s tests -t . -p "test_*.py"
```

## Layout

- `src/ai_book2video/ingest.py`: document to sections
- `src/ai_book2video/script.py`: scene script format and validation
- `src/ai_book2video/motion.py`: animated scene templates and the timeline engine
- `src/ai_book2video/capture.mjs`: headless Chrome frame capture (DevTools protocol)
- `src/ai_book2video/browser.py`: find Chrome and Node
- `src/ai_book2video/speech.py`: narration (espeak-ng or a custom command)
- `src/ai_book2video/subtitles.py`: SRT timing
- `src/ai_book2video/video.py`: per-scene clips and the joined MP4
- `src/ai_book2video/cli.py`: the `ai-book2video` commands
- `SKILL.md`: the instructions Claude reads when it uses the tool

## Status

Version 0.1: first working version, MIT licensed (see `LICENSE`). Known limits are listed in `SKILL.md`. Not yet done: better voices, GPU rendering, custom drawings beyond the built-in stick-figure stage, and images from the book.
