"""OS-backed secrets and an explicitly injected in-memory test implementation."""

from __future__ import annotations

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from cold_mailer.domain.models import ValidationError


class OSKeyring:
    def __init__(self, profile: str) -> None:
        self.service = "ColdMailer:" + profile

    def get(self, reference: str) -> str | None:
        try:
            return keyring.get_password(self.service, reference)
        except KeyringError:
            raise ValidationError(
                "OS credential storage is unavailable. Check your user session."
            ) from None

    def set(self, reference: str, value: str) -> None:
        if not value:
            raise ValidationError("A nonempty password is required.")
        try:
            keyring.set_password(self.service, reference, value)
        except KeyringError:
            raise ValidationError("Could not save to OS credential storage.") from None

    def delete(self, reference: str) -> None:
        try:
            keyring.delete_password(self.service, reference)
        except PasswordDeleteError:
            pass
        except KeyringError:
            raise ValidationError("Could not remove the OS credential.") from None


class MemoryCredentials:
    """Tests inject this explicitly; production never falls back to plaintext storage."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def get(self, reference: str) -> str | None:
        return self._values.get(reference)

    def set(self, reference: str, value: str) -> None:
        self._values[reference] = value

    def delete(self, reference: str) -> None:
        self._values.pop(reference, None)
