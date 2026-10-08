import json

import numpy as np
import pytest

from explainers.narration import Narration


@pytest.fixture
def narration(tmp_path):
    (tmp_path / "data").mkdir()
    doc = dict(title="T", voice="v", speed=1.0, duration=6.0, env_fps=60,
               sections=[dict(id="a", title="First"), dict(id="b", title="")],
               beats=[dict(id="a.1", section="a", kind="fact", sources=["s"], text="Left, then right. Right?", t0=0.5, t1=2.0,
                           words=[["Left,", 0.5, 0.8, "lˈɛft"], ["then", 0.9, 1.0, "ðˈɛn"], ["right.", 1.0, 1.3, "ɹˈIt"],
                                  ["Right?", 1.6, 2.0, "ɹˈIt"]]),
                      dict(id="b.1", section="b", kind="opinion", sources=[], text="France's turn.", t0=3.0, t1=4.0,
                           words=[["France's", 3.0, 3.5, "fɹˈænsɪz"], ["turn.", 3.5, 4.0, "tˈɜɹn"]])])
    (tmp_path / "data" / "narration.json").write_text(json.dumps(doc))
    np.save(tmp_path / "data" / "voice.npy", np.full(360, 200, np.uint8))
    return Narration(tmp_path)


def test_cues_find_words_whatever_their_punctuation_or_case(narration):
    assert narration.at("a.1") == 0.5
    assert narration.at("a.1", "left") == 0.5
    assert narration.at("a.1", "right") == 1.0
    assert narration.at("a.1", "Right", 2) == 1.6
    assert narration.end("a.1", "right", 2) == 2.0
    assert narration.at("b.1", "France's") == 3.0
    assert narration.section("a") == (0.5, 2.0)


def test_a_cue_for_a_word_that_is_not_said_raises(narration):
    with pytest.raises(KeyError, match="says 'veto' 0 time"):
        narration.at("a.1", "veto")
    with pytest.raises(KeyError, match="no beat"):
        narration.at("c.1")


def test_beat_at_holds_the_last_beat_through_a_pause(narration):
    assert narration.beat_at(0.2) is None
    assert narration.beat_at(1.0).id == "a.1"
    assert narration.beat_at(2.5).id == "a.1" and not narration.speaking(2.5)
    assert narration.beat_at(3.2).id == "b.1" and narration.speaking(3.2)
    assert narration.said(1.05) == "Left, then right."


def test_the_mouth_is_shut_between_beats_and_open_on_a_vowel(narration):
    assert narration.mouth(2.6)[1] == 0.0
    assert narration.mouth(3.25)[1] > 0.2
