"""Record a script in your own voice, a beat at a time: python -m explainers.record VIDEO [BEAT or SECTION ...]

    python -m explainers.record VIDEO                  every beat with no take yet, or whose words have changed
    python -m explainers.record VIDEO room.2 deal      these beats and sections again
    python -m explainers.record VIDEO --room           ten seconds of the empty room, to lay under the gaps
    python -m explainers.record VIDEO --list           which beats have takes
    python -m explainers.record VIDEO --from FILE BEAT a file recorded elsewhere as the take for one beat

Run it in a terminal of your own: it shows a beat, records from the microphone while you read it (Enter
starts, Enter stops), tells you the level and what it heard, and asks whether to keep the take. Takes are
VIDEO/audio/takes/<beat>.wav, mono at 48 kHz, untouched. `narrate` then uses a take wherever a beat has
one and the synthetic voice everywhere else, so a video can be drafted in the synthetic voice and
re-voiced a beat at a time.

A beat does not have to be read word for word. Say it another way and the take is listened to
(explainers/listen.py), the difference is shown, and on Enter the script follows the reading: script.md
gets the words that were said. That goes for a fact as much as for a joke, so the beats that changed are
listed at the end with the sourced ones marked: their sources have to bear the new words out. Commit the
script before a session, and `git diff` shows what the voice changed.

A take is tied to its words: change a beat's wording afterwards and its take goes stale (`--list` shows
which), though spelling and punctuation can change freely. There is no need to hurry the keys or sit still
at the ends: a take is cut to its first and last word.
"""
import argparse
import difflib
import math
import shutil
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import numpy as np

from explainers import check
from explainers import script as S

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
    return "fresh" if not words.exists() or align.sound(words.read_text()) == align.sound(beat.plain) else "stale"


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


def hush(audio):
    """How loud the room is between the words of a take (RMS, linear)."""
    rms, voice = _frames(audio)
    quiet = rms[rms < 0.6 * voice]
    return float(np.median(quiet)) if len(quiet) else 0.0


def edges(audio, start, end, head=0.0, tail=0.0):
    """A take's first word starts a little before the aligner hears it, and its last trails off after: follow
    the sound out to where it meets the room, then take `head` and `tail` seconds of the room as well,
    stopping short of any other sound there (the key that started or stopped the recording, a breath).
    Seconds in, seconds out."""
    rms, voice = _frames(audio)
    lo = i = min(len(rms) - 1, int(start * 100))
    while lo > 0 and i - lo < 40 and rms[lo - 1] > voice:
        lo -= 1
    hi = j = min(len(rms) - 1, int(end * 100))
    quiet = 0
    while hi < len(rms) - 1 and hi - j < 90 and quiet < 8:
        hi += 1
        quiet = quiet + 1 if rms[hi] <= voice else 0
    hi += 1 - quiet
    for _ in range(int(head * 100)):
        if lo == 0 or rms[lo - 1] > voice:
            break
        lo -= 1
    for _ in range(int(tail * 100)):
        if hi >= len(rms) or rms[hi] > voice:
            break
        hi += 1
    return lo / 100, hi / 100


def judge(audio, beat, before=""):
    """What to tell the reader about a take: the levels, and what was read. Also the beat's words as they
    were said, or None when they were the script's, and whether the take is near enough to the script to
    be taken for a reading of it. `before` is the beat before this one, for the listener to go on."""
    from explainers import align, listen
    peak, room, voice = levels(audio)
    notes = [f"{len(audio) / SR:.1f}s   peak {peak:.0f} dB   voice {voice:.0f} dB   room {room:.0f} dB"]
    if peak > -1.0:
        notes.append("  ! it clipped: turn the microphone down, or back off a little")
    elif voice < -34:
        notes.append("  ! quiet: come closer, or turn the microphone up")
    if room > -50:
        notes.append("  ! the room is loud under the voice: a fan, a window, the computer?")
    said = listen.heard(audio, SR, before)
    near = listen.likeness(beat.text, said) >= 0.6
    spans = listen.departures(audio, SR, beat.text, said)
    text = listen.follow(beat.text, said, spans) if spans else None
    if text is not None and not align.spelled(S.plain(text)):
        text = None                         # nothing was said at all
    if not near:
        notes.append("  ! this is a long way from the script. Heard: " + textwrap.shorten(said, 110, placeholder=" ..."))
        return notes, text, False
    if text is not None:
        notes.append("  you said it another way:")
        notes += ["      " + line for line in listen.describe(beat.text, said, spans)]
        if beat.kind in S.SOURCED:
            notes.append(f"  ! this is a {beat.kind} ({', '.join(beat.sources)}): its source has to bear the new words out")
    words = S.plain(text or beat.text).split()
    unsure = [w for w, (_, _, sure) in zip(words, align.words(audio, SR, words)) if sure < 0.3]
    notes.append("  ? not sure of: " + ", ".join(unsure) if unsure else f"  every word found ({len(words)})")
    return notes, text, True


def retype(text):
    """The reader's own correction of a line, typed over `text`."""
    try:
        import readline
        readline.set_startup_hook(lambda: readline.insert_text(text))
    except ImportError:
        readline = None
    try:
        return " ".join(input("  ").split())
    finally:
        if readline:
            readline.set_startup_hook(None)


