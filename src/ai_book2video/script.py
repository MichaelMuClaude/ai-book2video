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

KINDS = ("title", "text", "bullets", "quote", "stat", "stage")
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

    @property
    def seconds_estimate(self) -> float:
        return sum(scene.seconds_estimate for scene in self.scenes)


def _words(text: str) -> int:
    return count_words(text)


def check(raw: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a raw script dict."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(raw, dict):
        return ["the script must be a JSON object"], []
    if not str(raw.get("title", "")).strip():
        errors.append("missing top-level 'title'")
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
        if kind == "stage":
            stage = scene.get("stage")
            if not isinstance(stage, dict):
                errors.append(f"{where}: 'stage' scenes need a 'stage' object (background, actors, props)")
            else:
                for actor in stage.get("actors", []):
                    if not isinstance(actor, dict) or actor.get("action", "stand") not in ("stand", "walk", "fall", "talk", "wave"):
                        errors.append(f"{where}: actor action must be stand, walk, fall, talk or wave")
                for prop in stage.get("props", []):
                    if not isinstance(prop, dict) or prop.get("type") not in ("car", "tree", "sun", "fire", "building", "podium", "book"):
                        errors.append(f"{where}: prop type must be car, tree, sun, fire, building, podium or book")
                if stage.get("background", "plain") not in ("street", "field", "room", "plain"):
                    errors.append(f"{where}: background must be street, field, room or plain")
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
    )
