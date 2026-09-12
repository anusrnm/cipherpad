import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

AppDialog {
    id: root

    heading: "About"
    standardButtons: Dialog.Close
    width: 400

    ColumnLayout {
        spacing: 10
        width: parent.width

        Label {
            text: "Cipherpad"
            color: Prefs.chromeText
            font.pixelSize: Prefs.fontSize + 8
            font.bold: true
        }

        Label {
            text: "Version " + appVersion
            color: Prefs.chromeText
            opacity: 0.7
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Prefs.border }

        Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            color: Prefs.chromeText
            opacity: 0.85
            text: "A text editor for plain and encrypted files, built with PySide6 and Qt Quick.\n\n"
                  + "Encryption uses " + (Crypto ? Crypto.algorithm() : "AES-256-GCM / scrypt")
                  + ": the passphrase is stretched with scrypt and the file body is sealed with "
                  + "authenticated encryption, so tampering is detected on open."
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Prefs.border }

        GridLayout {
            columns: 2
            columnSpacing: 16
            rowSpacing: 4
            Layout.fillWidth: true

            Repeater {
                model: [
                    "Ctrl+N", "New file",
                    "Ctrl+O", "Open",
                    "Ctrl+S", "Save",
                    "Ctrl+F", "Find",
                    "Ctrl+H", "Replace",
                    "Ctrl+G", "Go to line",
                    "Ctrl+D", "Duplicate line",
                    "Ctrl+/", "Toggle comment",
                    "Alt+\u2191/\u2193", "Move line",
                    "Ctrl+Shift+E", "Encrypt file",
                    "Ctrl+ +/-", "Zoom"
                ]
                Label {
                    text: modelData
                    color: Prefs.chromeText
                    opacity: index % 2 === 0 ? 1.0 : 0.7
                    font.family: index % 2 === 0 ? Prefs.fontFamily : root.font.family
                    font.pixelSize: Math.max(11, Prefs.fontSize - 1)
                }
            }
        }
    }
}
