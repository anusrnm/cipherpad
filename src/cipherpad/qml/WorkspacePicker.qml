import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

AppDialog {
    id: root
    objectName: "workspacePicker"
    width: Math.min(720, parent.width - 40)
    height: Math.min(560, parent.height - 40)
    standardButtons: Dialog.Close
    initialFocusItem: query
    property bool commandsMode: false
    property var commands: []
    property var results: []
    signal fileRequested(string path)
    signal commandRequested(string command)

    function updateResults() {
        if (commandsMode) {
            const words = query.text.toLowerCase().trim().split(/\s+/)
            results = commands.filter(c => words.every(w => c.label.toLowerCase().includes(w)))
        } else {
            results = Workspace.quickFiles(query.text)
        }
        list.currentIndex = results.length ? 0 : -1
    }

    function showFiles() {
        commandsMode = false
        heading = "Quick Open"
        query.text = ""
        updateResults()
        open()
        query.forceActiveFocus()
        if (!Workspace.busy)
            Workspace.scanFiles()
    }

    function showCommands() {
        commandsMode = true
        heading = "Command Palette"
        query.text = ""
        updateResults()
        open()
        query.forceActiveFocus()
    }

    function choose(index) {
        if (index < 0 || index >= results.length)
            return
        const entry = results[index]
        if (commandsMode && entry.enabled === false)
            return
        close()
        if (commandsMode)
            commandRequested(entry.command)
        else
            fileRequested(entry.path)
    }

    Connections {
        target: Workspace
        function onEntriesChanged() { if (!root.commandsMode) root.updateResults() }
    }
    onCommandsChanged: if (commandsMode) updateResults()

    ColumnLayout {
        anchors.fill: parent
        TextField {
            id: query
            objectName: "workspacePickerQuery"
            Layout.fillWidth: true
            color: Prefs.chromeText
            placeholderText: root.commandsMode ? "Search commands" : "Fuzzy filename search"
            onTextChanged: root.updateResults()
            Keys.onDownPressed: list.currentIndex = Math.min(list.count - 1, list.currentIndex + 1)
            Keys.onUpPressed: list.currentIndex = Math.max(0, list.currentIndex - 1)
            onAccepted: root.choose(list.currentIndex)
        }
        Label {
            Layout.fillWidth: true
            visible: !root.commandsMode
            text: Workspace.busy ? "Scanning workspace..." : Workspace.status
            color: Prefs.chromeText
            wrapMode: Text.Wrap
        }
        ListView {
            id: list
            objectName: "workspacePickerResults"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.results
            ScrollBar.vertical: ScrollBar {}
            delegate: ItemDelegate {
                required property var modelData
                required property int index
                width: list.width
                highlighted: list.currentIndex === index
                enabled: !root.commandsMode || modelData.enabled !== false
                contentItem: Label {
                    text: modelData.label || modelData.relative
                    color: highlighted ? Prefs.background : Prefs.chromeText
                    elide: Text.ElideMiddle
                }
                background: Rectangle { color: highlighted ? Prefs.accent : "transparent" }
                onClicked: root.choose(index)
            }
            Label {
                anchors.centerIn: parent
                visible: list.count === 0 && (root.commandsMode || !Workspace.busy)
                text: "No matches"
                color: Prefs.chromeText
            }
        }
        BarButton {
            visible: !root.commandsMode && Workspace.busy
            text: "Cancel scan"
            wide: true
            onClicked: Workspace.cancel()
        }
    }
}
