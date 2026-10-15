"""Motion graphics: each scene is an animated HTML page driven by a timeline.

A page exposes window.setT(t). The renderer calls it once per frame with t in seconds,
so every frame is deterministic. Animations are tweens on element properties:
x, y (px), s (scale), sx (scale X), r (rotation, deg), o (opacity), and two text
properties: chars (typewriter) and count (number count-up).
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field

from ai_book2video.script import Scene

WIDTH = 1920
HEIGHT = 1080

PALETTES = [
    {"bg": "#ff5a5f", "ink": "#ffffff", "accent": "#ffd23f", "card": "#1b1b3a", "card_ink": "#ffffff"},
    {"bg": "#0f172a", "ink": "#ffffff", "accent": "#22d3ee", "card": "#f472b6", "card_ink": "#0f172a"},
    {"bg": "#fff3d6", "ink": "#1b1b3a", "accent": "#7c3aed", "card": "#ff5a5f", "card_ink": "#ffffff"},
    {"bg": "#06d6a0", "ink": "#06201a", "accent": "#ffffff", "card": "#ff006e", "card_ink": "#ffffff"},
]

ENGINE = r"""
const EASE = {
  linear: (t) => t,
  out: (t) => 1 - Math.pow(1 - t, 3),
  inOut: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  back: (t) => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); },
};
const ELS = {};
document.querySelectorAll('[data-id]').forEach((el) => { ELS[el.dataset.id] = el; });
const FULL = {};
document.querySelectorAll('[data-text]').forEach((el) => { FULL[el.dataset.id] = el.dataset.text; });
function apply(t) {
  const state = {};
  for (const id in ELS) state[id] = Object.assign({ x: 0, y: 0, s: 1, sx: 1, r: 0, o: 1, chars: 0, count: 0 }, INIT[id] || {});
  for (const a of ANIMS) {
    if (t < a.at) continue;
    const st = state[a.id];
    const from = a.from === null || a.from === undefined ? st[a.p] : a.from;
    let v;
    if (t >= a.at + a.dur) v = a.to;
    else v = from + (a.to - from) * EASE[a.e || 'out'](Math.max(0, (t - a.at) / a.dur));
    st[a.p] = v;
  }
  for (const id in ELS) {
    const el = ELS[id];
    const st = state[id];
    let y = st.y;
    const fl = el.dataset.float;
    if (fl) { const [amp, period, phase] = fl.split(',').map(Number); y += amp * Math.sin((2 * Math.PI * t) / period + phase); }
    let rot = st.r;
    const sw = el.dataset.swing;
    if (sw) { const [amp, period, phase] = sw.split(',').map(Number); rot += amp * Math.sin((2 * Math.PI * t) / period + phase); }
    el.style.transform = `translate(${st.x}px, ${y}px) rotate(${rot}deg) scale(${st.s}) scaleX(${st.sx})`;
    el.style.opacity = String(Math.max(0, Math.min(1, st.o)));
  }
  for (const a of ANIMS) {
    if (a.p !== 'chars' && a.p !== 'count') continue;
    const el = ELS[a.id];
    if (!el) continue;
    const cur = state[a.id][a.p];
    if (a.p === 'chars') {
      const text = FULL[a.id] || '';
      el.textContent = text.slice(0, Math.round(cur));
    } else {
      const dec = Number(el.dataset.dec || 0);
      el.textContent = (el.dataset.prefix || '') + Number(cur).toFixed(dec) + (el.dataset.suffix || '');
    }
  }
}
function captions(t) {
  const box = document.getElementById('caption');
  const line = document.querySelector('#caption span');
  if (!box || !line) return;
  let txt = '';
  let op = 0;
  for (const c of CUES) {
    if (t >= c[0] && t < c[1]) { txt = c[2]; op = Math.min(1, (t - c[0]) / 0.2, (c[1] - t) / 0.2); break; }
  }
  if (line.textContent !== txt) line.textContent = txt;
  box.style.opacity = String(Math.max(0, op));
}
window.setT = (t) => { apply(t); captions(t); };
apply(0);
captions(0);
"""

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: %(w)dpx; height: %(h)dpx; overflow: hidden; }
body { background: %(bg)s; font-family: "Noto Sans CJK SC", "DejaVu Sans", "Helvetica Neue", Arial, sans-serif; }
#stage { position: relative; width: %(w)dpx; height: %(h)dpx; overflow: hidden; background: %(bg)s; }
.el { position: absolute; will-change: transform, opacity; white-space: nowrap; }
.word { display: inline-block; margin-right: 0.22em; will-change: transform, opacity; }
.heavy { font-weight: 900; letter-spacing: -0.01em; }
.origin-left { transform-origin: left center; }
.wrap { white-space: normal; }
.card { border-radius: 30px; display: flex; align-items: center; padding: 0 40px; }
.badge { border-radius: 50%%; width: 84px; height: 84px; display: flex; align-items: center; justify-content: center;
  font-weight: 900; font-size: 46px; flex: 0 0 auto; }
.disc { border-radius: 50%%; }
#caption { position: absolute; left: 0; right: 0; bottom: 56px; text-align: center; font-size: 54px; font-weight: 700;
  color: #ffffff; pointer-events: none; opacity: 0; }
#caption span { display: inline-block; max-width: 1600px; white-space: normal; background: rgba(0, 0, 0, 0.62); padding: 10px 34px; border-radius: 18px; line-height: 1.35; }
"""


