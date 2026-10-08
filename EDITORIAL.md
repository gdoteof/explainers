# Editorial standard

These videos take on arguments that people have been having for a long time: left and right, abortion,
the drug war, capitalism and communism, the environment. On questions like those a viewer has good reason
to ask of every sentence, "says who?" The standard below is how a video answers that, and
`python -m explainers.check` enforces the parts of it a program can.

## Every statement says what kind of statement it is

A script is a list of beats, and each beat carries one of six labels. Five of them show on screen while
the beat is spoken.

| Kind | On screen | What it promises | Needs |
| --- | --- | --- | --- |
| `fact` | **FACT** and the source | It can be checked, and we checked it. | A source, with the passage quoted in `sources.toml` |
| `estimate` | **ESTIMATE** and the source | Somebody measured or modelled this number, and it could be off. The narration says by how much, or says that nobody knows. | A source |
| `view` | **A VIEW** and the source | Some people hold this. It is put the way they would put it, and the narration says who they are. | A source in which they say it themselves |
| `opinion` | **MY OPINION** | This is what the channel thinks. Reasonable people think otherwise. | Nothing |
| `speculation` | **A GUESS** | Nobody knows this: it is about the future, or about something unmeasured. | Nothing |
| `line` | nothing | It claims nothing: a question, a transition, a joke. | Nothing |

When a sentence mixes kinds, split it. "Overdose deaths passed 100,000 a year, which shows prohibition has
failed" is a fact and then an opinion, and each half gets its own beat and its own label.

When in doubt between two kinds, take the weaker one: an `estimate` rather than a `fact`, a `view` rather
than a `fact`, `speculation` rather than an `opinion` about what will happen.

## Sources

- Read the source. `quote` in `sources.toml` is the passage that backs the script, copied out, so that the
  next person can check the claim without reading the whole thing. A claim with no passage to quote is not
  a fact yet.
- Prefer, in this order: the primary document or dataset; scholarship that works from it; a standard
  reference work; careful journalism. An encyclopedia or a search result is a way to find a source, not
  one.
- A number comes with its unit, its year, who counted, and what it is a share of.
- A source's own politics do not disqualify it for a `view` (the best source for what a movement believes
  is the movement), but they do for a `fact` when a neutral source exists.
- Every source is shown on screen in short form while its beat is spoken, and listed in full in the
  description (`python -m explainers.describe`).

## Contested questions

- State each side's position so that the people who hold it would say "yes, that is what we think". Take
  the strongest form of it, from its own advocates, before saying anything against it.
- Separate the two kinds of disagreement. Some are about what is true (does this policy reduce overdoses?),
  and evidence bears on them. Some are about what matters (how to weigh liberty against safety), and
  evidence does not settle them. Say which kind each one is.
- Give a `view` the same quality of picture, voice and time as the view against it.
- An `opinion` comes after the views, not instead of them, and says what would change it.
- Do not present a matter of settled evidence as an open one in order to look balanced, or an open one as
  settled in order to look decisive.

## Corrections

When a video turns out to be wrong, say so where the viewer will see it: a pinned comment and a line at the
top of the description, with the time of the error and the correction. Record it in the video's
`CORRECTIONS.md`. A mistake is not fixed by quietly replacing the upload.

## Who is talking

The narrator is the channel's author, recorded, or a synthetic voice in a video that has not been voiced
yet; the host is a drawing of a robot. Scripts are researched and drafted with an AI model and edited by a
person, who is responsible for what they say. The description of every video says which voice it is, and
says the rest.
