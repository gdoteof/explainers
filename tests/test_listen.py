"""Where a reading leaves its script, and how the script follows it: the parts that need no speech model."""
import pytest

pytest.importorskip("num2words")

from explainers import align, listen, script as S


def spans(text, said):
    return listen.differences(text, said)


def test_spelling_punctuation_and_spacing_are_not_differences():
    assert spans("We began to recognise one another: the neighbours.", "we began to recognize one another, the neighbors") == []
    assert spans("UnitedHealth took 31 per cent of it.", "United Health took thirty-one percent of it.") == []
    assert spans("In 2032 — or so — it runs out.", "In twenty thirty-two or so it runs out.") == []
    assert spans("Four programmes, in your favour.", "Four programs in your favor.") == []


def test_another_word_is_a_difference_however_close():
    text = "About two hundred billion dollars went to Medicare."
    assert spans(text, "About two hundred million dollars went to Medicare.") == [(3, 4, 3, 4)]
    assert spans(text, "About two hundred billion dollars went to Medicaid.") == [(7, 8, 7, 8)]
    assert spans("fourteen cents", "forty cents") == [(0, 1, 0, 1)]
    assert spans("it is four", "it is for") == [(2, 3, 2, 3)]


def test_words_added_and_left_out_are_found_where_they_are():
    assert spans("Three numbers.", "Three numbers. Say them out loud.") == [(2, 2, 2, 6)]
    assert spans("Three numbers. Say them out loud.", "Three numbers.") == [(2, 6, 2, 2)]
    assert spans("So where did they come from?", "So, where do they come from?") == [(2, 3, 2, 3)]


def test_the_script_follows_only_the_spans_it_is_given():
    text, said = "Here is my guess: fourteen cents, squeezed onto it.", "Here's my guess, fifteen cents squeezed into it."
    found = spans(text, said)
    assert found == [(0, 2, 0, 1), (4, 5, 3, 4), (7, 8, 6, 7)]
    assert listen.follow(text, said, found[1:]) == "Here is my guess: fifteen cents, squeezed into it."
    assert listen.follow(text, said, []) == text


def test_a_word_that_stands_in_keeps_the_script_s_punctuation_and_marks_stay_whole():
    text = "The Baron de [Gauville](/ɡoʊvˈil/) wrote it down: we were *beginning*, he said."
    said = "The Baron de Gauville wrote this down. We were starting, he said."
    found = spans(text, said)
    assert listen.follow(text, said, found) == "The Baron de [Gauville](/ɡoʊvˈil/) wrote this down: we were starting, he said."
    assert listen.describe(text, said, found[:1]) == ["“Gauville wrote it down: we”  →  “Gauville wrote this down: we”"]


def test_a_word_that_stands_in_is_a_capital_only_where_the_script_starts_a_sentence():
    text, said = "People over sixty-five: fourteen cents.", "People over sixty-five. Fifteen cents."
    assert listen.follow(text, said, spans(text, said)) == "People over sixty-five: fifteen cents."
    text, said = "It is easy. Spending it well is hard.", "It is easy, but I think spending it well is hard."
    assert listen.follow(text, said, spans(text, said)) == "It is easy. But I think spending it well is hard."
    assert listen.describe(text, said, spans(text, said), around=1) == ["“easy. Spending”  →  “easy. But I think spending”"]
    text, said = "It is easy. Medicare is hard.", "It is easy, and then Medicare is hard."
    assert listen.follow(text, said, spans(text, said)) == "It is easy. And then Medicare is hard."
    text, said = "It is hard, and slow.", "It is hard. I mean slow."
    assert listen.follow(text, said, spans(text, said)) == "It is hard, I mean slow."


def test_a_loose_reading_is_still_near_and_another_text_is_not():
    text = "Spending money is easy. Spending money well is hard."
    assert listen.likeness(text, "Spending money is easy, but spending it well is really hard.") > 0.6
    assert listen.likeness(text, "Thank you for watching.") < 0.3


def test_a_take_does_for_a_respelling_of_its_words():
    assert align.sound("a programme of 31 per cent") == align.sound("A program of thirty-one percent.")
    assert align.sound("four") != align.sound("for")
    assert align.sound("your hours") == "YOURHOURS"


def test_reword_changes_one_beat_and_nothing_else(tmp_path):
    (tmp_path / "script.md").write_text(
        "# T\n\nvoice: am_michael\n\n## a: A\n> Wide: the room.\n\n<!-- a note\nover two lines -->\n[fact: x | pause 1.0]\nLeft,\n> a note in the middle\nand right.\n\n[line]\nThe end.\n")
    S.reword(tmp_path, "a.1", "Left,  and then right.")
    assert (tmp_path / "script.md").read_text() == (
        "# T\n\nvoice: am_michael\n\n## a: A\n> Wide: the room.\n\n<!-- a note\nover two lines -->\n[fact: x | pause 1.0]\nLeft, and then right.\n> a note in the middle\n\n[line]\nThe end.\n")
    script = S.load(tmp_path)
    assert [b.plain for b in script.beats] == ["Left, and then right.", "The end."] and not script.errors
    assert script.beats[0].pause == 1.0 and script.beats[0].sources == ["x"]