@dataclass
class Timeline:
    anims: list[dict] = field(default_factory=list)
    init: dict[str, dict] = field(default_factory=dict)

    def start(self, element: str, **values) -> None:
        self.init.setdefault(element, {}).update(values)

    def add(self, element: str, prop: str, to, at: float, dur: float, ease: str = "out", frm=None) -> None:
        self.anims.append({"id": element, "p": prop, "to": to, "at": round(at, 3), "dur": round(dur, 3), "e": ease, "from": frm})

    def sorted_anims(self) -> list[dict]:
        return sorted(self.anims, key=lambda a: a["at"])


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _font_size(text: str, big: int = 190, mid: int = 150, small: int = 118) -> int:
    length = len(text)
    if length <= 14:
        return big
    if length <= 28:
        return mid
    return small


def _heading_lines(text: str, size: int, width: int = 1620) -> int:
    """Rough line count for a heading set at `size` px in a box `width` px wide."""
    import math

    return max(1, math.ceil(len(text) * 0.56 * size / width))


def _sentences(text: str) -> list[str]:
    import re

    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part for part in parts if part]


def _wrapper_page(palette: dict, body: str, timeline: Timeline, duration: float, title: str, cues=None) -> str:
    css = CSS % {"w": WIDTH, "h": HEIGHT, "bg": palette["bg"]}
    anims = json.dumps(timeline.sorted_anims())
    init = json.dumps(timeline.init)
    # Transition panels: cover the frame at the start, and again at the end, like an ad cut.
    panel_css = f"background:{palette['accent']};"
    start = (
        f'<div class="el" data-id="wipe-out" style="left:0;top:0;width:{WIDTH}px;height:{HEIGHT}px;{panel_css}"></div>'
    )
    end = (
        f'<div class="el" data-id="wipe-in" style="left:0;top:0;width:{WIDTH}px;height:{HEIGHT}px;{panel_css}"></div>'
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{_esc(title)}</title><style>{css}</style></head><body>"
        f"<div id='stage'>{body}<div id='caption'><span></span></div>{start}{end}</div>"
        f"<script>const ANIMS = {anims}; const INIT = {init}; const DURATION = {duration:.3f}; const CUES = {json.dumps(cues or [], ensure_ascii=False)};\n{ENGINE}</script>"
        "</body></html>"
    )


def _transitions(timeline: Timeline, duration: float) -> None:
    timeline.start("wipe-out", x=0)
    timeline.add("wipe-out", "x", -WIDTH - 200, 0.0, 0.75, "inOut", frm=0)
    timeline.start("wipe-in", x=WIDTH + 200)
    timeline.add("wipe-in", "x", 0, max(0.0, duration - 0.7), 0.6, "inOut", frm=WIDTH + 200)


