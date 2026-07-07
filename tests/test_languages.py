import pytest
from click.testing import CliRunner

from prelexy.cli import cli
from prelexy.languages import LANGUAGES, UnsupportedLanguageError, get_language
from prelexy.textproc import in_dictionary


def test_registry_covers_english_and_dutch():
    en = get_language("en")
    assert en.spacy_models[0] == "en_core_web_md"
    assert en.wordnet_lang == "eng"
    nl = get_language("nl")
    assert nl.spacy_models[0] == "nl_core_news_md"
    assert nl.wordnet_lang == "nld"
    assert nl.espeak_voice == "nl"


def test_unsupported_language_error_says_what_and_where():
    with pytest.raises(UnsupportedLanguageError) as excinfo:
        get_language("xx")
    message = str(excinfo.value)
    assert "'xx'" in message
    for code in LANGUAGES:
        assert code in message
    assert "Deferred" in message


def test_cli_rejects_unsupported_language(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    result = CliRunner().invoke(cli, ["words", "--language", "xx", "--db", str(tmp_path / "d.db")])
    assert result.exit_code != 0
    assert "not supported yet" in result.output


def test_dutch_membership_gate_uses_wordfreq():
    assert in_dictionary("fiets", "nl")
    assert in_dictionary("huis", "nl")
    assert not in_dictionary("xqzt", "nl")
