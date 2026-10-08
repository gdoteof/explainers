"""Footnote, the host: a small hovering robot with a screen for a face, two loose hands, and an asterisk on
its antenna, which is the mark of a footnote.

    draw(canvas, pose, at)                  at = (x, y, scale): the middle of the head, and pixels to a unit
    perform(keys, t)                        the pose at t from [(time, Pose, seconds to get there), ...]
    travel(keys, t)                         where it is at t, from [(time, (x, y, scale), seconds), ...]
    alive(pose, t, narration, key)          that pose hovering, blinking and saying the narration
    reach(at, (px, py))                     a point of the screen in the rig's units, for a hand to go to
    sign(canvas, text, hand, scale, ...)    a paddle the host holds up: MY OPINION

Units: the head is 2.4 wide and 1.9 tall with the origin at its middle, y runs down, the body hangs below
to about 2.5, and the antenna's star sits at about -1.8. "l" and "r" are the screen's left and right.
"""
import math
from dataclasses import dataclass, fields, replace

import skia

from explainers import draw as D
from explainers.anim import back, clamp, drift, ease_out, rnd

BODY = (112, 86, 204)
BODY_DARK = (84, 62, 168)
BODY_LIGHT = (146, 122, 232)
SCREEN = (27, 23, 44)
GLOW = (255, 241, 204)
STAR = (244, 180, 50)
HAND = (150, 127, 234)
SHADOW = (60, 50, 40)

REST_L, REST_R = (-1.12, 1.78), (1.12, 1.78)


@dataclass
class Pose:
    dx: float = 0.0         # the whole robot moved, in units
    dy: float = 0.0
    lean: float = 0.0       # tilted, in degrees
    squash: float = 0.0     # squashed (+) or stretched (-)
    head: float = 0.0       # the head's tilt in degrees
    turn: float = 0.0       # the face turned to screen left (-1) or right (1)
    nod: float = 0.0        # the face up (-1) or down (1)
    look_x: float = 0.0     # the eyes, -1..1
    look_y: float = 0.0
    lid: float = 0.0        # 0 open, 1 shut
    wide: float = 0.0       # eyes wide
    happy: float = 0.0      # eyes as smiling arcs
    frown: float = 0.0      # the tops of the eyes cut inwards (+, stern) or outwards (-, worried)
    skew: float = 0.0       # one eye half shut: doubt (+ the left one, - the right one)
    smile: float = 0.3      # the mouth's corners up (+) or down (-)
    mw: float = 0.8         # the mouth's width and opening (narration.mouth)
    mh: float = 0.0
    lx: float = None        # the left hand, in units from the middle of the head; None lets it hang
    ly: float = None
    rx: float = None
    ry: float = None
    grip_l: str = "rest"    # rest, point, open, hold, thumb
    grip_r: str = "rest"
    aim_l: float = None     # where the finger points, degrees (0 right, -90 up); None points away from the body
    aim_r: float = None
    spark: float = 0.0      # the antenna's star lit up, 0..1
    sway: float = 0.0       # the antenna bent to the right (+) or left (-)


MOVES = {"dx", "dy", "lean", "squash", "head", "lx", "ly", "rx", "ry"}
_HANDS = {"lx": REST_L[0], "ly": REST_L[1], "rx": REST_R[0], "ry": REST_R[1]}


def mix(a, b, k, over=None):
    """Pose a moved a fraction k of the way to pose b. `over` is the fraction for the things that travel
    (the body, the head, the hands), which may overshoot 1 and settle."""
    if k <= 0:
        return a
    over = k if over is None else over
    if k >= 1 and over == 1:
        return b
    vals = {}
    for f in fields(Pose):
        x, y = getattr(a, f.name), getattr(b, f.name)
        if isinstance(x, str) or isinstance(y, str):
            vals[f.name] = y if k >= 0.5 else x
            continue
        if f.name in _HANDS and (x is None) != (y is None):
            x = _HANDS[f.name] if x is None else x
            y = _HANDS[f.name] if y is None else y
        elif x is None or y is None:
            vals[f.name] = y if k >= 0.5 else x
            continue
        vals[f.name] = x + (y - x) * (over if f.name in MOVES else min(1.0, k))
    return Pose(**vals)


