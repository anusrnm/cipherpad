import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs

AppDialog {
    id: root
    objectName: "validationDialog"
    heading: "Validate JSON / XML"
    width: Math.min(700, parent.width - 40)
    standardButtons: Dialog.Close
    property var pane: null
    property var validationResult: ({})
    property string validatedText: ""
    property string schemaPath: ""

    function showFor(editorPane) {
        pane = editorPane
        schemaPath = ""
        open()
        validateNow()
    }
    function validateNow() {
        if (!pane || !pane.doc)
            return
        validatedText = pane.editor.text
        validationResult = Inspection.validate(validatedText, pane.doc.language, schemaPath)
    }
    onClosed: {
        pane = null
        validatedText = ""
        validationResult = ({})
    }
    FileDialog {
        id: schemaDialog
        title: "Select a self-contained JSON Schema or XSD (UTF-8)"
        fileMode: FileDialog.OpenFile
        onAccepted: {
            root.schemaPath = String(selectedFile)
            root.validateNow()
        }
    }

    ColumnLayout {
        width: parent.width
        Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: "Optional self-contained JSON Schema or XSD. Remote references, DTDs and XSD imports/includes are not loaded."
            color: Prefs.chromeText
        }
        RowLayout {
            BarButton { text: "Select Schema..."; wide: true; onClicked: schemaDialog.open() }
            BarButton { text: "Clear Schema"; wide: true; enabled: root.schemaPath !== ""; onClicked: { root.schemaPath = ""; root.validateNow() } }
            BarButton { objectName: "validateAgainButton"; text: "Validate"; wide: true; onClicked: root.validateNow() }
        }
        Label {
            Layout.fillWidth: true
            text: root.schemaPath || "Syntax validation only"
            elide: Text.ElideMiddle
            color: Prefs.chromeText
        }
        Label {
            objectName: "validationResult"
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: root.validationResult.valid ? "Valid" : (root.validationResult.error || "")
                  + (root.validationResult.line > 0 ? "\nLine " + root.validationResult.line + ", column " + root.validationResult.column : "")
                  + (root.validationResult.instancePath ? "\nJSON pointer: " + root.validationResult.instancePath : "")
            color: root.validationResult.valid ? Prefs.chromeText : Prefs.error
        }
        BarButton {
            objectName: "validationGotoButton"
            text: "Go to Error"
            wide: true
            enabled: root.validationResult.line > 0 && root.pane !== null && root.pane.editor.text === root.validatedText
            onClicked: {
                const target = root.pane
                const start = target.metrics.positionForLine(root.validationResult.line)
                // Parser columns count code points; the editor uses UTF-16.
                const lineEnd = target.metrics.lineEndPosition(root.validationResult.line)
                const line = target.editor.text.slice(start, lineEnd)
                const offset = Array.from(line).slice(0, Math.max(0, root.validationResult.column - 1)).join("").length
                target.editor.cursorPosition = start + offset
                root.close()
                target.focusEditor()
                target.ensureCursorVisible()
            }
        }
    }
}
