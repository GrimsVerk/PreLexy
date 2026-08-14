from pathlib import Path

from click.testing import CliRunner

from prelexy.clean import clean_text, strip_subtitles
from prelexy.cli import cli

SRT_SAMPLE = """\
1
00:00:01,000 --> 00:00:04,000
Hallo, welkom bij de podcast.

2
00:00:04,500 --> 00:00:07,000
Vandaag praten we
over fietsen.
"""

VTT_SAMPLE = """\
WEBVTT

NOTE
this comment block disappears

00:00.000 --> 00:04.000
Hallo, <i>welkom</i> bij de podcast.

00:04.500 --> 00:07.000
Vandaag praten we over fietsen.
"""


def test_strip_subtitles_srt() -> None:
    text = strip_subtitles(SRT_SAMPLE)
    assert text == "Hallo, welkom bij de podcast. Vandaag praten we over fietsen."


def test_strip_subtitles_vtt_drops_header_notes_and_tags() -> None:
    text = strip_subtitles(VTT_SAMPLE)
    assert text == "Hallo, welkom bij de podcast. Vandaag praten we over fietsen."
    assert "NOTE" not in text and "<i>" not in text


def test_strip_subtitles_reparagraphs_long_streams_at_sentence_ends() -> None:
    cue = "00:00.000 --> 00:01.000\nDit is een zin die eindigt.\n\n"
    text = strip_subtitles("WEBVTT\n\n" + cue * 120)
    paragraphs = text.split("\n\n")
    assert len(paragraphs) > 1
    assert all(p.endswith(".") for p in paragraphs)  # no mid-sentence cuts


def test_pipe_becomes_I() -> None:
    cleaned, counts = clean_text("“| dare say,” he said. | am what | am.")
    assert cleaned == "“I dare say,” he said. I am what I am."
    assert counts["pipe-as-I"] == 3


def test_pipe_inside_a_word_is_left_alone() -> None:
    cleaned, _ = clean_text("the a|b notation stays")
    assert "a|b" in cleaned


def test_broken_hyphenation_is_rejoined() -> None:
    cleaned, counts = clean_text("a moss- coloured velvet jerkin, cross- gartered hose")
    assert "moss-coloured" in cleaned
    assert "cross-gartered" in cleaned
    assert counts["broken-hyphen"] == 2


def test_hyphenation_across_line_breaks_is_rejoined() -> None:
    cleaned, _ = clean_text("the long tussore-\nsilk curtains")
    assert "tussore-silk curtains" in cleaned
    # the Dorian Gray scan's actual pattern: hyphen, trailing space, newline
    cleaned, _ = clean_text("She wore a moss- \ncoloured velvet jerkin")
    assert "moss-coloured velvet" in cleaned
    # but a hyphen before a paragraph break is left alone
    untouched = "ended with a dash-\n\nA new paragraph."
    assert clean_text(untouched)[0] == untouched


def test_letterless_lines_are_dropped() -> None:
    cleaned, counts = clean_text("A real line.\n= \n42\n* * *\nAnother real line.")
    assert cleaned == "A real line.\nAnother real line."
    assert counts["letterless-line"] == 3


def test_blank_runs_collapse_but_paragraphs_survive() -> None:
    cleaned, _ = clean_text("Paragraph one.\n\n\n\n\nParagraph two.\n\nParagraph three.")
    assert cleaned == "Paragraph one.\n\nParagraph two.\n\nParagraph three."


def test_clean_text_is_idempotent() -> None:
    dirty = "“| say,” he said- ly.\n===\n\n\n\nEnd- ing."
    once, _ = clean_text(dirty)
    twice, counts = clean_text(once)
    assert once == twice
    assert not any(counts.values())


def test_clean_command_writes_output_and_summary(tmp_path: Path) -> None:
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
