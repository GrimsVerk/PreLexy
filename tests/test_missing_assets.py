"""First-run friendliness: a missing model or data file gives one clear message."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from prelexy import cli as cli_module
from prelexy.textproc import MissingAssetError, load_nlp


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))


def _no_models(monkeypatch: pytest.MonkeyPatch) -> None:
    import spacy

    def fail(name: str, **kwargs: object) -> None:
        raise OSError(f"[E050] Can't find model {name!r}")

    monkeypatch.setattr(spacy, "load", fail)


def test_load_nlp_names_the_exact_download_command(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_models(monkeypatch)
    with pytest.raises(MissingAssetError) as info:
        load_nlp("nl")
    message = str(info.value)
    assert "python -m spacy download nl_core_news_md" in message
    assert "uv" in message


def test_ingest_reports_missing_model_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_models(monkeypatch)
    text = tmp_path / "book.txt"
    text.write_text("A perambulating gentleman.")
    result = CliRunner().invoke(
        cli_module.cli, ["ingest", str(text), "--db", str(tmp_path / "t.db")]
    )
    assert result.exit_code != 0
    assert "python -m spacy download en_core_web_md" in result.output
    assert "Traceback" not in result.output


def test_main_prints_message_for_missing_asset(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom() -> None:
        raise MissingAssetError("Install it with:  python -m nltk.downloader wordnet")

    monkeypatch.setattr(cli_module, "cli", boom)
    with pytest.raises(SystemExit) as info:
        cli_module.main()
    assert info.value.code == 1
    assert "python -m nltk.downloader wordnet" in capsys.readouterr().err


def test_play_warns_once_and_continues_without_the_english_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_models(monkeypatch)
    result = CliRunner().invoke(
        cli_module.cli,
        ["play", "--profile", "p", "--db", str(tmp_path / "t.db")],
    )
    assert "python -m spacy download en_core_web_md" in result.output
    assert "Traceback" not in result.output
    assert result.output.count("Warning:") == 1
