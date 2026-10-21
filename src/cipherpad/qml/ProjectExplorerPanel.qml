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
    property int currentExplorerRow: -1
    property var selectedPaths: []
    readonly property var selectedFiles: selectedPaths.filter(path => {
        const row = indexForPath(path)
        return row >= 0 && !Explorer.itemAt(row).isDir
    })
    property string selectionAnchor: ""
    readonly property bool canModifySelection: selectedPaths.length > 0
        && !selectedPaths.some(path => Explorer.rootFolders.includes(path))
    readonly property bool treeFocused: treeView.activeFocus
    signal compareFilesRequested(var paths)

    function fileTypeIcon(fileType) {
        const icons = {
            python: "\ud83d\udc0d",
            javascript: "JS",
            typescript: "TS",
            qml: "\ud83e\udde9",
            c: "C",
            cpp: "C++",
            csharp: "C#",
            java: "\u2615",
            go: "\ud83d\udc39",
            rust: "\ud83e\udd80",
            json: "{}",
            xml: "<>",
            html: "\ud83c\udf10",
            css: "\ud83c\udfa8",
            markdown: "\ud83d\udcdd",
            yaml: "\u2699\ufe0f",
            toml: "\u2699\ufe0f",
            ini: "\u2699\ufe0f",
            shell: ">_",
            powershell: ">_",
            sql: "\ud83d\uddc4\ufe0f",
            encrypted: "\ud83d\udd12",
            text: "\ud83d\udcc4",
            file: "\ud83d\udcc4"
        }
        return icons[fileType] || "\ud83d\udcc4"
    }

    function selectPath(path, isDir, toggle, range) {
        selectedPath = path
        selectedIsDir = isDir
        if (range && indexForPath(selectionAnchor) >= 0) {
            const from = indexForPath(selectionAnchor)
            const to = indexForPath(path)
            let paths = toggle ? selectedPaths.slice() : []
            for (let row = Math.min(from, to); row <= Math.max(from, to); ++row) {
                const candidate = Explorer.itemAt(row).path
                if (!paths.includes(candidate))
                    paths.push(candidate)
            }
            selectedPaths = paths
        } else {
            selectedPaths = toggle
                ? (selectedPaths.includes(path) ? selectedPaths.filter(item => item !== path) : selectedPaths.concat([path]))
                : [path]
            selectionAnchor = path
        }
        currentExplorerRow = -1
        for (let i = 0; i < Explorer.count; ++i) {
            const item = Explorer.itemAt(i)
            if (item.path === path) {
                currentExplorerRow = i
                treeView.positionViewAtRow(i, TableView.Contain)
                break
            }
        }
        treeView.forceActiveFocus()
    }

    function selectIndex(index, range) {
        if (Explorer.count === 0)
            return
        const targetIndex = Math.max(0, Math.min(Explorer.count - 1, index))
        const item = Explorer.itemAt(targetIndex)
        if (item)
            selectPath(item.path, item.isDir, false, range)
    }

    function moveSelection(delta, range) {
        if (Explorer.count === 0)
            return
        selectIndex(currentExplorerRow < 0 || !selectedPath
            ? (delta >= 0 ? 0 : Explorer.count - 1)
            : currentExplorerRow + delta, range)
    }

    function activateSelection() {
        const item = Explorer.itemAt(currentExplorerRow)
        if (!item)
            return
        if (item.isDir)
            toggleTreeExpansion(currentExplorerRow)
        else
            root.openFileRequested(item.path)
    }

    function expandSelection() {
        const row = currentExplorerRow
        const item = Explorer.itemAt(row)
        if (!item || !item.isDir)
            return
        if (!treeView.isExpanded(row)) {
            treeView.expand(row)
            return
        }
        const child = Explorer.itemAt(row + 1)
        if (child && child.depth > item.depth)
            selectPath(child.path, child.isDir, false)
    }

    function collapseSelection() {
        const row = currentExplorerRow
        const item = Explorer.itemAt(row)
        if (!item)
            return
        if (item.isDir && treeView.isExpanded(row)) {
            treeView.collapse(row)
            return
        }
        const parentIndex = indexForPath(Explorer.parentDirectory(item.path))
        if (parentIndex >= 0)
            selectIndex(parentIndex)
    }

    function toggleTreeExpansion(row) {
        if (treeView.isExpanded(row))
            treeView.collapse(row)
        else
            treeView.expand(row)
    }

    function syncTreeExpansion() {
        let row = 0
        while (row < Explorer.count) {
            const item = Explorer.itemAt(row)
            if (item.isDir && item.expanded && item.hasChildren && !treeView.isExpanded(row))
                treeView.expand(row)
            ++row
        }
    }

    function indexForPath(path) {
        for (let i = 0; i < Explorer.count; ++i) {
            if (Explorer.itemAt(i).path === path)
                return i
        }
        return -1
    }
    function compareSelected() {
        compareFilesRequested(selectedPaths.length === 2 ? selectedFiles : [])
    }
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
        function onRootFoldersChanged() {
            filenameFilter.text = ""
            root.selectedPaths = []
            root.selectionAnchor = ""
            root.selectedPath = ""
            root.selectedIsDir = false
            root.currentExplorerRow = -1
        }
        function onCountChanged() {
            Qt.callLater(root.syncTreeExpansion)
            const visiblePaths = []
            for (let i = 0; i < Explorer.count; ++i) {
                const item = Explorer.itemAt(i)
                visiblePaths.push(item.path)
            }
            root.selectedPaths = root.selectedPaths.filter(path => visiblePaths.includes(path))
            const selectedRow = root.indexForPath(root.selectedPath)
            if (selectedRow >= 0)
                root.currentExplorerRow = selectedRow
            else if (root.selectedPath) {
                root.selectedPath = ""
                root.selectedIsDir = false
                root.currentExplorerRow = -1
            }
        }
    }
    Connections {
        target: Explorer.treeModel
        function onModelReset() { Qt.callLater(root.syncTreeExpansion) }
    }
    Timer {
        id: filterDelay
        interval: 150
        onTriggered: root.applyFilter()
    }

    FolderDialog {
        id: moveDialog
        title: "Move Selected Items to Folder"
        property var sourcePaths: []
        onAccepted: Explorer.transferItems(sourcePaths, String(selectedFolder), true)
    }

    function moveSelected() {
        moveDialog.sourcePaths = selectedPaths.slice()
        moveDialog.open()
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
                const wasDir = root.selectedIsDir
                const renamed = Explorer.rename(sourcePath, name)
                if (renamed)
                    root.selectPath(renamed, wasDir, false)
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
        heading: targetPaths.length > 1 ? "Delete Selected Items" : "Delete Item"
        standardButtons: Dialog.Yes | Dialog.Cancel
        width: 420
        property string targetPath: ""
        property string targetName: ""
        property var targetPaths: []
        function prompt(path, name) {
            targetPath = path
            targetName = name
            targetPaths = root.selectedPaths.slice()
            open()
        }
        Label {
            width: parent.width
            text: (deleteDialog.targetPaths.length > 1
                  ? "Move " + deleteDialog.targetPaths.length + " selected items"
                  : "Move \"" + deleteDialog.targetName + "\"")
                  + " to Trash/Recycle Bin? All contents of selected folders are included."
            color: Prefs.chromeText
            wrapMode: Text.Wrap
        }
        onAccepted: {
            Explorer.deleteItems(targetPaths)
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
                    text: "EXPLORER" + (root.selectedPaths.length > 1 ? " (" + root.selectedPaths.length + ")" : "")
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
                onClicked: Explorer.pasteItems(root.targetDirectory)
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
        TreeView {
            id: treeView
            objectName: "projectExplorerTree"
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: Explorer.rootFolderCount > 0
            activeFocusOnTab: true
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: Explorer.treeModel
            rowSpacing: 0
            columnSpacing: 0

            Component.onCompleted: Qt.callLater(root.syncTreeExpansion)
            onExpanded: function(row) {
                const item = Explorer.itemAt(row)
                if (item)
                    Explorer.expand(item.path)
            }
            onCollapsed: function(row) {
                const item = Explorer.itemAt(row)
                if (item)
                    Explorer.collapse(item.path)
            }

            Keys.priority: Keys.BeforeItem
            Keys.onPressed: function(event) {
                const ctrl = (event.modifiers & Qt.ControlModifier) !== 0
                const range = (event.modifiers & Qt.ShiftModifier) !== 0
                if (ctrl) {
                    if (event.key === Qt.Key_A) {
                        const paths = []
                        for (let i = 0; i < Explorer.count; ++i) {
                            const item = Explorer.itemAt(i)
                            if (!item.isRoot)
                                paths.push(item.path)
                        }
                        root.selectedPaths = paths
                    } else if (event.key === Qt.Key_C || event.key === Qt.Key_X) {
                        Explorer.copyItems(root.selectedPaths, event.key === Qt.Key_X)
                    } else if (event.key === Qt.Key_V) {
                        Explorer.pasteItems(root.targetDirectory)
                    } else
                        return
                    event.accepted = true
                    return
                }
                switch (event.key) {
                case Qt.Key_Up:
                    root.moveSelection(-1, range)
                    break
                case Qt.Key_Down:
                    root.moveSelection(1, range)
                    break
                case Qt.Key_Home:
                    root.selectIndex(0, range)
                    break
                case Qt.Key_End:
                    root.selectIndex(Explorer.count - 1, range)
                    break
                case Qt.Key_Delete:
                    if (root.canModifySelection)
                        deleteDialog.prompt(root.selectedPath, Explorer.itemAt(root.currentExplorerRow).name || "")
                    break
                case Qt.Key_Escape:
                    root.selectedPaths = []
                    break
                case Qt.Key_Left:
                    root.collapseSelection()
                    break
                case Qt.Key_Right:
                    root.expandSelection()
                    break
                case Qt.Key_Return:
                case Qt.Key_Enter:
                    root.activateSelection()
                    break
                default:
                    return
                }
                event.accepted = true
            }

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
                implicitWidth: treeView.width
                implicitHeight: 24

                required property int row
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

                color: root.selectedPaths.includes(path) ? Prefs.selection : rowHovered ? (isCurrentFile ? Prefs.selection : Prefs.border)
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
                    objectName: "explorerRow:" + delegateItem.path
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton | Qt.RightButton

                    onClicked: function (mouse) {
                        const toggle = (mouse.modifiers & Qt.ControlModifier) !== 0
                        const range = (mouse.modifiers & Qt.ShiftModifier) !== 0
                        if (mouse.button !== Qt.RightButton || !root.selectedPaths.includes(delegateItem.path))
                            root.selectPath(delegateItem.path, delegateItem.isDir, toggle, range)
                        else {
                            root.selectedPath = delegateItem.path
                            root.selectedIsDir = delegateItem.isDir
                            root.currentExplorerRow = delegateItem.row
                            treeView.forceActiveFocus()
                        }
                        if (mouse.button === Qt.LeftButton) {
                            if (delegateItem.isDir && !toggle && !range) {
                                root.toggleTreeExpansion(delegateItem.row)
                            } else if (!delegateItem.isDir && !toggle && !range) {
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
                            visible: delegateItem.hasChildren
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
                            return root.fileTypeIcon(delegateItem.fileType)
                        }
                        font.pixelSize: 12
                        Layout.preferredWidth: 24
                        Layout.alignment: Qt.AlignVCenter
                        horizontalAlignment: Text.AlignHCenter
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
                        objectName: "explorerCompareItem"
                        text: "Compare Selected Files"
                        shortcutText: "Ctrl+D"
                        enabled: root.selectedPaths.length === 2 && root.selectedFiles.length === 2
                        onTriggered: root.compareSelected()
                    }
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
                        enabled: root.selectedPaths.length === 1
                        onTriggered: nameDialog.promptRename(delegateItem.path, delegateItem.name)
                    }
                    AppMenuItem {
                        objectName: "explorerDuplicateItem"
                        text: "Duplicate"
                        enabled: !delegateItem.isRoot && root.selectedPaths.length === 1
                        onTriggered: Explorer.duplicateItem(delegateItem.path)
                    }
                    AppMenuItem {
                        objectName: "explorerCutItem"
                        text: "Cut"
                        enabled: root.canModifySelection
                        onTriggered: Explorer.copyItems(root.selectedPaths, true)
                    }
                    AppMenuItem {
                        objectName: "explorerCopyItem"
                        text: "Copy"
                        onTriggered: Explorer.copyItems(root.selectedPaths, false)
                    }
                    AppMenuItem {
                        objectName: "explorerPasteItem"
                        text: "Paste"
                        enabled: Explorer.canPaste
                        onTriggered: Explorer.pasteItems(root.targetDirectory)
                    }
                    AppMenuItem {
                        objectName: "explorerMoveItems"
                        text: "Move Selected Items To\u2026"
                        enabled: root.canModifySelection
                        onTriggered: root.moveSelected()
                    }
                    AppMenuItem {
                        objectName: "explorerDeleteItem"
                        text: "Delete\u2026"
                        enabled: root.canModifySelection
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
