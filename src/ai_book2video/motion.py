"""Motion graphics for phone (portrait) video.

Each scene is an animated HTML page driven by a timeline. The page exposes window.setT(t);
the renderer calls it once per frame with t in seconds, so every frame is deterministic.

Canvas: 1080 x 1920 (9:16). Script x positions are written for a 1920-wide stage and are
scaled to the portrait width with STAGE_SCALE, so the same scene scripts work.

Animations are tweens on element properties: x, y (px), s (scale), sx (scale X),
r (rotation, deg), o (opacity), and two text properties: chars (typewriter) and count (number).
Limbs can swing with data-swing="amplitude,period,phase" (degrees, seconds, radians).
"""

from __future__ import annotations

import html
import json
import math
import re
from dataclasses import dataclass, field

from ai_book2video.script import Scene

WIDTH = 1080
HEIGHT = 1920
STAGE_SCALE = WIDTH / 1920
GROUND = 1240
CAPTION_TOP = 1420
PAD = 70

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
  for (const id in ELS) state[id] = Object.assign({ x: 0, y: 0, s: 1, sx: 1, sy: 1, r: 0, o: 1, chars: 0, count: 0 }, INIT[id] || {});
  for (const a of ANIMS) {
    if (t < a.at) continue;
    const st = state[a.id];
    if (!st) continue;
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
    let sy = st.sy;
    const bl = el.dataset.blink;
    if (bl) { const [period, phase] = bl.split(',').map(Number); if (((t + phase) % period) < 0.13) sy *= 0.12; }
    let op = st.o;
    const fp = el.dataset.flap;
    if (fp) { const period = Number(fp); if ((t % period) >= period / 2) op = 0; }
    el.style.transform = `translate(${st.x}px, ${y}px) rotate(${rot}deg) scale(${st.s}) scaleX(${st.sx}) scaleY(${sy})`;
    el.style.opacity = String(Math.max(0, Math.min(1, op)));
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
  if (!box) return;
  const en = document.getElementById('cap-en');
  const zh = document.getElementById('cap-zh');
  let cur = null;
  for (const c of CUES) { if (t >= c[0] && t < c[1]) { cur = c; break; } }
  const op = cur ? Math.min(1, (t - cur[0]) / 0.2, (cur[1] - t) / 0.2) : 0;
  const enText = cur ? cur[2] : '';
  const zhText = cur ? cur[3] : '';
  if (en.textContent !== enText) {
    en.textContent = enText;
    en.style.fontSize = enText.length > 150 ? '38px' : enText.length > 95 ? '44px' : '50px';
  }
  if (zh.textContent !== zhText) {
    zh.textContent = zhText;
    zh.style.fontSize = zhText.length > 60 ? '34px' : zhText.length > 40 ? '38px' : '42px';
  }
  box.style.opacity = String(Math.max(0, op));
}
window.setT = (t) => { apply(t); captions(t); };
apply(0);
captions(0);
"""

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: %(w)dpx; height: %(h)dpx; overflow: hidden; }
body { background: %(bg)s; font-family: "Noto Sans", "Noto Sans CJK SC", "DejaVu Sans", "Helvetica Neue", Arial, sans-serif; }
#stage { position: relative; width: %(w)dpx; height: %(h)dpx; overflow: hidden; background: %(bg)s; }
.el { position: absolute; will-change: transform, opacity; white-space: nowrap; }
.word { display: inline-block; margin-right: 0.22em; will-change: transform, opacity; }
.heavy { font-weight: 900; letter-spacing: -0.01em; }
.origin-left { transform-origin: left center; }
.wrap { white-space: normal; }
.card { border-radius: 36px; display: flex; align-items: center; padding: 0 44px; }
.disc { border-radius: 50%%; }
#caption { position: absolute; left: %(pad)dpx; right: %(pad)dpx; top: %(cap)dpx; text-align: center; color: #ffffff;
  pointer-events: none; opacity: 0; }
#caption .box { display: inline-block; max-width: 100%%; background: rgba(0, 0, 0, 0.74); padding: 26px 36px 28px;
  border-radius: 28px; }
#cap-en { display: block; font-size: 50px; font-weight: 800; line-height: 1.25; white-space: normal; }
#cap-zh { display: block; font-size: 42px; font-weight: 600; line-height: 1.35; margin-top: 14px; color: #ffe9a8; white-space: normal;
  font-family: "Noto Sans CJK SC", "Noto Sans", sans-serif; }
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


def _sx(x: float) -> float:
    """Script x (written for a 1920-wide stage) to portrait pixels."""
    return float(x) * STAGE_SCALE


def _heading_size(text: str, big: int = 118, mid: int = 98, small: int = 80) -> int:
    length = len(text)
    if length <= 16:
        return big
    if length <= 36:
        return mid
    return small


def _heading_lines(text: str, size: int, width: int = WIDTH - 2 * PAD) -> int:
    return max(1, math.ceil(len(text) * 0.58 * size / width))


def _words_html(prefix: str, text: str, size: int, color: str, weight: str = "heavy") -> tuple[str, list[str]]:
    ids: list[str] = []
    spans: list[str] = []
    for index, word in enumerate(text.split()):
        ident = f"{prefix}{index}"
        ids.append(ident)
        spans.append(f'<span class="el word {weight}" data-id="{ident}" style="position:relative;font-size:{size}px;color:{color};">{_esc(word)}</span>')
    return " ".join(spans), ids


def _enter_words(timeline: Timeline, ids: list[str], start: float, step: float, lift: int = 150, dur: float = 0.7) -> None:
    for index, ident in enumerate(ids):
        at = start + index * step
        timeline.start(ident, y=lift, o=0)
        timeline.add(ident, "y", 0, at, dur, "back")
        timeline.add(ident, "o", 1, at, dur * 0.5, "out")


def _transitions(timeline: Timeline, duration: float) -> None:
    timeline.start("wipe-out", x=0)
    timeline.add("wipe-out", "x", -WIDTH - 200, 0.0, 0.75, "inOut", frm=0)
    timeline.start("wipe-in", x=WIDTH + 200)
    timeline.add("wipe-in", "x", 0, max(0.0, duration - 0.7), 0.6, "inOut", frm=WIDTH + 200)


def _header(book: str, chapter: str, palette: dict) -> str:
    """Top-left label on every scene: the book's English title and the chapter number."""
    if not book and not chapter:
        return ""
    badge = (f'<span style="display:inline-block;background:{palette["accent"]};color:#000;font-weight:900;'
             f'font-size:40px;padding:6px 22px;border-radius:14px;margin-right:18px;">CH {_esc(chapter)}</span>') if chapter else ""
    name = f'<span style="font-size:36px;font-weight:700;">{_esc(book)}</span>' if book else ""
    return (f'<div class="el" data-id="header" style="left:{PAD}px;top:56px;max-width:{WIDTH - 2 * PAD}px;white-space:normal;'
            f'background:rgba(0,0,0,0.55);color:#ffffff;padding:14px 24px;border-radius:20px;line-height:1.3;">'
            f'{badge}{name}</div>')


