import QtQuick
import QtQuick.Controls.Basic

// Small read-out in the status bar (encoding, line endings, indentation, ...).
Item {
    id: chip

    property string text: ""
    property string tip: ""
    property bool accented: false

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight
    visible: text !== ""

    Text {
        id: label
        anchors.centerIn: parent
        text: chip.text
        color: chip.accented ? Prefs.accent : Prefs.chromeText
        opacity: chip.accented ? 1.0 : 0.8
        font.pixelSize: Math.max(10, Prefs.fontSize - 2)
    }

    ToolTip.text: chip.tip
    ToolTip.visible: chip.tip !== "" && hover.hovered
    ToolTip.delay: 600

    HoverHandler { id: hover }
}
