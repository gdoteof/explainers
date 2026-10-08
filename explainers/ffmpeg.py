"""Locating ffmpeg.

Set FFMPEG to override the binary. A snap-packaged ffmpeg can only read and write under $HOME, so keep
audio and build output inside the repo, not /tmp.
"""
import os
import shutil

FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
QUIET = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y"]
