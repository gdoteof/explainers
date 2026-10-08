"""When each word of a known text is said in a recording: forced alignment with a small speech model
(wav2vec2, on the CPU). It is how a take in the narrator's own voice gets the word timings that the
synthetic voice reports for itself.

    words(audio, sr, ["In", "the", "summer", "of", "1789,"])   [(start, end, sureness), ...], in seconds
    heard(audio, sr)                                           what the model thinks was said, roughly
"""
import math
import re
import unicodedata
from functools import lru_cache

import numpy as np

MODEL = "facebook/wav2vec2-base-960h"
SR = 16000
NEVER = -1e30
EARLY = 0.07            # the model marks a word a moment after it starts (measured against the synthetic voice's own timings)


def spell(word):
    """A word of the script as the pieces a listener hears, in capitals: "1789," is SEVENTEEN EIGHTY NINE,
    "left-wing" is LEFT WING, "France's" is FRANCE'S."""
    from num2words import num2words

    def year(n):
        return num2words(n, to="year") if 1100 <= n <= 2099 else num2words(n)

    def decade(m):
        said = year(int(m.group(1)))
        return f" {said[:-1]}ies " if said.endswith("y") else f" {said}s "

    w = word.replace("’", "'").replace("&", " and ").replace("%", " percent ")
    w = re.sub(r"(\d{4})s\b", decade, w)
    w = re.sub(r"(\d+)(?:st|nd|rd|th)\b", lambda m: f" {num2words(int(m.group(1)), to='ordinal')} ", w)
    w = re.sub(r"\d+(?:,\d{3})+", lambda m: f" {num2words(int(m.group(0).replace(',', '')))} ", w)
    w = re.sub(r"\d+\.\d+", lambda m: f" {num2words(float(m.group(0)))} ", w)
    w = re.sub(r"\d+", lambda m: f" {year(int(m.group(0)))} ", w)
    w = unicodedata.normalize("NFKD", w).encode("ascii", "ignore").decode()
    return [p.upper() for p in (q.strip("'") for q in re.findall(r"[A-Za-z']+", w)) if p]


def spelled(text):
    """A whole text as `spell` hears it: what two wordings must share for one take to do for both."""
    return [p for w in text.split() for p in spell(w)]


@lru_cache(maxsize=1)
def _model():
    import warnings
    import torch
    from transformers import Wav2Vec2CTCTokenizer, Wav2Vec2ForCTC
    from transformers.utils import logging
    warnings.filterwarnings("ignore")
    logging.set_verbosity_error()
    logging.disable_progress_bar()
    torch.set_grad_enabled(False)
    return Wav2Vec2ForCTC.from_pretrained(MODEL).eval(), Wav2Vec2CTCTokenizer.from_pretrained(MODEL).get_vocab()


def _emit(audio, sr):
    """(log probability of each letter in each frame, seconds per frame)."""
    import torch
    from scipy.signal import resample_poly
    model, _ = _model()
    g = math.gcd(SR, sr)
    x = (resample_poly(audio, SR // g, sr // g) if sr != SR else audio).astype(np.float32)
    x = (x - x.mean()) / (x.std() + 1e-7)
    logits = model(torch.from_numpy(x)[None]).logits[0]
    return torch.log_softmax(logits, -1).numpy(), len(x) / SR / logits.shape[0]


def trace(logp, tokens, blank=0):
    """The likeliest way to say `tokens` in order across the frames of `logp`: for each frame, which token is
    being said, or -1 between tokens. (The Viterbi path of a CTC model, with an optional blank between
    every two tokens.)"""
    labels = np.array([blank] + [x for tok in tokens for x in (tok, blank)])
    n = len(labels)
    emit = logp[:, labels]
    skip = np.zeros(n, bool)
    skip[2:] = (labels[2:] != blank) & (labels[2:] != labels[:-2])
    score = np.full(n, NEVER)
    score[:2] = emit[0, :2]
    back = np.zeros((len(logp), n), np.int8)
    for t in range(1, len(logp)):
        step = np.concatenate(([NEVER], score[:-1]))
        jump = np.where(skip, np.concatenate(([NEVER, NEVER], score[:-2])), NEVER)
        ways = np.stack([score, step, jump])
        back[t] = ways.argmax(0)
        score = ways.max(0) + emit[t]
    s = n - 1 if score[n - 1] >= score[n - 2] else n - 2
    if score[s] < NEVER / 2:
        raise ValueError("the recording is too short for these words")
    out = np.zeros(len(logp), int)
    for t in range(len(logp) - 1, -1, -1):
        out[t] = s // 2 if s % 2 else -1
        s -= int(back[t, s])
    return out


def words(audio, sr, script_words):
    """[(start, end, sureness 0..1)] for each word of the script, in seconds from the start of the audio.
    A word runs to the next one when they are spoken together, and a little past its last sound otherwise."""
    logp, step = _emit(audio, sr)
    _, vocab = _model()
    tokens, owner = [], []                  # the letters to find, and the script word each belongs to
    for i, w in enumerate(script_words):
        for piece in spell(w):
            if tokens:
                tokens.append(vocab["|"])
                owner.append(-1)
            for ch in piece:
                if ch in vocab:
                    tokens.append(vocab[ch])
                    owner.append(i)
    if not tokens:
        raise ValueError("no words to find")
    said = trace(logp, tokens, vocab["<pad>"])
    first, last, best = {}, {}, {}
    for t, k in enumerate(said):
        if k < 0 or owner[k] < 0:
            continue
        first.setdefault(owner[k], t)
        last[owner[k]] = t
        best[k] = max(best.get(k, 0.0), float(np.exp(logp[t, tokens[k]])))
    letters = {}
    for k, p in best.items():
        letters.setdefault(owner[k], []).append(p)
    out, start, end = [], 0.0, 0.0
    for i in range(len(script_words)):
        if i not in first:                  # a word with no sound of its own: a dash, a bare symbol
            out.append((end, end, 1.0))
            continue
        start, end = max(start, first[i] * step - EARLY), (last[i] + 1) * step
        out.append((start, end, float(np.mean(letters[i]))))
    total = len(audio) / sr
    for i, (start, end, sure) in enumerate(out):
        after = next((o[0] for o in out[i + 1:] if o[1] > o[0]), None)
        end = after if after is not None and after - end < 0.3 else min(total, end + 0.1)
        out[i] = (round(start, 3), round(max(end, start + step), 3), round(sure, 3))
    return out


def heard(audio, sr):
    """What the model makes of the audio with no script to go on, in capitals. Rough, but enough to tell a
    reading of the script from a reading of something else."""
    logp, _ = _emit(audio, sr)
    _, vocab = _model()
    letter = {i: ch for ch, i in vocab.items()}
    ids = logp.argmax(-1)
    keep = [i for k, i in enumerate(ids) if i != vocab["<pad>"] and (k == 0 or i != ids[k - 1])]
    return " ".join("".join(letter[i] for i in keep).replace("|", " ").split())