def _words_html(prefix: str, text: str, size: int, color: str, weight: str = "heavy", extra: str = "") -> tuple[str, list[str]]:
    words = text.split()
    ids = []
    spans = []
    for index, word in enumerate(words):
        ident = f"{prefix}{index}"
        ids.append(ident)
        spans.append(f'<span class="el word {weight}" data-id="{ident}" style="position:relative;font-size:{size}px;color:{color};{extra}">{_esc(word)}</span>')
    return " ".join(spans), ids


def _enter_words(timeline: Timeline, ids: list[str], start: float, step: float, lift: int = 150, dur: float = 0.7) -> None:
    for index, ident in enumerate(ids):
        at = start + index * step
        timeline.start(ident, y=lift, o=0)
        timeline.add(ident, "y", 0, at, dur, "back")
        timeline.add(ident, "o", 1, at, dur * 0.5, "out")


def _title(scene: Scene, duration: float, palette: dict) -> tuple[str, Timeline]:
    tl = Timeline()
    body = []
    body.append(f'<div class="el disc" data-id="c1" data-float="18,7,0" style="left:-260px;top:520px;width:960px;height:960px;background:{palette["accent"]};opacity:.95"></div>')
    body.append(f'<div class="el disc" data-id="c2" data-float="14,5.5,1.2" style="left:1480px;top:-180px;width:520px;height:520px;background:{palette["card"]};"></div>')
    tl.start("c1", s=0)
    tl.start("c2", s=0)
    tl.add("c1", "s", 1, 0.1, 0.9, "back")
    tl.add("c2", "s", 1, 0.25, 0.9, "back")
    tag = f'<div class="el card heavy" data-id="tag" style="left:160px;top:170px;height:86px;background:{palette["card"]};color:{palette["card_ink"]};font-size:40px;"><span>EXPLAINER</span></div>'
    body.append(tag)
    tl.start("tag", o=0, r=-5)
    tl.add("tag", "o", 1, 0.05, 0.3)
    tl.add("tag", "s", 1, 0.05, 0.5, "back", frm=0.6)
    size = _font_size(scene.heading, big=200, mid=160, small=130)
    words, ids = _words_html("h", scene.heading, size, palette["ink"])
    body.append(f'<div class="el wrap" data-id="heading" style="left:160px;top:330px;width:1600px;line-height:1.02;">{words}</div>')
    _enter_words(tl, ids, 0.35, 0.14, lift=180, dur=0.75)
    if scene.body:
        body.append(
            f'<div class="el" data-id="sub" data-text="{_esc(scene.body)}" '
            f'style="left:168px;top:{330 + size * 2 + 40}px;font-size:62px;color:{palette["card_ink"]};font-weight:600;'
            f'background:{palette["card"]};padding:14px 30px;border-radius:22px;">'
            f'{_esc(scene.body)}</div>'
        )
        tl.start("sub", o=1)
        tl.add("sub", "chars", len(scene.body), 1.5, min(2.4, 0.045 * len(scene.body)), "linear", frm=0)
    _transitions(tl, duration)
    return "".join(body), tl


def _text(scene: Scene, duration: float, palette: dict) -> tuple[str, Timeline]:
    tl = Timeline()
    body = []
    size = _font_size(scene.heading, big=150, mid=128, small=104)
    words, ids = _words_html("h", scene.heading, size, palette["ink"])
    rule = f'<div class="el origin-left" data-id="rule" style="position:relative;display:block;margin-top:26px;width:680px;height:20px;background:{palette["accent"]};border-radius:10px;"></div>'
    body.append(f'<div class="el wrap" data-id="head-block" style="left:150px;top:150px;width:1620px;line-height:1.04;">'
                f'<div style="position:relative;">{words}</div>{rule}</div>')
    _enter_words(tl, ids, 0.25, 0.12, lift=140, dur=0.65)
    tl.start("rule", sx=0)
    tl.add("rule", "sx", 1, 0.9, 0.6, "out")
    sentences = _sentences(scene.body) or [scene.body]
    top = 150 + _heading_lines(scene.heading, size) * size * 1.06 + 110
    stack = []
    span = max(0.0, duration - 2.4)
    step = min(1.4, max(0.55, span / max(1, len(sentences))))
    for index, sentence in enumerate(sentences):
        ident = f"s{index}"
        stack.append(
            f'<div class="el wrap" data-id="{ident}" style="position:relative;display:block;width:1440px;margin:0 0 26px 0;'
            f'padding:22px 34px;border-radius:24px;background:{palette["card"]};color:{palette["card_ink"]};font-size:56px;font-weight:700;line-height:1.35;">{_esc(sentence)}</div>'
        )
        at = 1.1 + index * step
        tl.start(ident, x=260, o=0)
        tl.add(ident, "x", 0, at, 0.7, "back")
        tl.add(ident, "o", 1, at, 0.35)
    body.append(f'<div style="position:absolute;left:150px;top:{top}px;width:1440px;">' + "".join(stack) + "</div>")
    body.append(f'<div class="el disc" data-id="spin" style="left:1500px;top:110px;width:260px;height:260px;background:{palette["accent"]};border-radius:40px;"></div>')
    tl.start("spin", r=0)
    tl.add("spin", "r", 360, 0.0, duration, "linear")
    _transitions(tl, duration)
    return "".join(body), tl


