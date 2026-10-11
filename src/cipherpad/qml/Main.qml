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
    readonly property var currentPane: currentDoc && currentDoc.locked ? null : (Documents.count >= 0 ? paneRepeater.itemAt(Documents.currentIndex) : null)
    readonly property alias prettyPrintCommand: prettyPrintAction
    property int pendingCloseIndex: -1
    property string pendingAction: ""
    property var pendingPaths: []
    property bool splitEditors: false
    property var leftDocument: null
    property var rightDocument: null
    property int activeSide: 0
    property real splitRatio: 0.5
    property bool showMarkdownPreview: false
    readonly property bool unlockedDocument: currentDoc !== null && !currentDoc.locked
    readonly property alias tabLockCommand: lockTabAction
    property bool showConsole: false

    CommandConsole {
        id: commandConsole
        objectName: "commandConsole"
        onErrorOccurred: function(message) { messageDialog.show(message) }
    }
    GitTools {
        id: gitTools
        objectName: "gitTools"
        onErrorOccurred: function(message) { messageDialog.show(message) }
        onOperationCompleted: function(message) { status.flash(message) }
        onDiffReady: function(diff, path) {
            comparisonDialog.heading = "Git Diff: " + path
            comparisonDialog.showComparison({diff: diff, left: "", right: "", leftName: "Git", rightName: path, equal: diff === "", unifiedOnly: true}, null, false)
        }
    }
    function workingDirectory() {
        if (currentDoc && currentDoc.filePath)
            return Explorer.parentDirectory(currentDoc.filePath)
        return Explorer.rootFolders.length ? Explorer.rootFolders[0] : commandConsole.homeDirectory
    }
    function toggleConsole() {
        showConsole = !showConsole
        if (showConsole)
            consolePanel.showFor(workingDirectory())
        else if (currentPane)
            currentPane.focusEditor()
    }
    function navigateBookmark(previous) {
        if (!currentPane)
            return
        const line = currentPane.metrics.adjacentBookmark(currentPane.currentLine, previous)
        if (line)
            currentPane.goToLine(line)
        else
            status.flash("No bookmarks in this tab")
    }
    function compareExplorerFiles(paths) {
        if (paths.length !== 2) {
            messageDialog.show("Select exactly two files in the explorer using Ctrl-click.")
            return
        }
        const left = Inspection.readFile(paths[0])
        const right = Inspection.readFile(paths[1])
        if (left.error || right.error) {
            messageDialog.show(left.error || right.error)
            return
        }
        showComparison(left.text, right.text, paths[0], paths[1], false)
    }
    GitPanel {
        id: gitPanel
        git: gitTools
        onFileRequested: function(path) { window.openFiles([path]) }
    }

    SafetyTools {
        id: safety
        objectName: "safetyTools"
        onErrorOccurred: function(message) { messageDialog.show(message) }
    }
    Connections {
        target: Prefs
        function onRecoveryEnabledChanged() { window.captureRecovery() }
    }
    Timer {
        interval: 30000
        repeat: true
        running: true
        onTriggered: window.captureRecovery()
    }
    function captureRecovery() {
        for (let i = 0; i < Documents.count; ++i) {
            const pane = paneAt(i)
            if (pane)
                safety.snapshot(pane.doc, pane.editor.text, Prefs.recoveryEnabled)
        }
    }
    function showRecovery() {
        recoveryDialog.entries = safety.availableRecovery()
        if (recoveryDialog.entries.length)
            recoveryDialog.open()
        else
            status.flash("No interrupted-session recovery snapshots")
    }
    function resolveRecoveryEntry(identifier, restore) {
        safety.resolveRecovery(identifier, Documents, restore)
        recoveryDialog.entries = safety.availableRecovery()
        if (!recoveryDialog.entries.length)
            recoveryDialog.close()
    }
    function toggleTabLock() {
        if (!currentDoc || !currentDoc.encrypted)
            return
        if (currentDoc.locked) {
            unlockTabDialog.document = currentDoc
            unlockTabDialog.promptUnlock(currentDoc.displayName, "")
            return
        }
        comparisonDialog.close()
        validationDialog.close()
        jsonTreeDialog.close()
        reloadConfirm.close()
        compareTabDialog.close()
        compareFileDialog.close()
        saveDialog.close()
        passphraseDialog.close()
        findBar.clearSensitive()
        showMarkdownPreview = false
        messageDialog.close()
        messageDialog.message = ""
        currentDoc.lock(currentPane.editor.text)
    }
    Action {
        id: lockTabAction
        objectName: "lockTabAction"
        text: window.currentDoc && window.currentDoc.locked ? "Unlock Tab..." : "Lock Encrypted Tab"
        shortcut: "Ctrl+Alt+L"
        enabled: window.currentDoc !== null && window.currentDoc.encrypted
        onTriggered: window.toggleTabLock()
    }

    function containsDocument(document) {
        for (let i = 0; i < Documents.count; ++i)
            if (Documents.documentAt(i) === document)
                return true
        return false
    }

    function toggleSplit() {
        if (splitEditors) {
            splitEditors = false
            leftDocument = null
            rightDocument = null
            return
        }
        if (!currentDoc)
            newFile()
        const original = currentDoc
        let other = null
        for (let i = 0; i < Documents.count; ++i)
            if (Documents.documentAt(i) !== original) {
                other = Documents.documentAt(i)
                break
            }
        if (!other) {
            const index = Documents.newDocument()
            other = Documents.documentAt(index)
            Documents.currentIndex = paneIndex(original)
        }
        leftDocument = original
        rightDocument = other
        activeSide = 0
        splitEditors = true
        if (currentPane)
            currentPane.focusEditor()
    }

    function paneIndex(document) {
        for (let i = 0; i < Documents.count; ++i)
            if (Documents.documentAt(i) === document)
                return i
        return -1
    }
    readonly property bool editableDocument: currentPane !== null && unlockedDocument && !currentDoc.readOnly

    Action {
        id: quickOpenAction
        objectName: "quickOpenAction"
        text: "Quick Open..."
        shortcut: "Ctrl+P"
        onTriggered: workspacePicker.showFiles()
    }
    Action {
        id: workspaceSearchAction
        objectName: "workspaceSearchAction"
        text: "Search Workspace..."
        shortcut: "Ctrl+Shift+F"
        onTriggered: workspaceSearchDialog.showSearch()
    }
    Action {
        id: commandPaletteAction
        objectName: "commandPaletteAction"
        text: "Command Palette..."
        shortcut: "F1"
        onTriggered: workspacePicker.showCommands()
    }

    Action {
        id: prettyPrintAction
        objectName: "prettyPrintAction"
        text: "Pretty Print"
        shortcut: "Ctrl+Shift+P"
        enabled: window.currentPane !== null && window.currentDoc !== null
                 && !window.currentDoc.readOnly
                 && !window.currentDoc.locked
                 && (window.currentDoc.language === "json" || window.currentDoc.language === "xml")
        onTriggered: window.prettyPrint()
    }

    onWidthChanged: if (visibility === Window.Windowed) Prefs.windowWidth = width
    onHeightChanged: if (visibility === Window.Windowed) Prefs.windowHeight = height
    // Only record user-visible states; Hidden (on close) and Minimized must not
    // overwrite the saved maximized flag.
    onVisibilityChanged: function (visibility) {
        if (visibility === Window.Maximized || visibility === Window.Windowed)
            Prefs.windowMaximized = (visibility === Window.Maximized)
    }

    Component.onCompleted: {
        Explorer.configure(Prefs.showHiddenFiles, Prefs.workspaceIgnorePatterns)
        if (Prefs.windowMaximized)
            showMaximized()
        else
            show()
        Qt.callLater(function() {
            recoveryDialog.entries = safety.availableRecovery()
            if (recoveryDialog.entries.length)
                recoveryDialog.open()
        })
    }

    onClosing: function (close) {
        if (Documents.hasModifiedDocuments) {
            close.accepted = false
            if (!unsavedDialog.visible) {
                pendingAction = "quit"
                unsavedDialog.openFor(-1)
            }
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
        if (!unlockedDocument) {
            if (currentDoc && currentDoc.locked)
                messageDialog.show("Unlock this tab before saving.")
            return false
        }
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
        if (!pane || !unlockedDocument)
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
        if (doc && doc.pinned) {
            status.flash("Unpin this tab before closing it")
            return
        }
        if (doc && doc.modified) {
            pendingAction = "close"
            unsavedDialog.openFor(index)
            return
        }
        Documents.closeDocument(index)
    }

    function runOp(fn) {
        const pane = currentPane
        if (!pane || !editableDocument)
            return
        pane.applySpan(fn(pane.editor.text, pane.editor.selectionStart, pane.editor.selectionEnd))
        pane.focusEditor()
    }

    function toast(message) { status.flash(message) }

    function prettyPrint() {
        const pane = currentPane
        if (!pane || !currentDoc)
            return
        const span = TextOps.prettyPrint(pane.editor.text, currentDoc.language,
                                         Prefs.tabWidth, Prefs.insertSpaces)
        if (span.error) {
            messageDialog.show(span.error)
            return
        }
        pane.applySpan(span)
        pane.focusEditor()
    }

    function comparePaneWithDisk(pane, external) {
        if (!pane || !pane.doc || pane.doc.locked)
            return
        const snapshot = pane.doc.diskSnapshot()
        if (snapshot.error) {
            messageDialog.show(snapshot.error)
            return
        }
        const result = Inspection.compare(snapshot.text, pane.editor.text,
                                          pane.doc.displayName + " (disk)", pane.doc.displayName + " (editor)")
        if (result.error) {
            messageDialog.show(result.error)
            return
        }
        if (external && result.equal)
            return
        comparisonDialog.heading = external ? "External Change Detected" : "Compare with Disk"
        comparisonDialog.showComparison(result, pane.doc, true)
    }

    function showComparison(left, right, leftName, rightName, otherEncrypted) {
        const result = Inspection.compare(left, right, leftName, rightName)
        result.sensitive = (currentDoc && currentDoc.encrypted) || otherEncrypted === true
        if (result.error)
            messageDialog.show(result.error)
        else {
            comparisonDialog.heading = "Compare Files"
            comparisonDialog.showComparison(result, null, false)
        }
    }

    function requestReload(document) {
        if (!document || document.locked || !containsDocument(document))
            return
        if (document.modified) {
            reloadConfirm.document = document
            reloadConfirm.open()
        } else
            document.reload()
    }

    function showJsonTree() {
        if (!currentPane || !unlockedDocument)
            return
        const result = Inspection.jsonTree(currentPane.editor.text)
        if (result.error)
            messageDialog.show(result.error)
        else
            jsonTreeDialog.showTree(result, currentDoc.encrypted)
    }

    function runCommand(command) {
        if (currentDoc && currentDoc.locked && ["save", "pretty", "undo", "redo", "upper", "lower", "trim", "unique", "reverse", "diskDiff", "fileDiff", "tabDiff", "validate", "jsonTree", "markdown"].includes(command)) {
            messageDialog.show("Unlock this tab before using this command.")
            return
        }
        switch (command) {
        case "console": toggleConsole(); break
        case "git": gitPanel.showFor(workingDirectory()); break
        case "pin": if (currentDoc) currentDoc.pinned = !currentDoc.pinned; break
        case "bookmark": if (currentPane) currentPane.metrics.toggleBookmark(currentPane.currentLine); break
        case "nextBookmark": navigateBookmark(false); break
        case "previousBookmark": navigateBookmark(true); break
        case "clearBookmarks": if (currentPane) currentPane.metrics.clearBookmarks(); break
        case "lock": toggleTabLock(); break
        case "recovery": showRecovery(); break
        case "new": newFile(); break
        case "open": openDialog.open(); break
        case "folder": openFolderDialog.open(); break
        case "save": saveCurrent(); break
        case "close": closeTab(Documents.currentIndex); break
        case "quick": workspacePicker.showFiles(); break
        case "workspaceSearch": workspaceSearchDialog.showSearch(); break
        case "find": findBar.open(false); break
        case "replace": findBar.open(true); break
        case "goto": gotoDialog.promptFor(currentPane.metrics.lineCount(), currentPane.currentLine); break
        case "preferences": prefsDialog.open(); break
        case "pretty": prettyPrint(); break
        case "undo": currentPane.editor.undo(); break
        case "redo": currentPane.editor.redo(); break
        case "selectAll": currentPane.editor.selectAll(); break
        case "upper": runOp(TextOps.upperCase); break
        case "lower": runOp(TextOps.lowerCase); break
        case "trim": runOp(TextOps.trimTrailingWhitespace); break
        case "unique": runOp(TextOps.uniqueLines); break
        case "reverse": runOp(TextOps.reverseLines); break
        case "encrypt": startEncrypt(); break
        case "wrap": Prefs.wordWrap = !Prefs.wordWrap; break
        case "explorer": Prefs.showProjectExplorer = !Prefs.showProjectExplorer; break
        case "hidden": Prefs.showHiddenFiles = !Prefs.showHiddenFiles; break
        case "zoomIn": Prefs.adjustFontSize(1); break
        case "zoomOut": Prefs.adjustFontSize(-1); break
        case "about": aboutDialog.open(); break
        case "split": toggleSplit(); break
        case "diskDiff": comparePaneWithDisk(currentPane, false); break
        case "fileDiff": compareFileDialog.open(); break
        case "tabDiff": compareTabDialog.open(); break
        case "validate": validationDialog.showFor(currentPane); break
        case "jsonTree": showJsonTree(); break
        case "markdown": showMarkdownPreview = !showMarkdownPreview; break
        default: messageDialog.show("Unknown command: " + command)
        }
    }

    WorkspacePicker {
        id: workspacePicker
        commands: [
            {command: "console", label: "View: Command Console (Ctrl+`)"},
            {command: "git", label: "Tools: Local Git (Ctrl+Alt+G)"},
            {command: "pin", label: "Tabs: Pin / Unpin Tab", enabled: window.currentDoc !== null},
            {command: "bookmark", label: "Bookmarks: Toggle (Ctrl+F2)", enabled: window.currentPane !== null},
            {command: "nextBookmark", label: "Bookmarks: Next (F2)", enabled: window.currentPane !== null},
            {command: "previousBookmark", label: "Bookmarks: Previous (Shift+F2)", enabled: window.currentPane !== null},
            {command: "clearBookmarks", label: "Bookmarks: Clear Tab Bookmarks", enabled: window.currentPane !== null},
            {command: "lock", label: "Security: Lock / Unlock Tab (Ctrl+Alt+L)", enabled: lockTabAction.enabled},
            {command: "recovery", label: "File: Recover Interrupted Session"},
            {command: "new", label: "File: New (Ctrl+N)"},
            {command: "open", label: "File: Open (Ctrl+O)"},
            {command: "folder", label: "Workspace: Add Folder (Ctrl+Shift+O)"},
            {command: "save", label: "File: Save (Ctrl+S)", enabled: window.currentDoc !== null},
            {command: "close", label: "File: Close Tab", enabled: window.currentDoc !== null},
            {command: "quick", label: "Workspace: Quick Open (Ctrl+P)"},
            {command: "workspaceSearch", label: "Workspace: Search (Ctrl+Shift+F)"},
            {command: "find", label: "Edit: Find (Ctrl+F)", enabled: window.currentPane !== null},
            {command: "replace", label: "Edit: Replace (Ctrl+H)", enabled: window.editableDocument},
            {command: "goto", label: "Edit: Go to Line", enabled: window.currentPane !== null},
            {command: "preferences", label: "Preferences (Ctrl+,)"},
            {command: "pretty", label: "Format: Pretty Print (Ctrl+Shift+P)", enabled: prettyPrintAction.enabled},
            {command: "undo", label: "Edit: Undo", enabled: window.editableDocument},
            {command: "redo", label: "Edit: Redo", enabled: window.editableDocument},
            {command: "selectAll", label: "Edit: Select All", enabled: window.currentPane !== null},
            {command: "upper", label: "Format: Uppercase", enabled: window.editableDocument},
            {command: "lower", label: "Format: Lowercase", enabled: window.editableDocument},
            {command: "trim", label: "Format: Trim Trailing Whitespace", enabled: window.editableDocument},
            {command: "unique", label: "Format: Remove Duplicate Lines", enabled: window.editableDocument},
            {command: "reverse", label: "Format: Reverse Lines", enabled: window.editableDocument},
            {command: "encrypt", label: "Tools: Encrypt File", enabled: window.currentDoc !== null && !window.currentDoc.encrypted},
            {command: "wrap", label: "View: Toggle Word Wrap"},
            {command: "explorer", label: "View: Toggle Explorer (Ctrl+B)"},
            {command: "hidden", label: "Workspace: Toggle Hidden Files"},
            {command: "zoomIn", label: "View: Zoom In"},
            {command: "zoomOut", label: "View: Zoom Out"},
            {command: "about", label: "Help: About"},
            {command: "split", label: "View: Toggle Split Editors (Ctrl+Alt+S)"},
            {command: "diskDiff", label: "Compare: Editor with Disk", enabled: window.currentDoc !== null && !window.currentDoc.isUntitled},
            {command: "fileDiff", label: "Compare: With File", enabled: window.currentPane !== null},
            {command: "tabDiff", label: "Compare: With Open Tab", enabled: Documents.count > 1},
            {command: "validate", label: "Tools: Validate JSON / XML", enabled: window.currentDoc !== null && ["json", "xml"].includes(window.currentDoc.language)},
            {command: "jsonTree", label: "View: JSON Tree", enabled: window.currentDoc !== null && window.currentDoc.language === "json"},
            {command: "markdown", label: "View: Markdown Preview", enabled: window.currentDoc !== null && window.currentDoc.language === "markdown"}
        ]
        onFileRequested: function(path) { window.openFiles([path]) }
        onCommandRequested: function(command) { window.runCommand(command) }
    }

    WorkspaceSearchDialog {
        id: workspaceSearchDialog
        onMatchRequested: function(match) {
            const index = Documents.indexOfPath(match.path)
            if (index >= 0 && Documents.documentAt(index).modified) {
                messageDialog.show("This result refers to the saved file. Save or reload the modified tab and search again.")
                return
            }
            window.openFiles([match.path])
            if (!window.currentDoc || window.currentDoc.filePath !== match.path || !window.currentPane)
                return
            const pane = window.currentPane
            const start = pane.metrics.positionForLine(match.line) + match.column - 1
            if (!Workspace.isCurrent(pane.editor.text, match.digest)) {
                messageDialog.show("The file has changed since the search. Search again to refresh results.")
                return
            }
            pane.selectRange(start, start + match.length)
            pane.focusEditor()
        }
    }

    // ------------------------------------------------------------- dialogs
    ComparisonDialog {
        safetyTools: safety
        id: comparisonDialog
        onReloadRequested: function(document) { window.requestReload(document) }
    }
    ValidationDialog { id: validationDialog }
    JsonTreeDialog { id: jsonTreeDialog; safetyTools: safety }
    AppDialog {
        id: reloadConfirm
        objectName: "reloadConfirmDialog"
        heading: "Discard edits and reload?"
        property var document: null
        standardButtons: Dialog.Discard | Dialog.Cancel
        Label {
            width: parent.width
            text: "Reloading will discard unsaved edits in " + (reloadConfirm.document ? reloadConfirm.document.displayName : "") + "."
            color: Prefs.chromeText
            wrapMode: Text.Wrap
        }
        onDiscarded: {
            if (window.containsDocument(document))
                document.reload()
            close()
        }
        onClosed: document = null
    }
    FileDialog {
        id: compareFileDialog
        title: "Compare current editor with a file"
        fileMode: FileDialog.OpenFile
        onAccepted: {
            if (!window.currentPane)
                return
            const snapshot = Inspection.readFile(String(selectedFile))
            if (snapshot.error)
                messageDialog.show(snapshot.error)
            else
                window.showComparison(window.currentPane.editor.text, snapshot.text,
                                      window.currentDoc.displayName + " (editor)", String(selectedFile))
        }
    }
    AppDialog {
        id: compareTabDialog
        objectName: "compareTabDialog"
        heading: "Compare with Open Tab"
        standardButtons: Dialog.Close
        width: 440
        height: Math.min(480, parent.height - 40)
        ListView {
            anchors.fill: parent
            model: Documents
            clip: true
            delegate: ItemDelegate {
                required property var document
                required property int index
                width: ListView.view.width
                enabled: document !== window.currentDoc && !document.locked && window.unlockedDocument
                contentItem: Label { text: document.displayName; color: Prefs.chromeText }
                onClicked: {
                    const other = window.paneAt(index)
                    window.showComparison(window.currentPane.editor.text, other.editor.text,
                                          window.currentDoc.displayName + " (editor)", document.displayName + " (editor)", document.encrypted)
                    compareTabDialog.close()
                }
            }
        }
    }
    FileDialog {
        id: openDialog
        title: "Open files"
        fileMode: FileDialog.OpenFiles
        nameFilters: ["All files (*)", "Text files (*.txt *.md *.log)",
                      "Encrypted files (*.enc *.aes)", "Source files (*.py *.js *.qml *.groovy *.gradle *.json *.xml *.html *.css)"]
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
            if (!window.unlockedDocument) {
                messageDialog.show("Unlock the tab before saving.")
                return
            }
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
        id: unlockTabDialog
        objectName: "unlockTabDialog"
        property var document: null
        onPassphraseAccepted: function(passphrase) {
            if (document && window.containsDocument(document)) {
                if (!document.unlock(passphrase))
                    promptUnlock(document.displayName, "Wrong passphrase, or the locked buffer is damaged.")
                else {
                    document = null
                    if (window.currentPane)
                        window.currentPane.focusEditor()
                }
            }
        }
        onRejected: document = null
    }

    AppDialog {
        id: recoveryDialog
        objectName: "recoveryDialog"
        heading: "Interrupted Session Recovery"
        width: 540
        standardButtons: Dialog.Close
        property var entries: []
        ColumnLayout {
            width: parent.width
            Label {
                Layout.fillWidth: true
                text: "Ordinary-tab snapshots contain plaintext. Restore creates an unsaved recovered tab; the original file is never overwritten. Encrypted tabs are excluded."
                wrapMode: Text.Wrap
                color: Prefs.chromeText
            }
            Repeater {
                model: recoveryDialog.entries
                RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    Label {
                        Layout.fillWidth: true
                        text: modelData.title + (modelData.error ? ": " + modelData.error : "")
                        wrapMode: Text.Wrap
                        color: Prefs.chromeText
                    }
                    BarButton {
                        objectName: "recoveryRestoreButton"
                        text: "Restore"
                        wide: true
                        enabled: !modelData.error
                        onClicked: window.resolveRecoveryEntry(modelData.id, true)
                    }
                    BarButton {
                        text: "Discard"
                        wide: true
                        onClicked: {
                            recoveryDiscard.identifier = modelData.id
                            recoveryDiscard.open()
                        }
                    }
                }
            }
        }
    }
    AppDialog {
        id: recoveryDiscard
        heading: "Discard recovery snapshot?"
        standardButtons: Dialog.Yes | Dialog.No
        property string identifier: ""
        Label { text: "This permanently removes the selected recovery snapshot."; color: Prefs.chromeText }
        onAccepted: {
            window.resolveRecoveryEntry(identifier, false)
        }
    }

    PassphraseDialog {
        id: passphraseDialog
        property string pendingPath: ""
        // "open" | "saveAs" | "encrypt" | "change"
        property string intent: "open"

        onPassphraseAccepted: function (passphrase) {
            if (intent !== "open" && !window.unlockedDocument)
                return
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
        function onCurrentIndexChanged() {
            if (!window.splitEditors)
                return
            const selected = Documents.currentDocument
            if (selected === window.leftDocument)
                window.activeSide = 0
            else if (selected === window.rightDocument)
                window.activeSide = 1
            else if (window.activeSide === 0)
                window.leftDocument = selected
            else
                window.rightDocument = selected
        }
        function onCountChanged() {
            if (unlockTabDialog.document && !window.containsDocument(unlockTabDialog.document))
                unlockTabDialog.reject()
            if (window.splitEditors && (!window.containsDocument(window.leftDocument) || !window.containsDocument(window.rightDocument)))
                window.toggleSplit()
            if (comparisonDialog.sourceDocument && !window.containsDocument(comparisonDialog.sourceDocument))
                comparisonDialog.close()
            if (validationDialog.pane && !window.containsDocument(validationDialog.pane.doc))
                validationDialog.close()
        }
    }

    Connections {
        target: Explorer
        function onErrorOccurred(message) { messageDialog.show(message) }
    }
    Connections {
        target: Workspace
        function onErrorOccurred(message) { messageDialog.show(message) }
    }
    Connections {
        target: Prefs
        function onShowHiddenFilesChanged() { Explorer.configure(Prefs.showHiddenFiles, Prefs.workspaceIgnorePatterns) }
        function onWorkspaceIgnorePatternsChanged() { Explorer.configure(Prefs.showHiddenFiles, Prefs.workspaceIgnorePatterns) }
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
            AppMenuItem { action: quickOpenAction; shortcutText: "Ctrl+P" }
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
                onTriggered: window.requestReload(window.currentDoc)
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
            AppMenuItem { text: "Cut"; shortcutText: "Ctrl+X"; enabled: window.editableDocument; onTriggered: if (window.currentPane) window.currentPane.copySelection(true) }
            AppMenuItem { text: "Copy"; shortcutText: "Ctrl+C"; enabled: window.unlockedDocument; onTriggered: if (window.currentPane) window.currentPane.copySelection(false) }
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
            AppMenuItem {
                action: prettyPrintAction
                shortcutText: "Ctrl+Shift+P"
            }
            MenuSeparator {}
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
            AppMenuItem { text: "Command Console"; shortcutText: "Ctrl+`"; checkable: true; checked: window.showConsole; onTriggered: window.toggleConsole() }
            AppMenuItem { text: "Local Git..."; shortcutText: "Ctrl+Alt+G"; onTriggered: gitPanel.showFor(window.workingDirectory()) }
            AppMenuItem { text: "Pin / Unpin Tab"; enabled: window.currentDoc !== null; onTriggered: window.runCommand("pin") }
            AppMenu {
                title: "Bookmarks"
                AppMenuItem { text: "Toggle Bookmark"; shortcutText: "Ctrl+F2"; enabled: window.currentPane !== null; onTriggered: window.runCommand("bookmark") }
                AppMenuItem { text: "Next Bookmark"; shortcutText: "F2"; enabled: window.currentPane !== null; onTriggered: window.navigateBookmark(false) }
                AppMenuItem { text: "Previous Bookmark"; shortcutText: "Shift+F2"; enabled: window.currentPane !== null; onTriggered: window.navigateBookmark(true) }
                AppMenuItem { text: "Clear Tab Bookmarks"; enabled: window.currentPane !== null; onTriggered: window.runCommand("clearBookmarks") }
            }
            AppMenuItem { text: "Split Editors"; shortcutText: "Ctrl+Alt+S"; checkable: true; checked: window.splitEditors; onTriggered: window.toggleSplit() }
            AppMenuItem { text: "JSON Tree"; enabled: window.currentDoc !== null && window.currentDoc.language === "json"; onTriggered: window.showJsonTree() }
            AppMenuItem { text: "Markdown Preview"; checkable: true; checked: window.showMarkdownPreview; enabled: window.currentDoc !== null && window.currentDoc.language === "markdown"; onTriggered: window.showMarkdownPreview = !window.showMarkdownPreview }
            AppMenuItem { action: commandPaletteAction; shortcutText: "F1" }
            AppMenuItem { action: workspaceSearchAction; shortcutText: "Ctrl+Shift+F" }
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
            AppMenuItem { action: lockTabAction; shortcutText: "Ctrl+Alt+L" }
            AppMenuItem { text: "Recover Interrupted Session..."; onTriggered: window.showRecovery() }
            AppMenuItem { text: "Validate JSON / XML"; enabled: window.unlockedDocument && ["json", "xml"].includes(window.currentDoc.language); onTriggered: validationDialog.showFor(window.currentPane) }
            AppMenuItem { text: "Compare with Disk"; enabled: window.currentDoc !== null && !window.currentDoc.isUntitled; onTriggered: window.comparePaneWithDisk(window.currentPane, false) }
            AppMenuItem { text: "Compare with File..."; enabled: window.currentPane !== null; onTriggered: compareFileDialog.open() }
            AppMenuItem { text: "Compare with Open Tab..."; enabled: window.unlockedDocument && Documents.count > 1; onTriggered: compareTabDialog.open() }
            MenuSeparator {}
            AppMenuItem {
                text: "Encrypt File\u2026"
                shortcutText: "Ctrl+Shift+E"
                enabled: window.currentDoc && !window.currentDoc.encrypted
                onTriggered: window.startEncrypt()
            }
            AppMenuItem {
                text: "Change Passphrase\u2026"
                enabled: window.unlockedDocument && window.currentDoc.encrypted
                onTriggered: {
                    passphraseDialog.intent = "change"
                    passphraseDialog.promptNew(window.currentDoc.displayName)
                }
            }
            AppMenuItem {
                text: "Remove Encryption"
                enabled: window.unlockedDocument && window.currentDoc.encrypted
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
            BarButton { text: "\ud83d\udcc4"; tip: "New (Ctrl+N)"; onClicked: window.newFile() }
            BarButton { text: "\ud83d\udcd6"; tip: "Open File (Ctrl+O)"; onClicked: openDialog.open() }
            BarButton { text: "\ud83d\udcc2"; tip: "Open Folder (Ctrl+Shift+O)"; onClicked: openFolderDialog.open() }
            BarButton { text: "\ud83d\udcbe"; tip: "Save (Ctrl+S)"; enabled: window.currentDoc !== null; onClicked: window.saveCurrent() }
            ToolSeparator {}
            BarButton { text: "\u21b6"; tip: "Undo"; enabled: window.currentPane !== null; onClicked: if (window.currentPane) window.currentPane.editor.undo() }
            BarButton { text: "\u21b7"; tip: "Redo"; enabled: window.currentPane !== null; onClicked: if (window.currentPane) window.currentPane.editor.redo() }
            ToolSeparator {}
            BarButton { text: "\ud83d\udd0d"; tip: "Find (Ctrl+F)"; onClicked: findBar.open(false) }
            BarButton { objectName: "quickOpenButton"; action: quickOpenAction; text: "\ud83d\udd70"; tip: "Quick Open (Ctrl+P)" }
            BarButton { text: "\ud83d\udd0e"; objectName: "workspaceSearchToolbarButton"; action: workspaceSearchAction; tip: "Search Workspace (Ctrl+Shift+F)" }
            BarButton { objectName: "commandPaletteButton"; action: commandPaletteAction; text: "\ud83d\uddf3"; tip: "Command Pallete (F1)" }
            BarButton { objectName: "splitEditorsButton"; text: "||"; tip: "Toggle Split Editors (Ctrl+Alt+S)"; onClicked: window.toggleSplit() }
            BarButton { objectName: "lockTabButton"; action: lockTabAction; text: window.currentDoc && window.currentDoc.locked ? "Unlock" : "Lock"; tip: "Lock / Unlock Encrypted Tab (Ctrl+Alt+L)" }
            BarButton {
                objectName: "prettyPrintButton"
                action: prettyPrintAction
                text: "{}"
                tip: "Pretty Print JSON/XML (Ctrl+Shift+P)"
                Accessible.name: "Pretty Print"
            }
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
                onCompareFilesRequested: function(paths) { window.compareExplorerFiles(paths) }
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
                            required property bool pinned
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
                                        text: (tabButton.pinned ? "[P] " : "") + (tabButton.modified ? "\u2022 " : "") + tabButton.title
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
                                    enabled: !tabButton.pinned
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
                                if (d && (d.modified || d.pinned))
                                    kept++
                                else
                                    Documents.closeDocument(i)
                            }
                            if (kept > 0)
                                window.toast(kept + " pinned or modified tab(s) kept")
                        }

                        AppMenuItem {
                            objectName: "pinTabMenuItem"
                            text: tabMenu.doc && tabMenu.doc.pinned ? "Unpin Tab" : "Pin Tab"
                            enabled: tabMenu.doc !== null
                            onTriggered: tabMenu.doc.pinned = !tabMenu.doc.pinned
                        }
                        AppMenuItem {
                            text: "Close"
                            enabled: tabMenu.doc !== null && !tabMenu.doc.pinned
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

                    Item {
                        id: stack
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: markdownPreview.visible ? parent.width * 0.6 : parent.width
                        visible: Documents.count > 0

                        Repeater {
                            id: paneRepeater
                            model: Documents
                            EditorPane {
                                id: editorPaneDelegate
                                required property var document
                                required property int index
                                doc: document
                                docIndex: index
                                prettyPrintAction: window.prettyPrintCommand
                                safetyTools: safety
                                lockAction: window.tabLockCommand
                                Connections {
                                    target: editorPaneDelegate.doc
                                    function onErrorOccurred(message) { messageDialog.show(message) }
                                }
                                visible: window.splitEditors
                                         ? (doc === window.leftDocument || doc === window.rightDocument)
                                         : index === Documents.currentIndex
                                x: window.splitEditors && doc === window.rightDocument ? stack.width * window.splitRatio + 3 : 0
                                width: !window.splitEditors ? stack.width : (doc === window.rightDocument ? stack.width * (1 - window.splitRatio) - 3 : stack.width * window.splitRatio - 3)
                                height: stack.height
                                onStatusChanged: status.refresh()
                                onActivated: {
                                    if (visible)
                                        Documents.currentIndex = index
                                }
                                onExternalChangeRequested: window.comparePaneWithDisk(editorPaneDelegate, true)
                            }
                        }
                        Rectangle {
                            objectName: "splitEditorDivider"
                            visible: window.splitEditors
                            x: stack.width * window.splitRatio - 3
                            width: 6
                            height: parent.height
                            color: Prefs.border
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.SplitHCursor
                                onPositionChanged: function(mouse) {
                                    if (pressed)
                                        window.splitRatio = Math.max(0.2, Math.min(0.8, mapToItem(stack, mouse.x, mouse.y).x / stack.width))
                                }
                            }
                        }
                    }
                    MarkdownPreview {
                        id: markdownPreview
                        safetyTools: safety
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        anchors.right: parent.right
                        width: parent.width * 0.4
                        visible: window.showMarkdownPreview && window.unlockedDocument && window.currentDoc.language === "markdown"
                        pane: visible ? window.currentPane : null
                        onCloseRequested: window.showMarkdownPreview = false
                    }
                }

                FindReplaceBar {
                    id: findBar
                    Layout.fillWidth: true
                    pane: window.currentPane
                    onToast: function (message) { status.flash(message) }
                    onClosed: if (window.currentPane) window.currentPane.focusEditor()
                }
                CommandConsolePanel {
                    id: consolePanel
                    backend: commandConsole
                    visible: window.showConsole
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(260, window.height * 0.4)
                    onCloseRequested: window.toggleConsole()
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
    Shortcut { sequence: "Ctrl+Alt+S"; onActivated: window.toggleSplit() }
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
    Shortcut { sequence: "Ctrl+D"; enabled: explorerSidebar.treeFocused || (window.currentPane !== null && window.currentPane.editor.activeFocus); onActivated: {
        if (explorerSidebar.treeFocused)
            explorerSidebar.compareSelected()
        else
            window.runOp(TextOps.duplicateLines)
    } }
    Shortcut { sequence: "Ctrl+`"; onActivated: window.toggleConsole() }
    Shortcut { sequence: "Ctrl+Alt+G"; onActivated: gitPanel.showFor(window.workingDirectory()) }
    Shortcut { sequence: "Ctrl+F2"; enabled: window.currentPane !== null; onActivated: window.runCommand("bookmark") }
    Shortcut { sequence: "F2"; enabled: window.currentPane !== null; onActivated: window.navigateBookmark(false) }
    Shortcut { sequence: "Shift+F2"; enabled: window.currentPane !== null; onActivated: window.navigateBookmark(true) }
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
