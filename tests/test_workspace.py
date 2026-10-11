"""Workspace discovery, fuzzy navigation and disk search."""

from __future__ import annotations

from pathlib import Path
from threading import Event
import time
import subprocess
import sys

import pytest
from PySide6.QtTest import QTest

from cipherpad.crypto import MAGIC
from cipherpad.explorer import ProjectExplorer
from cipherpad.workspace import WorkspaceTools, discover_entries, fuzzy_files, search_entries


def test_discovery_exclusions_and_nested_roots(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("hello")
    (tmp_path / ".env").write_text("secret")
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "ignored.py").write_text("hello")
    report = discover_entries([str(tmp_path), str(tmp_path / "src")], False, "cache", Event())
    assert [Path(item["path"]).name for item in report["entries"]] == ["src", "main.py"]
    report = discover_entries([str(tmp_path)], True, "cache", Event())
    assert ".env" in [Path(item["path"]).name for item in report["entries"]]


def test_discovery_path_globs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "skip.py").write_text("")
    (tmp_path / "keep.py").write_text("")
    report = discover_entries([str(tmp_path)], True, "src/*.py", Event())
    assert "skip.py" not in [Path(item["path"]).name for item in report["entries"]]


def test_fuzzy_files_prefers_filename_and_subsequence() -> None:
    entries = [
        {"path": "main.py", "relative": "src/main.py", "isDir": False},
        {"path": "menu.py", "relative": "src/menu.py", "isDir": False},
        {"path": "directory", "relative": "main.py", "isDir": True},
    ]
    assert fuzzy_files(entries, "mnpy")[0]["path"] == "main.py"
    assert fuzzy_files(entries, "no-match") == []
    assert len(fuzzy_files(entries, "")) == 2


def test_search_case_word_masks_and_utf16(tmp_path: Path) -> None:
    path = tmp_path / "main.py"
    path.write_text("\U0001f600 hello HELLO\nhello_world hello\n", encoding="utf-8")
    (tmp_path / "other.txt").write_text("hello")
    entries = discover_entries([str(tmp_path)], False, "", Event())["entries"]
    result = search_entries(entries, "hello", "*.py", False, True, Event())
    assert len(result["matches"]) == 3
    first = result["matches"][0]
    assert first["line"] == 1
    assert first["column"] == 4
    assert first["length"] == 5
    assert len(search_entries(entries, "hello", "*.py", True, True, Event())["matches"]) == 2


def test_search_excludes_encrypted_binary_and_large_files(tmp_path: Path) -> None:
    (tmp_path / "encrypted.txt").write_bytes(MAGIC + b"hello")
    (tmp_path / "binary.bin").write_bytes(b"\x00hello")
    (tmp_path / "secret.enc").write_text("hello")
    (tmp_path / "huge.txt").write_bytes(b"h" * (2 * 1024 * 1024 + 1))
    entries = discover_entries([str(tmp_path)], False, "", Event())["entries"]
    result = search_entries(entries, "hello", "", False, False, Event())
    assert result["matches"] == []
    assert result["skipped"] == 4


def test_search_utf16_and_crlf(tmp_path: Path) -> None:
    (tmp_path / "wide.txt").write_bytes("first\r\nhello\r\n".encode("utf-16"))
    entries = discover_entries([str(tmp_path)], False, "", Event())["entries"]
    result = search_entries(entries, "hello", "", False, False, Event())
    assert result["matches"][0]["line"] == 2


def test_limits_and_cancellation(tmp_path: Path) -> None:
    (tmp_path / "one.txt").write_text("hello\nhello\n")
    (tmp_path / "two.txt").write_text("")
    report = discover_entries([str(tmp_path)], False, "", Event(), limit=1)
    assert report["limited"]
    assert len(report["entries"]) == 1
    result = search_entries(report["entries"], "hello", "", False, False, Event(), limit=1)
    assert result["limited"]
    assert len(result["matches"]) == 1
    cancelled = Event()
    cancelled.set()
    assert discover_entries([str(tmp_path)], False, "", cancelled)["entries"] == []
    assert search_entries(report["entries"], "hello", "", False, False, cancelled)["matches"] == []


