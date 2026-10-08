"""Left and Right, the pilot: where the two words come from, and how the labels work.

Scenes, cut on the narration: the hook (the host and the two words), the room (the hall, the dots sorting
themselves, the quotation, one deputy trying the seats), the minutes (a page that will not name the
sides), into English (the first sighting, then the manim chart), the opinion (the dots dropped onto one
line, and the paddle), and the deal (the five labels).
"""
import math
from pathlib import Path

from explainers import draw as D
from explainers import host, theme
from explainers import script as S
from explainers.anim import back, clamp, ease, ease_out, lerp, pop, ramp, rnd, smooth, window
from explainers.host import Pose
from explainers.inserts import Clip
from explainers.narration import Narration

import hall

ROOT = Path(__file__).resolve().parent
N = Narration(ROOT)
SOURCES, _ = S.load_sources(ROOT)
A, E = N.at, N.end

T_ROOM = A("room.1") - 0.45
T_QUOTE = A("room.3") - 0.3
T_WANDER = A("room.4") - 0.35
T_SLOW = A("slow.1") - 0.45
T_ENGLISH = A("english.1") - 0.45
T_CHART = A("english.2") - 0.45
T_OPINION = A("opinion.1") - 0.5
T_DEAL = A("deal.1") - 0.5
CHART = Clip(ROOT, "charts.py", "WordsInBooks", start=T_CHART)

# --- the host -----------------------------------------------------------------------------------

CENTRE, SIDE, OWN, DEAL_AT = (960, 500, 150), (1668, 540, 98), (430, 520, 132), (320, 530, 122)
WHERE = [(0.0, CENTRE, 0.0), (T_ROOM - 0.5, SIDE, 1.0), (T_OPINION - 0.5, OWN, 1.0), (T_DEAL - 0.3, DEAL_AT, 0.6)]

HELLO = Pose(smile=0.5)
TO_LEFT = Pose(turn=-0.8, look_x=-1.0, lean=-4, lx=-1.6, ly=0.6, grip_l="open", aim_l=-150)
TO_RIGHT = Pose(turn=0.8, look_x=1.0, lean=4, rx=1.6, ry=0.6, grip_r="open", aim_r=-30)
BOTH = Pose(smile=0.4, lx=-1.6, ly=0.95, grip_l="open", aim_l=-140, rx=1.6, ry=0.95, grip_r="open", aim_r=-40)
WONDER = Pose(look_x=0.5, look_y=-0.9, head=-7, turn=0.25, smile=0.0, lx=-0.5, ly=1.22, grip_l="point", aim_l=-78)
SHOW = Pose(turn=-0.7, look_x=-0.9, lean=-3, lx=-1.8, ly=0.7, grip_l="point", aim_l=188)
WATCH = Pose(turn=-0.75, look_x=-1.0, look_y=0.2, smile=0.4)
READ = Pose(turn=-0.7, look_x=-0.9, look_y=-0.1, head=4, smile=0.2, lid=0.12)
SHRUG = Pose(turn=-0.3, look_x=-0.4, head=6, smile=0.1, skew=0.6, lx=-1.6, ly=1.1, grip_l="open", aim_l=-150,
             rx=1.6, ry=1.1, grip_r="open", aim_r=-30)
