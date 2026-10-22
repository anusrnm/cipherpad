import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Cipherpad

// Prompts for a passphrase. In "confirm" mode it asks twice and shows a
// strength meter; in "unlock" mode it asks once.
AppDialog {
    id: root

    // "unlock" | "confirm"
    property string mode: "unlock"
    property string fileName: ""
    property string errorText: ""
    property bool allowEmpty: false

    signal passphraseAccepted(string passphrase)

    readonly property bool confirming: mode === "confirm"
    readonly property var strength: Crypto ? Crypto.passphraseStrength(passField.text) : [0, "Empty"]
    readonly property var strengthColors: ["#e06c75", "#e5c07b", "#98c379", "#56b6c2"]
    readonly property bool mismatch: confirming && confirmField.text !== "" && confirmField.text !== passField.text
    readonly property bool acceptable: passField.text.length > 0
                                       && (!confirming || confirmField.text === passField.text)

    heading: confirming ? "Set passphrase" : "Enter passphrase"
    standardButtons: Dialog.Ok | Dialog.Cancel
    initialFocusItem: passField
    width: 420

    function promptUnlock(name, message) {
        mode = "unlock"
        fileName = name || ""
        errorText = message || ""
        passField.text = ""
        confirmField.text = ""
        open()
        passField.forceActiveFocus()
    }

    function promptNew(name) {
        mode = "confirm"
        fileName = name || ""
        errorText = ""
        passField.text = ""
        confirmField.text = ""
        open()
        passField.forceActiveFocus()
    }

    onAccepted: root.passphraseAccepted(passField.text)
    onClosed: {
        passField.text = ""
        confirmField.text = ""
        revealBox.checked = false
    }

    ColumnLayout {
        spacing: 10
        width: parent.width

        Label {
            Layout.fillWidth: true
            visible: root.fileName !== ""
            text: root.confirming
                  ? "Encrypt \u201c" + root.fileName + "\u201d with a passphrase."
                  : "\u201c" + root.fileName + "\u201d is encrypted."
            color: Prefs.chromeText
            wrapMode: Text.Wrap
            opacity: 0.9
        }

        Label {
            Layout.fillWidth: true
            visible: root.errorText !== ""
            text: root.errorText
            color: "#e06c75"
            wrapMode: Text.Wrap
        }

        EditorTextField {
            id: passField
            Layout.fillWidth: true
            echoMode: revealBox.checked ? TextInput.Normal : TextInput.Password
            placeholderText: "Passphrase"
            onAccepted: if (root.acceptable) root.accept()
        }

        EditorTextField {
            id: confirmField
            Layout.fillWidth: true
            visible: root.confirming
            echoMode: revealBox.checked ? TextInput.Normal : TextInput.Password
            placeholderText: "Confirm passphrase"
            borderColor: root.mismatch ? "#e06c75" : Prefs.border
            onAccepted: if (root.acceptable) root.accept()
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            CheckBox {
                id: revealBox
                text: "Show passphrase"
                contentItem: Text {
                    text: parent.text
                    color: Prefs.chromeText
                    leftPadding: parent.indicator.width + 6
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: Math.max(11, Prefs.fontSize - 1)
                }
                indicator: Rectangle {
                    implicitWidth: 15
                    implicitHeight: 15
                    y: (parent.height - height) / 2
                    radius: 3
                    color: parent.checked ? Prefs.accent : "transparent"
                    border.color: Prefs.border
                }
            }

            Item { Layout.fillWidth: true }

            Label {
                visible: root.confirming && passField.text.length > 0
                text: root.mismatch ? "does not match" : root.strength[1]
                color: root.mismatch ? "#e06c75" : Prefs.chromeText
                font.pixelSize: Math.max(11, Prefs.fontSize - 1)
                opacity: 0.9
            }
        }

        // strength meter
        Row {
            Layout.fillWidth: true
            visible: root.confirming
            spacing: 4
            Repeater {
                model: 4
                Rectangle {
                    width: (root.width - 32 - 12) / 4
                    height: 4
                    radius: 2
                    color: index < root.strength[0]
                           ? root.strengthColors[Math.max(0, root.strength[0] - 1)]
                           : Prefs.border
                }
            }
        }

        Label {
            Layout.fillWidth: true
            visible: root.confirming
            text: "AES-256-GCM with scrypt key derivation. If you lose this passphrase the file cannot be recovered."
            color: Prefs.chromeText
            opacity: 0.6
            wrapMode: Text.Wrap
            font.pixelSize: Math.max(10, Prefs.fontSize - 3)
        }
    }

    Component.onCompleted: {
        const okButton = standardButton(Dialog.Ok)
        if (okButton)
            okButton.enabled = Qt.binding(function () { return root.acceptable })
    }
}
