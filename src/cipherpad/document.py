"""Document backing store: encoding, line endings, encryption and file IO."""

from __future__ import annotations

import os
import tempfile
from typing import Final

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QFileSystemWatcher,
    QModelIndex,
    QObject,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtQml import QmlElement, QmlUncreatable

from . import crypto
from .languages import detect_language, language_names

QML_IMPORT_NAME = "Cipherpad"
QML_IMPORT_MAJOR_VERSION = 1

BOMS: Final = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)

ENCODINGS: Final = (
    "utf-8",
    "utf-8-sig",
    "utf-16-le",
    "utf-16-be",
    "utf-32-le",
    "utf-32-be",
    "cp1252",
    "latin-1",
    "ascii",
    "cp437",
    "shift_jis",
    "gb18030",
    "koi8-r",
)

LINE_ENDINGS: Final = {"lf": "\n", "crlf": "\r\n", "cr": "\r"}

_BINARY_SNIFF_BYTES: Final = 8000


def detect_encoding(data: bytes, fallback: str = "utf-8") -> str:
    for bom, encoding in BOMS:
        if data.startswith(bom):
            return encoding
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return "cp1252" if fallback == "utf-8" else fallback
    return "utf-8"


def detect_line_ending(text: str, fallback: str = "lf") -> str:
    crlf = text.count("\r\n")
    cr = text.count("\r") - crlf
    lf = text.count("\n") - crlf
    if crlf == cr == lf == 0:
        return fallback
    if crlf >= lf and crlf >= cr:
        return "crlf"
    return "lf" if lf >= cr else "cr"


def looks_binary(data: bytes) -> bool:
    return b"\x00" in data[:_BINARY_SNIFF_BYTES]


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


