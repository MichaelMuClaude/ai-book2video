---
name: ai-book2video
description: Turn a book chapter, or any Markdown or plain-text document, into a fun, animated, narrated portrait MP4 for phones, with colourful SVG stick-figure scenes, a camera that cuts on every sentence, natural English narration and English–Chinese subtitles. Use this whenever someone wants a chapter, book, article, report or notes turned into a short video, an explainer, a narrated summary, or a "book to video" series, even if they never say "video" together with the document.
compatibility: Written for Claude Code. Needs Python 3.10+, Node.js 22+, ffmpeg with libx264, Chrome or Chromium, and Kokoro in its own virtual environment (or espeak-ng as a fallback). Input must be Markdown (.md) or plain text (.txt).
---

# ai-book2video

You turn one chapter into one short video. You read the chapter, think about it, and write a scene script. The `ai-book2video` tool renders the animation, the narration, the bilingual subtitles and the MP4.

The style that works: a portrait video, colourful stick figures acting out the story on an SVG stage, a camera that moves to a new shot on every sentence, actions timed to the words, speech bubbles and impact bursts, English narration in the Kokoro voice `af_heart`, and English–Chinese subtitles. It is an animation, not a slide show: the picture tells the story, and on-screen text is short.

## Commands

```bash
ai-book2video doctor                                   # check the tools (Kokoro should show GPU: True)
ai-book2video ingest book.md -o book.json              # split into sections
ai-book2video outline book.json                        # list the sections
ai-book2video section book.json s03 --max-words 1200   # read a section (use --part for long ones)
ai-book2video validate chapter.script.json             # check the script and the sentence pairs
ai-book2video preview chapter.script.json -o preview   # three frames per scene
ai-book2video build chapter.script.json -o sample.mp4 --scenes 1,14,30 --sfx  # a short sample first
ai-book2video build chapter.script.json -o chapter.mp4 --sfx                   # the full render (Kokoro voice by default)
ai-book2video check chapter.mp4                        # measure the finished film: motion, frozen stretches, jumps, sound
ai-book2video analyze-ref reference.mp4                # measure a reference video or picture to copy its style
```

Before you start, read `LESSONS.md` in this skill's folder: what has worked and what went wrong, with evidence.

## Workflow for one chapter

