import numpy as np
import pytest

from explainers import draw as D
from explainers import sets, theme

ROOM = sets.Classroom()


def test_the_screen_has_the_frame_s_shape():
    x0, y0, x1, y1 = ROOM.SCREEN
    assert (x1 - x0) / (y1 - y0) == pytest.approx(theme.W / theme.H)


def test_the_wide_shot_is_the_room_as_drawn():
    m = ROOM.view(0.0)
    p = m.mapXY(300, 700)
    assert (p.x(), p.y()) == pytest.approx((300, 700))


def test_the_close_shot_fills_the_frame_with_the_screen():
    x0, y0, x1, y1 = ROOM.SCREEN
    m = ROOM.view(1.0)
    a, b = m.mapXY(x0, y0), m.mapXY(x1, y1)
    assert (a.x(), a.y()) == pytest.approx((0, 0), abs=1e-3)
    assert (b.x(), b.y()) == pytest.approx((theme.W, theme.H), abs=1e-3)


def test_the_camera_only_goes_in_as_the_zoom_rises():
    scales = [ROOM.view(z).getScaleX() for z in (0.0, 0.25, 0.5, 0.75, 1.0)]
    assert scales == sorted(scales)
    assert scales[2] / scales[1] == pytest.approx(scales[3] / scales[2])       # an even speed


def test_shots_ease_from_one_cue_to_the_next():
    keys = [(0.0, 0.0, 0.0), (2.0, 1.0, 1.0), (5.0, 0.0, 1.0)]
    assert sets.shots(keys, 1.9) == 0.0
    assert 0.0 < sets.shots(keys, 2.5) < 1.0
    assert sets.shots(keys, 4.0) == 1.0
    assert sets.shots(keys, 9.0) == 0.0


def test_a_slide_is_seen_as_drawn_in_the_close_shot_and_smaller_in_the_wide_one():
    def slide(c):
        c.drawPath(D.rect(0, 0, theme.W / 2, theme.H), D.fill(theme.HOST))

    def shot(zoom):
        s, c = theme.stage()
        ROOM.draw(c, zoom, slide=slide)
        return D.array(s)[..., :3].astype(int)

    close, wide = shot(1.0), shot(0.0)
    host, white = np.array(theme.HOST), np.array(theme.WHITE)
    assert abs(close[540, 300] - host).max() < 30 and abs(close[540, 1600] - white).max() < 30
    x0, y0, x1, y1 = ROOM.SCREEN
    y, quarter = (y0 + y1) // 2, (x1 - x0) // 4
    assert abs(wide[y, x0 + quarter] - host).max() < 30 and abs(wide[y, x1 - quarter] - white).max() < 30