@QmlElement
@QmlUncreatable("Documents are created by DocumentManager")
class Document(QObject):
    """A single open file (or unsaved buffer)."""

    filePathChanged = Signal()
    modifiedChanged = Signal()
    encryptedChanged = Signal()
    encodingChanged = Signal()
    lineEndingChanged = Signal()
    languageChanged = Signal()
    readOnlyChanged = Signal()

    contentLoaded = Signal(str)
    errorOccurred = Signal(str)
    saved = Signal()
    passphraseRequired = Signal()
    externallyChanged = Signal()

    def __init__(self, title: str = "Untitled", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._file_path = ""
        self._fallback_title = title
        self._modified = False
        self._encrypted = False
        self._passphrase = ""
        self._encoding = "utf-8"
        self._line_ending = "lf"
        self._language = "plain"
        self._read_only = False
        self._loaded_text = ""
        self._watcher: QFileSystemWatcher | None = None
        self._suppress_watch = False

    # -------------------------------------------------------- properties
    @Property(str, notify=filePathChanged)
    def filePath(self) -> str:
        return self._file_path

    @Property(str, notify=filePathChanged)
    def fileName(self) -> str:
        return os.path.basename(self._file_path) if self._file_path else self._fallback_title

    @Property(str, notify=filePathChanged)
    def directory(self) -> str:
        return os.path.dirname(self._file_path) if self._file_path else ""

    @Property(bool, notify=filePathChanged)
    def isUntitled(self) -> bool:
        return not self._file_path

    @Property(bool, notify=modifiedChanged)
    def modified(self) -> bool:
        return self._modified

    @modified.setter
    def modified(self, value: bool) -> None:
        value = bool(value)
        if self._modified == value:
            return
        self._modified = value
        self.modifiedChanged.emit()

    @Property(bool, notify=encryptedChanged)
    def encrypted(self) -> bool:
        return self._encrypted

    @Property(bool, notify=encryptedChanged)
    def hasPassphrase(self) -> bool:
        return bool(self._passphrase)

    @Property(str, notify=encodingChanged)
    def encoding(self) -> str:
        return self._encoding

    @encoding.setter
    def encoding(self, value: str) -> None:
        if value not in ENCODINGS or self._encoding == value:
            return
        self._encoding = value
        self.encodingChanged.emit()
        self.modified = True

    @Property(str, notify=lineEndingChanged)
    def lineEnding(self) -> str:
        return self._line_ending

    @lineEnding.setter
    def lineEnding(self, value: str) -> None:
        if value not in LINE_ENDINGS or self._line_ending == value:
            return
        self._line_ending = value
        self.lineEndingChanged.emit()
        self.modified = True

    @Property(str, notify=languageChanged)
    def language(self) -> str:
        return self._language

    @language.setter
    def language(self, value: str) -> None:
        if self._language == value:
            return
        self._language = value
        self.languageChanged.emit()

    @Property(bool, notify=readOnlyChanged)
    def readOnly(self) -> bool:
        return self._read_only

    @Property(str, notify=filePathChanged)
    def displayName(self) -> str:
        return self.fileName

    @Property("QStringList", constant=True)
    def availableEncodings(self) -> list[str]:
        return list(ENCODINGS)

    @Property("QVariantList", constant=True)
    def availableLanguages(self) -> list[dict]:
        return [{"id": lid, "name": name} for lid, name in language_names()]

    # ------------------------------------------------------------- slots
    @Slot(str, result=bool)
    @Slot(str, str, result=bool)
    def load(self, path: str, passphrase: str = "") -> bool:
        """Read *path* into the buffer, decrypting when required."""
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
        except OSError as exc:
            self.errorOccurred.emit(f"Could not open {path}:\n{exc.strerror or exc}")
            return False

        encrypted = crypto.is_encrypted(raw)
        if encrypted:
            if not passphrase:
                self.passphraseRequired.emit()
                return False
            try:
                raw = crypto.decrypt(raw, passphrase)
            except crypto.CryptoError as exc:
                self.errorOccurred.emit(str(exc))
                return False

        if looks_binary(raw):
            self.errorOccurred.emit(
                f"{os.path.basename(path)} looks like a binary file and cannot be edited safely."
            )
            return False

        encoding = "utf-8" if encrypted else detect_encoding(raw, self._encoding)
        try:
            text = raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            encoding = "latin-1"
            text = raw.decode(encoding, errors="replace")

        self._line_ending = detect_line_ending(text, self._line_ending)
        self._encoding = encoding
        self._encrypted = encrypted
        self._passphrase = passphrase if encrypted else ""
        self._loaded_text = normalize_newlines(text)
        self._read_only = os.path.exists(path) and not os.access(path, os.W_OK)
        self._set_path(path)
        self.modified = False

        self.encodingChanged.emit()
        self.lineEndingChanged.emit()
        self.encryptedChanged.emit()
        self.readOnlyChanged.emit()
        self.language = detect_language(path, self._loaded_text[:512])
        self.contentLoaded.emit(self._loaded_text)
        self._watch(path)
        return True

    @Slot(result=str)
    def takeContent(self) -> str:
        """Return the text produced by the most recent successful load.

        ``contentLoaded`` fires while the document is still being created, i.e.
        before its editor pane exists, so newly created panes pull the buffered
        text from here when they are completed.
        """
        return self._loaded_text

    @Slot(str, result=bool)
    def save(self, text: str) -> bool:
        if not self._file_path:
            self.errorOccurred.emit("This document has no file name yet. Use Save As.")
            return False
        return self._write(self._file_path, text, self._encrypted, self._passphrase)

    @Slot(str, str, result=bool)
    @Slot(str, str, bool, str, result=bool)
    def saveAs(self, path: str, text: str, encrypt: bool = False, passphrase: str = "") -> bool:
        if encrypt and not passphrase:
            self.errorOccurred.emit("A passphrase is required to save an encrypted file.")
            return False
        if not self._write(path, text, encrypt, passphrase):
            return False

        self._encrypted = encrypt
        self._passphrase = passphrase if encrypt else ""
        self._read_only = False
        self._set_path(path)
        self.encryptedChanged.emit()
        self.readOnlyChanged.emit()
        self.language = detect_language(path, text[:512])
        self._watch(path)
        return True

    @Slot(str, str, result=bool)
    def encryptWith(self, text: str, passphrase: str) -> bool:
        """Turn an existing document into an encrypted one."""
        if not passphrase:
            self.errorOccurred.emit("A passphrase is required to encrypt this file.")
            return False
        if not self._file_path:
            self.errorOccurred.emit("Save the file before encrypting it.")
            return False
        if not self._write(self._file_path, text, True, passphrase):
            return False
        self._encrypted = True
        self._passphrase = passphrase
        self.encryptedChanged.emit()
        return True

    @Slot(str, result=bool)
    def removeEncryption(self, text: str) -> bool:
        if not self._encrypted:
            return True
        if self._file_path and not self._write(self._file_path, text, False, ""):
            return False
        self._encrypted = False
        self._passphrase = ""
        self.encryptedChanged.emit()
        if not self._file_path:
            self.modified = True
        return True

    @Slot(str, str, result=bool)
    def changePassphrase(self, text: str, passphrase: str) -> bool:
        """Re-encrypt the current document using a new passphrase."""
        if not passphrase:
            self.errorOccurred.emit("A passphrase is required.")
            return False
        if not self._encrypted:
            self.errorOccurred.emit("Only encrypted files have a passphrase to change.")
            return False
        if self._file_path and not self._write(self._file_path, text, True, passphrase):
            return False
        self._passphrase = passphrase
        return True

    @Slot(str, result=bool)
    def verifyPassphrase(self, passphrase: str) -> bool:
        return crypto.constant_time_equals(self._passphrase, passphrase)

    @Slot(result=bool)
    def reload(self) -> bool:
        if not self._file_path:
            return False
        return self.load(self._file_path, self._passphrase)

    @Slot(str)
    def setPassphrase(self, passphrase: str) -> None:
        self._passphrase = passphrase

    @Slot(str, result="QVariantMap")
    def passphraseStrength(self, passphrase: str) -> dict:
        score, label = crypto.passphrase_strength(passphrase)
        return {"score": score, "label": label}

    @Slot(str)
    def setLanguageFromContent(self, sample: str) -> None:
        self.language = detect_language(self._file_path, sample[:512])

    @Slot()
    def close(self) -> None:
        self._unwatch()
        self._passphrase = ""

    # ------------------------------------------------------------ helpers
    def _write(self, path: str, text: str, encrypt: bool, passphrase: str) -> bool:
        newline = LINE_ENDINGS.get(self._line_ending, "\n")
        payload = normalize_newlines(text).replace("\n", newline)

        encoding = "utf-8" if encrypt else self._encoding
        try:
            data = payload.encode(encoding)
        except (UnicodeEncodeError, LookupError) as exc:
            self.errorOccurred.emit(
                f"Text cannot be written as {encoding}: {exc}\nTry switching the encoding to UTF-8."
            )
            return False

        if encrypt:
            try:
                data = crypto.encrypt(data, passphrase)
            except crypto.CryptoError as exc:
                self.errorOccurred.emit(str(exc))
                return False

        self._suppress_watch = True
        try:
            self._atomic_write(path, data)
        except OSError as exc:
            self.errorOccurred.emit(f"Could not save {path}:\n{exc.strerror or exc}")
            return False
        finally:
            self._suppress_watch = False

        self._loaded_text = normalize_newlines(text)
        self.modified = False
        self.saved.emit()
        return True

    @staticmethod
    def _atomic_write(path: str, data: bytes) -> None:
        """Write via a sibling temp file so a failure never truncates the original."""
        directory = os.path.dirname(os.path.abspath(path)) or "."
        os.makedirs(directory, exist_ok=True)
        handle, temp_path = tempfile.mkstemp(dir=directory, prefix=".cipherpad-", suffix=".tmp")
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, path)
        except BaseException:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def _set_path(self, path: str) -> None:
        path = os.path.abspath(path)
        if self._file_path == path:
            return
        self._file_path = path
        self.filePathChanged.emit()

    def _watch(self, path: str) -> None:
        self._unwatch()
        self._watcher = QFileSystemWatcher([path], self)
        self._watcher.fileChanged.connect(self._on_file_changed)

    def _unwatch(self) -> None:
        if self._watcher is not None:
            self._watcher.deleteLater()
            self._watcher = None

    def _on_file_changed(self, _path: str) -> None:
        if self._suppress_watch:
            return
        self.externallyChanged.emit()


