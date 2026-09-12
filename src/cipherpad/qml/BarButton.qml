import QtQuick
import QtQuick.Controls.Basic

// Compact push button for the find bar and dialog footers.
Button {
    id: control

    property string tip: ""
    property bool wide: false

    implicitWidth: wide ? Math.max(84, contentLabel.implicitWidth + 20) : 28
    implicitHeight: 26
    ToolTip.text: tip
    ToolTip.visible: tip !== "" && hovered
    ToolTip.delay: 500

    contentItem: Text {
        id: contentLabel
        text: control.text
        color: control.enabled ? Prefs.chromeText : Qt.rgba(0.5, 0.5, 0.5, 0.6)
        font.family: Prefs.fontFamily
        font.pixelSize: Math.max(11, Prefs.fontSize - 1)
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        radius: 3
        color: control.down ? Prefs.accent
               : control.hovered ? Prefs.border
               : "transparent"
        border.color: control.wide ? Prefs.border : "transparent"
        border.width: 1
    }
}
