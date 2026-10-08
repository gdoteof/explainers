"""Render a video to mp4: python -m explainers.render VIDEO [--workers N] [--chunk F] [--end S] [--out PATH] [--fresh]

Frames are rendered by a process pool in chunks; each chunk is piped as raw RGB into its own ffmpeg/x264
segment under VIDEO/build/segments (finished segments are kept, so an interrupted render resumes; pass
--fresh after changing code or narration). The segments are then joined and muxed with the narration.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from multiprocessing import Pool

from explainers.ffmpeg import FFMPEG
from explainers.video import build_inserts, load

X264 = ["-c:v", "libx264", "-preset", "slow", "-crf", "16",
        "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-color_range", "tv", "-threads", "2"]


def seg_path(v, i):
    return v.build / "segments" / f"seg_{i:04d}.mp4"


def render_chunk(job):
    root, i, f0, f1 = job
    v = load(root)
    out = seg_path(v, i)
    tmp = out.with_suffix(".tmp.mp4")
    w, h = v.size
    cmd = [FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
           "-r", str(v.fps), "-i", "-", *X264, str(tmp)]
    t_start = time.time()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for f in range(f0, f1):
            proc.stdin.write(v.rgb(f / v.fps).tobytes())
    except BaseException:
        proc.stdin.close()
        proc.wait()
        tmp.unlink(missing_ok=True)
        raise
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed on segment {i}")
    tmp.rename(out)
    return i, f1 - f0, time.time() - t_start


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 4))
    ap.add_argument("--chunk", type=int, default=60)
    ap.add_argument("--end", type=float, help="seconds to render (default: the whole video)")
    ap.add_argument("--out", help="default: the video's OUTPUT")
    ap.add_argument("--fresh", action="store_true", help="discard finished segments and inserts first")
    args = ap.parse_args()

    v = load(args.video)
    build_inserts(v, force=args.fresh)
    seg_dir = v.build / "segments"
    if args.fresh and seg_dir.exists():
        shutil.rmtree(seg_dir)
    seg_dir.mkdir(parents=True, exist_ok=True)
    for tmp in seg_dir.glob("*.tmp.mp4"):
        tmp.unlink()
    end = v.end if args.end is None else args.end
    n = int(round(end * v.fps))
    jobs = [(str(v.root), i, f0, min(n, f0 + args.chunk)) for i, f0 in enumerate(range(0, n, args.chunk))]
    todo = [j for j in jobs if not seg_path(v, j[1]).exists()]
    print(f"{n} frames in {len(jobs)} segments, {len(todo)} to render with {args.workers} workers", flush=True)

    t0, done = time.time(), 0
    with Pool(args.workers) as pool:
        for i, nf, dt in pool.imap_unordered(render_chunk, todo):
            done += 1
            if done % 10 == 0 or done == len(todo):
                print(f"  {done}/{len(todo)} segments, {time.time() - t0:.0f}s", flush=True)

    listing = seg_dir / "concat.txt"
    listing.write_text("".join(f"file '{seg_path(v, j[1]).name}'\n" for j in jobs))
    dur = n / v.fps
    out = args.out or str(v.output)
    cmd = [FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing)]
    if v.audio:
        cmd += ["-i", str(v.audio), "-map", "0:v", "-map", "1:a", "-af", "apad", "-ar", "48000", "-ac", "2",
                "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "copy", "-t", f"{dur:.3f}", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    print(f"wrote {out} ({dur:.1f}s) in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    sys.exit(main())
