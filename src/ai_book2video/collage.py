"""Paper-collage stage: the same stick-figure script, drawn as torn, pasted paper.

Reuses svgstage's skeleton, camera and animation engine — "one skeleton, one choreography, many
renderings" (see LESSONS.md #2, and anything2video's own sand/ink/collage cards, which make the same
choice). Only how a figure, a prop and the background are drawn changes: paper scraps with torn,
jittered edges instead of flat crayon shapes; sepia photo-cutout heads instead of round white ones;
letters and newsprint headlines instead of colour props. Actions, faces, speech, the camera and the
script format are identical to the crayon stage, so a script can switch styles by name alone.
"""

from __future__ import annotations

import html
import math
import random

from ai_book2video.script import Scene
from ai_book2video.svgstage import (  # the parts that do not depend on the crayon look
    ACTOR_SCALE, CHEST, FACES, GROUND, HEIGHT, SCALE, WIDTH,
    _aim, _beat_events, _camera, _director, _face_timeline, _fill_box, actor_x, when,
)

INK = "#2b2016"
PAPER = ("#f3e6c8", "#ead9b3", "#e3cfa0", "#efe2c2")  # kraft/cream tones: background and props
INK_TONES = ("#2b2016", "#3a2a1a", "#241a12")
# Period clothing colours: deliberately far from the cream paper tones so a figure reads against it.
CLOTHING = ("#2e4057", "#6b2d3c", "#39513c", "#5a4a1f", "#3a3550", "#4a2f24", "#2f4a4a")
PHOTO_TONE = "#b9a179"  # a sepia photograph is visibly darker than the cream paper it is pasted on

DEFS = """
<defs>
  <filter id="paper-grain" x="-10%" y="-10%" width="120%" height="120%">
    <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="11" result="grain"/>
    <feColorMatrix in="grain" type="matrix" values="0 0 0 0 0.55  0 0 0 0 0.47  0 0 0 0 0.33  0 0 0 0.12 0" result="speck"/>
    <feComposite in="speck" in2="SourceGraphic" operator="atop"/>
  </filter>
  <filter id="paper-wobble" x="-10%" y="-10%" width="120%" height="120%">
    <feTurbulence type="fractalNoise" baseFrequency="0.045" numOctaves="2" seed="6" result="wave"/>
    <feDisplacementMap in="SourceGraphic" in2="wave" scale="4" xChannelSelector="R" yChannelSelector="G"/>
  </filter>
  <filter id="paper-shadow" x="-30%" y="-30%" width="160%" height="160%">
    <feDropShadow dx="0" dy="10" stdDeviation="10" flood-color="#000000" flood-opacity="0.28"/>
  </filter>
</defs>
"""


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _torn_rect(w: float, h: float, jag: float, seed: int, rx: float = 0.0) -> str:
    """A rectangle path whose four edges are torn: short random-length jagged segments instead of a
    straight line, seeded so the same shape renders the same way every time."""
    rng = random.Random(seed)
    x0, y0, x1, y1 = -w / 2, -h / 2, w / 2, h / 2
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    parts = [f"M{x0 + rx:.1f},{y0:.1f}"]
    for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1]):
        length = math.hypot(bx - ax, by - ay)
        steps = max(3, int(length / 26))
        for i in range(1, steps + 1):
            p = i / steps
            px, py = ax + (bx - ax) * p, ay + (by - ay) * p
            nx, ny = -(by - ay) / length, (bx - ax) / length  # outward normal of this edge
            j = (rng.uniform(0.3, 1.0) * jag) if i < steps else 0
            parts.append(f"L{px + nx * j:.1f},{py + ny * j:.1f}")
    parts.append("Z")
    return " ".join(parts)


def _scrap(x: float, y: float, w: float, h: float, colour: str, rotation: float, seed: int, jag: float = 7) -> str:
    path = _torn_rect(w, h, jag, seed)
    return (f'<g transform="translate({x:.0f} {y:.0f}) rotate({rotation:.1f})" filter="url(#paper-shadow)">'
            f'<path d="{path}" fill="{colour}" filter="url(#paper-grain)"/></g>')


