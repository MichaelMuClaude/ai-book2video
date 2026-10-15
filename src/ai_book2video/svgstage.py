"""SVG stage: colourful, hand-drawn look for stick-figure scenes.

The stage is one inline <svg> covering the portrait frame (1080 x 1920). Actors, props and
backgrounds are SVG groups. The motion engine moves and rotates them with CSS transforms, the
same way it moves HTML elements, so the timeline code is shared.

Look:
- crayon texture on backgrounds (feTurbulence speckle),
- hand-drawn wobble on outlines (feDisplacementMap),
- round white heads with faces, coloured bodies, thick black outlines with round caps,
- bold colour blocks, and colourful props.

Life:
- a camera that cuts to a new shot on every narration sentence (wide, medium, close) and drifts,
- action times can name a sentence ("s2", "s2+0.5") so the action lands when it is said,
- faces (neutral, happy, sad, surprised, hurt), blinking, breathing, a mouth that moves when talking,
- walking bob, a bouncy fall, speech bubbles, impact bursts and speed lines.
"""

from __future__ import annotations

import html

from ai_book2video.script import Scene

WIDTH = 1080
HEIGHT = 1920
GROUND = 1240
SCALE = WIDTH / 1920
ACTOR_SCALE = 1.35
CHEST = 250 * ACTOR_SCALE
BODY_COLOURS = ["#ffd23f", "#22c55e", "#f97316", "#3b82f6", "#ec4899", "#14b8a6", "#a855f7"]
INK = "#111111"
FACES = ("neutral", "happy", "sad", "surprised", "hurt")
SHOTS = ((1.0, False), (1.22, True), (1.42, True))  # (zoom, focus on an actor)

DEFS = """
<defs>
  <filter id="crayon" x="-5%" y="-5%" width="110%" height="110%">
    <feTurbulence type="fractalNoise" baseFrequency="0.55" numOctaves="3" seed="4" result="grain"/>
    <feColorMatrix in="grain" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.2 1.7" result="speck"/>
    <feComposite in="SourceGraphic" in2="speck" operator="in" result="speckled"/>
    <feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="9" result="wave"/>
    <feDisplacementMap in="speckled" in2="wave" scale="10" xChannelSelector="R" yChannelSelector="G"/>
  </filter>
  <filter id="wobble" x="-10%" y="-10%" width="120%" height="120%">
    <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="2" seed="2" result="wave"/>
    <feDisplacementMap in="SourceGraphic" in2="wave" scale="7" xChannelSelector="R" yChannelSelector="G"/>
  </filter>
</defs>
"""


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _fill_box(origin: str) -> str:
    return f"transform-box:fill-box;transform-origin:{origin};"


