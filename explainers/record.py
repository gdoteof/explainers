"""Record a script in your own voice, a beat at a time: python -m explainers.record VIDEO [BEAT or SECTION ...]

    python -m explainers.record VIDEO                  every beat with no take yet, or whose words have changed
    python -m explainers.record VIDEO room.2 deal      these beats and sections again
    python -m explainers.record VIDEO --room           ten seconds of the empty room, to lay under the gaps
    python -m explainers.record VIDEO --list           which beats have takes
    python -m explainers.record VIDEO --from FILE BEAT a file recorded elsewhere as the take for one beat

Run it in a terminal of your own: it shows a beat, records from the microphone while you read it (Enter
starts, Enter stops), tells you the level and whether it heard the script's words, and asks whether to
keep the take. Takes are VIDEO/audio/takes/<beat>.wav, mono at 48 kHz, untouched. `narrate` then uses a
take wherever a beat has one and the synthetic voice everywhere else, so a video can be drafted in the
synthetic voice and re-voiced a beat at a time.

A take is tied to its words: change a beat's wording and its take goes stale (`--list` shows which), though
punctuation can change freely. There is no need to hurry the keys or sit still at the ends: a take is cut
to its first and last word.
"""
import argparse
import difflib
import math
import shutil
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np

from explainers import check

SR = 48000
ROOM = "_room"
WPM = 155


def take_path(root, beat_id):
    return Path(root) / "audio" / "takes" / f"{beat_id}.wav"


def state(root, beat):
    """"none", "fresh", or "stale": a take recorded for other words than the beat has now."""
    from explainers import align
    wav = take_path(root, beat.id)
    if not wav.exists():
        return "none"
    words = wav.with_suffix(".txt")
    return "fresh" if not words.exists() or align.spelled(words.read_text()) == align.spelled(beat.plain) else "stale"