def _bullets(scene: Scene, duration: float, palette: dict) -> tuple[str, Timeline]:
    tl = Timeline()
    body = []
    size = _font_size(scene.heading, big=130, mid=118, small=104)
    words, ids = _words_html("h", scene.heading, size, palette["ink"])
    body.append(f'<div class="el wrap" data-id="heading" style="left:150px;top:110px;width:1620px;line-height:1.04;">{words}</div>')
    _enter_words(tl, ids, 0.2, 0.1, lift=120, dur=0.6)
    count = max(1, len(scene.items))
    span = max(0.0, duration - 2.2)
    step = min(0.9, max(0.35, span / count))
    top0 = 110 + _heading_lines(scene.heading, size) * size * 1.06 + 60
    gap = 158
    for index, item in enumerate(scene.items):
        ident = f"b{index}"
        left_side = index % 2 == 0
        top = top0 + index * gap
        body.append(
            f'<div class="el card" data-id="{ident}" style="left:170px;top:{top}px;width:1560px;min-height:128px;padding:16px 40px;background:{palette["card"]};color:{palette["card_ink"]};">'
            f'<div class="el badge" data-id="{ident}n" style="position:relative;margin-right:34px;background:{palette["accent"]};color:{palette["ink"] if palette["accent"] != palette["card"] else "#000"};">{index + 1}</div>'
            f'<span style="font-size:54px;font-weight:700;white-space:normal;line-height:1.2;">{_esc(item)}</span></div>'
        )
        at = 0.9 + index * step
        tl.start(ident, x=(-520 if left_side else 520), o=0)
        tl.add(ident, "x", 0, at, 0.75, "back")
        tl.add(ident, "o", 1, at, 0.3)
    _transitions(tl, duration)
    return "".join(body), tl


def _quote(scene: Scene, duration: float, palette: dict) -> tuple[str, Timeline]:
    tl = Timeline()
    body = []
    mark_id = "mark"
    body.append(f'<div class="el heavy" data-id="{mark_id}" style="left:130px;top:-40px;font-size:460px;line-height:1;color:{palette["accent"]};">&ldquo;</div>')
    tl.start(mark_id, s=0)
    tl.add(mark_id, "s", 1, 0.1, 0.6, "back")
    text = scene.body
    words = text.split()
    size = 100
    spans = []
    ids = []
    for index, word in enumerate(words):
        ident = f"q{index}"
        ids.append(ident)
        spans.append(f'<span class="el word" data-id="{ident}" style="position:relative;font-size:{size}px;font-style:italic;font-weight:700;color:{palette["ink"]};">{_esc(word)}</span>')
    body.append(f'<div class="el wrap" data-id="quote" style="left:250px;top:300px;width:1500px;line-height:1.3;">' + " ".join(spans) + "</div>")
    span = max(0.0, duration * 0.6 - 0.6)
    step = min(0.16, max(0.05, span / max(1, len(words))))
    for index, ident in enumerate(ids):
        at = 0.6 + index * step
        tl.start(ident, y=50, o=0)
        tl.add(ident, "y", 0, at, 0.35)
        tl.add(ident, "o", 1, at, 0.25)
    if scene.source:
        body.append(f'<div class="el" data-id="by" style="left:260px;top:880px;font-size:50px;font-weight:600;color:{palette["ink"]};opacity:.8;">— {_esc(scene.source)}</div>')
        tl.start("by", x=-200, o=0)
        tl.add("by", "x", 0, duration * 0.7, 0.6)
        tl.add("by", "o", 1, duration * 0.7, 0.5)
    _transitions(tl, duration)
    return "".join(body), tl


