import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import Cipherpad

ApplicationWindow {
    id: window

    width: Prefs.windowWidth
    height: Prefs.windowHeight
    color: Prefs.background
    font.pixelSize: Prefs.fontSize
    title: (currentDoc
            ? (currentDoc.modified ? "\u2022 " : "") + currentDoc.displayName + " \u2014 "
            : "") + "Cipherpad"

    readonly property var currentDoc: Documents.currentDocument
    readonly property var currentPane: Documents.count >= 0 ? paneRepeater.itemAt(Documents.currentIndex) : null
    property int pendingCloseIndex: -1
    property string pendingAction: ""
    property var pendingPaths: []

    onWidthChanged: if (visibility === Window.Windowed) Prefs.windowWidth = width
    onHeightChanged: if (visibility === Window.Windowed) Prefs.windowHeight = height
    // Only record user-visible states; Hidden (on close) and Minimized must not
    // overwrite the saved maximized flag.
    onVisibilityChanged: function (visibility) {
        if (visibility === Window.Maximized || visibility === Window.Windowed)
            Prefs.windowMaximized = (visibility === Window.Maximized)
    }

    Component.onCompleted: {
        if (Prefs.windowMaximized)
            showMaximized()
        else
            show()
    }

    onClosing: function (close) {
        if (Documents.hasModifiedDocuments && pendingAction !== "quit") {
            close.accepted = false
            pendingAction = "quit"
            unsavedDialog.openFor(-1)
        }
    }

    // ------------------------------------------------------------ commands
    function paneAt(index) { return paneRepeater.itemAt(index) }

    function newFile() {
        Documents.currentIndex = Documents.newDocument()
    }

    function openFiles(paths) {
        for (let i = 0; i < paths.length; ++i) {
            const path = String(paths[i]).replace(/^file:\/{3}/, "")
            const result = Documents.openFile(path)
            if (result === -2) {
                pendingPaths = paths.slice(i + 1)
                passphraseDialog.intent = "open"
                passphraseDialog.pendingPath = path
                passphraseDialog.promptUnlock(baseName(path), "")
                return
            }
            if (result >= 0) {
                Documents.currentIndex = result
                Prefs.addRecentFile(path)
            }
        }
    }

    function baseName(path) {
        const parts = String(path).split(/[\\/]/)
        return parts[parts.length - 1]
    }

    function startEncrypt() {
        if (!currentDoc || currentDoc.encrypted)
            return
        if (currentDoc.isUntitled) {
            saveDialog.encrypting = true
            passphraseDialog.intent = "saveAs"
            saveDialog.open()
            return
        }
        passphraseDialog.intent = "encrypt"
        passphraseDialog.promptNew(currentDoc.displayName)
    }

    function saveCurrent() {
        if (!currentDoc)
            return false
        if (currentDoc.isUntitled) {
            saveDialog.open()
            return false
        }
        const ok = currentDoc.save(preparedText())
        if (ok) {
            currentDoc.modified = false
            status.flash("Saved " + currentDoc.fileName)
            Prefs.addRecentFile(currentDoc.filePath)
        }
        return ok
    }

    // Applies the on-save clean-ups through the metrics layer so they are
    // undoable and the editor stays in sync with what hits the disk.
    function preparedText() {
        const pane = currentPane
        if (!pane)
            return ""
        if (Prefs.trimTrailingWhitespaceOnSave) {
            const span = TextOps.trimTrailingWhitespace(pane.editor.text, 0, pane.editor.text.length)
            pane.applySpan(span)
        }
        let text = pane.editor.text
        if (Prefs.ensureNewlineAtEof && text.length > 0 && !text.endsWith("\n")) {
            pane.metrics.replaceRange(text.length, text.length, "\n")
            text = pane.editor.text
        }
        return text
    }

    function closeTab(index) {
        const doc = Documents.documentAt(index)
        if (doc && doc.modified) {
            pendingAction = "close"
            unsavedDialog.openFor(index)
            return
        }
        Documents.closeDocument(index)
    }

    function runOp(fn) {
        const pane = currentPane
        if (!pane)
            return
        pane.applySpan(fn(pane.editor.text, pane.editor.selectionStart, pane.editor.selectionEnd))
        pane.focusEditor()
    }

    function toast(message) { status.flash(message) }

    // ------------------------------------------------------------- dialogs
    FileDialog {
        id: openDialog
        title: "Open files"
        fileMode: FileDialog.OpenFiles
        nameFilters: ["All files (*)", "Text files (*.txt *.md *.log)",
                      "Encrypted files (*.enc *.aes)", "Source files (*.py *.js *.json *.xml *.html *.css)"]
        onAccepted: window.openFiles(selectedFiles)
    }

    FolderDialog {
        id: openFolderDialog
        title: "Open Folder"
        onAccepted: {
            if (Explorer.addFolder(String(selectedFolder))) {
                Prefs.showProjectExplorer = true
            }
        }
    }

    FileDialog {
        id: saveDialog
        title: "Save as"
        fileMode: FileDialog.SaveFile
        nameFilters: ["All files (*)", "Text files (*.txt)", "Encrypted files (*.enc)"]
        property bool encrypting: false
        onAccepted: {
            const path = String(selectedFile).replace(/^file:\/{3}/, "")
            if (encrypting) {
                passphraseDialog.pendingPath = path
                passphraseDialog.promptNew(window.baseName(path))
            } else {
                if (window.currentDoc.saveAs(path, window.preparedText())) {
                    window.currentDoc.modified = false
                    Prefs.addRecentFile(path)
                    Documents.refresh(Documents.currentIndex)
                    status.flash("Saved " + window.baseName(path))
                }
            }
            encrypting = false
        }
    }

    PassphraseDialog {
        id: passphraseDialog
        property string pendingPath: ""
        // "open" | "saveAs" | "encrypt" | "change"
        property string intent: "open"

        onPassphraseAccepted: function (passphrase) {
            switch (intent) {
            case "open": {
                const result = Documents.openFile(pendingPath, passphrase)
                if (result >= 0) {
                    Documents.currentIndex = result
                    Prefs.addRecentFile(pendingPath)
                    if (window.pendingPaths.length > 0) {
                        const rest = window.pendingPaths
                        window.pendingPaths = []
                        window.openFiles(rest)
                    }
                } else {
                    promptUnlock(window.baseName(pendingPath), "Wrong passphrase, or the file is damaged.")
                }
                break
            }
            case "saveAs":
                if (window.currentDoc.saveAs(pendingPath, window.preparedText(), true, passphrase)) {
                    window.currentDoc.modified = false
                    Prefs.addRecentFile(pendingPath)
                    Documents.refresh(Documents.currentIndex)
                    status.flash("Saved encrypted " + window.baseName(pendingPath))
                }
                break
            case "encrypt":
                if (window.currentDoc.encryptWith(window.preparedText(), passphrase)) {
                    window.currentDoc.modified = false
                    Documents.refresh(Documents.currentIndex)
                    status.flash("File is now encrypted")
                }
                break
            case "change":
                if (window.currentDoc.changePassphrase(window.preparedText(), passphrase))
                    status.flash("Passphrase changed")
                break
            }
        }

        onRejected: {
            window.pendingPaths = []
        }
    }

    GoToLineDialog {
        id: gotoDialog
        onLineRequested: function (line) { if (window.currentPane) window.currentPane.goToLine(line) }
    }

    PreferencesDialog { id: prefsDialog }
    AboutDialog { id: aboutDialog }
    StatisticsDialog { id: statsDialog }

    AppDialog {
        id: unsavedDialog
        heading: "Unsaved changes"
        standardButtons: Dialog.Save | Dialog.Discard | Dialog.Cancel
        width: 400

        property int index: -1
        property string names: ""

        function openFor(idx) {
            index = idx
            if (idx >= 0) {
                const doc = Documents.documentAt(idx)
                names = doc ? doc.displayName : ""
            } else {
                names = "One or more files"
            }
            open()
        }

        Label {
            width: parent.width
            text: unsavedDialog.index >= 0
                  ? "\u201c" + unsavedDialog.names + "\u201d has unsaved changes."
                  : "Some open files have unsaved changes."
            color: Prefs.chromeText
            wrapMode: Text.Wrap
        }

        onAccepted: {
            // Save
            if (index >= 0) {
                Documents.currentIndex = index
                if (window.saveCurrent()) {
                    Documents.closeDocument(index)
                }
            } else {
                for (let i = 0; i < Documents.count; ++i) {
                    Documents.currentIndex = i
                    if (Documents.currentDocument.modified)
                        window.saveCurrent()
                }
                if (!Documents.hasModifiedDocuments)
                    Qt.quit()
            }
            window.pendingAction = ""
        }

        onDiscarded: {
            if (index >= 0) {
                Documents.documentAt(index).modified = false
                Documents.closeDocument(index)
            } else {
                Documents.closeAll()
                Qt.quit()
            }
            window.pendingAction = ""
            close()
        }

        onRejected: window.pendingAction = ""
    }

    AppDialog {
        id: messageDialog
        heading: "Error"
        standardButtons: Dialog.Close
        width: 420
        property string message: ""
        function show(text) { message = text; open() }
        Label {
            width: parent.width
            text: messageDialog.message
            color: Prefs.chromeText
            wrapMode: Text.Wrap
        }
    }

    Connections {
        target: Documents
        function onErrorOccurred(message) { messageDialog.show(message) }
    }

    // ---------------------------------------------------------------- menu
    menuBar: MenuBar {
        background: Rectangle {
            color: Prefs.chrome
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: Prefs.border
            }
        }
        delegate: MenuBarItem {
            id: menuBarItem
            contentItem: Text {
                text: menuBarItem.text
                color: Prefs.chromeText
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: Math.max(11, Prefs.fontSize - 1)
            }
            background: Rectangle {
                color: menuBarItem.highlighted ? Prefs.accent : "transparent"
            }
        }

        AppMenu {
            title: "File"
            AppMenuItem { text: "New"; shortcutText: "Ctrl+N"; onTriggered: window.newFile() }
            AppMenuItem { text: "Open File\u2026"; shortcutText: "Ctrl+O"; onTriggered: openDialog.open() }
            AppMenuItem { text: "Open Folder\u2026"; shortcutText: "Ctrl+Shift+O"; onTriggered: openFolderDialog.open() }
            AppMenu {
                id: recentMenu
                title: "Open Recent"
                enabled: Prefs.recentFiles.length > 0
                Instantiator {
                    model: Prefs.recentFiles
                    delegate: AppMenuItem {
                        text: window.baseName(modelData)
                        onTriggered: window.openFiles([modelData])
                    }
                    onObjectAdded: function (index, object) { recentMenu.insertItem(index, object) }
                    onObjectRemoved: function (index, object) { recentMenu.removeItem(object) }
                }
            }
            AppMenuItem { text: "Close All Folders"; enabled: Explorer.rootFolderCount > 0; onTriggered: Explorer.clearFolders() }
            MenuSeparator {}
            AppMenuItem { text: "Save"; shortcutText: "Ctrl+S"; enabled: window.currentDoc !== null; onTriggered: window.saveCurrent() }
            AppMenuItem {
                text: "Save As\u2026"
                shortcutText: "Ctrl+Shift+S"
                enabled: window.currentDoc !== null
                onTriggered: { saveDialog.encrypting = false; saveDialog.open() }
            }
            AppMenuItem {
                text: "Save Encrypted As\u2026"
                enabled: window.currentDoc !== null
                onTriggered: {
                    saveDialog.encrypting = true
                    passphraseDialog.intent = "saveAs"
                    saveDialog.open()
                }
            }
            AppMenuItem {
                text: "Reload from Disk"
                enabled: window.currentDoc && !window.currentDoc.isUntitled
                onTriggered: window.currentDoc.reload()
            }
            MenuSeparator {}
            AppMenuItem { text: "Close Tab"; shortcutText: "Ctrl+W"; enabled: Documents.count > 0; onTriggered: window.closeTab(Documents.currentIndex) }
            AppMenuItem { text: "Quit"; shortcutText: "Ctrl+Q"; onTriggered: window.close() }
        }

        AppMenu {
            title: "Edit"
            AppMenuItem { text: "Undo"; shortcutText: "Ctrl+Z"; enabled: window.currentPane !== null; onTriggered: if (window.currentPane) window.currentPane.editor.undo() }
            AppMenuItem { text: "Redo"; shortcutText: "Ctrl+Y"; enabled: window.currentPane !== null; onTriggered: if (window.currentPane) window.currentPane.editor.redo() }
            MenuSeparator {}
            AppMenuItem { text: "Cut"; shortcutText: "Ctrl+X"; enabled: window.currentPane !== null; onTriggered: if (window.currentPane) window.currentPane.editor.cut() }
            AppMenuItem { text: "Copy"; shortcutText: "Ctrl+C"; enabled: window.currentPane !== null; onTriggered: if (window.currentPane) window.currentPane.editor.copy() }
            AppMenuItem { text: "Paste"; shortcutText: "Ctrl+V"; enabled: window.currentPane !== null; onTriggered: if (window.currentPane) window.currentPane.editor.paste() }
            AppMenuItem { text: "Select All"; shortcutText: "Ctrl+A"; enabled: window.currentPane !== null; onTriggered: if (window.currentPane) window.currentPane.editor.selectAll() }
            MenuSeparator {}
            AppMenuItem { text: "Find\u2026"; shortcutText: "Ctrl+F"; onTriggered: findBar.open(false) }
            AppMenuItem { text: "Replace\u2026"; shortcutText: "Ctrl+H"; onTriggered: findBar.open(true) }
            AppMenuItem { text: "Go to Line\u2026"; shortcutText: "Ctrl+G"; enabled: window.currentPane !== null
                onTriggered: if (window.currentPane) gotoDialog.promptFor(window.currentPane.metrics.lineCount(),
                                                  window.currentPane.currentLine) }
        }

        AppMenu {
            title: "Format"
            AppMenuItem { text: "Duplicate Line"; shortcutText: "Ctrl+D"; enabled: window.currentPane !== null
                onTriggered: window.runOp(TextOps.duplicateLines) }
            AppMenuItem { text: "Delete Line"; shortcutText: "Ctrl+Shift+K"; enabled: window.currentPane !== null
                onTriggered: window.runOp(TextOps.deleteLines) }
            AppMenuItem { text: "Move Line Up"; shortcutText: "Alt+Up"; enabled: window.currentPane !== null
                onTriggered: window.runOp(TextOps.moveLinesUp) }
            AppMenuItem { text: "Move Line Down"; shortcutText: "Alt+Down"; enabled: window.currentPane !== null
                onTriggered: window.runOp(TextOps.moveLinesDown) }
            AppMenuItem { text: "Join Lines"; shortcutText: "Ctrl+J"; enabled: window.currentPane !== null
                onTriggered: window.runOp(TextOps.joinLines) }
            MenuSeparator {}
            AppMenuItem { text: "Toggle Comment"; shortcutText: "Ctrl+/"; enabled: window.currentPane !== null
                onTriggered: {
                    const pane = window.currentPane
                    if (!pane) return
                    pane.applySpan(TextOps.toggleComment(pane.editor.text, pane.editor.selectionStart,
                                                         pane.editor.selectionEnd, window.currentDoc.language))
                }
            }
            AppMenuItem { text: "Indent"; enabled: window.currentPane !== null; onTriggered: {
                    const pane = window.currentPane
                    if (!pane) return
                    pane.applySpan(TextOps.indent(pane.editor.text, pane.editor.selectionStart,
                                                  pane.editor.selectionEnd, Prefs.tabWidth, Prefs.insertSpaces))
                } }
            AppMenuItem { text: "Unindent"; enabled: window.currentPane !== null; onTriggered: {
                    const pane = window.currentPane
                    if (!pane) return
                    pane.applySpan(TextOps.unindent(pane.editor.text, pane.editor.selectionStart,
                                                    pane.editor.selectionEnd, Prefs.tabWidth))
                } }
            MenuSeparator {}
            AppMenuItem { text: "UPPERCASE"; enabled: window.currentPane !== null; onTriggered: window.runOp(TextOps.upperCase) }
            AppMenuItem { text: "lowercase"; enabled: window.currentPane !== null; onTriggered: window.runOp(TextOps.lowerCase) }
            AppMenuItem { text: "Title Case"; enabled: window.currentPane !== null; onTriggered: window.runOp(TextOps.titleCase) }
            AppMenuItem { text: "Toggle Case"; enabled: window.currentPane !== null; onTriggered: window.runOp(TextOps.toggleCase) }
            MenuSeparator {}
            AppMenuItem { text: "Sort Lines"; enabled: window.currentPane !== null; onTriggered: {
                    const pane = window.currentPane
                    if (!pane) return
                    pane.applySpan(TextOps.sortLines(pane.editor.text, pane.editor.selectionStart,
                                                     pane.editor.selectionEnd, false, false))
                } }
            AppMenuItem { text: "Sort Lines Descending"; enabled: window.currentPane !== null; onTriggered: {
                    const pane = window.currentPane
                    if (!pane) return
                    pane.applySpan(TextOps.sortLines(pane.editor.text, pane.editor.selectionStart,
                                                     pane.editor.selectionEnd, true, false))
                } }
            AppMenuItem { text: "Remove Duplicate Lines"; enabled: window.currentPane !== null; onTriggered: window.runOp(TextOps.uniqueLines) }
            AppMenuItem { text: "Reverse Lines"; enabled: window.currentPane !== null; onTriggered: window.runOp(TextOps.reverseLines) }
            AppMenuItem { text: "Trim Trailing Whitespace"; enabled: window.currentPane !== null; onTriggered: window.runOp(TextOps.trimTrailingWhitespace) }
            MenuSeparator {}
            AppMenuItem { text: "Insert Timestamp"; enabled: window.currentPane !== null; onTriggered: {
                    const pane = window.currentPane
                    if (!pane) return
                    pane.insertAtCursor(TextOps.timestamp(""))
                } }
        }

        AppMenu {
            title: "View"
            AppMenuItem { text: "Project Explorer"; shortcutText: "Ctrl+B"; checkable: true; checked: Prefs.showProjectExplorer
                onTriggered: Prefs.showProjectExplorer = !Prefs.showProjectExplorer }
            MenuSeparator {}
            AppMenuItem { text: "Zoom In"; shortcutText: "Ctrl++"; onTriggered: Prefs.adjustFontSize(1) }
            AppMenuItem { text: "Zoom Out"; shortcutText: "Ctrl+-"; onTriggered: Prefs.adjustFontSize(-1) }
            AppMenuItem { text: "Reset Zoom"; shortcutText: "Ctrl+0"; onTriggered: Prefs.fontSize = 13 }
            MenuSeparator {}
            AppMenuItem { text: "Word Wrap"; checkable: true; checked: Prefs.wordWrap
                onTriggered: Prefs.wordWrap = !Prefs.wordWrap }
            AppMenuItem { text: "Line Numbers"; checkable: true; checked: Prefs.showLineNumbers
                onTriggered: Prefs.showLineNumbers = !Prefs.showLineNumbers }
            AppMenuItem { text: "Highlight Current Line"; checkable: true; checked: Prefs.highlightCurrentLine
                onTriggered: Prefs.highlightCurrentLine = !Prefs.highlightCurrentLine }
            AppMenuItem { text: "Syntax Highlighting"; checkable: true; checked: Prefs.syntaxHighlighting
                onTriggered: Prefs.syntaxHighlighting = !Prefs.syntaxHighlighting }
            AppMenuItem { text: "Show Whitespace"; checkable: true; checked: Prefs.showWhitespace
                onTriggered: Prefs.showWhitespace = !Prefs.showWhitespace }
            MenuSeparator {}
            AppMenuItem { text: "Toolbar"; checkable: true; checked: Prefs.showToolBar
                onTriggered: Prefs.showToolBar = !Prefs.showToolBar }
            AppMenuItem { text: "Status Bar"; checkable: true; checked: Prefs.showStatusBar
                onTriggered: Prefs.showStatusBar = !Prefs.showStatusBar }
        }

        AppMenu {
            title: "Tools"
            AppMenuItem {
                text: "Encrypt File\u2026"
                shortcutText: "Ctrl+Shift+E"
                enabled: window.currentDoc && !window.currentDoc.encrypted
                onTriggered: window.startEncrypt()
            }
            AppMenuItem {
                text: "Change Passphrase\u2026"
                enabled: window.currentDoc && window.currentDoc.encrypted
                onTriggered: {
                    passphraseDialog.intent = "change"
                    passphraseDialog.promptNew(window.currentDoc.displayName)
                }
            }
            AppMenuItem {
                text: "Remove Encryption"
                enabled: window.currentDoc && window.currentDoc.encrypted
                onTriggered: {
                    if (window.currentDoc.removeEncryption(window.preparedText())) {
                        Documents.refresh(Documents.currentIndex)
                        status.flash("Encryption removed")
                    }
                }
            }
            MenuSeparator {}
            AppMenuItem { text: "Statistics\u2026"; enabled: window.currentPane !== null; onTriggered: {
                    const pane = window.currentPane
                    if (!pane) return
                    statsDialog.showFor(window.currentDoc.displayName,
                                        TextOps.statistics(pane.editor.text, ""),
                                        TextOps.statistics(pane.editor.text, pane.editor.selectedText))
                } }
            AppMenuItem { text: "Preferences\u2026"; shortcutText: "Ctrl+,"; onTriggered: prefsDialog.open() }
        }

        AppMenu {
            title: "Help"
            AppMenuItem { text: "About"; onTriggered: aboutDialog.open() }
        }
    }

    // ------------------------------------------------------------- toolbar
    header: ToolBar {
        visible: Prefs.showToolBar
        background: Rectangle {
            color: Prefs.chrome
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: Prefs.border
            }
        }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 6
            anchors.rightMargin: 6
            spacing: 4

            BarToggle {
                checked: Prefs.showProjectExplorer
                text: "\ud83d\udcc1"
                tip: "Toggle Project Explorer (Ctrl+B)"
                onClicked: Prefs.showProjectExplorer = !Prefs.showProjectExplorer
            }
            ToolSeparator {}
            BarButton { text: "\uff0b"; tip: "New (Ctrl+N)"; onClicked: window.newFile() }
            BarButton { text: "\u2b06"; tip: "Open File (Ctrl+O)"; onClicked: openDialog.open() }
            BarButton { text: "\ud83d\udcc2"; tip: "Open Folder (Ctrl+Shift+O)"; onClicked: openFolderDialog.open() }
            BarButton { text: "\u2b07"; tip: "Save (Ctrl+S)"; enabled: window.currentDoc !== null; onClicked: window.saveCurrent() }
            ToolSeparator {}
            BarButton { text: "\u21b6"; tip: "Undo"; enabled: window.currentPane !== null; onClicked: if (window.currentPane) window.currentPane.editor.undo() }
            BarButton { text: "\u21b7"; tip: "Redo"; enabled: window.currentPane !== null; onClicked: if (window.currentPane) window.currentPane.editor.redo() }
            ToolSeparator {}
            BarButton { text: "\ud83d\udd0d"; tip: "Find (Ctrl+F)"; onClicked: findBar.open(false) }
            ToolSeparator {}
            BarButton {
                text: "\ud83d\udd12"
                tip: window.currentDoc && window.currentDoc.encrypted
                     ? "File is encrypted" : "Encrypt file (Ctrl+Shift+E)"
                enabled: window.currentDoc !== null && !window.currentDoc.encrypted
                onClicked: window.startEncrypt()
            }

            Item { Layout.fillWidth: true }

            Label {
                text: "Language"
                color: Prefs.chromeText
                opacity: 0.7
                font.pixelSize: Math.max(10, Prefs.fontSize - 2)
            }
            ComboBox {
                id: languageCombo
                implicitHeight: 26
                Layout.preferredWidth: 150
                model: window.currentDoc ? window.currentDoc.availableLanguages : []
                textRole: "name"
                valueRole: "id"
                enabled: window.currentDoc !== null
                onActivated: if (window.currentDoc) window.currentDoc.language = currentValue
                Connections {
                    target: window
                    function onCurrentDocChanged() { languageCombo.syncFromDoc() }
                }
                function syncFromDoc() {
                    if (!window.currentDoc)
                        return
                    currentIndex = indexOfValue(window.currentDoc.language)
                }
                Component.onCompleted: syncFromDoc()
                contentItem: Text {
                    text: languageCombo.displayText
                    color: Prefs.chromeText
                    leftPadding: 8
                    rightPadding: 20
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    font.pixelSize: Math.max(10, Prefs.fontSize - 2)
                }
                background: Rectangle {
                    color: Prefs.background
                    border.color: Prefs.border
                    radius: 3
                }
                delegate: ItemDelegate {
                    width: languageCombo.width
                    highlighted: languageCombo.highlightedIndex === index
                    contentItem: Text {
                        text: modelData.name
                        color: Prefs.chromeText
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: Math.max(10, Prefs.fontSize - 2)
                    }
                    background: Rectangle { color: highlighted ? Prefs.accent : Prefs.chrome }
                }
                popup: Popup {
                    y: languageCombo.height
                    width: languageCombo.width
                    implicitHeight: Math.min(320, contentItem.implicitHeight)
                    padding: 1
                    contentItem: ListView {
                        clip: true
                        implicitHeight: contentHeight
                        model: languageCombo.popup.visible ? languageCombo.delegateModel : null
                        currentIndex: languageCombo.highlightedIndex
                        ScrollIndicator.vertical: ScrollIndicator {}
                    }
                    background: Rectangle {
                        color: Prefs.chrome
                        border.color: Prefs.border
                        radius: 3
                    }
                }
            }
        }
    }

    // -------------------------------------------------------------- panes & explorer
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Project Explorer Sidebar
            ProjectExplorerPanel {
                id: explorerSidebar
                visible: Prefs.showProjectExplorer
                Layout.preferredWidth: Prefs.projectExplorerWidth
                Layout.fillHeight: true
                onOpenFileRequested: function (path) { window.openFiles([path]) }
            }

            // Resizable Splitter
            Rectangle {
                id: explorerSplitter
                visible: Prefs.showProjectExplorer
                Layout.preferredWidth: 4
                Layout.fillHeight: true
                color: splitterArea.containsMouse || splitterArea.drag.active ? Prefs.accent : Prefs.border

                MouseArea {
                    id: splitterArea
                    anchors.fill: parent
                    anchors.leftMargin: -2
                    anchors.rightMargin: -2
                    cursorShape: Qt.SizeHorCursor
                    hoverEnabled: true

                    property int startMouseX: 0
                    property int startWidth: 0

                    onPressed: function (mouse) {
                        startMouseX = mouse.x
                        startWidth = Prefs.projectExplorerWidth
                    }

                    onPositionChanged: function (mouse) {
                        if (pressed) {
                            const delta = mouse.x - startMouseX
                            const newW = Math.max(120, Math.min(window.width * 0.7, Prefs.projectExplorerWidth + delta))
                            Prefs.projectExplorerWidth = Math.round(newW)
                        }
                    }

                    onDoubleClicked: {
                        Prefs.projectExplorerWidth = 220
                    }
                }
            }

            // Editor Area Column
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                // ----------------------------------------------------------- tabs
                // A ListView (rather than TabBar) keeps tabs at a fixed width;
                // TabBar stretches its buttons to fill the available space.
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 30
                    visible: Documents.count > 0
                    color: Prefs.chrome

                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: 1
                        color: Prefs.border
                    }

                    ListView {
                        id: tabBar
                        anchors.fill: parent
                        orientation: ListView.Horizontal
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        interactive: contentWidth > width
                        model: Documents

                        Connections {
                            target: Documents
                            function onCurrentIndexChanged() {
                                if (Documents.currentIndex >= 0)
                                    tabBar.positionViewAtIndex(Documents.currentIndex, ListView.Contain)
                            }
                        }

                        WheelHandler {
                            acceptedDevices: PointerDevice.Mouse
                            onWheel: (event) => {
                                const delta = event.angleDelta.y !== 0 ? event.angleDelta.y : event.angleDelta.x
                                tabBar.contentX = Math.max(0, Math.min(tabBar.contentWidth - tabBar.width,
                                                                       tabBar.contentX - delta))
                            }
                        }

                        delegate: Item {
                            id: tabButton
                            required property int index
                            required property string title
                            required property bool modified
                            required property bool encrypted
                            readonly property bool checked: index === Documents.currentIndex
                            readonly property bool hovered: tabMouse.containsMouse

                            width: 180
                            height: 30

                            Rectangle {
                                anchors.fill: parent
                                color: tabButton.checked ? Prefs.background
                                       : tabButton.hovered ? Prefs.border : "transparent"
                                Rectangle {
                                    anchors.right: parent.right
                                    width: 1
                                    height: parent.height
                                    color: Prefs.border
                                }
                                Rectangle {
                                    anchors.top: parent.top
                                    width: parent.width
                                    height: 2
                                    color: tabButton.checked ? Prefs.accent : "transparent"
                                }
                            }

                            MouseArea {
                                id: tabMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
                                onClicked: (mouse) => {
                                    if (mouse.button === Qt.MiddleButton) {
                                        window.closeTab(tabButton.index)
                                        return
                                    }
                                    Documents.currentIndex = tabButton.index
                                    if (mouse.button === Qt.RightButton) {
                                        tabMenu.tabIndex = tabButton.index
                                        tabMenu.popup()
                                    }
                                }
                            }

                            Item {
                                anchors.fill: parent
                                Row {
                                    anchors.left: parent.left
                                    anchors.leftMargin: 10
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 4
                                    Text {
                                        id: lockIcon
                                        visible: tabButton.encrypted
                                        text: "\ud83d\udd12"
                                        color: Prefs.accent
                                        font.pixelSize: Math.max(10, Prefs.fontSize - 3)
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                    Text {
                                        id: tabLabel
                                        text: (tabButton.modified ? "\u2022 " : "") + tabButton.title
                                        color: Prefs.chromeText
                                        opacity: tabButton.checked ? 1.0 : 0.65
                                        elide: Text.ElideMiddle
                                        width: Math.max(0, tabButton.width - 10 - 4 - 18 - 6
                                                        - (tabButton.encrypted ? lockIcon.implicitWidth + 4 : 0))
                                        font.pixelSize: Math.max(11, Prefs.fontSize - 1)
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                BarButton {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 4
                                    anchors.verticalCenter: parent.verticalCenter
                                    implicitWidth: 18
                                    implicitHeight: 18
                                    text: "\u2715"
                                    onClicked: window.closeTab(tabButton.index)
                                }
                            }
                        }
                    }

                    AppMenu {
                        id: tabMenu
                        property int tabIndex: -1
                        readonly property var doc: tabIndex >= 0 && tabIndex < Documents.count
                                                   ? Documents.documentAt(tabIndex) : null

                        // Closes unmodified tabs in [first, last] except `keep`,
                        // highest index first so lower indices stay valid.
                        function closeRange(first, last, keep) {
                            let kept = 0
                            for (let i = last; i >= first; --i) {
                                if (i === keep)
                                    continue
                                const d = Documents.documentAt(i)
                                if (d && d.modified)
                                    kept++
                                else
                                    Documents.closeDocument(i)
                            }
                            if (kept > 0)
                                window.toast(kept + " tab(s) with unsaved changes kept")
                        }

                        AppMenuItem {
                            text: "Close"
                            onTriggered: window.closeTab(tabMenu.tabIndex)
                        }
                        AppMenuItem {
                            text: "Close Others"
                            enabled: Documents.count > 1
                            onTriggered: tabMenu.closeRange(0, Documents.count - 1, tabMenu.tabIndex)
                        }
                        AppMenuItem {
                            text: "Close Tabs to the Right"
                            enabled: tabMenu.tabIndex < Documents.count - 1
                            onTriggered: tabMenu.closeRange(tabMenu.tabIndex + 1, Documents.count - 1, -1)
                        }
                        AppMenuItem {
                            text: "Close All"
                            onTriggered: tabMenu.closeRange(0, Documents.count - 1, -1)
                        }

                        MenuSeparator {
                            contentItem: Rectangle {
                                implicitHeight: 1
                                color: Prefs.border
                            }
                        }

                        AppMenuItem {
                            text: "Save"
                            onTriggered: {
                                Documents.currentIndex = tabMenu.tabIndex
                                window.saveCurrent()
                            }
                        }
                        AppMenuItem {
                            text: "Encrypt\u2026"
                            enabled: tabMenu.doc !== null && !tabMenu.doc.encrypted
                            onTriggered: {
                                Documents.currentIndex = tabMenu.tabIndex
                                window.startEncrypt()
                            }
                        }
                        AppMenuItem {
                            text: "Copy Path"
                            enabled: tabMenu.doc !== null && !tabMenu.doc.isUntitled
                            onTriggered: Explorer.copyToClipboard(tabMenu.doc.filePath)
                        }
                    }
                }

                // Editor Stack or Empty State
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    // Empty placeholder when no tabs are open
                    ColumnLayout {
                        anchors.centerIn: parent
                        visible: Documents.count === 0
                        spacing: 12

                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: "Cipherpad"
                            color: Prefs.chromeText
                            opacity: 0.25
                            font.pixelSize: Prefs.fontSize + 10
                            font.bold: true
                        }

                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: "Ctrl+N: New File   \u2022   Ctrl+O: Open File   \u2022   Ctrl+Shift+O: Open Folder   \u2022   Ctrl+B: Explorer"
                            color: Prefs.chromeText
                            opacity: 0.4
                            font.pixelSize: Math.max(11, Prefs.fontSize - 1)
                        }
                    }

                    StackLayout {
                        id: stack
                        anchors.fill: parent
                        visible: Documents.count > 0
                        currentIndex: Documents.currentIndex

                        Repeater {
                            id: paneRepeater
                            model: Documents
                            EditorPane {
                                required property var document
                                required property int index
                                doc: document
                                docIndex: index
                                onStatusChanged: status.refresh()
                            }
                        }
                    }
                }

                FindReplaceBar {
                    id: findBar
                    Layout.fillWidth: true
                    pane: window.currentPane
                    onToast: function (message) { status.flash(message) }
                    onClosed: if (window.currentPane) window.currentPane.focusEditor()
                }
            }
        }

        // --------------------------------------------------------- status
        Rectangle {
            id: status
            Layout.fillWidth: true
            visible: Prefs.showStatusBar
            implicitHeight: 24
            color: Prefs.chrome

            property string message: ""
            function flash(text) { message = text; flashTimer.restart() }
            function refresh() { positionLabel.update() }

            Timer {
                id: flashTimer
                interval: 3000
                onTriggered: status.message = ""
            }

            Rectangle {
                anchors.top: parent.top
                width: parent.width
                height: 1
                color: Prefs.border
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 14

                Label {
                    text: status.message
                    color: Prefs.accent
                    font.pixelSize: Math.max(10, Prefs.fontSize - 2)
                    elide: Text.ElideRight
                    Layout.maximumWidth: 320
                }

                Item { Layout.fillWidth: true }

                Label {
                    id: positionLabel
                    function update() {}
                    text: {
                        const pane = window.currentPane
                        if (!pane)
                            return ""
                        const sel = pane.selectionLength
                        return "Ln " + pane.currentLine + ", Col " + pane.currentColumn
                                + (sel > 0 ? "  (" + sel + " selected)" : "")
                    }
                    color: Prefs.chromeText
                    opacity: 0.8
                    font.pixelSize: Math.max(10, Prefs.fontSize - 2)
                }

                StatusChip {
                    text: window.currentDoc ? window.currentDoc.encoding.toUpperCase() : ""
                    tip: "Character encoding"
                }
                StatusChip {
                    text: window.currentDoc ? window.currentDoc.lineEnding.toUpperCase() : ""
                    tip: "Line endings"
                }
                StatusChip {
                    text: Prefs.insertSpaces ? "Spaces: " + Prefs.tabWidth : "Tabs: " + Prefs.tabWidth
                    tip: "Indentation"
                }
                StatusChip {
                    text: window.currentDoc && window.currentDoc.encrypted ? "\ud83d\udd12 Encrypted" : ""
                    visible: text !== ""
                    accented: true
                    tip: "AES-256-GCM"
                }
            }
        }
    }

    // ---------------------------------------------------------- shortcuts
    Shortcut { sequences: [StandardKey.New]; onActivated: window.newFile() }
    Shortcut { sequences: [StandardKey.Open]; onActivated: openDialog.open() }
    Shortcut { sequences: [StandardKey.Save]; enabled: window.currentDoc !== null; onActivated: window.saveCurrent() }
    Shortcut { sequences: [StandardKey.SaveAs]; enabled: window.currentDoc !== null; onActivated: { saveDialog.encrypting = false; saveDialog.open() } }
    Shortcut { sequences: [StandardKey.Close]; enabled: Documents.count > 0; onActivated: window.closeTab(Documents.currentIndex) }
    Shortcut { sequences: [StandardKey.Quit]; onActivated: window.close() }
    Shortcut { sequences: [StandardKey.Find]; onActivated: findBar.open(false) }
    Shortcut { sequences: [StandardKey.Replace]; onActivated: findBar.open(true) }
    Shortcut { sequences: [StandardKey.FindNext]; onActivated: findBar.findNext() }
    Shortcut { sequences: [StandardKey.FindPrevious]; onActivated: findBar.findPrevious() }
    Shortcut { sequences: [StandardKey.ZoomIn]; onActivated: Prefs.adjustFontSize(1) }
    Shortcut { sequences: [StandardKey.ZoomOut]; onActivated: Prefs.adjustFontSize(-1) }
    Shortcut { sequence: "Ctrl+0"; onActivated: Prefs.fontSize = 13 }
    Shortcut { sequence: "Ctrl+G"; enabled: window.currentPane !== null; onActivated: gotoDialog.promptFor(
                   window.currentPane ? window.currentPane.metrics.lineCount() : 1,
                   window.currentPane ? window.currentPane.currentLine : 1) }
    Shortcut { sequence: "Ctrl+D"; enabled: window.currentPane !== null; onActivated: window.runOp(TextOps.duplicateLines) }
    Shortcut { sequence: "Ctrl+Shift+K"; enabled: window.currentPane !== null; onActivated: window.runOp(TextOps.deleteLines) }
    Shortcut { sequence: "Alt+Up"; enabled: window.currentPane !== null; onActivated: window.runOp(TextOps.moveLinesUp) }
    Shortcut { sequence: "Alt+Down"; enabled: window.currentPane !== null; onActivated: window.runOp(TextOps.moveLinesDown) }
    Shortcut { sequence: "Ctrl+J"; enabled: window.currentPane !== null; onActivated: window.runOp(TextOps.joinLines) }
    Shortcut { sequence: "Ctrl+,"; onActivated: prefsDialog.open() }
    Shortcut { sequence: "Ctrl+B"; onActivated: Prefs.showProjectExplorer = !Prefs.showProjectExplorer }
    Shortcut { sequence: "Ctrl+Shift+O"; onActivated: openFolderDialog.open() }
    Shortcut {
        sequence: "Ctrl+/"
        enabled: window.currentPane !== null
        onActivated: {
            const pane = window.currentPane
            if (!pane) return
            pane.applySpan(TextOps.toggleComment(pane.editor.text, pane.editor.selectionStart,
                                                 pane.editor.selectionEnd, window.currentDoc.language))
        }
    }
    Shortcut {
        sequence: "Ctrl+Shift+E"
        enabled: window.currentDoc !== null && !window.currentDoc.encrypted
        onActivated: window.startEncrypt()
    }
    Shortcut {
        sequence: "Ctrl+Tab"
        enabled: Documents.count > 0
        onActivated: if (Documents.count > 0) Documents.currentIndex = (Documents.currentIndex + 1) % Documents.count
    }
    Shortcut {
        sequence: "Ctrl+Shift+Tab"
        enabled: Documents.count > 0
        onActivated: if (Documents.count > 0) Documents.currentIndex =
                     (Documents.currentIndex - 1 + Documents.count) % Documents.count
    }

    // --------------------------------------------------------- drag & drop
    DropArea {
        anchors.fill: parent
        onDropped: function (drop) {
            if (drop.hasUrls) {
                for (let i = 0; i < drop.urls.length; ++i) {
                    const urlStr = String(drop.urls[i])
                    if (Explorer.addFolder(urlStr)) {
                        Prefs.showProjectExplorer = true
                    } else {
                        window.openFiles([urlStr])
                    }
                }
            }
        }
    }
}
