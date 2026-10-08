"""Check a script against its sources: python -m explainers.check VIDEO [--urls]

Every paragraph has to be labelled, every fact, estimate and view has to cite a source in sources.toml,
and every cited source has to say where it is and quote the passage that backs the script. Prints the
script's length and how it divides between the kinds of statement. `--urls` also fetches every source's
URL. Exits non-zero if anything is wrong; `narrate` runs the same check and refuses a script that fails.
"""
import argparse
import sys
import urllib.request
from collections import Counter

from explainers import script as S

WPM = 155                                   # what the voice does, near enough to plan with


def report(root):
    """(script, sources, errors, warnings) for the video at root."""
    script = S.load(root)
    sources, source_errors = S.load_sources(root)
    errors, warnings = S.problems(script, sources, source_errors)
    return script, sources, errors, warnings


def fetch(url):
    """None if the URL answers, else what went wrong."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (explainers source check)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return None if r.status < 400 else f"HTTP {r.status}"
    except Exception as e:                  # a dead link, a refusal, a timeout: all worth a look by hand
        return str(e)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video")
    ap.add_argument("--urls", action="store_true", help="fetch every source's URL")
    args = ap.parse_args()
    script, sources, errors, warnings = report(args.video)

    words = S.word_count(script)
    pauses = sum(b.pause for b in script.beats)
    print(f"{script.title}: {len(script.beats)} beats in {len(script.sections)} sections, {words} words, "
          f"about {words / WPM * 60 + pauses:.0f}s at {WPM} words a minute")
    by_kind = Counter()
    for b in script.beats:
        by_kind[b.kind] += len(b.plain.split())
    print("  " + ", ".join(f"{k} {by_kind[k] * 100 // max(1, words)}%" for k in S.KINDS if by_kind[k]))
    print(f"  {len(sources)} sources")
    if args.urls:
        for key, s in sources.items():
            if s.url:
                bad = fetch(s.url)
                if bad:
                    warnings.append(f"source {key}: {s.url} did not load ({bad})")
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
