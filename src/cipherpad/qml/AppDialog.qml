import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Base shell every dialog in the app uses so they share chrome and colours.
Dialog {
    id: root

    property string heading: title

    modal: true
    anchors.centerIn: Overlay.overlay
    closePolicy: Popup.CloseOnEscape
    padding: 16

    Overlay.modal: Rectangle { color: "#99000000" }

    background: Rectangle {
        color: Prefs.chrome
        border.color: Prefs.border
        border.width: 1
        radius: 6
    }

    header: Item {
        implicitHeight: 40
        Label {
            anchors.left: parent.left
            anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            text: root.heading
            color: Prefs.chromeText
            font.pixelSize: Math.max(13, Prefs.fontSize + 1)
            font.bold: true
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: Prefs.border
        }
    }

    footer: DialogButtonBox {
        id: buttonBox
        padding: 12
        spacing: 8
        alignment: Qt.AlignRight
        background: Rectangle {
            color: "transparent"
            Rectangle {
                width: parent.width
                height: 1
                color: Prefs.border
            }
        }
        delegate: BarButton { wide: true }
    }
}
