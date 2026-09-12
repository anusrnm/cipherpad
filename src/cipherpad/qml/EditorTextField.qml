import QtQuick
import QtQuick.Controls.Basic

// Themed single-line text field used across the chrome and dialogs.
TextField {
    id: field

    property color borderColor: Prefs.border

    color: Prefs.chromeText
    placeholderTextColor: Qt.rgba(field.color.r, field.color.g, field.color.b, 0.45)
    selectionColor: Prefs.accent
    selectedTextColor: Prefs.background
    font.family: Prefs.fontFamily
    font.pixelSize: Math.max(11, Prefs.fontSize - 1)
    leftPadding: 8
    rightPadding: 8
    implicitHeight: 28

    background: Rectangle {
        color: Prefs.background
        border.color: field.activeFocus ? Prefs.accent : field.borderColor
        border.width: 1
        radius: 3
    }
}
