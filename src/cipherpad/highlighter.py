"""Syntax highlighting for the QML ``TextArea`` document.

``QQuickTextDocument`` exposes the underlying ``QTextDocument`` of a Qt Quick
``TextArea``, which lets a regular ``QSyntaxHighlighter`` drive highlighting for
a QML editor. :class:`SyntaxHighlighter` is the QML-facing wrapper that owns the
real highlighter and re-applies it whenever the language, palette or document
changes.
"""

from __future__ import annotations

import re

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QColor, QFontMetricsF, QSyntaxHighlighter, QTextCharFormat, QTextDocument, QTextOption
from PySide6.QtQml import QmlElement
from PySide6.QtQuick import QQuickTextDocument

from .languages import (
    Language,
    MultiLineRule,
    detect_language,
    get_language,
    language_names,
)

QML_IMPORT_NAME = "Cipherpad"
QML_IMPORT_MAJOR_VERSION = 1

# Lower number wins: a quote inside a comment must not start a string, and a
# keyword inside a string must stay a string.
STYLE_PRIORITY = {
    "comment": 0,
    "string": 1,
    "heading": 2,
    "decorator": 2,
    "preprocessor": 2,
    "tag": 2,
    "link": 2,
    "error": 2,
    "attribute": 3,
    "function": 4,
    "keyword": 5,
    "type": 5,
    "builtin": 5,
    "number": 6,
    "operator": 7,
}

DEFAULT_PALETTE = {
    "keyword": "#c07ee0",
    "type": "#4ec9b0",
    "builtin": "#56a8f5",
    "string": "#98c379",
    "comment": "#6c7280",
    "number": "#d19a66",
    "function": "#61afef",
    "operator": "#c8ccd4",
    "preprocessor": "#e5c07b",
    "decorator": "#e5c07b",
    "tag": "#e06c75",
    "attribute": "#d19a66",
    "heading": "#61afef",
    "link": "#56a8f5",
    "error": "#e06c75",
}

_ITALIC_STYLES = {"comment"}
_BOLD_STYLES = {"keyword", "heading", "tag"}


class _CompiledMultiLine:
    __slots__ = ("start", "end", "style")

    def __init__(self, rule: MultiLineRule) -> None:
        flags = re.MULTILINE
        self.start = re.compile(rule.start, flags)
        self.end = re.compile(rule.end, flags)
        self.style = rule.style