def _wrapper_page(palette: dict, body: str, timeline: Timeline, duration: float, title: str, cues=None, book: str = "", chapter: str = "") -> str:
    css = CSS % {"w": WIDTH, "h": HEIGHT, "bg": palette["bg"], "pad": PAD, "cap": CAPTION_TOP}
    body = _header(book, chapter, palette) + body
    anims = json.dumps(timeline.sorted_anims())
    init = json.dumps(timeline.init)
    panel = f"background:{palette['accent']};"
    start = f'<div class="el" data-id="wipe-out" style="left:0;top:0;width:{WIDTH}px;height:{HEIGHT}px;{panel}"></div>'
    end = f'<div class="el" data-id="wipe-in" style="left:0;top:0;width:{WIDTH}px;height:{HEIGHT}px;{panel}"></div>'
    caption = '<div id="caption"><div class="box"><span id="cap-en"></span><span id="cap-zh"></span></div></div>'
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{_esc(title)}</title><style>{css}</style></head><body>"
        f"<div id='stage'>{body}{caption}{start}{end}</div>"
        f"<script>const ANIMS = {anims}; const INIT = {init}; const DURATION = {duration:.3f}; "
        f"const CUES = {json.dumps(cues or [], ensure_ascii=False)};\n{ENGINE}</script>"
        "</body></html>"
    )


