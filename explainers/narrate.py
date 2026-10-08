"""Speak a script: python -m explainers.narrate VIDEO [--voice NAME] [--speed X] [--force]

Each beat of script.md is synthesised on its own with Kokoro (on the CPU, a few times faster than real
time) and kept in VIDEO/build/narration, so a rerun only speaks the beats whose words changed. The beats
are then laid end to end with the script's pauses between them:

    VIDEO/audio/narration.wav    the whole narration
    VIDEO/data/narration.json    every beat and every word with its start and end: what the video is cut to
    VIDEO/data/voice.npy         how loud the voice is, 60 times a second, for the host's mouth

The voice gets a word wrong now and then, mostly names. VIDEO/say.txt fixes them, one per line:

    Gauville = go-VEEL          a respelling, read by the voice's own rules
    Versailles = /vɛɹsˈI/       or the phonemes themselves, between slashes

The report lists every word the voice had to guess at; listen to those first.
"""
import argparse
import hashlib
import json
import re
import sys
import warnings
from pathlib import Path

import numpy as np

from explainers import check
from explainers import script as S

SR = 24000
MODEL = "hexgrad/Kokoro-82M"
ENV_FPS = 60
HEAD, TAIL = 0.05, 0.14                     # seconds of the voice's own silence kept before and after a beat


def pipeline(voice):
    from kokoro import KPipeline
    warnings.filterwarnings("ignore")
    return KPipeline(lang_code="b" if voice[:1] == "b" else "a", repo_id=MODEL)


def read_say(root, pipe):
    """{word: "/phonemes/"} from say.txt; a respelling is turned into phonemes by the voice's own rules."""
    path, out = Path(root) / "say.txt", {}
    if not path.exists():
        return out
    for n, line in enumerate(path.read_text().splitlines(), 1):
        line = line.split("#")[0].strip()
        if not line:
            continue
        word, eq, how = (p.strip() for p in line.partition("="))
        if not (eq and word and how):
            raise SystemExit(f"say.txt:{n}: expected `Word = respelling` or `Word = /phonemes/`")
        if not (how.startswith("/") and how.endswith("/")):
            _, tokens = pipe.g2p(how.replace("-", " "))
            how = "/" + "".join((t.phonemes or "") + (" " if t.whitespace else "") for t in tokens).strip().replace(" ", "") + "/"
        out[word] = how
    return out


def spoken(text, say):
    """The beat's text with say.txt applied, as [word](/phonemes/) marks."""
    marked = [m.span() for m in S._SAID.finditer(text)]
    for word, how in sorted(say.items(), key=lambda kv: -len(kv[0])):
        def swap(m):
            if any(a <= m.start() < b for a, b in marked):
                return m.group(0)
            return f"[{m.group(0)}]({how})"
        text = re.sub(rf"(?<![\w\[]){re.escape(word)}(?![\w\]])", swap, text)
        marked = [m.span() for m in S._SAID.finditer(text)]
    return text


def speak(pipe, text, voice, speed):
    """(samples, [[word, start, end, phonemes, rating]]) for one beat, trimmed to the words. A word is what
    the script has between two spaces, punctuation and all ("problem.", "France's"); its times are those of
    its sounds, not of the pause after it."""
    chunks, words, offset, open_word = [], [], 0.0, None
    for r in pipe(text.replace("*", ""), voice=voice, speed=speed, split_pattern=None):
        audio = r.audio.numpy().astype(np.float32)
        for tok in r.tokens or []:
            sounded = tok.start_ts is not None and tok.end_ts is not None and re.search(r"\w", tok.text)
            if open_word is None and not sounded:
                if words:                                 # a dash or a quote mark standing alone
                    words[-1][0] += (" " if words[-1][5] else "") + tok.text
                    words[-1][5] = bool(tok.whitespace)
                continue
            if open_word is None:
                open_word = [tok.text, offset + tok.start_ts, offset + tok.end_ts, tok.phonemes or "", getattr(tok, "rating", None), False]
            else:
                open_word[0] += tok.text
                if sounded:
                    open_word[2] = offset + tok.end_ts
                    open_word[3] += tok.phonemes or ""
                    if getattr(tok, "rating", None) is not None:
                        open_word[4] = tok.rating if open_word[4] is None else min(open_word[4], tok.rating)
            if tok.whitespace:
                open_word[5] = True
                words.append(open_word)
                open_word = None
        if open_word is not None:
            words.append(open_word)
            open_word = None
        chunks.append(audio)
        offset += len(audio) / SR
    audio = np.concatenate(chunks)
    if not words:
        raise SystemExit(f"the voice gave no word timings for: {text!r}")
    a = max(0.0, words[0][1] - HEAD)
    b = min(len(audio) / SR, words[-1][2] + TAIL)
    audio = audio[int(a * SR):int(b * SR)].copy()
    n = int(0.03 * SR)
    audio[-n:] *= np.linspace(1.0, 0.0, n, dtype=np.float32)
    return audio, [[w, t0 - a, t1 - a, ph, rating] for w, t0, t1, ph, rating, _ in words]


