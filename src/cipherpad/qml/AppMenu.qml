import QtQuick
import QtQuick.Controls.Basic

// Shared menu surface so the popup follows the active application theme.
Menu {
    id: control

    background: Rectangle {
        implicitWidth: 220
        color: Prefs.chrome
        border.color: Prefs.border
        border.width: 1
        radius: 3
    }
}
