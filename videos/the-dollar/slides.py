"""What goes on the projector in "Where a Federal Dollar Goes". A slide is a 1920x1080 picture drawn on a
canvas; the set puts it on its screen (explainers/sets.py).

The cents are the Treasury's outlays by function for fiscal 2025 over the total (sources.toml: mts), and
"everything else" is what is left after the receipts the Treasury books as negative spending.
"""
from explainers import draw as D
from explainers import theme
from explainers.anim import clamp, ease_out

# (name, cents of the dollar, as the script says it, colour): the biggest first, as the script cuts them
SLICES = [
    ("Social Security", 22.5, "22½¢", theme.HOST),
    ("Medicare", 14.2, "14¢", theme.SIDE_B),
    ("Health", 14.0, "14¢", theme.SIDE_B_DARK),
    ("Interest", 13.8, "14¢", theme.ALERT),
    ("Military", 13.1, "13¢", theme.INK_SOFT),
    ("Income security", 10.0, "10¢", theme.SIDE_A),
    ("Veterans", 5.4, "5¢", theme.SIDE_A_DARK),
    ("Everything else", 7.0, "7¢", (150, 142, 128)),
]
X0, X1, TOP, BOTTOM = 130, 1790, 400, 640
CENT = (X1 - X0) / 100


def dollar(c, cut=len(SLICES), title="One dollar of federal spending", note="Fiscal year 2025"):
    """The dollar as a bar of a hundred cents. `cut` is how many slices have been cut off and named so
    far; a fraction is the next one on its way."""
    theme.heading(c, title, X0, 190, 92)
    D.text(c, note, X0, 262, D.font("medium", 44), D.fill(theme.INK_SOFT))
    c.drawPath(D.rect(X0, TOP, X1, BOTTOM, 16), D.fill(theme.PAPER_DARK))
    x = X0
    for i, (name, value, said, colour) in enumerate(SLICES):
        w = value * CENT
        k = ease_out(clamp(cut - i))
        if k > 0:
            with D.layer(c, k):
                with D.moved(c, y=-26 * (1 - k)):
                    c.drawPath(D.rect(x + 4, TOP, x + w - 4, BOTTOM, 14), D.fill(colour))
                    size = 76 if w > 190 else 60 if w > 120 else 44
                    D.text(c, said, x + w / 2, (TOP + BOTTOM) / 2 + size * 0.36, D.font("black", size),
                           D.fill(theme.WHITE), "m", track=-size * 0.02)
                low = i % 2 == 1 and w < 240                # narrow neighbours take turns on two lines
                y = BOTTOM + (132 if low else 62)
                if low:
                    c.drawPath(D.capsule((x + w / 2, BOTTOM + 12), (x + w / 2, BOTTOM + 84), 2.5), D.fill(theme.RULE))
                fnt = D.font("bold", 40)
                for line in D.wrap(name, fnt, max(w - 10, 200)):
                    D.text(c, line, x + w / 2, y, fnt, D.fill(theme.INK), "m")
                    y += 48
        x += w