def when(value, cues: list, default: float = 0.0) -> float:
    """A time in seconds. Numbers pass through; "s2" is the start of sentence 2; "s2+0.5" adds an offset."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower()
    if not text.startswith("s"):
        return float(text)
    offset = 0.0
    for sign in ("+", "-"):
        if sign in text[1:]:
            head, tail = text[1:].split(sign, 1)
            offset = float(tail) * (1 if sign == "+" else -1)
            text = "s" + head
            break
    index = int(text[1:]) - 1
    if not cues:
        return default + offset
    index = max(0, min(index, len(cues) - 1))
    return float(cues[index][0]) + offset


def background(kind: str, palette: dict, split: bool = False) -> str:
    """Coloured background with crayon texture. `split` gives two colour blocks, left and right."""
    bg = palette["bg"]
    accent = palette["accent"]
    card = palette["card"]
    pad = 300  # extra area around the frame so camera moves never show an edge
    parts = [f'<rect x="{-pad}" y="{-pad}" width="{WIDTH + 2 * pad}" height="{HEIGHT + 2 * pad}" fill="{bg}"/>']
    if split:
        parts.append(f'<rect x="{-pad}" y="{-pad}" width="{WIDTH // 2 + pad}" height="{GROUND + pad}" fill="{accent}"/>')
        parts.append(f'<rect x="{WIDTH // 2}" y="{-pad}" width="{WIDTH // 2 + pad}" height="{GROUND + pad}" fill="{card}"/>')
    if kind == "street":
        for x, w, h, colour in ((-120, 160, 640, accent), (40, 300, 760, card), (360, 220, 560, accent), (640, 260, 880, card), (930, 200, 620, accent), (1150, 180, 700, card)):
            parts.append(f'<rect x="{x}" y="{GROUND - h}" width="{w}" height="{h}" rx="10" fill="{colour}" opacity="0.35" stroke="{INK}" stroke-width="6"/>')
            for wy in range(GROUND - h + 50, GROUND - 60, 110):
                parts.append(f'<rect x="{x + 30}" y="{wy}" width="40" height="50" rx="6" fill="#fef3c7" opacity="0.7"/>')
    elif kind == "field":
        parts.append(f'<ellipse cx="200" cy="{GROUND + 40}" rx="760" ry="300" fill="#22c55e" opacity="0.55"/>')
        parts.append(f'<ellipse cx="900" cy="{GROUND + 60}" rx="760" ry="280" fill="#16a34a" opacity="0.55"/>')
    elif kind == "room":
        parts.append(f'<rect x="{WIDTH // 2 - 320}" y="260" width="640" height="{GROUND - 260}" rx="18" fill="{accent}" opacity="0.35" stroke="{INK}" stroke-width="6"/>')
        parts.append(f'<rect x="{WIDTH // 2 - 160}" y="380" width="320" height="260" rx="14" fill="#bae6fd" stroke="{INK}" stroke-width="6"/>')
    ground_colour = "#8b5a2b" if kind in ("field", "plain") else "#6b7280"
    parts.append(f'<rect x="{-pad}" y="{GROUND}" width="{WIDTH + 2 * pad}" height="{HEIGHT - GROUND + pad}" fill="{ground_colour}" opacity="0.75"/>')
    return f'<g filter="url(#crayon)">{"".join(parts)}</g>'


def _burst(gid: str, x: float, y: float, spec: dict, cues: list, tl) -> str:
    """A comic impact star that pops in at a moment and fades."""
    import math

    points = []
    for i in range(16):
        r = 120 if i % 2 == 0 else 60
        a = math.pi * 2 * i / 16
        points.append(f"{r * math.cos(a):.0f},{r * math.sin(a):.0f}")
    word = _esc(spec.get("text", "!"))
    at = when(spec.get("at"), cues, 1.0)
    dur = float(spec.get("dur", 1.2))
    tl.start(gid, s=0, o=0)
    tl.add(gid, "s", 1, at, 0.35, "back")
    tl.add(gid, "o", 1, at, 0.1)
    tl.add(gid, "o", 0, at + dur, 0.3)
    return (f'<g data-id="{gid}" style="{_fill_box("50% 50%")}"><g transform="translate({x:.0f} {y:.0f})">'
            f'<polygon points="{" ".join(points)}" fill="#fde047" stroke="{INK}" stroke-width="8" stroke-linejoin="round"/>'
            f'<text x="0" y="16" text-anchor="middle" font-size="52" font-weight="900" fill="{INK}" '
            f'font-family="Noto Sans, DejaVu Sans, sans-serif">{word}</text></g></g>')


def prop(prefix: str, index: int, spec: dict, palette: dict, tl, cues: list) -> str:
    kind = spec["type"]
    gid = f"{prefix}p{index}"
    x0 = float(spec.get("x", 0)) * SCALE
    y0 = float(spec.get("y", 0))
    if kind == "burst":
        return _burst(gid, x0, y0 if y0 else GROUND - 300, spec, cues, tl)
    if kind == "sun":
        rays = "".join(
            f'<line x1="0" y1="-120" x2="0" y2="-160" stroke="#f59e0b" stroke-width="12" stroke-linecap="round" transform="rotate({a})"/>'
            for a in range(0, 360, 45)
        )
        return (f'<g data-id="{gid}" data-float="12,5,0"><g transform="translate({x0:.0f} {y0 + 260:.0f})">{rays}'
                f'<circle r="90" fill="#fde047" stroke="{INK}" stroke-width="8"/></g></g>')
    if kind == "fire":
        return (f'<g data-id="{gid}" data-float="8,0.7,{index}"><g transform="translate({x0:.0f} {GROUND})">'
                f'<path d="M0,-130 C40,-90 60,-40 40,0 L-40,0 C-60,-40 -40,-90 0,-130 Z" fill="#f97316" stroke="{INK}" stroke-width="6"/>'
                f'<path d="M0,-70 C20,-40 26,-20 18,0 L-18,0 C-26,-20 -20,-40 0,-70 Z" fill="#fde047"/></g></g>')
    if kind == "building":
        w = int(float(spec.get("w", 200)) * SCALE)
        h = int(spec.get("h", 400))
        return (f'<g data-id="{gid}"><rect x="{x0:.0f}" y="{GROUND - h}" width="{w}" height="{h}" rx="10" '
                f'fill="{palette["card"]}" opacity="0.55" stroke="{INK}" stroke-width="6"/></g>')
    if kind == "car":
        moving = spec.get("to") is not None
        lines = "".join(
            f'<line x1="-300" y1="{y}" x2="-190" y2="{y}" stroke="{INK}" stroke-width="9" stroke-linecap="round" opacity="0.55"/>'
            for y in (-170, -120, -70)
        ) if moving else ""
        inner = (
            lines
            + f'<rect x="-150" y="-150" width="300" height="92" rx="30" fill="#14b8a6" stroke="{INK}" stroke-width="8"/>'
            + f'<rect x="-88" y="-212" width="176" height="72" rx="24" fill="#14b8a6" stroke="{INK}" stroke-width="8"/>'
            + f'<rect x="-66" y="-196" width="60" height="44" rx="8" fill="#e0f2fe" stroke="{INK}" stroke-width="5"/>'
            + f'<rect x="6" y="-196" width="60" height="44" rx="8" fill="#e0f2fe" stroke="{INK}" stroke-width="5"/>'
            + f'<circle cx="-80" cy="-40" r="38" fill="{INK}"/><circle cx="80" cy="-40" r="38" fill="{INK}"/>'
            + f'<circle cx="-80" cy="-40" r="14" fill="#e5e7eb"/><circle cx="80" cy="-40" r="14" fill="#e5e7eb"/>'
        )
    elif kind == "tree":
        inner = (
            f'<rect x="-9" y="-160" width="18" height="160" rx="6" fill="#92400e" stroke="{INK}" stroke-width="6"/>'
            f'<circle cx="0" cy="-240" r="88" fill="#22c55e" stroke="{INK}" stroke-width="7"/>'
        )
    elif kind == "podium":
        inner = f'<rect x="-52" y="-150" width="104" height="150" rx="10" fill="#374151" stroke="{INK}" stroke-width="7"/>'
    elif kind == "book":
        inner = (f'<rect x="-50" y="-74" width="100" height="74" rx="8" fill="#ec4899" stroke="{INK}" stroke-width="7"/>'
                 f'<rect x="-50" y="-30" width="100" height="10" fill="#fde047"/>')
    else:
        inner = ""
    tl.start(gid, x=x0)
    if spec.get("to") is not None:
        tl.add(gid, "x", float(spec["to"]) * SCALE, when(spec.get("at"), cues), float(spec.get("dur", 3)), "linear", frm=x0)
    return f'<g data-id="{gid}"><g transform="translate(0 {GROUND})">{inner}</g></g>'


def _leg(ident: str, x: float, swing: str) -> str:
    return (f'<g transform="translate({x} -130)"><path data-id="{ident}"{swing} d="M0,0 L0,130" stroke="{INK}" '
            f'stroke-width="12" stroke-linecap="round" fill="none" style="{_fill_box("50% 0%")}"/></g>')


def _arm(ident: str, x: float, y: float, swing: str) -> str:
    return (f'<g transform="translate({x} {y})"><path data-id="{ident}"{swing} d="M0,0 L0,100" stroke="{INK}" '
            f'stroke-width="12" stroke-linecap="round" fill="none" style="{_fill_box("50% 0%")}"/></g>')


def _mouths(gid: str, talking: bool) -> str:
    shapes = {
        "neutral": f'<path d="M-14,-298 L14,-298" stroke="{INK}" stroke-width="6" stroke-linecap="round" fill="none"/>',
        "happy": f'<path d="M-18,-304 Q0,-282 18,-304" stroke="{INK}" stroke-width="6" stroke-linecap="round" fill="none"/>',
        "sad": f'<path d="M-16,-290 Q0,-306 16,-290" stroke="{INK}" stroke-width="6" stroke-linecap="round" fill="none"/>',
        "surprised": f'<ellipse cx="0" cy="-296" rx="9" ry="12" fill="{INK}"/>',
        "hurt": f'<path d="M-16,-296 L-8,-303 L0,-296 L8,-303 L16,-296" stroke="{INK}" stroke-width="5" stroke-linejoin="round" fill="none"/>',
    }
    parts = [f'<g data-id="{gid}-m-{name}">{shape}</g>' for name, shape in shapes.items()]
    if talking:
        parts.append(f'<g data-id="{gid}-m-talk" data-flap="0.34"><ellipse cx="0" cy="-297" rx="11" ry="9" fill="{INK}"/></g>')
    return "".join(parts)


def _face_timeline(gid: str, spec: dict, cues: list, tl) -> None:
    """Show one mouth at a time. 'faces' lists changes: [{"at": "s2", "face": "surprised"}]."""
    start = spec.get("face", "neutral")
    if start not in FACES:
        start = "neutral"
    for name in FACES:
        tl.start(f"{gid}-m-{name}", o=1 if name == start else 0)
    changes = list(spec.get("faces", []))
    if spec.get("action") == "fall" and not any(c.get("face") == "hurt" for c in changes):
        changes.append({"at": spec.get("at", 0), "face": "hurt"})
    current = start
    for change in sorted(changes, key=lambda c: when(c.get("at"), cues)):
        face = change.get("face", "neutral")
        if face not in FACES or face == current:
            continue
        at = when(change.get("at"), cues)
        tl.add(f"{gid}-m-{current}", "o", 0, at, 0.08)
        tl.add(f"{gid}-m-{face}", "o", 1, at, 0.08)
        current = face


def _bubbles(gid: str, spec: dict, cues: list, tl) -> str:
    """Speech bubbles: 'say': [{"text": "Yes!", "at": "s2", "dur": 2.5}]. A bubble that would leave the frame flips left."""
    out = []
    for index, line in enumerate(spec.get("say", [])):
        text = _esc(str(line.get("text", "")))
        width = max(140, int(len(str(line.get("text", ""))) * 24 + 70))
        bid = f"{gid}-say{index}"
        at = when(line.get("at"), cues, 0.5)
        dur = float(line.get("dur", 2.5))
        tl.start(bid, o=0, s=0.6)
        tl.add(bid, "o", 1, at, 0.15)
        tl.add(bid, "s", 1, at, 0.35, "back")
        tl.add(bid, "o", 0, at + dur, 0.25)
        x = max(actor_x(spec, at, cues), actor_x(spec, at + dur, cues))
        flip = x + (40 + width) * ACTOR_SCALE > WIDTH - 24
        left = -40 - width if flip else 40
        tail = (f'M{width - 30},18 L{width - 10},60 L{width - 64},20' if flip else 'M30,18 L10,60 L64,20')
        out.append(
            f'<g data-id="{bid}" style="{_fill_box("100% 100%" if flip else "0% 100%")}"><g transform="translate({left} -470)">'
            f'<rect x="0" y="-70" width="{width}" height="92" rx="40" fill="#ffffff" stroke="{INK}" stroke-width="7"/>'
            f'<path d="{tail}" fill="#ffffff" stroke="{INK}" stroke-width="7" stroke-linejoin="round"/>'
            f'<text x="{width / 2:.0f}" y="-8" text-anchor="middle" font-size="40" font-weight="800" fill="{INK}" '
            f'font-family="Noto Sans, Noto Sans CJK SC, DejaVu Sans, sans-serif">{text}</text></g></g>'
        )
    return "".join(out)


def actor_x(spec: dict, t: float, cues: list) -> float:
    """Where an actor's feet are at time t, in portrait pixels (for the camera)."""
    x0 = float(spec.get("x", 0)) * SCALE
    if spec.get("action") != "walk" or spec.get("to") is None:
        return x0
    x1 = float(spec["to"]) * SCALE
    at = when(spec.get("at"), cues)
    dur = float(spec.get("dur", 3))
    if t <= at:
        return x0
    if t >= at + dur:
        return x1
    return x0 + (x1 - x0) * (t - at) / dur


