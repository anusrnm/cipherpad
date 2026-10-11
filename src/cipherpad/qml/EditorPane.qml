import QtQuick
import QtQuick.Controls.Basic
import Cipherpad

// One editing surface: gutter + text area + the glue that turns backend
// EditSpan results into single-undo edits.
Item {
    id: pane

    required property var doc          // Document instance from DocumentManager
    required property int docIndex
    required property var prettyPrintAction

    readonly property alias editor: editor
    readonly property alias metrics: metrics
    readonly property int currentLine: cursorInfo.line !== undefined ? cursorInfo.line : 1
    readonly property int currentColumn: cursorInfo.column !== undefined ? cursorInfo.column : 1
    readonly property int selectionLength: editor.selectionEnd - editor.selectionStart
    property var cursorInfo: ({ line: 1, column: 1, lineStart: 0 })

    signal statusChanged()

    // ------------------------------------------------------------ editing
    // Every backend command returns {start, end, text, selectionStart,
    // selectionEnd, changed}; applying it through metrics keeps undo atomic.
    function applySpan(span) {
        if (!span || !span.changed)
            return false
        metrics.replaceRange(span.start, span.end, span.text)
        if (span.selectionStart === span.selectionEnd)
            editor.cursorPosition = span.selectionStart
        else
            editor.select(span.selectionStart, span.selectionEnd)
        ensureCursorVisible()
        return true
    }

    function selStart() { return editor.selectionStart }
    function selEnd() { return editor.selectionEnd }
    function focusEditor() { editor.forceActiveFocus() }

    function goToLine(line) {
        editor.cursorPosition = metrics.positionForLine(line)
        ensureCursorVisible()
        focusEditor()
    }

    function selectRange(from, to) {
        editor.select(from, to)
        ensureCursorVisible()
    }

    function ensureCursorVisible() {
        const rect = editor.cursorRectangle
        const top = flick.contentY
        const bottom = top + flick.height
        if (rect.y < top)
            flick.contentY = Math.max(0, rect.y - flick.height * 0.25)
        else if (rect.y + rect.height > bottom)
            flick.contentY = Math.min(Math.max(0, flick.contentHeight - flick.height),
                                      rect.y + rect.height - flick.height + flick.height * 0.25)
    }

    function updateCursorInfo() {
        cursorInfo = metrics.cursorInfo(editor.cursorPosition)
        bracketTimer.restart()
        pane.statusChanged()
    }

    // ------------------------------------------------------- highlighting
    SyntaxHighlighter {
        id: highlighter
        document: editor.textDocument
        language: pane.doc ? pane.doc.language : "plain"
        enabled: Prefs.syntaxHighlighting
    }

    DocumentMetrics {
        id: metrics
        document: editor.textDocument
        onLayoutChanged: gutter.refresh()
    }

    function applyPalette() {
        highlighter.setPalette(Prefs.syntaxPalette())
        highlighter.setTabWidth(Prefs.tabWidth)
        highlighter.setShowWhitespace(Prefs.showWhitespace)
    }

    function applySearchHighlight(pattern, caseSensitive, wholeWord, regex) {
        if (pattern === "")
            highlighter.clearSearchHighlight()
        else
            highlighter.setSearchHighlight(pattern, caseSensitive, wholeWord, regex, Prefs.accent)
    }

    Connections {
        target: Prefs
        function onPaletteChanged() { pane.applyPalette() }
        function onTabWidthChanged() { highlighter.setTabWidth(Prefs.tabWidth) }
        function onShowWhitespaceChanged() { highlighter.setShowWhitespace(Prefs.showWhitespace) }
    }

    Connections {
        target: pane.doc
        function onContentLoaded(text) { pane.adoptContent(text) }
        function onLanguageChanged() { highlighter.language = pane.doc.language }
    }

    // Tracks the text last known to correspond to the document's on-disk /
    // clean state. Syntax highlighting reformats the block(s) whenever the
    // palette, language, tab width, etc. change, and that reformatting fires
    // TextArea.onTextChanged even though the actual characters are unchanged
    // (Qt Quick's TextEdit re-emits textChanged on any document content
    // reflow, not just genuine edits). Comparing against the last-known text
    // avoids marking the document dirty for these no-op reflows.
    property string _lastKnownText: ""

    function adoptContent(text) {
        editor.text = text
        editor.cursorPosition = 0
        pane._lastKnownText = text
        pane.doc.modified = false
        flick.contentY = 0
        gutter.refresh()
        pane.updateCursorInfo()
    }

    Component.onCompleted: {
        applyPalette()
        // Content loaded before this pane existed is buffered on the document.
        const buffered = pane.doc ? pane.doc.takeContent() : ""
        if (buffered.length > 0)
            adoptContent(buffered)
        else
            updateCursorInfo()
    }

    // ------------------------------------------------------------- layout
    Rectangle {
        anchors.fill: parent
        color: Prefs.background

        Row {
            anchors.fill: parent

            LineNumberGutter {
                id: gutter
                visible: Prefs.showLineNumbers
                width: visible ? implicitWidth : 0
                height: parent.height
                metrics: pane.metrics
                flickable: flick
                currentLine: pane.currentLine
                editorPadding: editor.topPadding
                onLineClicked: function (line) {
                    editor.select(metrics.positionForLine(line), metrics.lineEndPosition(line))
                    pane.focusEditor()
                }
            }

            Rectangle {
                width: gutter.visible ? 1 : 0
                height: parent.height
                color: Prefs.border
            }

            Flickable {
                id: flick
                width: parent.width - gutter.width - (gutter.visible ? 1 : 0)
                height: parent.height
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                contentWidth: editor.contentWidth
                onContentYChanged: gutter.refresh()
                onHeightChanged: gutter.refresh()

                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                    contentItem: Rectangle {
                        implicitWidth: 10
                        radius: 5
                        color: Prefs.border
                        opacity: parent.pressed ? 1.0 : (parent.active ? 0.8 : 0.4)
                        Behavior on opacity { NumberAnimation { duration: 150 } }
                    }
                }
                ScrollBar.horizontal: ScrollBar {
                    policy: Prefs.wordWrap ? ScrollBar.AlwaysOff : ScrollBar.AsNeeded
                }

                TextArea.flickable: TextArea {
                    id: editor
                    objectName: "editorTextArea"
                    focus: true
                    selectByMouse: true
                    persistentSelection: true
                    textFormat: TextEdit.PlainText
                    wrapMode: Prefs.wordWrap ? TextEdit.WrapAtWordBoundaryOrAnywhere : TextEdit.NoWrap
                    readOnly: pane.doc ? pane.doc.readOnly : false
                    leftPadding: 8
                    rightPadding: 8
                    topPadding: 6
                    bottomPadding: 6

                    color: Prefs.text
                    selectionColor: Prefs.selection
                    font.family: Prefs.fontFamily
                    font.pixelSize: Prefs.fontSize
                    font.bold: Prefs.fontBold
                    font.italic: Prefs.fontItalic
                    background: null

                    onTextChanged: {
                        if (editor.text !== pane._lastKnownText) {
                            pane._lastKnownText = editor.text
                            if (pane.doc)
                                pane.doc.modified = true
                        }
                        gutter.refresh()
                    }
                    onCursorPositionChanged: pane.updateCursorInfo()
                    onSelectedTextChanged: pane.statusChanged()

                    // current-line band, drawn behind the glyphs
                    Rectangle {
                        z: -2
                        visible: Prefs.highlightCurrentLine
                                 && editor.selectionStart === editor.selectionEnd
                        x: 0
                        y: editor.cursorRectangle.y
                        width: Math.max(flick.width, editor.contentWidth)
                        height: editor.cursorRectangle.height
                        color: Prefs.currentLine
                    }

                    // matching bracket outline
                    Rectangle {
                        z: -1
                        visible: Prefs.matchBrackets && bracketState.found
                        x: bracketState.box.x
                        y: bracketState.box.y
                        width: Math.max(3, bracketState.box.width)
                        height: bracketState.box.height
                        color: "transparent"
                        border.color: Prefs.accent
                        border.width: 1
                        radius: 2
                    }

                    Keys.onPressed: function (event) { pane.handleKey(event) }

                    TapHandler {
                        acceptedButtons: Qt.RightButton
                        onTapped: function (eventPoint) {
                            pane.focusEditor()
                            editorMenu.popup(eventPoint.position)
                        }
                    }

                    AppMenu {
                        id: editorMenu
                        objectName: "editorContextMenu"
                        AppMenuItem { text: "Undo"; shortcutText: "Ctrl+Z"; enabled: editor.canUndo && !editor.readOnly
                            onTriggered: editor.undo() }
                        AppMenuItem { text: "Redo"; shortcutText: "Ctrl+Y"; enabled: editor.canRedo && !editor.readOnly
                            onTriggered: editor.redo() }
                        MenuSeparator {}
                        AppMenuItem { text: "Cut"; shortcutText: "Ctrl+X"; enabled: pane.selectionLength > 0 && !editor.readOnly
                            onTriggered: editor.cut() }
                        AppMenuItem { text: "Copy"; shortcutText: "Ctrl+C"; enabled: pane.selectionLength > 0
                            onTriggered: editor.copy() }
                        AppMenuItem { text: "Paste"; shortcutText: "Ctrl+V"; enabled: editor.canPaste && !editor.readOnly
                            onTriggered: editor.paste() }
                        AppMenuItem { text: "Select All"; shortcutText: "Ctrl+A"; onTriggered: editor.selectAll() }
                        MenuSeparator {}
                        AppMenuItem {
                            objectName: "prettyPrintContextItem"
                            action: pane.prettyPrintAction
                            shortcutText: "Ctrl+Shift+P"
                        }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------ bracket match
    QtObject {
        id: bracketState
        property bool found: false
        property rect box: Qt.rect(0, 0, 0, 0)
    }

    Timer {
        id: bracketTimer
        interval: 40
        onTriggered: {
            if (!Prefs.matchBrackets) { bracketState.found = false; return }
            const info = metrics.matchingBracket(editor.cursorPosition)
            bracketState.found = info.found === true
            if (bracketState.found)
                bracketState.box = editor.positionToRectangle(info.to)
        }
    }

    // --------------------------------------------------------- key handling
    function handleKey(event) {
        const tabWidth = Prefs.tabWidth
        const useSpaces = Prefs.insertSpaces
        const hasSelection = editor.selectionStart !== editor.selectionEnd

        if (event.key === Qt.Key_Tab && !(event.modifiers & Qt.ShiftModifier)) {
            event.accepted = true
            if (hasSelection)
                applySpan(TextOps.indent(editor.text, selStart(), selEnd(), tabWidth, useSpaces))
            else if (useSpaces)
                insertAtCursor(TextOps.tabFiller(pane.currentColumn - 1, tabWidth))
            else
                insertAtCursor("\t")
            return
        }

        if (event.key === Qt.Key_Backtab
                || (event.key === Qt.Key_Tab && (event.modifiers & Qt.ShiftModifier))) {
            event.accepted = true
            applySpan(TextOps.unindent(editor.text, selStart(), selEnd(), tabWidth))
            return
        }

        if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                && !(event.modifiers & Qt.ShiftModifier)) {
            event.accepted = true
            const indentation = Prefs.autoIndent && !hasSelection
                              ? TextOps.indentForNewline(
                                    editor.text, editor.cursorPosition, tabWidth, useSpaces)
                              : ""
            insertAtCursor("\n" + indentation)
            return
        }

        if (Prefs.autoCloseBrackets && event.text.length === 1 && !hasSelection) {
            const closing = TextOps.closingBracket(event.text)
            if (closing !== "") {
                event.accepted = true
                const at = editor.cursorPosition
                metrics.replaceRange(at, at, event.text + closing)
                editor.cursorPosition = at + 1
                return
            }
            // Typing a closing bracket that is already there just steps over it.
            if (TextOps.isClosingBracket(event.text)
                    && editor.text.charAt(editor.cursorPosition) === event.text) {
                event.accepted = true
                editor.cursorPosition += 1
                return
            }
        }
    }

    function insertAtCursor(text) {
        const from = editor.selectionStart
        metrics.replaceRange(from, editor.selectionEnd, text)
        editor.cursorPosition = from + text.length
        ensureCursorVisible()
    }

    // -------------------------------------------------------------- zoom
    WheelHandler {
        acceptedModifiers: Qt.ControlModifier
        onWheel: function (event) { Prefs.adjustFontSize(event.angleDelta.y > 0 ? 1 : -1) }
    }
}
