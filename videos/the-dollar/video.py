"""The baseline video: the host says the script, with the section's title, the words as they are said,
and the label for each kind of statement. Replace it scene by scene."""
from pathlib import Path

from explainers import draw as D
from explainers import host, theme
from explainers import script as S
from explainers.anim import ramp, smooth
from explainers.narration import Narration

ROOT = Path(__file__).resolve().parent
N = Narration(ROOT)
SOURCES, _ = S.load_sources(ROOT)
HOST_AT = (430, 470, 118)
GROUND = 900
TALK = host.Pose(turn=0.35, look_x=0.4)
POINT = host.Pose(turn=0.6, look_x=0.9, lean=3, rx=1.75, ry=0.55, grip_r="point", aim_r=-12)


def words(c, t):
    """The beat being said, set large: said words in ink, the rest waiting in grey."""
    b = N.beat_at(t)
    if b is None or t > b.t1 + 0.6:
        return
    fnt = D.font("bold", 56)
    x0, y, width = 800, 420, 960
    space = D.text_width(" ", fnt)
    x = x0
    for word, t0, _, _ in b.words:
        w = D.text_width(word, fnt)
        if x + w > x0 + width:
            x, y = x0, y + 78
        k = smooth(ramp(t, t0 - 0.05, 0.12))
        D.text(c, word, x, y - 6 * (1 - k), fnt, D.fill(D.mix(theme.RULE, theme.INK, k)))
        x += w + space


def frame(t):
    s, c = theme.stage()
    b = N.beat_at(t)
    if b is not None:
        theme.heading(c, dict(N.sections)[b.section] or b.section, 800, 250, 64, theme.INK_SOFT, font="bold")
    words(c, t)
    pose = host.perform([(0.0, TALK, 0.3)] + [(b.t0, POINT if i % 2 else TALK, 0.45) for i, b in enumerate(N.beats)], t)
    host.draw(c, host.alive(pose, t, N), HOST_AT, shadow=GROUND)
    theme.narration_label(c, N, SOURCES, t)
    return s
