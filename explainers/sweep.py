"""Draw every frame without encoding, to catch exceptions and find slow frames.

    python -m explainers.sweep VIDEO [--workers N] [--start S] [--end S] [--step N]

Exits non-zero if any frame raised; prints one traceback per distinct error.
"""
import argparse
import os
import sys
import time
import traceback
from multiprocessing import Pool

from explainers.video import build_inserts, load


def work(job):
    root, frames = job
    v = load(root)
    errs, slow = [], (0.0, None)
    for f in frames:
        t = f / v.fps
        a = time.time()
        try:
            v.rgb(t)
        except Exception:
            errs.append((t, traceback.format_exc(limit=6)))
        dt = time.time() - a
        if dt > slow[0]:
            slow = (dt, t)
    return errs, slow, len(frames)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 4))
    ap.add_argument("--start", type=float, default=0.0, help="first second to draw")
    ap.add_argument("--end", type=float, help="last second to draw (default: the end)")
    ap.add_argument("--step", type=int, default=1, help="draw every Nth frame")
    args = ap.parse_args()
    v = load(args.video)
    build_inserts(v)
    f0 = int(round(args.start * v.fps))
    f1 = v.frames if args.end is None else min(v.frames, int(round(args.end * v.fps)) + 1)
    frames = list(range(f0, f1, args.step))
    jobs = [(str(v.root), frames[i::64]) for i in range(64)]
    a = time.time()
    with Pool(args.workers) as pool:
        res = pool.map(work, jobs)
    errs = [e for r in res for e in r[0]]
    slow = max((r[1] for r in res), key=lambda s: s[0])
    print(f"{sum(r[2] for r in res)} frames in {time.time() - a:.0f}s, {len(errs)} errors, "
          f"slowest {slow[0]:.3f}s at t={slow[1]}")
    seen = set()
    for t, tb in errs:
        key = tb.strip().splitlines()[-1]
        if key not in seen:
            seen.add(key)
            print(f"--- t={t:.3f}\n{tb}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