def background(kind: str, palette: dict, split: bool = False) -> str:
    """A kraft-paper backdrop with two or three large torn scraps pasted onto it."""
    pad = 300
    base = PAPER[0]
    parts = [f'<rect x="{-pad}" y="{-pad}" width="{WIDTH + 2 * pad}" height="{HEIGHT + 2 * pad}" fill="{base}"/>']
    if split:
        parts.append(_scrap(WIDTH * 0.26, HEIGHT * 0.46, WIDTH * 0.62 + 100, HEIGHT * 0.86, PAPER[1], -1.1, 101, 10))
        parts.append(_scrap(WIDTH * 0.76, HEIGHT * 0.5, WIDTH * 0.58 + 100, HEIGHT * 0.92, PAPER[2], 1.4, 102, 10))
    else:
        parts.append(_scrap(WIDTH * 0.5, HEIGHT * 0.42, WIDTH * 0.92, HEIGHT * 0.7, PAPER[1], -0.8, 103, 9))
        parts.append(_scrap(WIDTH * 0.5, HEIGHT * 0.86, WIDTH * 1.05, HEIGHT * 0.42, PAPER[2], 0.5, 104, 9))
    ground_colour = {"night": "#453826", "room": "#d8c49a"}.get(kind, PAPER[3])
    parts.append(_scrap(WIDTH * 0.5, GROUND + (HEIGHT - GROUND) / 2, WIDTH + 140, (HEIGHT - GROUND) + 120,
                        ground_colour, 0, 105, 10))
    return f'<g filter="url(#paper-wobble)">{"".join(parts)}</g>'


def _tape(x: float, y: float, rotation: float, seed: int) -> str:
    rng = random.Random(seed)
    w, h = rng.uniform(60, 80), 26
    return (f'<g transform="translate({x:.0f} {y:.0f}) rotate({rotation:.1f})" opacity="0.8">'
            f'<rect x="{-w/2:.0f}" y="{-h/2:.0f}" width="{w:.0f}" height="{h:.0f}" fill="#f4efd8" opacity="0.65"/></g>')


