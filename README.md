# explainers

Narrated explainer videos about the arguments people keep having: left and right, abortion, the drug war,
capitalism and communism, the environment. They are drawn in Python, frame by frame, as flat vector
animation (Skia), with [manim](https://www.manim.community/) for the charts and mathematics it suits, and
spoken by a voice that runs on the machine. One character, the host, is in all of them.

What sets them apart is the [editorial standard](EDITORIAL.md): every sentence of a script is labelled as
a fact, an estimate, somebody's view, an opinion or a guess. Facts have to cite a source, the label is on
screen while the sentence is spoken, and a script that breaks the rule does not get narrated.

| Video | What it is |
| --- | --- |
| [`left-and-right`](videos/left-and-right) | *Left and Right*, a short pilot: where the two words come from (a seating plan in 1789), how late English took them up, and how the labels work |
| [`_template`](videos/_template) | Starting point for the next video: the host says the script and nothing else happens |

## Layout

```
explainers/               shared library and CLIs
  script.py               script.md and sources.toml: beats, the six kinds of statement, what breaks the rules
  check.py                python -m explainers.check VIDEO         labels, sources, length; --urls fetches them
  narrate.py              python -m explainers.narrate VIDEO       script -> voice, with every word's timing
  record.py               python -m explainers.record VIDEO        read the script into a microphone, a beat at a time
  align.py                when each word is said in a recording, found by listening for the script's words
  listen.py               what a take really says, and where it leaves the script (so the script can follow it)
  narration.py            the narration at render time: cues by beat and word, the speaker's mouth
  describe.py             python -m explainers.describe VIDEO      description with sources, captions.srt
  draw.py                 Skia helpers: smooth paths from a few points, shape arithmetic, type
  anim.py                 easing curves, ramps, deterministic randomness
  theme.py                the paper, the palette, the type, and the on-screen label for each kind of statement
  host.py                 Footnote, the host: a rig posed by numbers; python -m explainers.host sheet.png
  sets.py                 where a video happens: a classroom whose projector screen shows the slides, and a
                          camera from the wide shot in to the screen; python -m explainers.sets sheet.png
  inserts.py              manim clips inside a video, rendered when their scene or the narration changes
  manimkit.py             the video's look and clock inside manim (import it only from a scene file)
  video.py                the video.py contract, and the loader the CLIs use
  new.py                  python -m explainers.new NAME            new video from _template
  preview.py              python -m explainers.preview VIDEO …     contact sheet of frames
  sweep.py                python -m explainers.sweep VIDEO         draw every frame, report exceptions
  render.py               python -m explainers.render VIDEO        parallel render -> x264 -> mp4 with the narration
  sheet.py                contact sheets of any pictures
  fonts/                  Inter (SIL OFL), PT Serif (ParaType Free Font Licence)
videos/
  left-and-right/         the pilot: script, sources, the hall, a manim chart, the video
  _template/              copy this to start a video (python -m explainers.new NAME)
```

Inside a video:

- `script.md` is the narration, beat by beat, each beat labelled. `sources.toml` is what it cites.
- `say.txt`, if there is one, tells the voice how to say the words it gets wrong.
- `video.py` draws it: `frame(t)` returns the picture at `t` seconds. See `explainers/video.py` for the
  rest of the contract. A video's other modules sit next to it and import each other flat.
- `data/` is committed. It holds the narration's timings (`narration.json`, `voice.npy`), which the video
  is cut to, and any dataset a chart draws.
- `audio/` and `build/` are ignored by git: the narration itself and the narrator's own takes
  (`audio/takes/`, the one thing here that cannot be made again), cached speech, manim frames, render
  segments and previews.

## Setup

You need [uv](https://docs.astral.sh/uv/) and `ffmpeg` on `PATH` (`FFMPEG=/path/to/ffmpeg` picks another
binary). A snap-packaged ffmpeg can only read and write under `$HOME`, so keep the repo there.

```sh
uv sync                                  # drawing and rendering: numpy, Pillow, Skia
uv sync --extra voice                    # narration too: Kokoro on CPU torch (the model downloads on first use)
uv sync --extra voice --extra manim      # manim inserts too; a LaTeX install is only needed for formulas
```

Nothing here needs a GPU.

## Pipeline: script -> voice -> video

```sh
uv run python -m explainers.new my-video             # videos/my-video from _template
# write videos/my-video/script.md and sources.toml
uv run python -m explainers.check videos/my-video    # every beat labelled, every fact sourced; --urls fetches the sources
uv run python -m explainers.narrate videos/my-video  # audio/narration.wav, data/narration.json
uv run python -m explainers.record videos/my-video   # optional: read it yourself, then narrate again
uv run python -m explainers.render videos/my-video   # the baseline video -> videos/my-video/my-video.mp4
uv run python -m explainers.describe videos/my-video # build/description.txt (chapters, sources), build/captions.srt
```

Then draw it: replace the template's `video.py` scene by scene, with the working loop below.

**Scripts.** A paragraph is a beat. Its first line, in square brackets, says what kind of statement it is
and which sources back it:

```
## room: A seating plan
> The hall from the president's chair.

[fact: bienfait, archives]
From a room. In the summer of 1789, France's new National Assembly was meeting at Versailles, and arguing
over how much power to leave the king: should he be able to veto its laws?

[opinion | pause 1.0]
I think a seating plan is a thin way to describe what people believe.
```

The kinds are `fact`, `estimate`, `view`, `opinion`, `speculation` and `line`;
[EDITORIAL.md](EDITORIAL.md) says what each one promises. Options follow a bar: `pause SECONDS` of silence
after the beat, `id NAME` to name it (otherwise a beat is `<section>.<n>`). Lines starting with `>` are
notes on the picture and `<!-- -->` is a comment; neither is spoken. `check` reports the length (about 155
words a minute) and how the words divide between the kinds.

**Sources.** One table per source in `sources.toml`: `cite` (the short form shown on screen), `title`,
`author`, `publisher`, `year`, `url` or `where`, and `quote`, the passage that backs the script. A cited
source without a quote is an error: the point is that somebody read it.

**The voice.** [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) speaks each beat on its own, several
times faster than real time on a CPU, and reports when every word starts and ends. Beats are cached, so
after an edit only the changed ones are spoken again. Set `voice:` and `speed:` at the top of the script
(`am_michael`, `af_heart`, `bm_george`, ...). It guesses at words it doesn't know, mostly names: `narrate`
lists them, and `say.txt` fixes the wrong ones (`Gauville = go-VEEL`, or phonemes between slashes).
Changing the script changes the timings, so `data/narration.json` is committed with the video that is cut
to it.

**Your own voice.** `python -m explainers.record VIDEO`, in a terminal, shows the script a beat at a time
and records each one from the microphone: Enter starts, Enter stops, and it reports the level, the room's
noise, and whether it heard the script's words before asking whether to keep the take. Takes are kept
untouched in `audio/takes/`. `narrate` then uses a take wherever a beat has one and the synthetic voice
elsewhere, so a video can be drafted in the synthetic voice and voiced a beat at a time. A take is cut to
its first and last word, matched in loudness to the others, and timed by a small speech model that listens
for the script's words (within a frame or so of the synthetic voice's own timings in our tests). `record
--room` records ten seconds of the empty room, which is laid under the gaps so that the room does not cut
in and out between beats. Changing a beat's words makes its take stale (`record --list`); changing its
spelling or punctuation does not.

