import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

AppDialog {
    id: root
    objectName: "workspaceSearchDialog"
    heading: "Search Workspace"
    width: Math.min(860, parent.width - 40)
    height: Math.min(650, parent.height - 40)
    standardButtons: Dialog.Close
    initialFocusItem: query
    signal matchRequested(var match)

    function showSearch() {
        open()
        query.forceActiveFocus()
        query.selectAll()
    }

    ColumnLayout {
        anchors.fill: parent
        Label {
            text: "Search saved files on disk. Unsaved buffers are not included."
            color: Prefs.chromeText
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }
        RowLayout {
            Layout.fillWidth: true
            TextField {
                id: query
                objectName: "workspaceSearchQuery"
                Layout.fillWidth: true
                color: Prefs.chromeText
                placeholderText: "Text to find"
                onAccepted: if (searchButton.enabled) searchButton.clicked()
            }
            BarButton {
                id: searchButton
                objectName: "workspaceSearchButton"
                text: "Search"
                wide: true
                enabled: query.text.length > 0 && !Workspace.busy
                onClicked: Workspace.search(query.text, masks.text, caseBox.checked, wordBox.checked)
            }
            BarButton {
                text: "Cancel"
                wide: true
                enabled: Workspace.busy
                onClicked: Workspace.cancel()
            }
        }
        TextField {
            id: masks
            objectName: "workspaceSearchMasks"
            Layout.fillWidth: true
            color: Prefs.chromeText
            placeholderText: "Filename filters, e.g. *.py;*.qml (empty = all)"
        }
        RowLayout {
            CheckBox { id: caseBox; text: "Match case" }
            CheckBox { id: wordBox; text: "Whole word" }
        }
        Label {
            text: Workspace.status
            color: Prefs.chromeText
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }
        ListView {
            id: results
            objectName: "workspaceSearchResults"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: Workspace.matches
            ScrollBar.vertical: ScrollBar {}
            Keys.onReturnPressed: {
                if (currentIndex >= 0) {
                    root.close()
                    root.matchRequested(Workspace.matches[currentIndex])
                }
            }
            delegate: ItemDelegate {
                required property var modelData
                required property int index
                objectName: "workspaceSearchMatch:" + index
                width: results.width
                highlighted: results.currentIndex === index
                contentItem: Column {
                    Label {
                        width: parent.width
                        text: modelData.label + ":" + modelData.line + ":" + modelData.column
                        color: Prefs.accent
                        elide: Text.ElideMiddle
                    }
                    Label {
                        width: parent.width
                        text: modelData.preview
                        color: Prefs.chromeText
                        elide: Text.ElideRight
                    }
                }
                background: Rectangle { color: highlighted ? Prefs.selection : "transparent" }
                onClicked: {
                    root.close()
                    root.matchRequested(modelData)
                }
            }
        }
    }
}
