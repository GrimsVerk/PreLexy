import pytest
from click.testing import CliRunner

from prelexy.cli import cli
from prelexy.store import Store
from prelexy.textproc import Candidate


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Every CLI test gets its own config dir (commands read the config now)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))


def write_config(tmp_path, body):
    path = tmp_path / "xdg" / "prelexy" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def isolate_play(monkeypatch, tmp_path):
    """Skip the spaCy model load (no model in the sandbox)."""
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
    monkeypatch.setattr(
        "prelexy.speech.pronounce", lambda word, language="en", voice=None: False
    )
    result = CliRunner().invoke(cli, ["say", "vermilion"])
    assert result.exit_code != 0
    assert "No speech engine found" in result.output

    monkeypatch.setattr(
        "prelexy.speech.pronounce", lambda word, language="en", voice=None: True
    )
    assert CliRunner().invoke(cli, ["say", "vermilion"]).exit_code == 0


def test_words_on_empty_db_explains_ingest(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["words", "--db", str(tmp_path / "empty.db")])
    assert result.exit_code != 0
    assert "ingest" in result.output


def test_ingest_converts_subtitle_files(tmp_path, monkeypatch):
    received = {}

    def capturing_extract(text, language="en", nlp=None):
        received["text"] = text
        return fake_extract(text, language, nlp)

    monkeypatch.setattr("prelexy.cli.extract_candidates", capturing_extract)
    db = tmp_path / "db.sqlite"
    episode = tmp_path / "episode.srt"
    episode.write_text(
        "1\n00:00:01,000 --> 00:00:04,000\nHallo, welkom bij de podcast.\n"
    )
    result = CliRunner().invoke(cli, ["ingest", str(episode), "--db", str(db)])
    assert result.exit_code == 0, result.output
    assert "-->" not in received["text"]
    assert "Hallo, welkom" in received["text"]
    with Store(db) as store:
        source = store.find_source_by_path(str(episode.resolve()))
        assert source["kind"] == "subtitles"


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


def test_play_uses_default_profile_from_config(tmp_path, monkeypatch):
    isolate_play(monkeypatch, tmp_path)
    write_config(tmp_path, 'default_profile = "erika"\n')
    db = tmp_path / "db.sqlite"
    result = CliRunner().invoke(cli, ["play", "--db", str(db)])
    assert result.exit_code == 0, result.output
    assert "Who is playing?" not in result.output
    with Store(db) as store:
        assert [row["name"] for row in store.list_profiles()] == ["erika"]


def test_play_remembers_the_profiles_language(tmp_path, monkeypatch):
    isolate_play(monkeypatch, tmp_path)
    db = tmp_path / "db.sqlite"
    with Store(db) as store:
        en_item = store.get_or_create_item(
            "en", "sagacious", lemma="sagacious", pos="ADJ", metadata={"zipf": 2.0}
        )
        store.add_sense(en_item, "having keen judgement", "en", "wordnet")
        nl_item = store.get_or_create_item(
            "nl", "fiets", lemma="fiets", pos="NOUN", metadata={"zipf": 4.0}
        )
        store.add_sense(nl_item, "a two-wheeled vehicle", "en", "wordnet")
    runner = CliRunner()

    # first session names the language explicitly
    result = runner.invoke(
        cli, ["play", "--db", str(db), "--profile", "anna", "--language", "nl"],
        input="q\n",
    )
    assert result.exit_code == 0, result.output
    assert "fiets" in result.output

    # the next session inherits it without any flag
    result = runner.invoke(
        cli, ["play", "--db", str(db), "--profile", "anna"], input="q\n"
    )
    assert result.exit_code == 0, result.output
    assert "fiets" in result.output
    assert "sagacious" not in result.output

    # a different profile still gets the config default (en)
    result = runner.invoke(
        cli, ["play", "--db", str(db), "--profile", "bert"], input="q\n"
    )
    assert result.exit_code == 0, result.output
    assert "sagacious" in result.output


def test_default_language_and_db_path_come_from_config(tmp_path, monkeypatch):
    config_db = tmp_path / "from-config.db"
    write_config(
        tmp_path,
        f'default_language = "nl"\ndb_path = "{config_db}"\n',
    )
    monkeypatch.setattr("prelexy.cli.extract_candidates", fake_extract)
    book = tmp_path / "book.txt"
    book.write_text("iets")
    result = CliRunner().invoke(cli, ["ingest", str(book)])
    assert result.exit_code == 0, result.output
    assert config_db.exists()  # config db_path honored without --db
    with Store(config_db) as store:
        assert store.find_item("nl", "perambulate") is not None  # config language

    # the --db flag still wins over the config value
    flag_db = tmp_path / "flag.db"
    result = CliRunner().invoke(cli, ["words", "--db", str(flag_db)])
    assert "No 'nl' items" in result.output  # language default still from config


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
