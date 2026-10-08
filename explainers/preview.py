"""Preview frames: python -m explainers.preview VIDEO NAME WHEN... [--full] [--cols N]

WHEN is a time in seconds, a range `a:b:step`, a beat id (three frames through that beat), a section id
(three frames through each of its beats) or `beats` (every beat). Writes VIDEO/build/preview/NAME.png, a
contact sheet captioned with the time, the beat and the words being said. `--full` also writes each
frame at full size as NAME_<t>.png.
"""
import argparse
from multiprocessing import Pool

from PIL import Image

from explainers.sheet import contact_sheet
from explainers.video import build_inserts, load


def through(t0, t1):
    """Three times in a beat: just in, the middle, the last word."""
    return [round(t0 + 0.25, 3), round((t0 + t1) / 2, 3), round(t1 - 0.05, 3)]


def parse_times(args, root):
    beats = None
    ts = []
    for a in args:
        try:
            if a.count(":") == 2:
                lo, hi, step = (float(x) for x in a.split(":"))
                ts += [round(lo + i * step, 3) for i in range(int((hi - lo) / step + 1e-9) + 1)]
            else:
                ts.append(float(a))
            continue
        except ValueError:
            pass
        if beats is None:
            from explainers.narration import Narration
            beats = Narration(root).beats
        hits = [b for b in beats if a in ("beats", b.id, b.section)]
        if not hits:
            raise SystemExit(f"{a!r} is not a time, a range, a beat or a section")
        for b in hits:
            ts += through(b.t0, b.t1)
    return ts


def render_one(job):
    root, name, t, full = job
    v = load(root)
    img = Image.fromarray(v.rgb(t))
    if full:
        img.save(v.build / "preview" / f"{name}_{t:08.3f}.png")
    return img.resize((640, 360), Image.LANCZOS), f"{t:.2f}  {v.label(t)}"[:86]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video")
    ap.add_argument("name")
    ap.add_argument("when", nargs="+")
    ap.add_argument("--full", action="store_true", help="also save every frame at full size")
    ap.add_argument("--cols", type=int, default=3)
    args = ap.parse_args()
    v = load(args.video)
    ts = [t for t in parse_times(args.when, v.root) if 0 <= t <= v.end]
    build_inserts(v)
    out_dir = v.build / "preview"
    out_dir.mkdir(parents=True, exist_ok=True)
    with Pool(min(len(ts), 16)) as pool:
        tiles = pool.map(render_one, [(str(v.root), args.name, t, args.full) for t in ts])
    print(contact_sheet(tiles, out_dir / f"{args.name}.png", cols=args.cols))


if __name__ == "__main__":
    main()
