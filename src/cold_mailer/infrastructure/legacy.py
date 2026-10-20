"""Explicit, read-only legacy account import. Never creates or replaces old keys."""

import sqlite3
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from cold_mailer.domain.models import ValidationError
from cold_mailer.infrastructure.smtp import SenderAccount


def read_legacy_accounts(database: Path, key: Path) -> list[SenderAccount]:
    if not database.is_file() or not key.is_file():
        raise ValidationError("Both the legacy database and its existing key are required.")
    try:
        fernet = Fernet(key.read_bytes())
        connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            connection.row_factory = sqlite3.Row
            return [
                SenderAccount(
                    row["id"],
                    row["email"],
                    row["smtp_server"],
                    row["port"],
                    row["username"],
                    fernet.decrypt(row["encrypted_password"].encode()).decode(),
                )
                for row in connection.execute("SELECT * FROM sender_accounts")
            ]
        finally:
            connection.close()
    except OSError, sqlite3.Error, InvalidToken, ValueError:
        raise ValidationError(
            "Legacy import failed. Verify the database/key pair; neither file was changed."
        ) from None
