"""Sets: the place a video happens in. The first is a classroom with a projector screen.

What is being explained is drawn as a slide, a 1920x1080 picture, and the set shows it on its screen. The
camera can be anywhere between the wide shot (the room, the host, the screen with the slide on it) and
the close one (the screen fills the frame, so the slide is seen exactly as it was drawn):

    room = sets.Classroom()

    def frame(t):
        s, c = theme.stage()
        room.draw(c, zoom, slide=lambda c: chart(c, t), chalk="Who pays", t=t,
                  actors=lambda c: host.draw(c, pose, room.STAND, shadow=room.GROUND))
        theme.narration_label(c, N, SOURCES, t, plate=1.0)      # in the frame, not in the room
        return s

`zoom` is 0 for the wide shot and 1 for the screen; `shots` turns cues into a zoom that eases from one to
the next. Everything in the room, the host included, is placed in the wide shot's coordinates, and the
camera moves it.

    python -m explainers.sets OUT.png       the classroom from three distances, as one sheet
"""
import math
from functools import lru_cache

import numpy as np
import skia

from explainers import draw as D
from explainers import theme
from explainers.anim import clamp, ease, lerp

W, H = theme.W, theme.H

WALL = (238, 231, 213)
WALL_LOW = (224, 215, 193)
SKIRTING = (188, 172, 144)
BOARDS = (216, 190, 154)
BOARDS_DARK = (184, 154, 116)
WOOD = (166, 124, 84)
WOOD_DARK = (132, 96, 64)
SLATE = (44, 76, 71)
SLATE_LIGHT = (62, 96, 90)
CHALK = (244, 241, 230)
METAL = (72, 66, 82)
METAL_DARK = (50, 45, 60)


def view(rect, zoom):
    """The camera's matrix: the whole frame at zoom 0, `rect` (16:9) filling the frame at zoom 1. The width
    of what is seen shrinks by the same factor each step, so the move has an even speed."""
    x0, y0, x1, _ = rect
    k = clamp(zoom)
    w = W * ((x1 - x0) / W) ** k
    f = (W - w) / (W - (x1 - x0)) if x1 - x0 < W else 0.0
    s = W / w
    m = skia.Matrix()
    m.setTranslate(-x0 * f * s, -y0 * f * s)
    m.preScale(s, s)
    return m


def shots(keys, t):
    """The zoom at t from [(time, zoom, seconds to get there), ...] in order: slow, fast, slow."""
    cur = keys[0][1]
    for t0, target, dur in keys[1:]:
        if t < t0:
            break
        cur = lerp(cur, target, ease((t - t0) / dur) if dur > 0 else 1.0)
    return cur


@lru_cache(maxsize=2)
def _tooth(w=W, h=H):
    """The paper's tooth as a grey picture to lay over a drawn set, so that it sits on the same paper."""
    g = D.grain(w, h, seed=7, scale=2, lo=-1.0, hi=1.0) * 9 + D.grain(w, h, seed=8, scale=1, lo=-1.0, hi=1.0) * 6
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    edge = ((xx / w - 0.5) ** 2 + (yy / h - 0.5) ** 2) * 34
    v = np.clip(128 + g - edge, 0, 255).astype(np.uint8)
    return D.from_array(np.dstack([v, v, v]))


def tooth(c, alpha=1.0):
    c.drawImage(_tooth(), 0, 0, skia.SamplingOptions(), skia.Paint(BlendMode=skia.BlendMode.kSoftLight, Alphaf=alpha))