CHART_IT = Pose(turn=-0.7, look_x=-0.9, look_y=0.1, lean=-3, lx=-1.8, ly=0.9, grip_l="point", aim_l=180)
WOW = Pose(turn=-0.7, look_x=-0.9, look_y=-0.5, wide=1.0, smile=0.6, dy=-0.12, spark=1.0, lx=-1.7, ly=0.4, grip_l="point", aim_l=205)
WINCE = Pose(turn=-0.75, look_x=-1.0, look_y=0.2, frown=-0.9, lid=0.15, smile=-0.5, head=5)
MINE = Pose(smile=0.6, head=-5, look_x=0.2, rx=2.15, ry=1.25, grip_r="hold")
MINE_LOOK = Pose(smile=0.3, head=3, turn=0.6, look_x=0.9, look_y=0.3, rx=2.15, ry=1.25, grip_r="hold")
TELL = Pose(turn=0.55, look_x=0.7, smile=0.5, rx=1.75, ry=0.5, grip_r="point", aim_r=-8)
TICK = Pose(turn=0.6, look_x=0.8, smile=0.5, rx=1.8, ry=0.95, grip_r="point", aim_r=8)
SURE = Pose(happy=1.0, smile=1.0, dy=-0.08, lx=-1.45, ly=0.85, grip_l="thumb")
ACT = [
    (0.0, HELLO, 0.2),
    (A("hook.1", "Left") - 0.12, TO_LEFT, 0.3), (A("hook.1", "Right") - 0.12, TO_RIGHT, 0.3),
    (A("hook.1", "We") - 0.1, BOTH, 0.4), (A("hook.1", "So") - 0.1, WONDER, 0.4),
    (T_ROOM - 0.3, SHOW, 0.5), (A("room.1", "arguing"), WATCH, 0.5),
    (A("room.2", "took") - 0.2, SHOW, 0.4), (A("room.2", "ones") + 0.3, WATCH, 0.5),
    (T_QUOTE, READ, 0.5),
    (T_WANDER, WATCH, 0.5), (A("room.4", "jeered") - 0.2, WINCE, 0.3), (A("room.4", "So") - 0.1, WATCH, 0.4),
    (A("slow.1"), SHRUG, 0.45), (A("slow.1", "next") - 0.3, SHOW, 0.5), (A("slow.1", "ruled") - 0.1, READ, 0.4),
    (T_ENGLISH, SHOW, 0.5), (A("english.1", "earliest") - 0.1, READ, 0.4),
    (T_CHART + 0.2, CHART_IT, 0.5), (A("english.3"), WATCH, 0.5), (A("english.3", "take") - 0.15, WOW, 0.3),
    (T_OPINION - 0.2, MINE, 0.5), (A("opinion.1", "A"), MINE_LOOK, 0.5),
    (T_DEAL, TELL, 0.5), (A("deal.2"), TICK, 0.4), (A("deal.2", "So") - 0.1, SURE, 0.35),
]


def host_now(t):
    return host.alive(host.perform(ACT, t), t, N), host.travel(WHERE, t)


# --- the hook -----------------------------------------------------------------------------------

def hook(c, t):
    fnt = D.font("black", 196)
    for word, x, colour, tilt, cue in (("LEFT", 350, theme.SIDE_A, -4, A("hook.1", "Left")),
                                        ("RIGHT", 1585, theme.SIDE_B, 4, A("hook.1", "Right"))):
        k = pop(t, cue - 0.05, 0.35)
        if k > 0:
            bob = 8 * math.sin((t - cue) * 2.2)
            with D.moved(c, s=k, rot=tilt, about=(x, 520)):
                D.text(c, word, x, 590 + bob, fnt, D.fill(colour), "m", track=-6)
    k = pop(t, A("hook.1", "where") - 0.1, 0.4)
    if k > 0:
        with D.moved(c, s=k, rot=12, about=(1190, 230)):
            D.text(c, "?", 1190, 310, D.font("black", 230), D.fill(theme.INK), "m")


# --- the room -----------------------------------------------------------------------------------

def crown(c, x, y, s, k):
    """A crown, for the king."""
    if k <= 0:
        return
    with D.moved(c, s=k, about=(x, y)):
        pts = [(-1.0, 0.55), (-1.15, -0.45), (-0.55, 0.0), (0.0, -0.8), (0.55, 0.0), (1.15, -0.45), (1.0, 0.55)]
        c.drawPath(D.poly([(x + px * s, y + py * s) for px, py in pts]), D.fill(theme.SIDE_A))
        c.drawPath(D.rect(x - s, y + 0.5 * s, x + s, y + 0.85 * s, 0.1 * s), D.fill(theme.SIDE_A_DARK))
        for px, py in ((-1.15, -0.45), (0.0, -0.8), (1.15, -0.45)):
            c.drawPath(D.oval(x + px * s, y + py * s, 0.16 * s), D.fill(theme.SIDE_A_DARK))


