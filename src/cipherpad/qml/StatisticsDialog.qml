import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

AppDialog {
    id: root

    property var stats: ({})
    property var selectionStats: null
    property string documentName: ""

    heading: "Statistics"
    standardButtons: Dialog.Close
    width: 380

    function showFor(name, data, selection) {
        documentName = name
        stats = data
        selectionStats = (selection && selection.characters > 0) ? selection : null
        open()
    }

    ColumnLayout {
        spacing: 6
        width: parent.width

        Label {
            Layout.fillWidth: true
            text: root.documentName
            color: Prefs.chromeText
            font.bold: true
            elide: Text.ElideMiddle
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Label {
                text: "Document"
                color: Prefs.chromeText
                opacity: 0.6
                Layout.preferredWidth: 80
                horizontalAlignment: Text.AlignRight
            }
            Label {
                visible: root.selectionStats !== null
                text: "Selection"
                color: Prefs.chromeText
                opacity: 0.6
                Layout.preferredWidth: 80
                horizontalAlignment: Text.AlignRight
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Prefs.border }

        Repeater {
            model: [
                { label: "Lines", key: "lines" },
                { label: "Words", key: "words" },
                { label: "Characters", key: "characters" },
                { label: "Characters (no spaces)", key: "charactersNoSpaces" },
                { label: "Paragraphs", key: "paragraphs" }
            ]
            RowLayout {
                Layout.fillWidth: true
                Label {
                    text: modelData.label
                    color: Prefs.chromeText
                    opacity: 0.8
                }
                Item { Layout.fillWidth: true }
                Label {
                    text: root.stats[modelData.key] !== undefined ? root.stats[modelData.key] : "0"
                    color: Prefs.chromeText
                    font.family: Prefs.fontFamily
                    Layout.preferredWidth: 80
                    horizontalAlignment: Text.AlignRight
                }
                Label {
                    visible: root.selectionStats !== null
                    text: root.selectionStats ? root.selectionStats[modelData.key] : ""
                    color: Prefs.accent
                    font.family: Prefs.fontFamily
                    Layout.preferredWidth: 80
                    horizontalAlignment: Text.AlignRight
                }
            }
        }
    }
}