def load(path):
    """A take as mono float32 at SR, with the rumble below the voice filtered out."""
    import soundfile as sf
    from scipy.signal import butter, resample_poly, sosfiltfilt
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    audio = audio.mean(axis=1)
    if sr != SR:
        g = math.gcd(SR, sr)
        audio = resample_poly(audio, SR // g, sr // g)
    return sosfiltfilt(butter(2, 70, "highpass", fs=SR, output="sos"), audio).astype(np.float32)


def _frames(audio, sr=SR):
    """The loudness of each hundredth of a second, and the level above which a frame is voice, not room."""
    hop = sr // 100
    n = len(audio) // hop
    rms = np.sqrt((audio[:n * hop].reshape(n, hop) ** 2).mean(axis=1)) if n else np.zeros(1, np.float32)
    return rms, max(2.5 * float(np.percentile(rms, 10)), 0.02 * float(rms.max()))


def levels(audio):
    """(peak, the room, the voice) in dB below full scale."""
    db = lambda x: 20 * math.log10(max(float(x), 1e-6))
    rms, voice = _frames(audio)
    loud = rms[rms > voice]
    return db(np.abs(audio).max()), db(np.percentile(rms, 10)), db(np.sqrt((loud ** 2).mean()) if len(loud) else 0)


def voiced(audio):
    """How loud the voice is where there is voice (RMS, linear): what takes are matched to each other by."""
    rms, voice = _frames(audio)
    loud = rms[rms > voice]
    return float(np.sqrt((loud ** 2).mean())) if len(loud) else 0.0


def edges(audio, start, end):
    """A take's first word starts a little before the aligner hears it, and its last trails off after: follow
    the sound out to where it meets the room. Seconds in, seconds out."""
    rms, voice = _frames(audio)
    lo = i = min(len(rms) - 1, int(start * 100))
    while lo > 0 and i - lo < 40 and rms[lo - 1] > voice:
        lo -= 1
    hi = j = min(len(rms) - 1, int(end * 100))
    quiet = 0
    while hi < len(rms) - 1 and hi - j < 90 and quiet < 8:
        hi += 1
        quiet = quiet + 1 if rms[hi] <= voice else 0
    return lo / 100, (hi + 1 - quiet) / 100


def judge(audio, beat):
    """What to tell the reader about a take: the levels, and whether it is the script that was read."""
    from explainers import align
    peak, room, voice = levels(audio)
    notes = [f"{len(audio) / SR:.1f}s   peak {peak:.0f} dB   voice {voice:.0f} dB   room {room:.0f} dB"]
    if peak > -1.0:
        notes.append("  ! it clipped: turn the microphone down, or back off a little")
    elif voice < -34:
        notes.append("  ! quiet: come closer, or turn the microphone up")
    if room > -50:
        notes.append("  ! the room is loud under the voice: a fan, a window, the computer?")
    want = align.spelled(beat.plain)
    got = align.heard(audio, SR).split()
    match = difflib.SequenceMatcher(None, want, got).ratio()
    if match < 0.6:
        notes.append("  ! this does not sound like the script. Heard: " + textwrap.shorten(" ".join(got).lower(), 110, placeholder=" ..."))
        return notes, False
    spans = align.words(audio, SR, beat.plain.split())
    unsure = [w for w, (_, _, sure) in zip(beat.plain.split(), spans) if sure < 0.3]
    if unsure:
        notes.append("  ? not sure of: " + ", ".join(unsure))
    else:
        notes.append(f"  every word found ({len(spans)})")
    return notes, True


def capture(path, mic=None, seconds=None):
    """Record from the microphone into `path` until Enter, or for `seconds`. False if it was called off."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("pw-record"):
        cmd = ["pw-record", "--rate", str(SR), "--channels", "1", "--format", "f32"] + (["--target", mic] if mic else [])
    elif shutil.which("parecord"):
        cmd = ["parecord", f"--rate={SR}", "--channels=1", "--format=float32le", "--file-format=wav"] + ([f"--device={mic}"] if mic else [])
    elif shutil.which("arecord"):
        cmd = ["arecord", "-q", "-r", str(SR), "-c", "1", "-f", "S16_LE"] + (["-D", mic] if mic else [])
    else:
        raise SystemExit("no recorder found: install pipewire (pw-record), pulseaudio-utils (parecord) or alsa-utils (arecord)")
    proc = subprocess.Popen(cmd + [str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    kept = True
    try:
        if seconds:
            proc.wait(timeout=seconds)
        else:
            input("  ● recording. Enter when you have finished ")
    except subprocess.TimeoutExpired:
        pass
    except (KeyboardInterrupt, EOFError):
        kept = False
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    if kept and not (path.exists() and path.stat().st_size > 1000):
        raise SystemExit("nothing was recorded: " + (proc.stderr.read().decode().strip() or "is a microphone connected?"))
    return kept


def play(path):
    for player in ("pw-play", "paplay", "aplay"):
        if shutil.which(player):
            try:
                subprocess.run([player, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except KeyboardInterrupt:
                pass
            return


def listing(root, script):
    import soundfile as sf
    for b in script.beats:
        s = state(root, b)
        took = f"{sf.info(take_path(root, b.id)).duration:5.1f}s" if s != "none" else "      "
        mark = {"fresh": "recorded", "stale": "WORDS CHANGED", "none": "-"}[s]
        print(f"  {b.id:<16} {took}  {mark:<14} {b.plain[:60]}")
    room = take_path(root, ROOM)
    print(f"  the room: {'recorded' if room.exists() else 'not recorded (python -m explainers.record VIDEO --room)'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video")
    ap.add_argument("only", nargs="*", metavar="BEAT", help="beat or section ids (default: whatever has no fresh take)")
    ap.add_argument("--mic", help="the source to record from, as `pactl list short sources` names it (default: the system's)")
    ap.add_argument("--room", action="store_true", help="record ten seconds of the room with nobody speaking")
    ap.add_argument("--list", action="store_true", help="show which beats have takes, and stop")
    ap.add_argument("--from", dest="file", metavar="FILE", help="use this recording as the take for the one BEAT named")
    ap.add_argument("--no-check", action="store_true", help="do not listen to the takes for the script's words")
    args = ap.parse_args()
    import soundfile as sf

    root = Path(args.video).resolve()
    script, _, errors, _ = check.report(root)
    if errors:
        print("\n".join(f"error: {e}" for e in errors))
        return 1
    if args.list:
        listing(root, script)
        return 0
    if args.room:
        input("The room on its own: sit as you will when reading, and keep quiet. Enter to start ")
        capture(take_path(root, ROOM), args.mic, seconds=10)
        peak, room, _ = levels(load(take_path(root, ROOM)))
        print(f"  the room is at {room:.0f} dB" + ("" if room < -50 else ": that is loud. Is something running?"))
        return 0
    known = {b.id for b in script.beats} | {sid for sid, _ in script.sections}
    unknown = [x for x in args.only if x not in known]
    if unknown:
        print(f"no beat or section called {', '.join(unknown)}")
        return 1
    todo = [b for b in script.beats if (b.id in args.only or b.section in args.only) or (not args.only and state(root, b) != "fresh")]
    if args.file:
        if len(todo) != 1 or not args.only:
            print("--from needs exactly one BEAT")
            return 1
        audio, sr = sf.read(args.file, dtype="float32", always_2d=True)
        take_path(root, todo[0].id).parent.mkdir(parents=True, exist_ok=True)
        sf.write(take_path(root, todo[0].id), audio.mean(axis=1), sr, subtype="FLOAT")
        take_path(root, todo[0].id).with_suffix(".txt").write_text(todo[0].plain + "\n")
        print("\n".join(judge(load(take_path(root, todo[0].id)), todo[0])[0]))
        return 0
    if not todo:
        print("every beat has a take. Name a beat or a section to record it again.")
        return 0
    if not args.no_check:
        print("loading the listener (the first time, a 360 MB download) ...")
        from explainers import align
        align._model()

    new = take_path(root, ".new")
    for n, b in enumerate(todo, 1):
        words = len(b.plain.split())
        print(f"\n\n{'─' * 78}\n{b.id}   {b.kind}   {n} of {len(todo)}   about {words / WPM * 60:.0f}s\n")
        print(textwrap.indent(textwrap.fill(b.plain, 72), "    ") + "\n")
        while True:
            said = input("Enter to record, s to skip, q to stop > ").strip().lower()
            if said == "q":
                new.unlink(missing_ok=True)
                return 0
            if said == "s":
                break
            if not capture(new, args.mic):
                new.unlink(missing_ok=True)
                print()
                return 0
            audio, ok = load(new), True
            if args.no_check:
                peak, room, voice = levels(audio)
                print(f"  {len(audio) / SR:.1f}s   peak {peak:.0f} dB   voice {voice:.0f} dB   room {room:.0f} dB")
            else:
                notes, ok = judge(audio, b)
                print("\n".join("  " + line for line in notes))
            ask = "Enter to keep it, r to read it again, p to hear it > " if ok else "Enter to read it again, k to keep it anyway, p to hear it > "
            keep = None
            while keep is None:
                said = input(ask).strip().lower()
                if said == "p":
                    play(new)
                elif said in ("", "r", "k"):
                    keep = said == "k" or (ok and said == "")
            if keep:
                new.replace(take_path(root, b.id))
                take_path(root, b.id).with_suffix(".txt").write_text(b.plain + "\n")
                break
    new.unlink(missing_ok=True)
    left = [b.id for b in script.beats if state(root, b) != "fresh"]
    print(f"\n{len(script.beats) - len(left)} of {len(script.beats)} beats are in your voice"
          + (f"; still synthetic: {', '.join(left)}" if left else "")
          + f".\nNext: python -m explainers.narrate {args.video}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
