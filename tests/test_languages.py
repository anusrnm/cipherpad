"""Tests for language definitions, aliases and detection."""

from __future__ import annotations

import pytest

from cipherpad.languages import (
    ALIASES,
    LANGUAGES,
    detect_language,
    get_language,
    language_names,
)


def test_plain_is_registered() -> None:
    assert "plain" in LANGUAGES
    assert get_language("plain").id == "plain"


def test_unknown_id_falls_back_to_plain() -> None:
    assert get_language("no-such-language").id == "plain"
    assert get_language("").id == "plain"


def test_lookup_is_case_insensitive() -> None:
    assert get_language("PYTHON").id == "python"
    assert get_language("Cpp").id == "cpp"


@pytest.mark.parametrize("alias, target", sorted(ALIASES.items()))
def test_every_alias_resolves(alias: str, target: str) -> None:
    assert target in LANGUAGES
    assert get_language(alias).id == target


def test_html_resolves_to_xml() -> None:
    assert get_language("html").id == "xml"
    assert get_language("HTML").id == "xml"


def test_lookup_by_display_name() -> None:
    assert get_language("XML / HTML").id == "xml"


@pytest.mark.parametrize(
    "path, expected",
    [
        ("main.py", "python"),
        ("app.js", "javascript"),
        ("Main.qml", "qml"),
        ("data.json", "json"),
        ("page.html", "xml"),
        ("style.css", "css"),
        ("notes.md", "markdown"),
        ("config.yaml", "yaml"),
        ("Dockerfile", "dockerfile"),
        ("readme.txt", "plain"),
        ("noextension", "plain"),
    ],
)
def test_detect_by_name(path: str, expected: str) -> None:
    assert detect_language(path) == expected


def test_detect_uses_shebang_when_extension_is_unknown() -> None:
    assert detect_language("script", "#!/usr/bin/env python3\nprint(1)\n") == "python"
    assert detect_language("script", "#!/bin/bash\necho hi\n") == "shell"
    assert detect_language("script", "#!/usr/bin/env node\n") == "javascript"


def test_detect_sniffs_markup_and_json() -> None:
    assert detect_language("unknown", "<?xml version='1.0'?>") == "xml"
    assert detect_language("unknown", "<!DOCTYPE html>\n<html>") == "xml"
    assert detect_language("unknown", '{"a": 1}') == "json"
    assert detect_language("unknown", "[1, 2, 3]") == "json"


def test_extension_wins_over_content() -> None:
    assert detect_language("thing.py", '{"a": 1}') == "python"


def test_language_names_are_sorted_pairs() -> None:
    names = language_names()
    assert ("plain", LANGUAGES["plain"].name) in names
    ids = {entry[0] for entry in names}
    assert ids == set(LANGUAGES)


def test_definitions_are_self_consistent() -> None:
    for lang_id, lang in LANGUAGES.items():
        assert lang.id == lang_id
        assert lang.name
        assert all(ext.startswith(".") for ext in lang.extensions)