def test_missing_root_is_reported(tmp_path: Path) -> None:
    report = discover_entries([str(tmp_path / "missing")], False, "", Event())
    assert report["errors"]


def test_links_are_not_followed(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "text.txt").write_text("hello")
    root = tmp_path / "workspace"
    root.mkdir()
    try:
        (root / "link").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires Windows developer mode or elevated permissions")
    report = discover_entries([str(root)], True, "", Event())
    assert report["entries"] == []
    assert report["skipped"] == 1


def test_workspace_facade_async_results_and_errors(tmp_path: Path) -> None:
    # Isolate event pumping from deferred Qt Quick teardown in other tests.
    script = (
        "import runpy; "
        f"runpy.run_path({str(Path(__file__).resolve())!r})"
        f"['_check_workspace_facade']({str(tmp_path)!r})"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def _check_workspace_facade(directory: str) -> None:
    from PySide6.QtGui import QGuiApplication

    qt_app = QGuiApplication([])
    tmp_path = Path(directory)
    explorer = ProjectExplorer()
    tools = WorkspaceTools(explorer)
    errors: list[str] = []
    tools.errorOccurred.connect(errors.append)
    tools.scanFiles()
    assert "folder" in errors[-1]
    tools.search("", "", False, False)
    assert "text" in errors[-1]
    (tmp_path / "one.py").write_text("hello")
    explorer.addFolder(str(tmp_path))
    try:
        tools.search("hello", "*.py", False, False)
        assert tools.busy
        tools.scanFiles()
        assert "already running" in errors[-1]
        deadline = time.monotonic() + 5
        while tools.busy and time.monotonic() < deadline:
            QTest.qWait(10)
        assert not tools.busy
        assert len(tools.matches) == 1
        assert tools.fileCount == 1
        assert tools.isCurrent("hello", tools.matches[0]["digest"])
        assert not tools.isCurrent("changed", tools.matches[0]["digest"])
        assert tools.quickFiles("onpy")[0]["path"] == str(tmp_path / "one.py")
        assert tools.filterPaths("*.py") == [str(tmp_path / "one.py")]
        explorer.configure(True, "*.py")
        assert tools.fileCount == 0
        assert tools.matches == []
        tools.scanFiles()
        assert tools.busy
        tools.invalidate()
        deadline = time.monotonic() + 5
        while tools.busy and time.monotonic() < deadline:
            QTest.qWait(10)
        assert not tools.busy
        assert tools.fileCount == 0
        assert tools.matches == []
        assert tools.status == "Cancelled."
    finally:
        tools.shutdown()


def test_explorer_filter_keeps_ancestors_and_expansion(qt_app, tmp_path: Path) -> None:
    nested = tmp_path / "src" / "nested"
    nested.mkdir(parents=True)
    path = nested / "match.py"
    path.write_text("")
    (tmp_path / "other.txt").write_text("")
    explorer = ProjectExplorer()
    explorer.addFolder(str(tmp_path))
    expanded = explorer._expanded_paths.copy()
    explorer.setFilterPaths([str(path)])
    assert [node.path for node in explorer._items] == [
        str(tmp_path), str(tmp_path / "src"), str(nested), str(path),
    ]
    assert explorer._expanded_paths == expanded
    explorer.clearFilter()
    assert str(tmp_path / "other.txt") in [node.path for node in explorer._items]
    assert str(path) not in [node.path for node in explorer._items]
    explorer.setFilterPaths([])
    assert explorer.rowCount() == 1


def test_explorer_ignore_settings(qt_app, tmp_path: Path) -> None:
    (tmp_path / ".hidden").write_text("")
    (tmp_path / "keep.py").write_text("")
    (tmp_path / "skip.py").write_text("")
    explorer = ProjectExplorer()
    explorer.addFolder(str(tmp_path))
    assert ".hidden" not in [node.name for node in explorer._items]
    explorer.configure(True, "skip.*")
    assert ".hidden" in [node.name for node in explorer._items]
    assert "skip.py" not in [node.name for node in explorer._items]
