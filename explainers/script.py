"""A video's script (script.md) and its sources (sources.toml).

    # Left and Right

    voice: am_michael
    speed: 1.0

    ## seats: Where the words come from
    > The hall from above, the president's chair at the top.

    [fact: gauchet, moniteur]
    In the summer of 1789, the men writing France's first constitution had a seating problem.

    [opinion | pause 1.0]
    I think a seating chart is a strange thing to sort all of politics by.

A paragraph is a beat: one stretch of narration, said in one breath and labelled with what kind of
statement it is. The label is the first line, in square brackets: the kind, then the keys of the sources
that back it, then options after a bar (`pause SECONDS` of silence after the beat, `id NAME`). A beat's id
is `<section>.<n>` unless it is given one. Lines that start with `>` are notes on the picture, and
`<!-- ... -->` is a comment; neither is spoken.

The kinds, and what each one promises (EDITORIAL.md has the long version):

    fact          checkable, and checked: needs at least one source
    estimate      a number somebody measured or modelled, with its uncertainty said out loud: needs a source
    view          what some people hold or argue, in terms they would accept, attributed: needs a source
    opinion       what this channel thinks: labelled on screen
    speculation   a guess about what is unknown or hasn't happened yet: labelled on screen
    line          no claim at all: a question, a transition, a joke
"""
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("fact", "estimate", "view", "opinion", "speculation", "line")
SOURCED = ("fact", "estimate", "view")
SETTINGS = {"voice": str, "speed": float, "lead": float, "gap": float, "section_gap": float, "tail": float}
DEFAULTS = {"voice": "am_michael", "speed": 1.0, "lead": 0.5, "gap": 0.35, "section_gap": 0.9, "tail": 1.5}

_TAG = re.compile(r"^\[([a-z]+)\s*(?::([^|\]]*))?((?:\|[^|\]]*)*)\]\s*$")
_SECTION = re.compile(r"^##\s+([a-z0-9][a-z0-9-]*)\s*(?::\s*(.*))?$")
_SAID = re.compile(r"\[([^\]]+)\]\(/[^)]*/\)")           # [word](/phonemes/): how the voice is told to say it
_WORD = re.compile(r"\[[^\]]+\]\(/[^)]*/\)\S*|\S+")       # a word of a beat's text, a marked one whole


RUDE = re.compile(r"fuck|shit|cunt|bitch|asshole", re.I)   # said by the narrator, not heard or read by the viewer


def mask(text):
    """A text with its swear words starred out past their first letter: "f***ing"."""
    return RUDE.sub(lambda m: m.group(0)[0] + "*" * (len(m.group(0)) - 1), text)


def plain(text):
    """A beat's text as a reader sees it: without the marks that tell the voice how to say a word."""
    return _SAID.sub(r"\1", text).replace("*", "")


def words(text):
    """A beat's text a word at a time, as written: punctuation stays on its word, and so does a mark."""
    return _WORD.findall(text)


@dataclass
class Beat:
    id: str
    section: str
    kind: str
    sources: list
    text: str                   # as written, with any [word](/phonemes/) marks: what the voice is given
    pause: float = 0.0
    notes: list = field(default_factory=list)
    line: int = 0               # where it is in script.md
    rows: tuple = ()            # and the lines its words are on

    @property
    def plain(self):
        """The words as a reader sees them."""
        return plain(self.text)


@dataclass
class Script:
    title: str
    settings: dict
    sections: list              # [(id, title)]
    beats: list
    errors: list                # [(line number, message)]: what stops this script being narrated

    def beat(self, beat_id):
        return next(b for b in self.beats if b.id == beat_id)


