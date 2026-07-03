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