def prop(prefix: str, index: int, spec: dict, palette: dict, tl, cues: list) -> str:
    kind = spec["type"]
    gid = f"{prefix}p{index}"
    x0 = float(spec.get("x", 0)) * SCALE
    y0 = float(spec.get("y", 0))

    from ai_book2video.svgstage import _move  # positioning/animation: identical to the crayon stage

    if kind == "burst":  # a torn newsprint headline clipping instead of a comic star
        text = str(spec.get("text", "!"))
        at = when(spec.get("at"), cues, 1.0)
        dur = float(spec.get("dur", 1.4))
        w = max(220, len(text) * 30 + 60)
        tl.start(gid, s=0, o=0, r=-2)
        tl.add(gid, "s", 1, at, 0.3, "back")
        tl.add(gid, "r", 2, at, 0.3, "back")
        tl.add(gid, "o", 1, at, 0.1)
        tl.add(gid, "o", 0, at + dur, 0.3)
        y = y0 if y0 else GROUND - 360
        path = _torn_rect(w, 130, 7, index + 50)
        return (f'<g data-id="{gid}" style="{_fill_box("50% 50%")}"><g transform="translate({x0:.0f} {y:.0f})" filter="url(#paper-shadow)">'
                f'<path d="{path}" fill="#efe6cf" filter="url(#paper-grain)"/>'
                f'<text x="0" y="12" text-anchor="middle" font-size="46" font-weight="900" fill="{INK}" '
                f'font-family="Georgia, \'Noto Serif\', serif" letter-spacing="1">{_esc(text.upper())}</text></g></g>')

    if kind == "letter":
        y = y0 if y0 else GROUND - 560
        lines = "".join(f'<line x1="-52" y1="{ly}" x2="52" y2="{ly}" stroke="{INK}" stroke-width="3" opacity="0.5"/>'
                        for ly in (-34, -12, 10, 32))
        path = _torn_rect(150, 190, 6, index + 70)
        _move(gid, x0, spec, cues, tl)
        return (f'<g data-id="{gid}"><g transform="translate(0 {y:.0f})"><g data-float="9,1.7,{index}" data-id="{gid}-f" filter="url(#paper-shadow)">'
                f'<path d="{path}" fill="#f6efd9" filter="url(#paper-grain)"/>{lines}'
                f'<circle cx="38" cy="54" r="12" fill="#8a2a1f" opacity="0.85"/></g></g></g>')  # a wax seal

    if kind == "clock":
        y = y0 if y0 else GROUND - 820
        turns = float(spec.get("spin", 1))
        at = when(spec.get("at"), cues)
        dur = float(spec.get("dur", 6))
        ticks = "".join(f'<line x1="0" y1="-74" x2="0" y2="-90" stroke="{INK}" stroke-width="5" stroke-linecap="round" transform="rotate({a})"/>'
                        for a in range(0, 360, 30))
        tl.start(f"{gid}-m", r=0)
        tl.start(f"{gid}-h", r=0)
        tl.add(f"{gid}-m", "r", 360 * turns, at, dur, "linear", frm=0)
        tl.add(f"{gid}-h", "r", 30 * turns, at, dur, "linear", frm=0)
        return (f'<g data-id="{gid}"><g transform="translate({x0:.0f} {y:.0f})" filter="url(#paper-shadow)">'
                f'<circle r="100" fill="#f0e6c9" stroke="{INK}" stroke-width="5" filter="url(#paper-grain)"/>{ticks}'
                f'<path data-id="{gid}-h" d="M0,0 L0,-46" stroke="{INK}" stroke-width="8" stroke-linecap="round" style="{_fill_box("50% 100%")}"/>'
                f'<path data-id="{gid}-m" d="M0,0 L0,-74" stroke="#8a2a1f" stroke-width="6" stroke-linecap="round" style="{_fill_box("50% 100%")}"/>'
                f'<circle r="8" fill="{INK}"/></g></g>')

    # Anything else (train, car, tree, sun, ...): a plain torn paper block, so unsupported props
    # still read as "something is here" instead of vanishing.
    w, h = float(spec.get("w", 160)), float(spec.get("h", 220))
    path = _torn_rect(w, h, 8, index + 90)
    _move(gid, x0, spec, cues, tl)
    return (f'<g data-id="{gid}"><g transform="translate(0 {GROUND - h / 2:.0f})" filter="url(#paper-shadow)">'
            f'<path d="{path}" fill="{PAPER[2]}" filter="url(#paper-grain)"/></g></g>')


def _mouths(gid: str, talking: bool) -> str:
    # Absolute coordinates (the head sits at y=-332): a data-id element must never carry its own
    # transform attribute, or the engine's per-frame CSS transform (even the identity one it writes
    # for an element with no position animation) silently replaces it — see actor()'s head comment.
    y = -332
    shapes = {
        "neutral": f'<path d="M-12,{y - 10} L12,{y - 10}" stroke="{INK}" stroke-width="4" stroke-linecap="round" fill="none"/>',
        "happy": f'<path d="M-15,{y - 14} Q0,{y + 2} 15,{y - 14}" stroke="{INK}" stroke-width="4" stroke-linecap="round" fill="none"/>',
        "sad": f'<path d="M-13,{y} Q0,{y - 16} 13,{y}" stroke="{INK}" stroke-width="4" stroke-linecap="round" fill="none"/>',
        "surprised": f'<ellipse cx="0" cy="{y - 6}" rx="7" ry="10" fill="{INK}"/>',
        "hurt": f'<path d="M-13,{y - 6} L-6,{y - 13} L0,{y - 6} L6,{y - 13} L13,{y - 6}" stroke="{INK}" stroke-width="4" stroke-linejoin="round" fill="none"/>',
    }
    parts = [f'<g data-id="{gid}-m-{name}">{shape}</g>' for name, shape in shapes.items()]
    if talking:
        parts.append(f'<g data-id="{gid}-m-talk" data-voice="1" data-flap="0.34"><ellipse cx="0" cy="{y - 7}" rx="9" ry="7" fill="{INK}"/></g>')
    return "".join(parts)


