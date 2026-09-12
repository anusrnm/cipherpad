import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Live-editing preferences: every control writes straight to Prefs, which
// persists through QSettings, so there is no apply/revert bookkeeping.
AppDialog {
    id: root

    heading: "Preferences"
    standardButtons: Dialog.Close
    width: 560
    height: 520

    component SectionLabel: Label {
        color: Prefs.chromeText
        font.bold: true
        font.pixelSize: Prefs.fontSize + 1
        topPadding: 6
    }

    component FieldLabel: Label {
        color: Prefs.chromeText
        opacity: 0.85
        Layout.preferredWidth: 170
    }

    component Check: CheckBox {
        id: box
        contentItem: Text {
            text: box.text
            color: Prefs.chromeText
            leftPadding: box.indicator.width + 6
            verticalAlignment: Text.AlignVCenter
            font.pixelSize: Math.max(11, Prefs.fontSize - 1)
        }
        indicator: Rectangle {
            implicitWidth: 15
            implicitHeight: 15
            x: 0
            y: (box.height - height) / 2
            radius: 3
            color: box.checked ? Prefs.accent : "transparent"
            border.color: Prefs.border
            Text {
                anchors.centerIn: parent
                visible: box.checked
                text: "\u2713"
                color: Prefs.background
                font.pixelSize: 11
            }
        }
    }

    component Combo: ComboBox {
        id: combo
        implicitHeight: 28
        Layout.preferredWidth: 190
        contentItem: Text {
            text: combo.displayText
            color: Prefs.chromeText
            leftPadding: 8
            rightPadding: 24
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            font.pixelSize: Math.max(11, Prefs.fontSize - 1)
        }
        background: Rectangle {
            color: Prefs.background
            border.color: combo.activeFocus ? Prefs.accent : Prefs.border
            radius: 3
        }
        indicator: Text {
            x: combo.width - width - 8
            y: (combo.height - height) / 2
            text: "\u25be"
            color: Prefs.chromeText
        }
        delegate: ItemDelegate {
            width: combo.width
            highlighted: combo.highlightedIndex === index
            contentItem: Text {
                text: combo.textRole ? modelData[combo.textRole] : modelData
                color: Prefs.chromeText
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: Math.max(11, Prefs.fontSize - 1)
            }
            background: Rectangle {
                color: highlighted ? Prefs.accent : Prefs.chrome
            }
        }
        popup: Popup {
            y: combo.height
            width: combo.width
            implicitHeight: Math.min(280, contentItem.implicitHeight)
            padding: 1
            contentItem: ListView {
                clip: true
                implicitHeight: contentHeight
                model: combo.popup.visible ? combo.delegateModel : null
                currentIndex: combo.highlightedIndex
                ScrollIndicator.vertical: ScrollIndicator {}
            }
            background: Rectangle {
                color: Prefs.chrome
                border.color: Prefs.border
                radius: 3
            }
        }
    }

    component Spin: SpinBox {
        id: spin
        implicitHeight: 28
        Layout.preferredWidth: 110
        editable: true
        contentItem: TextInput {
            text: spin.textFromValue(spin.value, spin.locale)
            color: Prefs.chromeText
            horizontalAlignment: Qt.AlignHCenter
            verticalAlignment: Qt.AlignVCenter
            readOnly: !spin.editable
            validator: spin.validator
            selectionColor: Prefs.accent
            font.pixelSize: Math.max(11, Prefs.fontSize - 1)
        }
        background: Rectangle {
            color: Prefs.background
            border.color: Prefs.border
            radius: 3
        }
        up.indicator: Rectangle {
            x: spin.width - width
            height: spin.height
            implicitWidth: 24
            color: spin.up.pressed ? Prefs.accent : "transparent"
            Text {
                anchors.centerIn: parent
                text: "+"
                color: Prefs.chromeText
            }
        }
        down.indicator: Rectangle {
            height: spin.height
            implicitWidth: 24
            color: spin.down.pressed ? Prefs.accent : "transparent"
            Text {
                anchors.centerIn: parent
                text: "\u2212"
                color: Prefs.chromeText
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        TabBar {
            id: tabs
            Layout.fillWidth: true
            background: Rectangle { color: "transparent" }
            Repeater {
                model: ["Editor", "Appearance", "Files", "Colours"]
                TabButton {
                    text: modelData
                    contentItem: Text {
                        text: parent.text
                        color: Prefs.chromeText
                        opacity: parent.checked ? 1.0 : 0.6
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: Math.max(11, Prefs.fontSize - 1)
                    }
                    background: Rectangle {
                        color: "transparent"
                        Rectangle {
                            anchors.bottom: parent.bottom
                            width: parent.width
                            height: 2
                            color: parent.parent.checked ? Prefs.accent : "transparent"
                        }
                    }
                }
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabs.currentIndex

            // ------------------------------------------------------ Editor
            Flickable {
                contentHeight: editorCol.implicitHeight
                clip: true
                ColumnLayout {
                    id: editorCol
                    width: parent.width
                    spacing: 6

                    SectionLabel { text: "Indentation" }
                    RowLayout {
                        FieldLabel { text: "Tab width" }
                        Spin {
                            from: 1; to: 16
                            value: Prefs.tabWidth
                            onValueModified: Prefs.tabWidth = value
                        }
                    }
                    Check {
                        text: "Insert spaces instead of tabs"
                        checked: Prefs.insertSpaces
                        onToggled: Prefs.insertSpaces = checked
                    }
                    Check {
                        text: "Auto-indent new lines"
                        checked: Prefs.autoIndent
                        onToggled: Prefs.autoIndent = checked
                    }

                    SectionLabel { text: "Typing" }
                    Check {
                        text: "Auto-close brackets and quotes"
                        checked: Prefs.autoCloseBrackets
                        onToggled: Prefs.autoCloseBrackets = checked
                    }
                    Check {
                        text: "Highlight matching bracket"
                        checked: Prefs.matchBrackets
                        onToggled: Prefs.matchBrackets = checked
                    }
                    Check {
                        text: "Word wrap"
                        checked: Prefs.wordWrap
                        onToggled: Prefs.wordWrap = checked
                    }

                    SectionLabel { text: "Search" }
                    Check {
                        text: "Wrap around when searching"
                        checked: Prefs.searchWrapAround
                        onToggled: Prefs.searchWrapAround = checked
                    }
                }
            }

            // -------------------------------------------------- Appearance
            Flickable {
                contentHeight: lookCol.implicitHeight
                clip: true
                ColumnLayout {
                    id: lookCol
                    width: parent.width
                    spacing: 6

                    SectionLabel { text: "Theme" }
                    RowLayout {
                        FieldLabel { text: "Colour theme" }
                        Combo {
                            model: Prefs.availableThemes
                            currentIndex: Math.max(0, Prefs.availableThemes.indexOf(Prefs.theme))
                            onActivated: Prefs.applyTheme(currentText)
                        }
                    }

                    SectionLabel { text: "Font" }
                    RowLayout {
                        FieldLabel { text: "Family" }
                        Combo {
                            id: familyCombo
                            model: Qt.fontFamilies()
                            Component.onCompleted: {
                                const i = model.indexOf(Prefs.fontFamily)
                                if (i >= 0) currentIndex = i
                            }
                            onActivated: Prefs.fontFamily = currentText
                        }
                    }
                    RowLayout {
                        FieldLabel { text: "Size" }
                        Spin {
                            from: 6; to: 72
                            value: Prefs.fontSize
                            onValueModified: Prefs.fontSize = value
                        }
                    }
                    RowLayout {
                        FieldLabel { text: "Line height" }
                        Spin {
                            from: 80; to: 300; stepSize: 5
                            value: Math.round(Prefs.lineHeight * 100)
                            onValueModified: Prefs.lineHeight = value / 100
                            textFromValue: function (v) { return (v / 100).toFixed(2) }
                            valueFromText: function (t) { return Math.round(parseFloat(t) * 100) }
                        }
                    }
                    Check {
                        text: "Bold"
                        checked: Prefs.fontBold
                        onToggled: Prefs.fontBold = checked
                    }
                    Check {
                        text: "Italic"
                        checked: Prefs.fontItalic
                        onToggled: Prefs.fontItalic = checked
                    }

                    SectionLabel { text: "Display" }
                    Check {
                        text: "Show line numbers"
                        checked: Prefs.showLineNumbers
                        onToggled: Prefs.showLineNumbers = checked
                    }
                    Check {
                        text: "Highlight current line"
                        checked: Prefs.highlightCurrentLine
                        onToggled: Prefs.highlightCurrentLine = checked
                    }
                    Check {
                        text: "Syntax highlighting"
                        checked: Prefs.syntaxHighlighting
                        onToggled: Prefs.syntaxHighlighting = checked
                    }
                    Check {
                        text: "Show whitespace characters"
                        checked: Prefs.showWhitespace
                        onToggled: Prefs.showWhitespace = checked
                    }
                    Check {
                        text: "Show toolbar"
                        checked: Prefs.showToolBar
                        onToggled: Prefs.showToolBar = checked
                    }
                    Check {
                        text: "Show status bar"
                        checked: Prefs.showStatusBar
                        onToggled: Prefs.showStatusBar = checked
                    }
                }
            }

            // ------------------------------------------------------- Files
            Flickable {
                contentHeight: fileCol.implicitHeight
                clip: true
                ColumnLayout {
                    id: fileCol
                    width: parent.width
                    spacing: 6

                    SectionLabel { text: "On save" }
                    Check {
                        text: "Trim trailing whitespace"
                        checked: Prefs.trimTrailingWhitespaceOnSave
                        onToggled: Prefs.trimTrailingWhitespaceOnSave = checked
                    }
                    Check {
                        text: "Ensure newline at end of file"
                        checked: Prefs.ensureNewlineAtEof
                        onToggled: Prefs.ensureNewlineAtEof = checked
                    }

                    SectionLabel { text: "Defaults for new files" }
                    RowLayout {
                        FieldLabel { text: "Encoding" }
                        Combo {
                            model: ["utf-8", "utf-8-sig", "utf-16", "latin-1", "cp1252", "ascii"]
                            currentIndex: Math.max(0, model.indexOf(Prefs.defaultEncoding))
                            onActivated: Prefs.defaultEncoding = currentText
                        }
                    }
                    RowLayout {
                        FieldLabel { text: "Line endings" }
                        Combo {
                            model: ["lf", "crlf", "cr"]
                            currentIndex: Math.max(0, model.indexOf(Prefs.defaultLineEnding))
                            onActivated: Prefs.defaultLineEnding = currentText
                        }
                    }

                    SectionLabel { text: "Session" }
                    Check {
                        text: "Reopen last session on startup"
                        checked: Prefs.restoreSession
                        onToggled: Prefs.restoreSession = checked
                    }
                    RowLayout {
                        BarButton {
                            text: "Clear recent files"
                            wide: true
                            onClicked: Prefs.clearRecentFiles()
                        }
                        BarButton {
                            text: "Reset all settings"
                            wide: true
                            onClicked: Prefs.resetToDefaults()
                        }
                    }
                }
            }

            // ----------------------------------------------------- Colours
            Flickable {
                contentHeight: colourGrid.implicitHeight
                clip: true
                GridLayout {
                    id: colourGrid
                    width: parent.width
                    columns: 2
                    columnSpacing: 12
                    rowSpacing: 4

                    Repeater {
                        model: [
                            { label: "Background", key: "background" },
                            { label: "Text", key: "text" },
                            { label: "Selection", key: "selection" },
                            { label: "Current line", key: "currentLine" },
                            { label: "Accent", key: "accent" },
                            { label: "Chrome", key: "chrome" },
                            { label: "Chrome text", key: "chromeText" },
                            { label: "Border", key: "border" },
                            { label: "Gutter background", key: "gutterBackground" },
                            { label: "Gutter text", key: "gutterText" },
                            { label: "Gutter current", key: "gutterCurrent" },
                            { label: "Keyword", key: "keyword" },
                            { label: "Type", key: "typeColor" },
                            { label: "Builtin", key: "builtin" },
                            { label: "String", key: "string" },
                            { label: "Comment", key: "comment" },
                            { label: "Number", key: "number" },
                            { label: "Function", key: "function" },
                            { label: "Operator", key: "operator" },
                            { label: "Preprocessor", key: "preprocessor" },
                            { label: "Decorator", key: "decorator" },
                            { label: "Tag", key: "tag" },
                            { label: "Attribute", key: "attribute" },
                            { label: "Heading", key: "heading" },
                            { label: "Link", key: "link" },
                            { label: "Error", key: "error" }
                        ]

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6

                            Rectangle {
                                width: 18
                                height: 18
                                radius: 3
                                color: Prefs[modelData.key]
                                border.color: Prefs.border
                            }
                            Label {
                                text: modelData.label
                                color: Prefs.chromeText
                                opacity: 0.85
                                Layout.preferredWidth: 110
                                font.pixelSize: Math.max(11, Prefs.fontSize - 1)
                            }
                            EditorTextField {
                                Layout.fillWidth: true
                                Layout.maximumWidth: 100
                                text: Prefs[modelData.key]
                                onEditingFinished: {
                                    if (/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(text))
                                        Prefs[modelData.key] = text
                                    else
                                        text = Prefs[modelData.key]
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