1. **Input.** The tool reads `.md` and `.txt` only. If the book is a PDF, EPUB or DOCX, ask for (or make, with the user's agreement) a Markdown version first.
2. **Find the chapter.** `ingest`, then `outline`. Chapters are found by headings, then by chapter lines, then by size. Tell the user which section you will use.
3. **Read closely.** Read the whole chapter with `section`, part by part. Note every event, date, number, person and argument, and where it comes from.
4. **Think about it.** Decide what the chapter is really about. Find a hook for the first few seconds (a striking contrast or question), the main beats, and one to three moments of reflection. Mark reflections clearly as yours ("Think about it", "Here is the idea worth keeping"), not as the author's claims.
5. **Write the script** (format below), about 25–45 scenes and 5–9 minutes for a full chapter. A first draft usually runs long; cut side stories and merge similar scenes rather than speed up:
   - The first scene has an original, catchy `heading` as the video title. Do not put the book title or chapter number on screen.
   - Most scenes are `stage` scenes: pick a background, place actors, give them actions and faces, and time the key moments to the narration with `"at": "s2"`.
   - English `narration` and Chinese `narration_zh`, with the same number of sentences. Avoid abbreviations with full stops ("Thomas Ricks", not "Thomas E. Ricks").
   - The last scene is a `title` credit: `"heading": "Based on"`, with the book title and author in `body`, and a one-sentence narration saying the video is based on it.
6. **Validate.** Fix every error. A sentence-count mismatch means a narration and its translation do not pair.
7. **Preview and look.** Run `preview` and read the frames. Check: labels do not overlap (keep actors at least 400 apart on the 0–1920 scale, use short labels), bursts sit above heads (`y` about 500–700), speech bubbles stay in the frame, nothing important is hidden by the caption box at the bottom.
8. **Sample before the full render.** Render two or three scenes with `--scenes`: the opening hook, the busiest action scene and one quiet scene. Look at frames, and ask the user to watch and listen when the look or the sound is new. Fix what is wrong in the script, then render everything. A full chapter takes minutes; a sample takes about one, so mistakes are cheap to find here.
9. **Build** in the background (run the build command itself as the background job; do not add a second `&`) (scenes render in parallel with `--jobs`; a full chapter takes about 5 minutes on 32 cores, longer on smaller machines) and check the result: duration, `manifest.json`, and a few frames taken with `ffmpeg -ss <t> -i out.mp4 -frames:v 1 frame.jpg` around the timed moments.
10. **Check with numbers.** Run `check` on the MP4. Fix every red item (a scene that hardly moves, a jump, blank frames, a silent scene) and look at the yellow ones at normal speed.
11. **Independent review.** If you can start a separate agent, give it only the finished video (or frames from every scene), the script and the chapter notes, and ask it to check facts, names, dates and numbers, whether each picture shows what the narration says, labels and text, and anything that looks broken. If you cannot, review it yourself as a stranger would, against the same list. Camera rhythm cannot be judged from still frames: ask the user to watch at normal speed.
12. **Deliver.** Report the length, number of scenes and file paths. If the user keeps books in one folder per book, put the MP4 and SRT next to the book.

## Script format

```json
{
  "title": "Two Men Named Winston",
  "language": "en",
  "scenes": [
    {
      "kind": "stage",
      "heading": "Two Men Named Winston",
      "narration": "A car in New York. A bullet in Spain. Two accidents nearly erased two men from history.",
      "narration_zh": "纽约的一辆车。西班牙的一颗子弹。两次意外，差点把两个人从历史里抹去。",
      "stage": {
        "background": "street",
        "split": true,
        "actors": [
          {"label": "Churchill", "x": 520, "action": "stand", "faces": [{"at": "s1+0.4", "face": "surprised"}]},
          {"label": "Orwell", "x": 1400, "action": "stand", "faces": [{"at": "s2+0.4", "face": "surprised"}]}
        ],
        "props": [{"type": "burst", "x": 520, "y": 520, "at": "s1+0.3", "text": "SCREECH!"}]
      }
    }
  ]
}
```

- **Actions:** `stand`, `walk` (`to`, `at`, `dur`), `fall` (`at`; the face turns `hurt`), `talk` (arm and mouth move), `wave`.
- **Faces:** `neutral`, `happy`, `sad`, `surprised`, `hurt`, changed over time with `faces`.
- **Speech bubbles:** `"say": [{"text": "I'm alive!", "at": "s3", "dur": 2.5}]`. Keep them to a few words.
- **Props:** `car` and `train` (move with `to`, `at`, `dur`; `"armoured": true` makes a grey train), `tree`, `sun`, `fire`, `building` (`w`, `h`), `podium`, `book`, `burst` (`text`, `at`, `dur`), `letter` (floats at `y`, can fly with `to`), `clock` (hands turn `spin` times over `dur` from `at`), `wall` (`w`, `h`), `crate` (`text` label), `chair`, `easel`.
- **Backgrounds:** `street`, `field`, `room`, `plain`, `night` (dark sky, stars and moon); `"split": true` adds two colour blocks.
- **Colours:** scenes take the built-in colour sets in turn. A top-level `"palettes": [{"bg": "#fff3d6", "accent": "#7c3aed", "card": "#1b1b3a"}, ...]` replaces them (text colours are worked out for contrast; add `ink` and `card_ink` to choose them). Use it to give a book its own look, or to follow a reference.
- **Sound:** with `--sfx`, things make a sound when they happen. Bursts choose by their word (BANG hits, FAIL droops, BRAVO chimes, `?` asks). Falls thud, trains whistle and chug, cars rumble past, letters swish, clocks tick, walkers step, bubbles pop, and each scene whooshes into the next. Any prop or actor can set `"sfx"` to `impact`, `chime`, `sad`, `question`, `pop` or `none`.
- **Timing:** seconds; `"s2"` / `"s2+0.5"` / `"s3-1"` for a sentence start plus an offset; or `"w:knife"` for the moment the narrator says a word (`"w:knife#2"` the second time, `"w:knife-0.3"` a little before). Prefer word cues for anything that should land on a word: with Kokoro they come from the voice's own word timings, so they are exact. A cue matches the start of a word, so `w:ten` finds "ten-year-old". `validate` rejects words the narration does not say. To make a moving car hit someone exactly on a sentence, start it about half its travel time earlier (`"at": "s2-1.2"` with `"dur": 2.4`).
- **Camera:** on by default. `"camera": "classic"` (the default) moves to the next framing on every sentence, wide → medium → close, with a slow push. `"camera": "director"` (top level, per stage, or `--camera director`) chooses the move for what each sentence shows: it opens wide, holds while something moves across the stage, eases toward a speaker, pushes in fast only on an impact or a fall, answers a push in with a pull or a glide, and never pushes in three times in a row. `"camera": false` on a stage keeps it still.
- **Something must happen in every stage scene:** an action, speech, a face change, a burst or movement. `validate` warns about scenes where nothing does; they look like slides.
- Other kinds (`title`, `text`, `bullets`, `quote`, `stat`) exist for credits and key points; use them sparingly.

## Matching a reference style

When the user shows a video or picture whose style they like:

1. Run `ai-book2video analyze-ref reference.mp4`. It reports the pacing (cuts, shot lengths, cuts a minute), the look (dominant colours, brightness, saturation), how much moves inside shots, and a starter `palettes` list, and saves a contact sheet with one frame per shot.
2. Read `reference.md` and look at the contact sheet. Decide what to take: colours (paste and adjust the palettes), backgrounds and props that match its world, pacing (long shots mean longer, calmer sentences and fewer actions; fast cuts mean short sentences and an action on most of them), and how busy each scene should be.
3. Say plainly what can and cannot be matched. The stage draws stick figures in SVG; a reference with photos, 3D or hand-painted art can lend its colours, pacing and energy, not its drawing.
4. Render one sample scene and put a frame of it next to the contact sheet before writing the rest.

## Sound effects

All effects are synthesised in code from tones and filtered noise (`sfx.py`), so there are no sound files to download or license. Each effect has a fixed level set against the narration: short hits sit just under the voice, continuous sounds (chugging, steps, ticks) well below it. `--sfx-volume` scales them all.

You cannot hear the result, so check it in other ways: compare loudness with `ffmpeg -i out.mp4 -af volumedetect -f null -`, draw the waveform with `showwavespic`, and, if a speech recogniser is installed, transcribe the mix to confirm every word of the narration still comes through. Then ask the user to listen and name the second where something sounds wrong, and fix that prop's `"sfx"` or `at`.

## Content rules

- **Be faithful.** Every fact must come from the chapter. When unsure, say less.
- **Copyright.** Summarise in your own words. At most one short quotation per video, under 15 words, attributed. Never reproduce passages. Name the source in the closing credit scene. Do not use the book's cover or illustrations.
- **Real people.** Show real people only as labelled stick figures, never as likenesses.
- **One idea per scene.** If a narration needs two ideas, split the scene.
- **No unrequested additions.** Do not add story jokes, characters or running gags the user did not ask for; show them in a sample and wait for a yes.

## Limits

- Rendering is about 3 seconds of compute per second of video (headless Chrome captures every frame); `--jobs` renders several scenes at once.
- The finished film is brought to -16 LUFS (`--loudness`, 0 to leave it as it is). Files are about 45 MB per minute; compress a copy (for example `-crf 28 -vf scale=720:-2`) before sending it to a phone.
- The stage has a fixed set of backgrounds, actions, faces and props; new kinds need code in `svgstage.py`.
- No background music yet. Sound effects are simple synthesised ones and are off unless `--sfx` is given.
