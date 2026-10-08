"""A video's narration at render time: when each beat and each word is said, and the speaker's mouth.

    N = Narration(ROOT)
    N.at("seats.2")                 when the beat starts
    N.at("seats.2", "right")        when its first "right" starts
    N.at("seats.2", "right", 2)     its second "right"
    N.end("seats.2")                when the beat's last word ends
    N.beat_at(t)                    the beat being said at t, or the last one said (None before the first)
    N.mouth(t)                      (width, opening) of a mouth saying what is being said at t
    N.loud(t)                       how loud the voice is, 0..1

Cues are looked up by the words of the script, so that the pictures follow when the narration is spoken
again. A cue that names a word the beat doesn't have raises, and the sweep finds it.
"""
import bisect
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# Mouth shapes as (width, opening), for the sounds Kokoro writes its phonemes in.
SHAPES = {
    "rest": (0.80, 0.00), "closed": (0.72, 0.00), "ah": (0.95, 1.00), "eh": (1.05, 0.60), "ee": (1.20, 0.32),
    "oh": (0.62, 0.85), "oo": (0.46, 0.42), "f": (0.86, 0.18), "l": (0.90, 0.50), "s": (1.00, 0.20),
}
_SOUND = {}
for _shape, _sounds in (("closed", "mbp"), ("f", "fv"), ("l", "lndtɾθðɫ"), ("s", "szʃʒʧʤkɡgŋjhçx"),
                        ("oo", "wuʊɹrQ"), ("oh", "ɔOoɒY"), ("ah", "æɑaAIWʌɐ"), ("eh", "ɛəɜɚɪᵻᵊe"), ("ee", "i")):
    for _ch in _sounds:
        _SOUND[_ch] = _shape


def _norm(word):
    return re.sub(r"[^\w]", "", word.lower().replace("’", "'").replace("'", ""))


@dataclass(frozen=True)
class Beat:
    id: str
    section: str
    kind: str
    sources: tuple
    text: str
    t0: float
    t1: float
    words: tuple                # ((word, start, end, phonemes), ...)


class Narration:
    def __init__(self, root):
        root = Path(root)
        doc = json.loads((root / "data" / "narration.json").read_text())
        self.title, self.duration, self.voice = doc["title"], doc["duration"], doc["voice"]
        self.takes = tuple(doc.get("takes", ()))          # the beats in the narrator's own voice
        self.sections = [(s["id"], s["title"]) for s in doc["sections"]]
        self.beats = [Beat(b["id"], b["section"], b["kind"], tuple(b["sources"]), b["text"], b["t0"], b["t1"],
                           tuple(tuple(w) for w in b["words"])) for b in doc["beats"]]
        self._by_id = {b.id: b for b in self.beats}
        self._starts = [b.t0 for b in self.beats]
        env = root / "data" / "voice.npy"
        self._env = np.load(env).astype(np.float32) / 255 if env.exists() else np.zeros(1, np.float32)
        self._env_fps = doc.get("env_fps", 60)
        keys = [(-1.0, "rest")]
        for b in self.beats:
            for _, t0, t1, phonemes in b.words:
                sounds = [_SOUND[ch] for ch in phonemes if ch in _SOUND] or ["eh"]
                if t0 - keys[-1][0] > 0.22:
                    keys.append((t0 - 0.06, "rest"))
                keys += [(t0 + (t1 - t0) * (i + 0.4) / len(sounds), s) for i, s in enumerate(sounds)]
            keys.append((b.t1 + 0.05, "rest"))
        self._keys, self._key_t = keys, [k[0] for k in keys]

    def beat(self, beat_id):
        try:
            return self._by_id[beat_id]
        except KeyError:
            raise KeyError(f"no beat {beat_id!r} in the narration (have: {', '.join(self._by_id)})") from None

    def _word(self, beat_id, word, nth):
        b = self.beat(beat_id)
        want = _norm(word)
        hits = [w for w in b.words if _norm(w[0]) == want]
        if len(hits) < nth:
            raise KeyError(f"beat {beat_id!r} says {word!r} {len(hits)} time(s), not {nth}: {b.text!r}")
        return hits[nth - 1]

    def at(self, beat_id, word=None, nth=1):
        """When a beat starts, or when the nth time it says a word starts."""
        return self.beat(beat_id).t0 if word is None else self._word(beat_id, word, nth)[1]

    def end(self, beat_id, word=None, nth=1):
        """When a beat's last word ends, or when the nth time it says a word ends."""
        return self.beat(beat_id).t1 if word is None else self._word(beat_id, word, nth)[2]

    def section(self, section_id):
        """(start of the section's first beat, end of its last)."""
        beats = [b for b in self.beats if b.section == section_id]
        if not beats:
            raise KeyError(f"no section {section_id!r} in the narration")
        return beats[0].t0, beats[-1].t1

    def beat_at(self, t):
        """The beat being said at t, or the one said last. None before the first."""
        i = bisect.bisect_right(self._starts, t) - 1
        return self.beats[i] if i >= 0 else None

    def speaking(self, t):
        b = self.beat_at(t)
        return b is not None and t <= b.t1

    def said(self, t):
        """The words of the current beat said so far, for a caption or a preview label."""
        b = self.beat_at(t)
        return "" if b is None else " ".join(w[0] for w in b.words if w[1] <= t)

    def loud(self, t):
        x = t * self._env_fps
        i = int(x)
        if i < 0 or i + 1 >= len(self._env):
            return 0.0
        return float(self._env[i] + (self._env[i + 1] - self._env[i]) * (x - i))

    def mouth(self, t):
        """(width, opening): the shape follows the words sound by sound, the opening how loud the voice is."""
        i = bisect.bisect_right(self._key_t, t) - 1
        if i < 0 or i + 1 >= len(self._keys):
            return SHAPES["rest"]
        (ta, a), (tb, b) = self._keys[i], self._keys[i + 1]
        k = min(1.0, max(0.0, (t - ta) / (tb - ta)))
        k = k * k * (3 - 2 * k)
        (wa, ha), (wb, hb) = SHAPES[a], SHAPES[b]
        return wa + (wb - wa) * k, (ha + (hb - ha) * k) * (0.4 + 0.6 * self.loud(t))
