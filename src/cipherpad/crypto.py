"""Passphrase-based file encryption.

Container layout (all integers little-endian)::

    offset  size  field
    0       8     magic b"QMLENC\\x01\\x00"
    8       1     kdf id (1 = scrypt)
    9       1     log2(N) for scrypt
    10      1     scrypt r
    11      1     scrypt p
    12      16    salt
    28      12    AES-GCM nonce
    40      ...   AES-256-GCM ciphertext with appended 16 byte tag

The 40 byte header is passed to AES-GCM as additional authenticated data, so
tampering with the KDF parameters is detected during decryption.
"""

from __future__ import annotations

import hmac
import os
import struct
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from PySide6.QtCore import QObject, Slot
from PySide6.QtQml import QmlElement

QML_IMPORT_NAME = "Cipherpad"
QML_IMPORT_MAJOR_VERSION = 1

MAGIC = b"QMLENC\x01\x00"
KDF_SCRYPT = 1

SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32
HEADER_SIZE = len(MAGIC) + 4 + SALT_SIZE + NONCE_SIZE

# 2**15 iterations keeps interactive unlocking well under a second while still
# being an expensive target for offline guessing.
DEFAULT_LOG_N = 15
DEFAULT_R = 8
DEFAULT_P = 1

# Guard rail so a corrupt/hostile header cannot make us allocate gigabytes.
MAX_LOG_N = 22


class CryptoError(Exception):
    """Base class for encryption failures."""


class InvalidPassphrase(CryptoError):
    """Raised when a container cannot be authenticated with the passphrase."""


class InvalidContainer(CryptoError):
    """Raised when the data is not a well-formed encrypted container."""


@dataclass(frozen=True)
class KdfParams:
    log_n: int = DEFAULT_LOG_N
    r: int = DEFAULT_R
    p: int = DEFAULT_P

    def validate(self) -> None:
        if not 1 <= self.log_n <= MAX_LOG_N:
            raise InvalidContainer(f"unsupported scrypt cost parameter: 2**{self.log_n}")
        if not 1 <= self.r <= 255 or not 1 <= self.p <= 255:
            raise InvalidContainer("unsupported scrypt r/p parameters")


def is_encrypted(data: bytes) -> bool:
    """Return True when *data* starts with the container magic."""
    return data[: len(MAGIC)] == MAGIC


def _derive_key(passphrase: str, salt: bytes, params: KdfParams) -> bytes:
    params.validate()
    kdf = Scrypt(salt=salt, length=KEY_SIZE, n=2**params.log_n, r=params.r, p=params.p)
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt(plaintext: bytes, passphrase: str, params: KdfParams | None = None) -> bytes:
    """Encrypt *plaintext* into a self-describing container."""
    if not passphrase:
        raise CryptoError("A passphrase is required to encrypt a file.")

    params = params or KdfParams()
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    header = MAGIC + struct.pack("<BBBB", KDF_SCRYPT, params.log_n, params.r, params.p) + salt + nonce

    key = _derive_key(passphrase, salt, params)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, header)
    return header + ciphertext


def decrypt(data: bytes, passphrase: str) -> bytes:
    """Decrypt a container produced by :func:`encrypt`."""
    if not is_encrypted(data):
        raise InvalidContainer("File is not an encrypted Cipherpad container.")
    if len(data) < HEADER_SIZE + 16:
        raise InvalidContainer("Encrypted file is truncated.")

    header = data[:HEADER_SIZE]
    kdf_id, log_n, r, p = struct.unpack("<BBBB", header[len(MAGIC) : len(MAGIC) + 4])
    if kdf_id != KDF_SCRYPT:
        raise InvalidContainer(f"Unsupported key derivation function id {kdf_id}.")

    salt = header[len(MAGIC) + 4 : len(MAGIC) + 4 + SALT_SIZE]
    nonce = header[len(MAGIC) + 4 + SALT_SIZE :]

    key = _derive_key(passphrase, salt, KdfParams(log_n, r, p))
    try:
        return AESGCM(key).decrypt(nonce, data[HEADER_SIZE:], header)
    except InvalidTag as exc:
        raise InvalidPassphrase("Incorrect passphrase, or the file has been modified.") from exc


def passphrase_strength(passphrase: str) -> tuple[int, str]:
    """Score a passphrase from 0-4 with a short human readable label.

    Deliberately simple: length dominates, character variety refines. The goal
    is to nudge users away from short passphrases, not to be an oracle.
    """
    if not passphrase:
        return 0, "Empty"

    classes = sum(
        (
            any(c.islower() for c in passphrase),
            any(c.isupper() for c in passphrase),
            any(c.isdigit() for c in passphrase),
            any(not c.isalnum() for c in passphrase),
        )
    )
    length = len(passphrase)

    if length < 8:
        score = 0
    elif length < 12:
        score = 1 + (classes >= 3)
    elif length < 16:
        score = 2 + (classes >= 3)
    elif length < 24:
        score = 3
    else:
        score = 4
    score = max(0, min(4, score))
    return score, ("Very weak", "Weak", "Fair", "Strong", "Very strong")[score]


def constant_time_equals(a: str, b: str) -> bool:
    """Compare two passphrases without leaking length/content via timing."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


@QmlElement
class CryptoInfo(QObject):
    """Read-only crypto helpers for QML (no key material crosses this line)."""

    @Slot(str, result="QVariantList")
    def passphraseStrength(self, passphrase: str) -> list:
        score, label = passphrase_strength(passphrase)
        return [score, label]

    @Slot(result=str)
    def algorithm(self) -> str:
        return "AES-256-GCM / scrypt"
