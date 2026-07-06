import pytest

from prelexy.config import DEFAULTS, config_path, load_config


def test_first_use_writes_commented_default_file(tmp_path):
    path = tmp_path / "config.toml"
    config = load_config(path)
    assert config == DEFAULTS
    text = path.read_text()
    assert text.startswith("#")
    assert "new_words = 7" in text
    assert "seen_words = 3" in text
    assert "similarity_floor" in text
    # the generated file round-trips to the same defaults
    assert load_config(path) == DEFAULTS


def test_file_values_override_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        "new_words = 12\nseen_words = 8\nsimilarity_floor = 0.5\nsimilarity_ceiling = 0.9\n"
    )
    config = load_config(path)
    assert config["new_words"] == 12
    assert config["seen_words"] == 8
    assert config["similarity_floor"] == 0.5
    assert config["similarity_ceiling"] == 0.9


def test_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("volume = 11\nsession_length = 10\n")  # incl. retired keys
    assert load_config(path) == DEFAULTS


@pytest.mark.parametrize(
    "body",
    [
        "new_words = -1",
        "new_words = 2.5",
        "seen_words = -3",
        'seen_words = "many"',
        "similarity_floor = 1.5",
        "similarity_ceiling = -0.1",
        "similarity_floor = 0.9\nsimilarity_ceiling = 0.5",  # floor above ceiling
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