def _stat(scene: Scene, duration: float, palette: dict) -> tuple[str, Timeline]:
    tl = Timeline()
    body = []
    body.append(f'<div class="el disc" data-id="burst" style="left:610px;top:80px;width:700px;height:700px;background:{palette["accent"]};"></div>')
    tl.start("burst", s=0)
    tl.add("burst", "s", 1, 0.05, 0.8, "back")
    body.append(f'<div class="el disc" data-id="ring" style="left:520px;top:-10px;width:920px;height:920px;border:10px solid {palette["card"]};"></div>')
    tl.start("ring", o=0, s=0.8)
    tl.add("ring", "o", 0.9, 0.1, 0.5)
    tl.add("ring", "s", 1, 0.1, 0.9, "out")
    number = scene.value if scene.value is not None else 0
    dec = 0 if float(number).is_integer() else 1
    shown = f"{scene.prefix}{int(number) if dec == 0 else number}{scene.suffix}"
    number_size = int(min(300, 1640 / max(1, 0.6 * len(shown))))
    body.append(
        f'<div class="el heavy" data-id="num" data-prefix="{_esc(scene.prefix)}" data-suffix="{_esc(scene.suffix)}" data-dec="{dec}" '
        f'style="left:0;top:{330 + (300 - number_size) // 2}px;width:{WIDTH}px;text-align:center;font-size:{number_size}px;color:{palette["ink"]};white-space:nowrap;">'
        f"{_esc(scene.prefix)}0{_esc(scene.suffix)}</div>"
    )
    tl.start("num", o=1)
    tl.add("num", "count", float(number), 0.35, min(2.0, max(1.0, duration * 0.4)), "out", frm=0)
    body.append(f'<div class="el" data-id="label" style="left:0;top:830px;width:{WIDTH}px;text-align:center;font-size:72px;font-weight:700;color:{palette["ink"]};white-space:normal;">{_esc(scene.heading or scene.body)}</div>')
    tl.start("label", y=60, o=0)
    tl.add("label", "y", 0, 2.2, 0.6, "back")
    tl.add("label", "o", 1, 2.2, 0.5)
    _transitions(tl, duration)
    return "".join(body), tl


TEMPLATES = {"title": _title, "text": _text, "bullets": _bullets, "quote": _quote, "stat": _stat}


def scene_page(scene: Scene, index: int, title: str, duration: float) -> str:
    """Full HTML page for one scene. Frame t is drawn by calling window.setT(t)."""
    palette = PALETTES[0] if scene.kind == "title" else PALETTES[index % len(PALETTES)]
    body, timeline = TEMPLATES[scene.kind](scene, duration, palette)
    return _wrapper_page(palette, body, timeline, duration, title)


# ---------------------------------------------------------------------------
# Stick-figure stage: a scene is a drawn background, props and stick figures
# that move on a timeline. Coordinates: x in pixels across the 1920 px frame,
# the ground line sits at GROUND pixels from the top.
# ---------------------------------------------------------------------------

GROUND = 820
BACKGROUNDS = ("street", "field", "room", "plain")
PROPS = ("car", "tree", "sun", "fire", "building", "podium", "book")
ACTIONS = ("stand", "walk", "fall", "talk", "wave")


