"""Tests for the text manipulation helpers exposed to QML."""

from __future__ import annotations

import re

import pytest

from cipherpad.textops import TextOps


@pytest.fixture()
def ops(qt_app) -> TextOps:  # noqa: ANN001
    return TextOps()


def apply(span: dict, text: str) -> str:
    """Apply an edit span the same way EditorPane.applySpan does."""
    if not span.get("changed", False):
        return text
    return text[: span["start"]] + span["text"] + text[span["end"] :]


SAMPLE = "beta\nalpha\ngamma\n"


def test_case_conversions(ops: TextOps) -> None:
    text = "hello world"
    assert apply(ops.upperCase(text, 0, len(text)), text) == "HELLO WORLD"
    assert apply(ops.lowerCase("HELLO", 0, 5), "HELLO") == "hello"
    assert apply(ops.titleCase(text, 0, len(text)), text) == "Hello World"
    assert apply(ops.toggleCase("aBc", 0, 3), "aBc") == "AbC"


def test_case_conversion_respects_selection(ops: TextOps) -> None:
    text = "hello world"
    assert apply(ops.upperCase(text, 0, 5), text) == "HELLO world"


def test_sort_lines(ops: TextOps) -> None:
    assert apply(ops.sortLines(SAMPLE, 0, len(SAMPLE), False, False), SAMPLE) == "alpha\nbeta\ngamma\n"
    assert apply(ops.sortLines(SAMPLE, 0, len(SAMPLE), True, False), SAMPLE) == "gamma\nbeta\nalpha\n"


def test_sort_lines_unique(ops: TextOps) -> None:
    text = "b\na\nb\n"
    assert apply(ops.sortLines(text, 0, len(text), False, True), text) == "a\nb\n"


def test_unique_and_reverse(ops: TextOps) -> None:
    text = "a\nb\na\n"
    assert apply(ops.uniqueLines(text, 0, len(text)), text) == "a\nb\n"
    assert apply(ops.reverseLines(SAMPLE, 0, len(SAMPLE)), SAMPLE) == "gamma\nalpha\nbeta\n"


def test_trim_trailing_whitespace(ops: TextOps) -> None:
    text = "a   \nb\t\nc\n"
    assert apply(ops.trimTrailingWhitespace(text, 0, len(text)), text) == "a\nb\nc\n"


def test_trim_reports_unchanged_when_clean(ops: TextOps) -> None:
    text = "a\nb\n"
    assert ops.trimTrailingWhitespace(text, 0, len(text)).get("changed") is False


def test_duplicate_and_delete_lines(ops: TextOps) -> None:
    text = "one\ntwo\n"
    assert apply(ops.duplicateLines(text, 0, 3), text) == "one\none\ntwo\n"
    assert apply(ops.deleteLines(text, 0, 3), text) == "two\n"


def test_move_lines(ops: TextOps) -> None:
    text = "one\ntwo\nthree\n"
    assert apply(ops.moveLinesDown(text, 0, 3), text) == "two\none\nthree\n"
    assert apply(ops.moveLinesUp(text, 4, 7), text) == "two\none\nthree\n"


def test_move_lines_at_boundaries_is_noop(ops: TextOps) -> None:
    text = "one\ntwo\n"
    assert ops.moveLinesUp(text, 0, 3).get("changed") is False


def test_join_lines(ops: TextOps) -> None:
    text = "one\ntwo\nthree\n"
    assert apply(ops.joinLines(text, 0, 8), text) == "one two\nthree\n"


def test_indent_and_unindent_with_spaces(ops: TextOps) -> None:
    text = "a\nb\n"
    indented = apply(ops.indent(text, 0, 3, 4, True), text)
    assert indented == "    a\n    b\n"
    assert apply(ops.unindent(indented, 0, 11, 4), indented) == "a\nb\n"


def test_indent_with_tabs(ops: TextOps) -> None:
    text = "a\n"
    assert apply(ops.indent(text, 0, 1, 4, False), text) == "\ta\n"


def test_convert_indentation(ops: TextOps) -> None:
    tabs = "\ta\n"
    spaces = apply(ops.convertIndentation(tabs, 0, len(tabs), 4, True), tabs)
    assert spaces == "    a\n"
    assert apply(ops.convertIndentation(spaces, 0, len(spaces), 4, False), spaces) == "\ta\n"


@pytest.mark.parametrize(
    ("language", "expected"),
    [("python", "# a\n"), ("javascript", "// a\n"), ("html", "<!-- a -->\n")],
)
def test_toggle_comment_adds_marker(ops: TextOps, language: str, expected: str) -> None:
    text = "a\n"
    assert apply(ops.toggleComment(text, 0, 1, language), text) == expected


def test_toggle_comment_is_reversible(ops: TextOps) -> None:
    text = "a\nb\n"
    commented = apply(ops.toggleComment(text, 0, 3, "python"), text)
    assert commented == "# a\n# b\n"
    assert apply(ops.toggleComment(commented, 0, 7, "python"), commented) == text


def test_toggle_comment_language_lookup_is_tolerant(ops: TextOps) -> None:
    text = "a\n"
    assert apply(ops.toggleComment(text, 0, 1, "Python"), text) == "# a\n"
    assert apply(ops.toggleComment(text, 0, 1, "PYTHON"), text) == "# a\n"


def test_toggle_comment_unknown_language_is_noop(ops: TextOps) -> None:
    assert ops.toggleComment("a\n", 0, 1, "not-a-language").get("changed") is False


def test_indent_for_newline(ops: TextOps) -> None:
    text = "    value = 1"
    assert ops.indentForNewline(text, len(text), 4, True) == "    "


def test_indent_for_newline_after_open_block(ops: TextOps) -> None:
    text = "def f():"
    assert len(ops.indentForNewline(text, len(text), 4, True)) >= 4


def test_bracket_helpers(ops: TextOps) -> None:
    assert ops.closingBracket("(") == ")"
    assert ops.closingBracket("[") == "]"
    assert ops.closingBracket("a") == ""
    assert ops.isClosingBracket(")")
    assert not ops.isClosingBracket("(")


def test_tab_filler_aligns_to_stop(ops: TextOps) -> None:
    assert ops.tabFiller(0, 4) == "    "
    assert ops.tabFiller(2, 4) == "  "
    assert ops.tabFiller(4, 4) == "    "


def test_indent_string(ops: TextOps) -> None:
    assert ops.indentString(2) == "  "


def test_timestamp(ops: TextOps) -> None:
    assert ops.timestamp("")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", ops.timestamp("date"))
    assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", ops.timestamp("time"))
    assert "T" in ops.timestamp("iso")


def test_statistics(ops: TextOps) -> None:
    stats = ops.statistics("one two\nthree\n\nfour\n", "")
    assert stats["words"] == 4
    assert stats["characters"] == 20
    assert stats["charactersNoSpaces"] == 15
    assert stats["lines"] == 5
    assert stats["paragraphs"] == 2
    assert stats["isSelection"] is False


def test_statistics_for_selection(ops: TextOps) -> None:
    stats = ops.statistics("one two", "one")
    assert stats["isSelection"] is True
    assert stats["words"] == 1


def test_statistics_of_empty_text(ops: TextOps) -> None:
    stats = ops.statistics("", "")
    assert stats["words"] == 0
    assert stats["characters"] == 0
