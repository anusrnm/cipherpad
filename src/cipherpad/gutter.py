"""Geometry helpers for the editor gutter and the status bar.

Word wrap makes "line N is at y = N * lineHeight" wrong, so the gutter asks the
real ``QTextDocument`` layout for the position and height of each block. Only
the blocks inside the viewport are reported, which keeps scrolling cheap even in
very large files.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, QPointF, Qt, Signal, Slot
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtQml import QmlElement
from PySide6.QtQuick import QQuickTextDocument

QML_IMPORT_NAME = "Cipherpad"
QML_IMPORT_MAJOR_VERSION = 1


@QmlElement
class DocumentMetrics(QObject):
    """Exposes ``QTextDocument`` layout information to QML."""

    documentChanged = Signal()
    layoutChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._quick_document: QQuickTextDocument | None = None
        self._document: QTextDocument | None = None

    def _get_document(self) -> QQuickTextDocument | None:
        return self._quick_document

    def _set_document(self, document: QQuickTextDocument | None) -> None:
        if self._quick_document is document:
            return
        if self._document is not None:
            try:
                self._document.contentsChanged.disconnect(self.layoutChanged)
            except (RuntimeError, TypeError):
                pass

        self._quick_document = document
        self._document = document.textDocument() if document is not None else None
        if self._document is not None:
            self._document.contentsChanged.connect(self.layoutChanged)
        self.documentChanged.emit()
        self.layoutChanged.emit()

    document = Property(QQuickTextDocument, _get_document, _set_document, notify=documentChanged)

    @Property(int, notify=layoutChanged)
    def lineCount(self) -> int:
        return self._document.blockCount() if self._document is not None else 0

    @Property(int, notify=layoutChanged)
    def characterCount(self) -> int:
        return self._document.characterCount() if self._document is not None else 0

    @Slot(float, float, result="QVariantList")
    def linesIn(self, top: float, bottom: float) -> list[dict]:
        """Blocks intersecting the vertical range ``[top, bottom]``."""
        if self._document is None:
            return []
        layout = self._document.documentLayout()
        if layout is None:
            return []

        # hitTest jumps straight to the first visible block instead of walking
        # the whole document, which keeps scrolling cheap in large files.
        block = self._document.firstBlock()
        if top > 0:
            hit = layout.hitTest(QPointF(0.0, top), Qt.HitTestAccuracy.FuzzyHit)
            if hit >= 0:
                candidate = self._document.findBlock(hit)
                if candidate.isValid():
                    block = candidate
                    previous = block.previous()
                    if previous.isValid() and layout.blockBoundingRect(previous).bottom() >= top:
                        block = previous

        result: list[dict] = []
        while block.isValid():
            rect = layout.blockBoundingRect(block)
            if rect.top() > bottom:
                break
            if rect.bottom() >= top and block.isVisible():
                block_layout = block.layout()
                result.append(
                    {
                        "number": block.blockNumber() + 1,
                        "y": rect.y(),
                        "height": rect.height(),
                        "wrapped": block_layout.lineCount() > 1 if block_layout else False,
                    }
                )
            block = block.next()
        return result

    @Slot(int, result="QVariantMap")
    def cursorInfo(self, position: int) -> dict:
        """1-based line/column for a character offset, plus the line's text."""
        if self._document is None:
            return {"line": 1, "column": 1, "lineText": "", "lineStart": 0, "lineEnd": 0}
        block = self._document.findBlock(max(0, position))
        if not block.isValid():
            return {"line": 1, "column": 1, "lineText": "", "lineStart": 0, "lineEnd": 0}
        start = block.position()
        text = block.text()
        return {
            "line": block.blockNumber() + 1,
            "column": position - start + 1,
            "lineText": text,
            "lineStart": start,
            "lineEnd": start + len(text),
        }

    @Slot(int, result=int)
    def positionForLine(self, line: int) -> int:
        """Character offset of the start of a 1-based line number."""
        if self._document is None:
            return 0
        block = self._document.findBlockByNumber(max(0, line - 1))
        if not block.isValid():
            return max(0, self._document.characterCount() - 1)
        return block.position()

    @Slot(int, result=int)
    def lineEndPosition(self, line: int) -> int:
        if self._document is None:
            return 0
        block = self._document.findBlockByNumber(max(0, line - 1))
        if not block.isValid():
            return max(0, self._document.characterCount() - 1)
        return block.position() + len(block.text())

    @Slot(int, result="QVariantMap")
    def matchingBracket(self, position: int) -> dict:
        """Find the bracket paired with the one next to *position*."""
        if self._document is None:
            return {"found": False}
        text = self._document.toPlainText()
        pairs = {"(": ")", "[": "]", "{": "}"}
        reverse = {v: k for k, v in pairs.items()}

        for index in (position, position - 1):
            if not 0 <= index < len(text):
                continue
            char = text[index]
            if char in pairs:
                depth = 0
                for scan in range(index, len(text)):
                    if text[scan] == char:
                        depth += 1
                    elif text[scan] == pairs[char]:
                        depth -= 1
                        if depth == 0:
                            return {"found": True, "from": index, "to": scan}
                return {"found": False}
            if char in reverse:
                depth = 0
                for scan in range(index, -1, -1):
                    if text[scan] == char:
                        depth += 1
                    elif text[scan] == reverse[char]:
                        depth -= 1
                        if depth == 0:
                            return {"found": True, "from": index, "to": scan}
                return {"found": False}
        return {"found": False}

    @Slot()
    def notifyLayoutChanged(self) -> None:
        self.layoutChanged.emit()

    @Slot(int, int, str, result=bool)
    def replaceRange(self, start: int, end: int, text: str) -> bool:
        """Replace ``[start, end)`` as a single undoable edit.

        Going through ``QTextCursor`` with an edit block means one Ctrl+Z undoes
        the whole command, unlike separate TextArea remove/insert calls.
        """
        if self._document is None:
            return False
        limit = max(0, self._document.characterCount() - 1)
        start = max(0, min(start, limit))
        end = max(start, min(end, limit))

        cursor = QTextCursor(self._document)
        cursor.beginEditBlock()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(text)
        cursor.endEditBlock()
        return True

    @Slot("QVariantList", result=bool)
    def replaceMany(self, spans: list) -> bool:
        """Apply several ``{start, end, text}`` spans as one undoable edit.

        Spans must be ordered last-to-first so earlier offsets stay valid.
        """
        if self._document is None or not spans:
            return False
        cursor = QTextCursor(self._document)
        cursor.beginEditBlock()
        for span in spans:
            cursor.setPosition(int(span["start"]))
            cursor.setPosition(int(span["end"]), QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(str(span["text"]))
        cursor.endEditBlock()
        return True

