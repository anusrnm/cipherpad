"""Tests for the text manipulation helpers exposed to QML."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from PySide6.QtCore import QFile, QMetaObject, QObject, QSettings, Qt, QUrl
from PySide6.QtGui import QGuiApplication, QTextDocument
from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression

from cipherpad.gutter import DocumentMetrics
from cipherpad.textops import TextOps


@pytest.fixture()
def ops(qt_app) -> TextOps:  # noqa: ANN001
    return TextOps()


def apply(span: dict, text: str) -> str:
    """Apply an edit span the same way EditorPane.applySpan does."""
    if not span.get("changed", False):
        return text
    return text[: span["start"]] + span["text"] + text[span["end"] :]


SAMPLE = "beta\nalpha\ngamma\n"


@pytest.mark.parametrize("width,spaces,indent", [(2, True, "  "), (4, True, "    "), (4, False, "\t")])
def test_pretty_print_json(ops: TextOps, width: int, spaces: bool, indent: str) -> None:
    text = '{"a":[1,{},[]],"b":true}'
    expected = (
        '{\n' + indent + '"a": [\n' + indent * 2 + '1,\n'
        + indent * 2 + '{},\n' + indent * 2 + '[]\n' + indent + '],\n'
        + indent + '"b": true\n}'
    )
    assert apply(ops.prettyPrint(text, "json", width, spaces), text) == expected
    assert not ops.prettyPrint(expected, "json", width, spaces)["changed"]


def test_pretty_print_json_preserves_tokens(ops: TextOps) -> None:
    text = r'{"x":1.234567890123456789,"x":1e9999,"s":"\u00e9\"{}","big":' + "9" * 5000 + "}"
    result = apply(ops.prettyPrint(text, "json", 2, True), text)
    assert re.sub(r"\s+", "", result) == text


@pytest.mark.parametrize("text", ['{"a":}', '{"a":1,}', '{"a":NaN}', "Infinity", "", "<root>"])
def test_pretty_print_invalid_input(ops: TextOps, text: str) -> None:
    language = "xml" if text.startswith("<") else "json"
    span = ops.prettyPrint(text, language, 2, True)
    assert not span["changed"]
    assert "Pretty Print failed:" in span["error"]
    assert apply(span, text) == text


def test_pretty_print_unsupported_language(ops: TextOps) -> None:
    assert ops.prettyPrint("print(1)", "python", 2, True)["error"]


@pytest.mark.parametrize("language,text", [("json", "{}\n"), ("xml", "<root/>\n")])
def test_pretty_print_preserves_final_newline(ops: TextOps, language: str, text: str) -> None:
    assert not ops.prettyPrint(text, language, 2, True)["changed"]


def test_pretty_print_xml(ops: TextOps) -> None:
    text = '<?xml version="1.0" encoding="UTF-8"?><root xmlns="urn:test"><!--note--><?test ok?><item a="1">value</item><empty/></root>'
    result = apply(ops.prettyPrint(text, "xml", 2, True), text)
    assert result == (
        '<?xml version="1.0" encoding="UTF-8"?>\n<root xmlns="urn:test">\n'
        '  <!--note-->\n  <?test ok?>\n  <item a="1">value</item>\n  <empty/>\n</root>'
    )
    assert not ops.prettyPrint(result, "xml", 2, True)["changed"]


@pytest.mark.parametrize("text", [
    "<p>Hello <b>world</b> !</p>",
    "<root><![CDATA[a < b]]><child/></root>",
    '<root xml:space="preserve"> <child> <nested/> </child> </root>',
    "<root>   </root>",
])
def test_pretty_print_xml_preserves_significant_whitespace(ops: TextOps, text: str) -> None:
    assert apply(ops.prettyPrint(text, "xml", 2, True), text) == text


def test_pretty_print_xml_tabs(ops: TextOps) -> None:
    text = "<root><branch><leaf/></branch></root>"
    assert apply(ops.prettyPrint(text, "xml", 4, False), text) == (
        "<root>\n\t<branch>\n\t\t<leaf/>\n\t</branch>\n</root>"
    )


def test_pretty_print_xml_doctype_is_reported(ops: TextOps) -> None:
    span = ops.prettyPrint('<!DOCTYPE root [<!ENTITY x "value">]><root>&x;</root>', "xml", 2, True)
    assert not span["changed"]
    assert "DOCTYPE" in span["error"]


@pytest.mark.parametrize("language,text", [
    ("json", '{"face":"\U0001f600","n":1}'),
    ("xml", "<root><face>\U0001f600</face><n>1</n></root>"),
])
def test_pretty_print_is_single_undoable_edit(ops: TextOps, language: str, text: str) -> None:
    document = QTextDocument()
    document.setPlainText(text)
    metrics = DocumentMetrics()
    metrics._document = document
    span = ops.prettyPrint(text, language, 2, True)
    assert span["end"] == document.characterCount() - 1
    assert metrics.replaceRange(span["start"], span["end"], span["text"])
    assert document.toPlainText() == span["text"]
    document.undo()
    assert document.toPlainText() == text
    document.redo()
    assert document.toPlainText() == span["text"]


def test_pretty_print_from_main_qml(tmp_path: Path) -> None:
    # Keep a full QML engine's ownership and teardown separate from Qt fixtures.
    script = (
        "import runpy; "
        f"runpy.run_path({str(Path(__file__).resolve())!r})"
        f"['_check_pretty_print_qml']({str(tmp_path)!r})"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _check_pretty_print_qml(settings_directory: str) -> None:
    from cipherpad import app, crypto, document, explorer, preferences, search
    from PySide6.QtTest import QTest

    qt_app = QGuiApplication([])
    original_settings = preferences.QSettings
    preferences.QSettings = lambda *args: QSettings(
        str(Path(settings_directory) / "prefs.ini"), QSettings.Format.IniFormat,
    )
    prefs = preferences.Preferences()
    preferences.QSettings = original_settings
    manager = document.DocumentManager()
    project_explorer = explorer.ProjectExplorer()
    project_explorer.bind_documents(manager)
    from cipherpad.workspace import WorkspaceTools
    workspace_tools = WorkspaceTools(project_explorer)
    backends = {
        "Prefs": prefs, "Documents": manager, "Search": search.SearchEngine(),
        "TextOps": TextOps(), "Crypto": crypto.CryptoInfo(),
        "Explorer": project_explorer, "appVersion": "test",
        "Workspace": workspace_tools,
    }
    engine = QQmlApplicationEngine()
    warnings: list[str] = []
    engine.warnings.connect(lambda messages: warnings.extend(m.toString() for m in messages))
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

    def find_row(path: Path):
        pending = [window.contentItem()]
        while pending:
            item = pending.pop()
            if item.objectName() == "explorerItem:" + str(path):
                return item
            pending.extend(item.childItems())
        raise AssertionError(f"Explorer row not found: {path}")

    try:
        manager.newDocument()
        qt_app.processEvents()
        action = window.findChild(QObject, "prettyPrintAction")
        button = window.findChild(QObject, "prettyPrintButton")
        pane = window.property("currentPane")
        context_item = pane.findChild(QObject, "prettyPrintContextItem")
        context_menu = pane.findChild(QObject, "editorContextMenu")
        assert all(item is not None for item in (action, button, context_item, context_menu)), (
            action, button, context_item, context_menu,
        )
        assert not action.property("enabled")
        assert not button.property("enabled")
        assert not context_item.property("enabled")
        for language, text in (
            ("json", '{"face":"\U0001f600","a":[1,2]}'),
            ("xml", "<root><face>\U0001f600</face><empty/></root>"),
        ):
            manager.currentDocument.language = language
            evaluate("currentPane.editor.text = " + json.dumps(text))
            assert QMetaObject.invokeMethod(window, "prettyPrint")
            assert "\n" in evaluate("currentPane.editor.text")
            assert manager.currentDocument.modified
            evaluate("currentPane.editor.undo()")
            assert evaluate("currentPane.editor.text") == text
        manager.currentDocument.language = "json"
        text = '{"a":[1,2]}'
        for source in ("toolbar", "context", "shortcut"):
            evaluate("currentPane.editor.text = " + json.dumps(text))
            qt_app.processEvents()
            assert action.property("enabled")
            assert button.property("enabled")
            assert context_item.property("enabled")
            if source == "toolbar":
                assert QMetaObject.invokeMethod(button, "click")
            elif source == "context":
                point = evaluate("currentPane.editor.mapToItem(null, 20, 15)")
                QTest.mouseClick(window, Qt.MouseButton.RightButton, pos=point.toPoint())
                qt_app.processEvents()
                assert context_menu.property("visible")
                assert QMetaObject.invokeMethod(context_item, "click")
                QMetaObject.invokeMethod(context_menu, "close")
            else:
                window.requestActivate()
                evaluate("currentPane.focusEditor()")
                qt_app.processEvents()
                QTest.keyClick(window, Qt.Key.Key_P, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
            qt_app.processEvents()
            assert "\n" in evaluate("currentPane.editor.text"), source
            evaluate("currentPane.editor.undo()")
            assert evaluate("currentPane.editor.text") == text
        manager.currentDocument.language = "groovy"
        assert not action.property("enabled")
        assert not button.property("enabled")
        assert not context_item.property("enabled")
        manager.currentDocument.language = "xml"
        evaluate('currentPane.editor.text = "<broken>"')
        assert QMetaObject.invokeMethod(window, "prettyPrint")
        assert evaluate("currentPane.editor.text") == "<broken>"
        assert evaluate("messageDialog.visible")
        assert "Pretty Print failed" in evaluate("messageDialog.message")
        evaluate("messageDialog.close()")

        project = Path(settings_directory) / "project"
        project.mkdir()
        file = project / "sample.txt"
        file.write_text("original")
        project_explorer.addFolder(str(project))
        prefs.showProjectExplorer = True
        QTest.qWait(50)
        row = find_row(file)
        QTest.mouseClick(window, Qt.MouseButton.RightButton, pos=row.mapToScene(
            row.boundingRect().center()
        ).toPoint())
        qt_app.processEvents()
        menu = row.findChild(QObject, "explorerItemMenu")
        assert menu.property("visible")
        rename_item = row.findChild(QObject, "explorerRenameItem")
        assert QMetaObject.invokeMethod(rename_item, "click")
        name_dialog = window.findChild(QObject, "explorerNameDialog")
        name_field = window.findChild(QObject, "explorerNameField")
        assert name_dialog.property("visible")
        name_field.setProperty("text", "renamed.txt")
        assert QMetaObject.invokeMethod(name_dialog, "accept")
        qt_app.processEvents()
        renamed = project / "renamed.txt"
        assert renamed.exists() and not file.exists()
        row = find_row(renamed)
        assert QMetaObject.invokeMethod(row.findChild(QObject, "explorerDuplicateItem"), "click")
        qt_app.processEvents()
        assert (project / "renamed copy.txt").read_text() == "original"
        destination = project / "destination"
        destination.mkdir()
        project_explorer.refresh()
        qt_app.processEvents()
        copied = project / "renamed copy.txt"
        row = find_row(copied)
        assert QMetaObject.invokeMethod(row.findChild(QObject, "explorerCopyItem"), "click")
        row = find_row(destination)
        QTest.mouseClick(window, Qt.MouseButton.RightButton, pos=row.mapToScene(
            row.boundingRect().center()
        ).toPoint())
        assert QMetaObject.invokeMethod(row.findChild(QObject, "explorerPasteItem"), "click")
        qt_app.processEvents()
        assert (destination / copied.name).read_text() == "original"
        row = find_row(copied)
        assert QMetaObject.invokeMethod(row.findChild(QObject, "explorerCutItem"), "click")
        assert project_explorer.canPaste
        # Select the destination via its real mouse handler before toolbar paste.
        row = find_row(project)
        QTest.mouseClick(window, Qt.MouseButton.RightButton, pos=row.mapToScene(
            row.boundingRect().center()
        ).toPoint())
        QMetaObject.invokeMethod(row.findChild(QObject, "explorerItemMenu"), "close")
        # Same-parent paste must report a conflict instead of deleting the source.
        assert QMetaObject.invokeMethod(window.findChild(QObject, "explorerPasteButton"), "click")
        assert copied.exists()
        assert evaluate("messageDialog.visible")
        evaluate("messageDialog.close()")
        assert QMetaObject.invokeMethod(window.findChild(QObject, "explorerNewFolderButton"), "click")
        name_field.setProperty("text", "created-folder")
        assert QMetaObject.invokeMethod(name_dialog, "accept")
        qt_app.processEvents()
        assert (project / "created-folder").is_dir()
        assert QMetaObject.invokeMethod(window.findChild(QObject, "explorerNewFileButton"), "click")
        name_field.setProperty("text", "created.txt")
        assert QMetaObject.invokeMethod(name_dialog, "accept")
        qt_app.processEvents()
        assert (project / "created.txt").exists()
        row = find_row(renamed)
        assert QMetaObject.invokeMethod(row.findChild(QObject, "explorerDeleteItem"), "click")
        delete_dialog = window.findChild(QObject, "explorerDeleteDialog")
        assert delete_dialog.property("visible")
        assert renamed.exists()
        assert QMetaObject.invokeMethod(delete_dialog, "reject")
        assert renamed.exists()
        row = find_row(renamed)
        assert QMetaObject.invokeMethod(row.findChild(QObject, "explorerDeleteItem"), "click")
        original_trash = QFile.moveToTrash
        def trash(path: str) -> bool:
            assert path == str(renamed)
            renamed.unlink()
            return True
        QFile.moveToTrash = trash
        try:
            assert QMetaObject.invokeMethod(delete_dialog, "accept")
        finally:
            QFile.moveToTrash = original_trash
        assert not renamed.exists()
        assert not project_explorer.renameItem(str(project / "missing"), "new")
        assert evaluate("messageDialog.visible")
        assert "Item not found" in evaluate("messageDialog.message")
        evaluate("messageDialog.close()")

        def wait_for_workspace() -> None:
            import time
            deadline = time.monotonic() + 5
            while workspace_tools.busy and time.monotonic() < deadline:
                QTest.qWait(10)
            assert not workspace_tools.busy
            QTest.qWait(50)

        workspace_file = project / "workspace-match.py"
        workspace_file.write_text("\U0001f600 hello\n", encoding="utf-8")
        project_explorer.refresh()
        # Real palette shortcut + Enter executes a shared editor command.
        QTest.keyClick(window, Qt.Key.Key_F1)
        QTest.qWait(30)
        assert evaluate("workspacePicker.visible && workspacePicker.commandsMode")
        picker_query = window.findChild(QObject, "workspacePickerQuery")
        picker_query.setProperty("text", "toggle word wrap")
        assert evaluate("workspacePicker.results.length") == 1
        old_wrap = prefs.wordWrap
        QTest.keyClick(window, Qt.Key.Key_Return)
        assert prefs.wordWrap != old_wrap
        assert not evaluate("workspacePicker.visible")
        # Palette toolbar uses the same action.
        assert QMetaObject.invokeMethod(window.findChild(QObject, "commandPaletteButton"), "click")
        assert evaluate("workspacePicker.commandsMode")
        evaluate("workspacePicker.close()")

        QTest.keyClick(window, Qt.Key.Key_P, Qt.KeyboardModifier.ControlModifier)
        wait_for_workspace()
        assert evaluate("workspacePicker.visible && !workspacePicker.commandsMode")
        picker_query.setProperty("text", "workspacematch")
        assert evaluate("workspacePicker.results.length") == 1
        QTest.keyClick(window, Qt.Key.Key_Return)
        assert manager.currentDocument.filePath == str(workspace_file)
        assert evaluate("currentPane.editor.text") == "\U0001f600 hello\n"

        QTest.keyClick(window, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        assert evaluate("workspaceSearchDialog.visible")
        search_query = window.findChild(QObject, "workspaceSearchQuery")
        search_query.setProperty("text", "hello")
        window.findChild(QObject, "workspaceSearchMasks").setProperty("text", "*.py")
        assert QMetaObject.invokeMethod(window.findChild(QObject, "workspaceSearchButton"), "click")
        wait_for_workspace()
        assert len(workspace_tools.matches) == 1
        # Click the actual search-result delegate, then verify UTF-16 selection.
        pending_items = [window.contentItem()]
        result_item = None
        while pending_items:
            item = pending_items.pop()
            if item.objectName() == "workspaceSearchMatch:0":
                result_item = item
                break
            pending_items.extend(item.childItems())
        assert result_item is not None
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=result_item.mapToScene(
            result_item.boundingRect().center()
        ).toPoint())
        assert evaluate("currentPane.editor.selectedText") == "hello"
        assert not evaluate("workspaceSearchDialog.visible")
        evaluate("currentPane.editor.text = 'changed'")
        evaluate("workspaceSearchDialog.matchRequested(Workspace.matches[0])")
        assert evaluate("messageDialog.visible")
        assert "modified tab" in evaluate("messageDialog.message")
        evaluate("messageDialog.close()")
        manager.currentDocument.modified = False
        evaluate("workspaceSearchDialog.matchRequested(Workspace.matches[0])")
        assert "changed since the search" in evaluate("messageDialog.message")
        evaluate("messageDialog.close()")

        filter_field = window.findChild(QObject, "explorerFilterField")
        filter_field.setProperty("text", "workspace-match")
        QTest.qWait(180)
        assert [node.name for node in project_explorer._items] == [project.name, workspace_file.name]
        filter_field.setProperty("text", "")
        QTest.qWait(30)
        prefs.showHiddenFiles = True
        prefs.workspaceIgnorePatterns = "*.py"
        assert project_explorer.showHidden
        assert project_explorer.ignorePatterns == "*.py"
        assert workspace_tools.fileCount == 0
        assert QMetaObject.invokeMethod(window.findChild(QObject, "quickOpenButton"), "click")
        wait_for_workspace()
        assert all(not entry["path"].endswith(".py") for entry in workspace_tools.quickFiles(""))
        evaluate("workspacePicker.close()")
        assert not warnings
    finally:
        workspace_tools.shutdown()
        window.setProperty("visible", False)
        del engine


def test_case_conversions(ops: TextOps) -> None:
    text = "hello world"
    assert apply(ops.upperCase(text, 0, len(text)), text) == "HELLO WORLD"
    assert apply(ops.lowerCase("HELLO", 0, 5), "HELLO") == "hello"
    assert apply(ops.titleCase(text, 0, len(text)), text) == "Hello World"
    assert apply(ops.toggleCase("aBc", 0, 3), "aBc") == "AbC"


def test_case_conversion_respects_selection(ops: TextOps) -> None:
    text = "hello world"
    assert apply(ops.upperCase(text, 0, 5), text) == "HELLO world"


def test_sort_lines(ops: TextOps) -> None:
    assert apply(ops.sortLines(SAMPLE, 0, len(SAMPLE), False, False), SAMPLE) == "alpha\nbeta\ngamma\n"
    assert apply(ops.sortLines(SAMPLE, 0, len(SAMPLE), True, False), SAMPLE) == "gamma\nbeta\nalpha\n"


def test_sort_lines_unique(ops: TextOps) -> None:
    text = "b\na\nb\n"
    assert apply(ops.sortLines(text, 0, len(text), False, True), text) == "a\nb\n"


def test_unique_and_reverse(ops: TextOps) -> None:
    text = "a\nb\na\n"
    assert apply(ops.uniqueLines(text, 0, len(text)), text) == "a\nb\n"
    assert apply(ops.reverseLines(SAMPLE, 0, len(SAMPLE)), SAMPLE) == "gamma\nalpha\nbeta\n"


def test_trim_trailing_whitespace(ops: TextOps) -> None:
    text = "a   \nb\t\nc\n"
    assert apply(ops.trimTrailingWhitespace(text, 0, len(text)), text) == "a\nb\nc\n"


def test_trim_reports_unchanged_when_clean(ops: TextOps) -> None:
    text = "a\nb\n"
    assert ops.trimTrailingWhitespace(text, 0, len(text)).get("changed") is False


def test_duplicate_and_delete_lines(ops: TextOps) -> None:
    text = "one\ntwo\n"
    assert apply(ops.duplicateLines(text, 0, 3), text) == "one\none\ntwo\n"
    assert apply(ops.deleteLines(text, 0, 3), text) == "two\n"


def test_move_lines(ops: TextOps) -> None:
    text = "one\ntwo\nthree\n"
    assert apply(ops.moveLinesDown(text, 0, 3), text) == "two\none\nthree\n"
    assert apply(ops.moveLinesUp(text, 4, 7), text) == "two\none\nthree\n"


def test_move_lines_at_boundaries_is_noop(ops: TextOps) -> None:
    text = "one\ntwo\n"
    assert ops.moveLinesUp(text, 0, 3).get("changed") is False


def test_join_lines(ops: TextOps) -> None:
    text = "one\ntwo\nthree\n"
    assert apply(ops.joinLines(text, 0, 8), text) == "one two\nthree\n"


def test_indent_and_unindent_with_spaces(ops: TextOps) -> None:
    text = "a\nb\n"
    indented = apply(ops.indent(text, 0, 3, 4, True), text)
    assert indented == "    a\n    b\n"
    assert apply(ops.unindent(indented, 0, 11, 4), indented) == "a\nb\n"


def test_indent_with_tabs(ops: TextOps) -> None:
    text = "a\n"
    assert apply(ops.indent(text, 0, 1, 4, False), text) == "\ta\n"


def test_convert_indentation(ops: TextOps) -> None:
    tabs = "\ta\n"
    spaces = apply(ops.convertIndentation(tabs, 0, len(tabs), 4, True), tabs)
    assert spaces == "    a\n"
    assert apply(ops.convertIndentation(spaces, 0, len(spaces), 4, False), spaces) == "\ta\n"


@pytest.mark.parametrize(
    ("language", "expected"),
    [("python", "# a\n"), ("javascript", "// a\n"), ("html", "<!-- a -->\n")],
)
def test_toggle_comment_adds_marker(ops: TextOps, language: str, expected: str) -> None:
    text = "a\n"
    assert apply(ops.toggleComment(text, 0, 1, language), text) == expected


def test_toggle_comment_is_reversible(ops: TextOps) -> None:
    text = "a\nb\n"
    commented = apply(ops.toggleComment(text, 0, 3, "python"), text)
    assert commented == "# a\n# b\n"
    assert apply(ops.toggleComment(commented, 0, 7, "python"), commented) == text


def test_toggle_comment_language_lookup_is_tolerant(ops: TextOps) -> None:
    text = "a\n"
    assert apply(ops.toggleComment(text, 0, 1, "Python"), text) == "# a\n"
    assert apply(ops.toggleComment(text, 0, 1, "PYTHON"), text) == "# a\n"


def test_toggle_comment_unknown_language_is_noop(ops: TextOps) -> None:
    assert ops.toggleComment("a\n", 0, 1, "not-a-language").get("changed") is False


def test_indent_for_newline(ops: TextOps) -> None:
    text = "    value = 1"
    assert ops.indentForNewline(text, len(text), 4, True) == "    "


def test_indent_for_newline_after_open_block(ops: TextOps) -> None:
    text = "def f():"
    assert len(ops.indentForNewline(text, len(text), 4, True)) >= 4


def test_bracket_helpers(ops: TextOps) -> None:
    assert ops.closingBracket("(") == ")"
    assert ops.closingBracket("[") == "]"
    assert ops.closingBracket("a") == ""
    assert ops.isClosingBracket(")")
    assert not ops.isClosingBracket("(")


def test_tab_filler_aligns_to_stop(ops: TextOps) -> None:
    assert ops.tabFiller(0, 4) == "    "
    assert ops.tabFiller(2, 4) == "  "
    assert ops.tabFiller(4, 4) == "    "


def test_indent_string(ops: TextOps) -> None:
    assert ops.indentString(2) == "  "


def test_timestamp(ops: TextOps) -> None:
    assert ops.timestamp("")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", ops.timestamp("date"))
    assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", ops.timestamp("time"))
    assert "T" in ops.timestamp("iso")


def test_statistics(ops: TextOps) -> None:
    stats = ops.statistics("one two\nthree\n\nfour\n", "")
    assert stats["words"] == 4
    assert stats["characters"] == 20
    assert stats["charactersNoSpaces"] == 15
    assert stats["lines"] == 5
    assert stats["paragraphs"] == 2
    assert stats["isSelection"] is False


def test_statistics_for_selection(ops: TextOps) -> None:
    stats = ops.statistics("one two", "one")
    assert stats["isSelection"] is True
    assert stats["words"] == 1


def test_statistics_of_empty_text(ops: TextOps) -> None:
    stats = ops.statistics("", "")
    assert stats["words"] == 0
    assert stats["characters"] == 0
