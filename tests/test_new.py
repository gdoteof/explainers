import pytest

from explainers import new


def start(tmp_path, monkeypatch, name):
    template = tmp_path / "_template"
    template.mkdir(exist_ok=True)
    for f in ("script.md", "sources.toml", "video.py"):
        (template / f).write_text(f"template {f}")
    monkeypatch.setattr(new, "VIDEOS", tmp_path)
    monkeypatch.setattr("sys.argv", ["new", name])
    new.main()
    return tmp_path / name


def test_new_copies_the_template(tmp_path, monkeypatch):
    dst = start(tmp_path, monkeypatch, "fresh")
    assert sorted(p.name for p in dst.iterdir()) == ["script.md", "sources.toml", "video.py"]


def test_new_keeps_research_that_is_already_there(tmp_path, monkeypatch):
    (tmp_path / "parked").mkdir()
    (tmp_path / "parked" / "sources.toml").write_text("read so far")
    dst = start(tmp_path, monkeypatch, "parked")
    assert (dst / "sources.toml").read_text() == "read so far"
    assert (dst / "script.md").read_text() == "template script.md"


def test_new_leaves_a_script_alone(tmp_path, monkeypatch):
    start(tmp_path, monkeypatch, "written")
    with pytest.raises(SystemExit):
        start(tmp_path, monkeypatch, "written")
