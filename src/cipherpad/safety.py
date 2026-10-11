"""Portable ordinary-buffer recovery and ownership-aware clipboard expiry."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLockFile, QMimeData, QObject, QStandardPaths, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QmlElement

from .document import ENCODINGS, LINE_ENDINGS, Document, DocumentManager

QML_IMPORT_NAME = "Cipherpad"
QML_IMPORT_MAJOR_VERSION = 1
MAX_SNAPSHOT_BYTES = 8_000_000
CLIPBOARD_TAG = "application/x-cipherpad-sensitive"
_ID = re.compile(r"[0-9a-f]{32}")


@QmlElement
class SafetyTools(QObject):
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None, *, directory: Path | None = None) -> None:
        super().__init__(parent)
        self._root = directory or Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / "recovery"
        self._session = uuid.uuid4().hex
        self._lock: QLockFile | None = None
        self._snapshots: dict[str, bytes] = {}
        self._bound: set[str] = set()
        self._token = b""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.expireClipboard)
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.dataChanged.connect(self._clipboard_changed)
        application = QCoreApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self.finish)

    @Slot(str, bool, int, result=bool)
    def copyText(self, text: str, sensitive: bool, seconds: int) -> bool:
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            self.errorOccurred.emit("The system clipboard is unavailable.")
            return False
        self._timer.stop()
        self._token = uuid.uuid4().bytes if sensitive and seconds > 0 else b""
        mime = QMimeData()
        mime.setText(text)
        if self._token:
            mime.setData(CLIPBOARD_TAG, self._token)
        clipboard.setMimeData(mime)
        current = clipboard.mimeData()
        if current is None or current.text() != text:
            self._token = b""
            self.errorOccurred.emit("Could not update the system clipboard.")
            return False
        if self._token:
            self._timer.start(min(seconds, 3600) * 1000)
        return True

    def _owns_clipboard(self) -> bool:
        clipboard = QGuiApplication.clipboard()
        mime = clipboard.mimeData() if clipboard is not None else None
        return bool(self._token and mime is not None and bytes(mime.data(CLIPBOARD_TAG)) == self._token)

    def _clipboard_changed(self) -> None:
        if not self._owns_clipboard():
            self._timer.stop()
            self._token = b""

    @Slot()
    def expireClipboard(self) -> None:
        self._timer.stop()
        if self._owns_clipboard():
            QGuiApplication.clipboard().clear()
        self._token = b""

    def _session_directory(self) -> Path:
        return self._root / self._session

    def _ensure_session(self) -> None:
        if self._lock is not None:
            return
        directory = self._session_directory()
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock = QLockFile(str(directory / "session.lock"))
        lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            raise OSError("Could not acquire the recovery session lock.")
        self._lock = lock

    @Slot(QObject, str, bool, result=bool)
    def snapshot(self, document: QObject, text: str, enabled: bool) -> bool:
        if not isinstance(document, Document):
            self.errorOccurred.emit("Recovery requires an open document.")
            return False
        key = document.recoveryId
        if key not in self._bound:
            self._bound.add(key)
            document.saved.connect(lambda: self.forget(key))
            document.closed.connect(lambda: self.forget(key))
            document.encryptedChanged.connect(lambda: self.forget(key))
        if not enabled or document.encrypted or document.locked or not document.modified:
            return self.forget(key)
        payload = json.dumps({
            "version": 1, "title": document.displayName, "path": document.filePath,
            "text": text, "language": document.language, "encoding": document.encoding,
            "lineEnding": document.lineEnding,
        }, ensure_ascii=True).encode("utf-8")
        if len(payload) > MAX_SNAPSHOT_BYTES:
            self.errorOccurred.emit(f"Recovery for {document.displayName} exceeds the 8 MB snapshot limit.")
            return False
        digest = hashlib.sha256(payload).digest()
        if self._snapshots.get(key) == digest:
            return True
        try:
            self._ensure_session()
            Document._atomic_write(str(self._session_directory() / (key + ".json")), payload)
        except OSError as exc:
            self.errorOccurred.emit(f"Could not write recovery snapshot: {exc}")
            return False
        self._snapshots[key] = digest
        return True

    def forget(self, key: str) -> bool:
        try:
            (self._session_directory() / (key + ".json")).unlink(missing_ok=True)
        except OSError as exc:
            self.errorOccurred.emit(f"Could not remove recovery snapshot: {exc}")
            return False
        self._snapshots.pop(key, None)
        return True

    def _read(self, path: Path) -> dict:
        if path.is_symlink():
            raise ValueError("Recovery snapshots must not be symbolic links.")
        with path.open("rb") as stream:
            raw = stream.read(MAX_SNAPSHOT_BYTES + 1)
        if len(raw) > MAX_SNAPSHOT_BYTES:
            raise ValueError("Recovery snapshot exceeds 8 MB.")
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get("version") != 1 or any(
            not isinstance(payload.get(key), str)
            for key in ("text", "title", "path", "language", "encoding", "lineEnding")
        ):
            raise ValueError("Invalid recovery snapshot format.")
        if payload["encoding"] not in ENCODINGS or payload["lineEnding"] not in LINE_ENDINGS:
            raise ValueError("Invalid recovery encoding or line ending.")
        return payload

    @Slot(result="QVariantList")
    def availableRecovery(self) -> list[dict]:
        entries = []
        if not self._root.exists():
            return entries
        try:
            for directory in sorted(self._root.iterdir()):
                if not _ID.fullmatch(directory.name) or directory.name == self._session or not directory.is_dir() or directory.is_symlink():
                    continue
                lock = QLockFile(str(directory / "session.lock"))
                lock.setStaleLockTime(0)
                if not lock.tryLock(0):
                    continue
                try:
                    for path in sorted(directory.glob("*.json")):
                        if not _ID.fullmatch(path.stem):
                            continue
                        entry = {"id": directory.name + ":" + path.stem}
                        try:
                            payload = self._read(path)
                            entry.update(title=payload["title"], path=payload["path"], error="")
                        except (OSError, ValueError, UnicodeError, RecursionError) as exc:
                            entry.update(title="Unreadable snapshot", path="", error=str(exc))
                        entries.append(entry)
                finally:
                    lock.unlock()
        except OSError as exc:
            self.errorOccurred.emit(f"Could not list recovery snapshots: {exc}")
        return entries

    @Slot(str, QObject, bool, result=bool)
    def resolveRecovery(self, identifier: str, manager: QObject, restore: bool) -> bool:
        parts = identifier.split(":")
        if len(parts) != 2 or not all(_ID.fullmatch(part) for part in parts) or parts[0] == self._session:
            self.errorOccurred.emit("Invalid recovery snapshot identifier.")
            return False
        directory = self._root / parts[0]
        if directory.is_symlink() or not directory.is_dir():
            self.errorOccurred.emit("Recovery session is missing or invalid.")
            return False
        lock = QLockFile(str(directory / "session.lock"))
        lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            self.errorOccurred.emit("This recovery session is in use by another application.")
            return False
        try:
            path = directory / (parts[1] + ".json")
            if restore:
                if not isinstance(manager, DocumentManager):
                    raise ValueError("Recovery requires a document manager.")
                payload = self._read(path)
                index = manager.newRecovered(payload["text"], payload["title"], payload["language"],
                                             payload["encoding"], payload["lineEnding"])
                document = manager.documentAt(index)
                if document is None or not self.snapshot(document, payload["text"], True):
                    raise OSError("Could not protect the restored buffer with a new recovery snapshot.")
            path.unlink()
        except (OSError, ValueError, UnicodeError, RecursionError) as exc:
            self.errorOccurred.emit(f"Could not {'restore' if restore else 'discard'} snapshot: {exc}")
            return False
        finally:
            lock.unlock()
        return True

    @Slot()
    def finish(self) -> None:
        self.expireClipboard()
        for key in list(self._snapshots):
            self.forget(key)
        if self._lock is not None:
            self._lock.unlock()
            self._lock = None
            try:
                directory = self._session_directory()
                if not any(directory.iterdir()):
                    directory.rmdir()
            except OSError as exc:
                self.errorOccurred.emit(f"Could not clean up the recovery session: {exc}")