# ---------------------------------------------------------------------------
# Scene templates. Each returns (body html, timeline).
# ---------------------------------------------------------------------------


def _title(scene: Scene, duration: float, palette: dict) -> tuple[str, Timeline]:
    tl = Timeline()
    body = []
    body.append(f'<div class="el disc" data-id="c1" data-float="22,7,0" style="left:-260px;top:700px;width:900px;height:900px;background:{palette["accent"]};"></div>')
    body.append(f'<div class="el disc" data-id="c2" data-float="16,5.5,1.2" style="left:700px;top:-180px;width:560px;height:560px;background:{palette["card"]};"></div>')
    tl.start("c1", s=0)
    tl.start("c2", s=0)
    tl.add("c1", "s", 1, 0.1, 0.9, "back")
    tl.add("c2", "s", 1, 0.25, 0.9, "back")
    body.append(f'<div class="el card heavy" data-id="tag" style="left:{PAD}px;top:230px;height:90px;background:{palette["card"]};color:{palette["card_ink"]};font-size:40px;"><span>EXPLAINER</span></div>')
    tl.start("tag", o=0, r=-5)
    tl.add("tag", "o", 1, 0.05, 0.3)
    tl.add("tag", "s", 1, 0.05, 0.5, "back", frm=0.6)
    size = _heading_size(scene.heading, big=150, mid=124, small=104)
    words, ids = _words_html("h", scene.heading, size, palette["ink"])
    body.append(f'<div class="el wrap" data-id="heading" style="left:{PAD}px;top:430px;width:{WIDTH - 2 * PAD}px;line-height:1.04;">{words}</div>')
    _enter_words(tl, ids, 0.35, 0.14, lift=180, dur=0.75)
    if scene.body:
        top = 430 + _heading_lines(scene.heading, size) * size * 1.05 + 40
        body.append(
            f'<div class="el wrap" data-id="sub" data-text="{_esc(scene.body)}" '
            f'style="left:{PAD}px;top:{top}px;width:{WIDTH - 2 * PAD}px;font-size:56px;color:{palette["card_ink"]};font-weight:700;'
            f'background:{palette["card"]};padding:18px 30px;border-radius:26px;">{_esc(scene.body)}</div>'
        )
        tl.start("sub", o=1)
        tl.add("sub", "chars", len(scene.body), 1.5, min(2.4, 0.04 * len(scene.body)), "linear", frm=0)
    _transitions(tl, duration)
    return "".join(body), tl


def _text(scene: Scene, duration: float, palette: dict) -> tuple[str, Timeline]:
    tl = Timeline()
    body = []
    size = _heading_size(scene.heading)
    words, ids = _words_html("h", scene.heading, size, palette["ink"])
    rule = f'<div class="el origin-left" data-id="rule" style="position:relative;display:block;margin-top:30px;width:520px;height:22px;background:{palette["accent"]};border-radius:11px;"></div>'
    body.append(f'<div class="el wrap" data-id="head-block" style="left:{PAD}px;top:240px;width:{WIDTH - 2 * PAD}px;line-height:1.04;">'
                f'<div style="position:relative;">{words}</div>{rule}</div>')
    _enter_words(tl, ids, 0.25, 0.12, lift=140, dur=0.65)
    tl.start("rule", sx=0)
    tl.add("rule", "sx", 1, 0.9, 0.6, "out")
    body.append(f'<div class="el disc" data-id="spin" style="left:{WIDTH - 300}px;top:820px;width:230px;height:230px;background:{palette["accent"]};border-radius:44px;"></div>')
    tl.start("spin", r=0)
    tl.add("spin", "r", 360, 0.0, duration, "linear")
    _transitions(tl, duration)
    return "".join(body), tl


