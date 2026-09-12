"""Multi-folder project explorer model for Cipherpad."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QFileSystemWatcher,
    QModelIndex,
    QObject,
    Qt,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QmlElement

QML_IMPORT_NAME = "Cipherpad"
QML_IMPORT_MAJOR_VERSION = 1

IGNORED_NAMES: Final = {
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    ".DS_Store",
    "node_modules",
    "Thumbs.db",
}

FILE_EXTENSIONS: Final = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".qml": "qml",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cs": "csharp",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".json": "json",
    ".xml": "xml",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "css",
    ".less": "css",
    ".md": "markdown",
    ".markdown": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".ps1": "powershell",
    ".sql": "sql",
    ".enc": "encrypted",
    ".aes": "encrypted",
    ".txt": "text",
    ".log": "text",
}


def normalize_folder_path(raw: str) -> str:
    path = str(raw).strip()
    if path.startswith("file:"):
        url = QUrl(path)
        local = url.toLocalFile()
        if local:
            path = local
        else:
            import re
            path = re.sub(r"^file:\/{2,3}", "", path)
    return os.path.normpath(os.path.abspath(path))


def get_file_type(name: str, is_dir: bool) -> str:
    if is_dir:
        return "folder"
    ext = os.path.splitext(name)[1].lower()
    return FILE_EXTENSIONS.get(ext, "file")


@dataclass
class ExplorerNode:
    path: str
    name: str
    is_dir: bool
    is_root: bool
    depth: int
    expanded: bool
    has_children: bool
    file_type: str
    root_path: str


@QmlElement
class ProjectExplorer(QAbstractListModel):
    """List model representing the visible nodes in a multi-folder project tree."""

    NameRole = Qt.ItemDataRole.UserRole + 1
    PathRole = Qt.ItemDataRole.UserRole + 2
    IsDirRole = Qt.ItemDataRole.UserRole + 3
    IsRootRole = Qt.ItemDataRole.UserRole + 4
    DepthRole = Qt.ItemDataRole.UserRole + 5
    ExpandedRole = Qt.ItemDataRole.UserRole + 6
    HasChildrenRole = Qt.ItemDataRole.UserRole + 7
    FileTypeRole = Qt.ItemDataRole.UserRole + 8
    RootPathRole = Qt.ItemDataRole.UserRole + 9

    rootFolderCountChanged = Signal()
    rootFoldersChanged = Signal()
    countChanged = Signal()
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._root_folders: list[str] = []
        self._expanded_paths: set[str] = set()
        self._items: list[ExplorerNode] = []
        self._watcher: QFileSystemWatcher | None = None

    # ------------------------------------------------------- model plumbing
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._items)

    def roleNames(self) -> dict:  # noqa: N802
        return {
            self.NameRole: QByteArray(b"name"),
            self.PathRole: QByteArray(b"path"),
            self.IsDirRole: QByteArray(b"isDir"),
            self.IsRootRole: QByteArray(b"isRoot"),
            self.DepthRole: QByteArray(b"depth"),
            self.ExpandedRole: QByteArray(b"expanded"),
            self.HasChildrenRole: QByteArray(b"hasChildren"),
            self.FileTypeRole: QByteArray(b"fileType"),
            self.RootPathRole: QByteArray(b"rootPath"),
        }

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        node = self._items[index.row()]
        match role:
            case self.NameRole | Qt.ItemDataRole.DisplayRole:
                return node.name
            case self.PathRole:
                return node.path
            case self.IsDirRole:
                return node.is_dir
            case self.IsRootRole:
                return node.is_root
            case self.DepthRole:
                return node.depth
            case self.ExpandedRole:
                return node.expanded
            case self.HasChildrenRole:
                return node.has_children
            case self.FileTypeRole:
                return node.file_type
            case self.RootPathRole:
                return node.root_path
        return None

    # ------------------------------------------------------------ properties
    @Property(int, notify=rootFolderCountChanged)
    def rootFolderCount(self) -> int:
        return len(self._root_folders)

    @Property("QStringList", notify=rootFoldersChanged)
    def rootFolders(self) -> list[str]:
        return list(self._root_folders)

    @Property(bool, notify=rootFolderCountChanged)
    def isEmpty(self) -> bool:
        return len(self._root_folders) == 0

    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._items)

    # ---------------------------------------------------------------- slots
    @Slot(str, result=bool)
    def addFolder(self, raw_path: str) -> bool:
        """Add a root project folder to the explorer."""
        if not raw_path:
            return False
        path = normalize_folder_path(raw_path)
        if not os.path.isdir(path):
            self.errorOccurred.emit(f"Not a valid directory: {path}")
            return False
        if path in self._root_folders:
            return False

        self._root_folders.append(path)
        self._expanded_paths.add(path)
        self._rebuild_tree()
        self.rootFolderCountChanged.emit()
        self.rootFoldersChanged.emit()
        return True

    @Slot(str, result=bool)
    def removeFolder(self, raw_path: str) -> bool:
        """Remove a root project folder from the explorer."""
        if not raw_path:
            return False
        path = normalize_folder_path(raw_path)
        if path not in self._root_folders:
            return False

        self._root_folders.remove(path)
        self._expanded_paths = {p for p in self._expanded_paths if not p.startswith(path)}
        self._rebuild_tree()
        self.rootFolderCountChanged.emit()
        self.rootFoldersChanged.emit()
        return True

    @Slot(int, result=bool)
    def removeFolderAt(self, index: int) -> bool:
        if 0 <= index < len(self._root_folders):
            return self.removeFolder(self._root_folders[index])
        return False

    @Slot()
    def clearFolders(self) -> None:
        """Remove all root folders."""
        if not self._root_folders:
            return
        self._root_folders.clear()
        self._expanded_paths.clear()
        self._rebuild_tree()
        self.rootFolderCountChanged.emit()
        self.rootFoldersChanged.emit()

    @Slot(str, result=bool)
    def hasFolder(self, raw_path: str) -> bool:
        path = normalize_folder_path(raw_path)
        return path in self._root_folders

    def _target_to_path(self, target: str | int) -> str:
        if isinstance(target, int):
            if 0 <= target < len(self._items):
                return self._items[target].path
            return ""
        return normalize_folder_path(str(target))

    @Slot(str)
    @Slot(int)
    def toggleExpanded(self, target: str | int) -> None:
        """Toggle expansion of the directory at *target* (path or row index)."""
        path = self._target_to_path(target)
        if not path:
            return
        if path in self._expanded_paths:
            self.collapse(path)
        else:
            self.expand(path)

    @Slot(str)
    @Slot(int)
    def toggleExpand(self, target: str | int) -> None:
        """Alias for toggleExpanded."""
        self.toggleExpanded(target)

    @Slot(str)
    @Slot(int)
    def expand(self, target: str | int) -> None:
        """Expand the directory at *target* (path or row index)."""
        path = self._target_to_path(target)
        if not path:
            return
        if path in self._expanded_paths:
            return
        self._expanded_paths.add(path)

        idx = self._find_index_by_path(path)
        if idx >= 0 and self._items[idx].is_dir:
            self._items[idx].expanded = True
            model_index = self.index(idx, 0)
            self.dataChanged.emit(model_index, model_index)

            descendants = self._collect_children(path, self._items[idx].depth, self._items[idx].root_path)
            if descendants:
                self.beginInsertRows(QModelIndex(), idx + 1, idx + len(descendants))
                self._items[idx + 1 : idx + 1] = descendants
                self.endInsertRows()
                self.countChanged.emit()
        else:
            self._rebuild_tree()
        self._update_watcher()

    @Slot(str)
    @Slot(int)
    def collapse(self, target: str | int) -> None:
        """Collapse the directory at *target* (path or row index)."""
        path = self._target_to_path(target)
        if not path:
            return
        if path not in self._expanded_paths:
            return
        self._expanded_paths.discard(path)

        idx = self._find_index_by_path(path)
        if idx >= 0 and self._items[idx].is_dir:
            self._items[idx].expanded = False
            model_index = self.index(idx, 0)
            self.dataChanged.emit(model_index, model_index)

            depth = self._items[idx].depth
            remove_count = 0
            for i in range(idx + 1, len(self._items)):
                if self._items[i].depth > depth:
                    remove_count += 1
                else:
                    break

            if remove_count > 0:
                self.beginRemoveRows(QModelIndex(), idx + 1, idx + remove_count)
                del self._items[idx + 1 : idx + 1 + remove_count]
                self.endRemoveRows()
                self.countChanged.emit()
        else:
            self._rebuild_tree()
        self._update_watcher()

    @Slot(str, result=bool)
    def isExpanded(self, raw_path: str) -> bool:
        path = normalize_folder_path(raw_path)
        return path in self._expanded_paths

    @Slot()
    def collapseAll(self) -> None:
        """Collapse all folders, keeping root folders in collapsed state."""
        self._expanded_paths.clear()
        self._rebuild_tree()

    @Slot()
    def expandAll(self) -> None:
        """Expand all directories in the explorer."""
        for root in self._root_folders:
            self._expand_all_recursive(root)
        self._rebuild_tree()

    def _expand_all_recursive(self, dir_path: str) -> None:
        self._expanded_paths.add(dir_path)
        try:
            with os.scandir(dir_path) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False) and not self._is_ignored(entry.name):
                        self._expand_all_recursive(entry.path)
        except OSError:
            pass

    @Slot()
    def refresh(self) -> None:
        """Re-scan disk and refresh the explorer tree."""
        self._rebuild_tree()

    @Slot(str)
    def copyToClipboard(self, text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

    @Slot(int, result="QVariantMap")
    def itemAt(self, index: int) -> dict:
        if 0 <= index < len(self._items):
            node = self._items[index]
            return {
                "name": node.name,
                "path": node.path,
                "isDir": node.is_dir,
                "isRoot": node.is_root,
                "depth": node.depth,
                "expanded": node.expanded,
                "hasChildren": node.has_children,
                "fileType": node.file_type,
                "rootPath": node.root_path,
            }
        return {}

    @Slot(int, result="QVariantMap")
    def rowData(self, index: int) -> dict:
        """Alias for itemAt."""
        return self.itemAt(index)

    @Slot(str, result=bool)
    @Slot(str, bool, result=bool)
    def copyPathToClipboard(self, raw_path: str, relative: bool = False) -> bool:
        """Copy the path or workspace-relative path to system clipboard."""
        path = normalize_folder_path(raw_path)
        if not path:
            return False
        if relative:
            for root in self._root_folders:
                if path == root or path.startswith(root + os.sep):
                    rel = os.path.relpath(path, root)
                    self.copyToClipboard(rel)
                    return True
        self.copyToClipboard(path)
        return True

    @Slot(result="QStringList")
    def openFolders(self) -> list[str]:
        return list(self._root_folders)

    @Slot("QStringList", result=int)
    def loadFolders(self, paths: list[str]) -> int:
        """Load multiple root folders (e.g. from session)."""
        loaded = 0
        for path in paths:
            norm = normalize_folder_path(path)
            if os.path.isdir(norm) and norm not in self._root_folders:
                self._root_folders.append(norm)
                self._expanded_paths.add(norm)
                loaded += 1
        if loaded:
            self._rebuild_tree()
            self.rootFolderCountChanged.emit()
            self.rootFoldersChanged.emit()
        return loaded

    @Slot(str, str, result=str)
    def createFile(self, parent_dir: str, name: str) -> str:
        """Create a new file in parent_dir."""
        parent_norm = normalize_folder_path(parent_dir)
        if not os.path.isdir(parent_norm):
            self.errorOccurred.emit(f"Parent directory not found: {parent_norm}")
            return ""
        file_path = os.path.join(parent_norm, name.strip())
        if os.path.exists(file_path):
            self.errorOccurred.emit(f"File already exists: {file_path}")
            return ""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("")
        except OSError as exc:
            self.errorOccurred.emit(f"Could not create file: {exc}")
            return ""
        self._expanded_paths.add(parent_norm)
        self._rebuild_tree()
        return file_path

    @Slot(str, str, result=str)
    def createFolder(self, parent_dir: str, name: str) -> str:
        """Create a new subfolder in parent_dir."""
        parent_norm = normalize_folder_path(parent_dir)
        if not os.path.isdir(parent_norm):
            self.errorOccurred.emit(f"Parent directory not found: {parent_norm}")
            return ""
        folder_path = os.path.join(parent_norm, name.strip())
        if os.path.exists(folder_path):
            self.errorOccurred.emit(f"Folder already exists: {folder_path}")
            return ""
        try:
            os.makedirs(folder_path, exist_ok=True)
        except OSError as exc:
            self.errorOccurred.emit(f"Could not create folder: {exc}")
            return ""
        self._expanded_paths.add(parent_norm)
        self._expanded_paths.add(folder_path)
        self._rebuild_tree()
        return folder_path

    @Slot(str, str, result=str)
    def createDirectory(self, parent_dir: str, name: str) -> str:
        """Alias for createFolder."""
        return self.createFolder(parent_dir, name)

    @Slot(str, result=bool)
    def deleteItem(self, raw_path: str) -> bool:
        """Delete a file or directory."""
        path = normalize_folder_path(raw_path)
        if not os.path.exists(path):
            return False
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.unlink(path)
        except OSError as exc:
            self.errorOccurred.emit(f"Could not delete: {exc}")
            return False
        if path in self._root_folders:
            self._root_folders.remove(path)
            self.rootFolderCountChanged.emit()
            self.rootFoldersChanged.emit()
        self._expanded_paths = {p for p in self._expanded_paths if not p.startswith(path)}
        self._rebuild_tree()
        return True

    @Slot(str, str, result=str)
    def rename(self, old_path: str, new_name: str) -> str:
        """Rename item and return new path on success, or empty string on failure."""
        old_norm = normalize_folder_path(old_path)
        if not os.path.exists(old_norm):
            return ""
        parent_dir = os.path.dirname(old_norm)
        new_path = os.path.join(parent_dir, new_name.strip())
        if self.renameItem(old_path, new_name):
            return new_path
        return ""

    @Slot(str, str, result=bool)
    def renameItem(self, old_path: str, new_name: str) -> bool:
        """Rename a file or folder to new_name in the same parent directory."""
        old_norm = normalize_folder_path(old_path)
        if not os.path.exists(old_norm):
            return False
        parent_dir = os.path.dirname(old_norm)
        new_path = os.path.join(parent_dir, new_name.strip())
        if os.path.exists(new_path):
            self.errorOccurred.emit(f"Target already exists: {new_path}")
            return False
        try:
            os.rename(old_norm, new_path)
        except OSError as exc:
            self.errorOccurred.emit(f"Could not rename: {exc}")
            return False

        if old_norm in self._root_folders:
            idx = self._root_folders.index(old_norm)
            self._root_folders[idx] = new_path
            self.rootFoldersChanged.emit()

        new_expanded: set[str] = set()
        for p in self._expanded_paths:
            if p == old_norm:
                new_expanded.add(new_path)
            elif p.startswith(old_norm + os.sep):
                new_expanded.add(new_path + p[len(old_norm) :])
            else:
                new_expanded.add(p)
        self._expanded_paths = new_expanded

        self._rebuild_tree()
        return True

    # ------------------------------------------------------------ helpers
    def _is_ignored(self, name: str) -> bool:
        if name in IGNORED_NAMES:
            return True
        if name.startswith(".") and name not in (".", ".."):
            return True
        return False

    def _has_children(self, dir_path: str) -> bool:
        try:
            with os.scandir(dir_path) as it:
                for entry in it:
                    if not self._is_ignored(entry.name):
                        return True
        except OSError:
            pass
        return False

    def _find_index_by_path(self, path: str) -> int:
        for i, node in enumerate(self._items):
            if node.path == path:
                return i
        return -1

    def _collect_children(self, dir_path: str, parent_depth: int, root_path: str) -> list[ExplorerNode]:
        """Collect direct and expanded indirect children for dir_path."""
        items: list[ExplorerNode] = []
        entries: list[os.DirEntry] = []
        try:
            with os.scandir(dir_path) as it:
                for entry in it:
                    if not self._is_ignored(entry.name):
                        entries.append(entry)
        except OSError:
            return items

        # Sort: directories first, then files; both alphabetically case-insensitive
        entries.sort(key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))

        for entry in entries:
            is_dir = entry.is_dir(follow_symlinks=False)
            path = os.path.normpath(entry.path)
            expanded = path in self._expanded_paths if is_dir else False
            has_children = self._has_children(path) if is_dir else False
            file_type = get_file_type(entry.name, is_dir)
            node = ExplorerNode(
                path=path,
                name=entry.name,
                is_dir=is_dir,
                is_root=False,
                depth=parent_depth + 1,
                expanded=expanded,
                has_children=has_children,
                file_type=file_type,
                root_path=root_path,
            )
            items.append(node)
            if is_dir and expanded:
                items.extend(self._collect_children(path, parent_depth + 1, root_path))
        return items

    def _rebuild_tree(self) -> None:
        self.beginResetModel()
        self._items.clear()

        for root in self._root_folders:
            if not os.path.isdir(root):
                continue
            is_expanded = root in self._expanded_paths
            has_children = self._has_children(root)
            root_node = ExplorerNode(
                path=root,
                name=os.path.basename(root) or root,
                is_dir=True,
                is_root=True,
                depth=0,
                expanded=is_expanded,
                has_children=has_children,
                file_type="folder",
                root_path=root,
            )
            self._items.append(root_node)
            if is_expanded:
                self._items.extend(self._collect_children(root, 0, root))

        self.endResetModel()
        self.countChanged.emit()
        self._update_watcher()

    def _update_watcher(self) -> None:
        if self._watcher is not None:
            self._watcher.deleteLater()
            self._watcher = None

        watch_dirs = [p for p in self._expanded_paths if os.path.isdir(p)]
        for root in self._root_folders:
            if root not in watch_dirs and os.path.isdir(root):
                watch_dirs.append(root)

        if watch_dirs:
            self._watcher = QFileSystemWatcher(watch_dirs, self)
            self._watcher.directoryChanged.connect(self._on_directory_changed)

    def _on_directory_changed(self, _path: str) -> None:
        self._rebuild_tree()