def room(c, t):
    quote = window(t, T_QUOTE, T_WANDER + 0.35, 0.5, 0.45)
    with D.layer(c, 1 - 0.8 * quote):
        k = ease_out(ramp(t, A("room.1", "In") - 0.2, 0.5))
        theme.heading(c, "Versailles, summer 1789", 110 - 30 * (1 - k), 122, 64, alpha=k)
        hall.chair(c, ease_out(ramp(t, T_ROOM + 0.2, 0.5)))
        go_right = A("room.2", "took") - 0.3              # the first sentence sorts the right, the second the left
        go_left = A("room.2", "ones") - 0.4
        hall.deputies(c, t, go_right, go_left, appear=T_ROOM + 0.3, skip=(hall.GAUVILLE,))
        gauville(c, t, go_right, go_left)
        # what they were arguing about
        gone = 1 - smooth(ramp(t, go_right - 0.3, 0.4))
        crown(c, hall.CX, 560, 46, pop(t, A("room.1", "king") - 0.1, 0.35) * gone)
        k = pop(t, A("room.1", "veto") - 0.1, 0.3) * gone
        if k > 0:
            with D.moved(c, s=k, about=(hall.CX, 670)):
                D.text(c, "veto?", hall.CX, 692, D.font("black", 68), D.fill(theme.INK), "m")
        # the two sides, named from the chair
        x, y = hall.CHAIR
        for word, cue, side, dark in (("RIGHT", A("room.2", "right"), 1, theme.SIDE_B_DARK),
                                      ("LEFT", A("room.2", "left"), -1, theme.SIDE_A_DARK)):
            k = pop(t, cue - 0.1, 0.35)
            if k <= 0:
                continue
            reach = ease_out(ramp(t, cue - 0.1, 0.4))
            c.drawPath(D.arrow((x + side * 125, y - 4), (x + side * (125 + 150 * reach), y - 4), 14), D.fill(dark))
            with D.moved(c, s=k, about=(x + side * 300, y)):
                D.text(c, word, x + side * 300, y + 33, D.font("black", 96), D.fill(dark), "l" if side > 0 else "r", track=-2)
    if quote > 0:
        card(c, t, quote)


JEERS = ((205, 318), (318, 262), (432, 222))


def gauville(c, t, go_right, go_left):
    """One deputy has a name. He tries two seats on the left, is jeered there, and goes back to the right."""
    x, y, k, seen = hall.place(hall.GAUVILLE, t, go_right, go_left, T_ROOM + 0.3)
    if seen <= 0:
        return
    home = (x, y)
    for word, seat in (("different", hall.SPARE[0]), ("hall", hall.SPARE[1]), ("So", home)):
        hop = ease(ramp(t, A("room.4", word) - 0.25, 0.6))
        x, y = lerp((x, y), seat, hop)
        y -= 54 * math.sin(math.pi * hop)
    marked = smooth(ramp(t, A("room.4", "tried") - 0.5, 0.4))
    away = ease(ramp(t, A("room.4", "different") - 0.25, 0.6)) * (1 - smooth(ramp(t, A("room.4", "So") + 0.2, 0.4)))
    jeer0, jeer1 = A("room.4", "jeered") - 0.2, A("room.4", "So") - 0.1
    if jeer0 < t < jeer1 + 0.3:
        x += 3.5 * math.sin(t * 43)
        for i, (jx, jy) in enumerate(JEERS):
            j = pop(t, jeer0 + 0.12 * i, 0.25, 1.6) * (1 - smooth(ramp(t, jeer1, 0.3)))
            if j > 0:
                with D.moved(c, s=j, rot=10 * math.sin(t * 9 + 2 * i), about=(jx, jy)):
                    c.drawPath(D.oval(jx, jy, 27), D.fill(theme.ALERT))
                    c.drawPath(D.poly([(jx - 9, jy + 22), (jx + 13, jy + 20), (jx + 16, jy + 46)]), D.fill(theme.ALERT))
                    D.text(c, "!", jx, jy + 15, D.font("black", 42), D.fill(theme.WHITE), "m")
    c.drawPath(D.oval(x, y, 11.5 * seen * (1 + 0.3 * marked)), D.fill(D.mix(hall.colour(hall.GAUVILLE, k), theme.INK, away)))
    if marked > 0:
        c.drawPath(D.oval(x, y, 25 * (2 - marked)), D.stroke(theme.INK, 4, marked))
        fnt = D.font("bold", 32)
        w = D.text_width("Gauville", fnt) + 36
        with D.layer(c, marked):
            c.drawPath(D.box(x, y - 62, w, 48, 24), D.fill(theme.WHITE))
            c.drawPath(D.box(x, y - 62, w, 48, 24), D.stroke(theme.INK, 3))
            D.text(c, "Gauville", x, y - 51, fnt, D.fill(theme.INK), "m")


