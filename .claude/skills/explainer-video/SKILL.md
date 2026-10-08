---
name: explainer-video
description: Run the conversation -> research -> script -> voice -> video pipeline in the explainers repo (~/claude/explainers) - interview the owner to find what a video should argue, research it into a sourced fact sheet, write a script whose every beat is labelled fact / estimate / view / opinion / speculation / line, check it, narrate it with the local voice, draw the scenes in Skia (manim for charts), render and write the description. Use when the user wants to talk through ideas for a video, wants an explainer video made or changed, a script drafted or fact-checked, or mentions the explainers pipeline or Footnote the host.
---

# Explainer video

Work from the repo root with `uv run`. `README.md` has the commands and file formats; `EDITORIAL.md` is the
standard. This is the order of work, and where the user's checkpoints are.

## 0. The conversation, where a video starts

Videos come out of what the owner thinks, tested, not out of a topic list. Before any research, interview
them.

- One or two questions at a time, in plain conversation, and short: the owner answers by dictation, and
  five at once was too many to answer or to keep straight. Over the rounds, mix the kinds: open questions
  ("what is each side protecting?"), quizzes they answer before you look the answer up ("what share would
  you guess?"), steelman tests ("put the other side's case so that they would sign it"), and bait: the
  strongest objection to what they just said, put bluntly. Follow the answer that surprised you, not the
  next question on a list.
- The owner's wrong guesses can go on screen: they have agreed to that. But a number is their guess only
  if they offered it as a guess. A number inside an example ("say they spend 70% on bills...") is an
  illustration: record it as one, never score it or show it as a guess, and ask when it is not clear
  which it was.
- Listen for the claim under the answer: a thesis that could be wrong, a distinction they keep making, a
  story of their own. Those are videos. A topic ("abortion") is not an idea; "the two sides are answering
  different questions" is one.
- Keep their words. Save answers verbatim and dated in `notes/<topic>.md`, which git ignores: the notes
  are raw and private, and the script is the published form. Mark your own summaries as yours.
- Sort what they said by what the script will need. What can be checked becomes research, then `fact`,
  `estimate` or `view` beats. What is theirs becomes `opinion` or `speculation`. Pin down loaded words
  before they go further ("engineered": by whom, and how would we know?), and tell them plainly when the
  sources do not support something they believe.
- Stop when there is a thesis, three or four moves that carry it, and the strongest objection to it. Play
  that back in a few lines and get a yes before researching.

The owner wants how things work now. Where a thing came from is a short aside inside a video, not the
video.

## 1. Research, before any script

- Settle the question the video answers in one sentence, and the three or four things a viewer should
  be able to say afterwards.
- Build a fact sheet: one claim per line, each with a source that was fetched and read in this session
  and the passage that backs it. Keep the sources in `videos/NAME/sources.toml` from the first day (a
  folder with only that file is a video being researched, or parked) and the claims in `notes/NAME.md`. Research in a subagent is fine, but tell it to return verbatim quotes and
  to mark what it could not stand up; never accept a URL it did not open.
- For a contested topic, collect each side's case from its own strongest advocates, and note which
  disagreements are about facts and which are about values.
- Write down what the sources do NOT support. Popular versions of a story are often tidier than the
  evidence.

## 2. Script (checkpoint: the user approves it)

- `python -m explainers.new NAME` (it fills in around a `sources.toml` that is already there), then
  `script.md`.
- A video runs 12 to 25 minutes: about 2,100 to 4,400 words at the owner's reading pace (about 175 words
  a minute with the pauses). Give it sections a viewer can feel the turn of, each with its own question.
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

## 3. Voice (checkpoint: the user records it)

- Draft with the synthetic voice: `python -m explainers.narrate videos/NAME`. Fix the words it guessed at
  in `say.txt`. Add `pause` to a beat when its picture needs time to land. The pictures can be built and
  the script settled on this draft.
- When the wording is settled, the user records it in a terminal of their own:
  `python -m explainers.record videos/NAME` shows each beat, records it, and checks the take for level and
  for the script's words. `--room` records the empty room once, for the gaps. Then `narrate` again: it
  uses a take wherever there is a fresh one. Pictures stay on their words, since cues are looked up by
  word, but beats change length: run `sweep` and look at a contact sheet before rendering.
- The user does not have to read word for word. Where a take leaves the script, `record` shows the
  difference and, if they keep it, rewrites the beat in script.md to what they said. So commit the script
  before they record, and afterwards read `git diff` of it: tidy the spelling and punctuation of the new
  words (that does not make a take stale), and for every changed `fact`, `estimate` or `view` read the
  source's quotation against the new words. If it no longer bears them out, tell the user: the beat is
  read again or relabelled, not left.
- Rewording a recorded beat yourself costs the user a new reading. Batch such changes and ask first.
- `--audition VOICE ...` compares synthetic voices for the draft; the script's `voice:` line picks one.

## 4. Pictures

- Start from the template's `video.py` and replace it scene by scene. One scene per section is the usual
  grain; cut between them with `theme.scenes`.
- A video happens on a set (`explainers/sets.py`): so far a classroom with a projector screen, which is
  what the owner asked for. Draw a chart, a card or a figure as a slide, a 1920x1080 picture, and give it
  to the set: the same slide is on the screen in the wide shot and fills the frame when the camera goes
  in (`sets.shots` for the moves). Go in when the slide has to be read, come out when the host has
  something to do, and turn the projector down (`on`) when the host steps forward with an opinion. Put
  the section's title on the board (`chalk`), and give the label a `plate` so it reads over the room.
  A script's `>` notes say "Wide" or "Projector". Other sets will follow: keep a slide free of the room.
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
