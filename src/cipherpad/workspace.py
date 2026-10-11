"""Cancellable workspace discovery and text search, away from the GUI thread."""

from __future__ import annotations

import codecs
import hashlib
import fnmatch
import os
import re
from threading import Event

from PySide6.QtCore import QObject, Property, QThread, Signal, Slot

from .crypto import MAGIC
from .document import detect_encoding, looks_binary, normalize_newlines
from .explorer import ProjectExplorer, is_ignored_path

MAX_ENTRIES = 20_000
MAX_MATCHES = 1_000
MAX_FILE_BYTES = 2 * 1024 * 1024


def discover_entries(
    roots: list[str], show_hidden: bool, ignores: str, cancelled: Event, limit: int = MAX_ENTRIES,
) -> dict:
    entries: list[dict] = []
    errors: list[str] = []
    seen: set[str] = set()
    skipped = 0
    pending = [(root, root) for root in reversed(roots)]
    while pending and not cancelled.is_set():
        directory, root = pending.pop()
        identity = os.path.normcase(os.path.abspath(directory))
        if identity in seen:
            continue
        seen.add(identity)
        try:
            children: list[os.DirEntry] = []
            with os.scandir(directory) as iterator:
                for child in iterator:
                    if cancelled.is_set():
                        break
                    if is_ignored_path(os.path.relpath(child.path, root), show_hidden, ignores):
                        continue
                    if child.is_symlink() or os.path.isjunction(child.path):
                        skipped += 1
                        continue
                    children.append(child)
                    if len(children) > limit - len(entries):
                        break
            children.sort(key=lambda item: (not item.is_dir(follow_symlinks=False), item.name.lower()))
            for child in children:
                if cancelled.is_set():
                    break
                relative = os.path.relpath(child.path, root)
                if len(entries) >= limit:
                    return {"entries": entries, "errors": errors, "skipped": skipped, "limited": True}
                is_dir = child.is_dir(follow_symlinks=False)
                entries.append({
                    "path": os.path.normpath(child.path), "relative": relative,
                    "label": os.path.basename(root) + os.sep + relative, "isDir": is_dir,
                })
                if is_dir:
                    pending.append((child.path, root))
        except OSError as exc:
            errors.append(f"{directory}: {exc}")
    return {"entries": entries, "errors": errors, "skipped": skipped, "limited": False}


def fuzzy_files(entries: list[dict], query: str, limit: int = 100) -> list[dict]:
    needle = query.strip().casefold()
    ranked: list[tuple[int, str, dict]] = []
    for entry in entries:
        if entry["isDir"]:
            continue
        name = os.path.basename(entry["path"]).casefold()
        path = entry["relative"].casefold()
        if not needle:
            score = 0
        elif name == needle:
            score = -300
        elif needle in name:
            score = -200 + name.index(needle)
        elif needle in path:
            score = -100 + path.index(needle)
        else:
            position = -1
            score = 0
            for char in needle:
                found = path.find(char, position + 1)
                if found < 0:
                    break
                score += found - position - 1
                position = found
            else:
                ranked.append((score, path, entry))
                continue
            continue
        ranked.append((score, path, entry))
    ranked.sort(key=lambda item: (item[0], len(item[1]), item[1]))
    return [entry for _, _, entry in ranked[:limit]]


def search_entries(
    entries: list[dict], needle: str, masks: str, case_sensitive: bool,
    whole_word: bool, cancelled: Event, limit: int = MAX_MATCHES,
) -> dict:
    matches: list[dict] = []
    errors: list[str] = []
    skipped = 0
    expression = re.escape(needle)
    if whole_word:
        expression = rf"\b{expression}\b"
    pattern = re.compile(expression, 0 if case_sensitive else re.IGNORECASE)
    filters = [mask.strip().replace("\\", "/").casefold() for mask in re.split("[;,]", masks) if mask.strip()]
    if not needle:
        return {"matches": [], "errors": [], "skipped": 0, "limited": False}
    for entry in entries:
        if cancelled.is_set():
            break
        if entry["isDir"]:
            continue
        path = entry["path"]
        relative = entry["relative"].replace("\\", "/").casefold()
        if filters and not any(
            fnmatch.fnmatchcase(relative, mask) or fnmatch.fnmatchcase(os.path.basename(path).casefold(), mask)
            for mask in filters
        ):
            continue
        try:
            if os.path.islink(path) or os.path.isjunction(path):
                skipped += 1
                continue
            if os.path.splitext(path)[1].lower() in (".enc", ".aes"):
                skipped += 1
                continue
            with open(path, "rb") as stream:
                data = stream.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES or data.startswith(MAGIC):
                skipped += 1
                continue
            encoding = detect_encoding(data)
            wide = data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE, codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE))
            if looks_binary(data) and not wide:
                skipped += 1
                continue
            text = normalize_newlines(data.decode(encoding))
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            for line_number, line in enumerate(text.split("\n"), 1):
                if cancelled.is_set():
                    break
                for match in pattern.finditer(line):
                    if cancelled.is_set():
                        break
                    if len(matches) >= limit:
                        return {"matches": matches, "errors": errors, "skipped": skipped, "limited": True}
                    matches.append({
                        "path": path, "label": entry["label"], "line": line_number,
                        "column": len(line[:match.start()].encode("utf-16-le")) // 2 + 1,
                        "length": len(match.group().encode("utf-16-le")) // 2,
                        "digest": digest,
                        "preview": line[max(0, match.start() - 80):match.end() + 160],
                    })
        except (OSError, UnicodeError) as exc:
            errors.append(f"{path}: {exc}")
    return {"matches": matches, "errors": errors, "skipped": skipped, "limited": False}