QUOTE = ("“We were beginning to recognise one another: those who were attached to their religion and to the king "
         "had stationed themselves on the president’s right …”")
QUOTE_BY = "Baron de Gauville, deputy for the nobility, in his journal for 29 August 1789. Our translation."


def card(c, t, k):
    x0, x1, top = 130, 1270, 270
    quote_font, by_font = D.font("serif-italic", 58), D.font("semi", 32)
    width = x1 - x0 - 150
    lines = len(D.wrap(QUOTE, quote_font, width))
    bottom = top + 130 + lines * 58 * 1.36 + 40 + len(D.wrap(QUOTE_BY, by_font, width)) * 42 + 30
    with D.layer(c, k):
        with D.moved(c, y=40 * (1 - ease_out(k))):
            c.drawPath(D.rect(x0 + 8, top + 14, x1 + 8, bottom + 14, 28), D.blurred(D.fill((60, 45, 30), 0.25), 18))
            c.drawPath(D.rect(x0, top, x1, bottom, 28), D.fill(theme.WHITE))
            c.drawPath(D.rect(x0, top + 44, x0 + 12, bottom - 44, 6), D.fill(theme.SIDE_B))
            y = D.paragraph(c, QUOTE, x0 + 80, top + 122, quote_font, D.fill(theme.INK), width, 1.36)
            D.paragraph(c, QUOTE_BY, x0 + 80, y + 14, by_font, D.fill(theme.INK_SOFT), width, 1.3)


# --- the minutes --------------------------------------------------------------------------------

ASKED, RULED = "“the right side of the Assembly”", "“a part of the Assembly”"


def slow(c, t):
    """A page of the Assembly's minutes: the words Gauville asked for go in, are struck out, and are replaced."""
    theme.heading(c, "Not official", 110, 122, 64)
    x0, y0, x1, y1 = 250, 200, 1290, 930
    k = ease_out(ramp(t, T_SLOW + 0.15, 0.5))
    if k <= 0:
        return
    grey = D.fill(theme.RULE)
    with D.layer(c, k):
        with D.moved(c, y=50 * (1 - k), rot=-1.5, about=((x0 + x1) / 2, (y0 + y1) / 2)):
            c.drawPath(D.rect(x0 + 8, y0 + 14, x1 + 8, y1 + 14, 10), D.blurred(D.fill((60, 45, 30), 0.25), 18))
            c.drawPath(D.rect(x0, y0, x1, y1, 10), D.fill(theme.WHITE))
            D.text(c, "THE MINUTES", x0 + 80, y0 + 104, D.font("black", 40), D.fill(theme.INK), track=5)
            D.text(c, "as read out on 9 April 1790", x1 - 80, y0 + 102, D.font("medium", 32), D.fill(theme.INK_SOFT), "r")
            c.drawPath(D.rect(x0 + 80, y0 + 136, x1 - 80, y0 + 140), D.fill(theme.INK))
            for i, w in enumerate((0.96, 0.82)):
                y = y0 + 200 + 46 * i
                c.drawPath(D.capsule((x0 + 80, y), (x0 + 80 + (x1 - x0 - 160) * w, y), 7), grey)
            fnt = D.font("serif-italic", 62)
            y = y0 + 372
            a = smooth(ramp(t, A("slow.1", "name") - 0.2, 0.4))
            D.text(c, ASKED, x0 + 80, y, fnt, D.fill(theme.INK, a))
            struck = ease(ramp(t, A("slow.1", "ruled") - 0.1, 0.45))
            if struck > 0:
                w = D.text_width(ASKED, fnt)
                c.drawPath(D.capsule((x0 + 70, y - 18), (x0 + 70 + (w + 20) * struck, y - 22), 4.5), D.fill(theme.ALERT))
            said = A("slow.1", "only") + 0.25
            p = pop(t, said, 0.35)
            if p > 0:
                with D.moved(c, s=0.9 + 0.1 * p, about=(x0 + 80, y + 110)):
                    D.text(c, RULED, x0 + 80, y + 124, D.font("serif-bold", 68), D.fill(theme.HOST, clamp(p)))
            for i, w in enumerate((0.9, 0.97, 0.55)):
                y = y0 + 588 + 46 * i
                c.drawPath(D.capsule((x0 + 80, y), (x0 + 80 + (x1 - x0 - 160) * w, y), 7), grey)


