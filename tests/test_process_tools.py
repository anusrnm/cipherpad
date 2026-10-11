"""Portable console, Git, pin, bookmark and explorer-command regressions."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import pytest
from PySide6.QtGui import QTextCursor, QTextDocument

from cipherpad.document import DocumentManager
from cipherpad.gutter import DocumentMetrics
from cipherpad.process_tools import parse_git_status


def test_pin_model_and_close_protection(qt_app):
    manager = DocumentManager()
    first = manager.newDocument()
    pinned = manager.documentAt(first)
    manager.newDocument()
    changes = []
    errors = []
    manager.dataChanged.connect(lambda *args: changes.append(args))
    manager.errorOccurred.connect(errors.append)
    pinned.pinned = True
    assert changes and manager.data(manager.index(first), manager.PinnedRole)
    assert not manager.closeDocument(first)
    assert errors and manager.count == 2
    manager.closeAll()
    assert manager.count == 1 and manager.currentDocument is pinned
    pinned.pinned = False
    manager.closeAll()
    assert manager.count == 0


def test_bookmarks_follow_utf16_edits_and_wrap(qt_app):
    document = QTextDocument("first\nsecond\nthird")
    metrics = DocumentMetrics()
    metrics._document = document
    metrics.toggleBookmark(2)
    metrics.toggleBookmark(3)
    assert metrics.bookmarks == [2, 3]
    cursor = QTextCursor(document)
    cursor.insertText("😀\n")
    assert metrics.bookmarks == [3, 4]
    assert metrics.adjacentBookmark(4, False) == 3
    assert metrics.adjacentBookmark(3, True) == 4
    document.undo()
    assert metrics.bookmarks == [2, 3]
    document.redo()
    assert metrics.bookmarks == [3, 4]
    metrics.toggleBookmark(3)
    assert metrics.bookmarks == [4]
    metrics.clearBookmarks()
    assert metrics.adjacentBookmark(1, False) == 0


def test_bookmark_deleted_line_and_duplicate_toggle(qt_app):
    document = QTextDocument("first\nsecond\nthird")
    metrics = DocumentMetrics()
    metrics._document = document
    metrics.toggleBookmark(2)
    cursor = QTextCursor(document.findBlockByNumber(1))
    cursor.movePosition(QTextCursor.MoveOperation.NextBlock, QTextCursor.MoveMode.KeepAnchor)
    cursor.removeSelectedText()
    assert metrics.bookmarks == [2]
    metrics.toggleBookmark(2)
    assert metrics.bookmarks == []
    metrics.toggleBookmark(99)
    assert metrics.bookmarks == []


def test_porcelain_names_and_rename():
    branch, entries = parse_git_status("## main...origin/main\0 M space name.txt\0R  new ü.txt\0old ü.txt\0?? :(glob)*.txt\0".encode())
    assert branch == "main...origin/main"
    assert [entry["path"] for entry in entries] == ["space name.txt", "new ü.txt", ":(glob)*.txt"]
    assert entries[1]["oldPath"] == "old ü.txt"
    assert entries[1]["staged"] and not entries[1]["unstaged"]


@pytest.mark.parametrize("raw", [b"bad\0", b"R  new\0"])
def test_porcelain_rejects_malformed(raw):
    with pytest.raises(ValueError):
        parse_git_status(raw)


def _wait(application, condition, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        application.processEvents()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("Qt operation did not complete")


def _check_processes(directory):
    from PySide6.QtCore import QProcess
    from PySide6.QtGui import QGuiApplication
    from cipherpad.process_tools import CommandConsole, GitTools, MAX_OUTPUT

    application = QGuiApplication([])
    root = Path(directory)
    command = CommandConsole()
    errors = []
    command.errorOccurred.connect(errors.append)
    executable = sys.executable.replace("\\", "/")
    assert command.runCommand(f'"{executable}" -u -c "import os; print(os.getcwd()); print(input())"', directory)
    _wait(application, lambda: directory in command.output)
    assert command.busy
    assert not command.runCommand("git --version", directory)
    assert command.sendInput("round trip")
    _wait(application, lambda: not command.busy)
    assert "round trip" in command.output and "[Exited: 0]" in command.output
    command.clearOutput()
    assert command.runCommand(f'"{executable}" -u -c "import time; print(\'ready\'); time.sleep(60)"', directory)
    _wait(application, lambda: "ready" in command.output)
    command.stop()
    _wait(application, lambda: not command.busy)
    assert command._process.state() == QProcess.ProcessState.NotRunning
    command._append("x" * (MAX_OUTPUT + 10))
    assert command.output.startswith("[Earlier output truncated]")
    assert len(command.output) == MAX_OUTPUT
    assert not command.runCommand("cipherpad-nonexistent-program", directory)
    assert not command.runCommand("git --version", str(root / "missing"))
    assert errors
    assert command.runCommand(f'"{executable}" -u -c "import time; time.sleep(60)"', directory)
    command.shutdown()
    assert command._process.state() == QProcess.ProcessState.NotRunning

    git = GitTools()
    git_errors = []
    diffs = []
    git.errorOccurred.connect(git_errors.append)
    git.diffReady.connect(lambda text, path: diffs.append((text, path)))

    def cli(*args):
        return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)

    cli("init", "-b", "main")
    cli("config", "user.name", "Cipherpad Test")
    cli("config", "user.email", "test@example.invalid")
    cli("config", "core.autocrlf", "false")
    cli("config", "commit.gpgsign", "false")
    name = "space ü [x].txt"
    (root / name).write_text("initial\n", encoding="utf-8")
    assert git.refresh(directory)
    _wait(application, lambda: not git.busy)
    assert git.root and git.branch and git.entries[0]["path"] == name
    assert git.stage(name, False)
    _wait(application, lambda: not git.busy)
    assert git.entries[0]["staged"]
    assert git.stage(name, True)
    _wait(application, lambda: not git.busy)
    assert not git.entries[0]["staged"], git_errors
    assert git.stage(name, False)
    _wait(application, lambda: not git.busy)
    assert git.diff(name, True)
    _wait(application, lambda: not git.busy)
    assert "+initial" in diffs[-1][0]
    assert git.commit("Test initial commit")
    _wait(application, lambda: not git.busy)
    assert not git.entries
    (root / name).write_text("changed\n", encoding="utf-8")
    other = "second.txt"
    (root / other).write_text("untracked\n", encoding="utf-8")
    assert git.refresh(directory)
    _wait(application, lambda: not git.busy)
    assert not git.stage("../outside", False)
    assert git.diff(name, False)
    _wait(application, lambda: not git.busy)
    assert "-initial" in diffs[-1][0] and "+changed" in diffs[-1][0]
    assert git.stage(name, False)
    _wait(application, lambda: not git.busy)
    assert len(git.entries) == 2 and next(e for e in git.entries if e["path"] == other)["status"] == "??"
    assert git.stage(name, True)
    _wait(application, lambda: not git.busy)
    cli("mv", name, "renamed ü.txt")
    assert git.refresh(directory)
    _wait(application, lambda: not git.busy)
    assert next(e for e in git.entries if e["path"] == "renamed ü.txt")["oldPath"] == name
    assert git.stage("renamed ü.txt", False)
    _wait(application, lambda: not git.busy)
    assert git.commit("Rename and edit")
    _wait(application, lambda: not git.busy)
    assert cli("log", "-1", "--format=%s").stdout.strip() == b"Rename and edit"
    assert git_errors == ["Refresh Git status and select a changed file."], git_errors
    git_errors.clear()
    with tempfile.TemporaryDirectory() as nonrepo:
        assert git.refresh(nonrepo)
        _wait(application, lambda: not git.busy)
        assert git_errors and not git.root and not git.entries
    git.shutdown()


def _check_ui(directory):
    from PySide6.QtCore import QSettings, QUrl, Qt, QObject, QPointF, QMetaObject
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression
    from PySide6.QtTest import QTest
    from PySide6.QtQuick import QQuickItem
    from cipherpad import app, crypto, explorer, preferences, search, textops
    from cipherpad.inspection import InspectionTools
    from cipherpad.workspace import WorkspaceTools

    application = QGuiApplication([])
    original = preferences.QSettings
    preferences.QSettings = lambda *args: QSettings(str(Path(directory) / "prefs.ini"), QSettings.Format.IniFormat)
    prefs = preferences.Preferences()
    preferences.QSettings = original
    manager = DocumentManager()
    project = explorer.ProjectExplorer()
    project.bind_documents(manager)
    workspace = WorkspaceTools(project)
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda items: warnings.extend(item.toString() for item in items))
    backends = {"Prefs": prefs, "Documents": manager, "Explorer": project, "Workspace": workspace,
                "Search": search.SearchEngine(), "TextOps": textops.TextOps(), "Crypto": crypto.CryptoInfo(),
                "Inspection": InspectionTools(), "appVersion": "test"}
    for name, backend in backends.items():
        engine.rootContext().setContextProperty(name, backend)
    engine.load(QUrl.fromLocalFile(str(app.QML_DIR / "Main.qml")))
    assert engine.rootObjects(), warnings
    window = engine.rootObjects()[0]

    def evaluate(source):
        expression = QQmlExpression(engine.contextForObject(window), window, source)
        result = expression.evaluate()[0]
        assert not expression.hasError(), expression.error().toString()
        return result

    def visual_child(item, name):
        if item.objectName() == name:
            return item
        if isinstance(item, QQuickItem):
            for child in item.childItems():
                found = visual_child(child, name)
                if found is not None:
                    return found
        return None

    try:
        root = Path(directory)
        first = root / "one.txt"
        second = root / "two.txt"
        first.write_text("one\n")
        second.write_text("two\n")
        project.addFolder(directory)
        prefs.showProjectExplorer = True
        manager.openFile(str(first))
        application.processEvents()
        evaluate("currentPane.editor.text = Array.from({length: 200}, (_, i) => 'line ' + i).join('\\n'); currentPane.goToLine(1)")
        application.processEvents()
        QTest.keyClick(window, Qt.Key.Key_PageDown)
        application.processEvents()
        assert evaluate("currentPane.currentLine") > 10
        assert 0 < evaluate("currentPane.editor.cursorRectangle.y") < evaluate("currentPane.height") + 30
        QTest.keyClick(window, Qt.Key.Key_PageUp)
        application.processEvents()
        assert evaluate("currentPane.currentLine") == 1
        original_text = evaluate("currentPane.editor.text")
        QTest.keyClick(window, Qt.Key.Key_PageDown, Qt.KeyboardModifier.ShiftModifier)
        application.processEvents()
        assert evaluate("currentPane.selectionLength") > 0
        QTest.keyClick(window, Qt.Key.Key_PageUp, Qt.KeyboardModifier.ShiftModifier)
        application.processEvents()
        assert evaluate("currentPane.editor.cursorPosition") == 0
        assert evaluate("currentPane.selectionLength") == 0
        assert evaluate("currentPane.editor.text") == original_text
        manager.currentDocument._read_only = True
        manager.currentDocument.readOnlyChanged.emit()
        evaluate("currentPane.editor.cursorPosition = currentPane.editor.length")
        QTest.keyClick(window, Qt.Key.Key_PageDown)
        assert evaluate("currentPane.editor.cursorPosition === currentPane.editor.length")
        QTest.keyClick(window, Qt.Key.Key_PageUp)
        assert evaluate("currentPane.editor.cursorPosition < currentPane.editor.length")
        assert evaluate("currentPane.editor.text") == original_text
        manager.currentDocument._read_only = False
        manager.currentDocument.readOnlyChanged.emit()
        evaluate("currentPane.editor.cursorPosition = 0")
        QTest.keyClick(window, Qt.Key.Key_PageUp)
        assert evaluate("currentPane.editor.cursorPosition") == 0
        prefs.wordWrap = True
        evaluate("currentPane.editor.text = 'wrapped text '.repeat(1500); currentPane.editor.cursorPosition = 0")
        application.processEvents()
        QTest.keyClick(window, Qt.Key.Key_PageDown)
        application.processEvents()
        assert evaluate("currentPane.currentLine") == 1
        assert evaluate("currentPane.editor.cursorPosition") > 100
        assert evaluate("currentPane.editor.cursorRectangle.y") > 100
        QTest.keyClick(window, Qt.Key.Key_PageUp)
        application.processEvents()
        assert evaluate("currentPane.editor.cursorPosition") == 0
        evaluate("toggleSplit()")
        application.processEvents()
        evaluate("currentPane.editor.text = Array.from({length: 200}, (_, i) => 'split ' + i).join('\\n'); currentPane.goToLine(1)")
        split_doc = manager.currentDocument
        other_doc = manager.documentAt(1 if manager.currentIndex == 0 else 0)
        other_pane_position = evaluate("paneAt(Documents.currentIndex === 0 ? 1 : 0).editor.cursorPosition")
        QTest.keyClick(window, Qt.Key.Key_PageDown)
        assert manager.currentDocument is split_doc
        assert evaluate("currentPane.currentLine") > 1
        assert evaluate("paneAt(Documents.currentIndex === 0 ? 1 : 0).editor.cursorPosition") == other_pane_position
        evaluate("toggleSplit()")
        manager.closeDocument(manager.indexOf(other_doc))
        evaluate("currentPane.focusEditor()")
        prefs.wordWrap = False
        evaluate("runCommand('pin')")
        evaluate("closeTab(0)")
        assert manager.count == 1 and manager.currentDocument.pinned
        manager.newDocument()
        application.processEvents()
        evaluate("tabMenu.closeRange(0, Documents.count - 1, -1)")
        assert manager.count == 1
        evaluate("runCommand('pin')")
        evaluate("currentPane.editor.text = 'one\\ntwo\\nthree'; currentPane.goToLine(2); runCommand('bookmark')")
        assert evaluate("currentPane.metrics.bookmarks.join(',')") == "2"
        evaluate("currentPane.metrics.replaceRange(0, 0, 'inserted\\n')")
        assert evaluate("currentPane.metrics.bookmarks.join(',')") == "3"
        evaluate("currentPane.goToLine(1); navigateBookmark(false)")
        assert evaluate("currentPane.currentLine") == 3
        evaluate("toggleConsole()")
        application.processEvents()
        assert evaluate("showConsole && consolePanel.visible")
        executable = sys.executable.replace("\\", "/")
        command = f'"{executable}" -u -c "import time; print(\'ui ready\'); time.sleep(60)"'
        evaluate(f"consolePanel.showFor({str(root)!r})")
        window.findChild(QObject, "consoleCommand").setProperty("text", command)
        assert QMetaObject.invokeMethod(window.findChild(QObject, "consoleRunButton"), "click")
        console = window.findChild(QObject, "commandConsole")
        _wait(application, lambda: "ui ready" in console.output)
        assert console.busy
        assert QMetaObject.invokeMethod(window.findChild(QObject, "consoleStopButton"), "click")
        _wait(application, lambda: not console.busy)
        evaluate("toggleConsole()")
        evaluate("currentPane.goToLine(1)")
        application.processEvents()
        QTest.keyClick(window, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
        assert evaluate("currentPane.editor.text.startsWith('inserted\\ninserted\\n')")
        for path in (first, second):
            row = visual_child(window.contentItem(), "explorerRow:" + str(path))
            assert row is not None
            point = row.mapToScene(QPointF(row.width() / 2, row.height() / 2)).toPoint()
            QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, point)
        assert evaluate("explorerSidebar.selectedFiles.length") == 2
        assert manager.count == 1
        application.processEvents()
        before = evaluate("currentPane.editor.text")
        QTest.keyClick(window, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
        application.processEvents()
        assert evaluate("comparisonDialog.visible")
        assert "+two" in evaluate("comparisonDialog.comparison.diff")
        assert evaluate("currentPane.editor.text") == before
        evaluate("comparisonDialog.close()")
        second.unlink()
        evaluate("explorerSidebar.compareSelected()")
        assert evaluate("messageDialog.visible")
        evaluate("messageDialog.close()")
        if shutil.which("git"):
            subprocess.run(["git", "init", "-b", "main", directory], check=True, capture_output=True)
            for key, value in (("user.name", "Cipherpad UI Test"), ("user.email", "test@example.invalid"),
                               ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
                subprocess.run(["git", "-C", directory, "config", key, value], check=True, capture_output=True)
        evaluate("runCommand('git')")
        application.processEvents()
        assert evaluate("gitPanel.visible")
        git = window.findChild(QObject, "gitTools")
        _wait(application, lambda: not git.busy)
        if shutil.which("git"):
            application.processEvents()
            row = visual_child(window.contentItem(), "gitEntry:one.txt")
            assert row is not None
            assert QMetaObject.invokeMethod(row, "clicked")
            assert QMetaObject.invokeMethod(window.findChild(QObject, "gitStageButton"), "click")
            _wait(application, lambda: not git.busy)
            assert evaluate("gitPanel.selected.staged")
            assert QMetaObject.invokeMethod(window.findChild(QObject, "gitStagedDiffButton"), "click")
            _wait(application, lambda: not git.busy)
            assert evaluate("comparisonDialog.visible && comparisonDialog.comparison.unifiedOnly")
            assert "+one" in evaluate("comparisonDialog.comparison.diff")
            evaluate("comparisonDialog.close()")
            window.findChild(QObject, "gitCommitMessage").setProperty("text", "UI verified saved content")
            assert QMetaObject.invokeMethod(window.findChild(QObject, "gitCommitButton"), "click")
            confirmation = window.findChild(QObject, "gitCommitConfirm")
            assert confirmation.property("visible")
            assert QMetaObject.invokeMethod(confirmation, "accept")
            _wait(application, lambda: not git.busy)
            committed = subprocess.run(["git", "-C", directory, "show", "HEAD:one.txt"], check=True, capture_output=True)
            assert committed.stdout == first.read_bytes()
            assert evaluate("currentPane.editor.text") == before
        evaluate("gitPanel.close(); messageDialog.close()")
        assert not warnings, warnings
    finally:
        window.findChild(QObject, "commandConsole").shutdown()
        window.findChild(QObject, "gitTools").shutdown()
        window.findChild(QObject, "safetyTools").finish()
        workspace.shutdown()
        for index in range(manager.count):
            manager.documentAt(index).pinned = False
        manager.closeAll()
        window.hide()
        del engine


def _isolated(function, tmp_path):
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join([str(Path(__file__).parent), str(Path(__file__).parents[1] / "src"), environment.get("PYTHONPATH", "")])
    result = subprocess.run([sys.executable, "-c", f"from test_process_tools import {function}; {function}({str(tmp_path)!r})"],
                            capture_output=True, text=True, env=environment, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(not shutil.which("git"), reason="Git is not installed")
def test_portable_process_lifecycle_and_local_git(tmp_path):
    _isolated("_check_processes", tmp_path)


def test_tools_qml_shortcuts_and_pins(tmp_path):
    _isolated("_check_ui", tmp_path)