def _background(kind: str, palette: dict) -> str:
    ground = "rgba(0,0,0,0.12)"
    shade = "rgba(0,0,0,0.10)"
    parts = [f'<div class="el" style="left:0;top:{GROUND}px;width:{WIDTH}px;height:{HEIGHT - GROUND}px;background:{ground};"></div>']
    if kind == "street":
        for x, w, h in ((80, 240, 520), (360, 200, 380), (1240, 260, 470), (1520, 230, 600)):
            parts.append(f'<div class="el" style="left:{x}px;top:{GROUND - h}px;width:{w}px;height:{h}px;background:{shade};border-radius:6px;"></div>')
        for x in range(120, WIDTH, 220):
            parts.append(f'<div class="el" style="left:{x}px;top:{GROUND + 90}px;width:90px;height:8px;background:{palette["ink"]};opacity:.35;"></div>')
    elif kind == "field":
        parts.append(f'<div class="el" style="left:-200px;top:{GROUND - 160}px;width:1000px;height:400px;border-radius:50%;background:{shade};"></div>')
        parts.append(f'<div class="el" style="left:900px;top:{GROUND - 120}px;width:1200px;height:360px;border-radius:50%;background:{shade};"></div>')
    elif kind == "room":
        parts.append(f'<div class="el" style="left:120px;top:200px;width:1680px;height:{GROUND - 200}px;background:{shade};border-radius:12px;"></div>')
        parts.append(f'<div class="el" style="left:1280px;top:380px;width:420px;height:24px;background:{palette["ink"]};opacity:.35;border-radius:6px;"></div>')
    return "".join(parts)


def _prop(prefix: str, index: int, spec: dict, palette: dict, tl: Timeline) -> str:
    kind = spec["type"]
    gid = f"{prefix}p{index}"
    ink = palette["ink"]
    x0 = float(spec.get("x", 0))
    y0 = float(spec.get("y", 0))
    if kind == "sun":
        html_ = f'<div class="el" data-id="{gid}" data-float="10,5,0" style="left:{x0 - 70}px;top:{y0 - 70}px;width:140px;height:140px;border-radius:50%;background:{palette["accent"]};"></div>'
        return html_
    if kind == "fire":
        return (f'<div class="el" data-id="{gid}" data-float="6,0.7,{index}" style="left:{x0 - 40}px;top:{GROUND - 90}px;width:80px;height:90px;'
                f'border-radius:50% 50% 40% 40%;background:{palette["accent"]};"></div>')
    if kind == "building":
        w = int(spec.get("w", 200))
        h = int(spec.get("h", 400))
        return f'<div class="el" data-id="{gid}" style="left:{x0}px;top:{GROUND - h}px;width:{w}px;height:{h}px;background:{ink};opacity:.18;border-radius:6px;"></div>'
    # Props that sit on the ground are groups with their origin at ground level.
    children: list[str] = []
    if kind == "car":
        children = [
            f'<div class="el" style="left:-130px;top:-130px;width:260px;height:80px;background:{palette["card"]};border-radius:24px;"></div>',
            f'<div class="el" style="left:-78px;top:-184px;width:150px;height:62px;background:{palette["card"]};border-radius:20px;"></div>',
            f'<div class="el" style="left:-100px;top:-64px;width:64px;height:64px;border-radius:50%;background:{ink};"></div>',
            f'<div class="el" style="left:36px;top:-64px;width:64px;height:64px;border-radius:50%;background:{ink};"></div>',
        ]
    elif kind == "tree":
        children = [
            f'<div class="el" style="left:-7px;top:-130px;width:14px;height:130px;background:{ink};border-radius:4px;"></div>',
            f'<div class="el" style="left:-56px;top:-230px;width:112px;height:112px;border-radius:50%;background:{palette["accent"]};"></div>',
        ]
    elif kind == "podium":
        children = [f'<div class="el" style="left:-44px;top:-120px;width:88px;height:120px;background:{ink};opacity:.55;border-radius:8px;"></div>']
    elif kind == "book":
        children = [f'<div class="el" style="left:-40px;top:-60px;width:80px;height:60px;background:{palette["card"]};border-radius:6px;"></div>']
    group = "".join(children)
    left = x0
    tween_to = spec.get("to")
    html_ = f'<div class="el" data-id="{gid}" style="left:0;top:{GROUND}px;width:0;height:0;transform-origin:0 0;">{group}</div>'
    if left or tween_to is not None:
        tl.start(gid, x=left)
        if tween_to is not None:
            tl.add(gid, "x", float(tween_to), float(spec.get("at", 0)), float(spec.get("dur", 3)), "linear", frm=left)
    return html_.replace(f'data-id="{gid}"', f'data-id="{gid}" style-x="{left}"', 0)


