import pytest
from click.testing import CliRunner

from prelexy import debug
from prelexy.cli import cli


@pytest.fixture(autouse=True)
def reset_debug(monkeypatch):
    monkeypatch.delenv("PRELEXY_DEBUG", raising=False)
    debug.enable(False)
    yield
    debug.enable(False)


def test_silent_by_default(capsys):
    debug.log("mcq", "should not appear")
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_logs_to_stderr_with_channel_when_enabled(capsys):
    debug.enable()
    debug.log("mcq", "hello")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[mcq] hello" in captured.err


def test_env_var_enables(monkeypatch, capsys):
    monkeypatch.setenv("PRELEXY_DEBUG", "1")
    debug.log("scheduler", "via env")
    assert "[scheduler] via env" in capsys.readouterr().err
    monkeypatch.setenv("PRELEXY_DEBUG", "0")
    assert not debug.enabled()


def test_cli_flag_enables(tmp_path):
    result = CliRunner().invoke(cli, ["--debug", "words", "--db", str(tmp_path / "empty.db")])
    assert result.exit_code != 0  # empty db message, but the flag was parsed
    assert debug.enabled()
