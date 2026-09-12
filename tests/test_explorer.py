"""Tests for the multi-folder ProjectExplorer model."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

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


def test_create_directory(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    created = explorer.createDirectory(str(sample_tree), "docs")
    assert created != ""
    assert (sample_tree / "docs").is_dir()


def test_rename_file(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    old_file = sample_tree / "README.md"
    new_path = explorer.rename(str(old_file), "README_OLD.md")
    assert new_path != ""
    assert not old_file.exists()
    assert (sample_tree / "README_OLD.md").exists()


def test_delete_item(explorer: ProjectExplorer, sample_tree: Path) -> None:
    explorer.addFolder(str(sample_tree))
    target = sample_tree / "main.py"
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

