"""Find/replace engine shared by the UI and the tests.

All operations are pure functions over a string; the QObject wrapper only
adapts them for QML. Results are returned as *spans* so the UI can apply edits
through ``TextArea.remove``/``insert`` and keep the native undo stack intact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from PySide6.QtCore import QObject, Slot
from PySide6.QtQml import QmlElement

QML_IMPORT_NAME = "Cipherpad"
QML_IMPORT_MAJOR_VERSION = 1


class SearchError(ValueError):
    """Raised when a user supplied regular expression cannot be compiled."""


@dataclass(frozen=True)
class SearchOptions:
    case_sensitive: bool = False
    whole_word: bool = False
    regex: bool = False
    wrap: bool = True


def build_pattern(needle: str, options: SearchOptions) -> re.Pattern[str]:
    expression = needle if options.regex else re.escape(needle)
    if options.whole_word:
        expression = rf"\b(?:{expression})\b"
    flags = re.MULTILINE | (0 if options.case_sensitive else re.IGNORECASE)
    try:
        return re.compile(expression, flags)
    except re.error as exc:
        raise SearchError(str(exc)) from exc


def find_all(text: str, needle: str, options: SearchOptions) -> list[tuple[int, int]]:
    if not needle:
        return []
    pattern = build_pattern(needle, options)
    spans: list[tuple[int, int]] = []
    position = 0
    length = len(text)
    while position <= length:
        match = pattern.search(text, position)
        if match is None:
            break
        spans.append((match.start(), match.end()))
        # Zero-width matches (e.g. the regex ``^``) must still make progress.
        position = match.end() if match.end() > match.start() else match.start() + 1
    return spans


def find_next(text: str, needle: str, start: int, options: SearchOptions) -> tuple[int, int] | None:
    spans = find_all(text, needle, options)
    if not spans:
        return None
    for span in spans:
        if span[0] >= start:
            return span
    return spans[0] if options.wrap else None


def find_previous(text: str, needle: str, start: int, options: SearchOptions) -> tuple[int, int] | None:
    spans = find_all(text, needle, options)
    if not spans:
        return None
    for span in reversed(spans):
        if span[1] <= start:
            return span
    return spans[-1] if options.wrap else None


def replacements(
    text: str, needle: str, replacement: str, options: SearchOptions
) -> list[tuple[int, int, str]]:
    """Every replacement to perform, with regex backreferences expanded."""
    if not needle:
        return []
    pattern = build_pattern(needle, options)
    result: list[tuple[int, int, str]] = []
    position = 0
    length = len(text)
    while position <= length:
        match = pattern.search(text, position)
        if match is None:
            break
        try:
            value = match.expand(replacement) if options.regex else replacement
        except (re.error, IndexError) as exc:
            raise SearchError(f"Invalid replacement template: {exc}") from exc
        result.append((match.start(), match.end(), value))
        position = match.end() if match.end() > match.start() else match.start() + 1
    return result


def replace_all(text: str, needle: str, replacement: str, options: SearchOptions) -> tuple[str, int]:
    spans = replacements(text, needle, replacement, options)
    if not spans:
        return text, 0
    chunks: list[str] = []
    cursor = 0
    for start, end, value in spans:
        chunks.append(text[cursor:start])
        chunks.append(value)
        cursor = end
    chunks.append(text[cursor:])
    return "".join(chunks), len(spans)


@QmlElement
class SearchEngine(QObject):
    """QML facade over the search functions."""

    @staticmethod
    def _options(case_sensitive: bool, whole_word: bool, regex: bool, wrap: bool = True) -> SearchOptions:
        return SearchOptions(bool(case_sensitive), bool(whole_word), bool(regex), bool(wrap))

    @Slot(str, str, bool, bool, bool, result=bool)
    def isValid(self, needle: str, _replacement: str, case_sensitive: bool, whole_word: bool, regex: bool) -> bool:
        if not needle:
            return True
        try:
            build_pattern(needle, self._options(case_sensitive, whole_word, regex))
        except SearchError:
            return False
        return True

    @Slot(str, str, int, bool, bool, bool, bool, result="QVariantList")
    def findNext(
        self, text: str, needle: str, start: int, case_sensitive: bool, whole_word: bool, regex: bool, wrap: bool
    ) -> list[int]:
        try:
            span = find_next(text, needle, start, self._options(case_sensitive, whole_word, regex, wrap))
        except SearchError:
            return []
        return list(span) if span else []

    @Slot(str, str, int, bool, bool, bool, bool, result="QVariantList")
    def findPrevious(
        self, text: str, needle: str, start: int, case_sensitive: bool, whole_word: bool, regex: bool, wrap: bool
    ) -> list[int]:
        try:
            span = find_previous(text, needle, start, self._options(case_sensitive, whole_word, regex, wrap))
        except SearchError:
            return []
        return list(span) if span else []

    @Slot(str, str, bool, bool, bool, result=int)
    def matchCount(self, text: str, needle: str, case_sensitive: bool, whole_word: bool, regex: bool) -> int:
        try:
            return len(find_all(text, needle, self._options(case_sensitive, whole_word, regex)))
        except SearchError:
            return 0

    @Slot(str, str, int, bool, bool, bool, result=int)
    def matchOrdinal(
        self, text: str, needle: str, position: int, case_sensitive: bool, whole_word: bool, regex: bool
    ) -> int:
        """1-based index of the match starting at *position*, else 0."""
        try:
            spans = find_all(text, needle, self._options(case_sensitive, whole_word, regex))
        except SearchError:
            return 0
        for index, (start, _end) in enumerate(spans, start=1):
            if start == position:
                return index
        return 0

    @Slot(str, str, str, bool, bool, bool, result="QVariantList")
    def replacementSpans(
        self, text: str, needle: str, replacement: str, case_sensitive: bool, whole_word: bool, regex: bool
    ) -> list[dict]:
        """Spans to replace, ordered last-to-first so indices stay valid."""
        try:
            spans = replacements(text, needle, replacement, self._options(case_sensitive, whole_word, regex))
        except SearchError:
            return []
        return [{"start": s, "end": e, "text": v} for s, e, v in reversed(spans)]

    @Slot(str, str, str, int, int, bool, bool, bool, result="QVariantMap")
    def replaceCurrent(
        self,
        text: str,
        needle: str,
        replacement: str,
        selection_start: int,
        selection_end: int,
        case_sensitive: bool,
        whole_word: bool,
        regex: bool,
    ) -> dict:
        """Expand *replacement* for the currently selected match, if it is one."""
        options = self._options(case_sensitive, whole_word, regex)
        if not needle or selection_end < selection_start:
            return {"matched": False}
        try:
            pattern = build_pattern(needle, options)
        except SearchError:
            return {"matched": False}
        match = pattern.match(text, selection_start, selection_end)
        if match is None or match.end() != selection_end:
            return {"matched": False}
        try:
            value = match.expand(replacement) if options.regex else replacement
        except (re.error, IndexError):
            return {"matched": False}
        return {"matched": True, "start": match.start(), "end": match.end(), "text": value}