# --- into English -------------------------------------------------------------------------------

PARIS, LONDON = (930, 850), (250, 390)
SEEN = "“… the right side of the Convention …”"


def english(c, t):
    """The words cross the Channel as news: a line from Paris to London, and where they are first seen in English."""
    theme.heading(c, "Into English", 110, 122, 64)
    go = A("english.1", "news") - 0.2
    path = D.curve([PARIS, (560, 790), (300, 600), LONDON], closed=False)
    for (x, y), name, align, cue in ((PARIS, "Paris", "l", T_ENGLISH + 0.2), (LONDON, "London", "l", go + 0.7)):
        k = pop(t, cue, 0.35)
        if k > 0:
            c.drawPath(D.oval(x, y, 18 * k), D.fill(theme.INK))
            D.text(c, name, x + 36, y + 17, D.font("black", 52), D.fill(theme.INK, clamp(k)), align)
    k = ease(ramp(t, go, 0.9))
    if k > 0:
        c.drawPath(D.part(path, 0.04, 0.04 + 0.9 * k), D.stroke(theme.INK, 6))
        (hx, hy), angle = D.along(path, 0.04 + 0.9 * k)
        with D.moved(c, rot=angle, about=(hx, hy)):
            c.drawPath(D.poly([(hx + 20, hy), (hx - 10, hy - 16), (hx - 10, hy + 16)]), D.fill(theme.INK))
    k = pop(t, A("english.1", "earliest") - 0.15, 0.4)
    if k > 0:
        x0, y0, x1, y1 = 520, 300, 1370, 640
        with D.layer(c, clamp(k * 1.5)):
            with D.moved(c, s=0.85 + 0.15 * k, about=(x0, y0 + 90)):
                c.drawPath(D.rect(x0 + 8, y0 + 14, x1 + 8, y1 + 14, 28), D.blurred(D.fill((60, 45, 30), 0.25), 18))
                c.drawPath(D.rect(x0, y0, x1, y1, 28), D.fill(theme.WHITE))
                D.text(c, "1794", x0 + 64, y0 + 132, D.font("black", 112), D.fill(theme.INK), track=-3)
                D.text(c, SEEN, x0 + 64, y0 + 222, D.font("serif-italic", 46), D.fill(theme.INK))
                D.paragraph(c, "from a translation of Camille Desmoulins, printed in London", x0 + 64, y0 + 286,
                            D.font("medium", 30), D.fill(theme.INK_SOFT), x1 - x0 - 128, 1.3)


def chart(c, t):
    CHART.draw(c, t)


# --- the opinion --------------------------------------------------------------------------------

LINE_Y, LINE_X0, LINE_X1 = 660, 1010, 1790
MINI = (1400, 310, 0.5)                     # the hall again, small: its middle, and its scale


def _columns():
    """Where each deputy lands on the line: in order of its seat from left to right, stacked in columns."""
    cols, per = 26, {}
    out = []
    for start, home, side in hall.DEPUTIES:
        col = min(cols - 1, int((home[0] - (hall.CX - 630)) / 1260 * cols))
        n = per.get(col, 0)
        per[col] = n + 1
        out.append((LINE_X0 + (col + 0.5) * (LINE_X1 - LINE_X0) / cols, LINE_Y - 16 - n * 13))
    return out


LANDING = _columns()


