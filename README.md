# ai-book2video

Turn a book chapter (or any Markdown document) into a fun, animated, narrated **portrait MP4** for phones.

- **9:16 video** (1080 × 1920), ready for short-video apps.
- **Animated stick-figure stage** drawn in SVG: colourful crayon-textured backgrounds, round-headed characters with faces (happy, sad, surprised, hurt), blinking, breathing, walking, falling, talking, speech bubbles, impact bursts and props (cars, trains, trees, sun, fire, buildings, books, podiums, letters, clocks, walls, crates, chairs, easels).
- **A camera that cuts on every sentence** (wide, medium, close-up) and drifts, so the picture never sits still.
- **Actions land on the words**: an action can be timed to a narration sentence (`"at": "s2"`), so the car hits exactly when the narrator says it does.
- **Natural English narration** with [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M), an open model that runs locally on your GPU. espeak-ng works as a fallback.
- **Bilingual subtitles**: each English sentence is shown with its Chinese translation, burned into the video and also written as an SRT file.
- **Timed to the voice**: subtitles start when each sentence is actually spoken, from Kokoro's word timings, and actions can land on a word (`"at": "w:knife"`). The English caption highlights the word being said as it is said.
- **A mouth driven by the real narration**: a `"talk"` actor's mouth opens with the synthesised voice's actual loudness, not a fixed flap.
- **A director camera** (default): it chooses the move for each sentence (hold, ease in, glide, pull back, or a fast push on an impact) instead of repeating one move. `"camera": "classic"` brings back the original cut-every-sentence style.
- **Checked with numbers** (`check`): motion per scene, frozen stretches, jumps, blank frames, silent scenes and loudness, before anyone watches. The finished film is levelled to -16 LUFS.
- **Background music made in code** (`--music calm|reflective|tense`): a pad, bass and plucked arpeggio on a four-chord progression, looped seamlessly under the film, kept well below the voice and ducked further whenever the narrator speaks.
- **Sound effects made in code** (`--sfx`): bangs, thuds, train whistles and chugs, footsteps, ticking clocks, pops and whooshes, synthesised from tones and noise and timed to the action. No sound files to download or license.
- **Learn a style from a reference** (`analyze-ref`): measure a video or picture you like (cuts, shot lengths, colours, motion), get a contact sheet and starter colour palettes, and give the book its own look with a `palettes` list.

The tool does the mechanical work. The scene script (what each scene shows and what the narrator says) is written by Claude or by hand, as JSON. See `SKILL.md` for the full workflow Claude follows.

## One chapter, one video

```bash
ai-book2video doctor                                   # check the tools
ai-book2video ingest book.md -o book.json              # split the book into sections (Markdown or text)
ai-book2video outline book.json                        # list the sections
ai-book2video section book.json s03                    # read one section (add --part 2 for long ones)
# write chapter3.script.json (see the format below)
ai-book2video validate chapter3.script.json            # check it, including the English/Chinese sentence pairs
ai-book2video preview chapter3.script.json -o preview  # three frames per scene, to check layout and motion
ai-book2video build chapter3.script.json -o sample.mp4 --scenes 1,14,30 --sfx   # sample a few scenes first
ai-book2video build chapter3.script.json -o chapter3.mp4 --sfx   # narration, frames, sound, MP4 and SRT
ai-book2video check chapter3.mp4                       # motion, frozen stretches, jumps, sound: red items block delivery
ai-book2video analyze-ref liked-video.mp4              # pacing, colours and motion of a style to follow
```

`LESSONS.md` collects what has worked and what went wrong, with evidence.

Render a sample of two or three scenes (the hook, the busiest scene, a quiet one) before the full chapter: a sample takes about a minute, so the look and the sound are cheap to fix there.

Try the example first:

```bash
ai-book2video build examples/tortoise-and-hare.script.json -o slow-and-steady.mp4
```

Input must be Markdown (`.md`) or plain text (`.txt`). Convert PDF, EPUB or DOCX to Markdown first.

## Install

