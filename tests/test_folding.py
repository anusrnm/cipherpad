"""Folding detection and real Qt Quick layout regressions."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from cipherpad.folding import fold_ranges
from cipherpad.languages import LANGUAGES


@pytest.mark.parametrize(
    ("language", "text", "expected"),
    [
        ("python", "def f():\n    if True:\n        pass\n    return 1\nnext()", {1: 4, 2: 3}),
        ("yaml", "root:\n  child:\n    value: true\nnext: false", {1: 3, 2: 3}),
        ("json", '{\n  "list": [\n    1\n  ]\n}', {1: 5, 2: 4}),
        ("xml", '<root title=">">\n<br>\n<child>\ntext\n</child>\n</root>', {1: 6, 3: 5}),
        ("markdown", "# Title\nbody\n## Child\nmore\n# Next\nlast", {1: 4, 3: 4, 5: 6}),
        ("toml", "[one]\nx = 1\n[two]\ny = 2", {1: 2, 3: 4}),
        ("ini", "[one]\nx = 1\n[two]\ny = 2", {1: 2, 3: 4}),
        ("shell", "if true; then\n  for x in a; do\n    echo x\n  done\nfi", {1: 5, 2: 4}),
        ("sql", "BEGIN\n  CASE\n    WHEN x THEN y\n  END\nEND", {1: 5, 2: 4}),
        ("dockerfile", "FROM python AS build\nRUN echo ok\nFROM scratch\nCOPY . /", {1: 2, 3: 4}),
        ("diff", "diff a b\n--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new", {1: 3, 4: 6}),
        ("plain", "{\ntext\n}", {}),
        ("javascript", 'function f() {\n  const s = "}"; // }\n  /* {\n  } */\n}', {1: 5, 3: 4}),
        ("python", 'def f():\n    s = """\nnot: code\n"""\n    return s', {1: 5, 2: 4}),
    ],
)
def test_language_ranges(language, text, expected):
    assert fold_ranges(text, language) == expected


@pytest.mark.parametrize("language", [
    "c", "cpp", "csharp", "java", "groovy", "go", "rust", "javascript",
    "typescript", "qml", "css", "powershell",
])
def test_brace_languages(language):
    assert fold_ranges("outer {\n inner {\n  value\n }\n}", language) == {1: 5, 2: 4}


@pytest.mark.parametrize("language", LANGUAGES)
def test_empty_and_incomplete_input(language):
    assert fold_ranges("", language) == {}
    assert all(end > start for start, end in fold_ranges('{\n"unterminated', language).items())


def test_markdown_fence_is_not_a_heading():
    assert fold_ranges("```\n# not a heading\ncode\n```\n", "markdown") == {1: 4}
    assert fold_ranges("\n```\ncode\n```", "markdown") == {2: 4}
    assert fold_ranges("# Don't fold prose as a string\ntext\n# Next\nmore", "markdown") == {1: 2, 3: 4}


def test_quick_folding_layout():
    result = subprocess.run(
        [sys.executable, "-c",
         "import runpy; runpy.run_path(r'tests\\test_folding.py')['_check_quick_folding']()"],
        capture_output=True, text=True, timeout=60,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _check_quick_folding():
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression
    from PySide6.QtTest import QTest
    from cipherpad import gutter  # noqa: F401 - register QML type

    application = QGuiApplication([])
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda items: warnings.extend(item.toString() for item in items))
    engine.loadData(b"""
import QtQuick
import QtQuick.Controls.Basic
import Cipherpad
ApplicationWindow {
    width: 600; height: 400; visible: true
    property alias editor: editor
    property alias metrics: metrics
    TextArea {
        id: editor; width: 500; textFormat: TextEdit.PlainText; cursorVisible: false
        text: "outer {\\n inner {\\n  value\\n }\\n}\\nafter"
    }
    DocumentMetrics { id: metrics; document: editor.textDocument; language: "javascript" }
}
""", QUrl.fromLocalFile(str(Path(__file__).with_name("folding.qml"))))
    assert engine.rootObjects(), warnings
    window = engine.rootObjects()[0]

    def evaluate(source):
        expression = QQmlExpression(engine.contextForObject(window), window, source)
        result = expression.evaluate()[0]
        assert not expression.hasError(), expression.error().toString()
        application.processEvents()
        QTest.qWait(30)
        return result

    try:
        application.processEvents()
        before = evaluate("editor.contentHeight")
        text = evaluate("editor.text")
        undo = evaluate("editor.canUndo")
        document = evaluate("editor.textDocument").textDocument()
        evaluate("metrics.toggleFold(2); metrics.toggleFold(1)")
        assert not document.findBlockByNumber(1).isVisible()
        assert evaluate("editor.contentHeight") < before, (
            before, evaluate("editor.contentHeight"), document.documentLayout().documentSize()
        )
        assert evaluate("editor.text") == text
        assert evaluate("editor.canUndo") == undo
        evaluate("metrics.toggleFold(1)")
        assert document.findBlockByNumber(1).isVisible()
        assert not document.findBlockByNumber(2).isVisible()
        evaluate("metrics.revealPosition(metrics.positionForLine(3))")
        assert document.findBlockByNumber(2).isVisible()
        assert evaluate("editor.contentHeight") == before
        evaluate("metrics.foldAll(true)")
        assert not document.findBlockByNumber(4).isVisible()
        evaluate("metrics.foldAll(false)")
        assert document.findBlockByNumber(4).isVisible()
        evaluate("metrics.toggleFold(1); editor.insert(0, '// new\\n')")
        assert document.findBlockByNumber(2).isVisible()
        evaluate("metrics.toggleFold(2); metrics.language = 'plain'")
        assert document.findBlockByNumber(2).isVisible()
        assert evaluate("editor.text").endswith(text)
        evaluate("editor.text = 'outer {\\n inner {\\n  value\\n }\\n}\\nafter'; metrics.language = 'javascript'; metrics.toggleFold(1)")
        folded_image = window.grabWindow()
        assert not folded_image.isNull()
        evaluate("editor.text = 'outer {\\nafter'")
        assert window.grabWindow() == folded_image
        evaluate("editor.width = 80; editor.wrapMode = TextEdit.Wrap; editor.text = 'outer {\\n a long line that wraps over several visual lines\\n}\\nafter'")
        wrapped_height = evaluate("editor.contentHeight")
        evaluate("metrics.toggleFold(1)")
        assert evaluate("editor.contentHeight") < wrapped_height
        assert evaluate("metrics.linesIn(0, 1000).map(row => row.number).join(',')") == "1,4"
        assert not warnings, warnings
    finally:
        window.close()
        engine.deleteLater()
        application.processEvents()
