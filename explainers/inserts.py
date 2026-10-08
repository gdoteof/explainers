"""Manim clips inside a video.

A video draws its frames with Skia, but a chart or a piece of mathematics is less work, and looks better,
in manim. Write the scene in a file of the video (a subclass of explainers.manimkit.Insert), and make a
Clip for it in video.py:

    CHART = Clip(ROOT, "charts.py", "WordsInBooks", start=N.at("english.1") - 0.5)

    def frame(t):
        ...
        CHART.draw(c, t)            # nothing before `start`; the last frame once the scene has ended

The scene is rendered once, as transparent PNG frames at the video's size and frame rate, into
VIDEO/build/inserts/<Scene>, and again whenever the scene's file, the narration or the start changes
(`render`, `preview` and `sweep` see to that before they draw). Inside the scene, `self.cue(beat, word)` is
a narration cue on the clip's own clock, so the chart moves on the words like everything else.

Needs the manim extra: uv sync --extra manim.
"""
import hashlib
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import skia

CLIPS = []                                  # every Clip made in this process, for explainers.video.build_inserts


class Clip:
    def __init__(self, root, file, scene, start=0.0):
        self.root, self.file, self.scene, self.start = Path(root), file, scene, float(start)
        self.dir = self.root / "build" / "inserts" / scene
        self._count = None
        CLIPS.append(self)

    def _stamp(self, video):
        h = hashlib.sha1()
        for path in (self.root / self.file, Path(__file__).with_name("manimkit.py"), Path(__file__).with_name("theme.py"),
                     self.root / "data" / "narration.json"):
            h.update(path.read_bytes() if path.exists() else b"-")
        h.update(f"{self.start:.3f}|{video.fps}|{video.size}".encode())
        return h.hexdigest()

    def build(self, video, force=False):
        stamp = self._stamp(video)
        mark = self.dir / "stamp"
        if not force and mark.exists() and mark.read_text() == stamp:
            return
        if self.dir.exists():
            shutil.rmtree(self.dir)
        self.dir.mkdir(parents=True)
        w, h = video.size
        env = dict(os.environ, EXPLAINERS_VIDEO=str(self.root), EXPLAINERS_T0=f"{self.start:.3f}")
        print(f"manim: {self.file} {self.scene}", flush=True)
        cmd = [sys.executable, "-m", "manim", "render", "--format", "png", "-r", f"{w},{h}", "--fps", str(video.fps),
               "--media_dir", str(self.dir / "media"), "--disable_caching", "-v", "WARNING", "--progress_bar", "none",
               str(self.root / self.file), self.scene]
        done = subprocess.run(cmd, cwd=self.root, env=env, capture_output=True, text=True)
        frames = sorted((self.dir / "media").rglob(f"{self.scene}*.png"))
        if done.returncode != 0 or not frames:
            raise SystemExit(f"manim failed on {self.scene}:\n{done.stdout[-3000:]}\n{done.stderr[-3000:]}")
        (self.dir / "frames").mkdir()
        for i, path in enumerate(frames):
            path.rename(self.dir / "frames" / f"{i:05d}.png")
        shutil.rmtree(self.dir / "media")
        mark.write_text(stamp)
        self._count = None

    @property
    def count(self):
        if self._count is None:
            self._count = len(list((self.dir / "frames").glob("*.png")))
        return self._count

    def image(self, t, fps=30):
        """The clip's frame at video time t as a skia.Image: None before the clip starts, its last frame after it ends."""
        i = int(round((t - self.start) * fps))
        if i < 0 or not self.count:
            return None
        return _load(str(self.dir / "frames" / f"{min(i, self.count - 1):05d}.png"))

    def draw(self, canvas, t, fps=30, alpha=1.0, x=0.0, y=0.0):
        img = self.image(t, fps)
        if img is not None and alpha > 0:
            canvas.drawImage(img, x, y, skia.SamplingOptions(), skia.Paint(Alphaf=min(1.0, alpha)))

    def end(self, fps=30):
        """When the scene's own animation is over, in video time."""
        return self.start + self.count / fps


@lru_cache(maxsize=8)
def _load(path):
    return skia.Image.open(path)