@QmlElement
class DocumentManager(QAbstractListModel):
    """List model of open documents, one per editor tab."""

    DocumentRole = Qt.ItemDataRole.UserRole + 1
    TitleRole = Qt.ItemDataRole.UserRole + 2
    ModifiedRole = Qt.ItemDataRole.UserRole + 3
    PathRole = Qt.ItemDataRole.UserRole + 4
    EncryptedRole = Qt.ItemDataRole.UserRole + 5

    countChanged = Signal()
    currentIndexChanged = Signal()
    documentAdded = Signal(int)
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._documents: list[Document] = []
        self._current_index = -1
        self._untitled_counter = 0

    # ------------------------------------------------------- model plumbing
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._documents)

    def roleNames(self) -> dict:  # noqa: N802
        return {
            self.DocumentRole: QByteArray(b"document"),
            self.TitleRole: QByteArray(b"title"),
            self.ModifiedRole: QByteArray(b"modified"),
            self.PathRole: QByteArray(b"path"),
            self.EncryptedRole: QByteArray(b"encrypted"),
        }

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._documents):
            return None
        document = self._documents[index.row()]
        match role:
            case self.DocumentRole:
                return document
            case self.TitleRole | Qt.ItemDataRole.DisplayRole:
                return document.fileName
            case self.ModifiedRole:
                return document.modified
            case self.PathRole:
                return document.filePath
            case self.EncryptedRole:
                return document.encrypted
        return None

    # ------------------------------------------------------------ properties
    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._documents)

    @Property(int, notify=currentIndexChanged)
    def currentIndex(self) -> int:
        return self._current_index

    @currentIndex.setter
    def currentIndex(self, value: int) -> None:
        value = max(-1, min(int(value), len(self._documents) - 1))
        if self._current_index == value:
            return
        self._current_index = value
        self.currentIndexChanged.emit()

    @Property(Document, notify=currentIndexChanged)
    def currentDocument(self) -> Document | None:
        if 0 <= self._current_index < len(self._documents):
            return self._documents[self._current_index]
        return None

    @Property(bool, notify=countChanged)
    def hasModifiedDocuments(self) -> bool:
        return any(document.modified for document in self._documents)

    # ---------------------------------------------------------------- slots
    @Slot(result=int)
    def newDocument(self) -> int:
        self._untitled_counter += 1
        document = Document(f"Untitled-{self._untitled_counter}", self)
        return self._append(document)

    @Slot(str, result=int)
    @Slot(str, str, result=int)
    def openFile(self, path: str, passphrase: str = "") -> int:
        """Open *path*, focusing an existing tab when already open.

        Returns the tab index, or -1 on failure / -2 when a passphrase is needed.
        """
        path = os.path.abspath(path)
        existing = self.indexOfPath(path)
        if existing >= 0:
            self.currentIndex = existing
            return existing

        document = Document(os.path.basename(path), self)
        document.errorOccurred.connect(self.errorOccurred)

        needs_passphrase = False

        def _on_passphrase_required() -> None:
            nonlocal needs_passphrase
            needs_passphrase = True

        document.passphraseRequired.connect(_on_passphrase_required)
        loaded = document.load(path, passphrase)
        document.passphraseRequired.disconnect(_on_passphrase_required)

        if not loaded:
            document.deleteLater()
            return -2 if needs_passphrase else -1
        return self._append(document)

    @Slot(str, result=bool)
    def requiresPassphrase(self, path: str) -> bool:
        try:
            with open(path, "rb") as handle:
                return crypto.is_encrypted(handle.read(len(crypto.MAGIC)))
        except OSError:
            return False

    @Slot(int, result=Document)
    def documentAt(self, index: int) -> Document | None:
        if 0 <= index < len(self._documents):
            return self._documents[index]
        return None

    @Slot(str, result=int)
    def indexOfPath(self, path: str) -> int:
        target = os.path.normcase(os.path.abspath(path))
        for index, document in enumerate(self._documents):
            if document.filePath and os.path.normcase(document.filePath) == target:
                return index
        return -1

    @Slot(QObject, result=int)
    def indexOf(self, document: QObject) -> int:
        try:
            return self._documents.index(document)  # type: ignore[arg-type]
        except ValueError:
            return -1

    @Slot(int, result=bool)
    def closeDocument(self, index: int) -> bool:
        if not 0 <= index < len(self._documents):
            return False
        current_index = self._current_index
        self.beginRemoveRows(QModelIndex(), index, index)
        document = self._documents.pop(index)
        self.endRemoveRows()
        document.close()
        document.deleteLater()

        self.countChanged.emit()
        if current_index > index:
            new_index = current_index - 1
        elif current_index == index:
            new_index = min(index, len(self._documents) - 1)
        else:
            new_index = current_index
        self._current_index = -1 if not self._documents else new_index
        self.currentIndexChanged.emit()
        return True

    @Slot()
    def closeAll(self) -> None:
        if not self._documents:
            return
        self.beginResetModel()
        for document in self._documents:
            document.close()
            document.deleteLater()
        self._documents.clear()
        self.endResetModel()
        self._current_index = -1
        self.countChanged.emit()
        self.currentIndexChanged.emit()

    @Slot(int)
    def refresh(self, index: int) -> None:
        """Tell the view that a document's title/flags changed."""
        if 0 <= index < len(self._documents):
            model_index = self.index(index, 0)
            self.dataChanged.emit(model_index, model_index)

    @Slot(result="QStringList")
    def openPaths(self) -> list[str]:
        return [d.filePath for d in self._documents if d.filePath and not d.encrypted]

    @Slot("QStringList", result=int)
    def openMany(self, paths: list[str]) -> int:
        """Open several files, skipping ones that fail or need a passphrase."""
        opened = 0
        for path in paths:
            if self.openFile(path) >= 0:
                opened += 1
        return opened

    # -------------------------------------------------------------- helpers
    def _append(self, document: Document) -> int:
        index = len(self._documents)
        self.beginInsertRows(QModelIndex(), index, index)
        self._documents.append(document)
        self.endInsertRows()

        document.modifiedChanged.connect(lambda: self.refresh(self.indexOf(document)))
        document.filePathChanged.connect(lambda: self.refresh(self.indexOf(document)))
        document.encryptedChanged.connect(lambda: self.refresh(self.indexOf(document)))

        self.countChanged.emit()
        self._current_index = index
        self.currentIndexChanged.emit()
        self.documentAdded.emit(index)
        return index
