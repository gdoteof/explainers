"""Animation helpers: clamping, ramps, easing curves, and randomness that is the same in every worker.

Frames render in parallel and in any order, so nothing here keeps state: every curve is a function of time.
"""
import math
import zlib


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def lerp(a, b, k):
    """From a to b by k. Numbers, or tuples of numbers (points, colours)."""
    if isinstance(a, (tuple, list)):
        return tuple(x + (y - x) * k for x, y in zip(a, b))
    return a + (b - a) * k


def ramp(t, t0, dur):
    """0 before t0, 1 from t0 + dur, a straight line between."""
    return clamp((t - t0) / dur) if dur > 0 else float(t >= t0)


def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x, p=3):
    return 1 - (1 - clamp(x)) ** p


def ease_in(x, p=3):
    return clamp(x) ** p


def ease(x):
    """Slow, fast, slow."""
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def back(x, s=1.7):
    """Ease out past 1 and settle: how a thing pops in."""
    x = clamp(x) - 1
    return 1 + x * x * ((s + 1) * x + s)


def elastic(x, wobbles=2.0, damp=5.0):
    """Ease to 1 with a decaying wobble."""
    x = clamp(x)
    return 1 - math.exp(-damp * x) * math.cos(wobbles * 2 * math.pi * x) if x < 1 else 1.0


def move(t, t0, dur=0.5, curve=ease):
    """How far along a move that starts at t0 and takes dur is, 0..1."""
    return curve(ramp(t, t0, dur))


def pop(t, t0, dur=0.3, s=1.7):
    """A thing's scale as it pops in at t0: 0 before, overshooting to 1."""
    return 0.0 if t < t0 else back((t - t0) / dur, s)


def window(t, t0, t1, fade_in=0.3, fade_out=0.3):
    """1 between t0 and t1, easing up over fade_in from t0 and down over fade_out to t1: how visible a thing is."""
    if t < t0 or t > t1:
        return 0.0
    return min(smooth((t - t0) / fade_in) if fade_in else 1.0, smooth((t1 - t) / fade_out) if fade_out else 1.0)


def rnd(*key):
    """A fixed random number in [0, 1) for a key: the same on every frame and in every worker."""
    return zlib.crc32(repr(key).encode()) / 2 ** 32


def drift(t, key, speed=1.0):
    """A slow wander in [-1, 1] that never repeats exactly: breathing, hovering, attention."""
    a, b, c = rnd(key, 1), rnd(key, 2), rnd(key, 3)
    return (math.sin(t * speed * (0.9 + a) + 6.28 * b) + 0.6 * math.sin(t * speed * (1.7 + b) + 6.28 * c)
            + 0.3 * math.sin(t * speed * (2.9 + c) + 6.28 * a)) / 1.9
