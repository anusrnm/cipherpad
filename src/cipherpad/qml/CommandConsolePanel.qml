import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs

Rectangle {
    id: root
    objectName: "commandConsolePanel"
    color: Prefs.chrome
    required property var backend
    property string initialDirectory: ""
    signal closeRequested()

    function showFor(directory) {
        if (!backend.busy)
            directoryField.text = directory
        commandField.forceActiveFocus()
    }
    function submit() {
        const text = commandField.text
        const ok = backend.busy ? backend.sendInput(text) : backend.runCommand(text, directoryField.text)
        if (ok)
            commandField.text = ""
    }
    FolderDialog {
        title: "Console working directory"
        id: directoryPicker
        onAccepted: directoryField.text = root.backend.localDirectory(selectedFolder.toString())
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 6
        spacing: 4
        RowLayout {
            Layout.fillWidth: true
            Label { text: "COMMAND CONSOLE"; color: Prefs.chromeText; font.bold: true }
            TextField {
                id: directoryField
                objectName: "consoleDirectory"
                Layout.fillWidth: true
                text: root.initialDirectory
                enabled: !root.backend.busy
                color: Prefs.chromeText
                placeholderText: "Working directory"
            }
            BarButton { text: "..."; tip: "Choose working directory"; enabled: !root.backend.busy; onClicked: directoryPicker.open() }
            BarButton { text: "Clear"; wide: true; onClicked: root.backend.clearOutput() }
            BarButton { objectName: "consoleStopButton"; text: "Stop"; wide: true; enabled: root.backend.busy; onClicked: root.backend.stop() }
            BarButton { text: "X"; tip: "Hide console (command keeps running)"; onClicked: root.closeRequested() }
        }
        Label {
            Layout.fillWidth: true
            text: "Runs an executable with arguments, not a shell. For pipes/built-ins, explicitly invoke your shell. Commands have your user permissions."
            color: Prefs.chromeText
            opacity: 0.7
            wrapMode: Text.Wrap
        }
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            TextArea {
                id: outputArea
                objectName: "consoleOutput"
                text: root.backend.output
                textFormat: TextEdit.PlainText
                readOnly: true
                selectByMouse: true
                font.family: Prefs.fontFamily
                color: Prefs.text
                wrapMode: TextEdit.Wrap
                onTextChanged: cursorPosition = length
                background: Rectangle { color: Prefs.background }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            TextField {
                id: commandField
                objectName: "consoleCommand"
                Layout.fillWidth: true
                color: Prefs.chromeText
                placeholderText: root.backend.busy ? "Standard input for running command..." : "Executable and arguments..."
                onAccepted: root.submit()
            }
            BarButton { objectName: "consoleRunButton"; text: root.backend.busy ? "Send" : "Run"; wide: true; onClicked: root.submit() }
            BarButton { text: "EOF"; tip: "Close standard input"; enabled: root.backend.busy; onClicked: root.backend.closeInput() }
        }
    }
}
