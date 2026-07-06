from click.testing import CliRunner

from prelexy.cli import cli
from prelexy.textproc import Candidate


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


def test_words_on_empty_db_explains_ingest(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["words", "--db", str(tmp_path / "empty.db")])
    assert result.exit_code != 0
    assert "ingest" in result.output


def test_question_command_previews_mcq(tmp_path, monkeypatch):
    from prelexy.store import Store

    monkeypatch.setattr(
        "prelexy.textproc.load_nlp", lambda language="en": (_ for _ in ()).throw(OSError)
    )
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