System tools: Python 3.10+, Node.js 22+, ffmpeg (with libx264), Chrome or Chromium, and espeak-ng (fallback voice). The package itself uses only the Python standard library:

```bash
git clone https://github.com/MichaelMuClaude/ai-book2video.git
cd ai-book2video
printf '#!/usr/bin/env bash\nexport PYTHONPATH="%s/src${PYTHONPATH:+:$PYTHONPATH}"\nexec python3 -m ai_book2video "$@"\n' "$PWD" > ~/.local/bin/ai-book2video
chmod +x ~/.local/bin/ai-book2video
```

Kokoro (the default voice) runs in its own virtual environment. With an NVIDIA GPU:

```bash
python3 -m venv ~/.venvs/kokoro
~/.venvs/kokoro/bin/pip install torch --index-url https://download.pytorch.org/whl/cu128
~/.venvs/kokoro/bin/pip install kokoro soundfile
```

The first run downloads the Kokoro model (about 330 MB) from Hugging Face. Set `KOKORO_PYTHON` if the environment lives elsewhere, or use `--tts espeak` to skip Kokoro.

## Script format

```json
{
  "title": "Slow and Steady",
  "language": "en",
  "scenes": [
    {
      "kind": "stage",
      "heading": "Slow and Steady",
      "narration": "A hare laughed at a tortoise. So the tortoise said: let us race.",
      "narration_zh": "一只兔子嘲笑乌龟。于是乌龟说：那我们来比赛吧。",
      "stage": {
        "background": "field",
        "split": true,
        "actors": [
          {"label": "Hare", "x": 500, "action": "talk", "face": "happy",
           "say": [{"text": "So slow!", "at": "s1+0.4", "dur": 2.0}]},
          {"label": "Tortoise", "x": 1400, "action": "stand", "face": "sad",
           "faces": [{"at": "s2", "face": "happy"}]}
        ],
        "props": [{"type": "sun", "x": 1500, "y": 100}]
      }
    }
  ]
}
```

**Narration.** `narration` is spoken (English). `narration_zh` is its Chinese translation, sentence by sentence: both must have the same number of sentences, and `validate` checks it. Avoid abbreviations with full stops (write "Thomas Ricks", not "Thomas E. Ricks") because a full stop ends a sentence.

**Scene kinds.** `stage` (the animated stick-figure scene) is the main one. `title`, `text`, `bullets`, `quote` and `stat` (a number that counts up) are also available, for openings, credits and key points.

**Stage.**