def _bullets(scene: Scene, duration: float, palette: dict) -> tuple[str, Timeline]:
    tl = Timeline()
    body = []
    size = _heading_size(scene.heading, big=116, mid=98, small=84)
    words, ids = _words_html("h", scene.heading, size, palette["ink"])
    body.append(f'<div class="el wrap" data-id="heading" style="left:{PAD}px;top:220px;width:{WIDTH - 2 * PAD}px;line-height:1.04;">{words}</div>')
    _enter_words(tl, ids, 0.2, 0.1, lift=120, dur=0.6)
    count = max(1, len(scene.items))
    span = max(0.0, duration - 2.2)
    step = min(0.9, max(0.35, span / count))
    top0 = 220 + _heading_lines(scene.heading, size) * size * 1.06 + 90
    gap = 200
    for index, item in enumerate(scene.items):
        ident = f"b{index}"
        left_side = index % 2 == 0
        top = top0 + index * gap
        body.append(
            f'<div class="el card" data-id="{ident}" style="left:{PAD}px;top:{top}px;width:{WIDTH - 2 * PAD}px;min-height:150px;padding:20px 36px;background:{palette["card"]};color:{palette["card_ink"]};">'
            f'<div class="el" data-id="{ident}n" style="position:relative;flex:0 0 auto;width:86px;height:86px;border-radius:50%;margin-right:30px;'
            f'background:{palette["accent"]};color:#000;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:46px;">{index + 1}</div>'
            f'<span style="font-size:50px;font-weight:700;white-space:normal;line-height:1.22;">{_esc(item)}</span></div>'
        )
        at = 0.9 + index * step
        tl.start(ident, x=(-600 if left_side else 600), o=0)
        tl.add(ident, "x", 0, at, 0.75, "back")
        tl.add(ident, "o", 1, at, 0.3)
    _transitions(tl, duration)
    return "".join(body), tl


def _quote(scene: Scene, duration: float, palette: dict) -> tuple[str, Timeline]:
    tl = Timeline()
    body = []
    body.append(f'<div class="el heavy" data-id="mark" style="left:{PAD}px;top:300px;font-size:420px;line-height:1;color:{palette["accent"]};">&ldquo;</div>')
    tl.start("mark", s=0)
    tl.add("mark", "s", 1, 0.1, 0.6, "back")
    words = scene.body.split()
    spans: list[str] = []
    ids: list[str] = []
    for index, word in enumerate(words):
        ident = f"q{index}"
        ids.append(ident)
        spans.append(f'<span class="el word" data-id="{ident}" style="position:relative;font-size:78px;font-style:italic;font-weight:700;color:{palette["ink"]};">{_esc(word)}</span>')
    body.append(f'<div class="el wrap" data-id="quote" style="left:{PAD + 40}px;top:640px;width:{WIDTH - 2 * PAD - 60}px;line-height:1.3;">' + " ".join(spans) + "</div>")
    span = max(0.0, duration * 0.6 - 0.6)
    step = min(0.16, max(0.05, span / max(1, len(words))))
    for index, ident in enumerate(ids):
        at = 0.6 + index * step
        tl.start(ident, y=50, o=0)
        tl.add(ident, "y", 0, at, 0.35)
        tl.add(ident, "o", 1, at, 0.25)
    if scene.source:
        body.append(f'<div class="el" data-id="by" style="left:{PAD + 40}px;top:1080px;font-size:44px;font-weight:600;color:{palette["ink"]};opacity:.8;">— {_esc(scene.source)}</div>')
        tl.start("by", x=-200, o=0)
        tl.add("by", "x", 0, duration * 0.7, 0.6)
        tl.add("by", "o", 1, duration * 0.7, 0.5)
    _transitions(tl, duration)
    return "".join(body), tl