class Classroom:
    """A classroom seen from the back of the room: a chalkboard, a pull-down screen over the middle of it,
    a clock, the teacher's desk, and the projector in front of us."""
    SCREEN = (608, 104, 1760, 752)      # 16:9: what the close shot fills the frame with
    FLOOR = 838                         # where the wall meets the floor
    GROUND = 915                        # the floor under the host, for its shadow
    STAND = (336, 560, 96)              # where the host hovers while something is on the screen
    FRONT = (500, 560, 140)             # stepped forward and large: when it speaks for itself
    BOARD = (90, 168, 1830, 782)

    def view(self, zoom):
        return view(self.SCREEN, zoom)

    def draw(self, c, zoom=0.0, slide=None, actors=None, chalk="", t=0.0, on=1.0):
        """The room as the camera sees it. `slide(c)` draws what is on the screen, as a 1920x1080 picture;
        `actors(c)` draws whoever is in the room, in the wide shot's coordinates; `chalk` is written on
        the board beside the screen; `on` is how bright the projector is (0 is a blank screen), to turn
        the slide down while the host speaks for itself."""
        c.save()
        c.concat(self.view(zoom))
        self._walls(c, t)
        self._board(c, chalk)
        self._screen(c, slide, on)
        self._desk(c)
        if actors is not None:
            actors(c)
        self._projector(c, on)
        c.restore()
        tooth(c)

    # --- the parts ------------------------------------------------------------------------------

    def _walls(self, c, t):
        far = 400
        c.drawPath(D.rect(-far, -far, W + far, self.FLOOR), D.fill(WALL))
        c.drawPath(D.rect(-far, 650, W + far, self.FLOOR), D.fill(WALL_LOW))
        c.drawPath(D.rect(-far, 644, W + far, 656), D.fill(SKIRTING))
        c.drawPath(D.rect(-far, self.FLOOR, W + far, H + far), D.fill(BOARDS))
        vx, vy = W / 2, self.FLOOR - 620                   # the floorboards run away from us to one point
        for i in range(-6, 15):
            xb = i * 240 - 120
            xt = vx + (xb - vx) * (self.FLOOR - vy) / (H + far - vy)
            c.drawPath(D.poly([(xt, self.FLOOR), (xb, H + far)], closed=False), D.stroke(BOARDS_DARK, 3, 0.55))
        c.drawPath(D.rect(-far, self.FLOOR - 24, W + far, self.FLOOR), D.fill(SKIRTING))
        c.drawPath(D.rect(-far, self.FLOOR, W + far, self.FLOOR + 10), D.fill(BOARDS_DARK, 0.5))
        self._clock(c, 206, 92, 56, t)

    def _clock(self, c, x, y, r, t):
        c.drawPath(D.oval(x + 5, y + 7, r), D.fill(theme.INK, 0.14))
        c.drawPath(D.oval(x, y, r), D.fill(METAL))
        c.drawPath(D.oval(x, y, r - 9), D.fill(theme.WHITE))
        for i in range(12):
            a = math.radians(i * 30)
            c.drawPath(D.capsule((x + (r - 20) * math.sin(a), y - (r - 20) * math.cos(a)),
                                 (x + (r - 14) * math.sin(a), y - (r - 14) * math.cos(a)), 1.8), D.fill(theme.INK_SOFT))
        for length, width, turns in ((r - 30, 3.6, 10 / 12 + t / 43200), (r - 19, 2.6, 10 / 60 + t / 3600)):
            a = math.radians(turns * 360)
            c.drawPath(D.capsule((x, y), (x + length * math.sin(a), y - length * math.cos(a)), width), D.fill(theme.INK))
        a = math.radians(int(t) * 6)                       # the second hand ticks
        c.drawPath(D.capsule((x - 8 * math.sin(a), y + 8 * math.cos(a)), (x + (r - 16) * math.sin(a), y - (r - 16) * math.cos(a)), 1.2),
                   D.fill(theme.ALERT))
        c.drawPath(D.oval(x, y, 4.5), D.fill(theme.INK))

    def _board(self, c, chalk):
        x0, y0, x1, y1 = self.BOARD
        c.drawPath(D.rect(x0 + 8, y0 + 12, x1 + 8, y1 + 12, 12), D.fill(theme.INK, 0.12))
        c.drawPath(D.rect(x0, y0, x1, y1, 12), D.fill(WOOD))
        slate = D.rect(x0 + 18, y0 + 18, x1 - 18, y1 - 22, 4)
        c.drawPath(slate, D.fill(SLATE))
        c.save()
        c.clipPath(slate, doAntiAlias=True)
        for sx, sy, rx, ry in ((330, 470, 300, 120), (1500, 300, 380, 150), (980, 660, 420, 90)):     # wiped chalk
            c.drawPath(D.oval(sx, sy, rx, ry, -8), D.blurred(D.fill(SLATE_LIGHT, 0.55), 46))
        if chalk:
            fnt = D.font("serif-italic", 52)
            left, width = x0 + 50, self.SCREEN[0] - x0 - 84
            y = y0 + 92
            for line in D.wrap(chalk, fnt, width):
                D.text(c, line, left, y, fnt, D.fill(CHALK, 0.92))
                y += 60
            rule = D.curve([(left - 4, y - 32), (left + width * 0.4, y - 38), (left + width * 0.74, y - 30)], closed=False)
            c.drawPath(rule, D.stroke(CHALK, 5, 0.8))
        c.restore()
        c.drawPath(D.rect(x0 - 10, y1 - 6, x1 + 10, y1 + 14, 6), D.fill(WOOD_DARK))                   # the chalk tray
        for cx, colour in ((x0 + 96, CHALK), (x0 + 150, theme.SIDE_A), (x0 + 188, CHALK)):
            c.drawPath(D.rect(cx, y1 - 15, cx + 34, y1 - 6, 3), D.fill(colour))
        c.drawPath(D.rect(x0 + 300, y1 - 26, x0 + 392, y1 - 6, 5), D.fill(METAL))
        c.drawPath(D.rect(x0 + 300, y1 - 12, x0 + 392, y1 - 6, 3), D.fill(WALL))

    def _screen(self, c, slide, on):
        x0, y0, x1, y1 = self.SCREEN
        c.drawPath(D.rect(x0 + 12, y0 + 18, x1 + 12, y1 + 34), D.blurred(D.fill(theme.INK, 0.42), 16))
        c.drawPath(D.rect(x0 - 30, y0 - 40, x1 + 30, y0 + 4, 10), D.fill(METAL))                      # the roller's case
        c.drawPath(D.rect(x0 - 30, y0 - 40, x1 + 30, y0 - 26, 7), D.fill(D.mix(METAL, theme.WHITE, 0.16)))
        for bx in (x0 + 90, x1 - 90):                                                                 # hung from the ceiling
            c.drawPath(D.rect(bx - 7, -400, bx + 7, y0 - 38), D.fill(METAL_DARK))
        c.drawPath(D.rect(x0, y0, x1, y1), D.fill(theme.WHITE))
        if slide is not None and on > 0:
            c.save()
            c.clipRect(skia.Rect.MakeLTRB(x0, y0, x1, y1), True)
            c.concat(D.matrix(x0, y0, (x1 - x0) / W))
            if on < 1:
                with D.layer(c, on):
                    slide(c)
            else:
                slide(c)
            c.restore()
        c.drawPath(D.rect(x0 - 12, y1, x1 + 12, y1 + 18, 7), D.fill(METAL))                           # the bar at the bottom
        mid = (x0 + x1) / 2
        c.drawPath(D.poly([(mid, y1 + 18), (mid, y1 + 50)], closed=False), D.stroke(METAL_DARK, 3))
        c.drawPath(D.oval(mid, y1 + 60, 10), D.stroke(METAL_DARK, 4))

    def _desk(self, c):
        x0, top = 1545, 872
        c.drawPath(D.oval(x0 + 250, H + 6, 330, 26), D.fill(theme.INK, 0.10))
        c.drawPath(D.rect(x0 + 26, top + 20, W + 200, H + 200), D.fill(WOOD_DARK))
        c.drawPath(D.rect(x0 + 60, top + 62, x0 + 300, top + 150, 8), D.fill(D.mix(WOOD_DARK, theme.INK, 0.14)))
        c.drawPath(D.oval(x0 + 180, top + 106, 9), D.fill(WOOD))
        c.drawPath(D.rect(x0, top, W + 200, top + 26, 6), D.fill(WOOD))
        for i, (colour, w, dx) in enumerate(((theme.SIDE_B, 190, 0), (theme.SIDE_A, 160, 18), (theme.HOST, 176, 6))):   # books
            y = top - 30 * (i + 1)
            c.drawPath(D.rect(x0 + 44 + dx, y, x0 + 44 + dx + w, y + 28, 5), D.fill(colour))
            c.drawPath(D.rect(x0 + 44 + dx + w - 26, y + 5, x0 + 44 + dx + w - 6, y + 23, 2), D.fill(theme.WHITE, 0.85))
        ax, ay = x0 + 304, top - 30                                                                   # an apple
        c.drawPath(D.union(D.oval(ax - 11, ay, 21, 24), D.oval(ax + 11, ay, 21, 24)), D.fill(theme.ALERT))
        c.drawPath(D.capsule((ax, ay - 20), (ax + 5, ay - 36), 2.5), D.fill(WOOD_DARK))
        c.drawPath(D.oval(ax + 16, ay - 32, 11, 5, -28), D.fill(theme.SIDE_B))

    def _projector(self, c, on):
        x0, _, x1, y1 = self.SCREEN
        px, py = (x0 + x1) / 2, 1004
        if on > 0:                                                                                    # the beam, up to the screen
            beam = D.poly([(px - 34, py), (px + 34, py), (x1, y1 + 18), (x0, y1 + 18)])
            c.drawPath(beam, D.blurred(D.fill(theme.WHITE, 0.10 * on), 10))
            c.drawPath(D.oval(px, py - 4, 60, 22), D.blurred(D.fill(theme.WHITE, 0.55 * on), 16))
        c.drawPath(D.rect(px - 46, py - 22, px + 46, py + 30, 10), D.fill(METAL_DARK))               # the lens, facing away
        body = D.rect(px - 190, py + 14, px + 190, H + 120, 22)
        c.drawPath(body, D.fill(METAL))
        c.drawPath(D.intersect(body, D.rect(px - 190, py + 14, px + 190, py + 32)), D.fill(D.mix(METAL, theme.WHITE, 0.18)))
        for i in range(5):
            vx = px - 150 + i * 22
            c.drawPath(D.capsule((vx, py + 52), (vx, py + 74), 3.5), D.fill(METAL_DARK))
        c.drawPath(D.oval(px + 150, py + 60, 6), D.fill(D.mix(METAL_DARK, (120, 220, 140), on)))


