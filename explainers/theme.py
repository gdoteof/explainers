"""The look every video shares: the paper, the palette, the type, and the label that says what kind of
statement is being made.

The two sides of an argument get SIDE_A and SIDE_B, mustard and teal, and never red and blue: red is the
left's colour in most of the world and the right's in the United States, so either choice would tell half
the audience the wrong thing before a word is said.
"""
from functools import lru_cache

import numpy as np
import skia

from explainers import draw as D
from explainers.anim import back, clamp, ease_out, ramp, smooth

W, H = 1920, 1080

PAPER = (245, 240, 229)
PAPER_DARK = (232, 225, 210)
INK = (34, 30, 42)
INK_SOFT = (96, 90, 104)
RULE = (206, 198, 182)
WHITE = (255, 253, 247)

SIDE_A = (226, 160, 36)         # mustard
SIDE_A_DARK = (176, 118, 16)
SIDE_B = (32, 140, 134)         # teal
SIDE_B_DARK = (20, 100, 98)
HOST = (112, 86, 204)           # the host's purple, and the channel's
ALERT = (214, 88, 60)

# What the label says for each kind of statement, and its colour. A `line` makes no claim and gets no label.
KIND = {
    "fact": ("FACT", INK),
    "estimate": ("ESTIMATE", (92, 100, 116)),
    "view": ("A VIEW", SIDE_B_DARK),
    "opinion": ("MY OPINION", HOST),
    "speculation": ("A GUESS", ALERT),
}


@lru_cache(maxsize=4)
def paper(w=W, h=H, colour=PAPER):
    """The background: flat paper with a little tooth and darker edges, as a skia.Image."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    edge = ((xx / w - 0.5) ** 2 + (yy / h - 0.5) ** 2) * 0.16
    tooth = D.grain(w, h, seed=7, scale=2, lo=-1.0, hi=1.0) * 2.2 + D.grain(w, h, seed=8, scale=1, lo=-1.0, hi=1.0) * 1.4
    rgb = np.asarray(colour, np.float32)[None, None, :] * (1 - edge[..., None]) + tooth[..., None]
    return D.from_array(np.clip(rgb, 0, 255).astype(np.uint8))


def stage(colour=PAPER):
    """A new frame: (surface, canvas), with the paper down."""
    s = D.surface(W, H)
    c = s.getCanvas()
    c.drawImage(paper(W, H, colour), 0, 0)
    return s, c


def tag_width(kind, size=30):
    name = KIND[kind][0]
    return D.text_width(name, D.font("black", size)) + size * 0.05 * (len(name) - 1) + size * 1.6


def tag(c, kind, x, y, size=30, k=1.0):
    """The pill that names a kind of statement, its left end at x and its baseline at y. `k` scales it
    about its left end, for popping it in. Returns its width."""
    name, colour = KIND[kind]
    fnt = D.font("black", size)
    track = size * 0.05
    w = tag_width(kind, size)
    h = size * 1.94
    with D.moved(c, s=k, about=(x, y - size * 0.34)):
        c.drawPath(D.rect(x, y - size * 1.33, x + w, y - size * 1.33 + h, h / 2), D.fill(colour))
        D.text(c, name, x + size * 0.8, y, fnt, D.fill(WHITE), track=track)
    return w


def label(c, kind, cite="", age=1.0, x=64, y=998, out=1.0, plate=0.0):
    """The statement label, bottom left: FACT with its source, or MY OPINION, or A GUESS. `age` is seconds
    since this label came up (it pops in), `out` fades it (1 shown, 0 gone). `plate` (0..1) lays a strip
    of paper under it, for a label that is over a set and not over the bare paper."""
    if kind not in KIND or out <= 0 or age <= 0:
        return
    with D.layer(c, out * clamp(age / 0.12)):
        reveal = ease_out(ramp(age, 0.15, 0.4))
        if plate > 0:
            right = x + tag_width(kind) + 22
            if cite:
                right += (D.text_width(cite, D.font("medium", 30)) + 20) * reveal
            strip = D.rect(x - 16, y - 58, right, y + 36, 47)
            c.drawPath(D.xf(strip, 3, 5), D.blurred(D.fill(INK, 0.22 * plate), 8))
            c.drawPath(strip, D.fill(PAPER, 0.96 * plate))
        w = tag(c, kind, x, y, 30, 0.6 + 0.4 * back(ramp(age, 0, 0.28), 1.4))
        if cite:
            c.save()
            c.clipRect(skia.Rect.MakeLTRB(x + w, y - 50, x + w + 1500 * reveal, y + 24))
            D.text(c, cite, x + w + 20 - 24 * (1 - reveal), y, D.font("medium", 30), D.fill(INK_SOFT))
            c.restore()


def narration_label(c, n, sources, t, **kw):
    """The label for whatever the narration is saying at t: up when a labelled beat starts, down a moment
    after its last word unless the next beat is the same kind of statement from the same sources."""
    b = n.beat_at(t)
    if b is None or b.kind not in KIND:
        return
    i = n.beats.index(b)
    same = lambda a, o: a.kind == o.kind and a.sources == o.sources
    first = b
    while i > 0 and same(n.beats[i - 1], first) and first.t0 - n.beats[i - 1].t1 < 2.5:
        i -= 1
        first = n.beats[i]
    j = n.beats.index(b)
    carries = j + 1 < len(n.beats) and same(n.beats[j + 1], b) and n.beats[j + 1].t0 - b.t1 < 2.5
    out = 1.0 if carries else 1 - smooth(ramp(t, b.t1 + 0.45, 0.3))
    cite = " · ".join(sources[key].cite for key in b.sources if key in sources)
    label(c, b.kind, cite, age=t - first.t0, out=out, **kw)


def heading(c, s, x, y, size=84, colour=INK, align="l", font="black", alpha=1.0):
    return D.text(c, s, x, y, D.font(font, size), D.fill(colour, alpha), align, track=-size * 0.02)


def body(c, s, x, y, width, size=40, colour=INK, font="medium", align="l", leading=1.32):
    return D.paragraph(c, s, x, y, D.font(font, size), D.fill(colour), width, leading, align)


def scenes(c, t, cuts, fade=0.5):
    """Draw the scene that is on at t. `cuts` is [(start, draw(c, t)), ...] in order; at each cut the old
    scene fades to the paper over half of `fade` and the new one comes up over the other half."""
    i = max((k for k, (start, _) in enumerate(cuts) if t >= start - fade / 2), default=0)
    start, scene = cuts[i]
    up = smooth(ramp(t, start, fade / 2)) if i else 1.0
    if t < start:                                         # the last moments of the scene before
        scene, up = cuts[i - 1][1], 1 - smooth(ramp(t, start - fade / 2, fade / 2))
    if up >= 1:
        scene(c, t)
    elif up > 0:
        with D.layer(c, up):
            scene(c, t)
