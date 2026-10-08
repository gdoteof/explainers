---
name: explainer-video
description: Run the research -> script -> voice -> video pipeline in the explainers repo (~/claude/explainers) - research a topic into a sourced fact sheet, write a script whose every beat is labelled fact / estimate / view / opinion / speculation / line, check it, narrate it with the local voice, draw the scenes in Skia (manim for charts), render and write the description. Use when the user wants an explainer video made or changed, a script drafted or fact-checked, or mentions the explainers pipeline or Footnote the host.
---

# Explainer video

Work from the repo root with `uv run`. `README.md` has the commands and file formats; `EDITORIAL.md` is the
standard. This is the order of work, and where the user's checkpoints are.

## 1. Research, before any script

- Settle the question the video answers in one sentence, and the three or four things a viewer should
  be able to say afterwards.
- Build a fact sheet: one claim per line, each with a source that was fetched and read in this session
  and the passage that backs it. Research in a subagent is fine, but tell it to return verbatim quotes and
  to mark what it could not stand up; never accept a URL it did not open.
- For a contested topic, collect each side's case from its own strongest advocates, and note which
  disagreements are about facts and which are about values.
- Write down what the sources do NOT support. Popular versions of a story are often tidier than the
  evidence.

## 2. Script (checkpoint: the user approves it)

- `python -m explainers.new NAME`, then `script.md` and `sources.toml`.
- One idea to a beat, a beat to a breath: 15 to 40 words. Write for the ear: short sentences, the
  important word last, numbers rounded to what a listener can hold, no brackets or abbreviations.
- Open on the question or the surprise, not on a greeting. Each section should leave the viewer wanting
  the next one.
- Label by what the sentence promises, not by how sure you feel. Split a beat that mixes kinds. A script
  that is mostly `fact` and `view` with a few clearly marked `opinion` beats is the target; `check` prints
  the split.
- Do not write the channel's `opinion` on a contested question yourself. Leave a marked gap, or draft one
  and say plainly that it is a draft for the user to accept, change or cut.
- Put a `>` note under each section saying what is on screen. Every beat needs a picture that changes at
  least every five seconds or so.
- `python -m explainers.check videos/NAME --urls` must pass. Show the user the script with the split and
  the source list.

## 3. Voice (checkpoint: the user picks the voice once, by ear)

- `python -m explainers.narrate videos/NAME --audition am_michael af_heart bm_george ...` for a new
  channel voice; after that the script's `voice:` line stands.
- `python -m explainers.narrate videos/NAME`. Fix the words it guessed at in `say.txt`. Add `pause` to a
  beat when its picture needs time to land.

## 4. Pictures

- Start from the template's `video.py` and replace it scene by scene. One scene per section is the usual
  grain; cut between them with `theme.scenes`.
- Hang every move on a cue: `N.at(beat, word)`. Never type a time in seconds.
- The host is small and to one side while something is being explained, and large when it speaks for
  itself (the opening, an opinion, the close). It looks at and points to what is being talked about.
- Charts, graphs and anything mathematical go in a manim `Insert`. Everything else is Skia.
- Sides of an argument are `theme.SIDE_A` / `theme.SIDE_B`. A dataset a chart draws is saved in the
  video's `data/` with where it came from and when.
- Loop: `preview` a section, look at the sheet, fix, repeat; `sweep` before every render.

## 5. Render and hand over (checkpoint: the user watches it)

- `python -m explainers.render videos/NAME --fresh`, then `python -m explainers.describe videos/NAME`.
- Report what is fact-checked and what is not, any beat whose label was a judgement call, and anything the
  voice says oddly.