def actor(prefix: str, index: int, spec: dict, palette: dict, tl, cues: list) -> str:
    """A vintage photo cutout, pasted on torn paper, with the same skeleton as the crayon actor:
    same x/action/face/say handling, same walk/fall/talk timing, so scripts are unchanged."""
    action = spec.get("action", "stand")
    if action not in ("stand", "walk", "fall", "talk", "wave"):
        action = "stand"
    gid = f"{prefix}a{index}"
    x0 = float(spec.get("x", 0)) * SCALE
    walking = action == "walk"
    talking = action == "talk"
    waving = action == "wave"
    seed = 200 + index

    def swing(amp: int, phase: float, period: float = 1.1) -> str:
        return f' data-swing="{amp},{period},{phase}"'

    def strip(ident: str, x: float, y: float, length: float, sw: str) -> str:
        return (f'<g transform="translate({x} {y})"><path data-id="{ident}"{sw} d="M0,0 L0,{length}" '
                f'stroke="{INK_TONES[index % 3]}" stroke-width="10" stroke-linecap="round" fill="none" '
                f'style="{_fill_box("50% 0%")}"/></g>')

    legs = strip(f"{gid}-ll", -13, -130, 130, swing(26, 0) if walking else "") + \
           strip(f"{gid}-rl", 13, -130, 130, swing(26, 3.1416) if walking else "")
    arm_r = swing(22, 3.1416) if walking else swing(14, 0, 0.7) if talking else swing(18, 0, 0.6) if waving else ""
    arms = strip(f"{gid}-la", -32, -238, 96, swing(22, 0) if walking else "") + \
           strip(f"{gid}-ra", 32, -238, 96, arm_r)
    torso_path = _torn_rect(70, 150, 5, seed)
    torso = f'<g transform="translate(0 -270)" filter="url(#paper-grain)"><path d="{torso_path}" fill="{CLOTHING[index % len(CLOTHING)]}"/></g>'
    photo_path = _torn_rect(108, 108, 3, seed + 1)
    head = (
        f'<g transform="translate(0 -332)"><path d="{photo_path}" fill="#e4d2a8" filter="url(#paper-grain)"/>'
        f'<circle r="47" fill="{PHOTO_TONE}" stroke="#fdf8ea" stroke-width="7"/></g>'
        f'<g data-id="{gid}-eyes" data-blink="{3.2 + index * 0.7:.1f},{index * 1.3:.1f}" style="{_fill_box("50% 50%")}">'
        f'<ellipse cx="-16" cy="-340" rx="6" ry="8" fill="#fdf8ea"/><ellipse cx="16" cy="-340" rx="6" ry="8" fill="#fdf8ea"/></g>'
        + _mouths(gid, talking)
    )
    label = ""
    if spec.get("label"):
        tag = _torn_rect(max(90, len(spec["label"]) * 20 + 30), 48, 4, seed + 2)
        label = (f'<g transform="translate(0 -398)" filter="url(#paper-shadow)"><path d="{tag}" fill="#f6efd9" filter="url(#paper-grain)"/>'
                 f'<text x="0" y="7" text-anchor="middle" font-size="30" font-weight="700" fill="{INK}" '
                 f'font-family="Georgia, \'Noto Serif\', serif">{_esc(spec["label"])}</text></g>')
    breathe = f' data-float="3,{2.4 + index * 0.3:.1f},{index:.1f}"' if not walking else ""
    figure = f'<g data-id="{gid}-f"{breathe} style="{_fill_box("50% 100%")}">{legs}{torso}{arms}{head}{label}</g>'
    bubbles = _notes(gid, spec, cues, tl)
    tl.start(f"{gid}-ll", r=-8)
    tl.start(f"{gid}-rl", r=8)
    tl.start(f"{gid}-la", r=24)
    tl.start(f"{gid}-ra", r=-24)
    if talking or waving:
        tl.start(f"{gid}-ra", r=-150 if waving else -110)
    _face_timeline(gid, spec, cues, tl)
    tl.start(gid, x=x0)
    if walking and spec.get("to") is not None:
        tl.add(gid, "x", float(spec["to"]) * SCALE, when(spec.get("at"), cues), float(spec.get("dur", 3)), "linear", frm=x0)
    if action == "fall":
        tl.start(f"{gid}-f", r=0)
        tl.add(f"{gid}-f", "r", 92, when(spec.get("at"), cues), 0.6, "back", frm=0)
    bob = ' data-float="7,0.55,0"' if walking else ""
    return (f'<g data-id="{gid}"{bob}><g filter="url(#paper-wobble)" transform="translate(0 {GROUND}) scale({ACTOR_SCALE})">'
            f'{figure}{bubbles}</g></g>')


