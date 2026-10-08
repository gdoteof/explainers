"""What a reading really says, and where it leaves its script.

    heard(audio, sr, before="...")          the words of a recording, with no script to go on
    departures(audio, sr, text, said)       where the reading stops being the beat it was a reading of
    follow(text, said, spans)               the beat, reworded to what was said there

Two speech models listen, and a beat is only reworded where both hear the same thing. Whisper (large-v3,
on the CPU: about four seconds a take) writes down what was said. It is good, but it also tidies: it hears
"here's" for "here is" and "guess is" for "guesses". So each place where its words differ from the script's
is put to the aligner's model (explainers/align.py), which is asked which of the two wordings fits the
sound better. Only where that one sides with Whisper too is the reading taken to have left the script.

Spelling is not a difference, nor punctuation, nor where the spaces fall: Whisper is made to write its
numbers out in words, as a script does, and the two wordings are compared by how they sound.
"""
import difflib
import math
import os
import re
from functools import lru_cache

import numpy as np

from explainers import align
from explainers import script as S

MODEL = "large-v3"
SR = 16000
MARGIN = 1.0            # how much better (in log likelihood) the heard words must fit the sound than the script's
# Whisper writes as the text before it was written, so this sets its style: numbers in words, no symbols
STYLE = "Fourteen cents of every dollar. In seventeen eighty-nine it was about twenty-two and a half percent; by the nineteen twenties, three hundred."
_AFTER = re.compile(r"[^\w'’]*$")       # the punctuation after a word


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel
    model = WhisperModel(MODEL, device="cpu", compute_type="int8", cpu_threads=min(16, os.cpu_count() or 4))
    figures = [i for token, i in model.hf_tokenizer.get_vocab().items() if re.search(r"[0-9$%£€]", token)]
    return model, figures


def heard(audio, sr, before=""):
    """The words of a recording as text. `before` is what was said just before it (the beat before, in a
    script): it gives the names their spellings."""
    from scipy.signal import resample_poly
    model, figures = _model()
    g = math.gcd(SR, sr)
    x = (resample_poly(audio, SR // g, sr // g) if sr != SR else audio).astype(np.float32)
    parts, _ = model.transcribe(x, language="en", beam_size=5, initial_prompt=f"{STYLE} {before}".strip(),
                                condition_on_previous_text=False, without_timestamps=True, suppress_tokens=[-1] + figures)
    return " ".join(p.text.strip() for p in parts)


def _sounds(words):
    return [align.sound(S.plain(w)) for w in words]


def likeness(text, said):
    """0..1: how much of one wording is in the other. A reading of a beat, however loose, is well above a
    half; a cough, or a reading of something else, is not."""
    return difflib.SequenceMatcher(None, [k for k in _sounds(S.words(text)) if k], [k for k in _sounds(S.words(said)) if k],
                                   autojunk=False).ratio()


def differences(text, said):
    """Where two wordings part, as [(a0, a1, b0, b1)]: words a0 to a1 of `text` against words b0 to b1 of
    `said`, either of which may be none at all. Wordings that sound the same have no differences."""
    ka, kb = _sounds(S.words(text)), _sounds(S.words(said))
    ia = [i for i, k in enumerate(ka) if k]             # a dash on its own has no sound: it stays where it is
    ib = [i for i, k in enumerate(kb) if k]
    out = []
    ops = difflib.SequenceMatcher(None, [ka[i] for i in ia], [kb[i] for i in ib], autojunk=False).get_opcodes()
    for op, i0, i1, j0, j1 in ops:
        if op == "equal" or "".join(ka[i] for i in ia[i0:i1]) == "".join(kb[i] for i in ib[j0:j1]):
            continue
        a0 = ia[i0] if i0 < len(ia) else len(ka)
        b0 = ib[j0] if j0 < len(ib) else len(kb)
        out.append((a0, ia[i1 - 1] + 1 if i1 > i0 else a0, b0, ib[j1 - 1] + 1 if j1 > j0 else b0))
    return out


def _opens(words, i):
    """Whether word i is the first of a sentence."""
    return i == 0 or S.plain(words[i - 1]).rstrip("\"”’')")[-1:] in ".?!"


def _stand_in(a, b, span):
    """The words of `b` that take the place of a span of `a`, punctuated as the script was: the last keeps
    what the script had after the word it replaces, and the first is a capital only where the script starts
    a sentence. Where a sentence ends is the writer's to say, not the listener's."""
    a0, a1, b0, b1 = span
    new = b[b0:b1]
    if new and a1 > a0:
        new[-1] = _AFTER.sub("", new[-1]) + _AFTER.search(S.plain(a[a1 - 1])).group(0)
    if new and _opens(a, a0) != _opens(b, b0) and not re.match(r"I\b", new[0]):
        new[0] = (new[0][:1].upper() if _opens(a, a0) else new[0][:1].lower()) + new[0][1:]
    return new


def follow(text, said, spans):
    """`text` with each of `spans` (as `differences` gives them) said the way `said` has it."""
    a, b = S.words(text), S.words(said)
    for a0, a1, b0, b1 in sorted(spans, reverse=True):
        new = _stand_in(a, b, (a0, a1, b0, b1))
        if new and a1 < len(a) and b1 < len(b) and _opens(a, a1) and not _opens(new + [""], len(new)) and b[b1][:1].islower():
            a[a1] = a[a1][:1].lower() + a[a1][1:]           # words put in front of a sentence: it no longer starts one
        a[a0:a1] = new
    return " ".join(a)


def departures(audio, sr, text, said):
    """The differences between a beat's `text` and what Whisper `said` of a reading of it that the sound
    bears out: the spans, of those `differences` finds, where the heard words fit the recording better than
    the script's own."""
    spans = differences(text, said)
    if not spans:
        return []
    fit = align.weigh(audio, sr, [S.plain(text)] + [S.plain(follow(text, said, [span])) for span in spans])
    return [span for span, score in zip(spans, fit[1:]) if score - fit[0] > MARGIN]


def describe(text, said, spans, around=2):
    """Each change as a line for the reader: the script's words, then what was said, with a word or two on
    either side to place it."""
    a, b = S.words(text), S.words(said)
    out = []
    for span in spans:
        a0, a1 = span[:2]
        lo, n = max(0, a0 - around), len(_stand_in(a, b, span))
        old, new = a[lo:a1 + around], S.words(follow(text, said, [span]))[lo:a0 + n + around]
        out.append(f"“{S.plain(' '.join(old))}”  →  “{S.plain(' '.join(new))}”")
    return out
