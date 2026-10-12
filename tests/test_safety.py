"""Recovery policy, memory locking and clipboard ownership regressions."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest

from cipherpad import crypto
from cipherpad.document import Document, DocumentManager
from cipherpad.safety import CLIPBOARD_TAG, MAX_SNAPSHOT_BYTES, SafetyTools


@pytest.fixture
def safety(qt_app, tmp_path):
    tools = SafetyTools(directory=tmp_path / "recovery")
    yield tools
    tools.finish()


def test_memory_lock_preserves_unsaved_content_and_blocks_io(qt_app, tmp_path):
    doc = Document()
    target = tmp_path / "note.enc"
    assert doc.saveAs(str(target), "saved", True, "secret")
    original = target.read_bytes()
    doc.modified = True
    loaded = []
    doc.contentLoaded.connect(loaded.append)
    assert doc.lock("unsaved \U0001f600\n")
    assert doc.locked and doc.encrypted and doc.modified
    assert not doc.hasPassphrase
    assert doc.takeContent() == "" and loaded == [""]
    assert b"unsaved" not in doc._locked_buffer
    assert not doc.save("")
    assert not doc.saveAs(str(tmp_path / "plain.txt"), "")
    assert not doc.removeEncryption("")
    assert not doc.changePassphrase("", "new")
    assert not doc.reload()
    assert doc.diskSnapshot()["error"]
    assert target.read_bytes() == original
    assert not (tmp_path / "plain.txt").exists()
    assert not doc.unlock("wrong")
    assert doc.locked and doc.modified and not doc.hasPassphrase
    assert doc.unlock("secret")
    assert doc.takeContent() == "unsaved \U0001f600\n"
    assert doc.modified and not doc.locked and doc.hasPassphrase
    assert doc.save(doc.takeContent())
    assert crypto.decrypt(target.read_bytes(), "secret").decode() == "unsaved \U0001f600\n"
    doc.close()
    assert not doc._locked_buffer and not doc.takeContent() and not doc.hasPassphrase


def test_clean_lock_and_plain_tab_refusal(qt_app, tmp_path):
    doc = Document()
    assert not doc.lock("ordinary")
    assert doc.saveAs(str(tmp_path / "clean.enc"), "", True, "pass")
    assert doc.lock("")
    assert doc.lock("")
    assert doc.unlock("pass")
    assert not doc.modified
    doc.close()


def test_snapshot_policy_and_cleanup(safety, tmp_path):
    doc = Document()
    doc.modified = True
    assert safety.snapshot(doc, "ordinary", True)
    files = list(safety._root.rglob("*.json"))
    assert len(files) == 1
    assert '"text": "ordinary"' in files[0].read_text()
    timestamp = files[0].stat().st_mtime_ns
    assert safety.snapshot(doc, "ordinary", True)
    assert files[0].stat().st_mtime_ns == timestamp
    assert doc.saveAs(str(tmp_path / "encrypted.enc"), "ordinary", True, "secret")
    assert not list(safety._root.rglob("*.json"))
    doc.modified = True
    assert safety.snapshot(doc, "sensitive plaintext", True)
    assert not list(safety._root.rglob("*.json"))
    assert doc.lock("locked plaintext")
    assert safety.snapshot(doc, "", True)
    assert not list(safety._root.rglob("*.json"))
    doc.close()


def test_save_close_and_disable_remove_snapshots(safety, tmp_path):
    for cleanup in ("save", "close", "disable"):
        doc = Document()
        doc.modified = True
        assert safety.snapshot(doc, "unsaved", True)
        if cleanup == "save":
            assert doc.saveAs(str(tmp_path / "saved.txt"), "unsaved")
        elif cleanup == "close":
            doc.close()
        else:
            assert safety.snapshot(doc, "unsaved", False)
        assert not list(safety._root.rglob("*.json"))
        doc.close()


def test_recovery_skips_live_sessions_and_restores_without_overwriting(safety, qt_app, tmp_path):
    manager = DocumentManager()
    old = SafetyTools(directory=safety._root)
    doc = Document()
    target = tmp_path / "original.txt"
    assert doc.saveAs(str(target), "disk")
    doc.modified = True
    assert old.snapshot(doc, "unsaved", True)
    assert safety.availableRecovery() == []
    # Releasing the lock without normal cleanup simulates an interrupted session.
    old._lock.unlock()
    entries = safety.availableRecovery()
    assert len(entries) == 1
    assert entries[0]["title"] == "original.txt"
    assert safety.resolveRecovery(entries[0]["id"], manager, True)
    recovered = manager.currentDocument
    assert recovered.isUntitled and recovered.modified
    assert recovered.takeContent() == "unsaved"
    assert recovered.displayName == "Recovered - original.txt"
    assert target.read_text() == "disk"
    assert not safety.availableRecovery()
    assert list(safety._session_directory().glob("*.json"))
    manager.closeAll()
    old.finish()
    doc.close()


def test_corrupt_recovery_is_visible_and_discardable(safety, qt_app):
    manager = DocumentManager()
    folder = safety._root / uuid.uuid4().hex
    folder.mkdir(parents=True)
    path = folder / (uuid.uuid4().hex + ".json")
    path.write_text("{bad")
    entries = safety.availableRecovery()
    assert len(entries) == 1 and entries[0]["error"]
    assert not safety.resolveRecovery(entries[0]["id"], manager, True)
    assert manager.count == 0 and path.exists()
    assert safety.resolveRecovery(entries[0]["id"], manager, False)
    assert not path.exists()
    assert not safety.resolveRecovery("../outside:bad", manager, False)


def test_snapshot_limit_reports_error(safety):
    messages = []
    safety.errorOccurred.connect(messages.append)
    doc = Document()
    doc.modified = True
    assert not safety.snapshot(doc, "x" * MAX_SNAPSHOT_BYTES, True)
    assert messages and "limit" in messages[-1]
    assert not list(safety._root.rglob("*.json"))
    doc.close()


def _make_crash_snapshot(directory):
    qt_app = QGuiApplication([])
    tools = SafetyTools(directory=Path(directory))
    doc = Document("Interrupted")
    doc.modified = True
    assert tools.snapshot(doc, "crash edits", True)
    assert qt_app is not None
    os._exit(0)


def test_actual_process_exit_leaves_recoverable_snapshot(safety, qt_app):
    _run_isolated("_make_crash_snapshot", safety._root)
    entries = safety.availableRecovery()
    assert len(entries) == 1
    manager = DocumentManager()
    assert safety.resolveRecovery(entries[0]["id"], manager, True)
    assert manager.currentDocument.takeContent() == "crash edits"
    assert manager.currentDocument.modified
    manager.closeAll()


def _check_clipboard(directory):
    qt_app = QGuiApplication([])
    safety = SafetyTools(directory=Path(directory))
    clipboard = QGuiApplication.clipboard()
    safety.copyText("sensitive", True, 1)
    assert clipboard.text() == "sensitive"
    assert clipboard.mimeData().hasFormat(CLIPBOARD_TAG)
    QTest.qWait(1150)
    assert clipboard.text() == ""
    safety.copyText("same text", True, 1)
    clipboard.setText("same text")
    QTest.qWait(1150)
    assert clipboard.text() == "same text"
    safety.copyText("secret", True, 30)
    clipboard.setText("another application")
    safety.expireClipboard()
    assert clipboard.text() == "another application"
    safety.copyText("ordinary", False, 30)
    safety.expireClipboard()
    assert clipboard.text() == "ordinary"
    safety.copyText("opted out", True, 0)
    safety.expireClipboard()
    assert clipboard.text() == "opted out"
    clipboard.clear()
    safety.finish()
    assert qt_app is not None


def test_sensitive_clipboard_timer_and_replacement(tmp_path):
    _run_isolated("_check_clipboard", tmp_path)


def _check_safety_ui(directory: str) -> None:
    from PySide6.QtCore import QMetaObject, QObject, QSettings, QStandardPaths, Qt, QUrl
    from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression
    from PySide6.QtQuick import QQuickItem
    from cipherpad import app, explorer, preferences, search, textops
    from cipherpad.inspection import InspectionTools
    from cipherpad.workspace import WorkspaceTools

    QStandardPaths.setTestModeEnabled(True)
    qt_app = QGuiApplication([])
    original_settings = preferences.QSettings
    preferences.QSettings = lambda *args: QSettings(str(Path(directory) / "prefs.ini"), QSettings.Format.IniFormat)
    prefs = preferences.Preferences()
    preferences.QSettings = original_settings
    manager = DocumentManager()
    project = explorer.ProjectExplorer()
    project.bind_documents(manager)
    workspace = WorkspaceTools(project)
    backends = {
        "Prefs": prefs, "Documents": manager, "Explorer": project, "Workspace": workspace,
        "Search": search.SearchEngine(), "TextOps": textops.TextOps(),
        "Crypto": crypto.CryptoInfo(), "Inspection": InspectionTools(), "appVersion": "test",
    }
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda items: warnings.extend(item.toString() for item in items))
    for name, backend in backends.items():
        engine.rootContext().setContextProperty(name, backend)
    engine.load(QUrl.fromLocalFile(str(app.QML_DIR / "Main.qml")))
    assert engine.rootObjects(), warnings
    window = engine.rootObjects()[0]
    tools = window.findChild(QObject, "safetyTools")
    tools._root = Path(directory) / "recovery"

    def evaluate(expression):
        expr = QQmlExpression(engine.contextForObject(window), window, expression)
        result = expr.evaluate()
        assert not expr.hasError(), expr.error().toString()
        return result[0]

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
        explorer_root = Path(directory) / "keyboard-project"
        source_dir = explorer_root / "src"
        source_dir.mkdir(parents=True)
        source_file = source_dir / "sample.py"
        source_file.write_text("print('keyboard')", encoding="utf-8")
        final_file = explorer_root / "notes.txt"
        final_file.write_text("opened with Enter", encoding="utf-8")
        assert project.addFolder(str(explorer_root))
        qt_app.processEvents()
        tree = visual_child(window.contentItem(), "projectExplorerTree")
        assert tree is not None
        tree.forceActiveFocus()
        QTest.keyClick(window, Qt.Key.Key_Down)
        assert evaluate("explorerSidebar.selectedPath") == str(explorer_root)
        QTest.keyClick(window, Qt.Key.Key_Down)
        assert evaluate("explorerSidebar.selectedPath") == str(source_dir)
        QTest.keyClick(window, Qt.Key.Key_Right)
        assert project.count == 4
        QTest.keyClick(window, Qt.Key.Key_Right)
        assert evaluate("explorerSidebar.selectedPath") == str(source_file)
        QTest.keyClick(window, Qt.Key.Key_Left)
        assert evaluate("explorerSidebar.selectedPath") == str(source_dir)
        QTest.keyClick(window, Qt.Key.Key_Left)
        assert project.count == 3
        QTest.keyClick(window, Qt.Key.Key_Right)
        assert project.count == 4
        QTest.keyClick(window, Qt.Key.Key_Left)
        assert project.count == 3
        QTest.keyClick(window, Qt.Key.Key_End)
        assert evaluate("explorerSidebar.selectedPath") == str(final_file)
        QTest.keyClick(window, Qt.Key.Key_Return)
        assert manager.currentDocument.filePath == str(final_file)
        manager.closeDocument(manager.currentIndex)
        project.clearFolders()

        manager.newDocument()
        qt_app.processEvents()
        evaluate('currentPane.editor.text = "ordinary edits"; captureRecovery()')
        assert len(list(tools._root.rglob("*.json"))) == 1
        prefs.recoveryEnabled = False
        assert not list(tools._root.rglob("*.json"))
        prefs.recoveryEnabled = True
        assert len(list(tools._root.rglob("*.json"))) == 1
        old = SafetyTools(directory=tools._root)
        interrupted = Document("Interrupted UI")
        interrupted.modified = True
        assert old.snapshot(interrupted, "recovered buffer", True)
        old._lock.unlock()
        evaluate("showRecovery()")
        assert evaluate("recoveryDialog.visible && recoveryDialog.entries.length === 1")
        qt_app.processEvents()
        button = visual_child(window.contentItem(), "recoveryRestoreButton")
        assert button is not None
        assert QMetaObject.invokeMethod(button, "click")
        qt_app.processEvents()
        assert evaluate("currentPane.editor.text") == "recovered buffer"
        assert manager.currentDocument.modified and manager.currentDocument.isUntitled
        manager.closeDocument(manager.currentIndex)
        old.finish()
        interrupted.close()
        doc = manager.currentDocument
        assert doc.saveAs(str(Path(directory) / "secret.enc"), "saved", True, "pass")
        assert not list(tools._root.rglob("*.json"))
        evaluate('currentPane.editor.text = "# unsaved secret"; currentDoc.language = "markdown"')
        evaluate('runCommand("markdown")')
        QTest.qWait(250)
        assert "unsaved secret" in evaluate("markdownPreview.rendered")
        preview = window.findChild(QObject, "markdownRendered")
        assert QMetaObject.invokeMethod(preview, "selectAll")
        assert QMetaObject.invokeMethod(preview, "forceActiveFocus")
        QTest.keyClick(window, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        assert "unsaved secret" in QGuiApplication.clipboard().text()
        assert QGuiApplication.clipboard().mimeData().hasFormat(CLIPBOARD_TAG)
        tools.expireClipboard()
        assert QGuiApplication.clipboard().text() == ""
        evaluate("comparePaneWithDisk(currentPane, false)")
        diff = window.findChild(QObject, "comparisonDiff")
        assert QMetaObject.invokeMethod(diff, "selectAll")
        assert QMetaObject.invokeMethod(diff, "forceActiveFocus")
        QTest.keyClick(window, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        assert "unsaved secret" in QGuiApplication.clipboard().text()
        assert QGuiApplication.clipboard().mimeData().hasFormat(CLIPBOARD_TAG)
        evaluate("comparisonDialog.close()")
        evaluate("currentPane.editor.selectAll(); currentPane.focusEditor()")
        QTest.keyClick(window, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        assert QGuiApplication.clipboard().text() == "# unsaved secret"
        assert QGuiApplication.clipboard().mimeData().hasFormat(CLIPBOARD_TAG)
        QTest.keyClick(window, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
        assert evaluate("currentPane.editor.text") == ""
        evaluate("currentPane.editor.undo()")
        assert evaluate("currentPane.editor.text") == "# unsaved secret"
        evaluate("captureRecovery()")
        assert not list(tools._root.rglob("*.json"))
        QTest.keyClick(window, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
        QTest.qWait(30)
        assert doc.locked and doc.modified, (doc.locked, doc.modified, manager.currentIndex,
                                            evaluate("lockTabAction.enabled"), warnings)
        assert evaluate("paneAt(0).editor.text") == ""
        assert evaluate("paneAt(0)._lastKnownText") == ""
        assert not evaluate("paneAt(0).editor.canUndo")
        assert evaluate("markdownPreview.rendered") == ""
        assert not evaluate("editableDocument")
        assert not doc.unlock("bad")
        assert doc.locked
        evaluate("messageDialog.close()")
        assert QMetaObject.invokeMethod(window.findChild(QObject, "lockTabButton"), "click")
        assert evaluate("unlockTabDialog.visible")
        evaluate('unlockTabDialog.passphraseAccepted("pass")')
        evaluate("unlockTabDialog.close()")
        assert not doc.locked and doc.modified
        assert evaluate("currentPane.editor.text") == "# unsaved secret"
        assert not evaluate("currentPane.editor.canUndo")
        assert evaluate("saveCurrent()")
        assert not doc.modified
        assert crypto.decrypt((Path(directory) / "secret.enc").read_bytes(), "pass").decode() == "# unsaved secret"
        evaluate('currentDoc.language = "json"; currentPane.editor.text = \'{"secret":1}\'')
        evaluate("showJsonTree()")
        assert evaluate("jsonTreeDialog.sensitive")
        evaluate('jsonTreeDialog.selectedPointer = "/secret"')
        assert QMetaObject.invokeMethod(window.findChild(QObject, "jsonTreeCopyPointerButton"), "click")
        assert QGuiApplication.clipboard().text() == "/secret"
        assert QGuiApplication.clipboard().mimeData().hasFormat(CLIPBOARD_TAG)
        evaluate("toggleTabLock()")
        assert not evaluate("jsonTreeDialog.visible")
        assert evaluate("jsonTreeDialog.nodes.length") == 0
        evaluate("window.close()")
        assert evaluate("unsavedDialog.visible")
        evaluate("window.close()")
        assert evaluate("unsavedDialog.visible")
        assert window.isVisible()
        evaluate("unsavedDialog.reject()")
        assert not warnings, warnings
    finally:
        tools.finish()
        workspace.shutdown()
        window.hide()
        manager.closeAll()
        del engine


def _run_isolated(function, tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1] / "src"), env.get("PYTHONPATH", "")])
    result = subprocess.run(
        [sys.executable, "-c", f"import sys; from test_safety import {function}; {function}(sys.argv[1])", str(tmp_path)],
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_safety_qml(tmp_path):
    _run_isolated("_check_safety_ui", tmp_path)
