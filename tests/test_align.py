"""The parts of the recorded-voice path that need no speech model: how a script word is heard, the path
through a model's output, and where a take's voice starts and stops."""
import numpy as np
import pytest

pytest.importorskip("num2words")
pytest.importorskip("scipy")

from explainers import align, record, script as S


def test_spell_reads_numbers_as_they_are_said():
    assert align.spell("1789,") == ["SEVENTEEN", "EIGHTY", "NINE"]
    assert align.spell("1920s") == ["NINETEEN", "TWENTIES"]
    assert align.spell("29th") == ["TWENTY", "NINTH"]
    assert align.spell("1,200") == ["ONE", "THOUSAND", "TWO", "HUNDRED"]
    assert align.spell("left-wing") == ["LEFT", "WING"]
    assert align.spell("France’s") == ["FRANCE'S"]
    assert align.spell("“Gauville”:") == ["GAUVILLE"]
    assert align.spell("—") == []


def test_spelled_ignores_punctuation_and_case():
    assert align.spelled("Left. Right, we sort…") == align.spelled("left right: We sort")
    assert align.spelled("the king") != align.spelled("the crown")


def test_trace_follows_the_letters_through_the_frames():
    sure, faint = np.log(0.98), np.log(0.01)
    said = [1, 1, 0, 2, 2, 0]                           # A A - B B -   (0 is the blank)
    logp = np.full((len(said), 3), faint)
    for t, k in enumerate(said):
        logp[t, k] = sure
    assert list(align.trace(logp, [1, 2])) == [0, 0, -1, 1, 1, -1]
    with pytest.raises(ValueError):
        align.trace(logp[:1], [1, 2, 1, 2])


def test_edges_follow_the_voice_out_to_the_room():
    rng = np.random.default_rng(0)
    sr = record.SR
    audio = rng.normal(0, 0.001, 4 * sr).astype(np.float32)
    t = np.arange(2 * sr) / sr
    audio[sr:3 * sr] += (0.3 * np.sin(2 * np.pi * 180 * t)).astype(np.float32)      # a voice from 1.0s to 3.0s
    a, b = record.edges(audio, 1.2, 2.7)                # the aligner hears it late and loses it early
    assert abs(a - 1.0) < 0.03 and abs(b - 3.0) < 0.03


def test_a_take_goes_stale_when_its_words_change(tmp_path):
    import soundfile as sf
    (tmp_path / "script.md").write_text("# T\n\n## a: A\n\n[line]\nLeft, and right.\n")
    beat = S.load(tmp_path).beats[0]
    assert record.state(tmp_path, beat) == "none"
    wav = record.take_path(tmp_path, beat.id)
    wav.parent.mkdir(parents=True)
    sf.write(wav, np.zeros(100, np.float32), record.SR)
    assert record.state(tmp_path, beat) == "fresh"      # a take with no note of its words is taken on trust
    wav.with_suffix(".txt").write_text("left and right\n")
    assert record.state(tmp_path, beat) == "fresh"
    wav.with_suffix(".txt").write_text("left and wrong\n")
    assert record.state(tmp_path, beat) == "stale"
