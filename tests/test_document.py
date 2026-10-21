"""Tests for Document / DocumentManager file handling."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cipherpad import crypto
from cipherpad.document import Document, DocumentManager


@pytest.fixture()
def doc(qt_app) -> Document:  # noqa: ANN001
    return Document("Untitled-1")


@pytest.fixture()
def manager(qt_app) -> DocumentManager:  # noqa: ANN001
    return DocumentManager()


def errors(document: Document) -> list[str]:
    """Collect errorOccurred payloads emitted after this call."""
    collected: list[str] = []
    document.errorOccurred.connect(collected.append)
    return collected


# ----------------------------------------------------------------- new document
def test_new_document_is_untitled(doc: Document) -> None:
    assert doc.isUntitled
    assert doc.filePath == ""
    assert not doc.modified
    assert not doc.encrypted


def test_display_name_is_the_file_name(doc: Document) -> None:
    assert doc.displayName == doc.fileName
    doc.modified = True
    assert doc.displayName == doc.fileName


def test_save_without_path_fails(doc: Document) -> None:
    messages = errors(doc)
    assert doc.save("text") is False
    assert messages and "Save As" in messages[0]


# ------------------------------------------------------------- plain round trip
def test_save_as_then_load(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    assert doc.saveAs(str(target), "hello\nworld\n")
    assert target.read_text(encoding="utf-8") == "hello\nworld\n"

    reopened = Document("note.txt")
    assert reopened.load(str(target))
    assert reopened.takeContent() == "hello\nworld\n"
    assert not reopened.encrypted


def test_save_as_sets_metadata(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "script.py"
    assert doc.saveAs(str(target), "print(1)\n")
    assert doc.filePath == os.path.abspath(str(target))
    assert doc.fileName == "script.py"
    assert not doc.isUntitled
    assert doc.language == "python"
    assert not doc.modified


def test_save_updates_existing_file(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    doc.saveAs(str(target), "one")
    assert doc.save("two")
    assert target.read_text(encoding="utf-8") == "two"


def test_modified_tracks_saved_content(doc: Document, tmp_path: Path) -> None:
    assert doc.saveAs(str(tmp_path / "note.txt"), "original")
    changes: list[bool] = []
    doc.modifiedChanged.connect(lambda: changes.append(doc.modified))
    doc.updateModified("edited")
    assert doc.modified
    doc.updateModified("edited")
    doc.updateModified("original")
    assert not doc.modified
    doc.updateModified("edited")
    assert doc.modified
    assert changes == [True, False, True]


def test_modified_tracks_loaded_and_reloaded_content(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    target.write_bytes(b"original\r\n")
    assert doc.load(str(target))
    doc.updateModified("edited\n")
    assert doc.modified
    doc.updateModified("original\n")
    assert not doc.modified
    target.write_bytes(b"replacement\r\n")
    assert doc.reload()
    doc.updateModified("original\n")
    assert doc.modified
    doc.updateModified("replacement\n")
    assert not doc.modified


def test_modified_baseline_moves_only_after_successful_save(doc: Document, tmp_path: Path) -> None:
    assert doc.saveAs(str(tmp_path / "note.txt"), "original")
    assert doc.save("edited")
    doc.updateModified("original")
    assert doc.modified
    doc.updateModified("edited")
    assert not doc.modified
    doc.encoding = "ascii"
    assert not doc.save("\u00e9")
    doc.encoding = "utf-8"
    doc.updateModified("edited")
    assert not doc.modified
    doc.updateModified("\u00e9")
    assert doc.modified


@pytest.mark.parametrize("setting,value", [("encoding", "latin-1"), ("lineEnding", "crlf")])
def test_text_undo_preserves_unsaved_format_changes(
    doc: Document, tmp_path: Path, setting: str, value: str,
) -> None:
    assert doc.saveAs(str(tmp_path / "note.txt"), "original")
    original = getattr(doc, setting)
    setattr(doc, setting, value)
    doc.updateModified("edited")
    doc.updateModified("original")
    assert doc.modified
    setattr(doc, setting, original)
    assert not doc.modified
    doc.updateModified("edited")
    setattr(doc, setting, value)
    setattr(doc, setting, original)
    assert doc.modified


def test_untitled_modified_clears_when_empty(doc: Document) -> None:
    doc.updateModified("text")
    assert doc.modified
    doc.updateModified("")
    assert not doc.modified


def test_recovered_document_stays_modified_until_saved(manager: DocumentManager, tmp_path: Path) -> None:
    index = manager.newRecovered("recovered", "note", "plain", "utf-8", "lf")
    recovered = manager.documentAt(index)
    recovered.updateModified("")
    assert recovered.modified
    recovered.updateModified("recovered")
    assert recovered.modified
    assert recovered.saveAs(str(tmp_path / "recovered.txt"), "recovered")
    recovered.updateModified("edit")
    recovered.updateModified("recovered")
    assert not recovered.modified


def test_locked_document_preserves_clean_baseline(doc: Document, tmp_path: Path) -> None:
    assert doc.saveAs(str(tmp_path / "secret.txt"), "original", True, "pw")
    doc.updateModified("edited")
    assert doc.lock("edited")
    doc.updateModified("")
    assert doc.modified
    assert doc.unlock("pw")
    doc.updateModified("edited")
    assert doc.modified
    doc.updateModified("original")
    assert not doc.modified


def test_save_emits_saved_signal(doc: Document, tmp_path: Path) -> None:
    seen: list[bool] = []
    doc.saved.connect(lambda: seen.append(True))
    doc.saveAs(str(tmp_path / "a.txt"), "x")
    assert seen


def test_save_normalises_line_endings(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "crlf.txt"
    doc.lineEnding = "crlf"
    doc.saveAs(str(target), "a\nb\n")
    assert target.read_bytes() == b"a\r\nb\r\n"


def test_load_detects_crlf(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "crlf.txt"
    target.write_bytes(b"a\r\nb\r\n")
    assert doc.load(str(target))
    assert doc.lineEnding == "crlf"
    assert doc.takeContent() == "a\nb\n"


# ------------------------------------------------------------------ encryption
def test_save_as_encrypted_writes_container(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "secret.txt"
    assert doc.saveAs(str(target), "top secret\n", True, "correct horse")
    assert doc.encrypted
    assert doc.hasPassphrase
    assert crypto.is_encrypted(target.read_bytes())


def test_encrypted_round_trip(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "secret.txt"
    doc.saveAs(str(target), "top secret\n", True, "correct horse")

    reopened = Document("secret.txt")
    assert reopened.load(str(target), "correct horse")
    assert reopened.takeContent() == "top secret\n"
    assert reopened.encrypted


def test_load_encrypted_without_passphrase_requests_one(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "secret.txt"
    doc.saveAs(str(target), "hidden", True, "pw")

    reopened = Document("secret.txt")
    asked: list[bool] = []
    reopened.passphraseRequired.connect(lambda: asked.append(True))
    assert reopened.load(str(target)) is False
    assert asked


def test_load_encrypted_with_wrong_passphrase_fails(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "secret.txt"
    doc.saveAs(str(target), "hidden", True, "pw")

    reopened = Document("secret.txt")
    messages = errors(reopened)
    assert reopened.load(str(target), "nope") is False
    assert messages


def test_save_as_encrypted_requires_passphrase(doc: Document, tmp_path: Path) -> None:
    messages = errors(doc)
    assert doc.saveAs(str(tmp_path / "x.txt"), "a", True, "") is False
    assert messages and "passphrase" in messages[0].lower()


def test_encrypt_with_converts_existing_file(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    doc.saveAs(str(target), "plain")
    assert not crypto.is_encrypted(target.read_bytes())

    assert doc.encryptWith("plain", "pw")
    assert doc.encrypted
    assert crypto.is_encrypted(target.read_bytes())


def test_encrypt_with_on_untitled_requires_save(doc: Document) -> None:
    messages = errors(doc)
    assert doc.encryptWith("text", "pw") is False
    assert not doc.encrypted
    assert messages


def test_encrypt_with_requires_passphrase(doc: Document) -> None:
    messages = errors(doc)
    assert doc.encryptWith("text", "") is False
    assert messages


def test_remove_encryption_writes_plaintext(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "secret.txt"
    doc.saveAs(str(target), "hidden", True, "pw")
    assert doc.removeEncryption("hidden")
    assert not doc.encrypted
    assert target.read_text(encoding="utf-8") == "hidden"


def test_remove_encryption_on_plain_document_is_noop(doc: Document) -> None:
    assert doc.removeEncryption("text")
    assert not doc.encrypted


def test_change_and_verify_passphrase(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "secret.txt"
    assert doc.saveAs(str(target), "secret", True, "old")
    assert doc.changePassphrase("secret", "first")
    assert doc.verifyPassphrase("first")
    assert not doc.verifyPassphrase("second")

    reopened = Document("secret.txt")
    assert reopened.load(str(target), "first")
    assert reopened.takeContent() == "secret"
    assert not Document("secret.txt").load(str(target), "old")


def test_change_passphrase_rejects_empty(doc: Document) -> None:
    messages = errors(doc)
    assert doc.changePassphrase("text", "") is False
    assert messages


def test_change_passphrase_rejects_plain_document(doc: Document) -> None:
    messages = errors(doc)
    assert doc.changePassphrase("text", "new passphrase") is False
    assert messages and "encrypted" in messages[0].lower()


def test_passphrase_strength_reports_label(doc: Document) -> None:
    weak = doc.passphraseStrength("a")
    strong = doc.passphraseStrength("Tr0ub4dor&3-correct-horse")
    assert weak["score"] < strong["score"]
    assert weak["label"] and strong["label"]


def test_encrypted_save_is_utf8_regardless_of_encoding(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "secret.txt"
    doc.encoding = "latin-1"
    assert doc.saveAs(str(target), "caf\u00e9 \u4e2d\u6587", True, "pw")

    reopened = Document("secret.txt")
    assert reopened.load(str(target), "pw")
    assert reopened.takeContent() == "caf\u00e9 \u4e2d\u6587"


# ---------------------------------------------------------------- error paths
def test_load_missing_file_reports_error(doc: Document, tmp_path: Path) -> None:
    messages = errors(doc)
    assert doc.load(str(tmp_path / "nope.txt")) is False
    assert messages


def test_load_binary_file_is_refused(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "blob.bin"
    target.write_bytes(b"\x00\x01\x02binary\x00payload")
    messages = errors(doc)
    assert doc.load(str(target)) is False
    assert messages and "binary" in messages[0].lower()


def test_reload_without_path_fails(doc: Document) -> None:
    assert doc.reload() is False


def test_reload_rereads_from_disk(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    doc.saveAs(str(target), "first")
    target.write_text("second", encoding="utf-8")
    assert doc.reload()
    assert doc.takeContent() == "second"


def test_atomic_write_leaves_no_temp_files(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    doc.saveAs(str(target), "content")
    assert [p.name for p in tmp_path.iterdir()] == ["note.txt"]


def test_save_creates_missing_directories(doc: Document, tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deep" / "note.txt"
    assert doc.saveAs(str(target), "content")
    assert target.read_text(encoding="utf-8") == "content"


def test_language_can_be_set_from_content(doc: Document) -> None:
    doc.setLanguageFromContent("#!/bin/bash\necho hi\n")
    assert doc.language != ""


# ------------------------------------------------------------ document manager
def test_manager_starts_empty(manager: DocumentManager) -> None:
    assert manager.count == 0
    assert manager.currentIndex == -1
    assert manager.currentDocument is None


def test_new_document_appends_and_focuses(manager: DocumentManager) -> None:
    index = manager.newDocument()
    assert index == 0
    assert manager.count == 1
    assert manager.currentIndex == 0
    assert manager.currentDocument is not None


def test_untitled_names_are_unique(manager: DocumentManager) -> None:
    manager.newDocument()
    manager.newDocument()
    names = {manager.documentAt(i).fileName for i in range(manager.count)}
    assert len(names) == 2


def test_open_file_returns_index(manager: DocumentManager, tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    target.write_text("hello", encoding="utf-8")
    assert manager.openFile(str(target)) == 0
    assert manager.documentAt(0).takeContent() == "hello"


def test_open_file_focuses_existing_tab(manager: DocumentManager, tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    target.write_text("hello", encoding="utf-8")
    first = manager.openFile(str(target))
    manager.newDocument()
    assert manager.openFile(str(target)) == first
    assert manager.count == 2
    assert manager.currentIndex == first


def test_open_missing_file_returns_minus_one(manager: DocumentManager, tmp_path: Path) -> None:
    assert manager.openFile(str(tmp_path / "nope.txt")) == -1
    assert manager.count == 0


def test_open_encrypted_without_passphrase_returns_minus_two(
    manager: DocumentManager, doc: Document, tmp_path: Path
) -> None:
    target = tmp_path / "secret.txt"
    doc.saveAs(str(target), "hidden", True, "pw")
    assert manager.openFile(str(target)) == -2
    assert manager.count == 0


def test_open_encrypted_with_wrong_passphrase_returns_minus_one(
    manager: DocumentManager, doc: Document, tmp_path: Path
) -> None:
    target = tmp_path / "secret.txt"
    doc.saveAs(str(target), "hidden", True, "pw")
    assert manager.openFile(str(target), "wrong") == -1


def test_open_encrypted_with_passphrase_succeeds(
    manager: DocumentManager, doc: Document, tmp_path: Path
) -> None:
    target = tmp_path / "secret.txt"
    doc.saveAs(str(target), "hidden", True, "pw")
    assert manager.openFile(str(target), "pw") == 0
    assert manager.documentAt(0).takeContent() == "hidden"


def test_requires_passphrase_detects_container(
    manager: DocumentManager, doc: Document, tmp_path: Path
) -> None:
    secret = tmp_path / "secret.txt"
    plain = tmp_path / "plain.txt"
    doc.saveAs(str(secret), "hidden", True, "pw")
    plain.write_text("hello", encoding="utf-8")
    assert manager.requiresPassphrase(str(secret))
    assert not manager.requiresPassphrase(str(plain))
    assert not manager.requiresPassphrase(str(tmp_path / "nope.txt"))


def test_index_of_path(manager: DocumentManager, tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    target.write_text("hello", encoding="utf-8")
    manager.openFile(str(target))
    assert manager.indexOfPath(str(target)) == 0
    assert manager.indexOfPath(str(tmp_path / "other.txt")) == -1


def test_index_of_document(manager: DocumentManager) -> None:
    manager.newDocument()
    document = manager.documentAt(0)
    assert manager.indexOf(document) == 0
    assert manager.indexOf(Document("orphan")) == -1


def test_document_at_out_of_range(manager: DocumentManager) -> None:
    assert manager.documentAt(5) is None
    assert manager.documentAt(-1) is None


def test_close_document_updates_current_index(manager: DocumentManager) -> None:
    manager.newDocument()
    manager.newDocument()
    assert manager.closeDocument(1)
    assert manager.count == 1
    assert manager.currentIndex == 0


def test_close_non_current_document_preserves_active_document(manager: DocumentManager) -> None:
    manager.newDocument()
    manager.newDocument()
    active_index = manager.newDocument()
    active_document = manager.currentDocument

    assert manager.closeDocument(0)
    assert manager.currentIndex == active_index - 1
    assert manager.currentDocument is active_document


def test_close_document_after_active_document_preserves_active_index(manager: DocumentManager) -> None:
    manager.newDocument()
    manager.newDocument()
    manager.newDocument()
    manager.currentIndex = 0

    assert manager.closeDocument(2)
    assert manager.currentIndex == 0


def test_close_last_document_clears_index(manager: DocumentManager) -> None:
    manager.newDocument()
    manager.closeDocument(0)
    assert manager.count == 0
    assert manager.currentIndex == -1


def test_close_invalid_index(manager: DocumentManager) -> None:
    assert manager.closeDocument(3) is False


def test_close_all(manager: DocumentManager) -> None:
    manager.newDocument()
    manager.newDocument()
    manager.closeAll()
    assert manager.count == 0
    assert manager.currentIndex == -1


def test_current_index_is_clamped(manager: DocumentManager) -> None:
    manager.newDocument()
    manager.currentIndex = 99
    assert manager.currentIndex == 0
    manager.currentIndex = -99
    assert manager.currentIndex == -1


def test_has_modified_documents(manager: DocumentManager) -> None:
    manager.newDocument()
    assert not manager.hasModifiedDocuments
    manager.documentAt(0).modified = True
    assert manager.hasModifiedDocuments