def _actor(prefix: str, index: int, spec: dict, palette: dict, tl: Timeline) -> str:
    """A stick figure. Its origin is its feet, so it can walk and fall about the feet."""
    ink = palette["ink"]
    gid = f"{prefix}a{index}"
    action = spec.get("action", "stand")
    if action not in ACTIONS:
        action = "stand"
    x0 = float(spec.get("x", 0))
    walking = action == "walk"
    talking = action == "talk"
    waving = action == "wave"
    leg_swing = ' data-swing="26,1.1,{p}"'
    arm_swing = ' data-swing="22,1.1,{p}"'
    limb_style = f"width:6px;background:{ink};border-radius:3px;transform-origin:50% 0;"

    def limb(ident, left, top, height, base, swing=""):
        return (f'<div class="el" data-id="{ident}"{swing} '
                f'style="left:{left}px;top:{top}px;height:{height}px;{limb_style}"></div>')

    children = [
        limb(f"{gid}-ll", -3, -110, 110, 0, leg_swing.format(p=0) if walking else ""),
        limb(f"{gid}-rl", -3, -110, 110, 0, leg_swing.format(p=3.1416) if walking else ""),
        f'<div class="el" style="left:-3px;top:-180px;width:6px;height:72px;background:{ink};border-radius:3px;"></div>',
        f'<div class="el" data-id="{gid}-head" style="left:-26px;top:-246px;width:52px;height:52px;border:6px solid {ink};border-radius:50%;"></div>',
        limb(f"{gid}-la", -3, -170, 86, 0, arm_swing.format(p=0) if walking else ""),
        limb(f"{gid}-ra", -3, -170, 86, 0, arm_swing.format(p=3.1416) if (walking or talking or waving) else ""),
    ]
    label = spec.get("label", "")
    if label:
        children.append(f'<div class="el" style="left:-120px;top:-300px;width:240px;text-align:center;font-size:40px;font-weight:700;color:{ink};">{_esc(label)}</div>')
    html_ = f'<div class="el" data-id="{gid}" style="left:0;top:{GROUND}px;width:0;height:0;transform-origin:0 0;">{"".join(children)}</div>'
    tl.start(f"{gid}-ll", r=-8)
    tl.start(f"{gid}-rl", r=8)
    tl.start(f"{gid}-la", r=24)
    tl.start(f"{gid}-ra", r=-24)
    if talking or waving:
        tl.start(f"{gid}-ra", r=-150 if waving else -110)
    tl.start(gid, x=x0)
    if walking and spec.get("to") is not None:
        tl.add(gid, "x", float(spec["to"]), float(spec.get("at", 0)), float(spec.get("dur", 3)), "linear", frm=x0)
    if action == "fall":
        tl.add(gid, "r", 90, float(spec.get("at", 0)), 0.5, "out", frm=0)
    return html_


def _stage(scene: Scene, duration: float, palette: dict) -> tuple[str, Timeline]:
    tl = Timeline()
    spec = scene.stage or {}
    body = [_background(spec.get("background", "plain"), palette)]
    if scene.heading:
        body.append(f'<div class="el" style="left:120px;top:70px;font-size:76px;font-weight:900;color:{palette["ink"]};">{_esc(scene.heading)}</div>')
    for index, prop in enumerate(spec.get("props", [])):
        body.append(_prop("s", index, prop, palette, tl))
    for index, actor in enumerate(spec.get("actors", [])):
        body.append(_actor("s", index, actor, palette, tl))
    _transitions(tl, duration)
    return "".join(body), tl


TEMPLATES["stage"] = _stage


def scene_page_with_cues(scene: Scene, index: int, title: str, duration: float, cues: list) -> str:
    palette = PALETTES[0] if scene.kind == "title" else PALETTES[index % len(PALETTES)]
    body, timeline = TEMPLATES[scene.kind](scene, duration, palette)
    return _wrapper_page(palette, body, timeline, duration, title, cues=cues)