def actor(prefix: str, index: int, spec: dict, palette: dict, tl, cues: list) -> str:
    """A stick-figure person with a round head, a face and a coloured body. Origin: feet on the ground."""
    action = spec.get("action", "stand")
    if action not in ("stand", "walk", "fall", "talk", "wave"):
        action = "stand"
    gid = f"{prefix}a{index}"
    body_colour = spec.get("colour") or BODY_COLOURS[index % len(BODY_COLOURS)]
    x0 = float(spec.get("x", 0)) * SCALE
    walking = action == "walk"
    talking = action == "talk"
    waving = action == "wave"

    def swing(amp: int, phase: float, period: float = 1.1) -> str:
        return f' data-swing="{amp},{period},{phase}"'

    legs = _leg(f"{gid}-ll", -14, swing(26, 0) if walking else "") + _leg(f"{gid}-rl", 14, swing(26, 3.1416) if walking else "")
    arm_r = swing(22, 3.1416) if walking else swing(14, 0, 0.7) if talking else swing(18, 0, 0.6) if waving else ""
    arms = _arm(f"{gid}-la", -34, -240, swing(22, 0) if walking else "") + _arm(f"{gid}-ra", 34, -240, arm_r)
    torso = f'<rect x="-34" y="-270" width="68" height="150" rx="30" fill="{body_colour}" stroke="{INK}" stroke-width="9"/>'
    head = (
        f'<circle cx="0" cy="-318" r="46" fill="#ffffff" stroke="{INK}" stroke-width="9"/>'
        f'<g data-id="{gid}-eyes" data-blink="{3.2 + index * 0.7:.1f},{index * 1.3:.1f}" style="{_fill_box("50% 50%")}">'
        f'<ellipse cx="-16" cy="-326" rx="6" ry="8" fill="{INK}"/><ellipse cx="16" cy="-326" rx="6" ry="8" fill="{INK}"/></g>'
        + _mouths(gid, talking)
    )
    label = ""
    if spec.get("label"):
        label = (f'<text x="0" y="-392" text-anchor="middle" font-size="36" font-weight="800" fill="{INK}" stroke="#ffffff" '
                 f'stroke-width="8" paint-order="stroke" font-family="Noto Sans, Noto Sans CJK SC, DejaVu Sans, sans-serif">{_esc(spec["label"])}</text>')
    breathe = f' data-float="3,{2.4 + index * 0.3:.1f},{index:.1f}"' if not walking else ""
    figure = (f'<g data-id="{gid}-f"{breathe} style="{_fill_box("50% 100%")}">'
              f'{legs}{torso}{arms}{head}{label}</g>')
    bubbles = _bubbles(gid, spec, cues, tl)
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
        tl.add(f"{gid}-f", "r", 90, when(spec.get("at"), cues), 0.6, "back", frm=0)
    bob = ' data-float="7,0.55,0"' if walking else ""
    return (f'<g data-id="{gid}"{bob}><g filter="url(#wobble)" transform="translate(0 {GROUND}) scale({ACTOR_SCALE})">'
            f'{figure}{bubbles}</g></g>')


