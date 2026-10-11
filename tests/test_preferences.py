"""Tests for the persisted preferences store."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QSettings

from cipherpad import preferences as prefs_module
from cipherpad.preferences import (
    DEFAULTS,
    MAX_FONT_SIZE,
    MAX_RECENT_FILES,
    MIN_FONT_SIZE,
    SYNTAX_KEYS,
    THEMES,
    Preferences,
)

TEST_ORG = "CipherpadTests"
TEST_APP = "CipherpadPrefsTests"


@pytest.fixture()
def prefs(qt_app, monkeypatch: pytest.MonkeyPatch) -> Iterator[Preferences]:  # noqa: ANN001
    """A Preferences instance backed by a throwaway QSettings scope."""
    monkeypatch.setattr(prefs_module, "ORGANIZATION", TEST_ORG)
    monkeypatch.setattr(prefs_module, "APPLICATION", TEST_APP)
    QSettings(TEST_ORG, TEST_APP).clear()
    instance = Preferences()
    yield instance
    instance._settings.clear()
    instance._settings.sync()


def reopen() -> Preferences:
    """A second Preferences reading the same (patched) settings scope."""
    return Preferences()


# -------------------------------------------------------------------- defaults
def test_defaults_are_loaded(prefs: Preferences) -> None:
    assert prefs.theme == DEFAULTS["theme"]
    assert prefs.fontSize == DEFAULTS["fontSize"]
    assert prefs.tabWidth == DEFAULTS["tabWidth"]
    assert prefs.insertSpaces is DEFAULTS["insertSpaces"]
    assert prefs.wordWrap is DEFAULTS["wordWrap"]
    assert prefs.recoveryEnabled is True
    assert prefs.clipboardExpirySeconds == 30


def test_recovery_and_clipboard_preferences_persist(prefs: Preferences) -> None:
    prefs.recoveryEnabled = False
    prefs.clipboardExpirySeconds = 90
    prefs.sync()
    restored = reopen()
    assert restored.recoveryEnabled is False
    assert restored.clipboardExpirySeconds == 90


def test_default_palette_matches_dark_theme(prefs: Preferences) -> None:
    for key, value in THEMES["Dark"].items():
        attribute = "typeColor" if key == "type" else key
        assert getattr(prefs, attribute) == value


def test_recent_and_session_start_empty(prefs: Preferences) -> None:
    assert prefs.recentFiles == []
    assert prefs.sessionFiles() == []


# ----------------------------------------------------------------- persistence
def test_scalar_values_persist(prefs: Preferences) -> None:
    prefs.fontSize = 21
    prefs.fontFamily = "Consolas"
    prefs.lineHeight = 1.5
    prefs.wordWrap = True
    prefs.sync()

    restored = reopen()
    assert restored.fontSize == 21
    assert restored.fontFamily == "Consolas"
    assert restored.lineHeight == pytest.approx(1.5)
    assert restored.wordWrap is True


def test_booleans_survive_string_round_trip(prefs: Preferences) -> None:
    prefs.showLineNumbers = False
    prefs.sync()
    assert reopen().showLineNumbers is False


def test_workspace_settings_persist(prefs: Preferences) -> None:
    prefs.showHiddenFiles = True
    prefs.workspaceIgnorePatterns = "*.tmp;build"
    prefs.sync()
    assert reopen().showHiddenFiles is True
    assert reopen().workspaceIgnorePatterns == "*.tmp;build"
    prefs.resetToDefaults()
    assert not prefs.showHiddenFiles
    assert prefs.workspaceIgnorePatterns == DEFAULTS["workspaceIgnorePatterns"]


def test_setter_coerces_types(prefs: Preferences) -> None:
    prefs.fontSize = "18"
    assert prefs.fontSize == 18
    assert isinstance(prefs.fontSize, int)


def test_setter_ignores_uncoercible_values(prefs: Preferences) -> None:
    prefs.fontSize = 14
    prefs.fontSize = "not a number"
    assert prefs.fontSize == 14


def test_setting_same_value_does_not_signal(prefs: Preferences) -> None:
    seen: list[bool] = []
    prefs.fontSizeChanged.connect(lambda: seen.append(True))
    prefs.fontSize = prefs.fontSize
    assert seen == []


def test_changing_value_signals_once(prefs: Preferences) -> None:
    seen: list[bool] = []
    prefs.fontSizeChanged.connect(lambda: seen.append(True))
    prefs.fontSize = prefs.fontSize + 1
    assert len(seen) == 1


# ---------------------------------------------------------------------- themes
def test_available_themes_lists_presets(prefs: Preferences) -> None:
    assert set(prefs.availableThemes) == set(THEMES)


def test_apply_theme_switches_palette(prefs: Preferences) -> None:
    target = next(name for name in THEMES if name != prefs.theme)
    prefs.applyTheme(target)
    assert prefs.theme == target
    assert prefs.background == THEMES[target]["background"]


def test_apply_theme_persists_colours(prefs: Preferences) -> None:
    target = next(name for name in THEMES if name != prefs.theme)
    prefs.applyTheme(target)
    prefs.sync()
    assert reopen().background == THEMES[target]["background"]


def test_apply_theme_emits_palette_changed(prefs: Preferences) -> None:
    seen: list[bool] = []
    prefs.paletteChanged.connect(lambda: seen.append(True))
    prefs.applyTheme(next(name for name in THEMES if name != prefs.theme))
    assert seen


def test_apply_unknown_theme_is_ignored(prefs: Preferences) -> None:
    before = prefs.theme
    prefs.applyTheme("Nonexistent")
    assert prefs.theme == before


def test_type_colour_is_exposed_as_type_color(prefs: Preferences) -> None:
    prefs.typeColor = "#123456"
    assert prefs.typeColor == "#123456"
    assert prefs.syntaxPalette()["type"] == "#123456"


def test_syntax_palette_covers_every_key(prefs: Preferences) -> None:
    palette = prefs.syntaxPalette()
    assert set(palette) == set(SYNTAX_KEYS)
    assert all(value.startswith("#") for value in palette.values())


def test_reset_to_defaults(prefs: Preferences) -> None:
    prefs.fontSize = 30
    prefs.wordWrap = True
    prefs.applyTheme(next(name for name in THEMES if name != DEFAULTS["theme"]))

    prefs.resetToDefaults()
    assert prefs.fontSize == DEFAULTS["fontSize"]
    assert prefs.wordWrap is DEFAULTS["wordWrap"]
    assert prefs.theme == DEFAULTS["theme"]
    assert prefs.background == DEFAULTS["background"]


def test_reset_to_defaults_persists(prefs: Preferences) -> None:
    prefs.fontSize = 30
    prefs.resetToDefaults()
    prefs.sync()
    assert reopen().fontSize == DEFAULTS["fontSize"]


# ------------------------------------------------------------------ font sizes
def test_adjust_font_size(prefs: Preferences) -> None:
    prefs.fontSize = 14
    prefs.adjustFontSize(2)
    assert prefs.fontSize == 16
    prefs.adjustFontSize(-3)
    assert prefs.fontSize == 13


def test_adjust_font_size_clamps_to_bounds(prefs: Preferences) -> None:
    prefs.adjustFontSize(1000)
    assert prefs.fontSize == MAX_FONT_SIZE
    prefs.adjustFontSize(-1000)
    assert prefs.fontSize == MIN_FONT_SIZE


# ---------------------------------------------------------------- recent files
def test_add_recent_file(prefs: Preferences) -> None:
    prefs.addRecentFile("a.txt")
    prefs.addRecentFile("b.txt")
    assert prefs.recentFiles == ["b.txt", "a.txt"]


def test_add_recent_file_moves_existing_to_front(prefs: Preferences) -> None:
    prefs.addRecentFile("a.txt")
    prefs.addRecentFile("b.txt")
    prefs.addRecentFile("a.txt")
    assert prefs.recentFiles == ["a.txt", "b.txt"]


def test_add_recent_file_ignores_empty(prefs: Preferences) -> None:
    prefs.addRecentFile("")
    assert prefs.recentFiles == []


def test_recent_files_are_capped(prefs: Preferences) -> None:
    for index in range(MAX_RECENT_FILES + 5):
        prefs.addRecentFile(f"file{index}.txt")
    assert len(prefs.recentFiles) == MAX_RECENT_FILES


def test_recent_files_persist(prefs: Preferences) -> None:
    prefs.addRecentFile("a.txt")
    prefs.sync()
    assert reopen().recentFiles == ["a.txt"]


def test_remove_recent_file(prefs: Preferences) -> None:
    prefs.addRecentFile("a.txt")
    prefs.removeRecentFile("a.txt")
    assert prefs.recentFiles == []


def test_remove_unknown_recent_file_is_noop(prefs: Preferences) -> None:
    prefs.addRecentFile("a.txt")
    prefs.removeRecentFile("zzz.txt")
    assert prefs.recentFiles == ["a.txt"]


def test_clear_recent_files(prefs: Preferences) -> None:
    prefs.addRecentFile("a.txt")
    prefs.clearRecentFiles()
    assert prefs.recentFiles == []


def test_recent_files_signal_on_change(prefs: Preferences) -> None:
    seen: list[bool] = []
    prefs.recentFilesChanged.connect(lambda: seen.append(True))
    prefs.addRecentFile("a.txt")
    prefs.removeRecentFile("a.txt")
    assert len(seen) == 2


# --------------------------------------------------------------------- session
def test_save_and_restore_session(prefs: Preferences) -> None:
    prefs.saveSession(["a.txt", "b.txt"])
    prefs.sync()
    assert reopen().sessionFiles() == ["a.txt", "b.txt"]


def test_save_session_drops_empty_entries(prefs: Preferences) -> None:
    prefs.saveSession(["a.txt", "", "b.txt"])
    assert prefs.sessionFiles() == ["a.txt", "b.txt"]


def test_save_empty_session_clears_it(prefs: Preferences) -> None:
    prefs.saveSession(["a.txt"])
    prefs.saveSession([])
    prefs.sync()
    assert reopen().sessionFiles() == []


def test_corrupt_list_setting_is_ignored(prefs: Preferences) -> None:
    prefs._settings.setValue("recentFiles", "{not json")
    prefs._settings.sync()
    assert reopen().recentFiles == []


# ----------------------------------------------------------- project explorer
def test_project_explorer_prefs_defaults(prefs: Preferences) -> None:
    assert prefs.showProjectExplorer is True
    assert prefs.projectExplorerWidth == 220
    assert prefs.projectFolders() == []


def test_project_explorer_prefs_persist(prefs: Preferences) -> None:
    prefs.showProjectExplorer = False
    prefs.projectExplorerWidth = 300
    prefs.saveProjectFolders(["/path/one", "/path/two"])
    prefs.sync()

    restored = reopen()
    assert restored.showProjectExplorer is False
    assert restored.projectExplorerWidth == 300
    assert restored.projectFolders() == ["/path/one", "/path/two"]
