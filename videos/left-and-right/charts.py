"""The chart: how often English books say "left-wing" and "right-wing", 1800 to 2019 (data/ngram.json).

The lines are five-year averages of Google's yearly counts. They draw themselves across the nineteenth
century while the narration says how little there is to see, and reach the 1920s when it does.
"""
import json
from pathlib import Path

from explainers.manimkit import *

DATA = json.loads((Path(__file__).resolve().parent / "data" / "ngram.json").read_text())
Y0 = DATA["first_year"]


def series(name, half=2):
    """[(year, uses per million words)], averaged over the five years around each."""
    raw = [v * 1e6 for v in DATA[name]]
    out = []
    for i in range(len(raw)):
        span = raw[max(0, i - half):i + half + 1]
        out.append((Y0 + i, sum(span) / len(span)))
    return out


class WordsInBooks(Insert):
    def construct(self):
        ax = Axes(x_range=[1800, 2020, 50], y_range=[0, 2.5, 0.5], x_length=10.4, y_length=4.8, tips=False,
                  axis_config=dict(color=INK, stroke_width=3, tick_size=0.07))
        ax.move_to(at(800, 535))
        years = VGroup(*(words(str(y), 30, INK_SOFT).next_to(ax.c2p(y, 0), DOWN, buff=0.2) for y in range(1800, 2001, 50)))
        levels = VGroup(*(words(f"{v:g}", 30, INK_SOFT).next_to(ax.c2p(1800, v), LEFT, buff=0.2) for v in (1, 2)))
        title = words("In English books", 64, weight="HEAVY").move_to(at(110, 100), aligned_edge=LEFT)
        sub = words("uses per million words, five-year average", 30, INK_SOFT)
        sub.next_to(years, DOWN, buff=0.22).align_to(ax, LEFT)

        left = ax.plot_line_graph(*zip(*series("left-wing")), add_vertex_dots=False, line_color=SIDE_A, stroke_width=9)
        right = ax.plot_line_graph(*zip(*series("right-wing")), add_vertex_dots=False, line_color=SIDE_B, stroke_width=9)
        # the key, in the empty top left of the plot: each name arrives as the narration says it
        key = VGroup()
        for name, colour, dark, level in (("“left-wing”", SIDE_A, SIDE_A_DARK, 2.2), ("“right-wing”", SIDE_B, SIDE_B_DARK, 1.82)):
            swatch = Line(ax.c2p(1812, level), ax.c2p(1826, level), color=colour, stroke_width=9)
            key.add(VGroup(swatch, words(name, 42, dark, weight="BOLD").next_to(swatch, RIGHT, buff=0.2)))

        band = Rectangle(width=ax.c2p(1940, 0)[0] - ax.c2p(1920, 0)[0], height=4.8, stroke_width=0,
                         fill_color=HOST, fill_opacity=0.14).move_to(ax.c2p(1930, 1.25))
        band_name = words("1920s and 30s", 34, HOST, weight="BOLD").next_to(band, UP, buff=0.12)
        room = VGroup(Dot(ax.c2p(1789, 0), radius=0.09, color=INK),
                      words("1789: the room", 30, INK, weight="BOLD"))
        room[1].next_to(room[0], UP, buff=0.5).shift(RIGHT * 1.6)
        pointer = Line(room[1].get_bottom() + DOWN * 0.06 + LEFT * 0.75, room[0].get_center() + UP * 0.14, color=INK, stroke_width=3)

        self.play(Create(ax), FadeIn(title, shift=UP * 0.15), run_time=0.7)
        self.play(FadeIn(years), FadeIn(levels), FadeIn(sub), run_time=0.4)
        self.play(FadeIn(room[0], scale=2.5), FadeIn(room[1]), Create(pointer), run_time=0.5)

        # the pen crosses the flat century by the time the narration reaches the twenties, then climbs
        takeoff = self.cue("english.3", "twenties")
        frac = (1920 - 1800) / (2019 - 1800)
        flat_l = left["line_graph"].copy().pointwise_become_partial(left["line_graph"], 0, frac)
        flat_r = right["line_graph"].copy().pointwise_become_partial(right["line_graph"], 0, frac)
        rest_l = left["line_graph"].copy().pointwise_become_partial(left["line_graph"], frac, 1)
        rest_r = right["line_graph"].copy().pointwise_become_partial(right["line_graph"], frac, 1)
        self.until(self.cue("english.2", "left-wing") - 0.15)
        self.play(FadeIn(key[0], shift=RIGHT * 0.15), run_time=0.3)
        self.until(self.cue("english.2", "right-wing") - 0.15)
        self.play(FadeIn(key[1], shift=RIGHT * 0.15), run_time=0.3)
        self.until(self.cue("english.2", "books") - 0.3)
        self.play(Create(flat_l), Create(flat_r), run_time=self.left(takeoff - 0.2), rate_func=linear)
        self.play(FadeIn(band), FadeIn(band_name, shift=UP * 0.1), run_time=0.35)
        self.play(Create(rest_l), Create(rest_r), run_time=2.2, rate_func=rate_functions.ease_out_sine)
        self.wait(0.5)
