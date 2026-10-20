"""Versioned portable backup envelope with authenticated encryption and bounded KDF."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from cold_mailer.domain.models import ValidationError
from cold_mailer.infrastructure.storage import Store

MAGIC = b"CMAILBACKUP\x01"
MAX_BYTES = 256 * 1024 * 1024


def derive(passphrase: str, salt: bytes) -> bytes:
    if len(passphrase) < 12 or len(passphrase) > 1024:
        raise ValidationError(
            "Use a backup passphrase of 12-1024 characters. It cannot be recovered if lost."
        )
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode("utf-8"))


def encrypted_backup(store: Store, destination: Path, passphrase: str) -> None:
    salt, nonce = os.urandom(16), os.urandom(12)
    key = derive(passphrase, salt)
    if destination.exists():
        raise ValidationError("Choose a new backup filename.")
    with TemporaryDirectory(prefix="cold-mailer-backup-") as temporary:
        database = Path(temporary) / "profile.sqlite3"
        store.backup(database)
        if database.stat().st_size > MAX_BYTES:
            raise ValidationError("Encrypted backup exceeds the 256 MiB limit.")
        envelope = MAGIC + salt + nonce
        encrypted = AESGCM(key).encrypt(nonce, database.read_bytes(), envelope)
        with destination.open("xb") as stream:
            stream.write(envelope + encrypted)


def restore_encrypted(source: Path, destination: Path, passphrase: str) -> None:
    if source.stat().st_size > MAX_BYTES + 128:
        raise ValidationError("Backup exceeds the supported size limit.")
    envelope = source.read_bytes()
    prefix = len(MAGIC) + 28
    if not envelope.startswith(MAGIC) or len(envelope) < prefix + 16:
        raise ValidationError("Unsupported or truncated encrypted backup.")
    salt = envelope[len(MAGIC) : len(MAGIC) + 16]
    nonce = envelope[len(MAGIC) + 16 : prefix]
    try:
        raw = AESGCM(derive(passphrase, salt)).decrypt(nonce, envelope[prefix:], envelope[:prefix])
    except InvalidTag:
        raise ValidationError(
            "Incorrect passphrase or damaged backup. No profile was restored."
        ) from None
    with TemporaryDirectory(prefix="cold-mailer-restore-") as temporary:
        database = Path(temporary) / "profile.sqlite3"
        database.write_bytes(raw)
        Store.restore(database, destination)
