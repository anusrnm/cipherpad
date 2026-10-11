import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    id: root
    objectName: "markdownPreview"
    color: Prefs.background
    property var pane: null
    property string source: pane ? pane.editor.text : ""
    property string rendered: ""
    property string error: ""
    property var safetyTools: null
    signal closeRequested()
    onSourceChanged: refreshTimer.restart()
    onVisibleChanged: {
        if (visible)
            refreshTimer.restart()
        else {
            rendered = ""
            error = ""
        }
    }
    Timer {
        id: refreshTimer
        interval: 200
        onTriggered: {
            if (!root.visible)
                return
            const result = Inspection.markdown(root.source)
            root.error = result.error || ""
            root.rendered = result.html || ""
        }
    }
    ColumnLayout {
        anchors.fill: parent
        RowLayout {
            Layout.fillWidth: true
            Label { Layout.fillWidth: true; text: "Markdown Preview (offline)"; color: Prefs.chromeText }
            BarButton { text: "X"; tip: "Close preview"; onClicked: root.closeRequested() }
        }
        Label {
            visible: root.error !== ""
            text: root.error
            color: Prefs.error
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            TextArea {
                id: previewText
                Keys.onPressed: function(event) {
                    if (event.matches(StandardKey.Copy) && root.safetyTools) {
                        event.accepted = true
                        if (previewText.selectedText.length)
                            root.safetyTools.copyText(previewText.selectedText,
                                                 root.pane && root.pane.doc.encrypted,
                                                 Prefs.clipboardExpirySeconds)
                    }
                }
                objectName: "markdownRendered"
                text: root.rendered
                readOnly: true
                selectByMouse: true
                textFormat: TextEdit.RichText
                wrapMode: TextEdit.Wrap
                color: Prefs.text
                background: null
            }
        }
    }
}