def _camera(spec: dict, cues: list, duration: float, tl) -> None:
    """Cut to a new shot on every sentence: wide, then medium on one actor, then close on another."""
    actors = spec.get("actors", [])
    cx, cy = WIDTH / 2, HEIGHT / 2
    tl.start("cam", x=0, y=0, s=1)
    beats = cues or [[0.0, duration, "", ""]]
    for index, cue in enumerate(beats):
        start, end = float(cue[0]), float(cue[1])
        zoom, focus = SHOTS[index % len(SHOTS)] if actors else (1.0, False)
        tx = ty = 0.0
        if focus:
            target = actors[(index // len(SHOTS) + index) % len(actors)]
            ax = actor_x(target, start + 0.5, cues)
            ay = GROUND - CHEST
            tx = -zoom * (ax - cx)
            ty = -zoom * (ay - cy) - 120
            tx = max(-cx * (zoom - 1), min(cx * (zoom - 1), tx))
            ty = max(-cy * (zoom - 1), min(cy * (zoom - 1), ty))
        move = 0.7 if index else 0.01
        tl.add("cam", "s", zoom, start, move, "inOut")
        tl.add("cam", "x", tx, start, move, "inOut")
        tl.add("cam", "y", ty, start, move, "inOut")
        drift_end = end if index < len(beats) - 1 else duration
        if drift_end - start - move > 0.3:
            tl.add("cam", "s", zoom + 0.05, start + move, drift_end - start - move, "linear")


def stage(scene: Scene, palette: dict, tl, cues: list | None = None, duration: float = 6.0) -> str:
    cues = cues or []
    spec = scene.stage or {}
    parts = [background(spec.get("background", "plain"), palette, split=bool(spec.get("split", False)))]
    for index, item in enumerate(spec.get("props", [])):
        parts.append(prop("s", index, item, palette, tl, cues))
    for index, item in enumerate(spec.get("actors", [])):
        parts.append(actor("s", index, item, palette, tl, cues))
    if spec.get("camera", True):
        _camera(spec, cues, duration, tl)
    camera = f'<g data-id="cam" style="transform-box:view-box;transform-origin:{WIDTH / 2:.0f}px {HEIGHT / 2:.0f}px;">{"".join(parts)}</g>'
    return (f'<svg class="stage-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
            f'width="{WIDTH}" height="{HEIGHT}" style="position:absolute;left:0;top:0;">{DEFS}{camera}</svg>')
