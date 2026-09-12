"""Preferences persisted with :class:`~PySide6.QtCore.QSettings`.

Every property writes through to disk as soon as it changes, so a crash never
loses the user's setup. Colour themes are presets that seed the individual
colour properties; users can still override any single colour afterwards.
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Property, QObject, QSettings, Signal, Slot
from PySide6.QtQml import QmlElement

QML_IMPORT_NAME = "Cipherpad"
QML_IMPORT_MAJOR_VERSION = 1

ORGANIZATION = "Cipherpad"
APPLICATION = "Cipherpad"

MIN_FONT_SIZE = 6
MAX_FONT_SIZE = 72
MAX_RECENT_FILES = 12

THEMES: dict[str, dict[str, str]] = {
    "Dark": {
        "background": "#1e1f22",
        "text": "#e6e6e6",
        "selection": "#2f5d8a",
        "currentLine": "#2a2c31",
        "gutterBackground": "#1a1b1e",
        "gutterText": "#6a6f78",
        "gutterCurrent": "#c8ccd4",
        "chrome": "#26282d",
        "chromeText": "#d6d9de",
        "border": "#3a3d44",
        "accent": "#4f8cc9",
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
    },
    "Light": {
        "background": "#ffffff",
        "text": "#1f2328",
        "selection": "#b4d5fe",
        "currentLine": "#f2f4f7",
        "gutterBackground": "#f6f8fa",
        "gutterText": "#9aa2ad",
        "gutterCurrent": "#1f2328",
        "chrome": "#f2f4f7",
        "chromeText": "#1f2328",
        "border": "#d8dde3",
        "accent": "#0969da",
        "keyword": "#8250df",
        "type": "#1f7a6c",
        "builtin": "#0550ae",
        "string": "#0a7d32",
        "comment": "#8b949e",
        "number": "#b35900",
        "function": "#0550ae",
        "operator": "#1f2328",
        "preprocessor": "#9a6700",
        "decorator": "#9a6700",
        "tag": "#b3212b",
        "attribute": "#b35900",
        "heading": "#0550ae",
        "link": "#0969da",
        "error": "#b3212b",
    },
    "Solarized Dark": {
        "background": "#002b36",
        "text": "#93a1a1",
        "selection": "#0f4a57",
        "currentLine": "#073642",
        "gutterBackground": "#012b33",
        "gutterText": "#586e75",
        "gutterCurrent": "#93a1a1",
        "chrome": "#073642",
        "chromeText": "#93a1a1",
        "border": "#0f4a57",
        "accent": "#268bd2",
        "keyword": "#859900",
        "type": "#b58900",
        "builtin": "#268bd2",
        "string": "#2aa198",
        "comment": "#586e75",
        "number": "#d33682",
        "function": "#268bd2",
        "operator": "#93a1a1",
        "preprocessor": "#cb4b16",
        "decorator": "#cb4b16",
        "tag": "#dc322f",
        "attribute": "#b58900",
        "heading": "#268bd2",
        "link": "#268bd2",
        "error": "#dc322f",
    },
    "High Contrast": {
        "background": "#000000",
        "text": "#ffffff",
        "selection": "#0060c0",
        "currentLine": "#1a1a1a",
        "gutterBackground": "#000000",
        "gutterText": "#a0a0a0",
        "gutterCurrent": "#ffffff",
        "chrome": "#0d0d0d",
        "chromeText": "#ffffff",
        "border": "#6f6f6f",
        "accent": "#3ff23f",
        "keyword": "#ff7fbf",
        "type": "#3ff2f2",
        "builtin": "#3fb0ff",
        "string": "#3ff23f",
        "comment": "#9a9a9a",
        "number": "#ffb03f",
        "function": "#3fb0ff",
        "operator": "#ffffff",
        "preprocessor": "#ffd700",
        "decorator": "#ffd700",
        "tag": "#ff6f6f",
        "attribute": "#ffb03f",
        "heading": "#3fb0ff",
        "link": "#3fb0ff",
        "error": "#ff6f6f",
    },
}

SYNTAX_KEYS = (
    "keyword",
    "type",
    "builtin",
    "string",
    "comment",
    "number",
    "function",
    "operator",
    "preprocessor",
    "decorator",
    "tag",
    "attribute",
    "heading",
    "link",
    "error",
)

DEFAULTS: dict[str, Any] = {
    "theme": "Dark",
    "fontFamily": "Cascadia Mono",
    "fontSize": 13,
    "fontBold": False,
    "fontItalic": False,
    "lineHeight": 1.25,
    "tabWidth": 4,
    "insertSpaces": True,
    "autoIndent": True,
    "wordWrap": False,
    "showLineNumbers": True,
    "highlightCurrentLine": True,
    "syntaxHighlighting": True,
    "showStatusBar": True,
    "showToolBar": True,
    "autoCloseBrackets": True,
    "matchBrackets": True,
    "showWhitespace": False,
    "trimTrailingWhitespaceOnSave": False,
    "ensureNewlineAtEof": False,
    "restoreSession": True,
    "defaultEncoding": "utf-8",
    "defaultLineEnding": "lf",
    "searchCaseSensitive": False,
    "searchWholeWord": False,
    "searchRegex": False,
    "searchWrapAround": True,
    "windowWidth": 1200,
    "windowHeight": 780,
    "windowMaximized": False,
}
DEFAULTS.update(THEMES["Dark"])


def _signal_name(key: str) -> str:
    """Notify signal for a settings key ("type" is exposed as typeColor in QML)."""
    return "typeColorChanged" if key == "type" else f"{key}Changed"


def _prop(name: str, type_: type, signal: Signal) -> Property:
    """Build a QSettings-backed Qt property."""

    def getter(self: "Preferences") -> Any:
        return self._values[name]

    def setter(self: "Preferences", value: Any) -> None:
        if type_ is not object:
            try:
                value = type_(value)
            except (TypeError, ValueError):
                return
        if self._values.get(name) == value:
            return
        self._values[name] = value
        self._settings.setValue(name, value)
        getattr(self, _signal_name(name)).emit()

    return Property(type_, getter, setter, notify=signal)


@QmlElement
class Preferences(QObject):
    """Application preferences, transparently persisted."""

    themeChanged = Signal()
    fontFamilyChanged = Signal()
    fontSizeChanged = Signal()
    fontBoldChanged = Signal()
    fontItalicChanged = Signal()
    lineHeightChanged = Signal()
    tabWidthChanged = Signal()
    insertSpacesChanged = Signal()
    autoIndentChanged = Signal()
    wordWrapChanged = Signal()
    showLineNumbersChanged = Signal()
    highlightCurrentLineChanged = Signal()
    syntaxHighlightingChanged = Signal()
    showStatusBarChanged = Signal()
    showToolBarChanged = Signal()
    autoCloseBracketsChanged = Signal()
    matchBracketsChanged = Signal()
    showWhitespaceChanged = Signal()
    trimTrailingWhitespaceOnSaveChanged = Signal()
    ensureNewlineAtEofChanged = Signal()
    restoreSessionChanged = Signal()
    defaultEncodingChanged = Signal()
    defaultLineEndingChanged = Signal()
    searchCaseSensitiveChanged = Signal()
    searchWholeWordChanged = Signal()
    searchRegexChanged = Signal()
    searchWrapAroundChanged = Signal()
    windowWidthChanged = Signal()
    windowHeightChanged = Signal()
    windowMaximizedChanged = Signal()

    backgroundChanged = Signal()
    textChanged = Signal()
    selectionChanged = Signal()
    currentLineChanged = Signal()
    gutterBackgroundChanged = Signal()
    gutterTextChanged = Signal()
    gutterCurrentChanged = Signal()
    chromeChanged = Signal()
    chromeTextChanged = Signal()
    borderChanged = Signal()
    accentChanged = Signal()
    keywordChanged = Signal()
    typeColorChanged = Signal()
    builtinChanged = Signal()
    stringChanged = Signal()
    commentChanged = Signal()
    numberChanged = Signal()
    functionChanged = Signal()
    operatorChanged = Signal()
    preprocessorChanged = Signal()
    decoratorChanged = Signal()
    tagChanged = Signal()
    attributeChanged = Signal()
    headingChanged = Signal()
    linkChanged = Signal()
    errorChanged = Signal()

    recentFilesChanged = Signal()
    paletteChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = QSettings(ORGANIZATION, APPLICATION)
        self._values: dict[str, Any] = {}
        for key, default in DEFAULTS.items():
            self._values[key] = self._read(key, default)
        self._recent_files: list[str] = self._read_list("recentFiles")
        self._session_files: list[str] = self._read_list("sessionFiles")

    # ------------------------------------------------------------------ io
    def _read(self, key: str, default: Any) -> Any:
        raw = self._settings.value(key, default)
        if isinstance(default, bool):
            if isinstance(raw, str):
                return raw.lower() in ("true", "1", "yes")
            return bool(raw)
        if isinstance(default, int):
            try:
                return int(raw)
            except (TypeError, ValueError):
                return default
        if isinstance(default, float):
            try:
                return float(raw)
            except (TypeError, ValueError):
                return default
        return str(raw) if raw is not None else default

    def _read_list(self, key: str) -> list[str]:
        raw = self._settings.value(key, "[]")
        try:
            data = json.loads(raw) if isinstance(raw, str) else list(raw)
        except (json.JSONDecodeError, TypeError):
            return []
        return [str(item) for item in data if item]

    def _write_list(self, key: str, values: list[str]) -> None:
        self._settings.setValue(key, json.dumps(values))

    # ----------------------------------------------------------- properties
    theme = _prop("theme", str, themeChanged)
    fontFamily = _prop("fontFamily", str, fontFamilyChanged)
    fontSize = _prop("fontSize", int, fontSizeChanged)
    fontBold = _prop("fontBold", bool, fontBoldChanged)
    fontItalic = _prop("fontItalic", bool, fontItalicChanged)
    lineHeight = _prop("lineHeight", float, lineHeightChanged)
    tabWidth = _prop("tabWidth", int, tabWidthChanged)
    insertSpaces = _prop("insertSpaces", bool, insertSpacesChanged)
    autoIndent = _prop("autoIndent", bool, autoIndentChanged)
    wordWrap = _prop("wordWrap", bool, wordWrapChanged)
    showLineNumbers = _prop("showLineNumbers", bool, showLineNumbersChanged)
    highlightCurrentLine = _prop("highlightCurrentLine", bool, highlightCurrentLineChanged)
    syntaxHighlighting = _prop("syntaxHighlighting", bool, syntaxHighlightingChanged)
    showStatusBar = _prop("showStatusBar", bool, showStatusBarChanged)
    showToolBar = _prop("showToolBar", bool, showToolBarChanged)
    autoCloseBrackets = _prop("autoCloseBrackets", bool, autoCloseBracketsChanged)
    matchBrackets = _prop("matchBrackets", bool, matchBracketsChanged)
    showWhitespace = _prop("showWhitespace", bool, showWhitespaceChanged)
    trimTrailingWhitespaceOnSave = _prop(
        "trimTrailingWhitespaceOnSave", bool, trimTrailingWhitespaceOnSaveChanged
    )
    ensureNewlineAtEof = _prop("ensureNewlineAtEof", bool, ensureNewlineAtEofChanged)
    restoreSession = _prop("restoreSession", bool, restoreSessionChanged)
    defaultEncoding = _prop("defaultEncoding", str, defaultEncodingChanged)
    defaultLineEnding = _prop("defaultLineEnding", str, defaultLineEndingChanged)
    searchCaseSensitive = _prop("searchCaseSensitive", bool, searchCaseSensitiveChanged)
    searchWholeWord = _prop("searchWholeWord", bool, searchWholeWordChanged)
    searchRegex = _prop("searchRegex", bool, searchRegexChanged)
    searchWrapAround = _prop("searchWrapAround", bool, searchWrapAroundChanged)
    windowWidth = _prop("windowWidth", int, windowWidthChanged)
    windowHeight = _prop("windowHeight", int, windowHeightChanged)
    windowMaximized = _prop("windowMaximized", bool, windowMaximizedChanged)

    background = _prop("background", str, backgroundChanged)
    text = _prop("text", str, textChanged)
    selection = _prop("selection", str, selectionChanged)
    currentLine = _prop("currentLine", str, currentLineChanged)
    gutterBackground = _prop("gutterBackground", str, gutterBackgroundChanged)
    gutterText = _prop("gutterText", str, gutterTextChanged)
    gutterCurrent = _prop("gutterCurrent", str, gutterCurrentChanged)
    chrome = _prop("chrome", str, chromeChanged)
    chromeText = _prop("chromeText", str, chromeTextChanged)
    border = _prop("border", str, borderChanged)
    accent = _prop("accent", str, accentChanged)
    keyword = _prop("keyword", str, keywordChanged)
    typeColor = _prop("type", str, typeColorChanged)
    builtin = _prop("builtin", str, builtinChanged)
    string = _prop("string", str, stringChanged)
    comment = _prop("comment", str, commentChanged)
    number = _prop("number", str, numberChanged)
    function = _prop("function", str, functionChanged)
    operator = _prop("operator", str, operatorChanged)
    preprocessor = _prop("preprocessor", str, preprocessorChanged)
    decorator = _prop("decorator", str, decoratorChanged)
    tag = _prop("tag", str, tagChanged)
    attribute = _prop("attribute", str, attributeChanged)
    heading = _prop("heading", str, headingChanged)
    link = _prop("link", str, linkChanged)
    error = _prop("error", str, errorChanged)

    @Property("QStringList", notify=recentFilesChanged)
    def recentFiles(self) -> list[str]:
        return list(self._recent_files)

    @Property("QStringList", notify=themeChanged)
    def availableThemes(self) -> list[str]:
        return list(THEMES)

    # -------------------------------------------------------------- actions
    @Slot(str)
    def applyTheme(self, name: str) -> None:
        """Apply a colour preset and persist every colour it defines."""
        palette = THEMES.get(name)
        if palette is None:
            return
        self.theme = name
        for key, value in palette.items():
            if self._values.get(key) == value:
                continue
            self._values[key] = value
            self._settings.setValue(key, value)
            getattr(self, _signal_name(key)).emit()
        self.paletteChanged.emit()

    @Slot(result="QVariantMap")
    def syntaxPalette(self) -> dict[str, str]:
        """Colours consumed by the syntax highlighter."""
        return {key: str(self._values[key]) for key in SYNTAX_KEYS}

    @Slot()
    def resetToDefaults(self) -> None:
        for key, default in DEFAULTS.items():
            if self._values.get(key) == default:
                continue
            self._values[key] = default
            self._settings.setValue(key, default)
            getattr(self, _signal_name(key)).emit()
        self.paletteChanged.emit()

    @Slot(int)
    def adjustFontSize(self, delta: int) -> None:
        self.fontSize = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, self.fontSize + delta))

    @Slot(str)
    def addRecentFile(self, path: str) -> None:
        if not path:
            return
        if path in self._recent_files:
            self._recent_files.remove(path)
        self._recent_files.insert(0, path)
        del self._recent_files[MAX_RECENT_FILES:]
        self._write_list("recentFiles", self._recent_files)
        self.recentFilesChanged.emit()

    @Slot(str)
    def removeRecentFile(self, path: str) -> None:
        if path not in self._recent_files:
            return
        self._recent_files.remove(path)
        self._write_list("recentFiles", self._recent_files)
        self.recentFilesChanged.emit()

    @Slot()
    def clearRecentFiles(self) -> None:
        if not self._recent_files:
            return
        self._recent_files.clear()
        self._write_list("recentFiles", self._recent_files)
        self.recentFilesChanged.emit()

    @Slot("QStringList")
    def saveSession(self, paths: list[str]) -> None:
        self._session_files = [p for p in paths if p]
        self._write_list("sessionFiles", self._session_files)

    @Slot(result="QStringList")
    def sessionFiles(self) -> list[str]:
        return list(self._session_files)

    @Slot()
    def sync(self) -> None:
        self._settings.sync()
