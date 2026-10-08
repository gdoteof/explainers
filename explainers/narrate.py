"""Speak a script: python -m explainers.narrate VIDEO [--voice NAME] [--speed X] [--force]
                  python -m explainers.narrate VIDEO --audition am_michael af_heart bm_george ...

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

A swear word (script.RUDE) is the narrator's to say and not the viewer's to hear: it is covered with a tone
in the narration, and starred out in narration.json, so in the captions and wherever a picture shows the
words. The takes and the cached speech stay as they were said.

A beat with a take in the narrator's own voice (VIDEO/audio/takes, made by `python -m explainers.record`)
uses the take instead: it is cut to its words, matched in loudness to the others, and timed by listening
for the script's words in it (explainers/align.py). `--tts` ignores the takes.

Either way the finished narration is brought to -16 LUFS with its peaks under -1.5 dB, which is about what
a viewer's other videos are at; a recorded voice is evened out a little first (2.5:1 above its average).

`--audition` speaks the opening of the script (about twenty seconds) in each of the voices named, into
VIDEO/build/audition/<voice>.wav, and changes nothing else: for choosing a voice by ear.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np

from explainers import check
from explainers import script as S
from explainers.ffmpeg import FFMPEG

SR = 24000                                  # what the synthetic voice comes out at
OUT_SR = 48000                              # the narration, and a recorded take
LEVEL = 0.1                                 # how loud the voice is in every beat, when takes are mixed in (RMS)
LOUDNESS, PEAK = -16.0, -2.5                # the finished narration: LUFS, and where the limiter holds its samples (dB)
SQUEEZE = "acompressor=threshold=-20dB:ratio=2.5:attack=8:release=150:knee=4:detection=rms"     # for a recorded voice
MODEL = "hexgrad/Kokoro-82M"
ENV_FPS = 60
HEAD, TAIL = 0.05, 0.14                     # seconds of the voice's own silence kept before and after a beat
TAKE_HEAD, TAKE_TAIL = 0.08, 0.2            # and of the room, around a recorded take


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


def said(pipe, text):
    """[[word, phonemes]] for a beat: the words `speak` would report, without speaking them."""
    words, word = [], None
    for tok in pipe.g2p(text.replace("*", ""))[1]:
        if not re.search(r"\w", tok.text):
            if word is None and words:                    # a dash or a quote mark standing alone
                words[-1][0] += tok.text
            elif word is not None:
                word[0] += tok.text
        elif word is None:
            word = [tok.text, tok.phonemes or ""]
        else:
            word[0] += tok.text
            word[1] += tok.phonemes or ""
        if tok.whitespace and word is not None:
            words.append(word)
            word = None
    return words + ([word] if word is not None else [])


def recorded(pipe, text, path):
    """(samples at OUT_SR, words, the words it was unsure of) for a take in the narrator's own voice: what
    `speak` gives for the synthetic one, with the times found by listening for the script's words."""
    from explainers import align, record
    audio = record.load(path)
    words = said(pipe, text)
    spans = align.words(audio, record.SR, [w for w, _ in words])
    a, b = record.edges(audio, spans[0][0], spans[-1][1], TAKE_HEAD, TAKE_TAIL)
    b = min(len(audio) / OUT_SR, b)
    audio = audio[int(a * OUT_SR):int(b * OUT_SR)].copy()
    n = int(0.02 * OUT_SR)
    audio[:n] *= np.linspace(0.0, 1.0, n, dtype=np.float32)
    audio[-2 * n:] *= np.linspace(1.0, 0.0, 2 * n, dtype=np.float32)
    timed = [[w, round(max(0.0, t0 - a), 3), round(min(b, t1) - a, 3), ph, None] for (w, ph), (t0, t1, _) in zip(words, spans)]
    return audio, timed, [w for (w, _), (_, _, sure) in zip(words, spans) if sure < 0.3]


