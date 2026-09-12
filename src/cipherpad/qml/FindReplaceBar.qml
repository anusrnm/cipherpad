import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Incremental find & replace. All matching logic lives in the Python
// SearchEngine; this only drives it and reports results.
Rectangle {
    id: bar

    property var pane: null
    readonly property string needle: findField.text
    readonly property string replacement: replaceField.text
    property bool replaceVisible: false
    property int matchCount: 0
    property int matchOrdinal: 0
    property bool patternValid: true

    signal closed()

    implicitHeight: layout.implicitHeight + 12
    color: Prefs.chrome
    visible: false

    function open(withReplace) {
        replaceVisible = withReplace === true
        if (pane && pane.editor.selectedText.length > 0
                && pane.editor.selectedText.indexOf("\n") < 0)
            findField.text = pane.editor.selectedText
        visible = true
        findField.forceActiveFocus()
        findField.selectAll()
        refresh()
    }

    function close() {
        visible = false
        if (pane)
            pane.applySearchHighlight("", false, false, false)
        bar.closed()
    }

    function refresh() {
        if (!pane)
            return
        patternValid = Search.isValid(needle, replacement, Prefs.searchCaseSensitive,
                                      Prefs.searchWholeWord, Prefs.searchRegex)
        if (!patternValid || needle === "") {
            matchCount = 0
            matchOrdinal = 0
            pane.applySearchHighlight("", false, false, false)
            return
        }
        const text = pane.editor.text
        matchCount = Search.matchCount(text, needle, Prefs.searchCaseSensitive,
                                       Prefs.searchWholeWord, Prefs.searchRegex)
        matchOrdinal = Search.matchOrdinal(text, needle, pane.editor.selectionStart,
                                           Prefs.searchCaseSensitive, Prefs.searchWholeWord,
                                           Prefs.searchRegex)
        pane.applySearchHighlight(needle, Prefs.searchCaseSensitive,
                                  Prefs.searchWholeWord, Prefs.searchRegex)
    }

    function findNext() {
        if (!pane || needle === "")
            return
        const from = pane.editor.selectionEnd
        const span = Search.findNext(pane.editor.text, needle, from, Prefs.searchCaseSensitive,
                                     Prefs.searchWholeWord, Prefs.searchRegex, Prefs.searchWrapAround)
        applyResult(span)
    }

    function findPrevious() {
        if (!pane || needle === "")
            return
        const span = Search.findPrevious(pane.editor.text, needle, pane.editor.selectionStart,
                                         Prefs.searchCaseSensitive, Prefs.searchWholeWord,
                                         Prefs.searchRegex, Prefs.searchWrapAround)
        applyResult(span)
    }

    function applyResult(span) {
        if (!span || span.length !== 2) {
            matchOrdinal = 0
            return
        }
        pane.selectRange(span[0], span[1])
        refresh()
    }

    function replaceOne() {
        if (!pane || needle === "")
            return
        const result = Search.replaceCurrent(pane.editor.text, needle, replacement,
                                             pane.editor.selectionStart, pane.editor.selectionEnd,
                                             Prefs.searchCaseSensitive, Prefs.searchWholeWord,
                                             Prefs.searchRegex)
        if (result.matched === true) {
            pane.metrics.replaceRange(result.start, result.end, result.text)
            pane.editor.cursorPosition = result.start + result.text.length
        }
        findNext()
    }

    function replaceAll() {
        if (!pane || needle === "")
            return
        const spans = Search.replacementSpans(pane.editor.text, needle, replacement,
                                              Prefs.searchCaseSensitive, Prefs.searchWholeWord,
                                              Prefs.searchRegex)
        if (spans.length === 0)
            return
        pane.metrics.replaceMany(spans)
        refresh()
        statusToast.show(spans.length + (spans.length === 1 ? " replacement" : " replacements"))
    }

    signal toast(string message)
    QtObject {
        id: statusToast
        function show(message) { bar.toast(message) }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 1
        color: Prefs.border
    }

    GridLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: 6
        columns: 2
        columnSpacing: 8
        rowSpacing: 6

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            ToolButton {
                text: bar.replaceVisible ? "\u25be" : "\u25b8"
                ToolTip.text: "Toggle replace"
                ToolTip.visible: hovered
                onClicked: bar.replaceVisible = !bar.replaceVisible
                contentItem: Text {
                    text: parent.text
                    color: Prefs.chromeText
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle { color: parent.hovered ? Prefs.border : "transparent"; radius: 3 }
            }

            EditorTextField {
                id: findField
                Layout.fillWidth: true
                Layout.maximumWidth: 320
                placeholderText: "Find"
                borderColor: bar.patternValid ? Prefs.border : "#e06c75"
                onTextChanged: bar.refresh()
                Keys.onReturnPressed: function (e) {
                    if (e.modifiers & Qt.ShiftModifier) bar.findPrevious(); else bar.findNext()
                }
                Keys.onEscapePressed: bar.close()
            }

            Label {
                text: !bar.patternValid ? "bad pattern"
                      : bar.needle === "" ? ""
                      : bar.matchCount === 0 ? "no results"
                      : (bar.matchOrdinal > 0 ? bar.matchOrdinal + " of " : "") + bar.matchCount
                color: (!bar.patternValid || (bar.needle !== "" && bar.matchCount === 0))
                       ? "#e06c75" : Prefs.chromeText
                opacity: 0.85
                Layout.minimumWidth: 80
            }

            BarButton { text: "\u2191"; tip: "Previous (Shift+Enter)"; onClicked: bar.findPrevious() }
            BarButton { text: "\u2193"; tip: "Next (Enter)"; onClicked: bar.findNext() }

            BarToggle {
                text: "Aa"; tip: "Match case"
                checked: Prefs.searchCaseSensitive
                onToggled: { Prefs.searchCaseSensitive = checked; bar.refresh() }
            }
            BarToggle {
                text: "\u2423W"; tip: "Whole word"
                checked: Prefs.searchWholeWord
                onToggled: { Prefs.searchWholeWord = checked; bar.refresh() }
            }
            BarToggle {
                text: ".*"; tip: "Regular expression"
                checked: Prefs.searchRegex
                onToggled: { Prefs.searchRegex = checked; bar.refresh() }
            }
            BarToggle {
                text: "\u21ba"; tip: "Wrap around"
                checked: Prefs.searchWrapAround
                onToggled: Prefs.searchWrapAround = checked
            }

            Item { Layout.fillWidth: true }

            BarButton { text: "\u2715"; tip: "Close (Esc)"; onClicked: bar.close() }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.columnSpan: 2
            visible: bar.replaceVisible
            spacing: 6

            Item { width: 30 }

            EditorTextField {
                id: replaceField
                Layout.fillWidth: true
                Layout.maximumWidth: 320
                placeholderText: "Replace with"
                Keys.onReturnPressed: bar.replaceOne()
                Keys.onEscapePressed: bar.close()
            }

            BarButton { text: "Replace"; wide: true; onClicked: bar.replaceOne() }
            BarButton { text: "Replace All"; wide: true; onClicked: bar.replaceAll() }

            Item { Layout.fillWidth: true }
        }
    }
}
