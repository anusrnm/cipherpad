import QtQuick
import QtQuick.Controls.Basic

// Themed menu entry that can show a shortcut hint on the right.
MenuItem {
    id: control

    property string shortcutText: ""

    implicitHeight: 26

    contentItem: Item {
        Text {
            anchors.left: parent.left
            anchors.leftMargin: control.checkable ? 20 : 4
            anchors.verticalCenter: parent.verticalCenter
            text: control.text
            color: control.enabled ? Prefs.chromeText : Qt.rgba(0.5, 0.5, 0.5, 0.7)
            font.pixelSize: Math.max(11, Prefs.fontSize - 1)
        }
        Text {
            anchors.right: parent.right
            anchors.rightMargin: 4
            anchors.verticalCenter: parent.verticalCenter
            visible: control.shortcutText !== ""
            text: control.shortcutText
            color: Prefs.chromeText
            opacity: 0.45
            font.pixelSize: Math.max(10, Prefs.fontSize - 2)
        }
    }

    indicator: Item {
        implicitWidth: 18
        height: control.height
        Text {
            anchors.centerIn: parent
            visible: control.checkable && control.checked
            text: "\u2713"
            color: Prefs.accent
            font.pixelSize: 12
        }
    }

    background: Rectangle {
        implicitWidth: 220
        color: control.highlighted ? Prefs.accent : "transparent"
    }
}
