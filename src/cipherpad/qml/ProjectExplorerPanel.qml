import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import Cipherpad

// Sidebar panel providing multi-folder workspace navigation and management.
Rectangle {
    id: root

    color: Prefs.chrome

    signal openFileRequested(string path)

    function openAddFolderDialog() {
        folderDialog.open()
    }

    FolderDialog {
        id: folderDialog
        title: "Select Folder to Add to Explorer"
        onAccepted: {
            const raw = String(selectedFolder)
            Explorer.addFolder(raw)
        }
    }

    AppDialog {
        id: nameDialog
        property string itemType: "file" // "file" | "folder"
        property string parentDir: ""
        heading: itemType === "file" ? "New File" : "New Folder"
        standardButtons: Dialog.Ok | Dialog.Cancel
        width: 360

        function prompt(type, dir) {
            itemType = type
            parentDir = dir
            nameField.text = ""
            open()
            nameField.forceActiveFocus()
        }

        ColumnLayout {
            width: parent.width
            spacing: 8
            Label {
                text: nameDialog.itemType === "file" ? "File name:" : "Folder name:"
                color: Prefs.chromeText
                font.pixelSize: Math.max(11, Prefs.fontSize - 1)
            }
            EditorTextField {
                id: nameField
                Layout.fillWidth: true
                placeholderText: nameDialog.itemType === "file" ? "e.g. main.py, notes.txt" : "e.g. src, docs"
                onAccepted: nameDialog.accept()
            }
        }

        onAccepted: {
            const name = nameField.text.trim()
            if (!name) return
            if (itemType === "file") {
                const created = Explorer.createFile(parentDir, name)
                if (created) {
                    root.openFileRequested(created)
                }
            } else {
                Explorer.createFolder(parentDir, name)
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // -------------------------------------------------- explorer header
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 28
            color: Prefs.chrome

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: Prefs.border
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 6
                spacing: 2

                Label {
                    text: "EXPLORER"
                    color: Prefs.chromeText
                    opacity: 0.75
                    font.bold: true
                    font.pixelSize: Math.max(10, Prefs.fontSize - 3)
                    Layout.fillWidth: true
                }

                BarButton {
                    text: "+"
                    tip: "Add Folder to Workspace\u2026"
                    implicitWidth: 22
                    implicitHeight: 22
                    onClicked: folderDialog.open()
                }

                BarButton {
                    text: "\u27f3"
                    tip: "Refresh Explorer"
                    implicitWidth: 22
                    implicitHeight: 22
                    onClicked: Explorer.refresh()
                }

                BarButton {
                    text: "\u2913"
                    tip: "Collapse All Folders"
                    implicitWidth: 22
                    implicitHeight: 22
                    onClicked: Explorer.collapseAll()
                }

                BarButton {
                    text: "\u2715"
                    tip: "Close Explorer (Ctrl+B)"
                    implicitWidth: 22
                    implicitHeight: 22
                    onClicked: Prefs.showProjectExplorer = false
                }
            }
        }

        // ---------------------------------------------------- empty state
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: Explorer.rootFolderCount === 0

            ColumnLayout {
                anchors.centerIn: parent
                spacing: 10
                width: parent.width - 24

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "\ud83d\udcc1"
                    font.pixelSize: 28
                    opacity: 0.6
                }

                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: "No folders in explorer"
                    color: Prefs.chromeText
                    opacity: 0.6
                    font.pixelSize: Math.max(11, Prefs.fontSize - 1)
                }

                BarButton {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Add Folder\u2026"
                    tip: "Add folder to workspace"
                    wide: true
                    onClicked: folderDialog.open()
                }
            }
        }

        // ------------------------------------------------------- file tree
        ListView {
            id: treeView
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: Explorer.rootFolderCount > 0
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: Explorer

            HoverHandler {
                id: treeHover
            }

            ScrollBar.vertical: ScrollBar {
                active: treeView.moving || treeHover.hovered
            }

            delegate: Rectangle {
                id: delegateItem
                width: treeView.width
                implicitHeight: 24

                required property int index
                required property string name
                required property string path
                required property bool isDir
                required property bool isRoot
                required property int depth
                required property bool expanded
                required property bool hasChildren
                required property string fileType
                required property string rootPath

                readonly property bool isCurrentFile: !isDir && !!window.currentDoc
                                                      && window.currentDoc.filePath === path
                readonly property bool rowHovered: rowHover.hovered

                color: rowHovered ? (isCurrentFile ? Prefs.selection : Prefs.border)
                       : isCurrentFile ? Prefs.selection
                       : "transparent"
                opacity: isCurrentFile && !rowHovered ? 0.45 : (rowHovered ? 0.7 : 1.0)

                HoverHandler {
                    id: rowHover
                }

                // Declared before the row so the row's buttons (e.g. the remove
                // button) sit on top and receive their own clicks.
                MouseArea {
                    id: delegateMouse
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton | Qt.RightButton

                    onClicked: function (mouse) {
                        if (mouse.button === Qt.LeftButton) {
                            if (delegateItem.isDir) {
                                Explorer.toggleExpanded(delegateItem.path)
                            } else {
                                root.openFileRequested(delegateItem.path)
                            }
                        } else if (mouse.button === Qt.RightButton) {
                            itemContextMenu.popup()
                        }
                    }
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Math.max(4, delegateItem.depth * 14 + 4)
                    anchors.rightMargin: 6
                    spacing: 4

                    // Expand / collapse arrow or spacer
                    Item {
                        implicitWidth: 12
                        implicitHeight: 16

                        Text {
                            visible: delegateItem.isDir
                            anchors.centerIn: parent
                            text: delegateItem.expanded ? "\u25be" : "\u25b8"
                            color: Prefs.chromeText
                            font.pixelSize: 11
                            opacity: 0.75
                        }
                    }

                    // Icon
                    Text {
                        text: {
                            if (delegateItem.isRoot) return "\ud83d\udcc1"
                            if (delegateItem.isDir) return delegateItem.expanded ? "\ud83d\udcc2" : "\ud83d\udcc1"
                            if (delegateItem.fileType === "encrypted") return "\ud83d\udd12"
                            if (delegateItem.fileType === "python") return "\ud83d\udc0d"
                            return "\ud83d\udcc4"
                        }
                        font.pixelSize: 12
                        Layout.alignment: Qt.AlignVCenter
                    }

                    // Item Name
                    Text {
                        Layout.fillWidth: true
                        text: delegateItem.name
                        color: Prefs.chromeText
                        font.pixelSize: Math.max(11, Prefs.fontSize - 2)
                        font.bold: delegateItem.isRoot
                        elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                    }

                    // Remove button for root folders
                    BarButton {
                        visible: delegateItem.isRoot && delegateItem.rowHovered
                        text: "\u2715"
                        tip: "Remove from Explorer"
                        implicitWidth: 16
                        implicitHeight: 16
                        onClicked: Explorer.removeFolder(delegateItem.path)
                    }
                }

                AppMenu {
                    id: itemContextMenu

                    // Hidden menu entries still occupy space in a Menu, so
                    // conditional entries collapse their height when hidden.
                    AppMenuItem {
                        text: "Open"
                        visible: !delegateItem.isDir
                        height: visible ? implicitHeight : 0
                        onTriggered: root.openFileRequested(delegateItem.path)
                    }

                    AppMenuItem {
                        text: "New File\u2026"
                        visible: delegateItem.isDir
                        height: visible ? implicitHeight : 0
                        onTriggered: nameDialog.prompt("file", delegateItem.path)
                    }

                    AppMenuItem {
                        text: "New Folder\u2026"
                        visible: delegateItem.isDir
                        height: visible ? implicitHeight : 0
                        onTriggered: nameDialog.prompt("folder", delegateItem.path)
                    }

                    AppMenuItem {
                        text: "Refresh"
                        visible: delegateItem.isDir
                        height: visible ? implicitHeight : 0
                        onTriggered: Explorer.refresh()
                    }

                    AppMenuItem {
                        text: "Remove Folder from Explorer"
                        visible: delegateItem.isRoot
                        height: visible ? implicitHeight : 0
                        onTriggered: Explorer.removeFolder(delegateItem.path)
                    }

                    MenuSeparator {
                        contentItem: Rectangle {
                            implicitHeight: 1
                            color: Prefs.border
                        }
                    }

                    AppMenuItem {
                        text: "Copy Path"
                        onTriggered: Explorer.copyToClipboard(delegateItem.path)
                    }
                }
            }
        }
    }
}
