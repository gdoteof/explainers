"""Loading a video: a directory (usually videos/<name>/) with a video.py.

video.py is the contract between a video and the shared tools:

    def frame(t): ...             the picture at t seconds: a skia.Surface or skia.Image, an (h, w, 3 or 4)
                                  uint8 array, or a PIL image, of SIZE. A pure function of t: frames are
                                  rendered in parallel and in any order.
    FPS = 30                      optional
    SIZE = (1920, 1080)           optional
    END = 92.5                    optional, seconds to render. Default: the narration's length
    AUDIO = ROOT / "audio" / "narration.wav"    optional. Default: that file if it exists, else silence
    OUTPUT = ROOT / "name.mp4"    optional, defaults to <dir name>.mp4
    def label(t): ...             optional, a caption for preview sheets. Default: the beat and the words said

A video's modules import each other flat (`import scenes`), so its directory goes on sys.path; only one
video is loaded per process. The explainers.inserts.Clips it makes are rendered before any frame is.
"""
import importlib
import json
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

import numpy as np
import skia


@dataclass(frozen=True)
class Video:
    root: Path
    fps: int
    end: float
    size: tuple
    audio: Path | None
    output: Path
    frame: Callable
    label: Callable
    module: object

    @property
    def build(self):
        return self.root / "build"

    @property
    def frames(self):
        return int(round(self.end * self.fps))

    def rgb(self, t):
        """The frame at t as (h, w, 3) uint8."""
        img = self.frame(t)
        if isinstance(img, skia.Surface):
            img = img.makeImageSnapshot()
        if isinstance(img, skia.Image):
            img = img.toarray(colorType=skia.kRGBA_8888_ColorType)
        a = np.asarray(img)
        w, h = self.size
        if a.shape[:2] != (h, w):
            raise ValueError(f"frame({t:.3f}) is {a.shape[1]}x{a.shape[0]}, not {w}x{h}")
        return np.ascontiguousarray(a[..., :3])


def _default_label(root):
    path = root / "data" / "narration.json"
    if not path.exists():
        return lambda t: ""
    from explainers.narration import Narration
    n = Narration(root)

    def label(t):
        b = n.beat_at(t)
        return "" if b is None else f"{b.id} [{b.kind}] {n.said(t)[-52:]}"
    return label


@lru_cache(maxsize=None)
def load(path):
    root = Path(path).resolve()
    if not (root / "video.py").is_file():
        raise SystemExit(f"{root} is not a video (no video.py)")
    sys.path.insert(0, str(root))
    mod = importlib.import_module("video")
    if Path(mod.__file__).resolve().parent != root:
        raise RuntimeError(f"imported {mod.__file__} instead of {root}/video.py")
    narration = root / "data" / "narration.json"
    end = getattr(mod, "END", None)
    if end is None:
        if not narration.exists():
            raise SystemExit(f"{root}: no END in video.py and no narration yet (python -m explainers.narrate {path})")
        end = json.loads(narration.read_text())["duration"]
    audio = getattr(mod, "AUDIO", root / "audio" / "narration.wav")
    return Video(root=root, fps=getattr(mod, "FPS", 30), end=float(end),
                 size=tuple(getattr(mod, "SIZE", (1920, 1080))),
                 audio=Path(audio) if audio and Path(audio).exists() else None,
                 output=Path(getattr(mod, "OUTPUT", root / f"{root.name}.mp4")),
                 frame=mod.frame, label=getattr(mod, "label", None) or _default_label(root), module=mod)


def build_inserts(video, force=False):
    """Render the video's manim clips that are out of date. Call it before any worker draws a frame."""
    from explainers import inserts
    for clip in inserts.CLIPS:
        clip.build(video, force=force)
