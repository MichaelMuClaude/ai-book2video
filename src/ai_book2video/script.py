"""The scene script: what each slide shows and what the narrator says.

A script is written by hand (or by Claude) as JSON:

    {
      "title": "How ai-paint works",
      "scenes": [
        {"kind": "title", "heading": "How ai-paint works", "body": "A two-minute tour",
         "narration": "This video explains ..."},
        {"kind": "bullets", "heading": "Three parts", "items": ["...", "..."],
         "narration": "..."},
        {"kind": "text", "heading": "...", "body": "...", "narration": "..."},
        {"kind": "quote", "body": "...", "source": "Chapter 2", "narration": "..."}
      ]
    }

The slide carries a few short words. The narration carries the explanation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ai_book2video.errors import Book2VideoError
from ai_book2video.text import count_words

WORD_CUE = re.compile(r"^w:(?P<word>[^#+\-]+?)(?:#(?P<nth>\d+))?(?P<offset>[+-][0-9.]+)?$")

KINDS = ("title", "text", "bullets", "quote", "stat", "stage")
PROPS = ("car", "train", "tree", "sun", "fire", "building", "podium", "book", "burst", "letter", "clock", "wall", "crate", "chair", "easel")
BACKGROUNDS = ("street", "field", "room", "plain", "night")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
PALETTE_KEYS = ("bg", "accent", "card")  # required; "ink" and "card_ink" are worked out for contrast when missing
WORDS_PER_MINUTE = 150
MAX_NARRATION_WORDS = 220
WARN_NARRATION_WORDS = 170
MAX_BODY_WORDS = 70
MAX_BULLETS = 6
MAX_BULLET_WORDS = 18


@dataclass
class Scene:
    index: int
    kind: str
    narration: str
    heading: str = ""
    body: str = ""
    items: list[str] = field(default_factory=list)
    source: str = ""
    id: str = ""
    value: float | None = None
    prefix: str = ""
    suffix: str = ""
    subtitle: str = ""
    stage: dict | None = None
    narration_zh: str = ""

    @property
    def narration_words(self) -> int:
        return count_words(self.narration)

    @property
    def seconds_estimate(self) -> float:
        return self.narration_words / WORDS_PER_MINUTE * 60


@dataclass
class Script:
    title: str
    scenes: list[Scene]
    language: str = "en"
    subtitle: str = ""
    warnings: list[str] = field(default_factory=list)
    book: str = ""
    chapter: str = ""
    palettes: list[dict] = field(default_factory=list)
    camera: str = "director"
    music: str = ""

    @property
    def seconds_estimate(self) -> float:
        return sum(scene.seconds_estimate for scene in self.scenes)


def _words(text: str) -> int:
    return count_words(text)


def _times(scene: dict) -> list:
    """Every "at" value in a stage: actors, their faces and speech, and props."""
    stage = scene.get("stage") if isinstance(scene.get("stage"), dict) else {}
    found = []
    for item in list(stage.get("actors", [])) + list(stage.get("props", [])):
        if not isinstance(item, dict):
            continue
        found.append(item.get("at"))
        for key in ("faces", "say"):
            found += [entry.get("at") for entry in item.get(key, []) if isinstance(entry, dict)]
    return [at for at in found if at is not None]


def check(raw: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a raw script dict."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(raw, dict):
        return ["the script must be a JSON object"], []
    if not str(raw.get("title", "")).strip():
        errors.append("missing top-level 'title'")
    if raw.get("camera", "director") not in ("classic", "director"):
        errors.append("top-level 'camera' must be classic or director")
    if raw.get("music") not in (None, "", "none", "calm", "reflective", "tense"):
        errors.append("top-level 'music' must be calm, reflective, tense or none")
    palettes = raw.get("palettes")
    if palettes is not None:
        if not isinstance(palettes, list) or not palettes:
            errors.append("'palettes' must be a non-empty list of colour sets")
        else:
            for number, palette in enumerate(palettes, start=1):
                if not isinstance(palette, dict):
                    errors.append(f"palette {number}: must be an object")
                    continue
                for key in PALETTE_KEYS:
                    if not HEX.match(str(palette.get(key, ""))):
                        errors.append(f"palette {number}: '{key}' must be a colour like #1b1b3a")
                for key in ("ink", "card_ink"):
                    if key in palette and not HEX.match(str(palette[key])):
                        errors.append(f"palette {number}: '{key}' must be a colour like #ffffff")
    scenes = raw.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        errors.append("'scenes' must be a non-empty list")
        return errors, warnings
    seen: set[str] = set()
    for number, scene in enumerate(scenes, start=1):
        where = f"scene {number}"
        if not isinstance(scene, dict):
            errors.append(f"{where}: must be an object")
            continue
        kind = scene.get("kind")
        if kind not in KINDS:
            errors.append(f"{where}: kind must be one of {', '.join(KINDS)}")
            continue
        scene_id = str(scene.get("id", "")).strip()
        if scene_id:
            if scene_id in seen:
                errors.append(f"{where}: duplicate id {scene_id!r}")
            seen.add(scene_id)
        narration = str(scene.get("narration", "")).strip()
        if not narration:
            errors.append(f"{where}: 'narration' is required")
        else:
            words = _words(narration)
            if words > MAX_NARRATION_WORDS:
                errors.append(f"{where}: narration has {words} words (limit {MAX_NARRATION_WORDS}); split the scene")
            elif words > WARN_NARRATION_WORDS:
                warnings.append(f"{where}: narration is long ({words} words, about {words / WORDS_PER_MINUTE * 60:.0f} s)")
        if kind in ("title", "text", "bullets") and not str(scene.get("heading", "")).strip():
            errors.append(f"{where}: '{kind}' scenes need a 'heading'")
        if kind == "text" and not str(scene.get("body", "")).strip():
            errors.append(f"{where}: 'text' scenes need a 'body'")
        if kind == "quote" and not str(scene.get("body", "")).strip():
            errors.append(f"{where}: 'quote' scenes need a 'body'")
        zh = str(scene.get("narration_zh", "")).strip()
        if zh and narration:
            from ai_book2video.subtitles import sentences as split_sentences

            en_count = len(split_sentences(narration))
            zh_count = len(split_sentences(zh))
            if en_count != zh_count:
                errors.append(f"{where}: narration_zh has {zh_count} sentences but narration has {en_count}; they must pair one to one")
        elif narration and not zh:
            warnings.append(f"{where}: no 'narration_zh'; the subtitle will be English only")
        for at in _times(scene):
            text = str(at).strip().lower()
            if isinstance(at, str) and text.startswith("w:"):
                match = WORD_CUE.match(text)
                if not match:
                    errors.append(f"{where}: word cue {at!r} should look like w:word, w:word#2 or w:word+0.3")
                    continue
                key = re.sub(r"[^0-9a-z]", "", match["word"])
                count = sum(1 for token in narration.split() if re.sub(r"[^0-9a-z]", "", token.lower()).startswith(key))
                if count < int(match["nth"] or 1):
                    errors.append(f"{where}: word cue {at!r}: the narration says {match['word']!r} {count} time(s)")
        if kind == "stage":
            stage = scene.get("stage")
            if not isinstance(stage, dict):
                errors.append(f"{where}: 'stage' scenes need a 'stage' object (background, actors, props)")
            else:
                actors = [a for a in stage.get("actors", []) if isinstance(a, dict)]
                props = [p for p in stage.get("props", []) if isinstance(p, dict)]
                lively = (any(a.get("action", "stand") != "stand" or a.get("say") or a.get("faces") for a in actors)
                          or any(p.get("type") == "burst" or p.get("to") is not None or p.get("type") == "clock" for p in props))
                if not lively:
                    warnings.append(f"{where}: nothing happens on stage (no action, speech, face change, burst or movement); "
                                    "it will look like a slide, so give someone something to do")
                for actor in stage.get("actors", []):
                    if not isinstance(actor, dict) or actor.get("action", "stand") not in ("stand", "walk", "fall", "talk", "wave"):
                        errors.append(f"{where}: actor action must be stand, walk, fall, talk or wave")
                for prop in stage.get("props", []):
                    if not isinstance(prop, dict) or prop.get("type") not in PROPS:
                        errors.append(f"{where}: prop type must be one of {', '.join(PROPS)}")
                if stage.get("background", "plain") not in BACKGROUNDS:
                    errors.append(f"{where}: background must be one of {', '.join(BACKGROUNDS)}")
        if kind == "stat":
            if not isinstance(scene.get("value"), (int, float)) or isinstance(scene.get("value"), bool):
                errors.append(f"{where}: 'stat' scenes need a numeric 'value' taken from the source")
            if not str(scene.get("heading", scene.get("body", ""))).strip():
                errors.append(f"{where}: 'stat' scenes need a 'heading' or 'body' label")
        if kind == "bullets":
            items = scene.get("items")
            if not isinstance(items, list) or not items:
                errors.append(f"{where}: 'bullets' scenes need a non-empty 'items' list")
            else:
                if len(items) > MAX_BULLETS:
                    warnings.append(f"{where}: {len(items)} bullets; more than {MAX_BULLETS} is hard to read on a slide")
                for item in items:
                    if _words(str(item)) > MAX_BULLET_WORDS:
                        warnings.append(f"{where}: bullet has more than {MAX_BULLET_WORDS} words: {str(item)[:50]!r}")
        if kind in ("text", "quote") and _words(str(scene.get("body", ""))) > MAX_BODY_WORDS:
            warnings.append(f"{where}: slide text has more than {MAX_BODY_WORDS} words; move detail into the narration")
    return errors, warnings


def load(path: Path) -> Script:
    """Read and validate a script file. Raises Book2VideoError with every problem found."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise Book2VideoError(f"script not found: {path}") from error
    except json.JSONDecodeError as error:
        raise Book2VideoError(f"{path} is not valid JSON: {error}") from error
    errors, warnings = check(raw)
    if errors:
        raise Book2VideoError("script has problems:\n  - " + "\n  - ".join(errors))
    scenes = []
    for index, item in enumerate(raw["scenes"], start=1):
        scenes.append(
            Scene(
                index=index,
                kind=item["kind"],
                narration=re.sub(r"\s+", " ", str(item["narration"])).strip(),
                heading=str(item.get("heading", "")).strip(),
                body=str(item.get("body", "")).strip(),
                items=[str(entry).strip() for entry in item.get("items", [])],
                source=str(item.get("source", "")).strip(),
                id=str(item.get("id", f"scene{index:02d}")).strip(),
                value=float(item["value"]) if item.get("value") is not None else None,
                subtitle=str(item.get("subtitle", "")).strip(),
                narration_zh=re.sub(r"\s+", " ", str(item.get("narration_zh", ""))).strip(),
                stage=item.get("stage") if isinstance(item.get("stage"), dict) else None,
                prefix=str(item.get("prefix", "")),
                suffix=str(item.get("suffix", "")),
            )
        )
    return Script(
        title=str(raw["title"]).strip(),
        scenes=scenes,
        language=str(raw.get("language", "en")),
        subtitle=str(raw.get("subtitle", "")).strip(),
        warnings=warnings,
        book=str(raw.get("book", "")).strip(),
        chapter=str(raw.get("chapter", "")).strip(),
        palettes=[dict(palette) for palette in raw.get("palettes") or []],
        camera=str(raw.get("camera", "director")),
        music="" if raw.get("music") in (None, "none") else str(raw.get("music")),
    )
