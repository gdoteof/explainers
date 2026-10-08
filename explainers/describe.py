"""What goes under a video: python -m explainers.describe VIDEO

Writes VIDEO/build/description.txt (chapters from the script's sections, then every source in the order
it is first cited, with the times it backs something said) and VIDEO/build/captions.srt (the narration as
subtitles, on the words' own timings). Run it after `narrate`.
"""
import argparse
from pathlib import Path

from explainers import script as S
from explainers.narration import Narration


def clock(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def description(n, sources):
    out = []
    chapters = [(n.section(sid)[0], title or sid) for sid, title in n.sections]
    if len(chapters) >= 3:
        out += [f"{clock(0 if i == 0 else t)} {title}" for i, (t, title) in enumerate(chapters)] + [""]
    out += ["How to read this video: a statement marked FACT has a source, shown on screen and listed below. "
            "ESTIMATE marks a number that was measured or modelled and could be off. A VIEW is a position some "
            "people hold, put the way they would put it. MY OPINION and A GUESS are exactly that.", "", "Sources"]
    seen = []
    for b in n.beats:
        for key in b.sources:
            if key not in seen:
                seen.append(key)
    for key in seen:
        times = ", ".join(clock(b.t0) for b in n.beats if key in b.sources)
        out.append(f"[{times}] {sources[key].reference()}")
    return "\n".join(out) + "\n"


def captions(n, width=42):
    """SRT cues: each beat broken at sentence ends, and at commas once a line runs long."""
    cues = []
    for b in n.beats:
        line = []
        for i, w in enumerate(b.words):
            line.append(w)
            text = " ".join(x[0] for x in line)
            last = i + 1 == len(b.words)
            if last or w[0][-1:] in ".?!" or (len(text) > width * 0.6 and w[0][-1:] in ",;:") or len(text) > width * 1.6:
                cues.append((line[0][1], line[-1][2], text))
                line = []
    out = []
    for i, (t0, t1, text) in enumerate(cues):
        nxt = cues[i + 1][0] if i + 1 < len(cues) else t1 + 1.0
        out.append(f"{i + 1}\n{srt_time(t0)} --> {srt_time(min(nxt - 0.02, max(t1 + 0.25, t0 + 0.9)))}\n{text}\n")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video")
    args = ap.parse_args()
    root = Path(args.video).resolve()
    n = Narration(root)
    sources, _ = S.load_sources(root)
    (root / "build").mkdir(exist_ok=True)
    (root / "build" / "description.txt").write_text(description(n, sources))
    (root / "build" / "captions.srt").write_text(captions(n))
    print(description(n, sources))
    print(root / "build" / "captions.srt")


if __name__ == "__main__":
    main()