A beat does not have to be read word for word. Each take is also written down by a second listener
(Whisper large-v3, on the CPU, about four seconds a take), and where its words differ from the script's
the aligner's model is asked which wording fits the sound better. Where both hear the reader's words and
not the script's, `record` shows the difference, and on Enter script.md gets the words that were said.
A fact can be reworded this way as easily as a joke, so the session ends with the beats that changed and
which of them are sourced: read those sources against the new words (`git diff` shows the changes).

Whoever speaks, the finished narration is brought to -16 LUFS with a limiter holding its peaks, and a
recorded voice is evened out a little first (a 2.5:1 compressor above its average level). `narrate` prints
the loudness it ended up at.

**Pictures.** `video.py` asks the narration when things are said and draws accordingly:

```python
N = Narration(ROOT)
N.at("room.2", "right")       # when the beat room.2 says "right"
N.end("room.2")               # when its last word ends
N.mouth(t)                    # the host's mouth, from the sounds being spoken
```

Cues are looked up by the script's words, so pictures stay on their words when the narration is spoken
again. `theme.narration_label` draws the label for the current beat, and `host.alive(pose, t, N)` makes
the host hover, blink and speak.

**Manim.** Write the scene in a file next to `video.py` as a subclass of `explainers.manimkit.Insert`, and
make an `explainers.inserts.Clip` for it. The scene has the narration's cues on its own clock
(`self.cue("english.3", "twenties")`, `self.until(t)`), is rendered with a transparent background at the
video's size and frame rate, and is drawn into the frame with `CLIP.draw(canvas, t)`. It is re-rendered
when its file, the narration or its start time changes.

## Working loop

```sh
uv run python -m explainers.preview videos/left-and-right look room         # three frames through each beat of a section
uv run python -m explainers.preview videos/left-and-right look 12:20:0.5 31 # or times and a:b:step ranges; `beats` is every beat
uv run python -m explainers.sweep   videos/left-and-right                   # every frame, a few seconds
uv run python -m explainers.render  videos/left-and-right --fresh
```

Look at the contact sheet (`build/preview/NAME.png`) rather than reasoning about coordinates. `render`
keeps finished segments so an interrupted render resumes; after changing code or narration, pass
`--fresh`.

## The host

`python -m explainers.host sheet.png` draws the character sheet. Footnote is a hovering robot with a
screen for a face, loose hands, and an asterisk on its antenna. A `Pose` is a couple of dozen numbers
(lean, head turn, eyes, lids, mouth, where each hand is and what it is doing); `host.perform` eases
between poses on a timeline, and `host.sign` is the paddle it holds up to own an opinion.

The two sides of an argument are drawn in mustard and teal, never red and blue: red means the left in most
of the world and the right in the United States.
