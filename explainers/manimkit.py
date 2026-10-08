"""The video's look and clock inside manim. Import it only from a scene file: it loads manim, which is slow.

    from explainers.manimkit import *

    class WordsInBooks(Insert):
        def construct(self):
            axes = Axes(...)
            self.play(Create(axes), run_time=1.0)
            self.until(self.cue("english.1", "nineteen"))       # wait for the word
            self.play(Create(line), run_time=self.cue("english.2") - self.now)

The frame is 16 by 9 manim units (so a unit is 120 pixels of a 1920x1080 frame) with the origin in the
middle and y up. The background is transparent: the video puts its own paper behind the clip.
"""
import os
from pathlib import Path

import manimpango
from manim import *  # noqa: F401,F403
from manim import ManimColor, Scene, Text, config

from explainers import theme
from explainers.draw import FONT_DIR, FONTS
from explainers.narration import Narration

for _file in set(FONTS.values()):
    manimpango.register_font(str(FONT_DIR / _file))

config.frame_height = 9.0
config.frame_width = 16.0
config.background_opacity = 0.0

PX = 1 / 120                                # a pixel of the 1920x1080 frame, in manim units


def colour(rgb):
    return ManimColor.from_rgb(tuple(int(v) for v in rgb))


INK, INK_SOFT, RULE, PAPER, WHITE = (colour(c) for c in (theme.INK, theme.INK_SOFT, theme.RULE, theme.PAPER, theme.WHITE))
SIDE_A, SIDE_B, HOST, ALERT = (colour(c) for c in (theme.SIDE_A, theme.SIDE_B, theme.HOST, theme.ALERT))
SIDE_A_DARK, SIDE_B_DARK = colour(theme.SIDE_A_DARK), colour(theme.SIDE_B_DARK)


def at(x, y):
    """A point of the 1920x1080 frame (pixels, y down) as a manim point."""
    return np.array([(x - 960) * PX, (540 - y) * PX, 0.0])


def words(s, px=40, colour=INK, weight="MEDIUM", font="Inter", **kw):
    """Type in the video's face at a size in pixels of the 1920x1080 frame, as the Skia side measures it."""
    return Text(s, font=font, weight=weight, color=colour, font_size=px * 0.5994, **kw)


class Insert(Scene):
    """A scene on the video's clock: time 0 is the clip's `start` in the video."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.t0 = float(os.environ.get("EXPLAINERS_T0", "0"))
        root = os.environ.get("EXPLAINERS_VIDEO")
        self.narration = Narration(root) if root and (Path(root) / "data" / "narration.json").exists() else None

    @property
    def now(self):
        """Seconds since the clip started."""
        return self.renderer.time

    def cue(self, beat, word=None, nth=1):
        """A narration cue on the clip's clock."""
        return self.narration.at(beat, word, nth) - self.t0

    def cue_end(self, beat, word=None, nth=1):
        return self.narration.end(beat, word, nth) - self.t0

    def wait(self, duration=1.0, stop_condition=None, frozen_frame=False):
        """A hold that writes every frame. Manim's own default writes a still hold as one PNG, which would
        put everything after it early in the video."""
        super().wait(duration, stop_condition=stop_condition, frozen_frame=frozen_frame)

    def until(self, t):
        """Hold until the clip's clock reads t. Does nothing if it already does."""
        if t - self.now > 1 / config.frame_rate:
            self.wait(t - self.now)

    def left(self, t, least=0.2):
        """Seconds from now until t, for an animation that should end on a cue (never less than `least`)."""
        return max(least, t - self.now)
