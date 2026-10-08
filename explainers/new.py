"""Start a new video from videos/_template.

    python -m explainers.new NAME      -> videos/NAME/ (script.md, sources.toml, video.py)

A folder that holds only research so far (a sources.toml and no script) is filled in around what is there.
Then write script.md and sources.toml, and run `python -m explainers.check videos/NAME`.
"""
import re
import shutil
import sys
from pathlib import Path

VIDEOS = Path(__file__).resolve().parent.parent / "videos"


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", sys.argv[1]):
        raise SystemExit("usage: python -m explainers.new NAME   (lower-case letters, digits and hyphens)")
    dst = VIDEOS / sys.argv[1]
    if (dst / "script.md").exists():
        raise SystemExit(f"{dst} already has a script")
    kept = sorted(p.name for p in dst.iterdir()) if dst.exists() else []
    skip = shutil.ignore_patterns("build", "audio", "data", "__pycache__", "*.mp4", *kept)
    shutil.copytree(VIDEOS / "_template", dst, ignore=skip, dirs_exist_ok=True)
    if kept:
        print(f"filled in {dst} around {', '.join(kept)}; next: write script.md")
    else:
        print(f"created {dst}; next: write script.md and sources.toml")


if __name__ == "__main__":
    main()
