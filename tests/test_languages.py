from pathlib import Path

import pytest
from click.testing import CliRunner

from prelexy.cli import cli
from prelexy.languages import LANGUAGES, UnsupportedLanguageError, get_language
from prelexy.textproc import in_dictionary


def test_registry_covers_english_and_dutch() -> None:
    en = get_language("en")
    assert en.spacy_models[0] == "en_core_web_md"
    assert en.wordnet_lang == "eng"
    nl = get_language("nl")
    assert nl.spacy_models[0] == "nl_core_news_md"
    assert nl.wordnet_lang == "nld"
    assert nl.espeak_voice == "nl"


def test_unsupported_language_error_says_what_and_where() -> None:
    with pytest.raises(UnsupportedLanguageError) as excinfo:
        get_language("xx")
    message = str(excinfo.value)
    assert "'xx'" in message
    for code in LANGUAGES:
        assert code in message
    assert "Deferred" in message


def test_cli_rejects_unsupported_language(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    result = CliRunner().invoke(cli, ["words", "--language", "xx", "--db", str(tmp_path / "d.db")])
    assert result.exit_code != 0
    assert "not supported yet" in result.output


def test_python_is_a_registered_code_language() -> None:
    from prelexy.languages import code_language_codes

    python = get_language("python")
    assert python.kind == "code"
    assert python.spacy_models == ()
    assert "python" in code_language_codes()


def test_code_languages_bypass_the_natural_stack() -> None:
    from prelexy.definitions import synonym_conflict, wordnet_lemma_names, wordnet_sense
    from prelexy.textproc import load_nlp

    assert wordnet_sense("pop", "method", "python") is None
    assert wordnet_lemma_names("method", "python") == ()
    assert not synonym_conflict("pop", "append", "method", language="python")
    assert in_dictionary("list.pop", "python")
    with pytest.raises(ValueError, match="ingest-docs"):
        load_nlp("python")


def test_dutch_membership_gate_uses_wordfreq() -> None:
    assert in_dictionary("fiets", "nl")
    assert in_dictionary("huis", "nl")
    assert not in_dictionary("xqzt", "nl")