def _sample(c):
    """A slide to look at the set with: a title, a bar and a sentence."""
    theme.heading(c, "What is on the projector", 130, 210, 96)
    widths = (0.34, 0.22, 0.18, 0.14, 0.12)
    colours = (theme.HOST, theme.SIDE_B, theme.SIDE_A, theme.ALERT, theme.INK_SOFT)
    x = 130.0
    for w, colour in zip(widths, colours):
        c.drawPath(D.rect(x, 340, x + 1660 * w - 12, 560, 14), D.fill(colour))
        x += 1660 * w
    theme.body(c, "A slide is drawn once, at full size. The room shows it on the screen, and the camera can go "
               "all the way in to it.", 130, 690, 1560, 54, theme.INK_SOFT)


def sheet(path, zooms=(0.0, 0.55, 1.0)):
    """The classroom from three distances, with the host and the sample slide, as one picture."""
    from PIL import Image

    from explainers import host
    from explainers.sheet import contact_sheet
    room = Classroom()
    pose = host.Pose(turn=0.7, look_x=1.0, lean=4, smile=0.5, rx=1.9, ry=0.3, grip_r="point", aim_r=-20)
    tiles = []
    for z in zooms:
        s, c = theme.stage()
        room.draw(c, z, slide=_sample, chalk="Today: the set", t=1.0,
                  actors=lambda c: host.draw(c, pose, room.STAND, shadow=room.GROUND))
        theme.label(c, "fact", "A source, in short", plate=1.0)
        tiles.append((Image.fromarray(D.array(s)[..., :3]), f"zoom {z:g}"))
    return contact_sheet(tiles, path, cols=len(zooms), tile=(960, 540))


if __name__ == "__main__":
    import sys
    print(sheet(sys.argv[1] if len(sys.argv) > 1 else "classroom.png"))
