"""Skia, the way the videos use it: a canvas, smooth paths from a few points, type, and the way out to bytes.

Coordinates are pixels of the frame, y down. Colours are (r, g, b), (r, g, b, a) or "#rrggbb".
"""
import math
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

import numpy as np
import skia

FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONTS = {
    "regular": "Inter-Regular.otf",
    "medium": "Inter-Medium.otf",
    "semi": "Inter-SemiBold.otf",
    "bold": "Inter-Bold.otf",
    "extra": "Inter-ExtraBold.otf",
    "black": "Inter-Black.otf",
    "serif": "PTSerif-Regular.ttf",
    "serif-italic": "PTSerif-Italic.ttf",
    "serif-bold": "PTSerif-Bold.ttf",
}


# --- canvas -------------------------------------------------------------------------------------

def surface(w, h, clear=None):
    s = skia.Surface(w, h)
    if clear is not None:
        s.getCanvas().clear(rgb(clear))
    return s


def array(surf):
    """The surface as an (h, w, 4) uint8 RGBA array."""
    return surf.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)


def from_array(a):
    """An (h, w, 3 or 4) uint8 array as a skia.Image."""
    a = np.asarray(a)
    if a.shape[2] == 3:
        a = np.dstack([a, np.full(a.shape[:2], 255, np.uint8)])
    return skia.Image.fromarray(np.ascontiguousarray(a), colorType=skia.kRGBA_8888_ColorType)


@contextmanager
def layer(canvas, alpha=1.0):
    """Everything drawn inside fades as one picture, so overlapping shapes don't show through each other."""
    canvas.saveLayer(None, skia.Paint(Alphaf=max(0.0, min(1.0, alpha))))
    try:
        yield canvas
    finally:
        canvas.restore()


@contextmanager
def moved(canvas, x=0.0, y=0.0, s=1.0, rot=0.0, about=(0.0, 0.0)):
    """Everything drawn inside is scaled and turned (degrees) about a point, then moved."""
    canvas.save()
    canvas.concat(matrix(x, y, s, rot, about=about))
    try:
        yield canvas
    finally:
        canvas.restore()


# --- paint --------------------------------------------------------------------------------------

def rgb(c, a=1.0):
    """A skia colour, with alpha 0..1."""
    if isinstance(c, str):
        c = tuple(int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    if len(c) == 4:
        a *= c[3] / 255
    return skia.Color(int(round(c[0])), int(round(c[1])), int(round(c[2])), int(round(255 * max(0.0, min(1.0, a)))))


def fill(c, a=1.0, **kw):
    return skia.Paint(AntiAlias=True, Color=rgb(c, a), **kw)


def stroke(c, w, a=1.0, cap="round", join="round", **kw):
    caps = {"round": skia.Paint.kRound_Cap, "butt": skia.Paint.kButt_Cap, "square": skia.Paint.kSquare_Cap}
    joins = {"round": skia.Paint.kRound_Join, "miter": skia.Paint.kMiter_Join, "bevel": skia.Paint.kBevel_Join}
    return skia.Paint(AntiAlias=True, Color=rgb(c, a), Style=skia.Paint.kStroke_Style, StrokeWidth=w,
                      StrokeCap=caps[cap], StrokeJoin=joins[join], **kw)


def blurred(paint, radius):
    """The paint, soft: for a shadow or a glow."""
    paint.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, radius))
    return paint


def mix(a, b, k):
    """Colour a moved a fraction k of the way to colour b."""
    return tuple(x + (y - x) * k for x, y in zip(a, b))


# --- paths --------------------------------------------------------------------------------------

def poly(pts, closed=True):
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    if closed:
        p.close()
    return p


