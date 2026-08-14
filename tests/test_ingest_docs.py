import zlib
from pathlib import Path

import pytest
from click.testing import CliRunner

from prelexy.cli import cli
from prelexy.store import Store, item_zipf

INVENTORY = "\n".join(
    [
        "itertools.chain py:function 1 library/itertools.html#$ -",
        "itertools.count py:function 1 library/itertools.html#$ -",
        "functools.reduce py:function 1 library/functools.html#$ -",
        "os.path.join py:function 1 library/os.path.html#$ -",  # page missing
    ]
)

ITERTOOLS_HTML = """
<dl><dt id="itertools.chain">itertools.chain(*iterables)</dt>
<dd><p>Make an iterator from several iterables. More text.</p></dd></dl>
<dl><dt id="itertools.count">itertools.count(start=0)</dt>
<dd><p>Make an iterator of evenly spaced values.</p></dd></dl>
"""

FUNCTOOLS_HTML = """
<dl><dt id="functools.reduce">functools.reduce(function, iterable)</dt>
<dd><p>Apply a function of two arguments cumulatively.</p></dd></dl>
"""


def make_docs_dir(tmp_path: Path) -> Path:
    docs = tmp_path / "python-docs"
    (docs / "library").mkdir(parents=True)
    header = (
        b"# Sphinx inventory version 2\n# Project: Python\n# Version: 3.12\n"
        b"# The remainder of this file is compressed using zlib.\n"
    )
    (docs / "objects.inv").write_bytes(header + zlib.compress(INVENTORY.encode()))
    (docs / "library" / "itertools.html").write_text(ITERTOOLS_HTML)
    (docs / "library" / "functools.html").write_text(FUNCTOOLS_HTML)
    return docs


def test_ingest_docs_whole_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    docs = make_docs_dir(tmp_path)
    db = tmp_path / "db.sqlite"
    result = CliRunner().invoke(cli, ["ingest-docs", str(docs), "--db", str(db)])
    assert result.exit_code == 0, result.output
    assert "Stored 3 documented objects" in result.output
    assert "1 missing pages" in result.output

    with Store(db) as store:
        item = store.find_item("python", "itertools.chain")
        assert item is not None
        assert item["pos"] == "function"
        import json

        metadata = json.loads(item["metadata"])
        assert metadata["module"] == "itertools"
        assert metadata["signature"] == "itertools.chain(*iterables)"
        assert "order" in metadata
        (sense,) = store.senses_for(item["id"])
        assert sense["provider"] == "docs"
        assert sense["gloss"] == "Make an iterator from several iterables."
        assert store.example_for(item["id"]) == "itertools.chain(*iterables)"
        assert item_zipf(item) == 0.0  # no zipf for code items

    # re-ingesting the same tree is refused
    result = CliRunner().invoke(cli, ["ingest-docs", str(docs), "--db", str(db)])
    assert result.exit_code != 0
    assert "already ingested" in result.output


def test_ingest_docs_module_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    docs = make_docs_dir(tmp_path)
    db = tmp_path / "db.sqlite"
    result = CliRunner().invoke(
        cli, ["ingest-docs", str(docs), "--modules", "functools", "--db", str(db)]
    )
    assert result.exit_code == 0, result.output
    with Store(db) as store:
        assert store.find_item("python", "functools.reduce") is not None
        assert store.find_item("python", "itertools.chain") is None


def test_ingest_docs_rejects_natural_language_and_missing_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    docs = make_docs_dir(tmp_path)
    result = CliRunner().invoke(cli, ["ingest-docs", str(docs), "--language", "nl"])
    assert result.exit_code != 0 and "not a code language" in result.output

    empty = tmp_path / "empty"
    empty.mkdir()
    result = CliRunner().invoke(cli, ["ingest-docs", str(empty)])
    assert result.exit_code != 0 and "objects.inv" in result.output
