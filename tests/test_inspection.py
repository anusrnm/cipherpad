"""Structured validation, offline preview and read-only comparison."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from cipherpad import crypto
from cipherpad.document import Document, read_disk_snapshot
from cipherpad.inspection import InspectionTools, compare_text, json_nodes, validate_document


@pytest.mark.parametrize("text,language", [('{"a": [1, true, null]}', "json"), ("<root><item/></root>", "xml")])
def test_syntax_validation(text: str, language: str) -> None:
    assert validate_document(text, language)["valid"]


def test_syntax_error_locations() -> None:
    result = validate_document('{\n"a": }\n', "json")
    assert not result["valid"]
    assert (result["line"], result["column"]) == (2, 6)
    result = validate_document("<root>\n</wrong>", "xml")
    assert not result["valid"]
    assert result["line"] == 2
    assert result["column"] > 0
    assert not validate_document('{"a": NaN}', "json")["valid"]
    assert not validate_document('{"a": Infinity}', "json")["valid"]


def test_xml_no_entities(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("DO NOT READ")
    text = f'<!DOCTYPE root [<!ENTITY leak SYSTEM "{secret.as_uri()}">]><root>&leak;</root>'
    result = validate_document(text, "xml")
    assert not result["valid"]
    assert "DOCTYPE" in result["error"]
    assert "DO NOT READ" not in result["error"]


def test_json_schema(tmp_path: Path) -> None:
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps({"type": "object", "properties": {"age": {"type": "integer"}}, "required": ["age"]}))
    assert validate_document('{"age": 4}', "json", schema.as_uri())["valid"]
    result = validate_document('{"age": "four"}', "json", str(schema))
    assert not result["valid"]
    assert result["instancePath"] == "/age"
    assert result["line"] == 0
    schema.write_text('{"$ref": "https://example.com/schema.json"}')
    assert "same-document" in validate_document("{}", "json", str(schema))["error"]
    schema.write_text('{"$defs":{"x":{"type":"integer"}},"$ref":"#/$defs/x"}')
    assert validate_document("3", "json", str(schema))["valid"]
    schema.write_text('{"$ref":"#/$defs/missing"}')
    assert not validate_document("3", "json", str(schema))["valid"]
    schema.write_text('{"type": "not-a-type"}')
    assert not validate_document("3", "json", str(schema))["valid"]
    schema.write_text("{broken")
    broken = validate_document("3", "json", str(schema))
    assert not broken["valid"]
    assert broken["line"] == 0
    assert "Schema error" in broken["error"]
    assert not validate_document("3", "json", str(tmp_path / "missing"))["valid"]


def test_xml_schema(tmp_path: Path) -> None:
    schema = tmp_path / "schema.xsd"
    schema.write_text(
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        '<xs:element name="age" type="xs:integer"/></xs:schema>'
    )
    assert validate_document("<age>42</age>", "xml", str(schema))["valid"]
    result = validate_document("<age>not-a-number</age>", "xml", str(schema))
    assert not result["valid"]
    assert result["line"] == 1
    assert validate_document('<?xml version="1.0" encoding="UTF-16"?><age>42</age>', "xml", str(schema))["valid"]
    schema.write_text(
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        '<xs:include schemaLocation="https://example.com/schema.xsd"/></xs:schema>'
    )
    assert "includes/imports" in validate_document("<age>42</age>", "xml", str(schema))["error"]


def test_inspection_limits() -> None:
    assert not validate_document(" " * 2_000_001, "json")["valid"]
    assert not validate_document("text", "plain")["valid"]
    assert compare_text("x" * 2_000_001, "", "a", "b")["error"]
    assert compare_text("\n" * 20_001, "", "a", "b")["error"]


def test_json_tree_types_paths_and_limits() -> None:
    result = json_nodes('{"a/b": [true, null, 2, "hello"], "~": {}}')
    nodes = result["nodes"]
    assert not result["error"]
    assert nodes[0]["container"] and nodes[0]["parent"] == -1
    assert nodes[1]["pointer"] == "/a~1b"
    assert nodes[2]["pointer"] == "/a~1b/0"
    assert "boolean" in nodes[2]["label"]
    assert "null" in nodes[3]["label"]
    assert nodes[-1]["pointer"] == "/~0"
    assert json_nodes("[1,2,3]", limit=2)["limited"]
    assert json_nodes("{broken")["error"]
    assert len(json_nodes("1")["nodes"]) == 1
    precise = json_nodes('{"same": 1e999, "same": 1.2300, "long": ' + "9" * 5000 + "}")
    assert len(precise["nodes"]) == 4
    assert precise["nodes"][1]["label"] == "same: number = 1e999"
    assert precise["nodes"][2]["label"] == "same: number = 1.2300"
    assert "valid JSON number" in json_nodes("NaN")["error"]
    assert not json_nodes("[1,2]", limit=3)["limited"]


def test_diff_exact_output() -> None:
    result = compare_text("same\nold\n", "same\nnew\n", "disk", "editor")
    assert result["diff"] == "--- disk\n+++ editor\n@@ -1,2 +1,2 @@\n same\n-old\n+new\n"
    assert not result["equal"]
    assert compare_text("same\n", "same\n", "a", "b")["equal"]
    result = compare_text("same", "same\n", "a", "b")
    assert "\\ No newline at end of file\n" in result["diff"]
    assert result["left"] == "same"
    assert result["right"] == "same\n"


def test_disk_snapshot_preserves_document_state(qt_app, tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    document = Document()
    assert document.saveAs(str(path), "original")
    document.modified = True
    path.write_bytes(b"external\r\nchange")
    snapshot = document.diskSnapshot()
    assert snapshot == {"error": "", "text": "external\nchange"}
    assert document.modified
    assert document.takeContent() == "original"
    assert document.filePath == str(path)
    document.close()


def test_encrypted_snapshot_stays_in_memory(qt_app, tmp_path: Path) -> None:
    path = tmp_path / "secret.enc"
    document = Document()
    assert document.saveAs(str(path), "secret", True, "passphrase")
    path.write_bytes(crypto.encrypt(b"external secret", "passphrase"))
    assert document.diskSnapshot()["text"] == "external secret"
    assert document.takeContent() == "secret"
    assert set(tmp_path.iterdir()) == {path}
    assert read_disk_snapshot(str(path))["error"]
    path.write_bytes(crypto.encrypt(b"new key", "different"))
    assert document.diskSnapshot()["error"]
    document.close()


def test_disk_snapshot_errors_and_encoding(qt_app, tmp_path: Path) -> None:
    assert Document().diskSnapshot()["error"]
    assert read_disk_snapshot(str(tmp_path / "missing"))["error"]
    path = tmp_path / "binary"
    path.write_bytes(b"\x00binary")
    assert read_disk_snapshot(str(path))["error"]
    path.write_bytes("wide\ntext".encode("utf-16"))
    assert read_disk_snapshot(str(path))["text"] == "\ufeffwide\ntext"
    path.write_bytes(b"x" * 8_000_001)
    assert read_disk_snapshot(str(path))["error"]


def test_markdown_offline(qt_app) -> None:
    tools = InspectionTools()
    result = tools.markdown("# Heading\n\n**bold**\n\n- one\n- two\n\n![secret](https://example.com/image.png)")
    assert not result["error"]
    assert "Heading" in result["html"] and "<ul" in result["html"]
    assert "<img" not in result["html"]
    assert "Image omitted" in result["html"]
    assert tools.markdown("x" * 2_000_001)["error"]


def test_inspection_ui(tmp_path: Path) -> None:
    script = (
        "import runpy; "
        f"runpy.run_path({str(Path(__file__).resolve())!r})"
        f"['_check_inspection_ui']({str(tmp_path)!r})"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def _check_inspection_ui(directory: str) -> None:
    from PySide6.QtCore import QMetaObject, QObject, QSettings, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression
    from PySide6.QtTest import QTest
    from cipherpad import app, preferences, explorer, search, textops
    from cipherpad.document import DocumentManager
    from cipherpad.workspace import WorkspaceTools

    qt_app = QGuiApplication([])
    original_settings = preferences.QSettings
    preferences.QSettings = lambda *args: QSettings(str(Path(directory) / "prefs.ini"), QSettings.Format.IniFormat)
    prefs = preferences.Preferences()
    preferences.QSettings = original_settings
    manager = DocumentManager()
    project_explorer = explorer.ProjectExplorer()
    project_explorer.bind_documents(manager)
    workspace = WorkspaceTools(project_explorer)
    backends = {
        "Prefs": prefs, "Documents": manager, "Explorer": project_explorer,
        "Search": search.SearchEngine(), "TextOps": textops.TextOps(),
        "Crypto": crypto.CryptoInfo(), "Workspace": workspace,
        "Inspection": InspectionTools(), "appVersion": "test",
    }
    engine = QQmlApplicationEngine()
    warnings: list[str] = []
    engine.warnings.connect(lambda items: warnings.extend(item.toString() for item in items))
    for name, backend in backends.items():
        engine.rootContext().setContextProperty(name, backend)
    engine.addImportPath(str(app.QML_DIR))
    engine.load(QUrl.fromLocalFile(str(app.QML_DIR / "Main.qml")))
    assert engine.rootObjects(), warnings
    window = engine.rootObjects()[0]

    def evaluate(expression: str):
        expr = QQmlExpression(engine.contextForObject(window), window, expression)
        value = expr.evaluate()
        assert not expr.hasError(), expr.error().toString()
        return value[0]

    try:
        first = manager.newDocument()
        qt_app.processEvents()
        evaluate('currentPane.editor.text = "left buffer"')
        second = manager.newDocument()
        qt_app.processEvents()
        evaluate('currentPane.editor.text = "right buffer"')
        evaluate(f"Documents.currentIndex = {first}")
        QTest.keyClick(window, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
        QTest.qWait(30)
        assert evaluate("splitEditors")
        assert evaluate("paneAt(0).visible && paneAt(1).visible")
        assert evaluate("paneAt(0).width < paneAt(0).parent.width")
        evaluate("paneAt(1).focusEditor()")
        assert manager.currentIndex == second
        evaluate('currentPane.editor.text = "right edited"')
        assert evaluate('paneAt(0).editor.text') == "left buffer"
        evaluate('currentPane.metrics.replaceRange(0, 5, "RIGHT")')
        QTest.keyClick(window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        assert evaluate('paneAt(1).editor.text') == "right edited"
        right_path = Path(directory) / "right.txt"
        assert manager.currentDocument.saveAs(str(right_path), "right edited")
        evaluate('currentPane.metrics.replaceRange(0, 5, "RIGHT")')
        QTest.keyClick(window, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
        assert right_path.read_text() == "RIGHT edited"
        assert evaluate('paneAt(0).editor.text') == "left buffer"
        assert evaluate("paneAt(0).doc.modified")
        evaluate('currentPane.metrics.replaceRange(0, 5, "right")')
        evaluate("paneAt(0).focusEditor()")
        assert manager.currentIndex == first
        assert QMetaObject.invokeMethod(window.findChild(QObject, "splitEditorsButton"), "click")
        assert not evaluate("splitEditors")
        assert evaluate("paneAt(0).visible && !paneAt(1).visible")
        assert evaluate("paneAt(1).editor.text") == "right edited"
        evaluate("toggleSplit()")
        third = manager.newDocument()
        qt_app.processEvents()
        assert evaluate("leftDocument === Documents.documentAt(2)")
        assert evaluate("paneAt(2).visible && paneAt(1).visible && !paneAt(0).visible")
        manager.closeDocument(third)
        qt_app.processEvents()
        assert not evaluate("splitEditors")
        manager.currentIndex = first

        evaluate('currentDoc.language = "json"; currentPane.editor.text = \'{\\n"a": }\'')
        evaluate('runCommand("validate")')
        assert evaluate("validationDialog.visible && !validationDialog.validationResult.valid")
        assert evaluate("validationDialog.validationResult.line") == 2
        assert QMetaObject.invokeMethod(window.findChild(QObject, "validationGotoButton"), "click")
        assert evaluate("currentPane.currentLine") == 2
        evaluate('currentPane.editor.text = \'{"nested":[1,2]}\'')
        evaluate('runCommand("jsonTree")')
        assert evaluate("jsonTreeDialog.visible && jsonTreeDialog.rows.length === 4")
        evaluate("jsonTreeDialog.toggle(jsonTreeDialog.nodes[1])")
        assert evaluate("jsonTreeDialog.rows.length") == 2
        evaluate("jsonTreeDialog.close()")
        assert evaluate("jsonTreeDialog.nodes.length") == 0

        evaluate('currentDoc.language = "markdown"; currentPane.editor.text = "# Heading"')
        evaluate('runCommand("markdown")')
        QTest.qWait(300)
        assert evaluate('markdownPreview.visible && markdownPreview.rendered.includes("Heading")')
        evaluate('currentPane.editor.text = "# Updated"')
        QTest.qWait(300)
        assert evaluate('markdownPreview.rendered.includes("Updated")')
        evaluate("showMarkdownPreview = false")
        assert evaluate("markdownPreview.rendered") == ""

        file = Path(directory) / "disk.txt"
        assert manager.currentDocument.saveAs(str(file), "old\n")
        evaluate('currentPane.editor.text = "new\\n"')
        evaluate('runCommand("diskDiff")')
        assert evaluate("comparisonDialog.visible")
        assert "-old\n+new\n" in evaluate("comparisonDialog.comparison.diff")
        assert evaluate("currentPane.editor.text") == "new\n"
        assert QMetaObject.invokeMethod(window.findChild(QObject, "comparisonReloadButton"), "click")
        assert evaluate("reloadConfirm.visible")
        evaluate("reloadConfirm.reject()")
        assert evaluate("currentPane.editor.text") == "new\n"
        # Real external-change signal opens comparison rather than reloading.
        file.write_text("external\n")
        QTest.qWait(200)
        if not evaluate("comparisonDialog.visible"):
            manager.currentDocument.externallyChanged.emit()
        assert evaluate("comparisonDialog.heading") == "External Change Detected"
        assert evaluate("comparisonDialog.comparison.left") == "external\n"
        assert QMetaObject.invokeMethod(window.findChild(QObject, "comparisonReloadButton"), "click")
        evaluate("reloadConfirm.discarded()")
        qt_app.processEvents()
        assert evaluate("currentPane.editor.text") == "external\n"
        assert not manager.currentDocument.modified
        evaluate('runCommand("tabDiff")')
        assert evaluate("compareTabDialog.visible")
        evaluate("compareTabDialog.close()")
        evaluate("toggleSplit()")
        manager.closeDocument(second)
        qt_app.processEvents()
        assert not evaluate("splitEditors")
        assert not warnings, warnings
    finally:
        workspace.shutdown()
        window.setProperty("visible", False)
        del engine