def perform(keys, t):
    """The pose at t. `keys` is [(time, Pose, seconds to get there), ...] in order: each move eases out,
    and what travels overshoots a little and settles."""
    cur = keys[0][1]
    for t0, target, dur in keys[1:]:
        if t < t0:
            break
        x = (t - t0) / dur
        cur = mix(cur, target, ease_out(x), back(x, 2.0) if x < 1 else 1.0)
    return cur


def alive(pose, t, narration=None, key="host", talk=True):
    """The pose with what a live thing adds: a hover, blinks, the antenna swaying, and the narration's mouth."""
    extra = dict(dy=pose.dy + 0.07 * math.sin(t * 2.1) + 0.03 * drift(t, key, 1.3),
                 lean=pose.lean + 1.2 * drift(t, (key, "lean"), 0.8),
                 sway=pose.sway + 0.5 * drift(t, (key, "sway"), 2.4))
    slot = int(t // 3.4)                                  # a blink somewhere in every 3.4 seconds, now and then two
    start = slot * 3.4 + 0.3 + 2.5 * rnd(key, slot)
    if 0 <= t - start < 0.12 or (rnd(key, slot, "twice") < 0.25 and 0 <= t - start - 0.3 < 0.12):
        extra["lid"] = 1.0
    if narration is not None and talk:
        w, h = narration.mouth(t)
        if h > 0.01 or narration.speaking(t):
            extra.update(mw=w, mh=h)
            extra["head"] = pose.head + 1.6 * (narration.loud(t) - 0.4) * math.sin(t * 5.3)
    return replace(pose, **extra)


def travel(keys, t):
    """Where the host is at t: (x, y, scale) from [(time, (x, y, scale), seconds to get there), ...]."""
    cur = keys[0][1]
    for t0, target, dur in keys[1:]:
        if t < t0:
            break
        k = (t - t0) / dur if dur > 0 else 1.0
        k = 1.0 if k >= 1 else 4 * k ** 3 if k < 0.5 else 1 - (-2 * k + 2) ** 3 / 2
        cur = tuple(a + (b - a) * k for a, b in zip(cur, target))
    return cur


def reach(at, point):
    """A point of the screen in the rig's units."""
    x, y, s = at
    return (point[0] - x) / s, (point[1] - y) / s


# --- the parts ----------------------------------------------------------------------------------

def _star(cx, cy, r, turn=0.0):
    """The footnote mark: six arms."""
    arms = []
    for i in range(3):
        a = math.radians(turn + 90 + i * 60)
        dx, dy = math.cos(a) * r, math.sin(a) * r
        arms.append(D.capsule((cx - dx, cy - dy), (cx + dx, cy + dy), r * 0.27))
    return D.union(*arms)


def _hand(grip, pos, side, aim, r=0.27):
    """A mitt at pos. `side` is -1 for the left hand, 1 for the right; the thumb is on the body's side."""
    x, y = pos

    def finger(angle, length, r0=0.36, r1=0.3, start=0.45):
        ux, uy = math.cos(angle), math.sin(angle)
        return D.capsule((x + ux * r * start, y + uy * r * start), (x + ux * r * length, y + uy * r * length), r * r0, r * r1)

    palm = D.oval(x, y, r * 1.02, r * 0.94)
    if grip == "point":
        a = math.radians((0 if side > 0 else 180) if aim is None else aim)
        return D.union(palm, finger(a, 2.3), finger(a - side * math.radians(95), 1.25, 0.38, 0.33, 0.2))
    if grip == "open":
        a = math.radians(-90 + side * 28 if aim is None else aim)
        return D.union(palm, *(finger(a + math.radians(30 * k), 1.75 - 0.12 * abs(k), 0.36, 0.33) for k in (-1, 0, 1)),
                       finger(a - side * math.radians(88), 1.4, 0.38, 0.33, 0.2))
    if grip == "thumb":
        a = math.radians(-90 if aim is None else aim)
        return D.union(D.oval(x, y, r * 1.02, r * 0.9), finger(a, 1.9, 0.4, 0.34, 0.3))
    if grip == "hold":
        return D.union(D.oval(x, y, r * 1.0, r * 0.88), finger(math.radians(-90 - side * 62), 1.15, 0.4, 0.36, 0.2))
    return D.union(palm, finger(math.radians(-90 - side * 38), 1.3, 0.4, 0.34, 0.3))


def _eye(c, cx, cy, side, p, s):
    """One eye on the screen: a tall rounded bar of light that lids, widens, frowns, or smiles into an arc."""
    w = 0.25 * (1 + 0.25 * p.wide)
    h = 0.56 * (1 + 0.3 * p.wide)
    glow = D.fill(GLOW)
    if p.happy > 0.5:
        arc = D.curve([(cx - w * 1.1, cy + 0.12), (cx, cy - 0.2), (cx + w * 1.1, cy + 0.12)], closed=False)
        c.drawPath(arc, D.stroke(GLOW, 0.17))
        return
    lid = clamp(p.lid + 0.5 * max(0.0, p.skew * -side))
    if lid > 0.93:
        c.drawPath(D.capsule((cx - w * 0.9, cy + 0.05), (cx + w * 0.9, cy + 0.05), 0.05), glow)
        return
    eye = D.rect(cx - w, cy - h / 2, cx + w, cy + h / 2, w)
    mid = cy - h / 2 + lid * h * 0.9 + 0.11 * abs(p.frown)     # the lid line, which slopes down to the nose when stern
    slope = -0.5 * p.frown * side
    if lid > 0.01 or p.frown:
        eye = D.intersect(eye, D.poly([(cx - 1, mid - slope), (cx + 1, mid + slope), (cx + 1, cy + 2), (cx - 1, cy + 2)]))
    c.drawPath(eye, glow)


def draw(c, pose, at, shadow=None, alpha=1.0):
    """Draw the host. `shadow` is the screen y of the ground under it, for the shadow it hovers over."""
    x, y, s = at
    p = pose
    if shadow is not None:
        gap = clamp((shadow - (y + (p.dy + 2.5) * s)) / (2.0 * s))
        c.drawPath(D.oval(x + p.dx * s, shadow, s * (0.95 - 0.3 * gap), s * (0.16 - 0.05 * gap)),
                   D.fill(SHADOW, alpha * (0.22 - 0.1 * gap)))
    c.save()
    if alpha < 1:
        c.saveLayer(None, skia.Paint(Alphaf=clamp(alpha)))
    c.concat(D.matrix(x, y, s))
    body_m = D.matrix(p.dx, p.dy, rot=p.lean, sx=1 + 0.6 * p.squash, sy=1 - p.squash, about=(0.0, 2.5))

    # the body, hanging under the head
    c.save()
    c.concat(body_m)
    torso = D.curve([(0, 1.0), (0.52, 1.05), (0.80, 1.42), (0.72, 2.02), (0.40, 2.42), (0, 2.5),
                     (-0.40, 2.42), (-0.72, 2.02), (-0.80, 1.42), (-0.52, 1.05)])
    c.drawPath(torso, D.fill(BODY_DARK))
    c.drawPath(D.intersect(torso, D.xf(torso, -0.16, -0.10)), D.fill(BODY))
    c.drawPath(D.oval(0, 1.66, 0.2), D.fill(SCREEN))
    c.drawPath(D.oval(0, 1.66, 0.11), D.fill(D.mix(BODY_LIGHT, STAR, clamp(p.spark))))
    c.drawPath(D.rect(-0.3, 0.84, 0.3, 1.1, 0.1), D.fill(SCREEN))

    # the head, tilting on the neck
    c.save()
    c.concat(D.matrix(rot=p.head, about=(0.0, 0.95)))
    tip = (0.9 * p.sway * 0.35 - 0.05 * p.turn, -1.78 - 0.05 * abs(p.sway))
    stalk = D.curve([(0.0, -0.9), (0.02 + 0.1 * p.sway, -1.3), tip], closed=False)
    c.drawPath(stalk, D.stroke(BODY_DARK, 0.085))
    if p.spark > 0.02:
        c.drawPath(D.oval(*tip, 0.42), D.blurred(D.fill(STAR, 0.6 * clamp(p.spark)), 0.14))
    c.drawPath(_star(*tip, 0.24 * (1 + 0.25 * clamp(p.spark)), turn=40 * p.sway), D.fill(STAR))
    for side in (-1, 1):
        c.drawPath(D.rect(side * 1.14 - 0.17, -0.34, side * 1.14 + 0.17, 0.34, 0.12), D.fill(BODY_DARK))
    head = D.rect(-1.2, -0.95, 1.2, 0.95, 0.62)
    c.drawPath(head, D.fill(BODY_DARK))
    c.drawPath(D.intersect(head, D.xf(head, -0.12, -0.10)), D.fill(BODY))
    c.drawPath(D.intersect(head, D.capsule((-0.72, -0.78), (-0.18, -0.80), 0.045)), D.fill(BODY_LIGHT))
    fx, fy = 0.13 * p.turn, 0.08 * p.nod                  # the screen slides over the head as it turns
    screen = D.rect(-0.93 + fx, -0.64 + fy, 0.93 + fx, 0.64 + fy, 0.44)
    c.drawPath(screen, D.fill(SCREEN))
    c.save()
    c.clipPath(screen, doAntiAlias=True)
    ex, ey = fx * 1.6 + 0.11 * p.look_x, -0.10 + fy * 1.6 + 0.08 * p.look_y
    for side in (-1, 1):
        _eye(c, side * 0.40 + ex, ey, side, p, s)
    mx, my = ex * 0.8, 0.36 + fy * 1.6 + 0.04 * p.look_y
    mw = 0.17 * p.mw
    if p.mh < 0.03:                                       # shut: a line that smiles or doesn't
        sag = 0.07 * p.smile
        lips = D.curve([(mx - mw, my - sag * 0.6), (mx, my + sag), (mx + mw, my - sag * 0.6)], closed=False)
        c.drawPath(lips, D.stroke(GLOW, 0.06))
    else:
        mh = 0.03 + 0.13 * p.mh
        c.drawPath(D.rect(mx - mw, my - mh * 0.55, mx + mw, my + mh, min(mw, mh * 0.8)), D.fill(GLOW))
    c.restore()
    c.restore()                                           # head
    c.restore()                                           # body

    # the hands: loose, so they go where they are sent
    for side, hx, hy, grip, aim, rest in ((-1, p.lx, p.ly, p.grip_l, p.aim_l, REST_L), (1, p.rx, p.ry, p.grip_r, p.aim_r, REST_R)):
        if hx is None:
            q = body_m.mapXY(rest[0], rest[1] + 0.05 * math.sin(side + p.dy * 9))
            hx, hy = q.x(), q.y()
        shape = _hand(grip, (hx, hy), side, aim)
        c.drawPath(D.xf(shape, 0.035, 0.05), D.fill(BODY_DARK, 0.55))
        c.drawPath(shape, D.fill(HAND))
    if alpha < 1:
        c.restore()
    c.restore()


def hand_at(pose, at, side):
    """Where a hand is on the screen under this pose. `side` is "l" or "r"."""
    x, y, s = at
    hx, hy = (pose.lx, pose.ly) if side == "l" else (pose.rx, pose.ry)
    if hx is None:
        rest = REST_L if side == "l" else REST_R
        q = D.matrix(pose.dx, pose.dy, rot=pose.lean, sx=1 + 0.6 * pose.squash, sy=1 - pose.squash, about=(0.0, 2.5)).mapXY(*rest)
        hx, hy = q.x(), q.y()
    return x + hx * s, y + hy * s


def sign(c, text, hand, s, colour, k=1.0, tilt=5.0, ink=(255, 253, 247)):
    """A paddle held up in a hand at `hand` (screen pixels): a stick and a card with a word or two on it.
    `k` is how far up it is, 0..1; draw it before the host so that the hand closes over the stick."""
    if k <= 0:
        return
    hx, hy = hand
    fnt = D.font("black", 0.36 * s)
    w = max(1.9 * s, D.text_width(text, fnt) + 0.6 * s)
    h = 0.92 * s
    with D.moved(c, rot=tilt * k, about=(hx, hy)):
        top = hy - (1.0 + 0.55 * k) * s
        c.drawPath(D.capsule((hx, hy + 0.25 * s), (hx, top), 0.07 * s), D.fill((92, 74, 60)))
        with D.moved(c, s=0.3 + 0.7 * k, about=(hx, top)):
            card = D.rect(hx - w / 2, top - h, hx + w / 2, top, 0.16 * s)
            c.drawPath(D.xf(card, 0.05 * s, 0.07 * s), D.fill((40, 30, 50), 0.22))
            c.drawPath(card, D.fill(colour))
            D.text(c, text, hx, top - h / 2 + 0.13 * s, fnt, D.fill(ink), "m", track=0.01 * s)


# --- the character sheet ------------------------------------------------------------------------

SHEET = [
    ("rest", Pose()),
    ("talking", Pose(mh=0.8, mw=0.95)),
    ("happy", Pose(happy=1.0, smile=1.0, dy=-0.1, lx=-1.5, ly=0.6, grip_l="open", rx=1.5, ry=0.6, grip_r="open")),
    ("pointing", Pose(turn=0.7, look_x=1.0, lean=4, rx=1.9, ry=0.3, grip_r="point", aim_r=-20)),
    ("doubt", Pose(skew=1.0, head=8, smile=-0.3, look_x=-0.5, lx=-0.7, ly=0.75, grip_l="rest")),
    ("stern", Pose(frown=1.0, smile=-0.6, nod=0.3)),
    ("worried", Pose(frown=-1.0, smile=-0.5, wide=0.4, lean=-3)),
    ("surprised", Pose(wide=1.0, mh=0.6, mw=0.6, dy=-0.15, squash=-0.06, spark=1.0)),
    ("thinking", Pose(look_x=0.6, look_y=-0.9, head=-7, turn=0.3, lx=-0.5, ly=1.22, grip_l="point", aim_l=-78)),
    ("opinion", Pose(smile=0.6, head=-5, look_x=0.5, rx=2.15, ry=1.25, grip_r="hold")),
    ("thumb", Pose(happy=1.0, smile=1.0, lx=-1.4, ly=0.9, grip_l="thumb")),
    ("asleep", Pose(lid=1.0, smile=0.1, nod=0.6, head=6, dy=0.12)),
]


def sheet(path, cols=4, cell=(480, 500)):
    """Every pose of SHEET on one page."""
    from explainers import theme
    rows = (len(SHEET) + cols - 1) // cols
    surf = D.surface(cols * cell[0], rows * cell[1], theme.PAPER)
    c = surf.getCanvas()
    for i, (name, pose) in enumerate(SHEET):
        x, y = (i % cols + 0.5) * cell[0], (i // cols) * cell[1] + 205
        at = (x, y, 88)
        if name == "opinion":
            sign(c, "MY OPINION", hand_at(pose, at, "r"), at[2], theme.HOST)
        draw(c, pose, at, shadow=y + 252)
        D.text(c, name, x, y + 285, D.font("semi", 22), D.fill(theme.INK_SOFT), "m")
    surf.makeImageSnapshot().save(str(path), skia.kPNG)
    return path


if __name__ == "__main__":
    import sys
    print(sheet(sys.argv[1] if len(sys.argv) > 1 else "host.png"))
