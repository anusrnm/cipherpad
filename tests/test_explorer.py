"""Tests for the multi-folder ProjectExplorer model."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from PySide6.QtCore import QFile, Qt

from cipherpad.explorer import ProjectExplorer


@pytest.fixture()
def explorer(qt_app) -> ProjectExplorer:  # noqa: ANN001
    return ProjectExplorer()


@pytest.fixture()
def sample_tree(tmp_path: Path) -> Path:
    """Create a sample directory structure with files and nested folders."""
    proj = tmp_path / "my_project"
    proj.mkdir()
    (proj / "README.md").write_text("# Test", encoding="utf-8")
    (proj / "main.py").write_text("print(1)", encoding="utf-8")

    src = proj / "src"
    src.mkdir()
    (src / "app.py").write_text("app = 1", encoding="utf-8")
    (src / "utils.py").write_text("utils = 1", encoding="utf-8")

    nested = src / "nested"
    nested.mkdir()
    (nested / "deep.txt").write_text("deep", encoding="utf-8")

    return proj


# ----------------------------------------------------------- roots & management
def test_starts_empty(explorer: ProjectExplorer) -> None:
    assert explorer.rowCount() == 0
    assert explorer.rootFolderCount == 0
    assert explorer.rootFolders == []


def test_add_folder(explorer: ProjectExplorer, sample_tree: Path) -> None:
    assert explorer.addFolder(str(sample_tree))
    assert explorer.rootFolderCount == 1
    assert explorer.rootFolders == [str(sample_tree)]
    assert explorer.rowCount() > 0


def test_add_folder_file_url(explorer: ProjectExplorer, sample_tree: Path) -> None:
    url = sample_tree.as_uri()
    assert explorer.addFolder(url)
    assert explorer.rootFolderCount == 1


def test_add_nonexistent_folder_fails(explorer: ProjectExplorer, tmp_path: Path) -> None:
    non_existent = tmp_path / "does_not_exist"
    assert not explorer.addFolder(str(non_existent))
    assert explorer.rootFolderCount == 0


def test_add_file_as_folder_fails(explorer: ProjectExplorer, sample_tree: Path) -> None:
    file_path = sample_tree / "README.md"
    assert not explorer.addFolder(str(file_path))
    assert explorer.rootFolderCount == 0


def test_add_duplicate_folder_ignored(explorer: ProjectExplorer, sample_tree: Path) -> None:
    assert explorer.addFolder(str(sample_tree))
    assert not explorer.addFolder(str(sample_tree))
    assert explorer.rootFolderCount == 1


def test_add_multiple_folders(explorer: ProjectExplorer, tmp_path: Path) -> None:
    dir1 = tmp_path / "proj1"
    dir2 = tmp_path / "proj2"
    dir1.mkdir()
    dir2.mkdir()

    assert explorer.addFolder(str(dir1))
    assert explorer.addFolder(str(dir2))
    assert explorer.rootFolderCount == 2
    assert explorer.rootFolders == [str(dir1), str(dir2)]


def test_remove_folder(explorer: ProjectExplorer, tmp_path: Path) -> None:
    dir1 = tmp_path / "proj1"
    dir2 = tmp_path / "proj2"
    dir1.mkdir()
    dir2.mkdir()
    (dir1 / "file1.txt").write_text("1")
    (dir2 / "file2.txt").write_text("2")

    explorer.addFolder(str(dir1))
    explorer.addFolder(str(dir2))
    assert explorer.rootFolderCount == 2

    assert explorer.removeFolder(str(dir1))
    assert explorer.rootFolderCount == 1
    assert explorer.rootFolders == [str(dir2)]


def test_remove_nonexistent_root_is_safe(explorer: ProjectExplorer) -> None:
    assert not explorer.removeFolder("/not/a/root")


def test_clear_folders(explorer: ProjectExplorer, tmp_path: Path) -> None:
    dir1 = tmp_path / "proj1"
    dir2 = tmp_path / "proj2"
    dir1.mkdir()
    dir2.mkdir()
    explorer.addFolder(str(dir1))
    explorer.addFolder(str(dir2))

    explorer.clearFolders()
    assert explorer.rootFolderCount == 0
    assert explorer.rowCount() == 0
    assert explorer.rootFolders == []


# ------------------------------------------------------------- tree & expansion
def test_root_node_roles(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))

    # Root item is index 0
    idx = explorer.index(0, 0)
    assert explorer.data(idx, ProjectExplorer.NameRole) == sample_tree.name
    assert explorer.data(idx, ProjectExplorer.PathRole) == str(sample_tree)
    assert explorer.data(idx, ProjectExplorer.IsDirRole) is True
    assert explorer.data(idx, ProjectExplorer.IsRootRole) is True
    assert explorer.data(idx, ProjectExplorer.ExpandedRole) is True
    assert explorer.data(idx, ProjectExplorer.DepthRole) == 0


def test_tree_model_hierarchy(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    model = explorer.treeModel

    root = model.index(0, 0)
    assert model.data(root, ProjectExplorer.NameRole) == sample_tree.name
    assert not model.parent(root).isValid()
    assert model.rowCount(root) == 3

    source = model.index(0, 0, root)
    assert model.data(source, ProjectExplorer.NameRole) == "src"
    assert model.parent(source) == root
    assert model.rowCount(source) == 3

    first_source_file = model.index(1, 0, source)
    assert model.data(first_source_file, ProjectExplorer.NameRole) == "app.py"
    assert model.parent(first_source_file) == source


def test_children_sorted_directories_first(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    # Direct children of sample_tree:
    # dir: src
    # files: main.py, README.md (alphabetical)
    names = [explorer.data(explorer.index(i, 0), ProjectExplorer.NameRole) for i in range(explorer.rowCount())]
    assert names[0] == sample_tree.name
    assert names[1] == "src"
    assert names[2] == "main.py"
    assert names[3] == "README.md"


def test_expand_and_collapse_subdirectory(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    initial_count = explorer.rowCount()  # root + src + main.py + README.md = 4

    # Index 1 is "src" (depth 1)
    src_idx = explorer.index(1, 0)
    assert explorer.data(src_idx, ProjectExplorer.NameRole) == "src"
    assert explorer.data(src_idx, ProjectExplorer.ExpandedRole) is False

    # Expand "src"
    explorer.expand(1)
    assert explorer.data(src_idx, ProjectExplorer.ExpandedRole) is True
    expanded_count = explorer.rowCount()
    # "src" children: nested (dir), app.py, utils.py
    assert expanded_count == initial_count + 3

    # Collapse "src"
    explorer.collapse(1)
    assert explorer.rowCount() == initial_count
    assert explorer.data(src_idx, ProjectExplorer.ExpandedRole) is False


def test_toggle_expansion(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    initial_count = explorer.rowCount()

    # Toggle index 1 ("src")
    explorer.toggleExpand(1)
    assert explorer.rowCount() == initial_count + 3

    explorer.toggleExpand(1)
    assert explorer.rowCount() == initial_count


def test_collapse_root(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    assert explorer.rowCount() > 1

    explorer.collapse(0)
    assert explorer.rowCount() == 1  # only the root node itself
    assert explorer.data(explorer.index(0, 0), ProjectExplorer.ExpandedRole) is False

    explorer.expand(0)
    assert explorer.rowCount() > 1


def test_row_data_helper(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    data = explorer.rowData(0)
    assert data["name"] == sample_tree.name
    assert data["path"] == str(sample_tree)
    assert data["isDir"] is True
    assert data["isRoot"] is True
    assert data["depth"] == 0


# ------------------------------------------------------------- file operations
def test_create_file(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    created = explorer.createFile(str(sample_tree), "new_note.txt")
    assert created != ""
    assert (sample_tree / "new_note.txt").exists()


def test_create_duplicate_file_fails(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    assert explorer.createFile(str(sample_tree), "README.md") == ""


@pytest.mark.parametrize("name", ["../outside.txt", "..\\outside.txt", "C:\\outside.txt"])
def test_create_file_rejects_path_names(
    explorer: ProjectExplorer, sample_tree: Path, name: str
) -> None:
    errors: list[str] = []
    explorer.errorOccurred.connect(errors.append)

    assert explorer.createFile(str(sample_tree), name) == ""
    assert errors
    assert not (sample_tree.parent / "outside.txt").exists()


def test_create_directory(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    created = explorer.createDirectory(str(sample_tree), "docs")
    assert created != ""
    assert (sample_tree / "docs").is_dir()


def test_create_folder_rejects_path_name(explorer: ProjectExplorer, sample_tree: Path) -> None:
    errors: list[str] = []
    explorer.errorOccurred.connect(errors.append)

    assert explorer.createFolder(str(sample_tree), "../outside") == ""
    assert errors
    assert not (sample_tree.parent / "outside").exists()


def test_rename_file(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    old_file = sample_tree / "README.md"
    new_path = explorer.rename(str(old_file), "README_OLD.md")
    assert new_path != ""
    assert not old_file.exists()
    assert (sample_tree / "README_OLD.md").exists()


def test_rename_rejects_path_name(explorer: ProjectExplorer, sample_tree: Path) -> None:
    old_file = sample_tree / "README.md"
    errors: list[str] = []
    explorer.errorOccurred.connect(errors.append)

    assert explorer.rename(str(old_file), "../outside.md") == ""
    assert old_file.exists()
    assert not (sample_tree.parent / "outside.md").exists()
    assert errors


def test_delete_item(explorer: ProjectExplorer, sample_tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    explorer.addFolder(str(sample_tree))
    target = sample_tree / "main.py"
    def trash(path: str) -> bool:
        assert path == str(target)
        target.unlink()
        return True
    monkeypatch.setattr(QFile, "moveToTrash", trash)
    assert target.exists()
    assert explorer.deleteItem(str(target))
    assert not target.exists()


def test_icon_names(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    # root folder
    assert explorer.data(explorer.index(0, 0), ProjectExplorer.FileTypeRole) == "folder"
    # src folder (collapsed)
    assert explorer.data(explorer.index(1, 0), ProjectExplorer.FileTypeRole) == "folder"
    # python file
    assert explorer.data(explorer.index(2, 0), ProjectExplorer.FileTypeRole) == "python"
    # markdown file
    assert explorer.data(explorer.index(3, 0), ProjectExplorer.FileTypeRole) == "markdown"


def test_copy_path_to_clipboard(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    file_path = str(sample_tree / "main.py")

    assert explorer.copyPathToClipboard(file_path, relative=False)
    assert explorer.copyPathToClipboard(file_path, relative=True)


def test_duplicate_files_and_folders(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    assert explorer.duplicateItem(str(sample_tree / "main.py")) == str(sample_tree / "main copy.py")
    assert explorer.duplicateItem(str(sample_tree / "main.py")) == str(sample_tree / "main copy 2.py")
    assert (sample_tree / "main copy.py").read_bytes() == (sample_tree / "main.py").read_bytes()
    result = explorer.duplicateItem(str(sample_tree / "src"))
    assert result == str(sample_tree / "src copy")
    assert (sample_tree / "src copy" / "nested" / "deep.txt").read_text() == "deep"


@pytest.mark.parametrize("cut", [False, True])
def test_copy_cut_paste(explorer: ProjectExplorer, sample_tree: Path, cut: bool) -> None:
    explorer.addFolder(str(sample_tree))
    source = sample_tree / "main.py"
    assert not explorer.canPaste
    assert explorer.copyItem(str(source), cut)
    assert explorer.canPaste
    target = sample_tree / "src" / "main.py"
    assert explorer.pasteItem(str(target.parent)) == str(target)
    assert target.read_text() == "print(1)"
    assert source.exists() != cut
    assert explorer.canPaste != cut


def test_paste_conflict_preserves_both_items(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    source = sample_tree / "main.py"
    target = sample_tree / "src" / "main.py"
    target.write_text("existing")
    errors: list[str] = []
    explorer.errorOccurred.connect(errors.append)
    explorer.copyItem(str(source), True)
    assert explorer.pasteItem(str(target.parent)) == ""
    assert source.read_text() == "print(1)"
    assert target.read_text() == "existing"
    assert explorer.canPaste
    assert "already exists" in errors[-1]


def test_copy_folder_into_descendant_rejected(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    source = sample_tree / "src"
    explorer.copyItem(str(source), False)
    assert explorer.pasteItem(str(source / "nested")) == ""
    assert not (source / "nested" / "src").exists()


def test_root_cut_delete_rejected(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    errors: list[str] = []
    explorer.errorOccurred.connect(errors.append)
    assert not explorer.copyItem(str(sample_tree), True)
    assert not explorer.deleteItem(str(sample_tree))
    assert sample_tree.exists()
    assert len(errors) == 2


def test_missing_item_errors(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    errors: list[str] = []
    explorer.errorOccurred.connect(errors.append)
    path = str(sample_tree / "missing")
    assert not explorer.copyItem(path, False)
    assert not explorer.deleteItem(path)
    assert not explorer.renameItem(path, "new")
    assert len(errors) == 3


def test_failed_copy_leaves_no_partial_destination(
    explorer: ProjectExplorer, sample_tree: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    explorer.addFolder(str(sample_tree))
    def failed_copy(source: str, target: str, **kwargs) -> None:
        Path(target).write_text("partial")
        raise OSError("test copy failure")
    monkeypatch.setattr(shutil, "copy2", failed_copy)
    errors: list[str] = []
    explorer.errorOccurred.connect(errors.append)
    assert explorer.duplicateItem(str(sample_tree / "main.py")) == ""
    assert not (sample_tree / "main copy.py").exists()
    assert not list(sample_tree.glob(".cipherpad-copy-*"))
    assert "test copy failure" in errors[-1]


def test_failed_cut_preserves_source_and_clipboard(
    explorer: ProjectExplorer, sample_tree: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    explorer.addFolder(str(sample_tree))
    source = sample_tree / "main.py"
    explorer.copyItem(str(source), True)
    def failed_move(*args) -> None:
        raise OSError("cross-volume move")
    monkeypatch.setattr(os, "rename", failed_move)
    assert explorer.pasteItem(str(sample_tree / "src")) == ""
    assert source.exists()
    assert explorer.canPaste


def test_rename_and_move_update_open_documents(explorer: ProjectExplorer, sample_tree: Path) -> None:
    from cipherpad.document import DocumentManager
    manager = DocumentManager()
    explorer.bind_documents(manager)
    explorer.addFolder(str(sample_tree))
    source = sample_tree / "src" / "app.py"
    manager.openFile(str(source))
    doc = manager.currentDocument
    doc.modified = True
    explorer.expand(str(sample_tree / "src"))
    renamed = sample_tree / "source"
    assert explorer.rename(str(sample_tree / "src"), "source") == str(renamed)
    assert doc.filePath == str(renamed / "app.py")
    assert doc.modified
    assert doc._watcher.files() == [str(renamed / "app.py")]
    assert explorer.isExpanded(str(renamed))
    explorer.copyItem(str(renamed / "app.py"), True)
    assert explorer.pasteItem(str(sample_tree)) == str(sample_tree / "app.py")
    assert doc.filePath == str(sample_tree / "app.py")
    assert doc.modified
    assert doc._watcher.files() == [str(sample_tree / "app.py")]
    manager.closeAll()


def test_delete_blocks_unsaved_documents(explorer: ProjectExplorer, sample_tree: Path) -> None:
    from cipherpad.document import DocumentManager
    manager = DocumentManager()
    explorer.bind_documents(manager)
    explorer.addFolder(str(sample_tree))
    source = sample_tree / "src" / "app.py"
    manager.openFile(str(source))
    manager.currentDocument.modified = True
    errors: list[str] = []
    explorer.errorOccurred.connect(errors.append)
    assert not explorer.deleteItem(str(source.parent))
    assert source.exists()
    assert "unsaved" in errors[-1]
    manager.closeAll()


def test_delete_closes_clean_documents(
    explorer: ProjectExplorer, sample_tree: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cipherpad.document import DocumentManager
    manager = DocumentManager()
    explorer.bind_documents(manager)
    explorer.addFolder(str(sample_tree))
    source = sample_tree / "main.py"
    manager.openFile(str(source))
    def trash(path: str) -> bool:
        assert path == str(source)
        source.unlink()
        return True
    monkeypatch.setattr(QFile, "moveToTrash", trash)
    explorer.copyItem(str(source), False)
    assert explorer.deleteItem(str(source))
    assert manager.count == 0
    assert not explorer.canPaste


def test_delete_blocks_pinned_documents(explorer: ProjectExplorer, sample_tree: Path) -> None:
    from cipherpad.document import DocumentManager
    manager = DocumentManager()
    explorer.bind_documents(manager)
    explorer.addFolder(str(sample_tree))
    source = sample_tree / "main.py"
    manager.openFile(str(source))
    manager.currentDocument.pinned = True
    errors = []
    explorer.errorOccurred.connect(errors.append)
    assert not explorer.deleteItem(str(source))
    assert source.exists() and manager.count == 1
    assert "Unpin" in errors[-1]
    manager.currentDocument.pinned = False
    manager.closeAll()


def test_delete_trash_failure_preserves_file(
    explorer: ProjectExplorer, sample_tree: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    explorer.addFolder(str(sample_tree))
    monkeypatch.setattr(QFile, "moveToTrash", lambda path: False)
    errors: list[str] = []
    explorer.errorOccurred.connect(errors.append)
    assert not explorer.deleteItem(str(sample_tree / "main.py"))
    assert (sample_tree / "main.py").exists()
    assert "Trash" in errors[-1]


def test_reveal_in_file_explorer(
    explorer: ProjectExplorer, sample_tree: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cipherpad import explorer as module
    calls: list[list[str]] = []
    monkeypatch.setattr(module.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "Popen", lambda args: calls.append(args))
    path = str(sample_tree / "main.py")
    assert explorer.revealItem(path)
    assert calls == [["explorer.exe", "/select,", path]]


def test_rename_folder_updates_nested_workspace_roots(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    nested = sample_tree / "src" / "nested"
    explorer.addFolder(str(nested))
    assert explorer.rename(str(sample_tree / "src"), "source")
    assert explorer.rootFolders == [str(sample_tree), str(sample_tree / "source" / "nested")]


def test_item_outside_workspace_rejected(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree / "src"))
    outside = sample_tree / "main.py"
    errors: list[str] = []
    explorer.errorOccurred.connect(errors.append)
    assert not explorer.deleteItem(str(outside))
    assert not explorer.renameItem(str(outside), "renamed.py")
    assert outside.exists()
    assert len(errors) == 2


def test_copy_folder_paste(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    destination = sample_tree / "destination"
    destination.mkdir()
    explorer.copyItem(str(sample_tree / "src"), False)
    assert explorer.pasteItem(str(destination)) == str(destination / "src")
    assert (destination / "src" / "nested" / "deep.txt").read_text() == "deep"
    assert (sample_tree / "src" / "nested" / "deep.txt").exists()


def test_rename_case_only(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    source = sample_tree / "main.py"
    target = sample_tree / "Main.py"
    assert explorer.rename(str(source), target.name) == str(target)
    assert target.read_text() == "print(1)"
    assert target.name in [entry.name for entry in sample_tree.iterdir()]
