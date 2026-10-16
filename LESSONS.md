# Lessons

What has proven to work in making chapter videos with this tool, and what has gone wrong. Each entry
says what to do, the evidence, and when it applies. When a later project confirms an entry, add to
its evidence; when one fails, write down where it stopped holding.

The habit of keeping this file, and several entries below, come from
[huashu-art-motion](https://github.com/alchaincyf/huashu-art-motion) by 花叔 (MIT) and
[chengfeng-video-styles](https://github.com/Agentchengfeng/chengfeng-video-styles) by 成峰.

**On Remotion.** It was considered as the rendering engine (it is, under the hood, the same thing
we built by hand: React components rendered deterministically from a frame number through headless
Chrome, then encoded with ffmpeg). Decided against adopting it:
- its own render model (`useCurrentFrame`/`interpolate` instead of CSS transitions) is the same
  "state is a pure function of time" rule our `Timeline.apply(t)` already follows; switching would
  not fix anything broken, only rewrite a tested engine in a different syntax.
- it is source-available, not OSI open source. The free tier covers individuals, for-profit
  organisations of up to 3 people, non-profits and evaluation; anyone outside that needs a paid
  Company License. Making it a dependency of an MIT project would mean every downstream user has to
  separately qualify for Remotion's own terms, which this project does not ask of anyone today.
- two of its ideas were worth taking on their own, without the dependency: see entries 18 and 19.

## Timing

**1. Time actions to words, not to guessed seconds.** Write `"at": "w:knife"` (or `"s2"` for a
sentence start) and let the tool turn it into a time.
- Evidence: subtitle and sentence times used to be shared out by word count. Against Whisper's word
  timestamps on real Kokoro narration, those estimates were up to 0.97 s early; the times now taken
  from Kokoro's own word timings agree with Whisper within 0.1 s.
- Applies: always with Kokoro. With espeak there are no word timings and the estimate is used.

**2. Avoid abbreviations with full stops in the narration** ("Thomas Ricks", not "Thomas E. Ricks").
- Evidence: the sentence splitter cut "E." into its own sentence and the Chinese pairing broke.

## Picture and camera

**3. Every stage scene needs something happening.** An action, a line of speech, a face change, a
burst or something moving. `validate` warns when a scene has none.
- Evidence: `check` on a finished 43-scene chapter flagged exactly the three scenes where one figure
  stood beside still props (under 0.5% of the picture moving); all others moved 1.7–5.5%.

**4. Do not repeat one camera move on every sentence.** Hold still when the picture itself moves; use
slow moves (push, glide, pull) to carry the eye; keep the fast push for an accent (an impact, a
fall); answer a push in with a pull or a glide; never three pushes in a row; no endless creeping zoom.
This is `"camera": "director"`.
- Evidence: huashu-art-motion's notes record that "every shot slowly pushes in" and "every narration
  beat gets a fast push" were both judged as slideshow-like; what was accepted mixed holds, pulls and
  glides with a few fast pushes on accents. In our 88 s comparison both cameras make 10 framing moves,
  but the director lands its 4 fast pushes on the stab, the BANG and the empty holster, and holds
  while the train crosses.
- Applies: explainer and story scenes. Judge camera rhythm at normal speed; still frames cannot show it.

**5. Long words in a burst need a label behind them.** The star's points pull in between its tips.
- Evidence: "UNSOLD" and "CHANCELLOR" spilled onto dark backgrounds until a yellow label was added.

**6. Speech bubbles on walkers flip by where the walker is when they speak**, not where they start.
- Evidence: a bubble said at the end of a walk to the right edge was cut off by the frame.

**7. The last preview frame of a scene can catch the camera mid-move.** A cropped frame there is a
transition, not a bug. Do not "fix" it with `"camera": false`, which freezes the whole scene on a
cropped shot.

## Sound

**8. Make sound effects in code and give each its own level.** Short hits sit just under the voice,
continuous sounds (chugging, steps, ticks) far below it.
- Evidence: with one shared level, effects peaked at about -7 dB, as loud as the narration. With
  per-effect levels they peak at -10 dB with an average near -36 dB; transcribing the mixed demo
  with Whisper matched 96.9% of the script's words, the misses being spellings such as "10-year-old".

**9. Bring the finished film to about -16 LUFS.**
- Evidence: `check` found the published chapters at -25 LUFS, far quieter than other videos on a
  phone. The build now normalises the loudness of the whole film in one measured step.

**10. You cannot hear the result, so measure it and then ask.** Compare loudness, draw the waveform,
transcribe the mix, then ask the user to listen and name the second that sounds wrong.

**18. Drive a mouth, or any repeating visual, from the real amplitude of the rendered audio,
not a fixed loop.**
- Evidence: a talking actor's mouth used to flap on a constant 0.34 s metronome, open half the time
  regardless of what was being said. Reading the actual narration WAV's loudness (24 samples a
  second, smoothed) and opening the mouth in proportion made it visibly open wider on stressed
  words and close between them, confirmed on cropped frames of real Kokoro audio. Costs nothing
  extra to compute (the WAV already exists); falls back to the old flap when there is no audio yet
  (a layout preview).

**19. Highlight the word a caption is saying, from the same word timing already used for cues.**
- Evidence: burned-in subtitles showed a whole sentence with no indication of where the narration
  currently was. The word spans (built once per sentence, not every frame) and highlight add about
  70 characters of script-reading cost and were confirmed against real Kokoro audio; the bolded word
  visibly tracks the narration in a cropped-frame check.

**20. Background music: render a loop that wraps, keep it 14 dB under, duck it under the voice.**
- Evidence: a 16-bar loop renders in about 3 s in plain Python; notes that ring past the end are
  added back at the start, so the loop tiles with nothing but a note attack at the seam. In an
  88 s demo the pauses between sentences rose from -83 dB (silence) to about -30 dB, the level
  during speech changed by under 0.1 dB, and Whisper still matched 97.5% of the script's words.
- From anything2video's audio engine (MIT): one mood per kind of film, the bed well under the voice.

**21b. A wipe needs a bright edge, or it reads as a PowerPoint transition.** A flat colour panel
sliding across, with no highlight at the edge that is actually sweeping the screen, looks like a
slide deck, not an animation.
- Evidence: our own scene-to-scene wipe was exactly this (confirmed on frames of a real render: a
  flat cyan slab, hard edge, no glow). Added a line at the sweeping edge with both a dark outline
  and a white core, so it reads against a light or a dark scene either way.
- From anything2video's gallery (Apache-2.0/MIT): a wipe transitions card names this as the
  "known pitfall" for exactly this effect, and gives the two-tone (white core, dark outline)
  recipe for it.

**21. Place a sound by its sync point, not its first sample.** A hit is heard on its transient, so
put it one frame early; a whoosh is heard at its peak, so centre it on the moment the movement
crosses the frame.
- From anything2video's audio engine (MIT).

**22. A second visual style can reuse the whole skeleton, camera and script format — only the
drawing changes.** anything2video's own sand/ink/collage cards make this same choice (see entry 2);
our `collage` style is the first time we did it ourselves, for a style of our own design, not theirs.
- Evidence: `collage.py` imports svgstage's camera (`_camera`, `_director`, `_aim`), skeleton
  geometry (leg/arm swing, blink timing, `actor_x`) and constants unchanged, and only replaces how a
  figure, a prop and the background are drawn. A real chapter-2 scene rendered in both styles with
  no script changes; `check` passed both at the same loudness and similar motion.
- A `"style"` field sits at the top of the script next to `"camera"` and `"music"`: a book picks one
  style for all its chapters, not a style per scene, because the point is a consistent look across a
  video, the same reason `"camera"` and `"music"` are top-level choices too.

**23. An SVG element with `data-id` must never also carry its own `transform=` attribute — the
second time this exact bug was made and fixed in this project.** The engine writes
`el.style.transform` for every `data-id` element on every frame, including elements with no position
animation at all (the identity transform `translate(0px, 0px) rotate(0deg) scale(1) ...`), and a CSS
`transform` always overrides an SVG `transform` *attribute* on the same element, even when the CSS
value is the identity. The element silently snaps to `(0, 0)`.
- Evidence: `collage.py`'s face wrapped its eyes and mouth in `<g data-id="..." transform="translate(0 -332)">`;
  the head rendered at the origin with the photo and eyes invisible or mispositioned, confirmed on a
  cropped frame. svgstage.py had already hit and fixed the same bug once (its mouth and eye shapes
  use absolute coordinates with no wrapping transform, for exactly this reason) — the rule was not
  carried over when writing the second renderer. Fixed by baking the offset into each shape's own
  coordinates instead of a wrapping transform, and added a regression test
  (`test_collage.py::TransformAttributeRegressionTests`) that scans both renderers' output for any
  `data-id` element that also has a `transform` attribute, so a third repeat fails the test suite
  instead of a cropped frame.

## Process

**11. Render a sample before the full chapter.** Two or three scenes: the hook, the busiest scene,
a quiet one. About a minute instead of several.

**12. Measure the finished film before anyone watches it** (`check`), then have it reviewed by
someone who did not make it, looking at facts, numbers and logic as well as the picture.
- Evidence (huashu-art-motion): independent reviewers caught problems the maker missed in three
  passes of their own, including content that looked perfect but said the wrong thing.

**13. Do not add story jokes or new elements the user did not ask for.** Show them in a sample and
wait for a yes.

**14. Learn a reference by measuring it.** `analyze-ref` before copying a look; impressions of a
style are often wrong. It found our own scene boundaries to within one frame.

## Rendering

**15. Render scenes in parallel, but not flat out.** Four at once kept a 16-core desktop CPU at an
average of 73.5 °C (75.6 °C with eight) for a 9-minute chapter in under 8 minutes.

**16. GPU video encoding is not worth it here.** NVENC saved 6% of the time and made files 50%
larger; nearly all the work is the browser drawing frames.

**17. Run the build itself as the background job.** Wrapping it in a second `&` inside a background
shell loses track of the render: no completion notice, an empty log, while it keeps running.
