"""Selection overlays and real QML tab-wheel regressions."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QTextDocument

from cipherpad.highlighter import _Highlighter
from cipherpad.languages import get_language


@pytest.mark.parametrize(
    ("text", "needle", "expected"),
    [
        ("cat Cat catapult cat", "cat", [(0, 3), (8, 11), (17, 20)]),
        ("a+b aab a+b", "a+b", [(0, 3), (8, 11)]),
        ("\U0001f600 cat \U0001f600 cat", "cat", [(3, 6), (10, 13)]),
        ("ab\ncd ab\ncd", "ab\ncd", [(0, 5), (6, 11)]),
        ("   \n  ", " ", []),
        ("cat", "", []),
    ],
)
def test_selection_matches(qt_app, text, needle, expected):
    document = QTextDocument(text)
    document.clearUndoRedoStacks()
    highlighter = _Highlighter(document)
    before = document.toPlainText()
    matches = highlighter.set_selection(needle, "#abcdef")
    assert [(m["start"], m["end"]) for m in matches] == expected
    for match in matches:
        block = document.findBlock(match["start"])
        offset = match["start"] - block.position()
        assert any(
            span.start <= offset < span.start + span.length
            and span.format.background().color() == QColor("#abcdef")
            for span in block.layout().formats()
        )
    assert document.toPlainText() == before
    assert not document.isUndoAvailable()
    assert highlighter.set_selection("", "#abcdef") == []
    assert not highlighter._selection_blocks


def test_overlay_preserves_syntax_and_search(qt_app):
    import re

    document = QTextDocument("return 42")
    highlighter = _Highlighter(document)
    highlighter.set_language(get_language("python"))
    highlighter.set_selection("return 42", "#abcdef")
    spans = document.firstBlock().layout().formats()
    assert spans[0].format.foreground().color() != spans[-1].format.foreground().color()
    highlighter.set_search(re.compile("42"), "#fedcba")
    assert document.firstBlock().layout().formats()[-1].format.background().color() == QColor("#fedcba")
    highlighter.set_search(None, "#fedcba")
    assert document.firstBlock().layout().formats()[-1].format.background().color() == QColor("#abcdef")
    highlighter.set_enabled(False)
    assert document.firstBlock().layout().formats()[0].format.background().color() == QColor("#abcdef")


def test_editor_navigation_ui(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c",
         "import runpy; runpy.run_path(r'tests\\test_editor_navigation.py')"
         f"['_check_ui']({str(tmp_path)!r})"],
        capture_output=True, text=True, timeout=60,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _check_ui(directory):
    from PySide6.QtCore import QObject, QPoint, QPointF, QSettings, Qt, QUrl
    from PySide6.QtGui import QGuiApplication, QWheelEvent
    from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression
    from PySide6.QtTest import QTest
    from cipherpad import app, crypto, document, explorer, preferences, search, textops
    from cipherpad.inspection import InspectionTools
    from cipherpad.workspace import WorkspaceTools

    application = QGuiApplication([])
    original = preferences.QSettings
    preferences.QSettings = lambda *args: QSettings(
        str(Path(directory) / "prefs.ini"), QSettings.Format.IniFormat,
    )
    prefs = preferences.Preferences()
    preferences.QSettings = original
    manager = document.DocumentManager()
    project = explorer.ProjectExplorer()
    project.bind_documents(manager)
    workspace = WorkspaceTools(project)
    backends = {
        "Prefs": prefs, "Documents": manager, "Explorer": project, "Workspace": workspace,
        "Search": search.SearchEngine(), "TextOps": textops.TextOps(), "Crypto": crypto.CryptoInfo(),
        "Inspection": InspectionTools(), "appVersion": "test",
    }
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda items: warnings.extend(item.toString() for item in items))
    for name, backend in backends.items():
        engine.rootContext().setContextProperty(name, backend)
    engine.load(QUrl.fromLocalFile(str(app.QML_DIR / "Main.qml")))
    assert engine.rootObjects(), warnings
    window = engine.rootObjects()[0]

    def evaluate(source):
        expression = QQmlExpression(engine.contextForObject(window), window, source)
        value = expression.evaluate()[0]
        assert not expression.hasError(), expression.error().toString()
        return value

    def wheel(delta, pixels=QPoint()):
        tabs = window.findChild(QObject, "documentTabs")
        position = tabs.mapToScene(QPointF(tabs.width() / 2, 15))
        event = QWheelEvent(
            position, position, pixels, delta, Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False,
        )
        QGuiApplication.sendEvent(window, event)
        QTest.qWait(50)
        assert tabs.y() == 0
        assert tabs.property("contentY") == 0
        assert 0 <= tabs.property("contentX") <= max(0, tabs.property("contentWidth") - tabs.width())
        return tabs

    try:
        manager.newDocument()
        QTest.qWait(200)
        wheel(QPoint(0, -120))
        wheel(QPoint(0, 120))
        for _ in range(12):
            manager.newDocument()
        QTest.qWait(200)
        evaluate("tabBar.positionViewAtBeginning()")
        tabs = wheel(QPoint(0, -120))
        assert tabs.property("contentX") > 0
        evaluate("tabBar.positionViewAtBeginning()")
        assert wheel(QPoint(-120, 0)).property("contentX") > 0
        evaluate("tabBar.positionViewAtBeginning()")
        assert wheel(QPoint(), QPoint(0, -60)).property("contentX") > 0
        for _ in range(20):
            wheel(QPoint(0, -120))
        for _ in range(20):
            wheel(QPoint(0, 120))
        assert tabs.property("contentX") == 0
        manager.currentIndex = 0
        manager.currentIndex = 12
        QTest.qWait(100)
        assert tabs.property("contentX") > 0
        assert evaluate("tabBar.itemAtIndex(12).x + 180 <= tabBar.contentX + tabBar.width + 1")
        assert evaluate("tabBar.itemAtIndex(12).x >= tabBar.contentX - 1")

        text = "\n".join("target" if i in (0, 80, 160) else f"line {i}" for i in range(200))
        evaluate("currentPane.editor.insert(0, " + json.dumps(text) + ")")
        evaluate("currentPane.editor.select(0, 6)")
        QTest.qWait(250)
        pane = window.property("currentPane")
        highlighter = pane.findChild(QObject, "selectionHighlighter")
        matches = highlighter.property("selectionMatches")
        assert len(matches) == 3, matches
        overview = pane.findChild(QObject, "selectionOverview")
        assert overview.width() == 8
        assert evaluate("currentPane.editor.text") == text
        assert evaluate("currentPane.editor.canUndo")
        position = overview.mapToScene(QPointF(4, overview.height() * 0.8))
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=position.toPoint())
        QTest.qWait(250)
        assert evaluate("currentPane.editor.selectionStart") == matches[-1]["start"]
        assert evaluate("currentPane.currentLine") == 161
        evaluate("currentPane.applySearchHighlight('line', false, false, false)")
        QTest.qWait(150)
        assert len(highlighter.property("selectionMatches")) == 3
        evaluate("currentPane.applySearchHighlight('', false, false, false)")
        evaluate("currentPane.editor.deselect()")
        QTest.qWait(200)
        assert not highlighter.property("selectionMatches")
        assert overview.width() == 0
        evaluate("currentPane.editor.select(0, 6)")
        QTest.qWait(200)
        evaluate("currentPane.metrics.replaceRange(0, 6, 'other')")
        evaluate("currentPane.editor.select(0, 5)")
        QTest.qWait(200)
        assert evaluate("currentPane.editor.selectedText") == "other"
        assert len(highlighter.property("selectionMatches")) == 1
        evaluate("currentPane.editor.undo()")
        QTest.qWait(200)
        evaluate("currentPane.editor.deselect()")
        evaluate("currentPane.editor.undo()")
        QTest.qWait(200)
        assert evaluate("currentPane.editor.text") == ""
        assert not highlighter.property("selectionMatches")
        evaluate("currentPane.editor.insert(0, 'ab\\ncd ab\\ncd')")
        evaluate("currentPane.editor.select(0, 5)")
        QTest.qWait(200)
        assert len(highlighter.property("selectionMatches")) == 2
        assert not warnings, warnings
    finally:
        workspace.shutdown()
        window.close()
        engine.deleteLater()
        application.processEvents()
