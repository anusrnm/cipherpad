import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Cipherpad

AppDialog {
    id: root
    objectName: "comparisonDialog"
    heading: "Compare"
    width: Math.min(1100, parent.width - 40)
    height: Math.min(740, parent.height - 40)
    standardButtons: Dialog.Close
    property var comparison: ({})
    property var sourceDocument: null
    property bool reloadAllowed: false
    property var safetyTools: null
    property bool sensitive: false
    signal reloadRequested(var document)

    function showComparison(result, document, allowReload) {
        comparison = result
        sourceDocument = document
        reloadAllowed = allowReload
        sensitive = document ? document.encrypted : result.sensitive === true
        views.currentIndex = 0
        open()
    }
    onClosed: {
        comparison = ({})
        sourceDocument = null
        sensitive = false
    }
    function copySelection(area, event) {
        if (event.matches(StandardKey.Copy) && safetyTools) {
            event.accepted = true
            if (area.selectedText.length)
                safetyTools.copyText(area.selectedText, sensitive, Prefs.clipboardExpirySeconds)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        Label {
            Layout.fillWidth: true
            text: root.comparison.equal ? "Versions are identical." : "Read-only comparison. Your editor buffer is unchanged."
            color: Prefs.chromeText
            wrapMode: Text.Wrap
        }
        TabBar {
            id: views
            Layout.fillWidth: true
            TabButton { text: "Unified Diff" }
            TabButton { text: "Side by Side"; enabled: root.comparison.unifiedOnly !== true }
        }
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: views.currentIndex
            ScrollView {
                clip: true
                TextArea {
                    id: diffText
                    Keys.onPressed: function(event) { root.copySelection(diffText, event) }
                    objectName: "comparisonDiff"
                    text: root.comparison.diff || ""
                    textFormat: TextEdit.PlainText
                    readOnly: true
                    selectByMouse: true
                    color: Prefs.text
                    font.family: Prefs.fontFamily
                    background: Rectangle { color: Prefs.background }
                    SyntaxHighlighter {
                        id: diffHighlighter
                        document: diffText.textDocument
                        language: "diff"
                        enabled: Prefs.syntaxHighlighting
                        Component.onCompleted: setPalette(Prefs.syntaxPalette())
                    }
                    Connections {
                        target: Prefs
                        function onPaletteChanged() { diffHighlighter.setPalette(Prefs.syntaxPalette()) }
                    }
                }
            }
            RowLayout {
                Repeater {
                    model: ["left", "right"]
                    ColumnLayout {
                        required property string modelData
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Label {
                            Layout.fillWidth: true
                            text: root.comparison[modelData + "Name"] || ""
                            elide: Text.ElideMiddle
                            color: Prefs.chromeText
                        }
                        ScrollView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            TextArea {
                                id: sideText
                                Keys.onPressed: function(event) { root.copySelection(sideText, event) }
                                text: root.comparison[modelData] || ""
                                textFormat: TextEdit.PlainText
                                readOnly: true
                                selectByMouse: true
                                color: Prefs.text
                                font.family: Prefs.fontFamily
                                background: Rectangle { color: Prefs.background }
                            }
                        }
                    }
                }
            }
        }
        BarButton {
            objectName: "comparisonReloadButton"
            text: "Reload Disk Version..."
            wide: true
            visible: root.reloadAllowed
            onClicked: {
                const document = root.sourceDocument
                root.close()
                root.reloadRequested(document)
            }
        }
    }
}