def _stat(scene: Scene, duration: float, palette: dict) -> tuple[str, Timeline]:
    tl = Timeline()
    body = []
    body.append(f'<div class="el disc" data-id="burst" style="left:{WIDTH // 2 - 330}px;top:520px;width:660px;height:660px;background:{palette["accent"]};"></div>')
    tl.start("burst", s=0)
    tl.add("burst", "s", 1, 0.05, 0.8, "back")
    body.append(f'<div class="el disc" data-id="ring" style="left:{WIDTH // 2 - 390}px;top:460px;width:780px;height:780px;border:10px solid {palette["card"]};"></div>')
    tl.start("ring", o=0, s=0.8)
    tl.add("ring", "o", 0.9, 0.1, 0.5)
    tl.add("ring", "s", 1, 0.1, 0.9, "out")
    number = scene.value if scene.value is not None else 0
    dec = 0 if float(number).is_integer() else 1
    shown = f"{scene.prefix}{int(number) if dec == 0 else number}{scene.suffix}"
    number_size = int(min(230, (WIDTH - 2 * PAD) / max(1, 0.6 * len(shown))))
    body.append(
        f'<div class="el heavy" data-id="num" data-prefix="{_esc(scene.prefix)}" data-suffix="{_esc(scene.suffix)}" data-dec="{dec}" '
        f'style="left:0;top:{800 - number_size // 2}px;width:{WIDTH}px;text-align:center;font-size:{number_size}px;color:{palette["ink"]};white-space:nowrap;">'
        f"{_esc(scene.prefix)}0{_esc(scene.suffix)}</div>"
    )
    tl.start("num", o=1)
    tl.add("num", "count", float(number), 0.35, min(2.0, max(1.0, duration * 0.4)), "out", frm=0)
    label = scene.heading or scene.body
    body.append(f'<div class="el wrap" data-id="label" style="left:{PAD}px;top:1040px;width:{WIDTH - 2 * PAD}px;text-align:center;font-size:66px;font-weight:700;color:{palette["ink"]};">{_esc(label)}</div>')
    tl.start("label", y=60, o=0)
    tl.add("label", "y", 0, 2.2, 0.6, "back")
    tl.add("label", "o", 1, 2.2, 0.5)
    _transitions(tl, duration)
    return "".join(body), tl


# ---------------------------------------------------------------------------
# Stick-figure stage. Script x (1920-based) is scaled to the portrait width;
# the ground sits at GROUND pixels from the top.
# ---------------------------------------------------------------------------

BACKGROUNDS = ("street", "field", "room", "plain")
PROPS = ("car", "tree", "sun", "fire", "building", "podium", "book")
ACTIONS = ("stand", "walk", "fall", "talk", "wave")


def _background(kind: str, palette: dict) -> str:
    ground = "rgba(0,0,0,0.12)"
    shade = "rgba(0,0,0,0.10)"
    parts = [f'<div class="el" style="left:0;top:{GROUND}px;width:{WIDTH}px;height:{HEIGHT - GROUND}px;background:{ground};"></div>']
    if kind == "street":
        for x, w, h in ((40, 300, 760), (360, 220, 560), (640, 260, 880), (930, 200, 620)):
            parts.append(f'<div class="el" style="left:{x}px;top:{GROUND - h}px;width:{w}px;height:{h}px;background:{shade};border-radius:8px;"></div>')
        for x in range(60, WIDTH, 200):
            parts.append(f'<div class="el" style="left:{x}px;top:{GROUND + 110}px;width:90px;height:10px;background:{palette["ink"]};opacity:.35;"></div>')
    elif kind == "field":
        parts.append(f'<div class="el" style="left:-300px;top:{GROUND - 220}px;width:1000px;height:520px;border-radius:50%;background:{shade};"></div>')
        parts.append(f'<div class="el" style="left:500px;top:{GROUND - 170}px;width:1000px;height:480px;border-radius:50%;background:{shade};"></div>')
    elif kind == "room":
        parts.append(f'<div class="el" style="left:{PAD}px;top:420px;width:{WIDTH - 2 * PAD}px;height:{GROUND - 420}px;background:{shade};border-radius:14px;"></div>')
    return "".join(parts)