def curve(pts, closed=True, tension=0.5):
    """A smooth path through the points (a Catmull-Rom spline). A point given as (x, y, "c") is a corner."""
    xy = [(float(p[0]), float(p[1])) for p in pts]
    corner = [len(p) > 2 for p in pts]
    n = len(xy)
    path = skia.Path()
    path.moveTo(*xy[0])

    def at(i):
        return xy[i % n] if closed else xy[max(0, min(n - 1, i))]

    def tangent(i):
        if corner[i % n] if closed else corner[max(0, min(n - 1, i))]:
            return 0.0, 0.0
        (ax, ay), (bx, by) = at(i - 1), at(i + 1)
        return (bx - ax) * tension / 3, (by - ay) * tension / 3

    for i in range(n if closed else n - 1):
        (x0, y0), (x1, y1) = at(i), at(i + 1)
        (ux, uy), (vx, vy) = tangent(i), tangent(i + 1)
        path.cubicTo(x0 + ux, y0 + uy, x1 - vx, y1 - vy, x1, y1)
    if closed:
        path.close()
    return path


def oval(cx, cy, rx, ry=None, rot=0.0):
    ry = rx if ry is None else ry
    p = skia.Path()
    p.addOval(skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry))
    return xf(p, rot=rot, about=(cx, cy)) if rot else p


def rect(x0, y0, x1, y1, r=0.0):
    p = skia.Path()
    box = skia.Rect.MakeLTRB(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    if r:
        r = min(r, box.width() / 2, box.height() / 2)
        p.addRRect(skia.RRect.MakeRectXY(box, r, r))
    else:
        p.addRect(box)
    return p


def box(cx, cy, w, h, r=0.0):
    """A rectangle by its centre and size."""
    return rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, r)


def union(*paths):
    out = paths[0]
    for p in paths[1:]:
        out = skia.Op(out, p, skia.kUnion_PathOp) or out
    return out


def intersect(a, b):
    return skia.Op(a, b, skia.kIntersect_PathOp) or skia.Path()


def minus(a, b):
    return skia.Op(a, b, skia.kDifference_PathOp) or a


def capsule(p0, p1, r0, r1=None):
    """A limb: the hull of a circle of radius r0 at p0 and one of r1 at p1."""
    r1 = r0 if r1 is None else r1
    (x0, y0), (x1, y1) = p0, p1
    d = math.hypot(x1 - x0, y1 - y0)
    a, b = oval(x0, y0, r0), oval(x1, y1, r1)
    if d < 1e-6 or d <= abs(r0 - r1):
        return a if r0 >= r1 else b
    th, ph = math.atan2(y1 - y0, x1 - x0), math.acos((r0 - r1) / d)
    quad = poly([(x0 + r0 * math.cos(th + ph), y0 + r0 * math.sin(th + ph)),
                 (x1 + r1 * math.cos(th + ph), y1 + r1 * math.sin(th + ph)),
                 (x1 + r1 * math.cos(th - ph), y1 + r1 * math.sin(th - ph)),
                 (x0 + r0 * math.cos(th - ph), y0 + r0 * math.sin(th - ph))])
    return union(a, b, quad)


def arrow(p0, p1, w, head=3.2):
    """An arrow from p0 to p1 as a shape: a shaft of width w and a head `head` times as wide."""
    (x0, y0), (x1, y1) = p0, p1
    d = math.hypot(x1 - x0, y1 - y0) or 1.0
    ux, uy = (x1 - x0) / d, (y1 - y0) / d
    vx, vy = -uy, ux
    hl = min(d, w * head * 0.95)
    bx, by = x1 - ux * hl, y1 - uy * hl
    hw = w * head / 2
    return poly([(x0 + vx * w / 2, y0 + vy * w / 2), (bx + vx * w / 2, by + vy * w / 2), (bx + vx * hw, by + vy * hw),
                 (x1, y1), (bx - vx * hw, by - vy * hw), (bx - vx * w / 2, by - vy * w / 2),
                 (x0 - vx * w / 2, y0 - vy * w / 2)])


def matrix(x=0.0, y=0.0, s=1.0, rot=0.0, sx=None, sy=None, about=(0.0, 0.0)):
    """Scale and turn about a point, then move by (x, y)."""
    m = skia.Matrix()
    m.setTranslate(x + about[0], y + about[1])
    m.preRotate(rot)
    m.preScale(s if sx is None else sx, s if sy is None else sy)
    m.preTranslate(-about[0], -about[1])
    return m