def opinion(c, t):
    drop = A("opinion.1", "one", 2) - 0.5
    theme.heading(c, "One line", LINE_X0, 122, 64, alpha=ease_out(ramp(t, drop, 0.5)))
    mx, my, ms = MINI
    for i, ((_, home, side), land) in enumerate(zip(hall.DEPUTIES, LANDING)):
        seen = smooth(ramp(t, T_OPINION + 0.2 + 0.4 * rnd("op", i), 0.3))
        k = ease(ramp(t, drop + 0.9 * rnd("fall", i), 0.9))
        sx, sy = mx + (home[0] - hall.CX) * ms, my + (home[1] - hall.CY) * ms
        x, y = lerp((sx, sy), land, k)
        r = lerp(6.2, 6.5, k) * seen
        c.drawPath(D.oval(x, y, r), D.fill(theme.SIDE_B if side == "r" else theme.SIDE_A))
    k = ease_out(ramp(t, drop - 0.1, 0.5))
    if k > 0:
        mid = (LINE_X0 + LINE_X1) / 2
        half = (LINE_X1 - LINE_X0) / 2 * k
        c.drawPath(D.capsule((mid - half, LINE_Y), (mid + half, LINE_Y), 5), D.fill(theme.INK))
        for word, x, align, colour, cue in (("left", LINE_X0, "l", theme.SIDE_A_DARK, A("opinion.1", "two")),
                                            ("right", LINE_X1, "r", theme.SIDE_B_DARK, A("opinion.1", "ends"))):
            a = smooth(ramp(t, cue - 0.1, 0.3))
            D.text(c, word, x, LINE_Y + 70, D.font("black", 56), D.fill(colour, a), align)
    # the questions that get squeezed onto it
    asks = ("taxes", "borders", "faith", "speech", "war", "trade", "schools", "drugs")
    t0 = A("opinion.1", "every") - 0.1
    fnt = D.font("bold", 36)
    for i, ask in enumerate(asks):
        start = t0 + 0.14 * i
        k = ease_out(ramp(t, start, 0.45))
        if k <= 0:
            continue
        x = LINE_X0 + 100 + (i % 4) * (LINE_X1 - LINE_X0 - 200) / 3
        y = lerp(LINE_Y + 420, LINE_Y + 150 + 72 * (i // 4), back(ramp(t, start, 0.45), 1.2))
        w = D.text_width(ask, fnt) + 44
        with D.layer(c, clamp(k * 2)):
            c.drawPath(D.box(x, y, w, 56, 28), D.fill(theme.WHITE))
            c.drawPath(D.box(x, y, w, 56, 28), D.stroke(theme.RULE, 2.5))
            D.text(c, ask, x, y + 12, fnt, D.fill(theme.INK), "m")


# --- the deal -----------------------------------------------------------------------------------

ROWS = [("fact", "has a source, on screen and below", A("deal.1", "fact") - 0.1),
        ("estimate", "a number that could be off", A("deal.2", "estimate") - 0.1),
        ("view", "what some people hold, in their words", A("deal.2", "view") - 0.3),
        ("opinion", "mine, and it says so", A("deal.2", "opinion") - 0.3),
        ("speculation", "nobody knows yet", A("deal.2", "guess") - 0.2)]


def deal(c, t):
    for i, (kind, gloss, cue) in enumerate(ROWS):
        k = pop(t, cue, 0.32, 1.5)
        if k <= 0:
            continue
        x, y = 640, 250 + 150 * i
        with D.layer(c, clamp(k * 1.5)):
            theme.tag(c, kind, x, y, 56, 0.7 + 0.3 * k)
            D.text(c, gloss, x + 510, y, D.font("medium", 38), D.fill(theme.INK_SOFT, ease_out(ramp(t, cue + 0.12, 0.3))))


# --- the frame ----------------------------------------------------------------------------------

CUTS = [(0.0, hook), (T_ROOM, room), (T_SLOW, slow), (T_ENGLISH, english), (T_CHART, chart), (T_OPINION, opinion),
        (T_DEAL, deal)]


def frame(t):
    s, c = theme.stage()
    theme.scenes(c, t, CUTS)
    pose, at = host_now(t)
    up = window(t, A("opinion.1", "opinion") - 0.25, T_DEAL - 0.1, 0.01, 0.3)
    if up > 0:
        k = back(ramp(t, A("opinion.1", "opinion") - 0.25, 0.4), 1.6) * up
        host.sign(c, "MY OPINION", host.hand_at(pose, at, "r"), at[2], theme.HOST, k)
    host.draw(c, pose, at, shadow=at[1] + at[2] * 3.25)
    theme.narration_label(c, N, SOURCES, t)
    return s
