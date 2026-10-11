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
    property string selectedPath: ""
    property bool selectedIsDir: false
    readonly property string targetDirectory: selectedPath
        ? (selectedIsDir ? selectedPath : Explorer.parentDirectory(selectedPath))
        : (Explorer.rootFolders.length > 0 ? Explorer.rootFolders[0] : "")

    function openAddFolderDialog() {
        folderDialog.open()
    }

    function applyFilter() {
        if (filenameFilter.text.trim())
            Explorer.setFilterPaths(Workspace.filterPaths(filenameFilter.text))
        else
            Explorer.clearFilter()
    }

    Connections {
        target: Workspace
        function onEntriesChanged() { root.applyFilter() }
    }
    Connections {
        target: Explorer
        function onOptionsChanged() { filenameFilter.text = "" }
        function onRootFoldersChanged() { filenameFilter.text = "" }
    }
    Timer {
        id: filterDelay
        interval: 150
        onTriggered: root.applyFilter()
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
        objectName: "explorerNameDialog"
        property string itemType: "file" // "file" | "folder"
        property string parentDir: ""
        property string sourcePath: ""
        heading: itemType === "rename" ? "Rename Item" : (itemType === "file" ? "New File" : "New Folder")
        standardButtons: Dialog.Ok | Dialog.Cancel
        width: 360

        function prompt(type, dir) {
            itemType = type
            parentDir = dir
            sourcePath = ""
            nameField.text = ""
            open()
            nameField.forceActiveFocus()
        }

        function promptRename(path, name) {
            itemType = "rename"
            sourcePath = path
            nameField.text = name
            open()
            nameField.forceActiveFocus()
            nameField.selectAll()
        }

        ColumnLayout {
            width: parent.width
            spacing: 8
            Label {
                text: nameDialog.itemType === "rename" ? "New name:" : (nameDialog.itemType === "file" ? "File name:" : "Folder name:")
                color: Prefs.chromeText
                font.pixelSize: Math.max(11, Prefs.fontSize - 1)
            }
            EditorTextField {
                id: nameField
                objectName: "explorerNameField"
                Layout.fillWidth: true
                placeholderText: nameDialog.itemType === "file" ? "e.g. main.py, notes.txt" : "e.g. src, docs"
                onAccepted: nameDialog.accept()
            }
        }

        onAccepted: {
            const name = nameField.text.trim()
            if (itemType === "rename") {
                const renamed = Explorer.rename(sourcePath, name)
                if (renamed && root.selectedPath === sourcePath)
                    root.selectedPath = renamed
            } else if (itemType === "file") {
                const created = Explorer.createFile(parentDir, name)
                if (created) {
                    root.openFileRequested(created)
                }
            } else {
                Explorer.createFolder(parentDir, name)
            }
        }
    }

    AppDialog {
        id: deleteDialog
        objectName: "explorerDeleteDialog"
        heading: "Delete Item"
        standardButtons: Dialog.Yes | Dialog.Cancel
        width: 420
        property string targetPath: ""
        property string targetName: ""
        function prompt(path, name) {
            targetPath = path
            targetName = name
            open()
        }
        Label {
            width: parent.width
            text: "Move \"" + deleteDialog.targetName
                  + "\" to Trash/Recycle Bin? All contents of a folder are included."
            color: Prefs.chromeText
            wrapMode: Text.Wrap
        }
        onAccepted: {
            if (Explorer.deleteItem(targetPath)) {
                root.selectedPath = ""
                root.selectedIsDir = false
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

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 6
            Layout.rightMargin: 6
            visible: Explorer.rootFolderCount > 0
            spacing: 2
            BarButton {
                objectName: "explorerNewFileButton"
                text: "+F"
                tip: "New File in Selected Folder"
                enabled: root.targetDirectory !== ""
                onClicked: nameDialog.prompt("file", root.targetDirectory)
            }
            BarButton {
                objectName: "explorerNewFolderButton"
                text: "+D"
                tip: "New Folder in Selected Folder"
                enabled: root.targetDirectory !== ""
                onClicked: nameDialog.prompt("folder", root.targetDirectory)
            }
            BarButton {
                objectName: "explorerPasteButton"
                text: "Paste"
                tip: "Paste Copied/Cut Explorer Item"
                enabled: Explorer.canPaste && root.targetDirectory !== ""
                implicitWidth: 48
                onClicked: Explorer.pasteItem(root.targetDirectory)
            }
            Item { Layout.fillWidth: true }
        }

        // ---------------------------------------------------- empty state
        TextField {
            id: filenameFilter
            objectName: "explorerFilterField"
            Layout.fillWidth: true
            Layout.leftMargin: 6
            Layout.rightMargin: 6
            visible: Explorer.rootFolderCount > 0
            color: Prefs.chromeText
            placeholderText: Workspace.busy ? "Scanning..." : "Filter files (*.py or name)"
            onTextChanged: {
                if (!text.trim())
                    Explorer.clearFilter()
                else
                    filterDelay.restart()
            }
            onActiveFocusChanged: if (activeFocus && !Workspace.busy) Workspace.scanFiles()
            Keys.onEscapePressed: text = ""
            ToolTip.visible: hovered
            ToolTip.text: "Filters workspace paths, retaining matching ancestors. " + Workspace.status
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
                objectName: "explorerItem:" + path
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
                        root.selectedPath = delegateItem.path
                        root.selectedIsDir = delegateItem.isDir
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
                    objectName: "explorerItemMenu"

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
                        onTriggered: nameDialog.prompt("file", root.targetDirectory)
                    }

                    AppMenuItem {
                        text: "New Folder\u2026"
                        onTriggered: nameDialog.prompt("folder", root.targetDirectory)
                    }

                    MenuSeparator {}
                    AppMenuItem {
                        objectName: "explorerRenameItem"
                        text: "Rename\u2026"
                        onTriggered: nameDialog.promptRename(delegateItem.path, delegateItem.name)
                    }
                    AppMenuItem {
                        objectName: "explorerDuplicateItem"
                        text: "Duplicate"
                        enabled: !delegateItem.isRoot
                        onTriggered: Explorer.duplicateItem(delegateItem.path)
                    }
                    AppMenuItem {
                        objectName: "explorerCutItem"
                        text: "Cut"
                        enabled: !delegateItem.isRoot
                        onTriggered: Explorer.copyItem(delegateItem.path, true)
                    }
                    AppMenuItem {
                        objectName: "explorerCopyItem"
                        text: "Copy"
                        onTriggered: Explorer.copyItem(delegateItem.path, false)
                    }
                    AppMenuItem {
                        objectName: "explorerPasteItem"
                        text: "Paste"
                        enabled: Explorer.canPaste
                        onTriggered: Explorer.pasteItem(root.targetDirectory)
                    }
                    AppMenuItem {
                        objectName: "explorerDeleteItem"
                        text: "Delete\u2026"
                        enabled: !delegateItem.isRoot
                        onTriggered: deleteDialog.prompt(delegateItem.path, delegateItem.name)
                    }
                    MenuSeparator {}
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
                    AppMenuItem {
                        text: "Copy Relative Path"
                        onTriggered: Explorer.copyPathToClipboard(delegateItem.path, true)
                    }
                    AppMenuItem {
                        text: "Reveal in File Explorer"
                        onTriggered: Explorer.revealItem(delegateItem.path)
                    }
                }
            }
        }
    }
}