def parse(text):
    title, settings, sections, beats, errors = "", dict(DEFAULTS), [], [], []
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    section, tag, para, notes, count = None, None, [], [], 0

    def close():
        nonlocal tag, para, notes, count
        if para:
            if tag is None:
                errors.append((para[0][0], "a paragraph with no label: start it with [fact: source], [opinion], [line], ..."))
            elif section is None:
                errors.append((para[0][0], "a beat before the first section (## name)"))
            else:
                kind, keys, opts, line = tag
                count += 1
                beats.append(Beat(id=opts.get("id") or f"{section}.{count}", section=section, kind=kind, sources=keys,
                                  text=" ".join(s for _, s in para), pause=float(opts.get("pause", 0.0)),
                                  notes=notes, line=line, rows=tuple(n for n, _ in para)))
                notes = []
        elif tag is not None:
            errors.append((tag[3], "a label with no paragraph under it"))
        tag, para = None, []

    for n, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s:
            close()
        elif s.startswith("# ") and not title:
            title = s[2:].strip()
        elif s.startswith("## "):
            close()
            m = _SECTION.match(s)
            if not m:
                errors.append((n, "a section is `## name` or `## name: Title`, the name in lower case, digits and hyphens"))
                continue
            section, count = m.group(1), 0
            if section in (sid for sid, _ in sections):
                errors.append((n, f"section {section!r} appears twice"))
            sections.append((section, m.group(2) or ""))
        elif s.startswith(">"):
            notes.append(s[1:].strip())
        elif _TAG.match(s):
            close()
            kind, keys, rest = _TAG.match(s).groups()
            opts = {}
            for part in rest.split("|")[1:]:
                key, _, value = part.strip().partition(" ")
                if key not in ("pause", "id") or not value.strip():
                    errors.append((n, f"unknown option {part.strip()!r}: use `pause SECONDS` or `id NAME`"))
                else:
                    opts[key] = value.strip()
            if kind not in KINDS:
                errors.append((n, f"unknown kind {kind!r}: one of {', '.join(KINDS)}"))
                kind = "line"
            tag = (kind, [k.strip() for k in (keys or "").split(",") if k.strip()], opts, n)
        elif section is None and not para and ":" in s and s.split(":")[0].strip() in SETTINGS:
            key, _, value = s.partition(":")
            try:
                settings[key.strip()] = SETTINGS[key.strip()](value.strip())
            except ValueError:
                errors.append((n, f"{key.strip()} should be a number"))
        else:
            para.append((n, s))
    close()
    seen = set()
    for b in beats:
        if b.id in seen:
            errors.append((b.line, f"beat id {b.id!r} appears twice"))
        seen.add(b.id)
    if not title:
        errors.append((1, "no title: start the script with `# Title`"))
    return Script(title, settings, sections, beats, errors)


def load(root):
    return parse((Path(root) / "script.md").read_text())


def reword(root, beat_id, text):
    """Give one beat of script.md new words, on one line, and leave its label, its notes and the rest of the
    file as they are."""
    path = Path(root) / "script.md"
    lines = path.read_text().splitlines(keepends=True)
    first, *rest = parse("".join(lines)).beat(beat_id).rows
    old = lines[first - 1]
    lines[first - 1] = " ".join(text.split()) + old[len(old.rstrip("\r\n")):]
    for n in sorted(rest, reverse=True):
        del lines[n - 1]
    path.write_text("".join(lines))


@dataclass
class Source:
    key: str
    cite: str                   # the short form shown on screen: "Gauchet, Right and Left (1996)"
    title: str
    author: str = ""
    publisher: str = ""
    year: str = ""
    url: str = ""
    where: str = ""             # the page, chapter or timestamp, for a source that is not one web page
    quote: tuple = ()           # the passages that back what the script says
    accessed: str = ""
    note: str = ""

    def reference(self):
        """One line for a description or a source list."""
        head = ", ".join(x for x in (self.author, f"“{self.title}”") if x)
        tail = ", ".join(x for x in (self.publisher, str(self.year), self.where) if x)
        return " ".join(x for x in (f"{head}." if head else "", f"{tail}." if tail else "", self.url) if x)


def load_sources(root):
    """{key: Source} from sources.toml, and a list of what is wrong with the file."""
    path = Path(root) / "sources.toml"
    if not path.exists():
        return {}, []
    out, errors = {}, []
    for key, row in tomllib.loads(path.read_text()).items():
        unknown = set(row) - set(Source.__dataclass_fields__)
        if unknown:
            errors.append(f"source {key}: unknown field(s) {', '.join(sorted(unknown))}")
            continue
        quote = row.pop("quote", ())
        row["year"] = str(row.get("year", ""))
        try:
            out[key] = Source(key=key, quote=(quote,) if isinstance(quote, str) else tuple(quote), **row)
        except TypeError as e:
            errors.append(f"source {key}: {e}")
    return out, errors


def problems(script, sources, source_errors=()):
    """(errors, warnings): everything that breaks the promise the labels make."""
    errors = [f"script.md:{n}: {msg}" for n, msg in script.errors] + list(source_errors)
    warnings = []
    used = set()
    for b in script.beats:
        where = f"script.md:{b.line}: {b.id} [{b.kind}]"
        if b.kind in SOURCED and not b.sources:
            errors.append(f"{where} has no source")
        for key in b.sources:
            used.add(key)
            if key not in sources:
                errors.append(f"{where} cites {key!r}, which is not in sources.toml")
        if b.kind in ("opinion", "speculation", "line") and b.sources:
            warnings.append(f"{where} cites sources: if part of it is checkable, split that part into a fact")
    for key, s in sources.items():
        if not (s.url or s.where):
            errors.append(f"source {key}: needs a url, or `where` it can be found")
        if key in used and not s.quote:
            errors.append(f"source {key}: needs a quote, the passage that backs what the script says")
        if key not in used:
            warnings.append(f"source {key} is not cited by any beat")
    return errors, warnings


def word_count(script):
    return sum(len(re.findall(r"[\w'’]+", b.plain)) for b in script.beats)