def _prop(prefix: str, index: int, spec: dict, palette: dict, tl: Timeline) -> str:
    kind = spec["type"]
    gid = f"{prefix}p{index}"
    ink = palette["ink"]
    x0 = _sx(spec.get("x", 0))
    y0 = float(spec.get("y", 0))
    if kind == "sun":
        return f'<div class="el" data-id="{gid}" data-float="12,5,0" style="left:{x0 - 90:.0f}px;top:{y0 + 260 - 90:.0f}px;width:180px;height:180px;border-radius:50%;background:{palette["accent"]};"></div>'
    if kind == "fire":
        return (f'<div class="el" data-id="{gid}" data-float="8,0.7,{index}" style="left:{x0 - 50:.0f}px;top:{GROUND - 110}px;width:100px;height:110px;'
                f'border-radius:50% 50% 40% 40%;background:{palette["accent"]};"></div>')
    if kind == "building":
        w = int(_sx(spec.get("w", 200)))
        h = int(spec.get("h", 400))
        return f'<div class="el" data-id="{gid}" style="left:{x0:.0f}px;top:{GROUND - h}px;width:{w}px;height:{h}px;background:{ink};opacity:.18;border-radius:8px;"></div>'
    children: list[str] = []
    if kind == "car":
        children = [
            f'<div class="el" style="left:-150px;top:-150px;width:300px;height:92px;background:{palette["card"]};border-radius:26px;"></div>',
            f'<div class="el" style="left:-90px;top:-212px;width:176px;height:72px;background:{palette["card"]};border-radius:22px;"></div>',
            f'<div class="el" style="left:-118px;top:-74px;width:74px;height:74px;border-radius:50%;background:{ink};"></div>',
            f'<div class="el" style="left:44px;top:-74px;width:74px;height:74px;border-radius:50%;background:{ink};"></div>',
        ]
    elif kind == "tree":
        children = [
            f'<div class="el" style="left:-8px;top:-150px;width:16px;height:150px;background:{ink};border-radius:4px;"></div>',
            f'<div class="el" style="left:-64px;top:-270px;width:128px;height:128px;border-radius:50%;background:{palette["accent"]};"></div>',
        ]
    elif kind == "podium":
        children = [f'<div class="el" style="left:-50px;top:-140px;width:100px;height:140px;background:{ink};opacity:.55;border-radius:10px;"></div>']
    elif kind == "book":
        children = [f'<div class="el" style="left:-46px;top:-70px;width:92px;height:70px;background:{palette["card"]};border-radius:8px;"></div>']
    group = "".join(children)
    left = x0
    tween_to = spec.get("to")
    html_ = f'<div class="el" data-id="{gid}" style="left:0;top:{GROUND}px;width:0;height:0;transform-origin:0 0;">{group}</div>'
    if left or tween_to is not None:
        tl.start(gid, x=left)
        if tween_to is not None:
            tl.add(gid, "x", _sx(tween_to), float(spec.get("at", 0)), float(spec.get("dur", 3)), "linear", frm=left)
    return html_


def _actor(prefix: str, index: int, spec: dict, palette: dict, tl: Timeline) -> str:
    """A stick figure. Its origin is its feet, so it can walk and fall about the feet."""
    ink = palette["ink"]
    gid = f"{prefix}a{index}"
    action = spec.get("action", "stand")
    if action not in ACTIONS:
        action = "stand"
    x0 = _sx(spec.get("x", 0))
    walking = action == "walk"
    talking = action == "talk"
    waving = action == "wave"
    limb_style = f"width:8px;background:{ink};border-radius:4px;transform-origin:50% 0;"

    def limb(ident: str, top: int, height: int, swing: str = "") -> str:
        return f'<div class="el" data-id="{ident}"{swing} style="left:-4px;top:{top}px;height:{height}px;{limb_style}"></div>'

    def swing(amp: int, phase: float) -> str:
        return f' data-swing="{amp},1.1,{phase}"'

    children = [
        limb(f"{gid}-ll", -130, 130, swing(26, 0) if walking else ""),
        limb(f"{gid}-rl", -130, 130, swing(26, 3.1416) if walking else ""),
        f'<div class="el" style="left:-4px;top:-210px;width:8px;height:86px;background:{ink};border-radius:4px;"></div>',
        f'<div class="el" data-id="{gid}-head" style="left:-32px;top:-290px;width:64px;height:64px;border:8px solid {ink};border-radius:50%;"></div>',
        limb(f"{gid}-la", -200, 100, swing(22, 0) if walking else ""),
        limb(f"{gid}-ra", -200, 100, swing(22, 3.1416) if (walking or talking or waving) else ""),
    ]
    label = spec.get("label", "")
    if label:
        children.append(f'<div class="el" style="left:-150px;top:-380px;width:300px;text-align:center;font-size:46px;font-weight:700;color:{ink};">{_esc(label)}</div>')
    html_ = f'<div class="el" data-id="{gid}" style="left:0;top:{GROUND}px;width:0;height:0;transform-origin:0 0;">{"".join(children)}</div>'
    tl.start(f"{gid}-ll", r=-8)
    tl.start(f"{gid}-rl", r=8)
    tl.start(f"{gid}-la", r=24)
    tl.start(f"{gid}-ra", r=-24)
    if talking or waving:
        tl.start(f"{gid}-ra", r=-150 if waving else -110)
    tl.start(gid, x=x0)
    if walking and spec.get("to") is not None:
        tl.add(gid, "x", _sx(spec["to"]), float(spec.get("at", 0)), float(spec.get("dur", 3)), "linear", frm=x0)
    if action == "fall":
        tl.add(gid, "r", 90, float(spec.get("at", 0)), 0.5, "out", frm=0)
    return html_


