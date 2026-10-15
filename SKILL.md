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
ai-book2video build chapter.script.json -o chapter.mp4 # render (Kokoro voice by default)
```

## Workflow for one chapter

1. **Input.** The tool reads `.md` and `.txt` only. If the book is a PDF, EPUB or DOCX, ask for (or make, with the user's agreement) a Markdown version first.
2. **Find the chapter.** `ingest`, then `outline`. Chapters are found by headings, then by chapter lines, then by size. Tell the user which section you will use.
3. **Read closely.** Read the whole chapter with `section`, part by part. Note every event, date, number, person and argument, and where it comes from.
4. **Think about it.** Decide what the chapter is really about. Find a hook for the first few seconds (a striking contrast or question), the main beats, and one to three moments of reflection. Mark reflections clearly as yours ("Think about it", "Here is the idea worth keeping"), not as the author's claims.
5. **Write the script** (format below), about 20–26 scenes and 5–6 minutes for a full chapter:
   - The first scene has an original, catchy `heading` as the video title. Do not put the book title or chapter number on screen.
   - Most scenes are `stage` scenes: pick a background, place actors, give them actions and faces, and time the key moments to the narration with `"at": "s2"`.
   - English `narration` and Chinese `narration_zh`, with the same number of sentences. Avoid abbreviations with full stops ("Thomas Ricks", not "Thomas E. Ricks").
   - The last scene is a `title` credit: `"heading": "Based on"`, with the book title and author in `body`, and a one-sentence narration saying the video is based on it.
6. **Validate.** Fix every error. A sentence-count mismatch means a narration and its translation do not pair.
7. **Preview and look.** Run `preview` and read the frames. Check: labels do not overlap (keep actors at least 400 apart on the 0–1920 scale, use short labels), bursts sit above heads (`y` about 500–700), speech bubbles stay in the frame, nothing important is hidden by the caption box at the bottom.
8. **Build** in the background (a full chapter takes about 15 minutes) and check the result: duration, `manifest.json`, and a few frames taken with `ffmpeg -ss <t> -i out.mp4 -frames:v 1 frame.jpg` around the timed moments.
9. **Deliver.** Report the length, number of scenes and file paths. If the user keeps books in one folder per book, put the MP4 and SRT next to the book.

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

- **Backgrounds:** `street`, `field`, `room`, `plain`; `"split": true` adds two colour blocks.
- **Actions:** `stand`, `walk` (`to`, `at`, `dur`), `fall` (`at`; the face turns `hurt`), `talk` (arm and mouth move), `wave`.
- **Faces:** `neutral`, `happy`, `sad`, `surprised`, `hurt`, changed over time with `faces`.
- **Speech bubbles:** `"say": [{"text": "I'm alive!", "at": "s3", "dur": 2.5}]`. Keep them to a few words.
- **Props:** `car` (moves with `to`, `at`, `dur`), `tree`, `sun`, `fire`, `building` (`w`, `h`), `podium`, `book`, `burst` (`text`, `at`, `dur`).
- **Timing:** seconds, or `"s2"` / `"s2+0.5"` / `"s3-1"` for a sentence start plus an offset. To make a moving car hit someone exactly on a sentence, start it about half its travel time earlier (`"at": "s2-1.2"` with `"dur": 2.4`).
- **Camera:** on by default; every sentence is a new shot. Set `"camera": false` on a stage for a still scene.
- Other kinds (`title`, `text`, `bullets`, `quote`, `stat`) exist for credits and key points; use them sparingly.

## Content rules

- **Be faithful.** Every fact must come from the chapter. When unsure, say less.
- **Copyright.** Summarise in your own words. At most one short quotation per video, under 15 words, attributed. Never reproduce passages. Name the source in the closing credit scene. Do not use the book's cover or illustrations.
- **Real people.** Show real people only as labelled stick figures, never as likenesses.
- **One idea per scene.** If a narration needs two ideas, split the scene.

## Limits

- Rendering is about 3 seconds of compute per second of video (headless Chrome captures every frame).
- Files are about 45 MB per minute; compress a copy (for example `-crf 28 -vf scale=720:-2`) before sending it to a phone.
- The stage has a fixed set of backgrounds, actions, faces and props; new kinds need code in `svgstage.py`.
- No background music or sound effects yet.
