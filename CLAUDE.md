# explainers

Narrated explainer videos on big recurring political arguments, drawn in Python. Start with `README.md`
for the layout and commands. `EDITORIAL.md` is the standard every script is held to: read it before
writing or changing a script. For the whole research -> script -> voice -> video pipeline, use the
`explainer-video` skill (`.claude/skills/explainer-video/SKILL.md`).

## Environment

- **Python:** run everything with `uv run` from the repo root. `uv sync --extra voice --extra manim` adds
  the narration stack (Kokoro on CPU torch) and manim.
- **ffmpeg:** it may be the snap build, which can only read and write under `$HOME`. Keep audio and build
  output inside the repo, not in `/tmp`. Set `FFMPEG` to use another binary.
- **GPU:** nothing here uses it. The voice runs on the CPU on purpose, so narration never waits for a
  GPU job elsewhere on the machine.

## Where a video starts

With a conversation: the owner's worldview is unpacked by interviewing them (step 0 of the skill), and a
video argues something they think, tested against sources. Their answers are kept in `notes/`, which git
ignores. Videos run 12 to 25 minutes and are about how things work now; history is an aside.

## Truth

- Never write a `fact` or an `estimate` from memory. Fetch the source, read it, and copy the passage that
  backs the beat into `sources.toml` as `quote`. If a claim can't be stood up, relabel it or cut it.
- `python -m explainers.check VIDEO` must pass before `narrate`. Its warnings are worth reading too.
- An `opinion` or `speculation` beat on a contested question is the channel owner's to give or approve.
  Draft one if asked, mark it for their review, and never slip a position into a `fact` or a `line`.
- On contested questions give each side its strongest form from its own advocates, with the same quality
  of picture and time.

## Conventions

- `explainers/` holds what every video shares, which includes the look (`theme.py`) and the host
  (`host.py`). Per-video code stays in `videos/<name>/`, and modules there import each other flat. If the
  same code gets copied into a second video, move it into `explainers/`.
- `videos/<name>/audio/takes/` holds the narrator's own recordings (`python -m explainers.record`). They are
  not in git and nothing can regenerate them: never delete, move or overwrite a take. `record` replaces one
  only when the narrator keeps a new reading, and a script edit that changes a beat's words makes its take
  stale, so say so before rewording a beat that is already recorded.
- `videos/<name>/data/` is committed. `narration.json` is what the pictures are cut to: after changing
  `script.md`, run `narrate` again and then `sweep`, which finds any cue whose word is gone. Media and
  `build/` are gitignored.
- Use manim (`explainers.inserts`) for charts, graphs and mathematics, and Skia for everything else.
- The two sides of an argument are `theme.SIDE_A` and `theme.SIDE_B` (mustard and teal), never red and
  blue.
- The repo is public. Routine pushes to `main` are fine, the owner has said so; ask before anything that
  rewrites history or publishes somewhere new (an upload, a release). Keep private notes out of committed
  files.
- Check visual changes by rendering previews and looking at the contact sheet, not by reasoning about
  coordinates.