class _WorkspaceJob(QThread):
    def __init__(self, roots: list[str], show_hidden: bool, ignores: str, search: tuple | None) -> None:
        super().__init__()
        self.roots = roots
        self.show_hidden = show_hidden
        self.ignores = ignores
        self.search = search
        self.cancelled = Event()
        self.report: dict = {}

    def run(self) -> None:
        self.report = discover_entries(self.roots, self.show_hidden, self.ignores, self.cancelled)
        if self.search is not None and not self.cancelled.is_set():
            found = search_entries(self.report["entries"], *self.search, self.cancelled)
            self.report["matches"] = found["matches"]
            self.report["errors"].extend(found["errors"])
            self.report["skipped"] += found["skipped"]
            self.report["limited"] |= found["limited"]


class WorkspaceTools(QObject):
    busyChanged = Signal()
    entriesChanged = Signal()
    matchesChanged = Signal()
    statusChanged = Signal()
    errorOccurred = Signal(str)

    def __init__(self, explorer: ProjectExplorer, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._explorer = explorer
        self._entries: list[dict] = []
        self._matches: list[dict] = []
        self._status = ""
        self._job: _WorkspaceJob | None = None
        explorer.rootFoldersChanged.connect(self.invalidate)
        explorer.optionsChanged.connect(self.invalidate)

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._job is not None

    @Property("QVariantList", notify=matchesChanged)
    def matches(self) -> list[dict]:
        return self._matches

    @Property(int, notify=entriesChanged)
    def fileCount(self) -> int:
        return sum(not entry["isDir"] for entry in self._entries)

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Slot()
    def invalidate(self) -> None:
        self.cancel()
        self._entries = []
        self._matches = []
        self.entriesChanged.emit()
        self.matchesChanged.emit()

    @Slot()
    def scanFiles(self) -> None:
        self._start(None)

    @Slot(str, str, bool, bool)
    def search(self, needle: str, masks: str, case_sensitive: bool, whole_word: bool) -> None:
        if not needle:
            self.errorOccurred.emit("Enter text to search for.")
            return
        self._start((needle, masks, case_sensitive, whole_word))

    def _start(self, search: tuple | None) -> None:
        if self.busy:
            self.errorOccurred.emit("A workspace scan is already running. Cancel it or wait for it to finish.")
            return
        if not self._explorer.rootFolders:
            self.errorOccurred.emit("Add a folder to Explorer first.")
            return
        self._matches = []
        self.matchesChanged.emit()
        self._status = "Searching files on disk..." if search else "Scanning workspace..."
        self.statusChanged.emit()
        self._job = _WorkspaceJob(
            self._explorer.rootFolders, self._explorer.showHidden, self._explorer.ignorePatterns, search,
        )
        self._job.finished.connect(self._finished)
        self.busyChanged.emit()
        self._job.start()

    @Slot()
    def _finished(self) -> None:
        job = self._job
        if job is None:
            return
        self._job = None
        if job.cancelled.is_set():
            self._status = "Cancelled."
        else:
            self._entries = job.report["entries"]
            self._matches = job.report.get("matches", [])
            self._status = (
                f"{self.fileCount} files; {len(self._matches)} matches. "
                f"{job.report['skipped']} skipped (binary/encrypted/large files or links)."
            )
            if job.report["limited"]:
                self._status += f" Results limited to {MAX_ENTRIES} entries / {MAX_MATCHES} matches."
            if job.report["errors"]:
                self._status += f" {len(job.report['errors'])} errors."
                self.errorOccurred.emit("\n".join(job.report["errors"][:10]))
            self.entriesChanged.emit()
            self.matchesChanged.emit()
        self.statusChanged.emit()
        self.busyChanged.emit()
        job.deleteLater()

    @Slot()
    def cancel(self) -> None:
        if self._job is not None:
            self._job.cancelled.set()

    @Slot(str, result="QVariantList")
    def quickFiles(self, query: str) -> list[dict]:
        return fuzzy_files(self._entries, query)

    @Slot(str, result="QStringList")
    def filterPaths(self, query: str) -> list[str]:
        needle = query.strip().casefold()
        return [
            entry["path"] for entry in self._entries
            if needle in entry["relative"].casefold()
            or fnmatch.fnmatchcase(os.path.basename(entry["path"]).casefold(), needle)
        ]

    @Slot(str, str, result=bool)
    def isCurrent(self, text: str, digest: str) -> bool:
        return hashlib.sha256(text.encode("utf-8")).hexdigest() == digest

    def shutdown(self) -> None:
        self.cancel()
        if self._job is not None:
            self._job.wait()
