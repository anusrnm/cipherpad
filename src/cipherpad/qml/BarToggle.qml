import QtQuick
import QtQuick.Controls.Basic

// Small sticky toggle used for the search option flags.
Button {
    id: control

    property string tip: ""

    checkable: true
    implicitWidth: 28
    implicitHeight: 26
    ToolTip.text: tip
    ToolTip.visible: tip !== "" && hovered
    ToolTip.delay: 500

    contentItem: Text {
        text: control.text
        color: control.checked ? Prefs.background : Prefs.chromeText
        font.pixelSize: Math.max(10, Prefs.fontSize - 2)
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        radius: 3
        color: control.checked ? Prefs.accent
               : control.hovered ? Prefs.border
               : "transparent"
    }
}