def _stage(scene: Scene, duration: float, palette: dict, cues: list | None = None, camera: str = "classic") -> tuple[str, Timeline]:
    """Stick-figure stage. SVG by default (colourful, hand-drawn look); "style": "html" uses the old divs."""
    spec = scene.stage or {}
    if spec.get("style", "svg") != "html":
        from ai_book2video import svgstage

        tl = Timeline()
        svg = svgstage.stage(scene, palette, tl, cues or [], duration, camera)
        heading = ""
        if scene.heading:
            size = _heading_size(scene.heading, big=110, mid=92, small=76)
            heading = (f'<div class="el wrap" data-id="stage-heading" style="left:{PAD}px;top:230px;width:{WIDTH - 2 * PAD}px;font-size:{size}px;'
                       f'font-weight:900;line-height:1.08;color:{palette["ink"]};text-shadow:0 4px 0 rgba(0,0,0,0.25);">{_esc(scene.heading)}</div>')
            fade_at = min(3.5, float(cues[1][0])) if cues and len(cues) > 1 else 3.5
            tl.start("stage-heading", o=1)
            tl.add("stage-heading", "o", 0, fade_at, 0.5)
        _transitions(tl, duration)
        return svg + heading, tl
    tl = Timeline()
    body = [_background(spec.get("background", "plain"), palette)]
    if scene.heading:
        size = _heading_size(scene.heading, big=110, mid=92, small=76)
        body.append(f'<div class="el wrap" style="left:{PAD}px;top:230px;width:{WIDTH - 2 * PAD}px;font-size:{size}px;font-weight:900;line-height:1.08;color:{palette["ink"]};">{_esc(scene.heading)}</div>')
    for index, prop in enumerate(spec.get("props", [])):
        body.append(_prop("s", index, prop, palette, tl))
    for index, actor in enumerate(spec.get("actors", [])):
        body.append(_actor("s", index, actor, palette, tl))
    _transitions(tl, duration)
    return "".join(body), tl


TEMPLATES = {"title": _title, "text": _text, "bullets": _bullets, "quote": _quote, "stat": _stat, "stage": _stage}


def _luminance(colour: str) -> float:
    channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _readable_on(colour: str) -> str:
    """Near-black or white, whichever has more contrast on the colour."""
    lum = _luminance(colour)
    return "#111111" if (lum + 0.05) / 0.05 > 1.05 / (lum + 0.05) else "#ffffff"


def complete_palette(palette: dict) -> dict:
    """Fill in text colours for a custom palette from a script's "palettes" list."""
    full = dict(palette)
    full.setdefault("ink", _readable_on(full["bg"]))
    full.setdefault("card_ink", _readable_on(full["card"]))
    return full


def _pick(scene: Scene, index: int, palettes: list[dict] | None = None) -> dict:
    if palettes:
        return complete_palette(palettes[0] if scene.kind == "title" else palettes[index % len(palettes)])
    return PALETTES[0] if scene.kind == "title" else PALETTES[index % len(PALETTES)]


def scene_page(scene: Scene, index: int, title: str, duration: float, cues: list | None = None, book: str = "", chapter: str = "",
               palettes: list[dict] | None = None, camera: str = "classic") -> str:
    """Full HTML page for one scene. `cues` is a list of [start, end, english, chinese] in scene seconds.
    `palettes` replaces the built-in colour sets (scenes take them in turn)."""
    palette = _pick(scene, index, palettes)
    if scene.kind == "stage":
        body, timeline = _stage(scene, duration, palette, cues, camera)
    else:
        body, timeline = TEMPLATES[scene.kind](scene, duration, palette)
    return _wrapper_page(palette, body, timeline, duration, title, cues=cues, book=book, chapter=chapter)
