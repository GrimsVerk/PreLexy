from click.testing import CliRunner

from prelexy.cli import cli
from prelexy.store import Store
from prelexy.textproc import Candidate


def isolate_play(monkeypatch, tmp_path):
    """Point the config at a temp dir and skip the spaCy model load."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(
        "prelexy.textproc.load_nlp",
        lambda language="en": (_ for _ in ()).throw(OSError("no model")),
    )


def fake_extract(text, language="en", nlp=None):
    return [
        Candidate(
            form="perambulate",
            lemma="perambulate",
            pos="VERB",
            zipf=1.8,
            occurrences=[("He perambulated.", 3)],
        ),
        Candidate(
            form="run",
            lemma="run",
            pos="VERB",
            zipf=5.9,
            occurrences=[("I run.", 2), ("He ran.", 20)],
        ),
    ]


def test_ingest_then_words_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("prelexy.cli.extract_candidates", fake_extract)
    db = tmp_path / "db.sqlite"
    book = tmp_path / "book.txt"
    book.write_text("some text")
    runner = CliRunner()

    result = runner.invoke(cli, ["ingest", str(book), "--db", str(db)])
    assert result.exit_code == 0, result.output
    assert "Stored 2 items (3 occurrences)" in result.output
    assert "perambulate" in result.output

    result = runner.invoke(cli, ["ingest", str(book), "--db", str(db)])
    assert result.exit_code != 0
    assert "already ingested" in result.output

    result = runner.invoke(cli, ["words", "--db", str(db)])
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0].startswith("form")
    assert lines[1].startswith("perambulate")  # rarest first
    assert lines[2].startswith("run")


def test_say_command_reports_missing_engine(monkeypatch):
    monkeypatch.setattr("prelexy.speech.pronounce", lambda word, language="en": False)
    result = CliRunner().invoke(cli, ["say", "vermilion"])
    assert result.exit_code != 0
    assert "No speech engine found" in result.output

    monkeypatch.setattr("prelexy.speech.pronounce", lambda word, language="en": True)
    assert CliRunner().invoke(cli, ["say", "vermilion"]).exit_code == 0


def test_words_on_empty_db_explains_ingest(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["words", "--db", str(tmp_path / "empty.db")])
    assert result.exit_code != 0
    assert "ingest" in result.output


def test_play_prompts_to_create_first_profile(tmp_path, monkeypatch):
    isolate_play(monkeypatch, tmp_path)
    db = tmp_path / "db.sqlite"
    runner = CliRunner()
    result = runner.invoke(cli, ["play", "--db", str(db)], input="alice\n")
    assert result.exit_code == 0, result.output
    assert "No profiles yet" in result.output
    assert "Nothing to practice" in result.output
    with Store(db) as store:
        assert [row["name"] for row in store.list_profiles()] == ["alice"]


def test_play_menu_picks_existing_profile_without_creating_one(tmp_path, monkeypatch):
    isolate_play(monkeypatch, tmp_path)
    db = tmp_path / "db.sqlite"
    with Store(db) as store:
        store.get_or_create_profile("alice")
        store.get_or_create_profile("bob")
    runner = CliRunner()
    result = runner.invoke(cli, ["play", "--db", str(db)], input="2\n")
    assert result.exit_code == 0, result.output
    assert "Who is playing?" in result.output
    with Store(db) as store:
        assert len(store.list_profiles()) == 2


def test_play_menu_rejects_bad_input_then_creates_new_profile(tmp_path, monkeypatch):
    isolate_play(monkeypatch, tmp_path)
    db = tmp_path / "db.sqlite"
    with Store(db) as store:
        store.get_or_create_profile("alice")
    runner = CliRunner()
    result = runner.invoke(cli, ["play", "--db", str(db)], input="7\nn\ncarol\n")
    assert result.exit_code == 0, result.output
    assert "Pick 1–1" in result.output
    with Store(db) as store:
        assert [row["name"] for row in store.list_profiles()] == ["alice", "carol"]


def test_play_profile_flag_bypasses_menu(tmp_path, monkeypatch):
    isolate_play(monkeypatch, tmp_path)
    db = tmp_path / "db.sqlite"
    runner = CliRunner()
    result = runner.invoke(cli, ["play", "--db", str(db), "--profile", "dave"])
    assert result.exit_code == 0, result.output
    assert "Who is playing?" not in result.output
    with Store(db) as store:
        assert [row["name"] for row in store.list_profiles()] == ["dave"]


def test_question_command_previews_mcq(tmp_path, monkeypatch):
    isolate_play(monkeypatch, tmp_path)  # question now reads the config too
    db = tmp_path / "db.sqlite"
    with Store(db) as store:
        source = store.add_source("t", "en", "book", None)
        target = store.get_or_create_item(
            "en", "sagacious", lemma="sagacious", pos="ADJ", metadata={"zipf": 2.5}
        )
        store.add_sense(target, "having keen judgement", "en", "wordnet")
        store.add_occurrences(target, source, [("A sagacious old man.", 2)])
        gaunt = store.get_or_create_item(
            "en", "gaunt", lemma="gaunt", pos="ADJ", metadata={"zipf": 2.6}
        )
        store.add_sense(gaunt, "very thin", "en", "wordnet")

    runner = CliRunner()
    result = runner.invoke(cli, ["question", "sagacious", "--db", str(db)])
    assert result.exit_code == 0, result.output
    assert "What does “sagacious” mean?" in result.output
    assert "A sagacious old man." in result.output
    assert "having keen judgement" in result.output
    assert " 4. " in result.output  # full set of options from the WordNet pool
    assert "*" in result.output

    result = runner.invoke(cli, ["question", "nonexistent", "--db", str(db)])
    assert result.exit_code != 0
    assert "not stored" in result.output
