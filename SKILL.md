---
name: ai-book2video
description: Turn a Markdown or plain-text document into a fun, animated, ad-style narrated MP4 video with bold motion graphics, a voice and subtitles. Use this whenever someone wants a video or narrated summary of a Markdown document, a book chapter that is already in Markdown, documentation, notes or a report, a "make this into a video" request for such a file, or an MP4 with narration and subtitles from written material, even if they never say "video" together with the document.
compatibility: Written for Claude Code. Needs Python 3.10+, Node.js 22+, ffmpeg with libx264, espeak-ng for narration, and Chrome or Chromium for frame capture. Input must be Markdown (.md) or plain text (.txt); convert other formats first.
---

# ai-book2video

This skill turns written material into a narrated video. You (Claude) read the document, write a scene script, and the `ai-book2video` tool renders the animated scenes, the narration, the MP4 and an SRT subtitle file.

The tool does the mechanical parts. You do the reading, the summary and the script. Do not hand the whole book to the tool as one block of text: a good video is a set of short scenes, each with one idea.

## The commands

```bash
ai-book2video doctor                         # check the tools
ai-book2video ingest book.md -o book.json    # split a Markdown or text file into sections
ai-book2video outline book.json              # list the section ids and their length
ai-book2video section book.json s03          # read one section (add --part 2 for a long one)
ai-book2video validate script.json           # check the scene script before rendering
ai-book2video preview script.json -o preview # render key frames per scene to review the motion
ai-book2video build script.json -o out.mp4   # render the narrated MP4 and out.srt
ai-book2video build script.json -o out.mp4 --scenes 1-3   # preview a few scenes first
```

## Workflow

0. **Input.** The tool reads `.md`, `.markdown` and `.txt` only. If the user has a PDF, EPUB or DOCX, ask them to convert it to Markdown first (or convert it yourself with a tool they agree to) before ingesting.
1. **Ingest and outline.** Run `ingest`, then `outline`. Tell the user how many sections and words there are, and ask which part they want if the book is long. Make a short plan: how many scenes (about 8–15 for a 2–4 minute video), and which idea each scene carries.
2. **Read the sections you need.** Use `section` to read them. For a long section, read it in parts with `--part`. Keep notes in your own words.
3. **Write the scene script** as JSON (see the format below). Write it to a file in the working folder, not in the chat.
4. **Validate.** Run `validate` and fix every error. Read the warnings; a long narration or a crowded scene is usually worth shortening.
5. **Preview.** Run `preview` and look at a few frames, or `build --scenes 1-3` and check the first clip. Check the title scene and one bullet scene especially.
6. **Build the full video.** Run `build`. Report the length, the number of scenes, the voice used and the output paths (MP4 and SRT).

## Scene script format

```json
{
  "title": "How ai-paint works",
  "subtitle": "optional line under the title",
  "language": "en",
  "scenes": [
    {"kind": "title", "heading": "How ai-paint works", "body": "A two-minute tour", "narration": "..."},
    {"kind": "text", "heading": "A picture is a JSON document", "body": "Short on-screen text.", "narration": "..."},
    {"kind": "bullets", "heading": "Three rules", "items": ["one", "two", "three"], "narration": "..."},
    {"kind": "quote", "body": "A short quotation.", "source": "Chapter 2, p. 14", "narration": "..."}
  ]
}
```

- `kind` is one of `title`, `text`, `bullets`, `quote`, `stat`.
- `stat` shows one number from the source, counted up on screen: `{"kind": "stat", "value": 2, "suffix": " near-death accidents", "heading": "Both men lived", ...}`. Use only numbers stated in the source.
- `narration` is required in every scene. It is what the voice says, so write full sentences that explain the idea. The limit is 220 words per scene; aim for 60–150.
- Each scene is an animated page: words pop in, bullets slide in, numbers count up, colours change between scenes. Keep on-screen text short (a heading, a short body or up to six bullets); put the detail in the narration. A warning appears if a scene has more than 70 words of text.
- The style is bold and playful, like an explainer ad, not a presentation. Do not write the script like slides.
- `id` is optional and must be unique if given.

## Rules for the content

- **Be faithful.** Every claim in the narration must come from the source. If the source is unclear, say less rather than guess.
- **Copyright.** Books are copyrighted. Explain the ideas in your own words and name the source. Quote at most one short passage per video, under 15 words, with attribution. Never reproduce a long passage of the book. Summaries must be clearly shorter than and different from the source.
- **One idea per scene.** If a narration needs two ideas, split the scene.
- **Name the source** in the title scene or a quote scene when the video is about a specific book or document.

## Narration voice

The default narration uses espeak-ng. It is intelligible but sounds robotic, and it works well for English. For Chinese, pass `--voice cmn`, but the quality is poor; a better engine is needed. For another engine, use `--tts command` with `--tts-command 'mytts --text {text} --out {out}'`. The command receives a text file and must write a WAV file to `{out}`.

Tell the user about the voice before the final build, and ask whether they want a different one, because a better voice usually needs a separate account or local model.

## Limits

- The animations are built-in templates (title, text, bullets, quote, stat). There are no custom diagrams or images from the book yet.
- Frames are rendered with headless Chrome, about one to two seconds of compute per second of video.
- Long documents are split by headings, chapter lines or size. The split may not match the book's own structure; check the `outline`.
- Narration speed is about 150–165 words per minute. A 2-minute video is about 300 words of narration.
- The renderer needs Chrome, Node.js 22+ and fonts that cover the script. CJK text needs a CJK font, which this machine has.
