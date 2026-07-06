import pytest

from prelexy.config import DEFAULTS, config_path, load_config


def test_first_use_writes_commented_default_file(tmp_path):
    path = tmp_path / "config.toml"
    config = load_config(path)
    assert config == DEFAULTS
    text = path.read_text()
    assert text.startswith("#")
    assert "session_length = 10" in text
    # the generated file round-trips to the same defaults
    assert load_config(path) == DEFAULTS


def test_file_values_override_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("session_length = 25\nnew_ratio = 0.5\n")
    config = load_config(path)
    assert config["session_length"] == 25
    assert config["new_ratio"] == 0.5


def test_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("volume = 11\n")
    assert load_config(path) == DEFAULTS


@pytest.mark.parametrize(
    "body",
    [
        "session_length = 0",
        "session_length = 2.5",
        "new_ratio = 1.5",
        "new_ratio = -0.1",
        'new_ratio = "high"',
    ],
)
def test_invalid_values_are_rejected(tmp_path, body):
    path = tmp_path / "config.toml"
    path.write_text(body)
    with pytest.raises(ValueError):
        load_config(path)


def test_config_path_respects_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_path() == tmp_path / "prelexy" / "config.toml"