def bleep(audio, words, sr=OUT_SR, pitch=1000.0):
    """`audio` with a tone over each swear word in `words` ([word, start, end, ...] in seconds), about as
    loud as the voice around it. Returns the audio and how many words it covered."""
    from explainers import record
    spans = [(w[1], w[2]) for w in words if S.RUDE.search(w[0])]
    if not spans:
        return audio, 0
    audio, level = audio.copy(), record.voiced(audio) or float(np.sqrt((audio ** 2).mean()))
    for t0, t1 in spans:
        a, b = max(0, int((t0 - 0.02) * sr)), min(len(audio), int((t1 + 0.02) * sr))
        tone = np.sin(2 * np.pi * pitch * np.arange(b - a) / sr).astype(np.float32) * level * 0.8
        n = min(int(0.008 * sr), (b - a) // 2)
        ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
        tone[:n] *= ramp
        tone[len(tone) - n:] *= ramp[::-1]
        audio[a:b] *= np.concatenate([1 - ramp, np.zeros(b - a - 2 * n, np.float32), ramp])
        audio[a:b] += tone
    return audio, len(spans)


def bed(room, n, quiet, level):
    """The sound of the empty room, n samples of it, for the gaps between takes: `quiet` is 1 where nobody is
    speaking and 0 under a take, which brings its own room with it. Only the calmest few seconds of the
    recording are used, so a key press or a creak in it is not repeated down the track, and it is set to
    `level`, how loud the room is between the words of the takes (RMS), so that the gaps match them."""
    step, span = OUT_SR // 4, min(4 * OUT_SR, len(room) // 2)
    starts = range(0, len(room) - span + 1, step)
    loud = [max(float(np.sqrt((room[i + k:i + k + step] ** 2).mean())) for k in range(0, span - step + 1, step)) for i in starts]
    i = starts[int(np.argmin(loud))]
    loop = room[i:i + span].copy()
    hop = OUT_SR // 100
    frames = np.sqrt((loop[:len(loop) // hop * hop].reshape(-1, hop) ** 2).mean(axis=1))
    loop *= level / max(float(np.median(frames)), 1e-9)
    fade = int(0.1 * OUT_SR)
    if len(loop) > 2 * fade:                                  # the end of the loop melts into its start
        k = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        loop[:fade] = loop[:fade] * k + loop[-fade:] * (1 - k)
        loop = loop[:-fade]
    return np.tile(loop, n // len(loop) + 1)[:n] * quiet


def loudness(path, chain="anull"):
    """(LUFS, true peak in dB) of a file after `chain`, as ffmpeg measures them."""
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", str(path), "-af", f"{chain},loudnorm=print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    if r.returncode or "{" not in r.stderr:
        raise SystemExit(f"ffmpeg could not measure {path}:\n{r.stderr[-600:]}")
    got = json.loads(r.stderr[r.stderr.rindex("{"):])
    return float(got["input_i"]), float(got["input_tp"])


def finish(raw, out, squeeze):
    """The assembled track `raw` at the loudness a viewer expects, as `out`: evened out first when it is a
    recorded voice (`squeeze`), then turned up to LOUDNESS, with a limiter holding the peaks under PEAK."""
    chain = SQUEEZE if squeeze else "anull"
    gain = LOUDNESS - loudness(raw, chain)[0]
    limit = f"alimiter=limit={10 ** (PEAK / 20):.4f}:attack=5:release=80:level=false,atrim=start=0.005,asetpts=PTS-STARTPTS"    # it looks 5 ms ahead
    r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw), "-af", f"{chain},volume={gain:.2f}dB,{limit}",
                        "-ar", str(OUT_SR), "-ac", "1", "-c:a", "pcm_s24le", str(out)], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"ffmpeg could not finish the narration:\n{r.stderr[-600:]}")
    return loudness(out)


def envelope(audio, sr=SR):
    """How loud the voice is, 0..1, ENV_FPS times a second: fast up, slow down, as a mouth moves."""
    hop = sr // ENV_FPS
    n = len(audio) // hop
    rms = np.sqrt((audio[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
    out = np.zeros(n, np.float32)
    level = 0.0
    for i, x in enumerate(rms):
        level = x if x > level else level * 0.72 + x * 0.28
        out[i] = level
    return np.clip(out / (np.percentile(out, 96) + 1e-9), 0.0, 1.0)


def audition(root, script, voices, speed, seconds=20.0):
    """The opening of the script in each voice, as VIDEO/build/audition/<voice>.wav."""
    import soundfile as sf
    out = root / "build" / "audition"
    out.mkdir(parents=True, exist_ok=True)
    for voice in voices:
        pipe = pipeline(voice)
        say = read_say(root, pipe)
        pieces, total = [], 0.0
        for b in script.beats:
            audio, _ = speak(pipe, spoken(b.text, say), voice, speed)
            pieces += [audio, np.zeros(int(script.settings["gap"] * SR), np.float32)]
            total += len(audio) / SR
            if total >= seconds:
                break
        track = np.concatenate(pieces)
        sf.write(out / f"{voice}.wav", track * 0.9 / max(1e-6, float(np.abs(track).max())), SR, subtype="PCM_16")
        print(out / f"{voice}.wav")
    return 0


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
    ap.add_argument("--tts", action="store_true", help="the synthetic voice for every beat, whatever takes there are")
    ap.add_argument("--audition", nargs="+", metavar="VOICE", help="speak the opening in each of these voices and stop")
    args = ap.parse_args()
    import soundfile as sf

    root = Path(args.video).resolve()
    script, sources, errors, _ = check.report(root)
    if errors:
        print("\n".join(f"error: {e}" for e in errors))
        return 1
    voice = args.voice or script.settings["voice"]
    speed = args.speed or script.settings["speed"]
    if args.audition:
        return audition(root, script, args.audition, speed)
    cache = root / "build" / "narration"
    cache.mkdir(parents=True, exist_ok=True)
    pipe = pipeline(voice)
    say = read_say(root, pipe)

    from scipy.signal import resample_poly
    from explainers import align, record

    t = script.settings["lead"]
    pieces, beats, guessed, own, stale, unsure, bleeped = [], [], [], [], [], [], []
    for i, b in enumerate(script.beats):
        text = spoken(b.text, say)
        take = "none" if args.tts else record.state(root, b)
        if take == "fresh":
            sound = hashlib.sha1(record.take_path(root, b.id).read_bytes()).hexdigest()
            key = hashlib.sha1(f"take|{align.MODEL}|{align.EARLY}|{TAKE_HEAD}|{TAKE_TAIL}|{sound}|{text}".encode()).hexdigest()[:16]
            wav, meta = cache / f"{key}.wav", cache / f"{key}.json"
            if args.force or not (wav.exists() and meta.exists()):
                audio, words, doubt = recorded(pipe, text, record.take_path(root, b.id))
                sf.write(wav, audio, OUT_SR, subtype="FLOAT")
                meta.write_text(json.dumps(dict(words=words, unsure=doubt)))
            audio, got = sf.read(wav, dtype="float32")[0], json.loads(meta.read_text())
            words = got["words"]
            unsure += [(b.id, w) for w in got["unsure"]]
            own.append(b.id)
        else:
            if take == "stale":
                stale.append(b.id)
            key = hashlib.sha1(f"{MODEL}|{voice}|{speed}|{text}".encode()).hexdigest()[:16]
            wav, meta = cache / f"{key}.wav", cache / f"{key}.json"
            if args.force or not (wav.exists() and meta.exists()):
                audio, words = speak(pipe, text, voice, speed)
                sf.write(wav, audio, SR, subtype="FLOAT")
                meta.write_text(json.dumps(words))
            audio, words = sf.read(wav, dtype="float32")[0], json.loads(meta.read_text())
            guessed += [(b.id, w, ph) for w, _, _, ph, rating in words if rating is not None and rating < 3]
            audio = resample_poly(audio, OUT_SR // SR, 1).astype(np.float32)
        audio, n = bleep(audio, words)
        bleeped += [b.id] * n
        pieces.append((t, audio, b.id in own))
        took = len(audio) / OUT_SR
        beats.append(dict(id=b.id, section=b.section, kind=b.kind, sources=b.sources, text=S.mask(b.plain),
                          t0=round(t, 3), t1=round(t + took, 3),
                          words=[[S.mask(w), round(t + t0, 3), round(t + t1, 3), ph] for w, t0, t1, ph, _ in words]))
        t += took + b.pause
        if i + 1 < len(script.beats):
            t += script.settings["section_gap" if script.beats[i + 1].section != b.section else "gap"]
    duration = t + script.settings["tail"]

    track = np.zeros(int(duration * OUT_SR) + 1, np.float32)
    quiet = np.ones(len(track), np.float32)
    rooms = []
    for t0, audio, mine in pieces:
        i = int(round(t0 * OUT_SR))
        if own:                                           # one loudness for every beat, whoever speaks it
            gain = LEVEL / max(record.voiced(audio), 1e-6)
            audio = audio * gain
            if mine:
                rooms.append(record.hush(audio))
                quiet[i:i + len(audio)] = 0.0
                edge = min(int(0.04 * OUT_SR), i, len(track) - i - len(audio))
                if edge > 0:
                    quiet[i - edge:i] = np.linspace(1.0, 0.0, edge)
                    quiet[i + len(audio):i + len(audio) + edge] = np.linspace(0.0, 1.0, edge)
        track[i:i + len(audio)] += audio
    room = record.take_path(root, record.ROOM)
    if own and room.exists():
        track += bed(record.load(room), len(track), quiet, float(np.median(rooms)))
    (root / "audio").mkdir(exist_ok=True)
    (root / "data").mkdir(exist_ok=True)
    sf.write(cache / "raw.wav", track, OUT_SR, subtype="FLOAT")
    loud, peak = finish(cache / "raw.wav", root / "audio" / "narration.wav", squeeze=bool(own))
    track = sf.read(root / "audio" / "narration.wav", dtype="float32")[0]
    np.save(root / "data" / "voice.npy", (envelope(track, OUT_SR) * 255).astype(np.uint8))
    whose = "recorded" if len(own) == len(beats) else voice
    (root / "data" / "narration.json").write_text(dump(
        dict(title=script.title, voice=whose, speed=speed, duration=round(duration, 3), env_fps=ENV_FPS,
             sections=[dict(id=sid, title=title) for sid, title in script.sections], **(dict(takes=own) if own else {})),
        beats))

    print(f"{script.title}: {duration:.1f}s, " + (f"all {len(beats)} beats recorded" if len(own) == len(beats) else
          (f"{len(own)} of {len(beats)} beats recorded, the rest " if own else "") + f"in {voice} at speed {speed:g}"))
    for b in beats:
        print(f"  {b['t0']:7.2f}  {b['t1'] - b['t0']:5.2f}s  {b['id']:<16} {b['kind']:<11} {'●' if b['id'] in own else ' '} {b['text'][:58]}")
    if bleeped:
        print(f"bleeped {len(bleeped)} word(s), in: " + ", ".join(dict.fromkeys(bleeped)))
    if stale:
        print("these takes were recorded for other words, so the synthetic voice stands in (python -m explainers.record "
              f"{args.video} {' '.join(stale)}):\n  " + ", ".join(stale))
    if unsure:
        print("listen to these words in the takes, the timing may be off:")
        for beat_id, word in unsure:
            print(f"  {beat_id:<16} {word}")
    if guessed:
        print("the voice guessed at these (fix a wrong one in say.txt):")
        for beat_id, word, ph in guessed:
            print(f"  {beat_id:<16} {word:<18} /{ph}/")
    print(f"{root / 'audio' / 'narration.wav'}  ({loud:.1f} LUFS, peak {peak:.1f} dB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
