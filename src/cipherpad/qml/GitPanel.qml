import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

AppDialog {
    id: root
    objectName: "gitPanel"
    required property var git
    property string directory: ""
    property string selectedPath: ""
    readonly property var selected: git.entries.find(entry => entry.path === selectedPath) || null
    signal fileRequested(string path)
    heading: "Git - Saved Files"
    width: Math.min(850, parent.width - 40)
    height: Math.min(650, parent.height - 40)
    standardButtons: Dialog.Close

    function showFor(path) {
        directory = path
        selectedPath = ""
        open()
        git.refresh(directory)
    }
    ColumnLayout {
        anchors.fill: parent
        RowLayout {
            Layout.fillWidth: true
            TextField {
                objectName: "gitDirectory"
                Layout.fillWidth: true
                text: root.directory
                color: Prefs.chromeText
                enabled: !root.git.busy
                onEditingFinished: root.directory = text
                placeholderText: "Repository directory"
            }
            BarButton { text: "Refresh"; wide: true; enabled: !root.git.busy; onClicked: root.git.refresh(root.directory) }
        }
        Label {
            Layout.fillWidth: true
            text: root.git.busy ? "Running Git..." : root.git.branch + (root.git.root ? "\n" + root.git.root : "")
            wrapMode: Text.Wrap
            color: Prefs.chromeText
        }
        Label {
            Layout.fillWidth: true
            text: "Git operates on saved files only. Unsaved editor changes are not staged. Commits include ALL staged repository changes and run configured Git hooks."
            wrapMode: Text.Wrap
            color: Prefs.chromeText
        }
        ListView {
            id: changes
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.git.entries
            ScrollBar.vertical: ScrollBar {}
            delegate: ItemDelegate {
                required property var modelData
                objectName: "gitEntry:" + modelData.path
                width: changes.width
                highlighted: root.selectedPath === modelData.path
                contentItem: Label {
                    text: modelData.status + "  " + modelData.path + (modelData.oldPath ? " <- " + modelData.oldPath : "")
                    color: Prefs.chromeText
                    elide: Text.ElideMiddle
                }
                onClicked: root.selectedPath = modelData.path
                onDoubleClicked: root.fileRequested(root.git.root + "/" + modelData.path)
            }
            Label {
                anchors.centerIn: parent
                text: root.git.root && !root.git.busy && !root.git.entries.length ? "Working tree clean" : ""
                color: Prefs.chromeText
            }
        }
        RowLayout {
            Layout.fillWidth: true
            BarButton { objectName: "gitStageButton"; text: "Stage"; wide: true; enabled: !!root.selected && !root.git.busy; onClicked: root.git.stage(root.selectedPath, false) }
            BarButton { objectName: "gitUnstageButton"; text: "Unstage"; wide: true; enabled: !!root.selected && root.selected.staged && !root.git.busy; onClicked: root.git.stage(root.selectedPath, true) }
            BarButton { objectName: "gitWorkingDiffButton"; text: "Working Diff"; wide: true; enabled: !!root.selected && !root.git.busy; onClicked: root.git.diff(root.selectedPath, false) }
            BarButton { objectName: "gitStagedDiffButton"; text: "Staged Diff"; wide: true; enabled: !!root.selected && root.selected.staged && !root.git.busy; onClicked: root.git.diff(root.selectedPath, true) }
        }
        RowLayout {
            Layout.fillWidth: true
            TextField {
                id: commitMessage
                objectName: "gitCommitMessage"
                Layout.fillWidth: true
                color: Prefs.chromeText
                placeholderText: "Commit message"
            }
            BarButton {
                objectName: "gitCommitButton"
                text: "Commit..."
                wide: true
                enabled: !root.git.busy && commitMessage.text.trim() !== "" && root.git.entries.some(entry => entry.staged)
                onClicked: commitConfirm.open()
            }
        }
    }
    AppDialog {
        id: commitConfirm
        objectName: "gitCommitConfirm"
        heading: "Commit all staged changes?"
        standardButtons: Dialog.Yes | Dialog.Cancel
        defaultButton: Dialog.Cancel
        width: 460
        Label {
            width: parent.width
            text: "Repository: " + root.git.root + "\n\n" + root.git.entries.filter(entry => entry.staged).map(entry => entry.path).join("\n")
            wrapMode: Text.Wrap
            color: Prefs.chromeText
        }
        onAccepted: root.git.commit(commitMessage.text)
    }
}