def envelope(audio):
    """How loud the voice is, 0..1, ENV_FPS times a second: fast up, slow down, as a mouth moves."""
    hop = SR // ENV_FPS
    n = len(audio) // hop
    rms = np.sqrt((audio[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
    out = np.zeros(n, np.float32)
    level = 0.0
    for i, x in enumerate(rms):
        level = x if x > level else level * 0.72 + x * 0.28
        out[i] = level
    return np.clip(out / (np.percentile(out, 96) + 1e-9), 0.0, 1.0)


def dump(head, beats):
    """narration.json as text: a beat to a block and a word to a line, so that a diff of it can be read."""
    js = lambda x: json.dumps(x, ensure_ascii=False)
    out = [js(head)[:-1] + ', "beats": [']
    for i, b in enumerate(beats):
        rest = {k: v for k, v in b.items() if k != "words"}
        out.append(" " + js(rest)[:-1] + ', "words": [')
        out += [f"  {js(w)}{',' if k + 1 < len(b['words']) else ''}" for k, w in enumerate(b["words"])]
        out.append(" ]}" + ("," if i + 1 < len(beats) else ""))
    out.append("]}")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video")
    ap.add_argument("--voice", help="a Kokoro voice (default: the script's `voice:`)")
    ap.add_argument("--speed", type=float, help="default: the script's `speed:`")
    ap.add_argument("--force", action="store_true", help="speak every beat again")
    args = ap.parse_args()
    import soundfile as sf

    root = Path(args.video).resolve()
    script, sources, errors, _ = check.report(root)
    if errors:
        print("\n".join(f"error: {e}" for e in errors))
        return 1
    voice = args.voice or script.settings["voice"]
    speed = args.speed or script.settings["speed"]
    cache = root / "build" / "narration"
    cache.mkdir(parents=True, exist_ok=True)
    pipe = pipeline(voice)
    say = read_say(root, pipe)

    t = script.settings["lead"]
    pieces, beats, guessed = [], [], []
    for i, b in enumerate(script.beats):
        text = spoken(b.text, say)
        key = hashlib.sha1(f"{MODEL}|{voice}|{speed}|{text}".encode()).hexdigest()[:16]
        wav, meta = cache / f"{key}.wav", cache / f"{key}.json"
        if args.force or not (wav.exists() and meta.exists()):
            audio, words = speak(pipe, text, voice, speed)
            sf.write(wav, audio, SR, subtype="FLOAT")
            meta.write_text(json.dumps(words))
        audio, words = sf.read(wav, dtype="float32")[0], json.loads(meta.read_text())
        guessed += [(b.id, w, ph) for w, _, _, ph, rating in words if rating is not None and rating < 3]
        pieces.append((t, audio))
        beats.append(dict(id=b.id, section=b.section, kind=b.kind, sources=b.sources, text=b.plain,
                          t0=round(t, 3), t1=round(t + len(audio) / SR, 3),
                          words=[[w, round(t + t0, 3), round(t + t1, 3), ph] for w, t0, t1, ph, _ in words]))
        t += len(audio) / SR + b.pause
        if i + 1 < len(script.beats):
            t += script.settings["section_gap" if script.beats[i + 1].section != b.section else "gap"]
    duration = t + script.settings["tail"]

    track = np.zeros(int(duration * SR) + 1, np.float32)
    for t0, audio in pieces:
        i = int(round(t0 * SR))
        track[i:i + len(audio)] += audio
    track *= 0.9 / max(1e-6, float(np.abs(track).max()))
    (root / "audio").mkdir(exist_ok=True)
    (root / "data").mkdir(exist_ok=True)
    sf.write(root / "audio" / "narration.wav", track, SR, subtype="PCM_16")
    np.save(root / "data" / "voice.npy", (envelope(track) * 255).astype(np.uint8))
    (root / "data" / "narration.json").write_text(dump(
        dict(title=script.title, voice=voice, speed=speed, duration=round(duration, 3), env_fps=ENV_FPS,
             sections=[dict(id=sid, title=title) for sid, title in script.sections]), beats))

    print(f"{script.title}: {duration:.1f}s in {voice} at speed {speed:g}")
    for b in beats:
        print(f"  {b['t0']:7.2f}  {b['t1'] - b['t0']:5.2f}s  {b['id']:<16} {b['kind']:<11} {b['text'][:60]}")
    if guessed:
        print("the voice guessed at these (fix a wrong one in say.txt):")
        for beat_id, word, ph in guessed:
            print(f"  {beat_id:<16} {word:<18} /{ph}/")
    print(root / "audio" / "narration.wav")
    return 0


if __name__ == "__main__":
    sys.exit(main())