| Field | Values |
|---|---|
| `background` | `street`, `field`, `room`, `plain`, `night`; `"split": true` adds two colour blocks |
| actor `action` | `stand`, `walk` (with `to`, `at`, `dur`), `fall` (at `at`), `talk`, `wave` |
| actor `face` / `faces` | `neutral`, `happy`, `sad`, `surprised`, `hurt`; `faces` changes the face over time |
| actor `say` | speech bubbles: `[{"text": "...", "at": "s2", "dur": 2.5}]` |
| actor `label`, `colour` | a short name above the head; a body colour |
| prop `type` | `car`, `train` (move with `to`; `armoured`), `tree`, `sun`, `fire`, `building` (`w`, `h`), `podium`, `book`, `burst` (`text`, `at`), `letter` (`y`, `to`), `clock` (`spin`, `at`, `dur`), `wall` (`w`, `h`), `crate` (`text`), `chair`, `easel` |
| `camera` | top level, per stage or `--camera`: `director` (default; the move fits what each sentence shows), `classic` (a new framing on every sentence), or `false` on a stage |
| timing (`at`) | seconds, `"s2+0.5"` (sentence start), or `"w:knife"` (when that word is said; `#2` for the second time) |
| `palettes` (top level) | colour sets scenes take in turn: `[{"bg": "#fff3d6", "accent": "#7c3aed", "card": "#1b1b3a"}]`; text colours are chosen for contrast |
| prop or actor `sfx` | with `--sfx`: `impact`, `chime`, `sad`, `question`, `pop` or `none` (otherwise chosen from the action or the burst's word) |

`x` positions are on a 0–1920 scale across the stage (they are fitted to the portrait frame); keep actors between about 250 and 1650. `y` is in pixels from the top. Times are seconds, or a sentence reference: `"s2"` is the start of sentence 2, `"s2+0.5"` half a second later.

## Output

`build` writes the MP4 and an SRT file next to it, plus a working folder with the pages, audio, clips and `manifest.json` (scene timings). Rendering uses headless Chrome to capture every frame. Scenes render in parallel (`--jobs`, default: an eighth of the CPU cores, at most 4, to keep the CPU cool; raise it for speed), each in its own Chrome, and the clips are then joined in order. On a 32-core machine a 9-minute chapter renders in about 5 minutes with `--jobs 8`; one scene at a time it takes about 3 seconds of compute per second of video. Files are about 45 MB per minute. `--encoder nvenc` encodes on an NVIDIA GPU instead of with libx264; in testing it saved only about 6% of the time (frame capture, not encoding, is the heavy part) and made files about 50% larger, so `cpu` stays the default.

## Copyright

Summarise in your own words, keep any quotation short and attributed, and name the book and author (for example in a closing credit scene). Do not reproduce long passages. Check the rules of the platform where you publish. This is not legal advice.

## Tests

```bash
python3 -m unittest discover -s tests -t . -p "test_*.py"
```

## Layout

- `src/ai_book2video/ingest.py`: Markdown or text to sections (CJK-aware word counts)
- `src/ai_book2video/script.py`: scene script format and validation
- `src/ai_book2video/motion.py`: page templates, the timeline engine and bilingual captions
- `src/ai_book2video/svgstage.py`: the SVG stick-figure stage, faces, props, camera and sentence timing
- `src/ai_book2video/capture.mjs`: headless Chrome frame capture (DevTools protocol)
- `src/ai_book2video/speech.py`, `tts_kokoro.py`: narration with Kokoro, espeak-ng or a custom command
- `src/ai_book2video/subtitles.py`: sentence splitting, bilingual cues and SRT
- `src/ai_book2video/sfx.py`: sound effects synthesised in code and placed on the action
- `src/ai_book2video/music.py`: background music synthesised in code as a seamless loop
- `src/ai_book2video/check.py`: measures a finished film (motion per scene, frozen stretches, jumps, blank frames, sound)
- `src/ai_book2video/reference.py`: reference analysis (cuts, shot lengths, colours, motion, contact sheet)
- `src/ai_book2video/video.py`: clips per scene, rendered in parallel and joined into the final MP4
- `src/ai_book2video/cli.py`: the `ai-book2video` commands
- `examples/tortoise-and-hare.script.json`: a public-domain example (Aesop)

## Acknowledgements

We learn from other people's good work and say so. No code was copied; the ideas were.

- [chengfeng-video-styles](https://github.com/Agentchengfeng/chengfeng-video-styles) by 成峰: render a short sample before the full video; make sound effects in code instead of fetching sound files; study a liked video shot by shot.
- [huashu-art-motion](https://github.com/alchaincyf/huashu-art-motion) by 花叔 (MIT): the camera rules behind the director camera (hold when the picture moves, fast moves only for accents, every push answered); cues that name a word instead of a second; measuring the finished film before delivery and failing slide-like scenes; independent review that checks facts as well as pictures; and keeping a lessons file with evidence.
- [anything2video](https://github.com/2021291696/anything2video) (MIT), whose audio engine comes from [mg-styles-15](https://github.com/Vincentwei1021/mg-styles-15): background music made in code with a mood per style, kept under the voice and ducked; sound placed by its sync point (a hit one frame early so it reads on the frame, a whoosh peaking as the movement crosses); and careful credit for every borrowed piece.
- [Remotion](https://github.com/remotion-dev/remotion) (its own licence, not used as a dependency — see `LESSONS.md`): the idea of driving a mouth or a visual from the real amplitude of the rendered audio instead of a fixed loop, and of highlighting the word a caption is currently saying from word-level timing.

## Licence

MIT (see `LICENSE`).
