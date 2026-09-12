"""Tests for the stateless search engine exposed to QML."""

from __future__ import annotations

import pytest

from cipherpad.search import SearchEngine


@pytest.fixture()
def engine(qt_app) -> SearchEngine:  # noqa: ANN001
    return SearchEngine()


def find_next(engine: SearchEngine, text: str, needle: str, start: int = 0, **flags) -> list[int]:
    return engine.findNext(
        text,
        needle,
        start,
        flags.get("cs", False),
        flags.get("ww", False),
        flags.get("rx", False),
        flags.get("wrap", True),
    )


def find_previous(engine: SearchEngine, text: str, needle: str, start: int, **flags) -> list[int]:
    return engine.findPrevious(
        text,
        needle,
        start,
        flags.get("cs", False),
        flags.get("ww", False),
        flags.get("rx", False),
        flags.get("wrap", True),
    )


# ----------------------------------------------------------------- validation
def test_empty_needle_is_valid(engine: SearchEngine) -> None:
    assert engine.isValid("", "", False, False, False)


def test_plain_text_is_always_valid(engine: SearchEngine) -> None:
    assert engine.isValid("a(b", "", False, False, False)


def test_broken_regex_is_invalid(engine: SearchEngine) -> None:
    assert not engine.isValid("a(b", "", False, False, True)


def test_valid_regex_is_valid(engine: SearchEngine) -> None:
    assert engine.isValid(r"\d+", "", False, False, True)


# --------------------------------------------------------------- forward find
def test_find_next_returns_span(engine: SearchEngine) -> None:
    assert find_next(engine, "hello world", "world") == [6, 11]


def test_find_next_missing_returns_empty(engine: SearchEngine) -> None:
    assert find_next(engine, "hello", "zzz") == []


def test_find_next_is_case_insensitive_by_default(engine: SearchEngine) -> None:
    assert find_next(engine, "Hello", "hello") == [0, 5]


def test_find_next_case_sensitive(engine: SearchEngine) -> None:
    assert find_next(engine, "Hello", "hello", cs=True) == []
    assert find_next(engine, "Hello", "Hello", cs=True) == [0, 5]


def test_find_next_whole_word(engine: SearchEngine) -> None:
    assert find_next(engine, "category cat", "cat", ww=True) == [9, 12]
    assert find_next(engine, "category", "cat", ww=True) == []


def test_find_next_regex(engine: SearchEngine) -> None:
    assert find_next(engine, "abc 123", r"\d+", rx=True) == [4, 7]


def test_find_next_invalid_regex_returns_empty(engine: SearchEngine) -> None:
    assert find_next(engine, "abc", "a(", rx=True) == []


def test_find_next_starts_after_position(engine: SearchEngine) -> None:
    assert find_next(engine, "aa", "a", start=1) == [1, 2]


def test_find_next_wraps(engine: SearchEngine) -> None:
    assert find_next(engine, "abc abc", "abc", start=5) == [0, 3]


def test_find_next_without_wrap_stops_at_end(engine: SearchEngine) -> None:
    assert find_next(engine, "abc abc", "abc", start=5, wrap=False) == []


def test_find_next_empty_needle(engine: SearchEngine) -> None:
    assert find_next(engine, "abc", "") == []


# -------------------------------------------------------------- backward find
def test_find_previous_returns_span(engine: SearchEngine) -> None:
    assert find_previous(engine, "abc abc", "abc", 7) == [4, 7]


def test_find_previous_before_position(engine: SearchEngine) -> None:
    assert find_previous(engine, "abc abc", "abc", 4) == [0, 3]


def test_find_previous_wraps(engine: SearchEngine) -> None:
    assert find_previous(engine, "abc abc", "abc", 0) == [4, 7]


def test_find_previous_without_wrap(engine: SearchEngine) -> None:
    assert find_previous(engine, "abc abc", "abc", 0, wrap=False) == []


# -------------------------------------------------------------------- counting
def test_match_count(engine: SearchEngine) -> None:
    assert engine.matchCount("a a a", "a", False, False, False) == 3


def test_match_count_no_matches(engine: SearchEngine) -> None:
    assert engine.matchCount("abc", "z", False, False, False) == 0


def test_match_count_invalid_regex(engine: SearchEngine) -> None:
    assert engine.matchCount("abc", "a(", False, False, True) == 0


def test_match_count_regex(engine: SearchEngine) -> None:
    assert engine.matchCount("a1 b22 c333", r"\d+", False, False, True) == 3


def test_match_ordinal_is_one_based(engine: SearchEngine) -> None:
    text = "a a a"
    assert engine.matchOrdinal(text, "a", 0, False, False, False) == 1
    assert engine.matchOrdinal(text, "a", 2, False, False, False) == 2
    assert engine.matchOrdinal(text, "a", 4, False, False, False) == 3


def test_match_ordinal_off_match_is_zero(engine: SearchEngine) -> None:
    assert engine.matchOrdinal("a a", "a", 1, False, False, False) == 0


# ----------------------------------------------------------------- replacement
def test_replacement_spans_are_reversed(engine: SearchEngine) -> None:
    spans = engine.replacementSpans("a a a", "a", "b", False, False, False)
    assert [span["start"] for span in spans] == [4, 2, 0]
    assert all(span["text"] == "b" for span in spans)


def test_replacement_spans_apply_cleanly(engine: SearchEngine) -> None:
    text = "one two one"
    for span in engine.replacementSpans(text, "one", "1", False, False, False):
        text = text[: span["start"]] + span["text"] + text[span["end"] :]
    assert text == "1 two 1"


def test_replacement_spans_expand_groups(engine: SearchEngine) -> None:
    text = "key=value"
    spans = engine.replacementSpans(text, r"(\w+)=(\w+)", r"\2=\1", False, False, True)
    assert spans[0]["text"] == "value=key"


def test_replacement_spans_invalid_regex(engine: SearchEngine) -> None:
    assert engine.replacementSpans("abc", "a(", "x", False, False, True) == []


def test_replace_current_matches_selection(engine: SearchEngine) -> None:
    result = engine.replaceCurrent("one two", "one", "1", 0, 3, False, False, False)
    assert result["matched"] is True
    assert (result["start"], result["end"], result["text"]) == (0, 3, "1")


def test_replace_current_rejects_non_match(engine: SearchEngine) -> None:
    assert engine.replaceCurrent("one two", "one", "1", 4, 7, False, False, False)["matched"] is False


def test_replace_current_rejects_partial_selection(engine: SearchEngine) -> None:
    assert engine.replaceCurrent("one two", "one", "1", 0, 2, False, False, False)["matched"] is False


def test_replace_current_expands_regex_groups(engine: SearchEngine) -> None:
    result = engine.replaceCurrent("key=value", r"(\w+)=(\w+)", r"\2=\1", 0, 9, False, False, True)
    assert result["text"] == "value=key"


def test_replace_current_with_empty_needle(engine: SearchEngine) -> None:
    assert engine.replaceCurrent("abc", "", "x", 0, 0, False, False, False)["matched"] is False


def test_replace_current_bad_group_reference(engine: SearchEngine) -> None:
    result = engine.replaceCurrent("abc", "abc", r"\9", 0, 3, False, False, True)
    assert result["matched"] is False