class _Highlighter(QSyntaxHighlighter):
    """Rule-driven highlighter with occupancy tracking."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._rules: list[tuple[re.Pattern[str], str]] = []
        self._multiline: list[_CompiledMultiLine] = []
        self._formats: dict[str, QTextCharFormat] = {}
        self._palette = dict(DEFAULT_PALETTE)
        self._enabled = True
        self._search: re.Pattern[str] | None = None
        self._search_format = QTextCharFormat()
        self._search_format.setBackground(QColor("#5a4a12"))
        self._rebuild_formats()

    # ------------------------------------------------------------- config
    def set_palette(self, palette: dict[str, str]) -> None:
        self._palette = {**DEFAULT_PALETTE, **{k: v for k, v in palette.items() if v}}
        self._rebuild_formats()
        self.rehighlight()

    def set_language(self, language: Language) -> None:
        rules: list[tuple[int, int, re.Pattern[str], str]] = []
        order = 0
        flags = re.MULTILINE
        kw_flags = flags | (re.IGNORECASE if language.case_insensitive_keywords else 0)

        for words, style in (
            (language.keywords, "keyword"),
            (language.types, "type"),
            (language.builtins, "builtin"),
        ):
            if not words:
                continue
            pattern = r"\b(?:%s)\b" % "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True))
            rules.append((STYLE_PRIORITY[style], order, re.compile(pattern, kw_flags), style))
            order += 1

        for pattern, style in language.rules:
            try:
                compiled = re.compile(pattern, flags)
            except re.error:
                continue
            rules.append((STYLE_PRIORITY.get(style, 5), order, compiled, style))
            order += 1

        rules.sort(key=lambda item: (item[0], item[1]))
        self._rules = [(compiled, style) for _, _, compiled, style in rules]
        self._multiline = [_CompiledMultiLine(rule) for rule in language.multiline]
        self.rehighlight()

    def set_enabled(self, enabled: bool) -> None:
        if self._enabled == enabled:
            return
        self._enabled = enabled
        self.rehighlight()

    def set_search(self, pattern: re.Pattern[str] | None, color: str) -> None:
        self._search = pattern
        self._search_format = QTextCharFormat()
        self._search_format.setBackground(QColor(color))
        self.rehighlight()

    def _rebuild_formats(self) -> None:
        self._formats.clear()
        for style, color in self._palette.items():
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if style in _ITALIC_STYLES:
                fmt.setFontItalic(True)
            if style in _BOLD_STYLES:
                fmt.setFontWeight(600)
            self._formats[style] = fmt

    # ---------------------------------------------------------- highlight
    def _claim(self, start: int, length: int, style: str, claimed: bytearray) -> None:
        if length <= 0:
            return
        end = min(start + length, len(claimed))
        if any(claimed[start:end]):
            return
        fmt = self._formats.get(style)
        if fmt is not None:
            self.setFormat(start, end - start, fmt)
        for i in range(start, end):
            claimed[i] = 1

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt override
        claimed = bytearray(len(text))
        if self._enabled:
            self._highlight_multiline(text, claimed)
            for pattern, style in self._rules:
                for match in pattern.finditer(text):
                    # A capturing group narrows the highlight (e.g. the name in
                    # "def name"); otherwise the whole match is styled.
                    start, end = (match.span(1) if match.lastindex else match.span())
                    self._claim(start, end - start, style, claimed)
        else:
            self.setCurrentBlockState(-1)

        if self._search is not None and text:
            for match in self._search.finditer(text):
                if match.end() == match.start():
                    continue
                merged = QTextCharFormat(self.format(match.start()))
                merged.setBackground(self._search_format.background())
                self.setFormat(match.start(), match.end() - match.start(), merged)

    def _highlight_multiline(self, text: str, claimed: bytearray) -> None:
        if not self._multiline:
            self.setCurrentBlockState(-1)
            return

        previous = self.previousBlockState()
        current = previous - 1 if previous > 0 else -1
        pos = 0
        length = len(text)

        while pos <= length:
            if current < 0:
                best_index = -1
                best_match = None
                for index, rule in enumerate(self._multiline):
                    match = rule.start.search(text, pos)
                    if match and (best_match is None or match.start() < best_match.start()):
                        best_index, best_match = index, match
                if best_match is None:
                    break
                current = best_index
                start_pos = best_match.start()
                search_from = max(best_match.end(), start_pos + 1)
            else:
                start_pos = pos
                search_from = pos

            rule = self._multiline[current]
            end_match = rule.end.search(text, search_from)
            if end_match is None:
                self._claim(start_pos, length - start_pos, rule.style, claimed)
                self.setCurrentBlockState(current + 1)
                return

            self._claim(start_pos, end_match.end() - start_pos, rule.style, claimed)
            pos = max(end_match.end(), start_pos + 1)
            current = -1

        self.setCurrentBlockState(-1)


@QmlElement
class SyntaxHighlighter(QObject):
    """QML-instantiable highlighter attached to a ``TextArea``'s document."""

    documentChanged = Signal()
    languageChanged = Signal()
    enabledChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._quick_document: QQuickTextDocument | None = None
        self._highlighter: _Highlighter | None = None
        self._language = "plain"
        self._enabled = True
        self._palette: dict[str, str] = dict(DEFAULT_PALETTE)
        self._search_color = "#5a4a12"
        self._search_pattern: re.Pattern[str] | None = None
        self._tab_width = 4

    # -------------------------------------------------------- properties
    def _get_document(self) -> QQuickTextDocument | None:
        return self._quick_document

    def _set_document(self, document: QQuickTextDocument | None) -> None:
        if self._quick_document is document:
            return
        self._quick_document = document
        self._highlighter = None
        if document is not None:
            text_document = document.textDocument()
            if text_document is not None:
                self._highlighter = _Highlighter(text_document)
                self._highlighter.set_palette(self._palette)
                self._highlighter.set_enabled(self._enabled)
                self._highlighter.set_language(get_language(self._language))
                self._highlighter.set_search(self._search_pattern, self._search_color)
                self._apply_tab_width(text_document)
        self.documentChanged.emit()

    document = Property(QQuickTextDocument, _get_document, _set_document, notify=documentChanged)

    def _get_language(self) -> str:
        return self._language

    def _set_language(self, language: str) -> None:
        if self._language == language:
            return
        self._language = language
        if self._highlighter is not None:
            self._highlighter.set_language(get_language(language))
        self.languageChanged.emit()

    language = Property(str, _get_language, _set_language, notify=languageChanged)

    def _get_enabled(self) -> bool:
        return self._enabled

    def _set_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._enabled == enabled:
            return
        self._enabled = enabled
        if self._highlighter is not None:
            self._highlighter.set_enabled(enabled)
        self.enabledChanged.emit()

    enabled = Property(bool, _get_enabled, _set_enabled, notify=enabledChanged)

    # ------------------------------------------------------------- slots
    @Slot("QVariantMap")
    def setPalette(self, palette: dict) -> None:
        self._palette = {str(k): str(v) for k, v in dict(palette).items()}
        if self._highlighter is not None:
            self._highlighter.set_palette(self._palette)

    @Slot(str, bool, bool, bool, str)
    def setSearchHighlight(
        self,
        needle: str,
        case_sensitive: bool,
        whole_word: bool,
        use_regex: bool,
        color: str = "#5a4a12",
    ) -> None:
        """Highlight every occurrence of the current search term."""
        self._search_color = color or self._search_color
        pattern: re.Pattern[str] | None = None
        if needle:
            expression = needle if use_regex else re.escape(needle)
            if whole_word:
                expression = rf"\b(?:{expression})\b"
            flags = re.MULTILINE | (0 if case_sensitive else re.IGNORECASE)
            try:
                pattern = re.compile(expression, flags)
            except re.error:
                pattern = None
        self._search_pattern = pattern
        if self._highlighter is not None:
            self._highlighter.set_search(pattern, self._search_color)

    @Slot()
    def clearSearchHighlight(self) -> None:
        self._search_pattern = None
        if self._highlighter is not None:
            self._highlighter.set_search(None, self._search_color)

    @Slot(int)
    def setTabWidth(self, spaces: int) -> None:
        """Render hard tabs as *spaces* columns wide."""
        self._tab_width = max(1, int(spaces))
        if self._quick_document is not None:
            document = self._quick_document.textDocument()
            if document is not None:
                self._apply_tab_width(document)

    def _apply_tab_width(self, document: QTextDocument) -> None:
        metrics = QFontMetricsF(document.defaultFont())
        option = document.defaultTextOption()
        option.setTabStopDistance(metrics.horizontalAdvance(" ") * self._tab_width)
        document.setDefaultTextOption(option)

    @Slot(bool)
    def setShowWhitespace(self, show: bool) -> None:
        if self._quick_document is None:
            return
        document = self._quick_document.textDocument()
        if document is None:
            return
        option = document.defaultTextOption()
        flags = option.flags()
        if show:
            flags |= QTextOption.Flag.ShowTabsAndSpaces
        else:
            flags &= ~QTextOption.Flag.ShowTabsAndSpaces
        option.setFlags(flags)
        document.setDefaultTextOption(option)

    @Slot()
    def rehighlight(self) -> None:
        if self._highlighter is not None:
            self._highlighter.rehighlight()

    @Slot(result="QVariantList")
    def availableLanguages(self) -> list[dict]:
        """``[{id, name}]`` for the language picker, alphabetical after Plain Text."""
        return [{"id": key, "name": name} for key, name in language_names()]

    @Slot(str, str, result=str)
    def detectLanguage(self, path: str, sample: str) -> str:
        return detect_language(path, sample)

    @Slot(str, result=str)
    def languageName(self, language_id: str) -> str:
        return get_language(language_id).name

    @Slot(str, result=str)
    def commentMarker(self, language_id: str) -> str:
        return get_language(language_id).line_comment