def xf(path, x=0.0, y=0.0, s=1.0, rot=0.0, sx=None, sy=None, about=(0.0, 0.0), m=None):
    """A copy of the path, scaled and turned (degrees) about a point, then moved."""
    out = skia.Path(path)
    out.transform(m if m is not None else matrix(x, y, s, rot, sx, sy, about))
    return out


def along(path, frac):
    """((x, y), angle in degrees) at a fraction of the way along a path."""
    pm = skia.PathMeasure(path, False)
    pos, tan = pm.getPosTan(pm.getLength() * max(0.0, min(1.0, frac)))
    return (pos.x(), pos.y()), math.degrees(math.atan2(tan.y(), tan.x()))


def part(path, a, b):
    """The stretch of a path from fraction a to fraction b: a line that draws itself."""
    pm = skia.PathMeasure(path, False)
    out = skia.Path()
    n = pm.getLength()
    pm.getSegment(n * max(0.0, a), n * min(1.0, b), out, True)
    return out


# --- type ---------------------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _typeface(name):
    path = FONT_DIR / FONTS[name] if name in FONTS else Path(name)
    face = skia.Typeface.MakeFromFile(str(path))
    if face is None:
        raise FileNotFoundError(f"no font at {path}")
    return face


@lru_cache(maxsize=512)
def font(name, size):
    f = skia.Font(_typeface(name), size)
    f.setSubpixel(True)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    return f


def text_width(s, fnt):
    return fnt.measureText(s)


def text(canvas, s, x, y, fnt, paint, align="l", track=0.0):
    """Draw a string with its baseline at y: align "l" starts at x, "m" centres on it, "r" ends at it.
    `track` adds space between letters, in pixels. Returns the width."""
    if track:
        widths = fnt.getWidths(fnt.textToGlyphs(s))
        w = sum(widths) + track * (len(s) - 1)
        x -= w / 2 if align == "m" else w if align == "r" else 0
        for ch, cw in zip(s, widths):
            canvas.drawString(ch, x, y, fnt, paint)
            x += cw + track
        return w
    w = fnt.measureText(s)
    canvas.drawString(s, x - (w / 2 if align == "m" else w if align == "r" else 0), y, fnt, paint)
    return w


def wrap(s, fnt, width):
    """The string broken into lines no wider than `width`. A newline in the string forces a break."""
    lines = []
    for para in s.split("\n"):
        line = ""
        for word in para.split():
            trial = f"{line} {word}".strip()
            if line and fnt.measureText(trial) > width:
                lines.append(line)
                line = word
            else:
                line = trial
        lines.append(line)
    return lines


def paragraph(canvas, s, x, y, fnt, paint, width, leading=1.3, align="l"):
    """Draw wrapped text with its first baseline at y. Returns the y of the baseline after the last line."""
    step = fnt.getSize() * leading
    for line in wrap(s, fnt, width):
        text(canvas, line, x, y, fnt, paint, align)
        y += step
    return y


def text_path(s, fnt, x=0.0, y=0.0, align="l"):
    """The outlines of a string as one path, for lettering that is stroked, clipped or drawn on."""
    glyphs = fnt.textToGlyphs(s)
    widths = fnt.getWidths(glyphs)
    x -= sum(widths) / 2 if align == "m" else sum(widths) if align == "r" else 0
    out = skia.Path()
    for g, w in zip(glyphs, widths):
        gp = fnt.getPath(g)
        if gp is not None:
            out.addPath(gp, x, y)
        x += w
    return out


# --- texture ------------------------------------------------------------------------------------

def grain(w, h, seed=0, scale=1, lo=0.0, hi=1.0):
    """White noise in [lo, hi], (h, w) float32, in blocks of `scale` pixels."""
    rng = np.random.default_rng(seed)
    g = rng.random(((h + scale - 1) // scale, (w + scale - 1) // scale), np.float32)
    if scale > 1:
        g = np.repeat(np.repeat(g, scale, 0), scale, 1)[:h, :w]
    return lo + (hi - lo) * g
