"""The hall, as a diagram: benches in a horseshoe, seen from above with the president's chair at the
bottom, so that his right is the screen's right. The deputies are dots. It is not a floor plan."""
import math

from explainers import draw as D
from explainers import theme
from explainers.anim import ease, lerp, ramp, rnd, smooth

CX, CY = 700, 600
CHAIR = (CX, 880)
ROWS = 6
GREY = (150, 144, 150)


def _seats():
    seats = []
    for r in range(ROWS):
        a, b = 290 + 62 * r, 140 + 44 * r
        n = int((230 / 360) * 2 * math.pi * math.sqrt((a * a + b * b) / 2) / 35)
        for k in range(n):
            phi = math.radians(-25 + 230 * (k + 0.5) / n)
            if abs(math.degrees(phi) - 90) < 3.2:         # the aisle
                continue
            seats.append((CX + a * math.cos(phi), CY - b * math.sin(phi)))
    return seats


def _nearest(seats, x, y):
    return min(seats, key=lambda s: (s[0] - x) ** 2 + (s[1] - y) ** 2)


_ALL = _seats()
SPARE = [_nearest(_ALL, 551, 433), _nearest(_ALL, 234, 442)]    # two seats on the left that nobody takes
SEATS = [s for s in _ALL if s not in SPARE]
RIGHT = [s for s in SEATS if s[0] > CX]
LEFT = [s for s in SEATS if s[0] < CX]
# Every deputy starts in somebody else's seat: the seats, shuffled.
_ORDER = sorted(range(len(SEATS)), key=lambda i: rnd("seat", i))
DEPUTIES = [(SEATS[_ORDER[i]], home, "r" if home[0] > CX else "l") for i, home in enumerate(SEATS)]
GAUVILLE = SEATS.index(_nearest(RIGHT, 1065, 425))                # the deputy the video follows


def chair(c, k=1.0):
    """The president's table and the president. `k` is how far they have come in, 0..1."""
    if k <= 0:
        return
    x, y = CHAIR
    with D.layer(c, k):
        c.drawPath(D.rect(x - 92, y - 28, x + 92, y + 22, 12), D.fill(theme.INK))
        c.drawPath(D.oval(x, y + 56, 27), D.fill(theme.INK))
        D.text(c, "the president", x + 48, y + 66, D.font("semi", 30), D.fill(theme.INK_SOFT))


def place(i, t, t_right, t_left, appear=0.0):
    """Where deputy i is at t: (x, y, how far over to his own side 0..1, how far he has faded in 0..1)."""
    start, home, side = DEPUTIES[i]
    seen = smooth(ramp(t, appear + 0.5 * rnd("in", i), 0.3))
    k = ease(ramp(t, (t_right if side == "r" else t_left) + 1.5 * rnd("go", i), 1.1))
    x, y = lerp(start, home, k)
    y -= 26 * math.sin(math.pi * k)                       # a hop on the way over
    if k <= 0:
        x += 2.5 * math.sin(t * 2.1 + 9 * rnd("mx", i))
        y += 2.5 * math.sin(t * 1.7 + 9 * rnd("my", i))
    return x, y, k, seen


def colour(i, k):
    """Grey until he has picked a side, then his side's colour."""
    return D.mix(GREY, theme.SIDE_B if DEPUTIES[i][2] == "r" else theme.SIDE_A, smooth(ramp(k, 0.2, 0.6)))


def deputies(c, t, t_right, t_left, appear=0.0, alpha=1.0, skip=()):
    """The dots. Before `t_right` they sit anywhere, in grey; from then the right-hand ones cross to their
    side and take its colour, and from `t_left` the others do. `skip` leaves out the ones drawn elsewhere."""
    for i in range(len(DEPUTIES)):
        if i in skip:
            continue
        x, y, k, seen = place(i, t, t_right, t_left, appear)
        if seen > 0:
            c.drawPath(D.oval(x, y, 11.5 * seen), D.fill(colour(i, k), alpha))
