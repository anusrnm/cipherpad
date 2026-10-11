import QtQuick
import QtQuick.Controls.Basic

// Line numbers that follow the real text layout, so they stay aligned even
// when word wrap turns one logical line into several visual ones.
Item {
    id: root

    required property var metrics
    required property var flickable
    property int currentLine: 1
    property real editorPadding: 6

    signal lineClicked(int line)
    signal bookmarkRequested(int line)
    property var bookmarks: metrics ? metrics.bookmarks : []

    property var rows: []
    readonly property int digits: Math.max(3, String(metrics ? metrics.lineCount : 1).length)

    implicitWidth: digits * fontMetrics.advanceWidth("0") + 24

    function refresh() {
        if (!metrics || !flickable) {
            rows = []
            return
        }
        const top = flickable.contentY - editorPadding
        rows = metrics.linesIn(Math.max(0, top), top + flickable.height)
    }

    function screenY(row) {
        return row.y + editorPadding - flickable.contentY
    }

    FontMetrics {
        id: fontMetrics
        font.family: Prefs.fontFamily
        font.pixelSize: Prefs.fontSize
    }

    Rectangle {
        anchors.fill: parent
        color: Prefs.gutterBackground
    }

    Item {
        anchors.fill: parent
        clip: true

        Repeater {
            model: root.rows
            delegate: Item {
                id: lineItem
                required property var modelData
                readonly property bool isCurrent: modelData.number === root.currentLine

                width: root.width
                height: modelData.height
                y: root.screenY(modelData)

                Rectangle {
                    anchors.fill: parent
                    visible: lineItem.isCurrent && Prefs.highlightCurrentLine
                    color: Prefs.currentLine
                }

                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.top: parent.top
                    text: lineItem.modelData.number
                    color: lineItem.isCurrent ? Prefs.gutterCurrent : Prefs.gutterText
                    font.family: Prefs.fontFamily
                    font.pixelSize: Prefs.fontSize
                    font.bold: lineItem.isCurrent
                }
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 3
                    text: "*"
                    color: Prefs.accent
                    visible: root.bookmarks.includes(lineItem.modelData.number)
                    font.bold: true
                }
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.ArrowCursor
        onClicked: function (mouse) {
            for (let i = 0; i < root.rows.length; ++i) {
                const row = root.rows[i]
                const top = root.screenY(row)
                if (mouse.y >= top && mouse.y <= top + row.height) {
                    if (mouse.x < 16)
                        root.bookmarkRequested(row.number)
                    else
                        root.lineClicked(row.number)
                    return
                }
            }
        }
    }
}
