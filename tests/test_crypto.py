"""Tests for the passphrase-based container format."""

from __future__ import annotations

import pytest

from cipherpad import crypto


def test_roundtrip_preserves_payload() -> None:
    payload = "héllo wörld\nsecond line\n".encode("utf-8")
    blob = crypto.encrypt(payload, "correct horse battery staple")
    assert blob != payload
    assert crypto.decrypt(blob, "correct horse battery staple") == payload


def test_container_is_recognisable() -> None:
    blob = crypto.encrypt(b"data", "pw")
    assert blob.startswith(crypto.MAGIC)
    assert crypto.is_encrypted(blob)
    assert not crypto.is_encrypted(b"plain text file")
    assert not crypto.is_encrypted(b"")


def test_ciphertext_is_randomised() -> None:
    first = crypto.encrypt(b"same", "pw")
    second = crypto.encrypt(b"same", "pw")
    assert first != second, "salt/nonce must be random per encryption"
    assert crypto.decrypt(first, "pw") == crypto.decrypt(second, "pw")


def test_wrong_passphrase_is_rejected() -> None:
    blob = crypto.encrypt(b"secret", "right")
    with pytest.raises(crypto.InvalidPassphrase):
        crypto.decrypt(blob, "wrong")


def test_empty_passphrase_is_rejected() -> None:
    with pytest.raises(crypto.CryptoError):
        crypto.encrypt(b"secret", "")


def test_tampered_ciphertext_is_detected() -> None:
    blob = bytearray(crypto.encrypt(b"secret payload", "pw"))
    blob[-1] ^= 0xFF
    with pytest.raises(crypto.InvalidPassphrase):
        crypto.decrypt(bytes(blob), "pw")


def test_tampered_header_is_detected() -> None:
    """The header is authenticated as AAD, so KDF downgrades are caught."""
    blob = bytearray(crypto.encrypt(b"secret payload", "pw"))
    blob[9] = 14  # log2(N): 15 -> 14
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt(bytes(blob), "pw")


def test_truncated_container_is_rejected() -> None:
    blob = crypto.encrypt(b"secret", "pw")
    with pytest.raises(crypto.InvalidContainer):
        crypto.decrypt(blob[: crypto.HEADER_SIZE - 1], "pw")


def test_non_container_is_rejected() -> None:
    with pytest.raises(crypto.InvalidContainer):
        crypto.decrypt(b"this is not an encrypted file at all", "pw")


def test_absurd_kdf_cost_is_refused() -> None:
    blob = bytearray(crypto.encrypt(b"secret", "pw"))
    blob[9] = crypto.MAX_LOG_N + 1
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt(bytes(blob), "pw")


def test_empty_payload_roundtrips() -> None:
    blob = crypto.encrypt(b"", "pw")
    assert crypto.decrypt(blob, "pw") == b""


@pytest.mark.parametrize(
    ("passphrase", "minimum"),
    [("", 0), ("abc", 0), ("password", 0), ("Tr0ub4dor&3xyz", 2), ("a-very-long-diceware-style-phrase-42", 3)],
)
def test_passphrase_strength_is_monotonic_enough(passphrase: str, minimum: int) -> None:
    score, label = crypto.passphrase_strength(passphrase)
    assert 0 <= score <= 4
    assert label
    assert score >= minimum


def test_constant_time_equals() -> None:
    assert crypto.constant_time_equals("abc", "abc")
    assert not crypto.constant_time_equals("abc", "abd")
    assert not crypto.constant_time_equals("abc", "abcd")


def test_qml_facade(qt_app) -> None:  # noqa: ANN001
    info = crypto.CryptoInfo()
    score, label = info.passphraseStrength("Tr0ub4dor&3xyz")
    assert isinstance(score, int)
    assert isinstance(label, str)
    assert "AES" in info.algorithm()