def ask(wav, beat, text, near):
    """Ask the reader what to do with a take. Returns the words to keep it under (the beat's own, or what was
    said in their place), or None to read it again."""
    if text is None and near:
        keys, menu = {"": beat.text, "r": None}, "Enter to keep it, r to read it again, p to hear it"
    elif text is None:
        keys, menu = {"": None, "k": beat.text}, "Enter to read it again, k to keep it anyway, p to hear it"
    elif near:
        keys = {"": text, "s": beat.text, "r": None}
        menu = "Enter to keep it as you said it (the script follows), s if you read the script's words, r to read it again,\n  e to correct what was heard, p to hear it"
    else:
        keys = {"": None, "k": text, "s": beat.text}
        menu = "Enter to read it again, k to keep it as you said it (the script follows), s if you read the script's words,\n  e to correct what was heard, p to hear it"
    while True:
        said = input(menu + " > ").strip().lower()
        if said == "p":
            play(wav)
        elif said == "e" and text is not None:
            typed = retype(S.plain(text))
            if typed:
                return typed
        elif said in keys:
            return keys[said]


def keep(root, beat, words):
    """Note the words a take was kept under, and give them to the script if they are not the script's.
    True if the script changed."""
    from explainers import align
    take_path(root, beat.id).with_suffix(".txt").write_text(S.plain(words) + "\n")
    if align.sound(S.plain(words)) == align.sound(beat.plain):
        return False
    S.reword(root, beat.id, words)
    return True


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
            time.sleep(0.4)                 # the last word is still ringing when the key goes down
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
    ap.add_argument("--as-said", action="store_true", help="with --from: where the recording leaves the script, the script follows it")
    ap.add_argument("--no-check", action="store_true", help="do not listen to the takes: keep each under the script's words")
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
    before = lambda b: script.beats[script.beats.index(b) - 1].plain if script.beats.index(b) else ""
    if args.file:
        if len(todo) != 1 or not args.only:
            print("--from needs exactly one BEAT")
            return 1
        b = todo[0]
        audio, sr = sf.read(args.file, dtype="float32", always_2d=True)
        take_path(root, b.id).parent.mkdir(parents=True, exist_ok=True)
        sf.write(take_path(root, b.id), audio.mean(axis=1), sr, subtype="FLOAT")
        notes, text, _ = judge(load(take_path(root, b.id)), b, before(b))
        print("\n".join(notes))
        if keep(root, b, text if args.as_said and text is not None else b.text):
            print(f"script.md now has these words for {b.id}:\n" + textwrap.indent(textwrap.fill(S.plain(text), 72), "    "))
        elif text is not None:
            print("the take is kept under the script's words: --as-said makes the script follow it instead")
        return 0
    if not todo:
        print("every beat has a take. Name a beat or a section to record it again.")
        return 0
    if not args.no_check:
        print("loading the listeners (the first time, a 3 GB download) ...")
        from explainers import align, listen
        align._model()
        listen._model()

    new, changed = take_path(root, ".new"), []
    for n, beat_id in enumerate([b.id for b in todo], 1):
        b = script.beat(beat_id)
        words = len(b.plain.split())
        print(f"\n\n{'─' * 78}\n{b.id}   {b.kind}   {n} of {len(todo)}   about {words / WPM * 60:.0f}s\n")
        print(textwrap.indent(textwrap.fill(b.plain, 72), "    ") + "\n")
        while True:
            said = input("Enter to record, s to skip, q to stop > ").strip().lower()
            if said == "q":
                new.unlink(missing_ok=True)
                return report(args.video, root, script, changed)
            if said == "s":
                break
            if not capture(new, args.mic):
                new.unlink(missing_ok=True)
                print()
                return report(args.video, root, script, changed)
            audio, text, near = load(new), None, True
            if args.no_check:
                peak, room, voice = levels(audio)
                print(f"  {len(audio) / SR:.1f}s   peak {peak:.0f} dB   voice {voice:.0f} dB   room {room:.0f} dB")
            else:
                notes, text, near = judge(audio, b, before(b))
                print("\n".join("  " + line for line in notes))
            kept = ask(new, b, text, near)
            if kept is not None:
                new.replace(take_path(root, b.id))
                if keep(root, b, kept):
                    changed.append(b.id)
                    script = S.load(root)
                break
    new.unlink(missing_ok=True)
    return report(args.video, root, script, changed)


def report(video, root, script, changed):
    """The last words of a session: what the reading changed in the script, and what is left to read."""
    if changed:
        print(f"\nscript.md now has your words for {', '.join(changed)} (`git diff` shows them).")
        sourced = [b for b in script.beats if b.id in changed and b.kind in S.SOURCED]
        if sourced:
            print("These are sourced, so read the source against the new words:\n"
                  + "\n".join(f"  {b.id}   {b.kind}: {', '.join(b.sources)}" for b in sourced))
    left = [b.id for b in script.beats if state(root, b) != "fresh"]
    print(f"\n{len(script.beats) - len(left)} of {len(script.beats)} beats are in your voice"
          + (f"; still synthetic: {', '.join(left)}" if left else "")
          + f".\nNext: python -m explainers.narrate {video}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
