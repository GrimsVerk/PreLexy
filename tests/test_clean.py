from click.testing import CliRunner

from prelexy.clean import clean_text
from prelexy.cli import cli


def test_pipe_becomes_I():
    cleaned, counts = clean_text("“| dare say,” he said. | am what | am.")
    assert cleaned == "“I dare say,” he said. I am what I am."
    assert counts["pipe-as-I"] == 3


def test_pipe_inside_a_word_is_left_alone():
    cleaned, _ = clean_text("the a|b notation stays")
    assert "a|b" in cleaned


def test_broken_hyphenation_is_rejoined():
    cleaned, counts = clean_text("a moss- coloured velvet jerkin, cross- gartered hose")
    assert "moss-coloured" in cleaned
    assert "cross-gartered" in cleaned
    assert counts["broken-hyphen"] == 2


def test_hyphenation_across_line_breaks_is_rejoined():
    cleaned, _ = clean_text("the long tussore-\nsilk curtains")
    assert "tussore-silk curtains" in cleaned
    # the Dorian Gray scan's actual pattern: hyphen, trailing space, newline
    cleaned, _ = clean_text("She wore a moss- \ncoloured velvet jerkin")
    assert "moss-coloured velvet" in cleaned
    # but a hyphen before a paragraph break is left alone
    untouched = "ended with a dash-\n\nA new paragraph."
    assert clean_text(untouched)[0] == untouched


def test_letterless_lines_are_dropped():
    cleaned, counts = clean_text("A real line.\n= \n42\n* * *\nAnother real line.")
    assert cleaned == "A real line.\nAnother real line."
    assert counts["letterless-line"] == 3


def test_blank_runs_collapse_but_paragraphs_survive():
    cleaned, _ = clean_text("Paragraph one.\n\n\n\n\nParagraph two.\n\nParagraph three.")
    assert cleaned == "Paragraph one.\n\nParagraph two.\n\nParagraph three."


def test_clean_text_is_idempotent():
    dirty = "“| say,” he said- ly.\n===\n\n\n\nEnd- ing."
    once, _ = clean_text(dirty)
    twice, counts = clean_text(once)
    assert once == twice
    assert not any(counts.values())


def test_clean_command_writes_output_and_summary(tmp_path):
    source = tmp_path / "book.txt"
    source.write_text("| am here.\n= \nmoss- coloured.")
    result = CliRunner().invoke(cli, ["clean", str(source)])
    assert result.exit_code == 0, result.output
    output = tmp_path / "book.cleaned.txt"
    assert output.read_text() == "I am here.\nmoss-coloured."
    assert "pipe-as-I: 1" in result.output
    assert "letterless-line: 1" in result.output

    explicit = tmp_path / "elsewhere.txt"
    result = CliRunner().invoke(cli, ["clean", str(source), "-o", str(explicit)])
    assert result.exit_code == 0
    assert explicit.exists()
