import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

AppDialog {
    id: root
    objectName: "jsonTreeDialog"
    heading: "JSON Tree"
    width: Math.min(760, parent.width - 40)
    height: Math.min(650, parent.height - 40)
    standardButtons: Dialog.Close
    property var nodes: []
    property var rows: []
    property var collapsed: ({})
    property bool limited: false
    property string selectedPointer: ""
    property var safetyTools: null
    property bool sensitive: false

    function showTree(result, encrypted) {
        sensitive = encrypted === true
        nodes = result.nodes
        limited = result.limited === true
        collapsed = ({})
        selectedPointer = ""
        rebuild()
        open()
    }
    function rebuild() {
        const hidden = ({})
        rows = nodes.filter(node => {
            hidden[node.index] = hidden[node.parent] || collapsed[node.parent] === true
            return !hidden[node.index]
        })
    }
    function toggle(node) {
        selectedPointer = node.pointer
        if (node.container) {
            collapsed[node.index] = !collapsed[node.index]
            rebuild()
        }
    }
    onClosed: {
        nodes = []
        rows = []
        collapsed = ({})
        selectedPointer = ""
        sensitive = false
    }
    ColumnLayout {
        anchors.fill: parent
        Label {
            visible: root.limited
            text: "Tree limited to 10,000 nodes."
            color: Prefs.error
        }
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.rows
            ScrollBar.vertical: ScrollBar {}
            delegate: ItemDelegate {
                required property var modelData
                width: ListView.view.width
                contentItem: Label {
                    leftPadding: Math.min(200, modelData.depth * 16)
                    text: (modelData.container ? (root.collapsed[modelData.index] ? "+ " : "- ") : "  ") + modelData.label
                    color: Prefs.chromeText
                    elide: Text.ElideRight
                }
                onClicked: root.toggle(modelData)
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Label {
                Layout.fillWidth: true
                text: "Pointer: " + (root.selectedPointer || "(root)")
                elide: Text.ElideMiddle
                color: Prefs.chromeText
            }
            BarButton {
                objectName: "jsonTreeCopyPointerButton"
                text: "Copy Pointer"; wide: true
                onClicked: {
                    if (root.safetyTools)
                        root.safetyTools.copyText(root.selectedPointer, root.sensitive, Prefs.clipboardExpirySeconds)
                    else
                        Explorer.copyToClipboard(root.selectedPointer)
                }
            }
        }
    }
}