def _notes(gid: str, spec: dict, cues: list, tl) -> str:
    """Speech becomes a pinned note, torn paper with a strip of tape, instead of a cartoon bubble."""
    out = []
    for index, line in enumerate(spec.get("say", [])):
        text = _esc(str(line.get("text", "")))
        width = max(150, int(len(str(line.get("text", ""))) * 22 + 60))
        bid = f"{gid}-say{index}"
        at = when(line.get("at"), cues, 0.5)
        dur = float(line.get("dur", 2.5))
        tl.start(bid, o=0, s=0.6, r=-3)
        tl.add(bid, "o", 1, at, 0.15)
        tl.add(bid, "s", 1, at, 0.35, "back")
        tl.add(bid, "r", 2, at, 0.35, "back")
        tl.add(bid, "o", 0, at + dur, 0.25)
        x = max(actor_x(spec, at, cues), actor_x(spec, at + dur, cues))
        flip = x + (40 + width) * ACTOR_SCALE > WIDTH - 24
        left = -40 - width if flip else 40
        path = _torn_rect(width, 96, 4, hash((gid, index)) % 1000)
        out.append(
            f'<g data-id="{bid}" style="{_fill_box("100% 100%" if flip else "0% 100%")}">'
            f'<g transform="translate({left + width / 2} -470)" filter="url(#paper-shadow)">'
            f'<path d="{path}" fill="#f8f2dd" filter="url(#paper-grain)"/>{_tape(0, -40, 4, index + 1)}'
            f'<text x="0" y="8" text-anchor="middle" font-size="36" font-weight="700" fill="{INK}" '
            f'font-family="Georgia, \'Noto Serif\', serif">{text}</text></g></g>'
        )
    return "".join(out)


def stage(scene: Scene, palette: dict, tl, cues: list | None = None, duration: float = 6.0, camera: str = "director") -> str:
    cues = cues or []
    spec = scene.stage or {}
    parts = [background(spec.get("background", "plain"), palette, split=bool(spec.get("split", False)))]
    for index, item in enumerate(spec.get("props", [])):
        parts.append(prop("c", index, item, palette, tl, cues))
    for index, item in enumerate(spec.get("actors", [])):
        parts.append(actor("c", index, item, palette, tl, cues))
    mode = spec.get("camera", True)
    if mode is True:
        mode = camera
    if mode == "director":
        _director(spec, cues, duration, tl, scene.index)
    elif mode:
        _camera(spec, cues, duration, tl)
    camera_g = f'<g data-id="cam" style="transform-box:view-box;transform-origin:{WIDTH / 2:.0f}px {HEIGHT / 2:.0f}px;">{"".join(parts)}</g>'
    return (f'<svg class="stage-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
            f'width="{WIDTH}" height="{HEIGHT}" style="position:absolute;left:0;top:0;">{DEFS}{camera_g}</svg>')
