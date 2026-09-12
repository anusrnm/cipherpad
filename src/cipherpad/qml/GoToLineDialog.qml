import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

AppDialog {
    id: root

    property int lineCount: 1
    signal lineRequested(int line)

    heading: "Go to line"
    standardButtons: Dialog.Ok | Dialog.Cancel
    width: 300

    function promptFor(count, current) {
        lineCount = Math.max(1, count)
        field.text = String(current)
        open()
        field.forceActiveFocus()
        field.selectAll()
    }

    onAccepted: {
        const value = parseInt(field.text, 10)
        if (!isNaN(value))
            root.lineRequested(Math.min(Math.max(1, value), root.lineCount))
    }

    ColumnLayout {
        spacing: 8
        width: parent.width

        Label {
            text: "Line number (1 \u2013 " + root.lineCount + ")"
            color: Prefs.chromeText
            opacity: 0.85
        }

        EditorTextField {
            id: field
            Layout.fillWidth: true
            validator: IntValidator { bottom: 1; top: root.lineCount }
            onAccepted: root.accept()
        }
    }
}
