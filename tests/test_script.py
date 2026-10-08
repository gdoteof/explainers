from explainers import script as S

GOOD = """# A Title

voice: af_heart
speed: 1.1

## one: The first part
> a note on the picture

[fact: book | pause 1.5]
The [Seine](/sˈɛn/) runs through *Paris*.

[opinion | id mine]
I like it.

<!-- a comment
over two lines -->
## two

[line]
On we go.
"""


def test_parses_beats_settings_and_notes():
    s = S.parse(GOOD)
    assert s.errors == []
    assert s.title == "A Title"
    assert s.settings["voice"] == "af_heart" and s.settings["speed"] == 1.1
    assert s.sections == [("one", "The first part"), ("two", "")]
    assert [b.id for b in s.beats] == ["one.1", "mine", "two.1"]
    fact = s.beats[0]
    assert (fact.kind, fact.sources, fact.pause, fact.notes) == ("fact", ["book"], 1.5, ["a note on the picture"])
    assert fact.plain == "The Seine runs through Paris."
    assert "[Seine](/sˈɛn/)" in fact.text


def test_a_paragraph_needs_a_label():
    s = S.parse("# T\n\n## a\n\nNobody said what this is.\n")
    assert any("no label" in msg for _, msg in s.errors)


def test_unknown_kind_and_option_are_errors():
    s = S.parse("# T\n\n## a\n\n[truth | loud yes]\nIt is so.\n")
    msgs = " ".join(msg for _, msg in s.errors)
    assert "unknown kind" in msgs and "unknown option" in msgs


def test_a_fact_needs_a_source_that_exists_and_quotes():
    s = S.parse("# T\n\n## a\n\n[fact]\nOne.\n\n[fact: ghost]\nTwo.\n\n[estimate: thin]\nThree.\n")
    sources = {"thin": S.Source(key="thin", cite="Thin (2020)", title="Thin", url="https://example.org")}
    errors, _ = S.problems(s, sources)
    text = "\n".join(errors)
    assert "a.1 [fact] has no source" in text
    assert "cites 'ghost'" in text
    assert "source thin: needs a quote" in text


def test_an_opinion_with_sources_is_a_warning_not_an_error():
    s = S.parse("# T\n\n## a\n\n[opinion: book]\nI think so.\n")
    sources = {"book": S.Source(key="book", cite="B", title="B", where="p. 1", quote=("x",))}
    errors, warnings = S.problems(s, sources)
    assert errors == [] and any("split" in w for w in warnings)
